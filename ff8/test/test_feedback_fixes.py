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


class TestLiveFindings20260930(unittest.TestCase):
    """Fixes from the 2026-09-30 live session."""

    def test_ambush_ignores_the_zero_max_hp_word(self):
        # live: max HP reads 0 for every character; only current HP is real
        ff8 = FakeProc()
        for c, hp in enumerate((745, 627, 0, 622)):
            ff8.write_u16(memory.CHAR_BASE + c * memory.CHAR_STRIDE, hp)
        self.assertEqual(ff8.ambush_party(1), 3)
        self.assertEqual(ff8.read_u16(memory.CHAR_BASE), 1)
        self.assertEqual(ff8.read_u16(memory.CHAR_BASE + 2 * memory.CHAR_STRIDE), 0)

    def test_battle_survives_the_module_5_tick(self):
        # 3 -> 5 (results flag still down) -> 100 -> 4 -> 2 must stay one battle
        ctx = DrawCtx()
        ctx.ff8.write_u16(ENCOUNTER_ID, 514)
        rec = BATTLE_ALLIES
        ctx.ff8.write_u16(rec + ALLY_CUR_HP, 500)
        ctx.ff8.write_u16(rec + ALLY_MAX_HP, 500)
        for module, post in ((3, 0), (5, 0), (100, 1), (4, 1), (2, 0)):
            ctx.ff8.write_u16(MODULE_DISPATCH, module)
            ctx.ff8.write_u8(POST_BATTLE, post)
            track_battle(ctx)
        self.assertEqual(ctx.last_battle_outcome, "won")
        self.assertIn(514, ctx.won_encounters)


class LampCtx(DrawCtx):
    def __init__(self, lamp=1, diablos_expected=True, check_missing=True):
        super().__init__()
        self.slot = 1
        self.lamp_window = False
        self.lamp_window_logged = False
        self.ap_set_gf_flags = set()
        self.missing_locations = {BASE_ID + 5} if check_missing else set()
        self.items_received = [mock.Mock(item=BASE_ID + 5 + 200)] if diablos_expected else []
        self.ff8.set_gf_unlocked(5, True)
        if lamp:
            self.ff8.add_item(168, lamp)

    def set_menu(self, open_):
        self.ff8.write_u8(IN_MENU, 1 if open_ else 0)
        self.ff8.write_u16(MODULE_DISPATCH, 6 if open_ else 2)


class TestLampWindow(unittest.TestCase):
    def setUp(self):
        from .. import client
        self.client = client
        # "GF Diablos" item id: find it from the table rather than guess
        self.diablos_item = next(i for i, d in client.ITEM_DATA_BY_ID.items()
                                 if d.grant == ("gf", 5))

    def _ctx(self, **kw):
        ctx = LampCtx(**kw)
        if ctx.items_received:
            ctx.items_received = [mock.Mock(item=self.diablos_item)]
        return ctx

    def test_hides_diablos_while_menu_open_and_restores_after(self):
        ctx = self._ctx()
        ctx.set_menu(True)
        self.client.maintain_lamp_window(ctx)
        self.assertTrue(ctx.lamp_window)
        self.assertFalse(ctx.ff8.gf_unlocked(5))
        ctx.set_menu(False)
        self.client.maintain_lamp_window(ctx)
        self.assertFalse(ctx.lamp_window)
        self.assertTrue(ctx.ff8.gf_unlocked(5))
        # live 2026-10-02: his return must not read as the game handing him
        # over (that sent "Magical Lamp: Diablos" with no fight)
        self.assertIn(5, ctx.ap_set_gf_flags)

    def test_stays_hidden_through_a_battle_started_from_the_menu(self):
        ctx = self._ctx()
        ctx.set_menu(True)
        self.client.maintain_lamp_window(ctx)
        ctx.ff8.write_u8(IN_MENU, 0)
        ctx.ff8.write_u16(MODULE_DISPATCH, 3)
        self.client.maintain_lamp_window(ctx)
        self.assertTrue(ctx.lamp_window)
        self.assertFalse(ctx.ff8.gf_unlocked(5))

    def test_no_window_without_lamp_or_with_check_done_or_vanilla_diablos(self):
        for kw in (dict(lamp=0), dict(check_missing=False), dict(diablos_expected=False)):
            ctx = self._ctx(**kw)
            ctx.set_menu(True)
            self.client.maintain_lamp_window(ctx)
            self.assertFalse(ctx.lamp_window, kw)
            self.assertTrue(ctx.ff8.gf_unlocked(5), kw)


class TestMonstersFelledLive(unittest.TestCase):
    """2026-09-30: Monsters Felled read misc3.monster_kills, which the game
    only re-sums when a field loads — world-map kills counted late."""

    def test_counts_character_record_kills_before_any_field_load(self):
        from ..client import trigger_satisfied
        from ..locations import LOCATION_TABLE
        ff8 = FakeProc()
        for char, kills in enumerate((20, 18, 12)):
            ff8.write_u16(memory.CHAR_BASE + char * memory.CHAR_STRIDE
                          + memory.CHAR_KILLS_OFFSET, kills)
        ff8.write_u32(memory.MONSTER_KILLS, 33)          # stale copy from the last town
        snap = ff8.snapshot()
        self.assertEqual(snap.kills_total(), 50)
        loc = next(d for d in LOCATION_TABLE if d.name == "Monsters Felled: 50")
        kind, value = loc.triggers[0]
        self.assertTrue(trigger_satisfied(None, kind, value, snap, [], {}))


class WarpCtx:
    """Just what maintain_warp_crystal / track_warp_window touch."""

    def __init__(self):
        from ..items import ITEM_TABLE
        self.ff8 = FakeProc()
        self.slot_data = {"fast_travel": 1}
        balamb = next(BASE_ID + d.id_offset for d in ITEM_TABLE
                      if d.grant == ("warp", "balamb"))
        self.items_received = [mock.Mock(item=balamb)]
        self.prev_warp_crystal = None
        self.pending_warp = None
        self.warp_mapping_logged = None
        self.warp_prev_module = None
        self.warp_gap_map_menu = False
        self.warp_gap_battle = False
        self.warp_gap_gil = None
        self.moment_faked = False
        self.true_moment = None
        self.ff8.write_u16(GAME_MOMENT, 100)
        self.ff8.write_u32(memory.GIL, 5000)

    def tick(self, module, menu=False):
        from ..client import maintain_warp_crystal, track_warp_window
        self.ff8.write_u16(MODULE_DISPATCH, module)
        self.ff8.write_u8(IN_MENU, 1 if menu else 0)
        track_warp_window(self)
        if not menu and module not in (3, 4, 5, 100):
            maintain_warp_crystal(self)

    def potions(self):
        return self.ff8.count_item(1)


class TestWarpTrigger(unittest.TestCase):
    """2026-10-02 hardening: only a Potion used from a WORLD-MAP menu is a warp
    request. A battle Potion warped with a stale target; a Call Shop sale was
    refunded (free gil)."""

    def setUp(self):
        self.ctx = WarpCtx()
        self.ctx.tick(2)                       # baseline: one Potion stocked
        self.assertEqual(self.ctx.potions(), 1)
        self.ctx.ff8.add_item(1, 4)            # the player owns 5
        self.ctx.tick(2)

    def use_one(self):
        before = self.ctx.potions()
        from .. import memory as m
        # drop one Potion straight in the inventory, as the menu would
        for slot in range(198):
            iid, qty = self.ctx.ff8.read_bytes(m.INVENTORY + slot * 2, 2)
            if iid == 1 and qty:
                self.ctx.ff8.write_bytes(m.INVENTORY + slot * 2, bytes([1, qty - 1]))
                break
        self.assertEqual(self.ctx.potions(), before - 1)

    def test_world_map_menu_use_warps_and_refunds(self):
        self.ctx.tick(6, menu=True)
        self.use_one()
        self.ctx.tick(2)
        self.assertEqual(self.ctx.potions(), 5)                      # refunded
        self.assertEqual(self.ctx.ff8.world_pos()[:2], (13249, -26779))  # at Balamb

    def test_battle_potion_is_ordinary_use(self):
        self.ctx.tick(3)
        self.use_one()
        self.ctx.tick(2)
        self.assertEqual(self.ctx.potions(), 4)
        self.assertIsNone(self.ctx.pending_warp)

    def test_field_menu_use_is_ordinary(self):
        self.ctx.tick(1)
        self.ctx.tick(6, menu=True)
        self.use_one()
        self.ctx.tick(1)
        self.assertEqual(self.ctx.potions(), 4)
        self.assertIsNone(self.ctx.pending_warp)

    def test_call_shop_sale_is_not_refunded(self):
        self.ctx.tick(6, menu=True)
        self.use_one()
        self.ctx.ff8.write_u32(memory.GIL, 5005)   # sold for 5 gil
        self.ctx.tick(2)
        self.assertEqual(self.ctx.potions(), 4)
        self.assertIsNone(self.ctx.pending_warp)


class TestCardClubWins(unittest.TestCase):
    """2026-09-30: Joker / Kadowaki / King checks fired at their reveal
    dialogue (var 475 is a dialogue flag). They now need a card win in their
    field after the reveal."""

    def setUp(self):
        from ..locations import LOCATION_TABLE
        self.loc = next(d for d in LOCATION_TABLE if d.name == "CC Group: Dr. Kadowaki Defeated")
        self.ctx = mock.Mock()
        self.ctx.ff8 = FakeProc()
        self.ctx.prev_tt_wins = 10
        self.ctx.prev_tt_field = 179
        self.ctx.ff8.write_u16(memory.FIELD_ID, 179)
        self.ctx.ff8.write_u8(0x18FEB93, 0x02)          # her confession is done
        self.ctx.ff8.write_u16(memory.TT_WINS, 10)

    def fires(self):
        from ..client import trigger_satisfied
        kind, value = self.loc.triggers[0]
        return trigger_satisfied(self.ctx, kind, value, self.ctx.ff8.snapshot(), [], {})

    def test_reveal_alone_does_not_fire(self):
        self.assertFalse(self.fires())

    def test_win_in_her_field_fires(self):
        self.ctx.ff8.write_u16(memory.TT_WINS, 11)
        self.assertTrue(self.fires())

    def test_win_elsewhere_or_before_the_reveal_does_not(self):
        self.ctx.ff8.write_u16(memory.TT_WINS, 11)
        self.ctx.ff8.write_u16(memory.FIELD_ID, 30)
        self.ctx.prev_tt_field = 30
        self.assertFalse(self.fires())
        self.ctx.ff8.write_u16(memory.FIELD_ID, 179)
        self.ctx.ff8.write_u8(0x18FEB93, 0)
        self.assertFalse(self.fires())
        self.ctx.ff8.write_u8(0x18FEB93, 0x02)
        self.ctx.prev_tt_wins = None                    # fresh baseline
        self.assertFalse(self.fires())


class TestWarpLabels(unittest.TestCase):
    """Live 2026-10-02: the menu's target index counts JOINED characters in
    roster order (Squall 0, Zell 1, Quistis 2, Selphie 3 with Irvine/Rinoa not
    yet joined). Labels used the roster index and named Irvine/Seifer/Edea."""

    def test_labels_follow_joined_characters(self):
        from ..client import maintain_warp_crystal
        from ..items import ITEM_TABLE
        ctx = WarpCtx()
        ctx.items_received = [mock.Mock(item=BASE_ID + d.id_offset) for d in ITEM_TABLE
                              if d.grant in (("warp", "balamb"), ("warp", "dollet"),
                                             ("warp", "timber"), ("warp", "fh"))]
        for c in (0, 1, 3, 5):                     # Squall, Zell, Quistis, Selphie
            ctx.ff8.write_u8(memory.CHAR_BASE + c * memory.CHAR_STRIDE
                             + memory.CHAR_EXISTS_OFFSET, 9)
        self.assertEqual(ctx.ff8.joined_chars(), [0, 1, 3, 5])
        ctx.ff8.write_u16(MODULE_DISPATCH, 2)
        with self.assertLogs("Client", level="INFO") as logs:
            maintain_warp_crystal(ctx)
        line = next(x for x in logs.output if "Fast Travel" in x)
        self.assertIn("Squall->Balamb, Zell->Dollet, Quistis->Timber, Selphie->Fisherman's Horizon",
                      line)
        self.assertNotIn("Irvine", line)


class TestBaselineBulkGate(unittest.TestCase):
    """Live 2026-10-02: an unstamped Disc 1 save sent 4 GF catch-up checks on
    the first tick (under the gate), got stamped by the item grant, then sent
    ~30 state checks the next tick as if it were a known campaign save. The
    first tick must count the state checks too and hold the save."""

    @staticmethod
    def run_first_tick(setup):
        import asyncio
        from ..client import FF8Context, detect_checks
        from ..locations import LOCATION_TABLE

        async def go():
            ctx = FF8Context(None, None)
            ctx.ff8 = FakeProc()
            ctx.slot_data = {}
            ctx.missing_locations = {BASE_ID + d.id_offset for d in LOCATION_TABLE}
            ctx.locations_checked = set()
            ctx.save_fingerprint = 0x1234
            ctx.ff8.write_u16(MODULE_DISPATCH, 2)
            setup(ctx.ff8)
            sent = await detect_checks(ctx)
            await ctx.shutdown()
            return ctx, sent
        return asyncio.run(go())

    def test_unstamped_save_with_many_state_checks_is_held_at_baseline(self):
        def setup(ff8):
            ff8.write_u16(GAME_MOMENT, 205)          # Fire Cavern .. SeeD done
            ff8.write_u16(memory.TT_WINS, 30)        # card-win ladder
            ff8.write_u32(memory.BATTLES_WON, 120)   # battles-won ladder
        ctx, sent = self.run_first_tick(setup)
        self.assertEqual(sent, [])
        self.assertTrue(ctx.save_frozen)

    def test_fresh_save_baselines_normally(self):
        ctx, _sent = self.run_first_tick(lambda ff8: ff8.write_u16(GAME_MOMENT, 5))
        self.assertFalse(ctx.save_frozen)
