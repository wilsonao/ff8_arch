# FF8 Archipelago — PopTracker pack

A [PopTracker](https://github.com/black-sliver/PopTracker) pack for the FF8 apworld, with
Archipelago autotracking. **Do not edit the pack by hand** — every file in
`ff8_ap_tracker/` is generated from the apworld's own item/location tables:

    python tools/gen_tracker_pack.py

Re-run that after any change to `ff8/items.py` or `ff8/locations.py`; it rewrites
`tracker/ff8_ap_tracker/` and `build/ff8_ap_tracker.zip`.

## Install

Drop `build/ff8_ap_tracker.zip` into your PopTracker `packs/` folder and pick
**Final Fantasy VIII (Archipelago)** from the pack list.

## Autotracking

Choose **AP** in PopTracker's autotracking menu (bottom bar) and enter the server,
slot, and password. On connect the pack:

- toggles GFs / Magical Lamp / Solomon Ring as the multiworld delivers them;
- clears map locations as your checks are sent;
- infers **Story Progress** (the `Pr` counter) from checked story beats — checking
  "Fire Cavern Cleared" etc. advances it, which unlocks the next region's checks
  in logic;
- reads slot data: the check-group options (Draw Point / Triple Triad /
  Optional Boss / Rare Card / Sidequest / Magazine / Stat Ladder / GF Ability
  Checks) show or hide their check sets, and **GFs Required for Disc 3** sets
  the GF-count logic gate;
- **follows the player**: the FF8 client publishes the party's current area
  (read from the savemap's save-preview location id, see `ff8/areas.py`) and
  the field screen it stands on (`ff8_field_<team>_<slot>`, -1 on the world
  map) to Archipelago data storage; the pack activates the matching World Map
  area sub-tab as you travel and, inside a town or dungeon, that place's
  floor-plan tab (back to the area map when you step onto the world map).
  The `»` toggle in the item row turns this off.

Everything also works manually (no connection): click items to toggle them and
the Story Progress counter to advance regions; the Disc 3 gate then assumes the
default of 6 GFs. The check-group toggles start ON so all check sets are
visible until slot data says otherwise.

## Maps

Four tabs (all original art — no game bitmaps, matching the repo's
no-Square-Enix-assets policy; the maps are our own renderings of the game's
walkmesh geometry, see below):

- **World Map** — the real FF8 world, rendered top-down from the game's own
  world walkmesh (every coastline, mountain, road and rail where the engine
  has it). Each town, dungeon or landmark is one pin at its entrance whose
  colour sums up every check inside it (hover for the list, click a chest to
  mark one); each of the 125 world-map draw points is its own pin on the
  exact tile you draw from. Space/Ragnarok and
  Ultimecia's Castle have no world position and live in inset panels on the
  ocean. Sub-tabs show the **Full** map or one area (Balamb / Galbadia /
  Trabia / Esthar / Centra / Space / Castle, rendered at a finer scale); with
  autotracking these follow the player automatically. Inside each area tab,
  one tab per town/dungeon shows its **floor plans**: every screen that holds
  a check, drawn from that screen's walkmesh seen directly from above and
  turned so the in-game camera looks up the page (left and right match what
  you see on screen; lighter floor is higher), with exits labelled and draw
  points marked where their sparkle is. Checks are pinned on the screen they are obtained
  on (boss fights, magazine pickups, card players, quest NPCs). Mouse-wheel
  zoom (PopTracker 0.34+) is the intended way to read the big maps.
- **Region Board** — one panel per logic region in story order; useful for
  seeing exactly what the current story progress unlocks. Every non-ability
  check appears here as well as on its World/Extras pin.
- **Quests & Extras** — panels for the check sets that aren't places:
  Sidequests, Stat Ladders, Rare Cards, and Triple Triad (win/card ladders, CC
  Group, compendium). The four regional "Rule Abolished" checks stay on the
  World Map.
- **GF Abilities** — one column per GF (its signature-ability checks, then
  "Mastered") and the party-wide abilities-learned ladder along the bottom.
  Each GF's column is in logic only once you hold that GF.

The item grid also tracks the three cameo GFs (Odin, Phoenix, Gilgamesh) as
plain toggles; they don't count toward the Disc 3 GF requirement, matching the
apworld's logic.

Sections gated by the Magical Lamp (Diablos) and Solomon Ring (Doomtrain) show
as out-of-logic until you have the item.

## Universal Tracker

The same three maps and location layout are also written to `ff8/tracker/`
(with a node/section → location-id mapping) and ship inside `ff8.apworld`, so
[Universal Tracker](https://github.com/FarisTheAncient/Archipelago/releases)
shows them as map pages with no extra install — the world regenerates from slot
data alone (`ut_can_gen_without_yaml`). Regenerating the pack refreshes both.

Adding new locations to the apworld later will make the generator fail with an
"unanchored node" assertion until the new place is given a world-map anchor in
`NODE_ANCHOR` (in `tools/gen_tracker_pack.py`) — that's intentional. To pin the
new check inside a town's floor plan as well, add it to
`tools/mapgen/attribution.json` (the field screen it is obtained on).

## Map geometry (tracker/geo)

The map images and coordinates come from the game files, extracted once by

    python -m tools.mapgen        # needs the FF8 Steam install (FF8_DIR)

which writes `tracker/geo/` (committed): `geo.json` with the world transform,
the 127 world draw-point positions (wmsetus.obj section 35), every world-map
field's exit coordinate (section 9), the named regions per segment (section
19) and the per-screen pixel data of each floor-plan sheet; `world.png` and
`area_*.png` rendered from `wmx.obj`; and `places/*.png` composed from each
field's `.id` walkmesh, `.ca` camera, `.inf` gateways and the draw-point
entity positions in its `.jsm` script. `gen_tracker_pack.py` only reads
`tracker/geo/` and `tools/mapgen/attribution.json`, so the pack regenerates
without the game. Re-run `tools.mapgen` only when the renderers or the
attribution table change.
