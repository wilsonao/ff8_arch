"""Test suite for the FF8 apworld.

Run from an Archipelago source checkout with the ff8 world in worlds/:

    pytest worlds/ff8/test

Every options-combo class inherits WorldTestBase's default tests (all-state
reachability, empty-state progress, and a real fill), so each class is a full
generation regression test for that combination.
"""

from test.bases import WorldTestBase

from ..items import GF_ORDER


class FF8TestBase(WorldTestBase):
    game = "Final Fantasy VIII"
    player = 1


ALL_TOGGLES_ON = {
    "draw_point_checks": True,
    "triple_triad_checks": True,
    "optional_boss_checks": True,
    "rare_card_checks": True,
    "sidequest_checks": True,
    "magazine_checks": True,
    "stat_checks": True,
    "gf_ability_checks": True,
}

ALL_TOGGLES_OFF = {k: False for k in ALL_TOGGLES_ON}

GF_ITEM_NAMES = [f"GF {gf}" for gf in GF_ORDER]
