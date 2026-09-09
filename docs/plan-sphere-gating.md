# Sphere gating plan (2026-09-09)

Goal: turn the seed from two plateaus (about 220 checks open at start, about
190 more once six GFs arrive) into a staircase of roughly 8 to 12 item-gated
steps, with the zero-item sphere confined to Disc 1 story beats. Origin:
SeraphIV's Discord feedback (sphere 1 "almost 200 checks") and the follow-up
analysis in `tools/sphere_report.py` (Phase 0).

Measured today, default options, seed 1:

| Measure | Value |
|---|---|
| Spheres as AP counts them | 12 (six are free story events) |
| Item-gated spheres after collapsing free events | 5 |
| Checks in item-sphere 1 | 220 of 455 (130 in the flat "Disc 2" region) |
| Checks in item-sphere 2 | 190 (Disc 3 + 4, once six GFs arrive) |

Design rule carried over from `gfs_required_for_disc3`: gates are logic
gates. The game never physically blocks the player unless Phase 4 is on.
This is exactly the "open world plus logic gates" feel SeraphIV asked for.

---

## Phase 0 — measurement tool (half a day)

`tools/sphere_report.py`: generates N solo seeds for a given option profile
and prints item-gated spheres (free story events collapsed), per-sphere region
and group composition, and which progression items unlock each step. This is
the acceptance test for every later phase and becomes a unit test in Phase 2.

Already prototyped in the scratchpad during the analysis; move it into
`tools/` and add a `--profile` switch for the option presets.

## Phase 1 — split the flat regions into story beats (1 day, data only)

`REGION_CHAIN` grows from 9 regions to about 17. Disc 1 keeps its six beats.
Story moments come from the existing `("story", N)` triggers in
`ff8/locations.py` and the vehicle spawn thresholds in `client.py`.

| New region | Enters at (moment) | Replaces |
|---|---|---|
| D-District Prison | 392 (parade won) | Disc 2 |
| Missile Base | 450 (prison escape) | Disc 2 |
| Garden Revolt | 482 (missile base done) | Disc 2 |
| Fisherman's Horizon | 612 (NORG) | Disc 2 |
| Balamb Liberation | 750 (Garden mobile) | Disc 2 |
| Garden War | 760 (Fujin/Raijin) | Disc 2 |
| Edea's House | 901 (Battle of the Gardens) | Disc 3 |
| Esthar | 1310 (Trabia Canyon dream; White SeeD ship, salt lake, city) | Disc 3 |
| Lunar Base | 2502 (Lunar Base launch) | Disc 3 |
| Sorceress Memorial | 3150 (ship in hand) | Disc 3 |
| Lunatic Pandora | 3790 (the attack) | Disc 3 |
| Ultimecia's Castle | 3860 (Adel) | Disc 4 |

Work items:

- Retag every "Disc 2", "Disc 3", "Disc 4" location (141 + 241 + 34) to its
  beat. Draw points, magazines, rare cards, and sidequests each have an
  obvious first-available beat. Grind ladders (steps, kills, TT wins) go in
  the beat where a normal run reaches the number.
- Add `Cleared: <beat>` events for each new beat. Events need no triggers; the
  client never sees them.
- Mirror the chain in `tools/gen_tracker_pack.py` (`REGION_CHAIN`,
  `STORY_PROGRESS_BUMPS`, region board columns) and regenerate the PopTracker
  and Universal Tracker packs. The Lua `progress` counter simply gets a larger
  range.
- Update the three tests that name the old regions
  (`test_generation.py:59`, `test_pool.py:620`, `test_universal_tracker.py:82`)
  and the edea goal truncation (chain up to Galbadia is unchanged).
- Sphere report after this phase must show the same 220 checks in sphere 1.
  This phase changes nothing about logic; it only creates the seams.

## Phase 2 — the gate ladder (1 to 2 days, generation side)

One new option instead of a dozen thresholds:

```
story_gates: off | normal | tight   (default: normal)
```

`off` reproduces today's behaviour. `normal` and `tight` select a ladder
table: for each beat, a minimum count of GFs, character unlocks, and junction
rights. Counts interpolate from `starting_gfs` up to `gfs_required_for_disc3`
at the Trabia beat and on to 10 or 12 at the castle, so the existing option
keeps its meaning. Character and junction thresholds are skipped when their
lock option is off, so the ladder degrades to GF-only gracefully.

Sketch of `normal` (counts are cumulative, subject to tuning by the report):

| Beat | GFs | Characters | Junction rights |
|---|---|---|---|
| Timber | 1 | 1 | 1 |
| Galbadia | 2 | 1 | 2 |
| D-District Prison | 2 | 2 | 3 |
| Garden Revolt | 3 | 2 | 4 |
| Fisherman's Horizon | 4 | 3 | 5 |
| Balamb Liberation | 4 | 3 | 6 + Garden item |
| Trabia and Orphanage | `gfs_required_for_disc3` | 4 | 7 |
| Esthar | +1 | 4 | 8 |
| Lunar Base | +2 | 4 | 9 |
| Lunatic Pandora | +3 | 4 | 10 + Ragnarok item |
| Ultimecia's Castle | +4 | 4 | 11 |

Travel tags: add `travel: str | None` to `LocationData` with values
`garden`, `ragnarok`, `chocobo`. World draw points, Trabia, Centra, Shumi,
Winhill revisits, Obel Lake, chocobo forests, Odin, Tonberry King, Cactuar
Island, Deep Sea Research Center, and the UFO sightings get tagged. A tagged
check is reachable when the player holds the vehicle item **or** has reached
the beat where vanilla grants that vehicle. With `vehicle_unlocks` on, the
two vehicle items become progression (classification override in
`create_item`), so an early Ragnarok pulls Disc 3 islands into an early
sphere. That is the "open world" half of the puzzle.

Tests: `test_spheres.py` sweeps 10 seeds per profile and asserts item-sphere
1 stays under 70 checks on `normal`, under 40 on `tight`, and that at least 8
item-gated spheres exist. Existing fill sweeps stay green.

Fill safety: the progression supply is 15 GFs, 4 characters, 11 junction
rights, 3 commands, 2 vehicles, Lamp, Ring. The ladder never asks for more
than the pool holds under any option combination; a test asserts this per
profile. Progression balancing in a large multiworld will flatten the ladder
somewhat, which is expected.

## Phase 3 — keep the Ragnarok (half a day, client)

Requirement from 2026-09-09: get the ship early and keep it, except where the
story scripts it away.

`vehicle_window_target` currently switches off once the true moment passes
the ship's vanilla threshold. Change it to: while the item is owned and the
player is on the world map, if the availability flag is clear or the ship is
not within reach, re-seed it beside the player at any moment value, except
inside an explicit blackout list of moment ranges (the space sequence, the
Lunatic Pandora interior, and any stretch a live test shows scripting the
ship). Reuse the 32-bit off-map seed. Live-verify at the two reclaim points.

## Phase 4 — hard vehicle gates (2 days plus live testing, client)

Optional, separate toggle `vehicle_gates` (off by default until verified).
The client withholds the vanilla Garden and Ragnarok grants by clearing the
availability bit and parking the vehicle off-map until the item arrives.
Scripted auto-pilot segments (the FH crash, the Garden battle) are
moment-driven and keep working. Beats that need free piloting (Balamb
Liberation, Lunatic Pandora) require the item in logic, which fill then
guarantees. Live risks to check: the FH to Balamb hand-off, and a save made
with the vehicle present.

## Phase 5 — ship it (1 day)

Tracker packs regenerated and versioned, `docs/player-guide.md` and
`docs/design.md` updated, a "Staircase" preset added, one live play-test on a
fresh default seed, then a v0.4.0 release and a reply in the Discord thread
with the before and after sphere report.

## Order and dependencies

0 → 1 → 2 is the critical path and delivers the feedback fix. 3 is
independent and can go first. 4 depends on 2 and on live testing time. 5
closes.

## Status (2026-09-09, built, uncommitted)

All five phases are implemented; 338 tests pass. Measured with
`tools/sphere_report.py` on default options (455 checks):

| story_gates | sphere 1 | item-gated spheres |
|---|---|---|
| off (old shape) | 221-223 | 5-7 |
| normal (default) | 59, all Disc 1 | 8-13 |
| tight | 24-25 | 11-15 |
| Staircase preset (tight + vehicles + all checks) | 28-29 | 10-14 |

Design deltas from the plan above: the first Disc 3 beat is "Edea's House"
(Laguna Dream 4 ends there at 1310, before the White SeeD ship, which is in
the Esthar beat); vehicle-only content is modeled as three hub regions rather
than a per-location travel tag; the ladder is a single `story_gates` choice
with the GF column scaled from `gfs_required_for_disc3`; the client keeps an
owned vehicle available for the whole game outside evidence-based story
blackouts (storyId.md moments) and only re-asserts the flag after the
vanilla hand-over, never moving the vehicle then.

## Live play-test (2026-09-09, seeds WilsonKeep / WilsonGate)

Test A (Disc 1, moment 205, Ragnarok in start inventory): early spawn after a
battle ✅; menu open/close with the true moment intact ✅; flight to Island
Closest to Heaven on Disc 1 ✅; a hub check ("Draw Point: Island Closest to
Heaven (Tornado)", fired in memory) sent and its item delivered ✅.
Findings fixed in-session: the ship vanished after every town visit (the
window only faked around battles) → the grace now also opens on every
field→world-map return; the ship parked 500 units from a town-exit tile
pinned the player → nudge raised to 900; a mobile Garden replaces the static
Garden on the world map and locked the player out of Balamb Garden → the
Garden item is dropped, the Ragnarok is the only vehicle item.

Test B (Disc 3, moment 3167, no vehicle in start inventory, vehicle_gates):
the availability bit was found to gate NOTHING past the story hand-over (the
ship spawned and boarded with it clear; clearing it on a save made aboard
dropped Squall into the sea) → withhold rewritten to park the ship far out
at sea while the player is off the map, never touching the bit. Verified:
withheld ship out at sea after a battle ✅; `!getitem Ragnarok` → status
"owned" ✅; next battle brings it back beside the player and it boards ✅.

Still to do by hand: commit, tag v0.4.0, `tracker/versions.json` sha sync
after CI builds the pack zip, and the Discord reply
(docs/release/v0.4.0-announcement.md). Not yet live-tested: the field-exit
grace timing on a slower machine, and a hub draw found by hand (the island
draw points are invisible; the fired-in-memory path is what was verified).
