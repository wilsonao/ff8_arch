"""Readers for the FF8 (Steam 2013) world and field data needed by the maps.

Formats were verified against the local game files on 2026-10-10 (every
triangle/vertex index in range, live-verified world coordinate convention,
field camera projection checked against rendered backgrounds). Sources:
Deling (myst6re/deling: WmxFile.cpp, WmsetFile.cpp, IdFile.h, CaFile.h,
InfFile.h, JsmFile.cpp), OpenVIII-monogame (Core/World, Core/Field) and the
qhimm wiki (FF8/WorldMap_wmx, FF8/WorldMap_wmsetxx, FF8/FileFormat_*).
"""

from __future__ import annotations

import importlib.util
import os
import struct
import sys
from dataclasses import dataclass, field as dc_field
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
GAME_DIR = os.environ.get(
    "FF8_DIR", r"F:\SteamLibrary\steamapps\common\FINAL FANTASY VIII")
LANG = os.path.join(GAME_DIR, "Data", "lang-en")


def _load_tool(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_dkt = _load_tool("dump_kernel_text")
Archive = _dkt.Archive


def open_archive(name: str) -> "Archive":
    return Archive.open(os.path.join(LANG, name))


# ---------------------------------------------------------------------------
# World map: wmx.obj
# ---------------------------------------------------------------------------
SEG_BYTES = 0x9000
GRID_COLS, GRID_ROWS = 32, 24          # 768 base segments, 8192 units each
SEG_UNITS = 8192
BLOCK_UNITS = 2048                     # 4x4 blocks per segment
WORLD_X0, WORLD_Y0 = -131072, -98304   # world extents: x in [-131072,131072), y in [-98304,98304)
WORLD_W, WORLD_H = 262144, 196608

_POLY = np.dtype([("v", "u1", 3), ("n", "u1", 3), ("uv", "u1", 6),
                  ("texi", "u1"), ("ground", "u1"), ("f1", "u1"), ("f2", "u1")])
_VERT = np.dtype([("x", "<i2"), ("y", "<i2"), ("z", "<i2"), ("w", "<i2")])
TRI_DTYPE = np.dtype([("seg", "i2"), ("blk", "i1"), ("idx", "u1"),
                      ("x", "i4", 3), ("y", "i4", 3), ("z", "i4", 3),
                      ("ny", "i4", 3), ("texi", "u1"), ("ground", "u1"),
                      ("f1", "u1"), ("f2", "u1"), ("uv", "u1", 6)])

# Story-state alternates: alt segment -> base grid segment it replaces.
ALT_SEGMENTS: dict[int, int] = {824: 149, 825: 150, 826: 267, 827: 274, 828: 275,
                                829: 327, 830: 214, 831: 215, 832: 246, 833: 247,
                                834: 361}
for _j in range(7):
    for _k in range(8):
        ALT_SEGMENTS[768 + _j * 8 + _k] = 373 + _j * 32 + _k   # Esthar cloaked
# Alternates that show the *present* state of a landmark (Gardens standing on
# their sites, Missile Base intact); the base segments already show Esthar
# uncloaked and the D-District Prison raised.
LANDMARK_ALTS = (826, 827, 828, 829)

# flags1 / flags2 bits
F1_WATER_TEX = 0x40
F1_ROAD_TEX = 0x20
F1_TOWN = 0x08          # enterable town footprint (the 0x800 bit of the +0xD field)
F2_WALKABLE = 0x80


def parse_wmx(wmx: bytes) -> tuple[np.ndarray, np.ndarray]:
    """(group id per segment, flat triangle table) for all 835 segments."""
    nseg = len(wmx) // SEG_BYTES
    groups = np.zeros(nseg, np.uint32)
    rows = []
    for s in range(nseg):
        base = s * SEG_BYTES
        groups[s] = struct.unpack_from("<I", wmx, base)[0]
        for b, o in enumerate(struct.unpack_from("<16I", wmx, base + 4)):
            p = base + o
            pc, vc, nc = wmx[p], wmx[p + 1], wmx[p + 2]
            polys = np.frombuffer(wmx, _POLY, pc, p + 4)
            verts = np.frombuffer(wmx, _VERT, vc, p + 4 + pc * 16)
            norms = np.frombuffer(wmx, _VERT, nc, p + 4 + pc * 16 + vc * 8)
            if pc and (polys["v"].max() >= vc or polys["n"].max() >= nc):
                raise ValueError(f"wmx segment {s} block {b}: index out of range")
            r = np.empty(pc, TRI_DTYPE)
            r["seg"] = s
            r["blk"] = b
            r["idx"] = np.arange(pc)
            r["x"] = verts["x"][polys["v"]]
            r["y"] = verts["y"][polys["v"]]
            r["z"] = verts["z"][polys["v"]]
            r["ny"] = norms["y"][polys["n"]]
            r["texi"] = polys["texi"]
            r["ground"] = polys["ground"]
            r["f1"] = polys["f1"]
            r["f2"] = polys["f2"]
            r["uv"] = polys["uv"]
            rows.append(r)
    return groups, np.concatenate(rows)


def load_wmx() -> tuple[np.ndarray, np.ndarray]:
    return parse_wmx(open_archive("world").read("wmx.obj"))


def world_xy(tris: np.ndarray, gridpos: np.ndarray | None = None):
    """World x/y (N,3) of each triangle's vertices.

    x = col*8192 - 131072 + bcol*2048 + vx ; y = row*8192 - 98304 + brow*2048 - vz
    (live-verified: reproduces the door tiles in tools/poc_story_keys.py to
    <1 unit). `gridpos` overrides the grid segment (for alternates)."""
    seg = (tris["seg"] if gridpos is None else gridpos).astype(np.int64)
    blk = tris["blk"].astype(np.int64)
    col, row = seg % GRID_COLS, seg // GRID_COLS
    bcol, brow = blk % 4, blk // 4
    wx = (col * SEG_UNITS + WORLD_X0 + bcol * BLOCK_UNITS)[:, None] + tris["x"]
    wy = (row * SEG_UNITS + WORLD_Y0 + brow * BLOCK_UNITS)[:, None] - tris["z"]
    return wx, wy


def segment_of(x: int, y: int) -> int:
    col = ((int(x) - WORLD_X0) % WORLD_W) >> 13
    row = ((int(y) - WORLD_Y0) % WORLD_H) >> 13
    return row * GRID_COLS + col


# ---------------------------------------------------------------------------
# World textures: texl.obj (20 TIMs, 8bpp, 16 CLUT rows of 256 colours)
# ---------------------------------------------------------------------------
TIM_STRIDE = 0x12800


def parse_texl(texl: bytes) -> tuple[np.ndarray, np.ndarray]:
    """(index images (20,256,256) u8, cluts (20,16,256,3) u8)."""
    idx_pages, clut_pages = [], []
    for i in range(20):
        off = i * TIM_STRIDE
        magic, flags = struct.unpack_from("<II", texl, off)
        assert magic == 0x10 and flags & 8, (i, hex(magic), flags)
        p = off + 8
        clen, _cx, _cy, cw, ch = struct.unpack_from("<IHHHH", texl, p)
        raw = np.frombuffer(texl, "<u2", cw * ch, p + 12)
        rgb = np.stack([(raw & 31) * 255 // 31, ((raw >> 5) & 31) * 255 // 31,
                        ((raw >> 10) & 31) * 255 // 31], 1).reshape(ch, cw, 3)
        clut = np.zeros((16, 256, 3), np.uint8)
        clut[:ch, :cw] = rgb
        p += clen
        ilen, _ix, _iy, iw, ih = struct.unpack_from("<IHHHH", texl, p)
        pix = np.frombuffer(texl, "u1", ilen - 12, p + 12).reshape(ih, iw * 2)
        idx_pages.append(pix[:256, :256])
        clut_pages.append(clut)
    return np.stack(idx_pages), np.stack(clut_pages)


def load_texl() -> tuple[np.ndarray, np.ndarray]:
    return parse_texl(open_archive("world").read("texl.obj"))


# ---------------------------------------------------------------------------
# World-map draw points: wmsetus.obj section 35 (0-based index 34)
# ---------------------------------------------------------------------------
def wmsetus_sections() -> list[bytes]:
    obj = open_archive("world").read("wmsetus.obj")
    offs = [struct.unpack_from("<I", obj, 4 * k)[0] for k in range(48)]
    return [obj[offs[i]:(offs[i + 1] if i < 47 else len(obj))] for i in range(48)]


@dataclass
class WorldDrawPoint:
    slot: int               # savemap draw slot (128..255)
    segment: int
    block: int
    tri: int
    x: int                  # world units (triangle centroid)
    y: int
    height: int


def world_draw_points(tris: np.ndarray) -> list[WorldDrawPoint]:
    """Every populated world draw point with its exact world position.

    Entry i (slot 128+i) = {u16 cell, u8 triangle, u8 pad} after a 0x2C-byte
    header; cell = block_row*128 + block_col on the 128x96 grid of 2048-unit
    blocks (the engine's `ff07` cell), triangle = polygon index inside that
    wmx block. 127 of 128 slots are populated (255 is empty)."""
    sec = wmsetus_sections()[34]
    wx, wy = world_xy(tris)
    out = []
    for i in range(128):
        cell, tri, _pad = struct.unpack_from("<HBB", sec, 0x2C + 4 * i)
        if cell == 0 and tri == 0:
            continue
        brow, bcol = divmod(cell, 128)
        seg = (brow // 4) * GRID_COLS + bcol // 4
        blk = (brow % 4) * 4 + bcol % 4
        sel = np.flatnonzero((tris["seg"] == seg) & (tris["blk"] == blk))
        k = sel[tri]
        out.append(WorldDrawPoint(
            128 + i, seg, blk, tri,
            int(round(wx[k].mean())), int(round(wy[k].mean())),
            int(round(tris["y"][k].mean()))))
    return out


def town_footprints(tris: np.ndarray, gridpos: np.ndarray) -> dict[int, tuple[int, int]]:
    """Grid segment -> world centroid of its enterable (town-flagged) triangles."""
    wx, wy = world_xy(tris, gridpos)
    town = (tris["f1"] & F1_TOWN) != 0
    out: dict[int, tuple[int, int]] = {}
    for seg in np.unique(gridpos[town]):
        m = town & (gridpos == seg)
        out[int(seg)] = (int(round(wx[m].mean())), int(round(wy[m].mean())))
    return out


# ---------------------------------------------------------------------------
# Fields: .id walkmesh, .ca camera, .inf gateways, .jsm/.sym scripts
# ---------------------------------------------------------------------------
SCREEN_W, SCREEN_H = 320, 224
NO_FIELD = 0x7FFF

# field-script opcodes (Deling JsmOpcode.h order == qhimm wiki numbers)
OP_PSHN_L = 0x07
OP_PSH_OTHER = {0x08, 0x0A, 0x0C, 0x0E, 0x10, 0x11, 0x12, 0x13}
KEYED = 0x1000000      # + instruction key, for non-CAL instructions
OP_SET3 = KEYED + 0x1E  # place entity at (x, y, z) on triangle <param>
OP_SETPLACE = 0x133
OP_DRAWPOINT = 0x137


def parse_id(b: bytes):
    """Walkmesh: list of 3 (x,y,z) vertices per triangle + per-edge access
    (-1 = wall, else the neighbouring triangle)."""
    n = struct.unpack_from("<I", b, 0)[0]
    tris, acc = [], []
    for i in range(n):
        v = struct.unpack_from("<12h", b, 4 + i * 24)
        tris.append(((v[0], v[1], v[2]), (v[4], v[5], v[6]), (v[8], v[9], v[10])))
        acc.append(struct.unpack_from("<3h", b, 4 + n * 24 + i * 6))
    return tris, acc


@dataclass
class Camera:
    axes: list[tuple[int, int, int]]   # 3 rows, /4096
    pos: tuple[int, int, int]
    zoom: int


def parse_ca(b: bytes) -> list[Camera]:
    cams = []
    n = len(b) // 40 + (1 if len(b) % 40 >= 38 else 0)
    for i in range(n):
        o = i * 40
        ax = struct.unpack_from("<9h", b, o)
        pos = struct.unpack_from("<3i", b, o + 20)
        zoom = struct.unpack_from("<H", b, o + 36)[0]
        cams.append(Camera([ax[0:3], ax[3:6], ax[6:9]], pos, zoom))
    return cams


@dataclass
class Gateway:
    line: tuple[tuple[int, int, int], tuple[int, int, int]]
    field: int
    dest: tuple[int, int, int]


@dataclass
class Inf:
    name: str
    control: int
    cam_range: tuple[int, int, int, int]      # top, bottom, right, left (screen-relative)
    gateways: list[Gateway]
    doors: list[tuple[tuple[int, int, int], tuple[int, int, int]]]


def parse_inf(b: bytes) -> Inf:
    gws, doors = [], []
    if len(b) >= 484:
        for g in range(12):
            o = 100 + 32 * g
            v = struct.unpack_from("<9h", b, o)
            fid = struct.unpack_from("<H", b, o + 18)[0]
            if fid != NO_FIELD:
                gws.append(Gateway((v[0:3], v[3:6]), fid, v[6:9]))
    if len(b) >= 676:
        for t in range(12):
            o = 484 + 16 * t
            v = struct.unpack_from("<6h", b, o)
            if b[o + 12] != 0xFF:
                doors.append((v[0:3], v[3:6]))
    cam_range = struct.unpack_from("<4h", b, 20) if len(b) >= 28 else (0, 0, 0, 0)
    return Inf(b[:9].split(b"\0")[0].decode("latin-1"), b[9] if len(b) > 9 else 0,
               cam_range, gws, doors)


@dataclass
class Entity:
    name: str
    scripts: list[tuple[str, tuple[int, ...]]] = dc_field(default_factory=list)


def parse_jsm(jsm: bytes, sym: bytes | None) -> list[Entity]:
    """Entities with their scripts as raw u32 words (names from .sym when present)."""
    nd, nl, nb, no, off_scripts, off_data = struct.unpack_from("<4B2H", jsm, 0)
    ngroups = (off_scripts - 8) // 2
    nscripts = (off_data - off_scripts) // 2
    if ngroups != nd + nl + nb + no:
        raise ValueError("jsm header mismatch")
    groups = []
    for i in range(ngroups):
        g = struct.unpack_from("<H", jsm, 8 + 2 * i)[0]
        typ = "line" if i < nl else "door" if i < nl + nd else "bg" if i < nl + nd + nb else "other"
        groups.append([g >> 7, (g & 0x7F) + 1, typ])
    positions = []
    for i in range(nscripts):
        p = struct.unpack_from("<H", jsm, off_scripts + 2 * i)[0]
        if i and p == 0:
            break
        positions.append(p & 0x7FFF)
    positions.append((len(jsm) - off_data) // 4)
    ents = [Entity(f"{typ}{i}") for i, (_a, _n, typ) in enumerate(groups)]
    for ent, (abs_m, nm, _typ) in zip(ents, groups):
        for m in range(nm):
            a = abs_m + m
            if a + 1 >= len(positions):
                break
            start, end = positions[a], positions[a + 1]
            ent.scripts.append((f"m{m}", struct.unpack_from(f"<{end - start}I", jsm,
                                                            off_data + start * 4)))
    if sym:
        lines = [ln.strip() for ln in sym.decode("latin-1").split("\n") if ln.strip()]
        nent = nl + nb + no
        by_abs = sorted(range(len(groups)), key=lambda i: groups[i][0])
        gi, mi = -1, 0
        for line in lines[nent:]:
            if "::" not in line:
                gi += 1
                mi = 0
                if gi < len(by_abs):
                    ents[by_abs[gi]].name = line
            else:
                mi += 1
                if gi < len(by_abs) and mi < len(ents[by_abs[gi]].scripts):
                    e = ents[by_abs[gi]]
                    e.scripts[mi] = (line.split("::", 1)[1], e.scripts[mi][1])
    return ents


def literal_calls(words: tuple[int, ...]):
    """Yield (instruction, literal args pushed before it) for every
    instruction in a script. A word's high byte is the instruction: 0 = CAL
    (the 24-bit param is the opcode number, e.g. 0x137 DRAWPOINT), 7 = PSHN_L
    (push a 24-bit signed literal), other pushes/pops, and keyed instructions
    such as SET3 (0x1E, param = walkmesh triangle, args x/y/z). Keyed
    instructions are yielded as KEYED + key so they never collide with CAL
    opcodes."""
    stack: list[int | None] = []
    for w in words:
        key = w >> 24
        if key == 0:
            yield w & 0xFFFFFF, tuple(stack[-4:])
            stack = []
        elif key == OP_PSHN_L:
            v = w & 0xFFFFFF
            stack.append(v - 0x1000000 if v & 0x800000 else v)
        elif key in OP_PSH_OTHER:
            stack.append(None)
        else:
            yield KEYED + key, tuple(stack[-4:])
            stack = []


@dataclass
class FieldData:
    name: str
    fid: int
    tris: list
    acc: list
    cameras: list[Camera]
    inf: Inf
    entities: list[Entity]
    draw_points: dict[int, tuple[int, int, int]]   # draw slot -> walkmesh position
    place_id: int | None                           # SETPLACE id (Hyne location name)


class Fields:
    """Lazy access to every field archive in field.fs."""

    def __init__(self, field_names: tuple[str, ...]):
        self.archive = open_archive("field")
        self.names = field_names
        self.id_of = {n: i for i, n in enumerate(field_names)}
        self.available = set(self.archive.field_names())

    def place_id(self, name: str) -> int | None:
        """The field's SETPLACE id (save-preview location name) from its
        script alone — cheap enough to run over every field."""
        sub = self.archive.field(name)
        try:
            ents = parse_jsm(sub.read(name + ".jsm"), None)
        except (KeyError, ValueError):
            return None
        for e in ents:
            for _sname, words in e.scripts:
                for op, args in literal_calls(words):
                    if op == OP_SETPLACE and args and args[-1] is not None:
                        return args[-1]
        return None

    def load(self, name: str) -> FieldData:
        sub = self.archive.field(name)
        tris, acc = parse_id(sub.read(name + ".id"))
        cams = parse_ca(sub.read(name + ".ca"))
        inf = parse_inf(sub.read(name + ".inf"))
        try:
            sym = sub.read(name + ".sym")
        except KeyError:
            sym = None
        ents = parse_jsm(sub.read(name + ".jsm"), sym)
        draw_points: dict[int, tuple[int, int, int]] = {}
        place = None
        for e in ents:
            slots: list[int] = []
            pos = None
            for _sname, words in e.scripts:
                for op, args in literal_calls(words):
                    if op == OP_DRAWPOINT and args and args[-1] is not None:
                        slots.append(args[-1] - 1)     # one entity may serve several slots
                    elif op == OP_SET3 and len(args) >= 3 and None not in args[-3:]:
                        pos = pos or tuple(args[-3:])
                    elif op == OP_SETPLACE and args and args[-1] is not None:
                        place = args[-1]
            if pos is not None:
                for slot in slots:
                    draw_points[slot] = pos
        return FieldData(name, self.id_of.get(name, -1), tris, acc, cams, inf, ents,
                         draw_points, place)


def project(cam: Camera, v: tuple[int, int, int]) -> tuple[float, float, float] | None:
    """Walkmesh point -> (sx, sy, depth) on the 320x224 screen (origin top-left).
    camera space c = R*v + pos with R = axes/4096; sx = 160 + zoom*cx/cz."""
    ax = cam.axes
    c = [sum(ax[r][k] * v[k] for k in range(3)) / 4096.0 + cam.pos[r] for r in range(3)]
    if c[2] <= 1e-6:
        return None
    return (SCREEN_W / 2 + cam.zoom * c[0] / c[2], SCREEN_H / 2 + cam.zoom * c[1] / c[2], c[2])
