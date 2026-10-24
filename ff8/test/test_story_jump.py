"""Story-jump guard: a field script reached out of order (early-Ragnarok
landing in a later-disc town) writes a moment several beats ahead. The client
must hold the story checks past the jump and the Edea goal, lift the hold when
an earlier save is loaded, and never treat a save load as a jump.
Reported 2026-09-29: one Timber scene sent Fire Cavern, Dollet, SeeD and
Laguna Dream 1 at once; Edea's House / FH / Dobe each ended an Edea seed."""

import asyncio
import unittest
from unittest import mock

from ..client import (GOAL_EDEA, beats_crossed, check_story_jump,
                      track_story_goal, trigger_satisfied)
from ..memory import DREAM_ACTIVE, DREAM_FLAGS, GAME_MOMENT
from .test_vehicle_window import FakeProc


class JumpCtx:
    def __init__(self, moment=20, goal=None):
        self.ff8 = FakeProc()
        self.ff8.write_u16(GAME_MOMENT, moment)
        self.slot_data = {"goal": goal} if goal is not None else {}
        self.story_prev_moment = None
        self.story_hold = None
        self.story_hold_accept = False
        self.goal_sent = False
        self.save_frozen = None
        self.moment_faked = False
        self.true_moment = None
        self.sidecar_writes = 0
        self.send_msgs = mock.AsyncMock()
        self.finished_game = False

    def save_sidecar(self):
        self.sidecar_writes += 1

    def tick(self, moment):
        self.ff8.write_u16(GAME_MOMENT, moment)
        check_story_jump(self, moment)

    def story(self, value):
        return trigger_satisfied(self, "story", value, self.ff8.snapshot(), [], {})


class TestStoryJump(unittest.TestCase):
    def test_beat_counting(self):
        self.assertEqual(beats_crossed(20, 233), 3)    # Dollet 30, SeeD 135, Timber 150
        self.assertEqual(beats_crossed(380, 392), 1)   # the parade -> D-District
        self.assertEqual(beats_crossed(392, 392), 0)

    def test_normal_play_is_never_held(self):
        ctx = JumpCtx()
        for m in (20, 30, 100, 135, 150, 233, 290, 392):
            ctx.tick(m)
        self.assertIsNone(ctx.story_hold)
        self.assertTrue(ctx.story(150))

    def test_early_timber_scene_is_held(self):
        ctx = JumpCtx()
        ctx.tick(20)
        with self.assertLogs("Client", level="WARNING"):
            ctx.tick(233)
        self.assertEqual(ctx.story_hold, (20, 233))
        self.assertEqual(ctx.sidecar_writes, 1)
        self.assertTrue(ctx.story(17))          # already past before the jump
        for value in (30, 135, 150, 233):       # Fire Cavern .. Laguna Dream 1
            self.assertFalse(ctx.story(value), value)

    def test_loading_an_earlier_save_lifts_the_hold(self):
        ctx = JumpCtx()
        ctx.tick(20)
        ctx.tick(233)
        ctx.story_prev_moment = None            # title screen -> load menu
        ctx.tick(18)
        self.assertIsNone(ctx.story_hold)
        self.assertFalse(ctx.story(30))         # not reached in this save
        ctx.tick(30)
        self.assertTrue(ctx.story(30))

    def test_keepstory_releases_the_held_checks(self):
        ctx = JumpCtx()
        ctx.tick(20)
        ctx.tick(233)
        ctx.story_hold_accept = True
        ctx.tick(233)
        self.assertIsNone(ctx.story_hold)
        self.assertTrue(ctx.story(150))

    def test_hold_survives_a_restart_and_a_later_load_is_no_jump(self):
        ctx = JumpCtx()
        ctx.story_hold = (20, 233)              # from the sidecar
        ctx.tick(240)                           # fresh baseline, still past it
        self.assertEqual(ctx.story_hold, (20, 233))
        fresh = JumpCtx()
        fresh.tick(900)                         # first read of a loaded save
        self.assertIsNone(fresh.story_hold)

    def test_edea_goal_waits_while_held(self):
        ctx = JumpCtx(goal=GOAL_EDEA)
        ctx.tick(205)
        ctx.tick(905)                           # Edea's House on Disc 1
        asyncio.run(track_story_goal(ctx))
        self.assertFalse(ctx.goal_sent)
        ok = JumpCtx(goal=GOAL_EDEA)
        ok.tick(380)
        ok.tick(392)                            # the parade win
        asyncio.run(track_story_goal(ok))
        self.assertTrue(ok.goal_sent)


class TestLagunaDreamRewind(unittest.TestCase):
    """Reported 2026-10-04: Laguna's first dream rewinds the moment to 22 in
    Timber Forest and resumes at 216. v0.9.0 read that as a jump and held the
    story checks and the Edea goal of everyone who played through it."""

    def dream(self, ctx, on=True):
        ctx.ff8.write_u8(DREAM_FLAGS, DREAM_ACTIVE if on else 0)

    def test_the_first_dream_is_not_a_jump(self):
        ctx = JumpCtx(goal=GOAL_EDEA)
        ctx.tick(205)                           # the Timber train
        self.dream(ctx)
        for m in (22, 22, 216, 223, 226, 228):  # forest, then Deling City
            ctx.tick(m)
        self.dream(ctx, on=False)
        ctx.tick(233)
        self.assertIsNone(ctx.story_hold)
        self.assertTrue(ctx.story(233))         # Laguna Dream 1: Deling City
        for m in (290, 380, 392):
            ctx.tick(m)
        asyncio.run(track_story_goal(ctx))
        self.assertTrue(ctx.goal_sent)

    def test_a_save_loaded_inside_the_dream_forest_is_not_a_jump(self):
        ctx = JumpCtx()
        self.dream(ctx)
        ctx.tick(22)                            # first read of the loaded save
        self.assertIsNone(ctx.story_prev_moment)
        ctx.tick(216)
        self.assertIsNone(ctx.story_hold)

    def test_moment_22_outside_a_dream_still_guards(self):
        ctx = JumpCtx()
        ctx.tick(22)                            # Fire Cavern, awake
        ctx.tick(233)                           # the early Timber train scene
        self.assertEqual(ctx.story_hold, (22, 233))

    def test_a_real_hold_is_not_lifted_by_the_dream_rewind(self):
        ctx = JumpCtx()
        ctx.tick(205)
        ctx.tick(905)                           # Edea's House on Disc 1
        self.dream(ctx)
        ctx.tick(22)
        self.assertEqual(ctx.story_hold, (205, 905))

    def test_a_v090_dream_hold_lifts_by_itself(self):
        ctx = JumpCtx(goal=GOAL_EDEA)
        ctx.story_hold = (22, 216)              # from a v0.9.0 sidecar
        with self.assertLogs("Client", level="INFO"):
            ctx.tick(392)
        self.assertIsNone(ctx.story_hold)
        self.assertTrue(ctx.story(310))         # Laguna Dream 2
        asyncio.run(track_story_goal(ctx))
        self.assertTrue(ctx.goal_sent)

    def test_the_magic_ledger_ignores_the_rewind(self):
        from ..client import dream_rewind
        ctx = JumpCtx()
        self.dream(ctx)
        self.assertTrue(dream_rewind(ctx.ff8, 22))
        self.assertTrue(dream_rewind(ctx.ff8.snapshot(), 22))
        self.assertFalse(dream_rewind(ctx.ff8, 216))
        self.dream(ctx, on=False)
        self.assertFalse(dream_rewind(ctx.ff8, 22))


class LoadCtx(JumpCtx):
    def __init__(self):
        super().__init__()
        self.load_clock = None
        self.load_suspect = None
        for name in ("prev_gf_flags", "magic_expected", "magic_prev_items",
                     "magic_prev_by_char", "magic_prev_totals", "draw_states_prev",
                     "magic_prev_dream", "gf_ap_prev", "prev_tt_wins",
                     "prev_warp_crystal", "pending_warp", "warp_gap_gil"):
            setattr(self, name, "kept")
        self.warp_gap_map_menu = self.warp_gap_battle = True

    def at(self, play_time, now, module=2, in_menu=False):
        from ..client import track_save_load
        from ..memory import GAME_TIME, IN_MENU, MODULE_DISPATCH
        self.ff8.write_u32(GAME_TIME, play_time)
        self.ff8.write_u16(MODULE_DISPATCH, module)
        self.ff8.write_u8(IN_MENU, 1 if in_menu else 0)
        track_save_load(self, now)


class TestSaveLoadDetection(unittest.TestCase):
    """Live 2026-10-02: a Ctrl+R reset never shows the title module; loading a
    moment-750 save over a 205 one logged "Story jumped" and the Potion count
    difference between the saves fired a warp. The play-time counter marks a
    load; every per-save baseline is dropped."""

    def test_play_time_jump_drops_every_baseline(self):
        ctx = LoadCtx()
        ctx.story_prev_moment = 205
        ctx.at(7000, 100.0)
        ctx.at(7001, 100.5)
        self.assertEqual(ctx.prev_warp_crystal, "kept")       # same save
        with self.assertLogs("Client", level="INFO"):
            ctx.at(9500, 130.0)                               # another save
        for name in ("prev_gf_flags", "magic_expected", "gf_ap_prev",
                     "magic_prev_totals", "draw_states_prev", "magic_prev_dream",
                     "prev_warp_crystal", "pending_warp", "story_prev_moment"):
            self.assertIsNone(getattr(ctx, name), name)
        self.assertFalse(ctx.warp_gap_map_menu)

    def test_backwards_play_time_is_a_load_and_8x_speed_is_not(self):
        ctx = LoadCtx()
        ctx.at(9500, 10.0)
        ctx.at(9504, 10.5)                                    # FFNx 8x
        self.assertEqual(ctx.prev_gf_flags, "kept")
        ctx.at(7000, 40.0)                                    # an older save
        self.assertIsNone(ctx.prev_gf_flags)

    def test_a_long_pause_is_not_a_load(self):
        ctx = LoadCtx()
        ctx.at(5000, 0.0)
        ctx.at(5000, 600.0)                                   # window unfocused
        ctx.at(5300, 900.0)                                   # a long battle
        self.assertEqual(ctx.prev_gf_flags, "kept")

    def test_a_menu_that_borrows_the_counter_is_not_a_load(self):
        # reported 2026-10-07/08: "Another save was loaded" at the tutorials
        ctx = LoadCtx()
        ctx.at(7000, 100.0)
        ctx.at(7001, 100.5, module=6)                         # the menu opens
        ctx.at(12, 101.0, module=6)                           # the tutorial's own clock
        self.assertEqual(ctx.load_suspect, (7001, 100.5))
        ctx.at(40, 130.0, module=6)
        ctx.at(7001, 130.5, module=6)                         # the player's clock is back
        self.assertIsNotNone(ctx.load_suspect)                # judged once the menu is gone
        with self.assertNoLogs("Client", level="INFO"):
            ctx.at(7003, 132.0)
        self.assertIsNone(ctx.load_suspect)
        self.assertEqual(ctx.prev_gf_flags, "kept")
        ctx.at(7004, 132.5)                                   # and tracking goes on
        self.assertEqual(ctx.prev_gf_flags, "kept")

    def test_a_load_through_a_menu_screen_is_still_a_load(self):
        for flag in (dict(module=6), dict(in_menu=True)):
            ctx = LoadCtx()
            ctx.at(7000, 100.0)
            ctx.at(900, 100.5, **flag)                        # loaded in the load screen
            self.assertEqual(ctx.prev_gf_flags, "kept", flag)  # not judged yet
            with self.assertLogs("Client", level="INFO"):
                ctx.at(902, 104.0)                            # the field of the other save
            self.assertIsNone(ctx.prev_gf_flags, flag)
            self.assertIsNone(ctx.load_suspect, flag)

    def test_the_title_screen_clears_a_suspicion(self):
        ctx = LoadCtx()
        ctx.at(7000, 100.0)
        ctx.at(12, 100.5, module=6)
        ctx.at(12, 101.0, module=0)
        self.assertIsNone(ctx.load_suspect)
        self.assertIsNone(ctx.load_clock)


if __name__ == "__main__":
    unittest.main()
