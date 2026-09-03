"""Logic-rule tests: key-item gates and the Disc 3 GF-count gate."""

from BaseClasses import CollectionState

from . import ALL_TOGGLES_OFF, ALL_TOGGLES_ON, FF8TestBase, GF_ITEM_NAMES


class TestKeyItemGates(FF8TestBase):
    options = {"starting_gfs": 0}

    def test_diablos_requires_magical_lamp(self):
        self.assertAccessDependency(["Magical Lamp: Diablos"], [["Magical Lamp"]],
                                    only_check_listed=True)

    def test_doomtrain_requires_solomon_ring(self):
        self.assertAccessDependency(["Solomon Ring: Doomtrain"], [["Solomon Ring"]],
                                    only_check_listed=True)


class TestGFAbilityGates(FF8TestBase):
    options = {"gf_ability_checks": True, "starting_gfs": 0}

    def test_ability_checks_require_their_gf(self):
        self.assertAccessDependency(
            ["Quezacotl Learns Card Mod", "Quezacotl Mastered"], [["GF Quezacotl"]],
            only_check_listed=True)
        self.assertAccessDependency(
            ["Eden Learns Expendx3-1", "Eden Mastered"], [["GF Eden"]],
            only_check_listed=True)

    def test_party_ladder_needs_no_specific_gf(self):
        state = CollectionState(self.multiworld)
        self.collect_all_but(["GF Quezacotl"], state)
        self.assertTrue(state.can_reach("GF Abilities Learned: 10", "Location", self.player))


class TestMasteredLockGates(FF8TestBase):
    """Under the lock options, a "GF Mastered" check needs every lock item
    covering a bit of that GF's 22-ability learn list; the signature LEARN
    checks and the party ladder need none."""
    options = {"gf_ability_checks": True, "starting_gfs": 0,
               "ability_locks": True, "junction_locks": True,
               "command_locks": True}

    def test_mastered_requires_signature_items(self):
        self.assertAccessDependency(
            ["Quezacotl Mastered"], [["Quezacotl: Card Mod"]],
            only_check_listed=True)

    def test_mastered_requires_command_items(self):
        # Magic Command, not Draw: Draw Command is precollected under
        # command_locks, so it can never be the blocking item.
        self.assertAccessDependency(
            ["Quezacotl Mastered"], [["Magic Command"]], only_check_listed=True)

    def test_mastered_requires_junction_items(self):
        # Quezacotl's learn list carries HP-J/Vit-J/Mag-J/Elem-Atk-J/Elem-Def-J
        # bits; one junction item is precollected at random, so test a learn-
        # list junction item that is still in the pool.
        from BaseClasses import CollectionState
        precollected = {i.name for i in
                        self.multiworld.precollected_items[self.player]}
        candidates = [n for n in ("HP-J", "Vit-J", "Mag-J", "Elem-Atk-J",
                                  "Elem-Def-J") if n not in precollected]
        self.assertTrue(candidates)
        state = CollectionState(self.multiworld)
        self.collect_all_but([candidates[0]], state)
        self.assertFalse(state.can_reach("Quezacotl Mastered", "Location",
                                         self.player))
        state.collect(self.get_item_by_name(candidates[0]))
        self.assertTrue(state.can_reach("Quezacotl Mastered", "Location",
                                        self.player))

    def test_learn_checks_and_ladder_need_no_lock_items(self):
        from BaseClasses import CollectionState
        from ..items import item_name_groups
        lock_items = (item_name_groups["GF Ability Unlocks"]
                      | item_name_groups["Junction Unlocks"]
                      | item_name_groups["Command Unlocks"])
        state = CollectionState(self.multiworld)
        self.collect_all_but(sorted(lock_items), state)
        self.assertTrue(state.can_reach("Quezacotl Learns Card Mod",
                                        "Location", self.player))
        self.assertTrue(state.can_reach("GF Abilities Learned: 150",
                                        "Location", self.player))


class TestDrawGates(FF8TestBase):
    """Draw-dependent checks: always need >= 1 GF (drawing needs a junctioned
    GF), and under command_locks the Draw Command item too — which also stops
    fill burying Draw Command behind a draw point. The scanned ladder needs
    Magic on top (Scan is drawn in-battle and cast before the clamp)."""
    options = {**ALL_TOGGLES_ON, "command_locks": True, "starting_gfs": 0}

    @staticmethod
    def _a_draw_location():
        from ..locations import LOCATION_TABLE
        return next(d.name for d in LOCATION_TABLE
                    if d.group == "draw" and not d.missable)

    def test_draw_command_precollected(self):
        """Draw Command ships precollected under command_locks (it gates ~224
        checks); the other three commands are pool items."""
        precollected = [i.name for i in
                        self.multiworld.precollected_items[self.player]]
        pool = [i.name for i in self.multiworld.itempool]
        self.assertIn("Draw Command", precollected)
        self.assertNotIn("Draw Command", pool)
        for name in ("Magic Command", "GF Command", "Item Command"):
            self.assertEqual(pool.count(name), 1, name)

    def test_draw_checks_satisfied_by_precollect(self):
        """The Draw Command rule exists but is satisfied from sphere 0 by the
        precollect — with a GF in hand, draw checks are open immediately."""
        state = CollectionState(self.multiworld)
        self.collect_all_but(["Magic Command"], state)
        self.assertTrue(state.can_reach(self._a_draw_location(),
                                        "Location", self.player))

    def test_scan_ladder_requires_magic_command(self):
        self.assertAccessDependency(["Enemies Scanned: 30"],
                                    [["Magic Command"]], only_check_listed=True)

    def test_draw_checks_require_a_gf(self):
        state = CollectionState(self.multiworld)
        self.collect_all_but(GF_ITEM_NAMES, state)
        loc = self._a_draw_location()
        self.assertFalse(state.can_reach(loc, "Location", self.player),
                         "draw check reachable with zero GFs")
        self.assertFalse(state.can_reach("Magic Collection: 5 Kinds",
                                         "Location", self.player))
        state.collect(self.get_item_by_name(GF_ITEM_NAMES[0]))
        self.assertTrue(state.can_reach(loc, "Location", self.player))


class TestDrawGatesNoLocks(FF8TestBase):
    """Without command_locks the GF requirement still applies, but no command
    items exist to demand."""
    options = {**ALL_TOGGLES_ON, "command_locks": False, "starting_gfs": 0}

    def test_gf_needed_command_items_absent(self):
        state = CollectionState(self.multiworld)
        self.collect_all_but(GF_ITEM_NAMES, state)
        loc = TestDrawGates._a_draw_location()
        self.assertFalse(state.can_reach(loc, "Location", self.player))
        state.collect(self.get_item_by_name(GF_ITEM_NAMES[0]))
        self.assertTrue(state.can_reach(loc, "Location", self.player))


class TestDisc3GFGate(FF8TestBase):
    options = {**ALL_TOGGLES_OFF, "starting_gfs": 0, "gfs_required_for_disc3": 12}

    def test_disc3_needs_gf_count(self):
        state = CollectionState(self.multiworld)
        # Everything except five GFs -> 11 GFs held, one short of the gate.
        self.collect_all_but(GF_ITEM_NAMES[:5], state)
        self.assertFalse(state.can_reach("Esthar: Lunar Base Launch", "Location", self.player),
                         "Disc 3 reachable with fewer GFs than the gate requires")
        # Disc 2 is not gated on GF count.
        self.assertTrue(state.can_reach("Missile Base Mission", "Location", self.player))
        state.collect(self.get_item_by_name(GF_ITEM_NAMES[0]))
        self.assertTrue(state.can_reach("Esthar: Lunar Base Launch", "Location", self.player),
                        "Disc 3 unreachable at exactly the required GF count")


class TestRegionChainOrder(FF8TestBase):
    options = {"starting_gfs": 0}

    def test_every_link_gated_by_its_clear_event(self):
        """Each region->region entrance requires exactly its predecessor's
        "Cleared" event. Checked at the entrance-rule level with sweeping
        disabled — a normal collect sweeps the free event items right back in,
        which is by design (the chain paces fill, it cannot strand a player)."""
        from .. import REGION_CHAIN
        for prev, nxt in zip(REGION_CHAIN, REGION_CHAIN[1:]):
            entrance = self.multiworld.get_entrance(f"{prev} -> {nxt}", self.player)
            state = CollectionState(self.multiworld)
            self.assertFalse(entrance.access_rule(state),
                             f"{prev} -> {nxt} open without Cleared: {prev}")
            state.collect(self.get_item_by_name(f"Cleared: {prev}"), prevent_sweep=True)
            if nxt != "Disc 3":  # Disc 3 additionally needs the GF-count gate
                self.assertTrue(entrance.access_rule(state),
                                f"{prev} -> {nxt} closed despite Cleared: {prev}")
