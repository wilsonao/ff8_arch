"""Regression tests for the Discord reports of 10-23 Oct 2026, and the magic
economy the maintainer asked for the same day.

1. First Draw fired when an ENEMY cast the spell (Elite Soldier's Aura, the
   Cerberus fight): the Magic command marks the spell drawn-once for any
   caster. The client NOPs that one call in FF8_EN.exe.
2. Story Keys: the Lunar Gate wanted Key: Sorceress Memorial and the other
   way round; a battle fought standing on the Centra Ruins' tiles dropped the
   player inside without the key (the world map reloads its doors from disk).
3. Logic: the Queen of Cards' cards sat under one town's key although she
   walks between eight spots; the point above the Fire Cavern is Blizzard
   early and Cure only from Disc 3; Siren's ST Med-RF was the one refine of
   hers that was not a check; scanning 30 kinds of enemy was too much.
4. A GF ability learned before its lock item arrived had to be learned again.
5. Checks-only magic arrived far too slowly: spell stocks now share
   magic_abundance % of what the party can hold, each copy rolled.
6. The tracker opened Disc 2 after one early card win; the client now
   publishes the true story moment.
"""

import asyncio
import struct
import unittest
from unittest import mock

from BaseClasses import CollectionState, LocationProgressType
from Fill import distribute_items_restrictive

from . import FF8TestBase
from .. import memory
from ..client import (FF8Context, SIGNATURE_LEARN_LOCATION, apply_code_patches,
                      enforce_gf_locks, enforce_story_keys, grant_items,
                      guard_doors_once, publish_moment, repair_story_key_table,
                      rolled_magic_qty)
from ..items import (BASE_ID, ITEM_DATA_BY_NAME, MAGIC_PARTY_CAPACITY, MAGIC_QTY_MAX,
                     PROGRESSIVE_TABLE, STOCK_TABLE, item_name_to_id)
from ..locations import LOCATION_DATA_BY_NAME, location_name_to_id
from ..memory import (DREAM_ACTIVE, DREAM_FLAGS, ENTRANCE_SCRIPT, GAME_MOMENT,
                      MODULE_DISPATCH)
from ..regions import (QUEEN_OF_CARDS_AREAS, REGION_CHAIN, STORY_KEY_AREAS,
                       key_areas_of_location, story_key_name)
from .test_oct_feedback_round4 import real_ctx
from .test_story_doors import FakeCtx as DoorCtx
from .test_vehicle_window import FakeProc

WORLDMAP = memory.MODULE_WORLDMAP


class CodeProc(FakeProc):
    """The fake process, with code writes going straight to the buffer."""

    def _write_code(self, offset, data):
        self.write_bytes(offset, data)


class TestEnemyCastIsNotADraw(unittest.TestCase):
    def proc(self, code=memory.MAGIC_CAST_DRAWN_CALL_BYTES):
        ff8 = CodeProc()
        ff8.write_bytes(memory.MAGIC_CAST_DRAWN_CALL, code)
        return ff8

    def test_the_call_is_replaced_once(self):
        ff8 = self.proc()
        args = (memory.MAGIC_CAST_DRAWN_CALL, memory.MAGIC_CAST_DRAWN_CALL_BYTES,
                memory.NOP5)
        self.assertEqual(ff8.patch_code(*args), "patched")
        self.assertEqual(ff8.read_bytes(memory.MAGIC_CAST_DRAWN_CALL, 5), memory.NOP5)
        self.assertEqual(ff8.patch_code(*args), "already")

    def test_other_code_is_left_alone_and_said(self):
        hooked = bytes.fromhex("e9aabbccdd")       # a mod's jump owns the spot
        ctx = mock.Mock(ff8=self.proc(hooked))
        with self.assertLogs("Client", level="WARNING"):
            apply_code_patches(ctx)
        self.assertEqual(ctx.ff8.read_bytes(memory.MAGIC_CAST_DRAWN_CALL, 5), hooked)

    def test_the_site_is_the_magic_command_call(self):
        # push esi; call 0x48B7A0 at 0x48D884 (rel32 from the next instruction)
        rel = 0x48B7A0 - (0x400000 + memory.MAGIC_CAST_DRAWN_CALL + 5)
        self.assertEqual(memory.MAGIC_CAST_DRAWN_CALL_BYTES,
                         b"\xe8" + struct.pack("<i", rel))
        self.assertEqual(len(memory.NOP5), 5)


class TestLunarGateDoors(unittest.TestCase):
    def test_each_key_names_its_own_door(self):
        # esview1 ("Welcome to 'Lunar Gate'") is entry 30 / segment 443;
        # efview1 (the Sealing Facility) is entry 29 / segment 441
        self.assertEqual(STORY_KEY_AREAS["Lunar Gate"].segments, (443,))
        self.assertIn(29, STORY_KEY_AREAS["Lunar Gate"].wm_fields)
        self.assertEqual(STORY_KEY_AREAS["Sorceress Memorial"].segments, (441,))
        self.assertIn(30, STORY_KEY_AREAS["Sorceress Memorial"].wm_fields)

    def test_an_older_seed_is_uncrossed(self):
        table = DoorCtx().slot_data["story_key_areas"]
        fixed = {a: dict(v) for a, v in table.items()}
        gate, memorial = table["Lunar Gate"], table["Sorceress Memorial"]
        for field in ("lock", "unlock", "segments", "wm_fields"):
            gate[field], memorial[field] = memorial[field], gate[field]
        self.assertTrue(repair_story_key_table(table))
        self.assertEqual(table, fixed)
        self.assertFalse(repair_story_key_table(table))   # already right

    def test_the_lunar_gate_key_opens_the_lunar_gate(self):
        ctx = DoorCtx(owned=["Lunar Gate"],
                      areas=["Lunar Gate", "Sorceress Memorial"])
        ctx.set_state(module=WORLDMAP, moment=1000)     # no story pass yet
        enforce_story_keys(ctx)
        self.assertEqual(ctx.word("Lunar Gate"), 443)           # open
        self.assertEqual(ctx.word("Sorceress Memorial"), 0xFFFF)


class TestDoorGuard(unittest.TestCase):
    def ruins(self, module=WORLDMAP):
        ctx = DoorCtx(areas=["Centra Ruins"])
        ctx.set_state(module=module, moment=800)
        enforce_story_keys(ctx)
        return ctx

    def test_a_reloaded_door_is_locked_again_at_once(self):
        ctx = self.ruins()
        self.assertEqual(ctx.word("Centra Ruins"), 0xFFFF)
        ctx.reset_script()                     # back from a battle: vanilla again
        self.assertTrue(guard_doors_once(ctx))
        self.assertEqual(ctx.word("Centra Ruins"), 0xFFFF)

    def test_nothing_is_written_off_the_map(self):
        ctx = self.ruins()
        ctx.set_state(module=memory.MODULE_BATTLE, moment=800)
        ctx.reset_script()
        guard_doors_once(ctx)
        self.assertEqual(ctx.word("Centra Ruins"), 592)

    def test_an_owned_key_is_not_guarded(self):
        ctx = self.ruins()
        ctx.own("Centra Ruins")
        enforce_story_keys(ctx)
        self.assertFalse(guard_doors_once(ctx))
        self.assertEqual(ctx.word("Centra Ruins"), 592)


class TestQueenOfCardsKeys(FF8TestBase):
    options = {"story_keys": "areas", "rare_card_checks": True}

    def test_her_cards_need_every_spot_she_walks_to(self):
        for card in ("Kiros", "Irvine", "Chubby Chocobo", "Doomtrain", "Phoenix"):
            self.assertEqual(key_areas_of_location(f"Rare Card: {card}"),
                             QUEEN_OF_CARDS_AREAS)
        self.assertEqual(key_areas_of_location("Rare Card: Rinoa"), ("Deling City",))
        self.assertEqual(key_areas_of_location("Rare Card: Squall"), ("Esthar City",))

    def test_one_missing_spot_keeps_kiros_out_of_logic(self):
        state = CollectionState(self.multiworld)
        self.collect_all_but([story_key_name("Winhill")], state)
        self.assertFalse(state.can_reach("Rare Card: Kiros", "Location", self.player))
        state.collect(self.get_item_by_name(story_key_name("Winhill")))
        self.assertTrue(state.can_reach("Rare Card: Kiros", "Location", self.player))


class TestWorldDrawPointTiming(FF8TestBase):
    options = {"world_draw_point_checks": True}

    def test_the_fire_cavern_point(self):
        blizzard = LOCATION_DATA_BY_NAME["Draw Point: Alcauld Plains (Blizzard)"]
        cure = LOCATION_DATA_BY_NAME["Draw Point: Alcauld Plains (Cure #2)"]
        self.assertTrue(blizzard.missable)
        self.assertEqual(cure.region, "Edea's House")
        self.assertEqual(self.multiworld.get_location(blizzard.name, self.player).progress_type,
                         LocationProgressType.EXCLUDED)

    def test_the_garden_and_missile_base_sites_wait_for_the_garden(self):
        self.assertEqual(LOCATION_DATA_BY_NAME["Draw Point: Monterosa Plateau (Dispel)"].region,
                         "Garden War")
        self.assertEqual(
            LOCATION_DATA_BY_NAME["Draw Point: Great Plains of Galbadia (Confuse)"].region,
            "Balamb Liberation")


class TestIdsStayPut(unittest.TestCase):
    def test_st_med_rf_is_appended(self):
        self.assertEqual(location_name_to_id["Siren Learns ST Med-RF"], BASE_ID + 849)
        self.assertEqual(item_name_to_id["Siren: ST Med-RF"], BASE_ID + 649)
        self.assertEqual(location_name_to_id["Brothers Learns HP Bonus"], BASE_ID + 812)
        self.assertEqual(location_name_to_id["Eden Learns Expendx3-1"], BASE_ID + 848)
        self.assertEqual(item_name_to_id["Eden: Expendx3-1"], BASE_ID + 648)

    def test_lower_scan_and_ability_ladders_keep_their_ids(self):
        self.assertEqual(location_name_to_id["Enemies Scanned: 15"], BASE_ID + 752)
        self.assertEqual(location_name_to_id["Enemies Scanned: 25"], BASE_ID + 753)
        self.assertEqual(location_name_to_id["GF Abilities Learned: 135"], BASE_ID + 874)

    def test_scan_has_a_stock(self):
        self.assertEqual(ITEM_DATA_BY_NAME["Scan Stock"].grant[:2], ("stock", 50))


def gf_ctx(items=(), checked=()):
    ctx = mock.Mock()
    ctx.ff8 = FakeProc()
    ctx.slot_data = {"ability_locks": True}
    ctx.save_frozen = None
    ctx.items_synced = True
    ctx.items_received = [mock.Mock(item=item_name_to_id[n]) for n in items]
    ctx.checked_locations = set(checked)
    ctx.locations_checked = set()
    ctx.ff8.set_gf_unlocked(0, True)
    return ctx


CARD = 25


class TestLearnedAbilityComesBack(unittest.TestCase):
    def test_card_returns_with_its_item(self):
        ctx = gf_ctx(["Quezacotl: Card"], [SIGNATURE_LEARN_LOCATION[(0, CARD)]])
        with self.assertLogs("Client", level="INFO") as logs:
            enforce_gf_locks(ctx)
        self.assertTrue(ctx.ff8.gf_ability_masks_all()[0] >> CARD & 1)
        self.assertIn("Card back", " ".join(logs.output))

    def test_never_learned_stays_to_be_learned(self):
        ctx = gf_ctx(["Quezacotl: Card"])
        enforce_gf_locks(ctx)
        self.assertFalse(ctx.ff8.gf_ability_masks_all()[0] >> CARD & 1)

    def test_learned_but_still_locked_stays_revoked(self):
        ctx = gf_ctx([], [SIGNATURE_LEARN_LOCATION[(0, CARD)]])
        ctx.ff8.write_gf_abilities(0, 1 << CARD)
        enforce_gf_locks(ctx)
        self.assertFalse(ctx.ff8.gf_ability_masks_all()[0] >> CARD & 1)


class TestMagicEconomy(FF8TestBase):
    auto_construct = False
    options = {"magic_mode": "checks_only", "trap_chance": 0}

    def filled(self, seed=1, **options):
        self.options = {**type(self).options, **options}
        self.world_setup(seed)
        distribute_items_restrictive(self.multiworld)
        return self.multiworld.worlds[self.player]

    def test_the_pool_carries_stocks_not_fixed_packs(self):
        world = self.filled()
        names = {i.name for i in self.multiworld.itempool if i.player == self.player}
        self.assertTrue(names & {d.name for d in STOCK_TABLE})
        self.assertFalse(any(n.endswith((" x5", " x10", " x15", " x20", " x3"))
                             for n in names), sorted(names))
        # progressive magic (on by default) owns the Fire/Cure families
        self.assertNotIn("Fira Stock", names)
        self.assertIsNotNone(world)

    def test_the_rolls_add_up_to_the_abundance(self):
        world = self.filled()
        rolls = world.magic_quantities()
        target = 1.5 * MAGIC_PARTY_CAPACITY
        self.assertAlmostEqual(sum(rolls.values()), target, delta=3 * len(rolls))
        names = {d.name for d in STOCK_TABLE} | {d.name for d in PROGRESSIVE_TABLE}
        for key, qty in rolls.items():
            player, address = map(int, key.split(":"))
            loc = self.multiworld.get_location(
                self.multiworld.worlds[player].location_id_to_name[address], player)
            self.assertIn(loc.item.name, names)
            self.assertTrue(5 <= qty <= 255, qty)
        self.assertGreater(max(rolls.values()) - min(rolls.values()), 40)
        self.assertEqual(world.fill_slot_data()["magic_quantities"], rolls)

    def test_abundance_and_goal_scale_the_total(self):
        half = sum(self.filled(magic_abundance=75).magic_quantities().values())
        self.assertAlmostEqual(half, 0.75 * MAGIC_PARTY_CAPACITY, delta=0.05 * half)
        # Disc 1 is 6 of 18 chapters; its few magic slots hit the per-copy
        # cap, so it lands below its share, never above
        edea = self.filled(goal="edea").magic_quantities()
        share = 1.5 * MAGIC_PARTY_CAPACITY * (REGION_CHAIN.index("Galbadia") + 1) / len(REGION_CHAIN)
        self.assertLessEqual(sum(edea.values()), share + 3 * len(edea))
        self.assertGreater(sum(edea.values()), 0.6 * share)
        self.assertLessEqual(max(edea.values()), MAGIC_QTY_MAX)

    def test_vanilla_magic_rolls_nothing(self):
        self.assertEqual(self.filled(magic_mode="vanilla").magic_quantities(), {})


class TestEdeaKeysFill(FF8TestBase):
    """The short world ran out of filler for its one-window locations once
    tier-1 stocks were useful (seed 33)."""
    auto_construct = False
    options = {"goal": "edea", "story_keys": "story", "starting_gfs": 1}

    def test_seed_33_fills(self):
        self.world_setup(33)
        distribute_items_restrictive(self.multiworld)
        self.assertTrue(self.multiworld.can_beat_game(self.multiworld.state))


ULTIMA_STOCK = item_name_to_id["Ultima Stock"]


class TestStockGrant(unittest.TestCase):
    def test_a_rolled_copy_gives_its_roll(self):
        found = mock.Mock(item=ULTIMA_STOCK, player=2, location=8800321)

        async def steps(ctx):
            ctx.items_received = [found]
            await grant_items(ctx)
        ctx = real_ctx(steps, [], {"magic_mode": 1,
                                   "magic_quantities": {"2:8800321": 135}})
        self.assertEqual(ctx.ff8.snapshot().magic_totals().get(19), 135)

    def test_a_copy_without_a_roll_gives_the_base(self):
        ctx = mock.Mock(slot_data={"magic_quantities": {"2:8800321": 135}})
        start = mock.Mock(player=0, location=-2)
        self.assertEqual(rolled_magic_qty(ctx, start, 30), 30)


class TestMomentFeed(unittest.TestCase):
    def published(self, moment, hold=None, dream=False, sent=None):
        async def steps(ctx):
            ctx.story_hold = hold
            ctx.sent_moment = sent
            if dream:
                ctx.ff8.write_u8(DREAM_FLAGS, DREAM_ACTIVE)
            await publish_moment(ctx)
        ctx = real_ctx(steps, [], moment=moment)
        return [m for call in ctx.send_msgs.call_args_list for m in call.args[0]]

    def test_the_moment_goes_out_as_a_max(self):
        msgs = self.published(300)
        self.assertEqual(msgs[0]["key"], "ff8_moment_None_1")
        self.assertEqual(msgs[0]["operations"], [{"operation": "max", "value": 300}])

    def test_quiet_when_unchanged_held_or_dreaming(self):
        self.assertEqual(self.published(300, sent=300), [])
        self.assertEqual(self.published(300, hold=(205, 750)), [])
        self.assertEqual(self.published(22, dream=True), [])


if __name__ == "__main__":
    unittest.main()
