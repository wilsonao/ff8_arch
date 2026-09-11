# World-map entrances (Story Keys Phase 0 research, 2026-09-11)

How FF8 (Steam 2013, FF8_EN.exe, no ASLR, base 0x400000) decides that
walking on the world map enters a town, from static RE plus one live
session. Addresses are virtual addresses unless marked module-relative
(module-relative = VA - 0x400000, the convention in `ff8/memory.py`).

## Mechanism

Every world-map tick, while the transition flag at 0x2036B70 is clear, the
main loop (0x53FF7B, and the vehicle loop at 0x541279) calls
`sub_545EA0(&wm_field)`:

1. Read the walkmesh triangle under the avatar (`[0x20409FC]`, a pointer to
   a 16-byte `wmx.obj` polygon record). If byte +0xE bit 3 (flag 0x800 of
   the 24-bit field at +0xD..+0xF) is clear: no entrance here, return 0.
   Every town's whole footprint is flagged (Balamb: 259 triangles), so the
   flag means "town ground", not "the door".
2. Run the **entrance script** = `wmsetus.obj` section 8 (0xA5C bytes)
   through the condition evaluator `sub_545F10` / opcode handler
   `sub_546100`. The script is resident in the decompressed copy of
   `wmsetus.obj` at 0x1E9DC3C (module-relative 0x1A9DC3C), section 8 at
   +0xB70. Live bytes matched the archive byte for byte on 2026-09-11.
3. The first entry whose conditions pass yields `ff08 <wm field>`;
   `sub_544630(wm_field)` posts `{1, avatar_type, wm_field, 0xFF}` at
   0x2036B4C (module-relative 0x1C36B4C) and fades out.
4. The field module (0x4708AC) indexes a runtime table
   (`[0xB6D068] - 0x6C0`, 72 entries x 24 bytes: `i16 x, y, z; u16 field_id;
   u8 direction; ...`) by the wm field number and writes the real field id
   into FIELD_ID (0x1CD2FC0), module dispatch = 1.

The story moment is only ever read through the script's `ff02`/`ff03`
conditions (cached u16 at 0x2036BDE). Nothing else gates a town.

### Script format (u16 opcode, u16 arg)

| opcode | meaning | handler |
|---|---|---|
| ff01 | begin entry | evaluator |
| ff02 n | moment >= n | 0x546136 |
| ff03 n | moment < n | 0x546164 |
| ff04 | then (conditions end, branches begin) | evaluator |
| ff05 | end branch | evaluator |
| ff06 n | player's segment == n | 0x546192 (`sub_553910(x, y)`) |
| ff07 n | player's 2048-unit cell == n | 0x5461FA |
| ff08 n | as a condition: avatar may enter wm field n; as the action: enter wm field n | 0x546254 |
| ff09 t | avatar type == t (0x80 foot, 0x84 chocobo, 0x30 Garden, 0x31 Ragnarok, 0x32 car) | 0x546254 |
| ff0a / ff0b / ff0c / ff0d / ff0e | if / do / else / elif / jump (branch structure) | evaluator |
| ff0f n, ff11 n | segment-local x <= n, x >= n (0..0x1FFF) | 0x5463A7, 0x546461 |
| ff10 n, ff12 n | segment-local y <= n, y >= n | 0x546406, 0x5464C0 |
| ff20 n | triangle index within the block == n | 0x546A44 |
| ff21 | unknown flag (Garden docking at FH, Edea's House) | 0x546A71 |
| ff16 | end of entry | evaluator |

Segment index from WORLD_POS (0x203EE80, i32 x, y, z): `col = ((x +
0x60000) mod 0x40000) >> 13`, `row = ((y + 0x48000) mod 0x30000) >> 13`,
`segment = row * 32 + col` (32 x 24 grid, 8192 units per segment). This
matches the `ff8/warp.py` landmark table exactly.

### Entries (38, decoded by `tools/poc_story_keys.py entries file`)

| # | segment | moment | avatar | wm field -> real field |
|---|---|---|---|---|
| 0 | 49 (r1,c17) | >= 750 | foot, Ragnarok | wm20 tmdome1 Shumi Village |
| 1 | 81 | | foot, Ragnarok | wm33 cwwood1 Chocobo Forest |
| 2 | 145 | | foot, Ragnarok | wm34 cwwood2 Chocobo Forest |
| 3 | 149 | >= 750 | foot, Ragnarok | wm19 tgview1 Trabia Garden |
| 4 | 150 | >= 750 | (y split) | wm19 Trabia Garden / wm35 cwwood3 |
| 5 | 219 | | foot, Ragnarok | wm36 cwwood4 Chocobo Forest |
| 6 | 234 | | foot | wm09 gnview1 Tomb of the Unknown King |
| 7 | 238 | >= 36 | foot, chocobo | wm03 dogate_2 Dollet |
| 8 | 264 | >= 333 | foot, chocobo | wm08 glrent1 Deling City |
| 9 | 267 | >= 290 | foot (x/y boxes) | wm06 ggview1 (moment < 490) / wm07 ggsta1 Galbadia Garden (< 3900) |
| 10 | 268 | 290..315 | foot | wm05 gwroad1 (Timber forest road) |
| 11 | 273 | | foot, chocobo | wm01 bcgate_1 Balamb town |
| 12 | 274 | < 570 | foot | wm00 bggate_1 Balamb Garden gate |
| 13 | 275 | | foot (x split) | wm02 bdview1 Fire Cavern (x >= 0x15A0) / wm00 Garden gate (< 570, x <= 0x800) |
| 14 | 279 | | foot, Ragnarok (x split) | wm22 tvglen1 / wm23 tvglen5 |
| 15 | 327 | 350..490 | foot, chocobo | wm11 gmout1 Missile Base |
| 16 | 361 | >= 350 | foot, chocobo | wm10 gppark1 D-District Prison |
| 17 | 365 | >= 205 | foot | wm04 tigate1 Timber |
| 18 | 370 | >= 3900 | Ragnarok | wm13 fhparar1 FH |
| 19 | 370 | 636..3900 | car (tile 0x40) | wm13 fhparar1 FH |
| 20 | 370 | 636..3900 | Garden (ff21) | wm12 fhdeck2 FH docks |
| 21 | 373 | >= 1600 | foot | wm24 etsta1 (< 3000) / wm46 etsta2 (3000..3900) |
| 22 | 374 | | foot | wm25 elview2 |
| 23 | 378 | >= 1750 | foot | wm28 edview1b (< 3000) / wm57 edview2 (3000..5000) |
| 24 | 393 | >= 750 | foot (x split) | wm14 gfvill24 Winhill / wm15 gfview1a |
| 25 | 406 | >= 1750 | car / Ragnarok / foot (x split) | wm27 ecpview1, wm68 ecpview2, wm26 ecenter2 Esthar City |
| 26-28 | 407, 438, 439 | 1750..3900 | foot, chocobo | wm26 ecenter2 Esthar City |
| 29 | 441 | >= 1750 | foot | wm30 efview1 (< 3000) / wm69 efview2 |
| 30 | 443 | >= 1750 | foot | wm29 esview1 (< 3000) / wm47 esview2 |
| 31 | 466 | | foot, Ragnarok | wm39 cwwood6 Chocobo Forest |
| 32 | 506 | >= 1750 | foot | wm31/wm48/wm49 eeview1-3 by moment |
| 33 | 592 | | foot, Ragnarok | wm16 crview1 Centra Ruins |
| 34 | 652 | >= 900 (ff21) | foot, Ragnarok | wm18 ehenter2 Edea's House |
| 35 | 653 | | foot, Ragnarok | wm38 cwwood7 Chocobo Forest |
| 36 | 693 | | foot, Ragnarok | wm37 cwwood5 Chocobo Forest |
| 37 | 705 | | car (tile 0x40) | wm21 sdisle1 |

Not in the script but flagged in `wmx.obj`: segments 205, 300, 329 (section
12, a four-entry script of the same shape returning `ff15 <n>`, used by the
touched-object path at 0x5485FD) and 214, 215, 246, 247 (north of Esthar,
no entry: unreachable on foot or handled by vehicles). Lunar Gate, Tears'
Point, Sorceress Memorial and the Deep Sea Research Center are not walk-in
entrances (Ragnarok landing / scripted arrivals) and the East Academy
station does not exist as a world-map location: the Deling train leaves
from Galbadia Garden's own field.

The full wm-field table (72 entries, live dump) is in
`tools/poc_story_keys.py` (`WM_FIELD_LABEL`) and the door coordinates per
segment in `DOORS` there.

## Live results (2026-09-11, Disc 1 save at moment 205, Balamb)

- Section 8 resident at 0x1E9E7AC == archive bytes.
- Warping onto Balamb's door tile (12390, -26709, height -301; segment 273
  block 10) entered field 106 `bcgate_1` within a tick, with the exit
  request record reading `01 00 01 FF` (avatar on foot, wm01). The trigger
  is level-sensitive: standing on a door tile is enough, no movement
  needed, and the tile pointer updates on a teleport.
- Door tile coordinates from `wmx.obj`: world x = col*8192 - 131072 +
  bcol*2048 + vertex.x, world y = row*8192 - 98304 + brow*2048 - vertex.z,
  height = vertex.y (blocks are a 4x4 grid inside the segment; vertex.z runs
  -2048..0). The `ff8/warp.py` landmark for Balamb is inside the flagged
  block but not on a flagged triangle, which is why the first automated
  poke was inconclusive.
- **Lock direction PASSED**: entry 11's segment argument set to 0xFFFF,
  avatar warped onto the same Balamb door tile (door flag read true, tile
  pointer 0x201B258), four seconds on the world map with no entry; pristine
  bytes restored, entrance works again.
- **The buffer is re-read from disk on every world-map load**: a Deling
  unlock written while inside Balamb town was gone after walking out
  (`live == file` again). The client must re-apply its gates on every
  `MODULE_WORLDMAP` entry, exactly like the vehicle park writes.
- **Tile pointer caveat**: `[0x20409FC]` updated within a second after a
  short teleport (same segment) but stayed at one address across three
  later teleports, including one to another continent. A teleport-then-
  read of the door flag is therefore not a reliable oracle; the engine
  refreshes it as the avatar moves. Consequence: the automated Deling
  early-entry test ("did not enter") is inconclusive until the player takes
  a step on the door; retest queued.
- **Unlock direction (C0 early entry) PASSED**: entry 8's moment argument
  set to 0 on the moment-205 save, avatar warped onto Deling City's door
  (segment 264); the first step refreshed the tile pointer (0x1FD0D40 ->
  0x1FD8CA8, door flag true) and the game entered field 750 `glrent1` with
  the exit request `01 00 08 FF`. What the town shows in that story state
  and whether leaving returns to the world map: see the C0 notes in
  `plan-sync-feedback.md` once the walk-through is done.
- Accident worth remembering: the Balamb Garden gate footprint (entry 12,
  segment 274, moment < 570) covers the open ground at (21731, -28016)
  where this save had been standing; restoring Balamb's entry while the
  stale tile flag was set entered `bggate_1`. Restore off any footprint.

## Design consequences for Story Keys

- Mechanism A is confirmed as a pure data edit: one u16 per town. Lock =
  `ff06` argument to 0xFFFF; unlock (early entry) = `ff02` argument to 0;
  restore = pristine bytes from `world.fs`. No rebuild, battle or field
  exit needed: the script is evaluated every tick from the resident buffer.
- The client must confirm whether the buffer survives world-map reloads
  (run_c0 step 1). Either answer is cheap: re-apply on every
  `MODULE_WORLDMAP` entry.
- Entries are per segment, so towns sharing a segment share a lock (Balamb
  Garden gate + Fire Cavern in 275 are split by an x condition, so they can
  be told apart by editing the branch's `ff08` instead; Trabia Garden +
  chocobo forest in 150 likewise). Everything else is one town per entry.
- Chocobo forests have no moment gate at all in vanilla: keys for them are
  pure lock.
- Esthar City is four entries (406, 407, 438, 439) plus the car/Ragnarok
  branches; one key covers all four.

## C0 early-entry walk-through (Deling City at moment 205, 2026-09-11)

Fields visited, in order: glrent1 (gate, car rental), glstaup3 / glstaup1 /
glstaup2 (bus stops), glmall1 (shopping arcade), glhtl1 (hotel lobby),
glclub1 (hotel lounge). The town behaved as a normal town through the gate,
the buses, the arcade and the hotel lobby. **glclub1 softlocked**: its
script runs the Julia lounge scene, which expects story state the save does
not have, and the conversation cannot proceed. No field write is safe, so
the only exit is a reload.

Consequence for C3 (early entry): the world-map door is the only gate the
client controls; interior doors inside a town cannot be blocked. Early
entry is therefore only shippable for towns whose every reachable interior
field is safe at moments below the story window, or with a documented
"do not enter X before the story" list per town. Deling City needs at
least the hotel lounge on that list; a per-town survey (every interior
field, on a low-moment save) is the Phase 2 live work for C3.
