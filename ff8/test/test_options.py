"""Option-combination generation tests.

Each class runs WorldTestBase's default tests (reachability + fill) for one
options profile. The profiles cover both extremes of every toggle and the
tightest fill configurations the option ranges allow.
"""

from . import ALL_LOCKS_ON, ALL_TOGGLES_OFF, ALL_TOGGLES_ON, FF8TestBase


class TestDefaultOptions(FF8TestBase):
    # Non-empty options dict so run_default_tests engages; values are the defaults.
    options = {"starting_gfs": 1, "gfs_required_for_disc3": 6}


class TestAllChecksOn(FF8TestBase):
    options = {**ALL_TOGGLES_ON, "death_link": True}


class TestAllChecksOff(FF8TestBase):
    options = {**ALL_TOGGLES_OFF, "starting_gfs": 0}


class TestTightGFGate(FF8TestBase):
    """The hardest fill: no starting GFs, Disc 3 logic-locked behind 12 of the
    16 GFs, and only the 33 core locations to place them in."""
    options = {**ALL_TOGGLES_OFF, "starting_gfs": 0, "gfs_required_for_disc3": 12}


class TestTightGFGateAllChecks(FF8TestBase):
    options = {**ALL_TOGGLES_ON, "starting_gfs": 0, "gfs_required_for_disc3": 12}


class TestMaxStartNoGate(FF8TestBase):
    options = {"starting_gfs": 3, "gfs_required_for_disc3": 0}


class TestCharacterLocksTightFill(FF8TestBase):
    """Character unlocks join the GFs as progression in the tightest fill."""
    options = {**ALL_TOGGLES_OFF, "character_locks": True, "starting_gfs": 0,
               "gfs_required_for_disc3": 12}


class TestSeeDCadetPreset(FF8TestBase):
    """The early-handicap preset generates and fills: every lock option on,
    progressive checks-only magic, no starter kit."""
    options = {**ALL_TOGGLES_ON, **ALL_LOCKS_ON,
               "starting_gfs": 1, "gfs_required_for_disc3": 6,
               "magic_mode": "checks_only", "starter_magic": "none",
               "progressive_magic": True}


class TestAllLocksTightFill(FF8TestBase):
    """Hardest lock fill: every lock item is progression, nothing given,
    Disc 3 gated behind 12 GFs."""
    options = {**ALL_TOGGLES_ON, **ALL_LOCKS_ON,
               "starting_gfs": 0, "gfs_required_for_disc3": 12,
               "magic_mode": "checks_only", "progressive_magic": True}


class TestOmegaGoal(FF8TestBase):
    options = {**ALL_TOGGLES_ON, "goal": "omega"}

    def test_victory_event_is_omega(self):
        self.assertTrue(self.multiworld.get_location("Omega Weapon Defeated", self.player))
        with self.assertRaises(KeyError):
            self.multiworld.get_location("Ultimecia Defeated", self.player)
