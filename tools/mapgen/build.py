"""Write tracker/geo/: the precise map data the pack generator consumes.

    python -m tools.mapgen [--no-world] [--no-places]

Outputs (all committed, regenerated only when this package changes):
  tracker/geo/geo.json         coordinates: world transform, world draw points,
                               world-map field exits, region segments, places
  tracker/geo/world.png        4096x3072 world render (1 px = 64 world units)
  tracker/geo/places/<key>.png one floor-plan sheet per town/dungeon

Inputs: the game files (ff8data.GAME_DIR) and tools/mapgen/attribution.json
(location -> field/world attribution, hand-curated + script-derived).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import struct
import sys
from pathlib import Path

import numpy as np

from . import ff8data as D
from . import fieldmaps as FM
from . import world as WORLD

ROOT = D.ROOT
GEO = ROOT / "tracker" / "geo"
ATTRIBUTION = ROOT / "tools" / "mapgen" / "attribution.json"
WORLD_SCALE = 64


def _load_ff8(name: str):
    spec = importlib.util.spec_from_file_location(f"ff8_{name}", ROOT / "ff8" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


FIELDS_MOD = _load_ff8("fields")
FIELD_NAMES: tuple[str, ...] = FIELDS_MOD.FIELD_NAMES
DRAW_POINT_FIELDS: dict[int, tuple[int, ...]] = FIELDS_MOD.DRAW_POINT_FIELDS


def hyne_location_names() -> list[str]:
    """Save-preview location names in id order (Hyne Locations::fillList)."""
    src = (ROOT / "thirdparty" / "hyne-src" / "src" / "Data.cpp").read_text(
        encoding="utf-8", errors="replace")
    names = {int(i): n for n, i in re.findall(r'QObject::tr\("([^"]*)","(\d+)"\)', src)}
    return [names.get(i, "") for i in range(max(names) + 1)]


# ---------------------------------------------------------------------------
# Places: which town/dungeon a field belongs to, from its SETPLACE name
# ---------------------------------------------------------------------------
# (regex on the Hyne location name, place key, place title)
PLACE_RULES: list[tuple[str, str, str]] = [
    (r"^B-Garden", "balamb_garden", "Balamb Garden"),
    (r"^Balamb", "balamb", "Balamb Town"),
    (r"^Fire Cavern", "fire_cavern", "Fire Cavern"),
    (r"^Dollet", "dollet", "Dollet"),
    (r"^Timber Forest", "timber_forest", "Timber Forest"),
    (r"^Timber", "timber", "Timber"),
    (r"^(Galbadia Garden|G-Garden)", "galbadia_garden", "Galbadia Garden"),
    (r"^Deling", "deling", "Deling City"),
    (r"^(Galbadia D-District Prison|Desert$)", "d_district", "D-District Prison"),
    (r"^Galbadia Missile Base", "missile_base", "Missile Base"),
    (r"^Winhill", "winhill", "Winhill"),
    (r"^Tomb of the Unknown King", "tomb", "Tomb of the Unknown King"),
    (r"^FH- Great Salt Lake", "salt_lake", "Great Salt Lake"),
    (r"^(Fishermans Horizon|FH-)", "fh", "Fisherman's Horizon"),
    (r"^(Esthar- (City|Odine|Airstation|Presidential)|Presidential Palace|Dr\. Odine)",
     "esthar", "Esthar City"),
    (r"^Lunar Gate", "lunar_gate", "Lunar Gate"),
    (r"^(Esthar Sorceress Memorial|Sorceress Memorial)", "memorial", "Sorceress Memorial"),
    (r"^Tears' Point", "tears_point", "Tears' Point"),
    (r"^Lunatic Pandora Laboratory", "pandora_lab", "Lunatic Pandora Laboratory"),
    (r"^Lunatic Pandora", "lunatic_pandora", "Lunatic Pandora"),
    (r"^Centra- Excavation Site", "centra_exc", "Centra Excavation Site"),
    (r"^Edea's House", "edea", "Edea's House"),
    (r"^Centra Ruins", "centra_ruins", "Centra Ruins"),
    (r"^(Trabia Garden|T-Garden)", "trabia", "Trabia Garden"),
    (r"^Trabia Canyon", "trabia_canyon", "Trabia Canyon"),
    (r"^(Shumi Village|Mystery Dome)", "shumi", "Shumi Village"),
    (r"^White SeeD Ship", "white_seed", "White SeeD Ship"),
    (r"^Ragnarok", "ragnarok", "Ragnarok"),
    (r"^Deep Sea", "deep_sea", "Deep Sea Research Center"),
    (r"^(Lunar Base|Outer Space)", "lunar_base", "Lunar Base"),
    (r"^Chocobo Forest", "chocobo", "Chocobo Forest"),
    (r"^(Ultimecia Castle|Commencement Room|Queen$)", "ult_castle", "Ultimecia's Castle"),
    (r"^(Train|Car|Inside Ship)$", "vehicles", "Trains & Vehicles"),
    (r"^(Emergency|Spaceship) Landing Zone", "esthar", "Esthar City"),
]
# fields with no SETPLACE of their own: by name prefix
PREFIX_PLACE = {
    "bc": "balamb", "bd": "fire_cavern", "bg": "balamb_garden", "bv": "vehicles",
    "cd": "centra_exc", "cr": "centra_ruins", "cw": "chocobo", "dd": "deep_sea",
    "do": "dollet", "eb": "lunatic_pandora", "ec": "esthar", "ed": "pandora_lab",
    "ee": "tears_point", "ef": "memorial", "eh": "edea", "el": "salt_lake",
    "em": "esthar", "ep": "esthar", "es": "lunar_gate", "et": "salt_lake",
    "fe": "ult_castle", "ff": "ult_castle", "fh": "fh", "gf": "winhill",
    "gg": "galbadia_garden", "gl": "deling", "gm": "missile_base", "gn": "tomb",
    "gp": "d_district", "gw": "timber_forest", "rg": "ragnarok", "sd": "deep_sea",
    "se": "lunar_base", "ss": "lunar_base", "tg": "trabia", "ti": "timber",
    "tm": "shumi", "tv": "trabia_canyon",
}
PLACE_TITLES = {key: title for _rx, key, title in PLACE_RULES}


def place_of(field: str, place_name: str | None) -> str | None:
    if place_name:
        for rx, key, _title in PLACE_RULES:
            if re.match(rx, place_name):
                return key
    return PREFIX_PLACE.get(field[:2])


def canonical_field(name: str) -> str:
    """Collapse story-state variants onto one screen: bccent1a -> bccent_1,
    bghall1b -> bghall_1, ebroad6a -> ebroad6 (when that field exists)."""
    names = set(FIELD_NAMES)
    m = re.match(r"^(.*?)(\d)([a-z])$", name)
    if m:
        for cand in (f"{m[1]}_{m[2]}", f"{m[1]}{m[2]}"):
            if cand in names:
                return cand
    return name


def short_title(place_name: str | None, field: str) -> str:
    if not place_name:
        return field
    return place_name.split("- ", 1)[1] if "- " in place_name else place_name


def field_place_name(fields: "D.Fields", loaded: dict, names: list[str], f: str) -> str | None:
    """A field's save-preview location name; fields that never call SETPLACE
    (e.g. bggate_2, bgmon_4) borrow it from a sibling screen (bggate_1)."""
    def name_of(fd):
        return (names[fd.place_id] if fd.place_id is not None and fd.place_id < len(names)
                else None)
    fd = loaded.get(f)
    if fd is None:
        try:
            fd = loaded[f] = fields.load(f)
        except Exception:  # noqa: BLE001
            return None
    pn = name_of(fd)
    if pn:
        return pn
    for sib in FIELD_NAMES:
        if sib != f and sib.startswith(f[:5]) and sib in fields.available:
            try:
                sd = loaded.get(sib) or fields.load(sib)
            except Exception:  # noqa: BLE001
                continue
            loaded.setdefault(sib, sd)
            pn = name_of(sd)
            if pn:
                return pn
    return None


# ---------------------------------------------------------------------------
# Per-area views (tracker tabs; keys match ff8/areas.py AREAS): world-unit
# rect + render scale. Rendered straight from the mesh so they stay sharp.
AREA_VIEWS: dict[str, tuple[int, int, int, int, int]] = {
    "balamb":   (-12000, -54000, 66000, -8000, 32),
    "galbadia": (-131072, -62000, -6000, 46000, 48),
    "trabia":   (-52000, -98304, 92000, -42000, 48),
    "esthar":   (14000, -46000, 131072, 52000, 48),
    "centra":   (-131072, 12000, 112000, 98304, 64),
}


def build_world(tris, out_dir: Path) -> tuple[dict, dict]:
    idx, cluts = D.load_texl()
    img = WORLD.render(tris, idx, cluts, WORLD_SCALE)
    img.save(out_dir / "world.png", optimize=True)
    world = {"scale": WORLD_SCALE, "width": img.width, "height": img.height,
             "x0": D.WORLD_X0, "y0": D.WORLD_Y0,
             "note": "px = (x - x0) / scale, py = (y - y0) / scale; north up"}
    areas = {}
    for view, (x0, y0, x1, y1, scale) in AREA_VIEWS.items():
        a = WORLD.render(tris, idx, cluts, scale, (x0, y0, x1, y1))
        a.save(out_dir / f"area_{view}.png", optimize=True)
        areas[view] = {"x0": x0, "y0": y0, "x1": x1, "y1": y1, "scale": scale,
                       "width": a.width, "height": a.height,
                       "image": f"area_{view}.png"}
        print(f"  area {view}: {a.width}x{a.height}")
    return world, areas


def world_points(tris) -> dict:
    """World-space anchors: draw points, field exits, named regions."""
    wd = {str(p.slot): {"x": p.x, "y": p.y, "segment": p.segment}
          for p in D.world_draw_points(tris)}
    secs = D.wmsetus_sections()
    s9 = secs[8]
    wm = {}
    for i in range(len(s9) // 12):
        x, y, h, _u = struct.unpack_from("<iihH", s9, 12 * i)
        if (x, y) != (0, 0):
            wm[str(i)] = {"x": x, "y": y}
    names = hyne_location_names()
    s19 = secs[18]
    regions: dict[str, list[int]] = {}
    for seg in range(D.GRID_COLS * D.GRID_ROWS):
        if s19[seg]:
            regions.setdefault(names[s19[seg]], []).append(seg)
    keep, gridpos = WORLD.grid_positions(tris)
    t = tris[keep]
    gp = gridpos[keep]
    wx, wy = D.world_xy(t, gp)
    land = (t["f2"] & D.F2_WALKABLE) != 0
    centroids = {}
    for name, segs in regions.items():
        m = land & np.isin(gp, segs)
        if m.any():
            centroids[name] = {"x": int(wx[m].mean()), "y": int(wy[m].mean())}
    towns = {str(s): {"x": x, "y": y}
             for s, (x, y) in D.town_footprints(t, gp).items()}
    return {"world_draw": wd, "wm_fields": wm, "regions": regions,
            "region_centroids": centroids, "town_footprints": towns}


def build_places(attribution: dict, out_dir: Path) -> dict:
    """Render one floor-plan sheet per place from the screens its checks live on."""
    names = hyne_location_names()
    fields = D.Fields(FIELD_NAMES)
    # field -> locations that need an on-screen spot there
    wanted: dict[str, list[str]] = {}
    for loc, a in attribution.items():
        if a.get("kind") == "field" and a.get("fields"):
            f = canonical_field(a["fields"][0])
            if f in fields.available:
                wanted.setdefault(f, []).append(loc)
    for slot, fids in DRAW_POINT_FIELDS.items():
        f = canonical_field(FIELD_NAMES[fids[0]])
        if f in fields.available:
            wanted.setdefault(f, [])
    loaded: dict[str, D.FieldData] = {}
    by_place: dict[str, list[str]] = {}
    labels: dict[int, str] = {}
    for f in sorted(wanted):
        try:
            fd = fields.load(f)
        except Exception as e:  # noqa: BLE001 - a broken field just loses its sheet
            print(f"  ! {f}: {e!r}")
            continue
        loaded[f] = fd
        pname = field_place_name(fields, loaded, names, f)
        key = place_of(f, pname)
        if key is None:
            print(f"  ! {f}: no place")
            continue
        by_place.setdefault(key, []).append(f)
    # exit labels: every field's short place name (loaded lazily for neighbours)
    for fd in list(loaded.values()):
        for gw in fd.inf.gateways:
            if gw.field in labels or gw.field >= len(FIELD_NAMES):
                continue
            n = FIELD_NAMES[gw.field]
            labels[gw.field] = short_title(field_place_name(fields, loaded, names, n), n)
    out_dir.mkdir(parents=True, exist_ok=True)
    places = {}
    for key, flist in sorted(by_place.items()):
        screens, titles = [], {}
        for f in flist:
            fd = loaded[f]
            titles[f] = short_title(field_place_name(fields, loaded, names, f), f)
            screens.append(FM.render_screen(fd, FIELD_NAMES, labels))
        pr = FM.compose_place(key, PLACE_TITLES.get(key, key), screens, titles)
        pr.image.save(out_dir / f"{key}.png", optimize=True)
        places[key] = {
            "title": PLACE_TITLES.get(key, key),
            "image": f"places/{key}.png",
            "width": pr.image.width, "height": pr.image.height,
            "tile": [FM.TILE_W, FM.TILE_H],
            "screens": {f: {"title": titles[f], "origin": list(pr.screens[f]),
                            "centre": list(pr.centres[f]), "field_id": loaded[f].fid}
                        for f in flist},
            "draw_points": {str(s): list(xy) for s, xy in pr.draw_points.items()},
        }
        print(f"  {key}: {len(flist)} screens, {len(pr.draw_points)} draw points, "
              f"{pr.image.width}x{pr.image.height}")
    return places


def all_field_places() -> dict[str, str]:
    """field id -> place key for every field in the game (fields without a
    SETPLACE borrow a sibling's, then fall back to the name prefix). Drives
    the tracker's follow-the-player floor-plan tabs."""
    names = hyne_location_names()
    fields = D.Fields(FIELD_NAMES)
    pid: dict[str, int | None] = {}
    for f in FIELD_NAMES:
        if f in fields.available:
            try:
                pid[f] = fields.place_id(f)
            except Exception:  # noqa: BLE001
                pid[f] = None
    out = {}
    for fid, f in enumerate(FIELD_NAMES):
        if f not in pid:
            continue
        p = pid[f]
        if p is None:
            p = next((pid[s] for s in FIELD_NAMES
                      if s != f and s.startswith(f[:5]) and pid.get(s) is not None), None)
        pname = names[p] if p is not None and p < len(names) else None
        key = place_of(f, pname)
        if key:
            out[str(fid)] = key
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-world", action="store_true")
    ap.add_argument("--no-places", action="store_true")
    args = ap.parse_args(argv)
    GEO.mkdir(parents=True, exist_ok=True)
    geo = json.loads((GEO / "geo.json").read_text()) if (GEO / "geo.json").exists() else {}
    print("parsing wmx.obj ...")
    _groups, tris = D.load_wmx()
    if not args.no_world:
        print("rendering world ...")
        geo["world"], geo["areas"] = build_world(tris, GEO)
    geo.update(world_points(tris))
    if not args.no_places:
        attribution = json.loads(ATTRIBUTION.read_text()) if ATTRIBUTION.exists() else {}
        print(f"rendering places ({len(attribution)} attributed locations) ...")
        geo["places"] = build_places(attribution, GEO / "places")
    geo["canonical_fields"] = {n: canonical_field(n) for n in FIELD_NAMES
                               if canonical_field(n) != n}
    print("mapping every field to its place ...")
    geo["field_places"] = all_field_places()
    (GEO / "geo.json").write_text(json.dumps(geo, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {GEO / 'geo.json'}")


if __name__ == "__main__":
    main()
