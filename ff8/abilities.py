"""GF ability data shared by items, locations, and the client.

Ability ids/AP costs/learn lists come from Hyne Data.cpp (Abilities::fillList,
apsTab, innateAbilities); bit i of a GF record's completeAbilities[16] mask
(record +20) = kernel ability id i. Split out of locations.py (2026-09-03) so
items.py can build lock items from the same tables without a circular import
(locations.py imports items.py).
"""

GF_ABILITY_NAMES: tuple[str, ...] = (
    "", "HP-J", "Str-J", "Vit-J", "Mag-J", "Spr-J", "Spd-J", "Eva-J", "Hit-J", "Luck-J",
    "Elem-Atk-J", "ST-Atk-J", "Elem-Def-J", "ST-Def-J", "Elem-Defx2", "Elem-Defx4",
    "ST-Def-Jx2", "ST-Def-Jx4", "Abilityx3", "Abilityx4", "Magic", "GF", "Draw", "Item",
    "???", "Card", "Doom", "Mad Rush", "Treatment", "Defend", "Darkside", "Recover",
    "Absorb", "Revive", "LV Down", "LV Up", "Kamikaze", "Devour", "MiniMog", "HP+20%",
    "HP+40%", "HP+80%", "Str+20%", "Str+40%", "Str+60%", "Vit+20%", "Vit+40%", "Vit+60%",
    "Mag+20%", "Mag+40%", "Mag+60%", "Spr+20%", "Spr+40%", "Spr+60%", "Spd+20%", "Spd+40%",
    "Eva+30%", "Luck+50%", "Mug", "Med Data", "Counter", "Return Damage", "Cover",
    "Initiative", "Move-HP Up", "HP Bonus", "Str Bonus", "Vit Bonus", "Mag Bonus",
    "Spr Bonus", "Auto-Protect", "Auto-Shell", "Auto-Reflect", "Auto-Haste", "Auto-Potion",
    "Expendx2-1", "Expendx3-1", "Ribbon", "Alert", "Move-Find", "Enc-Half", "Enc-None",
    "Rare Item", "SumMag+10%", "SumMag+20%", "SumMag+30%", "SumMag+40%", "GFHP+10%",
    "GFHP+20%", "GFHP+30%", "GFHP+40%", "Boost", "Haggle", "Sell-High", "Familiar",
    "Call Shop", "Junk Shop", "T Mag-RF", "I Mag-RF", "F Mag-RF", "L Mag-RF", "Time Mag-RF",
    "ST Mag-RF", "Supt Mag-RF", "Forbid Mag-RF", "Recov Med-RF", "ST Med-RF", "Ammo-RF",
    "Tool-RF", "Forbid Med-RF", "GFRecov Med-RF", "GFAbl Med-RF", "Mid Mag-RF",
    "High Mag-RF", "Med LV Up", "Card Mod",
)
GF_ABILITY_AP: tuple[int, ...] = (
    0, 50, 50, 50, 50, 50, 120, 200, 120, 200, 160, 160, 100, 100, 130, 180, 130, 180,
    150, 200, 1, 1, 1, 1, 0, 40, 60, 60, 100, 100, 100, 200, 80, 200, 100, 100, 100, 100,
    0, 60, 120, 240, 60, 120, 240, 60, 120, 240, 60, 120, 240, 60, 120, 240, 150, 200,
    150, 200, 200, 200, 200, 0, 100, 160, 200, 100, 100, 100, 100, 100, 250, 250, 250,
    250, 150, 250, 250, 0, 200, 40, 30, 100, 250, 40, 70, 140, 200, 40, 70, 140, 200, 10,
    150, 150, 150, 200, 150, 30, 30, 30, 30, 30, 60, 30, 200, 30, 30, 30, 30, 200, 30, 30,
    60, 60, 120, 80,
)
# Each GF's 22 learnable abilities (kernel; Hyne innateAbilities), GF_INDEX order.
GF_LEARN_LISTS: list[list[int]] = [
    [83, 84, 85, 87, 88, 91, 97, 112, 1, 48, 49, 10, 3, 12, 14, 25, 115, 4, 23, 20, 21, 22],
    [83, 84, 85, 87, 88, 23, 91, 98, 3, 45, 46, 51, 52, 12, 14, 2, 10, 26, 5, 20, 21, 22],
    [83, 84, 85, 87, 88, 89, 91, 99, 107, 42, 43, 10, 66, 1, 23, 12, 14, 27, 2, 20, 21, 22],
    [87, 88, 108, 83, 84, 85, 91, 100, 106, 48, 49, 11, 68, 23, 13, 16, 28, 79, 4, 20, 21, 22],
    [83, 84, 85, 87, 88, 89, 91, 39, 40, 41, 65, 2, 10, 5, 12, 23, 62, 29, 1, 20, 21, 22],
    [87, 88, 89, 101, 102, 1, 39, 40, 41, 4, 48, 49, 23, 8, 80, 81, 30, 58, 18, 20, 21, 22],
    [87, 88, 89, 105, 45, 46, 67, 1, 39, 40, 4, 11, 13, 16, 60, 72, 23, 18, 3, 20, 21, 22],
    [87, 88, 89, 83, 84, 85, 91, 103, 110, 51, 52, 69, 5, 14, 4, 10, 74, 31, 23, 20, 21, 22],
    [83, 84, 85, 87, 88, 89, 91, 6, 54, 55, 42, 43, 2, 12, 14, 10, 63, 32, 23, 20, 21, 22],
    [87, 88, 89, 6, 54, 55, 73, 5, 13, 16, 17, 11, 18, 2, 78, 4, 75, 8, 23, 20, 21, 22],
    [87, 88, 89, 83, 84, 85, 91, 59, 114, 51, 52, 113, 18, 10, 14, 15, 5, 33, 23, 20, 21, 22],
    [83, 84, 85, 86, 87, 88, 89, 90, 91, 71, 32, 30, 96, 109, 15, 17, 23, 10, 11, 20, 21, 22],
    [83, 84, 85, 86, 87, 88, 89, 90, 91, 58, 75, 70, 23, 82, 64, 44, 50, 104, 19, 20, 21, 22],
    [87, 88, 89, 23, 7, 56, 75, 9, 57, 29, 74, 63, 65, 66, 67, 68, 69, 64, 36, 20, 21, 22],
    [83, 84, 85, 87, 88, 89, 91, 74, 64, 63, 57, 23, 56, 92, 93, 94, 95, 34, 35, 20, 21, 22],
    [83, 84, 85, 86, 87, 88, 89, 90, 91, 111, 30, 27, 8, 6, 7, 57, 76, 37, 23, 20, 21, 22],
]
# Signature abilities per GF: the refines, field/party abilities and bonuses
# players actually chase (junction basics and %-stat fillers left out).
GF_SIGNATURE_ABILITIES: dict[int, list[int]] = {
    0: [25, 115, 97],            # Quezacotl: Card, Card Mod, T Mag-RF
    1: [98, 26],                 # Shiva: I Mag-RF, Doom
    2: [99, 107, 66],            # Ifrit: F Mag-RF, Ammo-RF, Str Bonus
    3: [100, 108, 79, 68],       # Siren: L Mag-RF, Tool-RF, Move-Find, Mag Bonus
    4: [65, 62],                 # Brothers: HP Bonus, Cover
    5: [80, 81, 58, 101, 102],   # Diablos: Enc-Half, Enc-None, Mug, Time Mag-RF, ST Mag-RF
    6: [105, 67, 72],            # Carbuncle: Recov Med-RF, Vit Bonus, Auto-Reflect
    7: [103, 110, 69, 74],       # Leviathan: Supt Mag-RF, GFRecov Med-RF, Spr Bonus, Auto-Potion
    8: [63, 32],                 # Pandemona: Initiative, Absorb
    9: [73, 75, 78],             # Cerberus: Auto-Haste, Expendx2-1, Alert
    10: [59, 114, 113, 33],      # Alexander: Med Data, Med LV Up, High Mag-RF, Revive
    11: [109, 71],               # Doomtrain: Forbid Med-RF, Auto-Shell
    12: [70, 82, 58],            # Bahamut: Auto-Protect, Rare Item, Mug
    13: [36, 9, 75],             # Cactuar: Kamikaze, Luck-J, Expendx2-1
    14: [92, 93, 94, 95],        # Tonberry: Haggle, Sell-High, Familiar, Call Shop
    15: [111, 76],               # Eden: GFAbl Med-RF, Expendx3-1
}

# --- Lock groups (junction_locks / command_locks options, 2026-09-03) ---
# junction_locks: one multiworld item per stat-junction ability, keyed by its
# primary ability id; the item also governs the listed upgrade abilities
# (Elem-Def-J carries Elem-Defx2/x4, ST-Def-J carries ST-Def-Jx2/x4). While the
# item is missing, the client clears these bits from every GF record — no GF
# offers the junction, so the stat cannot be powered — and restores each GF's
# DEFAULT bits when it arrives. Luck-J (id 9) is deliberately NOT here: it is
# Cactuar's signature-ability check/item (ability_locks would fight over the
# same bit), and it is the least consequential junction anyway.
JUNCTION_LOCK_GROUPS: dict[int, tuple[int, ...]] = {
    1: (1,),                 # HP-J
    2: (2,),                 # Str-J
    3: (3,),                 # Vit-J
    4: (4,),                 # Mag-J
    5: (5,),                 # Spr-J
    6: (6,),                 # Spd-J
    7: (7,),                 # Eva-J
    8: (8,),                 # Hit-J
    10: (10,),               # Elem-Atk-J
    11: (11,),               # ST-Atk-J
    12: (12, 14, 15),        # Elem-Def-J (+x2/x4 slots)
    13: (13, 16, 17),        # ST-Def-J (+x2/x4 slots)
}

# command_locks: the four basic battle commands, present in every GF's default
# mask (bits 20-23) and every learn list. While locked, the bits are cleared
# from all GF records (the command can't be equipped) and equipped command
# slots holding the id are zeroed; Attack and limit breaks always remain.
COMMAND_ABILITY_IDS: dict[str, int] = {
    "Magic": 20, "GF": 21, "Draw": 22, "Item": 23,
}


def ability_mask(ids) -> int:
    """Bitmask over completeAbilities bit ids."""
    mask = 0
    for aid in ids:
        mask |= 1 << aid
    return mask
