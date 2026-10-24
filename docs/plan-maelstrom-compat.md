# Maelstrom compatibility plan — 2026-10-10

**Status 2026-10-10 (planning; nothing built on main yet):**
- Shipped before this plan (v0.8.0, commit 8910bbc): the source-verified
  compatibility matrix (`plan-sync-feedback.md` §E1), the live draw-point
  table read at attach (`memory.DRAW_POINT_DEFS`), the `KernelText` "modded"
  state, guide §6 "Playing with Maelstrom", the FAQ entry.
- Verified today: a Python port of .NET Framework `System.Random` matches a
  C# oracle compiled with the `csc.exe` that ships with Windows, on 12 seeds
  including both int32 extremes (`tools/maelstrom_oracle/`). Every Maelstrom
  shuffle is therefore reproducible from its seed number at generation time.
- Maelstrom upstream: pinned at commit 756fca6 (2026-09-29, tag v0.6.6);
  nothing but music shuffle changed since the September review.
- Never done: the live confirmation seed. Maelstrom is not installed on the
  dev PC and the F: install has no `.bak` files (never patched).

## 1. Goal

A player who runs Maelstrom first (boss, card, draw-point and GF-ability
shuffles on) and then our client gets: every check firing where logic says
it is, the Ultimecia goal detected, no lock fighting the shuffled data, and
an attach-time warning when the game on disk does not match the seed the
multiworld was generated for. Free Roam stays out of scope (it rewrites the
field scripts our Story Keys and moment reads depend on, and it is a
pre-alpha upstream).

Principle unchanged from `plan-sync-feedback.md`: integrate, never rebuild.
We do not patch files; Maelstrom does. We only need to *know* what it did.

## 2. Why a seed port, not a spoiler import

The old E3 idea was parsing Maelstrom's spoiler file. Two things kill it:

- Website-hosted generation cannot read a file path, and the spoiler is a
  names-only text dump (`SpoilerFile.cs`: boss names, "Card: Field (NPC)",
  per-GF ability names) that still needs every table below to be useful.
- The shuffles are pure functions of `(seed, settings)`:

| Shuffle | Generator | Inputs |
|---|---|---|
| Cards | `new Random(seed + 3)`, one `Next(0, decks.Count)` per card in `Cards.json` order | enabled rows of `Decks.json` (245 decks, 167 fields) |
| Bosses | `new Random(seed + 2)`; Tonberry King first from solo bosses, then each encounter in `Bosses.json` order with the Restrict* filters | `Bosses.json` (61 encounters), `BossRandom` (duplicates), `RestrictSorcs/Omega/Ultimecia` ∈ normal / afterdisc1 / off |
| Draw points | `new Random(seed + 4)`, one `Next(spellIDs.Length)` per located row of `DrawPoints.json` | `Spells.json` filtered by IncludeApoc / IncludeSlot / IncludeCut |
| GF abilities | `new Random(seed + 1)`; SwapSets = a 16-way draw without replacement; RandomSets = per GF a draw per slot from the eligible ability list | `Abilities.json`, `GfAbilitiesSwapSets`, `BasicsType` ∈ off / first / all, `Count` 1..21, `IncludeItemOnly`, `NoMenuDuplicates` |

`seed` is `int.Parse(seedString)`; Maelstrom's own auto-seeds are always
numeric. A non-numeric seed falls back to `string.GetHashCode()`, which we
refuse (it differs between 32- and 64-bit runtimes).

So the apworld takes the Maelstrom seed plus the handful of toggles that
change a shuffle's *logic* (bosses, cards, abilities), recomputes the
placements, and generates against them. Draw points need no port for logic
(the client already reads the live exe table) but the port is the cheapest
seed check we have: the client compares the predicted table with the live
one at attach and warns on a mismatch.

Cost of this design: the vendored data and ported algorithms are pinned to
one Maelstrom version. The oracle harness in Phase 0 makes re-pinning a
mechanical job (regenerate vectors, diff).

## 3. Option surface (`ff8/options.py`)

All new options default to "off" and are ignored unless `maelstrom_seed` is
set. Names mirror Maelstrom's tabs so a player can copy their settings.

| Option | Type | Notes |
|---|---|---|
| `maelstrom_seed` | FreeText, default `""` | Empty = feature off. Must parse as an int32 (`OptionError` otherwise, with the GetHashCode explanation) |
| `maelstrom_bosses` | Toggle | Boss shuffle on in Maelstrom |
| `maelstrom_boss_duplicates` | Toggle | Maelstrom "with duplicates" (`BossRandom`) |
| `maelstrom_restrict_sorceresses` | Choice normal / afterdisc1 / off | default normal |
| `maelstrom_restrict_omega` | Choice normal / afterdisc1 / off | default normal |
| `maelstrom_restrict_ultimecia` | Choice normal / afterdisc1 / off | default normal; anything but normal splits the final boss (see Phase 1) |
| `maelstrom_cards` | Toggle | Card shuffle on |
| `maelstrom_abilities` | Toggle | GF ability shuffle on |
| `maelstrom_abilities_swap_sets` | Toggle | |
| `maelstrom_abilities_basics` | Choice off / first / all | `GfAbilitiesBasicsType` |
| `maelstrom_abilities_count` | Range 1..21, default 21 | |
| `maelstrom_abilities_include_item_only` | Toggle | |
| `maelstrom_abilities_no_menu_duplicates` | Toggle | |
| `maelstrom_draw_points` | Toggle | Logic-neutral; only drives the attach-time seed check |
| `maelstrom_draw_points_apoc` / `_slot` / `_cut` | Toggle | Same |

Shop, loot, weapon, price, music, Doomtrain, tweaks, emergency spell: no
option, they never touched our data (matrix §E1).

`fill_slot_data` adds a `maelstrom` dict: the seed, the toggles, the
predicted draw-point table (256 bytes, hex), the per-GF default masks and
learn lists when abilities are on, and the card → field id map when cards are
on. The client needs nothing else from generation.

## 4. Phases

### Phase 0 — Foundations (1 to 2 days)

New package `ff8/maelstrom/`:

- `dotnet_random.py`: the verified port (already in
  `tools/maelstrom_oracle/dotnet_random.py`, move it). Unit test replays the
  12 oracle vectors.
- `data/`: vendored `Bosses.json`, `Cards.json`, `Decks.json`,
  `Abilities.json`, `JunctionableGFs.json`, `DrawPoints.json`, `Spells.json`
  from commit 756fca6, with Maelstrom's MIT licence text and the pinned
  commit in a `README`. These are small (the largest is `Decks.json`).
- `shuffles.py`: `shuffle_cards(seed) -> dict[card_id, deck_id]`,
  `shuffle_bosses(seed, settings) -> dict[enc_id, enc_id]`,
  `shuffle_draw_points(seed, settings) -> list[int]` (256-byte table in our
  `DRAW_POINT_DEFS` slot order: Maelstrom's `Offset` is the slot index),
  `shuffle_abilities(seed, settings) -> list[GFAbilitySet]` where each set is
  the 21 `(unlocker, ability_id)` entries plus the init learned mask. Port
  line by line from `Boss.cs`, `CardShuffle.cs`, `DrawPointShuffle.cs`,
  `AbilityShuffle.cs`; keep the `seed + n` offsets and the exact iteration
  orders (LINQ `Where` keeps list order; `Dictionary` key order is insertion
  order for these sizes, but the ports should iterate the JSON lists, not
  dicts).
- `tools/maelstrom_oracle/`: `Oracle.cs` (already there) grows a second
  harness that loads the release `Maelstrom.exe` by reflection and calls
  `Boss.Randomise`, `CardShuffle.Shuffle`, `DrawPointShuffle.Randomise` and
  the ability generator for a grid of seeds × settings, dumping JSON. Those
  dumps become `ff8/test/fixtures/maelstrom_vectors.json`; `test_maelstrom.py`
  asserts the ports reproduce every one. `AbilityShuffle.Randomise` takes a
  `FileSource`; the harness feeds it the clean kernel/init from a vanilla
  install's `main.fs` (read-only), so run it on the dev PC once.
- Vanilla GF ability lists: `kernel.bin` section 2 is already decoded for
  `GF_ABILITY_PREREQ`; reuse `tools/dump_kernel_text.kernel_bin()` to build
  the vanilla 16 × 21 `(unlocker, ability)` table the swap-sets port needs.

Exit criterion: ports match the oracle on at least 20 seeds for each shuffle
and every settings combination the options expose.

### Phase 1 — Goal and client hardening (half a day, ships on its own)

- **Ultimecia goal under the split** (`client.py` `track_goal`): the
  three-pool phase machine never completes when `RestrictUltimecia` is not
  `normal` (encounter 511 is rebuilt to hold only the final form; 846-848
  precede it). Add a second trigger that does not need the phases: on
  `ULTIMECIA_FIELD`, `last_encounter == 511` and the battle exits with a
  living party. The vanilla fight satisfies it too, so it also backstops the
  phase machine. Keep the phase logging.
- **Attach-time seed check** (`client.py` attach path, after
  `DRAW_POINT_DEFS` is read): when slot data carries a predicted draw-point
  table, compare it with the live one. Match: log "Maelstrom seed N
  confirmed". Mismatch: a loud warning naming the first differing slot
  ("the game on disk was not patched with Maelstrom seed N and these
  settings; checks will fire but logic is for the generated seed"). When
  draw points are not shuffled, log that the seed cannot be confirmed from
  memory and fall back to the kernel check from Phase 3.
- `/ff8verify` prints the maelstrom block of slot data and the check result.

### Phase 2 — Card shuffle with honest logic (2 to 3 days)

The only data missing is where each deck *is* in our region model.

- `ff8/maelstrom/decks.py`: `DECK_FIELD_REGIONS: dict[str, tuple[str, str | None, bool]]`
  keyed by Maelstrom `FieldID` (all 167 are in `fields.FIELD_NAMES`, verified):
  `(beat, story_key_area or None, missable)`. Group by town to fill it:
  Balamb Garden 30 fields, Esthar 26, Timber 15, Balamb 13, Dollet 12, FH 11,
  Galbadia Garden 9, Shumi 8, Ragnarok 8, Winhill 7, Deling 7, Trabia 7,
  Lunar Base 5, Lunar Gate 4, and one each for D-District, Odine's lab,
  Centra, the White SeeD ship and Edea's House. Beat = the first beat whose
  main line (or `AreaData` key) makes the field reachable; `missable` = the
  NPC is gone later (Laguna-dream fields, the train, the White SeeD ship,
  Lunar Base, D-District). Err late, exactly as `_CARD_REGIONS` does today.
  Per-NPC overrides for the handful of decks that appear only in one story
  state (Queen of Cards stops, CC Group members) go in a second, smaller
  dict keyed by `(FieldID, EntityName)`.
- Generation (`__init__.py` `create_regions` / the rare-card block in
  `locations.py`): when `maelstrom_cards` is on, build `_CARD_REGIONS` from
  `shuffle_cards(seed)` → deck → field → region instead of the vanilla
  table. Location names and ids do not change (datapackage stability); only
  `region`, `missable` and the Story Keys area (`AREA_LOCATIONS` is derived
  from the same lookup) move. A card landing on a field with no table entry
  fails generation with the field named, so the table cannot rot silently.
- Client: when a rare-card check fires, log the live `FIELD_ID` against the
  predicted field; mismatch → the same "wrong seed" warning as Phase 1.
- Tracker: Universal Tracker follows the logic automatically. The PopTracker
  pack's Rare Cards tab keeps vanilla holders; add one line to its notes.
  (A per-seed pack is possible from the same table but is not worth it until
  someone asks.)
- Guide §6: card shuffle moves from "turn `rare_card_checks` off" to
  "supported with `maelstrom_cards`".

### Phase 3 — GF ability shuffle (3 to 5 days)

What breaks today: `ability_locks` / `junction_locks` / `command_locks`
restore `memory.GF_ABILITY_DEFAULTS` (vanilla) every tick, the GF Abilities
ladder counts "learned beyond vanilla default", and logic uses
`GF_LEARN_LISTS`, `GF_SIGNATURE_ABILITIES`, `GF_ABILITY_PREREQ`.

- Generation: `shuffle_abilities` yields, per GF, the 21-slot list, the
  init-learned mask (SwapSets: the matched GF's vanilla mask; RandomSets:
  bits 20-23 when basics apply, else empty) and the prerequisites (SwapSets:
  the matched GF's unlockers; RandomSets: none, Maelstrom writes unlocker 1).
  Wrap the three vanilla tables in a `GFAbilityTables` object the world
  builds once and threads through `__init__.py` and `regions.py` in place of
  the module constants.
- `ability_locks` cannot follow the shuffle: its items are named
  "Quezacotl: Card Mod" (46 items, one per vanilla signature). Under
  `maelstrom_abilities` the option is forced off at generation with a logged
  reason. `junction_locks` and `command_locks` are per ability, not per GF,
  so they keep working once the client restores the shuffled defaults.
  (Stretch, only on demand: a GF-agnostic ability-lock item set, "Lock:
  Card Mod", which would also simplify vanilla.)
- Logic: junction availability = any GF whose shuffled list holds the
  junction (today it is the vanilla GF set); the GF Abilities ladder tier
  sizes come from the shuffled lists' lengths (RandomSets with `count` 5
  leaves far fewer learnable abilities; cap the ladder so no tier exceeds the
  total learnable count); prerequisite rules from the shuffled prereqs.
- Client: slot data carries the 16 default masks and learn lists. Locks use
  them instead of `GF_ABILITY_DEFAULTS`; `gf_abilities_learned` subtracts
  the slot-data default bit counts. At attach, read kernel section 2 from
  the resident block (`text.KERNEL_BASE + SECTION_OFFSETS[2]`, 16 records,
  21 × 4-byte entries at the known offset) and compare ability ids with the
  slot data: this confirms the seed and settings even when draw points are
  vanilla. Mismatch → warning, and the locks fall back to *not* restoring any
  bit they cannot account for (never clear a bit that is in neither table).
- In-game text: GF ability names are kernel text we do not rename; nothing
  to do.

### Phase 4 — Boss awareness (half a day to a day, optional)

Boss shuffle already works for checks and GF revokes (encounter ids stay
put, `award-gf` scripts move, the Tonberry King flag moves). With the port
in hand the remaining value is informational: `/ff8maelstrom` prints the
boss map ("Dollet tower: Elvoret → Jumbo Cactuar"), the card holders and the
draw-point spells, so a player need not keep the spoiler file open. The
optional-boss and GF checks stay keyed on the vanilla encounter ids; no
logic change. Skip if time is short.

### Phase 5 — Live verification, docs, release (1 day plus one live session)

Live session, in this order, on the dev PC (ask before patching the modded
install; Maelstrom patches the four archives in place with `.bak` backups
and touches the exe only for draw points, so FFNx and Junction VIII should
coexist; restore via the Vanilla preset afterwards):

1. Install Maelstrom v0.6.6, Set Seed = a fixed number, bosses + cards +
   draw points + abilities (SwapSets) on, spoiler file on.
2. Diff the spoiler file against `shuffle_*` output for that seed: this is
   the end-to-end proof of the ports on a real install.
3. Generate a short AP seed (Disc One Rush preset + the maelstrom options),
   attach, confirm the draw-table and kernel checks pass, then: one boss
   check and its GF revoke at the vanilla place; one shuffled rare card from
   the predicted NPC; a draw-point rename over the modded kernel; a junction
   lock restoring a shuffled default; the Ultimecia goal via a castle save
   with `RestrictUltimecia: off` on a second Maelstrom roll.
4. Repeat step 3 with the wrong seed to see the warnings fire.

Docs: guide §6 rewritten around the options (define "seed" and "Set Seed"
inline, per the jargon rule), FAQ entry, `design.md` §4 item 9, a release
note. Release as a minor version (new options and slot data).

## 5. Stays unsupported, and why

- **Free Roam**: rewrites field scripts and story flow wholesale; our
  moment reads, Story Keys doors and pickup text all assume vanilla scripts.
- **`ability_locks` with ability shuffle**: item names carry the GF (see
  Phase 3); forced off, everything else in the ability family works.
- **Non-numeric Maelstrom seeds**: refused at generation.
- **Remastered**: never supported by this apworld anyway.
- **Mid-seed re-rolls**: the guide already says to restore the same seed
  and settings; the attach check now catches it.

## 6. Risks

- **Version drift**: a Maelstrom data-table or algorithm change silently
  changes every placement. Mitigations: pinned vendored data, the oracle
  fixtures, the attach-time checks (draw table, kernel lists, per-card
  field) that turn a drift into a warning instead of silent bad logic, and a
  guide line naming the supported Maelstrom version.
- **Deck table errors** (Phase 2): a card placed one beat too early is an
  out-of-logic check, not a softlock; a card placed on a missable NPC that
  is not flagged missable can strand a progression item. Default the
  uncertain rows to missable and late.
- **Ability ladder sizing** (Phase 3): RandomSets with small `count` can
  shrink the learnable pool below the vanilla tier thresholds; generation
  must clamp or drop tiers rather than place unreachable checks.
- **Kernel section 2 layout in memory**: `KERNEL_BASE` and the section
  table are proven for the text sections; the GF record stride for section 2
  is read from the file today, not from memory. Verify once live with
  `/ff8verify` before relying on it.
- **Live test touches the dev install**: do it with the user's go-ahead;
  the Vanilla preset restores the archives from `.bak`.

## 7. Order and estimates

| Step | Effort | Depends on | Release |
|---|---|---|---|
| Phase 1 goal fix + draw-table check | 0.5 day | nothing (the check needs Phase 0's draw-point port, ship the goal fix first) | next patch |
| Phase 0 foundations | 1 to 2 days | nothing | with Phase 2 |
| Phase 2 cards | 2 to 3 days | Phase 0 | minor release A |
| Phase 3 abilities | 3 to 5 days | Phase 0 | minor release B |
| Phase 4 `/ff8maelstrom` | 0.5 to 1 day | Phase 0 | with A or B |
| Phase 5 live session + docs | 1 day + 1 session | A (then again after B) | each release |

Total: roughly two working weeks for the full set, with the goal fix and
the card support shippable after the first week.

## 8. Test plan

- `test_maelstrom.py`: the 12 Random vectors; the oracle shuffle fixtures;
  a generation test per option combination (cards on, abilities swap,
  abilities random with count 5, all off) asserting every rare-card
  location has a region in `REGION_CHAIN`, no ladder tier exceeds the
  learnable total, and `ability_locks` is forced off.
- `test_feedback_fixes.py`-style client test for the goal fallback: a fake
  context on field 573 with `last_encounter` 511 exiting alive sends the
  goal with the phase machine stuck at 0.
- The existing `test_memory.py` draw-point spell check gains a sibling: the
  ported draw-point shuffle with seed 0 and all filters off produces a table
  whose every byte is a valid spell id with the refill/bountiful bits kept.
