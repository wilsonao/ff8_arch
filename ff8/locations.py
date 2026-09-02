"""Location (check) definitions for the Final Fantasy VIII apworld.

Each location carries one or more detection triggers, consumed by the bundled client
(client.py); a location fires when ANY trigger is satisfied:

  ("story", N)   -> game-moment counter (savemap var 256) reaches N.
  ("boss", E)    -> battle against encounter ID E ends in victory (fight-flag 1->0
                    transition, the autosplitter's pattern). Non-missable even when
                    AP granted the reward GF beforehand.
  ("gf_flag", G) -> GF G's unlock flag has a rising edge not caused by the client
                    (the vanilla game granted it).
  ("item", I)    -> in-game item I appears in the inventory (vanilla handout); the
                    client removes it and sends the check.
  ("item_gone", I) -> in-game item I's count decreases without the client removing
                    it (the player used it, e.g. the Solomon Ring).
  ("draw", N)    -> draw point slot N leaves the Full state (2-bit state at
                    +0x18FEA2C + N//4, bits (N%4)*2: 0=Full, 1=Half, 2=Empty,
                    3=Exhausted; ff8-memory README "Field - Draw Points").
  ("tt_wins", N) -> Triple Triad total-wins counter (u16 at +0x18FEFAC) reaches N.
  ("flag_bit", (OFF, MASK)) -> byte at module offset OFF has MASK bits set
                    (CC Group quest, rare cards, blue magic, Angelo tricks).
  ("popcount16_ge", (OFF, N)) -> u16 at OFF has at least N bits set
                    (Timber Maniacs collection ladder; bit-order agnostic).
  ("byteflag_ge", (OFF, LEN, MASK, N)) -> at least N of the LEN bytes from OFF
                    have all MASK bits set (chocobo-forests solved ladder:
                    seven quest vars, 0x80 = solved, order-agnostic).
  ("dream_flag", MASK) -> a MISC2 dream byte bit in MASK rises without the
                    client having set it (vanilla cameo-GF acquisition; mirrors
                    gf_flag). Evaluated per bit, so Odin's mask can include
                    Gilgamesh (who replaces Odin and clears his bit).
  ("item_own", I) -> the inventory holds >= 1 of game item I. Unlike "item",
                    the item is NOT removed: used for magazines the player must
                    keep (Combat King / Pet Pals teach limits when read). A
                    later sale or trade doesn't matter — the check stays sent.
  ("u8_ge", (OFF, N)) / ("u16_ge", (OFF, N)) / ("u32_ge", (OFF, N)) ->
                    unsigned int at module offset OFF reaches N (battles-won,
                    SeeD tests, escapes, steps, kills, Squall's EXP).
  ("bits_ge", (OFF, MASK, N)) -> popcount(u32 at OFF & MASK) >= N (castle-seal
                    bitmask ladder, weapon remodels via misc1.unlocked_weapons).
  ("popcount_ge", (OFF, LEN, N)) -> total set bits in the LEN bytes at OFF
                    reaches N (magics-drawn and enemies-scanned ladders;
                    bit-order agnostic).
  ("bits_clear", (OFF, LEN, MASK)) -> every one of the LEN bytes at OFF has
                    all MASK bits clear (Triple Triad rule abolition: the
                    virgin rule bytes carry the bit, so clear = abolished).
                    Guarded by game moment >= 20 so a hypothetical
                    pre-init zeroed savemap can never false-fire it.
  ("cards_seen_range", (START, COUNT, N)) -> at least N of the COUNT common-
                    card bytes from TTCARDS+START carry the bit-7 "obtained
                    once" flag (card-level set collections; quantity-proof).
  ("cards_owned", N) -> distinct Triple Triad cards ever obtained reaches N
                    (commons with the bit-7 "seen" flag + set rare bits).

State-based triggers (story/draw/tt_wins/flag_bit/popcount16_ge/item_own/
u8_ge/u16_ge/u32_ge/bits_ge/popcount_ge/bits_clear/cards_seen_range/
cards_owned) auto-catch-up after offline play; edge-based
ones (boss/gf_flag/item/item_gone/dream_flag) only fire while the client is
watching — dream_flag additionally catches up on connect when the bit is set
and the multiworld never granted it.

`gf` names the GF index to revoke after the check fires if that GF wasn't received
from the multiworld (vanilla-reward suppression).

Sources: encounter IDs from ff8-speedruns/ff8-memory reference/encounterId.md;
story moments from reference/storyId.md + FF8Autosplitter.asl.
"""

from dataclasses import dataclass

from BaseClasses import Location

from .items import BASE_ID, GAME_NAME


class FF8Location(Location):
    game = GAME_NAME


@dataclass(frozen=True)
class LocationData:
    name: str
    id_offset: int
    region: str
    triggers: tuple
    gf: int | None = None
    missable: bool = False  # one-window (or pure-grind) location -> excluded from progression fill
    group: str = "core"     # option gate: core | draw | tt | boss_extra | cards | sidequest | magazine | stats | abilities
    requires_gf: int | None = None  # logic: needs the "GF <name>" item (GF ability checks)


GF_INDEX = {name: i for i, name in enumerate([
    "Quezacotl", "Shiva", "Ifrit", "Siren",
    "Brothers", "Diablos", "Carbuncle", "Leviathan",
    "Pandemona", "Cerberus", "Alexander", "Doomtrain",
    "Bahamut", "Cactuar", "Tonberry", "Eden",
])}

# Boss encounter IDs (reference/encounterId.md)
ENC_GEROGERO = 104          # Fake President -> Gerogero (President's Car)
ENC_SEIFER_LP = 795         # Seifer 3rd (Lunatic Pandora)
ENC_ODIN = 317              # Odin (Centra Ruins throne room; timer battle, no escape)
ENC_OMEGA = 462             # Omega Weapon (Castle Chapel)
ENC_UFO_SIGHTINGS = {       # the four UFO sightings end on their own; any battle
    "Beach (Moai)": 745,    # end counts, which is exactly "you found the sighting"
    "Plains (Cow)": 746,
    "Tundra (Metal)": 747,
    "Desert (Pyramid)": 748,
}
ENC_UFO_FIGHT = 749         # UFO?? (Cliff) — the shoot-down fight
ENC_PUPU = 750              # PuPu (elixir quest; ends win or mercy, either fires)
# Ultimecia Castle bosses. Sphinxaur is listed in the reference under the
# spelling "Sphynxaur" (363, Castle Hall) — appended last so the established
# 260-266 offsets stay stable; the fight morphs into Sphinxara mid-encounter,
# so one encounter ID covers both forms.
ENC_CASTLE_BOSSES = {
    "Krysta": 372, "Tri-Point": 377, "Catoblepas": 410, "Trauma": 431,
    "Gargantua": 436, "Red Giant": 441, "Tiamat": 483, "Sphinxaur": 363,
}
# Ragnarok Propagators (all eight are mandatory story kills; the reference
# labels the red pair 85/86 apart from the purple/green/yellow 814-819 block)
ENC_PROPAGATORS = {
    "Red Propagator (Cargo Bay)": 85,
    "Red Propagator (Cargo Bay Door)": 86,
    "Purple Propagator": 814,
    "Green Propagator": 815,
    "Yellow Propagator": 816,
    "Purple Propagator (Cargo)": 817,
    "Green Propagator (Cargo)": 818,
    "Yellow Propagator (Cargo)": 819,
}
ENC_IFRIT = 94
ENC_ELVORET = 29            # Biggs -> Wedge -> Elvoret (Dollet tower; Siren draw)
ENC_BROTHERS = 190          # Brothers (Tomb sarcophagus)
ENC_DIABLOS = 811
ENC_IGUIONS = 147           # 2 Iguion (Carbuncle draw)
ENC_NORG = 63               # NORG (Leviathan draw)
ENC_FUJIN_RAIJIN_BALAMB = 84  # Raijin + Fujin (Balamb hotel; Pandemona draw)
ENC_CERBERUS = 118
ENC_SEIFER_EDEA_2 = 120     # Seifer + Edea (Auditorium; Alexander draw)
ENC_BAHAMUT = 326
ENC_ULTIMA_WEAPON = 354     # Eden draw
ENC_JUMBO_CACTUAR = 712


LOCATION_TABLE: list[LocationData] = [
    # --- GF acquisition points: offsets 0..15 (offset == GF index) ---
    # Every GF location keeps its gf_flag trigger (vanilla grant seen directly) and,
    # where the acquisition is a battle, a boss trigger so the check still fires when
    # the multiworld already delivered that GF. The two study panels use a story
    # fallback (moment 30 = Fire Cavern done, by which the game has forced both).
    LocationData("Study Panel: Quezacotl", 0, "Balamb Prologue",
                 (("gf_flag", 0), ("story", 30)), gf=0),
    LocationData("Study Panel: Shiva", 1, "Balamb Prologue",
                 (("gf_flag", 1), ("story", 30)), gf=1),
    LocationData("Fire Cavern: Ifrit", 2, "Fire Cavern",
                 (("gf_flag", 2), ("boss", ENC_IFRIT)), gf=2),
    LocationData("Dollet Comm Tower: Siren", 3, "Dollet Exam",
                 (("gf_flag", 3), ("boss", ENC_ELVORET)), gf=3),
    LocationData("Tomb of the Unknown King: Brothers", 4, "Galbadia",
                 (("gf_flag", 4), ("boss", ENC_BROTHERS)), gf=4),
    LocationData("Magical Lamp: Diablos", 5, "Timber",
                 (("gf_flag", 5), ("boss", ENC_DIABLOS)), gf=5),
    LocationData("Deling Sewers: Carbuncle", 6, "Galbadia",
                 (("gf_flag", 6), ("boss", ENC_IGUIONS)), gf=6),
    LocationData("Balamb Garden MD Level: Leviathan", 7, "Disc 2",
                 (("gf_flag", 7), ("boss", ENC_NORG)), gf=7),
    LocationData("Balamb Town: Pandemona", 8, "Disc 2",
                 (("gf_flag", 8), ("boss", ENC_FUJIN_RAIJIN_BALAMB)), gf=8),
    LocationData("Galbadia Garden: Cerberus", 9, "Disc 2",
                 (("gf_flag", 9), ("boss", ENC_CERBERUS)), gf=9),
    LocationData("Galbadia Garden: Alexander", 10, "Disc 2",
                 (("gf_flag", 10), ("boss", ENC_SEIFER_EDEA_2)), gf=10),
    # Doomtrain: granted by using the Solomon Ring (no battle). gf_flag covers the
    # vanilla path; item_gone (ring count decreasing = the player used it) covers
    # the case where AP delivered Doomtrain first, so the use is still visible.
    # Remaining gap: ring used offline while Doomtrain was already AP-granted.
    LocationData("Solomon Ring: Doomtrain", 11, "Disc 3",
                 (("gf_flag", 11), ("item_gone", 167)), gf=11),
    LocationData("Deep Sea Research Center: Bahamut", 12, "Disc 3",
                 (("gf_flag", 12), ("boss", ENC_BAHAMUT)), gf=12),
    LocationData("Cactuar Island: Jumbo Cactuar", 13, "Disc 3",
                 (("gf_flag", 13), ("boss", ENC_JUMBO_CACTUAR)), gf=13),
    # Tonberry King has no distinct encounter ID (regular Tonberries are 236-238 and
    # escapable). Backup trigger: the savemap's tomberry_sr_vaincu counter goes
    # 0 -> 1 on the kill (Hyne MISC2+28, VERIFY) — closes the AP-granted-first gap.
    LocationData("Centra Ruins: Tonberry King", 14, "Disc 3",
                 (("gf_flag", 14), ("flag_bit", (0x18FE944, 0x01))), gf=14),
    LocationData("Ultima Weapon: Eden", 15, "Disc 3",
                 (("gf_flag", 15), ("boss", ENC_ULTIMA_WEAPON)), gf=15),

    # --- Story/boss beats: offsets 100+ ---
    LocationData("Fire Cavern Cleared", 100, "Fire Cavern", (("story", 30),)),
    LocationData("Dollet Exam Completed", 101, "Dollet Exam", (("story", 135),)),
    LocationData("SeeD Graduation", 102, "SeeD", (("story", 150),)),
    LocationData("Timber: Forest Owls Mission", 103, "Timber", (("story", 290),)),
    LocationData("Timber: Fake President Unmasked", 113, "Timber", (("boss", ENC_GEROGERO),)),
    LocationData("Deling City: Sorceress Assassination", 104, "Galbadia", (("story", 392),)),
    LocationData("Lunatic Pandora: Seifer Defeated", 114, "Disc 3", (("boss", ENC_SEIFER_LP),)),
    LocationData("D-District Prison Escape", 105, "Disc 2", (("story", 450),)),
    LocationData("Missile Base Mission", 106, "Disc 2", (("story", 482),)),
    # story 620 is an approximate offline-catch-up fallback (storyId.md: fight starts
    # in the 600-612 window); the boss trigger is the primary signal.
    # story 612 = post-NORG infirmary scene (storyId.md verbatim; pro stays 610
    # through the whole fight, 612 is the first post-fight value).
    LocationData("NORG Defeated", 107, "Disc 2", (("boss", ENC_NORG), ("story", 612))),
    # story 760 = fade-out after the post-Fujin/Raijin hotel conversation —
    # state-based catch-up fallback for the encounter edge (storyId.md).
    LocationData("Balamb Liberated", 108, "Disc 2",
                 (("boss", ENC_FUJIN_RAIJIN_BALAMB), ("story", 760))),
    LocationData("Battle of the Gardens", 109, "Disc 2", (("story", 901),)),
    LocationData("Esthar: Lunar Base Launch", 110, "Disc 3", (("story", 2502),)),
    LocationData("Lunatic Pandora: Adel Defeated", 111, "Disc 3", (("story", 3860),)),
    LocationData("Ultimecia's Castle Entered", 112, "Disc 4", (("story", 4020),)),

    # --- Laguna dream completions: offsets 120-124 ---
    # End-of-dream game moments from storyId.md, cross-checked against the
    # autosplitter's ld1..ld5 splits (233/310/—/1310/1900). There are FIVE
    # dreams; the old "dream 1 end 310 vs Forest Owls 290 contradiction" was a
    # misattribution — 310 ends dream 2 (Centra excavation, played in Timber
    # Forest AFTER the Forest Owls arc). Dream 3 (Winhill) never moves the
    # story counter (pro stays 395 throughout; the ASL detects it by field id
    # 801), so its check uses 420 — the first post-dream value, entering
    # Squall's D-District cell. All state-based, auto-catch-up.
    LocationData("Laguna Dream 1: Deling City", 120, "Timber", (("story", 233),)),
    LocationData("Laguna Dream 2: Centra Excavation", 121, "Timber", (("story", 310),)),
    LocationData("Laguna Dream 3: Winhill", 122, "Disc 2", (("story", 420),)),
    LocationData("Laguna Dream 4: Trabia Canyon", 123, "Disc 3", (("story", 1310),)),
    LocationData("Laguna Dream 5: Esthar", 124, "Disc 3", (("story", 1900),)),

    # --- Vanilla unique-item handouts: offsets 150+ (reference/itemId.md) ---
    LocationData("Cid's Parting Gift", 150, "Timber", (("item", 168),)),        # Magical Lamp
    LocationData("Tears Point: Fallen Relic", 151, "Disc 3", (("item", 167),)), # Solomon Ring
]

# --- Optional bosses (option-gated): offsets 250+ ---
# Odin's fight is a can't-escape timer battle; letting the Centra Ruins timer hit
# zero mid-fight is a scripted game over, which could falsely credit a win — rare
# enough to accept, noted here. Omega Weapon is EXCLUDED (superboss; filler only).
LOCATION_TABLE += [
    # Second trigger = offline catch-up on the dream byte: Odin's own bit, OR
    # Gilgamesh's (he replaces Odin and clears Odin's bit, but can only appear
    # if Odin was earned — the two bits never coexist in any library save).
    LocationData("Centra Ruins: Odin Defeated", 250, "Disc 2",
                 (("boss", ENC_ODIN), ("dream_flag", 0x0A)), group="boss_extra"),
    LocationData("Ultimecia Castle: Omega Weapon", 251, "Disc 4",
                 (("boss", ENC_OMEGA),), missable=True, group="boss_extra"),
    # UFO/PuPu locations carry a second, state-based trigger for offline
    # catch-up: the quest byte WORLDMAP.koyok_quest (varblock+1397, from
    # Hyne SaveData.h + WorldmapEditor bindings): bits 2-5 = the four
    # sightings, bit 6 = UFO?? beaten, bit 7 = PuPu concluded. The UFO kill
    # also sets MISC2.ufo_battle_encountered bit 0 (+0x18FE948, written by
    # the battle module). VERIFY live.
    LocationData("UFO Sighting: Beach (Moai)", 252, "Disc 3",
                 (("boss", ENC_UFO_SIGHTINGS["Beach (Moai)"]),
                  ("flag_bit", (0x18FEF2D, 0x04))), group="boss_extra"),
    LocationData("UFO Sighting: Plains (Cow)", 253, "Disc 3",
                 (("boss", ENC_UFO_SIGHTINGS["Plains (Cow)"]),
                  ("flag_bit", (0x18FEF2D, 0x08))), group="boss_extra"),
    LocationData("UFO Sighting: Tundra (Metal)", 254, "Disc 3",
                 (("boss", ENC_UFO_SIGHTINGS["Tundra (Metal)"]),
                  ("flag_bit", (0x18FEF2D, 0x10))), group="boss_extra"),
    LocationData("UFO Sighting: Desert (Pyramid)", 255, "Disc 3",
                 (("boss", ENC_UFO_SIGHTINGS["Desert (Pyramid)"]),
                  ("flag_bit", (0x18FEF2D, 0x20))), group="boss_extra"),
    LocationData("UFO?? Shot Down", 256, "Disc 3",
                 (("boss", ENC_UFO_FIGHT),
                  ("flag_bit", (0x18FEF2D, 0x40)),
                  ("flag_bit", (0x18FE948, 0x01))), group="boss_extra"),
    LocationData("PuPu Encountered", 257, "Disc 3",
                 (("boss", ENC_PUPU),
                  ("flag_bit", (0x18FEF2D, 0x80))), group="boss_extra"),
] + [
    LocationData(f"Ultimecia Castle: {name}", 260 + i, "Disc 4",
                 (("boss", enc),), group="boss_extra")
    for i, (name, enc) in enumerate(ENC_CASTLE_BOSSES.items())
]

# Boss-kill checks split from the GF locations that share the same fight:
# Ultima Weapon and Jumbo Cactuar each yield the GF check AND a kill check,
# doubling the reward density of the two hardest optional fights. Ultima
# Weapon stays a normal check to match the precedent of "Ultima Weapon: Eden"
# (also boss-gated, not excluded).
LOCATION_TABLE += [
    LocationData("Ultima Weapon Defeated", 268, "Disc 3",
                 (("boss", ENC_ULTIMA_WEAPON),), group="boss_extra"),
    LocationData("Jumbo Cactuar Defeated", 269, "Disc 3",
                 (("boss", ENC_JUMBO_CACTUAR),), group="boss_extra"),
] + [
    LocationData(f"Ragnarok: {name}", 620 + i, "Disc 3",
                 (("boss", enc),), group="boss_extra")
    for i, (name, enc) in enumerate(ENC_PROPAGATORS.items())
]

# Ultimecia Castle seal ladder: the savemap byte the autosplitter names "seal"
# (`byte seal: "FF8_EN.exe", 0x18FEB06`, IDA var 334 UltimeciaSeals) is a
# BITMASK with one bit per broken seal (confirmed offline 2026-08-31: 0x00 at
# castle entry, 0x21 on two-seal speedrun saves, 0xF7/0xEB partial, 0xFF all).
# The ladder counts set bits, so it is boss-order agnostic. State-based
# complement to the per-boss encounter edges above: kills made while the
# client was offline still catch up here.
SEAL_FLAGS_OFFSET = 0x18FEB06
_ORDINALS = ["First", "Second", "Third", "Fourth", "Fifth", "Sixth", "Seventh", "Eighth"]
LOCATION_TABLE += [
    LocationData(f"Ultimecia Castle: {ordinal} Seal Broken", 680 + i, "Disc 4",
                 (("bits_ge", (SEAL_FLAGS_OFFSET, 0xFF, i + 1)),), group="boss_extra")
    for i, ordinal in enumerate(_ORDINALS)
]

# --- Triple Triad (option-gated): offsets 270+ ---
# Win-ladder thresholds read the u16 total-wins counter; CC Group membership
# bits Jack..Hearts live in +0x18FEB95 (bits 0,1,4,2,3 — that order;
# live-verified clean 2026-08-27). The README's Dr. Kadowaki/King byte
# (+0x18FDD0B) is NOT usable: it sits inside Shiva's GF record
# (completeAbilities[11]), and her learned abilities false-fired the King
# check on a Disc 1 save — those two members have no checks until a real
# offset is found. Joker's flag is also undocumented. Regions pace the ladder
# as a rough time proxy; the CC quest runs Disc 2-3 in Balamb Garden.
CC_QUEST_OFFSET = 0x18FEB95
LOCATION_TABLE += [
    LocationData("Triple Triad: 5 Wins", 270, "Balamb Prologue", (("tt_wins", 5),), group="tt"),
    LocationData("Triple Triad: 15 Wins", 271, "Timber", (("tt_wins", 15),), group="tt"),
    LocationData("Triple Triad: 30 Wins", 272, "Galbadia", (("tt_wins", 30),), group="tt"),
    LocationData("Triple Triad: 60 Wins", 273, "Disc 2", (("tt_wins", 60),), group="tt"),
    LocationData("Triple Triad: 100 Wins", 274, "Disc 3", (("tt_wins", 100),), group="tt"),
    LocationData("CC Group: Jack Defeated", 280, "Disc 2",
                 (("flag_bit", (CC_QUEST_OFFSET, 0x01)),), group="tt"),
    LocationData("CC Group: Club Defeated", 281, "Disc 2",
                 (("flag_bit", (CC_QUEST_OFFSET, 0x02)),), group="tt"),
    LocationData("CC Group: Diamond Defeated", 282, "Disc 2",
                 (("flag_bit", (CC_QUEST_OFFSET, 0x10)),), group="tt"),
    LocationData("CC Group: Spade Defeated", 283, "Disc 2",
                 (("flag_bit", (CC_QUEST_OFFSET, 0x04)),), group="tt"),
    LocationData("CC Group: Heart Defeated", 284, "Disc 2",
                 (("flag_bit", (CC_QUEST_OFFSET, 0x08)),), group="tt"),
    # Kadowaki/King restored 2026-08-28 at the REAL offset: Hyne's CC editor
    # encodes rank Kadowaki as 0x021F and King as 0x221F — the high byte is
    # tt_players_bgu_dialogs2 (FIELD+219, var 475, +0x18FEB93): bit 1 =
    # Kadowaki rank, bit 5 = King ("dormitory to Quistis night"). The old
    # +0x18FDD0B attempt was inside Shiva's GF record. VERIFY live.
    LocationData("CC Group: Dr. Kadowaki Defeated", 285, "Disc 2",
                 (("flag_bit", (0x18FEB93, 0x02)),), group="tt"),
    LocationData("CC Group: King Defeated", 286, "Disc 3",
                 (("flag_bit", (0x18FEB93, 0x20)),), group="tt"),
    # Joker (Training Center): bit 4 of the same byte, Hyne's "joker BGU CC"
    # flag. Offline 2026-08-31: set in exactly the 50 legitimate library saves
    # that own the Leviathan card (Joker's reward) and in none without it —
    # the only exceptions are hacked all-rares-at-Disc-1 saves. Independent of
    # the Jack..Heart chain (set with cc=0x01 in one series). VERIFY live.
    LocationData("CC Group: Joker Defeated", 287, "Disc 2",
                 (("flag_bit", (0x18FEB93, 0x10)),), group="tt"),
]

# Unique-card-collection ladder: distinct cards ever obtained out of 110 (77
# commons at TTCARDS+0, 0x18FEF38, counted by their bit-7 "seen" flag — a
# strict superset of quantity>0 in all 273 library saves, and immune to the
# player refining cards into items — plus the 33 rare bits already used by
# the cards group). The tutorial hand-out is 7 cards, so the ladder starts
# at 10. State-based, auto-catches-up. Regions pace the ladder as a rough
# time proxy, erring late.
LOCATION_TABLE += [
    LocationData("Triple Triad: 10 Unique Cards", 590, "Balamb Prologue",
                 (("cards_owned", 10),), group="tt"),
    LocationData("Triple Triad: 20 Unique Cards", 591, "Timber",
                 (("cards_owned", 20),), group="tt"),
    LocationData("Triple Triad: 35 Unique Cards", 592, "Galbadia",
                 (("cards_owned", 35),), group="tt"),
    LocationData("Triple Triad: 50 Unique Cards", 593, "Disc 2",
                 (("cards_owned", 50),), group="tt"),
    LocationData("Triple Triad: 70 Unique Cards", 594, "Disc 3",
                 (("cards_owned", 70),), group="tt"),
    # Extended tiers (2026-08-31 TT pass; library: 85 kinds = 92 saves,
    # 100 = 54, all 110 = 30). 100 stays reachable without any of the four
    # missable-holder rares (77 commons + 29 rares >= 100); 110 needs every
    # rare AND PuPu's one-chance card -> filler only, and CC-Ragnarok makes
    # lost rares recoverable only on Disc 4.
    LocationData("Triple Triad: 85 Unique Cards", 595, "Disc 3",
                 (("cards_owned", 85),), group="tt"),
    LocationData("Triple Triad: 100 Unique Cards", 596, "Disc 3",
                 (("cards_owned", 100),), group="tt"),
    LocationData("Triple Triad: 110 Unique Cards", 597, "Disc 4",
                 (("cards_owned", 110),), missable=True, group="tt"),
]

# Balamb Garden card circuit: FIELD.tt_bgu_victory_count (var 478,
# +0x18FEB96) counts wins against Garden players — the counter the CC quest
# paces itself on. Library: 0 on non-card saves, 30-129 on every save with
# CC progress, so 15/40/100 land naturally for anyone doing the questline.
BGU_WINS_OFFSET = 0x18FEB96
LOCATION_TABLE += [
    LocationData(f"Balamb Garden: {n} Card Wins", 775 + i, region,
                 (("u8_ge", (BGU_WINS_OFFSET, n)),), group="tt")
    for i, (n, region) in enumerate([
        (15, "Disc 2"), (40, "Disc 3"), (100, "Disc 3"),
    ])
]

# Rule abolition: FIELD.tt_rules[8] at +0x18FEAC8 (region order Balamb,
# Galbadia, Trabia, Centra, Dollet, FH, Lunar Gate, Esthar; bit 3 = Random).
# Virgin values are unanimous across every early library save
# (01/02/0C/0E/88/90/DF/C0), spreading only ever ADDS bits, so a cleared
# Random bit == the player abolished it (Dollet 60/273 saves, Trabia 54,
# Centra 29, Lunar Gate 15). Abolition is never missable (all four regions
# stay revisitable pre-Disc 4) but is RNG-heavy challenge-decline grinding;
# Lunar Gate starts with ALL rules (0xDF) and is the nastiest to manipulate,
# so it and the extinction capstone are filler-only. The capstone spans all
# 8 region bytes: Random gone everywhere, spread copies included.
TT_RULES_OFFSET = 0x18FEAC8
_RANDOM_ABOLITION: list[tuple[str, int, str, bool]] = [
    ("Dollet", 4, "Disc 2", False),
    ("Trabia", 2, "Disc 2", False),
    ("Centra", 3, "Disc 2", False),
    ("Lunar Gate", 6, "Disc 3", True),
]
LOCATION_TABLE += [
    LocationData(f"Rule Abolished: Random ({region_name})", 780 + i, region,
                 (("bits_clear", (TT_RULES_OFFSET + slot, 1, 0x08)),),
                 missable=missable, group="tt")
    for i, (region_name, slot, region, missable) in enumerate(_RANDOM_ABOLITION)
] + [
    LocationData("Random Rule Extinct", 784, "Disc 3",
                 (("bits_clear", (TT_RULES_OFFSET, 8, 0x08)),),
                 missable=True, group="tt"),
]

# Card Compendium: the 77 commons are stored 11 per level (Hyne Data.cpp
# card list order), and "own all 11 of level N" reads as at-least-11
# bit-7 "obtained once" flags in that index range — refining cards away
# can't undo it. Only the Level 5 set is missable: PuPu (card 47) is a
# one-chance reward (feed the UFO?? five elixirs; kill it and the card is
# gone for good). Everything else is farmable from NPCs/Card/Card Mod.
LOCATION_TABLE += [
    LocationData(f"Card Compendium: Level {lvl} Set", 784 + lvl, region,
                 (("cards_seen_range", ((lvl - 1) * 11, 11, 11)),),
                 missable=(lvl == 5), group="tt")
    for lvl, region in [
        (1, "Galbadia"), (2, "Disc 2"), (3, "Disc 2"), (4, "Disc 2"),
        (5, "Disc 3"), (6, "Disc 3"), (7, "Disc 3"),
    ]
]

# --- Rare card checks (option-gated): offsets 500 + rare index ---
# Ownership bit per rare card: cards_rare[i//8] bit i%8 at +0x18FEFA6 (Hyne
# TTCARDS+110, base anchored by the adjacent win/loss/draw counters). Name order
# is Hyne's card list at index 77+i (verified against Data.cpp). A card later
# lost to an NPC clears its bit, but a sent check stays sent. `missable` marks
# cards whose holder leaves the game for good (Watts' Angelo, Zone's Shiva on
# the White SeeD ship, Ellone's Laguna on Lunar Base, the King's Gilgamesh which
# needs Odin recruited before the Disc 3 Seifer fight). Regions are the earliest
# practical window, erring late where the holder is uncertain.
CARDS_RARE_OFFSET = 0x18FEFA6
_CARD_REGIONS: list[tuple[str, str, bool]] = [
    ("Chubby Chocobo", "Disc 3", False),   # Queen of Cards chain
    ("Angelo", "Timber", True),            # Watts, Forest Owls train
    ("Gilgamesh", "Disc 3", True),         # CC King; needs Odin pre-Seifer
    ("MiniMog", "Balamb Prologue", False), # laps runner, Balamb Garden
    ("Chicobo", "Disc 2", False),          # chocobo forests
    ("Quezacotl", "Disc 2", False),        # Mayor Dobe, FH
    ("Shiva", "Disc 2", True),             # Zone, White SeeD ship
    ("Ifrit", "Disc 2", False),            # Martine, FH docks
    ("Siren", "Galbadia", False),
    ("Sacred", "Galbadia", False),
    ("Minotaur", "Galbadia", False),
    ("Carbuncle", "Disc 2", False),        # CC member
    ("Diablos", "Disc 2", False),
    ("Leviathan", "Disc 2", False),        # CC Joker
    ("Odin", "Disc 3", False),
    ("Pandemona", "Disc 2", False),
    ("Cerberus", "Disc 2", False),
    ("Alexander", "Disc 3", False),
    ("Phoenix", "Disc 3", False),
    ("Bahamut", "Disc 3", False),
    ("Doomtrain", "Disc 3", False),        # Queen of Cards chain
    ("Eden", "Disc 3", False),
    ("Ward", "Disc 3", False),             # Dr. Odine
    ("Kiros", "Disc 3", False),            # Queen of Cards chain
    ("Laguna", "Disc 3", True),            # Ellone, Lunar Base
    ("Selphie", "Disc 2", False),          # Trabia friend
    ("Quistis", "Disc 2", False),          # Trepie groupie
    ("Irvine", "Disc 3", False),           # Queen of Cards chain
    ("Zell", "Disc 2", False),             # Ma Dincht
    ("Rinoa", "Disc 3", False),            # General Caraway
    ("Edea", "Disc 3", False),             # Edea, orphanage
    ("Seifer", "Disc 3", False),           # Cid
    ("Squall", "Disc 3", False),           # Laguna, Esthar
]
LOCATION_TABLE += [
    LocationData(f"Rare Card: {name}", 500 + i, region,
                 (("flag_bit", (CARDS_RARE_OFFSET + i // 8, 1 << (i % 8))),),
                 missable=missable, group="cards")
    for i, (name, region, missable) in enumerate(_CARD_REGIONS)
]

# --- Sidequest checks (option-gated): offsets 540+ ---
# Quistis blue magics: bits of the u16 at +0x18FE76C (Hyne LIMITB+0).
# CONFIRMED live 2026-08-27: offset and bit order (in-game limit list order)
# verified bit-for-bit against a real save (0x01BF = her exact known list).
# Laser Eye is known from the start, so it is not a check.
QUISTIS_LIMITS_OFFSET = 0x18FE76C
_BLUE_MAGIC: list[tuple[int, str, str]] = [
    (1,  "Ultra Waves", "Timber"),
    (2,  "Electrocute", "Timber"),
    (3,  "LV?Death", "Disc 2"),
    (4,  "Degenerator", "Disc 2"),
    (5,  "Aqua Breath", "Disc 2"),
    (6,  "Micro Missiles", "Disc 2"),
    (7,  "Acid", "Disc 2"),
    (8,  "Gatling Gun", "Disc 2"),
    (9,  "Fire Breath", "Disc 2"),
    (10, "Bad Breath", "Disc 3"),
    (11, "White Wind", "Disc 3"),
    (12, "Homing Laser", "Disc 3"),
    (13, "Mighty Guard", "Disc 3"),
    (14, "Ray-Bomb", "Disc 2"),
    (15, "Shockwave Pulsar", "Disc 3"),
]
LOCATION_TABLE += [
    LocationData(f"Blue Magic: {name}", 540 + bit, region,
                 (("flag_bit", (QUISTIS_LIMITS_OFFSET + bit // 8, 1 << (bit % 8))),),
                 group="sidequest")
    for bit, name, region in _BLUE_MAGIC
]

# Angelo tricks: bits of the u8 at +0x18FE773 (Hyne LIMITB.angel_known).
# CONFIRMED live 2026-08-27: the byte tracks Pet Pals magazines READ (trick
# discovered), canonical order bit0=Rush..bit7=Wishing Star. Rush and Cannon
# are Rinoa's innate tricks — no magazine, their bits never set, so no checks.
ANGELO_KNOWN_OFFSET = 0x18FE773
_ANGELO_TRICKS: list[tuple[int, str, str]] = [
    (1, "Angelo Recover", "Disc 2"),
    (2, "Angelo Reverse", "Disc 2"),
    (3, "Angelo Search", "Disc 2"),
    (5, "Angelo Strike", "Disc 2"),
    (6, "Invincible Moon", "Disc 2"),
    (7, "Wishing Star", "Disc 3"),
]
LOCATION_TABLE += [
    LocationData(f"Angelo Trick: {name}", 560 + bit, region,
                 (("flag_bit", (ANGELO_KNOWN_OFFSET, 1 << bit)),), group="sidequest")
    for bit, name, region in _ANGELO_TRICKS
]

# Zell Duel finishers: bits of the u16 at +0x18FE76E (Hyne LIMITB.zell, +2 —
# right after Quistis's blue-magic u16). Bit order is Hyne's ZellLBs list;
# bits 0-3 and 6 (Punch Rush/Booya/Heel Drop/Mach Kick/Burning Rave) are
# innate and set in every library save, so no checks. Reading Combat King
# 001-005 sets bits 4/5/7/8/9 — CONFIRMED offline 2026-08-31: each learned
# bit appears only in saves that own the matching magazine (strict subset,
# 273 saves). Missability mirrors the magazine table: only Combat King 004
# (Different Beat) comes from a renewable source (Esthar pet shop).
ZELL_DUELS_OFFSET = 0x18FE76E
_ZELL_DUELS: list[tuple[int, str, str, bool]] = [
    (4, "Dolphin Blow", "Disc 2", True),      # Combat King 001, D-District Prison
    (5, "Meteor Strike", "Disc 2", True),     # Combat King 002, occupied Balamb
    (7, "Meteor Barret", "Disc 3", True),     # Combat King 003, source uncertain
    (8, "Different Beat", "Disc 3", False),   # Combat King 004, Esthar pet shop
    (9, "My Final Heaven", "Disc 3", True),   # Combat King 005, Lunatic Pandora
]
LOCATION_TABLE += [
    LocationData(f"Zell Duel: {name}", 710 + bit, region,
                 (("flag_bit", (ZELL_DUELS_OFFSET + bit // 8, 1 << (bit % 8))),),
                 missable=missable, group="sidequest")
    for bit, name, region, missable in _ZELL_DUELS
]

# Timber Maniacs: popcount ladder over the u16 issue bitmask at +0x18FEAE8
# (Hyne FIELD+48; FIELD internals carry four independent live anchors). Ladder
# is bit-order agnostic. Several issues sit in one-time areas, so the 9- and
# 12-issue tiers are missable -> excluded.
TIMBER_MANIACS_OFFSET = 0x18FEAE8
LOCATION_TABLE += [
    LocationData("Timber Maniacs: 1 Issue", 570, "Timber",
                 (("popcount16_ge", (TIMBER_MANIACS_OFFSET, 1)),), group="sidequest"),
    LocationData("Timber Maniacs: 3 Issues", 571, "Disc 2",
                 (("popcount16_ge", (TIMBER_MANIACS_OFFSET, 3)),), group="sidequest"),
    LocationData("Timber Maniacs: 6 Issues", 572, "Disc 2",
                 (("popcount16_ge", (TIMBER_MANIACS_OFFSET, 6)),), group="sidequest"),
    LocationData("Timber Maniacs: 9 Issues", 573, "Disc 3",
                 (("popcount16_ge", (TIMBER_MANIACS_OFFSET, 9)),), missable=True,
                 group="sidequest"),
    LocationData("Timber Maniacs: 12 Issues", 574, "Disc 3",
                 (("popcount16_ge", (TIMBER_MANIACS_OFFSET, 12)),), missable=True,
                 group="sidequest"),
]

# Per-issue Timber Maniacs checks (added 2026-09-02, beta feedback: hunters
# want a tracker pin per issue). Bit -> location map from Hyne ItemEditor.cpp
# timbermaniacsStrings (bit i = row i), validated against the 273-save library:
# every bit's earliest appearance matches its source's story window, bits 14/15
# zero everywhere. The two Balamb issues are MUTUALLY EXCLUSIVE in vanilla (no
# save holds both; completionists max at 13 of 14) -> both missable, as are the
# one-window White SeeD Ship, the occupation-window Balamb Hotel, and the
# often-absent Shumi/Edea's House issues (quest/window-gated per library
# absence patterns). These live in the magazine group: they're magazine
# pickups, and the ladder above (sidequest group) stays untouched.
_TM_ISSUES: list[tuple[int, str, str, bool]] = [
    (0,  "Balamb Hotel", "Disc 2", True),          # occupation window; excl. w/ Station
    (1,  "Balamb Station", "SeeD", True),          # mutually exclusive w/ Hotel
    (2,  "Dollet Pub", "Timber", False),
    (3,  "Dollet Hotel", "Timber", False),
    (4,  "Timber Maniacs Building", "Timber", False),
    (5,  "Timber Hotel", "Timber", False),
    (6,  "Deling City Hotel", "Galbadia", False),
    (7,  "FH Grease Monkey's House", "Disc 2", False),
    (8,  "FH Hotel", "Disc 2", False),
    (9,  "Trabia Garden Cemetery", "Disc 2", False),
    (10, "Centra Ruins", "Disc 2", False),         # automatic on visit
    (11, "Shumi Village", "Disc 2", True),         # behind Shumi quest progress
    (12, "Edea's House", "Disc 3", True),
    (13, "White SeeD Ship", "Disc 3", True),       # one visit only
]
LOCATION_TABLE += [
    LocationData(f"Timber Maniacs: {name}", 900 + bit, region,
                 (("flag_bit", (TIMBER_MANIACS_OFFSET + bit // 8, 1 << (bit % 8))),),
                 missable=missable, group="magazine")
    for bit, name, region, missable in _TM_ISSUES
]

# Chocobo forests: vars 616-622 (0x18FEC20+) are the seven forests' quest
# bytes. Library-settled 2026-09-02 (238 legit saves): values only ever
# {0, 0x02, 0x20, 0x40, 0x80}, monotone stages with 0x80 = forest solved
# (all seven 0x80 in every completionist save). WHICH var is WHICH forest is
# still unknown (no Hyne binding; partial saves gave no location evidence), so
# the checks are an order-agnostic solved-count ladder via the new byteflag_ge
# trigger; per-forest named checks wait on one live forest-solve diff. Forests
# open with the mobile Garden (Disc 2); the seventh (Sanctuary) is late.
CHOCOBO_FORESTS_OFFSET = 0x18FEC20
LOCATION_TABLE += [
    LocationData("Chocobo Forests Solved: 1", 914, "Disc 2",
                 (("byteflag_ge", (CHOCOBO_FORESTS_OFFSET, 7, 0x80, 1)),), group="sidequest"),
    LocationData("Chocobo Forests Solved: 3", 915, "Disc 2",
                 (("byteflag_ge", (CHOCOBO_FORESTS_OFFSET, 7, 0x80, 3)),), group="sidequest"),
    LocationData("Chocobo Forests Solved: 5", 916, "Disc 3",
                 (("byteflag_ge", (CHOCOBO_FORESTS_OFFSET, 7, 0x80, 5)),), group="sidequest"),
    LocationData("Chocobo Forests Solved: 7", 917, "Disc 3",
                 (("byteflag_ge", (CHOCOBO_FORESTS_OFFSET, 7, 0x80, 7)),), group="sidequest"),
]

# Cameo GF acquisitions via the MISC2 dream byte (+0x18FE97A; bit layout
# confirmed offline 2026-08-31 across the save library): edge-based so the
# multiworld granting "GF Phoenix"/"GF Gilgamesh" doesn't self-fire them.
# Phoenix needs a Phoenix Pinion drop (luck-gated) and Gilgamesh needs Odin
# before the Disc 3 Seifer fight -> both excluded from progression fill.
LOCATION_TABLE += [
    LocationData("Phoenix Summoned", 575, "Disc 3",
                 (("dream_flag", 0x04),), missable=True, group="sidequest"),
    LocationData("Gilgamesh Arrives", 576, "Disc 3",
                 (("dream_flag", 0x08),), missable=True, group="sidequest"),
]

# Queen of Cards chain: FIELD.tt_cardqueen_quest (var 300, +0x18FEAE4) is the
# "last created card" — 1 Kiros, 2 Irvine, 3 Chubby Chocobo, 4 Doomtrain,
# 5 Phoenix (values from Hyne TTriadEditor.cpp; var provenance: JSM scan shows
# it written only by the Dollet artist's field). The chain is sequential, so
# u8_ge tiers work. Losing rare cards to the Queen is reversible (win them
# back), so not missable — but the grind is real, so all EXCLUDED. VERIFY.
QUEEN_QUEST_OFFSET = 0x18FEAE4
_QUEEN_CARDS = ["Kiros", "Irvine", "Chubby Chocobo", "Doomtrain", "Phoenix"]
LOCATION_TABLE += [
    LocationData(f"Queen of Cards: {card} Card Created", 690 + i,
                 "Disc 2" if i < 2 else "Disc 3",
                 (("u8_ge", (QUEEN_QUEST_OFFSET, i + 1)),),
                 missable=True, group="sidequest")
    for i, card in enumerate(_QUEEN_CARDS)
]

# Obel Lake quest: WORLDMAP.obel_quest[8] at varblock+1398 (+0x18FEF2E), full
# bit map from Hyne WorldmapEditor.cpp checkbox bindings. Milestone checks
# only (the reward beats). State-based catch-up. VERIFY live.
OBEL_BASE = 0x18FEF2E
LOCATION_TABLE += [
    LocationData("Obel Lake: Mr. Monkey Found", 700, "Disc 2",
                 (("flag_bit", (OBEL_BASE + 6, 0x04)),), group="sidequest"),
    LocationData("Obel Lake: Eldbeak Pillar Read", 701, "Disc 2",
                 (("flag_bit", (OBEL_BASE + 1, 0x80)),), group="sidequest"),
    LocationData("Obel Lake: All Rocks Found", 702, "Disc 2",
                 (("flag_bit", (OBEL_BASE + 3, 0x20)),), group="sidequest"),
    LocationData("Obel Lake: Minde Island Treasure", 703, "Disc 3",
                 (("flag_bit", (OBEL_BASE + 2, 0x01)),), group="sidequest"),
    LocationData("Obel Lake: Esthar Mountains Treasure", 704, "Disc 3",
                 (("flag_bit", (OBEL_BASE + 2, 0x02)),), group="sidequest"),
]

# Battles-won ladder: MISC2 victory_count u32 at +0x18FE934 (Hyne SaveData.h,
# packed between the live-anchored play-time/countdown and battles-escaped
# fields; VERIFY live). Battles are infinitely farmable, so every tier stays
# reachable; regions err late so logic never expects early grinding.
BATTLES_WON_OFFSET = 0x18FE934
LOCATION_TABLE += [
    LocationData("Battles Won: 25", 600, "Timber",
                 (("u32_ge", (BATTLES_WON_OFFSET, 25)),), group="sidequest"),
    LocationData("Battles Won: 50", 601, "Galbadia",
                 (("u32_ge", (BATTLES_WON_OFFSET, 50)),), group="sidequest"),
    LocationData("Battles Won: 100", 602, "Disc 2",
                 (("u32_ge", (BATTLES_WON_OFFSET, 100)),), group="sidequest"),
    LocationData("Battles Won: 200", 603, "Disc 3",
                 (("u32_ge", (BATTLES_WON_OFFSET, 200)),), group="sidequest"),
]

# SeeD written tests: MISC2 testLevel u8 at +0x18FE98B (Hyne SaveData.h; the
# struct's "pos=100" comment pins it exactly; VERIFY live). Tests are taken
# from the in-game menu any time after SeeD graduation, so nothing is missable.
SEED_TEST_LEVEL_OFFSET = 0x18FE98B
LOCATION_TABLE += [
    LocationData("SeeD Tests: Level 5", 610, "SeeD",
                 (("u8_ge", (SEED_TEST_LEVEL_OFFSET, 5)),), group="sidequest"),
    LocationData("SeeD Tests: Level 10", 611, "Timber",
                 (("u8_ge", (SEED_TEST_LEVEL_OFFSET, 10)),), group="sidequest"),
    LocationData("SeeD Tests: Level 20", 612, "Disc 2",
                 (("u8_ge", (SEED_TEST_LEVEL_OFFSET, 20)),), group="sidequest"),
    LocationData("SeeD Tests: Level 30", 613, "Disc 3",
                 (("u8_ge", (SEED_TEST_LEVEL_OFFSET, 30)),), group="sidequest"),
]

# Weapon remodels: MISC1.unlocked_weapons (u32 at +0x18FE750, Hyne SaveData.h)
# has bit i set once kernel weapon id i has been made at any point. Confirmed
# offline 2026-08-31 against 273 library saves (tools/save_scan.py): every
# equipped weaponID's bit is set, the base weapons [0,7,11,15,19,24] always
# are, saves that own no Weapons Monthly still carry a bit for every tier they
# passed through, and bits survive downgrades — a monotonic "ever made" record,
# so a check can't be lost by re-remodeling (the equipped weaponID byte at
# char record +0x09 can go back down; it stays a /ff8verify aid only). Kernel
# ids are grouped per character (Hyne Data.cpp): Squall 0-6, Zell 7-10,
# Irvine 11-14, Quistis 15-18, Rinoa 19-23, Selphie 24-27. Mid tiers can be
# skipped by remodeling straight to a later weapon, so only the two
# guaranteed-reachable rungs are checks: "first remodel" (a second bit in the
# character's range) and the ultimate weapon. Ultimates need heavy item
# farming -> excluded, filler only.
WEAPONS_UNLOCKED_OFFSET = 0x18FE750
_WEAPON_CHECKS: list[tuple[str, int, int, str, str]] = [
    # (name, base weapon id, ultimate id, ultimate name, remodel region)
    ("Squall", 0, 6, "Lion Heart", "Timber"),
    ("Zell", 7, 10, "Ehrgeiz", "Timber"),
    ("Irvine", 11, 14, "Exeter", "Galbadia"),
    ("Quistis", 15, 18, "Save the Queen", "Timber"),
    ("Rinoa", 19, 23, "Shooting Star", "Galbadia"),
    ("Selphie", 24, 27, "Strange Vision", "Timber"),
]


def _weapon_mask(lo: int, hi: int) -> int:
    return sum(1 << b for b in range(lo, hi + 1))


LOCATION_TABLE += [
    LocationData(f"Weapon Remodel: {name}", 660 + i, region,
                 (("bits_ge", (WEAPONS_UNLOCKED_OFFSET, _weapon_mask(base, top), 2)),),
                 group="sidequest")
    for i, (name, base, top, _tn, region) in enumerate(_WEAPON_CHECKS)
] + [
    LocationData(f"Ultimate Weapon: {top_name} ({name})", 666 + i, "Disc 3",
                 (("bits_ge", (WEAPONS_UNLOCKED_OFFSET, 1 << top, 1)),),
                 missable=True, group="sidequest")
    for i, (name, _base, top, top_name, _r) in enumerate(_WEAPON_CHECKS)
]

# --- Magazine checks (option-gated): offsets 640+ ---
# item_own trigger: owning >= 1 of the magazine's item id sends the check, and
# the magazine is NOT intercepted — Combat King and Pet Pals must stay with the
# player (reading them teaches Zell's limits / Angelo's tricks, which are
# themselves sidequest checks). State-based, so offline pickups catch up.
# `missable` marks one-window sources (D-District Prison, occupied Balamb,
# Lunatic Pandora, the Forest Owls train). Combat King 003 is dual-sourced
# (library-girl quest finale at the Balamb hotel OR purchase in Esthar's
# book/pet shops — guide-confirmed 2026-09-02), so it is NOT missable.
# Item ids from ff8-memory reference/itemId.md.
_MAGAZINES: list[tuple[int, str, str, bool]] = [
    (177, "Weapons Monthly 1st", "Disc 4", False),   # Ultimecia Castle armory
    (178, "Weapons Monthly March", "SeeD", False),   # Squall's dorm
    (179, "Weapons Monthly April", "Galbadia", False),  # Deling sewers
    (180, "Weapons Monthly May", "Disc 2", True),    # D-District Prison
    (181, "Weapons Monthly June", "Disc 2", False),  # Fisherman's Horizon
    (182, "Weapons Monthly July", "Disc 2", False),  # Trabia Garden
    (183, "Weapons Monthly August", "Disc 3", False),  # Esthar
    (184, "Combat King 001", "Disc 2", True),        # D-District Prison
    (185, "Combat King 002", "Disc 2", True),        # occupied Balamb hotel
    (186, "Combat King 003", "Disc 3", False),       # library-girl quest OR Esthar shop
    (187, "Combat King 004", "Disc 3", False),       # Esthar pet shop
    (188, "Combat King 005", "Disc 3", True),        # Lunatic Pandora (Raijin)
    (189, "Pet Pals Vol.1", "Timber", True),         # Rinoa's room, Owls train
    (190, "Pet Pals Vol.2", "Timber", False),        # Timber pet shop
    (195, "Occult Fan I", "Balamb Prologue", False),  # Garden library shelf
    (196, "Occult Fan II", "Timber", False),         # Timber Maniacs building
    (197, "Occult Fan III", "Disc 2", False),        # FH, Master Fisherman
    (198, "Occult Fan IV", "Disc 3", False),         # Esthar
    (163, "Girl Next Door", "Timber", False),        # Timber Maniacs building
]
LOCATION_TABLE += [
    LocationData(f"Magazine: {name}", 640 + i, region,
                 (("item_own", item_id),), missable=missable, group="magazine")
    for i, (item_id, name, region, missable) in enumerate(_MAGAZINES)
]

# Shop-only Pet Pals issues, added 2026-09-02 (beta feedback): purchasable all
# game once their shop opens, matching the Combat King 004 precedent — the
# payoff of reading them (Angelo tricks) doubles as sidequest checks, but
# owning the issue is its own check. The 640+ window is full past 658 (660+ =
# weapon remodels), so these take explicit ids in the free 672-675 block.
_MAGAZINES_SHOP: list[tuple[int, int, str, str]] = [
    (672, 191, "Pet Pals Vol.3", "Timber"),   # Timber pet shop
    (673, 192, "Pet Pals Vol.4", "Timber"),   # Timber pet shop
    (674, 193, "Pet Pals Vol.5", "Disc 3"),   # Esthar pet shop
    (675, 194, "Pet Pals Vol.6", "Disc 3"),   # Esthar pet shop
]
LOCATION_TABLE += [
    LocationData(f"Magazine: {name}", offset, region,
                 (("item_own", item_id),), group="magazine")
    for offset, item_id, name, region in _MAGAZINES_SHOP
]

# --- Stat ladder checks (option-gated): offsets 720+ ---
# Lifetime counters the game keeps on its own; every ladder is farmable at any
# point, so (matching the battles-won precedent) nothing is missable — regions
# err late so logic never expects early grinding. All offsets decoded from
# Hyne SaveData.h structs and confirmed against the 273-save library
# 2026-08-31 (tools/save_scan.py; tier values chosen from that data's
# per-disc percentiles). See ff8/memory.py for the per-field evidence.
#
# Squall's level: flat 1000 EXP per level (level = exp//1000 + 1, Hyne
# PersoEditor; legit maxed saves sit at exactly 99000). Reading his EXP u32
# (char record 0, +4) with u32_ge((L-1)*1000) IS the level check. Squall
# starts at ~6.5k EXP (level 7) and is never benched, so his record is the
# stable one to ladder on. Library medians: Disc 1 ~8, casual Disc 3 ~20-40.
SQUALL_EXP_OFFSET = 0x18FE0EC   # CHAR_BASE + CHAR_EXP_OFFSET
LOCATION_TABLE += [
    LocationData(f"Squall: Level {level}", 720 + i, region,
                 (("u32_ge", (SQUALL_EXP_OFFSET, (level - 1) * 1000)),),
                 group="stats")
    for i, (level, region) in enumerate([
        (10, "Disc 2"), (15, "Disc 2"), (20, "Disc 3"),
        (30, "Disc 3"), (40, "Disc 3"),
    ])
]

# Distinct magics ever obtained: popcount of misc2.magic_drawn_once (bit =
# spell id - 1, ids 1-56 -> 7 bytes). Draw points and battle draws both set
# bits; multiworld magic filler does NOT (it writes inventory slots), so the
# ladder only moves on the player's own draws. ~50 kinds are obtainable
# pre-endgame; library kitchen-sink saves top out at 50.
MAGIC_DRAWN_OFFSET = 0x18FE95C
LOCATION_TABLE += [
    LocationData(f"Magic Collection: {n} Kinds", 730 + i, region,
                 (("popcount_ge", (MAGIC_DRAWN_OFFSET, 7, n)),), group="stats")
    for i, (n, region) in enumerate([
        (5, "Timber"), (10, "Galbadia"), (20, "Disc 2"),
        (30, "Disc 3"), (40, "Disc 3"),
    ])
]

# Marquee first-draws: single bits of the same bitmask for the game's
# headline spells — rewards draw-point hunting and enemy-draw curiosity.
# All eight have repeatable sources (refilling draw points and/or common
# late-game enemies), so none are missable. Bit = spell id - 1.
_MARQUEE_DRAWS: list[tuple[str, int, str]] = [
    ("Ultima", 19, "Disc 2"),    # FH mayor's residence / Shumi Village points
    ("Meteor", 16, "Disc 3"),    # FH salt lake, Lunatic Pandora, Ruby Dragons
    ("Holy", 14, "Disc 2"),      # Centra excavation point, Elnoyles
    ("Flare", 15, "Disc 3"),     # Odine's lab lobby, Ruby Dragons/Hexadragons
    ("Quake", 17, "Disc 3"),     # Odine's laboratory point
    ("Tornado", 18, "Disc 2"),   # Abyss Worms/Thrustaevis
    ("Triple", 34, "Disc 3"),    # Odin, CC King, Cerberus, Deep Sea point
    ("Aura", 32, "Disc 2"),      # Trabia festival stage point, Seifer draws
]
LOCATION_TABLE += [
    LocationData(f"First Draw: {name}", 740 + i, region,
                 (("flag_bit", (MAGIC_DRAWN_OFFSET + (sid - 1) // 8,
                                1 << ((sid - 1) % 8))),), group="stats")
    for i, (name, sid, region) in enumerate(_MARQUEE_DRAWS)
]

# Enemy intel: popcount of misc2.ennemy_scanned_once (20 bytes, bit per scan
# page). Most library saves never scan (median 0), so tiers stay modest; the
# option is an opt-in and Scan is drawable from Disc 1 on. VERIFY live.
ENEMIES_SCANNED_OFFSET = 0x18FE964
LOCATION_TABLE += [
    LocationData(f"Enemies Scanned: {n}", 750 + i, region,
                 (("popcount_ge", (ENEMIES_SCANNED_OFFSET, 20, n)),), group="stats")
    for i, (n, region) in enumerate([
        (5, "Timber"), (10, "Galbadia"), (20, "Disc 2"), (30, "Disc 3"),
    ])
]

# Battles escaped: misc2.battle_escaped u16 (+18, the README's confirmed
# 0x18FE93A row). Running away is a two-second farm; library medians are
# 3 / 12 / 23 by disc.
BATTLES_ESCAPED_OFFSET = 0x18FE93A
LOCATION_TABLE += [
    LocationData(f"Battles Escaped: {n}", 755 + i, region,
                 (("u16_ge", (BATTLES_ESCAPED_OFFSET, n)),), group="stats")
    for i, (n, region) in enumerate([
        (5, "Disc 2"), (15, "Disc 3"), (30, "Disc 3"),
    ])
]

# Monsters felled: misc3.monster_kills u32 (var 68) — individual enemies, not
# battles (~1.8x the battles-won counter in the library), complementing the
# battles-won ladder in the sidequest group.
MONSTER_KILLS_OFFSET = 0x18FE9FC
LOCATION_TABLE += [
    LocationData(f"Monsters Felled: {n}", 760 + i, region,
                 (("u32_ge", (MONSTER_KILLS_OFFSET, n)),), group="stats")
    for i, (n, region) in enumerate([
        (50, "Galbadia"), (150, "Disc 2"), (300, "Disc 3"), (500, "Disc 3"),
    ])
]

# Steps walked: misc3.steps u32 (var 4), lifetime. Library: fresh save ~4k,
# every Disc 2 save >= 147k, Disc 3 lower quartile ~395k.
STEPS_OFFSET = 0x18FE9BC
LOCATION_TABLE += [
    LocationData(f"Steps Taken: {label}", 765 + i, region,
                 (("u32_ge", (STEPS_OFFSET, n)),), group="stats")
    for i, (n, label, region) in enumerate([
        (20_000, "20,000", "Galbadia"), (60_000, "60,000", "Disc 2"),
        (150_000, "150,000", "Disc 2"), (300_000, "300,000", "Disc 3"),
    ])
]

# Tonberries culled: misc2.tomberry_vaincus u32 (+24). The King answers for
# his subjects at 20 — the same counter the Tonberry King check's flag sits
# behind. Centra Ruins opens with the mobile Garden (Disc 2).
TONBERRY_KILLS_OFFSET = 0x18FE940
LOCATION_TABLE += [
    LocationData(f"Tonberries Culled: {n}", 770 + i, region,
                 (("u32_ge", (TONBERRY_KILLS_OFFSET, n)),), group="stats")
    for i, (n, region) in enumerate([
        (5, "Disc 2"), (10, "Disc 3"), (20, "Disc 3"),
    ])
]

# SeeD rank: misc3.seedExp u16 (var 16, the README's confirmed "SeeD test
# points" row); rank = exp // 100, 31 = rank A (Hyne MiscEditor). The ONE
# non-monotonic ladder: rank decays (every 3rd payslip / bad conduct), so a
# tier fires on the highest rank ever SEEN while the client is attached —
# AP's once-sent latch makes decay afterwards harmless, and rank is always
# regainable (written tests +100 each, battles trickle points: library
# testLevel=0 runs show 500->546->552). A peak reached with the client
# detached that decays before reconnecting is missed until re-earned; the
# player doc says so. Graduation (moment 17) grades ~rank 5 (one library
# save got 430), so tier 5 is a near-gimme in the SeeD region; higher tiers
# err late like every ladder. Rank A needs all 30 tests plus a held margin
# (legit library ceiling is exactly 3100) — pure grind, filler only.
SEED_EXP_OFFSET = 0x18FE9C8
LOCATION_TABLE += [
    LocationData(f"SeeD Rank: {label}", 795 + i, region,
                 (("u16_ge", (SEED_EXP_OFFSET, n * 100)),),
                 missable=(label == "A"), group="stats")
    for i, (n, label, region) in enumerate([
        (5, "5", "SeeD"), (10, "10", "Disc 2"),
        (20, "20", "Disc 3"), (31, "A", "Disc 3"),
    ])
]

# --- GF ability mastery (option-gated `gf_ability_checks`, group "abilities") ---
# Each GF record (0x44 bytes from 0x18FDCA8) carries Hyne's completeAbilities[16]
# at +20: bit i = kernel ability id i. Every GF's new-game DEFAULT mask is
# unanimous across the 273-save library (memory.GF_ABILITY_DEFAULTS, 2026-09-01),
# so a multiworld-granted GF arrives knowing exactly its defaults and only play
# moves the bits — "learned beyond default" can never be satisfied by receipt.
# Ability ids/AP costs/learn lists come from Hyne Data.cpp (Abilities::fillList,
# apsTab, innateAbilities). Library check: every signature ability below is
# learned in 25-95% of saves owning the GF; full mastery (all 22) in 45-88% for
# the Disc 1-2 GFs. Ability-teaching items (Rosetta Stone & co.) set the same
# bits and count as earned — the filler pool never contains one. Amnesia Greens
# can clear bits again, harmlessly: checks are >=/once semantics. Every check
# here also requires the GF item itself (set_rules), so GFs gate real content.
GF_ABILITIES_BASE = 0x18FDCA8 + 20          # memory.gf_abilities_addr(0)
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
_GF_NAMES = list(GF_INDEX)


def _ability_region(ap_cost: int) -> str:
    """Pacing by AP price: ~1 AP per early fight, ~10+ per Disc 2 fight."""
    if ap_cost <= 60:
        return "Dollet Exam"
    if ap_cost <= 100:
        return "Timber"
    if ap_cost <= 160:
        return "Galbadia"
    if ap_cost <= 200:
        return "Disc 2"
    return "Disc 3"


def _gf_ability_mask(ids) -> int:
    mask = 0
    for aid in ids:
        mask |= 1 << aid
    return mask


_sig_i = 0
for _gf, _ids in GF_SIGNATURE_ABILITIES.items():
    for _aid in _ids:
        LOCATION_TABLE.append(LocationData(
            f"{_GF_NAMES[_gf]} Learns {GF_ABILITY_NAMES[_aid]}", 800 + _sig_i,
            _ability_region(GF_ABILITY_AP[_aid]),
            (("flag_bit", (GF_ABILITIES_BASE + _gf * 0x44 + _aid // 8, 1 << (_aid % 8))),),
            group="abilities", requires_gf=_gf))
        _sig_i += 1
# Mastery: all 22 natural abilities known (bits_all over the 16-byte mask).
LOCATION_TABLE += [
    LocationData(f"{_GF_NAMES[_gf]} Mastered", 850 + _gf, "Disc 3",
                 (("bits_all", (GF_ABILITIES_BASE + _gf * 0x44, 16,
                                _gf_ability_mask(GF_LEARN_LISTS[_gf]))),),
                 group="abilities", requires_gf=_gf)
    for _gf in range(16)
]
# Party-wide ladder: abilities learned beyond default, summed over all 16 GFs
# (244 possible). Library: Disc 1 median 10, Disc 2 median 94, finishers ~230.
LOCATION_TABLE += [
    LocationData(f"GF Abilities Learned: {n}", 870 + i, region,
                 (("gf_abilities_ge", n),), missable=grind, group="abilities")
    for i, (n, region, grind) in enumerate([
        (10, "Timber", False), (25, "Galbadia", False), (50, "Disc 2", False),
        (100, "Disc 2", False), (150, "Disc 3", False), (200, "Disc 3", True),
    ])
]

# --- Draw point checks (option-gated): offsets 300 + slot index ---
# Slot index N maps to savemap byte +0x18FEA2C + N//4, bits (N%4)*2 (ff8-memory
# README "Field - Draw Points", EN column, row order == slot order). Only named
# field-screen draw points are included; "???" slots and hidden world-map draw
# points are left out. `missable` marks one-window areas (D-District Prison,
# Missile Base, Galbadia Garden, White SeeD Ship, Lunar Base, the Lunatic Pandora
# Laboratory dream) — those are excluded from progression fill so a missed sparkle
# can never strand a progression item. Regions err late where access is fuzzy;
# story gates here are events, not items, so a late-leaning region is always safe.
#
# (slot, spell, place, region, missable)
DRAW_POINT_TABLE: list[tuple[int, str, str, str, bool]] = [
    (0,   "Cure",      "Balamb Garden Front Gate",        "Balamb Prologue", False),
    (1,   "Blizzard",  "Balamb Garden Training Center",   "Balamb Prologue", False),
    (2,   "Full-life", "Balamb Garden MD Level",          "Disc 2",          False),
    (3,   "Esuna",     "Balamb Garden Library",           "Balamb Prologue", False),
    (4,   "Demi",      "Balamb Garden Cafeteria",         "Balamb Prologue", False),
    (5,   "Bio",       "Balamb Garden Master Room",       "Disc 2",          False),
    (6,   "Thunder",   "Balamb Town Square",              "Fire Cavern",     False),
    (7,   "Cure",      "Balamb Harbor",                   "Fire Cavern",     False),
    (8,   "Fire",      "Fire Cavern",                     "Fire Cavern",     False),
    (9,   "Silence",   "Dollet Town Square",              "Dollet Exam",     False),
    (10,  "Blind",     "Dollet Comm Tower",               "Dollet Exam",     False),
    (11,  "Scan",      "Timber City Square",              "Timber",          False),
    (12,  "Cure",      "Timber City Square",              "Timber",          False),
    (13,  "Blizzaga",  "Timber Editorial Department",     "Timber",          False),
    (14,  "Haste",     "Galbadia Garden Hall",            "Galbadia",        True),
    (15,  "Life",      "Galbadia Garden Clubroom",        "Galbadia",        True),
    (16,  "Shell",     "Galbadia Garden Athletic Track",  "Galbadia",        True),
    (17,  "Protect",   "Galbadia Garden Gymnasium",       "Galbadia",        True),
    (18,  "Double",    "Galbadia Garden Auditorium",      "Disc 2",          True),
    (19,  "Aura",      "Galbadia Garden Back Entrance",   "Galbadia",        True),
    (20,  "Cure",      "Timber Forest",                   "Timber",          False),
    (21,  "Water",     "Timber Forest",                   "Timber",          False),
    (22,  "Thundara",  "Deling City Square",              "Galbadia",        False),
    (23,  "Zombie",    "Deling City Sewer",               "Galbadia",        False),
    (24,  "Esuna",     "Deling City Sewer",               "Galbadia",        False),
    (25,  "Bio",       "Deling City Sewer",               "Galbadia",        False),
    # 26 = Fira / ??? (unknown slot, skipped)
    (27,  "Berserk",   "D-District Prison",               "Disc 2",          True),
    (28,  "Thundaga",  "D-District Prison",               "Disc 2",          True),
    (29,  "Aero",      "Prison Desert",                   "Disc 2",          True),
    (30,  "Blizzara",  "Missile Base",                    "Disc 2",          True),
    (31,  "Blind",     "Missile Base",                    "Disc 2",          True),
    (32,  "Full-life", "Missile Base",                    "Disc 2",          True),
    (33,  "Drain",     "Winhill Village",                 "Disc 2",          False),
    (34,  "Dispel",    "Winhill Village",                 "Disc 2",          False),
    (35,  "Curaga",    "Winhill Vacant House",            "Disc 2",          False),
    (36,  "Reflect",   "Winhill Village",                 "Disc 2",          False),
    (37,  "Protect",   "Tomb of the Unknown King",        "Galbadia",        False),
    (38,  "Float",     "Tomb of the Unknown King",        "Galbadia",        False),
    (39,  "Cura",      "Tomb of the Unknown King",        "Galbadia",        False),
    (40,  "Haste",     "FH Station Yard",                 "Disc 2",          False),
    (41,  "Shell",     "FH Residential Area",             "Disc 2",          False),
    (42,  "Regen",     "Fishermans Horizon",              "Disc 2",          False),
    (43,  "Full-life", "FH Factory",                      "Disc 2",          False),
    (44,  "Ultima",    "FH Mayor's Residence",            "Disc 2",          False),
    (45,  "Thundaga",  "FH Great Salt Lake",              "Disc 3",          False),
    (46,  "Meteor",    "FH Great Salt Lake",              "Disc 3",          False),
    (47,  "Curaga",    "Esthar City",                     "Disc 3",          False),
    (48,  "Blizzard",  "Esthar City",                     "Disc 3",          False),
    (49,  "Quake",     "Odine's Laboratory",              "Disc 3",          False),
    (50,  "Tornado",   "Esthar City",                     "Disc 3",          False),
    (51,  "Double",    "Odine's Laboratory Lobby",        "Disc 3",          False),
    # 52 = Pain / ??? (skipped)
    (53,  "Flare",     "Odine's Laboratory Lobby",        "Disc 3",          False),
    (54,  "Stop",      "Sorceress Memorial",              "Disc 3",          False),
    # 55 = Stop / ??? (skipped)
    (56,  "Life",      "Tears' Point",                    "Disc 3",          False),
    (57,  "Reflect",   "Tears' Point",                    "Disc 3",          False),
    (58,  "Death",     "Lunatic Pandora Laboratory",      "Disc 2",          True),
    (59,  "Holy",      "Centra Excavation Site",          "Disc 2",          False),
    (60,  "Silence",   "Centra Excavation Site",          "Disc 2",          False),
    (61,  "Ultima",    "Centra Excavation Site",          "Disc 2",          False),
    (62,  "Confuse",   "Centra Excavation Site",          "Disc 2",          False),
    (63,  "Break",     "Lunatic Pandora",                 "Disc 3",          False),
    (64,  "Meteor",    "Lunatic Pandora",                 "Disc 3",          False),
    (65,  "Curaga",    "Lunatic Pandora",                 "Disc 3",          False),
    # 66 = Slow / ??? (skipped)
    (67,  "Curaga",    "Edea's House Bedroom",            "Disc 2",          False),
    # 68, 69 = Flare, Holy / ??? (skipped)
    (70,  "Sleep",     "Centra Excavation Site",          "Disc 2",          False),
    (71,  "Confuse",   "Centra Excavation Site #2",       "Disc 2",          False),
    (72,  "Aero",      "Centra Ruins",                    "Disc 2",          False),
    (73,  "Drain",     "Centra Ruins",                    "Disc 2",          False),
    (74,  "Pain",      "Centra Ruins",                    "Disc 2",          False),
    (75,  "Thundaga",  "Trabia Garden Front Gate",        "Disc 2",          False),
    (76,  "Zombie",    "Trabia Garden Cemetery",          "Disc 2",          False),
    (77,  "Aura",      "Trabia Garden Festival Stage",    "Disc 2",          False),
    (78,  "Ultima",    "Shumi Village Entrance",          "Disc 2",          False),
    (79,  "Blizzaga",  "Shumi Village",                   "Disc 2",          False),
    (80,  "Firaga",    "Shumi Village Residence",         "Disc 2",          False),
    # 81 = Tornado / ??? (skipped)
    (82,  "Holy",      "White SeeD Ship Cabin",           "Disc 2",          True),
    (83,  "Cura",      "Ragnarok Aisle",                  "Disc 3",          False),
    (84,  "Life",      "Ragnarok Aisle",                  "Disc 3",          False),
    (85,  "Full-life", "Ragnarok Hangar",                 "Disc 3",          False),
    (86,  "Dispel",    "Deep Sea Research Center",        "Disc 3",          False),
    (87,  "Esuna",     "Deep Sea Research Center",        "Disc 3",          False),
    (88,  "Triple",    "Deep Sea Deposit",                "Disc 3",          False),
    (89,  "Ultima",    "Deep Sea Deposit",                "Disc 3",          False),
    (90,  "Meltdown",  "Lunar Base Pod",                  "Disc 3",          True),
    (91,  "Meteor",    "Lunar Base Residential Zone",     "Disc 3",          True),
    # 92-99 = ??? / Wilderness (unknown slots, skipped)
    (100, "Flare",     "Ultimecia Castle",                "Disc 4",          False),
    (101, "Curaga",    "Ultimecia Castle Storage Room",   "Disc 4",          False),
    (102, "Cura",      "Ultimecia Castle Passageway",     "Disc 4",          False),
    # 103, 104 = Scan, Esuna / ??? (skipped)
    (105, "Slow",      "Ultimecia Castle Courtyard",      "Disc 4",          False),
    (106, "Dispel",    "Ultimecia Castle Chapel",         "Disc 4",          False),
    (107, "Stop",      "Ultimecia Castle Clock Tower",    "Disc 4",          False),
    (108, "Life",      "Ultimecia Castle Master Room",    "Disc 4",          False),
    # 109 = Flare / ??? (skipped)
    (110, "Aura",      "Ultimecia Castle Wine Cellar",    "Disc 4",          False),
    (111, "Holy",      "Ultimecia Castle Treasure Room",  "Disc 4",          False),
    (112, "Meteor",    "Ultimecia Castle Terrace",        "Disc 4",          False),
    (113, "Meltdown",  "Ultimecia Castle Art Gallery",    "Disc 4",          False),
    (114, "Ultima",    "Ultimecia Castle Armory",         "Disc 4",          False),
    (115, "Full-life", "Ultimecia Castle Prison Cell",    "Disc 4",          False),
    (116, "Triple",    "Ultimecia Castle Clock Tower",    "Disc 4",          False),
]

DRAW_POINT_LOCATIONS: list[LocationData] = [
    LocationData(f"Draw Point: {place} ({spell})", 300 + slot, region,
                 (("draw", slot),), missable=missable, group="draw")
    for slot, spell, place, region, missable in DRAW_POINT_TABLE
]

LOCATION_TABLE += DRAW_POINT_LOCATIONS

# --- World-map draw point checks (option-gated): offsets 1000 + (slot-128) ---
# Added 2026-09-02. The savemap draw array is 64 bytes = 256 slots: 32 bytes
# field (slots 0-127, table above) + 32 bytes world map (slots 128-255, Hyne
# SaveData.h "draw_points[64] // 32 field, 32 worldmap"). Slot rows from the
# ff8-memory README "Field - Draw Points" table continuation (bytes 0x18FEA4C+,
# EN column, row order == slot order) — same source and encoding the field
# half was live-verified against; three "???" slots (135/165/255) skipped.
# World draw points are INVISIBLE in-game (no sparkle), which is exactly why
# they make good tracker pins. They refill over time; the trigger fires on the
# first draw (state leaves Full) like every field point. Nothing here is
# missable — the world map stays open through Disc 3 (the Disc 4 lockout is
# handled by regioning, per the rest of the table). Region errs late for
# island/archipelago spots that realistically need the Ragnarok.
# (slot, spell, place, region)
WORLD_DRAW_POINT_TABLE: list[tuple[int, str, str, str]] = [
    # Balamb continent
    (128, "Cure",      "Alcauld Plains",           "Fire Cavern"),
    (129, "Esuna",     "Alcauld Plains",           "Fire Cavern"),
    (245, "Blizzard",  "Alcauld Plains",           "Fire Cavern"),
    (246, "Cure",      "Alcauld Plains",           "Fire Cavern"),
    # Timber / Dollet region
    (130, "Thunder",   "Mandy Beach",              "Timber"),
    (131, "Fira",      "Lanker Plains",            "Timber"),
    (132, "Thundara",  "Shenand Hill",             "Timber"),
    (166, "Break",     "Shenand Hill",             "Timber"),
    (134, "Blizzard",  "Yaulny Canyon",            "Timber"),
    (136, "Cure",      "Hasberry Plains",          "Timber"),
    (138, "Cura",      "Hasberry Plains",          "Timber"),
    (178, "Pain",      "Hasberry Plains",          "Timber"),
    (137, "Water",     "Malgo Peninsula",          "Timber"),
    (164, "Quake",     "Holy Glory Cape",          "Timber"),
    (177, "Drain",     "Holy Glory Cape",          "Timber"),
    (163, "Aura",      "Long Horn Island",         "Disc 3"),
    # Galbadia continent
    (133, "Blizzara",  "Monterosa Plateau",        "Galbadia"),
    (141, "Shell",     "Monterosa Plateau",        "Galbadia"),
    (143, "Aero",      "Monterosa Plateau",        "Galbadia"),
    (144, "Bio",       "Monterosa Plateau",        "Galbadia"),
    (179, "Berserk",   "Monterosa Plateau",        "Galbadia"),
    (182, "Meltdown",  "Monterosa Plateau",        "Galbadia"),
    (247, "Dispel",    "Monterosa Plateau",        "Galbadia"),
    (139, "Esuna",     "Great Plains of Galbadia", "Galbadia"),
    (248, "Confuse",   "Great Plains of Galbadia", "Galbadia"),
    (140, "Scan",      "Wilburn Hill",             "Galbadia"),
    (180, "Float",     "Wilburn Hill",             "Galbadia"),
    (142, "Haste",     "Dingo Desert",             "Galbadia"),
    (183, "Zombie",    "Lallapalooza Canyon",      "Galbadia"),
    (181, "Zombie",    "Rem Archipelago",          "Disc 3"),
    (145, "Life",      "Winhill Bluffs",           "Galbadia"),
    (162, "Reflect",   "Humphrey Archipelago",     "Disc 3"),
    # Centra continent
    (146, "Demi",      "Centra Crater",            "Disc 2"),
    (147, "Protect",   "Nectar Peninsula",         "Disc 2"),
    (148, "Holy",      "Cape of Good Hope",        "Disc 2"),
    (149, "Thundaga",  "Almaj Mountains",          "Disc 2"),
    # Trabia continent
    (152, "Regen",     "Winter Island",            "Disc 2"),
    (153, "Blizzaga",  "Winter Island",            "Disc 2"),
    (172, "Quake",     "Winter Island",            "Disc 2"),
    (173, "Sleep",     "Winter Island",            "Disc 2"),
    (174, "Silence",   "Winter Island",            "Disc 2"),
    (154, "Confuse",   "Hawkwind Plains",          "Disc 2"),
    (155, "Flare",     "Bika Snowfield",           "Disc 2"),
    (156, "Dispel",    "Bika Snowfield",           "Disc 2"),
    (157, "Slow",      "Bika Snowfield",           "Disc 2"),
    (175, "Flare",     "Bika Snowfield",           "Disc 2"),
    (158, "Quake",     "Vienne Mountains",         "Disc 2"),
    (176, "Death",     "Albatross Archipelago",    "Disc 3"),
    # Esthar continent
    (150, "Stop",      "Shalmal Peninsula",        "Disc 3"),
    (151, "Firaga",    "Kashkabald Desert",        "Disc 3"),
    (159, "Curaga",    "West Coast",               "Disc 3"),
    (160, "Tornado",   "Nortes Mountains",         "Disc 3"),
    (161, "Full-life", "Nortes Mountains",         "Disc 3"),
    (167, "Meteor",    "Grandidi Forest",          "Disc 3"),
    (168, "Ultima",    "Grandidi Forest",          "Disc 3"),
    (169, "Triple",    "Grandidi Forest",          "Disc 3"),
    (171, "Blind",     "Grandidi Forest",          "Disc 3"),
    (170, "Confuse",   "Millefeuille Archipelago", "Disc 3"),
    (249, "Meteor",    "Great Plains of Esthar",   "Disc 3"),
    (250, "Double",    "Great Plains of Esthar",   "Disc 3"),
    (251, "Double",    "Great Plains of Esthar",   "Disc 3"),
    (252, "Holy",      "Great Plains of Esthar",   "Disc 3"),
    (253, "Flare",     "Sollet Mountains",         "Disc 3"),
    (254, "Ultima",    "Abadan Plains",            "Disc 3"),
    # Island Closest to Heaven (slots 184-211, row order preserved)
    (184, "Tornado", "Island Closest to Heaven", "Disc 3"),
    (185, "Quake",   "Island Closest to Heaven", "Disc 3"),
    (186, "Meteor",  "Island Closest to Heaven", "Disc 3"),
    (187, "Holy",    "Island Closest to Heaven", "Disc 3"),
    (188, "Flare",   "Island Closest to Heaven", "Disc 3"),
    (189, "Aura",    "Island Closest to Heaven", "Disc 3"),
    (190, "Ultima",  "Island Closest to Heaven", "Disc 3"),
    (191, "Triple",  "Island Closest to Heaven", "Disc 3"),
    (192, "Life",    "Island Closest to Heaven", "Disc 3"),
    (193, "Tornado", "Island Closest to Heaven", "Disc 3"),
    (194, "Quake",   "Island Closest to Heaven", "Disc 3"),
    (195, "Meteor",  "Island Closest to Heaven", "Disc 3"),
    (196, "Holy",    "Island Closest to Heaven", "Disc 3"),
    (197, "Flare",   "Island Closest to Heaven", "Disc 3"),
    (198, "Aura",    "Island Closest to Heaven", "Disc 3"),
    (199, "Ultima",  "Island Closest to Heaven", "Disc 3"),
    (200, "Triple",  "Island Closest to Heaven", "Disc 3"),
    (201, "Life",    "Island Closest to Heaven", "Disc 3"),
    (202, "Tornado", "Island Closest to Heaven", "Disc 3"),
    (203, "Quake",   "Island Closest to Heaven", "Disc 3"),
    (204, "Meteor",  "Island Closest to Heaven", "Disc 3"),
    (205, "Holy",    "Island Closest to Heaven", "Disc 3"),
    (206, "Flare",   "Island Closest to Heaven", "Disc 3"),
    (207, "Aura",    "Island Closest to Heaven", "Disc 3"),
    (208, "Ultima",  "Island Closest to Heaven", "Disc 3"),
    (209, "Triple",  "Island Closest to Heaven", "Disc 3"),
    (210, "Life",    "Island Closest to Heaven", "Disc 3"),
    (211, "Ultima",  "Island Closest to Heaven", "Disc 3"),
    # Island Closest to Hell (slots 212-244, row order preserved)
    (212, "Meteor", "Island Closest to Hell", "Disc 3"),
    (213, "Holy",   "Island Closest to Hell", "Disc 3"),
    (214, "Flare",  "Island Closest to Hell", "Disc 3"),
    (215, "Aura",   "Island Closest to Hell", "Disc 3"),
    (216, "Ultima", "Island Closest to Hell", "Disc 3"),
    (217, "Triple", "Island Closest to Hell", "Disc 3"),
    (218, "Life",   "Island Closest to Hell", "Disc 3"),
    (219, "Meteor", "Island Closest to Hell", "Disc 3"),
    (220, "Holy",   "Island Closest to Hell", "Disc 3"),
    (221, "Triple", "Island Closest to Hell", "Disc 3"),
    (222, "Aura",   "Island Closest to Hell", "Disc 3"),
    (223, "Ultima", "Island Closest to Hell", "Disc 3"),
    (224, "Triple", "Island Closest to Hell", "Disc 3"),
    (225, "Life",   "Island Closest to Hell", "Disc 3"),
    (226, "Meteor", "Island Closest to Hell", "Disc 3"),
    (227, "Holy",   "Island Closest to Hell", "Disc 3"),
    (228, "Flare",  "Island Closest to Hell", "Disc 3"),
    (229, "Aura",   "Island Closest to Hell", "Disc 3"),
    (230, "Ultima", "Island Closest to Hell", "Disc 3"),
    (231, "Triple", "Island Closest to Hell", "Disc 3"),
    (232, "Life",   "Island Closest to Hell", "Disc 3"),
    (233, "Meteor", "Island Closest to Hell", "Disc 3"),
    (234, "Triple", "Island Closest to Hell", "Disc 3"),
    (235, "Flare",  "Island Closest to Hell", "Disc 3"),
    (236, "Aura",   "Island Closest to Hell", "Disc 3"),
    (237, "Ultima", "Island Closest to Hell", "Disc 3"),
    (238, "Triple", "Island Closest to Hell", "Disc 3"),
    (239, "Life",   "Island Closest to Hell", "Disc 3"),
    (240, "Meteor", "Island Closest to Hell", "Disc 3"),
    (241, "Holy",   "Island Closest to Hell", "Disc 3"),
    (242, "Flare",  "Island Closest to Hell", "Disc 3"),
    (243, "Aura",   "Island Closest to Hell", "Disc 3"),
    (244, "Ultima", "Island Closest to Hell", "Disc 3"),
]

# Duplicate spell+place pairs (the islands especially) get " #2"/" #3" name
# suffixes in slot order so every location name stays unique.
WORLD_DRAW_POINT_LOCATIONS: list[LocationData] = []
_wdp_seen: dict[str, int] = {}
for _slot, _spell, _place, _region in sorted(WORLD_DRAW_POINT_TABLE):
    _base = f"Draw Point: {_place} ({_spell})"
    _n = _wdp_seen.get(_base, 0) + 1
    _wdp_seen[_base] = _n
    _name = _base if _n == 1 else f"Draw Point: {_place} ({_spell} #{_n})"
    WORLD_DRAW_POINT_LOCATIONS.append(
        LocationData(_name, 1000 + (_slot - 128), _region,
                     (("draw", _slot),), group="world_draw"))

LOCATION_TABLE += WORLD_DRAW_POINT_LOCATIONS

LOCATION_DATA_BY_NAME: dict[str, LocationData] = {d.name: d for d in LOCATION_TABLE}
location_name_to_id: dict[str, int] = {d.name: BASE_ID + d.id_offset for d in LOCATION_TABLE}
assert len(LOCATION_DATA_BY_NAME) == len(LOCATION_TABLE), "duplicate location name"
assert len({d.id_offset for d in LOCATION_TABLE}) == len(LOCATION_TABLE), "duplicate offset"

DRAW_POINT_NAMES = {d.name for d in DRAW_POINT_LOCATIONS}
WORLD_DRAW_POINT_NAMES = {d.name for d in WORLD_DRAW_POINT_LOCATIONS}

# group -> region -> location names, for create_regions ("core" is always on;
# the other groups are gated by their option toggles).
LOCATIONS_BY_GROUP: dict[str, dict[str, list[str]]] = {}
for _d in LOCATION_TABLE:
    LOCATIONS_BY_GROUP.setdefault(_d.group, {}).setdefault(_d.region, []).append(_d.name)

# Hint groups ("/hint_location group") exposed via World.location_name_groups.
_GROUP_DISPLAY = {"draw": "Draw Points", "world_draw": "World Draw Points",
                  "tt": "Triple Triad",
                  "boss_extra": "Optional Bosses", "cards": "Rare Cards",
                  "sidequest": "Sidequests", "magazine": "Magazines",
                  "stats": "Stat Ladders", "abilities": "GF Abilities"}
location_name_groups: dict[str, set[str]] = {
    display: {d.name for d in LOCATION_TABLE if d.group == key}
    for key, display in _GROUP_DISPLAY.items()
}
location_name_groups["GFs"] = {d.name for d in LOCATION_TABLE if d.gf is not None}
location_name_groups["Story"] = {d.name for d in LOCATION_TABLE
                                 if d.group == "core" and d.gf is None}
