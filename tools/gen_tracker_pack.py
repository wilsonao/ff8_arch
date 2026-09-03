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

PACK_VERSION = "0.8.1"

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
ff8_areas = _load("areas")

BASE_ID = ff8_items.BASE_ID
GF_ORDER = ff8_items.GF_ORDER

# Mirrors REGION_CHAIN in ff8/__init__.py (not imported to avoid the AP core).
# Region i is tracker-accessible at story progress >= i.
REGION_CHAIN = [
    "Balamb Prologue", "Fire Cavern", "Dollet Exam", "SeeD",
    "Timber", "Galbadia", "Disc 2", "Disc 3", "Disc 4",
]
REGION_INDEX = {r: i for i, r in enumerate(REGION_CHAIN)}
DISC3_INDEX = REGION_INDEX["Disc 3"]
MAX_PROGRESS = len(REGION_CHAIN) - 1

_table_regions = {d.region for d in ff8_locations.LOCATION_TABLE}
assert _table_regions <= set(REGION_CHAIN), f"unknown regions: {_table_regions - set(REGION_CHAIN)}"

# Story beats that mark a region cleared: checking them auto-bumps tracker
# progress to the given value (index of the newly accessible region). Other
# checks bump only to their own region's index (you were there to check it).
STORY_PROGRESS_BUMPS = {
    100: 2,  # Fire Cavern Cleared        -> Dollet Exam
    101: 3,  # Dollet Exam Completed      -> SeeD
    102: 4,  # SeeD Graduation            -> Timber
    103: 5,  # Timber: Forest Owls        -> Galbadia
    104: 6,  # Sorceress Assassination    -> Disc 2
    109: 7,  # Battle of the Gardens      -> Disc 3
    111: 8,  # Adel Defeated              -> Disc 4
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
    ["Balamb Prologue", "Fire Cavern", "Dollet Exam", "SeeD", "Timber", "Galbadia"],
    ["Disc 2", "Disc 4"],
    ["Disc 3"],
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
# Geographic world map (stylized original rendering of the FF8 world).
# Surface anchors are (x, y, label); nodes sharing an anchor spread into a
# small cluster around it. Interiors live in inset panels drawn on the ocean.
# ---------------------------------------------------------------------------

GEO_W, GEO_H = 1100, 800
CLUSTER_PITCH = 22
INSET_PITCH = 26
INSET_PAD = 12
INSET_HEADER = 24

ANCHORS: dict[str, tuple[int, int, str | None]] = {
    "balamb_town":     (572, 330, "Balamb"),
    "fire_cavern":     (622, 300, "Fire Cavern"),
    "dollet":          (345, 170, "Dollet"),
    "timber":          (390, 256, "Timber"),
    "timber_forest":   (348, 292, None),
    "tomb":            (428, 218, "Tomb"),
    "deling":          (225, 345, "Deling City"),
    "winhill":         (255, 482, "Winhill"),
    "missile_base":    (148, 420, "Missile Base"),
    "d_district":      (335, 405, "D-District"),
    "fh":              (655, 415, "FH"),
    "salt_lake":       (805, 300, "Salt Lake"),
    "esthar":          (908, 288, "Esthar"),
    "pandora_lab":     (958, 242, "Pandora Lab"),
    "memorial":        (832, 372, "Memorial"),
    "lunar_gate":      (958, 385, "Lunar Gate"),
    "tears_point":     (902, 452, "Tears Point"),
    "lunatic_pandora": (852, 482, "Lunatic Pandora"),
    "trabia":          (655, 130, "Trabia"),
    "shumi":           (472, 88, "Shumi"),
    "centra_exc":      (475, 640, "Excavation Site"),
    "centra_ruins":    (572, 606, "Centra Ruins"),
    "edea":            (652, 680, "Orphanage"),
    "white_seed":      (728, 635, "White SeeD"),
    "cactuar":         (772, 585, "Cactuar"),
    "deep_sea":        (330, 652, "Deep Sea RC"),
    # World-map draw point areas (world_draw_point_checks). Unlabeled: the
    # pins sit on open terrain; labels would clutter the continents.
    "wm_alcauld":      (585, 310, None),
    "wm_mandy":        (425, 240, None),
    "wm_lanker":       (415, 275, None),
    "wm_shenand":      (370, 310, None),
    "wm_yaulny":       (355, 360, None),
    "wm_hasberry":     (310, 155, None),
    "wm_malgo":        (390, 120, None),
    "wm_holy_glory":   (300, 120, None),
    "wm_long_horn":    (420, 135, None),
    "wm_monterosa":    (170, 320, None),
    "wm_gp_galbadia":  (250, 290, None),
    "wm_wilburn":      (285, 390, None),
    "wm_dingo":        (140, 470, None),
    "wm_lallapalooza": (200, 445, None),
    "wm_rem":          (100, 520, None),
    "wm_winhill":      (270, 505, None),
    "wm_humphrey":     (300, 545, None),
    "wm_crater":       (600, 640, None),
    "wm_nectar":       (700, 610, None),
    "wm_good_hope":    (760, 660, None),
    "wm_almaj":        (520, 615, None),
    "wm_winter":       (700, 100, None),
    "wm_hawkwind":     (500, 110, None),
    "wm_bika":         (585, 105, None),
    "wm_vienne":       (620, 155, None),
    "wm_albatross":    (740, 160, None),
    "wm_shalmal":      (880, 420, None),
    "wm_kashkabald":   (830, 540, None),
    "wm_west_coast":   (790, 350, None),
    "wm_nortes":       (810, 220, None),
    "wm_grandidi":     (900, 185, None),
    "wm_millefeuille": (795, 175, None),
    "wm_gp_esthar":    (935, 210, None),
    "wm_sollet":       (975, 170, None),
    "wm_abadan":       (985, 330, None),
    "island_heaven":   (1062, 448, "Heaven"),
    "island_hell":     (42, 320, "Hell"),
}

# World draw point node (= place) -> anchor.
WORLD_DRAW_ANCHOR = {
    "Alcauld Plains": "wm_alcauld",
    "Mandy Beach": "wm_mandy",
    "Lanker Plains": "wm_lanker",
    "Shenand Hill": "wm_shenand",
    "Yaulny Canyon": "wm_yaulny",
    "Hasberry Plains": "wm_hasberry",
    "Malgo Peninsula": "wm_malgo",
    "Holy Glory Cape": "wm_holy_glory",
    "Long Horn Island": "wm_long_horn",
    "Monterosa Plateau": "wm_monterosa",
    "Great Plains of Galbadia": "wm_gp_galbadia",
    "Wilburn Hill": "wm_wilburn",
    "Dingo Desert": "wm_dingo",
    "Lallapalooza Canyon": "wm_lallapalooza",
    "Rem Archipelago": "wm_rem",
    "Winhill Bluffs": "wm_winhill",
    "Humphrey Archipelago": "wm_humphrey",
    "Centra Crater": "wm_crater",
    "Nectar Peninsula": "wm_nectar",
    "Cape of Good Hope": "wm_good_hope",
    "Almaj Mountains": "wm_almaj",
    "Winter Island": "wm_winter",
    "Hawkwind Plains": "wm_hawkwind",
    "Bika Snowfield": "wm_bika",
    "Vienne Mountains": "wm_vienne",
    "Albatross Archipelago": "wm_albatross",
    "Shalmal Peninsula": "wm_shalmal",
    "Kashkabald Desert": "wm_kashkabald",
    "West Coast": "wm_west_coast",
    "Nortes Mountains": "wm_nortes",
    "Grandidi Forest": "wm_grandidi",
    "Millefeuille Archipelago": "wm_millefeuille",
    "Great Plains of Esthar": "wm_gp_esthar",
    "Sollet Mountains": "wm_sollet",
    "Abadan Plains": "wm_abadan",
    "Island Closest to Heaven": "island_heaven",
    "Island Closest to Hell": "island_hell",
}

# option-gated location groups -> tracker toggle code driving their visibility
GROUP_OPT = {"draw": "opt_draw_points", "world_draw": "opt_wdraw",
             "tt": "opt_tt", "boss_extra": "opt_boss",
             "cards": "opt_cards", "sidequest": "opt_sq", "magazine": "opt_mags",
             "stats": "opt_stats", "abilities": "opt_abil"}
# Pure counter/grind groups: checking one implies no story progress.
NO_PROGRESS_GROUPS = {"stats", "abilities"}
# GF ability checks live on their own tab (one column per GF), not the world map.
ABILITIES_ANCHOR = "abilities_tab"

# key -> (x, y, columns, title); height follows from the node count.
# World-map insets sit on open ocean and must not cover a continent.
INSETS: dict[str, tuple[int, int, int, str]] = {
    "balamb_garden":   (455, 188, 7, "Balamb Garden"),
    "galbadia_garden": (30, 610, 5, "Galbadia Garden"),
    "space":           (890, 30, 6, "Space / Ragnarok"),
    "ult_castle":      (830, 600, 7, "Ultimecia's Castle"),
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
    "UFO Sighting: Beach (Moai)": "timber",       # Mandy Beach
    "UFO Sighting: Plains (Cow)": "winhill",      # Winhill Bluffs
    "UFO Sighting: Tundra (Metal)": "trabia",     # Heath Peninsula
    "UFO Sighting: Desert (Pyramid)": "cactuar",  # Kashkabald Desert
    "UFO?? Shot Down": "esthar",                  # Grandidi cliffs
    "PuPu Encountered": "balamb_town",            # Balamb crater
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
_GROUP_PANEL = {"cards": "rare_cards", "sidequest": "sidequests", "stats": "stats",
                "tt": "triple_triad", "abilities": ABILITIES_ANCHOR}
for _d in ff8_locations.LOCATION_TABLE:
    if _d.group in _GROUP_PANEL:
        NODE_ANCHOR.setdefault(_d.name, _GROUP_PANEL[_d.group])

# World draw point nodes are named by place; anchor them geographically.
NODE_ANCHOR.update(WORLD_DRAW_ANCHOR)

# Per-area world-map views: crop rects (x0, y0, x1, y1) on the world image,
# one nested tab each under "World Map". Keys match ff8/areas.py AREAS (the
# client publishes the player's current area under these keys and the pack's
# autotracking activates the matching tab). Crops are upscaled by VIEW_SCALE
# so PopTracker (which never zooms past 1:1) can show them big.
VIEW_SCALE = 2
AREA_VIEWS: dict[str, tuple[int, int, int, int]] = {
    "balamb":   (450, 181, 700, 400),
    "galbadia": (10, 110, 460, 740),
    "trabia":   (410, 40, 880, 185),
    "esthar":   (590, 170, 1100, 540),
    "centra":   (280, 530, 810, 760),
    "space":    (870, 10, 1090, 160),
    "castle":   (815, 585, 1055, 800),
}
assert set(AREA_VIEWS) == set(ff8_areas.AREAS), "AREA_VIEWS out of sync with ff8/areas.py"


def area_view_coords(geo_coords: dict) -> dict[str, dict]:
    """Per-view {node key: (x, y)} for every world node inside the view's rect
    (in the upscaled crop's pixel space). A node may appear in several views;
    it must appear in at least one."""
    out = {view: {} for view in AREA_VIEWS}
    for key, (x, y) in geo_coords.items():
        hit = False
        for view, (x0, y0, x1, y1) in AREA_VIEWS.items():
            if x0 <= x <= x1 and y0 <= y <= y1:
                out[view][key] = ((x - x0) * VIEW_SCALE, (y - y0) * VIEW_SCALE)
                hit = True
        assert hit, f"world node outside every area view: {key} at ({x}, {y})"
    return out


def draw_area_views(world_png: Path):
    """Crop the rendered world map into the per-area view images."""
    world = Image.open(world_png)
    for view, (x0, y0, x1, y1) in AREA_VIEWS.items():
        crop = world.crop((x0, y0, x1, y1))
        crop = crop.resize((crop.width * VIEW_SCALE, crop.height * VIEW_SCALE),
                           Image.LANCZOS)
        crop.save(world_png.parent / f"area_{view}.png")


# Stylized continent outlines (hand-placed, chaikin-smoothed at render time).
CONTINENTS: dict[str, list[tuple[int, int]]] = {
    "galbadia": [
        (70, 190), (150, 140), (260, 150), (330, 130), (400, 160), (430, 210),
        (420, 260), (360, 270), (340, 310), (390, 350), (400, 420), (360, 460),
        (300, 450), (290, 510), (230, 540), (160, 520), (120, 470), (60, 430),
        (40, 350), (70, 280),
    ],
    "balamb": [
        (480, 325), (520, 300), (575, 292), (630, 302), (648, 330), (612, 356),
        (550, 362), (500, 352),
    ],
    "trabia": [
        (480, 150), (530, 100), (600, 70), (700, 60), (790, 80), (850, 120),
        (840, 170), (760, 190), (670, 180), (580, 190), (510, 180),
    ],
    "shumi_island": [
        (430, 95), (460, 65), (505, 70), (515, 100), (485, 120), (445, 115),
    ],
    "esthar": [
        (780, 250), (840, 200), (920, 190), (1000, 210), (1050, 260),
        (1060, 340), (1030, 420), (1000, 480), (930, 520), (860, 500),
        (820, 440), (780, 380), (770, 310),
    ],
    "centra": [
        (400, 600), (470, 560), (560, 555), (650, 580), (720, 600), (740, 640),
        (700, 690), (620, 710), (540, 730), (460, 700), (410, 660),
    ],
}


def chaikin(pts: list[tuple[float, float]], iterations: int = 2):
    for _ in range(iterations):
        out = []
        n = len(pts)
        for i in range(n):
            p, q = pts[i], pts[(i + 1) % n]
            out.append((0.75 * p[0] + 0.25 * q[0], 0.75 * p[1] + 0.25 * q[1]))
            out.append((0.25 * p[0] + 0.75 * q[0], 0.25 * p[1] + 0.75 * q[1]))
        pts = out
    return pts


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


def layout_geo(nodes, order_by_region):
    """Assign map coordinates to every node key.

    Returns (world_coords, extras_coords, by_anchor): a node is on exactly one
    of the world map or the Extras panels (ability nodes are on neither — see
    layout_abilities()).
    """
    # Collect nodes per anchor in stable region/table order.
    by_anchor: dict[str, list] = {}
    for region in REGION_CHAIN:
        for key in order_by_region[region]:
            name = nodes[key]["name"]
            anchor = NODE_ANCHOR.get(name)
            assert anchor, f"unanchored node: {name!r} — add it to NODE_ANCHOR"
            by_anchor.setdefault(anchor, []).append(key)
    unused = (set(ANCHORS) | set(INSETS) | set(EXTRAS_PANELS)) - set(by_anchor)
    assert not unused, f"anchors with no nodes: {unused}"

    by_anchor.pop(ABILITIES_ANCHOR, None)   # laid out by layout_abilities()
    coords: dict[tuple, tuple[int, int]] = {}
    extras: dict[tuple, tuple[int, int]] = {}
    for anchor, keys in by_anchor.items():
        if anchor in EXTRAS_PANELS:
            extras.update(panel_node_coords(EXTRAS_PANELS[anchor], keys))
        elif anchor in INSETS:
            coords.update(panel_node_coords(INSETS[anchor], keys))
        else:
            ax, ay, _label = ANCHORS[anchor]
            n = len(keys)
            cols = math.ceil(math.sqrt(n))
            rows = math.ceil(n / cols)
            x0 = ax - (cols - 1) * CLUSTER_PITCH / 2
            y0 = ay - (rows - 1) * CLUSTER_PITCH / 2
            for j, key in enumerate(keys):
                r, c = divmod(j, cols)
                coords[key] = (round(x0 + c * CLUSTER_PITCH), round(y0 + r * CLUSTER_PITCH))
    return coords, extras, by_anchor


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
    for region in REGION_CHAIN:
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


def draw_world(path: Path, by_anchor: dict[str, list]):
    scale = 3
    W, H = GEO_W * scale, GEO_H * scale
    img = Image.new("RGB", (W, H), "#152238")
    d = ImageDraw.Draw(img)

    def sp(pt):  # scale point
        return (pt[0] * scale, pt[1] * scale)

    # Horizon Bridge: Galbadia -> FH -> Esthar
    d.line([sp((430, 390)), sp((655, 415)), sp((775, 370))],
           fill="#54627a", width=2 * scale)

    for pts in CONTINENTS.values():
        smooth = [sp(p) for p in chaikin([(float(x), float(y)) for x, y in pts])]
        d.polygon(smooth, fill="#33465e", outline="#4d6785", width=scale)

    # Small ocean features: FH platform, research center, Cactuar Island,
    # White SeeD ship marker.
    for cx, cy, r, fill in [
        (655, 415, 11, "#3d5068"), (330, 652, 10, "#3d5068"),
        (772, 585, 12, "#4a5c45"), (728, 635, 8, "#3d5068"),
    ]:
        d.ellipse([sp((cx - r, cy - r)), sp((cx + r, cy + r))],
                  fill=fill, outline="#4d6785", width=scale)

    # Inset panels
    title_font = _font(13 * scale)
    for key, keys in by_anchor.items():
        if key not in INSETS:
            continue
        x, y, w, h, _cols = inset_geometry(key, len(keys))
        d.rounded_rectangle([sp((x, y)), sp((x + w, y + h))], radius=7 * scale,
                            fill="#1c2333", outline="#3b4a6b", width=2 * scale)
        d.text(sp((x + 8, y + 5)), INSETS[key][3], font=title_font, fill="#e8ecf5")

    # Anchor labels, below each pin cluster.
    label_font = _font(11 * scale)
    for anchor, keys in by_anchor.items():
        if anchor in INSETS or anchor in EXTRAS_PANELS:
            continue
        ax, ay, label = ANCHORS[anchor]
        if not label:
            continue
        n = len(keys)
        cols = math.ceil(math.sqrt(n))
        rows = math.ceil(n / cols)
        ly = ay + (rows - 1) * CLUSTER_PITCH / 2 + 14
        box = d.textbbox((0, 0), label, font=label_font)
        d.text((ax * scale - (box[2] - box[0]) / 2, ly * scale), label,
               font=label_font, fill="#dfe7f2",
               stroke_width=scale, stroke_fill="#152238")

    img = img.resize((GEO_W, GEO_H), Image.LANCZOS)
    img.save(path)


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
    for slot, spell, place, region, missable in ff8_locations.DRAW_POINT_TABLE:
        name = f"Draw Point: {place} ({spell})"
        draw_place[name] = (place, spell)
    # World draw locations carry "#n" dedupe suffixes; recover (place, spell)
    # by zipping with the slot-sorted table they were built from.
    for d, (slot, spell, place, region) in zip(
            ff8_locations.WORLD_DRAW_POINT_LOCATIONS,
            sorted(ff8_locations.WORLD_DRAW_POINT_TABLE)):
        draw_place[d.name] = (place, spell)

    nodes: dict[tuple[str, str], dict] = {}
    order_by_region: dict[str, list] = {r: [] for r in REGION_CHAIN}

    def get_node(region: str, node_name: str) -> dict:
        key = (region, node_name)
        if key not in nodes:
            nodes[key] = {"region": region, "name": node_name, "sections": []}
            order_by_region[region].append(key)
        return nodes[key]

    # Node-level extra access requirements (key-item gates from set_rules()).
    ACCESS = {"Magical Lamp: Diablos": ["magical_lamp"],
              "Solomon Ring: Doomtrain": ["solomon_ring"]}
    for d in ff8_locations.LOCATION_TABLE:
        if d.requires_gf is not None:
            ACCESS[d.name] = [gf_code(GF_ORDER[d.requires_gf])]

    for d in ff8_locations.LOCATION_TABLE:
        ap_id = BASE_ID + d.id_offset
        if (d.name in ff8_locations.DRAW_POINT_NAMES
                or d.name in ff8_locations.WORLD_DRAW_POINT_NAMES):
            place, spell = draw_place[d.name]
            node = get_node(d.region, place)
            sec_name = f"{spell} Draw Point"
            existing = {s[0] for s in node["sections"]}
            i = 2
            while sec_name in existing:
                sec_name = f"{spell} Draw Point #{i}"
                i += 1
            node["sections"].append((sec_name, ap_id, d.group, None))
        else:
            node = get_node(d.region, d.name)
            node["sections"].append(("Check", ap_id, d.group, ACCESS.get(d.name)))

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
                   extra_pins: dict | None = None) -> list[dict]:
    out = []
    for region in REGION_CHAIN:
        if not order_by_region[region]:
            continue
        idx = REGION_INDEX[region]
        access = ["$disc3_access"] if idx == DISC3_INDEX else [f"$at_progress|{idx}"]
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
                map_locations = [{"map": "world", "x": gx, "y": gy},
                                 {"map": "board", "x": bx, "y": by}]
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
    return out


def emit_ut_name_mapping(nodes, order_by_region) -> dict[str, int]:
    """Universal Tracker `poptracker_name_mapping`: "<node>/<section>" -> AP id
    (UT matches sections by AP location name otherwise, and ours are "Check" /
    "<spell> Draw Point")."""
    out: dict[str, int] = {}
    for region in REGION_CHAIN:
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
        # filler (gil/consumable/magic packs) is not tracked

    loc_lines = []
    for region in REGION_CHAIN:
        for key in order_by_region[region]:
            node = nodes[key]
            for sec_name, ap_id, group, _acc in node["sections"]:
                offset = ap_id - BASE_ID
                ref = f"@{region}/{node['name']}/{sec_name}"
                if group in NO_PROGRESS_GROUPS:
                    loc_lines.append(f'    [{ap_id}] = {{section = "{ref}"}},')
                    continue
                bump = STORY_PROGRESS_BUMPS.get(offset, REGION_INDEX[region])
                loc_lines.append(
                    f'    [{ap_id}] = {{section = "{ref}", progress = {bump}}},')

    toggles = ([gf_code(g) for g in GF_ORDER] + [gf_code(g) for g in CAMEO_GFS]
               + ["magical_lamp", "solomon_ring",
                  "opt_draw_points", "opt_wdraw", "opt_tt", "opt_boss",
                  "opt_cards", "opt_sq", "opt_mags",
                  "opt_stats", "opt_abil"])
    toggle_lines = ",\n    ".join(f'"{c}"' for c in toggles)
    area_lines = "\n".join(f'    {key} = "{ff8_areas.AREAS[key]}",'
                           for key in AREA_VIEWS)

    return f"""-- Generated by tools/gen_tracker_pack.py -- do not edit by hand.
-- AP item id -> tracker item code.
ITEM_MAPPING = {{
{chr(10).join(item_lines)}
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
"""


INIT_LUA = """Tracker:AddItems("items/items.json")
Tracker:AddMaps("maps/maps.json")
Tracker:AddLocations("locations/locations.json")
Tracker:AddLayouts("layouts/tracker.json")

ScriptHost:LoadScript("scripts/logic.lua")

if _G.Archipelago then
    ScriptHost:LoadScript("scripts/autotracking.lua")
end
"""

LOGIC_LUA = f"""-- Access-rule helpers. Mirrors the region gating in ff8/__init__.py:
-- a linear story chain, plus a GF-count threshold in front of Disc 3.

GF_THRESHOLD_DEFAULT = {6}
AP_GF_THRESHOLD = nil  -- set from slot_data by autotracking.lua

function at_progress(n)
    local o = Tracker:FindObjectForCode("progress")
    return o ~= nil and o.AcquiredCount >= tonumber(n)
end

function disc3_access()
    if not at_progress({DISC3_INDEX}) then
        return false
    end
    local need = AP_GF_THRESHOLD or GF_THRESHOLD_DEFAULT
    return Tracker:ProviderCountForCode("gf") >= need
end
"""

AUTOTRACKING_LUA = """-- Archipelago autotracking: connect PopTracker's AP autotracker to the room.
ScriptHost:LoadScript("scripts/mapping.lua")

CUR_INDEX = -1
AREA_KEY = nil  -- data-storage key the FF8 client publishes the area under

function updateAreaTab(area)
    local opt = Tracker:FindObjectForCode("opt_autotab")
    if opt and not opt.Active then return end
    local tab = AREA_TABS[area]
    if not tab then return end
    Tracker:UiHint("ActivateTab", "World Map")
    Tracker:UiHint("ActivateTab", tab)
end

function onClear(slot_data)
    CUR_INDEX = -1
    for _, code in ipairs(RESET_TOGGLES) do
        local o = Tracker:FindObjectForCode(code)
        if o then o.Active = false end
    end
    local p = Tracker:FindObjectForCode("progress")
    if p then p.AcquiredCount = 0 end
    for _, m in pairs(LOCATION_MAPPING) do
        local o = Tracker:FindObjectForCode(m.section)
        if o then o.AvailableChestCount = o.ChestCount end
    end
    AP_GF_THRESHOLD = nil
    if slot_data then
        local thr = slot_data["gfs_required_for_disc3"]
        if thr then AP_GF_THRESHOLD = tonumber(thr) end
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
    -- subscribe and fetch the current value so the map opens on it.
    AREA_KEY = string.format("ff8_area_%d_%d",
                             Archipelago.TeamNumber or 0,
                             Archipelago.PlayerNumber or 0)
    Archipelago:SetNotify({AREA_KEY})
    Archipelago:Get({AREA_KEY})
end

function onItem(index, item_id, item_name, player_number)
    if index <= CUR_INDEX then return end
    CUR_INDEX = index
    local code = ITEM_MAPPING[item_id]
    if not code then return end
    local o = Tracker:FindObjectForCode(code)
    if o then o.Active = true end
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
end

function onRetrieved(key, value)
    if key == AREA_KEY then updateAreaTab(value) end
end

Archipelago:AddClearHandler("clear handler", onClear)
Archipelago:AddItemHandler("item handler", onItem)
Archipelago:AddLocationHandler("location handler", onLocation)
Archipelago:AddSetReplyHandler("set reply handler", onSetReply)
Archipelago:AddRetrievedHandler("retrieved handler", onRetrieved)
"""


def emit_layouts() -> dict:
    rows = [
        [gf_code(g) for g in GF_ORDER[:8]],
        [gf_code(g) for g in GF_ORDER[8:]] + [gf_code(g) for g in CAMEO_GFS],
        ["magical_lamp", "solomon_ring", "progress",
         "opt_draw_points", "opt_wdraw", "opt_tt", "opt_boss", "opt_cards",
         "opt_sq", "opt_mags", "opt_stats", "opt_abil", "opt_autotab"],
    ]
    grid = {"type": "itemgrid", "item_margin": "2,2", "item_size": "32,32", "rows": rows}
    return {
        "layouts": {
            "ff8_item_grid": grid,
            "tracker_default": {
                "type": "container",
                "background": "#10141f",
                "content": [{
                    "type": "dock",
                    "content": [
                        {"type": "group", "header": "Items", "dock": "top",
                         "content": {"type": "layout", "key": "ff8_item_grid"}},
                        {"type": "tabbed", "tabs": [
                            {"title": "World Map",
                             "content": {"type": "tabbed", "tabs": (
                                 [{"title": "Full",
                                   "content": {"type": "map", "maps": ["world"]}}]
                                 + [{"title": ff8_areas.AREAS[view],
                                     "content": {"type": "map",
                                                 "maps": [f"area_{view}"]}}
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
        secs = [s[0] for s in node["sections"] if s[0] != "Check"]
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

    n_pinned = len(pins)
    print(f"Community variant written to {COMMUNITY_PACK}")
    print(f"  {n_pinned} of {len(nodes)} nodes pinned on community tabs")
    print(f"  zip: {COMMUNITY_ZIP} (local only — contains SE art, do not publish)")


def main():
    nodes, order_by_region = build_model()
    abil_coords, per_gf, ladder, abil_h = layout_abilities(nodes, order_by_region)
    nodes_by_region = {r: [k for k in order_by_region[r] if k not in abil_coords]
                       for r in REGION_CHAIN}
    board_coords, bw, bh, cells = layout_board(nodes_by_region)
    geo_coords, extras_coords, by_anchor = layout_geo(nodes, order_by_region)
    view_coords = area_view_coords(geo_coords)

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
    draw_world(PACK / "images" / "world_map.png", by_anchor)
    draw_area_views(PACK / "images" / "world_map.png")
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
        "author": "ff8_arch",
        "min_poptracker_version": "0.26.0",
        "variants": {"standard": {"display_name": "Standard"}},
    })
    dump("maps/maps.json", [
        {"name": "world", "location_size": 14, "location_border_thickness": 2,
         "img": "images/world_map.png"},
        {"name": "board", "location_size": 18, "location_border_thickness": 2,
         "img": "images/board_map.png"},
        {"name": "extras", "location_size": 18, "location_border_thickness": 2,
         "img": "images/extras_map.png"},
        {"name": "abilities", "location_size": 16, "location_border_thickness": 2,
         "img": "images/abilities_map.png"},
    ] + [
        {"name": f"area_{view}", "location_size": 22,
         "location_border_thickness": 2, "img": f"images/area_{view}.png"}
        for view in AREA_VIEWS
    ])
    dump("items/items.json", emit_items())
    dump("locations/locations.json",
         emit_locations(nodes, order_by_region, geo_coords, board_coords,
                        abil_coords, extras_coords, view_coords))
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
    shutil.copy(PACK / "locations" / "locations.json", UT_DIR / "locations" / "locations.json")
    for img in ("world_map.png", "board_map.png", "extras_map.png", "abilities_map.png",
                *(f"area_{view}.png" for view in AREA_VIEWS)):
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
    print(f"  world map {GEO_W}x{GEO_H}px, board {bw}x{bh}px, "
          f"extras {ew}x{eh}px, abilities {ABIL_W}x{abil_h}px")
    print(f"  zip: {BUILD_ZIP}")
    print(f"  UT pages: {UT_DIR}")

    emit_community_variant(nodes, order_by_region, geo_coords, board_coords,
                           abil_coords, extras_coords, view_coords)


if __name__ == "__main__":
    main()
