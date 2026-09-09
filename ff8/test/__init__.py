"""Test suite for the FF8 apworld.

Run from an Archipelago source checkout with the ff8 world in worlds/:

    pytest worlds/ff8/test

Every options-combo class inherits WorldTestBase's default tests (all-state
reachability, empty-state progress, and a real fill), so each class is a full
generation regression test for that combination.
"""

from test.bases import WorldTestBase

from ..items import GF_ORDER


class FF8TestBase(WorldTestBase):
    game = "Final Fantasy VIII"
    player = 1


ALL_TOGGLES_ON = {
    "draw_point_checks": True,
    "world_draw_point_checks": True,
    "triple_triad_checks": True,
    "optional_boss_checks": True,
    "rare_card_checks": True,
    "sidequest_checks": True,
    "magazine_checks": True,
    "stat_checks": True,
    "gf_ability_checks": True,
}

# The early-handicap lock options (2026-09-03) plus progressive magic; on by
# default as of v0.3.0 (challenging-by-default), so tests that want the
# baseline pool must turn them off explicitly.
ALL_LOCKS_ON = {
    "character_locks": True,
    "ability_locks": True,
    "junction_locks": True,
    "command_locks": True,
}
ALL_LOCKS_OFF = {k: False for k in ALL_LOCKS_ON}

# "Everything off": check groups AND the default-on locks/progressive magic.
# Locks default-on would overflow the few core-only locations, so an "off"
# profile must clear them too.
ALL_TOGGLES_OFF = ({k: False for k in ALL_TOGGLES_ON} | ALL_LOCKS_OFF
                   | {"progressive_magic": False})

GF_ITEM_NAMES = [f"GF {gf}" for gf in GF_ORDER]


def item_spheres(multiworld, player: int) -> list[list]:
    """The player's locations grouped into item-gated spheres: free story
    events ("Cleared: <beat>") are swept between steps, so a sphere boundary
    is always a multiworld item. The last list is the unreachable remainder
    (empty for a sound seed). Shared with tools/sphere_report.py."""
    from BaseClasses import CollectionState
    real = [loc for loc in multiworld.get_locations(player) if loc.address is not None]
    events = [loc for loc in multiworld.get_locations(player) if loc.address is None]
    state = CollectionState(multiworld)
    done: set = set()
    spheres: list[list] = []
    while True:
        state.sweep_for_advancements(locations=events)
        new = [loc for loc in real if loc not in done and loc.can_reach(state)]
        if not new:
            break
        spheres.append(new)
        done.update(new)
        for loc in new:
            state.collect(loc.item, True, loc)
    spheres.append([loc for loc in real if loc not in done])
    return spheres
