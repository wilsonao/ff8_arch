"""Generate the PopTracker pack for the FF8 apworld.

Reads the canonical item/location tables from ff8/items.py + ff8/locations.py
(the same data the apworld ships) and emits a complete PopTracker pack under
tracker/ff8_ap_tracker/, plus a zip in build/. Re-run after any table change so
the tracker can never drift out of sync with the apworld:

    python tools/gen_tracker_pack.py

Everything in the pack is generated: JSON definitions, the Lua AP-id mapping,
the item icons, and both maps — a stylized geographic world map and a schematic
region board (original art only — no Square Enix assets, per docs/design.md §6).

Adding a location to the apworld later? The generator will fail with an
"unanchored nodes" assertion until you give the new place a spot in
NODE_ANCHOR below — that's deliberate.
"""

import importlib.util
import io
import re
import json
import shutil
import math
import sys
import types
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
PACK = ROOT / "tracker" / "ff8_ap_tracker"
UT_DIR = ROOT / "ff8" / "tracker"   # Universal Tracker map pages, shipped inside the apworld
BUILD_ZIP = ROOT / "build" / "ff8_ap_tracker.zip"

# Community-art variant: a contributed hand-placed marker layout over real
# FF8 map art (world map, Triple Triad compendium sheet, character screen).
# The marker data is ours to ship (tracker/community_map/mapping.json); the
# images contain Square Enix art and stay local-only (design.md §6), so the
# variant pack is generated ONLY when the art is present, into a gitignored
# directory, and is never part of the release zip or the apworld's UT pages.
COMMUNITY_DATA = ROOT / "tracker" / "community_map" / "mapping.json"
COMMUNITY_ART = ROOT / "thirdparty" / "community_map_art" / "images"
COMMUNITY_PACK = ROOT / "tracker" / "ff8_ap_tracker_community"
COMMUNITY_ZIP = ROOT / "build" / "ff8_ap_tracker_community.zip"
# The contributed mapping.json is natively a "mapping preset" for the
# Archipelago Visual Tracker (Wakamu/Archipelago, visualtracker.apworld;
# packs authored with Wakamu/archipelago-mapping-editor). Presets are zips
# of mapping.json + images, loaded from <Archipelago install>/visual_packs/.
# We emit two:
#   VISUAL_ZIP           — over our generated original art; a release asset.
#   VISUAL_COMMUNITY_ZIP — our fixed/extended community mapping over the
#                          contributed SE art; local-only, never published.
VISUAL_ZIP = ROOT / "build" / "ff8_visual_tracker.zip"
VISUAL_COMMUNITY_ZIP = ROOT / "build" / "ff8_visual_tracker_community.zip"
# Single-icon catch-all markers on the contributed world map. Their checks
# have better homes (Extras panels, GF Abilities tab, the community cards and
# characters tabs), and expanding them into per-node pin clusters would bury
# the map's bottom edge, so the converter skips them.
COMMUNITY_SKIP_MARKERS = {"GF checks", "Battles", "Triple Triad",
                          "Characters", "Magazines"}
# mapping.json tab name -> (map id, packed image name, pin size, cluster pitch)
COMMUNITY_TABS = {
    "World Map": ("cworld", "community_world.png", 16, 22),
    "Triple Triad": ("ccards", "community_cards.png", 48, 50),
    "Characters": ("cchars", "community_chars.png", 28, 30),
}
# Per-area crops of the community world image (view key -> crop rect, upscale,
# pin size). Keys/titles match ff8/areas.py AREAS so the follow-the-player
# Lua (ActivateTab "World Map" + area title) drives these tabs unchanged.
# Views may overlap; a pin lands in every view whose rect contains it.
# space/castle cover the artist's corner art, not geography, and the balamb
# island sits where the trabia/esthar rects meet: pins inside these views
# belong to them exclusively (checked first, in dict order) so corner and
# island clusters don't bleed into neighboring views.
COMMUNITY_EXCLUSIVE_VIEWS = ("space", "castle", "balamb")
COMMUNITY_AREA_VIEWS: dict[str, tuple[tuple[int, int, int, int], int, int]] = {
    "space":    ((0, 0, 190, 150), 4, 24),
    "castle":   ((0, 140, 230, 300), 4, 24),
    "balamb":   ((860, 330, 1110, 540), 3, 24),
    "galbadia": ((0, 180, 880, 800), 1, 20),
    "trabia":   ((830, 40, 1530, 400), 2, 24),
    "esthar":   ((920, 380, 1600, 1010), 2, 24),
    "centra":   ((0, 690, 1280, 1200), 1, 20),
}

# FFX-pack-style place tabs: a world marker with at least this many nodes gets
# its own sub-tab inside its area — a generated board (labeled pin grid over a
# darkened zoom of the art) so dense spots like Balamb Garden read as a
# checklist instead of a wall of squares. Smaller markers stay map-only.
COMMUNITY_PLACE_MIN = 5
# Marker label -> shorter/unambiguous tab title. "Esthar" MUST be renamed: it
# would collide with the area tab title and confuse UiHint("ActivateTab").
COMMUNITY_PLACE_TITLES = {
    "Esthar": "Esthar City",
    "Fishermans Horizon": "FH",
    "Tomb of the Unknown King": "Tomb",
    "Deep Sea Research Center": "Deep Sea RC",
    "Lunar Gate/Base/Ragnarok": "Lunar Gate",
    "Laguna Dream 2: Centra Excavation": "Excavation Site",
}
# Place-board geometry (drawn at 2x and downscaled).
PLACE_PIN = 24
PLACE_PITCH_X = 150
PLACE_PITCH_Y = 62
PLACE_PAD = 24
PLACE_HEADER = 46

PACK_VERSION = "0.16.0"

# ---------------------------------------------------------------------------
# Load ff8 tables without an Archipelago environment: stub BaseClasses, then
# load items.py/locations.py as a synthetic package (importing the real ff8
# package would pull in worlds.AutoWorld and the whole AP core).
# ---------------------------------------------------------------------------

_bc = types.ModuleType("BaseClasses")


class _Stub:
    pass


class _IC:
    progression = "progression"
    useful = "useful"
    filler = "filler"
    trap = "trap"


_bc.Location = _Stub
_bc.Item = _Stub
_bc.ItemClassification = _IC
sys.modules["BaseClasses"] = _bc

_pkg = types.ModuleType("ff8_src")
_pkg.__path__ = [str(ROOT / "ff8")]
sys.modules["ff8_src"] = _pkg


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"ff8_src.{name}", ROOT / "ff8" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


ff8_items = _load("items")
ff8_locations = _load("locations")
ff8_regions = _load("regions")
ff8_areas = _load("areas")
ff8_abilities = sys.modules["ff8_src.abilities"]
ff8_memory = _load("memory")

BASE_ID = ff8_items.BASE_ID
GF_ORDER = ff8_items.GF_ORDER

# Story beats (ff8/regions.py, the same table the apworld builds its region
# chain from). Beat i is tracker-accessible at story progress >= i, plus the
# gate ladder (LOGIC_LUA mirrors regions.gate_requirements). The three travel
# hubs are not beats: they open at their vanilla grant beat or with the
# vehicle item, and carry no story progress of their own.
REGION_CHAIN = list(ff8_regions.REGION_CHAIN)
REGION_INDEX = {r: i for i, r in enumerate(REGION_CHAIN)}
HUBS = dict(ff8_regions.HUBS)
# Early-entry areas (regions.EARLY_REGIONS): hub-shaped regions holding an
# area's first-opening checks, reachable from the door's first beat or, with
# vehicle_unlocks, from the ship (plus story keys on for a moment-gated door).
EARLY_REGIONS = dict(ff8_regions.EARLY_REGIONS)
ALL_REGIONS = REGION_CHAIN + list(HUBS) + list(EARLY_REGIONS)
MAX_PROGRESS = len(REGION_CHAIN) - 1
VEHICLE_CODES = {ff8_regions.RAGNAROK_ITEM: "vehicle_ragnarok"}
# Story keys (story_keys option): one toggle per area, code "key_<slug>".
KEY_CODES = {area: "key_" + re.sub(r"[^a-z0-9]+", "_", area.lower()).strip("_")
             for area in ff8_regions.STORY_KEY_AREAS}
KEY_INITIALS = {
    "Balamb": "Ba", "Fire Cavern": "FC", "Dollet": "Do", "Timber": "Ti",
    "Galbadia Garden": "GG", "Tomb of the Unknown King": "Tb",
    "Deling City": "De", "Missile Base": "MB", "Winhill": "Wi",
    "Shumi Village": "Sh", "Centra Ruins": "CR", "Chocobo Forests": "Cf",
    "Trabia Garden": "TG", "Edea's House": "EH", "Great Salt Lake": "SL",
    "Esthar City": "Es", "Lunatic Pandora Laboratory": "LP", "Lunar Gate": "LG",
    "Sorceress Memorial": "SM", "Tears' Point": "TP",
}
assert set(KEY_INITIALS) == set(KEY_CODES)
# Junction / command lock items: one toggle each (code "lock_<slug>") next to
# the ladder counters, so a player sees WHICH junctions are unlocked, not just
# how many (DrMisunderstood built his own tracker for this, 2026-10-01).
LOCK_ICONS = {
    "HP-J": "HP", "Str-J": "St", "Vit-J": "Vi", "Mag-J": "Ma", "Spr-J": "Sp",
    "Spd-J": "Sd", "Eva-J": "Ev", "Hit-J": "Hi", "Elem-Atk-J": "EA",
    "ST-Atk-J": "SA", "Elem-Def-J": "ED", "ST-Def-J": "SD",
    "Magic Command": "Mg", "GF Command": "GF", "Draw Command": "Dr",
    "Item Command": "It",
}
LOCK_CODES = {name: "lock_" + re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
              for name in LOCK_ICONS}
assert set(LOCK_ICONS) == (ff8_items.item_name_groups["Junction Unlocks"]
                          | ff8_items.item_name_groups["Command Unlocks"]), "lock icons"
# GF ability lock items ("Quezacotl: Card"): hidden toggles (no layout slot,
# fifty would swamp it) that only feed the learn-check access rules.
ABILITY_LOCK_CODES = {d.name: f"ablock_{d.id_offset - 600}"
                      for d in ff8_items.ABILITY_LOCK_TABLE}
LOCK_OPTION = ({name: "junction_locks" for name in ff8_items.item_name_groups["Junction Unlocks"]}
               | {name: "command_locks" for name in ff8_items.item_name_groups["Command Unlocks"]}
               | {name: "ability_locks" for name in ABILITY_LOCK_CODES})


def lock_rule(item: str) -> str:
    """Access rule for a lock item: needed only while its option is on."""
    code = LOCK_CODES.get(item) or ABILITY_LOCK_CODES[item]
    return f"$lock_access|{LOCK_OPTION[item]}|{code}"


def lock_items_for(gf: int, aid: int) -> list[str]:
    """Every lock item (any option) that holds GF `gf`'s ability `aid` down;
    mirrors __init__._lock_items_for with all three options on."""
    out = []
    if aid in ff8_abilities.GF_SIGNATURE_ABILITIES[gf]:
        out.append(f"{GF_ORDER[gf]}: {ff8_abilities.GF_ABILITY_NAMES[aid]}")
    out += [ff8_abilities.GF_ABILITY_NAMES[primary]
            for primary, bits in ff8_abilities.JUNCTION_LOCK_GROUPS.items() if aid in bits]
    out += [f"{name} Command" for name, cid in ff8_abilities.COMMAND_ABILITY_IDS.items()
            if cid == aid]
    return out


def ff8_world_reads_magic_drawn(kind: str, value) -> bool:
    """__init__._reads_magic_drawn: the trigger reads magic_drawn_once."""
    if kind == "flag_bit":
        return (ff8_memory.MAGIC_DRAWN <= value[0]
                < ff8_memory.MAGIC_DRAWN + ff8_memory.MAGIC_DRAWN_LEN)
    if kind == "popcount_ge":
        return value[0] == ff8_memory.MAGIC_DRAWN
    return False

_table_regions = {d.region for d in ff8_locations.LOCATION_TABLE}
assert _table_regions <= set(ALL_REGIONS), f"unknown regions: {_table_regions - set(ALL_REGIONS)}"


def region_of(d) -> str:
    """The region a location's node sits under: its table region, or the
    area's early-entry region (mirrors __init__.create_regions)."""
    return ff8_regions.logic_region(d.name, d.region)

# Story checks that end a beat: checking them auto-bumps tracker progress to
# the index of the newly accessible beat. Other checks bump only to their own
# beat's index (you were there to check it); hub checks bump nothing.
STORY_PROGRESS_BUMPS = {
    offset: REGION_INDEX[next_beat] for offset, next_beat in [
        (100, "Dollet Exam"),          # Fire Cavern Cleared
        (101, "SeeD"),                 # Dollet Exam Completed
        (102, "Timber"),               # SeeD Graduation
        (103, "Galbadia"),             # Timber: Forest Owls
        (104, "D-District Prison"),    # Sorceress Assassination
        (105, "Missile Base"),         # D-District Prison Escape
        (106, "Garden Revolt"),        # Missile Base Mission
        (107, "Fisherman's Horizon"),  # NORG Defeated
        (115, "Balamb Liberation"),    # FH: Garden Repaired
        (108, "Garden War"),           # Balamb Liberated
        (109, "Edea's House"),      # Battle of the Gardens
        (123, "Esthar"),               # Laguna Dream 4: Trabia Canyon
        (110, "Lunar Base"),           # Esthar: Lunar Base Launch
        (116, "Sorceress Memorial"),   # Lunar Base: Ragnarok Landing
        (111, "Ultimecia's Castle"),   # Adel Defeated
    ]
}

GF_INITIALS = {
    "Quezacotl": "Qz", "Shiva": "Sh", "Ifrit": "If", "Siren": "Si",
    "Brothers": "Br", "Diablos": "Di", "Carbuncle": "Cb", "Leviathan": "Lv",
    "Pandemona": "Pn", "Cerberus": "Ce", "Alexander": "Al", "Doomtrain": "Dt",
    "Bahamut": "Bh", "Cactuar": "Cc", "Tonberry": "Tb", "Eden": "Ed",
}
GF_COLORS = [
    "#c9a227", "#7fd4e8", "#d1512d", "#c77dc2",
    "#8a6d4a", "#5b2d7a", "#3fae6a", "#2d6fc7",
    "#b03a5b", "#6b7280", "#d8d3c0", "#4b3fae",
    "#274472", "#79b653", "#3b7a57", "#9db4d8",
]


# Cameo GFs (useful-class items 300-302): tracked as plain toggles, deliberately
# NOT providing the shared "gf" code that feeds the Disc 3 count.
CAMEO_GFS = ["Odin", "Phoenix", "Gilgamesh"]
CAMEO_ITEM_NAMES = {f"GF {g}" for g in CAMEO_GFS}
CAMEO_ICONS = {"Odin": ("Od", "#334155"), "Phoenix": ("Ph", "#ea580c"),
               "Gilgamesh": ("Gm", "#a16207")}
assert CAMEO_ITEM_NAMES <= {d.name for d in ff8_items.ITEM_TABLE}, "cameo GF items missing"


def gf_code(name: str) -> str:
    return f"gf_{name.lower()}"


# ---------------------------------------------------------------------------
# Icons (generated originals)
# ---------------------------------------------------------------------------

def _font(size: int):
    for path in (r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\segoeuib.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def make_icon(path: Path, text: str, color: str, size: int = 32):
    scale = 4  # render large, downscale for smooth edges
    s = size * scale
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([scale, scale, s - scale, s - scale], radius=6 * scale,
                        fill=color, outline="#0e1018", width=scale)
    font = _font(int(s * 0.44))
    box = d.textbbox((0, 0), text, font=font)
    tw, th = box[2] - box[0], box[3] - box[1]
    # White text with a dark outline reads on any fill color.
    x, y = (s - tw) / 2 - box[0], (s - th) / 2 - box[1]
    d.text((x, y), text, font=font, fill="#ffffff",
           stroke_width=scale, stroke_fill="#0e1018")
    img = img.resize((size, size), Image.LANCZOS)
    img.save(path)


# ---------------------------------------------------------------------------
# Region board (schematic logic-order map): three columns of region panels.
# ---------------------------------------------------------------------------

NODES_PER_ROW = 9
PITCH = 30
CELL_W = 12 * 2 + NODES_PER_ROW * PITCH  # padding + node grid
PAD = 12
HEADER = 26
MAP_COLUMNS = [
    [b for b, disc in ff8_regions.BEATS if disc == 1],
    [b for b, disc in ff8_regions.BEATS if disc == 2],
    [b for b, disc in ff8_regions.BEATS if disc == 3],
    [b for b, disc in ff8_regions.BEATS if disc == 4] + list(HUBS) + list(EARLY_REGIONS),
]
COL_GAP = 14


def layout_board(nodes_by_region: dict[str, list]):
    """Assign (x, y) board coordinates to every node; return coords, w, h, cells."""
    coords: dict[str, tuple[int, int]] = {}
    cells: dict[str, tuple[int, int, int]] = {}  # region -> (x, y, h)
    width = COL_GAP + len(MAP_COLUMNS) * (CELL_W + COL_GAP)
    height = 0
    for ci, column in enumerate(MAP_COLUMNS):
        x0 = COL_GAP + ci * (CELL_W + COL_GAP)
        y0 = COL_GAP
        for region in column:
            n = len(nodes_by_region.get(region, []))
            rows = max(1, math.ceil(n / NODES_PER_ROW))
            cell_h = HEADER + PAD + rows * PITCH + PAD
            cells[region] = (x0, y0, cell_h)
            for j, node_key in enumerate(nodes_by_region.get(region, [])):
                r, c = divmod(j, NODES_PER_ROW)
                coords[node_key] = (x0 + PAD + c * PITCH + PITCH // 2,
                                    y0 + HEADER + PAD + r * PITCH + PITCH // 2)
            y0 += cell_h + COL_GAP
        height = max(height, y0)
    return coords, width, height, cells


def draw_board(path: Path, cells: dict[str, tuple[int, int, int]], width: int, height: int):
    img = Image.new("RGB", (width, height), "#10141f")
    d = ImageDraw.Draw(img)
    title_font = _font(15)
    for region, (x, y, h) in cells.items():
        d.rounded_rectangle([x, y, x + CELL_W, y + h], radius=8,
                            fill="#1c2333", outline="#3b4a6b", width=2)
        d.text((x + PAD, y + 6), region, font=title_font, fill="#e8ecf5")
    img.save(path)


# ---------------------------------------------------------------------------
# Geographic world map, rendered from the game's own world walkmesh by
# tools/mapgen (tracker/geo/world.png + geo.json; see tools/mapgen/__init__).
# Every pin sits at its real world coordinate: landmark anchors come from the
# world-map exit table (wmsetus section 9, "wm" entries), named regions from
# the per-segment region map, and world draw points from their own table.
# Nodes sharing an anchor spread into a small cluster around it. Space and
# Ultimecia's Castle have no world position and live in inset panels drawn on
# open ocean.
# ---------------------------------------------------------------------------

GEO_DIR = ROOT / "tracker" / "geo"
GEO = json.loads((GEO_DIR / "geo.json").read_text(encoding="utf-8"))
# location -> where it is physically obtained (tools/mapgen/attribution.json:
# kind field/world/none, fields [primary first], place, confidence)
ATTRIBUTION_FILE = ROOT / "tools" / "mapgen" / "attribution.json"
ATTRIBUTION: dict[str, dict] = (json.loads(ATTRIBUTION_FILE.read_text(encoding="utf-8"))
                                if ATTRIBUTION_FILE.exists() else {})
GEO_W, GEO_H = GEO["world"]["width"], GEO["world"]["height"]
CLUSTER_PITCH = 44      # pin pitch (image px) inside a landmark cluster, world map
VIEW_PITCH = 30         # same, inside the per-area views
INSET_PITCH = 52
INSET_PAD = 24
INSET_HEADER = 48
CANONICAL_FIELD: dict[str, str] = GEO.get("canonical_fields", {})


def world_px(x: float, y: float) -> tuple[int, int]:
    w = GEO["world"]
    return (round((x - w["x0"]) / w["scale"]), round((y - w["y0"]) / w["scale"]))


def spot_px(spec: tuple) -> tuple[int, int]:
    """A world anchor spec -> image pixel.
    ("wm", n): exit point of world-map field n; ("region", name): land
    centroid of that save-preview region; ("xy", x, y): raw world units;
    ("off", spec, dx, dy): another spec shifted by world units."""
    kind = spec[0]
    if kind == "wm":
        pt = GEO["wm_fields"][str(spec[1])]
        return world_px(pt["x"], pt["y"])
    if kind == "region":
        pt = GEO["region_centroids"][spec[1]]
        return world_px(pt["x"], pt["y"])
    if kind == "xy":
        return world_px(spec[1], spec[2])
    if kind == "off":
        x, y = spot_px(spec[1])
        return (x + round(spec[2] / GEO["world"]["scale"]),
                y + round(spec[3] / GEO["world"]["scale"]))
    raise ValueError(spec)


# anchor key -> (world spot, label drawn under the cluster)
ANCHOR_SPOTS: dict[str, tuple[tuple, str | None]] = {
    "balamb_town":     (("wm", 1), "Balamb"),
    "balamb_garden":   (("wm", 0), "Balamb Garden"),
    "fire_cavern":     (("wm", 2), "Fire Cavern"),
    "dollet":          (("wm", 3), "Dollet"),
    "timber":          (("wm", 4), "Timber"),
    "timber_forest":   (("wm", 5), None),
    "galbadia_garden": (("wm", 6), "Galbadia Garden"),
    "tomb":            (("wm", 9), "Tomb"),
    "deling":          (("wm", 8), "Deling City"),
    "winhill":         (("wm", 14), "Winhill"),
    "missile_base":    (("wm", 11), "Missile Base"),
    "d_district":      (("wm", 10), "D-District"),
    "fh":              (("wm", 12), "FH"),
    "salt_lake":       (("wm", 25), "Salt Lake"),
    "esthar":          (("wm", 26), "Esthar"),
    "pandora_lab":     (("wm", 28), "Pandora Lab"),
    "memorial":        (("wm", 30), "Memorial"),
    "lunar_gate":      (("wm", 29), "Lunar Gate"),
    "tears_point":     (("wm", 31), "Tears Point"),
    # Lunatic Pandora parks beside Tears' Point on Disc 3
    "lunatic_pandora": (("off", ("wm", 31), -7000, -5000), "Lunatic Pandora"),
    "trabia":          (("wm", 19), "Trabia"),
    "shumi":           (("wm", 20), "Shumi"),
    "centra_exc":      (("wm", 17), "Excavation Site"),
    "centra_ruins":    (("wm", 16), "Centra Ruins"),
    "edea":            (("wm", 18), "Orphanage"),
    "white_seed":      (("wm", 41), "White SeeD"),
    "cactuar":         (("region", "Esthar- Cactuar Island"), "Cactuar"),
    "deep_sea":        (("wm", 21), "Deep Sea RC"),
    "island_heaven":   (("region", "Island Closest to Heaven"), "Heaven"),
    "island_hell":     (("region", "Island Closest to Hell"), "Hell"),
    # UFO quest: the four sighting regions, the shoot-down over Grandidi, PuPu
    # at the Balamb Garden crater
    "ufo_beach":       (("region", "Timber- Mandy Beach"), "UFO"),
    "ufo_plains":      (("region", "Winhill- Winhill Bluffs"), "UFO"),
    "ufo_tundra":      (("region", "Trabia- Heath Peninsula"), "UFO"),
    "ufo_desert":      (("region", "Esthar- Kashkabald Desert"), "UFO"),
    "ufo_fight":       (("wm", 42), "UFO??"),
    "pupu":            (("wm", 57), "PuPu"),
}
ANCHORS: dict[str, tuple[int, int, str | None]] = {
    key: (*spot_px(spec), label) for key, (spec, label) in ANCHOR_SPOTS.items()}

# option-gated location groups -> tracker toggle code driving their visibility
GROUP_OPT = {"draw": "opt_draw_points", "world_draw": "opt_wdraw",
             "tt": "opt_tt", "tt_rules": "opt_tt,$tt_rules_on", "boss_extra": "opt_boss",
             "cards": "opt_cards", "sidequest": "opt_sq", "magazine": "opt_mags",
             "stats": "opt_stats", "abilities": "opt_abil"}
# Pure counter/grind groups: checking one implies no story progress.
NO_PROGRESS_GROUPS = {"stats", "abilities"}
# GF ability checks live on their own tab (one column per GF), not the world map.
ABILITIES_ANCHOR = "abilities_tab"

# key -> (x, y, columns, title); height follows from the node count.
# World-map insets sit on open ocean and must not cover a continent.
INSETS: dict[str, tuple[int, int, int, str]] = {
    "space":           (3340, 60, 6, "Space / Ragnarok"),
    "ult_castle":      (3300, 2520, 7, "Ultimecia's Castle"),
}

# Non-geographic check sets (quest ladders, card lists, grind counters) get
# their own "Quests & Extras" map so the world map stays readable. Same panel
# geometry as INSETS; laid out as two columns.
EXTRAS_PANELS: dict[str, tuple[int, int, int, str]] = {
    "sidequests":   (14, 14, 12, "Sidequests"),
    "stats":        (14, 232, 12, "Stat Ladders"),
    "rare_cards":   (364, 14, 12, "Rare Cards"),
    "triple_triad": (364, 154, 12, "Triple Triad"),
}

# Every map node (draw-point place or AP location name) must appear here.
NODE_ANCHOR: dict[str, str] = {
    # Balamb Garden interior
    "Study Panel: Quezacotl": "balamb_garden",
    "Study Panel: Shiva": "balamb_garden",
    "Balamb Garden Front Gate": "balamb_garden",
    "Balamb Garden Training Center": "balamb_garden",
    "Balamb Garden Library": "balamb_garden",
    "Balamb Garden Cafeteria": "balamb_garden",
    "SeeD Graduation": "balamb_garden",
    "Balamb Garden MD Level": "balamb_garden",
    "Balamb Garden Master Room": "balamb_garden",
    "Balamb Garden MD Level: Leviathan": "balamb_garden",
    "NORG Defeated": "balamb_garden",
    # Balamb island
    "Balamb Town Square": "balamb_town",
    "Balamb Harbor": "balamb_town",
    "Balamb Town: Pandemona": "balamb_town",
    "Balamb Liberated": "balamb_town",
    "Fire Cavern: Ifrit": "fire_cavern",
    "Fire Cavern Cleared": "fire_cavern",
    "Fire Cavern": "fire_cavern",
    # Galbadia continent
    "Dollet Comm Tower: Siren": "dollet",
    "Dollet Exam Completed": "dollet",
    "Dollet Town Square": "dollet",
    "Dollet Comm Tower": "dollet",
    "Magical Lamp: Diablos": "timber",
    "Timber: Forest Owls Mission": "timber",
    "Cid's Parting Gift": "timber",
    "Timber City Square": "timber",
    "Timber Editorial Department": "timber",
    "Timber Forest": "timber_forest",
    "Tomb of the Unknown King: Brothers": "tomb",
    "Tomb of the Unknown King": "tomb",
    "Deling Sewers: Carbuncle": "deling",
    "Deling City: Sorceress Assassination": "deling",
    "Deling City Square": "deling",
    "Deling City Sewer": "deling",
    "Winhill Village": "winhill",
    "Winhill Vacant House": "winhill",
    "Missile Base Mission": "missile_base",
    "Missile Base": "missile_base",
    "D-District Prison Escape": "d_district",
    "D-District Prison": "d_district",
    "Prison Desert": "d_district",
    # Galbadia Garden interior
    "Galbadia Garden Hall": "galbadia_garden",
    "Galbadia Garden Clubroom": "galbadia_garden",
    "Galbadia Garden Athletic Track": "galbadia_garden",
    "Galbadia Garden Gymnasium": "galbadia_garden",
    "Galbadia Garden Back Entrance": "galbadia_garden",
    "Galbadia Garden Auditorium": "galbadia_garden",
    "Galbadia Garden: Cerberus": "galbadia_garden",
    "Galbadia Garden: Alexander": "galbadia_garden",
    "Battle of the Gardens": "galbadia_garden",
    # Fisherman's Horizon + Esthar
    "FH Station Yard": "fh",
    "FH Residential Area": "fh",
    "Fishermans Horizon": "fh",
    "FH Factory": "fh",
    "FH Mayor's Residence": "fh",
    "Fisherman's Horizon: Garden Repaired": "fh",
    "FH Great Salt Lake": "salt_lake",  # despite the table's "FH" prefix
    "Esthar City": "esthar",
    "Odine's Laboratory": "esthar",
    "Odine's Laboratory Lobby": "esthar",
    "Solomon Ring: Doomtrain": "esthar",
    "Lunatic Pandora Laboratory": "pandora_lab",
    "Sorceress Memorial": "memorial",
    "Esthar: Lunar Base Launch": "lunar_gate",
    "Tears' Point": "tears_point",
    "Tears Point: Fallen Relic": "tears_point",
    "Lunatic Pandora": "lunatic_pandora",
    "Lunatic Pandora: Adel Defeated": "lunatic_pandora",
    # Space
    "Lunar Base Pod": "space",
    "Lunar Base: Ragnarok Landing": "space",
    "Lunar Base Residential Zone": "space",
    "Ragnarok Aisle": "space",
    "Ragnarok Hangar": "space",
    # Trabia + Shumi
    "Trabia Garden Front Gate": "trabia",
    "Trabia Garden Cemetery": "trabia",
    "Trabia Garden Festival Stage": "trabia",
    "Shumi Village Entrance": "shumi",
    "Shumi Village": "shumi",
    "Shumi Village Residence": "shumi",
    # Centra + ocean
    "Centra Excavation Site": "centra_exc",
    "Centra Excavation Site #2": "centra_exc",
    "Centra Ruins": "centra_ruins",
    "Centra Ruins: Tonberry King": "centra_ruins",
    "Edea's House Bedroom": "edea",
    "White SeeD Ship Cabin": "white_seed",
    "Cactuar Island: Jumbo Cactuar": "cactuar",
    "Deep Sea Research Center: Bahamut": "deep_sea",
    "Ultima Weapon: Eden": "deep_sea",
    "Deep Sea Research Center": "deep_sea",
    "Deep Sea Deposit": "deep_sea",
    # Ultimecia's Castle
    "Ultimecia's Castle Entered": "ult_castle",
    "Ultimecia Castle": "ult_castle",
    "Ultimecia Castle Storage Room": "ult_castle",
    "Ultimecia Castle Passageway": "ult_castle",
    "Ultimecia Castle Courtyard": "ult_castle",
    "Ultimecia Castle Chapel": "ult_castle",
    "Ultimecia Castle Clock Tower": "ult_castle",
    "Ultimecia Castle Master Room": "ult_castle",
    "Ultimecia Castle Wine Cellar": "ult_castle",
    "Ultimecia Castle Treasure Room": "ult_castle",
    "Ultimecia Castle Terrace": "ult_castle",
    "Ultimecia Castle Art Gallery": "ult_castle",
    "Ultimecia Castle Armory": "ult_castle",
    "Ultimecia Castle Prison Cell": "ult_castle",
    # Core additions (Gerogero / Seifer at Lunatic Pandora)
    "Timber: Fake President Unmasked": "timber",
    "Lunatic Pandora: Seifer Defeated": "lunatic_pandora",
    # Optional bosses (optional_boss_checks)
    "Centra Ruins: Odin Defeated": "centra_ruins",
    "Ultimecia Castle: Omega Weapon": "ult_castle",
    "UFO Sighting: Beach (Moai)": "ufo_beach",
    "UFO Sighting: Plains (Cow)": "ufo_plains",
    "UFO Sighting: Tundra (Metal)": "ufo_tundra",
    "UFO Sighting: Desert (Pyramid)": "ufo_desert",
    "UFO?? Shot Down": "ufo_fight",
    "PuPu Encountered": "pupu",
    "Ultimecia Castle: Krysta": "ult_castle",
    "Ultimecia Castle: Tri-Point": "ult_castle",
    "Ultimecia Castle: Catoblepas": "ult_castle",
    "Ultimecia Castle: Trauma": "ult_castle",
    "Ultimecia Castle: Gargantua": "ult_castle",
    "Ultimecia Castle: Red Giant": "ult_castle",
    "Ultimecia Castle: Tiamat": "ult_castle",
    # Triple Triad (triple_triad_checks): the four region rule-abolish checks are
    # geographic; everything else (win/card ladders, CC Group, compendium) is a
    # counter and goes to the Triple Triad panel on the Extras tab (see the
    # group loop below).
    "Rule Abolished: Random (Dollet)": "dollet",
    "Rule Abolished: Random (Trabia)": "trabia",
    "Rule Abolished: Random (Centra)": "centra_ruins",
    "Rule Abolished: Random (Lunar Gate)": "lunar_gate",
    # Optional-boss additions: Sphinxaur, kill checks, Ragnarok Propagators
    "Ultimecia Castle: Sphinxaur": "ult_castle",
    "Ultima Weapon Defeated": "deep_sea",
    "Jumbo Cactuar Defeated": "cactuar",
    "Ragnarok: Red Propagator (Cargo Bay)": "space",
    "Ragnarok: Red Propagator (Cargo Bay Door)": "space",
    "Ragnarok: Purple Propagator": "space",
    "Ragnarok: Green Propagator": "space",
    "Ragnarok: Yellow Propagator": "space",
    "Ragnarok: Purple Propagator (Cargo)": "space",
    "Ragnarok: Green Propagator (Cargo)": "space",
    "Ragnarok: Yellow Propagator (Cargo)": "space",
    # Magazines (magazine_checks) — pinned at their real pickup spots
    "Magazine: Weapons Monthly 1st": "ult_castle",
    "Magazine: Weapons Monthly March": "balamb_garden",
    "Magazine: Weapons Monthly April": "deling",
    "Magazine: Weapons Monthly May": "d_district",
    "Magazine: Weapons Monthly June": "fh",
    "Magazine: Weapons Monthly July": "trabia",
    "Magazine: Weapons Monthly August": "esthar",
    "Magazine: Combat King 001": "d_district",
    "Magazine: Combat King 002": "balamb_town",
    "Magazine: Combat King 003": "esthar",
    "Magazine: Combat King 004": "esthar",
    "Magazine: Combat King 005": "lunatic_pandora",
    "Magazine: Pet Pals Vol.1": "timber",
    "Magazine: Pet Pals Vol.2": "timber",
    "Magazine: Pet Pals Vol.3": "timber",
    "Magazine: Pet Pals Vol.4": "timber",
    "Magazine: Pet Pals Vol.5": "esthar",
    "Magazine: Pet Pals Vol.6": "esthar",
    # Timber Maniacs issues (magazine_checks) — pinned at their pickup spots
    "Timber Maniacs: Balamb Hotel": "balamb_town",
    "Timber Maniacs: Balamb Station": "balamb_town",
    "Timber Maniacs: Dollet Pub": "dollet",
    "Timber Maniacs: Dollet Hotel": "dollet",
    "Timber Maniacs: Timber Maniacs Building": "timber",
    "Timber Maniacs: Timber Hotel": "timber",
    "Timber Maniacs: Deling City Hotel": "deling",
    "Timber Maniacs: FH Grease Monkey's House": "fh",
    "Timber Maniacs: FH Hotel": "fh",
    "Timber Maniacs: Trabia Garden Cemetery": "trabia",
    "Timber Maniacs: Centra Ruins": "centra_ruins",
    "Timber Maniacs: Shumi Village": "shumi",
    "Timber Maniacs: Edea's House": "edea",
    "Timber Maniacs: White SeeD Ship": "white_seed",
    "Magazine: Occult Fan I": "balamb_garden",
    "Magazine: Occult Fan II": "timber",
    "Magazine: Occult Fan III": "fh",
    "Magazine: Occult Fan IV": "esthar",
    "Magazine: Girl Next Door": "timber",
    # Laguna dream completions (pinned at each dream's real-world locale)
    "Laguna Dream 1: Deling City": "deling",
    "Laguna Dream 2: Centra Excavation": "timber",
    "Laguna Dream 3: Winhill": "winhill",
    "Laguna Dream 4: Trabia Canyon": "trabia",
    "Laguna Dream 5: Esthar": "esthar",
    # Ultimecia Castle seal ladder
    **{f"Ultimecia Castle: {o} Seal Broken": "ult_castle"
       for o in ("First", "Second", "Third", "Fourth",
                 "Fifth", "Sixth", "Seventh", "Eighth")},
}

# Rare-card, sidequest, stat-ladder and Triple Triad checks live in panels on
# the Extras tab; anchor them from the table's group field so new entries never
# need hand-placement (explicit NODE_ANCHOR entries above still win).
_GROUP_PANEL = {"cards": "rare_cards", "sidequest": "sidequests", "stats": "stats", "tt_rules": "triple_triad",
                "tt": "triple_triad", "abilities": ABILITIES_ANCHOR}
for _d in ff8_locations.LOCATION_TABLE:
    if _d.group in _GROUP_PANEL:
        NODE_ANCHOR.setdefault(_d.name, _GROUP_PANEL[_d.group])


# Per-area world-map views, one nested tab each under "World Map". Keys match
# ff8/areas.py AREAS (the client publishes the player's current area under
# these keys and the pack's autotracking activates the matching tab). The five
# geographic views are rendered straight from the walkmesh at a finer scale
# by tools/mapgen (geo.json "areas"); Space and Castle are crops of their
# inset panels on the world image. A pin lands in every view containing it.
WORLD_PIN_SIZE = 40
# PopTracker draws pins at a constant screen size (location_size scaled by
# how much the image is shrunk to fit its widget), so each map's pin size is
# chosen from its image size: ~PIN_SCREEN_PX in a WIDGET_W x WIDGET_H widget.
PIN_SCREEN_PX = 14
WIDGET_W, WIDGET_H = 1000, 700


def pin_size(width: int, height: int) -> int:
    return max(22, min(80, round(PIN_SCREEN_PX * max(width / WIDGET_W, height / WIDGET_H))))


def view_pin_size(view: str) -> int:
    v = AREA_VIEWS[view]
    return pin_size(v["width"], v["height"])


def _inset_rect(key: str) -> tuple[int, int, int, int]:
    x, y, cols, _title = INSETS[key]
    w = INSET_PAD * 2 + cols * INSET_PITCH
    return (x - 10, y - 10, x + w + 10, y + 10 + INSET_HEADER + INSET_PAD * 2 + 8 * INSET_PITCH)


def area_views() -> dict[str, dict]:
    """View key -> {x0, y0 (world units), scale, width, height, image | crop}."""
    out = {}
    for view, a in GEO["areas"].items():
        out[view] = {"x0": a["x0"], "y0": a["y0"], "scale": a["scale"],
                     "width": a["width"], "height": a["height"],
                     "image": GEO_DIR / a["image"]}
    w = GEO["world"]
    for view, key in (("space", "space"), ("castle", "ult_castle")):
        x0, y0, x1, y1 = _inset_rect(key)
        out[view] = {"x0": x0 * w["scale"] + w["x0"], "y0": y0 * w["scale"] + w["y0"],
                     "scale": w["scale"], "width": x1 - x0, "height": y1 - y0,
                     "image": None, "crop": (x0, y0, x1, y1)}
    return out


AREA_VIEWS = area_views()
assert set(AREA_VIEWS) == set(ff8_areas.AREAS), "area views out of sync with ff8/areas.py"


def view_px(view: str, px: float, py: float) -> tuple[float, float]:
    """World-image pixel -> this view's pixel."""
    v, w = AREA_VIEWS[view], GEO["world"]
    wx = px * w["scale"] + w["x0"]
    wy = py * w["scale"] + w["y0"]
    return ((wx - v["x0"]) / v["scale"], (wy - v["y0"]) / v["scale"])


def in_view(view: str, vx: float, vy: float) -> bool:
    v = AREA_VIEWS[view]
    return 0 <= vx < v["width"] and 0 <= vy < v["height"]


# place key (tools/mapgen PLACE_RULES) -> area view its floor-plan tab lives under
PLACE_AREA = {
    "balamb": "balamb", "balamb_garden": "balamb", "fire_cavern": "balamb",
    "dollet": "galbadia", "timber": "galbadia", "timber_forest": "galbadia",
    "galbadia_garden": "galbadia", "deling": "galbadia", "d_district": "galbadia",
    "missile_base": "galbadia", "winhill": "galbadia", "tomb": "galbadia",
    "vehicles": "galbadia",
    "trabia": "trabia", "shumi": "trabia", "trabia_canyon": "trabia",
    "fh": "esthar", "salt_lake": "esthar", "esthar": "esthar", "lunar_gate": "esthar",
    "memorial": "esthar", "tears_point": "esthar", "pandora_lab": "esthar",
    "lunatic_pandora": "esthar",
    "centra_exc": "centra", "centra_ruins": "centra", "edea": "centra",
    "white_seed": "centra", "deep_sea": "centra", "chocobo": "centra",
    "ragnarok": "space", "lunar_base": "space",
    "ult_castle": "castle",
}


def cluster(cx: float, cy: float, keys: list, pitch: int,
            bounds: tuple[int, int, int, int] | None = None) -> dict:
    """Spread keys on a square grid centred on (cx, cy), clamped to bounds."""
    n = len(keys)
    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)
    x0 = cx - (cols - 1) * pitch / 2
    y0 = cy - (rows - 1) * pitch / 2
    if bounds:
        bx0, by0, bx1, by1 = bounds
        half = pitch / 2
        x0 = min(max(x0, bx0 + half), bx1 - half - (cols - 1) * pitch)
        y0 = min(max(y0, by0 + half), by1 - half - (rows - 1) * pitch)
    return {key: (round(x0 + (j % cols) * pitch), round(y0 + (j // cols) * pitch))
            for j, key in enumerate(keys)}


def area_view_coords(geo_coords: dict, by_anchor: dict, exact: dict) -> dict[str, dict]:
    """Per-view {node key: (x, y)} in the view's pixel space. Landmark clusters
    are re-laid around the anchor in view pixels so zoomed views stay tidy;
    exact pins (world draw points) and inset pins keep their spot."""
    out = {view: {} for view in AREA_VIEWS}
    placed = set()
    for anchor, keys in by_anchor.items():
        if anchor in EXTRAS_PANELS or anchor in INSETS:
            continue
        ax, ay, _label = ANCHORS[anchor]
        for view, v in AREA_VIEWS.items():
            vx, vy = view_px(view, ax, ay)
            if in_view(view, vx, vy):
                out[view].update(cluster(vx, vy, keys, view_pin_size(view) + 4,
                                         (0, 0, v["width"], v["height"])))
        placed.update(keys)
    inset_keys = {k for a, keys in by_anchor.items() if a in INSETS for k in keys}
    for key, (x, y) in geo_coords.items():
        if key in placed:
            continue
        for view, v in AREA_VIEWS.items():
            # inset panels are drawn on the world image only; their pins belong
            # to their own crop view, not to a continent render they overlap
            if (key in inset_keys) != (v["image"] is None):
                continue
            vx, vy = view_px(view, x, y)
            if in_view(view, vx, vy):
                out[view][key] = (round(vx), round(vy))
    return out


def place_labels(d: ImageDraw.ImageDraw, labels: list[tuple[str, float, float, float, float]],
                 font, size: tuple[int, int]):
    """Draw landmark labels next to their pin clusters, avoiding other
    clusters and labels. `labels` = (text, x0, y0, x1, y1 of the cluster)."""
    taken = [(x0, y0, x1, y1) for _t, x0, y0, x1, y1 in labels]
    W, H = size
    pad = 6

    def hits(box):
        return any(box[0] < t[2] and box[2] > t[0] and box[1] < t[3] and box[3] > t[1]
                   for t in taken)

    for text, x0, y0, x1, y1 in labels:
        bb = d.textbbox((0, 0), text, font=font, stroke_width=3)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        cx = (x0 + x1) / 2
        cy = (y0 + y1) / 2
        cands = [(cx - tw / 2, y1 + pad), (cx - tw / 2, y0 - pad - th),
                 (x1 + pad, cy - th / 2), (x0 - pad - tw, cy - th / 2),
                 (cx - tw / 2, y1 + pad + th), (cx - tw / 2, y0 - pad - 2 * th)]
        box = None
        for lx, ly in cands:
            lx = min(max(lx, 2), W - tw - 2)
            ly = min(max(ly, 2), H - th - 2)
            box = (lx, ly, lx + tw, ly + th)
            if not hits(box):
                break
        d.text((box[0], box[1]), text, font=font, fill="#f1f4fa", stroke_width=3,
               stroke_fill="#0c1220")
        taken.append(box)


def cluster_boxes(by_anchor: dict, coords: dict, half: float):
    """[(label, x0, y0, x1, y1)] for every labelled anchor with pins in coords."""
    out = []
    for anchor, (ax, ay, label) in ANCHORS.items():
        if not label:
            continue
        pts = [coords[k] for k in by_anchor.get(anchor, []) if k in coords]
        if not pts:
            continue
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        out.append((label, min(xs) - half, min(ys) - half, max(xs) + half, max(ys) + half))
    return out


def draw_area_views(world_png: Path, by_anchor: dict, view_coords: dict):
    """Per-area view images: the mapgen render (or the inset crop) plus labels."""
    world = Image.open(world_png)
    font = _font(34)
    for view, v in AREA_VIEWS.items():
        if v["image"]:
            img = Image.open(v["image"]).convert("RGB")
            d = ImageDraw.Draw(img)
            place_labels(d, cluster_boxes(by_anchor, view_coords[view],
                                          (view_pin_size(view) + PLACE_PIN_EXTRA) / 2),
                         font, img.size)
        else:
            img = world.crop(v["crop"])
        img.save(world_png.parent / f"area_{view}.png", optimize=True)


def panel_geometry(spec: tuple[int, int, int, str], count: int) -> tuple[int, int, int, int, int]:
    """Return (x, y, w, h, cols) of a panel `(x, y, cols, title)` holding `count` nodes."""
    x, y, cols, _title = spec
    rows = math.ceil(count / cols)
    w = INSET_PAD * 2 + cols * INSET_PITCH
    h = INSET_HEADER + INSET_PAD * 2 + rows * INSET_PITCH
    return x, y, w, h, cols


def inset_geometry(key: str, count: int) -> tuple[int, int, int, int, int]:
    return panel_geometry(INSETS[key], count)


def panel_node_coords(spec, keys) -> dict:
    x, y, _w, _h, cols = panel_geometry(spec, len(keys))
    coords = {}
    for j, key in enumerate(keys):
        r, c = divmod(j, cols)
        coords[key] = (x + INSET_PAD + c * INSET_PITCH + INSET_PITCH // 2,
                       y + INSET_HEADER + INSET_PAD + r * INSET_PITCH
                       + INSET_PITCH // 2 - INSET_PAD // 2)
    return coords


def node_exact_spot(node: dict) -> tuple[int, int] | None:
    """World-image pixel of a node that has its own exact world position
    (world draw points, by savemap slot)."""
    slot = node.get("slot")
    if slot is not None and slot >= 128:
        pt = GEO["world_draw"].get(str(slot))
        if pt:
            return world_px(pt["x"], pt["y"])
    return None


def layout_geo(nodes, order_by_region):
    """Assign map coordinates to every node key.

    Returns (world_coords, extras_coords, by_anchor, exact): a node is on
    exactly one of the world map or the Extras panels (ability nodes are on
    neither — see layout_abilities()). `exact` holds the nodes pinned at
    their own world spot rather than in an anchor cluster.
    """
    by_anchor: dict[str, list] = {}
    exact: dict[tuple, tuple[int, int]] = {}
    for region in ALL_REGIONS:
        for key in order_by_region[region]:
            node = nodes[key]
            spot = node_exact_spot(node)
            if spot:
                exact[key] = spot
                continue
            anchor = NODE_ANCHOR.get(node["name"]) or NODE_ANCHOR.get(node.get("place", ""))
            assert anchor, f"unanchored node: {node['name']!r} — add it to NODE_ANCHOR"
            by_anchor.setdefault(anchor, []).append(key)
    # label-only landmarks (e.g. the Ragnarok islands, whose draw points pin
    # themselves) may have no clustered nodes; panels may not
    unused = (set(INSETS) | set(EXTRAS_PANELS)) - set(by_anchor)
    assert not unused, f"panels with no nodes: {unused}"

    by_anchor.pop(ABILITIES_ANCHOR, None)   # laid out by layout_abilities()
    coords: dict[tuple, tuple[int, int]] = dict(exact)
    extras: dict[tuple, tuple[int, int]] = {}
    for anchor, keys in by_anchor.items():
        if anchor in EXTRAS_PANELS:
            extras.update(panel_node_coords(EXTRAS_PANELS[anchor], keys))
        elif anchor in INSETS:
            coords.update(panel_node_coords(INSETS[anchor], keys))
        else:
            ax, ay, _label = ANCHORS[anchor]
            coords.update(cluster(ax, ay, keys, CLUSTER_PITCH, (0, 0, GEO_W, GEO_H)))
    return coords, extras, by_anchor, exact


def layout_places(nodes) -> dict:
    """{node key: [map_location dicts]} on the per-place floor-plan sheets.

    Draw points sit exactly where their sparkle is (slot -> projected
    position); other checks cluster around the centre of the screen they are
    obtained on (tools/mapgen/attribution.json)."""
    places = GEO.get("places", {})
    id2name = {BASE_ID + d.id_offset: d.name for d in ff8_locations.LOCATION_TABLE}
    pins: dict[tuple, list[dict]] = {}
    by_screen: dict[tuple[str, str], list] = {}
    for key, node in nodes.items():
        slot = node.get("slot")
        if slot is not None:
            for pkey, place in places.items():
                xy = place["draw_points"].get(str(slot))
                if xy:
                    pins.setdefault(key, []).append(
                        {"map": f"place_{pkey}", "x": xy[0], "y": xy[1]})
            if key in pins:
                continue
        names = [id2name[s[1]] for s in node["sections"]]
        attr = next((ATTRIBUTION[n] for n in names if n in ATTRIBUTION), None)
        if not attr or attr.get("kind") != "field" or not attr.get("fields"):
            continue
        field = attr["fields"][0]
        field = CANONICAL_FIELD.get(field, field)
        for pkey, place in places.items():
            if field in place["screens"]:
                by_screen.setdefault((pkey, field), []).append(key)
                break
    for (pkey, field), keys in by_screen.items():
        place = places[pkey]
        scr = place["screens"][field]
        ox, oy = scr["origin"]
        tw, th = place.get("tile", (800, 560))
        cx, cy = scr["centre"]
        pitch = pin_size(place["width"], place["height"]) + 4
        for key, (x, y) in cluster(cx, cy, keys, pitch,
                                   (ox, oy, ox + tw, oy + th)).items():
            pins.setdefault(key, []).append({"map": f"place_{pkey}", "x": x, "y": y})
    return pins


def draw_extras(path: Path, by_anchor: dict[str, list]) -> tuple[int, int]:
    """Panel board for the Extras tab; returns the image size."""
    boxes = {key: panel_geometry(EXTRAS_PANELS[key], len(by_anchor[key]))
             for key in EXTRAS_PANELS}
    width = max(x + w for x, _y, w, _h, _c in boxes.values()) + 14
    height = max(y + h for _x, y, _w, h, _c in boxes.values()) + 14
    img = Image.new("RGB", (width, height), "#10141f")
    d = ImageDraw.Draw(img)
    title_font = _font(15)
    for key, (x, y, w, h, _cols) in boxes.items():
        d.rounded_rectangle([x, y, x + w, y + h], radius=8,
                            fill="#1c2333", outline="#3b4a6b", width=2)
        d.text((x + PAD, y + 6), EXTRAS_PANELS[key][3], font=title_font, fill="#e8ecf5")
    img.save(path)
    return width, height


# ---------------------------------------------------------------------------
# GF Abilities tab: 16 columns (signature abilities top-down, Mastered last)
# and the party-wide abilities-learned ladder along the bottom.
# ---------------------------------------------------------------------------

ABIL_W = 1100
ABIL_COL = 66
ABIL_X0 = 22 + ABIL_COL // 2
ABIL_TOP = 74
ABIL_ROW = 44
ABIL_LADDER_GAP = 34
ABIL_LADDER_PITCH = 90


def layout_abilities(nodes, order_by_region):
    """Return (coords, per_gf_keys, ladder_keys, height) for the abilities map."""
    per_gf: dict[int, list] = {i: [] for i in range(len(GF_ORDER))}
    ladder: list = []
    for region in ALL_REGIONS:
        for key in order_by_region[region]:
            node = nodes[key]
            if node["sections"][0][2] != "abilities":
                continue
            data = ff8_locations.LOCATION_DATA_BY_NAME[node["name"]]
            if data.requires_gf is None:
                ladder.append(key)
            else:
                per_gf[data.requires_gf].append(key)
    coords: dict[tuple, tuple[int, int]] = {}
    rows = max(len(v) for v in per_gf.values())
    for gf, keys in per_gf.items():
        cx = ABIL_X0 + gf * ABIL_COL
        for r, key in enumerate(keys):
            coords[key] = (cx, ABIL_TOP + r * ABIL_ROW)
    ladder_y = ABIL_TOP + rows * ABIL_ROW + ABIL_LADDER_GAP
    lx0 = ABIL_W // 2 - (len(ladder) - 1) * ABIL_LADDER_PITCH // 2
    for j, key in enumerate(ladder):
        coords[key] = (lx0 + j * ABIL_LADDER_PITCH, ladder_y)
    return coords, per_gf, ladder, ladder_y + 44


def draw_abilities(path: Path, nodes, coords, per_gf, ladder, height: int):
    scale = 3
    img = Image.new("RGB", (ABIL_W * scale, height * scale), "#10141f")
    d = ImageDraw.Draw(img)
    head = _font(13 * scale)
    small = _font(9 * scale)
    tiny = _font(8 * scale)

    def text_c(x, y, txt, font, fill):
        w = d.textlength(txt, font=font)
        d.text((x * scale - w / 2, y * scale), txt, font=font, fill=fill)

    d.text((22 * scale, 8 * scale), "GF Abilities", font=head, fill="#e8ecf5")
    for gf, keys in per_gf.items():
        cx = ABIL_X0 + gf * ABIL_COL
        color = GF_COLORS[gf]
        text_c(cx, 30, GF_ORDER[gf], small, "#e8ecf5")
        d.line([(cx * scale - 26 * scale, 44 * scale), (cx * scale + 26 * scale, 44 * scale)],
               fill=color, width=scale)
        for key in keys:
            x, y = coords[key]
            name = nodes[key]["name"]
            label = "Mastered" if name.endswith(" Mastered") else name.split(" Learns ", 1)[1]
            d.ellipse([(x - 8) * scale, (y - 8) * scale, (x + 8) * scale, (y + 8) * scale],
                      outline=color, width=scale)
            text_c(x, y + 10, label, tiny, "#aab4cc")
    if ladder:
        ly = coords[ladder[0]][1]
        text_c(ABIL_W // 2, ly - 30, "Abilities learned beyond default (all GFs)", small, "#e8ecf5")
        for key in ladder:
            x, y = coords[key]
            n = nodes[key]["name"].rsplit(": ", 1)[1]
            d.ellipse([(x - 8) * scale, (y - 8) * scale, (x + 8) * scale, (y + 8) * scale],
                      outline="#4f46e5", width=scale)
            text_c(x, y + 10, n, tiny, "#aab4cc")
    img = img.resize((ABIL_W, height), Image.LANCZOS)
    img.save(path)


def draw_world(path: Path, by_anchor: dict[str, list], geo_coords: dict):
    """The world render plus inset panels and landmark labels."""
    img = Image.open(GEO_DIR / "world.png").convert("RGB")
    d = ImageDraw.Draw(img)

    title_font = _font(30)
    for key, keys in by_anchor.items():
        if key not in INSETS:
            continue
        x, y, w, h, _cols = inset_geometry(key, len(keys))
        d.rounded_rectangle([x, y, x + w, y + h], radius=14,
                            fill="#1c2333", outline="#3b4a6b", width=3)
        d.text((x + 16, y + 10), INSETS[key][3], font=title_font, fill="#e8ecf5")

    place_labels(ImageDraw.Draw(img),
                 cluster_boxes(by_anchor, geo_coords, (WORLD_PIN_SIZE + PLACE_PIN_EXTRA) / 2),
                 _font(34), img.size)
    img.save(path, optimize=True)


# ---------------------------------------------------------------------------
# Build node/section model from the location tables
# ---------------------------------------------------------------------------

def build_model():
    """Group locations into map nodes.

    Non-draw locations each get their own node named by the AP location name.
    Draw points are grouped into one node per field place, one section per spell.
    Returns (nodes, node order per region) where a node is a dict with keys:
    region, name, sections [= list of (section_name, ap_id, group, access)],
    where group is the location's option group ("core"/"draw"/"tt"/"boss_extra").
    """
    draw_place = {}   # AP location name -> (place, spell)
    draw_slot = {}    # AP location name -> savemap draw slot
    for slot, spell, place, region, missable in ff8_locations.DRAW_POINT_TABLE:
        name = f"Draw Point: {place} ({spell})"
        draw_place[name] = (place, spell)
        draw_slot[name] = slot
    # World draw locations carry "#n" dedupe suffixes; recover (place, spell)
    # by zipping with the slot-sorted table they were built from.
    for d, (slot, spell, place, region) in zip(
            ff8_locations.WORLD_DRAW_POINT_LOCATIONS,
            sorted(ff8_locations.WORLD_DRAW_POINT_TABLE)):
        draw_place[d.name] = (place, spell)
        draw_slot[d.name] = slot

    nodes: dict[tuple[str, str], dict] = {}
    order_by_region: dict[str, list] = {r: [] for r in ALL_REGIONS}

    def get_node(region: str, node_name: str) -> dict:
        key = (region, node_name)
        if key not in nodes:
            nodes[key] = {"region": region, "name": node_name, "sections": []}
            order_by_region[region].append(key)
        return nodes[key]

    # Node-level extra access requirements, mirroring __init__.set_rules.
    # Requirements AND together inside one rule string.
    ACCESS = {"Magical Lamp: Diablos": ["magical_lamp"],
              "Solomon Ring: Doomtrain": ["solomon_ring"]}

    def require(name: str, *rules: str) -> None:
        rule = ",".join(rules)
        prior = ACCESS.get(name)
        ACCESS[name] = [f"{prior[0]},{rule}"] if prior else [rule]

    for d in ff8_locations.LOCATION_TABLE:
        if d.requires_gf is not None:
            require(d.name, gf_code(GF_ORDER[d.requires_gf]))
        # Story keys: a check inside a keyed area needs the door open (the
        # Queen of Cards' cards need every door she can stand behind).
        keys = ff8_regions.key_areas_of_location(d.name)
        if keys:
            require(d.name, *(f"$key_access|{KEY_CODES[a]}" for a in keys))
        # Drawing needs a junctioned GF (and the Draw command); the scan
        # ladder casts the Scan it draws, so it needs Magic too. The tracker
        # showed Balamb Garden's draw points in logic with no GF (2026-10-16).
        draw_dep = (d.group in ("draw", "world_draw")
                    or any(ff8_world_reads_magic_drawn(k, v) for k, v in d.triggers))
        scan_dep = any(k == "popcount_ge" and v[0] == ff8_memory.ENEMIES_SCANNED
                       for k, v in d.triggers)
        if draw_dep or scan_dep:
            require(d.name, "gf", lock_rule("Draw Command"))
        if scan_dep:
            require(d.name, lock_rule("Magic Command"))
        # GF ability checks: a learn check needs the lock items along its
        # prerequisite chain, Mastered every lock item on the GF's list.
        if d.group == "abilities" and d.requires_gf is not None:
            gf = d.requires_gf
            if d.name.endswith(" Mastered"):
                abilities = ff8_abilities.GF_LEARN_LISTS[gf]
            else:
                aid = ff8_abilities.GF_ABILITY_NAMES.index(
                    d.name.split(" Learns ", 1)[1])
                abilities = ff8_abilities.prereq_chain(gf, aid)
            needed = sorted({item for a in abilities for item in lock_items_for(gf, a)})
            if needed:
                require(d.name, *(lock_rule(item) for item in needed))

    for d in ff8_locations.LOCATION_TABLE:
        ap_id = BASE_ID + d.id_offset
        if (d.name in ff8_locations.DRAW_POINT_NAMES
                or d.name in ff8_locations.WORLD_DRAW_POINT_NAMES):
            # one node per draw point so each sparkle gets its own exact pin
            place, spell = draw_place[d.name]
            node = get_node(region_of(d), d.name.removeprefix("Draw Point: "))
            node["place"] = place
            node["slot"] = draw_slot[d.name]
            # section named like the node: landmark pins list sections by
            # name, so "Cure Draw Point" alone would not say which one
            node["sections"].append((node["name"], ap_id, d.group, ACCESS.get(d.name)))
        else:
            node = get_node(region_of(d), d.name)
            node["sections"].append((d.name, ap_id, d.group, ACCESS.get(d.name)))

    # Draw-point-only places sort after story/GF nodes inside each region.
    for region in order_by_region:
        order_by_region[region].sort(
            key=lambda k: all(s[2] in ("draw", "world_draw")
                              for s in nodes[k]["sections"]))
    return nodes, order_by_region


# ---------------------------------------------------------------------------
# Emitters
# ---------------------------------------------------------------------------

def emit_items() -> list[dict]:
    items = []
    for i, gf in enumerate(GF_ORDER):
        items.append({
            "name": f"GF {gf}",
            "type": "toggle",
            "img": f"images/{gf_code(gf)}.png",
            "codes": f"{gf_code(gf)},gf",
        })
    # Cameo GFs are useful-class rewards, not part of the Disc 3 "gf" count.
    for gf in CAMEO_GFS:
        items.append({
            "name": f"GF {gf}",
            "type": "toggle",
            "img": f"images/{gf_code(gf)}.png",
            "codes": gf_code(gf),
        })
    items += [
        {"name": "Magical Lamp", "type": "toggle",
         "img": "images/magical_lamp.png", "codes": "magical_lamp"},
        {"name": "Solomon Ring", "type": "toggle",
         "img": "images/solomon_ring.png", "codes": "solomon_ring"},
        {"name": "Story Progress", "type": "consumable",
         "img": "images/progress.png", "codes": "progress",
         "min_quantity": 0, "max_quantity": MAX_PROGRESS},
        {"name": "Ragnarok", "type": "toggle",
         "img": "images/vehicle_ragnarok.png", "codes": "vehicle_ragnarok"},
    ]
    # Story keys: a toggle per door (story_keys option; the tracker's
    # key_access rule ignores them while the option is off).
    items += [
        {"name": f"Key: {area}", "type": "toggle",
         "img": f"images/{code}.png", "codes": f"{code},storykey"}
        for area, code in KEY_CODES.items()
    ]
    items += [
        {"name": name, "type": "toggle", "img": f"images/{code}.png", "codes": code}
        for name, code in LOCK_CODES.items()
    ]
    items += [
        {"name": name, "type": "toggle", "img": "images/abil_checks.png", "codes": code}
        for name, code in ABILITY_LOCK_CODES.items()
    ]
    items += [
        # Ladder counters (story_gates): the lock items count as groups. Max
        # = every item that can exist including the precollected one.
        {"name": "Character Unlocks", "type": "consumable",
         "img": "images/char_unlocks.png", "codes": "char_unlocks",
         "min_quantity": 0, "max_quantity": ff8_regions.CHARACTER_TOTAL},
        {"name": "Junction Rights", "type": "consumable",
         "img": "images/junction_unlocks.png", "codes": "junction_unlocks",
         "min_quantity": 0, "max_quantity": ff8_regions.JUNCTION_TOTAL},
        {"name": "Command Unlocks", "type": "consumable",
         "img": "images/command_unlocks.png", "codes": "command_unlocks",
         "min_quantity": 0, "max_quantity": ff8_regions.COMMAND_TOTAL},
    ]
    # Check-group visibility toggles: default ON so a manual (unconnected)
    # tracker shows every check group — draw points included; connecting via
    # AP overwrites them from slot data to match the seed's options.
    for name, img, code in [
        ("Draw Point Checks (option)", "draw_points", "opt_draw_points"),
        ("World Draw Point Checks (option)", "wdraw_checks", "opt_wdraw"),
        ("Triple Triad Checks (option)", "tt_checks", "opt_tt"),
        ("Optional Boss Checks (option)", "boss_checks", "opt_boss"),
        ("Rare Card Checks (option)", "card_checks", "opt_cards"),
        ("Sidequest Checks (option)", "sq_checks", "opt_sq"),
        ("Magazine Checks (option)", "mag_checks", "opt_mags"),
        ("Stat Ladder Checks (option)", "stat_checks", "opt_stats"),
        ("GF Ability Checks (option)", "abil_checks", "opt_abil"),
    ]:
        items.append({"name": name, "type": "toggle",
                      "img": f"images/{img}.png", "codes": code,
                      "initial_active_state": True})
    # Follow-the-player: while ON (and autotracking), the map jumps to the
    # area the party is in. A UI preference, so not part of RESET_TOGGLES.
    items.append({"name": "Follow Game (auto area tab)", "type": "toggle",
                  "img": "images/autotab.png", "codes": "opt_autotab",
                  "initial_active_state": True})
    return items


def emit_locations(nodes, order_by_region, geo_coords, board_coords,
                   abil_coords, extras_coords, view_coords,
                   extra_pins: dict | None = None,
                   aggregate: tuple[set, list[dict]] | None = None) -> list[dict]:
    """`aggregate` = (clustered node keys, place nodes): those nodes lose their
    own world/area pins and the place nodes (one per landmark) are appended
    as a top-level "Places" location instead."""
    skip_world = aggregate[0] if aggregate else set()
    out = []
    for region in ALL_REGIONS:
        if not order_by_region[region]:
            continue
        if region in HUBS:
            grant_beat, vehicle = HUBS[region]
            # the ship edge may start at a later beat (regions.HUB_SHIP_FROM)
            ship_from = ff8_regions.HUB_SHIP_FROM.get(region)
            from_idx = REGION_INDEX[ship_from] if ship_from else 0
            access = [f"$hub_access|{REGION_INDEX[grant_beat]}|{VEHICLE_CODES[vehicle]}|{from_idx}"]
        elif region in EARLY_REGIONS:
            first_beat, vehicle = EARLY_REGIONS[region]
            gated = int(ff8_regions.early_area_gated(region.removeprefix(ff8_regions.EARLY_PREFIX)))
            access = [f"$early_access|{REGION_INDEX[first_beat]}|{VEHICLE_CODES[vehicle]}|{gated}"]
        else:
            access = [f"$beat_access|{REGION_INDEX[region]}"]
        children = []
        for key in order_by_region[region]:
            node = nodes[key]
            if key in abil_coords:
                ax, ay = abil_coords[key]
                map_locations = [{"map": "abilities", "x": ax, "y": ay}]
            elif key in extras_coords:
                ex, ey = extras_coords[key]
                bx, by = board_coords[key]
                map_locations = [{"map": "extras", "x": ex, "y": ey},
                                 {"map": "board", "x": bx, "y": by}]
            else:
                gx, gy = geo_coords[key]
                bx, by = board_coords[key]
                map_locations = [{"map": "board", "x": bx, "y": by}]
                if key not in skip_world:
                    map_locations.insert(0, {"map": "world", "x": gx, "y": gy})
                    for view in AREA_VIEWS:
                        if key in view_coords[view]:
                            vx, vy = view_coords[view][key]
                            map_locations.append(
                                {"map": f"area_{view}", "x": vx, "y": vy})
            if extra_pins:
                map_locations += extra_pins.get(key, [])
            sections = []
            for sec_name, ap_id, group, sec_access in node["sections"]:
                sec = {"name": sec_name}
                opt_code = GROUP_OPT.get(group)
                if opt_code:
                    if group == "tt_rules" and (sec_name.startswith("Rule Abolished")
                                                or sec_name == "Random Rule Extinct"):
                        # gone from the game under a fixed rule set
                        opt_code += ",$tt_abolish_on"
                    sec["visibility_rules"] = [opt_code]
                if sec_access:
                    sec["access_rules"] = sec_access
                sections.append(sec)
            children.append({
                "name": node["name"],
                "map_locations": map_locations,
                "sections": sections,
            })
        out.append({"name": region, "access_rules": access, "children": children})
    if aggregate:
        out.append({"name": "Places", "children": aggregate[1]})
    return out


PLACE_PIN_EXTRA = 12     # a landmark pin is a little bigger than a lone check pin
# landmark label -> place-node name when the label alone would repeat
PLACE_NODE_NAMES = {
    "ufo_beach": "UFO: Mandy Beach", "ufo_plains": "UFO: Winhill Bluffs",
    "ufo_tundra": "UFO: Heath Peninsula", "ufo_desert": "UFO: Kashkabald Desert",
    "ufo_fight": "UFO?? Shot Down", "pupu": "PuPu",
}


def clustered_keys(by_anchor: dict) -> set:
    """Node keys that sit in a landmark cluster on the world map (not insets,
    not Extras panels, not exact world-draw spots)."""
    return {key for anchor, keys in by_anchor.items()
            if anchor not in INSETS and anchor not in EXTRAS_PANELS for key in keys}


def layout_place_nodes(nodes, by_anchor: dict) -> list[dict]:
    """One location per landmark for the world/area maps. Its sections are
    `ref`s to the real check sections (PopTracker shows one pin whose colour
    aggregates every check inside, lists them on hover, and toggles the real
    section on click), so the floor plans keep the individual pins."""
    out = []
    for anchor, keys in by_anchor.items():
        if anchor in INSETS or anchor in EXTRAS_PANELS:
            continue
        ax, ay, label = ANCHORS[anchor]
        name = PLACE_NODE_NAMES.get(anchor) or label or anchor.replace("_", " ").title()
        map_locations = [{"map": "world", "x": ax, "y": ay,
                          "size": WORLD_PIN_SIZE + PLACE_PIN_EXTRA}]
        for view, v in AREA_VIEWS.items():
            if v["image"] is None:
                continue
            vx, vy = view_px(view, ax, ay)
            if in_view(view, vx, vy):
                map_locations.append({"map": f"area_{view}", "x": round(vx), "y": round(vy),
                                      "size": view_pin_size(view) + PLACE_PIN_EXTRA})
        sections = []
        for key in keys:
            node = nodes[key]
            assert "/" not in node["name"], node["name"]
            for sec_name, _ap_id, _group, _acc in node["sections"]:
                sections.append({"ref": f"{key[0]}/{node['name']}/{sec_name}"})
        out.append({"name": name, "map_locations": map_locations, "sections": sections})
    names = [p["name"] for p in out]
    dups = {n for n in names if names.count(n) > 1}
    assert not dups, f"place node names repeat (extend PLACE_NODE_NAMES): {dups}"
    return out


def aggregate_coords(by_anchor: dict, geo_coords: dict, view_coords: dict):
    """Label geometry for the aggregated maps: every clustered node collapses
    onto its landmark pin."""
    geo = dict(geo_coords)
    views = {view: dict(c) for view, c in view_coords.items()}
    for anchor, keys in by_anchor.items():
        if anchor in INSETS or anchor in EXTRAS_PANELS:
            continue
        ax, ay, _label = ANCHORS[anchor]
        for key in keys:
            geo[key] = (ax, ay)
            for view, v in AREA_VIEWS.items():
                if v["image"] is None:
                    continue
                vx, vy = view_px(view, ax, ay)
                if in_view(view, vx, vy):
                    views[view][key] = (round(vx), round(vy))
                else:
                    views[view].pop(key, None)
    return geo, views


def nudge_duplicate_pins(locations: list[dict], maps: list[dict]) -> int:
    """Two checks can share one exact spot (world draw slots 245/246 sit on
    the same triangle; one D-District entity serves two slots). Universal
    Tracker keys pins by (x, y) per map and would drop one, so shift
    later duplicates one pin width to the right. Returns the count moved."""
    size = {m["name"]: m["location_size"] for m in maps}
    seen: set[tuple[str, int, int]] = set()
    moved = 0
    for region in locations:
        for child in region["children"]:
            for ml in child["map_locations"]:
                key = (ml["map"], ml["x"], ml["y"])
                while key in seen:
                    ml["x"] += size.get(ml["map"], 20) + 4
                    key = (ml["map"], ml["x"], ml["y"])
                    moved += 1
                seen.add(key)
    return moved


def emit_ut_name_mapping(nodes, order_by_region) -> dict[str, int]:
    """Universal Tracker `poptracker_name_mapping`: "<node>/<section>" -> AP id
    (UT matches sections by AP location name otherwise; draw-point sections
    are named without the "Draw Point: " prefix)."""
    out: dict[str, int] = {}
    for region in ALL_REGIONS:
        for key in order_by_region[region]:
            node = nodes[key]
            for sec_name, ap_id, _group, _acc in node["sections"]:
                out[f"{node['name']}/{sec_name}"] = ap_id
    return out


def emit_mapping_lua(nodes, order_by_region) -> str:
    item_lines = []
    for i, gf in enumerate(GF_ORDER):
        item_lines.append(f'    [{BASE_ID + i}] = "{gf_code(gf)}",')
    for d in ff8_items.ITEM_TABLE:
        if d.name == "Magical Lamp":
            item_lines.append(f'    [{BASE_ID + d.id_offset}] = "magical_lamp",')
        elif d.name == "Solomon Ring":
            item_lines.append(f'    [{BASE_ID + d.id_offset}] = "solomon_ring",')
        elif d.name in CAMEO_ITEM_NAMES:
            item_lines.append(
                f'    [{BASE_ID + d.id_offset}] = "{gf_code(d.name.removeprefix("GF "))}",')
        elif d.name in VEHICLE_CODES:
            item_lines.append(f'    [{BASE_ID + d.id_offset}] = "{VEHICLE_CODES[d.name]}",')
        elif d.name in ff8_items.item_name_groups["Character Unlocks"]:
            item_lines.append(f'    [{BASE_ID + d.id_offset}] = "char_unlocks",')
        elif d.name in ff8_items.item_name_groups["Junction Unlocks"]:
            item_lines.append(f'    [{BASE_ID + d.id_offset}] = "junction_unlocks",')
        elif d.name in ff8_items.item_name_groups["Command Unlocks"]:
            item_lines.append(f'    [{BASE_ID + d.id_offset}] = "command_unlocks",')
        elif d.name in ff8_items.item_name_groups["Story Keys"]:
            item_lines.append(f'    [{BASE_ID + d.id_offset}] = "{KEY_CODES[d.grant[1]]}",')
        elif d.name in ABILITY_LOCK_CODES:
            item_lines.append(f'    [{BASE_ID + d.id_offset}] = "{ABILITY_LOCK_CODES[d.name]}",')
        # filler (gil/consumable/magic packs) is not tracked
    extra_lines = [f'    [{BASE_ID + d.id_offset}] = "{LOCK_CODES[d.name]}",'
                   for d in ff8_items.ITEM_TABLE if d.name in LOCK_CODES]

    loc_lines = []
    for region in ALL_REGIONS:
        for key in order_by_region[region]:
            node = nodes[key]
            for sec_name, ap_id, group, _acc in node["sections"]:
                offset = ap_id - BASE_ID
                ref = f"@{region}/{node['name']}/{sec_name}"
                if group in NO_PROGRESS_GROUPS:
                    loc_lines.append(f'    [{ap_id}] = {{section = "{ref}"}},')
                    continue
                if region in HUBS or region in EARLY_REGIONS:
                    loc_lines.append(f'    [{ap_id}] = {{section = "{ref}"}},')
                    continue
                # Only story-bound (core) checks imply their own chapter:
                # card, draw-point and side-quest regions err late, so one
                # early Diablos card used to open Disc 2 (2026-10-20). The
                # client's moment feed (onSetReply) is the precise source.
                if offset not in STORY_PROGRESS_BUMPS and group != "core":
                    loc_lines.append(f'    [{ap_id}] = {{section = "{ref}"}},')
                    continue
                bump = STORY_PROGRESS_BUMPS.get(offset, REGION_INDEX[region])
                loc_lines.append(
                    f'    [{ap_id}] = {{section = "{ref}", progress = {bump}}},')

    toggles = ([gf_code(g) for g in GF_ORDER] + [gf_code(g) for g in CAMEO_GFS]
               + ["magical_lamp", "solomon_ring", "vehicle_ragnarok"]
               + list(KEY_CODES.values()) + list(LOCK_CODES.values())
               + list(ABILITY_LOCK_CODES.values())
               + ["opt_draw_points", "opt_wdraw", "opt_tt", "opt_boss",
                  "opt_cards", "opt_sq", "opt_mags",
                  "opt_stats", "opt_abil"])
    toggle_lines = ",\n    ".join(f'"{c}"' for c in toggles)
    area_lines = "\n".join(f'    {key} = "{ff8_areas.AREAS[key]}",'
                           for key in AREA_VIEWS)
    places = GEO.get("places", {})
    field_lines = "\n".join(
        f'    [{fid}] = {{"{ff8_areas.AREAS[PLACE_AREA[key]]}", "{places[key]["title"]}"}},'
        for fid, key in sorted(GEO.get("field_places", {}).items(), key=lambda kv: int(kv[0]))
        if key in places and key in PLACE_AREA)
    beat_lines = "\n".join(f'    [{i}] = "{name}",' for i, name in enumerate(REGION_CHAIN))
    moment_lines = "\n".join(f'    [{i}] = {ff8_regions.BEAT_START_MOMENT[name]},'
                             for i, name in enumerate(REGION_CHAIN))
    ladder_lines = []
    for mode, rows in ff8_regions.GATE_LADDER.items():
        ladder_lines.append(f'    {mode} = {{')
        for beat, (gfs, chars, junctions, commands) in rows.items():
            ladder_lines.append(
                f'        ["{beat}"] = {{{gfs}, {chars}, {junctions}, {commands}}},')
        ladder_lines.append("    },")
    vehicle_beat_lines = "\n".join(
        f'    ["{beat}"] = "{VEHICLE_CODES[item]}",'
        for beat, item in ff8_regions.VEHICLE_BEATS.items())
    key_beat_lines = "\n".join(
        f'    ["{beat}"] = {{'
        + ", ".join(f'"{KEY_CODES[k[len(ff8_regions.STORY_KEY_PREFIX):]]}"' for k in keys)
        + "},"
        for beat, keys in ff8_regions.STORY_KEY_BEATS.items())

    return f"""-- Generated by tools/gen_tracker_pack.py -- do not edit by hand.
-- AP item id -> tracker item code.
ITEM_MAPPING = {{
{chr(10).join(item_lines)}
}}

-- AP item id -> a second code it also lights (the per-lock toggle beside
-- its ladder counter).
ITEM_EXTRA_CODES = {{
{chr(10).join(extra_lines)}
}}

-- AP location id -> {{section ref, story progress implied by checking it}}.
LOCATION_MAPPING = {{
{chr(10).join(loc_lines)}
}}

RESET_TOGGLES = {{
    {toggle_lines}
}}

-- Data-storage area value -> world-map area tab title (ff8/areas.py AREAS).
AREA_TABS = {{
{area_lines}
}}

-- Field id (the client publishes the field the party stands on) ->
-- {{area tab, floor-plan tab}} for every screen of a town/dungeon that has a
-- floor-plan sheet (tools/mapgen: geo.json field_places).
FIELD_TABS = {{
{field_lines}
}}

-- Story beats by progress index (ff8/regions.py REGION_CHAIN).
BEAT_NAMES = {{
{beat_lines}
}}

-- Story moment each beat starts at (ff8/regions.py BEAT_START_MOMENT): the
-- client publishes the true moment, and the chapter it falls in is reached.
BEAT_START_MOMENTS = {{
{moment_lines}
}}

-- Gate ladder (ff8/regions.py GATE_LADDER): beat -> {{GFs, characters,
-- junction rights, commands}}; the GF column is written for a Disc 3 anchor
-- of {ff8_regions.GF_ANCHOR} and scaled by the seed's gfs_required_for_disc3.
GATE_LADDER = {{
{chr(10).join(ladder_lines)}
}}
GF_ANCHOR = {ff8_regions.GF_ANCHOR}
GF_TOTAL = {ff8_regions.GF_TOTAL}
FIRST_DISC3_BEAT = {REGION_INDEX["Edea's House"]}

-- Beats whose story needs a vehicle you may not have yet (vehicle_gates).
VEHICLE_BEATS = {{
{vehicle_beat_lines}
}}

-- Beats whose main line walks through a keyed door (story_keys = story).
STORY_KEY_BEATS = {{
{key_beat_lines}
}}
"""


INIT_LUA = """Tracker:AddItems("items/items.json")
Tracker:AddMaps("maps/maps.json")
Tracker:AddLocations("locations/locations.json")
Tracker:AddLayouts("layouts/tracker.json")

-- mapping.lua carries the beat names and gate ladder logic.lua reads, so it
-- loads first, AP or not (a manual tracker still needs the access rules).
ScriptHost:LoadScript("scripts/mapping.lua")
ScriptHost:LoadScript("scripts/logic.lua")

if _G.Archipelago then
    ScriptHost:LoadScript("scripts/autotracking.lua")
end
"""

LOGIC_LUA = """-- Access-rule helpers. Mirrors the region gating in ff8/__init__.py:
-- a linear chain of story beats, each entered at its story progress index
-- AND the gate ladder for it (regions.gate_requirements), plus the three
-- travel hubs (vanilla grant beat OR the vehicle item).

-- Seed options, set from slot_data by autotracking.lua (defaults = the
-- apworld defaults, so an unconnected tracker shows the default logic).
AP_OPTS = {
    story_gates = "normal",
    gfs_required_for_disc3 = 6,
    character_locks = true,
    junction_locks = true,
    command_locks = true,
    ability_locks = true,
    vehicle_unlocks = false,
    vehicle_gates = false,
    story_keys = "off",
}
STORY_GATE_MODES = {[0] = "off", [1] = "normal", [2] = "tight"}
STORY_KEY_MODES = {[0] = "off", [1] = "areas", [2] = "story"}

function at_progress(n)
    local o = Tracker:FindObjectForCode("progress")
    return o ~= nil and o.AcquiredCount >= tonumber(n)
end

COUNTER_CODES = {char_unlocks = true, junction_unlocks = true, command_unlocks = true}

local function count(code)
    local o = Tracker:FindObjectForCode(code)
    if o == nil then return 0 end
    if COUNTER_CODES[code] then return o.AcquiredCount end
    return o.Active and 1 or 0
end

-- regions.gate_requirements: item counts needed to ENTER beat `idx`.
function beat_requirements(idx)
    local anchor = tonumber(AP_OPTS.gfs_required_for_disc3) or 0
    local mode = AP_OPTS.story_gates
    local gfs, chars, junctions, commands = 0, 0, 0, 0
    if mode == "off" then
        if idx == FIRST_DISC3_BEAT then gfs = anchor end
        return gfs, 0, 0, 0
    end
    local row = GATE_LADDER[mode] and GATE_LADDER[mode][BEAT_NAMES[idx]]
    if row == nil then return 0, 0, 0, 0 end
    if anchor > 0 then
        gfs = math.floor((row[1] * anchor * 2 + GF_ANCHOR) / (2 * GF_ANCHOR))
        if gfs > GF_TOTAL then gfs = GF_TOTAL end
    end
    if AP_OPTS.character_locks then chars = row[2] end
    if AP_OPTS.junction_locks then junctions = row[3] end
    if AP_OPTS.command_locks then commands = row[4] end
    return gfs, chars, junctions, commands
end

function beat_access(n)
    local idx = tonumber(n)
    if not at_progress(idx) then return false end
    local gfs, chars, junctions, commands = beat_requirements(idx)
    if Tracker:ProviderCountForCode("gf") < gfs then return false end
    -- one character, one junction right and the Draw command are always
    -- precollected; the server sends them on connect, so counts include them.
    if count("char_unlocks") < chars then return false end
    if count("junction_unlocks") < junctions then return false end
    if count("command_unlocks") < commands then return false end
    if AP_OPTS.vehicle_unlocks and AP_OPTS.vehicle_gates then
        local vehicle = VEHICLE_BEATS[BEAT_NAMES[idx]]
        if vehicle and count(vehicle) < 1 then return false end
    end
    if AP_OPTS.story_keys == "story" then
        for _, code in ipairs(STORY_KEY_BEATS[BEAT_NAMES[idx]] or {}) do
            if count(code) < 1 then return false end
        end
    end
    return true
end

-- A lock item (junction / command / GF ability): needed only while its
-- option is on for this seed.
function lock_access(option, code)
    if not AP_OPTS[option] then return true end
    return count(code) >= 1
end

-- The chapter a story moment falls in (BEAT_START_MOMENTS).
function progress_for_moment(moment)
    local m = tonumber(moment) or 0
    local idx = 0
    for i, start in pairs(BEAT_START_MOMENTS) do
        if m >= start and i > idx then idx = i end
    end
    return idx
end

-- A check inside a keyed area: needs the door's key while story keys are on.
function key_access(code)
    if AP_OPTS.story_keys == "off" then return true end
    return count(code) >= 1
end

-- Triple Triad Rule Checks toggle and the fixed-rules option (both from slot
-- data; defaults keep everything visible).
function tt_rules_on()
    return AP_OPTS.triple_triad_rule_checks ~= false
end

function tt_abolish_on()
    return AP_OPTS.triple_triad_rules == nil or AP_OPTS.triple_triad_rules == 0
end

function hub_access(grant_idx, vehicle_code, from_idx)
    -- the ship opens the hub from beat from_idx on (0 = from the start)
    if AP_OPTS.vehicle_unlocks and count(vehicle_code) >= 1
            and beat_access(tonumber(from_idx) or 0) then return true end
    return beat_access(grant_idx)
end

-- An early-entry area: its first beat, or the ship (vehicle_unlocks); a door
-- the game gates on the story moment also needs story keys on, since only
-- then does the client lower the gate. The area's key is a separate rule on
-- each check (key_access).
function early_access(first_idx, vehicle_code, gated)
    if AP_OPTS.vehicle_unlocks and count(vehicle_code) >= 1
            and (tonumber(gated) == 0 or AP_OPTS.story_keys ~= "off") then
        return true
    end
    return beat_access(first_idx)
end
"""

AUTOTRACKING_LUA = """-- Archipelago autotracking: connect PopTracker's AP autotracker to the room.
-- (scripts/mapping.lua is already loaded by init.lua.)

CUR_INDEX = -1
AREA_KEY = nil   -- data-storage key the FF8 client publishes the area under
FIELD_KEY = nil  -- data-storage key with the field id the party stands on (-1 = world map)
HINTS_KEY = nil  -- server-managed data-storage key with the slot's hints
MOMENT_KEY = nil -- the highest story moment the FF8 client has seen
HIGHLIGHTED = {} -- section codes currently carrying a hint highlight

function updateAreaTab(area)
    local opt = Tracker:FindObjectForCode("opt_autotab")
    if opt and not opt.Active then return end
    local tab = AREA_TABS[area]
    if not tab then return end
    Tracker:UiHint("ActivateTab", "World Map")
    Tracker:UiHint("ActivateTab", tab)
end

-- Follow the player into towns: open the floor-plan tab of the place whose
-- screen the party is on, or the area's map when back on the world map.
function updatePlaceTab(field)
    local opt = Tracker:FindObjectForCode("opt_autotab")
    if opt and not opt.Active then return end
    local id = tonumber(field)
    if id == nil then return end
    id = math.floor(id)
    Tracker:UiHint("ActivateTab", "World Map")
    if id < 0 then
        Tracker:UiHint("ActivateTab", "Map")
        return
    end
    local tabs = FIELD_TABS[id]
    if not tabs then return end
    Tracker:UiHint("ActivateTab", tabs[1])
    Tracker:UiHint("ActivateTab", tabs[2])
end

-- AP hint status -> PopTracker section highlight (Highlight is nil on
-- PopTracker builds without section-highlight support; everything guards on it).
local function hintHighlight(hint)
    if hint.found then return Highlight.NONE end
    local by_status = {
        [1] = Highlight.UNSPECIFIED,   -- HINT_UNSPECIFIED
        [10] = Highlight.NO_PRIORITY,  -- HINT_NO_PRIORITY
        [20] = Highlight.AVOID,        -- HINT_AVOID
        [30] = Highlight.PRIORITY,     -- HINT_PRIORITY
    }
    return by_status[hint.status] or Highlight.UNSPECIFIED
end

function updateHints(hints)
    if not Highlight or type(hints) ~= "table" then return end
    for code in pairs(HIGHLIGHTED) do
        local o = Tracker:FindObjectForCode(code)
        if o then o.Highlight = Highlight.NONE end
    end
    HIGHLIGHTED = {}
    for _, hint in ipairs(hints) do
        -- Only hints whose location is in this world can be pinned on our maps.
        local m = hint.finding_player == Archipelago.PlayerNumber
                  and LOCATION_MAPPING[hint.location]
        if m then
            local o = Tracker:FindObjectForCode(m.section)
            if o then
                local hl = hintHighlight(hint)
                o.Highlight = hl
                if hl ~= Highlight.NONE then HIGHLIGHTED[m.section] = true end
            end
        end
    end
end

function onClear(slot_data)
    CUR_INDEX = -1
    -- 580 locations reset at once: batch so logic/UI recalculate only once.
    Tracker.BulkUpdate = true
    for _, code in ipairs(RESET_TOGGLES) do
        local o = Tracker:FindObjectForCode(code)
        if o then o.Active = false end
    end
    local p = Tracker:FindObjectForCode("progress")
    if p then p.AcquiredCount = 0 end
    for _, code in ipairs({"char_unlocks", "junction_unlocks", "command_unlocks"}) do
        local o = Tracker:FindObjectForCode(code)
        if o then o.AcquiredCount = 0 end
    end
    for _, m in pairs(LOCATION_MAPPING) do
        local o = Tracker:FindObjectForCode(m.section)
        if o then o.AvailableChestCount = o.ChestCount end
    end
    if Highlight then
        for code in pairs(HIGHLIGHTED) do
            local o = Tracker:FindObjectForCode(code)
            if o then o.Highlight = Highlight.NONE end
        end
    end
    HIGHLIGHTED = {}
    Tracker.BulkUpdate = false
    if slot_data then
        local thr = slot_data["gfs_required_for_disc3"]
        if thr then AP_OPTS.gfs_required_for_disc3 = tonumber(thr) end
        local mode = slot_data["story_gates"]
        if mode ~= nil then
            AP_OPTS.story_gates = STORY_GATE_MODES[tonumber(mode)] or tostring(mode)
        end
        local keys = slot_data["story_keys"]
        if keys ~= nil then
            AP_OPTS.story_keys = STORY_KEY_MODES[tonumber(keys)] or tostring(keys)
        end
        for _, key in ipairs({"character_locks", "junction_locks", "command_locks",
                              "ability_locks", "vehicle_unlocks", "vehicle_gates",
                              "triple_triad_rule_checks"}) do
            if slot_data[key] ~= nil then
                AP_OPTS[key] = slot_data[key] == 1 or slot_data[key] == true
            end
        end
        if slot_data["triple_triad_rules"] ~= nil then
            AP_OPTS.triple_triad_rules = tonumber(slot_data["triple_triad_rules"]) or 0
        end
        local function set_opt(code, key)
            local o = Tracker:FindObjectForCode(code)
            if o and slot_data[key] ~= nil then
                o.Active = slot_data[key] == 1 or slot_data[key] == true
            end
        end
        set_opt("opt_draw_points", "draw_point_checks")
        set_opt("opt_wdraw", "world_draw_point_checks")
        set_opt("opt_tt", "triple_triad_checks")
        set_opt("opt_boss", "optional_boss_checks")
        set_opt("opt_cards", "rare_card_checks")
        set_opt("opt_sq", "sidequest_checks")
        set_opt("opt_mags", "magazine_checks")
        set_opt("opt_stats", "stat_checks")
        set_opt("opt_abil", "gf_ability_checks")
    end
    -- Follow-the-player: the FF8 client publishes the party's map area here;
    -- subscribe and fetch the current value so the map opens on it. The hints
    -- key is server-managed and drives section highlights on the maps.
    AREA_KEY = string.format("ff8_area_%d_%d",
                             Archipelago.TeamNumber or 0,
                             Archipelago.PlayerNumber or 0)
    FIELD_KEY = string.format("ff8_field_%d_%d",
                              Archipelago.TeamNumber or 0,
                              Archipelago.PlayerNumber or 0)
    HINTS_KEY = string.format("_read_hints_%d_%d",
                              Archipelago.TeamNumber or 0,
                              Archipelago.PlayerNumber or 0)
    MOMENT_KEY = string.format("ff8_moment_%d_%d",
                               Archipelago.TeamNumber or 0,
                               Archipelago.PlayerNumber or 0)
    Archipelago:SetNotify({AREA_KEY, FIELD_KEY, HINTS_KEY, MOMENT_KEY})
    Archipelago:Get({AREA_KEY, FIELD_KEY, HINTS_KEY, MOMENT_KEY})
end

function onItem(index, item_id, item_name, player_number)
    if index <= CUR_INDEX then return end
    CUR_INDEX = index
    local code = ITEM_MAPPING[item_id]
    if not code then return end
    local o = Tracker:FindObjectForCode(code)
    if not o then return end
    if COUNTER_CODES[code] then
        -- counters (character / junction / command unlocks)
        if o.AcquiredCount < o.MaxCount then o.AcquiredCount = o.AcquiredCount + 1 end
    else
        o.Active = true
    end
    local extra = ITEM_EXTRA_CODES[item_id]
    local t = extra and Tracker:FindObjectForCode(extra)
    if t then t.Active = true end
end

function bumpProgress(n)
    local p = Tracker:FindObjectForCode("progress")
    if p and p.AcquiredCount < n then p.AcquiredCount = n end
end

function onLocation(location_id, location_name)
    local m = LOCATION_MAPPING[location_id]
    if not m then return end
    local o = Tracker:FindObjectForCode(m.section)
    if o and o.AvailableChestCount > 0 then
        o.AvailableChestCount = o.AvailableChestCount - 1
    end
    if m.progress then bumpProgress(m.progress) end
end

function onSetReply(key, value, old_value)
    if key == AREA_KEY then updateAreaTab(value) end
    if key == FIELD_KEY then updatePlaceTab(value) end
    if key == HINTS_KEY then updateHints(value) end
    if key == MOMENT_KEY and value ~= nil then bumpProgress(progress_for_moment(value)) end
end

function onRetrieved(key, value)
    if key == AREA_KEY then updateAreaTab(value) end
    if key == FIELD_KEY then updatePlaceTab(value) end
    if key == HINTS_KEY then updateHints(value) end
    if key == MOMENT_KEY and value ~= nil then bumpProgress(progress_for_moment(value)) end
end

Archipelago:AddClearHandler("clear handler", onClear)
Archipelago:AddItemHandler("item handler", onItem)
Archipelago:AddLocationHandler("location handler", onLocation)
Archipelago:AddSetReplyHandler("set reply handler", onSetReply)
Archipelago:AddRetrievedHandler("retrieved handler", onRetrieved)
"""


def place_tabs(view: str) -> list[dict]:
    """Floor-plan tabs (one per town/dungeon) that live under an area tab."""
    return [{"title": place["title"],
             "content": {"type": "map", "maps": [f"place_{key}"]}}
            for key, place in GEO.get("places", {}).items()
            if PLACE_AREA.get(key) == view]


def area_tab_content(view: str) -> dict:
    """An area tab: its map, plus nested floor-plan tabs when it has places."""
    tabs = [{"title": "Map", "content": {"type": "map", "maps": [f"area_{view}"]}}]
    tabs += place_tabs(view)
    if len(tabs) == 1:
        return tabs[0]["content"]
    return {"type": "tabbed", "tabs": tabs}


def emit_layouts() -> dict:
    rows = [
        [gf_code(g) for g in GF_ORDER[:8]],
        [gf_code(g) for g in GF_ORDER[8:]] + [gf_code(g) for g in CAMEO_GFS],
        ["magical_lamp", "solomon_ring", "progress",
         "vehicle_ragnarok",
         "char_unlocks", "junction_unlocks", "command_unlocks"],
        [LOCK_CODES[n] for n in LOCK_ICONS if not n.endswith(" Command")],
        [LOCK_CODES[n] for n in LOCK_ICONS if n.endswith(" Command")],
        list(KEY_CODES.values())[:10],
        list(KEY_CODES.values())[10:],
        ["opt_draw_points", "opt_wdraw", "opt_tt", "opt_boss", "opt_cards",
         "opt_sq", "opt_mags", "opt_stats", "opt_abil", "opt_autotab"],
    ]
    grid = {"type": "itemgrid", "item_margin": "2,2", "item_size": "32,32", "rows": rows}

    def block(block_rows):
        return {"type": "itemgrid", "item_margin": "2,2", "item_size": "32,32",
                "h_alignment": "left", "v_alignment": "top", "margin": "6,0,18,0",
                "rows": block_rows}
    # Side-by-side blocks (GFs | progress + locks | story keys + options) keep
    # the item bar three rows tall so the maps get the window's height.
    bar = {"type": "array", "orientation": "horizontal", "h_alignment": "left",
           "v_alignment": "top",
           "content": [block(rows[0:2]), block(rows[2:5]), block(rows[5:8])]}
    return {
        "layouts": {
            "ff8_item_grid": grid,
            "ff8_item_bar": bar,
            "tracker_default": {
                "type": "container",
                "background": "#10141f",
                "content": [{
                    "type": "dock",
                    "content": [
                        {"type": "group", "header": "Items", "dock": "top",
                         "content": {"type": "layout", "key": "ff8_item_bar"}},
                        {"type": "tabbed", "tabs": [
                            {"title": "World Map",
                             "content": {"type": "tabbed", "tabs": (
                                 [{"title": "Full",
                                   "content": {"type": "map", "maps": ["world"]}}]
                                 + [{"title": ff8_areas.AREAS[view],
                                     "content": area_tab_content(view)}
                                    for view in AREA_VIEWS])}},
                            {"title": "Region Board",
                             "content": {"type": "map", "maps": ["board"]}},
                            {"title": "Quests & Extras",
                             "content": {"type": "map", "maps": ["extras"]}},
                            {"title": "GF Abilities",
                             "content": {"type": "map", "maps": ["abilities"]}},
                        ]},
                    ],
                }],
            },
            "tracker_broadcast": {
                "type": "container",
                "background": "#10141f",
                "content": [{"type": "layout", "key": "ff8_item_grid"}],
            },
        }
    }


def community_pins(nodes) -> dict:
    """Community mapping data -> {node key: [map_location dicts]}.

    Markers list AP location names; nodes sharing a marker are laid out as a
    small cluster grid around the marker's coordinate (clamped to the image).
    """
    data = json.loads(COMMUNITY_DATA.read_text(encoding="utf-8"))
    id2name = {BASE_ID + d.id_offset: d.name for d in ff8_locations.LOCATION_TABLE}
    name2key = {}
    for key, node in nodes.items():
        for _sec, ap_id, _group, _acc in node["sections"]:
            name2key[id2name[ap_id]] = key

    pins: dict[tuple, list[dict]] = {}
    for tab in data["tabs"]:
        map_id, img_name, size, pitch = COMMUNITY_TABS[tab["name"]]
        with Image.open(COMMUNITY_ART / Path(tab["image"]).name) as img:
            w, h = img.size
        for mk in tab["markers"]:
            if tab["name"] == "World Map" and mk.get("label") in COMMUNITY_SKIP_MARKERS:
                continue
            keys = []
            for loc in mk["locations"]:
                key = name2key.get(loc)
                assert key, f"community mapping names unknown location: {loc!r}"
                if key not in keys:
                    keys.append(key)
            n = len(keys)
            cols = math.ceil(math.sqrt(n))
            rows = math.ceil(n / cols)
            half = size // 2 + 2
            x0 = min(max(mk["x"] - (cols - 1) * pitch / 2, half),
                     w - half - (cols - 1) * pitch)
            y0 = min(max(mk["y"] - (rows - 1) * pitch / 2, half),
                     h - half - (rows - 1) * pitch)
            for j, key in enumerate(keys):
                r, c = divmod(j, cols)
                pins.setdefault(key, []).append(
                    {"map": map_id, "x": round(x0 + c * pitch),
                     "y": round(y0 + r * pitch)})
    return pins


def community_world_places(nodes, data) -> list[dict]:
    """World-map markers -> [{label, slug, x, y, keys}] in mapping order.

    Every marker becomes a place; nodes keep marker order. Label-less markers
    (lone UFO sightings) get a place too — they just never earn a tab.
    """
    id2name = {BASE_ID + d.id_offset: d.name for d in ff8_locations.LOCATION_TABLE}
    name2key = {}
    for key, node in nodes.items():
        for _sec, ap_id, _group, _acc in node["sections"]:
            name2key[id2name[ap_id]] = key

    tab = next(t for t in data["tabs"] if t["name"] == "World Map")
    places, slugs = [], set()
    for mk in tab["markers"]:
        label = mk.get("label")
        if label in COMMUNITY_SKIP_MARKERS:
            continue
        keys = []
        for loc in mk["locations"]:
            key = name2key.get(loc)
            assert key, f"community mapping names unknown location: {loc!r}"
            if key not in keys:
                keys.append(key)
        slug = "".join(c if c.isalnum() else "_" for c in (label or "ufo").lower())
        while slug in slugs:
            slug += "_"
        slugs.add(slug)
        places.append({"label": label, "slug": slug,
                       "x": mk["x"], "y": mk["y"], "keys": keys})
    return places


def place_view(place) -> str:
    """The area view a place's tab lives under: first crop containing the
    marker, in COMMUNITY_AREA_VIEWS order (exclusive corner views first)."""
    for view, ((x0, y0, x1, y1), _scale, _sz) in COMMUNITY_AREA_VIEWS.items():
        if x0 <= place["x"] <= x1 and y0 <= place["y"] <= y1:
            return view
    raise AssertionError(
        f"community marker outside every area view: {place['label']} "
        f"({place['x']}, {place['y']})")


def place_node_label(node, place_label: str | None) -> str:
    """Short per-pin caption on a place board: the node name minus the place's
    own words ("Balamb Garden Front Gate" -> "Front Gate")."""
    name = node["name"]
    prefixes = []
    if place_label:
        base = [place_label, place_label.replace("'s", "")]
        for b in base:
            prefixes += [b + ": ", b + " "]
            first = b.split(" ", 1)[0]
            if len(first) >= 4:
                prefixes += [first + ": ", first + " "]
    prefixes.sort(key=len, reverse=True)
    for pref in prefixes:
        if name.lower().startswith(pref.lower()) and len(name) > len(pref):
            name = name[len(pref):]
            break
    name = name.replace("Magazine: ", "Mag: ")
    if not name.strip() or name == place_label:
        secs = [s[0] for s in node["sections"] if s[0] != node["name"]]
        name = secs[0] if secs else node["name"]
    return name if len(name) <= 22 else name[:21] + "…"


def draw_place_board(path: Path, place, entries, art: Image.Image) -> dict:
    """Board image for one place: labeled pin grid over a darkened zoom of the
    art around the marker. Returns {node key: (x, y)} pin coordinates."""
    n = len(entries)
    cols = 5 if n > 16 else min(4, n)
    rows = math.ceil(n / cols)
    bw = PLACE_PAD * 2 + cols * PLACE_PITCH_X
    bh = PLACE_HEADER + PLACE_PAD + rows * PLACE_PITCH_Y + PLACE_PAD // 2

    # Backdrop: art around the marker at 2x zoom, darkened for contrast.
    cw, ch = bw // 2, bh // 2
    cx0 = min(max(place["x"] - cw // 2, 0), art.width - cw)
    cy0 = min(max(place["y"] - ch // 2, 0), art.height - ch)
    back = art.crop((cx0, cy0, cx0 + cw, cy0 + ch)).convert("RGB")

    s = 2
    img = back.resize((bw * s, bh * s), Image.LANCZOS)
    img = Image.blend(img, Image.new("RGB", img.size, (13, 17, 27)), 0.78)
    d = ImageDraw.Draw(img)
    head = _font(17 * s)
    tiny = _font(9 * s)
    d.text((PLACE_PAD * s, 12 * s), place["label"] or "", font=head,
           fill="#e8ecf5", stroke_width=s, stroke_fill="#0d111b")

    coords = {}
    for j, (key, label) in enumerate(entries):
        r, c = divmod(j, cols)
        x = PLACE_PAD + c * PLACE_PITCH_X + PLACE_PITCH_X // 2
        y = PLACE_HEADER + PLACE_PAD + r * PLACE_PITCH_Y
        coords[key] = (x, y)
        w = d.textlength(label, font=tiny)
        d.text((x * s - w / 2, (y + PLACE_PIN // 2 + 4) * s), label,
               font=tiny, fill="#c7d0e2", stroke_width=s, stroke_fill="#0d111b")
    img = img.resize((bw, bh), Image.LANCZOS)
    img.save(path)
    return coords


def emit_visual_preset(nodes, order_by_region, geo_coords, extras_coords,
                       abil_coords):
    """Publishable Visual Tracker mapping preset over the generated art.

    Same tab/marker schema as the contributed community preset
    (tracker/community_map/README.md), but pinned on our own world / extras /
    abilities images, so the zip ships no SE assets and can be a release asset.
    """
    id_name = {BASE_ID + d.id_offset: d.name for d in ff8_locations.LOCATION_TABLE}

    def marker(key, xy, size):
        node = nodes[key]
        return {"x": int(xy[0]), "y": int(xy[1]), "label": node["name"],
                "locations": sorted(id_name[s[1]] for s in node["sections"]),
                "size": size}

    world_m, extras_m, abil_m = [], [], []
    for region in ALL_REGIONS:
        for key in order_by_region[region]:
            if key in abil_coords:
                abil_m.append(marker(key, abil_coords[key], 16))
            elif key in extras_coords:
                extras_m.append(marker(key, extras_coords[key], 20))
            else:
                world_m.append(marker(key, geo_coords[key], 16))

    tabs = [
        {"name": "World Map", "image": "images/world_map.png",
         "location_size": 16, "markers": world_m},
        {"name": "Extras", "image": "images/extras_map.png",
         "location_size": 20, "markers": extras_m},
        {"name": "GF Abilities", "image": "images/abilities_map.png",
         "location_size": 16, "markers": abil_m},
    ]
    with zipfile.ZipFile(VISUAL_ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("mapping.json", json.dumps(
            {"game": "Final Fantasy VIII", "tabs": tabs}, indent=1) + "\n")
        for tab in tabs:
            img = Path(tab["image"]).name
            z.write(PACK / "images" / img, tab["image"])
    print(f"  Visual Tracker preset: {VISUAL_ZIP} "
          f"({len(world_m)}/{len(extras_m)}/{len(abil_m)} markers)")


def visual_counters_tab(z: zipfile.ZipFile, data: dict) -> dict | None:
    """Generated catch-all tab for the community Visual Tracker preset.

    The SE map art has no home for pure grind counters, so any table location
    the community mapping leaves unpinned lands here, on a small generated
    board written into the zip — keeping the preset at full check coverage no
    matter how the tables or the mapping evolve.
    """
    pinned = {loc for tab in data["tabs"]
              for mk in tab["markers"] for loc in mk["locations"]}
    missing = [d.name for d in ff8_locations.LOCATION_TABLE if d.name not in pinned]
    if not missing:
        return None

    cols = 4
    rows = math.ceil(len(missing) / cols)
    w = PLACE_PAD * 2 + cols * PLACE_PITCH_X
    h = PLACE_HEADER + PLACE_PAD + rows * PLACE_PITCH_Y + PLACE_PAD
    scale = 2
    img = Image.new("RGB", (w * scale, h * scale), "#10141f")
    d = ImageDraw.Draw(img)
    d.text((PLACE_PAD * scale, 10 * scale), "Counters",
           font=_font(15 * scale), fill="#e8ecf5")
    small = _font(9 * scale)
    markers = []
    for j, name in enumerate(missing):
        r, c = divmod(j, cols)
        x = PLACE_PAD + c * PLACE_PITCH_X + PLACE_PITCH_X // 2
        y = PLACE_HEADER + PLACE_PAD + r * PLACE_PITCH_Y
        d.ellipse([(x - 12) * scale, (y - 12) * scale,
                   (x + 12) * scale, (y + 12) * scale],
                  outline="#3b4a6b", width=scale)
        tw = d.textlength(name, font=small)
        d.text((x * scale - tw / 2, (y + 15) * scale), name,
               font=small, fill="#aab4cc")
        markers.append({"x": x, "y": y, "label": name,
                        "locations": [name], "size": 20})
    img = img.resize((w, h), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    z.writestr("images/counters.png", buf.getvalue())
    return {"name": "Counters", "image": "images/counters.png",
            "location_size": 20, "markers": markers}


def emit_community_variant(nodes, order_by_region, geo_coords, board_coords,
                           abil_coords, extras_coords, view_coords):
    """Generate the local-only community-art variant pack (see COMMUNITY_DATA)."""
    if not COMMUNITY_DATA.exists():
        return
    data = json.loads(COMMUNITY_DATA.read_text(encoding="utf-8"))
    tab_images = {t["name"]: Path(t["image"]).name for t in data["tabs"]}
    missing = [p for p in tab_images.values() if not (COMMUNITY_ART / p).exists()]
    if missing:
        print(f"Community variant skipped: {COMMUNITY_ART} lacks {missing} "
              "(images are local-only; see tracker/community_map/README.md)")
        return

    pins = community_pins(nodes)
    for key, extra in layout_places(nodes).items():
        pins.setdefault(key, []).extend(extra)
    places = community_world_places(nodes, data)

    # Map-view pins: re-cluster each place's nodes as a tight grid around the
    # scaled marker inside every view whose crop contains it, in that view's
    # pixel space (the corner views claim their pins exclusively). Clustering
    # per view — instead of scaling up the full-map cluster — is what keeps
    # zoomed views from becoming walls of overlapping squares.
    assert set(COMMUNITY_AREA_VIEWS) == set(ff8_areas.AREAS), \
        "COMMUNITY_AREA_VIEWS out of sync with ff8/areas.py"
    for place in places:
        place_view(place)   # asserts every marker sits inside some view
        for view, ((x0, y0, x1, y1), scale, size) in COMMUNITY_AREA_VIEWS.items():
            if not (x0 <= place["x"] <= x1 and y0 <= place["y"] <= y1):
                continue
            vw, vh = (x1 - x0) * scale, (y1 - y0) * scale
            pitch = size + 4
            n = len(place["keys"])
            cols = math.ceil(math.sqrt(n))
            rows = math.ceil(n / cols)
            half = size // 2 + 2
            px = (place["x"] - x0) * scale
            py = (place["y"] - y0) * scale
            gx0 = min(max(px - (cols - 1) * pitch / 2, half),
                      vw - half - (cols - 1) * pitch)
            gy0 = min(max(py - (rows - 1) * pitch / 2, half),
                      vh - half - (rows - 1) * pitch)
            for j, key in enumerate(place["keys"]):
                r, c = divmod(j, cols)
                pins.setdefault(key, []).append(
                    {"map": f"cworld_{view}", "x": round(gx0 + c * pitch),
                     "y": round(gy0 + r * pitch)})
            if view in COMMUNITY_EXCLUSIVE_VIEWS:
                break

    if COMMUNITY_PACK.exists():
        shutil.rmtree(COMMUNITY_PACK)
    shutil.copytree(PACK, COMMUNITY_PACK)
    for tab_name, (map_id, img_name, size, _pitch) in COMMUNITY_TABS.items():
        shutil.copy(COMMUNITY_ART / tab_images[tab_name],
                    COMMUNITY_PACK / "images" / img_name)
    place_maps = []   # (slug, tab title, area view) for places that earn a tab
    with Image.open(COMMUNITY_ART / tab_images["World Map"]) as world_art:
        for view, ((x0, y0, x1, y1), scale, _sz) in COMMUNITY_AREA_VIEWS.items():
            crop = world_art.crop((x0, y0, x1, y1))
            if scale != 1:
                crop = crop.resize((crop.width * scale, crop.height * scale),
                                   Image.LANCZOS)
            crop.save(COMMUNITY_PACK / "images" / f"community_world_{view}.png")
        for place in places:
            if not place["label"] or len(place["keys"]) < COMMUNITY_PLACE_MIN:
                continue
            entries = [(k, place_node_label(nodes[k], place["label"]))
                       for k in place["keys"]]
            coords = draw_place_board(
                COMMUNITY_PACK / "images" / f"community_place_{place['slug']}.png",
                place, entries, world_art)
            for key, (x, y) in coords.items():
                pins.setdefault(key, []).append(
                    {"map": f"cplace_{place['slug']}", "x": x, "y": y})
            title = COMMUNITY_PLACE_TITLES.get(place["label"], place["label"])
            place_maps.append((place["slug"], title, place_view(place)))

    titles = [t for _s, t, _v in place_maps]
    reserved = {"World Map", "Full", "Map", "Cards", "Characters",
                "Region Board", "Quests & Extras", "GF Abilities",
                *ff8_areas.AREAS.values()}
    clashes = (reserved & set(titles)) | {t for t in titles if titles.count(t) > 1}
    assert not clashes, f"place tab titles collide (fix COMMUNITY_PLACE_TITLES): {clashes}"

    def patch(rel: str, fn):
        p = COMMUNITY_PACK / rel
        obj = json.loads(p.read_text(encoding="utf-8"))
        obj = fn(obj) or obj
        p.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")

    patch("maps/maps.json", lambda maps: maps + [
        {"name": map_id, "location_size": size, "location_border_thickness": 2,
         "img": f"images/{img_name}"}
        for map_id, img_name, size, _pitch in COMMUNITY_TABS.values()
    ] + [
        {"name": f"cworld_{view}", "location_size": sz,
         "location_border_thickness": 1,
         "img": f"images/community_world_{view}.png"}
        for view, (_rect, _scale, sz) in COMMUNITY_AREA_VIEWS.items()
    ] + [
        {"name": f"cplace_{slug}", "location_size": PLACE_PIN,
         "location_border_thickness": 1,
         "img": f"images/community_place_{slug}.png"}
        for slug, _title, _view in place_maps])

    def patch_manifest(mf):
        mf["name"] += " — Community Art"
        mf["package_uid"] += "_community"
    patch("manifest.json", patch_manifest)

    def patch_layouts(lay):
        # The community variant's "World Map" group IS the art map: Full plus
        # per-area crops, titled exactly like the standard pack's so the
        # follow-the-player Lua drives them unchanged. The generated stylized
        # world map stays in the standard pack; here it would just duplicate.
        tabbed = lay["layouts"]["tracker_default"]["content"][0]["content"][1]
        keep = [t for t in tabbed["tabs"]
                if t["title"] in ("Region Board", "Quests & Extras", "GF Abilities")]
        # Each area tab nests FFX-style: a "Map" tab (the art crop) plus one
        # board tab per major place inside it.
        area_tabs = []
        for view in AREA_VIEWS:
            sub = [{"title": "Map",
                    "content": {"type": "map", "maps": [f"cworld_{view}"]}}]
            sub += [{"title": title,
                     "content": {"type": "map", "maps": [f"cplace_{slug}"]}}
                    for slug, title, v in place_maps if v == view]
            sub += [t for t in place_tabs(view)
                    if t["title"] not in {x["title"] for x in sub}]
            content = (sub[0]["content"] if len(sub) == 1
                       else {"type": "tabbed", "tabs": sub})
            area_tabs.append({"title": ff8_areas.AREAS[view], "content": content})
        tabbed["tabs"] = [
            {"title": "World Map", "content": {"type": "tabbed", "tabs": (
                [{"title": "Full",
                  "content": {"type": "map", "maps": ["cworld"]}}]
                + area_tabs)}},
            {"title": "Cards", "content": {"type": "map", "maps": ["ccards"]}},
            {"title": "Characters",
             "content": {"type": "map", "maps": ["cchars"]}},
        ] + keep
    patch("layouts/tracker.json", patch_layouts)

    (COMMUNITY_PACK / "locations" / "locations.json").write_text(
        json.dumps(emit_locations(nodes, order_by_region, geo_coords,
                                  board_coords, abil_coords, extras_coords,
                                  view_coords, extra_pins=pins),
                   indent=2) + "\n", encoding="utf-8")

    COMMUNITY_ZIP.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(COMMUNITY_ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(COMMUNITY_PACK.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(COMMUNITY_PACK).as_posix())

    with zipfile.ZipFile(VISUAL_COMMUNITY_ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        for tab in data["tabs"]:
            rel = tab["image"]
            z.write(COMMUNITY_ART / Path(rel).name, rel)
        counters = visual_counters_tab(z, data)
        out = {"game": data["game"],
               "tabs": data["tabs"] + ([counters] if counters else [])}
        z.writestr("mapping.json", json.dumps(out, indent=1) + "\n")

    n_pinned = len(pins)
    print(f"Community variant written to {COMMUNITY_PACK}")
    print(f"  {n_pinned} of {len(nodes)} nodes pinned on community tabs")
    print(f"  zip: {COMMUNITY_ZIP} (local only — contains SE art, do not publish)")
    print(f"  Visual Tracker preset: {VISUAL_COMMUNITY_ZIP} (local only — "
          "copy into <Archipelago>/visual_packs/)")


def main():
    nodes, order_by_region = build_model()
    abil_coords, per_gf, ladder, abil_h = layout_abilities(nodes, order_by_region)
    nodes_by_region = {r: [k for k in order_by_region[r] if k not in abil_coords]
                       for r in ALL_REGIONS}
    board_coords, bw, bh, cells = layout_board(nodes_by_region)
    geo_coords, extras_coords, by_anchor, exact = layout_geo(nodes, order_by_region)
    view_coords = area_view_coords(geo_coords, by_anchor, exact)
    place_pins = layout_places(nodes)
    place_nodes = layout_place_nodes(nodes, by_anchor)
    clustered = clustered_keys(by_anchor)
    label_geo, label_views = aggregate_coords(by_anchor, geo_coords, view_coords)

    for sub in ("images", "items", "locations", "layouts", "maps", "scripts"):
        (PACK / sub).mkdir(parents=True, exist_ok=True)

    # --- art ---
    for i, gf in enumerate(GF_ORDER):
        make_icon(PACK / "images" / f"{gf_code(gf)}.png", GF_INITIALS[gf], GF_COLORS[i])
    for gf, (initials, color) in CAMEO_ICONS.items():
        make_icon(PACK / "images" / f"{gf_code(gf)}.png", initials, color)
    make_icon(PACK / "images" / "magical_lamp.png", "La", "#d97706")
    make_icon(PACK / "images" / "solomon_ring.png", "Ri", "#7c3aed")
    make_icon(PACK / "images" / "progress.png", "Pr", "#0d9488")
    make_icon(PACK / "images" / "vehicle_ragnarok.png", "Rg", "#b91c1c")
    for area, code in KEY_CODES.items():
        make_icon(PACK / "images" / f"{code}.png", KEY_INITIALS[area], "#a16207")
    make_icon(PACK / "images" / "char_unlocks.png", "Ch", "#9333ea")
    make_icon(PACK / "images" / "junction_unlocks.png", "Jn", "#2563eb")
    make_icon(PACK / "images" / "command_unlocks.png", "Cm", "#ca8a04")
    for name, code in LOCK_CODES.items():
        make_icon(PACK / "images" / f"{code}.png", LOCK_ICONS[name],
                  "#ca8a04" if name.endswith(" Command") else "#2563eb")
    make_icon(PACK / "images" / "draw_points.png", "DP", "#0284c7")
    make_icon(PACK / "images" / "wdraw_checks.png", "WD", "#0ea5e9")
    make_icon(PACK / "images" / "tt_checks.png", "TT", "#db2777")
    make_icon(PACK / "images" / "boss_checks.png", "OB", "#b91c1c")
    make_icon(PACK / "images" / "card_checks.png", "RC", "#9333ea")
    make_icon(PACK / "images" / "sq_checks.png", "SQ", "#65a30d")
    make_icon(PACK / "images" / "mag_checks.png", "MG", "#ca8a04")
    make_icon(PACK / "images" / "stat_checks.png", "ST", "#0891b2")
    make_icon(PACK / "images" / "abil_checks.png", "GA", "#4f46e5")
    make_icon(PACK / "images" / "autotab.png", "»", "#475569")
    draw_board(PACK / "images" / "board_map.png", cells, bw, bh)
    draw_world(PACK / "images" / "world_map.png", by_anchor, label_geo)
    draw_area_views(PACK / "images" / "world_map.png", by_anchor, label_views)
    for key, place in GEO.get("places", {}).items():
        shutil.copy(GEO_DIR / place["image"], PACK / "images" / f"place_{key}.png")
    ew, eh = draw_extras(PACK / "images" / "extras_map.png", by_anchor)
    draw_abilities(PACK / "images" / "abilities_map.png", nodes, abil_coords,
                   per_gf, ladder, abil_h)

    # --- json ---
    def dump(rel: str, data):
        (PACK / rel).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    dump("manifest.json", {
        "name": "Final Fantasy VIII (Archipelago)",
        "game_name": "Final Fantasy VIII",
        "package_uid": "ff8_archipelago",
        "package_version": PACK_VERSION,
        "platform": "pc",
        "author": "wilsonao",
        # 0.34.0 added map zoom/pan, which the full-resolution world and
        # floor-plan maps rely on
        "min_poptracker_version": "0.34.0",
        # "ap" makes PopTracker offer the Archipelago connect button for the
        # variant; without it the pack loads but can never autotrack.
        "variants": {"standard": {"display_name": "Standard",
                                  "flags": ["ap"]}},
    })
    maps = [
        {"name": "world", "location_size": WORLD_PIN_SIZE, "location_border_thickness": 3,
         "img": "images/world_map.png"},
        {"name": "board", "location_size": 18, "location_border_thickness": 2,
         "img": "images/board_map.png"},
        {"name": "extras", "location_size": 18, "location_border_thickness": 2,
         "img": "images/extras_map.png"},
        {"name": "abilities", "location_size": 16, "location_border_thickness": 2,
         "img": "images/abilities_map.png"},
    ] + [
        {"name": f"area_{view}", "location_size": view_pin_size(view),
         "location_border_thickness": 3, "img": f"images/area_{view}.png"}
        for view in AREA_VIEWS
    ] + [
        {"name": f"place_{key}", "location_size": pin_size(place["width"], place["height"]),
         "location_border_thickness": 2, "img": f"images/place_{key}.png"}
        for key, place in GEO.get("places", {}).items()
    ]
    dump("maps/maps.json", maps)
    dump("items/items.json", emit_items())
    locations = emit_locations(nodes, order_by_region, geo_coords, board_coords,
                               abil_coords, extras_coords, view_coords, place_pins,
                               aggregate=(clustered, place_nodes))
    nudge_duplicate_pins(locations, maps)
    dump("locations/locations.json", locations)
    # Universal Tracker ignores `ref` sections, so its copy keeps one pin per
    # check on the world/area maps.
    ut_locations = emit_locations(nodes, order_by_region, geo_coords, board_coords,
                                  abil_coords, extras_coords, view_coords, place_pins)
    nudge_duplicate_pins(ut_locations, maps)
    dump("layouts/tracker.json", emit_layouts())

    # --- lua ---
    (PACK / "scripts" / "init.lua").write_text(INIT_LUA, encoding="utf-8")
    (PACK / "scripts" / "logic.lua").write_text(LOGIC_LUA, encoding="utf-8")
    (PACK / "scripts" / "autotracking.lua").write_text(AUTOTRACKING_LUA, encoding="utf-8")
    (PACK / "scripts" / "mapping.lua").write_text(
        emit_mapping_lua(nodes, order_by_region), encoding="utf-8")

    # --- Universal Tracker copy inside the apworld package ---
    # Same maps/locations/images (UT ignores PopTracker access/visibility rules
    # and uses its own logic) plus the node/section -> id mapping.
    for sub in ("maps", "locations", "images"):
        (UT_DIR / sub).mkdir(parents=True, exist_ok=True)
    for old in UT_DIR.rglob("*"):
        if old.is_file():
            old.unlink()
    shutil.copy(PACK / "maps" / "maps.json", UT_DIR / "maps" / "maps.json")
    (UT_DIR / "locations" / "locations.json").write_text(
        json.dumps(ut_locations, indent=2) + "\n", encoding="utf-8")
    for img in ("world_map.png", "board_map.png", "extras_map.png", "abilities_map.png",
                *(f"area_{view}.png" for view in AREA_VIEWS),
                *(f"place_{key}.png" for key in GEO.get("places", {}))):
        shutil.copy(PACK / "images" / img, UT_DIR / "images" / img)
    (UT_DIR / "ut_name_mapping.json").write_text(
        json.dumps(emit_ut_name_mapping(nodes, order_by_region), indent=1) + "\n",
        encoding="utf-8")
    (UT_DIR / "README.md").write_text(
        "Generated by tools/gen_tracker_pack.py for Universal Tracker map pages "
        "(FF8World.tracker_world). Do not edit by hand.\n", encoding="utf-8")

    # --- zip ---
    BUILD_ZIP.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(BUILD_ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(PACK.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(PACK).as_posix())

    n_locs = len(ff8_locations.LOCATION_TABLE)
    print(f"Pack written to {PACK}")
    print(f"  {n_locs} AP locations -> {len(nodes)} map nodes")
    print(f"  {len(place_pins)} nodes pinned on {len(GEO.get('places', {}))} place sheets")
    print(f"  world map {GEO_W}x{GEO_H}px, board {bw}x{bh}px, "
          f"extras {ew}x{eh}px, abilities {ABIL_W}x{abil_h}px")
    print(f"  zip: {BUILD_ZIP}")
    print(f"  UT pages: {UT_DIR}")

    emit_visual_preset(nodes, order_by_region, geo_coords, extras_coords,
                       abil_coords)
    emit_community_variant(nodes, order_by_region, geo_coords, board_coords,
                           abil_coords, extras_coords, view_coords)


if __name__ == "__main__":
    main()
