"""Vehicle moment-window + seeding (vehicle_unlocks), against a fake process.

Two things are load-bearing and easy to get wrong:

1. park_vehicle_at_char must copy the player's FULL 32-bit X/Y (low AND high
   words). The high word of Y ([3]) is a real coordinate, not a marker; zeroing
   it throws the vehicle 65536 units (one world-map segment) away — the bug that
   defeated every earlier relocation attempt.

2. The moment-window fakes GAME_MOMENT only TRANSIENTLY around a battle (through
   the battle and a short grace after returning to the world map, so the rebuild
   spawns the vehicle), then restores the true value. It must never fake on the
   idle world map (a long Disc-mismatch, suspected crash cause), never in a
   field (its scripts read the moment — black-screens), never in a menu (a save
   would capture it); and every moment reader must see the true value while a
   fake is live.
"""

import struct
import unittest
from unittest import mock

from ..items import BASE_ID
from ..memory import (FF8Interface, GAME_MOMENT, IN_MENU, MODULE_DISPATCH,
                      WM_AVATAR_TYPE, WM_CHAR_POS, WM_RAGNAROK_POS,
                      WM_VEHICLE_FLAGS, WM_FLAG_RAGNAROK)
from ..client import (MOMENT_GRACE_SECONDS, VEHICLE_FAKE_MARGIN, VEHICLE_GRANTS,
                      VEHICLE_PARK_NUDGE, moment_true, restore_true_moment,
                      seed_vehicles, snapshot_true, update_moment_window,
                      WITHHOLD_PARK_XY, vehicle_blacked_out,
                      vehicle_window_target, withhold_vehicles)

RAG_THRESHOLD = VEHICLE_GRANTS["ragnarok"][3]     # 3150
RAG_ITEM = BASE_ID + 311                           # "Ragnarok" full AP id
FAKE = RAG_THRESHOLD + VEHICLE_FAKE_MARGIN


class FakeClock:
    """Controllable monotonic clock so the grace window can be advanced."""

    def __init__(self):
        self.t = 1000.0

    def monotonic(self):
        return self.t

    def advance(self, dt):
        self.t += dt


class FakeProc(FF8Interface):
    """FF8Interface with all primitives backed by one flat bytearray, addressed
    by the raw module offsets the client uses (base 0)."""

    SIZE = 0x1D00000                                # covers up to WM_AVATAR_TYPE

    def __init__(self):
        super().__init__()
        self.mem = bytearray(self.SIZE)

    @property
    def attached(self) -> bool:
        return True

    def read_bytes(self, off, size):
        return bytes(self.mem[off:off + size])

    def write_bytes(self, off, data):
        self.mem[off:off + len(data)] = data

    def read_u8(self, off):
        return self.mem[off]

    def read_u16(self, off):
        return int.from_bytes(self.mem[off:off + 2], "little")

    def read_u32(self, off):
        return int.from_bytes(self.mem[off:off + 4], "little")

    def write_u8(self, off, v):
        self.mem[off] = v & 0xFF

    def write_u16(self, off, v):
        self.mem[off:off + 2] = (v & 0xFFFF).to_bytes(2, "little")

    def write_u32(self, off, v):
        self.mem[off:off + 4] = (v & 0xFFFFFFFF).to_bytes(4, "little")


class _Item:
    def __init__(self, item):
        self.item = item


class FakeCtx:
    """Just the attributes the window functions touch."""

    def __init__(self, owned=("ragnarok",), vehicle_unlocks=True, vehicle_gates=False):
        self.ff8 = FakeProc()
        self.slot_data = {"vehicle_unlocks": 1 if vehicle_unlocks else 0,
                          "vehicle_gates": 1 if vehicle_gates else 0}
        ids = {"ragnarok": RAG_ITEM}
        self.items_received = [_Item(ids[k]) for k in owned]
        self.moment_faked = False
        self.true_moment = None
        self._moment_fake_value = None
        self._moment_grace_until = 0.0

    # world-state setters used by the tests
    def set_state(self, module=2, in_menu=0, avatar=0, moment=30):
        self.ff8.write_u16(MODULE_DISPATCH, module)
        self.ff8.write_u8(IN_MENU, in_menu)
        self.ff8.write_u32(WM_AVATAR_TYPE, avatar)
        self.ff8.write_u16(GAME_MOMENT, moment)


class TestParkVehicle(unittest.TestCase):
    def test_full_32bit_copy_preserves_y_high_word(self):
        ff8 = FakeProc()
        # a player record whose Y is a real int32 with a nonzero high word
        # (Y = -27528 => high word -1): the segment info the old code discarded
        rec = struct.pack("<iihh", 14168, -27528, -451, 99)  # Xi, Yi, height, heading
        ff8.write_bytes(WM_CHAR_POS, rec)
        x, y = ff8.park_vehicle_at_char(WM_RAGNAROK_POS, WM_FLAG_RAGNAROK, x_nudge=300)
        out = ff8.read_bytes(WM_RAGNAROK_POS, 12)
        ox = int.from_bytes(out[0:4], "little", signed=True)
        oy = int.from_bytes(out[4:8], "little", signed=True)
        oheading = int.from_bytes(out[10:12], "little", signed=True)
        self.assertEqual(ox, 14168 + 300)      # X nudged by the offset
        self.assertEqual(oy, -27528)           # full 32-bit Y preserved (no wrap)
        self.assertEqual(oheading, 1)          # heading forced valid
        self.assertEqual((x, y), (14468, -27528))
        # availability bit set
        self.assertTrue(ff8.read_u8(WM_VEHICLE_FLAGS) & WM_FLAG_RAGNAROK)

    def test_x_nudge_crosses_low_word_boundary(self):
        # X whose low word is near 0xFFFF: the +300 must carry into the high
        # word, not wrap the low word (that would jump a segment in X).
        ff8 = FakeProc()
        ff8.write_bytes(WM_CHAR_POS, struct.pack("<iihh", 32700, 5000, -400, 0))
        ff8.park_vehicle_at_char(WM_RAGNAROK_POS, WM_FLAG_RAGNAROK, x_nudge=300)
        out = ff8.read_bytes(WM_RAGNAROK_POS, 12)
        self.assertEqual(int.from_bytes(out[0:4], "little", signed=True), 33000)


class TestMomentWindow(unittest.TestCase):
    def setUp(self):
        # drive client.time.monotonic from a controllable clock
        self.clock = FakeClock()
        self._patch = mock.patch("worlds.ff8.client.time", self.clock)
        self._patch.start()
        self.addCleanup(self._patch.stop)

    def test_no_fake_on_idle_world_map(self):
        # THE key safety property: standing on the world map with no recent
        # battle must NOT fake the moment (that was the continuous-fake crash).
        ctx = FakeCtx()
        ctx.set_state(module=2, moment=30)
        update_moment_window(ctx)
        self.assertFalse(ctx.moment_faked)
        self.assertEqual(ctx.ff8.game_moment(), 30)

    def test_fakes_in_battle_then_grace_on_world_map(self):
        ctx = FakeCtx()
        ctx.set_state(module=3, moment=30)       # a battle
        update_moment_window(ctx)
        self.assertTrue(ctx.moment_faked)
        self.assertEqual(ctx.true_moment, 30)
        self.assertEqual(ctx.ff8.game_moment(), FAKE)
        # return to the world map within the grace window -> still faked so the
        # rebuild spawns the vehicle
        ctx.ff8.write_u16(MODULE_DISPATCH, 2)
        self.clock.advance(1.0)                  # < MOMENT_GRACE_SECONDS
        update_moment_window(ctx)
        self.assertTrue(ctx.moment_faked)
        self.assertEqual(ctx.ff8.game_moment(), FAKE)

    def test_restores_after_grace_expires(self):
        ctx = FakeCtx()
        ctx.set_state(module=3, moment=30)
        update_moment_window(ctx)
        ctx.ff8.write_u16(MODULE_DISPATCH, 2)    # back on the world map
        self.clock.advance(MOMENT_GRACE_SECONDS + 0.5)   # grace has elapsed
        update_moment_window(ctx)
        self.assertFalse(ctx.moment_faked)
        self.assertEqual(ctx.ff8.game_moment(), 30)      # true moment restored

    def test_restores_when_menu_opens_during_grace(self):
        ctx = FakeCtx()
        ctx.set_state(module=3, moment=30)
        update_moment_window(ctx)
        ctx.ff8.write_u16(MODULE_DISPATCH, 2)
        ctx.ff8.write_u8(IN_MENU, 1)             # save menu, still inside grace
        update_moment_window(ctx)
        self.assertFalse(ctx.moment_faked)
        self.assertEqual(ctx.ff8.game_moment(), 30)

    def test_restores_and_ends_grace_in_field(self):
        ctx = FakeCtx()
        ctx.set_state(module=3, moment=30)
        update_moment_window(ctx)
        ctx.ff8.write_u16(MODULE_DISPATCH, 1)    # a field: scripts read the moment
        update_moment_window(ctx)
        self.assertEqual(ctx.ff8.game_moment(), 30)
        update_moment_window(ctx)                # and stays true for the field's whole life
        self.assertFalse(ctx.moment_faked)
        self.assertEqual(ctx.ff8.game_moment(), 30)

    def test_field_exit_opens_grace(self):
        # leaving a field for the world map rebuilds the map: the grace must
        # open there too, then expire like the battle grace
        ctx = FakeCtx()
        clock = FakeClock()
        with mock.patch("worlds.ff8.client.time.monotonic", clock.monotonic):
            ctx.set_state(module=1, moment=30)          # in a field
            update_moment_window(ctx)
            self.assertEqual(ctx.ff8.game_moment(), 30)
            ctx.set_state(module=2, moment=30)          # back on the world map
            update_moment_window(ctx)
            self.assertEqual(ctx.ff8.game_moment(), FAKE)
            clock.advance(MOMENT_GRACE_SECONDS + 0.1)
            update_moment_window(ctx)
            self.assertEqual(ctx.ff8.game_moment(), 30)
            update_moment_window(ctx)                   # staying put: no re-fake
            self.assertEqual(ctx.ff8.game_moment(), 30)

    def test_no_fake_while_riding(self):
        ctx = FakeCtx()
        ctx.set_state(module=3, moment=30, avatar=0x32)  # already aboard
        update_moment_window(ctx)
        self.assertFalse(ctx.moment_faked)
        self.assertEqual(ctx.ff8.game_moment(), 30)

    def test_no_fake_when_option_off(self):
        ctx = FakeCtx(vehicle_unlocks=False)
        ctx.set_state(module=3, moment=30)
        update_moment_window(ctx)
        self.assertFalse(ctx.moment_faked)
        self.assertEqual(ctx.ff8.game_moment(), 30)

    def test_no_fake_when_not_owned(self):
        ctx = FakeCtx(owned=())
        ctx.set_state(module=3, moment=30)
        update_moment_window(ctx)
        self.assertFalse(ctx.moment_faked)

    def test_window_off_once_story_reaches_threshold(self):
        ctx = FakeCtx()
        ctx.set_state(module=3, moment=RAG_THRESHOLD + 100)  # story already there
        self.assertIsNone(vehicle_window_target(ctx))
        update_moment_window(ctx)
        self.assertFalse(ctx.moment_faked)

    def test_adopts_external_moment_change(self):
        ctx = FakeCtx()
        ctx.set_state(module=3, moment=30)
        update_moment_window(ctx)
        self.assertTrue(ctx.moment_faked)
        # the game itself advances the story moment (not our fake value)
        ctx.ff8.write_u16(GAME_MOMENT, 45)
        update_moment_window(ctx)
        # 45 is the new truth; still < threshold and in battle, so re-fake off it
        self.assertEqual(ctx.true_moment, 45)
        self.assertEqual(ctx.ff8.game_moment(), FAKE)

    def test_readers_see_true_moment_while_faked(self):
        ctx = FakeCtx()
        ctx.set_state(module=3, moment=30)
        update_moment_window(ctx)
        self.assertEqual(moment_true(ctx), 30)
        self.assertEqual(snapshot_true(ctx).game_moment(), 30)   # not the fake
        self.assertNotEqual(ctx.ff8.game_moment(), 30)           # memory is faked

    def test_restore_true_moment_is_idempotent(self):
        ctx = FakeCtx()
        ctx.set_state(module=3, moment=30)
        update_moment_window(ctx)
        restore_true_moment(ctx)
        self.assertEqual(ctx.ff8.game_moment(), 30)
        restore_true_moment(ctx)                 # second call: no-op, no crash
        self.assertEqual(ctx.ff8.game_moment(), 30)


class TestSeeding(unittest.TestCase):
    def test_parks_only_off_the_world_map(self):
        ctx = FakeCtx()
        # on the world map: seeding sets the flag but must NOT park (the live
        # vehicle object would clobber the write and the reload reads stale)
        ctx.set_state(module=2, moment=30)
        ctx.ff8.write_bytes(WM_CHAR_POS, struct.pack("<iihh", 100, 200, -400, 0))
        seed_vehicles(ctx)
        self.assertTrue(ctx.ff8.read_u8(WM_VEHICLE_FLAGS) & WM_FLAG_RAGNAROK)
        self.assertEqual(ctx.ff8.read_bytes(WM_RAGNAROK_POS, 12), bytes(12))

        # off the world map (in a battle): now it parks beside the player,
        # offset by the Ragnarok's own X nudge (500)
        ctx.ff8.write_u16(MODULE_DISPATCH, 3)
        seed_vehicles(ctx)
        out = ctx.ff8.read_bytes(WM_RAGNAROK_POS, 12)
        self.assertEqual(int.from_bytes(out[0:4], "little", signed=True),
                         100 + VEHICLE_PARK_NUDGE["ragnarok"])

    def test_no_seed_when_option_off(self):
        ctx = FakeCtx(vehicle_unlocks=False)
        ctx.ff8.write_u16(MODULE_DISPATCH, 3)
        ctx.ff8.write_bytes(WM_CHAR_POS, struct.pack("<iihh", 100, 200, -400, 0))
        seed_vehicles(ctx)
        self.assertEqual(ctx.ff8.read_bytes(WM_RAGNAROK_POS, 12), bytes(12))
        self.assertFalse(ctx.ff8.read_u8(WM_VEHICLE_FLAGS) & WM_FLAG_RAGNAROK)

    def test_kept_available_after_the_story_hands_it_over(self):
        # past the vanilla threshold: the bit is re-set (a script that took
        # the ship back is undone) but the ship is NOT moved any more
        ctx = FakeCtx()
        ctx.set_state(module=3, moment=RAG_THRESHOLD + 200)
        ctx.ff8.write_bytes(WM_CHAR_POS, struct.pack("<iihh", 100, 200, -400, 0))
        seed_vehicles(ctx)
        self.assertTrue(ctx.ff8.read_u8(WM_VEHICLE_FLAGS) & WM_FLAG_RAGNAROK)
        self.assertEqual(ctx.ff8.read_bytes(WM_RAGNAROK_POS, 12), bytes(12))

    def test_hands_off_during_story_blackout(self):
        # the Lunatic Pandora attack (3790-4005) owns the Ragnarok: no bit, no
        # parking, no fake window
        ctx = FakeCtx()
        ctx.set_state(module=3, moment=3800)
        ctx.ff8.write_bytes(WM_CHAR_POS, struct.pack("<iihh", 100, 200, -400, 0))
        seed_vehicles(ctx)
        self.assertFalse(ctx.ff8.read_u8(WM_VEHICLE_FLAGS) & WM_FLAG_RAGNAROK)
        self.assertEqual(ctx.ff8.read_bytes(WM_RAGNAROK_POS, 12), bytes(12))
        ctx.set_state(module=3, moment=2600)        # in space, pre-threshold
        self.assertIsNone(vehicle_window_target(ctx))
        seed_vehicles(ctx)
        self.assertFalse(ctx.ff8.read_u8(WM_VEHICLE_FLAGS) & WM_FLAG_RAGNAROK)

    def test_blackout_table(self):
        self.assertTrue(vehicle_blacked_out("ragnarok", 3790))
        self.assertTrue(vehicle_blacked_out("ragnarok", 4004))
        self.assertFalse(vehicle_blacked_out("ragnarok", 4005))
        self.assertFalse(vehicle_blacked_out("ragnarok", 3150))
        self.assertTrue(vehicle_blacked_out("ragnarok", 2544))
        self.assertFalse(vehicle_blacked_out("nope", 30))


class TestWithhold(unittest.TestCase):
    """vehicle_gates: the story's own vehicle is parked out at sea until the
    item (the availability bit is never touched — it gates nothing live)."""

    def _ctx(self, **kw):
        ctx = FakeCtx(owned=(), vehicle_gates=True, **kw)
        ctx.ff8.write_u8(WM_VEHICLE_FLAGS, WM_FLAG_RAGNAROK)   # the story granted it
        ctx.ff8.write_bytes(WM_RAGNAROK_POS, struct.pack("<iihh", 100, 200, -400, 0))
        return ctx

    def _rag_xy(self, ctx):
        rec = ctx.ff8.read_bytes(WM_RAGNAROK_POS, 12)
        return struct.unpack("<ii", rec[:8])

    def test_parks_at_sea_off_map_past_threshold(self):
        ctx = self._ctx()
        ctx.set_state(module=1, moment=RAG_THRESHOLD + 10)       # in a field
        withhold_vehicles(ctx)
        self.assertEqual(self._rag_xy(ctx), WITHHOLD_PARK_XY)
        self.assertTrue(ctx.ff8.read_u8(WM_VEHICLE_FLAGS) & WM_FLAG_RAGNAROK)

    def test_never_on_the_world_map_or_before_threshold(self):
        ctx = self._ctx()
        ctx.set_state(module=2, moment=RAG_THRESHOLD + 10)       # live object owns the block
        withhold_vehicles(ctx)
        self.assertEqual(self._rag_xy(ctx), (100, 200))
        ctx.set_state(module=1, moment=30)                       # story has not handed it over
        withhold_vehicles(ctx)
        self.assertEqual(self._rag_xy(ctx), (100, 200))

    def test_never_while_riding_or_in_blackout(self):
        ctx = self._ctx()
        ctx.set_state(module=1, moment=RAG_THRESHOLD + 10, avatar=0x31)
        withhold_vehicles(ctx)
        self.assertEqual(self._rag_xy(ctx), (100, 200))
        ctx.set_state(module=1, moment=3800)                     # Lunatic Pandora attack
        withhold_vehicles(ctx)
        self.assertEqual(self._rag_xy(ctx), (100, 200))

    def test_owned_item_ends_the_withholding(self):
        ctx = FakeCtx(owned=("ragnarok",), vehicle_gates=True)
        ctx.ff8.write_bytes(WM_RAGNAROK_POS, struct.pack("<iihh", 100, 200, -400, 0))
        ctx.set_state(module=1, moment=RAG_THRESHOLD + 10)
        withhold_vehicles(ctx)
        self.assertEqual(self._rag_xy(ctx), (100, 200))

    def test_owned_item_brings_a_withheld_ship_back(self):
        # the ship was parked at sea before the item arrived: the next off-map
        # tick re-parks it beside the player, even past the story hand-over
        ctx = FakeCtx(owned=("ragnarok",), vehicle_gates=True)
        ctx.ff8.write_bytes(WM_RAGNAROK_POS, struct.pack("<iihh", *WITHHOLD_PARK_XY, -400, 0))
        ctx.ff8.write_bytes(WM_CHAR_POS, struct.pack("<iihh", 1000, 2000, -400, 0))
        ctx.set_state(module=1, moment=RAG_THRESHOLD + 10)
        seed_vehicles(ctx)
        self.assertEqual(self._rag_xy(ctx), (1000 + VEHICLE_PARK_NUDGE["ragnarok"], 2000))

    def test_gate_option_off_does_nothing(self):
        ctx = FakeCtx(owned=(), vehicle_gates=False)
        ctx.ff8.write_bytes(WM_RAGNAROK_POS, struct.pack("<iihh", 100, 200, -400, 0))
        ctx.set_state(module=1, moment=RAG_THRESHOLD + 10)
        withhold_vehicles(ctx)
        self.assertEqual(self._rag_xy(ctx), (100, 200))


if __name__ == "__main__":
    unittest.main()
