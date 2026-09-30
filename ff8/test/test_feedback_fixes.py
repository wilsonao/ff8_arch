"""Regression tests for the Sep 2026 beta-feedback fixes (docs/plan-beta-feedback-2026-09.md).

1. A faked story moment must never outlive the client: error paths restore
   it, a sidecar record repairs a fake that did survive (even one baked into
   a save), and field-origin battles are never faked at all.
2. First Draw checks: a drawn-once bit that the game sets for multiworld-
   granted stock is housekeeping, not a draw; a real draw is recognised by
   the stock rising or a matching draw point emptying.
3. Battle tracking starts only in module 3 — a POST_BATTLE pulse outside
   combat (Triple Triad) must not replay "Battle won" with a stale id.
4. Gil Snatch can empty the purse (no floor, by design); is_safe excludes the title screen; the legacy
   slot-only save fingerprint is still accepted.
"""

import unittest
from unittest import mock

from .. import memory
from ..items import BASE_ID
from ..memory import (GAME_MOMENT, IN_MENU, MODULE_DISPATCH, POST_BATTLE,
                      MAGIC_DRAWN, DRAW_POINTS, CHAR_BASE, CHAR_STRIDE,
                      CHAR_MAGIC_OFFSET, BATTLE_ALLIES, ALLY_STRIDE,
                      ALLY_CUR_HP, ALLY_MAX_HP, ENCOUNTER_ID)
from ..client import (abandon_fake, fingerprint_ok, repair_leaked_moment,
                      resolve_pending_draws, restore_true_moment, track_battle,
                      update_moment_window, VEHICLE_GRANTS,
                      VEHICLE_FAKE_MARGIN)
from .test_vehicle_window import FakeClock, FakeCtx as WindowCtx, FakeProc

FAKE = VEHICLE_GRANTS["ragnarok"][3] + VEHICLE_FAKE_MARGIN


class RecordingCtx(WindowCtx):
    """Window ctx that also records sidecar writes like the real context."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.fake_record = None
        self.sidecar_writes = 0
        self.max_moment = 0

    def save_sidecar(self):
        self.sidecar_writes += 1


class TestMomentLeak(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        p = mock.patch("worlds.ff8.client.time", self.clock)
        p.start()
        self.addCleanup(p.stop)

    def _fake_in_battle(self, ctx, moment=205):
        ctx.set_state(module=3, moment=moment)
        update_moment_window(ctx)
        self.assertTrue(ctx.moment_faked)
        self.assertEqual(ctx.ff8.game_moment(), FAKE)

    def test_fake_is_recorded_and_cleared_in_sidecar(self):
        ctx = RecordingCtx()
        self._fake_in_battle(ctx)
        self.assertEqual(ctx.fake_record, (205, FAKE))
        self.assertGreaterEqual(ctx.sidecar_writes, 1)
        restore_true_moment(ctx)
        self.assertIsNone(ctx.fake_record)
        self.assertEqual(ctx.ff8.game_moment(), 205)

    def test_abandon_fake_restores_when_process_is_alive(self):
        # the old error path dropped the state and left the fake in memory
        ctx = RecordingCtx()
        self._fake_in_battle(ctx)
        abandon_fake(ctx)
        self.assertFalse(ctx.moment_faked)
        self.assertEqual(ctx.ff8.game_moment(), 205)
        self.assertIsNone(ctx.fake_record)

    def test_abandon_fake_keeps_record_when_write_fails(self):
        ctx = RecordingCtx()
        self._fake_in_battle(ctx)
        with mock.patch.object(ctx.ff8, "write_u16", side_effect=OSError("gone")):
            abandon_fake(ctx)
        self.assertFalse(ctx.moment_faked)
        self.assertEqual(ctx.fake_record, (205, FAKE))   # repair can finish later

    def test_repair_after_interrupted_fake(self):
        # client died mid-fake; a new client (fresh state, sidecar record) sees
        # the fake value live -> writes the truth back, once
        ctx = RecordingCtx()
        ctx.fake_record = (205, FAKE)
        ctx.set_state(module=2, moment=FAKE)      # e.g. a save that captured it
        update_moment_window(ctx)
        self.assertEqual(ctx.ff8.game_moment(), 205)
        self.assertIsNone(ctx.fake_record)
        self.assertFalse(ctx.moment_faked)

    def test_repair_ignores_other_values(self):
        ctx = RecordingCtx()
        ctx.fake_record = (205, FAKE)
        for live in (205, 300, FAKE + 1):
            ctx.set_state(module=2, moment=live)
            self.assertFalse(repair_leaked_moment(ctx, live))
            self.assertEqual(ctx.ff8.game_moment(), live)
        self.assertEqual(ctx.fake_record, (205, FAKE))

    def test_field_battle_is_never_faked(self):
        # a boss fought from a field returns to field scripts that read the
        # moment on their first frames: no fake, no grace
        ctx = RecordingCtx()
        ctx.set_state(module=1, moment=205)
        update_moment_window(ctx)
        ctx.ff8.write_u16(MODULE_DISPATCH, 3)
        update_moment_window(ctx)
        self.assertFalse(ctx.moment_faked)
        self.assertEqual(ctx.ff8.game_moment(), 205)
        ctx.ff8.write_u16(MODULE_DISPATCH, 1)     # back to the field
        update_moment_window(ctx)
        self.assertFalse(ctx.moment_faked)

    def test_worldmap_battle_is_faked(self):
        ctx = RecordingCtx()
        ctx.set_state(module=2, moment=205)
        update_moment_window(ctx)
        ctx.ff8.write_u16(MODULE_DISPATCH, 3)
        update_moment_window(ctx)
        self.assertTrue(ctx.moment_faked)


class DrawCtx:
    """Just what resolve_pending_draws / track_battle touch."""

    def __init__(self):
        self.ff8 = FakeProc()
        self.draw_point_defs = None
        self.magic_pending = set()
        self.magic_prev_totals = None
        self.draw_states_prev = None
        self.sidecar_writes = 0
        # battle tracking
        self.battle_active = False
        self.last_encounter = 0
        self.results_seen = False
        self.party_alive_seen = False
        self.battle_wiped = False
        self.won_encounters = set()
        self.last_battle_outcome = ""

    def save_sidecar(self):
        self.sidecar_writes += 1

    # helpers
    def set_stock(self, char, slot, spell, qty):
        base = CHAR_BASE + char * CHAR_STRIDE + CHAR_MAGIC_OFFSET + slot * 2
        self.ff8.write_u8(base, spell)
        self.ff8.write_u8(base + 1, qty)

    def set_drawn(self, spell, on=True):
        addr = MAGIC_DRAWN + (spell - 1) // 8
        mask = 1 << ((spell - 1) % 8)
        cur = self.ff8.read_u8(addr)
        self.ff8.write_u8(addr, cur | mask if on else cur & ~mask)

    def drawn(self, spell):
        return bool(self.ff8.read_u8(MAGIC_DRAWN + (spell - 1) // 8)
                    >> ((spell - 1) % 8) & 1)

    def set_draw_state(self, slot, state):
        addr = DRAW_POINTS + slot // 4
        shift = (slot % 4) * 2
        cur = self.ff8.read_u8(addr) & ~(3 << shift)
        self.ff8.write_u8(addr, cur | (state << shift))

    def tick(self):
        resolve_pending_draws(self, self.ff8.snapshot())


TRIPLE = 34


class TestFirstDrawAttribution(unittest.TestCase):
    def test_housekeeping_bit_is_cleared(self):
        ctx = DrawCtx()
        ctx.set_stock(0, 0, TRIPLE, 5)          # granted by the multiworld
        ctx.magic_pending.add(TRIPLE)
        ctx.tick()                              # baseline
        ctx.set_drawn(TRIPLE)                   # the game "notices" the stock
        ctx.tick()
        self.assertFalse(ctx.drawn(TRIPLE))     # cleared: not a draw
        self.assertIn(TRIPLE, ctx.magic_pending)

    def test_stock_rise_counts_as_real_draw(self):
        ctx = DrawCtx()
        ctx.set_stock(0, 0, TRIPLE, 5)
        ctx.magic_pending.add(TRIPLE)
        ctx.tick()
        ctx.set_stock(0, 0, TRIPLE, 9)          # drew 4 more in battle
        ctx.set_drawn(TRIPLE)
        ctx.tick()
        self.assertTrue(ctx.drawn(TRIPLE))
        self.assertNotIn(TRIPLE, ctx.magic_pending)
        self.assertEqual(ctx.sidecar_writes, 1)

    def test_matching_draw_point_counts_as_real_draw(self):
        ctx = DrawCtx()
        # slot 5 gives TRIPLE in this (fake) exe table
        defs = bytearray(memory.DRAW_POINT_DEFS_VANILLA)
        defs[5] = TRIPLE
        ctx.draw_point_defs = bytes(defs)
        ctx.set_stock(0, 0, TRIPLE, 5)
        ctx.magic_pending.add(TRIPLE)
        ctx.tick()
        ctx.set_draw_state(5, 2)                # the point emptied
        ctx.set_drawn(TRIPLE)                   # stock capped/cast: no rise
        ctx.tick()
        self.assertTrue(ctx.drawn(TRIPLE))
        self.assertNotIn(TRIPLE, ctx.magic_pending)

    def test_other_draw_point_does_not_count(self):
        ctx = DrawCtx()
        ctx.set_stock(0, 0, TRIPLE, 5)
        ctx.magic_pending.add(TRIPLE)
        ctx.tick()
        ctx.set_draw_state(0, 2)                # vanilla slot 0 is Cure
        ctx.set_drawn(TRIPLE)
        ctx.tick()
        self.assertFalse(ctx.drawn(TRIPLE))

    def test_non_pending_spells_are_untouched(self):
        ctx = DrawCtx()
        ctx.set_drawn(1)                        # Fire, drawn for real long ago
        ctx.tick()
        ctx.tick()
        self.assertTrue(ctx.drawn(1))


class TestBattleTracking(unittest.TestCase):
    def _alive(self, ctx):
        rec = BATTLE_ALLIES
        ctx.ff8.write_u16(rec + ALLY_CUR_HP, 500)
        ctx.ff8.write_u16(rec + ALLY_MAX_HP, 500)

    def test_post_battle_pulse_outside_combat_is_ignored(self):
        ctx = DrawCtx()
        ctx.ff8.write_u16(ENCOUNTER_ID, 514)    # stale world-map encounter
        ctx.ff8.write_u16(MODULE_DISPATCH, 1)   # a field: card game
        self._alive(ctx)
        for pulse in (1, 0, 1, 0):
            ctx.ff8.write_u8(POST_BATTLE, pulse)
            track_battle(ctx)
        self.assertFalse(ctx.battle_active)
        self.assertNotIn(514, ctx.won_encounters)
        self.assertEqual(ctx.last_battle_outcome, "")

    def test_real_win_is_still_credited(self):
        ctx = DrawCtx()
        ctx.ff8.write_u16(ENCOUNTER_ID, 190)
        self._alive(ctx)
        ctx.ff8.write_u16(MODULE_DISPATCH, 3)   # combat
        track_battle(ctx)
        ctx.ff8.write_u16(MODULE_DISPATCH, 100)  # victory transition
        ctx.ff8.write_u8(POST_BATTLE, 1)
        track_battle(ctx)
        ctx.ff8.write_u16(MODULE_DISPATCH, 4)    # results
        track_battle(ctx)
        ctx.ff8.write_u16(MODULE_DISPATCH, 2)    # back to the world map
        ctx.ff8.write_u8(POST_BATTLE, 0)
        track_battle(ctx)
        self.assertEqual(ctx.last_battle_outcome, "won")
        self.assertIn(190, ctx.won_encounters)


class TestSmallFixes(unittest.TestCase):
    def test_gil_trap_has_no_floor(self):
        # A floor (3000, the Timber fare) was tried and taken back out: being
        # robbed blind before the train is the point of the trap.
        ff8 = FakeProc()
        ff8.write_u32(memory.GIL, 4000)
        self.assertEqual(ff8.take_gil(1500), 1500)
        self.assertEqual(ff8.read_u32(memory.GIL), 2500)
        self.assertEqual(ff8.take_gil(1500), 1500)
        self.assertEqual(ff8.take_gil(1500), 1000)
        self.assertEqual(ff8.read_u32(memory.GIL), 0)
        self.assertEqual(ff8.take_gil(1500), 0)

    def test_is_safe_excludes_title_screen(self):
        ff8 = FakeProc()
        ff8.write_u16(GAME_MOMENT, 400)         # last loaded save still in RAM
        ff8.write_u16(MODULE_DISPATCH, memory.MODULE_TITLE)
        self.assertFalse(ff8.is_safe())
        ff8.write_u16(MODULE_DISPATCH, memory.MODULE_FIELD)
        self.assertTrue(ff8.is_safe())

    def test_fingerprint_accepts_seed_keyed_and_legacy(self):
        ctx = mock.Mock(save_fingerprint=0x11111111, legacy_fingerprint=0x22222222)
        self.assertTrue(fingerprint_ok(ctx, 0x11111111))
        self.assertTrue(fingerprint_ok(ctx, 0x22222222))
        self.assertFalse(fingerprint_ok(ctx, 0x33333333))
        ctx.legacy_fingerprint = 0
        self.assertFalse(fingerprint_ok(ctx, 0))


if __name__ == "__main__":
    unittest.main()
