"""Checks-only magic enforcement + the refined_magic option, against a fake
process.

The client can never watch a refine happen: menus are unsafe ticks, so
enforce_magic only sees the accumulated stock delta on the next safe tick.
What distinguishes a refine from a draw is the shape of the unsafe gap the
delta arrived in — a menu was open (refines only happen there), no battle ran
(no draws could have mixed in), and inventory items were spent (every
...Mag-RF consumes items; draws never do). These tests pin that evidence
chain: each leg missing must mean repossession, all three present must mean
the cap absorbs the increase.
"""

import unittest

from ..memory import (CHAR_BASE, CHAR_MAGIC_OFFSET, GAME_MOMENT, IN_MENU,
                      INVENTORY)
from ..client import enforce_magic, track_refine_window
from .test_vehicle_window import FakeProc

FIRE = 1      # any spell id; names only affect log text
POTION = 1    # any item id


def set_magic(ff8, sid, qty, slot=0):
    ff8.write_bytes(CHAR_BASE + CHAR_MAGIC_OFFSET + slot * 2,
                    bytes([sid, qty]))


def set_item(ff8, iid, qty, slot=0):
    ff8.write_bytes(INVENTORY + slot * 2, bytes([iid, qty]))


class FakeCtx:
    """Just the attributes enforce_magic / track_refine_window touch."""

    def __init__(self, refined=True, checks_only=True):
        self.ff8 = FakeProc()
        self.slot_data = {"magic_mode": 1 if checks_only else 0,
                          "refined_magic": 1 if refined else 0}
        self.save_frozen = None
        self.magic_expected = None
        self.magic_last_moment = 0
        self.refine_menu_seen = False
        self.refine_battle_seen = False
        self.magic_prev_items = None
        self.moment_faked = False
        self.true_moment = None
        self.battle_active = False
        self.ff8.write_u16(GAME_MOMENT, 100)


def baselined_ctx(**kwargs):
    """A ctx whose ledger is settled: Fire x5 stocked, 3 Potions held."""
    ctx = FakeCtx(**kwargs)
    set_magic(ctx.ff8, FIRE, 5)
    set_item(ctx.ff8, POTION, 3)
    enforce_magic(ctx)               # baseline tick
    return ctx


def menu_tick(ctx):
    """One unsafe tick with the menu open."""
    ctx.ff8.write_u8(IN_MENU, 1)
    track_refine_window(ctx)
    ctx.ff8.write_u8(IN_MENU, 0)


def battle_tick(ctx):
    ctx.battle_active = True
    track_refine_window(ctx)
    ctx.battle_active = False


def fire_stock(ctx):
    return ctx.ff8.snapshot().magic_totals().get(FIRE, 0)


class TestRefineKept(unittest.TestCase):
    def test_refine_signature_absorbs_into_cap(self):
        ctx = baselined_ctx()
        menu_tick(ctx)
        set_item(ctx.ff8, POTION, 1)     # 2 Potions spent...
        set_magic(ctx.ff8, FIRE, 9)      # ...refined into +4 Fire
        enforce_magic(ctx)
        self.assertEqual(fire_stock(ctx), 9)
        self.assertEqual(ctx.magic_expected[FIRE], 9)
        # the raise is permanent: later ticks leave it alone
        enforce_magic(ctx)
        self.assertEqual(fire_stock(ctx), 9)

    def test_raised_cap_allows_redraw_after_casting(self):
        ctx = baselined_ctx()
        menu_tick(ctx)
        set_item(ctx.ff8, POTION, 1)
        set_magic(ctx.ff8, FIRE, 9)
        enforce_magic(ctx)
        set_magic(ctx.ff8, FIRE, 4)      # cast some off
        enforce_magic(ctx)
        set_magic(ctx.ff8, FIRE, 9)      # drawn back up to the raised cap
        enforce_magic(ctx)
        self.assertEqual(fire_stock(ctx), 9)
        set_magic(ctx.ff8, FIRE, 12)     # drawn past it
        enforce_magic(ctx)
        self.assertEqual(fire_stock(ctx), 9)

    def test_flags_are_consumed_by_the_enforcement_tick(self):
        ctx = baselined_ctx()
        menu_tick(ctx)
        set_item(ctx.ff8, POTION, 1)
        enforce_magic(ctx)               # menu session ends, nothing refined
        set_magic(ctx.ff8, FIRE, 9)      # a later draw (no menu since)
        enforce_magic(ctx)
        self.assertEqual(fire_stock(ctx), 5)


class TestRepossessedAnyway(unittest.TestCase):
    def test_draw_without_menu(self):
        ctx = baselined_ctx()
        set_magic(ctx.ff8, FIRE, 9)
        enforce_magic(ctx)
        self.assertEqual(fire_stock(ctx), 5)

    def test_menu_but_no_item_spent(self):
        # a draw whose UI trips the menu flag (field draw point) spends nothing
        ctx = baselined_ctx()
        menu_tick(ctx)
        set_magic(ctx.ff8, FIRE, 9)
        enforce_magic(ctx)
        self.assertEqual(fire_stock(ctx), 5)

    def test_menu_but_battle_in_the_same_gap(self):
        # battle draws could have mixed into the delta: keep nothing
        ctx = baselined_ctx()
        menu_tick(ctx)
        battle_tick(ctx)
        set_item(ctx.ff8, POTION, 1)
        set_magic(ctx.ff8, FIRE, 9)
        enforce_magic(ctx)
        self.assertEqual(fire_stock(ctx), 5)

    def test_option_off(self):
        ctx = baselined_ctx(refined=False)
        ctx.ff8.write_u8(IN_MENU, 1)
        track_refine_window(ctx)         # option off: not even tracked
        ctx.ff8.write_u8(IN_MENU, 0)
        self.assertFalse(ctx.refine_menu_seen)
        set_item(ctx.ff8, POTION, 1)
        set_magic(ctx.ff8, FIRE, 9)
        enforce_magic(ctx)
        self.assertEqual(fire_stock(ctx), 5)


class TestVanillaMode(unittest.TestCase):
    def test_enforcement_never_runs(self):
        ctx = FakeCtx(checks_only=False)
        set_magic(ctx.ff8, FIRE, 5)
        enforce_magic(ctx)
        set_magic(ctx.ff8, FIRE, 99)
        enforce_magic(ctx)
        self.assertEqual(fire_stock(ctx), 99)
        self.assertIsNone(ctx.magic_expected)


if __name__ == "__main__":
    unittest.main()
