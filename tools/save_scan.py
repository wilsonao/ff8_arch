"""Offline savemap scanner — verify offsets against the SAVE LIBRARY, no game needed.

Every VERIFY item in docs/verification-plan.md Phase 3 is a savemap byte, and
F:\\ff8_saves\\library holds ~270 real saves spanning the whole game. A PC save
is u32 size + LZS(8192-byte block) whose MAIN section (block offset 464, 4944
bytes, Hyne SaveData.h) is the exact image the game loads to the live savemap
at memory.SAVEMAP_BASE — so  live_addr = SAVEMAP_BASE + (block_pos - 464)  and
every constant in ff8/memory.py can be read straight out of a save file.
Mapping cross-checked on gil (misc1+24), game_moment (field+0), koyok_quest
(worldmap+117) and cards_rare (ttcards+110).

Results 2026-08-31 (273 saves; details in docs/verification-plan.md):
  seal byte 0x18FEB06 is a BITMASK (popcount = seals broken); TT commons bit 7
  = "obtained once" (superset of qty>0, 0 violations); misc1.unlocked_weapons
  0x18FE750 = bit per weapon id ever made; dream byte bits 1-5 decoded (Odin,
  Phoenix, Gilgamesh, Angelo-disabled, Angel Wing; Gilgamesh clears Odin);
  tonberry flag = GF Tonberry on all legit saves; PuPu bit6 == misc2.ufo;
  Joker = var 475 bit 4 (matches Leviathan-card ownership 50/50); var 387 is
  the Laguna-dream-3 var (not the Winhill vase); vars 753-1023 zero everywhere.
  Stat-check pass (same day): LIMITB.zell innate mask 0x004F in all saves and
  learned bits strictly subset of Combat King ownership; magic_drawn_once bit
  = spell id - 1 (draw points count; no bits >= 56); char level = exp//1000+1
  (header "level" is the party average, NOT Squall's); steps/monster_kills/
  battle_escaped/tomberry_vaincus distributions -> the stat-ladder tiers.

Commands:
  table [DIRS...] [--csv OUT]      one row per save (sorted disc/moment/time)
                                    with every VERIFY field decoded
  dump FILE                        one save, every field, verbose
  diff FILE_A FILE_B               annotated savemap diff of two saves
                                    (offline twin of savemap_diff.py)
  vars LO HI [DIRS...]             per field-var: distinct values, #saves
                                    nonzero, earliest moment nonzero
  corr ADDR MASK [DIRS...] [--lo N --hi N]
                                    label saves by (u8(ADDR) & MASK) == MASK;
                                    rank vars by how well "nonzero" predicts
                                    the label (finds the byte a quest owns)
  check [DIRS...]                  invariants: CRC, header gil == main gil,
                                    AP state header zero, weapon ids in range

DIRS defaults to the library plus the user's save backups.
"""

import argparse
import csv
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import savemap_map as SM  # noqa: E402
import psx2steam as P  # noqa: E402

M = SM.M
ROOT = SM.ROOT
BLOCK_MAIN = P.MAIN_OFF                   # 464: MAIN starts here in the 8192 block
HDR = P.HDR
DEFAULT_DIRS = [Path(r"F:\ff8_saves\library"),
                Path(r"F:\ff8_save_backups")]
HYNE_DATA = ROOT / "thirdparty" / "hyne-src" / "src" / "Data.cpp"

MISC1 = M.SAVEMAP_BASE + (3188 - BLOCK_MAIN)
MISC2 = SM.MISC2_BASE
V = M.VAR_BLOCK                           # var N == misc3 + N (Hyne pos 3808)
TTCARDS = M.TT_CARDS
CHAR_ORDER = SM.CHAR_ORDER
WEAPON_RANGES = [(0, 6), (7, 10), (11, 14), (15, 18), (19, 23), (24, 27)]


def live_to_pos(addr: int) -> int:
    return addr - M.SAVEMAP_BASE + BLOCK_MAIN


def load_location_names() -> dict[int, str]:
    names: dict[int, str] = {}
    if HYNE_DATA.exists():
        text = HYNE_DATA.read_text(encoding="utf-8", errors="replace")
        for name, num in re.findall(r'QObject::tr\("([^"]+)",\s*"(\d+)"\)', text):
            names.setdefault(int(num), name)
    return names


LOC_NAMES = load_location_names()


class Save:
    def __init__(self, path: Path):
        self.path = path
        raw = path.read_bytes()
        if len(raw) == P.BLOCK and raw[:2] == b"SC":
            blk = raw
        else:
            size = int.from_bytes(raw[:4], "little")
            blk = P.lzs_decompress(raw[4:4 + size])
        if len(blk) != P.BLOCK or blk[:2] != b"SC":
            raise ValueError(f"{path.name}: not an FF8 save block")
        self.blk = blk
        stored = int.from_bytes(blk[P.CRC_A:P.CRC_A + 2], "little")
        self.crc_ok = P.checksum(blk) == stored
        self.loc_id = int.from_bytes(blk[HDR:HDR + 2], "little")
        self.save_count = int.from_bytes(blk[HDR + 6:HDR + 8], "little")
        self.hdr_gil = int.from_bytes(blk[HDR + 8:HDR + 12], "little")
        self.seconds = int.from_bytes(blk[HDR + 12:HDR + 16], "little")
        self.level = blk[HDR + 16]
        self.disc = int.from_bytes(blk[HDR + 68:HDR + 72], "little") + 1
        lib = path.parent.name
        self.src = "user" if lib.startswith("user_") else lib

    # --- reads addressed by LIVE module offset ---
    def u8(self, addr: int) -> int:
        return self.blk[live_to_pos(addr)]

    def u16(self, addr: int) -> int:
        p = live_to_pos(addr)
        return int.from_bytes(self.blk[p:p + 2], "little")

    def u32(self, addr: int) -> int:
        p = live_to_pos(addr)
        return int.from_bytes(self.blk[p:p + 4], "little")

    def bytes_at(self, addr: int, n: int) -> bytes:
        p = live_to_pos(addr)
        return self.blk[p:p + n]

    def var(self, n: int) -> int:
        return self.u8(V + n)

    def savemap(self) -> bytes:
        return self.blk[BLOCK_MAIN:BLOCK_MAIN + M.SAVEMAP_SIZE]

    # --- decoded fields ---
    @property
    def moment(self) -> int:
        return self.u16(M.GAME_MOMENT)

    @property
    def playtime(self) -> str:
        s = self.seconds
        return f"{s // 3600}:{s % 3600 // 60:02d}"

    @property
    def location(self) -> str:
        return LOC_NAMES.get(self.loc_id, f"loc{self.loc_id}")

    def weapons(self) -> list[int]:
        return [self.u8(M.CHAR_BASE + i * M.CHAR_STRIDE + M.CHAR_WEAPON_OFFSET)
                for i in range(6)]

    def commons(self) -> tuple[int, int, int]:
        """(#qty>0, #bit7 set, #disagreements) over the 77 common-card bytes."""
        raw = self.bytes_at(TTCARDS, M.TT_CARDS_COMMON)
        q = sum(1 for b in raw if b & 0x7F)
        e = sum(1 for b in raw if b & 0x80)
        x = sum(1 for b in raw if bool(b & 0x7F) != bool(b & 0x80))
        return q, e, x

    def rares(self) -> int:
        rb = self.bytes_at(M.CARDS_RARE, 5)
        return sum(b.bit_count() for b in rb[:4]) + (rb[4] & 0x01)

    def draws(self) -> int:
        raw = self.bytes_at(M.DRAW_POINTS, M.DRAW_POINTS_LEN)
        return sum(1 for b in raw for s in range(4) if (b >> (2 * s)) & 3)

    def popcount(self, addr: int, n: int) -> int:
        return sum(b.bit_count() for b in self.bytes_at(addr, n))

    def squall_level(self) -> int:
        return min(100, self.u32(M.SQUALL_EXP) // 1000 + 1)

    def level_sets(self) -> int:
        """How many of the 7 common-card level sets (11 cards each) are
        complete by the bit-7 'obtained once' flag."""
        return sum(1 for lvl in range(7)
                   if all(self.u8(M.TT_CARDS + lvl * 11 + i) & M.TT_CARD_SEEN
                          for i in range(11)))

    def gf_abilities_learned(self) -> int:
        """Abilities learned beyond each GF's default set, summed (0..244)."""
        total = 0
        for i in range(16):
            mask = int.from_bytes(self.bytes_at(M.gf_abilities_addr(i), 16), "little")
            total += max(0, mask.bit_count() - M.GF_ABILITY_DEFAULT_BITS[i])
        return total

    def gfs_mastered(self) -> int:
        """GFs knowing all 22 of their natural abilities."""
        from worlds.ff8.locations import GF_LEARN_LISTS  # lazy: heavy import
        n = 0
        for i, ids in enumerate(GF_LEARN_LISTS):
            mask = int.from_bytes(self.bytes_at(M.gf_abilities_addr(i), 16), "little")
            if all(mask >> a & 1 for a in ids):
                n += 1
        return n

    def row(self) -> dict:
        obel = self.bytes_at(V + 1398, 8)
        q, e, x = self.commons()
        return {
            "file": self.path.name, "src": self.src, "disc": self.disc,
            "loc": self.location, "moment": self.moment, "time": self.playtime,
            "lv": self.level, "gil": self.hdr_gil,
            "seal": f"{self.var(334):02X}", "seals": self.var(334).bit_count(),
            "cc": f"{self.var(477):02X}", "cc2": f"{self.var(475):02X}",
            "joker": int(bool(self.var(475) & 0x10)),
            "dlg1": f"{self.var(474):02X}", "dlg3": f"{self.var(476):02X}",
            "bgu_w": self.var(478),
            "queen": self.var(300), "q_loc": self.var(296),
            "pupu": f"{self.var(1397):02X}", "ufo": self.u32(M.UFO_KILLED),
            "obel": obel.hex(),
            "dream": f"{self.u8(M.DREAM_FLAGS):02X}",
            "tonb": self.u32(MISC2 + 24), "tonbK": self.u32(M.TONBERRY_KING_FLAG),
            "won2": self.u32(M.BATTLES_WON), "won3": self.u32(V + 20),
            "esc": self.u16(M.BATTLES_ESCAPED),
            "zell": f"{self.u16(M.ZELL_DUELS):04X}",
            "sq_lv": self.squall_level(),
            "magics": self.popcount(M.MAGIC_DRAWN, M.MAGIC_DRAWN_LEN),
            "scans": self.popcount(M.ENEMIES_SCANNED, M.ENEMIES_SCANNED_LEN),
            "steps": self.u32(M.STEPS), "mkills": self.u32(M.MONSTER_KILLS),
            "seed": self.u8(M.SEED_TEST_LEVEL), "seedExp": self.u16(V + 16),
            "tm": self.u16(M.TIMBER_MANIACS).bit_count(),
            "wpn": "/".join(str(w) for w in self.weapons()),
            "unlkW": f"{self.u32(MISC1 + 4):08X}",
            "rare": self.rares(), "com_q": q, "com_e": e, "com_x": x,
            "lvsets": self.level_sets(),
            "gfab": self.gf_abilities_learned(),
            "gfmast": self.gfs_mastered(),
            "rules": self.bytes_at(M.TT_RULES, 8).hex(),
            "draws": self.draws(),
            "choco": self.bytes_at(V + 616, 7).hex(),
            "shumi": self.bytes_at(V + 607, 17).hex(),
            "dream3": f"{self.var(387):02X}",   # Laguna dream 3 (Winhill) var, 0x1A once done
            "ap_hdr": self.bytes_at(V + 1000, 8).hex(),
            "crc": "ok" if self.crc_ok else "BAD",
        }


def iter_saves(paths: list[Path]):
    for p in paths:
        files = sorted(p.rglob("*.ff8")) if p.is_dir() else [p]
        for f in files:
            try:
                yield Save(f)
            except Exception as e:  # noqa: BLE001
                print(f"SKIP {f}: {e}", file=sys.stderr)


def load_all(dirs: list[str]) -> list[Save]:
    paths = [Path(d) for d in dirs] if dirs else DEFAULT_DIRS
    saves = list(iter_saves(paths))
    saves.sort(key=lambda s: (s.disc, s.moment, s.seconds))
    return saves


# ------------------------------------------------------------------ commands

def cmd_table(args):
    saves = load_all(args.dirs)
    rows = [s.row() for s in saves]
    cols = list(rows[0].keys()) if rows else []
    widths = {c: max(len(c), *(len(str(r[c])) for r in rows)) for c in cols}
    print(" ".join(c.ljust(widths[c]) for c in cols))
    for r in rows:
        print(" ".join(str(r[c]).ljust(widths[c]) for c in cols))
    print(f"\n{len(rows)} saves")
    if args.csv:
        out = Path(args.csv)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
        print(f"csv: {out}")


def cmd_dump(args):
    s = Save(Path(args.file))
    for k, v in s.row().items():
        print(f"{k:>8}: {v}")
    print("\n-- per-character weaponID / exists / exp --")
    for i, ch in enumerate(CHAR_ORDER):
        base = M.CHAR_BASE + i * M.CHAR_STRIDE
        print(f"  {ch:8} weapon={s.u8(base + 0x09):3d} exists={s.u8(base + 0x94):3d} "
              f"exp={s.u32(base + 4)}")
    print("\n-- GF unlock bytes --")
    print("  " + " ".join(f"{gf}={s.u8(M.GF_UNLOCK_BASE + i * M.GF_RECORD_STRIDE)}"
                         for i, gf in enumerate(SM.GF_ORDER)))
    print("\n-- field vars 256..1023 nonzero --")
    nz = [(n, s.var(n)) for n in range(256, 1024) if s.var(n)]
    print("  " + " ".join(f"{n}={v:02X}" for n, v in nz))
    print("\n-- worldmap vars 1280..1407 nonzero --")
    nz = [(n, s.var(n)) for n in range(1280, 1408) if s.var(n)]
    print("  " + " ".join(f"{n}={v:02X}" for n, v in nz))


def cmd_diff(args):
    a, b = Save(Path(args.a)), Save(Path(args.b))
    print(f"A: {a.path.name}  disc {a.disc} moment {a.moment} {a.location} {a.playtime}")
    print(f"B: {b.path.name}  disc {b.disc} moment {b.moment} {b.location} {b.playtime}")
    old, new = a.savemap(), b.savemap()
    i, n, changes = 0, len(new), 0
    while i < n:
        if old[i] == new[i]:
            i += 1
            continue
        j = i
        while j < n and old[j] != new[j] and j - i < 16:
            j += 1
        off = M.SAVEMAP_BASE + i
        print(f"  +0x{off:X} {SM.annotate(off)}: "
              f"{old[i:j].hex()} -> {new[i:j].hex()}")
        changes += j - i
        i = j
    print(f"{changes} bytes differ")


def cmd_vars(args):
    saves = load_all(args.dirs)
    print(f"{len(saves)} saves; var range {args.lo}..{args.hi}")
    print(f"{'var':>5} {'live':>10} {'#nz':>4} {'#val':>4} {'1st disc/moment':>16}"
          f"  values(count)  first saves")
    for v in range(args.lo, args.hi + 1):
        vals = Counter(s.var(v) for s in saves)
        nz = [s for s in saves if s.var(v)]
        if args.nonzero and not nz:
            continue
        first = f"{nz[0].disc}/{nz[0].moment}" if nz else "-"
        top = " ".join(f"{k:02X}({c})" for k, c in vals.most_common(6))
        names = " ".join(s.path.name for s in nz[:3])
        print(f"{v:>5} 0x{V + v:X} {len(nz):>4} {len(vals):>4} {first:>16}  {top}  {names}")


def cmd_corr(args):
    saves = load_all(args.dirs)
    addr, mask = int(args.addr, 0), int(args.mask, 0)
    pos = [s for s in saves if (s.u8(addr) & mask) == mask]
    neg = [s for s in saves if (s.u8(addr) & mask) != mask]
    print(f"label: (u8(0x{addr:X}) & 0x{mask:02X}) == mask -> "
          f"{len(pos)} positive / {len(neg)} negative saves")
    print("positives: " + " ".join(s.path.name for s in pos))
    results = []
    for v in range(args.lo, args.hi + 1):
        p_nz = sum(1 for s in pos if s.var(v))
        n_nz = sum(1 for s in neg if s.var(v))
        if p_nz == 0:
            continue
        results.append((p_nz / max(len(pos), 1), -n_nz, v, p_nz, n_nz))
    results.sort(reverse=True)
    print(f"\n{'var':>5} {'live':>10} {'nz in pos':>10} {'nz in neg':>10}  pos values")
    for _, _, v, p_nz, n_nz in results[:args.top]:
        vals = Counter(s.var(v) for s in pos)
        print(f"{v:>5} 0x{V + v:X} {p_nz:>4}/{len(pos):<5} {n_nz:>4}/{len(neg):<5}  "
              + " ".join(f"{k:02X}({c})" for k, c in vals.most_common(5)))


def cmd_check(args):
    saves = load_all(args.dirs)
    bad = 0
    for s in saves:
        probs = []
        if not s.crc_ok:
            probs.append("crc")
        if s.u32(M.GIL) != s.hdr_gil:
            probs.append(f"gil main={s.u32(M.GIL)} hdr={s.hdr_gil}")
        if any(s.bytes_at(V + 1000, 8)):
            probs.append(f"ap_hdr={s.bytes_at(V + 1000, 8).hex()}")
        nz = [n for n in range(753, 1024) if s.var(n)]
        if nz:
            probs.append(f"free-vars nonzero: {nz[:8]}")
        for i, (lo, hi) in enumerate(WEAPON_RANGES):
            w = s.weapons()[i]
            if not lo <= w <= hi:
                probs.append(f"{CHAR_ORDER[i]} weapon {w} outside {lo}-{hi}")
        zell = s.u16(M.ZELL_DUELS)
        if (zell & 0x004F) != 0x004F or zell & ~0x03FF:
            probs.append(f"zell duel mask 0x{zell:04X} (innate 0x004F should be "
                         "set, nothing past bit 9)")
        if s.popcount(M.MAGIC_DRAWN + 7, 1):
            probs.append("magic_drawn_once byte 7 nonzero (no spell ids > 56)")
        if probs:
            bad += 1
            print(f"{s.path.name}: " + "; ".join(probs))
    print(f"{len(saves)} saves checked, {bad} with findings")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("table")
    t.add_argument("dirs", nargs="*")
    t.add_argument("--csv")
    d = sub.add_parser("dump")
    d.add_argument("file")
    f = sub.add_parser("diff")
    f.add_argument("a")
    f.add_argument("b")
    v = sub.add_parser("vars")
    v.add_argument("lo", type=int)
    v.add_argument("hi", type=int)
    v.add_argument("dirs", nargs="*")
    v.add_argument("--nonzero", action="store_true")
    c = sub.add_parser("corr")
    c.add_argument("addr")
    c.add_argument("mask")
    c.add_argument("dirs", nargs="*")
    c.add_argument("--lo", type=int, default=256)
    c.add_argument("--hi", type=int, default=1407)
    c.add_argument("--top", type=int, default=25)
    k = sub.add_parser("check")
    k.add_argument("dirs", nargs="*")
    args = ap.parse_args()
    {"table": cmd_table, "dump": cmd_dump, "diff": cmd_diff, "vars": cmd_vars,
     "corr": cmd_corr, "check": cmd_check}[args.cmd](args)


if __name__ == "__main__":
    main()
