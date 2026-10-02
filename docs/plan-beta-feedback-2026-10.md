# Beta feedback plan — Discord thread, 28 Sep – 1 Oct 2026

**Status 2026-10-02 (branch fix/oct-feedback, uncommitted, 583 tests):**
- **Headline CONFIRMED LIVE:** the running game read var256 = 205 with the
  world-map copy at 3167 on the world map.
- **Built:**
  - Headline fixes 1-3: honest copy (`heal_wm_moment_copy`), story-jump
    guard (`check_story_jump` + `/ff8keepstory`, which also covers the Edea
    goal), A1-A7.
  - B1-B6: learn-prerequisite rules from `GF_ABILITY_PREREQ`, with the
    ladder tier 150 → 140; Tonberry key rule; Bika slot 175 → Ragnarok
    Flight; no keys in Ultimecia's Castle; Card Club `cc_win` trigger;
    option text.
  - C3: per-junction/command tracker toggles.
  - Player guide; packs regenerated (versions not bumped yet).
- **Design changes from the plan:**
  - B4 keeps the Lunatic Pandora Laboratory key as progression. A location
    rule on a non-progression item makes that location unreachable in
    logic, which fails generation.
  - The Edea goal stays moment-based, behind the jump guard, which keeps
    offline catch-up.
- **Not built:** C1 free-roam option (judge after the honest-copy live
  test); C2 fast-travel paging (needs the WARP_TARGET_CHAR capture); D
  sidequest research.
- **Live play test 2026-10-02 (seed output/livetest_1002, slot WilsonOct,
  saves slot1 02 and 10):**
  - PASSED:
    - Door copy healed after a battle (205, not 3167); the ship spawns,
      boards, flies and lands; the Balamb Garden gate opens; Deling stays
      shut at 205.
    - Junction strip keeps ST-Atk (Zell's Blind at +0x66).
    - World-map menu Potion warps; a battle Potion doesn't.
    - Baseline bulk gate held 15 checks for /ff8adopt.
    - /ff8keepstory released 9 held story checks.
    - Card game: module 8, FIELD_ID stays put, TT_WINS rises inside the
      game (cc_win's premise).
  - FOUND AND FIXED during the test:
    - WARP_TARGET_CHAR indexes JOINED characters in roster order (0/1/3
      for Squall/Zell/Selphie with Irvine and Rinoa unjoined; Quistis in
      reserve = 2 -> Timber). Labels now come from memory.joined_chars().
    - A Ctrl+R reset never shows module 0, so every title-based
      re-baseline was dead. New track_save_load / save_loaded detect loads
      from a GAME_TIME discontinuity. That fixed a false "Story jumped" on a
      load, a load-time warp plus Potion "refund", and carried-over item,
      AP and First Draw baselines.
    - The Lamp window's give-back read as a vanilla grant and sent "Magical
      Lamp: Diablos" with no fight; it now marks the write as ours.
  - Not exercised live: the specific Kadowaki/King/Joker fields (no save
    can reach a rematch); B3 Garden Travel points.

Source: screenshots of the Archipelago Discord thread (DrMisunderstood,
yezzdia, TimShuggah). Follows docs/plan-beta-feedback-2026-09.md (reports up
to 27 Sep, Phases 0–3 released in v0.8.0). DrMisunderstood played these on
v0.7.0, so every item was re-checked against main plus the uncommitted Lamp
window, ambush and battle-module-5 fixes. None of the code paths below
changed between v0.7.0 and main unless noted.

"Verified" means the cause is confirmed in code, exe or data. "Likely" means
it fits the code but hasn't been reproduced live.

## Headline: why the early Ragnarok breaks the story — VERIFIED statically

The world map keeps its **own copy of the story moment**, a u16 at
VA 0x2036BDE. On every map load, `sub_544860` copies var256 into it
(0x5448F2/0x544903: `mov dl,[0x1CFEAB8]` → `mov [esi+0x6E],dl`, esi =
0x2036B70) and then runs placement. Each tick, the door evaluator compares
against the copy (0x54613A: `mov dl,[0x2036BDF]; mov al,[0x2036BDE]`), not
var256.

The early-Ragnarok window fakes var256 = 3167 during exactly that reload (the
battle return, and the field exit at client.py:984-989); that is how the ship
spawns. So **after every faked rebuild, every town door is judged at Disc 3+
moment until the next map load**, even after var256 is restored. v0.8.0's
leak fixes only cover var256.

This explains the 29 Sep exploration without a leaked save:
- Timber entered before Fire Cavern: Timber's gate is moment 205, and the
  true moment was under 30.
- Winhill, Shumi, Trabia (gate 750), Edea's House (900), FH (636..3900, entry
  19 is the Ragnarok pad), GSL and Esthar (1600/1750) entered on Disc 1. GSL
  and Esthar loaded their Disc 3 variants.
- Missile Base (<490) and the exam-era Galbadia Garden branch were shut.
- Not yet reported, but predicted: the Balamb Garden gate (<570) and the
  Timber forest road (290..315) are shut after a faked battle.

It also corrects the September plan. "Disc-1 FH entry only via a leaked
3167" (plan-beta-feedback-2026-09.md, 2.3) is wrong: the cached copy is the
cause.

The old note "cached lever 0x2036BDE doesn't work" (Session 7, 2026-09-08)
fits this picture. Holding the copy at 3167 didn't spawn the ship because
the load overwrites it from var256 before placement runs. It is dead as a
*spawn* lever, but it is the live *door* gate.

Two side effects multiply the damage once a door lets the player in early:
- **Story checks fire from moment jumps — VERIFIED.** A story check is
  `game_moment() >= value` (client.py:1648-1649). Nothing compares the
  moment between ticks. `_bulk_gated` skips saves that carry our AP header,
  so campaign saves are never held. The Timber train scene (writes ≥233)
  sent Fire Cavern, Dollet, SeeD Graduation and Dream 1 in one tick.
  Caraway's mansion sent Forest Owls and Dream 2.
- **The Edea goal is a moment threshold — VERIFIED.** `moment_true >= 392`
  (client.py:58, 1632-1643). Edea's House, the FH "welcome" scene and the
  Dobe negotiation all write a higher moment, so each one ended the game.
  The Omega goal (encounter 462) and the Ultimecia goal (field 573 + HP
  phases) are robust.

### Fixes, in order
1. **Honest copy (root fix, every mode).** When the grace window ends on the
   world map, write the true moment into 0x2036BDE/0x2036BDF. That is about
   10 lines in `update_moment_window` (client.py:943-1003). Placement is only
   evaluated at load, so the ship should stay put.
   Live check first: after a world-map battle and the 3 s grace, the copy
   reads 3167 while var256 reads the true moment. Then: Timber is shut below
   205; the Balamb Garden gate is open; boarding, flying and landing still
   work.
2. **Edea goal from the fight, not the moment.** The parade fight is
   encounter 136. Its scene flags include NO_VICTORY_SEQUENCE, so
   `track_battle` will likely log it as "escaped". Reuse the Ultimecia
   pattern (client.py:1614-1625): battle 136 seen and left with the party
   alive, saved to the sidecar, then moment ≥ 392. `won_encounters` isn't
   saved today (client.py:639, 732).
3. **Jump guard.** If the true moment crosses more than one beat start
   (`BEAT_START_MOMENT`) in a single 0.5 s tick, hold story checks and the
   goal, log what happened and why, and release with an `/ff8adopt`-style
   command. This protects the multiworld, but not the save: the scene has
   already written its story flags.
4. **Story-safe Ragnarok (default) vs free roam (opt-in).** With the honest
   copy, vanilla gates do most of the work. A few spots have no gate and
   need a lock patch when `vehicle_unlocks` is on, independent of
   `story_keys`: the Deep Sea Research Center (entry 37, a Ragnarok pad),
   the GSL foot side (segment 374 → wm25), FH entries 18-20, the D-District
   garage, and Dollet below moment 30. Then survey Centra Ruins, which is
   marked `early=True` with no interior survey note. Keep today's behaviour
   behind an explicit free-roam option whose text warns about softlocks and
   the Edea goal. This matches DrMisunderstood's suggestion: the Ragnarok
   should be for free-roam play, not story play.
   The lock patch can't cover the section-36 exits (wm40-45, wm17/64/44),
   multi-branch entries (segments 275, 150, 267, 279, 406, 32), or Lunatic
   Pandora (spawned at reload).
5. **Still not built from the September plan:** 1.1 step 5, "don't fake
   below moment 150" (Dollet exam, invisible Squall). `VEHICLE_BLACKOUTS`
   (client.py:92-94) only has (2544,3150) and (3790,4005).

Also noted: the avatar codes in docs/research/world-map-entrances.md:47 and
tools/poc_story_keys.py:25,97 are wrong. The Ragnarok is 0x32 (memory.py:558,
confirmed live), and the exe sends 0x32 to wm44 and 0x30 to wm65. The rows
labelled "Ragnarok" are avatar 0x31.

## Phase A — client bugs (no regeneration; existing seeds fixed by a client update)

### A1. "Death x5" grants Pain, "Pain x5" grants Float — VERIFIED
items.py:135-136 grant spell ids 45 and 47. The kernel names (text.MAGIC_NAMES)
are 43 Death, 45 Pain, 47 Float. Every other magic item and all 99 field
draw-point slots match the exe.
Fix: 43 and 45. Add a test asserting every magic item's name equals
`MAGIC_NAMES[id]`. Fix the comment at items.py:104-113 ("Float 48" → 47).
Wrong stock already granted stays in the save.

### A2. Status-attack junction wiped while Elem-Def-J is locked — VERIFIED
memory.py:229-230 map ST-Atk-J (11) to 0x6A and Elem-Def-J (12) to
0x66..0x69. Hyne's struct (thirdparty/hyne-src/src/SaveData.h) and 528
junctioned records in the save library say: 0x65 elem-atk, **0x66 status-atk**,
0x67-0x6A elem-def ×4, 0x6B-0x6E status-def ×4.
Effect: with ST-Atk-J owned but Elem-Def-J locked, `strip_locked_char_state`
(client.py:2314) zeroes 0x66 every safe tick. The junction survives while the
menu is open and vanishes when it closes. That is exactly "it says it has
been revoked". The reverse also breaks: with Elem-Def-J owned and ST-Atk-J
locked, the client wipes elem-def slot 4 and leaves ST-Atk alone.
The live self-test (tools/live_selftest.py:650) checks the repo's own
offsets, so it couldn't catch this.
Fix: `11: (0x66,)`, `12: (0x67, 0x68, 0x69, 0x6A)`; fix the comment at
memory.py:215; pin the offsets to the Hyne layout in a test. Make the strip
log name the character, the slot and the missing item. Only log revokes for
owned GFs; the "Doomtrain: locked —" lines for unowned GFs are noise.

### A3. Checks-only magic takes the excess from Squall even when he's absent — VERIFIED
`enforce_magic` (client.py:1391-1442) computes the excess from party-wide
totals, and `remove_magic` (memory.py:1136-1152) takes it from records 0→7,
so Squall pays first. The drawer keeps the drawn copies.
Fix: keep last tick's per-character stock; give `remove_magic` a `prefer=`
list (characters whose stock of that spell rose since the last tick first).
A Switch-menu swap leaves the total unchanged, so it never triggers this.

### A4. "Locked: Key: Chocobo Forests" shown at Trabia Garden — VERIFIED (message only)
`announce_shut_door` (client.py:1349-1365) picks the first shut area whose
segments contain the player's segment. Segment 150 is Trabia (Y ≥ 0x1000 →
wm19) and a chocobo forest (Y ≤ 0xFFF → wm35). The door words respect the
split; only the message is wrong. The same bug affects segment 275: in areas
mode with Fire Cavern locked, the Balamb Garden gate prints "Locked: Key:
Fire Cavern".
Fix: an optional per-segment split in `AreaData` (Trabia y ≥ 0x1000, forests
y ≤ 0xFFF, Fire Cavern x ≥ 0x15A0); filter candidates by the local
coordinate; make the pick deterministic.

### A5. Monsters Felled fires late — VERIFIED (late, not never)
The exe routine at 0x52BC00 rebuilds monster_kills (0x18FE9FC) as the sum of
the eight character records' kill counters (+0x90) only when a field script
loads. World-map fights don't count until the next town. That fits "not sure
I'm receiving them".
Fix: a trigger kind that sums the u16 at char record +0x90 directly, used in
place of `u32_ge` on 0x18FE9FC (locations.py:916-920).
Live check first: the ambush note shows some record fields are written only
at save time.

### A6. Fast-travel trigger hardening — LIKELY
- The trigger reads `WARP_TARGET_CHAR` (memory.py:587-591), which is the
  cursor position in the item-use list, but destinations are labelled by
  roster index (client.py:1156-1162). Only slot 0 was confirmed live. So
  labels are wrong whenever the party isn't in roster order, and Seifer and
  Edea (records 6-7) can never be selected.
- `maintain_warp_crystal` runs on any safe tick. A Potion used in battle is
  seen as a drop after the fight and warps with a stale target. Selling
  Potions at a shop is refunded, which is a free-gil exploit.
Fix: arm a warp only when the drop happened in a menu opened from the world
map (module 6 entered from 2), and re-baseline after battles and shops. See C2
for the destination redesign.

### A7. Junction VIII launch sent nothing (TimShuggah) — environment, LIKELY
The client attaches to `FF8_EN.exe` by name with no version check, and the
maintainer's own J8 + FFNx setup works. Ranked causes:
1. J8 or the game elevated (admin), so the client can't open the process.
2. J8 pointed at another install (the 2000 `ff8.exe`); the client waits
   silently because `ff8.exe` isn't in `WRONG_PROCESS_HINTS` (memory.py:20-46).
3. A different save loaded ("HOLDING this save").
4. A stale duplicate `FF8_EN.exe`.
Cheap fixes: add an `ff8.exe` hint; mention elevation and J8 in the attach
failure message; log the hooked exe's path on attach. Ask him for the client
log from the J8 run.

## Phase B — world/logic fixes (world bump + tracker pack regen)

### B1. GF learn prerequisites aren't in logic — VERIFIED (DrMisunderstood's Disc 3 dead end)
kernel.bin section 2 stores a prerequisite byte per learnable ability
(record +0x1C, value ≥ 101 → entry value−101 must be learned first;
cross-checked against the save library). abilities.py has no prerequisite
data. `set_rules` (__init__.py:536-559) adds lock items only to "Mastered"
checks, on the assumption that "the learn edge fires before the revoke".
That holds for the locked ability itself, but not for an ability whose
prerequisite is held down by a lock. A logic probe on main found eight learn
checks in logic without the item they really need:
- Leviathan GFRecov Med-RF ← "Leviathan: Supt Mag-RF" (the player's case:
  Key: Lunar Gate sat on it, and the Supt Mag-RF item sat at Tonberries 5)
- Quezacotl Card Mod ← "Quezacotl: Card"
- Diablos Enc-None ← "Diablos: Enc-Half"
- Alexander Med LV Up ← "Alexander: Med Data"
- Tonberry Sell-High ← "Tonberry: Haggle"
- Tonberry Call Shop ← "Tonberry: Familiar"
- Cerberus Auto-Haste ← Spd-J (junction lock)
- Cactuar Expendx2-1 ← Eva-J (junction lock)
- Possibly Carbuncle Auto-Reflect via Counter (prerequisite values below 100
  aren't decoded yet).
Fix: generate `GF_ABILITY_PREREQ` from kernel.bin into abilities.py; in
`set_rules`, add every lock item on each learn check's prerequisite chain.
test_abilities.py:99-112 assumes 154 lock-free abilities, but counting
prerequisites only 140 are, so "GF Abilities Learned: 150" can need lock
items. Fix the ladder or the tier.
Rejected: DrMisunderstood's "pre-unlock every ability", which would remove
the lock design. Modelling the chain gives him what he actually wanted:
nothing unreachable.

### B2. Tonberries Culled has no Centra Ruins key rule — VERIFIED
"Tonberries Culled: 5/10/20" (locations.py:945) are missing from
`AREA_LOCATIONS["Centra Ruins"]` (regions.py:394-395), so all three are in
logic without the key.
Fix: add the prefix. That pushes the Centra key ahead of anything that needs
the Tonberry checks.

### B3. Bika Snowfield "Flare #2" needs the Ragnarok — Garden reachability is the player's claim, unverified
Slot 175 (locations.py:1248) sits in "Garden Travel". On main, story mode can
still put Key: Great Salt Lake there with no other route.
Fix: move 175 to "Ragnarok Flight". Then walk the other Garden Travel points
live (Vienne 158, Almaj 149, Cape of Good Hope 148, Nectar 147, Centra Crater
146, Hawkwind 154, Bika 155-157), erring late per locations.py:1187.
Optional data: have the client log WORLD_POS and the slot each time a world
draw fires, so later moves rest on coordinates.

### B4. Key placement rules — VERIFIED (design)
- Key: Lunatic Pandora Laboratory gates only "Draw Point: Lunatic Pandora
  Laboratory (Death)", a filler-only, one-window point (locations.py:1116),
  so it isn't a logic bug that it landed in Ultimecia's Castle. But the key
  is near-useless. Make it useful-class, not progression.
- No "Key:" item should be placed in Ultimecia's Castle; there is no world
  map on Disc 4. Add an item rule. This answers DrMisunderstood's "keys only
  on Discs 1-3".

### B5. Card Club checks fire at the reveal, not the win — VERIFIED
Joker, Kadowaki and King read var 475 (locations.py:345-360), which Hyne
names `tt_players_bgu_dialogs2`; these are dialogue flags:
- Kadowaki: bghoke_1 sets bit 1 right after "I was the CC group King…".
- Joker: bgmon_4 sets bit 4 after "I'm Card Magician 'Joker'".
- King: bgryo2_1 sets bit 5 when the dorm-night event starts.
A win stores no savemap flag for any of the three. The five suits (var 477)
are set after the win and are fine.
Recommended fix: a true-defeat trigger. It fires when TT_WINS rises while
FIELD_ID is 179 (Kadowaki), 217/841 (Joker) or 246 (King), with the reveal
bit already set. It only catches wins while the client runs.
Live check: FIELD_ID stays put through the card game. Fallback: rename the
three checks to what they detect.

### B6. Option text — VERIFIED
- `story_gates` (options.py:52-64): "off … (pre-0.4 behaviour)" meant
  nothing to two players, and "normal frees about 25 checks" is wrong (the
  default first sphere is ~57; 25 is the tight figure). Replacement draft:
  > How many multiworld items the generator assumes you hold before each
  > story chapter's checks count as reachable. It never blocks you in-game
  > and adds or removes no checks; you always play the whole story in order.
  > It only decides where progression items can be placed.
  > **off:** the only requirement is the "GFs Required for Disc 3" count at
  > Edea's House; about 220 checks are reachable from the start, so your
  > power can arrive late. **normal:** about 60 checks open at the start;
  > from Timber on, each chapter needs a few more GFs (plus character,
  > junction and command unlocks when those locks are on), rising to the
  > Disc 3 count. **tight:** one or two more items every chapter, and a very
  > small start.
- StatChecks docstring still says steps "20k-300k"; the tiers are 100k-400k.

## Phase C — design changes the feedback asks for

### C1. Story-safe Ragnarok
See the headline, fix 4. This is the biggest gameplay improvement in this
batch.

### C2. Fast-travel destinations (DrMisunderstood)
Seifer and Edea own Winhill and Trabia, but Seifer never appears on the world
map and Edea only joins on Disc 3, so two warps are effectively console-only.
Proposal: page by item. Potion on the Nth listed party member = page 1;
Potion+ (id 2) = page 2; Hi-Potion+ (id 4) = page 3. Page size equals the
number of selectable list entries. Label from the live list order (savemap
party array), never records 6-7. Print overflow destinations as
"/ff8warp only". Optionally rename the Potion's kernel text to show the page.
Live capture needed: a party in non-roster order, e.g. [Squall, Selphie,
Zell], with reserves present. Record WARP_TARGET_CHAR for each visible
target, and check whether reserves appear in the list.

### C3. Tracker: per-junction toggles
The pack shows each GF and Key, but junction unlocks only as one "Junction
Rights" counter (tools/gen_tracker_pack.py:1121-1126). DrMisunderstood built
his own tracker to see GFs, junctions and keys individually. Add a toggle per
junction-lock item (and per command lock), and keep the counter for the
ladder logic.

## Phase D — new check requests (backlog; none exist today)

| Request | Signal known? | Note |
|---|---|---|
| Garden faction war: saving each department | no | needs a live diff; Garden Revolt beat |
| Grease Monkey rescue (occupied Balamb) | no | only the unrelated "Timber Maniacs: FH Grease Monkey's House" exists |
| Master Fisherman (FH) | no | |
| Shumi Village quest stages | candidate vars 605-623 | savemap-measurables.md:88; each stage needs a live diff |
| Winhill vase pieces | no | var 387 is the dream, not the vases |
| D-District Prison boxes / Moombas | pickups not mapped | one-window area, so new checks there are filler-only |
| Timber NPC who gives Rinoa a Potion | no | Potions are too common to detect by count; skip |

Suggested scope: a "sidequest expansion" research pass on Shumi, Winhill,
Master Fisherman and the Garden departments; it answers "otherwise what is
the point of the keys?" for those towns.

## Not bugs (answer and move on)
- **Timber Maniacs from Centra Ruins:** vanilla. The crview1 startup script
  hands over the Centra issue silently on first arrival (sets var 305 bit 2).
  Optional: a client log line and a guide note.
- **Shumi Ultima draw not a check:** slot 78 is a location ("Draw Point:
  Shumi Village Entrance (Ultima)"), but it doesn't exist on an Edea-goal
  seed. The early Shumi entry itself is the cached-moment bug.
- **Odin and Gilgamesh both appearing:** two independent items (September
  plan 2.8); the doubled appearances are harmless and goofy.
- **"Lunatic Pandora on the map but can't fly in":** spawned by the 3167
  reload; it goes away with the honest copy only if placement re-runs at the
  true moment. Fold into the live check.
- **Triple Triad Random-rule workarounds:** the `triple_triad_rules:
  no_random` option is on main, unreleased (Phase 4).

## Unsticking DrMisunderstood's current Disc 3 seed — LIKELY
That seed ships the story-window data in its slot data (v0.7.0 __init__.py:582),
and the v0.8.0 client opens GSL and Esthar City (901–2502) and Lunar Gate
(1310–3150) during their beats in every keys mode. Updating only the client
to 0.8.0 should open the GSL and Lunar Gate doors without the keys. The
Rinoa-carry GSL softlock is inside that window. Untested live.

## Live verification list
1. 0x2036BDE after a world-map battle + grace = 3167 (the headline). Then the
   honest-copy write: Timber shut below 205, Garden gate open, ship boards,
   flies and lands.
2. Encounter 136 (Edea parade): what `track_battle` logs.
3. Monsters Felled: char record kills rise after a world-map battle without a
   field load; 0x18FE9FC doesn't.
4. Card Club: FIELD_ID through the card game; TT_WINS rises by the next safe
   tick.
5. Fast travel: WARP_TARGET_CHAR per visible target with a non-roster party.
6. Bika and the other Garden Travel world draw points by Garden.
7. A2 junction offsets: own ST-Atk-J with Elem-Def-J locked; the status
   junction must survive closing the menu.
8. What wm25, wm45 and wm40-43 lead to.

## Suggested order
A1, A2, A3, A4 (small client fixes, no regen) + headline fixes 2 and 3 (Edea
goal, jump guard) → live check 1 → headline fix 1 (honest copy) → B1-B6
(world bump, pack regen) → C1 story-safe Ragnarok + free-roam option → C2,
C3 → D research.
Bundle the first two groups with what's already on main (Phase 4 options,
gil-floor revert) and uncommitted (Lamp window, ambush, battle-module-5
fix) as v0.9.0.
