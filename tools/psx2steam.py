# SPDX-License-Identifier: GPL-3.0-or-later
#
# psx2steam.py — part of ff8_arch (https://github.com/wilsonao/ff8_arch).
# The LZS container codec and the game's bugged CRC-16 table below are ported
# from Hyne, the Final Fantasy VIII save editor:
#   Copyright (C) 2009-2013 Arzel Jérôme <myst6re@gmail.com>
#   https://github.com/myst6re/hyne (GPL-3.0-or-later)
# so this file — unlike the rest of the repository, which is MIT — is
# distributed under the GNU General Public License v3 or later. See
# tools/LICENSE.GPL-3.0 for the full text. It is a development tool and is
# not part of the shipped ff8.apworld.
"""Convert PSX FF8 saves (DexDrive .gme / raw .mcr memory cards) to Steam 2013
`.ff8` files, with per-save labels pulled from the save's preview header.

Format facts (Hyne source, thirdparty/hyne-src — SaveData.cpp/.h, LZS.cpp,
SavecardData.cpp):
  * Uncompressed save == the 8192-byte PSX block, identically laid out on PC:
      0x000  "SC" + icon-frame count + 0x01 + Shift-JIS title   (96 B header)
      0x060  icon bitmap, padded to 288 B
      0x180  u16 checksum, then FF 08
      0x184  HEADER/76: locationID u16, hpLeader u16, hpMax u16, saveCount u16,
             gil u32, time u32 (seconds), level u8, party u8[3], names 4x12,
             disc u32, curSave u32
      0x1D0  MAIN/4944 (gfs, chars, shops, config @+2704 ... field vars)
      0x1520 u16 checksum again, zero padding to 8192
  * checksum = CRC-16/CCITT (poly 0x1021, init 0xFFFF, final ~crc) over
    MAIN's 4944 bytes [0x1D0:0x1520].
  * PC container = u32-LE compressed-size prefix + FF8 LZS stream (Okumura
    LZSS: 4096-byte ring zero-initialised, write cursor starts at 4078,
    references are raw ring positions, length 3..18).
  * PS -> PC conversion tweak (Hyne SaveData::save(convertAnalogConfig=true)):
    config.analog_volume (abs offset 0x1D0+2704+3 = 0xC63) = (v & 0x80) | 100,
    then recompute both checksums.

Usage:
  psx2steam.py selftest [SAVE_DIR]      validate LZS+CRC ports against the
                                        real Steam saves in the user dir
                                        (auto-found under Documents, or
                                        FF8_SAVE_DIR)
  psx2steam.py convert IN_DIR OUT_DIR   convert every save block in every
                                        .gme/.mcr under IN_DIR; writes
                                        OUT_DIR/<src>-blkNN.ff8 + index.csv
"""

import csv
import re
import sys
from pathlib import Path

CARD = 131072
GME_HEADER = 3904
BLOCK = 8192
MAIN_OFF, MAIN_LEN = 0x1D0, 4944
CRC_A, CRC_B = 0x180, MAIN_OFF + MAIN_LEN
HDR = 0x184
ANALOG_OFF = MAIN_OFF + 2704 + 3

CRC_TAB = []
for _i in range(256):
    _c = _i << 8
    for _ in range(8):
        _c = ((_c << 1) ^ 0x1021) & 0xFFFF if _c & 0x8000 else (_c << 1) & 0xFFFF
    CRC_TAB.append(_c)
# FF8's actual table (see Hyne SaveData.cpp crcTab) zeroes the last entry —
# an original-game quirk every FF8 save carries. Without this, checksums
# computed here never match game-written saves.
CRC_TAB[255] = 0


def checksum(block: bytes) -> int:
    crc = 0xFFFF
    for b in block[MAIN_OFF:MAIN_OFF + MAIN_LEN]:
        crc = (CRC_TAB[((crc >> 8) ^ b) & 0xFF] ^ (crc << 8)) & 0xFFFF
    return crc ^ 0xFFFF


# ---------------------------------------------------------------- LZS (FF8)

def lzs_decompress(data: bytes, expected: int = BLOCK) -> bytes:
    buf = bytearray(4096)          # decoder ring, zero-initialised
    cur = 4078
    out = bytearray()
    flags, nbits = 0, 0
    i, n = 0, len(data)
    while i < n and len(out) < expected:
        if nbits == 0:
            flags, nbits = data[i], 8
            i += 1
            continue
        if flags & 1:
            if i >= n:
                break
            b = data[i]; i += 1
            out.append(b)
            buf[cur] = b
            cur = (cur + 1) & 4095
        else:
            if i + 1 >= n:
                break
            pos = data[i] | ((data[i + 1] & 0xF0) << 4)
            length = (data[i + 1] & 0x0F) + 3
            i += 2
            for k in range(length):
                b = buf[(pos + k) & 4095]
                out.append(b)
                buf[cur] = b
                cur = (cur + 1) & 4095
        flags >>= 1
        nbits -= 1
    return bytes(out[:expected])


def lzs_compress(data: bytes) -> bytes:
    """Greedy FF8-LZS encoder. Only references ring positions that are
    (a) already written this stream or (b) inside the decoder's zeroed
    init region [0:4078] and not yet overwritten -- matching what any
    conforming decoder is guaranteed to reproduce."""
    ring = bytearray(4096)
    valid = bytearray([1]) * 4078 + bytearray(4096 - 4078)
    cur = 4078
    out = bytearray()
    flag_pos = None
    flag_bit = 0

    def emit(is_literal, payload):
        nonlocal flag_pos, flag_bit
        if flag_bit == 0:
            flag_pos = len(out)
            out.append(0)
        if is_literal:
            out[flag_pos] |= 1 << flag_bit
        out.extend(payload)
        flag_bit = (flag_bit + 1) & 7

    def push(b):
        nonlocal cur
        ring[cur] = b
        valid[cur] = 1
        cur = (cur + 1) & 4095

    i, n = 0, len(data)
    while i < n:
        best_len, best_pos = 0, 0
        max_len = min(18, n - i)
        if max_len >= 3:
            first = data[i]
            for pos in range(4096):
                if not valid[pos] or ring[pos] != first:
                    continue
                # cap at the ring-distance to the write cursor: this token's
                # own writes land at cur..cur+len-1, and the decoder must
                # never read a position after this token has clobbered it
                dist = (cur - pos) & 4095
                if dist == 0:
                    continue
                limit = min(max_len, dist)
                length = 1
                while length < limit:
                    p = (pos + length) & 4095
                    if not valid[p] or ring[p] != data[i + length]:
                        break
                    length += 1
                if length > best_len:
                    best_len, best_pos = length, pos
                    if length == max_len:
                        break
        if best_len >= 3:
            emit(False, bytes((best_pos & 0xFF,
                               ((best_pos >> 4) & 0xF0) | (best_len - 3))))
            for k in range(best_len):
                push(data[i + k])
            i += best_len
        else:
            emit(True, data[i:i + 1])
            push(data[i])
            i += 1
    return bytes(out)


# ------------------------------------------------------------- containers

def card_image(path: Path) -> bytes | None:
    data = path.read_bytes()
    if data[:11] == b"123-456-STD":
        return data[GME_HEADER:]
    if data[:2] == b"MC":
        return data if len(data) == CARD else data[-CARD:]
    if len(data) > GME_HEADER and data[GME_HEADER:GME_HEADER + 2] == b"MC":
        return data[GME_HEADER:]
    idx = data.find(b"MC")
    if 0 <= idx < BLOCK and len(data) - idx >= BLOCK:
        return data[idx:]
    return None


def gme_comments(path: Path) -> list[str]:
    comments = [""] * 16
    data = path.read_bytes()
    if data[:11] == b"123-456-STD":
        for i in range(15):
            raw = data[64 + i * 256: 64 + (i + 1) * 256].split(b"\0")[0]
            comments[i + 1] = "".join(chr(c) for c in raw
                                      if 32 <= c < 127).strip()
    return comments


def blocks(card: bytes):
    for b in range(1, 16):
        d = card[b * 128: b * 128 + 128]
        if d[0] == 0x51:  # first (and, for FF8, only) block of a save
            blk = card[b * BLOCK: (b + 1) * BLOCK]
            if blk[:2] == b"SC":
                yield b, blk


def title_of(blk: bytes) -> str:
    try:
        t = blk[4:68].decode("shift_jis", "replace")
    except Exception:
        return "?"
    return re.sub(r"\s+", " ", t).strip("\0 \ufffd")


def labels_of(blk: bytes) -> dict:
    u16 = lambda o: int.from_bytes(blk[o:o + 2], "little")
    u32 = lambda o: int.from_bytes(blk[o:o + 4], "little")
    secs = u32(HDR + 12)  # seconds on PSX and PC alike (matches the title's HH:MM)
    return {
        "locationID": u16(HDR),
        "saveCount": u16(HDR + 6),
        "gil": u32(HDR + 8),
        "playtime": f"{secs // 3600}:{secs % 3600 // 60:02d}",
        "level": blk[HDR + 16],
        "disc": u32(HDR + 68) + 1,
    }


def convert_block(blk: bytes) -> bytes:
    stored = int.from_bytes(blk[CRC_A:CRC_A + 2], "little")
    if checksum(blk) != stored:
        raise ValueError(f"stored CRC {stored:#06x} != computed "
                         f"{checksum(blk):#06x} (layout assumption broken)")
    out = bytearray(blk)
    out[ANALOG_OFF] = (out[ANALOG_OFF] & 0x80) | 100
    crc = checksum(out)
    out[CRC_A:CRC_A + 2] = crc.to_bytes(2, "little")
    out[CRC_B:CRC_B + 2] = crc.to_bytes(2, "little")
    comp = lzs_compress(bytes(out))
    if lzs_decompress(comp) != bytes(out):
        raise AssertionError("LZS roundtrip failed")
    return len(comp).to_bytes(4, "little") + comp


# ------------------------------------------------------------------ modes

def find_user_dir() -> Path:
    """The Steam save folder: Documents\\Square Enix\\FINAL FANTASY VIII
    Steam\\user_<steam id>. Honors FF8_SAVE_DIR, otherwise takes the first
    user_* folder under the (possibly OneDrive-redirected) Documents."""
    import os
    env = os.environ.get("FF8_SAVE_DIR")
    if env:
        return Path(env)
    roots = [Path.home() / "Documents", Path.home() / "OneDrive" / "Documents"]
    for root in roots:
        base = root / "Square Enix" / "FINAL FANTASY VIII Steam"
        users = sorted(base.glob("user_*")) if base.is_dir() else []
        if users:
            return users[0]
    raise SystemExit("no FF8 Steam save folder found — set FF8_SAVE_DIR")


def selftest(user_dir: Path | None = None) -> int:
    user_dir = user_dir or find_user_dir()
    ok = True
    for f in sorted(user_dir.glob("slot*_save*.ff8")):
        raw = f.read_bytes()
        size = int.from_bytes(raw[:4], "little")
        blk = lzs_decompress(raw[4:4 + size])
        stored = int.from_bytes(blk[CRC_A:CRC_A + 2], "little")
        stored2 = int.from_bytes(blk[CRC_B:CRC_B + 2], "little")
        calc = checksum(blk)
        rt = lzs_decompress(lzs_compress(blk)) == blk
        good = (len(blk) == BLOCK and blk[:2] == b"SC"
                and calc == stored == stored2 and rt)
        ok &= good
        print(f"{'PASS' if good else 'FAIL'} {f.name}: len={len(blk)} "
              f"magic={blk[:2]!r} crc calc={calc:#06x} "
              f"stored={stored:#06x}/{stored2:#06x} roundtrip={rt} "
              f"| {title_of(blk)} | {labels_of(blk)}")
    return 0 if ok else 1


def convert(in_dir: Path, out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for src in sorted(list(in_dir.glob("*.gme")) + list(in_dir.glob("*.mcr"))):
        card = card_image(src)
        if card is None:
            print(f"SKIP {src.name}: unrecognized container")
            continue
        comments = gme_comments(src)
        src_id = re.sub(r"[^0-9A-Za-z]+", "", src.stem.split(".")[-1]) or src.stem
        for b, blk in blocks(card):
            name = f"{src_id}-blk{b:02d}.ff8"
            try:
                payload = convert_block(blk)
            except (ValueError, AssertionError) as e:
                print(f"SKIP {src.name} blk{b:02d}: {e}")
                continue
            (out_dir / name).write_bytes(payload)
            lab = labels_of(blk)
            rows.append({"file": name, "source": src.name, "blk": b,
                         "title": title_of(blk), **lab,
                         "comment": comments[b]})
            print(f"OK   {name}  disc={lab['disc']} loc={lab['locationID']} "
                  f"time={lab['playtime']} lv={lab['level']}")
    index = out_dir / "index.csv"
    with index.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["file", "source", "blk", "title",
                                          "locationID", "disc", "playtime",
                                          "level", "gil", "saveCount",
                                          "comment"])
        w.writeheader()
        w.writerows(rows)
    print(f"\n{len(rows)} saves converted; index: {index}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "selftest":
        sys.exit(selftest(Path(sys.argv[2]) if len(sys.argv) > 2 else None))
    if len(sys.argv) == 4 and sys.argv[1] == "convert":
        sys.exit(convert(Path(sys.argv[2]), Path(sys.argv[3])))
    print(__doc__)
    sys.exit(2)
