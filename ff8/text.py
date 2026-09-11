"""In-game text: FF8's text codec and live rewriting of kernel.bin names.

FF8_EN.exe loads the whole of kernel.bin (Data/lang-en/main.fs) into one
static block at module+0x18F3E48 with the file layout intact: a u32 section
count, u32 section offsets, then the sections. Every menu / battle-results /
shop string for an item, spell or ability is read from that block, so
rewriting it in place changes what the game shows — no file patching.
Established live on 2026-09-10: the file header and both item text sections
each hit exactly once in the process, at that base, and a write there sticks.

Layout of the pairs we touch (data section, text section, record stride):

    magic         1 / 32   60 bytes x 57   (id = record index)
    battle items  7 / 38   24 bytes x 33   (item id 0..32; 0 is a dummy)
    items         8 / 39    4 bytes x 166  (item id 33..198 = index + 33)

Each data record starts with two u16 offsets (name, description) relative to
its text section; the text section is a packed run of NUL-terminated strings
in FF8's encoding. Strings are variable length with no slack, so a rename
re-packs the entire text section and rewrites every record's offsets; the
result must fit the vanilla section size (the block is contiguous, so growing
one section would overwrite the next).

What this does NOT change: field-script messages such as "Received [Magical
Lamp]!" are literal text inside each field's own MSD table, not built from
the kernel name. Those need the field text patched (file or resident copy),
which is a separate piece of work.
"""

from __future__ import annotations

import struct
from typing import Iterable

from .kernel_text_vanilla import SECTION_OFFSETS, VANILLA

KERNEL_BASE = 0x18F3E48         # resident kernel.bin (module-relative)
KERNEL_SECTIONS = 56

# --- codec (English table; Hyne src/FF8text_caract.cpp) -------------------
_TABLE = [
    " ", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "%", "/", ":", "!", "?",
    "…", "+", "-", "=", "*", "&", "「", "」", "(", ")", "·", ".", ",", "~", "“", "”",
    "‘", "#", "$", "'", "_", "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K",
    "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z", "a",
    "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m", "n", "o", "p", "q",
    "r", "s", "t", "u", "v", "w", "x", "y", "z", "À", "Á", "Â", "Ä", "Ç", "È", "É",
    "Ê", "Ë", "Ì", "Í", "Î", "Ï", "Ñ", "Ò", "Ó", "Ô", "Ö", "Ù", "Ú", "Û", "Ü", "Œ",
    "ß", "à", "á", "â", "ä", "ç", "è", "é", "ê", "ë", "ì", "í", "î", "ï", "ñ", "ò",
    "ó", "ô", "ö", "ù", "ú", "û", "ü", "œ", "", "[", "]", "■", "○", "♦", "【", "】",
    "□", "", "『", "』", "", ";", "", "¯", "×", "", "", "↓", "°", "¡", "¿", "─",
    "«", "»", "±", "♫", "", "↑", "", "", "", "™", "<", ">", "", "", "", "",
    "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "",
    "", "", "®", "", "", "", "", "", "in", "e ", "ne", "to", "re", "HP", "l ", "ll",
    "GF", "nt", "il", "o ", "ef", "on", " w", " r", "wi", "fi", "EC", "s ", "ar", "FE", " S", "ag",
]
DECODE = {0x20 + i: s for i, s in enumerate(_TABLE) if s}
_ENC1 = {s: b for b, s in DECODE.items() if len(s) == 1}
_ENC2 = {s: b for b, s in DECODE.items() if len(s) == 2}   # dictionary pairs
# ASCII look-alikes for characters the font lacks (player/item names are UTF-8)
_FOLD = {"\"": "'", "`": "'", "’": "'", "\\": "/", "|": "/", "{": "(", "}": ")",
         "\t": " ", "\r": "", "–": "-", "—": "-", "…": "..."}
# Characters vanilla kernel text actually uses, by string kind. The menu
# renderer crashed (access violation in its quad builder, 2026-09-10) on a
# NAME containing a dictionary-pair byte and the "…" glyph, neither of which
# any vanilla name has; so names get plain single-byte characters from this
# set and descriptions may additionally use the pairs vanilla descriptions use.
NAME_ALPHABET = frozenset(" '+-.0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz")
DESC_ALPHABET = NAME_ALPHABET | frozenset("!%&*,/=?")
DESC_PAIRS = frozenset([" S", " r", " w", "GF", "HP", "ag", "ar", "e ", "ef", "fi", "il",
                        "in", "l ", "ll", "ne", "nt", "o ", "on", "re", "s ", "to", "wi"])


def decode(raw: bytes) -> str:
    """FF8 bytes -> text. Control codes become {xNNNN}; 0x02 is a newline."""
    out = []
    i = 0
    while i < len(raw):
        c = raw[i]
        if c == 0:
            break
        if c == 0x02:
            out.append("\n")
            i += 1
            continue
        if 1 <= c <= 0x1F:
            arg = raw[i + 1] if i + 1 < len(raw) else 0
            out.append("{x%02x%02x}" % (c, arg))
            i += 2
            continue
        out.append(DECODE.get(c, "{x%02x}" % c))
        i += 1
    return "".join(out)


def encode(text: str, pairs: bool = True, alphabet: frozenset | None = None,
           pair_set: frozenset | None = None) -> bytes:
    """Text -> FF8 bytes (no terminator). Unknown characters become '?'.
    With pairs=True the two-letter dictionary codes are used, which is how
    the vanilla text is packed and buys ~15% more room. `alphabet` limits
    the single characters emitted (others become a space); `pair_set`
    limits which dictionary pairs may be used."""
    text = "".join(_FOLD.get(ch, ch) for ch in text)
    out = bytearray()
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\n":
            out.append(0x02)
            i += 1
            continue
        pair = text[i:i + 2]
        if pairs and pair in _ENC2 and (pair_set is None or pair in pair_set):
            out.append(_ENC2[pair])
            i += 2
            continue
        if alphabet is not None and ch not in alphabet:
            ch = " "
        out.append(_ENC1.get(ch, _ENC1["?"]))
        i += 1
    return bytes(out)


def encode_name(text: str) -> bytes:
    """A name string: single-byte characters vanilla names use, no pairs."""
    return encode(text, pairs=False, alphabet=NAME_ALPHABET)


def encode_desc(text: str) -> bytes:
    """A description: vanilla's description characters and dictionary pairs."""
    return encode(text, pairs=True, alphabet=DESC_ALPHABET, pair_set=DESC_PAIRS)


FIELD_ALPHABET = NAME_ALPHABET | frozenset("[]!,?\n")


def encode_field(text: str) -> bytes:
    """A field message line: plain bytes (field text uses no dictionary
    pairs: 14 of 21,353 vanilla strings), newline as 0x02."""
    return encode(text, pairs=False, alphabet=FIELD_ALPHABET)


def fit_message(named, fallbacks, item: str, who: str, budget: int) -> bytes:
    """Encode a message within `budget` bytes. `named` templates (callables
    of (item, who)) are tried at decreasing item-name lengths, each at
    decreasing player-name lengths, so the item name is kept as long as any
    framing fits it; only then the item-less `fallbacks`, the last of which
    is cut if it must be."""
    for item_chars in (40, 24, 17, 12, 8):
        for template in named:
            for who_chars in (16, 10, 6):
                raw = encode_field(template(fit(item, item_chars), fit(who, who_chars)))
                if len(raw) <= budget:
                    return raw
    for template in fallbacks:
        for who_chars in (16, 10, 6):
            raw = encode_field(template("", fit(who, who_chars)))
            if len(raw) <= budget:
                return raw
    return encode_field(fallbacks[-1]("", ""))[:budget]


def fit(text: str, max_chars: int) -> str:
    """Shorten to the display budget, keeping the start (the distinctive
    part of AP item names is usually first: 'Progressive Sword'). Plain
    cut, no ellipsis: vanilla kernel text never uses that glyph."""
    text = " ".join(text.split())
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip()


# --- kernel tables ---------------------------------------------------------
class TextTable:
    """One (data section, text section) pair: name/description per record."""

    def __init__(self, data: bytes, text: bytes, stride: int):
        self.stride = stride
        self.count = len(data) // stride
        self.data_size = len(data)
        self.text_size = len(text)
        self.records = []           # (name_bytes, desc_bytes) raw, no NUL
        self.tail = [bytes(data[k * stride + 4:(k + 1) * stride])
                     for k in range(self.count)]
        for k in range(self.count):
            no, do = struct.unpack_from("<HH", data, k * stride)
            self.records.append((self._cstr(text, no), self._cstr(text, do)))

    @staticmethod
    def _cstr(text: bytes, off: int) -> bytes:
        if off >= len(text):
            return b""
        end = text.find(b"\x00", off)
        return text[off:end if end >= 0 else len(text)]

    def name(self, index: int) -> str:
        return decode(self.records[index][0])

    def description(self, index: int) -> str:
        return decode(self.records[index][1])

    def render(self, overrides: dict[int, tuple[bytes | None, bytes | None]]
               ) -> tuple[bytes, bytes]:
        """Re-pack with `overrides` (index -> (name, desc), None keeps the
        vanilla string). Returns (data, text) padded to the vanilla sizes.
        Raises ValueError when the packed text would not fit."""
        text = bytearray()
        data = bytearray()
        for k, (vn, vd) in enumerate(self.records):
            on, od = overrides.get(k, (None, None))
            name = vn if on is None else on
            desc = vd if od is None else od
            offs = []
            for s in (name, desc):
                if not s and k == 0 and vn == b"" and vd == b"":
                    offs.append(0xFFFF)     # dummy record keeps its 0xFFFF
                    continue
                offs.append(len(text))
                text += s + b"\x00"
            data += struct.pack("<HH", *offs) + self.tail[k]
        if len(text) > self.text_size:
            raise ValueError(f"text {len(text)} > section {self.text_size}")
        text += b"\x00" * (self.text_size - len(text))
        return bytes(data), bytes(text)


TABLES = {                          # name -> (data section, text section, stride)
    "magic": (1, 32, 60),
    "battle_items": (7, 38, 24),
    "items": (8, 39, 4),
}
BATTLE_ITEM_COUNT = 33              # item ids 0..32 live in battle_items
NAME_CHARS = 17                     # longest vanilla item name ("Sorceress' Letter")
DESC_CHARS = 44                     # longest vanilla description
# The vanilla text sections are packed with zero slack, so longer strings must
# be paid for by shorter ones. apply() tries these (name, description) caps in
# order and keeps the first render that fits: descriptions give way first,
# the name (what the player actually reads in a list) last.
BUDGETS = ((NAME_CHARS, DESC_CHARS), (NAME_CHARS, 32), (NAME_CHARS, 24),
           (NAME_CHARS, 16), (NAME_CHARS, 12), (NAME_CHARS, 8), (NAME_CHARS, 0),
           (14, 0), (12, 0), (10, 0), (8, 0))


def _magic_names() -> tuple[str, ...]:
    table = TextTable(VANILLA[1], VANILLA[32], 60)
    return tuple(table.name(k) for k in range(table.count))


MAGIC_NAMES = _magic_names()        # kernel magic index -> vanilla spell name


def item_slot(item_id: int) -> tuple[str, int]:
    if item_id < BATTLE_ITEM_COUNT:
        return "battle_items", item_id
    return "items", item_id - BATTLE_ITEM_COUNT


def vanilla_table(name: str) -> TextTable:
    ds, ts, stride = TABLES[name]
    return TextTable(VANILLA[ds], VANILLA[ts], stride)


def section_offset(section: int) -> int:
    """Module-relative offset of a kernel section in the resident block."""
    return KERNEL_BASE + SECTION_OFFSETS[section]


class KernelText:
    """Live view of the resident kernel text. `apply` rewrites whole
    sections; `restore` puts the vanilla bytes back. Refuses to touch a block
    that is neither vanilla nor our own last render (a modded kernel.bin)."""

    def __init__(self, ff8):
        self.ff8 = ff8
        self.rendered: dict[str, tuple[bytes, bytes]] = {}   # table -> last write
        self.foreign = False

    def header_ok(self) -> bool:
        hdr = self.ff8.read_bytes(KERNEL_BASE, 4 + 4 * KERNEL_SECTIONS)
        count = struct.unpack_from("<I", hdr, 0)[0]
        if count != KERNEL_SECTIONS:
            return False
        offs = struct.unpack_from("<%dI" % KERNEL_SECTIONS, hdr, 4)
        return list(offs) == list(SECTION_OFFSETS)

    def read_sections(self, name: str) -> tuple[bytes, bytes]:
        ds, ts, _ = TABLES[name]
        return (self.ff8.read_bytes(section_offset(ds), len(VANILLA[ds])),
                self.ff8.read_bytes(section_offset(ts), len(VANILLA[ts])))

    def state(self, name: str) -> str:
        """'vanilla', 'ours' (matches our last write), 'renamed' (only names
        and offsets differ from vanilla: an earlier client run's rewrite that
        the game still holds) or 'foreign' (record data differs: a modded
        kernel.bin, which is never touched)."""
        ds, ts, stride = TABLES[name]
        cur = self.read_sections(name)
        if cur == (VANILLA[ds], VANILLA[ts]):
            return "vanilla"
        if cur == self.rendered.get(name):
            return "ours"
        tails = TextTable(cur[0], cur[1], stride).tail
        if tails == vanilla_table(name).tail:
            return "renamed"
        return "foreign"

    def apply(self, name: str, overrides: dict[int, tuple[str | None, str | None]]
              ) -> bool:
        """Render `overrides` (index -> (name text, description text)) over the
        vanilla table and write it if the resident block differs. Returns
        True when the resident text now matches the request."""
        table = vanilla_table(name)
        for name_chars, desc_chars in BUDGETS:
            raw = {k: (None if n is None else encode_name(fit(n, name_chars)),
                       None if d is None else encode_desc(fit(d, desc_chars)))
                   for k, (n, d) in overrides.items()}
            try:
                data, text = table.render(raw)
                break
            except ValueError:
                continue
        else:
            raise ValueError(f"{len(overrides)} names don't fit {name} even "
                             "at the smallest budget")
        if not self.header_ok():
            return False
        st = self.state(name)
        if st == "foreign":
            self.foreign = True
            return False
        if self.read_sections(name) == (data, text):
            self.rendered[name] = (data, text)
            return True
        ds, ts, _ = TABLES[name]
        # text first so the offsets never point past a shorter new string
        self.ff8.write_bytes(section_offset(ts), text)
        self.ff8.write_bytes(section_offset(ds), data)
        self.rendered[name] = (data, text)
        return True

    def restore(self, names: Iterable[str] = TABLES) -> None:
        """Vanilla bytes back for our own or an earlier run's renames."""
        for name in names:
            if self.state(name) in ("ours", "renamed"):
                ds, ts, _ = TABLES[name]
                self.ff8.write_bytes(section_offset(ts), VANILLA[ts])
                self.ff8.write_bytes(section_offset(ds), VANILLA[ds])
            self.rendered.pop(name, None)
