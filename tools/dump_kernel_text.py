"""FF8 (Steam 2013) archive + text inspection, and the generator for
ff8/kernel_text_vanilla.py.

    python tools/dump_kernel_text.py gen            # regenerate ff8/kernel_text_vanilla.py
    python tools/dump_kernel_text.py items          # list item ids, names, descriptions
    python tools/dump_kernel_text.py field bgsido_2 [filter]   # a field's message table
    python tools/dump_kernel_text.py grep Received  # every field message matching
    python tools/dump_kernel_text.py fields         # regenerate ff8/fields.py (needs the
                                                    # game running: the map list is only
                                                    # resident in memory)
    python tools/dump_kernel_text.py pickups        # regenerate ff8/pickups.py from
                                                    # ff8/fields.py + the field text

Reads Data/lang-en/*.fs archives straight from the Steam install (FS/FI/FL
triple, LZS-compressed entries), so nothing is copied out of the game folder.
The in-game text codec lives in ff8/text.py; this tool only reuses it.
"""
import importlib.util
import os
import re
import struct
import sys
import textwrap
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME_DIR = os.environ.get(
    "FF8_DIR", r"F:\SteamLibrary\steamapps\common\FINAL FANTASY VIII")
LANG = os.path.join(GAME_DIR, "Data", "lang-en")
KERNEL_SECTIONS_SHIPPED = (1, 32, 7, 38, 8, 39)   # magic, battle items, items


def _load_text_module():
    """ff8/text.py without importing the ff8 package (needs Archipelago)."""
    pkg = types.ModuleType("ff8")
    pkg.__path__ = [os.path.join(ROOT, "ff8")]
    sys.modules["ff8"] = pkg
    for name in ("kernel_text_vanilla", "text"):
        spec = importlib.util.spec_from_file_location(
            "ff8." + name, os.path.join(ROOT, "ff8", name + ".py"))
        mod = importlib.util.module_from_spec(spec)
        sys.modules["ff8." + name] = mod
        spec.loader.exec_module(mod)
    return sys.modules["ff8.text"]


# --- archives ---------------------------------------------------------------
def lzs_decompress(data: bytes) -> bytes:
    """FF8 LZS: u32 compressed length, then LZSS over a 4 KiB ring."""
    n = struct.unpack_from("<I", data, 0)[0]
    src = data[4:4 + n]
    out = bytearray()
    ring = bytearray(4096)
    pos = 0xFEE
    i = 0
    while i < len(src):
        flags = src[i]
        i += 1
        for bit in range(8):
            if i >= len(src):
                break
            if flags & (1 << bit):
                c = src[i]
                i += 1
                out.append(c)
                ring[pos] = c
                pos = (pos + 1) & 0xFFF
            else:
                a, b = src[i], src[i + 1]
                i += 2
                off = a | ((b & 0xF0) << 4)
                for k in range((b & 0x0F) + 3):
                    c = ring[(off + k) & 0xFFF]
                    out.append(c)
                    ring[pos] = c
                    pos = (pos + 1) & 0xFFF
    return bytes(out)


class Archive:
    """One FS/FI/FL triple, from files or from bytes (nested field archives)."""

    def __init__(self, fl: bytes, fi: bytes, fs: bytes):
        self.names = fl.decode("latin-1").splitlines()
        self.entries = [struct.unpack_from("<III", fi, k * 12)
                        for k in range(len(fi) // 12)]
        self.fs = fs

    @classmethod
    def open(cls, base: str) -> "Archive":
        with open(base + ".fl", "rb") as f:
            fl = f.read()
        with open(base + ".fi", "rb") as f:
            fi = f.read()
        with open(base + ".fs", "rb") as f:
            fs = f.read()
        return cls(fl, fi, fs)

    def find(self, suffix: str) -> int:
        for k, n in enumerate(self.names):
            if n.lower().endswith(suffix.lower()):
                return k
        raise KeyError(suffix)

    def read(self, suffix: str) -> bytes:
        size, off, comp = self.entries[self.find(suffix)]
        if comp == 1:
            clen = struct.unpack_from("<I", self.fs, off)[0]
            return lzs_decompress(self.fs[off:off + 4 + clen])
        if comp == 0:
            return self.fs[off:off + size]
        raise NotImplementedError(f"compression {comp}")

    def field(self, name: str) -> "Archive":
        """A field's own archive nested inside field.fs."""
        return Archive(self.read(name + ".fl"), self.read(name + ".fi"),
                       self.read(name + ".fs"))

    def field_names(self) -> list[str]:
        return sorted({n.rsplit("\\", 1)[-1][:-3].lower()
                       for n in self.names if n.lower().endswith(".fl")})


def msd_strings(msd: bytes, decode) -> list[str]:
    """A field's message table: u32 offsets then NUL-terminated strings."""
    if len(msd) < 4:
        return []
    count = struct.unpack_from("<I", msd, 0)[0] // 4
    out = []
    for k in range(count):
        off = struct.unpack_from("<I", msd, 4 * k)[0]
        end = msd.find(b"\x00", off)
        out.append(decode(msd[off:end if end >= 0 else len(msd)]))
    return out


# --- field ids / draw points ------------------------------------------------
MAPLIST_OFFSET = 0x15FB118      # module-relative: "mapdata\maplist" loaded whole,
                                # newline-separated field names; index == field id
                                # (FIELD_ID at +0x18D2FC0). The engine NUL-terminates
                                # the current entry in place, so split on both.
JSM_DRAWPOINT = 0x137           # field-script opcode DRAWPOINT (arg: slot + 1)
JSM_PSHN_L = 7                  # push literal (instruction high byte)


def read_maplist() -> list[str]:
    import pymem
    pm = pymem.Pymem("FF8_EN.exe")
    buf = pm.read_bytes(pm.base_address + MAPLIST_OFFSET, 0x4000).decode("latin-1")
    m = re.match(r"[a-z0-9_\n\x00]+", buf)
    return [n for n in re.split(r"[\n\x00]+", m.group(0)) if n]


def scan_draw_points(field_names: list[str]) -> dict[int, list[int]]:
    """savemap draw slot -> field ids whose script calls DRAWPOINT(slot + 1)."""
    fields = Archive.open(os.path.join(LANG, "field"))
    avail = set(fields.field_names())
    out: dict[int, list[int]] = {}
    for fid, name in enumerate(field_names):
        if name not in avail:
            continue
        try:
            jsm = fields.field(name).read(name + ".jsm")
        except (KeyError, NotImplementedError):
            continue
        start = struct.unpack_from("<H", jsm, 6)[0]
        words = struct.unpack_from("<%dI" % ((len(jsm) - start) // 4), jsm, start)
        for i in range(1, len(words)):
            if words[i] == JSM_DRAWPOINT and words[i - 1] >> 24 == JSM_PSHN_L:
                out.setdefault((words[i - 1] & 0xFFFFFF) - 1, []).append(fid)
    return out


def cmd_fields():
    names = read_maplist()
    draws = scan_draw_points(names)
    out = [
        '"""Field ids and draw-point screens for FF8 (Steam 2013). Generated by',
        "tools/dump_kernel_text.py fields; do not edit by hand.",
        "",
        "FIELD_NAMES: index == the live field id (memory.FIELD_ID), from the resident",
        "mapdata/maplist. DRAW_POINT_FIELDS: savemap draw-point slot -> the field ids",
        "whose script calls DRAWPOINT(slot + 1), i.e. the screens where that draw point",
        'is on screen (from every field .jsm in Data/lang-en/field.fs)."""',
        "",
        "FIELD_NAMES: tuple[str, ...] = (",
    ]
    for i in range(0, len(names), 8):
        out.append("    " + ", ".join(repr(n) for n in names[i:i + 8]) + ",")
    out += [")", "", "DRAW_POINT_FIELDS: dict[int, tuple[int, ...]] = {"]
    for slot in sorted(draws):
        fids = sorted(set(draws[slot]))
        out.append("    %d: (%s,),  # %s" % (
            slot, ", ".join(map(str, fids)), ", ".join(names[f] for f in fids)))
    out += ["}", ""]
    path = os.path.join(ROOT, "ff8", "fields.py")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out))
    print("wrote", path, len(names), "fields,", len(draws), "draw slots")


# --- pickup lines -----------------------------------------------------------
# Item checks whose field message names the item differently from kernel.bin.
PICKUP_ALIASES = {
    "Weapons Mon 1st": "Weapons Monthly, First Issue",
    "Weapons Mon Mar": "Weapons Monthly, March Issue",
    "Weapons Mon Apr": "Weapons Monthly, April Issue",
    "Weapons Mon May": "Weapons Monthly, May Issue",
    "Weapons Mon Jun": "Weapons Monthly, June Issue",
    "Weapons Mon Jul": "Weapons Monthly, July Issue",
    "Weapons Mon Aug": "Weapons Monthly, August Issue",
    "Pet Pals Vol.1": "Pet Pals  Vol.1",
    "Pet Pals Vol.2": "Pet Pals Vol. 2",
}
# Timber Maniacs issue bit (locations._TM_ISSUES) -> screens carrying its
# "Found an old issue of [Timber Maniacs]!" line. Bit 10 (Centra Ruins) is
# awarded silently and has none.
TM_ISSUE_FIELDS = {
    0: ("bchtr_1",), 1: ("bcform_1",), 2: ("dopub_2",), 3: ("dohtr_1",),
    4: ("timania1",), 5: ("tihtr1",), 6: ("glhtr1", "glhtr1a"), 7: ("fhmin1",),
    8: ("fhhtr1",), 9: ("tggrave1",), 11: ("tmhtr1", "tmmin1"), 12: ("ehblan3",),
    13: ("secont1",),
}
ITEM_CHECK_IDS = [163, 167, 168] + list(range(177, 199))    # magazines, ring, lamp


def cmd_pickups(text):
    sys.path.insert(0, ROOT)
    spec = importlib.util.spec_from_file_location(
        "ff8.fields", os.path.join(ROOT, "ff8", "fields.py"))
    fields_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fields_mod)
    field_names = fields_mod.FIELD_NAMES
    fields = Archive.open(os.path.join(LANG, "field"))
    items = text.vanilla_table("items")
    wanted = {}          # "[Name]" -> ("item", id)
    for iid in ITEM_CHECK_IDS:
        name = items.name(iid - text.BATTLE_ITEM_COUNT)
        wanted["[%s]" % PICKUP_ALIASES.get(name, name)] = ("item", iid)
    tm_fields = {f: bit for bit, fs in TM_ISSUE_FIELDS.items() for f in fs}
    found = {}           # key -> list of (field id, index, raw hex, text)
    for fid, name in enumerate(field_names):
        try:
            msd = fields.field(name).read(name + ".msd")
        except (KeyError, NotImplementedError):
            continue
        if len(msd) < 4:
            continue
        count = struct.unpack_from("<I", msd, 0)[0] // 4
        for k in range(count):
            off = struct.unpack_from("<I", msd, 4 * k)[0]
            end = msd.find(b"\x00", off)
            raw = msd[off:end if end >= 0 else len(msd)]
            s = text.decode(raw)
            key = None
            if s.startswith("Received ["):
                for br, k2 in wanted.items():
                    if br in s:
                        key = k2
            elif s.startswith("Found an old issue of [Timber Maniacs]") and name in tm_fields:
                key = ("tm", tm_fields[name])
            if key is not None:
                found.setdefault(key, []).append((fid, k, raw.hex(), s))
    out = [
        '"""Pickup message lines for FF8 (Steam 2013). Generated by',
        "tools/dump_kernel_text.py pickups; do not edit by hand.",
        "",
        "PICKUP_LINES: (kind, id) -> the field-text lines the game shows when that",
        "check is collected: (field id, message index, vanilla bytes hex). kind",
        '"item" = game item id (magazines, Magical Lamp, Solomon Ring); kind "tm" =',
        "Timber Maniacs issue bit. The client rewrites the line in the resident",
        'message table of that field, within the vanilla byte length."""',
        "",
        "PICKUP_LINES: dict[tuple[str, int], tuple[tuple[int, int, str], ...]] = {",
    ]
    for key in sorted(found):
        out.append("    %r: (" % (key,))
        for fid, k, hx, s in found[key]:
            out.append("        (%d, %d, %r),  # %s: %s" % (
                fid, k, hx, field_names[fid], s.split("\n")[0][:50]))
        out.append("    ),")
    out += ["}", ""]
    path = os.path.join(ROOT, "ff8", "pickups.py")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out))
    print("wrote", path, len(found), "checks,", sum(len(v) for v in found.values()), "lines")


# --- commands ---------------------------------------------------------------
def kernel_bin() -> bytes:
    return Archive.open(os.path.join(LANG, "main")).read("kernel.bin")


def cmd_gen():
    d = kernel_bin()
    n = struct.unpack_from("<I", d, 0)[0]
    offs = [struct.unpack_from("<I", d, 4 + 4 * i)[0] for i in range(n)]
    ends = offs[1:] + [len(d)]
    import base64
    out = [
        '"""Vanilla FF8 (Steam 2013, English) kernel.bin text sections, embedded so the',
        "client can (a) prove the resident kernel is unmodified before rewriting names and",
        "(b) restore it exactly. Generated from Data/lang-en/main.fs:kernel.bin by",
        'tools/dump_kernel_text.py; do not edit by hand."""',
        "import base64", "",
        "SECTION_OFFSETS = %r" % (offs,), "KERNEL_SIZE = %d" % len(d), "",
    ]
    for s in KERNEL_SECTIONS_SHIPPED:
        b64 = base64.b64encode(d[offs[s]:ends[s]]).decode()
        out.append("SECTION_%d = base64.b64decode(" % s)
        out += ['    "%s"' % line for line in textwrap.wrap(b64, 88)]
        out += [")", ""]
    out.append("VANILLA = {%s}" % ", ".join(
        "%d: SECTION_%d" % (s, s) for s in KERNEL_SECTIONS_SHIPPED))
    path = os.path.join(ROOT, "ff8", "kernel_text_vanilla.py")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out) + "\n")
    print("wrote", path)


def cmd_items(text):
    for table in ("battle_items", "items"):
        t = text.vanilla_table(table)
        base = 0 if table == "battle_items" else text.BATTLE_ITEM_COUNT
        for k in range(t.count):
            print(base + k, t.name(k), "|", t.description(k))


def cmd_field(text, name, needle=None):
    fields = Archive.open(os.path.join(LANG, "field"))
    sub = fields.field(name)
    msd = sub.read(name + ".msd")
    for k, s in enumerate(msd_strings(msd, text.decode)):
        if needle is None or needle.lower() in s.lower():
            print(k, repr(s))


def cmd_grep(text, pattern):
    fields = Archive.open(os.path.join(LANG, "field"))
    rx = re.compile(pattern, re.I)
    for name in fields.field_names():
        try:
            msd = fields.field(name).read(name + ".msd")
        except (KeyError, NotImplementedError):
            continue
        for k, s in enumerate(msd_strings(msd, text.decode)):
            if rx.search(s):
                print(name, k, repr(s))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    text = _load_text_module()
    args = sys.argv[1:]
    if not args or args[0] == "gen":
        cmd_gen()
    elif args[0] == "items":
        cmd_items(text)
    elif args[0] == "field":
        cmd_field(text, args[1], args[2] if len(args) > 2 else None)
    elif args[0] == "grep":
        cmd_grep(text, args[1])
    elif args[0] == "fields":
        cmd_fields()
    elif args[0] == "pickups":
        cmd_pickups(text)
    else:
        sys.exit(__doc__)
