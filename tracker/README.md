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
  (read from the savemap's save-preview location id, see `ff8/areas.py`) to
  Archipelago data storage, and the pack activates the matching World Map
  area sub-tab as you travel. The `»` toggle in the item row turns this off.

Everything also works manually (no connection): click items to toggle them and
the Story Progress counter to advance regions; the Disc 3 gate then assumes the
default of 6 GFs. The check-group toggles start ON so all check sets are
visible until slot data says otherwise.

## Maps

Four tabs (all original art — no game assets, matching the repo's
no-Square-Enix-assets policy):

- **World Map** — a stylized rendering of the FF8 world with check pins at
  their real geography (towns, dungeons, the Horizon Bridge, magazine pickups,
  UFO sightings, optional bosses). Interior areas live in inset panels on the
  ocean: Balamb Garden, Galbadia Garden, Space/Ragnarok, and Ultimecia's Castle.
  Sub-tabs show the **Full** map or one area at a time (Balamb / Galbadia /
  Trabia / Esthar / Centra / Space / Castle — cropped, enlarged views); with
  autotracking these follow the player automatically.
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
`NODE_ANCHOR` (in `tools/gen_tracker_pack.py`) — that's intentional.
