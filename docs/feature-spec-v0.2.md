# FF8 Archipelago — v0.2 Feature Spec (2026-09-02)

Specs the post-beta feature set chosen from a comparative survey of the other Final Fantasy /
Kingdom Hearts Archipelago integrations (FF1, FF4FE, FF5CD, FF6WC, FFMQ, FF7pelago, FFX,
FF12 Open World, FFT: Ivalice Island, FFTA/A2, FF13-2/LR, KH1/KH2). Selection criterion: ideas
that thicken our thin progression pool or add goal/cross-game variety **without violating the
no-patching rule** (design.md §1 — live savemap writes only, story stays vanilla).

The survey's headline finding: at all-options our pool is ~560 filler / 580 slots with only
18+5 progression items, while every well-liked FF/KH world derives its texture from ability,
region, or permission items. `character_locks` (2026-09-02) was the first fix; F1–F3 below
continue it. Everything here is generation- or client-side; nothing new is required from
`memory.py` beyond one offset (F1's optional AP refund) and one write pattern already proven
(`clear_char_junctions`-style masking).

Feature order = recommended build order.

---

## F1. GF Ability Locks (`ability_locks`) — progression thickener

> **Status: IMPLEMENTED 2026-09-03** (F1.1 + F1.2; F1.3 AP refund still
> research-gated on the GF AP-field offset). Shipped alongside F2 and F7 as
> the "early-game handicap" slice; live VERIFY items below still stand.

*Pattern source: KH2 ability items / FF5CD job abilities / FFT job unlocks, adapted to the
`character_locks` enforcement model.*

**Player-facing.** New toggle option **GF Ability Locks** (default off). When on, each of the
**49 signature GF abilities** (the ones that already have checks: refines, Enc-None, Mug,
Card Mod, stat Bonuses, Tonberry's shop tricks, the Auto-*s…) has a matching multiworld item
**"&lt;GF&gt;: &lt;Ability&gt;"** (e.g. `Quezacotl: Card Mod`, item group `GF Abilities`,
offsets 600–648). Until the item arrives, the GF can still *learn* the ability in-game — the
learn still **sends its check** — but the client revokes the learned bit within a second and
(optionally, F1.3) refunds the AP. Once the item is received, the ability sticks (relearn if it
was revoked earlier; with the AP refund that costs only menu time). Non-signature abilities
(the other ~195) are never intercepted.

**Why the locks model and not granting.** Granting `completeAbilities` bits directly is the
obvious design and it is wrong twice over:

1. A granted bit makes the game consider the ability learned, so the player can never fire the
   learn edge — every early-arriving item would permanently kill its own check (no backup
   trigger exists, unlike GF `boss` triggers).
2. Granted bits corrupt every mask-derived reading: `bits_all` Mastered checks would fire off
   received items, and `gf_abilities_ge` ladder tiers would count grants as learning.

The locks model (identical in shape to `character_locks`: the item is client state, enforcement
is a revocation write on safe ticks) has none of these problems: bits only ever get set by real
learning, so all existing triggers keep their exact semantics.

**F1.1 Generation.**
- `items.py`: 49 `ItemData` entries, grant `("ability", gf_index, bit)` where `bit` is the
  Hyne ability id already used by the `flag_bit` checks. Classification **progression** — they
  gate the Mastered checks (below). A generation test asserts the 49 names are unique.
- Pool membership conditional on the option (same `create_items` pattern as `CHAR_UNLOCKS`).
- Logic: each **"GF Mastered"** check (`bits_all` over the 22-ability learn list) additionally
  requires that GF's signature-ability items — without them the mask can never be complete.
  Signature-ability *learn* checks themselves need **no** new rule (the learn fires
  pre-revocation), and the party ladder needs none either: 244 − 49 = 195 uninterceptable
  abilities still satisfy the highest in-logic tier (150; the 200 tier stays EXCLUDED).
- Presets: **Junction Master** adds `ability_locks: true`.

**F1.2 Client.**
- Enforcement tick (inside the existing safe-tick re-assert pass): for each GF, compute
  `locked_mask = signature_bits & ~received_bits`; if `snapshot mask & locked_mask` is nonzero,
  clear those bits at `gf_abilities_addr(gf_index)` (record `+20`, 16 bytes). Never enforced
  while a foreign save is frozen (BULK_GATE), mirroring junction locks.
- Check detection is untouched: learn edges and the attach-time state catch-up
  (bit set + check unsent → learn happened offline → send, then revoke if unpermitted) fall out
  of the existing `flag_bit` machinery plus the enforcement pass ordering: **detect first,
  revoke second, same tick**.
- `/ff8` gains a per-GF locked/permitted summary line; `/ff8verify` asserts
  `signature_bits ⊆ GF_ABILITY_DEFAULTS`-disjoint (a signature ability must not be in any
  default mask, else it would be revoked at game start — generation-time assert too).

**F1.3 AP refund (optional polish, recommended).** On revocation, add the ability's AP cost
(known per ability from Hyne `Data.cpp`, already vendored for the region pacing) back to that
GF's AP pool so a pre-item learn costs nothing but menu time. Needs the GF record's AP field
offset — the one new `memory.py` research item in this spec. Ship F1 without it if the offset
isn't settled; the feel is worse but nothing breaks.

**VERIFY (live):** clearing a learned bit is accepted by the game outside menus (Hyne does this
to saves; we do it to live memory — confirm the ability menu and junction effects update, and
that clearing an *equipped* ability (Enc-None, Auto-Haste) safely unequips rather than dangling
— test explicitly with Enc-None active). Confirm a revoked ability can be relearned and
re-fires nothing (check already sent — dedup is server-side anyway).

**Risk & effort.** Low risk (write pattern proven by junction locks; worst case = option ships
default-off). ~2–3 sessions including the live verify.

---

## F2. Progressive Magic (`progressive_magic`) — checks-only mode only

> **Status: IMPLEMENTED 2026-09-03.** As spec'd, with one delta: the starter
> kit swap folds into the new `starter_magic` option (F7.3) — under
> `progressive_magic` the basic kit is [Progressive Fire/Blizzard/Thunder/
> Cure, Sleep x10], `none` precollects nothing, `generous` adds a second
> Progressive Cure + Progressive Life + Protect/Shell.

*Pattern source: FFMQ Progressive Gear, FF13-2 Progressive Mog Level.*

**Player-facing.** Toggle (default off, only meaningful under `magic_mode: checks_only`).
Five spell families become count-based **progressive items** — the Nth copy received unlocks
the Nth stage cap:

| Item (copies in pool) | Stage 1 | Stage 2 | Stage 3 |
|---|---|---|---|
| Progressive Fire ×3 | Fire x20 | Fira x15 | Firaga x10 |
| Progressive Blizzard ×3 | Blizzard x20 | Blizzara x15 | Blizzaga x10 |
| Progressive Thunder ×3 | Thunder x20 | Thundara x15 | Thundaga x10 |
| Progressive Cure ×3 | Cure x20 | Cura x10 | Curaga x10 |
| Progressive Life ×2 | Life x10 | Full-life x5 | — |

Base-tier spells (Fire/Blizzard/Thunder ids 1/4/7) join the roster only through these chains
(they're currently absent — the roster starts at the -ra tier). All other spells stay
standalone items. Every stage grant raises the family's *stage spell* cap exactly like a flat
magic item; casting/drawing semantics unchanged.

**Generation.** New items at offsets 260–264, classification useful. When the option is on,
`create_items` removes the 14 subsumed flat items (`Fira/Blizzara/Thundara x15`, `Cure x20`,
`Cura/Curaga x10`, `-ga trios`, `Life x10`, `Full-life x5`) from the filler roster and seeds
the 14 progressive copies into the pool directly (not via filler weights — fixed counts), so
total magic density is preserved. `STARTER_MAGIC` swaps to
`[Progressive Fire, Progressive Blizzard, Progressive Thunder, Sleep x10]` + one
`Progressive Cure`.

**Interplay with `tiered_magic`.** Progressive copies are **excluded from the post_fill
re-sort** — copy-counting self-paces them (the 3rd Fire can't precede the first two), and
identical names make sphere-sorting meaningless. `MAGIC_TIERS` coverage assert updates to
"every *flat* magic grant".

**Client.** The cap ledger keys on received-count per progressive name → stage spell id + qty
(a static table next to `MAGIC_TIERS`). `/ff8magic` prints family stages
(`Fire ██░ 2/3`).

**Risk & effort.** No new memory surface at all; ~1 session + tests. The main cost is
generation-test coverage of the roster swap (pool size invariants under all option combos).

---

## F3. Goal requirements: GF gate + Bounty mode

*Pattern source: FF6WC's adjustable Kefka gates, KH2 Hitlist/Bounties, FF4FE objectives.*

**F3.1 `gfs_required_for_goal`** (Range 0–16, default 0). Logic: the Victory event additionally
requires `has_group("GFs", n)`. Client: `CLIENT_GOAL` is only sent when the requirement is met
at detection time (kill Ultimecia early and the goal simply completes later, the moment the Nth
GF arrives — log a clear "goal deferred: 4/10 GFs" line). Pairs naturally with
`gfs_required_for_disc3`; add a generation assert `goal ≥ disc3` is *not* required (they're
independent proxies) but warn in the option docstring that goal &lt; disc3 is the usual choice.

**F3.2 Bounty mode: `bounties`** (Range 0–10, default 0). Generation picks N random bosses from
the **non-missable optional boss candidates** (13: Odin, UFO??, PuPu, Ultima Weapon, Jumbo
Cactuar, the 8 Ultimecia Castle bosses) and requires their kills for victory alongside the goal
boss:

- Each chosen bounty gets a **hidden event location** sharing the boss's battle trigger, holding
  a locked `Bounty: <boss>` event item; Victory requires all N (the visible boss check keeps
  holding its normal pool item — no slot is consumed).
- Chosen bounties are published in **slot data** (and therefore UT); the PopTracker pack gets a
  bounty badge on the corresponding boss pins + a bounty checklist in the Quests tab
  (`gen_tracker_pack.py` reads the same slot-data key).
- Candidates already excluded by disabled check groups are still valid bounty targets — the
  event location is independent of `optional_boss_checks` (detection is the battle tracker,
  which always runs). Odin's known timer-expiry false-credit caveat (design.md §2) is accepted
  here exactly as it is for his check.
- `goal: omega` + bounties composes fine (Omega itself is never a candidate).

New preset **Bounty Hunter**: `goal: ultimecia`, `bounties: 6`, `gfs_required_for_goal: 8`,
all check groups on.

**Risk & effort.** Pure generation + slot-data + tracker work, ~1–2 sessions. No client memory
changes (battle tracker already credits these encounter IDs).

---

## F4. Trap expansion, per-trap weights, TrapLink

*Pattern source: FF7pelago (16 weighted traps + TrapLink).*

**F4.1 New traps** (same contract as the existing three: one-shot savemap writes on a safe
field tick, recoverable, never KO/strand, never touch checks):

| Trap | Offset | Effect | Write |
|---|---|---|---|
| Tithe | 403 | lose 10% of gil (min 500, floored at 0) | `take_gil` with computed amount |
| Item Snatch | 404 | lose up to 3 of a random *consumable* stack | `remove_item`; candidate ids = the filler consumable table only — never key items, magazines, or refine materials the player farmed |
| Card Snatch | 405 | lose duplicates (down to 1, never to 0) of a random common card held &gt;1 | write TTCARDS low-7-bit qty; **bit-7 "seen" flag untouched**, so `cards_owned` / compendium checks are provably unaffected (refining already drains qty the same way) |

Rejected: a draw-point drain trap — writing any slot out of Full *is* the `draw` check trigger,
so it would send checks; not worth special-casing.

**F4.2 `trap_weights`** (OptionDict, default = current built-ins + new traps at weight 2/2/1).
Zero-weight removes a trap from the pull table; `trap_chance` keeps governing the overall rate.
Validation at generation: unknown keys error, all-zero falls back to defaults with a warning.

**F4.3 TrapLink** (`trap_link` Toggle, default off). Standard TrapLink tag protocol: our traps
broadcast on fire; incoming linked traps map by name → nearest local effect via a static table
(anything gil/money-ish → Gil Snatch or Tithe, HP/damage-ish → Ambush, mana/magic-ish → Magic
Leak, item-ish → Item Snatch, everything unmatched → Gil Snatch). Incoming traps respect the
same safe-tick + non-lethal contract; while a foreign save is frozen they are dropped, not
queued (matching how we treat traps as one-shots, and avoiding a post-adopt burst).

**Risk & effort.** ~1 session client-side + option plumbing. Card Snatch needs the TTCARDS
qty-write verified live once (bit-7 preservation is the only invariant).

---

## F5. EnergyLink (`energy_link`) — gil-backed

*No FF/KH world has EnergyLink; cheap differentiator, and gil is the one resource we can move
in both directions safely (`add_gil`/`take_gil`).*

- Exchange rate: **1 EnergyLink unit = 1 gil**. Deposits: 25% of every *gil filler item*
  granted (the player receives 75%; the item log line says so). Nothing else auto-deposits —
  traps and vanilla gil stay local.
- Withdraw: `/ff8energy` shows the pool; `/ff8energy withdraw <amount>` requests up to that
  much from the shared pool → `add_gil` on the next safe tick. Standard EL DataStorage ops
  (`EnergyLink{team}` key, atomic add with floor-at-zero semantics on withdraw).
- Option default off; when off, gil items grant 100% and the commands explain the option.

**Risk & effort.** Half a session; the only design point worth care is rounding (integer gil,
track the remainder locally so repeated deposits don't leak value).

---

## F6. Junk conversion (`junk_to_gil`)

*Pattern source: FF4FE's junk-tier auto-sell ("items of this tier or below are automatically
sold for cold hard cash") — its most-praised QoL option.*

Toggle (default off). When on, **filler-class consumable items** convert to a flat gil grant on
receipt instead of inventory writes; useful-class items (Elixir, Mega-Potion/Phoenix, Energy
Crystal, 10000 Gil…) always deliver as themselves. Conversion values live in the item table
(new optional `sell_gil` field on `ItemData`): Potion Pack 400, Hi-Potion Pack 600, X-Potion
Pack 1000, Phoenix Down Pack 750, Remedy Pack 750, Tent Pack 600, Cottage 450, Dragon Fang 500.
Magic items never convert (they're the junction economy). Log line: `Potion Pack → 400 gil
(junk conversion)`. Composes with F5: converted gil counts as a gil item for the 25% deposit.

Client-only (the pool itself is unchanged, so the option is purely local and even
post-generation-safe — a nice property FF4FE doesn't have). ~Half a session.

---

## F7. Early-game handicap: junction locks, command locks, starter magic

> **Status: IMPLEMENTED 2026-09-03** (spec written retroactively with the
> implementation — the design conversation is the primary source).

**Motivation.** Beta observation: the classic AP "massively handicapped until
others send items" sensation never happens — FF8's power is draw + junction,
and the defaults leave both fully vanilla. The v0.2 pool thickeners (F1/F2)
don't create the *early* crunch by themselves: F1's signature abilities are
utility, and one received GF restores its full default junction set. F7 locks
the power system itself, below the GF level.

**F7.1 `junction_locks`** (Toggle, default off). Twelve items named exactly
like the junction abilities (`HP-J` … `ST-Def-J`, offsets 700-711,
progression). Enforcement is the F1 revocation pattern applied to
**default-mask bits across all 16 GF records**: while an item is missing its
bits (incl. governed x2/x4 upgrades) are cleared everywhere, and magic
junctioned to that stat is zeroed in the char records (per-stat bytes of the
`character_locks` junction block, Hyne field order — the one new VERIFY).
On receipt the GFs' **default** bits are re-asserted every safe tick.

Why this is safe where F1's grant-bits analysis said "never set bits":
restoring a *default* bit returns the record to its vanilla new-game state —
`gf_abilities_ge` counts beyond-default only (restores contribute 0), Mastered
`bits_all` masks already contained default bits at new game, and no junction
bit is a signature check (Luck-J, the one overlap, is excluded from the
groups; asserted at import and in tests). The restore domain is
option-governed bits only, so nothing else is ever force-set.

- Precollect: one random junction item (mirrors `character_locks`; guarantees
  the client's items-synced gate arms immediately, and something is always
  junctionable once a GF arrives).
- Logic: each "GF Mastered" additionally requires the junction items covering
  bits in that GF's learn list. The 150 party-ladder tier stays item-free:
  244 beyond-default learns − 90 interceptable under ALL lock options = 154
  (test-asserted ≥ 150).

**F7.2 `command_locks`** (Toggle, default off). Magic/GF/Draw/Item Command
items (offsets 720-723, progression), same mechanism on bits 20-23 (default
on every GF, in every learn list): cleared from all records while locked,
equipped command slots (`+0x50-0x52`) holding the id zeroed, defaults restored
on receipt. Attack + limits always remain; field-menu item use is untouched,
so healing between fights always works. Mastered checks require all four under
the option.

**F7.3 `starter_magic`** (Choice none/basic/generous, default basic). Scales
the checks-only precollected kit; `none` is the "no verbs until the multiworld
feeds you" opening. Ignored under vanilla magic.

**Client cross-cutting.** One enforcement pass (`enforce_gf_locks`) runs after
`grant_items` on safe ticks — detect first, revoke second, same tick — and is
gated on `items_synced` (set on the connection's first ReceivedItems packet)
so a reconnect race can never revoke a permitted ability; F1 revocations are
irreversible-until-relearn, so this gate matters. Pool-overflow validation:
lock items without enough enabled locations raise a readable OptionError at
generation instead of a fill failure.

**Presets.** `Junction Master` gains `ability_locks` + `junction_locks`; new
**SeeD Cadet** preset = every lock option + progressive checks-only magic +
`starter_magic: none` + 1 starting GF — the underdog opening as a one-click.

**VERIFY (live, shares F1's session):** clearing default junction/command bits
is accepted outside menus and the junction/battle menus update; zeroing one
per-stat junction byte reads back as exactly that junction removed (byte order
is Hyne's struct order, not yet live-diffed); an equipped locked command slot
zeroed while on the field doesn't dangle in the next battle.

---

## Tier 2 — research-gated (spec'd for direction, not committed)

- **`exp_multiplier`** (1–4): after each battle-end pulse, diff each char's EXP u32 against the
  pre-battle snapshot and write `base + delta × (mult−1)`. FF8's flat 1000/level curve means
  level is derived from EXP, so the write *should* just take (same reasoning as the Squall
  level ladder reads). VERIFY: stat/level-up processing when EXP jumps multiple levels in one
  write, and interaction with the level-scaled enemy system (this option is a difficulty
  *increase* in FF8 — say so loudly in the docstring). Do not ship before a full disc of live
  play.
- **Shopsanity heuristic**: detect "first purchase at shop X" via shop-menu module state +
  gil-decrease + inventory-delta within one tick window. No write path needed (checks only).
  Fragile by construction — prototype behind a hidden option and measure false-positive rate
  during the campaign playthrough before ever exposing it.
- **Per-enemy Scan checks**: already on the backlog (design.md §2, `ennemy_scanned_once`
  bit-order needs one live diff); the survey confirms the pattern's popularity (FFX
  CaptureSanity, FFT poach). Unblocks ~30 checks for free once the bit order is settled.

Explicitly *not* adopted, with reasons on record: open-world/region-unlock items and entrance
shuffle (require field-script patching — the defining trade of our design), in-game received
item text (same; remains player-guide §13 limitation), FFTA-style player-named NPCs (no text
writes), KH1-style per-companion DeathLink granularity (FF8 wipes are party-level; no
per-character death concept outside battle).

---

## Cross-cutting

- **Slot data / UT**: every new option lands in slot data + `interpret_slot_data`; bounties add
  a `bounty_ids` list. UT regen-from-slot-data must reproduce bounty event locations.
- **Tracker**: `gen_tracker_pack.py` — bounty badges + checklist (F3.2), GF Abilities tab item
  rows gain lock-state coloring under `ability_locks` (F1), nothing else changes.
- **Tests**: `WorldTestBase` option-combo matrix extends with
  `ability_locks × character_locks × magic_mode × progressive_magic` and bounty fills at 0/1/10;
  pool-size and offset-uniqueness invariants cover offsets 260–264, 403–405, 600–648.
- **Docs**: player-guide sections per feature; option docstrings are the primary UX surface
  (WebHost) — write them player-first like the existing ones.
- **Versioning**: F1–F3 are generation-affecting → **v0.2.0** (seed-incompatible, bump
  `archipelago.json`); F4–F6 are client/pool-local → v0.2.x point releases are fine, except
  F4.1's new trap *items* which are also generation-affecting → ship trap items with v0.2.0
  even if TrapLink lands later.

## Sequencing

1. **v0.2.0**: F1 (ability locks) + F2 (progressive magic) + F7 (junction/command
   locks, starter magic) — **implemented 2026-09-03** — + F3 (goal gates/bounties)
   + F4.1 trap items — one seed-breaking release, beta'd together.
2. **v0.2.1+**: F4.2/4.3 (weights, TrapLink), F5 (EnergyLink), F6 (junk conversion).
3. **Research track** (parallel, no release coupling): F1.3 AP-refund offset, scan-check bit
   order, shopsanity prototype, exp-multiplier verification — all fed by the ongoing campaign
   playthrough's flight recorder.
