# Story Keys plan (2026-09-10)

Goal: real key items for towns and areas. Today every gate except
`vehicle_gates` is a logic gate (the game never physically stops you; Hdot's
Discord feedback, 2026-09-09: "the progression isn't really gated except
that you might be too weak"). Story Keys adds `Key: <area>` items that the
client enforces on the world map: without the key, you cannot walk into the
area. Story-required entrances (Lunar Gate, Tears' Point, ...) turn the
matching story beat into a genuine key gate, the way `vehicle_gates` already
does for the Ragnarok.

Origin of the mechanism: during the Ragnarok tests, faking the story moment
past 750 made the mobile Garden replace the static one and locked the player
out of Balamb Garden (`docs/plan-sphere-gating.md`, live play-test A). The
world map decides per location, from data, whether an entrance exists. That
decision is what a key flips.

Amendments (2026-09-11): `plan-sync-feedback.md` section C extends this
plan with an unlock-direction test in Phase 0, keys that carry the warp
(retiring `fast_travel`), boss keys, and an early-entry sub-region. Read
both before starting Phase 0.

Hard rules carried over from the vehicle work:

- **Never fake the story moment** for this. Continuous faking crashed on a
  long idle; faking inside a field black-screens. Keys work by editing
  location data or the player's position, both proven-safe write classes.
- **World map only.** There is no safe way to eject a player from a field.
  Story-scripted arrivals (the train to Timber, the Garden crash into FH, the
  Ragnarok landing) bypass every world-map entrance and are not gated.
- **A key must be in logic before any beat whose story forces that
  entrance**, exactly like `VEHICLE_BEATS`. Fill then guarantees it.

---

## Phase 0 — find the entrance switch (1 day, research)

Two candidate mechanisms. Phase 0 picks one; everything after is the same.

**A. Edit the entrance data in memory (preferred).** `wmsetus.obj` is
resident at a fixed address (memory notes: section 9 at VA 0x1E9DC3C is the
object placement script, opcode `ff02` = moment >=, `ff13 <obj>` = spawn,
`ff1a`-`ff1d` = touched-object handlers). If a town's entrance is an object
record or an entry in a sibling section (location id -> field id), rewriting
that record makes the door not exist until the key arrives. Restoring the
bytes and passing through one rebuild (any battle or field exit) brings it
back. Nothing about the story moment changes, so none of the faking failures
apply.

Steps:

1. Dump every section of `wmsetus.obj` from `world.fs` (Deling, or the
   pefile-era scratch scripts) and diff the section 9 decode against the
   landmark table in `ff8/warp.py`.
2. On a Disc 1 world-map save, stand outside Dollet, record `FIELD_ID`
   (0x18D2FC0) and a snapshot of the wmset block, walk in, snapshot again.
   The bytes that select the Dollet field are the entrance switch. Repeat
   for Balamb town (a plain town) and Fire Cavern (a dungeon entrance).
3. Poke test: overwrite the located record (threshold to 0xFFFF, or the
   field id to a no-op), trigger a battle, try to enter. Then restore, battle,
   enter. Both directions must work on the same save without a reload.
4. Confirm the record survives a field round trip (the wm reloads wmset on
   every world-map load; the client must re-apply on each load, like the
   vehicle park writes).

**B. Invisible wall (fallback, no research needed).** The client already
writes `WORLD_POS` at 30 Hz in the moment-window loop. Each gated entrance
gets a guard circle; a player inside it without the key is pushed back to
the circle's edge and the client prints "Locked: Key: Dollet". Radius must be
generous (the Ragnarok park nudge of 900 units is the scale) because a
running player crosses an entry tile between two ticks. Never while
`avatar_riding()` (vehicles cannot enter locations anyway, and a wall under a
landing ship is undefined).

Decision rule: A if step 3 works for all three test entrances; otherwise B.
Either way, Phase 0 also produces the table below with real coordinates and
field ids for every area.

**Status 2026-09-11 (static RE + first live session), full write-up in
`docs/research/world-map-entrances.md`:** mechanism A, and simpler than
planned. Entrances are not objects. A town is (a) its footprint of walkmesh
triangles flagged 0x800 in `wmx.obj` and (b) one entry in the resident
*entrance script* (`wmsetus.obj` section 8, VA 0x1E9E7AC, 38 entries),
evaluated every world-map tick: `segment == n` [and `moment >= m`] then
`enter wm field k`, where wm fields 0..71 map through a 72-entry table to
the real town field. Lock = the entry's segment argument -> 0xFFFF; unlock
(early entry) = its moment argument -> 0; restore = pristine bytes from
`world.fs`. No rebuild step: the script is data read live, so a key
arriving while the player stands outside opens the door at once. Live so
far: resident bytes == archive; warping onto Balamb's door tile entered
`bcgate_1` immediately (trigger is level-sensitive). `tools/poc_story_keys.py`
carries the decoder, lock/unlock/restore/warp/poke commands, the per-segment
door coordinates and the wm-field labels. Step 3 lock direction: PASSED
(Balamb locked, four seconds on its door tile, no entry; restore reopens).
Step 4: the buffer is RE-READ from disk on every world-map load, so the
client re-applies gates on each `MODULE_WORLDMAP` entry (same pattern as
the vehicle park writes; the "win a battle to open the door" note is moot,
a key opens the door on the next tick). The C0 unlock direction test
(Deling City on a moment-205 save) was inconclusive by teleport alone (the
tile pointer goes stale after long warps) and is queued with a player step.
East Academy station: not a world-map location (the Deling train leaves
from Galbadia Garden's field).

## Phase 1 — key table and logic (1 to 2 days, generation)

**Status 2026-09-11: BUILT (uncommitted), 428 tests green.** Shape as built,
where it differs from the plan below:

- No sub-regions. Keyed checks stay in their story beat and get an extra
  `has(Key: <area>)` rule (`regions.AREA_LOCATIONS`, name prefixes); under
  `story` the beat entry rule also requires `STORY_KEY_BEATS[beat]`. Early
  entry (C3) would be the sub-region layer on top; deferred, see C0 notes.
- 20 keys (`regions.STORY_KEY_AREAS`): Balamb, Fire Cavern, Dollet, Timber,
  Galbadia Garden (+ the Timber forest road), Tomb of the Unknown King,
  Deling City, Missile Base, Winhill, Shumi Village, Centra Ruins, Chocobo
  Forests (7 forests + the sanctuary, one key), Trabia Garden, Edea's House,
  Great Salt Lake (+ the Esthar-side station), Esthar City (4 entries),
  Lunatic Pandora Laboratory, Lunar Gate, Sorceress Memorial, Tears' Point.
  Not keyed: Balamb Garden, FH (vehicle-only entries), D-District Prison
  (no revisit content), Deep Sea Research Center (Ragnarok hub), Ultimecia's
  Castle, Lunatic Pandora.
- Each key carries its lock/unlock byte patches (offset into the resident
  entrance script, vanilla value, new value) and its warp destination;
  slot data `story_key_areas` ships the table, so the client never
  hard-codes offsets and refuses to patch a script that does not match.
- `story` precollects Key: Balamb and Key: Fire Cavern
  (`STORY_KEY_PRECOLLECTED`): with them in the pool sphere 1 was Balamb
  Prologue's 10 checks. Measured (`tools/sphere_report.py`, 3 seeds):
  default 59 checks in sphere 1 / depth 10-17; `story` 46 / 13-16.
- `fast_travel` adds nothing while `story_keys` is on (keys carry warps).
- Preset "Story Keys" = Staircase + `story_keys: story`.

New option:

```
story_keys: off | areas | story   (default: off until live-verified)
```

- `off`: no key items, today's behaviour.
- `areas`: every area below has a key. Area content (draw points, shops,
  TT players, magazines, sidequests) needs the key in logic. **The story
  path never needs a key**: when the true moment is inside the window where
  the story requires that entrance, the client lifts the gate (a "story
  pass"). Nobody is ever BK'd on the main line by this mode.
- `story`: `areas` plus the story-required entrances are hard gates: the
  beat entry rule requires the key, and the client never grants a story
  pass. This is Hdot's request.

Areas, first pass (Phase 0 fills in the coordinates and field ids):

| Key | Story-required for beat | Notes |
|---|---|---|
| Fire Cavern | Fire Cavern | second beat; `story` mode places it in Balamb Prologue |
| Balamb (town) | Timber (train), Balamb Liberation | Disc 1 hub; precollected unless `story` |
| Dollet | none (exam arrives by boat) | revisit content only |
| Timber | none (train) | revisit content only |
| Galbadia Garden | Galbadia | walk in from the Timber forest |
| East Academy Station | Galbadia (Deling by train) | verify in Phase 0 whether the station is a world-map location |
| Deling City | none (train) | revisit content only |
| Missile Base | Missile Base | Selphie's team drives in from the world map |
| Winhill | none (Laguna dream) | revisit content only |
| Shumi Village | none | optional area |
| Trabia Garden | Garden War | Garden lands, walk in |
| Edea's House | Garden War | walk in from Centra |
| Centra Ruins | none | Odin, Tonberry King |
| White SeeD Ship | Esthar | approached by Garden |
| Great Salt Lake | Esthar | on foot after Edea's House |
| Esthar City | Esthar (+ Sorceress Memorial revisit) | one key for the city entrances |
| Lunar Gate | Lunar Base | the cleanest hard gate in the game |
| Sorceress Memorial | Sorceress Memorial | |
| Tears' Point | Lunatic Pandora | |
| Deep Sea Research Center | none | optional; Ragnarok hub |
| Chocobo Forests (7) | none | one key each, or one "Chocobo Forests" key (decide by pool size) |

Not gated: Balamb Garden (home base; the static object is the mobile-Garden
swap that caused the original lock-out, and gating it strands the shop and
the SeeD checks), Ultimecia's Castle (the goal), Lunatic Pandora itself (the
Ragnarok ram is scripted).

Work items:

- `ff8/regions.py`: `AREAS: dict[key, AreaData(name, beat_first_available,
  story_beats: list[str], entrance: (x, y, radius) | record id, fields:
  list[int])]`. Add `STORY_KEY_BEATS` in the shape of `VEHICLE_BEATS` (beat
  -> keys), derived from the table.
- Each area becomes a sub-region hanging off its first-available beat, entry
  rule `state.has(key)`. Retag area-bound locations (every draw point, shop,
  TT player, magazine, sidequest whose `region` is a beat but whose field is
  inside an area) to the area region. Story-critical locations (bosses,
  story flags, GF draws that the story forces) stay in the beat.
- Under `story`, `_beat_rule` also requires `STORY_KEY_BEATS[nxt]`.
- `ff8/items.py`: `KEY_TABLE` (ids in a fresh window), progression under
  `story`, progression under `areas` too (area content can hold other
  worlds' items). Item group "Story Keys". Chocobo-forest keys are useful
  class if they only gate the forest checks and nothing else.
- `create_items`: pool grows by the key count (about 20 to 27). The edea
  goal truncates keys whose first-available beat is gone, like hubs.
- Slot data: `story_keys` plus the area table (entrance coords, radius,
  field ids) so the client and Universal Tracker never hard-code them.
- `tools/sphere_report.py`: keys appear as unlock items per sphere. Target
  on `story` + `normal` gates: sphere 1 unchanged (59), item-gated spheres
  up by 3 to 5.

Tests: generation sweep per mode (20 seeds), key-before-beat assertion for
every `STORY_KEY_BEATS` entry, edea truncation, a `test_spheres.py` row for
`story`, and a table assertion that every area's fields are disjoint and its
beat exists.

## Phase 2 — client enforcement (1 to 2 days plus live testing)

**Status 2026-09-11: BUILT + LIVE-VERIFIED (uncommitted), 439 tests green.**
`client.enforce_story_keys` runs every tick: on the world map it writes every
missing key's lock words (`slot_data["story_key_areas"]`) into the resident
entrance script and reopens a door the tick its key arrives or a story pass
begins (`areas` mode, `regions.story_pass_windows`); off the map it forgets
the applied set (the game re-reads the script from disk on every world-map
load) and, on a field entered through a shut door, logs a bug-report
warning from the wm exit request (`memory.WM_EXIT_REQUEST`). Words that hold
neither the vanilla nor the locked value (another game version/language)
leave that door alone, log-once. "Locked: Key: X" is logged when the avatar
stands on a shut door's tiles (`memory.WM_CUR_TRIANGLE_PTR` flag, 10 s rate
limit). Keys unlock `/ff8warp` destinations; the Potion warp crystal stays a
`fast_travel` feature. Unlock (early-entry) patches are shipped in slot data
but never applied (C0: interior soft-locks). Live, real client + MultiServer
on a moment-205 save: all 16 missing doors shut on connect, the precollected
and already-checked keys' doors open; warping onto Timber's door logged
"Locked: Key: Timber" with no entry; `!getitem Key: Timber` logged "Timber is
open" and the game entered tigate1 at once. Unit coverage:
`ff8/test/test_story_doors.py` (fake process).

Common to A and B:

- `received_key_areas(ctx)` from `items_received`, same shape as
  `received_vehicle_keys`.
- `story_pass_active(ctx, area)`: true when `story_keys == "areas"` and the
  true moment lies in one of the area's `story_beats` windows (moment
  thresholds from `BEATS`). The gate is skipped for that area.
- Enforcement runs only when `MODULE_DISPATCH == MODULE_WORLDMAP`,
  `is_safe()`, and not `avatar_riding()`.
- Message on block (once per approach, rate-limited): `Locked: Key: Dollet`.
- Key receipt while gated: A restores the record and the next rebuild opens
  the door (tell the player: "win a battle or leave a town"); B lifts the
  wall immediately.
- Backstop: if the client sees a gated area's `FIELD_ID` without its key and
  without a story pass, it logs a warning with moment and position. This is
  a bug report, never an action.

Mechanism A: `apply_entrance_gates(ctx)` writes the gated records on every
world-map load (the same place the vehicle park is re-asserted) and restores
originals for owned keys. Keep a copy of the pristine bytes read on first
attach; never write while `IN_MENU` (a world-map save must not capture an
edited record; verify in Phase 0 whether wmset is even in the savemap, it
should not be).

Mechanism B: extend the 30 Hz loop (`MOMENT_WINDOW_HZ`) with the wall check;
it only runs while any gated area is within 2x its radius, so the idle world
map costs nothing extra.

Live tests (in order, on the existing Disc 1 and Disc 3 library saves):

1. Dollet gated, walk in: blocked, message shown. `!getitem Key: Dollet`,
   battle (A) or nothing (B), walk in: enters.
2. Story pass: `areas` mode, Fire Cavern gated, moment in the Fire Cavern
   beat window: enters without the key.
3. `story` mode, Lunar Gate gated on a Disc 3 save before the launch: blocked.
   Key arrives, enters, launch plays normally.
4. Save on the world map next to a gated entrance, reload: still gated
   (A: record re-applied on load).
5. Balamb Liberation: Garden lands, disembark, Balamb town gated in `story`
   mode without the key: blocked; with the key: the liberation sequence starts.
6. Missile Base drive-in (the only car entrance): gated and ungated.
7. Long idle on the world map inside a guard circle (B only): no crash, no
   drift.

## Phase 3 — trackers, docs, release (1 day)

- `tools/gen_tracker_pack.py`: key items in the items grid ("Story Keys"
  tab or a row on the Vehicles tab), area sub-regions on the region boards,
  `LOGIC_LUA` mirrors the sub-region rule and `STORY_KEY_BEATS`.
- Universal Tracker: nothing to do beyond slot data, as with v0.4.0.
- `docs/player-guide.md`: option text, the `areas` versus `story` difference,
  the "win a battle to open the door" note for A.
- `docs/design.md`: mechanism, addresses, the story-pass rule.
- Preset: "Story Keys" = Staircase + `story_keys: story`.
- Release as v0.6.0 with `story_keys` off by default and the same stability
  note as v0.4.0; Discord reply to Hdot with the before/after sphere report.

## Order and dependencies

0 gates everything (it decides A or B and produces the area table). 1 and
the common half of 2 can start on the fallback assumption (B) while 0 runs,
since the option, items, regions, and tests are mechanism-agnostic. 3 closes.
Roughly five to seven working days plus two live sessions.

## Open questions for Phase 0

- Are town entrances objects in section 9, or terrain triangles with a
  location code resolved elsewhere? (Decides A versus B.)
- Does East Academy Station exist as a world-map location on the Disc 1
  route, or does Galbadia Garden's own station handle the Deling train?
- Is wmset re-read from disk on every world-map load, or kept resident? (Sets
  how often A must re-apply.)
- Does a chocobo entering a forest count as `avatar_riding()`? (Sets the
  chocobo-forest gate rule.)
