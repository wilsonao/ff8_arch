# Beta feedback plan — Discord thread, 23–27 Sep 2026

**Status 2026-09-28:** Phases 0–3 BUILT (uncommitted at time of writing; 531
tests pass, packs regenerated as 0.14.0, world 0.8.0, announcement drafted in
docs/release/v0.8.0-announcement.md). Not done: Phase 4 options (4.1), the
FH/Centra "story-window doors" without keys (2.3, needs the FH entrance offset
— the entry table shows FH gated at moment 636 on foot, so how the Ragnarok
got in is unverified), the Lunatic Pandora despawn research (2.3), and the
Magical Lamp with Diablos owned (2.9, needs a live test). 0.7.1 was folded
into 0.8.0 rather than released separately.

Source: screenshots of the Archipelago Discord thread (Gaothaire, Loto, AmphaRaven,
DrMisunderstood, Konzera, Pianoman7117, Hukos). Every report below was checked
against the code on main (8910bbc) and, where possible, the 285-save library.
"Verified" means the cause is confirmed in code or data; "likely" means the
report fits the code but the trigger has not been reproduced live.

Released state: v0.7.0 (2026-09-15). One unreleased commit, 8910bbc, carries
the enc-assist log-spam fix, Maelstrom rename compatibility and nine corrected
world draw-point spells. The Lamp/Ring rename scoping (948253a) IS in v0.7.0.

## Phase 0 — Release 0.7.1 now

Nothing on main is risky; players on 0.7.0 are missing the enc-assist fix and
the nine wrong world draw-point names. Cut 0.7.1 before starting Phase 1 so the
bigger fixes get their own release.

## Phase 1 — Client bugs that corrupt saves or checks (highest priority)

### 1.1 Faked story moment 3167 persists into saves (AmphaRaven) — VERIFIED
The early-Ragnarok feature writes moment 3150+17 = 3167 during battle modules
and a 3 s grace window (`client.py:762-834`). AmphaRaven's save read 3167 on
Disc 2; that number is ours.
Leak paths found in code:
- Any exception in `game_watcher` (`client.py:2428-2432`) or `moment_window_loop`
  (`:2086-2090`) is treated as "lost process" and clears `moment_faked` /
  `true_moment` WITHOUT writing the true value back. After that, 3167 is
  above the threshold so `vehicle_window_target` returns None and the fake is
  never undone. Next save bakes it in.
- Server disconnect mid-battle: both loops stop while `ctx.server`/`ctx.slot`
  are unset (`:2080-2081`, `:2393`); player can open the menu and save.
- Instance-lock stand-down (`:2027-2036`) stops the loop without restoring.
- Client killed (not clean shutdown).
- No load-time detection or repair exists.
Fix:
1. In both `except` blocks: call `restore_true_moment` (best effort) BEFORE
   clearing state.
2. Restore on `on_package` disconnect / socket loss and on stand-down.
3. Persist `true_moment` to the sidecar each time a fake starts; on attach,
   if live moment == fake target and the sidecar's true moment is below the
   threshold, write the sidecar value back and log a one-line repair notice.
   Also refuse to raise `max_moment` / fire story checks from a moment that
   equals the fake target unless the sidecar agrees.
4. Do not fake for battles entered from a field (module 1 origin): no
   world-map rebuild follows, so there is nothing to gain and field scripts
   can read 3167 on return.
5. Do not fake while true moment < 150 (Dollet exam / SeeD Squall model);
   Hukos confirms the invisible-Squall vanilla bug in that window.
6. Tests for each leak path (exception mid-fake, disconnect mid-fake, repair
   on attach).

### 1.2 Checks credited from the previous seed's memory (DrMisunderstood) — VERIFIED
New seed, same client, immediately sent "Tomb: Brothers", "SeeD Rank: 5",
intercepted Quezacotl and revoked Shiva. Causes:
- `save_fingerprint = crc32(seed_name:auth)` but `CommonContext.seed_name` is
  never set, so every seed with the same slot name shares a fingerprint
  (`client.py:630-631`; the sidecar already switched to `ff8_server_seed_name`
  at `:595-599`, the fingerprint did not).
- `is_safe()` does not exclude the title screen (module 0), which still holds
  the last loaded save (`memory.py:842-851`).
- `won_encounters`, `ap_set_gf_flags`, `ap_set_dream_bits`, `prev_item_counts`
  are never cleared on Connected; `prev_gf_flags` only on attach.
- `grant_items` reuses the old seed's applied-items cursor from the AP header
  (`:1717-1735`), so the new seed's first N items would be skipped.
Fix: fingerprint from `ff8_server_seed_name`; store the fingerprint in the AP
header and treat a mismatch as "foreign save" (bulk hold + `/ff8adopt` path);
skip all detection on module 0; clear per-session sets on Connected; reset
the applied-items cursor when the header fingerprint differs.

### 1.3 "Steps Taken 20,000" on first world-map entry (DrMisunderstood) — VERIFIED (tiers, not offset)
Settled in a parallel session on 2026-09-28 against the save library: the
counter is real and resets on New Game, but the world map ticks ~30/s per
frame of movement versus ~7/s in fields, so the Fire Cavern trip alone
reaches 12k–18k. Library minima per region: Galbadia 104k, Missile Base 202k,
Garden War 275k, Sorceress Memorial 404k. Current tiers 20k/60k/150k/300k
(ids 765–768) fire one or two beats early.
Fix: retier to 100k (Galbadia) / 200k (Missile Base) / 270k (Garden War) /
400k (Sorceress Memorial). Threshold is in the location name, so this touches
`ut_name_mapping.json`, both tracker packs (regen) and needs a world version
bump. Still worth a five-minute live sanity read via `/ff8verify`.

### 1.4 "First Draw: <spell>" fires when the spell is RECEIVED (Konzera, DrMisunderstood) — VERIFIED
First Draw = `flag_bit` on `magic_drawn_once` 0x18FE95C (`locations.py:859-878`).
`add_magic` only writes stock (`memory.py:1071-1106`) but the game evidently
sets the "drawn once" bit when stock first appears. Progressive magic goes
through the same path and also feeds the Magic Collection popcount ladder.
Fix: snapshot the bitmask before each grant; after the grant, clear any bit
that appeared for a spell we just wrote (the client owns that write; a later
real draw sets it again). Test with a fake-memory harness.

### 1.5 "Battle won: encounter 514" repeating during Triple Triad (DrMisunderstood) — LIKELY
`track_battle` treats any nonzero `POST_BATTLE` (0x1678CA4) as a battle and
logs the stale `ENCOUNTER_ID` on the falling edge (`client.py:1232-1269`,
`memory.py:817-840`). A pulsing byte during a card game repeats the log.
Side effects: stale boss ids can satisfy `("boss", enc)` triggers and the
Omega goal; card games count as battles for DeathLink and assist; `is_safe`
pauses detection.
Fix: require module 3 to enter the "fighting" state; use `POST_BATTLE` only
for the results phase; clear `ENCOUNTER_ID` bookkeeping on leaving module 3.
Verify the card-game module/byte behaviour live once.

## Phase 2 — Logic and softlocks (world + client)

### 2.1 Deling City locked after the Tomb (DrMisunderstood) — VERIFIED, story mode
In `story` mode the Galbadia beat requires Key: Deling City, but the train
carries the player into Deling without it and only `areas` mode has the
auto-open story window (`client.py:1031-1035`, window `regions.py:219-228`).
The key was placed at Island Closest to Hell (see 2.2).
Fix: apply the story window in `story` mode too, for every keyed town whose
story beat walks through it (Deling 290–392, Timber forest road 290–315,
Dollet, FH, Esthar). Keys then only matter for out-of-story visits, which is
what the option text promises.

### 2.2 Islands Closest to Heaven/Hell in Disc-1 logic (DrMisunderstood) — VERIFIED
The Ragnarok Flight hub is reachable from the start with only the Ragnarok
item when `vehicle_unlocks` is on (`__init__.py:270-272`), and all 61 island
draw points sit in it with no level, disc or story gate. Level-100 enemies
one-shot a Disc-1 party; the ship also re-parks on top of the hidden points.
Fix: split the hub. "Ragnarok Flight (early)" keeps continent draw points and
early-entry towns; "Ragnarok Flight (islands)" additionally requires the
Esthar beat (or Sorceress Memorial). Progression may not be placed on the
islands before that beat. Update `docs/design.md` and the option text.

### 2.3 Story-key warps ignore the story (Esthar on Disc 1) — VERIFIED
Every owned key adds a warp with no disc or moment check (`client.py:919-930`;
table `warp.py:28-43`). Esthar's door is vanilla-gated at moment 1750, so the
player lands on an empty map. FH and Centra Ruins entered by Ragnarok on
Disc 1 both softlocked (Mayor's house Disc-2 scene; Centra Ruins escape).
Fix:
- Warps: refuse a destination whose beat start is above the true moment,
  with a client message naming the beat.
- Doors: a small "story-window doors" set (FH, Centra Ruins, Esthar) is
  locked until its beat regardless of `story_keys`, using the same entrance
  patch. This covers `story_keys: off` + early Ragnarok.
- Early Ragnarok spawns Lunatic Pandora with it (3167 is post-space). Research
  whether the LP world-map object can be parked off-map after the rebuild the
  way the vehicle seed is; otherwise document it as a known cosmetic.

### 2.4 Dream 2 forest gated by Key: Galbadia Garden (DrMisunderstood) — VERIFIED
The key locks entry 10 (Timber forest road, `regions.py:251-255`) but "Laguna
Dream 2" sits in the Timber region with no key rule (`locations.py:235`).
Fix: covered by the 2.1 story window (290–315). Also add the key rule to
Dream 2 under `story_keys: story` so logic and doors agree.

### 2.5 Draw-point regions (Gaothaire) — one VERIFIED, two to move conservatively
| Slot | Point | Now | Evidence | Move to |
|---|---|---|---|---|
| 4 | Balamb Garden Cafeteria (Demi) | Balamb Prologue | first used at moment 522 in the save library | Garden Revolt |
| 9 | Dollet Town Square (Silence) | Dollet Exam | never used in 285 saves; player doubts exam access | Timber (Dollet revisit) — verify live |
| 166, 132 | Shenand Hill (Break, Thundara) | Timber | player says plateau needs the flying Garden | Balamb Liberation — verify live |
| 135 | bridge Fire near Timber | skipped as "???" (`locations.py:1165`) | vanilla table says Fire, refills | add as a location |
Erring late only delays a check in logic; erring early can strand a key.
Regenerate the tracker packs after the moves.

### 2.6 Blue Magic rules assume nothing about sources — VERIFIED
"Blue Magic: Electrocute" (Coral Fragment: Creeps in Deling sewers, or Card
Mod of the Creeps card) has region-only rules in Timber (`locations.py:509-531`).
Fix: audit all 15 against realistic sources and move each to the beat where
the item first drops (Electrocute -> Galbadia); Card Mod routes are not logic.

### 2.7 Gil Snatch to 0 gil before Timber (DrMisunderstood) — VERIFIED
Flat 1500 per trap, floor 0 (`items.py:356-362`, `memory.py:955-959`).
DECISION 2026-09-30: no floor — the maintainer wants these goofy interactions;
the 3000 floor shipped in v0.8.0 was reverted right after.
Fix: take min(1500, 30% of gil) and never take the player below 3000 (the
Timber fare). Also fix `docs/design.md:214` (trap_chance default is 10, not 0).

### 2.8 Odin / Gilgamesh (DrMisunderstood) — VERIFIED minor
An early "GF Gilgamesh" stops the client re-giving "GF Odin" for good
(`client.py:1863-1873`). Fix: apply that suppression only after the Seifer
fight moment; document that the two are independent items.

### 2.9 Magical Lamp with Diablos already owned (DrMisunderstood) — UNVERIFIED
Nothing handles this (`docs/verification-plan.md:28` skipped it). Test live:
if the vanilla Lamp refuses to start while the GF bit is set, the client
should clear the Diablos bit while a real Lamp is held and the check is
missing, then restore it. Until then the guide should say `/ff8check`.

## Phase 3 — In-game text

### 3.1 Draw-point spell rename leaks into battle (DrMisunderstood) — VERIFIED
"Meltdown x5" replaced "Cure" in the enemy Draw list. `maintain_in_game_text`
runs only on safe ticks so a field's rename survives into battle
(`client.py:2330-2343`, `:2417-2427`).
Fix: from the per-tick path, `kt.restore(["magic"])` when the module enters
`MOMENT_BATTLE_MODULES`; re-apply on return to the field.

### 3.2 Magazine renames persist after the check (Konzera) — VERIFIED
Magazines are non-intercepting by design (they teach limits), but the kernel
rename is keyed on `missing | checked` (`client.py:2218-2222`), so a real
Weapons Monthly keeps saying "Dragon Fang" forever.
Fix: scope magazine renames to `missing_locations` only; document that the
magazine itself still works.

### 3.3 Ragnarok re-parks after every fight — VERIFIED
`seed_vehicles` re-parks 900 units east on every off-map tick (`client.py:862-873`).
Fix: skip re-parking when a live vehicle record already exists within ~2000
units of the player. Fix the stale "500" in `test_vehicle_window.py:295`.

## Phase 4 — Requested options and docs

### 4.1 Options (Loto, DrMisunderstood)
- `ap_multiplier` (1–4x): client adds extra AP to each GF at the results
  module, or patch the AP calc; needs a short research task.
- `enemy_level`: cap or fixed enemy level written to the enemy slots at
  battle start (One Shot already touches `0x1927D88`); most useful with
  junction locks on.
- `triple_triad_rules`: option to clear Random (and optionally set Open) in
  every region's rule byte at connect; client already reads the bytes
  (`client.py:241`), needs the write path.
- Split `triple_triad_checks` into base wins/cards and a separate
  `triple_triad_rule_checks` for rule abolition and region-win counts; drop
  or rename the "100 wins in Balamb Garden" tier so it does not duplicate
  the 100-wins check.

### 4.2 Player guide
- New section "How each check triggers": limits fire on learn not use
  (AmphaRaven confirmed); Enemy Scanned; First Draw; GF ability checks fire
  on learn even when locked; magazines keep their vanilla function under a
  new name; Lamp; Odin and Gilgamesh independent; character junctions can
  be in the starting inventory.
- Document `/ff8` as the unlock-state command (guide currently calls it
  connection status only).
- Stat Ladders: say explicitly they are the game's own lifetime counters,
  not Steam achievements (AmphaRaven skipped them for that reason).
- Traps: say plainly that Gil Snatch can leave you short for the train.

## Live verification list (needs the game)
1. Steps counter: quick sanity read only (tiers already settled from the save library).
2. Dollet Town Square Silence during the exam; Shenand Hill on foot on Disc 1.
3. POST_BATTLE / module during a Triple Triad game.
4. Magical Lamp use with GF Diablos owned.
5. Lunatic Pandora object after an early Ragnarok rebuild.
6. First Draw bit after an AP magic grant (confirms 1.4 before/after fix).

## Suggested order
0.7.1 release -> 1.1, 1.2 (save/seed safety) -> 1.4, 1.5, 1.3 -> 2.1, 2.3, 2.2
(softlocks) -> 2.5, 2.6, 2.7, 3.x -> 4.2 docs -> 0.8.0 release -> 4.1 options.

## Draft Discord replies
- To AmphaRaven: "The 3167 value is ours: the early-Ragnarok feature briefly
  fakes the story counter during battles and a crash path could leave it in
  place. Fix and an automatic save repair are going into the next release;
  sorry for the Hyne detour."
- To DrMisunderstood: "Thanks, this is the most useful log I've had. The
  Deling lockout, Esthar warp, FH/Centra softlocks and islands-in-logic are
  all real and on the list; the Steps/First-Draw/'Battle won' oddities are
  client bugs too. Workaround for the Lamp with Diablos owned: `/ff8check
  Magical Lamp: Diablos`. `/ff8` prints your current unlock state."
- To Loto: "AP multiplier, an enemy-level cap and a Random-rule switch are
  all on the roadmap after the softlock fixes."
