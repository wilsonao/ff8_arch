"""Item definitions for the Final Fantasy VIII apworld."""

from dataclasses import dataclass

from BaseClasses import Item, ItemClassification

BASE_ID = 8_800_000

GAME_NAME = "Final Fantasy VIII"


class FF8Item(Item):
    game = GAME_NAME


# Junctionable GFs, in savemap record order (Quezacotl record at FF8_EN.exe+0x18FDCB9, stride 0x44).
# The list order doubles as the client's GF index.
GF_ORDER = [
    "Quezacotl", "Shiva", "Ifrit", "Siren",
    "Brothers", "Diablos", "Carbuncle", "Leviathan",
    "Pandemona", "Cerberus", "Alexander", "Doomtrain",
    "Bahamut", "Cactuar", "Tonberry", "Eden",
]


@dataclass(frozen=True)
class ItemData:
    name: str
    id_offset: int
    classification: ItemClassification
    # Client-side grant payload: ("gf", gf_index) | ("item", game_item_id, qty)
    #                          | ("gil", amount) | ("magic", spell_id, qty)
    #                          | ("bit", module_offset, mask)  [savemap flag]
    #                          | ("trap_gil", amount) | ("trap_hp", hp_left)
    #                          | ("trap_magic", qty)  [traps, one-shot]
    grant: tuple


ITEM_TABLE: list[ItemData] = []

# --- GFs: offsets 0..15 ---
for _i, _gf in enumerate(GF_ORDER):
    ITEM_TABLE.append(ItemData(f"GF {_gf}", _i, ItemClassification.progression, ("gf", _i)))

# --- Key items: offsets 100+ ---
# In-game item IDs confirmed from ff8-speedruns/ff8-memory reference/itemId.md.
MAGICAL_LAMP_GAME_ID = 168
SOLOMON_RING_GAME_ID = 167

ITEM_TABLE += [
    ItemData("Magical Lamp", 100, ItemClassification.progression, ("item", MAGICAL_LAMP_GAME_ID, 1)),
    ItemData("Solomon Ring", 101, ItemClassification.progression, ("item", SOLOMON_RING_GAME_ID, 1)),
]

# --- Filler: offsets 200+ ---
# Game item IDs from reference/itemId.md, spell IDs from reference/magicId.md.
# "magic" grants write straight into Squall's 32 magic slots (savemap char record 0)
# — junction fuel without the draw grind. Weights are relative pull odds.
_F, _U = ItemClassification.filler, ItemClassification.useful
_FILLER_SPECS: list[tuple[str, int, ItemClassification, tuple, int]] = [
    ("500 Gil",           200, _F, ("gil", 500), 6),
    ("2000 Gil",          201, _F, ("gil", 2000), 4),
    ("10000 Gil",         202, _U, ("gil", 10000), 2),
    ("Potion Pack",       203, _F, ("item", 1, 8), 4),
    ("Phoenix Down Pack", 204, _F, ("item", 7, 3), 4),
    ("Remedy Pack",       205, _F, ("item", 16, 3), 3),
    ("Elixir",            206, _U, ("item", 9, 1), 2),
    ("Hi-Potion Pack",    207, _F, ("item", 3, 6), 4),
    ("Mega-Potion Pack",  208, _U, ("item", 6, 4), 2),
    ("Mega Phoenix",      209, _U, ("item", 8, 1), 2),
    ("X-Potion Pack",     210, _F, ("item", 5, 2), 3),
    ("Tent Pack",         211, _F, ("item", 33, 3), 3),
    ("Cottage",           212, _F, ("item", 35, 1), 2),
    ("Energy Crystal",    213, _U, ("item", 68, 1), 1),
    ("Dragon Fang",       214, _F, ("item", 126, 1), 2),
    # Magic stocks (spell id, count)
    ("Cura x10",          220, _F, ("magic", 22, 10), 4),
    ("Curaga x10",        221, _U, ("magic", 23, 10), 2),
    ("Protect x10",       222, _F, ("magic", 29, 10), 3),
    ("Shell x10",         223, _F, ("magic", 30, 10), 3),
    ("Haste x10",         224, _U, ("magic", 35, 10), 2),
    ("Regen x10",         225, _F, ("magic", 26, 10), 3),
    ("Full-life x5",      226, _U, ("magic", 25, 5), 2),
    ("Aura x5",           227, _U, ("magic", 32, 5), 2),
    ("Meltdown x5",       228, _U, ("magic", 49, 5), 2),
    ("Triple x5",         229, _U, ("magic", 34, 5), 2),
    ("Ultima x3",         230, _U, ("magic", 19, 3), 1),
]

# --- Checks-only magic roster: offsets 231+ ---
# Pulled as filler only when magic_mode is checks_only (vanilla-mode weight 0
# keeps the vanilla distribution unchanged), where granted caps are the whole
# junction economy and need elemental/status coverage. Spell ids follow the
# kernel magic order; every segment is pinned by ids already in use above:
# the 1-9 elemental trios lead into Water 10 / Bio 12 before the confirmed
# Holy 14..Ultima 19 run (locations.py marquee draws); Cure 21 precedes
# confirmed Cura 22; Life 24 sits between Curaga 23 and Full-life 25; Esuna
# 27 between Regen 26 and Protect 29; the status block Slow 36..Float 48
# exactly spans confirmed Haste 35 to Meltdown 49. VERIFY in-game: the names
# of Water/Bio/Esuna and the status spells on first grant.
_CHECKS_ONLY_MAGIC_SPECS: list[tuple[str, int, ItemClassification, tuple, int]] = [
    ("Cure x20",      231, _F, ("magic", 21, 20), 3),
    ("Fira x15",      232, _F, ("magic", 2, 15), 3),
    ("Blizzara x15",  233, _F, ("magic", 5, 15), 3),
    ("Thundara x15",  234, _F, ("magic", 8, 15), 3),
    ("Water x15",     235, _F, ("magic", 10, 15), 3),
    ("Bio x10",       236, _F, ("magic", 12, 10), 2),
    ("Life x10",      237, _F, ("magic", 24, 10), 3),
    ("Esuna x10",     238, _F, ("magic", 27, 10), 2),
    ("Slow x10",      239, _F, ("magic", 36, 10), 2),
    ("Blind x10",     240, _F, ("magic", 38, 10), 2),
    ("Sleep x10",     241, _F, ("magic", 40, 10), 2),
    ("Firaga x10",    242, _U, ("magic", 3, 10), 2),
    ("Blizzaga x10",  243, _U, ("magic", 6, 10), 2),
    ("Thundaga x10",  244, _U, ("magic", 9, 10), 2),
    ("Stop x10",      245, _U, ("magic", 37, 10), 2),
    ("Holy x5",       246, _U, ("magic", 14, 5), 2),
    ("Flare x5",      247, _U, ("magic", 15, 5), 2),
    ("Quake x5",      248, _U, ("magic", 17, 5), 2),
    ("Tornado x5",    249, _U, ("magic", 18, 5), 2),
    ("Meteor x3",     250, _U, ("magic", 16, 3), 1),
    ("Death x5",      251, _U, ("magic", 45, 5), 1),
    ("Pain x5",       252, _U, ("magic", 47, 5), 1),
]

FILLER_TABLE = ([ItemData(n, o, c, g) for n, o, c, g, _w in _FILLER_SPECS]
                + [ItemData(n, o, c, g) for n, o, c, g, _w in _CHECKS_ONLY_MAGIC_SPECS])
FILLER_WEIGHTS: dict[str, int] = (
    {n: w for n, _o, _c, _g, w in _FILLER_SPECS}
    | {n: 0 for n, _o, _c, _g, _w in _CHECKS_ONLY_MAGIC_SPECS})
# checks_only pull odds: the expanded roster joins at spec weight, putting
# magic at ~57% of filler pulls — the stat economy — without drowning out
# gil and consumables entirely.
FILLER_WEIGHTS_CHECKS_ONLY: dict[str, int] = (
    {n: w for n, _o, _c, _g, w in _FILLER_SPECS}
    | {n: w for n, _o, _c, _g, w in _CHECKS_ONLY_MAGIC_SPECS})
ITEM_TABLE += FILLER_TABLE

# Precollected under checks_only so junctioning isn't starved before the
# first magic checks arrive (early enemy/point draws all yield nothing).
STARTER_MAGIC = ["Cure x20", "Fira x15", "Blizzara x15", "Thundara x15",
                 "Sleep x10"]

# --- Cameo GFs: offsets 300+ ---
# Non-junctionable summons stored as bits of the MISC2 dream byte (+0x18FE97A,
# Hyne-derived, VERIFY): bit1 Odin, bit2 Phoenix, bit3 Gilgamesh. Granting is
# additive — vanilla acquisition is not intercepted, its check is battle/edge
# based instead. Useful class: they are damage cameos, not junction power.
DREAM_FLAGS_OFFSET = 0x18FE97A
ITEM_TABLE += [
    ItemData("GF Odin", 300, ItemClassification.useful, ("bit", DREAM_FLAGS_OFFSET, 0x02)),
    ItemData("GF Phoenix", 301, ItemClassification.useful, ("bit", DREAM_FLAGS_OFFSET, 0x04)),
    ItemData("GF Gilgamesh", 302, ItemClassification.useful, ("bit", DREAM_FLAGS_OFFSET, 0x08)),
]

# --- Traps: offsets 400+ ---
# Replace a share of filler when `trap_chance` > 0. Every effect is a plain
# savemap write on a safe field tick and fully recoverable: gil comes back,
# HP heals at any save point/tent, leaked magic redraws (checks-only: the cap
# is untouched, so the spell refills to it). Nothing here can KO or strand.
_T = ItemClassification.trap
_TRAP_SPECS: list[tuple[str, int, tuple, int]] = [
    ("Gil Snatch",   400, ("trap_gil", 1500), 3),   # lose up to 1500 gil
    ("Ambush",       401, ("trap_hp", 1), 2),        # every party member drops to 1 HP
    ("Magic Leak",   402, ("trap_magic", 10), 2),    # lose 10 of your most-stocked spell
]
TRAP_TABLE = [ItemData(n, o, _T, g) for n, o, g, _w in _TRAP_SPECS]
TRAP_WEIGHTS: dict[str, int] = {n: w for n, _o, _g, w in _TRAP_SPECS}
ITEM_TABLE += TRAP_TABLE

ITEM_DATA_BY_NAME: dict[str, ItemData] = {d.name: d for d in ITEM_TABLE}
item_name_to_id: dict[str, int] = {d.name: BASE_ID + d.id_offset for d in ITEM_TABLE}

item_name_groups = {
    "GFs": {f"GF {gf}" for gf in GF_ORDER},
    "Cameo GFs": {"GF Odin", "GF Phoenix", "GF Gilgamesh"},
    "Key Items": {"Magical Lamp", "Solomon Ring"},
    "Magic": {d.name for d in FILLER_TABLE if d.grant[0] == "magic"},
    "Traps": {d.name for d in TRAP_TABLE},
}

DEFAULT_FILLER = "500 Gil"
