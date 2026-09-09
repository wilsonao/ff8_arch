"""Fast-travel warp destinations for the Final Fantasy VIII apworld.

Writing the live world-map position (i32 X/Y/Z at memory.WORLD_POS) teleports
the player and the engine reloads the destination segment's terrain — proven
live 2026-09-06. Coordinates are the ff8-speedruns/ff8-memory world-map.md
landmark table, which is in the same live-coord space (no transform needed).

Each destination is an AP unlock item ("Warp: <name>"); the client's /ff8warp
command teleports to an owned destination while on the world map. `region` is
the story region the destination belongs to (for future logic integration —
warp items are useful-class for now and gate nothing).
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class WarpDest:
    key: str          # lowercase command token
    name: str         # display name
    x: int
    y: int
    z: int
    region: str       # REGION_CHAIN member the destination sits in


# Curated travel hubs from world-map.md (towns, Gardens, key landmarks).
# Ordered roughly by story progression.
WARP_DESTINATIONS: list[WarpDest] = [
    WarpDest("balamb",        "Balamb",             13249, -26779, -304, "Balamb Prologue"),
    WarpDest("balambgarden",  "Balamb Garden",      24576, -29406, -658, "Balamb Prologue"),
    WarpDest("firecavern",    "Fire Cavern",        29839, -29350, -692, "Fire Cavern"),
    WarpDest("dollet",        "Dollet",            -15639, -39437, -172, "Dollet Exam"),
    WarpDest("timber",        "Timber",            -22564,  -4867, -700, "Timber"),
    WarpDest("delingcity",    "Deling City",       -61806, -28649, -892, "Galbadia"),
    WarpDest("galbadiagarden","Galbadia Garden",   -37471, -25062, -573, "Galbadia"),
    WarpDest("winhill",       "Winhill",           -50285,   6320, -385, "Disc 2"),
    WarpDest("fh",            "Fisherman's Horizon", 48811, -1653, -430, "Disc 2"),
    WarpDest("shumi",         "Shumi Village",      10362, -76967, -845, "Disc 2"),
    WarpDest("trabiagarden",  "Trabia Garden",      48893, -57979, -800, "Disc 2"),
    WarpDest("edeahouse",     "Edea's House",      -23150,  62853, -648, "Disc 2"),
    WarpDest("centraruins",   "Centra Ruins",        6887,  55285, -582, "Disc 2"),
    WarpDest("esthar",        "Esthar",             57011,  -2295, -297, "Disc 3"),
]

WARP_BY_KEY: dict[str, WarpDest] = {d.key: d for d in WARP_DESTINATIONS}
WARP_ITEM_PREFIX = "Warp: "


def warp_item_name(dest: WarpDest) -> str:
    return f"{WARP_ITEM_PREFIX}{dest.name}"


# In-game "warp crystal": the client keeps WARP_CRYSTAL_STOCK of this real
# item in the player's inventory and refunds it on use, so using it on a party
# member (from the field menu, on the world map) triggers a warp instead of
# being spent. The targeted party slot (0..5) selects the destination — the
# Nth party member warps to the Nth unlocked destination.
#
# Must be a SINGLE-TARGET item (so the game prompts a character to select) that
# IS consumed on use (so the count-drop is a reliable commit signal). Plain
# Potion (id 1): single-target, and its 200 HP heal is trivial once characters
# have thousands of HP, so by the time warp destinations unlock nobody uses
# Potions to heal — a de-facto dedicated warp item with negligible accidental
# triggers. Consumed only when the target isn't at full HP (the usual
# world-map case). Tunable if playtesting wants a different item.
WARP_CRYSTAL_ITEM_ID = 1
WARP_CRYSTAL_ITEM_NAME = "Potion"
WARP_CRYSTAL_STOCK = 1

