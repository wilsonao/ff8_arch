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


# --- Story Keys ---------------------------------------------------------------
# docs/plan-story-keys.md + docs/research/world-map-entrances.md. Walking into
# a town from the world map is decided by the ENTRANCE SCRIPT (wmsetus.obj
# section 8, resident at module+0x1A9DC3C+0xB70, re-read from disk on every
# world-map load): "player's segment == N [and moment >= M] -> enter field".
# A key item's door is one u16 in that script. The client keeps the door shut
# until the key arrives (lock patches) and, for early entry, removes the
# story's moment gate (unlock patches). Offsets are relative to the section;
# each patch carries the vanilla value so the client refuses to touch a
# script that does not match (another game version or language file).
from dataclasses import dataclass


@dataclass(frozen=True)
class AreaData:
    entries: tuple[int, ...]        # entrance-script entry indices (reference)
    first_beat: str                 # beat whose story first opens the door
    story_beats: tuple[str, ...]    # beats whose main line walks through it
    warp: str | None                # ff8/warp.py destination the key carries
    segments: tuple[int, ...]       # world-map segments the door(s) sit in
    wm_fields: tuple[int, ...]      # wm entry fields (0..71) the door(s) lead to
    lock: tuple[tuple[int, int, int], ...]    # (offset, vanilla, locked)
    unlock: tuple[tuple[int, int, int], ...]  # (offset, vanilla, early-entry)
    early: bool = False             # interiors safe before the story arrives


STORY_KEY_PREFIX = "Key: "


def story_key_name(area: str) -> str:
    return STORY_KEY_PREFIX + area


ENTRANCE_SCRIPT_LEN = 0xA5C

# Story moment at which each beat begins (the previous beat's end trigger,
# ff8-memory storyId.md / locations.py). Only bounds the client's story
# passes (areas mode): a door the main line walks through stays open from
# the start of the beat before the gated beat to the end of the gated beat.
# Lunatic Pandora's start is approximate; nothing precise depends on it.
BEAT_START_MOMENT: dict[str, int] = {
    "Balamb Prologue": 0, "Fire Cavern": 17, "Dollet Exam": 30, "SeeD": 135,
    "Timber": 150, "Galbadia": 290, "D-District Prison": 392,
    "Missile Base": 450, "Garden Revolt": 482, "Fisherman's Horizon": 612,
    "Balamb Liberation": 750, "Garden War": 760, "Edea's House": 901,
    "Esthar": 1310, "Lunar Base": 2502, "Sorceress Memorial": 3150,
    "Lunatic Pandora": 3400, "Ultimecia's Castle": 3860,
}
FINAL_MOMENT = 4020


def beat_end_moment(beat: str) -> int:
    i = BEAT_INDEX[beat]
    return (BEAT_START_MOMENT[REGION_CHAIN[i + 1]] if i + 1 < len(REGION_CHAIN)
            else FINAL_MOMENT)


def story_pass_windows(area: str) -> tuple[tuple[int, int], ...]:
    """[start, end) moment windows during which the story itself walks
    through the area's door: from the start of the beat before each gated
    story beat to the end of that beat."""
    out = []
    for beat in STORY_KEY_AREAS[area].story_beats:
        i = BEAT_INDEX[beat]
        prev = REGION_CHAIN[max(i - 1, 0)]
        out.append((BEAT_START_MOMENT[prev], beat_end_moment(beat)))
    return tuple(out)

STORY_KEY_AREAS: dict[str, AreaData] = {
    "Balamb": AreaData(
        entries=(11,), first_beat="Balamb Prologue", story_beats=('Dollet Exam', 'Timber', 'Balamb Liberation'),
        warp='balamb', segments=(273,), wm_fields=(1,),
        lock=((0x0356, 273, 0xffff),),
        unlock=()),
    "Fire Cavern": AreaData(
        entries=(13,), first_beat="Fire Cavern", story_beats=('Fire Cavern',),
        warp='firecavern', segments=(275,), wm_fields=(2,),
        lock=((0x03c2, 5536, 0xffff),),
        unlock=()),
    "Dollet": AreaData(
        entries=(7,), first_beat="Dollet Exam", story_beats=(),
        warp='dollet', segments=(238,), wm_fields=(3,),
        lock=((0x025a, 238, 0xffff),),
        unlock=((0x025e, 36, 0x0),)),
    "Timber": AreaData(
        entries=(17,), first_beat="Timber", story_beats=(),
        warp='timber', segments=(365,), wm_fields=(4,),
        lock=((0x04ee, 365, 0xffff),),
        unlock=((0x04f2, 205, 0x0),)),
    "Galbadia Garden": AreaData(
        entries=(9, 10), first_beat="Galbadia", story_beats=('Galbadia',),
        warp='galbadiagarden', segments=(267, 268), wm_fields=(5, 6, 7),
        lock=((0x02d2, 267, 0xffff), (0x032a, 268, 0xffff)),
        unlock=((0x02d6, 290, 0x0),)),
    "Tomb of the Unknown King": AreaData(
        entries=(6,), first_beat="Galbadia", story_beats=('Galbadia',),
        warp=None, segments=(234,), wm_fields=(9,),
        lock=((0x0236, 234, 0xffff),),
        unlock=(), early=True),
    "Deling City": AreaData(
        entries=(8,), first_beat="Galbadia", story_beats=('Galbadia',),
        warp='delingcity', segments=(264,), wm_fields=(8,),
        lock=((0x0296, 264, 0xffff),),
        unlock=((0x029a, 333, 0x0),)),
    "Missile Base": AreaData(
        entries=(15,), first_beat="Missile Base", story_beats=('Missile Base',),
        warp=None, segments=(327,), wm_fields=(11,),
        lock=((0x046a, 327, 0xffff),),
        unlock=((0x046e, 350, 0x0),)),
    "Winhill": AreaData(
        entries=(24,), first_beat="Balamb Liberation", story_beats=(),
        warp='winhill', segments=(393,), wm_fields=(14, 15),
        lock=((0x0652, 393, 0xffff),),
        unlock=((0x0656, 750, 0x0),)),
    "Shumi Village": AreaData(
        entries=(0,), first_beat="Balamb Liberation", story_beats=(),
        warp='shumi', segments=(49,), wm_fields=(20,),
        lock=((0x00a2, 49, 0xffff),),
        unlock=((0x00a6, 750, 0x0),)),
    "Centra Ruins": AreaData(
        entries=(33,), first_beat="Balamb Liberation", story_beats=(),
        warp='centraruins', segments=(592,), wm_fields=(16,),
        lock=((0x094e, 592, 0xffff),),
        unlock=(), early=True),
    "Chocobo Forests": AreaData(
        entries=(1, 2, 5, 31, 35, 36, 4, 14), first_beat="Balamb Liberation", story_beats=(),
        warp=None, segments=(81, 145, 150, 219, 279, 466, 653, 693), wm_fields=(22, 23, 33, 34, 35, 36, 37, 38, 39),
        lock=((0x00de, 81, 0xffff), (0x0116, 145, 0xffff), (0x01fe, 219, 0xffff), (0x0892, 466, 0xffff), (0x09c6, 653, 0xffff), (0x09fe, 693, 0xffff), (0x01ca, 4095, 0x0), (0x01e2, 4095, 0x0), (0x03fa, 279, 0xffff)),
        unlock=(), early=True),
    "Trabia Garden": AreaData(
        entries=(3, 4), first_beat="Garden War", story_beats=('Garden War',),
        warp='trabiagarden', segments=(149, 150), wm_fields=(19,),
        lock=((0x014e, 149, 0xffff), (0x019a, 4096, 0xffff), (0x01b2, 4096, 0xffff)),
        unlock=((0x0152, 750, 0x0), (0x018e, 750, 0x0))),
    "Edea's House": AreaData(
        entries=(34,), first_beat="Garden War", story_beats=('Garden War',),
        warp='edeahouse', segments=(652,), wm_fields=(18,),
        lock=((0x0986, 652, 0xffff),),
        unlock=((0x098a, 900, 0x0),)),
    "Great Salt Lake": AreaData(
        entries=(21, 22), first_beat="Esthar", story_beats=('Esthar',),
        warp=None, segments=(373, 374), wm_fields=(24, 25, 46),
        lock=((0x0596, 373, 0xffff), (0x05e2, 374, 0xffff)),
        unlock=((0x059a, 1600, 0x0),)),
    "Esthar City": AreaData(
        entries=(25, 26, 27, 28), first_beat="Esthar", story_beats=('Esthar',),
        warp='esthar', segments=(406, 407, 438, 439), wm_fields=(26, 27, 68),
        lock=((0x0696, 406, 0xffff), (0x0742, 407, 0xffff), (0x0786, 438, 0xffff), (0x07ca, 439, 0xffff)),
        unlock=((0x069a, 1750, 0x0), (0x0746, 1750, 0x0), (0x078a, 1750, 0x0), (0x07ce, 1750, 0x0))),
    "Lunatic Pandora Laboratory": AreaData(
        entries=(23,), first_beat="Esthar", story_beats=(),
        warp=None, segments=(378,), wm_fields=(28, 57),
        lock=((0x0606, 378, 0xffff),),
        unlock=((0x060a, 1750, 0x0),)),
    "Lunar Gate": AreaData(
        entries=(29,), first_beat="Esthar", story_beats=('Lunar Base',),
        warp=None, segments=(441,), wm_fields=(30, 69),
        lock=((0x080e, 441, 0xffff),),
        unlock=((0x0812, 1750, 0x0),)),
    "Sorceress Memorial": AreaData(
        entries=(30,), first_beat="Esthar", story_beats=('Sorceress Memorial',),
        warp=None, segments=(443,), wm_fields=(29, 47),
        lock=((0x0852, 443, 0xffff),),
        unlock=((0x0856, 1750, 0x0),)),
    "Tears' Point": AreaData(
        entries=(32,), first_beat="Esthar", story_beats=('Lunatic Pandora',),
        warp=None, segments=(506,), wm_fields=(31, 48, 49),
        lock=((0x08ca, 506, 0xffff),),
        unlock=((0x08ce, 1750, 0x0),)),
}

# Keys handed out at the start under story_keys: story. Their doors gate the
# second and third beats, so leaving them in the pool would shrink the opening
# sphere to Balamb Prologue's ten checks and make the multiworld's slowest
# player the gate to this game's first hour (the Sync-feedback failure mode).
# They stay real items: the client still enforces the doors, and other seeds
# (areas mode) keep them in the pool.
STORY_KEY_PRECOLLECTED: tuple[str, ...] = ("Balamb", "Fire Cavern")

# Beat -> keys its main line needs (story mode makes the beat entry require
# them, areas mode grants a story pass for these beats instead).
STORY_KEY_BEATS: dict[str, tuple[str, ...]] = {}
for _area, _data in STORY_KEY_AREAS.items():
    for _beat in _data.story_beats:
        STORY_KEY_BEATS[_beat] = STORY_KEY_BEATS.get(_beat, ()) + (story_key_name(_area),)

# Area -> location-name prefixes of the checks that sit inside the area (need
# the key in logic). Story-critical checks the main line forces (the Dollet
# exam, the Deling assassination, the Missile Base mission...) stay unlisted:
# they are reachable through the story pass / the beat's own gate.
AREA_LOCATIONS: dict[str, tuple[str, ...]] = {
    "Balamb": ("Draw Point: Balamb Harbor", "Draw Point: Balamb Town Square",
               "Timber Maniacs: Balamb Hotel", "Timber Maniacs: Balamb Station",
               "Rare Card: Zell", "Rare Card: Pandemona",
               "Magazine: Combat King 002"),
    "Fire Cavern": ("Draw Point: Fire Cavern",),
    "Dollet": ("Draw Point: Dollet Town Square", "Timber Maniacs: Dollet Hotel",
               "Timber Maniacs: Dollet Pub", "Rare Card: Siren",
               "Rule Abolished: Random (Dollet)"),
    "Timber": ("Draw Point: Timber City Square",
               "Draw Point: Timber Editorial Department",
               "Timber Maniacs: Timber Hotel",
               "Timber Maniacs: Timber Maniacs Building",
               "Magazine: Girl Next Door", "Magazine: Pet Pals Vol.1",
               "Magazine: Pet Pals Vol.2", "Magazine: Pet Pals Vol.3",
               "Magazine: Pet Pals Vol.4"),
    "Galbadia Garden": ("Draw Point: Galbadia Garden Athletic Track",
                        "Draw Point: Galbadia Garden Back Entrance",
                        "Draw Point: Galbadia Garden Clubroom",
                        "Draw Point: Galbadia Garden Gymnasium",
                        "Draw Point: Galbadia Garden Hall",
                        "Magazine: Weapons Monthly April"),
    "Tomb of the Unknown King": ("Draw Point: Tomb of the Unknown King",
                                 "Tomb of the Unknown King: Brothers",
                                 "Rare Card: Sacred", "Rare Card: Minotaur"),
    "Deling City": ("Draw Point: Deling City Square", "Draw Point: Deling City Sewer",
                    "Timber Maniacs: Deling City Hotel", "Rare Card: Rinoa",
                    "Rare Card: Kiros"),
    "Missile Base": (),
    "Winhill": ("Draw Point: Winhill Village", "Draw Point: Winhill Vacant House"),
    "Shumi Village": ("Draw Point: Shumi Village", "Timber Maniacs: Shumi Village"),
    "Centra Ruins": ("Draw Point: Centra Ruins", "Timber Maniacs: Centra Ruins",
                     "Centra Ruins: Odin Defeated", "Centra Ruins: Tonberry King"),
    "Chocobo Forests": ("Chocobo Forests Solved", "Rare Card: Chicobo"),
    "Trabia Garden": ("Draw Point: Trabia Garden",
                      "Timber Maniacs: Trabia Garden Cemetery",
                      "Rare Card: Selphie", "Rule Abolished: Random (Trabia)"),
    "Edea's House": ("Draw Point: Edea's House", "Timber Maniacs: Edea's House",
                     "Rare Card: Edea", "Rare Card: Seifer"),
    "Great Salt Lake": ("Draw Point: FH Great Salt Lake",),
    "Esthar City": ("Draw Point: Esthar City", "Draw Point: Odine's Laboratory",
                    "Rare Card: Ward", "Rare Card: Phoenix", "Rare Card: Squall"),
    "Lunatic Pandora Laboratory": ("Draw Point: Lunatic Pandora Laboratory",),
    "Lunar Gate": ("Rule Abolished: Random (Lunar Gate)",),
    "Sorceress Memorial": ("Draw Point: Sorceress Memorial",),
    "Tears' Point": ("Draw Point: Tears' Point", "Tears Point: Fallen Relic"),
}


def area_of_location(name: str) -> str | None:
    for area, prefixes in AREA_LOCATIONS.items():
        if any(name.startswith(p) for p in prefixes):
            return area
    return None


# --- Early entry (plan-sync-feedback.md C3) ------------------------------------
# An area flagged `early` has interiors that behave before the story reaches
# it (surveyed live, or no story gate at all: the game already lets a player
# who can reach the tile walk in). Its "first opening" checks, the ones the
# location table puts in the beat whose story first opens the door, move to
# an "Early: <area>" region reachable from that beat (vanilla) or, with
# vehicle_unlocks, from the Menu with the Ragnarok item, exactly like a travel
# hub. Checks the table places in a LATER beat depend on story state (a card
# holder who has not arrived, a magazine not yet on its shelf) and stay put.
# The area's key rule still applies to every check (set_rules), so with story
# keys on an early visit needs the key as well as the ship. Areas with a
# story-moment gate in the entrance script (unlock patches) additionally need
# story_keys on: only then does the client hold the door table and can lower
# the gate (client.apply_doors); without keys their early region has no Menu
# edge, and the tracker mirrors that (gen_tracker_pack.py early_access).
EARLY_PREFIX = "Early: "


def early_region_name(area: str) -> str:
    return EARLY_PREFIX + area


EARLY_ENTRY_AREAS: tuple[str, ...] = tuple(
    area for area, data in STORY_KEY_AREAS.items() if data.early)

# Early region -> (beat whose story first opens the door, vehicle item), the
# HUBS shape.
EARLY_REGIONS: dict[str, tuple[str, str]] = {
    early_region_name(area): (STORY_KEY_AREAS[area].first_beat, RAGNAROK_ITEM)
    for area in EARLY_ENTRY_AREAS}


def early_area_gated(area: str) -> bool:
    """The entrance script checks the story moment for this door (the client
    must lower it), so early entry needs story keys on."""
    return bool(STORY_KEY_AREAS[area].unlock)


def logic_region(name: str, vanilla_region: str) -> str:
    """Region a location lives in for logic and trackers: its table region,
    or the area's early region when the area allows early entry and the
    table region is the door's first-opening beat."""
    area = area_of_location(name)
    if area in EARLY_ENTRY_AREAS and vanilla_region == STORY_KEY_AREAS[area].first_beat:
        return early_region_name(area)
    return vanilla_region


assert set(AREA_LOCATIONS) == set(STORY_KEY_AREAS)
assert set(BEAT_START_MOMENT) == set(REGION_CHAIN)
assert all(BEAT_START_MOMENT[a] < BEAT_START_MOMENT[b] for a, b in zip(REGION_CHAIN, REGION_CHAIN[1:]))
for _area, _data in STORY_KEY_AREAS.items():
    assert _data.first_beat in BEAT_INDEX, _area
    assert all(BEAT_INDEX[b] >= BEAT_INDEX[_data.first_beat] for b in _data.story_beats), _area
    for _off, _old, _new in _data.lock + _data.unlock:
        assert 0 <= _off < ENTRANCE_SCRIPT_LEN - 1 and _old != _new, (_area, _off)
_all_offsets = [p[0] for d in STORY_KEY_AREAS.values() for p in d.lock + d.unlock]
assert len(_all_offsets) == len(set(_all_offsets)), "two keys patch the same word"
assert not set(EARLY_REGIONS) & (set(REGION_CHAIN) | set(HUBS))
assert all(STORY_KEY_AREAS[a].first_beat != REGION_CHAIN[0] for a in EARLY_ENTRY_AREAS), \
    "an area open from the first beat gains nothing from early entry"
