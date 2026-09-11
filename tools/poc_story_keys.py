"""PROOF OF CONCEPT: lock / unlock world-map town entrances by editing the
resident entrance script (Story Keys, Phase 0). No game files modified.

Background (static RE of FF8_EN.exe + wmsetus.obj, 2026-09-11):

Walking into a town from the world map is decided by DATA, per tick:

  1. The walkmesh triangle under the player carries flag 0x800 (byte +0xE
     bit 3 of the 16-byte triangle record). Every town's footprint is flagged.
  2. If so, sub_545EA0 runs the ENTRANCE SCRIPT = wmsetus.obj section 8,
     resident at module+0x1A9DC3C+0xB70 (38 entries). An entry is

        ff01                       BEGIN
        ff06 <segment>             player's world-map segment == <segment>
        [ff02 <moment>]            GAME_MOMENT >= <moment>
        [ff03 <moment>]            GAME_MOMENT <  <moment>
        ff04                       THEN
        ff0a ff09 <avatar> [pos..] ff0b  ff08 <wm field>  ff05   (branches)
        ...  ff16                  end of entry

     (segment = row*32 + col of the 32x24 grid, 8192 units per segment,
     col = ((x + 0x60000) mod 0x40000) >> 13, row = ((y + 0x48000) mod
     0x30000) >> 13 in WORLD_POS units; ff0f/ff11 = local x <=/>= arg,
     ff10/ff12 = local y <=/>= arg; ff09 0x80 = on foot, 0x84 = chocobo,
     0x31 = Ragnarok, 0x32 = car, 0x30 = Garden.)
  3. The first matching entry's `ff08 <wm field>` (0..71) goes to
     sub_544630, which posts {1, avatar, wm_field, 0xFF} at module+0x1C36B4C;
     the field module maps wm field N through a 72 x 24-byte table
     ([0xb6d068] - 0x6c0: x, y, z, real field id, direction) into FIELD_ID.

So a town's door is one u16 in a resident data buffer:

  LOCK   = write 0xFFFF over the entry's segment argument (no segment is
           ever 0xFFFF, so the entry never matches; the player walks over
           the town footprint and nothing happens).
  UNLOCK = write 0 over the entry's `ff02 <moment>` argument (the story
           threshold disappears; the entrance exists at any moment).
  RESTORE = write the pristine bytes back (read from world.fs).

Nothing about the story moment changes, so none of the moment-faking
failures apply. Whether the buffer is re-read from disk on every world-map
load is what the `status` command's "live == file" line answers after a
field round trip.

Usage (game running, standing on the world map; AP client NOT connected):
    python tools/poc_story_keys.py status          # state + which entries are edited
    python tools/poc_story_keys.py entries         # decode the live entrance script
    python tools/poc_story_keys.py lock 11         # Balamb town: no entrance
    python tools/poc_story_keys.py unlock 8        # Deling City: no moment gate
    python tools/poc_story_keys.py restore [N|all] # pristine bytes back
    python tools/poc_story_keys.py warp e11        # teleport onto entry 11's door
                                                   # tile (also sN = segment N's
                                                   # door, a ff8/warp.py landmark
                                                   # name, or x y z)
    python tools/poc_story_keys.py watch           # poll module/field/segment
    python tools/poc_story_keys.py poke 11         # lock, warp onto the door,
                                                   # expect no entry; restore,
                                                   # expect the field to load
"""
import importlib.util
import os
import struct
import sys
import time

_FF8_DIR = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "ff8")


def _load(mod: str, fname: str):
    spec = importlib.util.spec_from_file_location(mod, os.path.join(_FF8_DIR, fname))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


memory = _load("ff8_memory", "memory.py")
warp = _load("ff8_warp", "warp.py")
FIELD_NAMES = _load("ff8_fields", "fields.py").FIELD_NAMES

GAME_DIR = os.environ.get(
    "FF8_GAME_DIR", r"F:\SteamLibrary\steamapps\common\FINAL FANTASY VIII")

# module-relative (memory.FF8Interface adds the base)
WMSET_BUF = 0x1A9DC3C            # wmsetus.obj decompressed whole, fixed address
SEC8_OFF = 0xB70                 # section 8 = entrance script
SEC8_LEN = 0xA5C
WM_CUR_TRI_PTR = 0x1C409FC       # absolute pointer to the triangle under the player
WM_EXIT_REQ = 0x1C36B4C          # {active, avatar, wm_field, 0xFF} posted on entry
WM_JUMP_TABLE_PTR = 0x76D068     # [ptr] - 0x6c0 = 72 x 24-byte wm-field table

OP = {0xff01: "BEGIN", 0xff02: "MOMENT>=", 0xff03: "MOMENT<", 0xff04: "THEN",
      0xff05: "END", 0xff06: "SEG==", 0xff07: "CELL==", 0xff08: "FIELD",
      0xff09: "AVATAR==", 0xff0a: "IF", 0xff0b: "DO", 0xff0c: "ELSE",
      0xff0e: "JUMP", 0xff0f: "X<=", 0xff10: "Y<=", 0xff11: "X>=", 0xff12: "Y>=",
      0xff16: "EOS"}
AVATAR = {0x80: "foot", 0x84: "chocobo", 0x30: "garden", 0x31: "ragnarok",
          0x32: "car"}

# Human names for the wm entry fields this script hands out (from the live
# 72-entry table + field name prefixes). Extend as Phase 0 confirms them.
WM_FIELD_LABEL = {
    0: "Balamb Garden gate", 1: "Balamb town", 2: "Fire Cavern", 3: "Dollet",
    4: "Timber", 5: "Timber forest road", 6: "Galbadia Garden (exam era)",
    7: "Galbadia Garden", 8: "Deling City", 9: "Tomb of the Unknown King",
    10: "D-District Prison", 11: "Missile Base", 12: "FH (Garden docks)",
    13: "FH (Ragnarok/car)", 14: "Winhill village", 15: "Winhill outskirts",
    16: "Centra Ruins", 18: "Edea's House", 19: "Trabia Garden",
    20: "Shumi Village", 21: "sdisle1 (car)", 22: "tvglen1", 23: "tvglen5",
    24: "etsta1", 25: "elview2", 26: "Esthar City", 27: "ecpview1",
    28: "edview1b", 29: "Great Salt Lake?", 30: "efview1", 31: "eeview1",
    33: "Chocobo Forest 1", 34: "Chocobo Forest 2", 35: "Chocobo Forest 3",
    36: "Chocobo Forest 4", 37: "Chocobo Forest 5", 38: "Chocobo Forest 7",
    39: "Chocobo Forest 6", 46: "etsta2", 47: "esview2", 48: "eeview2",
    49: "eeview3", 57: "edview2", 68: "ecpview2", 69: "efview2",
}

# One door tile per entrance segment: the flagged wmx.obj triangle nearest the
# centroid of that segment's flagged triangles, in WORLD_POS units (world x =
# col*8192 - 131072 + bcol*2048 + vx, world y = row*8192 - 98304 + brow*2048
# - vz, height = vy; convention verified live 2026-09-11: warping onto
# (12390, -26709) entered Balamb town at once). Segments without an entry in
# the script (205, 214, 215, 246, 247, 300, 329) are flagged but scripted
# elsewhere (section 12 / vehicles).
DOORS = {
    49: (12372, -83945, -1023), 81: (10939, -80692, -1269),
    145: (11438, -64606, -956), 149: (48730, -59339, -1111),
    150: (49663, -60245, -800), 205: (-20441, -43012, -575),
    214: (56517, -44223, -848), 215: (59767, -42390, -575),
    219: (97792, -48732, -1561), 234: (-42035, -36813, -413),
    238: (-14338, -39085, -130), 246: (56727, -39805, -764),
    247: (59615, -40020, -805), 264: (-61405, -30760, -932),
    267: (-38914, -24766, -713), 268: (-31893, -25912, -1079),
    273: (12300, -26453, -443), 275: (30240, -29392, -691),
    279: (59557, -31457, -909), 300: (-28306, -23609, -804),
    329: (-51478, -12290, -545), 361: (-55487, -6245, -231),
    365: (-22158, -5632, -828), 370: (20278, -2320, -91),
    373: (48134, -2208, -462), 378: (83844, -4147, -553),
    393: (-51165, 6287, -385), 406: (54739, 5441, -1033),
    407: (57929, 6808, -400), 438: (55447, 11415, -400),
    439: (59244, 11528, -400), 441: (77829, 12233, -306),
    443: (95894, 10225, -415), 466: (17849, 22654, -938),
    506: (85967, 26575, -392), 592: (6177, 55196, -886),
    652: (-29644, 70234, -247), 653: (-21063, 69758, -938),
    693: (43961, 75902, -698), 705: (-118656, 85889, -368),
}


# --- pristine bytes from world.fs ------------------------------------------
def _lzs(data: bytes) -> bytes:
    out = bytearray()
    ring = bytearray(4096)
    rpos = 0xFEE
    i = 0
    n = len(data)
    while i < n:
        flags = data[i]
        i += 1
        for bit in range(8):
            if i >= n:
                break
            if flags & (1 << bit):
                b = data[i]
                i += 1
                out.append(b)
                ring[rpos] = b
                rpos = (rpos + 1) & 0xFFF
            else:
                if i + 1 >= n:
                    break
                b1, b2 = data[i], data[i + 1]
                i += 2
                off = b1 | ((b2 & 0xF0) << 4)
                for k in range((b2 & 0x0F) + 3):
                    b = ring[(off + k) & 0xFFF]
                    out.append(b)
                    ring[rpos] = b
                    rpos = (rpos + 1) & 0xFFF
    return bytes(out)


def pristine_wmsetus() -> bytes:
    lang = os.path.join(GAME_DIR, "Data", "lang-en")
    with open(os.path.join(lang, "world.fl")) as f:
        names = [ln.strip() for ln in f if ln.strip()]
    fi = open(os.path.join(lang, "world.fi"), "rb").read()
    fs = open(os.path.join(lang, "world.fs"), "rb").read()
    for k, path in enumerate(names):
        if path.lower().endswith("wmsetus.obj"):
            size, off, comp = struct.unpack_from("<III", fi, k * 12)
            if comp == 1:
                csize = struct.unpack_from("<I", fs, off)[0]
                return _lzs(fs[off + 4: off + 4 + csize])
            return fs[off: off + size]
    raise SystemExit("wmsetus.obj not in world.fl")


PRISTINE_SEC8 = pristine_wmsetus()[SEC8_OFF: SEC8_OFF + SEC8_LEN]


# --- decoding ----------------------------------------------------------------
def entry_offsets(sec8: bytes) -> list[int]:
    offs = []
    k = 0
    while True:
        v = struct.unpack_from("<I", sec8, 4 * k)[0]
        if v == 0 or v >= len(sec8):
            return offs
        offs.append(v)
        k += 1


def decode_entry(sec8: bytes, offs: list[int], i: int) -> list[tuple[int, int, int]]:
    """[(offset_in_sec8, opcode, arg)] for entry i."""
    end = offs[i + 1] if i + 1 < len(offs) else len(sec8)
    out = []
    p = offs[i]
    while p + 4 <= end:
        op, arg = struct.unpack_from("<HH", sec8, p)
        if op == 0:
            break
        out.append((p, op, arg))
        p += 4
    return out


def entry_summary(toks) -> str:
    parts = []
    for _, op, arg in toks:
        if op == 0xff06:
            parts.append(f"SEG=={arg}(r{arg // 32},c{arg % 32})" if arg != 0xFFFF
                         else "SEG==0xFFFF[LOCKED]")
        elif op == 0xff08:
            parts.append(f"FIELD:wm{arg:02d}={WM_FIELD_LABEL.get(arg, '?')}")
        elif op == 0xff09:
            parts.append(f"AVATAR=={AVATAR.get(arg, hex(arg))}")
        elif op in (0xff02, 0xff03):
            parts.append(f"{OP[op]}{arg}")
        elif arg:
            parts.append(f"{OP.get(op, f'{op:04x}')}:{arg:#x}")
        else:
            parts.append(OP.get(op, f"{op:04x}"))
    return " ".join(parts)


def segment_of(x: int, y: int) -> int:
    col = ((x + 0x60000) % 0x40000) >> 13
    row = ((y + 0x48000) % 0x30000) >> 13
    return row * 32 + col


# --- live access ---------------------------------------------------------------
def attach() -> memory.FF8Interface:
    ff8 = memory.FF8Interface()
    if not ff8.attach():
        sys.exit("FF8_EN.exe not running (or attach blocked): "
                 + str(ff8.last_attach_error))
    return ff8


def read_sec8(ff8) -> bytes:
    return ff8.read_bytes(WMSET_BUF + SEC8_OFF, SEC8_LEN)


def write_sec8_u16(ff8, off_in_sec8: int, value: int) -> None:
    ff8.write_u16(WMSET_BUF + SEC8_OFF + off_in_sec8, value)


def live_state(ff8) -> dict:
    x, y, z = ff8.world_pos()
    tri = ff8.read_u32(WM_CUR_TRI_PTR)
    flag = None
    if tri:
        try:
            flag = bool(ff8.read_abs(tri, 16)[0xE] & 0x08)
        except Exception:
            flag = None
    return {
        "module": ff8.read_u16(memory.MODULE_DISPATCH),
        "field": ff8.field_id(),
        "moment": ff8.game_moment(),
        "pos": (x, y, z),
        "segment": segment_of(x, y),
        "avatar": ff8.read_u8(memory.WM_AVATAR_TYPE),
        "door_tile": flag,
        "exit_req": ff8.read_bytes(WM_EXIT_REQ, 4).hex(),
    }


def fmt_state(s: dict) -> str:
    seg = s["segment"]
    return (f"module={s['module']} field={s['field']}({FIELD_NAMES[s['field']] if s['field'] < len(FIELD_NAMES) else '?'}) "
            f"moment={s['moment']} pos={s['pos']} seg={seg}(r{seg // 32},c{seg % 32}) "
            f"avatar={s['avatar']:#x} door_tile={s['door_tile']} exit_req={s['exit_req']}")


def diff_entries(live: bytes) -> list[int]:
    offs = entry_offsets(PRISTINE_SEC8)
    changed = []
    for i in range(len(offs)):
        end = offs[i + 1] if i + 1 < len(offs) else len(PRISTINE_SEC8)
        if live[offs[i]:end] != PRISTINE_SEC8[offs[i]:end]:
            changed.append(i)
    return changed


# --- commands ------------------------------------------------------------------
def cmd_status(ff8):
    print(fmt_state(live_state(ff8)))
    live = read_sec8(ff8)
    same = live == PRISTINE_SEC8
    print(f"entrance script live == file: {same}"
          + ("" if same else f"  edited entries: {diff_entries(live)}"))


def cmd_entries(ff8, source="live"):
    sec8 = read_sec8(ff8) if source == "live" else PRISTINE_SEC8
    offs = entry_offsets(sec8)
    for i in range(len(offs)):
        print(f"[{i:2d}] +{SEC8_OFF + offs[i]:#06x}  {entry_summary(decode_entry(sec8, offs, i))}")


def _entry_indices(arg: str, n: int) -> list[int]:
    return list(range(n)) if arg == "all" else [int(arg)]


def cmd_lock(ff8, which: str):
    sec8 = read_sec8(ff8)
    offs = entry_offsets(sec8)
    for i in _entry_indices(which, len(offs)):
        for p, op, arg in decode_entry(sec8, offs, i):
            if op == 0xff06:
                write_sec8_u16(ff8, p + 2, 0xFFFF)
                print(f"locked [{i}] (segment arg at +{SEC8_OFF + p + 2:#x}: {arg} -> 0xFFFF)")
                break


def cmd_unlock(ff8, which: str):
    sec8 = read_sec8(ff8)
    offs = entry_offsets(sec8)
    for i in _entry_indices(which, len(offs)):
        for p, op, arg in decode_entry(sec8, offs, i):
            if op == 0xff02 and arg:
                write_sec8_u16(ff8, p + 2, 0)
                print(f"unlocked [{i}] (MOMENT>= arg at +{SEC8_OFF + p + 2:#x}: {arg} -> 0)")
            elif op == 0xff03 and arg != 0xFFFF:
                write_sec8_u16(ff8, p + 2, 0xFFFF)
                print(f"unlocked [{i}] (MOMENT< arg at +{SEC8_OFF + p + 2:#x}: {arg} -> 0xFFFF)")


def cmd_restore(ff8, which: str = "all"):
    if which == "all":
        ff8.write_bytes(WMSET_BUF + SEC8_OFF, PRISTINE_SEC8)
        print("restored the whole entrance script")
        return
    offs = entry_offsets(PRISTINE_SEC8)
    i = int(which)
    end = offs[i + 1] if i + 1 < len(offs) else len(PRISTINE_SEC8)
    ff8.write_bytes(WMSET_BUF + SEC8_OFF + offs[i], PRISTINE_SEC8[offs[i]:end])
    print(f"restored [{i}]")


def entry_segment(i: int) -> int:
    offs = entry_offsets(PRISTINE_SEC8)
    for _, op, arg in decode_entry(PRISTINE_SEC8, offs, i):
        if op == 0xff06:
            return arg
    raise SystemExit(f"entry {i} has no segment condition")


def resolve_dest(args: list[str]) -> tuple[int, int, int]:
    """x y z | landmark name (ff8/warp.py) | eN (entry N's door) | sN (segment N's door)."""
    if len(args) == 3:
        return int(args[0]), int(args[1]), int(args[2])
    key = args[0].lower()
    if key[:1] in "es" and key[1:].isdigit():
        seg = entry_segment(int(key[1:])) if key[0] == "e" else int(key[1:])
        if seg not in DOORS:
            sys.exit(f"segment {seg} has no door tile")
        return DOORS[seg]
    d = warp.WARP_BY_KEY.get(key)
    if d is None:
        sys.exit(f"unknown destination {args[0]!r}; known: eN, sN, x y z, "
                 + ", ".join(warp.WARP_BY_KEY))
    return d.x, d.y, d.z


def cmd_warp(ff8, args: list[str]):
    s = live_state(ff8)
    if s["module"] != 2:
        sys.exit("not on the world map (module %d)" % s["module"])
    x, y, z = resolve_dest(args)
    ff8.warp(x, y, z)
    print(f"warped to {(x, y, z)} seg={segment_of(x, y)}")


def poll(ff8, seconds: float, until=None):
    """Print state changes for `seconds`; stop early when until(state) is true."""
    last = None
    t0 = time.time()
    s = None
    while time.time() - t0 < seconds:
        s = live_state(ff8)
        key = (s["module"], s["field"], s["segment"], s["door_tile"])
        if key != last:
            print(f"  t+{time.time() - t0:4.1f}s {fmt_state(s)}")
            last = key
        if until and until(s):
            break
        time.sleep(0.25)
    return s


def cmd_poke(ff8, idx: str, dest: list[str]):
    i = int(idx)
    s = live_state(ff8)
    if s["module"] != 2:
        sys.exit("start on the world map")
    print("== step 1: lock, warp onto the door, expect to stay on the world map")
    cmd_lock(ff8, str(i))
    x, y, z = resolve_dest(dest or [f"e{i}"])
    ff8.warp(x, y, z)
    # the engine needs a tick or two to re-resolve the tile under the avatar
    s = poll(ff8, 4.0, until=lambda st: st["module"] != 2)
    if s["module"] != 2:
        print("FAIL: entered a field while locked")
        cmd_restore(ff8, str(i))
        return
    if not s["door_tile"]:
        print("INCONCLUSIVE: the tile under the player is not a door tile "
              "(walk onto the town and re-run status); restoring")
        cmd_restore(ff8, str(i))
        return
    print("PASS: on a door tile, locked, still on the world map after 4 s")
    print("== step 2: restore, expect the field to load")
    cmd_restore(ff8, str(i))
    s = poll(ff8, 6.0, until=lambda st: st["module"] == 1)
    if s["module"] == 1:
        print(f"PASS: entered field {s['field']} ({FIELD_NAMES[s['field']]})")
    else:
        print("FAIL: still on the world map after restoring")


def main(argv: list[str]):
    if not argv:
        print(__doc__)
        return
    cmd, args = argv[0], argv[1:]
    if cmd == "entries" and args[:1] == ["file"]:
        cmd_entries(None, "file")
        return
    ff8 = attach()
    if cmd == "status":
        cmd_status(ff8)
    elif cmd == "entries":
        cmd_entries(ff8)
    elif cmd == "lock":
        cmd_lock(ff8, args[0])
    elif cmd == "unlock":
        cmd_unlock(ff8, args[0])
    elif cmd == "restore":
        cmd_restore(ff8, args[0] if args else "all")
    elif cmd == "warp":
        cmd_warp(ff8, args)
    elif cmd == "watch":
        poll(ff8, float(args[0]) if args else 600.0)
    elif cmd == "poke":
        cmd_poke(ff8, args[0], args[1:])
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
