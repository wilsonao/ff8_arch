"""Precise tracker-map data extracted from the FF8 (Steam 2013) game files.

    python -m tools.mapgen            # writes tracker/geo/ (needs the game install)

tools/gen_tracker_pack.py then builds the PopTracker pack from tracker/geo/
alone, so the pack can be regenerated (CI, contributors) without the game.

What is extracted (all from Data/lang-en/{world,field}.fs; nothing here is a
game asset — the images are our own renderings of the walkmesh geometry and
the JSON holds coordinates):

- ff8data:   archive reader, wmx.obj world walkmesh, texl.obj palettes, the
             world-map draw point table (wmsetus.obj section 35), field
             walkmesh/camera/gateway/script parsing and the field camera
             projection.
- world:     a top-down world map rendered from the 517k walkmesh triangles.
- fieldmaps: per-screen floor plans (projected walkmesh, exits, draw points)
             composed into one image per town/dungeon.
- build:     drives both and writes tracker/geo/geo.json + images.
"""
