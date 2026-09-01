"""Universal Tracker regeneration: a world rebuilt from slot data alone (the
UT re_gen_passthrough path) must produce the same locations and rules."""

from BaseClasses import CollectionState, MultiWorld
from test.general import setup_multiworld
from worlds.AutoWorld import AutoWorldRegister, call_all

from . import ALL_TOGGLES_ON, FF8TestBase

UT_STEPS = ("generate_early", "create_regions", "create_items", "set_rules",
            "connect_entrances", "generate_basic")


def regen_from_slot_data(game: str, slot_data: dict) -> MultiWorld:
    """Mimic UT's TMain: default options, generation_is_fake, passthrough."""
    world_type = AutoWorldRegister.world_types[game]
    mw = setup_multiworld(world_type, steps=(), seed=12345)
    mw.generation_is_fake = True
    mw.re_gen_passthrough = {game: slot_data}
    for step in UT_STEPS:
        call_all(mw, step)
    return mw


class TestUTRegen(FF8TestBase):
    options = {**ALL_TOGGLES_ON, "starting_gfs": 3, "gfs_required_for_disc3": 9,
               "goal": "omega", "magic_mode": "checks_only", "trap_chance": 30}

    def test_world_has_ut_hooks(self):
        self.assertTrue(type(self.world).ut_can_gen_without_yaml)
        self.assertEqual(self.world.interpret_slot_data({"a": 1}), {"a": 1})
        tw = type(self.world).tracker_world
        self.assertEqual(tw["map_page_folder"], "tracker")
        mapping = tw["poptracker_name_mapping"]
        self.assertGreater(len(mapping), 300)
        ids = set(self.world.location_name_to_id.values())
        for key, loc_id in mapping.items():
            self.assertIn("/", key)
            self.assertIn(loc_id, ids, key)

    def test_regen_matches_original(self):
        slot_data = self.world.fill_slot_data()
        mw = regen_from_slot_data(self.game, slot_data)
        world = mw.worlds[1]
        self.assertEqual(world.options.goal.value, self.world.options.goal.value)
        self.assertEqual(world.options.gfs_required_for_disc3.value, 9)
        self.assertEqual(world.options.magic_mode.current_key, "checks_only")
        self.assertEqual(world.options.trap_chance.value, 30)
        original = {loc.name for loc in self.multiworld.get_locations(self.player) if loc.address}
        regen = {loc.name for loc in mw.get_locations(1) if loc.address}
        self.assertEqual(original, regen)
        # Rules survive regeneration: a 30-40 AP signature check (Dollet Exam
        # region) needs the region chain AND its GF item. CollectionState picks
        # up the regen's random precollected GFs, so test a GF it did not roll.
        precollected = {item.name for item in mw.precollected_items[1]}
        gf, check = next((g, c) for g, c in (
            ("Quezacotl", "Quezacotl Learns Card"), ("Shiva", "Shiva Learns I Mag-RF"),
            ("Ifrit", "Ifrit Learns F Mag-RF"), ("Siren", "Siren Learns L Mag-RF"),
        ) if f"GF {g}" not in precollected)
        state = CollectionState(mw)
        for name in ("Cleared: Balamb Prologue", "Cleared: Fire Cavern"):
            state.collect(world.create_event(name), prevent_sweep=True)
        self.assertFalse(state.can_reach(check, "Location", 1))
        state.collect(world.create_item(f"GF {gf}"), prevent_sweep=True)
        self.assertTrue(state.can_reach(check, "Location", 1))
        self.assertFalse(state.can_reach("Cerberus Mastered", "Location", 1))  # Disc 3
