"""Render the FF8 world map top-down from the wmx.obj walkmesh.

Every one of the ~517k triangles is drawn at its real world position, coloured
from its own texture page/CLUT (texl.obj) or, for water/road/rail triangles
that use the animated wmset atlases, from a fixed palette, then shaded by
height and slope. The result is our own rendering of the game's geometry (no
game bitmap is copied), with north up and the continents where the engine
puts them: Galbadia west, Trabia north, Balamb centre, Esthar east, Centra
south.

World -> pixel: px = (wx + 131072) / S, py = (wy + 98304) / S.
"""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw

from . import ff8data as D

# Fixed colours for triangles whose texture lives outside texl.obj, plus the
# per-class fallback palette (used to tint the sampled texture so terrain
# types stay distinguishable on a small tracker map).
PAL = {
    "sea": (24, 52, 112), "shallow": (44, 96, 164), "thin_water": (80, 140, 196),
    "beach_wave": (214, 198, 150), "lake_river": (62, 118, 186),
    "forest": (28, 88, 36), "grass": (96, 164, 72), "ground": (150, 148, 94),
    "desert": (222, 198, 132), "snow": (236, 238, 242), "esthar_road": (124, 142, 170),
    "plateau": (160, 132, 92), "foothill": (132, 120, 84), "rail": (84, 66, 58),
    "road": (176, 156, 124), "mountain": (112, 102, 96),
}
FOREST = (0, 1, 2, 3, 4, 5)
FOOTHILL = (15, 16, 17, 18, 23, 24, 25)


def terrain_class(g: np.ndarray) -> np.ndarray:
    cls = np.full(len(g), "ground", dtype="<U12")
    for name, mask in (
        ("sea", g == 34), ("shallow", g == 33), ("thin_water", g == 32),
        ("beach_wave", g == 10), ("lake_river", g == 31), ("forest", np.isin(g, FOREST)),
        ("grass", g == 6), ("ground", g == 7), ("desert", g == 8), ("snow", g == 9),
        ("esthar_road", g == 12), ("plateau", g == 14), ("foothill", np.isin(g, FOOTHILL)),
        ("rail", g == 27), ("road", g == 28), ("mountain", g == 29),
    ):
        cls[mask] = name
    return cls


def grid_positions(tris: np.ndarray, alts=D.LANDMARK_ALTS) -> tuple[np.ndarray, np.ndarray]:
    """(mask of triangles to draw, grid segment for each) with the chosen
    alternate segments drawn in place of their base segment."""
    use = {s: s for s in range(D.GRID_COLS * D.GRID_ROWS)}
    for a in alts:
        use[D.ALT_SEGMENTS[a]] = a
    draw_as = np.full(835, -1, np.int64)
    for pos, s in use.items():
        draw_as[s] = pos
    segs = tris["seg"].astype(np.int64)
    gridpos = draw_as[segs]
    return gridpos >= 0, gridpos


def render(tris: np.ndarray, texl_idx: np.ndarray, texl_cluts: np.ndarray,
           scale: int = 64, bbox: tuple[int, int, int, int] | None = None) -> Image.Image:
    """Top-down render at `scale` world units per pixel of the whole world,
    or of the world-unit rectangle `bbox` = (x0, y0, x1, y1)."""
    x0, y0, x1, y1 = bbox or (D.WORLD_X0, D.WORLD_Y0, D.WORLD_X0 + D.WORLD_W,
                              D.WORLD_Y0 + D.WORLD_H)
    W, H = round((x1 - x0) / scale), round((y1 - y0) / scale)
    keep, gridpos = grid_positions(tris)
    t, gridpos = tris[keep], gridpos[keep]
    wx, wy = D.world_xy(t, gridpos)
    if bbox:
        inside = ((wx.max(1) >= x0) & (wx.min(1) <= x1)
                  & (wy.max(1) >= y0) & (wy.min(1) <= y1))
        t, gridpos, wx, wy = t[inside], gridpos[inside], wx[inside], wy[inside]
    px = (wx - x0) / scale
    py = (wy - y0) / scale
    height = -t["y"].mean(1)

    g = t["ground"].astype(int)
    f1 = t["f1"].astype(int)
    cls = terrain_class(g)
    water = (f1 & 0x60) == D.F1_WATER_TEX
    road_tex = (f1 & D.F1_ROAD_TEX) != 0
    base = np.array([PAL[c] for c in cls], np.float32)

    # texture colour: sample the page/clut at the UV centroid and near each vertex
    tp = (t["texi"] >> 4).astype(int)
    cl = (t["texi"] & 15).astype(int)
    u = t["uv"][:, 0::2].astype(int)
    v = t["uv"][:, 1::2].astype(int)
    uc, vc = u.mean(1), v.mean(1)
    samples = []
    for k in range(3):
        us = ((u[:, k] * 2 + uc) / 3).astype(int).clip(0, 255)
        vs = ((v[:, k] * 2 + vc) / 3).astype(int).clip(0, 255)
        samples.append(texl_cluts[tp, cl, texl_idx[tp, vs, us]])
    samples.append(texl_cluts[tp, cl, texl_idx[tp, vc.astype(int).clip(0, 255),
                                                uc.astype(int).clip(0, 255)]])
    tex = np.mean(samples, 0).astype(np.float32)
    color = tex * 0.7 + base * 0.3
    color[water] = base[water]
    color[road_tex & (cls == "rail")] = PAL["rail"]
    color[road_tex & (cls != "rail")] = PAL["road"]

    ny = -t["ny"].mean(1) / 4096.0
    shade = (0.62 + 0.38 * ny.clip(0, 1)) * (0.82 + 0.18 * (height / 2300.0).clip(0, 1))
    shade[water] = 1.0
    rgb = (color * shade[:, None]).clip(0, 255).astype(np.uint8)

    img = Image.new("RGB", (W, H), PAL["sea"])
    d = ImageDraw.Draw(img)
    for i in np.argsort(height, kind="stable"):     # low first, peaks on top
        d.polygon([(px[i, 0], py[i, 0]), (px[i, 1], py[i, 1]), (px[i, 2], py[i, 2])],
                  fill=tuple(int(c) for c in rgb[i]))
    return img


def to_pixel(x: float, y: float, scale: int) -> tuple[float, float]:
    return (x - D.WORLD_X0) / scale, (y - D.WORLD_Y0) / scale
