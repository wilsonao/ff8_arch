"""Memory map and process interface for FF8 Steam 2013 (FF8_EN.exe).

All offsets are module-relative statics (the 2013 port keeps the live savemap in static
module memory — no pointer chains). Sources: ff8-speedruns/ff8-memory (GPL-3.0),
ff8-speedruns/ff8-auto-splitter, wiki.ffrtt.ru FF8/Variables. See docs/research/ in the
repo for the full provenance report. Offsets marked VERIFY have not yet been confirmed
in-game by this project.
"""

import logging

logger = logging.getLogger("FF8Client")

PROCESS_NAME = "FF8_EN.exe"

# Near-miss executables players commonly have running instead of the supported
# one. Scanned while FF8_EN.exe can't be found, so the client's "waiting" loop
# can say what is actually wrong instead of retrying silently.
WRONG_PROCESS_HINTS = {
    "ffviii.exe": (
        "FF8 Remastered is running - Remastered is NOT supported. "
        "This world needs the Steam 2013 release (FF8_EN.exe)."),
    "ffviii_launcher.exe": (
        "The FF8 Remastered launcher is running - Remastered is NOT supported. "
        "This world needs the Steam 2013 release (FF8_EN.exe)."),
    "ff8_fr.exe": (
        "A non-English FF8 2013 executable is running (FF8_FR.exe). "
        "Only the English executable (FF8_EN.exe) is supported - "
        "switch the game's language to English in Steam."),
    "ff8_de.exe": (
        "A non-English FF8 2013 executable is running (FF8_DE.exe). "
        "Only the English executable (FF8_EN.exe) is supported - "
        "switch the game's language to English in Steam."),
    "ff8_es.exe": (
        "A non-English FF8 2013 executable is running (FF8_ES.exe). "
        "Only the English executable (FF8_EN.exe) is supported - "
        "switch the game's language to English in Steam."),
    "ff8_it.exe": (
        "A non-English FF8 2013 executable is running (FF8_IT.exe). "
        "Only the English executable (FF8_EN.exe) is supported - "
        "switch the game's language to English in Steam."),
    "ff8_launcher.exe": (
        "The FF8 2013 launcher is open but the game itself isn't running yet - "
        "press Play (the client attaches to FF8_EN.exe)."),
}


def find_wrong_process() -> str | None:
    """When FF8_EN.exe isn't running, name the near-miss the player has running
    instead (Remastered, a non-English 2013 exe, or just the launcher)."""
    import pymem.process
    try:
        names = {p.szExeFile.decode(errors="ignore").lower()
                 for p in pymem.process.list_processes()}
    except Exception:
        return None
    for name, hint in WRONG_PROCESS_HINTS.items():
        if name in names:
            return hint
    return None

# --- Core state ---
GIL = 0x18FE764                 # u32
GAME_MOMENT = 0x18FEAB8         # u16, savemap var 256 ("pro" in the autosplitter)
FIELD_ID = 0x18D2FC0            # u16, current/next field
ENGINE_STATE = 0x18E0758        # u32, 0 = field
MODULE_DISPATCH = 0x18D8FC6     # u16 mode_StateGlobal (community CT). CONFIRMED live
                                # 2026-08-28: 0=title, 2=worldmap, 3=battle,
                                # 100=victory transition (transient), 4=battle results
                                # (POST_BATTLE=1 throughout 100/4). 1=field
                                # (observed live 2026-08-31 on the new-game intro).
MODULE_BATTLE = 3
MODULE_TITLE = 0                # title screen — the game's only route to the
                                # load menu (no in-game load exists), so seeing
                                # it means any save could be loaded next
IN_MENU = 0x1976358             # u8 bool
POST_BATTLE = 0x1678CA4         # u8, in post-battle results screen

# --- Battle tracking (autosplitter names: fight1 = POST_BATTLE, fight2 = IN_MENU) ---
ENCOUNTER_ID = 0x1996DA8        # u16, current/last encounter
# Ultimecia final-battle state machine (FF8Autosplitter.asl):
ULTIMECIA_FIELD = 573           # field ID of the final battle sequence
ENEMY_HP_P2 = 0x1927D98         # i32, phase 2 HP pool
ENEMY_HP_P3 = 0x1927F38         # i32, phase 3 HP pool
ENEMY_HP_P1M = 0x1927F3C        # i32, phase 1 max-HP marker (0 -> >0 = fight started)
FINAL_BLOW = 0x1927C30          # u8?, 0 -> 1 on the killing blow in phase 3.
                                # UNRELIABLE live 2026-08-28: read 52/62 (garbage)
                                # around the real fight and the ==1 edge never
                                # appeared at 2 Hz — kept only as a fast path;
                                # the authoritative win signal is phase 3 +
                                # battle exited alive (track_goal)

# --- Inventory: 198 entries x 2 bytes (item id, quantity) ---
INVENTORY = 0x18FE79C
INVENTORY_SLOTS = 198

# --- Characters: 8 records of 0x98, savemap order Squall..Edea (README
# "Character - Party Struct"). 32 magic slots at +0x10: (spell id, qty) byte pairs.
CHAR_BASE = 0x18FE0E8
CHAR_STRIDE = 0x98
CHAR_COUNT = 8
CHAR_MAGIC_OFFSET = 0x10
CHAR_MAGIC_SLOTS = 32
CHAR_CUR_HP_OFFSET = 0x00       # u16 current HP (Hyne PERSONNAGES.current_HPs)
CHAR_MAX_HP_OFFSET = 0x02       # u16 max HP

# --- GFs: 16 records of 0x44 bytes; unlock flag byte at record start +? ---
# Quezacotl's unlock byte confirmed at 0x18FDCB9; Siren (index 3) at 0x18FDD85
# cross-checks against the autosplitter. Full record layout (HP/EXP/abilities) VERIFY.
GF_UNLOCK_BASE = 0x18FDCB9
GF_RECORD_STRIDE = 0x44
GF_COUNT = 16
GF_RECORD_BASE = GF_UNLOCK_BASE - 0x11      # 0x18FDCA8: record start (Hyne GF struct)
# GF learned-ability bitmask: Hyne GF.completeAbilities[16] at record +20,
# bit i = kernel ability id i (0..115; Hyne Abilities list order). Per-GF
# DEFAULT masks below are the pre-initialized new-game state — unanimous
# across all 273 library saves where the GF is not yet owned (save_scan,
# 2026-09-01) — so a multiworld-granted GF arrives with exactly these bits and
# "learned beyond default" is never satisfied by receipt alone.
GF_ABILITIES_OFFSET = 20
GF_ABILITIES_LEN = 16
GF_ABILITY_DEFAULTS: list[int] = [int.from_bytes(bytes.fromhex(h), "little") for h in (
    "1000f000000000000000000000000000",  # Quezacotl: Mag-J, Magic, GF, Draw, Item
    "2000f000000000000000000000000000",  # Shiva: Spr-J + commands
    "0404f000000000000000000000000000",  # Ifrit: Str-J, Elem-Atk-J + commands
    "1028f000000000000000000000000000",  # Siren: Mag-J, ST-Atk-J, ST-Def-J + commands
    "0200f000800000000000000000000000",  # Brothers: HP-J, HP+20% + commands
    "1000f400000000000000000000000000",  # Diablos: Mag-J, Abilityx3 + commands
    "0800f400000000000000000000000000",  # Carbuncle: Vit-J, Abilityx3 + commands
    "2040f000000000000000000000000000",  # Leviathan: Spr-J, Elem-Defx2 + commands
    "0414f000000000000000000000000000",  # Pandemona: Str-J, Elem-Atk-J, Elem-Def-J + commands
    "0401f400000000000000000000000000",  # Cerberus: Str-J, Hit-J, Abilityx3 + commands
    "2040f400000000000000000000000000",  # Alexander: Spr-J, Elem-Defx2, Abilityx3 + commands
    "000cf000000000000000000001000000",  # Doomtrain: Elem-Atk-J, ST-Atk-J, Junk Shop + commands
    "0000f800001004000000000000010000",  # Bahamut: Abilityx4, Str+60%, Mag+60%, Forbid Mag-RF + commands
    "0000f000000000003e00000000000000",  # Cactuar: the five stat Bonuses + commands
    "0000f0000c0000030000000000000000",  # Tonberry: LV Down/Up, Eva+30%, Luck+50% + commands
    "c001f000200000000000000000000000",  # Eden: Spd-J, Eva-J, Hit-J, Devour + commands
)]
GF_ABILITY_DEFAULT_BITS: list[int] = [m.bit_count() for m in GF_ABILITY_DEFAULTS]


def gf_abilities_addr(gf_index: int) -> int:
    """Module offset of a GF's 16-byte learned-ability mask."""
    return GF_RECORD_BASE + gf_index * GF_RECORD_STRIDE + GF_ABILITIES_OFFSET

# --- Draw point state: 2-bit fields, 4 per byte (ff8-memory README) ---
# Slot N -> byte DRAW_POINTS + N//4, bits (N%4)*2. 0=Full, 1=Half, 2=Empty,
# 3=Exhausted (never refills). Nonzero = the player has drawn it recently.
DRAW_POINTS = 0x18FEA2C
DRAW_POINTS_LEN = 0x40
DRAW_POINT_SLOTS = DRAW_POINTS_LEN * 4

# --- Battle ally slots: 3 records of 0xD0 (README "Battle - Ally Slots") ---
BATTLE_ALLIES = 0x1927B18
ALLY_STRIDE = 0xD0
ALLY_COUNT = 3
ALLY_CUR_HP = 0x10              # u16
ALLY_MAX_HP = 0x14              # u16

# --- Triple Triad (README "Triple Triad - Stats", CONFIRMED rows) ---
TT_WINS = 0x18FEFAC             # u16 total card wins (Hyne TTCARDS.tt_victory_count)
# CC Group quest bitmask offsets live in locations.py next to their checks.

# --- Hyne-derived savemap offsets (live MAIN base 0x18FDCA8, cross-anchored via
# persos/items/gil/game-moment/tt-rules/CC-byte/tt-wins; see docs/research).
# Live-save verification 2026-08-27 confirmed QUISTIS_LIMITS, ANGELO_KNOWN,
# TIMBER_MANIACS, and CARDS_RARE exactly. The MISC2 internals (DREAM_FLAGS,
# TONBERRY_KING_FLAG, BATTLES_WON, SEED_TEST_LEVEL, UFO_KILLED) were then
# confirmed OFFLINE 2026-08-31 by decoding 273 library saves with
# tools/save_scan.py (save MAIN == live savemap image; see that tool's docstring).
QUISTIS_LIMITS = 0x18FE76C      # u16 bitmask, blue magics learned (LIMITB+0) CONFIRMED
ZELL_DUELS = 0x18FE76E          # u16 bitmask, Duel moves known (LIMITB.zell, LIMITB+2).
                                # Bit order = Hyne ZellLBs list: 0 Punch Rush, 1 Booya,
                                # 2 Heel Drop, 3 Mach Kick, 4 Dolphin Blow, 5 Meteor
                                # Strike, 6 Burning Rave, 7 Meteor Barret, 8 Different
                                # Beat, 9 My Final Heaven. CONFIRMED offline 2026-08-31
                                # across 273 library saves: innate mask 0x004F set in
                                # every save, no bits past bit 9, and each learned bit
                                # (4/5/7/8/9) appears only in saves that own the matching
                                # Combat King issue (184/185/186/187/188) — reading the
                                # magazine sets the bit, exactly like Angelo's tricks.
ANGELO_KNOWN = 0x18FE773        # u8, Pet Pals issues read (LIMITB+7) CONFIRMED;
                                # bit order Rush..Wishing Star, innate bits 0/4 never set
ANGELO_COMPLETED = 0x18FE772    # u8, tricks fully learned (LIMITB+6); unused, for research
# MISC2.dream (MISC2+82). Bits per Hyne SaveData.h, CONFIRMED offline 2026-08-31
# against 273 library saves: bit 1 Odin, bit 2 Phoenix, bit 3 Gilgamesh
# (Gilgamesh CLEARS Odin — the two bits never coexist), bit 4 "Angelo disabled"
# (set while Rinoa is comatose, Esthar..Lunar Base), bit 5 "Angel Wing enabled"
# (Rinoa's sorceress limit, from the Ragnarok onward). Bits 4/5 are story-driven
# and must never be clobbered: the client only ORs its cameo bits in.
DREAM_FLAGS = 0x18FE97A
DREAM_ODIN = 0x02
DREAM_PHOENIX = 0x04
DREAM_GILGAMESH = 0x08
DREAM_ANGELO_DISABLED = 0x10
DREAM_ANGEL_WING = 0x20
TONBERRY_KING_FLAG = 0x18FE944  # u32 tomberry_sr_vaincu, 0 -> 1 on kill (MISC2+28).
                                # CONFIRMED offline 2026-08-31: =1 in exactly the 52
                                # legit saves that own GF Tonberry (and >=20 kills in
                                # misc2+24 tomberry_vaincus); 0 everywhere else.
TIMBER_MANIACS = 0x18FEAE8      # u16 bitmask of issues collected (FIELD+48) CONFIRMED
                                # bit -> location map from Hyne ItemEditor.cpp
                                # (bit0 Balamb Hotel .. bit13 White SeeD Ship),
                                # library-validated 2026-09-02; bits 14/15 unused.
CHOCOBO_FORESTS = 0x18FEC20     # vars 616-622: seven forest quest bytes; 0x80 =
                                # solved (library-settled 2026-09-02, values only
                                # {0,02,20,40,80}). Var->forest identity UNKNOWN —
                                # solved-count ladder only until one live diff.
CARDS_RARE = 0x18FEFA6          # 5 bytes, bit per rare card 77..109 (TTCARDS+110) CONFIRMED

# MISC2 struct base = 0x18FE928 (packed layout from Hyne SaveData.h). Interior
# anchors observed live or in the ff8-memory README: game_time (+0) is the
# README's confirmed IGT row, countdown (+4) its timer row, battle_escaped (+18)
# its 0x18FE93A row — so the struct's packing holds in live memory, unlike MISC3.
MISC2_BASE = 0x18FE928
BATTLES_WON = 0x18FE934         # u32 victory_count (MISC2+12), battles won total.
                                # Offline 2026-08-31: equals MISC3.victory_count (var 20)
                                # in 270/273 saves (off by 1-4 in the rest), plausible
                                # 0..4157 range -> consistent; live +1 edge still unseen.
BATTLES_ESCAPED = 0x18FE93A     # u16 battle_escaped (MISC2+18); also the ff8-memory
                                # README's confirmed row for this address. Offline
                                # 2026-08-31: 0..180 across 273 saves, growing by disc.
TONBERRY_KILLS = 0x18FE940      # u32 tomberry_vaincus (MISC2+24), Tonberries killed.
                                # Offline 2026-08-31: 0 everywhere except Tonberry-quest
                                # saves (20/21/23) — the King spawns at 20.
MAGIC_DRAWN = 0x18FE95C         # magic_drawn_once[8] (MISC2+52): bit (spell_id - 1) set
                                # the first time that magic is obtained (draw points
                                # count: all 20 library saves that drew the FH Ultima
                                # point carry Ultima's bit). AP grants write inventory
                                # slots directly and never touch this — the drawn-magic
                                # ladder can't be self-fired by multiworld magic filler.
                                # CONFIRMED offline 2026-08-31: Fire (bit 0) set in
                                # 262/273 saves, Apocalypse (bit 19) only on final-battle
                                # saves, no bits >= 56 anywhere.
MAGIC_DRAWN_LEN = 7             # spell ids 1..56 -> bits 0..55: seven full bytes
ENEMIES_SCANNED = 0x18FE964     # ennemy_scanned_once[20] (MISC2+60): bit per enemy
                                # scan-page ever viewed. Offline 2026-08-31: popcount
                                # 0..134 across 273 saves, monotone with progress in
                                # each series. VERIFY live (which action sets a bit).
ENEMIES_SCANNED_LEN = 20
SEED_TEST_LEVEL = 0x18FE98B     # u8 testLevel (MISC2+99), SeeD written tests passed.
                                # Offline 2026-08-31: 0..30 across 273 saves, 30 on
                                # every kitchen-sink save -> consistent.

# Triple Triad card inventory (Hyne TTCARDS struct). Base = CARDS_RARE - 110;
# pinned live by two already-confirmed interior fields: cards_rare (+110) and
# tt_victory_count (+116 == TT_WINS). cards[77] at +0: one byte per common card,
# low 7 bits = quantity currently held, bit 7 = "obtained at least once" (Hyne's
# TTriadEditor "exists" flag). CONFIRMED offline 2026-08-31: in 273 saves bit 7
# is a strict superset of qty>0 (0 violations); card-refining runs show 60+
# bit-7 cards with <12 held. The unique-card ladder counts bit 7 so refining
# cards into items (core FF8 play) can't stall a collection check.
TT_CARDS = 0x18FEF38
TT_CARD_SEEN = 0x80
TT_CARDS_COMMON = 77
CARDS_RARE_COUNT = 33

# Triple Triad rules per region (FIELD.tt_rules[8], vars 272-279; the
# ff8-memory README's confirmed "TT rules per region" row). One bitmask per
# region, order per Hyne TTriadEditor: 0 Balamb, 1 Galbadia, 2 Trabia,
# 3 Centra, 4 Dollet, 5 FH, 6 Lunar Gate, 7 Esthar. Bits (same source):
# 0 Open, 1 Same, 2 Plus, 3 Random, 4 Sudden Death, 5 (Retry), 6 Same Wall,
# 7 Elemental. Virgin values are unanimous across all 19 early library saves
# (moment <= 50): 01/02/0C/0E/88/90/DF/C0 — so "virgin bit now clear" is a
# clean abolition signal (spreading only ever ADDS bits). Abolition evidence
# across 273 saves: Dollet Random cleared in 60, Trabia 54, Centra 29,
# Lunar Gate 15.
TT_RULES = 0x18FEAC8
TT_RULES_REGIONS = 8
TT_RULE_RANDOM = 0x08
# Wins against Balamb Garden players (FIELD.tt_bgu_victory_count, var 478) —
# the counter the CC Group questline paces itself on. Offline 2026-08-31:
# bimodal across the library — 0 on non-card saves, 30..129 on every save
# with any CC-member bit set.
BGU_WINS = 0x18FEB96

# Character records (savemap PERSONNAGES, order Squall/Zell/Irvine/Quistis/
# Rinoa/Selphie/Seifer/Edea): weaponID byte at +0x09, between the live-anchored
# HP (+0) / EXP (+4) and magic (+0x10) fields. Kernel weapon ids, grouped per
# character (Hyne Data.cpp): Squall 0-6, Zell 7-10, Irvine 11-14, Quistis 15-18,
# Rinoa 19-23, Selphie 24-27, Seifer 28, Laguna/Kiros/Ward 30-32. CONFIRMED
# offline 2026-08-31: every one of 273 library saves reads inside those ranges
# (tools/save_scan.py check).
CHAR_WEAPON_OFFSET = 0x09
# Character EXP u32 at record +4 (Hyne PERSONNAGES.exp). Level is flat 1000
# EXP per level: level = exp // 1000 + 1 (Hyne PersoEditor sets exp =
# (level-1)*1000; every legit maxed library save sits at exactly 99000 =
# level 100). The save-header "level" byte is NOT this — it tracks the party
# average (a maxed Squall coexists with header levels 58-61), so level checks
# read the character record, not the header.
CHAR_EXP_OFFSET = 0x04
SQUALL_EXP = CHAR_BASE + CHAR_EXP_OFFSET
# MISC1.unlocked_weapons (Hyne SaveData.h, misc1+4): u32 bitmask, bit i set once
# kernel weapon id i has been remodeled/equipped at any point. Monotonic (bits
# survive downgrades), base weapons always set, every equipped id's bit set,
# saves without a single Weapons Monthly still carry bits for every tier they
# passed through -> "weapon ever made", not "recipe known". Confirmed across
# 273 library saves 2026-08-31; the remodel checks read this, not weaponID.
WEAPONS_UNLOCKED = 0x18FE750

# Savemap field-variable block (vars 0..1023); GAME_MOMENT == VAR_BLOCK + 256.
# Vars 0..255 are the engine's MISC3 struct (Hyne SaveData.h) — packing anchored
# by seedExp (+16 == the ff8-memory README's confirmed "SeeD test points"
# 0x18FE9C8 row) and last_field_id (+84 == its "previous map ID" 0x18FEA0C row).
VAR_BLOCK = 0x18FE9B8
STEPS = 0x18FE9BC               # u32 MISC3.steps (var 4), lifetime step counter.
                                # Offline 2026-08-31: 3.7k on a fresh Balamb save up to
                                # 8.8M on kitchen-sink saves, monotone with playtime.
SEED_EXP = 0x18FE9C8            # u16 MISC3.seedExp (var 16) — SeeD rank points; rank =
                                # exp // 100, 0..31 with 31 = rank A (Hyne MiscEditor).
                                # The ff8-memory README's confirmed "SeeD test points"
                                # row. NON-MONOTONIC: decays every 3rd payslip / on bad
                                # conduct — rank checks rely on AP's once-sent latch, so
                                # they fire on the highest rank SEEN while connected.
                                # Offline 2026-09-01 (273 saves): graduation (moment 17)
                                # awards ~500 (one save 430); battles regain it (500->
                                # 546->552 on a testLevel=0 run); decay floor 138; legit
                                # ceiling exactly 3100 (=A); 5 cheated saves read 4095.
MONSTER_KILLS = 0x18FE9FC       # u32 MISC3.monster_kills (var 68), total enemies felled.
                                # Offline 2026-08-31: >= per-character kills[8] sum in
                                # all 273 saves, ~1.8x battles won -> consistent.

# CC Group membership bits (Jack/Club/Spade/Heart/Diamond = bits 0,1,2,3,4;
# live-verified 2026-08-27). Checks referencing it live in locations.py.
CC_GROUP_FLAGS = 0x18FEB95

# Ultimecia Castle seals (the autosplitter's `seal` byte; IDA var 334
# `UltimeciaSeals`). u8 BITMASK, one bit per broken seal — NOT a count.
# Confirmed offline 2026-08-31 across the save library: 0x00 on castle-entry
# saves, 0x21 on speedrun saves that break exactly two seals, 0xF7/0xEB on
# partial clears, 0xFF on all-seals saves. Seals broken = popcount.
SEAL_FLAGS = 0x18FEB06

# CC Group rank byte 2 (Hyne FIELD.tt_players_bgu_dialogs2, var 475):
# bit 1 = Kadowaki rank, bit 5 = King. VERIFY live.
CC_DIALOGS2 = 0x18FEB93
# Queen of Cards "last created card" 0-5 (FIELD.tt_cardqueen_quest, var 300).
QUEEN_QUEST = 0x18FEAE4
# PuPu/UFO quest byte (WORLDMAP.koyok_quest, varblock+1397): bits 2-5 the four
# sightings, bit 6 UFO?? beaten, bit 7 PuPu concluded. VERIFY live.
PUPU_QUEST = 0x18FEF2D
# UFO?? kill flag bit 0 (MISC2.ufo_battle_encountered, +32). VERIFY live.
UFO_KILLED = 0x18FE948

# MISC2 struct (Hyne SaveData.h) base = 0x18FE928, anchored two independent
# ways: UFO_KILLED above == MISC2+32, and MISC1 base 0x18FE74C
# (WEAPONS_UNLOCKED-4) + MISC1(32) + LIMITB(16) + ITEMS(428) == 0x18FE928.
# module/location are what the save preview header shows ("B-Garden-
# Cafeteria" etc.); the engine refreshes them on field/worldmap transitions.
SAVE_MODULE = 0x18FE998         # u16 MISC2.module: 1=field, 2=worldmap, 3=battle
CURRENT_LOCATION = 0x18FE99A    # u16 MISC2.location: location-name id 0..250
                                # (Hyne Locations::fillList order; ff8/areas.py
                                # groups these into tracker map areas)

# --- AP client persistent state, embedded in the savemap ---
# Field vars 753-1023 are verified free (FF8ModdingWiki IDA + JSM scan of all
# 882 field scripts: referenced nowhere, zero in real saves) and sit inside
# the save file's checksummed span — so bytes written here persist through the
# game's own save/load. The client stores its per-save delivery state at vars
# 1000+: reloading an older save (or starting a new game) then re-grants
# exactly the items that save has not yet received, replacing the old
# "consumables lost on reload" limitation.
AP_STATE_MAGIC_OFF = 0x18FE9B8 + 1000   # u16 magic "AP" (0x4150)
AP_STATE_MAGIC = 0x4150
AP_STATE_FINGERPRINT_OFF = 0x18FE9B8 + 1002  # u32 seed+slot fingerprint
AP_STATE_APPLIED_OFF = 0x18FE9B8 + 1006      # u16 items applied to this save

# --- Savemap snapshot span: one read covers every savemap-resident offset the
# watcher consumes (GF records through the TTCARDS tail). Battle-module and
# engine-state addresses (BATTLE_ALLIES, ENCOUNTER_ID, IN_MENU, ...) sit far
# outside and stay individual reads.
SAVEMAP_BASE = 0x18FDCA8
SAVEMAP_END = 0x18FEFB0        # exclusive; past TT_WINS (0x18FEFAC + 2)
SAVEMAP_SIZE = SAVEMAP_END - SAVEMAP_BASE


class SavemapSnapshot:
    """One tick's savemap state, parsed out of a single read_bytes so every
    trigger evaluates against the same instant — no torn reads between the
    dozens of fields the watcher consults. Read-only; writes go through
    FF8Interface directly."""

    def __init__(self, buf: bytes):
        self.buf = buf
        self._item_counts: dict[int, int] | None = None
        self._draw_states: list[int] | None = None
        self._unique_cards: int | None = None

    # -- primitives (module-relative offsets, same address space as FF8Interface) --
    def read_u8(self, offset: int) -> int:
        return self.buf[offset - SAVEMAP_BASE]

    def read_u16(self, offset: int) -> int:
        i = offset - SAVEMAP_BASE
        return int.from_bytes(self.buf[i:i + 2], "little")

    def read_u32(self, offset: int) -> int:
        i = offset - SAVEMAP_BASE
        return int.from_bytes(self.buf[i:i + 4], "little")

    def read_bytes(self, offset: int, size: int) -> bytes:
        i = offset - SAVEMAP_BASE
        return self.buf[i:i + size]

    # -- derived views --
    def game_moment(self) -> int:
        return self.read_u16(GAME_MOMENT)

    def gf_unlocked(self, gf_index: int) -> bool:
        return self.read_u8(GF_UNLOCK_BASE + gf_index * GF_RECORD_STRIDE) != 0

    def count_item(self, item_id: int) -> int:
        if self._item_counts is None:
            raw = self.read_bytes(INVENTORY, INVENTORY_SLOTS * 2)
            counts: dict[int, int] = {}
            for slot in range(INVENTORY_SLOTS):
                iid, qty = raw[slot * 2], raw[slot * 2 + 1]
                if iid and qty:
                    counts[iid] = counts.get(iid, 0) + qty
            self._item_counts = counts
        return self._item_counts.get(item_id, 0)

    def draw_states(self) -> list[int]:
        if self._draw_states is None:
            raw = self.read_bytes(DRAW_POINTS, DRAW_POINTS_LEN)
            self._draw_states = [(b >> shift) & 0b11
                                 for b in raw for shift in (0, 2, 4, 6)]
        return self._draw_states

    def unique_cards_owned(self) -> int:
        if self._unique_cards is None:
            raw = self.read_bytes(TT_CARDS, 115)
            commons = sum(1 for b in raw[:TT_CARDS_COMMON] if b & TT_CARD_SEEN)
            rare_bytes = raw[110:115]
            rares = sum(b.bit_count() for b in rare_bytes[:4]) + (rare_bytes[4] & 0x01)
            self._unique_cards = commons + rares
        return self._unique_cards

    def char_weapon(self, char_index: int) -> int:
        return self.read_u8(CHAR_BASE + char_index * CHAR_STRIDE + CHAR_WEAPON_OFFSET)

    def gf_abilities(self, gf_index: int) -> int:
        """A GF's learned-ability bitmask as a 128-bit int (bit = ability id)."""
        return int.from_bytes(self.read_bytes(gf_abilities_addr(gf_index),
                                              GF_ABILITIES_LEN), "little")

    def gf_abilities_learned(self, gf_index: int) -> int:
        """Abilities learned beyond the GF's new-game default set (Amnesia
        Greens can push a mask below default, hence the clamp)."""
        return max(0, self.gf_abilities(gf_index).bit_count()
                   - GF_ABILITY_DEFAULT_BITS[gf_index])

    def gf_abilities_learned_total(self) -> int:
        return sum(self.gf_abilities_learned(i) for i in range(GF_COUNT))

    def magic_totals(self) -> dict[int, int]:
        """Total stock per spell id across all 8 character records. Party-
        global on purpose: the junction Switch menu moves whole magic
        inventories between characters, so a per-character ledger would
        misread a swap as a draw."""
        totals: dict[int, int] = {}
        for char in range(CHAR_COUNT):
            raw = self.read_bytes(CHAR_BASE + char * CHAR_STRIDE + CHAR_MAGIC_OFFSET,
                                  CHAR_MAGIC_SLOTS * 2)
            for slot in range(CHAR_MAGIC_SLOTS):
                sid, qty = raw[slot * 2], raw[slot * 2 + 1]
                if sid and qty:
                    totals[sid] = totals.get(sid, 0) + qty
        return totals


class FF8Interface:
    """Thin pymem wrapper. All addresses module-relative; attach() resolves the base."""

    def __init__(self):
        self.pm = None
        self.base = 0
        # User-facing message when FF8_EN.exe was FOUND but couldn't be opened
        # (antivirus / permissions). None while absent or attached.
        self.last_attach_error: str | None = None

    @property
    def attached(self) -> bool:
        return self.pm is not None

    def attach(self) -> bool:
        import pymem
        import pymem.exception
        try:
            self.pm = pymem.Pymem(PROCESS_NAME)
            self.base = self.pm.base_address
            self.last_attach_error = None
            logger.info(f"Attached to {PROCESS_NAME} (base 0x{self.base:X})")
            return True
        except pymem.exception.ProcessNotFound:
            self.pm = None
            self.last_attach_error = None
            return False
        except Exception as e:
            self.pm = None
            self.last_attach_error = (
                f"Found {PROCESS_NAME} but couldn't attach ({type(e).__name__}). "
                "Antivirus may be blocking memory access; running the Archipelago "
                "Launcher as administrator is the usual fix.")
            return False

    def detach(self) -> None:
        self.pm = None
        self.base = 0

    # -- primitives --
    def read_u8(self, offset: int) -> int:
        return self.pm.read_uchar(self.base + offset)

    def read_u16(self, offset: int) -> int:
        return self.pm.read_ushort(self.base + offset)

    def read_u32(self, offset: int) -> int:
        return self.pm.read_uint(self.base + offset)

    def read_bytes(self, offset: int, size: int) -> bytes:
        return self.pm.read_bytes(self.base + offset, size)

    def write_u8(self, offset: int, value: int) -> None:
        self.pm.write_uchar(self.base + offset, value & 0xFF)

    def write_u16(self, offset: int, value: int) -> None:
        self.pm.write_ushort(self.base + offset, value & 0xFFFF)

    def write_u32(self, offset: int, value: int) -> None:
        self.pm.write_uint(self.base + offset, value & 0xFFFFFFFF)

    def write_bytes(self, offset: int, data: bytes) -> None:
        self.pm.write_bytes(self.base + offset, data, len(data))

    # -- game state --
    def game_moment(self) -> int:
        return self.read_u16(GAME_MOMENT)

    def field_id(self) -> int:
        return self.read_u16(FIELD_ID)

    def location_id(self) -> int:
        return self.read_u16(CURRENT_LOCATION)

    def gil(self) -> int:
        return self.read_u32(GIL)

    def in_battle(self) -> bool:
        """True during real combat (module 3) or the victory/results phase
        (POST_BATTLE pulse — also what the self-test's fake battles write).
        POST_BATTLE alone is NOT combat: it stays 0 the whole real fight
        (confirmed live 2026-08-28)."""
        return (self.read_u16(MODULE_DISPATCH) == MODULE_BATTLE
                or self.read_u8(POST_BATTLE) != 0)

    def battle_results(self) -> bool:
        """True while the victory/results flag is up (real win: from the
        victory transition through the rewards screen; never on a wipe)."""
        return self.read_u8(POST_BATTLE) != 0

    def encounter_id(self) -> int:
        return self.read_u16(ENCOUNTER_ID)

    def is_safe(self) -> bool:
        """True when it's safe to read savemap state and write rewards: not in a
        menu/battle (the two flags the autosplitter gates on) and past the title
        screen. ENGINE_STATE is deliberately not consulted — observed value 6 while
        standing on a normal field screen (2026-08-26), so "0 = field" does not hold
        as a gate."""
        return (self.read_u8(IN_MENU) == 0
                and self.read_u8(POST_BATTLE) == 0
                and self.read_u16(MODULE_DISPATCH) != MODULE_BATTLE
                and self.game_moment() > 0)

    def snapshot(self) -> SavemapSnapshot:
        """Read the whole savemap span in one call (~4.9 KB)."""
        return SavemapSnapshot(self.read_bytes(SAVEMAP_BASE, SAVEMAP_SIZE))

    # -- GFs --
    def gf_unlocked(self, gf_index: int) -> bool:
        return self.read_u8(GF_UNLOCK_BASE + gf_index * GF_RECORD_STRIDE) != 0

    def gf_flags_all(self) -> list[bool]:
        """All 16 unlock flags in one read (re-assertion path)."""
        span = GF_RECORD_STRIDE * (GF_COUNT - 1) + 1
        raw = self.read_bytes(GF_UNLOCK_BASE, span)
        return [raw[i * GF_RECORD_STRIDE] != 0 for i in range(GF_COUNT)]

    def set_gf_unlocked(self, gf_index: int, unlocked: bool) -> None:
        # Confirmed in-game 2026-08-26: the unlock byte alone is sufficient — records
        # are pre-initialized at new game (sane level/HP, default junction abilities,
        # summonable in battle). No record template needed.
        self.write_u8(GF_UNLOCK_BASE + gf_index * GF_RECORD_STRIDE, 1 if unlocked else 0)

    # -- inventory --
    def read_inventory(self) -> list[tuple[int, int]]:
        raw = self.read_bytes(INVENTORY, INVENTORY_SLOTS * 2)
        return [(raw[i * 2], raw[i * 2 + 1]) for i in range(INVENTORY_SLOTS)]

    def count_item(self, item_id: int) -> int:
        return sum(qty for iid, qty in self.read_inventory() if iid == item_id)

    def add_item(self, item_id: int, qty: int) -> bool:
        inv = self.read_inventory()
        for slot, (iid, have) in enumerate(inv):
            if iid == item_id and have > 0:
                self.write_bytes(INVENTORY + slot * 2, bytes([item_id, min(have + qty, 100)]))
                return True
        for slot, (iid, have) in enumerate(inv):
            if iid == 0 or have == 0:
                self.write_bytes(INVENTORY + slot * 2, bytes([item_id, min(qty, 100)]))
                return True
        logger.warning(f"Inventory full; could not grant item {item_id} x{qty}")
        return False

    def remove_item(self, item_id: int, qty: int = 1) -> None:
        """Remove up to qty copies (one vanilla handout), leaving other copies —
        e.g. an AP-granted duplicate — untouched."""
        for slot, (iid, have) in enumerate(self.read_inventory()):
            if iid == item_id and have > 0 and qty > 0:
                take = min(have, qty)
                left = have - take
                qty -= take
                new = bytes([item_id, left]) if left > 0 else bytes([0, 0])
                self.write_bytes(INVENTORY + slot * 2, new)

    def add_gil(self, amount: int) -> None:
        self.write_u32(GIL, min(self.gil() + amount, 99_999_999))

    # -- traps (one-shot, field-only, recoverable) --
    def take_gil(self, amount: int) -> int:
        cur = self.gil()
        take = min(cur, amount)
        self.write_u32(GIL, cur - take)
        return take

    def ambush_party(self, hp_left: int = 1) -> int:
        """Drop every living character to hp_left HP; returns how many."""
        hit = 0
        for char_index in range(CHAR_COUNT):
            rec = CHAR_BASE + char_index * CHAR_STRIDE
            cur, mx = self.read_u16(rec + CHAR_CUR_HP_OFFSET), self.read_u16(rec + CHAR_MAX_HP_OFFSET)
            if mx > 0 and cur > hp_left:
                self.write_u16(rec + CHAR_CUR_HP_OFFSET, hp_left)
                hit += 1
        return hit

    def leak_magic(self, qty: int) -> tuple[int, int] | None:
        """Remove up to qty of the party's most-stocked spell; (spell, taken)."""
        totals = self.snapshot().magic_totals()
        if not totals:
            return None
        sid = max(totals, key=totals.get)
        take = min(qty, totals[sid])
        self.remove_magic(sid, take)
        return sid, take

    # -- savemap bit flags --
    def set_bits(self, offset: int, mask: int) -> None:
        self.write_u8(offset, self.read_u8(offset) | mask)

    # -- magic --
    def add_magic(self, spell_id: int, qty: int) -> bool:
        """Stock spells into the party's magic inventories: top up existing
        stacks (cap 100 each), else the first empty slot — Squall first, then
        the other characters (the checks-only roster's 33 spell kinds can
        outgrow one character's 32 slots). Returns False if any of the stock
        found no room (all 8 characters full)."""
        for char_index in range(CHAR_COUNT):
            base = CHAR_BASE + char_index * CHAR_STRIDE + CHAR_MAGIC_OFFSET
            raw = self.read_bytes(base, CHAR_MAGIC_SLOTS * 2)
            for top_up in (True, False):
                for slot in range(CHAR_MAGIC_SLOTS):
                    if qty <= 0:
                        return True
                    sid, have = raw[slot * 2], raw[slot * 2 + 1]
                    if top_up:
                        if sid == spell_id and 0 < have < 100:
                            take = min(qty, 100 - have)
                            self.write_bytes(base + slot * 2,
                                             bytes([spell_id, have + take]))
                            qty -= take
                    elif sid == 0 or have == 0:
                        take = min(qty, 100)
                        self.write_bytes(base + slot * 2, bytes([spell_id, take]))
                        raw = raw[:slot * 2] + bytes([spell_id, take]) + raw[slot * 2 + 2:]
                        qty -= take
        return qty <= 0

    def remove_magic(self, spell_id: int, qty: int) -> None:
        """Remove up to qty of a spell across every character (checks-only
        enforcement), clearing a stack to (0, 0) when it empties — the same
        state the game leaves when the last junctioned copy is cast."""
        for char_index in range(CHAR_COUNT):
            base = CHAR_BASE + char_index * CHAR_STRIDE + CHAR_MAGIC_OFFSET
            raw = self.read_bytes(base, CHAR_MAGIC_SLOTS * 2)
            for slot in range(CHAR_MAGIC_SLOTS):
                if qty <= 0:
                    return
                sid, have = raw[slot * 2], raw[slot * 2 + 1]
                if sid == spell_id and have > 0:
                    take = min(have, qty)
                    qty -= take
                    left = have - take
                    new = bytes([spell_id, left]) if left > 0 else bytes([0, 0])
                    self.write_bytes(base + slot * 2, new)

    def unique_cards_owned(self) -> int:
        """Number of distinct Triple Triad cards ever obtained: commons with the
        bit-7 "seen" flag plus set rare-ownership bits (33 bits over 5 bytes)."""
        raw = self.read_bytes(TT_CARDS, 115)
        commons = sum(1 for b in raw[:TT_CARDS_COMMON] if b & TT_CARD_SEEN)
        rare_bytes = raw[110:115]
        rares = sum(b.bit_count() for b in rare_bytes[:4]) + (rare_bytes[4] & 0x01)
        return commons + rares

    def char_weapon(self, char_index: int) -> int:
        return self.read_u8(CHAR_BASE + char_index * CHAR_STRIDE + CHAR_WEAPON_OFFSET)

    def gf_abilities(self, gf_index: int) -> int:
        """A GF's learned-ability bitmask as a 128-bit int (bit = ability id)."""
        return int.from_bytes(self.read_bytes(gf_abilities_addr(gf_index),
                                              GF_ABILITIES_LEN), "little")

    def gf_abilities_learned(self, gf_index: int) -> int:
        """Abilities learned beyond the GF's new-game default set (Amnesia
        Greens can push a mask below default, hence the clamp)."""
        return max(0, self.gf_abilities(gf_index).bit_count()
                   - GF_ABILITY_DEFAULT_BITS[gf_index])

    def gf_abilities_learned_total(self) -> int:
        return sum(self.gf_abilities_learned(i) for i in range(GF_COUNT))

    # -- draw points --
    def read_draw_states(self) -> list[int]:
        """All 2-bit draw point states, indexed by slot (0=Full/never drawn)."""
        raw = self.read_bytes(DRAW_POINTS, DRAW_POINTS_LEN)
        return [(b >> shift) & 0b11 for b in raw for shift in (0, 2, 4, 6)]

    # -- battle party (DeathLink) --
    def ally_hps(self) -> list[tuple[int, int]]:
        """(current, max) HP per battle ally slot; max == 0 means slot empty.
        Battle-module memory — only meaningful while in_battle()."""
        out = []
        for i in range(ALLY_COUNT):
            rec = BATTLE_ALLIES + i * ALLY_STRIDE
            out.append((self.read_u16(rec + ALLY_CUR_HP), self.read_u16(rec + ALLY_MAX_HP)))
        return out

    def kill_party(self) -> None:
        """Zero every occupied ally slot's HP (DeathLink receive). VERIFY: assumed
        the battle engine notices externally-zeroed HP and runs its KO/game-over
        logic on the next tick."""
        for i in range(ALLY_COUNT):
            rec = BATTLE_ALLIES + i * ALLY_STRIDE
            if self.read_u16(rec + ALLY_MAX_HP) > 0:
                self.write_u16(rec + ALLY_CUR_HP, 0)
