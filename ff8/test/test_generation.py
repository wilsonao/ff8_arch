"""Multi-seed generation stability for the tightest option profiles.

A single-seed pass can hide flaky fills; the tight GF gate (0 starting GFs,
12 required for Disc 3, core locations only) is the configuration most likely
to fail intermittently, so it gets swept across many seeds.
"""

from Fill import distribute_items_restrictive

from . import ALL_TOGGLES_OFF, ALL_TOGGLES_ON, FF8TestBase


class GenerationSweepMixin:
    seeds = range(1, 21)

    def test_generation_across_seeds(self):
        for seed in self.seeds:
            with self.subTest(seed=seed):
                self.world_setup(seed)
                distribute_items_restrictive(self.multiworld)
                state = self.multiworld.get_all_state()
                self.assertTrue(self.multiworld.has_beaten_game(state, self.player),
                                f"seed {seed}: cannot beat game after fill")
                for location in self.multiworld.get_locations(self.player):
                    self.assertTrue(location.item is not None or location.address is None,
                                    f"seed {seed}: {location.name} left unfilled")


class TestTightCoreSweep(GenerationSweepMixin, FF8TestBase):
    auto_construct = False
    options = {**ALL_TOGGLES_OFF, "starting_gfs": 0, "gfs_required_for_disc3": 12}


class TestTightAllChecksSweep(GenerationSweepMixin, FF8TestBase):
    auto_construct = False
    seeds = range(1, 11)
    options = {**ALL_TOGGLES_ON, "starting_gfs": 0, "gfs_required_for_disc3": 12}


class TestDefaultSweep(GenerationSweepMixin, FF8TestBase):
    auto_construct = False
    seeds = range(1, 11)
    options = {"starting_gfs": 1}
