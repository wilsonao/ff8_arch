"""Item pool, precollection, exclusion, and slot-data invariants."""

from BaseClasses import ItemClassification, LocationProgressType

from . import ALL_TOGGLES_OFF, ALL_TOGGLES_ON, FF8TestBase, GF_ITEM_NAMES
from ..items import ITEM_TABLE
from ..locations import LOCATION_DATA_BY_NAME


class TestPoolBalance(FF8TestBase):
    # magic_mode pinned to vanilla: the precollected-GF count and the vanilla
    # filler-roster test below both depend on it.
    options = {**ALL_TOGGLES_ON, "starting_gfs": 2, "magic_mode": "vanilla"}

    def test_pool_matches_locations(self):
        """Every unfilled location gets exactly one pool item (events excluded)."""
        unfilled = self.multiworld.get_unfilled_locations(self.player)
        pool = [i for i in self.multiworld.itempool if i.player == self.player]
        self.assertEqual(len(pool), len(unfilled))

    def test_starting_gfs_precollected(self):
        precollected = [i.name for i in self.multiworld.precollected_items[self.player]]
        self.assertEqual(len(precollected), 2)
        for name in precollected:
            self.assertIn(name, GF_ITEM_NAMES)

    def test_all_gfs_exist(self):
        """Every GF is either precollected or in the pool — never lost."""
        pool_names = [i.name for i in self.multiworld.itempool]
        precollected = [i.name for i in self.multiworld.precollected_items[self.player]]
        for name in GF_ITEM_NAMES:
            self.assertEqual(pool_names.count(name) + precollected.count(name), 1, name)

    def test_key_items_in_pool(self):
        pool_names = [i.name for i in self.multiworld.itempool]
        self.assertIn("Magical Lamp", pool_names)
        self.assertIn("Solomon Ring", pool_names)

    def test_character_unlocks_absent_when_off(self):
        """character_locks defaults off: no unlock items anywhere."""
        from ..items import item_name_groups
        everywhere = ([i.name for i in self.multiworld.itempool]
                      + [i.name for i in self.multiworld.precollected_items[self.player]])
        self.assertFalse(set(everywhere) & item_name_groups["Character Unlocks"])

    def test_missable_locations_excluded(self):
        """Locations flagged missable must never hold progression."""
        for location in self.multiworld.get_locations(self.player):
            if location.address is None:
                continue  # event
            data = LOCATION_DATA_BY_NAME[location.name]
            if data.missable:
                self.assertEqual(location.progress_type, LocationProgressType.EXCLUDED,
                                 f"{location.name} is missable but not excluded")
            else:
                self.assertEqual(location.progress_type, LocationProgressType.DEFAULT,
                                 f"{location.name} unexpectedly excluded")

    def test_slot_data_keys(self):
        slot_data = self.world.fill_slot_data()
        for key in ("starting_gfs", "gfs_required_for_disc3", "magic_mode",
                    "starter_magic", "progressive_magic", "tiered_magic",
                    "character_locks", "ability_locks", "junction_locks",
                    "command_locks", "trap_chance",
                    "draw_point_checks", "world_draw_point_checks",
                    "triple_triad_checks", "optional_boss_checks", "rare_card_checks",
                    "sidequest_checks", "magazine_checks", "stat_checks",
                    "gf_ability_checks", "death_link"):
            self.assertIn(key, slot_data)

    def test_lock_items_absent_when_off(self):
        """ability/junction/command locks default off: none of their items
        (and no progressive magic) may appear anywhere."""
        from ..items import item_name_groups
        everywhere = ([i.name for i in self.multiworld.itempool]
                      + [i.name for i in self.multiworld.precollected_items[self.player]])
        for group in ("GF Ability Unlocks", "Junction Unlocks",
                      "Command Unlocks", "Progressive Magic"):
            self.assertFalse(set(everywhere) & item_name_groups[group], group)

    def test_vanilla_filler_skips_checks_only_roster(self):
        """In vanilla magic mode the expanded magic roster (weight 0) must
        never be pulled, keeping the vanilla filler distribution unchanged."""
        from ..items import FILLER_WEIGHTS
        expanded = {n for n, w in FILLER_WEIGHTS.items() if w == 0}
        self.assertTrue(expanded)
        pulls = {self.world.get_filler_item_name() for _ in range(300)}
        self.assertFalse(pulls & expanded)

    def test_all_locations_present_when_all_options_on(self):
        real_locations = [loc for loc in self.multiworld.get_locations(self.player)
                          if loc.address is not None]
        self.assertEqual(len(real_locations), 580)


class TestCoreOnlyPool(FF8TestBase):
    options = {**ALL_TOGGLES_OFF, "starting_gfs": 0}

    def test_core_location_count(self):
        real_locations = [loc for loc in self.multiworld.get_locations(self.player)
                          if loc.address is not None]
        self.assertEqual(len(real_locations), 38)

    def test_progression_fits_core(self):
        """All progression items must fit the core-only location count."""
        progression = [i for i in self.multiworld.itempool
                       if ItemClassification.progression in i.classification]
        unfilled = self.multiworld.get_unfilled_locations(self.player)
        self.assertLessEqual(len(progression), len(unfilled))


class TestChecksOnlyMagic(FF8TestBase):
    options = {**ALL_TOGGLES_ON, "magic_mode": "checks_only"}

    def test_starter_magic_precollected(self):
        from ..items import STARTER_MAGIC
        precollected = [i.name for i in self.multiworld.precollected_items[self.player]]
        for name in STARTER_MAGIC:
            self.assertIn(name, precollected)

    def test_filler_pulls_expanded_roster(self):
        """The checks-only weights make the expanded magic roster pullable
        (its combined weight is ~28% of the pool — 300 pulls without a hit
        would be a broken table)."""
        from ..items import FILLER_WEIGHTS
        expanded = {n for n, w in FILLER_WEIGHTS.items() if w == 0}
        pulls = {self.world.get_filler_item_name() for _ in range(300)}
        self.assertTrue(pulls & expanded)

    def test_pool_still_matches_locations(self):
        unfilled = self.multiworld.get_unfilled_locations(self.player)
        pool = [i for i in self.multiworld.itempool if i.player == self.player]
        self.assertEqual(len(pool), len(unfilled))


class TestCharacterLocks(FF8TestBase):
    options = {**ALL_TOGGLES_ON, "character_locks": True}

    def test_one_unlock_precollected_rest_in_pool(self):
        from ..items import item_name_groups
        unlocks = item_name_groups["Character Unlocks"]
        precollected = [i.name for i in self.multiworld.precollected_items[self.player]
                        if i.name in unlocks]
        pool = [i.name for i in self.multiworld.itempool if i.name in unlocks]
        self.assertEqual(len(precollected), 1)
        self.assertEqual(len(pool), 4)
        self.assertEqual(set(precollected) | set(pool), unlocks)

    def test_unlocks_are_progression(self):
        from ..items import item_name_groups
        for item in self.multiworld.itempool:
            if item.name in item_name_groups["Character Unlocks"]:
                self.assertIn(ItemClassification.progression, item.classification)

    def test_pool_still_matches_locations(self):
        unfilled = self.multiworld.get_unfilled_locations(self.player)
        pool = [i for i in self.multiworld.itempool if i.player == self.player]
        self.assertEqual(len(pool), len(unfilled))


class TestLockPools(FF8TestBase):
    options = {**ALL_TOGGLES_ON, "ability_locks": True, "junction_locks": True,
               "command_locks": True}

    def test_ability_lock_items_in_pool(self):
        from ..items import item_name_groups
        pool = [i.name for i in self.multiworld.itempool]
        for name in item_name_groups["GF Ability Unlocks"]:
            self.assertEqual(pool.count(name), 1, name)
        self.assertEqual(len(item_name_groups["GF Ability Unlocks"]), 49)

    def test_one_junction_precollected_rest_in_pool(self):
        from ..items import item_name_groups
        unlocks = item_name_groups["Junction Unlocks"]
        precollected = [i.name for i in self.multiworld.precollected_items[self.player]
                        if i.name in unlocks]
        pool = [i.name for i in self.multiworld.itempool if i.name in unlocks]
        self.assertEqual(len(precollected), 1)
        self.assertEqual(len(pool), 11)
        self.assertEqual(set(precollected) | set(pool), unlocks)

    def test_command_items_in_pool(self):
        pool = [i.name for i in self.multiworld.itempool]
        for name in ("Magic Command", "GF Command", "Draw Command",
                     "Item Command"):
            self.assertEqual(pool.count(name), 1, name)

    def test_lock_items_are_progression(self):
        from ..items import item_name_groups
        locks = (item_name_groups["GF Ability Unlocks"]
                 | item_name_groups["Junction Unlocks"]
                 | item_name_groups["Command Unlocks"])
        for item in self.multiworld.itempool:
            if item.name in locks:
                self.assertIn(ItemClassification.progression, item.classification)

    def test_pool_still_matches_locations(self):
        unfilled = self.multiworld.get_unfilled_locations(self.player)
        pool = [i for i in self.multiworld.itempool if i.player == self.player]
        self.assertEqual(len(pool), len(unfilled))


class TestLockOverflowRejected(FF8TestBase):
    """Lock items without enough locations to hold them must fail generation
    with a readable OptionError, not a cryptic fill failure."""
    auto_construct = False

    def test_core_only_with_locks_raises(self):
        from Options import OptionError
        self.options = {**ALL_TOGGLES_OFF, "ability_locks": True,
                        "junction_locks": True, "command_locks": True}
        with self.assertRaises(OptionError):
            self.world_setup()


class TestProgressiveMagic(FF8TestBase):
    options = {**ALL_TOGGLES_ON, "magic_mode": "checks_only",
               "progressive_magic": True}

    def test_fixed_copy_counts(self):
        """14 progressive copies exist in total; the starter kit's copies are
        precollected, the rest are in the pool."""
        from ..items import PROGRESSIVE_MAGIC_COUNTS
        pool = [i.name for i in self.multiworld.itempool]
        precollected = [i.name for i in
                        self.multiworld.precollected_items[self.player]]
        for name, count in PROGRESSIVE_MAGIC_COUNTS.items():
            self.assertEqual(pool.count(name) + precollected.count(name),
                             count, name)

    def test_starter_kit_is_progressive(self):
        from ..items import STARTER_MAGIC_PROGRESSIVE
        precollected = [i.name for i in
                        self.multiworld.precollected_items[self.player]]
        for name in STARTER_MAGIC_PROGRESSIVE:
            self.assertIn(name, precollected)

    def test_subsumed_flat_magic_never_pulled(self):
        from ..items import PROGRESSIVE_SUBSUMED
        pulls = {self.world.get_filler_item_name() for _ in range(400)}
        self.assertFalse(pulls & PROGRESSIVE_SUBSUMED)

    def test_pool_still_matches_locations(self):
        unfilled = self.multiworld.get_unfilled_locations(self.player)
        pool = [i for i in self.multiworld.itempool if i.player == self.player]
        self.assertEqual(len(pool), len(unfilled))


class TestProgressiveMagicIgnoredInVanilla(FF8TestBase):
    options = {**ALL_TOGGLES_ON, "magic_mode": "vanilla",
               "progressive_magic": True}

    def test_no_progressive_items_anywhere(self):
        from ..items import item_name_groups
        everywhere = ([i.name for i in self.multiworld.itempool]
                      + [i.name for i in
                         self.multiworld.precollected_items[self.player]])
        self.assertFalse(set(everywhere) & item_name_groups["Progressive Magic"])


class TestStarterMagicNone(FF8TestBase):
    options = {**ALL_TOGGLES_ON, "magic_mode": "checks_only",
               "starter_magic": "none"}

    def test_no_magic_precollected(self):
        from ..items import item_name_groups
        precollected = [i.name for i in
                        self.multiworld.precollected_items[self.player]]
        self.assertFalse(set(precollected)
                         & (item_name_groups["Magic"]
                            | item_name_groups["Progressive Magic"]))


class TestStarterMagicGenerous(FF8TestBase):
    options = {**ALL_TOGGLES_ON, "magic_mode": "checks_only",
               "starter_magic": "generous"}

    def test_generous_kit_precollected(self):
        from ..items import STARTER_MAGIC, STARTER_MAGIC_GENEROUS_EXTRA
        precollected = [i.name for i in
                        self.multiworld.precollected_items[self.player]]
        for name in STARTER_MAGIC + STARTER_MAGIC_GENEROUS_EXTRA:
            self.assertIn(name, precollected)


class TestTieredMagic(FF8TestBase):
    # trap_chance 0 maximizes the magic sample; checks_only maximizes the
    # spell roster. The sphere sort runs in post_fill, so each test does a
    # real fill first.
    auto_construct = False
    options = {**ALL_TOGGLES_ON, "magic_mode": "checks_only", "trap_chance": 0,
               "tiered_magic": True}

    def _fill_and_collect(self, seed):
        from Fill import distribute_items_restrictive
        from worlds.AutoWorld import call_all
        from ..items import MAGIC_TIERS
        self.world_setup(seed)
        distribute_items_restrictive(self.multiworld)
        call_all(self.multiworld, "post_fill")
        sphere_of = {}
        for index, sphere in enumerate(self.multiworld.get_spheres()):
            for loc in sphere:
                sphere_of[loc] = index
        return [(sphere_of[loc], MAGIC_TIERS[loc.item.name], loc)
                for loc in self.multiworld.get_filled_locations()
                if loc.item.player == self.player
                and loc.item.name in MAGIC_TIERS]

    def test_magic_tiers_follow_spheres(self):
        """After post_fill, no higher-tier magic may sit in an earlier sphere
        than any lower-tier magic (excluded slots aside: they may only hold
        filler-class magic, i.e. tier 0, whatever their sphere)."""
        for seed in range(1, 6):
            with self.subTest(seed=seed):
                placements = [(s, t) for s, t, loc in self._fill_and_collect(seed)
                              if loc.progress_type != LocationProgressType.EXCLUDED]
                self.assertEqual({t for _s, t in placements}, {0, 1, 2})
                for low in (0, 1):
                    for high in range(low + 1, 3):
                        max_low = max(s for s, t in placements if t == low)
                        min_high = min(s for s, t in placements if t == high)
                        self.assertGreaterEqual(
                            min_high, max_low,
                            f"tier {high} magic in sphere {min_high} but "
                            f"tier {low} magic still in sphere {max_low}")

    def test_useful_magic_never_swapped_onto_excluded(self):
        for _s, _t, loc in self._fill_and_collect(1):
            if ItemClassification.useful in loc.item.classification:
                self.assertNotEqual(loc.progress_type, LocationProgressType.EXCLUDED,
                                    loc.name)


class TestTieredMagicMultiworld(FF8TestBase):
    """Two FF8 worlds: each player's magic still travels to the other world,
    and each player's tiers follow the combined multiworld spheres."""
    auto_construct = False

    def test_cross_world_sphere_pacing(self):
        from test.general import setup_multiworld
        from Fill import distribute_items_restrictive
        from worlds.AutoWorld import call_all
        from .. import FF8World
        from ..items import MAGIC_TIERS

        options = {**ALL_TOGGLES_ON, "magic_mode": "checks_only",
                   "trap_chance": 0, "tiered_magic": True}
        multiworld = setup_multiworld([FF8World, FF8World], seed=1,
                                      options=options)
        distribute_items_restrictive(multiworld)
        call_all(multiworld, "post_fill")

        sphere_of = {}
        for index, sphere in enumerate(multiworld.get_spheres()):
            for loc in sphere:
                sphere_of[loc] = index

        for player in (1, 2):
            placements = [(sphere_of[loc], MAGIC_TIERS[loc.item.name], loc)
                          for loc in multiworld.get_filled_locations()
                          if loc.item.player == player
                          and loc.item.name in MAGIC_TIERS]
            self.assertTrue(any(loc.player != player for _s, _t, loc in placements),
                            f"player {player}'s magic never left their world")
            usable = [(s, t) for s, t, loc in placements
                      if loc.progress_type != LocationProgressType.EXCLUDED]
            for low in (0, 1):
                for high in range(low + 1, 3):
                    max_low = max(s for s, t in usable if t == low)
                    min_high = min(s for s, t in usable if t == high)
                    self.assertGreaterEqual(
                        min_high, max_low,
                        f"player {player}: tier {high} in sphere {min_high} "
                        f"before tier {low} ends in sphere {max_low}")


class TestTieredMagicOff(FF8TestBase):
    auto_construct = False
    options = {**ALL_TOGGLES_ON, "magic_mode": "checks_only", "tiered_magic": False}

    def test_post_fill_leaves_placements_alone(self):
        from Fill import distribute_items_restrictive
        from worlds.AutoWorld import call_all
        self.world_setup()
        distribute_items_restrictive(self.multiworld)
        before = [(loc.name, loc.item.name)
                  for loc in self.multiworld.get_filled_locations()]
        call_all(self.multiworld, "post_fill")
        after = [(loc.name, loc.item.name)
                 for loc in self.multiworld.get_filled_locations()]
        self.assertEqual(before, after)


class TestTrapsEverywhere(FF8TestBase):
    options = {**ALL_TOGGLES_ON, "trap_chance": 100}

    def test_every_filler_slot_is_a_trap(self):
        pool = [i for i in self.multiworld.itempool if i.player == self.player]
        traps = [i for i in pool if i.classification == ItemClassification.trap]
        non_trap = [i for i in pool if i.classification != ItemClassification.trap]
        self.assertGreater(len(traps), 100)
        # everything that is not a trap is a real (non-filler) item
        from ..items import FILLER_TABLE
        filler_names = {f.name for f in FILLER_TABLE}
        self.assertFalse([i.name for i in non_trap if i.name in filler_names])

    def test_pool_still_matches_locations(self):
        unfilled = self.multiworld.get_unfilled_locations(self.player)
        pool = [i for i in self.multiworld.itempool if i.player == self.player]
        self.assertEqual(len(pool), len(unfilled))


class TestNoTrapsAtZeroChance(FF8TestBase):
    options = {**ALL_TOGGLES_ON, "trap_chance": 0}

    def test_zero_chance_pool_has_no_traps(self):
        pool = [i for i in self.multiworld.itempool if i.player == self.player]
        self.assertFalse([i.name for i in pool
                          if i.classification == ItemClassification.trap])


class TestOptionPresets(FF8TestBase):
    auto_construct = False

    def test_presets_use_valid_options_and_values(self):
        from ..options import FF8Options, OPTION_PRESETS
        for preset_name, preset in OPTION_PRESETS.items():
            for option_name, value in preset.items():
                self.assertIn(option_name, FF8Options.type_hints, preset_name)
                FF8Options.type_hints[option_name].from_any(value)


class TestTableIntegrity(FF8TestBase):
    # No multiworld needed; static table checks.
    auto_construct = False

    def test_unique_item_offsets(self):
        offsets = [d.id_offset for d in ITEM_TABLE]
        self.assertEqual(len(offsets), len(set(offsets)))

    def test_grant_payload_shapes(self):
        for d in ITEM_TABLE:
            kind = d.grant[0]
            self.assertIn(kind, ("gf", "item", "gil", "magic", "bit", "char",
                                 "ability", "junction", "command",
                                 "prog_magic", "trap_gil", "trap_hp",
                                 "trap_magic"))
            if kind in ("item", "magic"):
                self.assertEqual(len(d.grant), 3)
                self.assertGreater(d.grant[2], 0)
            elif kind in ("bit", "ability"):
                self.assertEqual(len(d.grant), 3)

    def test_progressive_stage_spell_ids(self):
        """Progressive stages use valid kernel spell ids and every stage
        quantity is positive (they deliver through the flat-magic path)."""
        from ..items import PROGRESSIVE_MAGIC_STAGES
        for name, stages in PROGRESSIVE_MAGIC_STAGES.items():
            self.assertGreaterEqual(len(stages), 2, name)
            for sid, qty in stages:
                self.assertTrue(1 <= sid <= 56, (name, sid))
                self.assertGreater(qty, 0, name)

    def test_magic_spell_ids(self):
        """Kernel spell ids are 1..56; one cap item per spell (a duplicate id
        would double-count toward the checks-only cap under one name)."""
        sids = [d.grant[1] for d in ITEM_TABLE if d.grant[0] == "magic"]
        for sid in sids:
            self.assertTrue(1 <= sid <= 56, sid)
        self.assertEqual(len(sids), len(set(sids)))

    def test_magic_tiers_cover_all_magic_filler(self):
        """Every magic filler item has a pacing tier and vice versa — an
        unmapped name would silently fall back to scattered placement."""
        from ..items import FILLER_TABLE, MAGIC_TIERS
        magic_names = {d.name for d in FILLER_TABLE if d.grant[0] == "magic"}
        self.assertEqual(set(MAGIC_TIERS), magic_names)
        self.assertTrue(set(MAGIC_TIERS.values()) <= {0, 1, 2})

    def test_starter_magic_names_exist(self):
        from ..items import ITEM_DATA_BY_NAME, STARTER_MAGIC
        for name in STARTER_MAGIC:
            self.assertEqual(ITEM_DATA_BY_NAME[name].grant[0], "magic", name)

    def test_trigger_offsets_inside_snapshot_span(self):
        """Every savemap offset a trigger reads must lie inside the single
        per-tick snapshot read, or the client would index out of the buffer."""
        from .. import memory
        from ..locations import LOCATION_TABLE

        def in_span(offset, width=1):
            self.assertGreaterEqual(offset, memory.SAVEMAP_BASE, hex(offset))
            self.assertLessEqual(offset + width, memory.SAVEMAP_END, hex(offset))

        for loc in LOCATION_TABLE:
            for kind, value in loc.triggers:
                if kind in ("flag_bit", "popcount16_ge", "u8_ge", "u16_ge",
                            "u32_ge", "bits_ge"):
                    width = {"flag_bit": 1, "popcount16_ge": 2, "u8_ge": 1,
                             "u16_ge": 2, "u32_ge": 4, "bits_ge": 4}[kind]
                    in_span(value[0], width)
                elif kind in ("popcount_ge", "bits_clear", "bits_all"):
                    in_span(value[0], value[1])
                elif kind == "cards_seen_range":
                    in_span(memory.TT_CARDS + value[0], value[1])
        for d in ITEM_TABLE:
            if d.grant[0] == "bit":
                in_span(d.grant[1])
        in_span(memory.DRAW_POINTS, memory.DRAW_POINTS_LEN)
        in_span(memory.TT_CARDS, 115)
        in_span(memory.INVENTORY, memory.INVENTORY_SLOTS * 2)
        in_span(memory.CHAR_BASE, memory.CHAR_COUNT * memory.CHAR_STRIDE)
        in_span(memory.GF_UNLOCK_BASE,
                memory.GF_RECORD_STRIDE * (memory.GF_COUNT - 1) + 1)
        in_span(memory.GF_RECORD_BASE, memory.GF_RECORD_STRIDE * memory.GF_COUNT)
        in_span(memory.TT_WINS, 2)
