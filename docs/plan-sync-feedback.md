# Sync feedback plan (2026-09-11)

Source: Hdot's Discord report from a two-player sync on the edea goal
(2026-09-10) and Hukos's follow-up on how locked down FF8 is under the hood.
Decisions taken in the discussion that this plan implements:

- Progression is all soft gating today. Story Keys (`plan-story-keys.md`)
  becomes the headline feature, extended with boss keys and an early-entry
  payoff.
- Warp items are not kept as a separate pool once the Ragnarok is an item.
  The warp mechanism survives inside the key items ("Key: Dollet" opens the
  entrance and lets you `/ff8warp dollet`).
- Maelstrom is integrated, not rebuilt. Compatibility matrix first, spoiler
  import second, nothing of ours reimplements its shuffles.
- Early entry means check access, never story sequence breaks. Town fields
  branch on the story moment and faking the moment is proven unsafe
  (`ff8-garden-mobility` notes, `plan-sphere-gating.md`). An early Deling City
  is a place to collect draw points, cards and pickups, not to fight Edea
  before Timber. Maelstrom's own Free Roam mode has sat at "10% complete" on
  the same wall for years; we do not attempt it.

Workstreams, in build order. A and B are hours each and ship first as a
patch release; C and D are the next minor; E follows once C is live.

Status (2026-09-11, released as v0.5.0):

- A DeathLink: BUILT, 7 unit tests (`ff8/test/test_deathlink.py`), guide
  updated. Not live-tested; the self-test's fake battles still pass through
  the receive path (they never look like the won phase).
- B Warp cleanup: BUILT (pool filtered by `beat_chain()`, option and guide
  text), 2 generation tests.
- D1 CORRECTED: beat-end checks already existed in core (`("story", n)`
  triggers). Only Fisherman's Horizon (750) and Lunar Base (3150) had none;
  both added (ids 115/116, 582 locations all-on, tracker pack regenerated).
- D2 Sync preset: BUILT with a 10-seed sweep. It needed the ability, junction
  and character locks OFF: Disc 1 has 57 on-path locations against 97 lock
  items. Final shape: 70 locations, 20 own progression items, sphere 1 = 49
  (`tight` gates give 20/50, no better ladder exists on six beats).
- D3 guide notes: BUILT (booster, length, story order, Sync).
- C0, E1: need live sessions. F: draft in `docs/release/`.

---

## A. DeathLink hardening (half a day)

Hdot dodged received deaths two ways: killing the last enemy before the
wipe registered (party leaves battle at 0 HP), then reviving on the field
with Phoenix Downs.

Cause, `ff8/client.py` `handle_deathlink`: the received death is armed on
the first battle tick and retired when the battle ends, whether or not a
wipe was ever observed. `in_battle()` also spans the results phase, so a
death arriving during results is "delivered" into a battle that is already
won.

Changes:

1. A received death is retired only when `battle_wiped` was observed while
   it was armed. A battle that ends any other way leaves it pending and it
   re-arms in the next battle. Log "DeathLink: battle ended without a wipe,
   re-applying next battle".
2. Never arm during the results phase (`battle_results()` true, or module
   100/4). Wait for the next real combat.
3. Track the wipe from our own kill: `kill_party()` every tick already, but
   also require `party_alive_seen` before arming so the intro-struct problem
   noted on 2026-08-28 stays covered.
4. Field revives: nothing to enforce out of battle (FF8 has no game over
   outside combat). With 1 and 2 the revive buys one field walk and the
   next battle finishes the job, which is the accepted behaviour for
   games that cannot die on the field.
5. Guide section 9: state the rule ("a received death ends your next
   battle; you cannot outrun it by winning or reviving").

Tests: extend `tools/deathlink_probe.py` scenarios and add a unit test that
drives `handle_deathlink` with a fake context through (a) death received
mid-battle then win, (b) death received during results, (c) death received
then escape, asserting pending survives (a) to (c) and clears only after a
wiped battle.

## B. Warp pool cleanup (half a day, retired by C)

1. `create_items`: only add `WARP_TABLE` entries whose `region` is in the
   truncated chain, the way hubs are filtered on the edea goal. Today an
   edea seed carries Edea's House and Esthar warps that lead nowhere.
2. Option text for `fast_travel` and the guide: warps move you on the world
   map only, they never skip story, and towns stay locked until the story
   opens them (until C lands).
3. Test: edea generation asserts no warp item names a post-Galbadia region.

Once C ships, `fast_travel` becomes a deprecated alias that maps to
`story_keys` (one release with a generation warning, then removed).

## C. Story Keys, boss keys, early entry (the main project)

Base plan: `plan-story-keys.md`, Phases 0 to 3 unchanged unless amended
here. Amendments:

### C0. Phase 0 also tests the unlock direction

Hukos's observation is the same lever the plan targets: the world map
decides per location, from the object placement script and a moment
threshold, whether an entrance exists. Phase 0 step 3 gains a fourth case:

- On a Disc 1 world-map save with the Ragnarok item (the early-boarding
  path), lower a Disc 2 town's threshold (Deling City, then Winhill),
  trigger a battle, fly there, walk in. Record whether the field loads,
  what state it shows, whether the exit returns to the world map, and
  which of the area's checks fire (draw points, pickups, shop, TT players).
  Then leave, restore the record, battle, confirm the entrance is gone.

Decision rule stays "A if it works for all three test entrances". If only
locking works (unlock loads a broken field), early entry is dropped and C3
below is skipped; keys still ship.

### C1. Keys carry the warp

- `KEY_TABLE` entries map to a `WarpDest` where one exists (`ff8/warp.py`
  landmarks; Phase 0 adds the missing ones from the area table).
- `/ff8warp <area>` requires the area's key instead of a warp item.
  `received_warp_keys` reads keys.
- Logic: nothing routes through the warp itself (as today). Reachability
  of an area is key plus either its beat (vanilla travel) or the Ragnarok
  under `vehicle_unlocks` (see C3).

### C2. Boss keys

A key for the field that holds each story boss, so a rushed story still
needs items other players hold. Same mechanism where the boss sits behind a
world-map entrance (Fire Cavern, Missile Base, Lunar Gate, Tears' Point);
elsewhere the boss key is the area key (Dollet for the exam, Galbadia
Garden, Edea's House). Bosses reached only by scripted travel (the train
arc to Timber, the parade) are not gated; the beat's own ladder covers them.

Under `story_keys: story` the beat entry rule requires the boss key. No
new items beyond the area keys; this is the table deciding which keys are
story-required. Sphere report target: every beat past Dollet needs at least
one key held by fill, none of them placeable in the beat they gate.

### C3. Early entry (only if C0 unlock passes)

New sub-region entrance: area reachable from the Menu with its key and the
Ragnarok item when `vehicle_unlocks` is on. Retagged area checks (draw
points, pickups, cards, shops, magazines) become reachable early; story
locations stay on the beat. This is what gives an early Ragnarok and the
keys their payoff and is the strongest lever on the partner-BK problem
(more of the 580 checks open in the first hour).

Client rule: early-entry areas are only unlocked while the true moment is
below the area's story window; inside the window the story pass applies;
above it vanilla behaviour. The record write happens on world-map load,
never in a field or menu.

Not gated and not unlockable: Balamb Garden, Ultimecia's Castle, Lunatic
Pandora (the same list as the base plan).

### C4. Live tests added to Phase 2

8. Early entry into Deling City on a Disc 1 save: field loads, shop and
   draw points check, exit works, save and reload inside the town works.
9. Enter early, then progress the story to the vanilla arrival: the
   scripted arrival still plays and the moment advances (no double state).
10. Key received while standing inside the area: no effect until the next
    world-map load.

Release: v0.6.0, `story_keys` off by default, same stability note as
v0.4.0.

## D. Sync pacing (one to two days, ships with C)

### D1. Story beat checks

Core already has a story-moment check at the end of nearly every beat
("Fire Cavern Cleared" ... "Ultimecia's Castle Entered", plus the Laguna
dreams), so the on-path pacing this was meant to add mostly exists. The
gaps were Fisherman's Horizon (no check at 750, Garden repaired) and Lunar
Base (none at 3150, the Ragnarok lands); both are now core checks. No new
group, no client work: the existing `story` trigger handles them.

### D2. "Sync" preset

edea goal, `story_gates: normal`, `story_keys: story`, check groups on
only for on-path content (core, story, draw points, bosses, magazines),
world draw points off, stat ladders off, TT off, trap chance 0. Purpose
text: "for public syncs where the other players should not wait on you".
Sphere report target: no sphere with fewer than 8 checks.

### D3. Guide

- Requirements or section 5: recommend the Steam speed booster for syncs
  and say the client does not care about it.
- Section 6: FF8 is a 30 to 40 hour game; on the edea goal about 8; pick
  the Sync preset for public games.
- Section 9: DeathLink rule from A.
- Known limitations: story order cannot be changed, early entry is for
  checks only.

## E. Maelstrom (after C is live)

Maelstrom (github.com/sleepeybunney/maelstrom, MIT, C#) patches files once
and does not run during play, so it can sit under our memory-hook client.
It patches the same data we read, which is the whole risk.

### E1. Compatibility matrix (one live day)

For each Maelstrom feature, run a short AP seed with it on and record what
breaks. Expected before testing:

| Maelstrom feature | Our subsystem at risk | Expected |
|---|---|---|
| Boss shuffle | boss checks and win credit by encounter id, GF-from-boss revokes | breaks |
| Draw point shuffle | per-point spell renames, draw-point checks | breaks names, checks may still fire |
| GF ability shuffle | ability locks, ability checks, kernel renames | breaks |
| Shop shuffle | none we read | safe |
| Loot (steal/drop) shuffle | none we read | safe |
| Weapon shuffle | none we read | probably safe |
| Card shuffle | rare-card checks (which NPC holds which card) | breaks |
| Music shuffle | none | safe |
| Names presets | party names in DeathLink text only | safe |
| Free Roam | everything | never supported |

Also confirm it coexists with the Junction VIII and FFNx install (its README
says untested) or document that AP-plus-Maelstrom needs a clean install.

### E2. Documented safe subset (half a day)

Guide section "Playing with Maelstrom": the features the matrix marked safe,
the order (Maelstrom first, then start the AP client), and that the AP
selftest must pass afterwards. No code.

### E3. Spoiler import (medium project, only on demand)

New generation input `maelstrom_spoiler: <path>`; the apworld parses boss
placements and card holders and remaps the affected locations (boss check
names keep their vanilla names, the encounter id behind each is swapped,
rare-card holders retagged). Draw point and ability shuffles stay
unsupported unless someone asks. Requires the Maelstrom seed to be fixed
before AP generation, which the guide explains.

## F. Discord reply (after A and B ship)

Reply to Hdot and Hukos with: the DeathLink fix, the warp cleanup, that
Story Keys is the next feature with the before-and-after sphere report,
that early entry for checks is being tested and story order will stay fixed
for the reasons Hukos gave, and that Maelstrom compatibility is on the list
with a request for anyone already running both to report what they see.

---

## Order and estimates

| Step | Effort | Depends on | Release |
|---|---|---|---|
| A DeathLink | 0.5 day | none | v0.5.0 (shipped) |
| B Warp cleanup | 0.5 day | none | v0.5.0 (shipped) |
| D3 guide notes (booster, length) | 0.5 day | none | v0.5.0 (shipped) |
| F Discord reply | 0.5 hour | A, B | with v0.5.0 |
| C0 Phase 0 research | 1 to 2 days live | none | |
| C1 to C4 keys, boss keys, early entry | 5 to 7 days plus two live sessions | C0 | v0.6.0 |
| D1 beat checks, D2 preset | 1 to 2 days | C for the preset | v0.5.0 (shipped) |
| E1 matrix | 1 live day | C live (keys change what "breaks" means) | |
| E2 safe subset doc | 0.5 day | E1 | v0.5.1 |
| E3 spoiler import | 3 to 5 days | E1, demand | v0.7.0 |

A, B, D3 and C0 can run in parallel. D1 is mechanism-independent and can
start any time.

## Risks

- C0 unlock direction fails: keys still ship, early entry is dropped, the
  Ragnarok stays a travel item and the pacing gain comes from D alone.
- wmset re-read on every world-map load with a slow client tick: a player
  could slip into a gated town between load and re-apply. Mitigation is the
  backstop log in the base plan plus applying on the first tick after
  `MODULE_WORLDMAP` is seen, before any position writes.
- Beat checks on the edea goal fire on moment thresholds the parade fight
  also crosses; the last beat check and the goal must not race (send the
  check first, then the goal, in the same tick).
- Maelstrom plus the modded install: if E1 shows it needs a clean install,
  E2 says so and E3 is deprioritised.
