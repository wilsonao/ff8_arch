"""Per-screen floor plans for towns and dungeons.

A field (one pre-rendered screen) has a 3D walkmesh and a camera. We draw the
walkmesh from directly overhead, turned so the in-game camera looks up the
page (left/right match the screen the player sees), shaded by height —
walkable floor, walls, exits labelled with where they lead, door triggers and
draw-point sparkles — without any game bitmap, and compose one image per
place (town/dungeon) from its check-bearing screens so the tracker can pin
every check at its exact spot.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFont

from . import ff8data as D

# Rendering geometry: every screen gets a fixed-size tile; the 320x224 screen
# plus whatever the walkmesh scrolls to is fitted into it (at most 2x).
CELL_SCALE = 1.5
TILE_W, TILE_H = int(400 * CELL_SCALE), int(280 * CELL_SCALE)
SHEET_ASPECT = 1.4          # target width/height of a place sheet (tracker widget shape)
TITLE_H = 26
GAP = 12
PAD = 14
HEADER = 40

BG = (16, 20, 31)
TILE_BG = (24, 30, 46)
SCREEN_BG = (34, 42, 62)
FLOOR = (78, 96, 128)
FLOOR_EDGE = (110, 130, 166)
WALL = (190, 205, 235)
EXIT = (255, 96, 80)
DOOR = (120, 220, 120)
DRAW = (255, 221, 0)
TEXT = (232, 236, 245)
DIM = (150, 160, 180)


def _font(size: int):
    for name in ("segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


@dataclass
class ScreenRender:
    name: str
    image: Image.Image                                # TILE_W x TILE_H
    draw_points: dict[int, tuple[int, int]]           # slot -> pixel in the tile
    exits: list[tuple[int, tuple[int, int]]]          # (dest field id, pixel)
    centre: tuple[int, int]                           # a safe pin spot (floor centroid)


class _Fit:
    """Map overhead (ground-plane) coordinates into a tile, keeping aspect."""

    def __init__(self, bbox: tuple[float, float, float, float]):
        x0, y0, x1, y1 = bbox
        pad = 10
        w = max(x1 - x0, 1.0)
        h = max(y1 - y0, 1.0)
        self.scale = min((TILE_W - 2 * pad) / w, (TILE_H - 2 * pad) / h)
        self.ox = (TILE_W - w * self.scale) / 2 - x0 * self.scale
        self.oy = (TILE_H - h * self.scale) / 2 - y0 * self.scale

    def __call__(self, p) -> tuple[float, float]:
        return (self.ox + p[0] * self.scale, self.oy + p[1] * self.scale)


def overhead(cam: D.Camera):
    """A walkmesh point -> (u, v, height) seen from directly above.

    The ground plane is the walkmesh x/y (z is height). It is turned so the
    in-game camera looks up the page: camera right = page right, camera
    forward = page up, so left/right match the screen the player sees."""
    r = (cam.axes[0][0], cam.axes[0][1])
    f = (cam.axes[2][0], cam.axes[2][1])
    rl = math.hypot(*r)
    if rl < 1e-6:                       # degenerate: fall back to raw axes
        r, rl = (1.0, 0.0), 1.0
    r = (r[0] / rl, r[1] / rl)
    fp = (-r[1], r[0])                  # perpendicular to right
    if fp[0] * f[0] + fp[1] * f[1] < 0:
        fp = (r[1], -r[0])

    def fn(v):
        return (v[0] * r[0] + v[1] * r[1], -(v[0] * fp[0] + v[1] * fp[1]), v[2])
    return fn


def render_screen(fd: D.FieldData, field_names: tuple[str, ...],
                  labels: dict[int, str] | None = None) -> ScreenRender:
    cam = fd.cameras[0]
    top = overhead(cam)
    proj = [[top(v) for v in t] for t in fd.tris]
    pts_all = [q for p in proj for q in p]
    extra = [top(v) for gw in fd.inf.gateways for v in gw.line]
    extra += [top(pos) for pos in fd.draw_points.values()]
    allp = pts_all + extra
    if not allp:
        allp = [(0.0, 0.0, 0.0)]
    bbox = (min(q[0] for q in allp), min(q[1] for q in allp),
            max(q[0] for q in allp), max(q[1] for q in allp))
    fit = _Fit(bbox)
    img = Image.new("RGB", (TILE_W, TILE_H), TILE_BG)
    d = ImageDraw.Draw(img)
    # floor, shaded by height (lighter = higher) so stairs and ledges read
    heights = [q[2] for q in pts_all] or [0.0]
    hmin, hmax = min(heights), max(heights)
    span = max(hmax - hmin, 1.0)
    order = sorted(range(len(fd.tris)), key=lambda i: sum(q[2] for q in proj[i]))
    xs, ys = [], []
    for i in order:
        p = proj[i]
        t = (sum(q[2] for q in p) / 3 - hmin) / span if span > 1.0 else 0.0
        shade = tuple(int(c * (0.85 + 0.45 * t)) for c in FLOOR)
        pts = [fit(q) for q in p]
        d.polygon(pts, fill=shade)
        for q in pts:
            xs.append(q[0])
            ys.append(q[1])
    # walls (edges without a neighbouring triangle)
    for i in order:
        p = proj[i]
        for e in range(3):
            if fd.acc[i][e] == -1:
                d.line([fit(p[e]), fit(p[(e + 1) % 3])], fill=WALL, width=2)
    for a, b in fd.inf.doors:
        d.line([fit(top(a)), fit(top(b))], fill=DOOR, width=3)
    font = _font(13)
    exits = []
    for gw in fd.inf.gateways:
        pa, pb = top(gw.line[0]), top(gw.line[1])
        d.line([fit(pa), fit(pb)], fill=EXIT, width=4)
        px, py = fit(((pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2))
        label = (labels or {}).get(gw.field) or (
            field_names[gw.field] if gw.field < len(field_names) else str(gw.field))
        d.text((px + 5, py - 8), label, font=font, fill=EXIT,
               stroke_width=2, stroke_fill=TILE_BG)
        exits.append((gw.field, (int(px), int(py))))
    dps = {}
    for slot, pos in fd.draw_points.items():
        px, py = fit(top(pos))
        r = 7
        d.ellipse([px - r, py - r, px + r, py + r], outline=DRAW, width=3)
        d.ellipse([px - 2, py - 2, px + 2, py + 2], fill=DRAW)
        dps[slot] = (int(px), int(py))
    # view hint: the player's camera looks up the page
    d.polygon([(TILE_W - 22, TILE_H - 10), (TILE_W - 14, TILE_H - 24),
               (TILE_W - 6, TILE_H - 10)], fill=DIM)
    d.text((TILE_W - 62, TILE_H - 24), "view", font=_font(11), fill=DIM)
    # pin spot for checks without an exact position: centroid of the floor
    inside = [(x, y) for x, y in zip(xs, ys) if 0 <= x < TILE_W and 0 <= y < TILE_H]
    if inside:
        cx = int(sum(x for x, _ in inside) / len(inside))
        cy = int(sum(y for _, y in inside) / len(inside))
    else:
        cx, cy = TILE_W // 2, TILE_H // 2
    return ScreenRender(fd.name, img, dps, exits, (cx, cy))


@dataclass
class PlaceRender:
    key: str
    title: str
    image: Image.Image
    screens: dict[str, tuple[int, int]]               # field name -> tile origin
    draw_points: dict[int, tuple[int, int]]           # slot -> pixel on the place image
    centres: dict[str, tuple[int, int]]               # field name -> pin spot
    panel: tuple[int, int, int, int] | None           # free-pin panel box (x0,y0,x1,y1)


def compose_place(key: str, title: str, screens: list[ScreenRender],
                  screen_titles: dict[str, str], panel_slots: int = 0,
                  cols: int | None = None) -> PlaceRender:
    """Lay the screens out in a grid under a title; optionally reserve a
    labelled panel at the bottom for checks that have no on-screen spot."""
    n = len(screens)
    cols = cols or max(1, min(n, math.ceil(math.sqrt(
        SHEET_ASPECT * n * (TILE_H + TITLE_H + GAP) / (TILE_W + GAP)))))
    rows = math.ceil(n / cols) if n else 0
    panel_h = 0
    panel_cols = 0
    if panel_slots:
        panel_cols = cols * 4
        panel_rows = math.ceil(panel_slots / panel_cols)
        panel_h = 30 + panel_rows * 44 + PAD
    W = PAD * 2 + cols * TILE_W + (cols - 1) * GAP
    H = HEADER + rows * (TILE_H + TITLE_H + GAP) + panel_h + PAD
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.text((PAD, 8), title, font=_font(24), fill=TEXT)
    origins, dps, centres = {}, {}, {}
    tfont = _font(16)
    for i, sr in enumerate(screens):
        r, c = divmod(i, cols)
        x0 = PAD + c * (TILE_W + GAP)
        y0 = HEADER + r * (TILE_H + TITLE_H + GAP)
        d.text((x0 + 4, y0 + 3), screen_titles.get(sr.name, sr.name), font=tfont, fill=TEXT)
        d.text((x0 + 4, y0 + 3), " " * 0, font=tfont, fill=TEXT)
        name_w = d.textlength(screen_titles.get(sr.name, sr.name), font=tfont)
        d.text((x0 + 10 + name_w, y0 + 6), sr.name, font=_font(12), fill=DIM)
        img.paste(sr.image, (x0, y0 + TITLE_H))
        origins[sr.name] = (x0, y0 + TITLE_H)
        for slot, (px, py) in sr.draw_points.items():
            dps[slot] = (x0 + px, y0 + TITLE_H + py)
        centres[sr.name] = (x0 + sr.centre[0], y0 + TITLE_H + sr.centre[1])
    panel = None
    if panel_slots:
        py0 = HEADER + rows * (TILE_H + TITLE_H + GAP)
        panel = (PAD, py0, W - PAD, py0 + panel_h - PAD)
        d.rounded_rectangle(panel, radius=8, fill=(22, 27, 40), outline=(60, 72, 100))
        d.text((PAD + 10, py0 + 6), "Other checks here", font=tfont, fill=DIM)
    return PlaceRender(key, title, img, origins, dps, centres, panel)


def panel_slot_coords(panel: tuple[int, int, int, int], n: int, cols: int):
    x0, y0, x1, _y1 = panel
    pitch = 44
    out = []
    for j in range(n):
        r, c = divmod(j, cols)
        out.append((x0 + 24 + c * pitch, y0 + 30 + 20 + r * pitch))
    return out
