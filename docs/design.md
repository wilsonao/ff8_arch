# FF8 Archipelago — Design Document (v0.1, 2026-08-26)

Target: **Final Fantasy VIII, Steam 2013 (`FF8_EN.exe`)** · Scope: **Core** (GFs, key items, story/boss
beats, draw points later) · Status: scaffold — addresses researched, in-game verification pending.

Companion research: [ff8-internals.md](research/ff8-internals.md), [archipelago-api.md](research/archipelago-api.md).

---

## 1. Architecture

One `.apworld` package (`ff8/`) containing both halves, following the KH2 / FF12 Open World pattern:

```
┌──────────────────┐   generation    ┌──────────────────────┐
│ apworld: World   │ ──────────────► │ AP server (room)     │
│ items/locations/ │                 └─────────▲────────────┘
│ regions/options  │                           │ websocket (AP protocol)
└──────────────────┘                 ┌─────────┴────────────┐
                                     │ FF8Client (Python,   │
                                     │ CommonContext +      │
                                     │ pymem, in apworld)   │
                                     └─────────▲────────────┘
                                               │ Read/WriteProcessMemory
                                     ┌─────────┴────────────┐
                                     │ FF8_EN.exe (2013)    │
                                     │ static savemap in    │
                                     │ module memory        │
                                     └──────────────────────┘
```

**No game-file patching in v1.** The 2013 port keeps the entire live savemap at *static module-relative
offsets* (see research §1), so a pure external memory client can both detect checks and grant/suppress
items. File patching (Deling/Hext, as Maelstrom does) is reserved for v2 features that need it (draw
point spell randomization, in-game text for received items).

## 2. Randomization model

The story itself is **not** randomized — FF8 is linear and progresses vanilla. What's randomized is
*what you get* at the game's reward moments. Every reward moment becomes an AP **location**; the
vanilla reward is suppressed by the client and the AP item pool is distributed across the multiworld.

### Locations (checks), v1

Each location carries one or more **triggers** (any satisfied → check fires):

| Trigger | Mechanism |
|---|---|
| `story` | `game moment` (savemap var 256 @ `+0x18FEAB8`) reaches a threshold — auto-catches-up after offline play |
| `boss` | battle-victory detection: fight flag (`+0x1678CA4`) 1→0 transition credited to the encounter ID (`+0x1996DA8`) seen during the battle — the autosplitter's pattern. Makes boss/draw GF checks fire even when AP already delivered that GF |
| `gf_flag` | GF unlock-flag rising edge not caused by the client = vanilla grant; plus an attach-time catch-up rule (flag set + GF never received + location unchecked → vanilla grant happened offline) |
| `item` | unique item ID appears in inventory array → remove + send check |
| `draw` | draw point slot leaves the Full state: 2-bit fields (0=Full/1=Half/2=Empty/3=Exhausted), 4 per byte from `+0x18FEA2C`, slot N at byte `N//4` bits `(N%4)*2` (ff8-memory README "Field - Draw Points"). Nonzero = drawn → auto-catches-up offline; a point that refills to Full unseen is caught on the next draw |
| `tt_wins` | Triple Triad total-wins u8 (`+0x18FEFAC`) reaches a threshold — state-based, auto-catch-up |
| `flag_bit` | byte at a module offset has given bits set. Used for the CC Group quest bitmasks: Jack/Club/Diamond/Spade/Hearts = bits 0,1,4,2,3 of `+0x18FEB95` (live-verified); Dr. Kadowaki/Joker/King = bits 1/4/5 of `+0x18FEB93` (Hyne `tt_players_bgu_dialogs2`; Joker's bit matches Leviathan-card ownership in 50/50 legit library saves, 2026-08-31) |
| `item_own` | inventory holds ≥ 1 of a game item ID — state-based and **non-intercepting** (magazines stay with the player; Combat King / Pet Pals teach limits when read) |
| `u8_ge` / `u32_ge` | unsigned int at a module offset reaches a threshold (battles-won ladder on MISC2 `victory_count` `+0x18FE934`, SeeD `testLevel` `+0x18FE98B`) |
| `byteflag_ge` | count of bytes in [OFF, OFF+LEN) with all MASK bits set ≥ N: chocobo-forests solved ladder (7 quest vars at `+0x18FEC20`, 0x80 = solved, order-agnostic) |
| `bits_ge` | popcount(u32 at offset & mask) ≥ N: the Ultimecia Castle seal **bitmask** `+0x18FEB06` (one bit per broken seal, order-agnostic ladder) and weapon remodels on MISC1 `unlocked_weapons` `+0x18FE750` (bit i = kernel weapon i ever made; monotonic, unlike the equipped `weaponID`) — both settled offline against the save library 2026-08-31 |
| `cards_owned` | distinct Triple Triad cards ever obtained ≥ N: commons with the bit-7 "seen" flag (77 bytes at TTCARDS `+0x18FEF38`; low 7 bits = held qty, which refining drains) + set rare bits |
| `bits_all` | every bit of a mask set across LEN bytes: a GF's 22-ability learn list in its `completeAbilities[16]` (record `+20`, bit = Hyne ability id) — "GF Mastered" checks (2026-09-01) |
| `gf_abilities_ge` | abilities learned beyond each GF's new-game default mask, summed over the 16 records (max 244). Default masks are unanimous across the save library (`memory.GF_ABILITY_DEFAULTS`), so a multiworld-granted GF never contributes on receipt |

v1 groups: 16 GF acquisitions (`gf_flag` + `boss` where the source is a battle; study
panels get a `story` 30 fallback), ~13 story/boss beats (`story`/`boss`), 2 key-item
handouts (`item`). Known gaps: Doomtrain (Solomon Ring use) and Tonberry King (no
distinct encounter ID) are `gf_flag`-only — their checks can't fire if AP granted that
GF first. Draw points: **99 named field-screen draw points** behind the
`draw_point_checks` option (`"???"` slots and hidden world-map points excluded); the
15 in one-window areas (D-District Prison, Missile Base, Galbadia Garden, White SeeD
Ship, Lunar Base, Lunatic Pandora Laboratory dream) are `LocationProgressType.EXCLUDED`
so they only ever hold filler. Battle-victory credit is withheld when the party was
wiped (all occupied battle-ally slots `+0x1927B18` stride `0xD0` at 0 HP after being
seen alive) so a loss — including a DeathLink kill — can't fake a boss check.

Location **groups** gate check sets behind options (`LocationData.group`): `core`
(33: GFs, story/boss beats incl. Gerogero 104 + Seifer-LP 795, key items), `draw` (99),
`tt` (15: win ladder 5/15/30/60/100 on the wins u16, unique-card ladder
10/20/35/50/70 via `cards_owned`, + 5 CC members Jack..Heart) behind
`triple_triad_checks`, `boss_extra` (26: Odin 317 — timer-expiry game-over could
false-credit, accepted; Omega 462 EXCLUDED; UFO sightings 745-748 — any battle end
counts, that IS the sighting; UFO?? 749; PuPu 750; 8 castle bosses — Sphinxaur IS in
the reference as "Sphynxaur" 363, gap closed 2026-08-27; Ultima Weapon 354 + Jumbo
Cactuar 712 kill checks split from their GF locations; 8 Ragnarok Propagators —
red pair 85/86, purple/green/yellow 814-819, all mandatory story kills) behind
`optional_boss_checks`, `cards` (33 rare cards via
ownership bits at `+0x18FEFA6`, Hyne TTCARDS+110, name order = Hyne card list 77+i;
Angelo/Shiva/Laguna/Gilgamesh cards missable→EXCLUDED) behind `rare_card_checks`,
`sidequest` (48: 15 blue magics — bits of `+0x18FE76C` CONFIRMED; 6 Angelo tricks —
bits of `+0x18FE773` CONFIRMED; Timber Maniacs popcount ladder on `+0x18FEAE8`,
bit-order agnostic, 9/12 tiers EXCLUDED; Phoenix/Gilgamesh cameo events — edge-based
`dream_flag` on MISC2 dream byte `+0x18FE97A` (bits decoded offline 2026-08-31:
b1 Odin/b2 Phoenix/b3 Gilgamesh — clears Odin —/b4 Angelo disabled/b5 Angel Wing),
both EXCLUDED; battles-won ladder 25/50/100/200 on MISC2 `victory_count`
`+0x18FE934`; SeeD written tests 5/10/20/30 on MISC2 `testLevel` `+0x18FE98B`;
weapon remodels — first remodel per main character + 6 ultimate weapons
EXCLUDED-as-grind, via `bits_ge` on MISC1 `unlocked_weapons` `+0x18FE750`
(bit per weapon ever made; kernel ids grouped per char per Hyne Data.cpp)) behind
`sidequest_checks`, and `magazine` (23 via `item_own`: 7 Weapons Monthly, 5 Combat
King, 6 Pet Pals, 4 Occult Fan, Girl Next Door; one-window issues + uncertain-source
Combat King 003 filler-only; ids from itemId.md — WM 177-183, CK 184-188, PP 189-194,
OF 195-198, GND 163; shop-only PP Vol.3-6 added 2026-09-02 per beta feedback,
at explicit ids 672-675 — the 640+ window is full past 658 — keeping earlier ids stable) behind `magazine_checks`. Tonberry King backup trigger:
`tomberry_sr_vaincu` `+0x18FE944` (confirmed offline: =1 on every legit
GF-Tonberry save). 2026-08-31 stat pass: 5 Zell Duel finishers join `sidequest`
(bits 4/5/7/8/9 of LIMITB.zell `+0x18FE76E`, taught by Combat King 001-005,
missability mirrors the magazines), and a new `stats` group (36, behind
`stat_checks`) reads lifetime counters: Squall level 10-40 (`u32_ge` on his exp,
flat 1000/level), magic-kinds ladder 5-40 + 8 marquee first-draws
(`magic_drawn_once` `+0x18FE95C`, bit = spell id − 1, immune to AP magic
filler), enemies scanned 5-30 (`ennemy_scanned_once` `+0x18FE964`), escapes
5/15/30 (`+0x18FE93A` u16), monsters felled 50-500 (var 68), steps
20k-300k (var 4), Tonberries culled 5/10/20 (`tomberry_vaincus` `+0x18FE940`);
all farmable, none missable (see docs/research/savemap-measurables.md).
2026-08-31 TT pass (+18 to `tt`, now 36): unique-card tiers 85/100/110 (110
needs every rare + PuPu's one-chance card → EXCLUDED, region Disc 4 since
CC-Ragnarok is the lost-rare recovery); Balamb Garden card-wins ladder
15/40/100 on `tt_bgu_victory_count` (var 478 `+0x18FEB96`; library: 0 on
non-card saves, 30-129 wherever CC bits are set); Random-rule abolition in
Dollet/Trabia/Centra/Lunar Gate + "Random Rule Extinct" capstone via new
`bits_clear` trigger on `tt_rules[8]` `+0x18FEAC8` (virgin bytes unanimous
01/02/0C/0E/88/90/DF/C0 across all early saves; spreading only ADDS bits so
clear == abolished; moment>=20 guard against a pre-init zeroed savemap;
Lunar Gate + capstone EXCLUDED-as-grind); Card Compendium level sets 1-7
via new `cards_seen_range` trigger (11 commons per level, bit-7 flags;
Level 5 EXCLUDED — PuPu card 47 is one-chance). Losses/draws counters
(TTCARDS+118/120) deliberately rejected: trivially throwable.
2026-09-01 GF ability pass: new `abilities` group (71, behind `gf_ability_checks`):
49 signature abilities per GF via `flag_bit` on the record's `completeAbilities`
mask (Card/Card Mod/T Mag-RF … Enc-None/Mug … Haggle/Sell-High/Familiar/Call
Shop; regions paced by AP cost ≤60 Dollet Exam → 250 Disc 3), 16 "GF Mastered"
(`bits_all` on the 22-ability learn list, Disc 3), party ladder 10/25/50/100/150
+ 200 EXCLUDED (`gf_abilities_ge`). Every GF-specific check carries
`requires_gf` → `set_rules` demands the "GF <name>" item, so GFs now gate
content beyond the Disc 3 count. Default masks lifted from the library (one
not-yet-owned mask per GF in all 273 saves), ability ids/AP/learn lists from
Hyne `Data.cpp`; the tracker gives the group its own "GF Abilities" tab.
All-on total: **429 locations** (358 + 71 abilities, 2026-09-01; 358 = 299 + 41 stats + 18 TT, 2026-08-31)
(2026-08-28 additions: 5 Laguna dream completions — end moments 233/310/420/
1310/1900 from storyId.md + autosplitter ld1-ld5 splits; 8 castle-seal ladder
checks on the autosplitter's `seal` byte `+0x18FEB06` = IDA `UltimeciaSeals`
(a bitmask — ladder counts bits, settled offline 2026-08-31);
CC Kadowaki/King restored at the REAL offset `+0x18FEB93` bits 1/5 from Hyne's
CC editor encoding; Queen of Cards chain ladder on `tt_cardqueen_quest`
`+0x18FEAE4` values 1-5; 5 Obel Lake milestones on `obel_quest` bits
`+0x18FEF2E+`; UFO/PuPu checks gained state-based catch-up triggers from
`koyok_quest` `+0x18FEF2D` bits 2-7 and `ufo_battle_encountered` `+0x18FE948`.
Provenance and the burn-down procedure live in
[verification-plan.md](verification-plan.md); its "Phase 3 — OFFLINE results"
section records which offsets the 273-save library scan (`tools/save_scan.py`,
2026-08-31) settled. 2026-09-02 pass (beta feedback — "everything huntable
should be a tracker pin"): per-issue Timber Maniacs checks (ids 900-913,
`flag_bit`) — the bit→location map is Hyne ItemEditor.cpp's
`timbermaniacsStrings` row order (bit0 Balamb Hotel … bit13 White SeeD Ship),
library-validated (earliest-moment per bit matches each source's story
window; bits 14/15 zero in all 238 legit saves; the two Balamb issues are
MUTUALLY EXCLUSIVE — no save holds both, completionists max at 13/14 → both
filler-only); chocobo forests shipped as a solved-count ladder (ids 914-917,
new `byteflag_ge` trigger over vars 616-622 at `+0x18FEC20`, mask 0x80 =
solved — values only {0,02,20,40,80} in the library; var→forest identity
still needs one live diff before per-forest names); Combat King 003
un-missabled (dual source: library-girl quest or Esthar shop purchase,
guide-confirmed); and the 125 hidden world-map draw points as a new
`world_draw` group / `world_draw_point_checks` toggle (ids 1000+(slot-128) —
the savemap draw array's second half, slots 128-255 at `+0x18FEA4C`, rows
from the ff8-memory README continuation; three "???" slots skipped; the
Islands Closest to Heaven/Hell are 28+33 of them). Still
researched-not-yet-added: per-forest chocobo checks,
Shumi (vars 607-615, 607 steps 0x20→0x40→0x80; a second cluster
605/614/615/623 first moves at moment ~3410 disc 3), Winhill vase (var 387
turned out to be the Laguna-dream-3 var; vase var still unknown). Joker's
var-460 candidate was refuted; Joker is `+0x18FEB93` bit 4 and is now a
check.)
Hyne-derivation provenance: live MAIN base
`0x18FDCA8` cross-anchored 7 ways; MISC3 internals proven to diverge from the save
layout (draw_points), so README live rows always win; MISC2 packing now anchored at
three interior points (+0 game_time = README IGT row, +4 countdown, +18
battle_escaped = README `0x18FE93A` row), so between-anchor fields (victory_count
+12, dream +82, testLevel +99 — pinned by the struct's `pos=100` comment) are
high-confidence but still VERIFY until observed live (raw values surfaced in `/ff8`).
TTCARDS is pinned by two live-confirmed interior fields (cards_rare +110, wins +116),
anchoring the commons array at its base; byte semantics (low 7 bits = quantity)
VERIFY. Researched and deferred: Laguna-dream completion checks — storyId.md's dream
boundaries are contradictory (dream-1 "end" 310 vs Forest Owls 290), needs the
telemetry playthrough; Chocobo forests / Obel Lake / Shumi / Winhill vase / Queen of
Cards quest chains — field-var flags not yet located.

**DeathLink**: party wipe in battle → `send_death` (suppressed when the wipe was caused
by a received DeathLink); received DeathLink → zero every occupied ally slot's HP u16
(`+0x10`, max HP `+0x14` marks occupancy), deferred until the next battle when received
on the field. VERIFY in-game: the battle engine noticing externally-zeroed HP.

### Items, v1

| Item | Class | Grant mechanism |
|---|---|---|
| 16 GFs (Quezacotl … Eden) | progression | write unlock byte in the GF's 68-byte savemap record (stride `0x44` from Quezacotl `+0x18FDCB9`); init record from template if zeroed |
| Magical Lamp | progression (gates Diablos check) | write into inventory array (`+0x18FE79C`, 198×2B) |
| Solomon Ring | progression (gates Doomtrain check) | same |
| Gil bundles (500/2000/10000) | filler | add to gil dword `+0x18FE764` |
| Consumable packs (Potions/Hi/X/Mega, Phoenix Downs, Remedies, Elixir, Tents/Cottage, Energy Crystal, Dragon Fang) | filler/useful | inventory array |
| Magic stocks (Cura/Curaga/Protect/Shell/Haste/Regen/Full-life/Aura/Meltdown/Triple/Ultima) | filler/useful | written into the party's 32-slot magic inventories ((spell id, qty) byte pairs at char record `+0x10`; top up stacks to 100 else first empty slot, Squall first then spilling to the other 7 records — the checks-only roster's 33 kinds can outgrow one character). CONFIRMED live 2026-08-27 (empty-slot placement, stacking, and the 100 cap all observed) |
| Checks-only magic roster (offsets 231-252: Cure/elemental -ra & -ga trios/Water/Bio/Life/Esuna/Slow/Blind/Sleep/Stop/Holy/Flare/Quake/Tornado/Meteor/Death/Pain) | filler/useful | same mechanism; pulled as filler only under `magic_mode: checks_only` (vanilla-mode weight 0). Spell ids derived from the kernel order pinned by the 19 ids already in use (VERIFY in-game: Water/Bio/Esuna/status-block names on first grant) |
| Traps (offsets 400-402: Gil Snatch / Ambush / Magic Leak) | trap | replace `trap_chance`% of filler pulls (default 0). One-shot savemap writes on a safe field tick: `take_gil` (≤1500, floored at 0), `ambush_party` (every living character to 1 HP — recoverable at any save point), `leak_magic` (10 of the most-stocked spell via `remove_magic`; under checks-only the cap is untouched so it redraws). Nothing can KO or strand; DeathLink is battle-side and unaffected (2026-09-01) |
| Cameo GFs (Odin, Phoenix, Gilgamesh) | useful | set bits 1/2/3 of the MISC2 dream byte `+0x18FE97A` (VERIFY). Additive — vanilla acquisition not intercepted. Re-asserted, except Odin once the Gilgamesh bit is set (the game converts Odin→Gilgamesh at the Disc 3 Seifer fight) |

GFs are classed progression because logic gates later regions on GF count (a party-power proxy: e.g.
entering Disc 3 areas "in logic" requires ≥6 GFs). Vanilla-granted GFs the player hasn't received from
AP are **revoked** by the client (flag cleared) after the check fires.

**Checks-only magic mode** (`magic_mode: checks_only`, 2026-08-31): the client keeps a
party-global per-spell **cap** ledger — stock at baseline plus every magic item granted —
and on each safe tick clamps any spell whose total across the 8 character records
exceeds its cap (`remove_magic`, emptied stacks cleared to (0,0) like a cast-to-zero).
Draws and refines above cap yield nothing (draw-point checks and the `magic_drawn_once`
stat ladders still fire — the game sets those at draw time, before the clamp); casting
spends normally, and re-drawing refills up to cap. The cap model is deliberate over a
strict ledger that ratchets down on casts: party shuffles and Laguna dreams can make
magic vanish and reappear wholesale, and a cap can never destroy stock that merely came
back — the worst failure mode is a small refill leak, never loss. Ledger re-baselines on
attach, reconnect, `/ff8adopt`, the title screen (module 0 — the only route to FF8's
load menu), and game-moment regression; it is never enforced while a foreign save is
frozen. A magic grant raises the cap by its full amount even if stocking found no room,
so overflow becomes drawable instead of lost. Generation-side: a 5-item starter kit
(Cure/Fira/Blizzara/Thundara/Sleep) is precollected and the filler pool draws from the
expanded roster (~57% magic pulls). `/ff8magic` dumps stock-vs-cap for debugging.

### Regions & logic

Linear region chain mirroring story order, gated by **event items** placed at story-beat locations
(standard linear-game AP pattern), so fill respects play order:

`Menu → Balamb Prologue → Fire Cavern → Dollet Exam → SeeD/Balamb → Timber → Galbadia/Deling (D1 end)
→ Disc 2 (D-District, Balamb, Fisherman's Horizon, Garden battle) → Disc 3 (Esthar, Lunar, Ragnarok)
→ Disc 4 (Ultimecia's Castle) → Victory`

Extra gates: Diablos check requires **Magical Lamp**; Doomtrain check requires **Solomon Ring** +
Disc 3; late regions require GF-count thresholds. Completion condition: `Victory` event at "Ultimecia
Defeated" (client sends `StatusUpdate: CLIENT_GOAL` on detecting the ending).

## 3. Client design (`ff8/client.py` + `ff8/memory.py`)

- `FF8Context(CommonContext)`: `game = "Final Fantasy VIII"`, `items_handling = 0b111`.
- Attach: `pymem.Pymem("FF8_EN.exe")`; re-hook loop every 5 s on failure; `/connect_game` style manual
  commands for other language exes (`FF8_FR.exe`, …) later — offsets differ per language, EN first.
- **Safe-state gate**: only trust reads / perform writes when in field module and not in menu or
  battle (module dispatch short @ `+0x18D8FC6`, engine state @ `+0x18E0758`, in-menu byte @
  `+0x1976358`, post-battle byte @ `+0x1678CA4`). Also require game moment > 0 (title screen guard)
  and stable across two consecutive polls before acting.
- **Watcher loop** (~0.5 s): snapshot savemap region in one `read_bytes` → detect checks → suppress
  vanilla rewards → send `LocationChecks` → grant pending received items → re-assert non-consumables
  (KH2 `verifyItems` pattern) → goal detection. Implemented 2026-08-28: `SavemapSnapshot` reads the
  span `0x18FDCA8..0x18FEFB0` (~4.9 KB) once per tick and serves every state trigger from that
  buffer, so all triggers see the same instant (no torn reads); battle-module/engine-state
  addresses stay individual reads. A span-bounds unit test guards future trigger additions.
- **Idempotency (2026-08-28 redesign)**: the delivery cursor lives *inside the save* — field vars
  1000+ are verified free (FF8ModdingWiki IDA + JSM scan: no script/EXE references, zero in real
  saves) and inside the save file's checksummed span, so an 8-byte header (magic, seed+slot
  fingerprint, items-applied u16) persists through the game's own save/load. Reloading an older
  save or starting a new game re-delivers exactly what that save is missing; the old "consumables
  lost on reload" limitation is gone. The sidecar JSON keeps the machine-local high-water mark
  (save-regression warning + migration seed for saves predating the header). VERIFY: header
  survival across save/load in-game.
- Slot data: option values + goal + logic thresholds the client needs.

## 4. Open questions / verification backlog

1. **Game-moment threshold table** — ~~fill from scratch~~ **mostly done (2026-08-26)**: sourced from
   `reference/storyId.md` + `FF8Autosplitter.asl`; 12 of 13 story checks have values in
   `locations.py`. Remaining: "Balamb Liberated" (between 750 and 850), edge-verification for NORG
   (612 may be fight start) and castle entry (4020), all via the `tools/attach_test.py` telemetry
   playthrough.
2. **GF record template** — **resolved (2026-08-26, tested in-game)**: the unlock byte alone is
   enough. GF records are pre-initialized at new game; a byte-granted Leviathan appeared at level 17
   / 1349 HP with its default junction abilities, junctioned fine, and summoned in battle without
   issue. No template needed.
3. **Item IDs** — **done (2026-08-26)**: confirmed from `reference/itemId.md` (Solomon Ring 167,
   Magical Lamp 168, Potion 1, Phoenix Down 7, Elixir 9, Remedy 16); tables updated.
4. **In-battle GF availability** — a GF granted mid-game has 0 compatibility/junction state; verify
   it's usable and give sane AP/abilities in the template.
5. **Ultimecia defeat signal** — **implemented (2026-08-26)**, pending a live endgame test: ported
   the autosplitter's state machine (field 573 + three HP pools @ `+0x1927D98/+0x1927F38/+0x1927F3C`
   + killing-blow flag @ `+0x1927C30`). Never use game moment 4050 — that's the pre-fight seal phase.
6. **Savemap mirror base** (`+0x18FDCA8`) — verify against gil anchor at runtime before using derived
   offsets (card inventory etc.).
7. **Steam save re-signing** is *not* needed (we never touch save files — only live memory), but
   confirm the game doesn't checksum live savemap regions on save (it shouldn't; Hyne-edited saves
   load fine, and trainers write these addresses routinely).
8. **2026-08-27 check-expansion offsets** — SETTLED OFFLINE 2026-08-31 via the save library
   (`tools/save_scan.py`): `battles_won` equals MISC3's twin counter in 270/273 saves, `seed_tests`
   spans 0..30, TTCARDS commons bit 7 = "obtained once" (now what `unique_cards_owned` counts),
   `weapons` read `[0, 7, 11, 15, 19, 24]` on every unremodeled save and remodel checks moved to
   the monotonic `unlocked_weapons` bitmask. Only the live +1 edges remain unobserved; the
   playthrough flight recorder covers them. Encounter-ID checks (Propagators 85/86/814-819,
   Sphinxaur 363) follow the proven autosplitter pattern and need only a spot check.

## 5. Milestones

- **M0 — scaffold** *(this commit)*: apworld generates a multiworld solo; client launches from the AP
  Launcher, attaches to FF8, logs gil/game moment/field ID live.
- **M1 — telemetry**: play through Disc 1 with the client logging; fill story-moment table and item ID
  enum; verify safe-state gating.
- **M2 — GF loop end-to-end**: GF checks fire, vanilla GFs revoked, AP-granted GFs junctionable;
  local 2-player test with a second world.
- **M3 — full core scope**: key items, story checks, filler pool balance, goal detection, sidecar
  persistence; complete a full playthrough.
- **M4 — release polish**: draw-point checks option ✅, DeathLink ✅ (code done, in-game verification
  of kill_party pending), `.apworld` build ✅ (official "Build APWorlds" launcher component →
  `build/apworlds/ff8.apworld`; clean-load via `custom_worlds` verified — the source
  `archipelago.json` must NOT contain `version`/`compatible_version`, the builder injects them),
  setup guide + game info page ✅, `/deathlink` + richer `/ff8` client commands ✅, Doomtrain gap
  closed via `item_gone` trigger (Solomon Ring count decrease; used key items are no longer
  re-asserted once their gated check is sent) ✅, save-regression warning via sidecar `max_moment` ✅
  (all 2026-08-26). 2026-08-28: world test suite ✅ (`ff8/test/` on AP's `WorldTestBase` —
  option-combo fills, multi-seed sweeps of the tight GF gate, logic rules, pool/table/offset
  invariants; `pytest worlds/ff8/test`), GitHub Actions CI ✅ (tests on 3.11/3.13 + apworld/tracker
  artifacts, AP pinned to the dev checkout's 0.6.8 commit), savemap snapshot ✅ (§3), WebHost
  option groups + presets ✅, location hint groups ✅, colored received-item log lines + batch
  summary ✅, `/ff8verify` split from `/ff8` ✅, `.apignore` keeps tests out of the shipped
  apworld ✅. Remaining: beta with the AP community Discord (future-game-design forum thread per
  AP world submission norms).
- **Pre-playthrough hardening (2026-08-28)**: goal option (ultimecia/omega — omega reuses the
  battle tracker, no new detection) ✅, `/ff8missed` + `/ff8check` rescue commands ✅,
  save-embedded delivery state (§3) ✅, research sweep closed the moment-table gaps (dreams,
  Balamb 760, NORG 612, castle 4020 all pinned from primary sources) ✅, 25 new checks (298
  total) ✅, verification tooling: `tools/flight_recorder.py` (playthrough black box),
  `tools/savemap_diff.py` (capture/diff/watch), `tools/savemap_map.py` (annotation map),
  `live_selftest.py` extended to every trigger family ✅. The full pre-playthrough burn-down
  procedure: [verification-plan.md](verification-plan.md).
- **PopTracker pack** ✅ (2026-08-26): `tracker/ff8_ap_tracker/`, generated from the apworld's
  own tables by `tools/gen_tracker_pack.py` (re-run after any item/location change; zip lands in
  `build/ff8_ap_tracker.zip`). AP autotracking: items/checks auto-marked, story progress inferred
  from checked story beats, `draw_point_checks` + `gfs_required_for_disc3` read from slot data.
  Original generated art only per §6: icons, a stylized geographic world map (check pins at real
  geography, inset panels for Balamb/Galbadia Garden, space, Ultimecia's Castle) plus a schematic
  region board as a second tab. New locations fail generation until given a `NODE_ANCHOR` entry.
  Live load test in PopTracker pending.

## 6. Legal/distribution notes

Ship no Square Enix assets or game data — the apworld contains only names, IDs, offsets, and our own
code (same posture as every AP world for a commercial game). Address tables derived from GPL-3.0
community research (`ff8-memory`, Hyne) — keep attribution in `docs/research/` and consider GPL-3.0
for the repo to stay compatible if we port code (we currently only use published constants/facts).
