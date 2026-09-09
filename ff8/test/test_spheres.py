"""Sphere shape (docs/plan-sphere-gating.md): the seed must play as a
staircase, not two plateaus. Measured with free story events collapsed
(item_spheres), the way a player experiences it.

Bounds are deliberately loose: progression balancing and other worlds reshape
a multiworld anyway. They catch a regression back to "everything is sphere 1"
and a ladder that fill cannot satisfy.
"""

from BaseClasses import CollectionState
from Fill import distribute_items_restrictive

from . import ALL_TOGGLES_ON, GF_ITEM_NAMES, FF8TestBase, item_spheres


class SphereShapeMixin:
    seeds = range(1, 6)
    max_first_sphere: int
    min_depth: int
    first_sphere_discs: set[int] | None = {1}

    def test_sphere_shape(self):
        from ..regions import DISC_OF_BEAT
        for seed in self.seeds:
            with self.subTest(seed=seed):
                self.world_setup(seed)
                distribute_items_restrictive(self.multiworld)
                spheres = item_spheres(self.multiworld, self.player)
                unreachable = spheres.pop()
                self.assertEqual(unreachable, [], f"seed {seed}: unreachable checks")
                self.assertLessEqual(len(spheres[0]), self.max_first_sphere,
                                     f"seed {seed}: sphere 1 too big")
                self.assertGreaterEqual(len(spheres), self.min_depth,
                                        f"seed {seed}: seed too shallow")
                if self.first_sphere_discs is not None:
                    discs = {DISC_OF_BEAT.get(loc.parent_region.name)
                             for loc in spheres[0]}
                    self.assertEqual(discs, self.first_sphere_discs,
                                     f"seed {seed}: sphere 1 leaks past Disc 1")


class TestNormalGatesDefault(SphereShapeMixin, FF8TestBase):
    auto_construct = False
    options = {}
    max_first_sphere = 70
    min_depth = 8


class TestNormalGatesAllChecks(SphereShapeMixin, FF8TestBase):
    auto_construct = False
    options = {**ALL_TOGGLES_ON}
    max_first_sphere = 90
    min_depth = 8


class TestTightGates(SphereShapeMixin, FF8TestBase):
    auto_construct = False
    options = {"story_gates": "tight"}
    max_first_sphere = 40
    min_depth = 10


class TestTightGatesNoStartingGFs(SphereShapeMixin, FF8TestBase):
    auto_construct = False
    options = {**ALL_TOGGLES_ON, "story_gates": "tight", "starting_gfs": 0,
               "gfs_required_for_disc3": 12}
    max_first_sphere = 40
    min_depth = 10


class TestGatesOffIsThePlateau(SphereShapeMixin, FF8TestBase):
    """story_gates off must keep the pre-0.4 shape (documented regression
    baseline, not a target)."""
    auto_construct = False
    seeds = range(1, 3)
    options = {"story_gates": "off"}
    max_first_sphere = 240
    min_depth = 3
    first_sphere_discs = None


class TestVehicleUnlocksOpenTheWorld(FF8TestBase):
    """With vehicle_unlocks, the vehicle item alone reaches its hub: the
    Ragnarok opens the island world draw points from the start."""
    options = {**ALL_TOGGLES_ON, "vehicle_unlocks": True, "starting_gfs": 0}

    def _hub_location(self, hub: str):
        return next(loc for loc in self.multiworld.get_locations(self.player)
                    if loc.parent_region.name == hub)

    def _check(self, hub: str, vehicle: str):
        # World draw points also need a GF to draw with; give one so the
        # vehicle is the only thing that matters.
        state = CollectionState(self.multiworld)
        state.collect(self.get_item_by_name(GF_ITEM_NAMES[0]))
        loc = self._hub_location(hub)
        self.assertFalse(state.can_reach(loc.name, "Location", self.player))
        state.collect(self.get_item_by_name(vehicle))
        self.assertTrue(state.can_reach(loc.name, "Location", self.player))

    def test_ragnarok_item_reaches_flight_hub(self):
        self._check("Ragnarok Flight", "Ragnarok")

    def test_ragnarok_item_reaches_garden_travel_hub(self):
        self._check("Garden Travel", "Ragnarok")


class TestHubsWithoutVehicles(FF8TestBase):
    """Without vehicle items the hubs open with their vanilla grant beat only."""
    options = {**ALL_TOGGLES_ON, "vehicle_unlocks": False}

    def test_hub_follows_grant_beat(self):
        from ..regions import HUBS
        for hub, (grant_beat, _vehicle) in HUBS.items():
            with self.subTest(hub=hub):
                entrances = [e.parent_region.name for e in
                             self.multiworld.get_region(hub, self.player).entrances]
                self.assertEqual(entrances, [grant_beat])


class TestVehicleGates(FF8TestBase):
    """vehicle_gates: the piloting beats need the vehicle item itself."""
    options = {**ALL_TOGGLES_ON, "vehicle_unlocks": True, "vehicle_gates": True,
               "story_gates": "off"}

    def test_sorceress_memorial_needs_ragnarok(self):
        state = CollectionState(self.multiworld)
        self.collect_all_but(["Ragnarok"], state)
        self.assertFalse(state.can_reach("Tears Point: Fallen Relic", "Location", self.player))
        self.assertTrue(state.can_reach("Esthar: Lunar Base Launch", "Location", self.player))
        state.collect(self.get_item_by_name("Ragnarok"))
        self.assertTrue(state.can_reach("Tears Point: Fallen Relic", "Location", self.player))


class TestVehicleGatesFill(FF8TestBase):
    """A real fill under vehicle_gates places the vehicles early enough."""
    options = {**ALL_TOGGLES_ON, "vehicle_unlocks": True, "vehicle_gates": True}


class TestLadderNeverExceedsThePool(FF8TestBase):
    """Every ladder row must be satisfiable from the items that exist under
    any option mix: the counts are capped at the group totals, and the
    Disc 3 anchor keeps its meaning."""
    auto_construct = False

    def test_caps_and_anchor(self):
        from ..regions import (CHARACTER_TOTAL, COMMAND_TOTAL, GF_TOTAL,
                               JUNCTION_TOTAL, REGION_CHAIN, gate_requirements)
        caps = {"GFs": GF_TOTAL, "Character Unlocks": CHARACTER_TOTAL,
                "Junction Unlocks": JUNCTION_TOTAL, "Command Unlocks": COMMAND_TOTAL}
        for mode in ("off", "normal", "tight"):
            for anchor in (0, 6, 12):
                for beat in REGION_CHAIN:
                    needed = gate_requirements(mode, beat, anchor, True, True, True)
                    for group, count in needed.items():
                        self.assertLessEqual(count, caps[group], (mode, anchor, beat))
        for mode in ("normal", "tight"):
            self.assertEqual(gate_requirements(mode, "Edea's House", 6, False, False, False),
                             {"GFs": 6})
            self.assertEqual(gate_requirements(mode, "Edea's House", 12, False, False, False),
                             {"GFs": 12})
            self.assertEqual(gate_requirements(mode, "Galbadia", 0, False, False, False), {})
        self.assertEqual(gate_requirements("off", "Galbadia", 6, True, True, True), {})
        self.assertEqual(gate_requirements("off", "Edea's House", 6, True, True, True),
                         {"GFs": 6})
