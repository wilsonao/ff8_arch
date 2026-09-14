"""Early entry (docs/plan-sync-feedback.md C3): an area flagged `early` puts
its first-opening checks in an "Early: <area>" region reachable from the
door's first beat (vanilla) or, with vehicle_unlocks, from the Menu with the
Ragnarok item; the area's key rule still applies to every check."""

import unittest

from . import ALL_TOGGLES_ON, FF8TestBase
from ..locations import LOCATION_DATA_BY_NAME
from ..regions import (EARLY_ENTRY_AREAS, EARLY_REGIONS, RAGNAROK_ITEM,
                       STORY_KEY_AREAS, early_area_gated, early_region_name,
                       logic_region)


class TestEarlyTables(unittest.TestCase):
    def test_flagged_areas(self):
        # Doors the game never gates on the story moment, plus the towns
        # whose interiors were surveyed live on a low-moment save.
        self.assertEqual(set(EARLY_ENTRY_AREAS),
                         {"Tomb of the Unknown King", "Centra Ruins", "Chocobo Forests",
                          "Winhill", "Shumi Village"})
        self.assertEqual({a for a in EARLY_ENTRY_AREAS if early_area_gated(a)},
                         {"Winhill", "Shumi Village"})

    def test_only_first_opening_checks_move(self):
        moved = {n for n, d in LOCATION_DATA_BY_NAME.items()
                 if logic_region(n, d.region) != d.region}
        self.assertIn("Draw Point: Centra Ruins (Aero)", moved)
        self.assertIn("Timber Maniacs: Centra Ruins", moved)
        self.assertIn("Tomb of the Unknown King: Brothers", moved)
        self.assertIn("Rare Card: Chicobo", moved)
        self.assertNotIn("Centra Ruins: Odin Defeated", moved)          # Garden War
        self.assertNotIn("Chocobo Forests Solved: 3", moved)            # Garden War
        self.assertIn("Draw Point: Winhill Village (Drain)", moved)
        self.assertIn("Draw Point: Shumi Village (Blizzaga)", moved)
        self.assertNotIn("Draw Point: Dollet Town Square (Silence)", moved)  # not flagged
        for name in moved:
            data = LOCATION_DATA_BY_NAME[name]
            area = next(a for a in EARLY_ENTRY_AREAS
                        if logic_region(name, data.region) == early_region_name(a))
            self.assertEqual(data.region, STORY_KEY_AREAS[area].first_beat, name)
        self.assertEqual(set(EARLY_REGIONS), {early_region_name(a) for a in EARLY_ENTRY_AREAS})


class TestEarlyWithShip(FF8TestBase):
    options = ALL_TOGGLES_ON | {"vehicle_unlocks": True, "story_keys": "areas"}

    def test_ship_and_key_open_the_area_from_the_start(self):
        loc = "Draw Point: Centra Ruins (Aero)"
        self.assertFalse(self.can_reach_location(loc))
        self.collect_by_name([RAGNAROK_ITEM])
        self.assertFalse(self.can_reach_location(loc))          # the key is still needed
        self.collect_by_name(["Key: Centra Ruins"])
        self.assertTrue(self.can_reach_location(loc))
        self.assertTrue(self.can_reach_location("Timber Maniacs: Centra Ruins"))
        # story-state checks stay on their beat
        self.assertFalse(self.can_reach_location("Centra Ruins: Odin Defeated"))
        self.assertFalse(self.can_reach_location("Draw Point: Dollet Town Square (Silence)"))

    def test_gated_town_needs_its_key_with_the_ship(self):
        loc = "Draw Point: Winhill Village (Drain)"
        self.collect_by_name([RAGNAROK_ITEM])
        self.assertFalse(self.can_reach_location(loc))
        self.collect_by_name(["Key: Winhill"])
        self.assertTrue(self.can_reach_location(loc))

    def test_tomb_from_the_start(self):
        self.collect_by_name([RAGNAROK_ITEM, "Key: Tomb of the Unknown King"])
        self.assertTrue(self.can_reach_location("Tomb of the Unknown King: Brothers"))
        self.assertTrue(self.can_reach_location("Rare Card: Sacred"))

    def test_early_region_entrances(self):
        for region_name, (first_beat, _v) in EARLY_REGIONS.items():
            region = self.multiworld.get_region(region_name, self.player)
            self.assertEqual(sorted(e.parent_region.name for e in region.entrances),
                             sorted(["Menu", first_beat]), region_name)

    def test_slot_data_flags_early_areas(self):
        table = self.world.fill_slot_data()["story_key_areas"]
        self.assertEqual({a for a, info in table.items() if info["early"]},
                         set(EARLY_ENTRY_AREAS))


class TestEarlyWithoutKeys(FF8TestBase):
    options = ALL_TOGGLES_ON | {"vehicle_unlocks": True, "story_keys": "off"}

    def test_ship_alone_opens_an_ungated_area(self):
        loc = "Draw Point: Centra Ruins (Aero)"
        self.assertFalse(self.can_reach_location(loc))
        self.collect_by_name([RAGNAROK_ITEM])
        self.assertTrue(self.can_reach_location(loc))

    def test_gated_town_stays_on_its_beat_without_keys(self):
        # Without story keys the client holds no door table, so it cannot
        # lower Winhill's gate: no Menu edge.
        region = self.multiworld.get_region(early_region_name("Winhill"), self.player)
        self.assertEqual([e.parent_region.name for e in region.entrances],
                         ["Balamb Liberation"])
        self.collect_by_name([RAGNAROK_ITEM])
        self.assertFalse(self.can_reach_location("Draw Point: Winhill Village (Drain)"))


class TestEarlyWithoutShip(FF8TestBase):
    options = ALL_TOGGLES_ON | {"vehicle_unlocks": False, "story_keys": "areas"}

    def test_vanilla_route_only(self):
        for region_name, (first_beat, _v) in EARLY_REGIONS.items():
            region = self.multiworld.get_region(region_name, self.player)
            self.assertEqual([e.parent_region.name for e in region.entrances],
                             [first_beat], region_name)
        self.collect_by_name([RAGNAROK_ITEM, "Key: Centra Ruins"])
        self.assertFalse(self.can_reach_location("Draw Point: Centra Ruins (Aero)"))


class TestEarlyEdeaGoal(FF8TestBase):
    options = ALL_TOGGLES_ON | {"goal": "edea", "vehicle_unlocks": True, "story_keys": "areas"}

    def test_truncated_world_keeps_only_disc1_early_areas(self):
        names = {r.name for r in self.multiworld.get_regions(self.player)}
        self.assertIn(early_region_name("Tomb of the Unknown King"), names)
        self.assertNotIn(early_region_name("Centra Ruins"), names)
        self.assertNotIn(early_region_name("Chocobo Forests"), names)
