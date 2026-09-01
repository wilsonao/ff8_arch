"""Shared savemap-offset annotation map for the verification tools.

Builds a best-effort human name for every module-relative offset inside the
client's savemap snapshot span, from three sources:
  1. named constants in ff8/memory.py (single fields + struct spans),
  2. the location tables in ff8/locations.py (which checks watch an offset),
  3. structural knowledge (GF/char record layout, field-var block indexing).

Used by flight_recorder.py and savemap_diff.py so a raw byte diff reads as
"char[Squall]+0x09 weaponID (watched by: Weapon Remodel: Squall)" instead of
an address. Import-safe without an Archipelago environment.
"""

import importlib.util
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# --- load ff8/memory.py + ff8/locations.py without AP (same trick as
# gen_tracker_pack.py: stub BaseClasses, synthetic package) ---
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
sys.modules.setdefault("BaseClasses", _bc)

_pkg = types.ModuleType("ff8_map_src")
_pkg.__path__ = [str(ROOT / "ff8")]
sys.modules.setdefault("ff8_map_src", _pkg)


def _load(name: str):
    full = f"ff8_map_src.{name}"
    if full in sys.modules:
        return sys.modules[full]
    spec = importlib.util.spec_from_file_location(full, ROOT / "ff8" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[full] = mod
    spec.loader.exec_module(mod)
    return mod


M = _load("memory")
_locations = _load("locations")
_items = _load("items")

GF_ORDER = _items.GF_ORDER
CHAR_ORDER = ["Squall", "Zell", "Irvine", "Quistis", "Rinoa", "Selphie", "Seifer", "Edea"]

# MISC2 struct base (Hyne SaveData.h packing; anchored live at +0/+4/+18).
MISC2_BASE = 0x18FE928

# (start, size, label) — later entries win over earlier ones, so order goes
# broad spans first, precise fields last.
_SPANS: list[tuple[int, int, str]] = []


def _span(start: int, size: int, label: str):
    _SPANS.append((start, size, label))


# Broad structural spans
_span(M.SAVEMAP_BASE, M.SAVEMAP_SIZE, "savemap")
for i, gf in enumerate(GF_ORDER):
    _span(M.GF_UNLOCK_BASE - 0x11 + i * M.GF_RECORD_STRIDE, M.GF_RECORD_STRIDE,
          f"gf_record[{gf}]")
for i, ch in enumerate(CHAR_ORDER):
    _span(M.CHAR_BASE + i * M.CHAR_STRIDE, M.CHAR_STRIDE, f"char[{ch}]")
_span(M.VAR_BLOCK, 1024, "field_var")            # var N at VAR_BLOCK + N
_span(M.INVENTORY, M.INVENTORY_SLOTS * 2, "inventory")
_span(M.DRAW_POINTS, M.DRAW_POINTS_LEN, "draw_points")
_span(M.TT_CARDS, M.TT_CARDS_COMMON, "tt_card_qty")
_span(MISC2_BASE, 0x90, "misc2")

# Precise named fields
_span(MISC2_BASE, 4, "misc2.game_time (ticks; noisy)")
_span(MISC2_BASE + 4, 4, "misc2.countdown (noisy)")
_span(M.BATTLES_ESCAPED, 2, "misc2.battle_escaped")
_span(M.TONBERRY_KILLS, 4, "misc2.tomberry_vaincus (tonberries killed)")
_span(M.MAGIC_DRAWN, 8, "misc2.magic_drawn_once (bit = spell id - 1)")
_span(M.ENEMIES_SCANNED, 20, "misc2.ennemy_scanned_once")
_span(M.STEPS, 4, "misc3.steps (lifetime)")
_span(M.MONSTER_KILLS, 4, "misc3.monster_kills")
_span(M.SQUALL_EXP, 4, "char[Squall].exp (level = exp//1000 + 1)")
_span(M.GIL, 4, "gil")
_span(M.TT_RULES, 8, "tt_rules[region] (b0 Open/b1 Same/b2 Plus/b3 Random/"
                     "b4 SuddenDeath/b6 SameWall/b7 Elemental; "
                     "Balamb,Galbadia,Trabia,Centra,Dollet,FH,LunarGate,Esthar)")
_span(M.BGU_WINS, 1, "tt_bgu_victory_count (wins vs Garden players, var 478)")
_span(M.WEAPONS_UNLOCKED, 4, "misc1.unlocked_weapons (bit i = weapon id i ever made)")
_span(M.GAME_MOMENT, 2, "game_moment (field_var 256)")
_span(M.QUISTIS_LIMITS, 2, "quistis_limits (blue magic bitmask)")
_span(M.ZELL_DUELS, 2, "zell_duels (Duel moves known bitmask)")
_span(M.ANGELO_COMPLETED, 1, "angelo_completed")
_span(M.ANGELO_KNOWN, 1, "angelo_known (Pet Pals read bits)")
_span(M.DREAM_FLAGS, 1, "dream_flags (b1 Odin/b2 Phoenix/b3 Gilgamesh/b4 Angelo off/b5 Angel Wing)")
_span(M.TONBERRY_KING_FLAG, 4, "tonberry_king_flag")
_span(M.BATTLES_WON, 4, "battles_won (misc2.victory_count)")
_span(M.SEED_TEST_LEVEL, 1, "seed_test_level (misc2.testLevel)")
_span(M.TIMBER_MANIACS, 2, "timber_maniacs bitmask")
_span(M.CC_GROUP_FLAGS, 1, "cc_group bits (Jack/Club/Spade/Heart/Diamond)")
_span(M.SEAL_FLAGS, 1, "castle_seal_flags (bitmask, popcount = seals broken)")
_span(M.CC_DIALOGS2, 1, "cc_dialogs2 (bit1 Kadowaki, bit4 Joker, bit5 King)")
_span(M.QUEEN_QUEST, 1, "queen_of_cards_quest (last card created 0-5)")
_span(M.PUPU_QUEST, 1, "pupu_ufo_quest (b2-5 sightings, b6 UFO?? beaten, b7 PuPu)")
_span(M.UFO_KILLED, 4, "misc2.ufo_battle_encountered")
_span(M.VAR_BLOCK + 1398, 8, "obel_quest bits")
_span(M.AP_STATE_MAGIC_OFF, 8, "AP client save-state header (free vars 1000+)")
# Diff-session candidates from the research pass (unverified; a live diff
# session will pin them — see docs/verification-plan.md):
_span(M.VAR_BLOCK + 616, 7, "chocobo_forest state candidates (vars 616-622)")
_span(M.VAR_BLOCK + 607, 17, "shumi_village quest cluster (vars 607-623)")
_span(M.VAR_BLOCK + 387, 1, "winhill_progress (var 387)")
_span(M.VAR_BLOCK + 460, 1, "cc_random_flags1 — Joker candidate (var 460)")
_span(M.CARDS_RARE, 5, "cards_rare ownership bits")
_span(M.TT_WINS, 2, "tt_wins")
for i, gf in enumerate(GF_ORDER):
    _span(M.GF_UNLOCK_BASE + i * M.GF_RECORD_STRIDE, 1, f"gf_unlock[{gf}]")
    _span(M.gf_abilities_addr(i), M.GF_ABILITIES_LEN,
          f"gf_abilities[{gf}] (bit = ability id; default mask "
          f"{M.GF_ABILITY_DEFAULTS[i]:032x})")
for i, ch in enumerate(CHAR_ORDER):
    _span(M.CHAR_BASE + i * M.CHAR_STRIDE + M.CHAR_WEAPON_OFFSET, 1,
          f"char[{ch}].weaponID [VERIFY]")
    _span(M.CHAR_BASE + i * M.CHAR_STRIDE + M.CHAR_MAGIC_OFFSET,
          M.CHAR_MAGIC_SLOTS * 2, f"char[{ch}].magic")

# offset -> location names that read it (from trigger tables)
_WATCHERS: dict[int, list[str]] = {}
for _loc in _locations.LOCATION_TABLE:
    for _kind, _value in _loc.triggers:
        offs: list[int] = []
        if _kind in ("flag_bit", "popcount16_ge", "u8_ge", "u16_ge", "u32_ge",
                     "bits_ge"):
            offs = [_value[0]]
        elif _kind in ("popcount_ge", "bits_clear"):
            offs = list(range(_value[0], _value[0] + _value[1]))
        elif _kind == "cards_seen_range":
            offs = list(range(M.TT_CARDS + _value[0],
                              M.TT_CARDS + _value[0] + _value[1]))
        elif _kind == "tt_wins":
            offs = [M.TT_WINS]
        elif _kind == "cards_owned":
            offs = [M.TT_CARDS]
        elif _kind == "dream_flag":
            offs = [M.DREAM_FLAGS]
        elif _kind == "draw":
            offs = [M.DRAW_POINTS + _value // 4]
        elif _kind == "story":
            offs = [M.GAME_MOMENT]
        for _o in offs:
            _WATCHERS.setdefault(_o, []).append(_loc.name)


def annotate(offset: int) -> str:
    """Best (most specific) name for a module-relative savemap offset."""
    best = None
    best_size = 1 << 30
    for start, size, label in _SPANS:
        if start <= offset < start + size and size <= best_size:
            rel = offset - start
            if label == "field_var":
                best = f"field_var[{rel}]"
            elif label == "inventory":
                best = f"inventory[slot {rel // 2}].{'id' if rel % 2 == 0 else 'qty'}"
            elif label == "draw_points":
                lo = rel * 4
                best = f"draw_points[slots {lo}-{lo + 3}]"
            elif label == "tt_card_qty":
                best = f"tt_card_qty[card {rel}]"
            elif rel and size > 4:
                best = f"{label}+0x{rel:02X}"
            else:
                best = label
            best_size = size
    watchers = _WATCHERS.get(offset)
    if watchers:
        shown = ", ".join(watchers[:3]) + (" ..." if len(watchers) > 3 else "")
        best = f"{best} (watched by: {shown})"
    return best or f"+0x{offset:X}"


# Offsets that tick constantly and should be squelched by diff-based tools.
NOISY = set(range(MISC2_BASE, MISC2_BASE + 8))       # game_time + countdown
STORY_LOCATIONS = sorted(
    ((v, loc.name) for loc in _locations.LOCATION_TABLE
     for k, v in loc.triggers if k == "story"))


if __name__ == "__main__":
    for probe in (M.GIL, M.GAME_MOMENT, M.DREAM_FLAGS, M.CHAR_BASE + 9,
                  M.DRAW_POINTS + 3, M.VAR_BLOCK + 500, M.TT_CARDS + 12,
                  M.INVENTORY + 7, M.CC_GROUP_FLAGS, M.GF_UNLOCK_BASE + 0x44):
        print(f"0x{probe:X}  ->  {annotate(probe)}")
