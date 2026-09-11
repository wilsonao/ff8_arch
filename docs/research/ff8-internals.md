# FF8 (Steam 2013, FF8_EN.exe) — Modding & Memory-Hacking Landscape: Technical Report

> Research report generated 2026-08-26. Facts are labeled **[confirmed]** (read directly from a cited
> source) or **[inference/recall]** (derived or from general knowledge — verify before depending on it).

**Scope:** Original 2013 Steam port (`FF8_EN.exe`), not Remastered.

---

## 1. Process memory layout — THE goldmine exists

### 1.1 `ff8-speedruns/ff8-memory` — comprehensive static address map [confirmed]

**Repo: https://github.com/ff8-speedruns/ff8-memory** (GPL-3.0, "Final Fantasy VIII research and tools").
Its `README.MD` is a full module-relative offset table for `FF8_EN.exe` and `FF8_FR.exe` — these are
**static offsets from the module base** (no pointer chains needed; the 2013 port keeps the whole live
savemap in static memory). Companion docs: `rng-tables.md`, `world-map.md`, `reference/` (ID enumerations).
Key entries (all EN offsets, module-relative):

| Thing | EN offset | Size / notes |
|---|---|---|
| **Gil** | `0x18FE764` | 4 bytes |
| **Story progress ("game moment")** | `0x18FEAB8` | 2 bytes |
| **Current field/map ID** | `0x18D2FC0` | 2 bytes — "field to load next / currently loaded" |
| Previous map ID | `0x18FEA0C` | 2 bytes |
| World map X/Y/Z (Squall) | `0x1C3EE80/84/88` | signed i32 each |
| **Play time (IGT)** | `0x18FE928` | 4 bytes, seconds |
| Active countdown timer | `0x18FE92C` | 2 bytes |
| **Engine state** | `0x18E0758` | 4 bytes, "0 = field" |
| **Module dispatch (field/battle/worldmap)** | `0x18D8FC6` | 2 bytes, values 1–11 |
| **In-menu flag** | `0x1976358` | 1 byte bool |
| In post-battle results screen | `0x1678CA4` | 1 byte |
| **Item inventory** | `0x18FE79C` | 198-entry array, stride 2: `+0` item ID (byte), `+1` quantity (byte) |
| **Character array** | `0x18FE0E8` | 8× stride `0x98`, savemap order Squall→Edea. `+0` HP (2B), `+4` EXP (4B), **32 magic slots at `+0x10`–`+0x4F`** (spell ID at even byte, qty at odd byte), junctioned-spell IDs (HP/STR/VIT/MAG/SPR/SPD/EVA/HIT/LCK) at `+0x5C`–`+0x64` |
| **GF unlock flags** | Quetzacotl `0x18FDCB9`, Shiva `0x18FDCFD`, Ifrit `0x18FDD41`, … same pattern through Eden (stride `0x44` = 68-byte GF record) | 1 byte each |
| GF stats (Quetzacotl) | HP `0x18FF618` (2B), MaxHP `0x18FF61A` (2B), EXP `0x18FF61C` (4B) | same-stride pattern for other GFs |
| **Draw point state** | `0x18FEA2C`–`0x18FEA6B` | bit flags (availability); README documents ~96 draw point locations with spell IDs |
| Triple Triad rules per region | `0x18FEAC8` | 8× 1-byte region rule flags + trade rule `+0x8` |
| TT total wins | `0x18FEFAC`; CC-group quest progress `0x18FEB95` | |
| SeeD test points | `0x18FE9C8` | 2 bytes (README notes rank behavior: +10/-10 per encounter/payout) |
| Battle allies | `0x1927B18` | 3× stride `0xD0`: ATB `+0xC`, HP `+0x10`, level `+0xB4` |
| Battle enemies | `0x1927D94` | 4× stride `0xD0`: HP `+0x4` (4B), level `+0xA8` |
| Encounter ID | `0x1996DA8` | short (from autosplitter) |
| **Field var block (savemap vars)** | `0x18FE9B8` | start of the 1024-byte saved-variable block (per ffrtt wiki, en-US) |

**Cross-check [confirmed]:** story progress `0x18FEAB8` = varblock `0x18FE9B8` + 256 — exactly matching
the wiki's "Variable 256 = main story progress" (see §3). Two independent sources agree.

**Not explicitly listed in the extraction:** Triple Triad *card inventory* array and
*party-members-unlocked* flags — but both live in the savemap block that is fully resident in this same
static region, so they are recoverable via the savemap layout (see §1.3, §2). The ff8-memory README is
large; read it directly.

### 1.2 LiveSplit autosplitter [confirmed]

**Repo: https://github.com/ff8-speedruns/ff8-auto-splitter** — single file `FF8Autosplitter.asl`.
Targets `FF8_EN.exe` and `FF8_FR.exe`, **static addresses only, no pointer paths**. Declares (EN):
progression `pro` short @ `0x18FEAB8`, field ID `sid` short @ `0x18D2FC0`, battle flags `fight1/fight2`
@ `0x1678CA4`/`0x1976358`, GF-drawn flags (Siren `0x18FDD85`, etc.), encounter ID short @ `0x1996DA8`,
enemy HP ints @ `0x1927D98`/`0x1927F38`, inventory slot bytes @ `0x18FE79C`–`0x18FEB1`. Split logic:
`pro` thresholds (e.g., `pro == 135` = Dollet escape), battle-flag 1→0 transitions for boss kills,
inventory checks (e.g., item ID 154 qty >3 for Fish Fins), 3-phase Ultimecia HP tracking. Distributed
via https://www.speedrun.com/ff8/resources. **Only exists for the 2013 version — no Remastered
autosplitter.**

### 1.3 Savemap mirror principle [inference — arithmetic from confirmed anchors]

The ffrtt wiki says save vars live at file offset `0xD10` in an uncompressed PC save and at `0x18FE9B8`
in EN memory ⇒ **live savemap base ≈ `FF8_EN.exe+0x18FDCA8`** (`0x18FE9B8 − 0xD10`). Sanity check:
Quetzacotl GF record byte at `0x18FDCB9` = base + `0x11`, consistent with GF records at the top of the
savemap. Practical consequence: **any field Hyne documents in the save format can be located in live
memory by adding its save offset to this base** — this gives you card inventory, party roster flags,
SeeD rank, everything. Verify the base with a known anchor (gil) before trusting it.

### 1.4 Cheat Engine tables / trainers [confirmed URLs, contents from search snippets]

fearlessrevolution.com (FearLess Cheat Engine) threads for 2013 Steam: **t=28746** ("FINAL FANTASY VIII
- table v1.0", targets `FF8_EN.exe`: health, gil, items, recharge), **t=10075** ("MULTI5 Cheat Table,
Steam v1.0.10" — all five language exes), **t=5604** ("Omega Trainer v1.0.10"), **t=3828**, **t=1029**.
(Site blocks scripted fetching — 403 — browse manually.) Useful but strictly inferior to ff8-memory as
documentation.

---

## 2. Save format — Hyne

- **Repo: https://github.com/myst6re/hyne** [confirmed] — "complete savegame editor for Final Fantasy
  VIII", GPL-3.0, C++/Qt6, Windows/macOS/Linux, by myst6re (Jérôme Arzel, the central FF8
  reverse-engineer).
- Key sources [confirmed file list]: `src/SaveData.h/.cpp` (the full parsed save structure),
  `src/SavecardData.h/.cpp` (container formats — PC files, PS1 memory cards), `src/FF8Text.h/.cpp`
  (FF8's custom text encoding), `src/Metadata.h/.cpp` + `src/Aes.h` (the 2013 Steam **`metadata.xml`
  signing** — Steam saves are validated; an external editor must re-sign, and Hyne implements this),
  `src/LZS.h`, `src/GZIP.h` (compression — PC saves are LZ4/LZS-compressed containers; repo depends on
  LZ4).
- Because Hyne edits everything (characters, magic, GFs, items, cards, story vars, draw points, SeeD
  rank, world position), `SaveData.h` is effectively the authoritative machine-readable savemap.
- Complementary docs: qhimm forum "FF8 Save File Format" thread
  https://forums.qhimm.com/index.php?topic=6263.0 and the wiki savemap/variables pages (§3).
- [recall] Savemap details worth knowing when reading `SaveData.h`: Triple Triad inventory is a
  per-card byte array (quantity, high bit = held by NPC); magic per character is the 32×(ID,qty) pairs
  confirmed in §1.1; Steam 2013 saves live in `Documents\Square Enix\FINAL FANTASY VIII Steam\user_x`
  as `slot{N}_save{NN}.ff8` plus signed `metadata.xml`.

---

## 3. Game internals

**Story progression [confirmed]:** Tracked in the field-script variable block — 1024 permanent
variables (0–1023) saved to the savemap (file offset `0xD10`), temporaries ≥1024 not persisted.
Accessed by field scripts via `PSHM/POPM`-family opcodes. **Variable 256 (word) = "Main Story quest
progress"** — this is the speedrun community's "game moment"/progress counter (their `pro`, memory
`0x18FEAB8` EN). Variable 528 (signed word) tracks sub-segment progress. Other notables: var 4 = steps,
var 20 = battles won, var 72 = gil, vars 720–723 = costumes, var 734 = split-party flags. Source:
https://wiki.ffrtt.ru/index.php/FF8/Variables (mirror: qhimm-modding.fandom.com/wiki/FF8/Variables).

**Field maps & item pickups [confirmed structure, mechanics part recall]:** Fields ship in the
`field.fs`/`field.fi`/`field.fl` archive triple (FS = data, FI = index, FL = file list). Each field
contains a **JSM script file** (bytecode; opcodes documented at the qhimm wiki: `FF8/FileFormat_JSM`,
`FF8/Field/Script/Opcodes`). Item pickups are field-script driven: an entity's script tests a savemap
variable/flag, runs an "add item" opcode, and sets the flag — meaning **randomizing pickups = editing
JSM scripts (via Deling) or intercepting the add-item routine in memory**. Deling (§4) opens/edits
these archives and scripts.

**Draw points [confirmed encoding in memory, split of data recall]:** Availability/recharge state is a
compact bit array in the savemap (`0x18FEA2C`–`0x18FEA6B` EN, ~96 documented locations). Which *spell*
a draw point contains is not in the save — it's in field data/world-map data (and ff8-memory's README
maps location→spell). Maelstrom demonstrates draw-point spell randomization is possible by file
patching.

**GF acquisition [general game knowledge — reliable]:** Three mechanisms: (a) fixed story grants via
field/battle scripts (Quezacotl/Shiva from Squall's study panel, Ifrit boss, Brothers, Cerberus,
Alexander, etc.); (b) **draw from bosses** (Siren←Elvoret, Carbuncle←Iguions, Leviathan←NORG,
Pandemona←Fujin, Cerberus is a fight, Alexander←Edea, Eden←Ultima Weapon/Tiamat, Bahamut fight);
missable if not drawn; (c) **items**: Magical Lamp→Diablos, Solomon Ring→Doomtrain (+ items). In the
savemap each GF is a 68-byte record whose unlock flag is the addresses in §1.1 — **granting a GF
externally = setting its unlock byte (+ sane stats) in the savemap region.** [last clause inference]

**In-game text [confirmed live 2026-09-10]:** `kernel.bin` (inside `main.fs`) is loaded whole into a
static block at **`+0x18F3E48`** with the file layout intact (u32 section count = 56, u32 section
offsets, then the sections; the file header and both item text sections each hit exactly once in the
process). Names/descriptions are packed NUL-terminated strings in text sections addressed by u16
offsets in the matching data section: magic 1/32 (60-byte records), battle items 7/38 (24-byte),
non-battle items 8/39 (4-byte; item id = index + 33). Writing there changes menu / shop /
battle-results names with no file patching — `ff8/text.py` re-packs a whole section (the block is
contiguous, so a section must not grow) and refuses to touch a block that isn't vanilla or its own
last write. The encoding is Hyne's `FF8text_caract.cpp` table (0x20-based; 0xE8+ are two-letter
dictionary codes such as "in", "re", "HP"; 0x02 newline; 0x01–0x1F two-byte control codes, e.g.
`{x0a23}` = "the item just received" in the battle-message table, kernel section 55). **Field
pickup messages are NOT built from kernel names**: each field's `.msd` (inside its nested archive in
`field.fs`, u32 offset table then strings) carries literal text such as `Received [Magical Lamp]!`
(bgsido_2 #21) — 163 of 175 receipt lines across all fields are literal. Per-location pickup text
therefore needs the field MSD rewritten (file patch, or the resident copy of the current field), and
"you received X from Y" toasts need injected code — the engine has no generic popup. GF names are in
the savemap (12-byte name per GF record), not the kernel. **Verified live 2026-09-10:** the item
menu, the battle draw message ("Received 4 AP Scans!") and the field draw-point prompt/draw
("Found a draw point! X found." / "Zell stocked 13 Xs.") all render from the resident kernel
names. **Renames must use bytes vanilla uses in the same kind of string**: a NAME containing a
dictionary-pair byte (0xE8+) or the "…" glyph (0x30) crashed the menu renderer (access violation
at 0x49DEFB in its quad builder, 62 ms after MODE_MENU); plain single-byte names and vanilla-style
descriptions are fine, and moving every offset in a section is fine.

**Field ids and draw-point screens [confirmed 2026-09-10]:** `mapdata\maplist` (982
newline-separated field names, index == `FIELD_ID` at `+0x18D2FC0`) is resident whole at
**`+0x15FB118`** (the engine NUL-terminates the current entry in place). It is not in any .fl
listing. Each field's `.jsm` declares its draw points as `PSHN_L (slot+1); DRAWPOINT (0x137)` —
JSM words are `param | opcode << 24`, with high byte 0 meaning "call opcode = low 24 bits". Scanning
every field gives slot → screen(s) for all 100 field draw slots (`ff8/fields.py`, generated by
`tools/dump_kernel_text.py fields`); slot 1 (Blizzard) → bgmon_4 = field 217, drawn live. **MISC2
.location (`+0x18FE99A`) does NOT refresh on field transitions** — it read 159 "Esthar- City" on a
Disc-1 save while walking Balamb Garden and Balamb town, and `MISC2.module` said 2 (world map) in
a field. Only the save/load path seems to refresh them; the tracker's follow-the-player area
publish reads them and will be stale mid-session. `MODULE_DISPATCH` = 6 while the main menu is
open, flipping one tick before the IN_MENU byte.

**Field message table at runtime [confirmed live 2026-09-10/11]:** the current field's `.msd` is
heap-allocated whole on field load (u32 offset table then strings, byte-identical to the archive
copy, no slack after it) and its address sits in two statics, **`+0x18E4778`** and `+0x18E50C8`.
The dialog renderer reads strings from that buffer at display time: rewriting a line in place
(same or shorter byte length, NUL-terminated) changes the box text with no file patching — proven
on bcport1a by rewriting the harbor gossip to "Sent [Progressive Hookshot] to Bob!". The buffer is
never refilled while the field stays loaded (150 s idle + several dialogs), only a field load gives a
fresh vanilla copy. Gotcha: a field often carries DUPLICATE lines for different story states
(bcport1a #29 and #40 are both "Hey, have you heard?"), so patch every matching index, not the
first. Field text uses no dictionary pairs (14 of 21,353 strings), so field rewrites are plain
bytes. `ff8/pickups.py` (generated: `tools/dump_kernel_text.py pickups`) lists, per item check and
per Timber Maniacs issue, the (field id, line index, vanilla bytes) of its "Received [X]!" /
"Found an old issue of [Timber Maniacs]!" line; budgets are 22-27 bytes for items, ~90 for the
Timber Maniacs lines. Shop-bought magazines and the Centra Ruins issue have no line. Caveat seen
while testing: after a shorter replacement had been displayed, restoring the vanilla line and
showing it again drew only as many characters as the replacement had (the window keeps the last
character count for that line until the field reloads). Harmless for one-shot pickup lines, and
only ever in the shorter-then-longer direction. Tooling: `tools/dump_kernel_text.py` (FS/FI/FL +
LZS reader, MSD dump/grep, regenerates `ff8/kernel_text_vanilla.py` and `ff8/fields.py`).

---

## 4. Modding toolchain

| Tool | URL | Role |
|---|---|---|
| **FFNx** | https://github.com/julianxhokaxhiu/FFNx | Next-gen graphics/engine driver, **explicitly supports FF8 Steam 2013** (not FF8 Remastered). Hooks: DX11/DX12/Vulkan/OpenGL renderers, external textures (DDS/BC7), external music/SFX/voice, data-dir override layer, **Hext runtime patching**, RenderDoc + imgui DevTools. **No Lua/scripting or code-injection API** — asset replacement + declarative byte patching only. [confirmed] |
| **Hext** | spec by DLPB (qhimm) | Community-standard declarative patch format: text files listing address = bytes, applied to **files or live memory**. Toolset: HextEdit, HextLaunch (launcher that patches memory at runtime), Hextract, HextCompare. FFNx implements DLPB's Hext spec; patch dirs like `FINAL FANTASY VIII/HL_Files/Hext_in/`. This is the community's closest thing to a runtime injection mechanism — but it's static byte-patching, not scripting. [confirmed] |
| **Deling** | https://github.com/myst6re/deling | Field/worldmap archive editor (FS/FI/FL), edits field scripts, texts, walkmesh, encounters. [confirmed] |
| **Doomtrain** | https://github.com/DarkShinryu/doomtrain | `kernel.bin` editor (C#): weapons, items, magic, GFs, abilities, refine formulas — all static game data. [confirmed] |
| **Junction VIII** | https://github.com/tsunamods-codes/Junction-VIII | 7th-Heaven-fork mod manager for FF8, Tsunamods; **2013 Steam + 2000 PC only, not Remastered**. [confirmed] |
| **Tonberry** | (qhimm; superseded) | Old texture-replacement injector for 2013 port; **effectively replaced by FFNx**. |
| **Community wiki** | https://hobbitdur.github.io/FF8ModdingWiki/ (+ wiki.ffrtt.ru "Final Fantasy Inside") | Current tool index & technical reference. [confirmed] |

**Runtime scripting: none exists.** No tool in the FF8 ecosystem offers Lua or an injection API. An
Archipelago-style client must follow the FF speedrun/rando pattern: **external process doing
ReadProcessMemory/WriteProcessMemory against the static addresses above** — which the flat, static,
fully-mapped memory layout makes unusually easy.

---

## 5. Existing randomizers & Archipelago status

- **Maelstrom** by Sleepey — **https://github.com/sleepeybunney/maelstrom** [confirmed]. C#, supports
  **both 2013 Steam (`FF8_EN.exe` et al.) and Remastered** (Remastered partially). Randomizes: boss
  locations (with optional repeats), draws/draw points (incl. cut spells), shops/junk shops, drops &
  steals, GF abilities (incl. item-exclusive), Triple Triad card locations, music, names. **Method:
  pure file patching** — point it at the exe, it patches game files (creating `.bak` backups),
  seed-reproducible, no resident process ("You don't need to keep the Maelstrom window open"). Restore
  via "Vanilla" preset. Its source is the best existing reference for *which files encode what* for
  randomization purposes.
- **Archipelago: no FF8 world exists.** [confirmed by exhaustive search] No FF8 apworld in
  ArchipelagoMW/Archipelago, no community apworld, nothing in the Manual-worlds collections; searches
  return only FF1 (core), FF4/FF6 (WorldsCollide-AP), FF7 (IronMogAP), FF12 Trial Mode, and Fire
  Emblem 8 (fe8-, not FF8). The field is open.
- Minor: `ff8-speedruns/ff8-controls-randomizer` (controller-mapping randomizer, C#) exists but is
  unrelated to progression randomization.

---

## Bottom line for building an FF8 memory-hacking client

1. **`ff8-speedruns/ff8-memory` + `FF8Autosplitter.asl` together give nearly every address needed,
   static, no pointer chains** — gil, items array, magic per character, GF unlocks, story var (game
   moment), field ID, battle/menu flags, draw points, TT rules/stats, SeeD points.
2. Anything missing (card inventory bytes, party roster, SeeD rank byte) falls out of **Hyne's
   `SaveData.h` savemap layout + the derived live-savemap base ≈ `+0x18FDCA8`** (verify the base
   against the gil anchor).
3. Watch `0x18D8FC6` (module dispatch) / `0x18E0758` (engine state) to gate writes to safe moments
   (field, not battle/menu). [inference on gating; addresses confirmed]
4. For content-side changes (draw point spells, shops, boss shuffle), Maelstrom proves file patching
   works and shows how; for check-detection and item granting, external memory R/W is the only live
   option — there is no scripting host to piggyback on.

## Sources

[ff8-memory](https://github.com/ff8-speedruns/ff8-memory) ·
[ff8-auto-splitter](https://github.com/ff8-speedruns/ff8-auto-splitter) ·
[ff8-speedruns org](https://github.com/ff8-speedruns) ·
[speedrun.com FF8 resources](https://www.speedrun.com/ff8/resources) ·
[Hyne](https://github.com/myst6re/hyne) ·
[Deling](https://github.com/myst6re/deling) ·
[Doomtrain](https://github.com/DarkShinryu/doomtrain) ·
[FFNx](https://github.com/julianxhokaxhiu/FFNx) ·
[Junction VIII](https://github.com/tsunamods-codes/Junction-VIII) ·
[Maelstrom](https://github.com/sleepeybunney/maelstrom) ·
[FF8/Variables (ffrtt wiki)](https://wiki.ffrtt.ru/index.php/FF8/Variables) ·
[qhimm FF8 save format thread](https://forums.qhimm.com/index.php?topic=6263.0) ·
[FF8ModdingWiki tools](https://hobbitdur.github.io/FF8ModdingWiki/technical-reference/tools/) ·
[FearLess CE table t=28746](https://fearlessrevolution.com/viewtopic.php?t=28746) ·
[MULTI5 table t=10075](https://fearlessrevolution.com/viewtopic.php?t=10075) ·
[Archipelago](https://github.com/ArchipelagoMW/Archipelago) ·
[ManualForArchipelago](https://github.com/ManualForArchipelago/Manual)
