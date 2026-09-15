"""Story-key door enforcement (client side) against a fake process.

The client keeps a missing key's door shut by writing its lock words into
the resident entrance script, re-applies them on every world-map visit (the
game re-reads the script from disk each time), reopens a door the tick its
key arrives or a story pass begins, and never touches a script whose words
do not match the expected game data.
"""

import struct
import unittest
from unittest import mock

from ..client import (STORY_KEYS_AREAS, STORY_KEYS_STORY, apply_doors,
                      doors_to_shut, enforce_story_keys, received_warp_keys,
                      world_segment)
from ..items import item_name_to_id
from ..memory import (ENTRANCE_SCRIPT, GAME_MOMENT, MODULE_DISPATCH,
                      WM_CUR_TRIANGLE_PTR, WM_EXIT_REQUEST, WORLD_POS)
from ..regions import STORY_KEY_AREAS, story_key_name, story_pass_windows
from .test_vehicle_window import FakeProc, _Item

TRI_ADDR = 0x1000     # where the fake "triangle under the avatar" record lives


def slot_table(areas=None) -> dict:
    return {
        area: {"lock": [list(p) for p in data.lock],
               "unlock": [list(p) for p in data.unlock],
               "story_beats": list(data.story_beats),
               "pass": [list(w) for w in story_pass_windows(area)],
               "warp": data.warp,
               "segments": list(data.segments),
               "wm_fields": list(data.wm_fields),
               "early": data.early}
        for area, data in STORY_KEY_AREAS.items()
        if areas is None or area in areas}


class FakeCtx:
    def __init__(self, mode=STORY_KEYS_STORY, owned=(), areas=None):
        self.ff8 = FakeProc()
        self.slot_data = {"story_keys": mode, "story_key_areas": slot_table(areas)}
        self.items_received = [_Item(item_name_to_id[story_key_name(a)]) for a in owned]
        self.items_synced = True
        self.moment_faked = False
        self.true_moment = None
        self.doors_applied = None
        self.early_applied = None
        self.doors_mismatch_logged = set()
        self.door_message_until = {}
        # vanilla words at every lock offset, as the game would load them
        self.reset_script()
        self.set_state()

    def reset_script(self):
        for data in STORY_KEY_AREAS.values():
            for off, vanilla, _new in data.lock + data.unlock:
                self.ff8.write_u16(ENTRANCE_SCRIPT + off, vanilla)

    def gate(self, area, i=0):
        """The area's story-moment gate word (unlock patch i)."""
        off = STORY_KEY_AREAS[area].unlock[i][0]
        return self.ff8.read_u16(ENTRANCE_SCRIPT + off)

    def set_state(self, module=2, moment=30, pos=(21731, -28016, -588), door_tile=False):
        self.ff8.write_u16(MODULE_DISPATCH, module)
        self.ff8.write_u16(GAME_MOMENT, moment)
        self.ff8.write_bytes(WORLD_POS, struct.pack("<3i", *pos))
        self.ff8.write_u32(WM_CUR_TRIANGLE_PTR, TRI_ADDR)
        rec = bytearray(16)
        rec[0xE] = 0x08 if door_tile else 0
        self.ff8.write_bytes(TRI_ADDR, bytes(rec))

    def word(self, area, i=0):
        off = STORY_KEY_AREAS[area].lock[i][0]
        return self.ff8.read_u16(ENTRANCE_SCRIPT + off)

    def own(self, *areas):
        self.items_received += [_Item(item_name_to_id[story_key_name(a)]) for a in areas]


class TestDoors(unittest.TestCase):
    def test_segment_math_matches_the_landmarks(self):
        self.assertEqual(world_segment(13249, -26779), 273)      # Balamb
        self.assertEqual(world_segment(-61806, -28649), 264)     # Deling City
        self.assertEqual(world_segment(48893, -57979), 149)      # Trabia Garden

    def test_missing_keys_shut_their_doors_on_the_world_map(self):
        ctx = FakeCtx(owned=("Balamb",))
        enforce_story_keys(ctx)
        self.assertEqual(ctx.word("Balamb"), 273)               # owned: vanilla
        self.assertEqual(ctx.word("Deling City"), 0xFFFF)       # missing: shut
        self.assertEqual(ctx.word("Fire Cavern"), 0xFFFF)       # branch word shut
        self.assertNotIn("Balamb", ctx.doors_applied)
        self.assertIn("Deling City", ctx.doors_applied)

    def test_key_arrival_reopens_the_door_at_once(self):
        ctx = FakeCtx()
        enforce_story_keys(ctx)
        self.assertEqual(ctx.word("Winhill"), 0xFFFF)
        ctx.own("Winhill")
        enforce_story_keys(ctx)
        self.assertEqual(ctx.word("Winhill"), 393)
        self.assertNotIn("Winhill", ctx.doors_applied)

    def test_doors_reapplied_after_a_field_visit(self):
        ctx = FakeCtx()
        enforce_story_keys(ctx)
        ctx.set_state(module=1)
        enforce_story_keys(ctx)
        self.assertIsNone(ctx.doors_applied)
        ctx.reset_script()                 # the game re-read the script from disk
        ctx.set_state(module=2)
        enforce_story_keys(ctx)
        self.assertEqual(ctx.word("Deling City"), 0xFFFF)

    def test_story_pass_only_in_areas_mode(self):
        # Deling's door is walked through during the Galbadia beat (moment
        # 290..392); areas mode leaves it open then, story mode does not.
        for mode, expect in ((STORY_KEYS_AREAS, 264), (STORY_KEYS_STORY, 0xFFFF)):
            ctx = FakeCtx(mode=mode)
            ctx.set_state(moment=333)
            enforce_story_keys(ctx)
            self.assertEqual(ctx.word("Deling City"), expect, mode)
            self.assertEqual(ctx.word("Winhill"), 0xFFFF, mode)   # no story beat: shut

    def test_mismatched_script_is_left_alone(self):
        ctx = FakeCtx()
        off = STORY_KEY_AREAS["Dollet"].lock[0][0]
        ctx.ff8.write_u16(ENTRANCE_SCRIPT + off, 0x1234)
        with self.assertLogs("Client", level="WARNING") as logs:
            enforce_story_keys(ctx)
        self.assertEqual(ctx.word("Dollet"), 0x1234)
        self.assertEqual(ctx.word("Timber"), 0xFFFF)              # others still shut
        self.assertTrue(any("Dollet" in line for line in logs.output))
        # log-once: a second pass stays quiet
        ctx.doors_applied = None
        with mock.patch("worlds.ff8.client.logger.warning") as warn:
            enforce_story_keys(ctx)
            warn.assert_not_called()

    def test_locked_message_on_a_door_tile(self):
        ctx = FakeCtx()
        ctx.set_state(pos=(12390, -26709, -301), door_tile=True)   # Balamb's door
        with self.assertLogs("Client", level="INFO") as logs:
            enforce_story_keys(ctx)
        self.assertTrue(any("Locked: Key: Balamb" in line for line in logs.output))
        with mock.patch("worlds.ff8.client.logger.info") as info:
            enforce_story_keys(ctx)                                 # rate-limited
            info.assert_not_called()

    def test_backstop_reports_a_shut_door_entered(self):
        ctx = FakeCtx()
        enforce_story_keys(ctx)
        ctx.set_state(module=1)
        ctx.ff8.write_bytes(WM_EXIT_REQUEST, bytes([1, 0, 8, 0xFF]))   # wm08 = Deling
        with self.assertLogs("Client", level="WARNING") as logs:
            enforce_story_keys(ctx)
        self.assertTrue(any("Deling City" in line for line in logs.output))

    def test_nothing_happens_without_the_option(self):
        ctx = FakeCtx()
        ctx.slot_data = {}
        enforce_story_keys(ctx)
        self.assertEqual(ctx.word("Deling City"), 264)
        self.assertEqual(doors_to_shut(ctx), set())

    def test_keys_unlock_warps(self):
        ctx = FakeCtx(owned=("Deling City", "Missile Base"))
        self.assertEqual(received_warp_keys(ctx), {"delingcity"})   # no warp for the base

    def test_apply_is_idempotent(self):
        ctx = FakeCtx()
        shut = doors_to_shut(ctx)
        apply_doors(ctx, shut)
        before = bytes(ctx.ff8.mem[ENTRANCE_SCRIPT:ENTRANCE_SCRIPT + 0xA5C])
        apply_doors(ctx, shut)
        self.assertEqual(before, bytes(ctx.ff8.mem[ENTRANCE_SCRIPT:ENTRANCE_SCRIPT + 0xA5C]))
