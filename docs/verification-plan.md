# Pre-Playthrough Verification Plan (2026-08-28)

Goal: burn down every `VERIFY` before committing 40+ hours to the real
playthrough, using saves and short targeted sessions instead of play time —
then make the playthrough itself un-wasteable by recording everything.

Research provenance: docs/research/ + the 2026-08-28 sweep (storyId.md /
FF8Autosplitter.asl / Hyne source / FF8ModdingWiki IDA+JSM variable table /
save-logistics survey). Tools referenced below all live in `tools/`.

## Status (2026-08-28)

- Save root is **OneDrive-redirected** on the dev machine:
  `<Documents>\Square Enix\FINAL FANTASY VIII Steam\user_<steam id>` (with
  `Documents` living under the OneDrive known-folder redirect).
- Phase 0: backup done (`F:\ff8_save_backups\2026-08-28` + the earlier
  `... Steam - Copy` in OneDrive). Hyne 1.11.4, FF8-Save-Swap, and
  `ff8_en_v1.6.CT` installed under `thirdparty\` (gitignored).
  Steam Cloud for FF8: toggled OFF by hand 2026-08-28. OneDrive: not
  actually syncing (dead redirect path) — no hazard, see step 2b.
- Phase 1: **DONE** — fresh 298-location seed in `output\live_test2`,
  self-test 16 PASS / 0 FAIL / 4 SKIP. All skips were pre-polluted live
  session state (battles=239, Squall weapon id, magazine owned, Phoenix
  dream bit), and those same trigger families fired correctly during the
  connect-scan, so every family is verified. Optional: re-run once on a
  clean save for a 20/20. Do NOT save the polluted live session to a slot.
- Phase 1 re-run 2026-08-31 on the 299-location world (bits_ge seal/weapon
  triggers, bit-7 card counting): **19 PASS / 0 FAIL / 1 SKIP** (lamp already
  owned) on a clean early save staged as slot2_save05 — armed hands-off by
  the new `tools/await_selftest.py` (waits for game field-stable, then runs
  the self-test). Two client bugs found+fixed on the way: the sidecar was
  keyed by `CommonContext.seed_name`, which is always None for patchless
  clients → ONE `FF8AP/None_<slot>.json` shared across all seeds (a fresh
  seed inherited max_moment 4050 / applied 300); now keyed by
  `server_seed_name`. And the headerless-save "migrate from the sidecar"
  path mis-seeded any foreign/library save once the session had granted
  items (silently skipped the starting GFs — only GF re-assert masked it);
  removed — no header now always means deliver from item 0. Real-engine
  bonus: a random battle win (enc 514) was correctly credited by the new
  module-3/results-pulse tracking. Note: bodcap "Leaving Garden" saves land
  on the WORLD MAP (module 2) — walk into a town before running the test.
- Phase 2: bodcap's ECM/EzCM menu-save pack (speedrun.com/ff8/resources)
  acquired → `F:\ff8_saves\library\` (ecm-kiros / ecm-ward / ezcm, ~30
  saves each, pre-Dollet → After Tiamat; see INDEX.md there for the
  save-number → run-point map). Covers all 5 Laguna dreams, prison,
  Balamb liberation, Esthar, sorceresses, castle-after-Tiamat. PLUS:
  31 GameFAQs DexDrive cards converted by the new `tools/psx2steam.py`
  (ports Hyne's formats: LZS container, savemap layout, the game's
  bugged CRC table with crcTab[255]=0) → 182 more saves in
  `library\gamefaqs\` with location-labeled index.csv. All former gaps
  closed: pre-Omega + pre-Ultimecia (Clock Tower / Master Room lv100),
  kitchen-sink endgame w/ CC done, castle entry, each disc end, Centra
  staging for Odin/Tonberry; Deep Sea reachable from Ragnarok saves.
  Converted saves are CRC-verified but not yet load-tested in-game.

## Phase 0 — one-time setup (~30 min)

1. **Back up** `Documents\Square Enix\FINAL FANTASY VIII Steam\user_<id>\`.
2. **Disable Steam Cloud** for FF8 (app 39150) — cloud sync resurrects/clobbers
   modified saves and will fight the save library. (Library → FF8 →
   Properties → General → uncheck "Keep games saves in the Steam Cloud".)
   2b. ~~Tame OneDrive~~ — checked 2026-08-28: the OneDrive-redirected
   save path is a leftover known-folder redirect; OneDrive is not running and
   no account is linked, files are plain local. No sync hazard. (If OneDrive
   is ever re-linked, revisit: pin the save folder + pause sync during swaps.)
3. Install **Hyne** (github.com/myst6re/hyne, v1.11+). It opens PSX
   (.gme/.mcr) and PC saves, converts to Steam 2013 format, and
   `File → Sign saves for the Cloud` re-signs `metadata.xml`
   (MD5(save+userID)). Note: the game itself loads *unsigned* saves fine —
   signing only matters if Cloud is on.
4. Get **FF8-Save-Swap** (github.com/ff8-speedruns/FF8-Save-Swap): hot-swaps
   any save from a library folder into `slot2_save28` while the game runs —
   no restart between test saves.
5. Get the **community CE table** (github.com/ff8-speedruns/ff8-memory
   releases, `ff8_en_v1.6.CT`): gives save-anywhere (`+0x18E490B` = 1),
   no-encounters (`+0x18FF6D8` = 8), and next-field teleport (`+0x18D2FC0`)
   for fast positioning.
6. **Never launch Chocobo World** during any of this (its save sync is the
   one fragile thing when using foreign saves).

## Phase 1 — extended self-test (~10 min, no saves needed)

Generate a test seed with **all option groups on**, start server + client,
stand on a field screen, run:

    ..\.venv\Scripts\python.exe ..\tools\live_selftest.py --connect localhost:38281 --name <slot>

Now covers every trigger family (state writes + fake battles + DeathLink +
item interception). Anything FAIL here is a client bug — fix before touching
the game further. This validates the snapshot-refactored read path.

## Phase 2 — build the save library (~1-2 hours)

Sources, best first:
1. **FF8 speedrun Discord** (via tools.ff8.wiki / speedrun.com/ff8): the
   practice-save pack used with FF8-Save-Swap — already 2013-format,
   segmented across the whole run.
2. **GameFAQs PC saves** (gamefaqs.gamespot.com/pc/197342-final-fantasy-viii/saves):
   a collection with "saves at every key section, each disc".
3. **GameFAQs PSX DexDrive saves** (/ps/197343-.../saves): end-of-disc-4 and
   Ultimecia Castle saves; open in Hyne → convert to Steam PC → sign.

Target points (validate each on load with `savemap_diff.py capture <label>` —
moment/field are stored with the capture): pre-Dollet, post-Timber,
pre/post each Laguna dream, Disc 2 start (prison), post-Balamb-liberation,
Disc 3 start, pre-Tonberry-King grind (Centra Ruins), pre-Odin, ~20 Tonberries
killed, pre-Ultima-Weapon, Disc 4 castle entry, castle with N seals broken,
pre-Ultimecia, endgame kitchen-sink save (all GFs/cards/quests done).

### Phase 3/4 progress (2026-08-28 live session)

- Converted GameFAQs save loaded in-game → **psx2steam converter validated**.
- CONFIRMED via the kitchen-sink save (values as predicted): CC bits 0x3F
  (Kadowaki bit1 + King bit5), dream byte 0x2E (Odin/Phoenix/Gilgamesh),
  tonberry_king=1, Queen-of-Cards=5, PuPu 0xFC, seed_tests=30,
  battles_won=773. Timber Maniacs u16=0x3FFD.
- SEAL_COUNT 0x18FEB06 read 0xFF on the all-seals save → likely a
  **bitmask** (8 seals), not a count. Compare against a castle-entry save
  (33864-blk03) before wiring the ladder.
- MODULE_DISPATCH enum complete: 0 title, 1 field, 2 worldmap, 3 battle,
  4 results, 100 victory transition. Save-file preview header (locID/disc
  at file 388+) is NOT mirrored into live memory — only MAIN is.
- Phase 4 #2 DONE (the hour-40 test): real Ultimecia kill from the
  kitchen-sink save. Phases 1-3 tracked perfectly; **FINAL_BLOW 0x1927C30 is
  garbage live** (read 52/62; ==1 edge never seen at 2 Hz) — the old kill
  detection MISSED the win. Fixed: phase 3 + final battle exited alive
  (enc 511 can't be escaped; post-battle ally HPs zero only on a wipe) =
  goal. Goal StatusUpdate sent + accepted ("completed their goal"); note
  release=auto then auto-releases all remaining slot locations (expected).
- Phase 4 #1 DONE: DeathLink receive in a real battle → real game-over.
  Three client bugs found+fixed on the way: in_battle() read the
  results-screen flag (dead in real combat), is_safe() allowed mid-battle
  writes, and a single kill_party write loses the race with battle init
  (fix: re-assert the wipe every tick until the battle ends). Win credit
  now requires the results pulse (escapes can't fake boss kills).

### Phase 3 — OFFLINE results (2026-08-31, `tools/save_scan.py`)

The save library turned out to be an oracle: a PC save's MAIN block (offset
464, 4944 B) is the exact image the game loads to the live savemap, so
`live = 0x18FDCA8 + (pos - 464)` and every VERIFY byte can be read from all
273 saves at once (`save_scan.py table/vars/corr/diff/check`). Mapping
cross-checked on gil, game_moment, koyok_quest and cards_rare. Findings:

| item | result |
|---|---|
| castle seals `0x18FEB06` | **BITMASK**, not a count: 0x00 castle entry, 0x21 two-seal speedrun saves, 0xF7/0xEB partial, 0xFF all. Ladder now `bits_ge` popcount. |
| TT commons `0x18FEF38+` | bit 7 = "obtained once", low 7 = held qty; bit 7 ⊇ qty>0 in all saves (0 violations). Unique-card ladder now counts bit 7. |
| weapon ids `char+0x09` | all 273 saves inside per-character ranges; **but** equipped id can go *down*. New signal: `misc1.unlocked_weapons` u32 `0x18FE750`, bit i = weapon i ever made (base bits always set, 0 inconsistencies, no-magazine saves carry every tier passed). Remodel checks now read it. |
| dream byte `0x18FE97A` | b1 Odin, b2 Phoenix, b3 Gilgamesh (clears Odin — never coexist), b4 Angelo disabled (Rinoa comatose), b5 Angel Wing. Odin check gained an Odin\|Gilgamesh catch-up trigger. |
| tonberry flag `0x18FE944` | =1 in exactly the 52 legit saves with GF Tonberry (+≥20 kills at misc2+24); the 15 counterexamples are hacked saves (11839/1175: lv100 at 0:00). |
| battles_won `0x18FE934` | == misc3.victory_count (var 20) in 270/273 saves; misc2+18 is the real escape counter. Consistent. |
| seed_test_level `0x18FE98B` | 0..30, 30 on every kitchen-sink save. Consistent. |
| CC Kadowaki/King `0x18FEB93` b1/b5 | Hyne's CC encoding (0x021F/0x221F) + data agree. **Joker = bit 4** ("joker BGU CC"): set in exactly the 50 legit saves owning the Leviathan card. Check added. |
| Queen of Cards `0x18FEAE4` | 0..5 monotonic within series; disc-4 players can get the chain cards from CC-Ragnarok with var=0 (so it stays EXCLUDED). |
| PuPu/UFO `0x18FEF2D` | b2-5 sightings, b6 ⇔ misc2.ufo==1 (10/10), b7 ⇒ all sightings. |
| obel_quest bits | milestone bits coherent across 8 distinct states (e.g. eldbeak/all-rocks/minde/mordor together on completed saves). |
| Laguna dream 3 | var 387 = 0x1A after the Winhill dream (395) — it is the dream var, **not** the vase quest. Vase var still unknown. |
| chocobo forests vars 616-622 | 7 vars = 7 forests, values only {0, 0x02, 0x20, 0x40, 0x80}; 0x80 = solved (all seven set in every completionist save; the only partial-solve saves have exactly one var at 0x80). SHIPPED 2026-09-02 as a solved-count ladder (`byteflag_ge`); var→forest identity still needs one live diff before per-forest checks. |
| Shumi vars 607-615 | 607 goes 0x20→0x40→0x80 across a series (quest stages); labels unknown. Deferred. |
| Joker var 460 candidate | refuted: nonzero at disc 1 moment 145. |
| free vars 753-1023 / AP header | zero in all 273 saves. |

Still live-only: draw-point first-draw, boss first-fire edges, magic-stock
menu visibility, Omega goal, Tonberry King encounter ID (none exists — flag
only), mid-game GF usability. Hacked saves to ignore in future scans:
11839-*, 1137, 1175, 4057-* (all rares at disc 1).

### Phase 3 — stat-check pass (2026-08-31, same-day follow-up)

Second offline sweep for the Zell-Duel + stat-ladder groups (41 new
locations, 299 → 340). Full field-by-field survey with verdicts:
`docs/research/savemap-measurables.md`. Findings:

| item | result |
|---|---|
| Zell duels `0x18FE76E` (LIMITB.zell u16) | innate mask 0x004F set in all 273 saves, nothing past bit 9; learned bits 4/5/7/8/9 each a strict subset of Combat King 001-005 ownership. Five sidequest checks added. |
| char level formula | flat 1000 EXP/level (legit maxed saves at exactly 99000; Hyne PersoEditor agrees). Save-header "level" byte is the **party average**, not Squall's. Squall ladder = `u32_ge` on his exp. |
| `magic_drawn_once` misc2+52 | bit = spell id − 1; Fire bit in 262/273 saves, no bits ≥ 56; draw points count (FH Ultima point ⇒ Ultima bit, 20/20). AP magic filler can't set bits. Kinds-ladder + 8 marquee first-draw checks added. |
| `ennemy_scanned_once` misc2+60 | popcount 0..134, median player never scans → modest tiers 5/10/20/30. Which action sets a bit: VERIFY live. |
| counters | battle_escaped (misc2+18) 0..180; tomberry_vaincus 0 except quest saves (20/21/23); steps (var 4) fresh ~4k / every disc-2 save ≥147k; monster_kills (var 68) ≥ Σkills[8] in all saves. Tiers set from per-disc percentiles. |
| rejected | payslip (semantics murky), seedExp (rank decays — non-monotonic; REVERSED 2026-09-01: AP's check latch makes decay harmless, see savemap-measurables.md), gils/dream_gils (wallet, AP-fillable), ko[8] (perverse incentive), per-char kills (duplicate axis), GF completeAbilities (AP-granted GFs arrive with default sets — needs beyond-default masks first). |
| anomaly | 4 saves drew draw-point slot 49 ("Quake, Odine's Lab") without Quake's magic bit, while slot 44 cross-validates 20/20 — slot 49's identity is suspect; check on the next live session. |

### Phase 3 — Triple Triad pass (2026-08-31, third same-day sweep)

18 more locations (340 → 358, `tt` group 18 → 36). Findings:

| item | result |
|---|---|
| `tt_rules[8]` `0x18FEAC8` | region order Balamb/Galbadia/Trabia/Centra/Dollet/FH/LunarGate/Esthar, bit 3 = Random (Hyne TTriadEditor). Virgin bytes unanimous across all 19 moment<=50 saves: 01/02/0C/0E/88/90/DF/C0. Spreading only ADDS bits → cleared virgin bit = abolished. Dollet Random cleared in 60 saves, Trabia 54, Centra 29, Lunar Gate 15, all four 12. New `bits_clear` trigger (moment>=20 init guard). |
| `tt_bgu_victory_count` var 478 | bimodal: 0 on non-card saves, 30-129 on every CC-progress save → Garden card-wins ladder 15/40/100. |
| card level sets | 11 commons per level in Hyne list order; set completion 175/147/144/138/35/106/72 by level. PuPu = card 47 (level 5, one-chance) → Level 5 set EXCLUDED. New `cards_seen_range` trigger (bit-7 flags, refining-proof). |
| unique tiers | 85 kinds in 92 saves, 100 in 54, all 110 in 30 → tiers added; 110 EXCLUDED (needs missable rares + PuPu), region Disc 4 (CC-Ragnarok recovery). |
| rejected | `tt_defeat_count`/`tt_egality_count` (throwable; egality also sits at the snapshot span boundary), trade rules (All = winner-takes-all, unwanted), `card_locations[33]` (churns). |

### Phase 3 — GF ability pass (2026-09-01, offline)

71 more locations (358 → 429, new `abilities` group behind `gf_ability_checks`).

| item | result |
|---|---|
| GF `completeAbilities[16]` at record +20 | bit i = Hyne ability id i, confirmed by decoding: Quezacotl default = Mag-J/Magic/GF/Draw/Item, Doomtrain default includes Junk Shop, Bahamut's Abilityx4/Str+60%/Mag+60%/Forbid Mag-RF, Cactuar's five Bonuses, Eden's Devour — all matching the in-game starting sets. |
| default masks | **unanimous**: one not-yet-owned mask per GF across all 273 saves (memory.GF_ABILITY_DEFAULTS; `ff8/test/test_abilities.py` re-checks the library when present). Owned records climb from default to 22 bits. A multiworld-granted GF therefore arrives at exactly default → "beyond default" never fires on receipt. |
| signature abilities (49) | each learned in 25-95% of saves owning the GF (Card 230/240, Card Mod 219/240, Enc-None 139/170, Auto-Haste 30/50, Auto-Reflect 35/141 is the rarest). `flag_bit` on the mask byte. |
| mastery (16) | all 22 natural abilities (Hyne innateAbilities) — 45-88% of owners for Disc 1-2 GFs, 50-88% for the late ones; new `bits_all(off,len,mask)` trigger. Normal checks in Disc 3. |
| party ladder | abilities beyond default summed over 16 GFs (max 244): Disc 1 p50 10 / p75 47, Disc 2 p50 94, finishers ~230 → tiers 10/25/50/100/150 normal, 200 EXCLUDED. New `gf_abilities_ge(n)` trigger. |
| logic | every GF-specific check requires the "GF <name>" item (`requires_gf` on LocationData, set_rules). |
| live VERIFY | the +1 edge on a real learn (flight recorder will show the mask byte diff at the post-battle AP screen). Ability-teaching items set the same bits — expected, counts as earned. |

### Phase 3 — per-enemy scan checks: BLOCKED (2026-09-01 library finding)

`misc2.ennemy_scanned_once[20]` is **not** a clean per-enemy flag in Hyne's
enemy-list order. Splitting the library by source: the 88 bodcap PC practice
saves carry zero bits; 115 of 150 GameFAQs (PSX-origin) saves carry bits, and
the dominant ones — 44 "Abyss Worm", 59 "Imp", 26 "Elastoid", 107 "Right
Probe", 67 "Bahamut", 0 "Dummy", 22, 33, 77 "NORG", 3, 34 "Gerogero", 31 —
are already set in the very first save of the game (Disc 1, moment 33,
dormitory), i.e. at new game on PSX. The user's PC saves show a Disc 1 save
with bits 19/37/48/62 ("Blitz/Grand Mantis/Malboro/Minotaur" by enemy id —
impossible that early), so the bit index is some other page order (Hyne's own
TODO: "scan pages for some ennemies"). Consequences: (1) per-enemy scan checks
need one live diff — cast Scan on a Bite Bug and read the flipped bit (the
flight recorder catches it) — before any name can be attached; (2) the
existing "Enemies Scanned" popcount ladder stays valid on PC (new-game bytes
are zero in every PC save incl. the campaign's first recorder snapshot) but
would misfire on a PSX-converted save — acceptable, those are research saves.

## Phase 3 — offset verification by savemap diff (~2-3 hours total)

Method per offset: load save A → `savemap_diff.py capture before` → do the
one thing (or swap to save B) → `savemap_diff.py watch --baseline before`
(or `capture after` + `diff before after`). The output names every byte that
moved. `/ff8verify` in the client prints the same fields live.

| VERIFY item | Offset | How to verify | Est. |
|---|---|---|---|
| battles_won | 0x18FE934 | win any battle, watch +1; cross-check Hyne's figure | 5 min |
| seed_test_level | 0x18FE98B | pass one SeeD written test in the menu | 5 min |
| weapon IDs | char+0x09 | remodel any weapon in a junk shop; expect base [0,7,11,15,19,24] pre-remodel | 10 min |
| TT commons semantics | 0x18FEF38+ | win any common card, watch the qty byte | 5 min |
| dream byte (cameos) | 0x18FE97A | load post-Odin save: expect bit1; endgame save: bits 1/2/3 | 5 min |
| tonberry_king_flag | 0x18FE944 | load pre/post-Tonberry-King saves and diff; or kill him from a positioned save (~20 min fight) | 5-30 min |
| castle seal count | 0x18FEB06 | castle saves with different seals broken; or break one live | 10 min |
| CC Kadowaki/King bits | 0x18FEB93 | endgame save with CC done: expect bits 1 and 5 | 5 min |
| Queen of Cards var | 0x18FEAE4 | any save mid-chain: value 0-5 = last created card | 5 min |
| PuPu/UFO byte | 0x18FEF2D | post-UFO-quest save: sighting bits + 0x40/0x80 | 5 min |
| obel_quest bits | 0x18FEF2E+ | save with Obel Lake done; or do one step live | 10 min |
| chocobo forests (vars 616-622) | 0x18FEC20+ | solve ONE forest live, watch — reveals which var = which forest (then RENAME the ladder into per-forest checks; ladder itself shipped 2026-09-02) | 20 min |
| Joker flag (var 460 candidate) | 0x18FEB84 | beat Joker in the Training Center, watch (then ADD the check) | 15 min |
| Shumi quest (vars 607/610/612) | — | do quest steps, watch (future checks) | optional |
| Winhill vase (var 387 bits) | — | pick up a vase piece, watch (future checks) | optional |
| AP save-state header | vars 1000+ | play with client, save, reload — `/ff8` shows the in-save counter surviving | 5 min |

## Phase 4 — targeted event sessions (~2-3 hours)

Things that need the *game engine* to act, not just bytes to read:
1. **DeathLink in a real battle** (kill_party): real fight, send a death from
   `tools/deathlink_probe.py`, confirm the engine runs its game-over.
2. **Ultimecia goal machine**: load the pre-Ultimecia save, win, confirm the
   client sends the goal (phases logged). This is the one test that otherwise
   only happens at hour 40 of the real run.
3. **Omega goal**: on a castle save, beat Omega with `goal: omega` slot —
   confirm goal fires from the battle tracker.
4. **Boss-win + GF interception on a real boss**: load pre-Ifrit save, win,
   confirm check + revoke + AP grant loop.
5. **Draw point first-draw** on a real sparkle.
6. **In-battle usability of a mid-game AP-granted GF** (junction + summon).

## Phase 5 — the real playthrough

Run the **flight recorder** for the entire playthrough, alongside the client:

    ..\.venv\Scripts\python.exe tools\flight_recorder.py

Every savemap change, moment transition, and battle gets logged with
annotations; snapshots every 5 min and at every moment change. If ANY check
misbehaves, the recording answers what happened without replaying
(`--report ... --moments --battles --offset 0x...`). `/ff8missed` diagnoses
pending checks mid-run; `/ff8check <name>` rescues a provably-missed
edge check without abandoning the run.

## Deferred (post-playthrough or file-patching v2)

- Chocobo forest / Joker / Shumi / Winhill-vase checks: add as soon as their
  Phase 3 diffs pin the vars (5-minute table edits; the generator forces
  tracker anchors).
- Laguna dream 3 has no story-moment of its own (pro stays 395; detection via
  field 801 would need a non-savemap trigger) — current check fires at 420,
  the first post-dream moment. Good enough; revisit only if players complain.
- In-game item names/text for received items (needs file patching).
