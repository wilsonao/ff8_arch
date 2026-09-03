# Community map art variant

A community contributor — **caedesender** on Discord — drafted a visual
tracker layout for the FF8 apworld:
three image tabs (world map, Triple Triad compendium sheet, character screen)
with hand-placed markers tying AP location names to pixel coordinates.
`mapping.json` here is that draft, bug-fixed and extended to current apworld
coverage (see below). Schema: `tabs[] -> {name, image, location_size,
markers[] -> {x, y, label?, locations[], size}}`.

## Why the images are not in the repo

The three PNGs contain Square Enix art (card faces, menu screenshots, game
renders), which we do not ship (design.md §6 — same reason the release pack
uses generated art only). The marker **data** is original work and lives here;
the **art** stays local-only:

```
thirdparty/community_map_art/images/1.png   world map      (1600x1200)
thirdparty/community_map_art/images/2.png   card compendium (1600x1200)
thirdparty/community_map_art/images/3.png   characters      (1600x1200)
```

`thirdparty/` is gitignored. When those files exist, `python
tools/gen_tracker_pack.py` additionally generates
`tracker/ff8_ap_tracker_community/` (also gitignored) and
`build/ff8_ap_tracker_community.zip`: the full standard pack — same logic,
autotracking, and option toggles — with its World Map group replaced by the
art map (a Full tab plus per-area crops: Balamb / Galbadia / Trabia / Esthar /
Centra / Space / Castle, `COMMUNITY_AREA_VIEWS` in the generator), and Cards /
Characters tabs from the other two images. Area tab titles match the standard
pack's, so follow-the-player autotabbing works unchanged. The space/castle
views crop the artist's corner art and the balamb view the island at the
trabia/esthar rect junction; those three claim their pins exclusively so
clusters don't bleed into neighboring views. Do not publish that zip anywhere.

## Origin of the format (identified 2026-09-03)

The contributed zip is not a PopTracker pack: it is a "mapping preset" for the
**Archipelago Visual Tracker** (https://github.com/Wakamu/Archipelago — a fork
of FarisTheAncient's UT repo; install its `visualtracker.apworld`, requires
Universal Tracker). Presets are authored with the companion Mapping Preset
Editor (https://github.com/Wakamu/archipelago-mapping-editor), which explains
the `mapping.json` schema. The tracker loads any `*.zip` from
`<Archipelago install>/visual_packs/`, matching the preset's `game` field to
the connected slot.

`tools/gen_tracker_pack.py` therefore emits two Visual Tracker presets:

- `build/ff8_visual_tracker.zip` — the same node data pinned on our
  **generated** world / extras / abilities images. No SE art, so this one is a
  release asset (attached by CI alongside the PopTracker pack).
- `build/ff8_visual_tracker_community.zip` — this (fixed + extended)
  `mapping.json` re-zipped with the local SE art, plus a generated catch-all
  "Counters" tab holding every table location the mapping leaves unpinned
  (the 26 grind counters, which have no geographic home on the art), so the
  preset always covers the full check table. Like the community PopTracker
  variant it contains SE art: local-only, never publish.

## Changes made to the contributed draft (v1, 2026-09-02)

Fixes:
- Galbadia Garden marker listed "Draw Point: Ultimecia Castle Art Gallery
  (Meltdown)" (copy-paste slip) — removed.
- Characters tab had "Angelo Trick: Wishing Star" twice; the marker on Rinoa's
  weapon row is actually "Ultimate Weapon: Shooting Star (Rinoa)" — renamed.
- Marker label "Laguna Dream 5: Esther" -> "Odine's Laboratory".

Extensions (the draft predates the 580-location table):
- Per-issue Timber Maniacs (14) added to their pickup cities; new "White SeeD
  Ship" marker (also holds its Holy draw point).
- Pet Pals Vol.3/4 -> Timber, Vol.5/6 -> Esthar; Combat King 002 -> Balamb.
- New markers: Obel Lake, Chocobo Forests, and all 37 world-map draw point
  areas (125 draw point checks) hand-placed on the world image.
- SeeD Rank ladder -> Balamb Garden; Cid's Parting Gift -> Train to Timber;
  Gilgamesh Arrives -> Lunatic Pandora; Rule Abolished: Random (Centra) ->
  Centra Ruins.

Converter notes (tools/gen_tracker_pack.py):
- The five single-icon catch-all markers bottom-right of the world map
  (Magazines / Triple Triad / Battles / GF checks / Characters) are skipped:
  PopTracker draws one pin per *node*, so each would explode into a large pin
  cluster. Those checks live on the pack's Extras / GF Abilities tabs (and the
  community Cards/Characters tabs) instead.
- 26 pure grind counters (First Draws, Magic Collection, Monsters Felled,
  Steps Taken, Enemies Scanned, Random Rule Extinct) are Extras-tab-only by
  design.
- The two lore islands aren't drawn on the world art; their markers sit at
  the correct open-ocean spots (far east / far west).

Feedback for the contributor (not applied, worth a look): magazine placements
disagree with our researched pickup spots in a few cases (e.g. draft has
Weapons Monthly April at Balamb Garden, we have it in the Deling sewers;
draft's March is at Dollet, ours at Balamb Garden) — cosmetic either way since
the pin is only a doorway to the check.
