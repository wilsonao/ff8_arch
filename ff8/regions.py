"""Story beats, travel hubs, and the logic-gate ladder (docs/plan-sphere-gating.md).

Pure data, no Archipelago imports: tools/gen_tracker_pack.py loads this module
standalone to mirror the region layout in the PopTracker pack.

The world is a linear chain of story BEATS. Entering beat N+1 needs the free
"Cleared: N" event (you played the story) plus, under `story_gates`, a few
multiworld items (the ladder below: a party-power proxy, like the old
gfs_required_for_disc3 gate, which the first Disc 3 beat still anchors).
Three HUB regions hang off the chain for world-map content that only needs a
vehicle: each is reachable from the beat where the story hands the vehicle
over, or (with vehicle_unlocks) from the start with the vehicle item alone.
"""

# Beat -> disc, in story order. Entering each beat requires the previous
# beat's "Cleared" event (and the ladder gate for it, if story_gates is on).
BEATS: list[tuple[str, int]] = [
    ("Balamb Prologue", 1),
    ("Fire Cavern", 1),
    ("Dollet Exam", 1),
    ("SeeD", 1),
    ("Timber", 1),
    ("Galbadia", 1),
    ("D-District Prison", 2),      # parade won (392) -> prison escape (450)
    ("Missile Base", 2),           # 450 -> missile base done (482)
    ("Garden Revolt", 2),          # 482 -> NORG (612)
    ("Fisherman's Horizon", 2),    # 612 -> Garden repaired and mobile (750)
    ("Balamb Liberation", 2),      # 750 -> Fujin/Raijin (760); needs the Garden
    ("Garden War", 2),             # 760 -> Trabia, orphanage, Battle of the Gardens (901)
    ("Edea's House", 3),           # 901 -> orphanage, Trabia Canyon dream (1310)
    ("Esthar", 3),                 # 1310 -> White SeeD ship, salt lake, Esthar, launch (2502)
    ("Lunar Base", 3),             # 2502 -> space, the Ragnarok lands (3150)
    ("Sorceress Memorial", 3),     # 3150 -> Rinoa, Tears' Point; needs the Ragnarok
    ("Lunatic Pandora", 3),        # -> Seifer, Adel (3860)
    ("Ultimecia's Castle", 4),     # 3860 -> castle entered (4020)
]
REGION_CHAIN: list[str] = [name for name, _disc in BEATS]
DISC_OF_BEAT: dict[str, int] = dict(BEATS)
BEAT_INDEX: dict[str, int] = {name: i for i, name in enumerate(REGION_CHAIN)}

# The last beat that exists on the edea goal (the game ends at the parade).
EDEA_GOAL_LAST_BEAT = "Galbadia"
# The gfs_required_for_disc3 anchor applies to entering this beat.
FIRST_DISC3_BEAT = "Edea's House"

# The vehicle item (items.VEHICLE_TABLE). Only the Ragnarok: a mobile Balamb
# Garden replaces the static Garden on the world map, so an early Garden item
# locked the player out of their own home base (live, 2026-09-09).
RAGNAROK_ITEM = "Ragnarok"

# Hub region -> (beat whose story grants the vehicle, vehicle item). A hub is
# reachable from that beat (vanilla) or, with vehicle_unlocks, from the Menu
# with the item. Under vehicle_gates the beat entry itself needs the item, so
# the vanilla edge no longer bypasses it.
HUBS: dict[str, tuple[str, str]] = {
    "Garden Travel": ("Balamb Liberation", RAGNAROK_ITEM),   # Centra + Trabia world map
    "Esthar Continent": ("Esthar", RAGNAROK_ITEM),           # Esthar mainland world map
    "Ragnarok Flight": ("Sorceress Memorial", RAGNAROK_ITEM),  # islands + archipelagos
}

# Beats whose story needs free piloting of a vehicle. With vehicle_gates the
# client withholds the vanilla vehicle until the item arrives, so entering
# these beats requires the item in logic (fill then guarantees it earlier).
VEHICLE_BEATS: dict[str, str] = {
    "Sorceress Memorial": RAGNAROK_ITEM,  # Esthar -> Tears' Point -> into Lunatic Pandora
}

# --- Gate ladder ------------------------------------------------------------
# Per beat: (GFs, character unlocks, junction rights, command unlocks). Counts
# are cumulative totals including precollected items (one character, one
# junction right, and the Draw command are always precollected, so a "1" in
# those columns is free). The GF column is written for the default Disc 3
# anchor of 6 and scaled by gfs_required_for_disc3 / 6 at generation time;
# character/junction/command columns only apply when that lock option is on.
GATE_LADDER: dict[str, dict[str, tuple[int, int, int, int]]] = {
    "normal": {
        "Timber":              (1, 0, 1, 0),
        "Galbadia":            (2, 1, 2, 0),
        "D-District Prison":   (2, 1, 3, 1),
        "Missile Base":        (3, 1, 3, 1),
        "Garden Revolt":       (3, 2, 4, 1),
        "Fisherman's Horizon": (4, 2, 5, 1),
        "Balamb Liberation":   (4, 2, 5, 2),
        "Garden War":          (5, 3, 6, 2),
        "Edea's House":        (6, 3, 7, 2),
        "Esthar":              (7, 4, 8, 3),
        "Lunar Base":          (8, 4, 8, 3),
        "Sorceress Memorial":  (9, 4, 9, 3),
        "Lunatic Pandora":     (10, 4, 10, 3),
        "Ultimecia's Castle":  (10, 4, 10, 3),
    },
    "tight": {
        "Timber":              (2, 1, 2, 0),
        "Galbadia":            (3, 1, 3, 1),
        "D-District Prison":   (3, 2, 4, 1),
        "Missile Base":        (4, 2, 4, 1),
        "Garden Revolt":       (4, 2, 5, 2),
        "Fisherman's Horizon": (5, 3, 6, 2),
        "Balamb Liberation":   (5, 3, 6, 2),
        "Garden War":          (6, 4, 7, 3),
        "Edea's House":        (6, 4, 8, 3),
        "Esthar":              (8, 4, 9, 3),
        "Lunar Base":          (9, 4, 9, 3),
        "Sorceress Memorial":  (10, 4, 10, 3),
        "Lunatic Pandora":     (12, 4, 11, 3),
        "Ultimecia's Castle":  (12, 4, 11, 3),
    },
}
GF_ANCHOR = 6           # the GF column is written against this Disc 3 count
GF_TOTAL = 16
CHARACTER_TOTAL = 5     # 4 pool items + 1 precollected
JUNCTION_TOTAL = 12     # 11 pool items + 1 precollected
COMMAND_TOTAL = 4       # 3 pool items + precollected Draw

# Item-group names (items.item_name_groups) the ladder columns count.
LADDER_GROUPS = ("GFs", "Character Unlocks", "Junction Unlocks", "Command Unlocks")


def gate_requirements(mode: str, beat: str, gfs_required_for_disc3: int,
                      character_locks: bool, junction_locks: bool,
                      command_locks: bool) -> dict[str, int]:
    """Item-group counts required to ENTER `beat` (empty when nothing is
    required). `mode` is the story_gates option key ("off", "normal",
    "tight"). "off" keeps the pre-ladder behaviour: only the first Disc 3
    beat is gated, on gfs_required_for_disc3 alone."""
    if mode == "off":
        if beat == FIRST_DISC3_BEAT and gfs_required_for_disc3 > 0:
            return {"GFs": gfs_required_for_disc3}
        return {}
    row = GATE_LADDER[mode].get(beat)
    if row is None:
        return {}
    gfs, chars, junctions, commands = row
    out: dict[str, int] = {}
    if gfs_required_for_disc3 > 0:
        # Scale the GF column to the player's Disc 3 anchor, rounding half
        # up, never above the 16 that exist.
        scaled = (gfs * gfs_required_for_disc3 * 2 + GF_ANCHOR) // (2 * GF_ANCHOR)
        scaled = min(scaled, GF_TOTAL)
        if scaled > 0:
            out["GFs"] = scaled
    if character_locks and chars > 0:
        out["Character Unlocks"] = min(chars, CHARACTER_TOTAL)
    if junction_locks and junctions > 0:
        out["Junction Unlocks"] = min(junctions, JUNCTION_TOTAL)
    if command_locks and commands > 0:
        out["Command Unlocks"] = min(commands, COMMAND_TOTAL)
    return out


assert all(set(rows) <= set(REGION_CHAIN) for rows in GATE_LADDER.values())
assert set(v[0] for v in HUBS.values()) <= set(REGION_CHAIN)
assert set(VEHICLE_BEATS) <= set(REGION_CHAIN)
for _mode, _rows in GATE_LADDER.items():
    _prev = (0, 0, 0, 0)
    for _beat in REGION_CHAIN:
        _row = _rows.get(_beat, _prev)
        assert all(a >= b for a, b in zip(_row, _prev)), f"{_mode} ladder dips at {_beat}"
        _prev = _row
