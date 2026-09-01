"""Savemap capture / diff / watch — verify offsets without a playthrough.

The idea: load a save, capture the live savemap; do ONE thing (load a later
save, pass a SeeD test, remodel a weapon, kill Tonberry King from a
positioned save); capture again or watch live. The annotated byte diff shows
exactly which savemap bytes that event owns — confirming or refuting every
VERIFY offset in minutes instead of hours of play. Purely read-only.

Commands (run with the game open):
    python tools\\savemap_diff.py capture <label>      # snapshot -> output/snapshots/<label>.bin
    python tools\\savemap_diff.py diff <a> <b>          # annotated diff of two captures
    python tools\\savemap_diff.py watch [--baseline L]  # live: print annotated changes as they happen
    python tools\\savemap_diff.py list                  # captures with moment/field metadata

Typical VERIFY session ("does 0x18FE98B really tick when I pass a SeeD test?"):
    capture before  ->  take the test in-game  ->  watch (or capture after + diff)
    The change list names every offset that moved; look for seed_test_level.
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import savemap_map as SM  # noqa: E402

M = SM.M
SNAP_DIR = SM.ROOT / "output" / "snapshots"


def attach() -> "M.FF8Interface":
    ff8 = M.FF8Interface()
    if not ff8.attach():
        print(f"FATAL: {M.PROCESS_NAME} not running")
        sys.exit(1)
    return ff8


def read_all(ff8) -> bytes:
    return ff8.read_bytes(M.SAVEMAP_BASE, M.SAVEMAP_SIZE)


def meta(ff8) -> dict:
    return {"moment": ff8.game_moment(), "field": ff8.field_id(),
            "gil": ff8.gil(), "time": time.strftime("%Y-%m-%d %H:%M:%S")}


def print_diff(old: bytes, new: bytes, squelch_noise: bool = True):
    changes = 0
    i, n = 0, len(new)
    while i < n:
        if old[i] == new[i]:
            i += 1
            continue
        j = i
        while j < n and old[j] != new[j]:
            j += 1
        off = M.SAVEMAP_BASE + i
        if not (squelch_noise and all(M.SAVEMAP_BASE + k in SM.NOISY for k in range(i, j))):
            print(f"  0x{off:X}  {old[i:j].hex():>16} -> {new[i:j].hex():<16}"
                  f"  {SM.annotate(off)}")
            changes += 1
        i = j
    if not changes:
        print("  (no changes outside the always-ticking clock fields)")
    return changes


def cmd_capture(label: str):
    ff8 = attach()
    SNAP_DIR.mkdir(parents=True, exist_ok=True)
    buf = read_all(ff8)
    (SNAP_DIR / f"{label}.bin").write_bytes(buf)
    (SNAP_DIR / f"{label}.json").write_text(json.dumps(meta(ff8), indent=1), encoding="utf-8")
    print(f"Captured '{label}': moment={ff8.game_moment()} field={ff8.field_id()}")


def cmd_diff(a: str, b: str):
    old = (SNAP_DIR / f"{a}.bin").read_bytes()
    new = (SNAP_DIR / f"{b}.bin").read_bytes()
    for label in (a, b):
        m = json.loads((SNAP_DIR / f"{label}.json").read_text(encoding="utf-8"))
        print(f"{label}: moment={m['moment']} field={m['field']} ({m['time']})")
    print(f"--- {a} -> {b} ---")
    print_diff(old, new)


def cmd_watch(baseline: str | None):
    ff8 = attach()
    if baseline:
        prev = (SNAP_DIR / f"{baseline}.bin").read_bytes()
        print(f"Watching against capture '{baseline}'. Ctrl+C to stop.")
    else:
        prev = read_all(ff8)
        print("Watching live changes. Ctrl+C to stop.")
    seen: dict[int, int] = {}
    while True:
        time.sleep(0.3)
        try:
            cur = read_all(ff8)
        except Exception:
            print("Read failed — game closed?")
            return
        i, n = 0, len(cur)
        while i < n:
            if prev[i] == cur[i]:
                i += 1
                continue
            j = i
            while j < n and prev[j] != cur[j]:
                j += 1
            off = M.SAVEMAP_BASE + i
            noisy = all(M.SAVEMAP_BASE + k in SM.NOISY for k in range(i, j))
            seen[off] = seen.get(off, 0) + 1
            if not noisy and seen[off] <= 20:
                stamp = time.strftime("%H:%M:%S")
                extra = " (squelching further changes here)" if seen[off] == 20 else ""
                print(f"{stamp}  0x{off:X}  {prev[i:j].hex():>12} -> {cur[i:j].hex():<12}"
                      f"  {SM.annotate(off)}{extra}")
            i = j
        prev = cur


def cmd_list():
    if not SNAP_DIR.exists():
        print("No captures yet.")
        return
    for p in sorted(SNAP_DIR.glob("*.json")):
        m = json.loads(p.read_text(encoding="utf-8"))
        print(f"{p.stem:30} moment={m['moment']:>5} field={m['field']:>4}  {m['time']}")


def main():
    ap = argparse.ArgumentParser(description="FF8 savemap capture/diff/watch")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("capture"); p.add_argument("label")
    p = sub.add_parser("diff"); p.add_argument("a"); p.add_argument("b")
    p = sub.add_parser("watch"); p.add_argument("--baseline", default=None)
    sub.add_parser("list")
    args = ap.parse_args()
    if args.cmd == "capture":
        cmd_capture(args.label)
    elif args.cmd == "diff":
        cmd_diff(args.a, args.b)
    elif args.cmd == "watch":
        cmd_watch(args.baseline)
    else:
        cmd_list()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nDone.")
