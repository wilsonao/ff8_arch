"""Story Keys (docs/plan-story-keys.md): key items, the door table the client
enforces, per-area location rules, and the story-mode beat gates."""

import unittest

from Fill import distribute_items_restrictive

from . import ALL_TOGGLES_ON, FF8TestBase, item_spheres
from ..items import item_name_groups
from ..locations import LOCATION_DATA_BY_NAME
from ..regions import (AREA_LOCATIONS, BEAT_INDEX, ENTRANCE_SCRIPT_LEN,
                       REGION_CHAIN, STORY_KEY_AREAS, STORY_KEY_BEATS,
                       area_of_location, story_key_name)
from .test_spheres import SphereShapeMixin


class TestKeyTable(unittest.TestCase):
    def test_every_area_prefix_matches_a_location(self):
        for area, prefixes in AREA_LOCATIONS.items():
            for prefix in prefixes:
                hits = [n for n in LOCATION_DATA_BY_NAME if n.startswith(prefix)]
                self.assertTrue(hits, f"{area}: prefix {prefix!r} matches nothing")

    def test_no_location_in_two_areas(self):
        for name in LOCATION_DATA_BY_NAME:
            areas = [a for a, ps in AREA_LOCATIONS.items()
                     if any(name.startswith(p) for p in ps)]
            self.assertLessEqual(len(areas), 1, f"{name}: {areas}")

    def test_area_locations_not_before_their_door(self):
        # A keyed check must sit in a beat at or after the beat whose story
        # first opens the door, else logic would demand a key the fill can
        # not yet have placed ahead of it.
        for name, data in LOCATION_DATA_BY_NAME.items():
            area = area_of_location(name)
            if area is None or data.region not in BEAT_INDEX:
                continue
            self.assertGreaterEqual(
                BEAT_INDEX[data.region], BEAT_INDEX[STORY_KEY_AREAS[area].first_beat],
                f"{name} ({data.region}) precedes {area}'s door")

    def test_patches_are_disjoint_and_in_range(self):
        seen = set()
        for area, data in STORY_KEY_AREAS.items():
            self.assertTrue(data.lock, f"{area} has no lock patch")
            for off, old, new in data.lock + data.unlock:
                self.assertTrue(0 <= off <= ENTRANCE_SCRIPT_LEN - 2)
                self.assertNotEqual(old, new)
                self.assertNotIn(off, seen, f"{area}: offset {off:#x} patched twice")
                seen.add(off)

    def test_story_beats_exist_and_follow_the_door(self):
        for area, data in STORY_KEY_AREAS.items():
            for beat in data.story_beats:
                self.assertIn(beat, REGION_CHAIN)
                self.assertGreaterEqual(BEAT_INDEX[beat], BEAT_INDEX[data.first_beat])
        self.assertIn("Key: Fire Cavern", STORY_KEY_BEATS["Fire Cavern"])
        self.assertIn("Key: Lunar Gate", STORY_KEY_BEATS["Lunar Base"])

    def test_key_items_exist(self):
        self.assertEqual(item_name_groups["Story Keys"],
                         {story_key_name(a) for a in STORY_KEY_AREAS})


class TestKeysOff(FF8TestBase):
    options = {"fast_travel": True}

    def test_no_keys_but_warps(self):
        names = [i.name for i in self.multiworld.itempool]
        self.assertFalse(set(names) & item_name_groups["Story Keys"])
        self.assertTrue(set(names) & item_name_groups["Warps"])
        self.assertEqual(self.world.fill_slot_data()["story_key_areas"], {})


class TestAreasMode(FF8TestBase):
    options = {**ALL_TOGGLES_ON, "story_keys": "areas", "fast_travel": True}

    def test_keys_replace_warps(self):
        # areas mode keeps every key in the pool (no beat depends on one).
        names = {i.name for i in self.multiworld.itempool}
        self.assertEqual(names & item_name_groups["Story Keys"],
                         item_name_groups["Story Keys"])
        self.assertFalse(names & item_name_groups["Warps"])

    def test_area_checks_need_their_key(self):
        self.assertAccessDependency(["Draw Point: Winhill Village (Drain)"],
                                    [["Key: Winhill"]], only_check_listed=True)
        self.assertAccessDependency(["Rare Card: Chicobo", "Chocobo Forests Solved: 3"],
                                    [["Key: Chocobo Forests"]], only_check_listed=True)

    def test_story_path_needs_no_key(self):
        # areas mode: the beats themselves never require a key.
        self.collect_all_but(list(item_name_groups["Story Keys"]))
        self.assertTrue(self.can_reach_location("Fire Cavern: Ifrit"))
        self.assertTrue(self.can_reach_location("Esthar: Lunar Base Launch"))

    def test_slot_data_carries_the_door_table(self):
        table = self.world.fill_slot_data()["story_key_areas"]
        self.assertEqual(set(table), set(STORY_KEY_AREAS))
        self.assertEqual(table["Balamb"]["lock"], [[0x356, 273, 0xFFFF]])
        self.assertEqual(table["Deling City"]["unlock"], [[0x29A, 333, 0]])
        self.assertEqual(table["Deling City"]["warp"], "delingcity")
        self.assertEqual(table["Lunar Gate"]["story_beats"], ["Lunar Base"])
        self.assertEqual(table["Lunar Gate"]["pass"], [[1310, 3150]])
        self.assertEqual(table["Balamb"]["segments"], [273])
        self.assertEqual(table["Fire Cavern"]["wm_fields"], [2])
        self.assertEqual(table["Esthar City"]["segments"], [406, 407, 438, 439])


class TestStoryMode(FF8TestBase):
    options = {"story_keys": "story"}

    def test_opening_keys_precollected(self):
        owned = {i.name for i in self.multiworld.precollected_items[self.player]}
        self.assertTrue({"Key: Balamb", "Key: Fire Cavern"} <= owned)
        pooled = {i.name for i in self.multiworld.itempool}
        self.assertFalse({"Key: Balamb", "Key: Fire Cavern"} & pooled)
        self.assertIn("Key: Deling City", pooled)

    def test_story_doors_gate_their_beats(self):
        self.assertAccessDependency(["Deling City: Sorceress Assassination"],
                                    [["Key: Deling City"]], only_check_listed=True)
        # The launch ends the Esthar beat; the key gates the beat after it.
        self.assertAccessDependency(["Cleared: Lunar Base"],
                                    [["Key: Lunar Gate"]], only_check_listed=True)

    def test_keys_are_progression(self):
        for item in self.multiworld.itempool:
            if item.name in item_name_groups["Story Keys"]:
                self.assertTrue(item.advancement, item.name)


class TestStoryModeSweep(FF8TestBase):
    auto_construct = False
    options = {**ALL_TOGGLES_ON, "story_keys": "story", "starting_gfs": 1}

    def test_keys_land_before_their_beats(self):
        for seed in range(1, 11):
            with self.subTest(seed=seed):
                self.world_setup(seed)
                distribute_items_restrictive(self.multiworld)
                spheres = item_spheres(self.multiworld, self.player)
                self.assertEqual(spheres.pop(), [], f"seed {seed}: unreachable checks")
                state = self.multiworld.get_all_state()
                self.assertTrue(self.multiworld.has_beaten_game(state, self.player))


class TestStoryModeSpheres(SphereShapeMixin, FF8TestBase):
    auto_construct = False
    options = {"story_keys": "story"}
    max_first_sphere = 70
    min_depth = 9


class TestEdeaGoalKeys(FF8TestBase):
    options = {"goal": "edea", "story_keys": "story", "starting_gfs": 1}

    def test_only_disc1_keys(self):
        names = ({i.name for i in self.multiworld.itempool}
                 | {i.name for i in self.multiworld.precollected_items[self.player]}
                 ) & item_name_groups["Story Keys"]
        self.assertIn("Key: Deling City", names)
        self.assertIn("Key: Tomb of the Unknown King", names)
        self.assertNotIn("Key: Winhill", names)
        self.assertNotIn("Key: Lunar Gate", names)
        self.assertEqual(set(self.world.fill_slot_data()["story_key_areas"]),
                         {n[len("Key: "):] for n in names})
