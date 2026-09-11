"""Multi-seed generation stability for the tightest option profiles.

A single-seed pass can hide flaky fills; the tight GF gate (0 starting GFs,
12 required for Disc 3, core locations only) is the configuration most likely
to fail intermittently, so it gets swept across many seeds.
"""

from Fill import distribute_items_restrictive

from . import ALL_TOGGLES_OFF, ALL_TOGGLES_ON, FF8TestBase
from ..options import OPTION_PRESETS


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


class TestEdeaGoalSweep(GenerationSweepMixin, FF8TestBase):
    """The edea goal removes every post-Disc-1 location, so the default lock
    items must fit — and keep fitting — in the truncated world."""
    auto_construct = False
    seeds = range(1, 11)
    options = {"goal": "edea", "starting_gfs": 1}


class TestSyncPresetSweep(GenerationSweepMixin, FF8TestBase):
    """The Sync preset is the edea goal with most check groups OFF, so the
    default lock items must still fit the small world on every seed."""
    auto_construct = False
    seeds = range(1, 11)
    options = {**OPTION_PRESETS["Sync"], "starting_gfs": 1}


class TestEdeaGoalWorldShape(FF8TestBase):
    options = {"goal": "edea"}

    def test_no_post_disc1_regions(self):
        regions = {r.name for r in self.multiworld.get_regions(self.player)}
        self.assertEqual(regions & {"Disc 2", "Disc 3", "Disc 4"}, set())

    def test_victory_is_edea(self):
        names = {loc.name for loc in self.multiworld.get_locations(self.player)}
        self.assertIn("Edea Defeated", names)
        self.assertNotIn("Ultimecia Defeated", names)


class TestEdeaGoalWarpPool(FF8TestBase):
    """Warp items only for destinations the truncated world contains: an edea
    seed shipping "Warp: Esthar" leads nowhere (Hdot's sync, 2026-09-10)."""
    options = {"goal": "edea", "fast_travel": True}

    def test_no_post_disc1_warps(self):
        from ..warp import WARP_BY_KEY, WARP_ITEM_PREFIX
        from ..regions import BEAT_INDEX, EDEA_GOAL_LAST_BEAT
        pool = [it.name for it in self.multiworld.itempool
                if it.player == self.player and it.name.startswith(WARP_ITEM_PREFIX)]
        self.assertIn(WARP_ITEM_PREFIX + "Deling City", pool)
        self.assertNotIn(WARP_ITEM_PREFIX + "Esthar", pool)
        self.assertNotIn(WARP_ITEM_PREFIX + "Edea's House", pool)
        last = BEAT_INDEX[EDEA_GOAL_LAST_BEAT]
        for dest in WARP_BY_KEY.values():
            self.assertEqual(WARP_ITEM_PREFIX + dest.name in pool,
                             BEAT_INDEX[dest.region] <= last, dest.name)


class TestFullGoalWarpPool(FF8TestBase):
    options = {"fast_travel": True}

    def test_every_warp_in_pool(self):
        from ..warp import WARP_BY_KEY, WARP_ITEM_PREFIX
        pool = [it.name for it in self.multiworld.itempool
                if it.player == self.player and it.name.startswith(WARP_ITEM_PREFIX)]
        self.assertEqual(len(pool), len(WARP_BY_KEY))
