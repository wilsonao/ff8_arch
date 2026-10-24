"""Regression tests for the Discord reports of 6-10 Oct 2026.

1. "Weapon Remodel" checks read the junk shop's LIST bitmask, so they went out
   when a recipe became listed and a real remodel gave nothing. They follow
   the weapon each character holds.
2. A used Magical Lamp was handed straight back: its check was only "sent"
   once the server had answered, and the item menu has safe ticks.
3. A game closed and restarted left the client holding a dead process while no
   slot was connected ("Attached, but reads are failing").
4. A draw point's spell rename followed the party into the main menu, and its
   description could be cut down to "Esuna - for".
5. Fast Travel announced story-locked destinations as usable.
6. /ff8 says which AP multiplier, Enemy Power and card rules the seed has.
7. Three groups of draw points sat in the wrong story chapter.

The "Another save was loaded" false alarm at tutorials is covered in
test_story_jump.py, beside the load detection it changes.
"""

import asyncio
import unittest
from unittest import mock

from .. import memory, text
from ..client import (FF8CommandProcessor, FF8Context, ITEM_HANDOUT_LOCS,
                      KEY_ITEM_GATES, drop_spent_key_item, game_watcher,
                      grant_items, maintain_warp_crystal, option_summary,
                      restore_spell_names_in_battle, send_checks,
                      trigger_satisfied)
from ..fields import DRAW_POINT_FIELDS, FIELD_NAMES
from ..items import BASE_ID, ITEM_TABLE, MAGICAL_LAMP_GAME_ID
from ..locations import DRAW_POINT_TABLE, LOCATION_DATA_BY_NAME, LOCATION_TABLE
from ..memory import (CHAR_BASE, CHAR_STRIDE, CHAR_WEAPON_OFFSET, GAME_MOMENT,
                      IN_MENU, MODULE_DISPATCH, WEAPONS_UNLOCKED)
from .test_feedback_fixes import WarpCtx
from .test_text import kernel_proc
from .test_vehicle_window import FakeProc

LAMP_ITEM = next(BASE_ID + d.id_offset for d in ITEM_TABLE if d.name == "Magical Lamp")
DIABLOS_CHECK = KEY_ITEM_GATES[MAGICAL_LAMP_GAME_ID]
CID_CHECK = BASE_ID + LOCATION_DATA_BY_NAME["Cid's Parting Gift"].id_offset


def weapon(ff8, char, weapon_id):
    ff8.write_u8(CHAR_BASE + char * CHAR_STRIDE + CHAR_WEAPON_OFFSET, weapon_id)


def fires(ff8, name):
    return any(trigger_satisfied(None, k, v, ff8.snapshot(), [], {})
               for k, v in LOCATION_DATA_BY_NAME[name].triggers)


class TestWeaponRemodel(unittest.TestCase):
    def setUp(self):
        self.ff8 = FakeProc()
        for char, base in enumerate((0, 7, 11, 15, 19, 24)):
            weapon(self.ff8, char, base)

    def test_a_listed_recipe_is_not_a_remodel(self):
        # every weapon listed in the junk shop, nothing made
        self.ff8.write_u32(WEAPONS_UNLOCKED, 0x0FFFFFFF)
        for loc in LOCATION_TABLE:
            if loc.name.startswith(("Weapon Remodel:", "Ultimate Weapon:")):
                self.assertFalse(fires(self.ff8, loc.name), loc.name)

    def test_the_weapon_in_hand_sends_the_check(self):
        weapon(self.ff8, 0, 1)                      # Shear Trigger
        self.assertTrue(fires(self.ff8, "Weapon Remodel: Squall"))
        self.assertFalse(fires(self.ff8, "Ultimate Weapon: Lion Heart (Squall)"))
        self.assertFalse(fires(self.ff8, "Weapon Remodel: Zell"))
        weapon(self.ff8, 0, 6)                      # straight to Lion Heart
        self.assertTrue(fires(self.ff8, "Weapon Remodel: Squall"))
        self.assertTrue(fires(self.ff8, "Ultimate Weapon: Lion Heart (Squall)"))

    def test_each_character_reads_its_own_record_and_range(self):
        for char, (name, first, top) in enumerate((
                ("Squall", 1, 6), ("Zell", 8, 10), ("Irvine", 12, 14),
                ("Quistis", 16, 18), ("Rinoa", 20, 23), ("Selphie", 25, 27))):
            self.assertFalse(fires(self.ff8, f"Weapon Remodel: {name}"), name)
            weapon(self.ff8, char, first)
            self.assertTrue(fires(self.ff8, f"Weapon Remodel: {name}"), name)
            ultimate = next(n for n in LOCATION_DATA_BY_NAME
                            if n.startswith("Ultimate Weapon:") and n.endswith(f"({name})"))
            self.assertFalse(fires(self.ff8, ultimate), name)
            weapon(self.ff8, char, top)
            self.assertTrue(fires(self.ff8, ultimate), name)


def lamp_ctx(steps):
    """Run steps(ctx) on a real context holding a delivered Magical Lamp."""
    async def go():
        ctx = FF8Context(None, None)
        ctx.ff8 = FakeProc()
        ctx.slot = 1
        ctx.slot_data = {}
        ctx.send_msgs = mock.AsyncMock()
        ctx.save_fingerprint = 0x1234
        ctx.items_received = [mock.Mock(item=LAMP_ITEM, player=1)]
        ctx.missing_locations = {DIABLOS_CHECK, CID_CHECK}
        ctx.ff8.write_u16(GAME_MOMENT, 60)
        ctx.ff8.write_u16(MODULE_DISPATCH, memory.MODULE_FIELD)
        try:
            await grant_items(ctx)                  # delivery
            assert ctx.ff8.count_item(MAGICAL_LAMP_GAME_ID) == 1
            await steps(ctx)
        finally:
            await ctx.shutdown()
        return ctx
    return asyncio.run(go())


class TestSpentKeyItem(unittest.TestCase):
    def test_a_sent_check_counts_as_sent_in_the_same_tick(self):
        async def steps(ctx):
            await send_checks(ctx, [DIABLOS_CHECK])
        ctx = lamp_ctx(steps)
        self.assertIn(DIABLOS_CHECK, ctx.locations_checked)
        self.assertEqual(ctx.send_msgs.call_args.args[0][0]["cmd"], "LocationChecks")

    def test_a_used_lamp_is_not_handed_back_after_the_win(self):
        async def steps(ctx):
            ctx.ff8.remove_item(MAGICAL_LAMP_GAME_ID)          # used from the menu
            ctx.ff8.write_u16(MODULE_DISPATCH, memory.MODULE_MENU)
            await grant_items(ctx)                             # a safe tick in the menu
            self.assertEqual(ctx.ff8.count_item(MAGICAL_LAMP_GAME_ID), 0)
            ctx.ff8.write_u16(MODULE_DISPATCH, memory.MODULE_FIELD)
            await send_checks(ctx, [DIABLOS_CHECK])            # the fight is won
            await grant_items(ctx)                             # same tick
        ctx = lamp_ctx(steps)
        self.assertEqual(ctx.ff8.count_item(MAGICAL_LAMP_GAME_ID), 0)

    def test_a_lamp_missing_from_a_reloaded_save_still_comes_back(self):
        async def steps(ctx):
            ctx.ff8.remove_item(MAGICAL_LAMP_GAME_ID)
            await grant_items(ctx)
        ctx = lamp_ctx(steps)
        self.assertEqual(ctx.ff8.count_item(MAGICAL_LAMP_GAME_ID), 1)

    def test_a_spare_from_an_older_client_is_removed_once_no_handout_is_due(self):
        async def steps(ctx):
            ctx.missing_locations = {CID_CHECK}                # Diablos done
            ctx.checked_locations = {DIABLOS_CHECK}
            await grant_items(ctx)
            self.assertEqual(ctx.ff8.count_item(MAGICAL_LAMP_GAME_ID), 1)   # Cid's is still to come
            ctx.missing_locations = set()
            ctx.checked_locations = {DIABLOS_CHECK, CID_CHECK}
            with self.assertLogs("Client", level="INFO") as logs:
                await grant_items(ctx)
            self.assertIn("Magical Lamp", logs.output[0])
        ctx = lamp_ctx(steps)
        self.assertEqual(ctx.ff8.count_item(MAGICAL_LAMP_GAME_ID), 0)
        self.assertEqual(ctx.prev_item_counts.get(MAGICAL_LAMP_GAME_ID, 0), 0)

    def test_the_handout_table_names_both_key_items(self):
        self.assertEqual(ITEM_HANDOUT_LOCS[MAGICAL_LAMP_GAME_ID], [CID_CHECK])
        self.assertEqual(len(ITEM_HANDOUT_LOCS), 2)
        data = mock.Mock(grant=("item", MAGICAL_LAMP_GAME_ID, 1))
        ctx = mock.Mock(missing_locations={CID_CHECK}, locations_checked=set())
        drop_spent_key_item(ctx, data)
        ctx.ff8.remove_item.assert_not_called()


class DeadGame(memory.FF8Interface):
    """Attached to a process that has since exited: every read fails."""

    def __init__(self):
        super().__init__()
        self.pm = object()

    def read_u16(self, offset):
        raise OSError("ReadProcessMemory failed")

    def attach(self):
        return False


class TestStaleProcess(unittest.TestCase):
    def test_a_dead_handle_is_dropped_without_a_server_connection(self):
        async def go():
            ctx = FF8Context(None, None)
            ctx.ff8 = DeadGame()
            self.assertTrue(ctx.ff8.attached)
            with mock.patch.object(memory, "find_wrong_process", return_value=None), \
                    self.assertLogs("Client", level="INFO") as logs:
                task = asyncio.create_task(game_watcher(ctx))
                await asyncio.sleep(0.05)
                task.cancel()
            await ctx.shutdown()
            return ctx, logs.output
        ctx, lines = asyncio.run(go())
        self.assertFalse(ctx.ff8.attached)
        self.assertTrue(any("re-hooking" in line for line in lines))

    def test_ff8_names_the_failure_and_what_to_do(self):
        async def go():
            ctx = FF8Context(None, None)
            ctx.ff8 = DeadGame()
            proc = FF8CommandProcessor(ctx)
            out = []
            proc.output = out.append
            proc._cmd_ff8()
            await ctx.shutdown()
            return out
        out = asyncio.run(go())
        self.assertIn("OSError", out[0])
        self.assertIn("run /ff8 once more", out[0])


class TestSpellNamesOutsideTheField(unittest.TestCase):
    def setUp(self):
        self.ctx = mock.Mock()
        self.ctx.ff8 = kernel_proc()
        self.ctx.kernel_text = text.KernelText(self.ctx.ff8)
        self.esuna = text.MAGIC_NAMES.index("Esuna")
        self.ctx.kernel_text.apply("magic", {self.esuna: ("Giant's Tonic", "Esuna - for Bob")})

    def live_name(self):
        kt = self.ctx.kernel_text
        return text.TextTable(*kt.read_sections("magic"), 60).name(self.esuna)

    def test_the_rename_stays_on_the_field(self):
        self.ctx.ff8.write_u16(MODULE_DISPATCH, memory.MODULE_FIELD)
        restore_spell_names_in_battle(self.ctx)
        self.assertEqual(self.live_name(), "Giant's Tonic")

    def test_the_main_menu_and_battle_show_the_real_spell(self):
        for module in (memory.MODULE_MENU, memory.MODULE_BATTLE):
            self.ctx.kernel_text.apply("magic", {self.esuna: ("Giant's Tonic", "Esuna - for Bob")})
            self.ctx.ff8.write_u16(MODULE_DISPATCH, module)
            restore_spell_names_in_battle(self.ctx)
            self.assertEqual(self.live_name(), "Esuna", module)

    def test_a_description_is_never_cut_down_to_a_dangling_for(self):
        full = "Esuna - for MeyrimeFF1"
        self.assertEqual(text.fit_desc(full, 44), full)
        self.assertEqual(text.fit_desc(full, 16), "Esuna - for Meyr")
        self.assertEqual(text.fit_desc(full, 12), "Esuna")
        self.assertEqual(text.fit_desc(full, 8), "Esuna")
        self.assertEqual(text.fit_desc(full, 0), "")
        self.assertEqual(text.fit_desc("For Bob - Hookshot", 12), "For Bob")
        self.assertEqual(text.fit_desc("Your Hookshot", 8), "Your Hoo")


class TestWarpAnnouncement(unittest.TestCase):
    def test_story_locked_destinations_say_so_and_reannounce_when_they_open(self):
        ctx = WarpCtx()                              # moment 100: the Dollet exam
        ctx.items_received = [mock.Mock(item=BASE_ID + d.id_offset) for d in ITEM_TABLE
                              if d.grant in (("warp", "balamb"), ("warp", "timber"),
                                             ("warp", "trabiagarden"))]
        for c in (0, 1, 3):                          # Squall, Zell, Quistis
            ctx.ff8.write_u8(CHAR_BASE + c * CHAR_STRIDE + memory.CHAR_EXISTS_OFFSET, 9)
        ctx.ff8.write_u16(MODULE_DISPATCH, memory.MODULE_WORLDMAP)
        with self.assertLogs("Client", level="INFO") as logs:
            maintain_warp_crystal(ctx)
        line = next(x for x in logs.output if "Fast Travel" in x)
        self.assertIn("Squall->Balamb, Zell->Timber (not until the Timber chapter), "
                      "Quistis->Trabia Garden (not until the Garden War chapter)", line)
        ctx.ff8.write_u16(GAME_MOMENT, 150)          # the Timber chapter begins
        with self.assertLogs("Client", level="INFO") as logs:
            maintain_warp_crystal(ctx)
        line = next(x for x in logs.output if "Fast Travel" in x)
        self.assertIn("Zell->Timber, Quistis->Trabia Garden (not until", line)


class TestOptionSummary(unittest.TestCase):
    def test_says_what_the_seed_was_generated_with(self):
        ctx = mock.Mock(slot_data={})
        self.assertIsNone(option_summary(ctx))       # a seed older than the options
        ctx.slot_data = {"ap_multiplier": 1, "enemy_power": 100, "triple_triad_rules": 0}
        self.assertEqual(option_summary(ctx), "AP multiplier x1 · Enemy Power 100% · "
                                              "Triple Triad rules: vanilla")
        ctx.slot_data = {"ap_multiplier": 2, "enemy_power": 50, "triple_triad_rules": 1}
        line = option_summary(ctx)
        self.assertIn("AP multiplier x2 (added after each battle", line)
        self.assertIn("Enemy Power 50% · Triple Triad rules: no Random", line)


class TestDrawPointPlacement(unittest.TestCase):
    """Where the field scripts put these points (DRAW_POINT_FIELDS) decides
    when they can be drawn."""

    def setUp(self):
        self.rows = {slot: (region, missable)
                     for slot, _spell, _place, region, missable in DRAW_POINT_TABLE}

    def screens(self, slot):
        return {FIELD_NAMES[f] for f in DRAW_POINT_FIELDS[slot]}

    def test_the_dream_points_are_one_window(self):
        for slot in (70, 71):
            self.assertTrue(all(n.startswith("cdfield") for n in self.screens(slot)))
            self.assertEqual(self.rows[slot], ("Galbadia", True))

    def test_the_lunatic_pandora_points_wait_for_disc_3(self):
        for slot in (59, 60, 61, 62):
            self.assertTrue(all(n.startswith("ebroad") for n in self.screens(slot)))
            self.assertEqual(self.rows[slot], ("Lunatic Pandora", False))

    def test_the_auditorium_is_a_disc_1_point(self):
        self.assertEqual(self.rows[18], ("Galbadia", True))

    def test_the_dream_cure_is_timber_city_squares_cure(self):
        # one savemap slot, two screens: the game itself treats them as one
        self.assertEqual(self.screens(12), {"ebroad41", "titown6"})


if __name__ == "__main__":
    unittest.main()
