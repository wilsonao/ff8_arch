"""Early entry, client side: the story-moment gate (unlock words) of an area
the table flags `early` is lowered only with the ship in the pool, the key
in hand and the true moment still below the gate, and put back otherwise.

No shipped area with a moment gate is flagged early yet (the interiors
still need a live survey), so these tests flag Winhill (gate 750) in the
slot table themselves.
"""

import unittest

from ..client import STORY_KEYS_AREAS, enforce_story_keys
from ..memory import ENTRANCE_SCRIPT
from ..regions import STORY_KEY_AREAS
from .test_story_doors import FakeCtx


def early_ctx(owned=("Winhill",), vehicle=True, moment=205, early=True):
    ctx = FakeCtx(STORY_KEYS_AREAS, owned=owned, areas=("Winhill", "Shumi Village"))
    ctx.slot_data["vehicle_unlocks"] = vehicle
    ctx.slot_data["story_key_areas"]["Winhill"]["early"] = early
    ctx.set_state(module=2, moment=moment)
    return ctx


class TestEarlyDoors(unittest.TestCase):
    def test_gate_lowered_with_ship_key_and_low_moment(self):
        ctx = early_ctx()
        enforce_story_keys(ctx)
        self.assertEqual(ctx.gate("Winhill"), 0)
        self.assertEqual(ctx.word("Winhill"), 393)          # the door itself is open
        self.assertEqual(ctx.early_applied, {"Winhill"})
        # Shumi: key missing and not flagged -> shut, gate untouched
        self.assertEqual(ctx.word("Shumi Village"), 0xFFFF)
        self.assertEqual(ctx.gate("Shumi Village"), 750)

    def test_gate_stays_vanilla_without_the_ship_or_key_or_flag(self):
        for kwargs in ({"vehicle": False}, {"owned": ()}, {"early": False}):
            with self.subTest(**kwargs):
                ctx = early_ctx(**kwargs)
                enforce_story_keys(ctx)
                self.assertEqual(ctx.gate("Winhill"), 750)
                self.assertEqual(ctx.early_applied, set())

    def test_gate_untouched_once_the_story_is_past_it(self):
        ctx = early_ctx(moment=750)
        enforce_story_keys(ctx)
        self.assertEqual(ctx.gate("Winhill"), 750)
        self.assertEqual(ctx.early_applied, set())

    def test_key_arrival_lowers_the_gate_at_once(self):
        ctx = early_ctx(owned=())
        enforce_story_keys(ctx)
        self.assertEqual(ctx.word("Winhill"), 0xFFFF)
        self.assertEqual(ctx.gate("Winhill"), 750)
        ctx.own("Winhill")
        enforce_story_keys(ctx)
        self.assertEqual(ctx.word("Winhill"), 393)
        self.assertEqual(ctx.gate("Winhill"), 0)

    def test_gate_restored_when_the_story_catches_up(self):
        ctx = early_ctx(moment=749)
        enforce_story_keys(ctx)
        self.assertEqual(ctx.gate("Winhill"), 0)
        ctx.set_state(module=2, moment=750)
        enforce_story_keys(ctx)
        self.assertEqual(ctx.gate("Winhill"), 750)

    def test_reapplied_after_a_field_visit(self):
        ctx = early_ctx()
        enforce_story_keys(ctx)
        ctx.set_state(module=1, moment=205)          # a field: the script reloads
        enforce_story_keys(ctx)
        self.assertIsNone(ctx.early_applied)
        ctx.reset_script()
        ctx.set_state(module=2, moment=205)
        enforce_story_keys(ctx)
        self.assertEqual(ctx.gate("Winhill"), 0)

    def test_mismatched_gate_word_is_left_alone(self):
        ctx = early_ctx()
        off = STORY_KEY_AREAS["Winhill"].unlock[0][0]
        ctx.ff8.write_u16(ENTRANCE_SCRIPT + off, 1234)
        with self.assertLogs("Client", level="WARNING"):
            enforce_story_keys(ctx)
        self.assertEqual(ctx.gate("Winhill"), 1234)
        self.assertEqual(ctx.word("Winhill"), 393)   # the whole door is skipped
