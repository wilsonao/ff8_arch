"""Item pool, precollection, exclusion, and slot-data invariants."""

from BaseClasses import ItemClassification, LocationProgressType

from . import ALL_TOGGLES_ON, FF8TestBase, GF_ITEM_NAMES
from ..items import ITEM_TABLE
from ..locations import LOCATION_DATA_BY_NAME


class TestPoolBalance(FF8TestBase):
    options = {**ALL_TOGGLES_ON, "starting_gfs": 2}

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
                    "trap_chance", "draw_point_checks",
                    "triple_triad_checks", "optional_boss_checks", "rare_card_checks",
                    "sidequest_checks", "magazine_checks", "stat_checks",
                    "gf_ability_checks", "death_link"):
            self.assertIn(key, slot_data)

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
        self.assertEqual(len(real_locations), 433)


class TestCoreOnlyPool(FF8TestBase):
    options = {"starting_gfs": 0}

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


class TestNoTrapsByDefault(FF8TestBase):
    options = {**ALL_TOGGLES_ON}

    def test_default_pool_has_no_traps(self):
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
            self.assertIn(kind, ("gf", "item", "gil", "magic", "bit",
                                 "trap_gil", "trap_hp", "trap_magic"))
            if kind in ("item", "magic"):
                self.assertEqual(len(d.grant), 3)
                self.assertGreater(d.grant[2], 0)
            elif kind == "bit":
                self.assertEqual(len(d.grant), 3)

    def test_magic_spell_ids(self):
        """Kernel spell ids are 1..56; one cap item per spell (a duplicate id
        would double-count toward the checks-only cap under one name)."""
        sids = [d.grant[1] for d in ITEM_TABLE if d.grant[0] == "magic"]
        for sid in sids:
            self.assertTrue(1 <= sid <= 56, sid)
        self.assertEqual(len(sids), len(set(sids)))

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
