"""The study panel grants Quezacotl AND Shiva in one interaction.

Lexra's report (2026-09-11): with Quezacotl precollected, reading the panel
only sent Shiva's check — Quezacotl's flag was already set by the client, so
its rising-edge trigger never fired and the check waited for the moment-30
fallback (after Fire Cavern). Each panel location now also fires on its
sibling's vanilla flag.
"""

import unittest

from ..client import trigger_satisfied
from ..locations import LOCATION_TABLE


class FakeCtx:
    def __init__(self, prev_gf_flags, ap_set):
        self.prev_gf_flags = prev_gf_flags
        self.ap_set_gf_flags = set(ap_set)


def panel(name):
    return next(loc for loc in LOCATION_TABLE if loc.name == name)


def fires(loc, ctx, gf_flags):
    return any(trigger_satisfied(ctx, k, v, None, gf_flags, {})
               for k, v in loc.triggers if k == "gf_flag")


class TestStudyPanelSiblings(unittest.TestCase):
    def setUp(self):
        self.quez = panel("Study Panel: Quezacotl")
        self.shiva = panel("Study Panel: Shiva")

    def test_precollected_quezacotl_still_fires_on_panel_read(self):
        # Quezacotl granted by us at game start; the panel then sets Shiva.
        before = [True, False] + [False] * 14
        after = [True, True] + [False] * 14
        ctx = FakeCtx(before, ap_set={0})
        self.assertTrue(fires(self.shiva, ctx, after))
        self.assertTrue(fires(self.quez, ctx, after))

    def test_precollected_shiva_still_fires_on_panel_read(self):
        before = [False, True] + [False] * 14
        after = [True, True] + [False] * 14
        ctx = FakeCtx(before, ap_set={1})
        self.assertTrue(fires(self.quez, ctx, after))
        self.assertTrue(fires(self.shiva, ctx, after))

    def test_both_vanilla_fire_together(self):
        ctx = FakeCtx([False] * 16, ap_set=set())
        after = [True, True] + [False] * 14
        self.assertTrue(fires(self.quez, ctx, after))
        self.assertTrue(fires(self.shiva, ctx, after))

    def test_both_precollected_do_not_fire_on_our_own_writes(self):
        # Both flags are ours: no vanilla edge, the story fallback must carry it.
        ctx = FakeCtx([False] * 16, ap_set={0, 1})
        after = [True, True] + [False] * 14
        self.assertFalse(fires(self.quez, ctx, after))
        self.assertFalse(fires(self.shiva, ctx, after))
        self.assertIn(("story", 30), self.quez.triggers)
        self.assertIn(("story", 30), self.shiva.triggers)

    def test_no_edge_no_fire(self):
        ctx = FakeCtx([True, True] + [False] * 14, ap_set=set())
        self.assertFalse(fires(self.quez, ctx, [True, True] + [False] * 14))
