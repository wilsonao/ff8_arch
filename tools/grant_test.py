"""M2 write test: grant (or revoke) a GF on the RUNNING game by setting its unlock byte.

Usage (game open, on a field screen, NOT in a menu or battle):
    ..\\.venv\\Scripts\\python.exe grant_test.py                  # grant Leviathan
    ..\\.venv\\Scripts\\python.exe grant_test.py --gf Pandemona   # grant a specific GF
    ..\\.venv\\Scripts\\python.exe grant_test.py --gf Leviathan --clear   # undo
    ..\\.venv\\Scripts\\python.exe grant_test.py --dump-only      # just dump records

Only live memory is touched — reloading a save (without saving first) undoes everything.

After granting, open the in-game menu -> GF and check:
  1. Does the GF appear in the list?
  2. Does it have sane HP / level, or zeros?
  3. Can you junction it to a character and see junction abilities?
Report what you see — this decides whether the client needs a record template (M2 open
question #2 in docs/design.md).

The tool also hex-dumps the 0x44-byte savemap record of the target GF and of a
reference GF you already own, before and after the write, so we can diff what a
"real" acquisition initializes.
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ff8"))
import memory  # noqa: E402

GF_ORDER = [
    "Quezacotl", "Shiva", "Ifrit", "Siren",
    "Brothers", "Diablos", "Carbuncle", "Leviathan",
    "Pandemona", "Cerberus", "Alexander", "Doomtrain",
    "Bahamut", "Cactuar", "Tonberry", "Eden",
]


def record_offset(gf_index: int) -> int:
    return memory.GF_UNLOCK_BASE + gf_index * memory.GF_RECORD_STRIDE


def dump_record(ff8: memory.FF8Interface, gf_index: int, label: str) -> bytes:
    raw = ff8.read_bytes(record_offset(gf_index), memory.GF_RECORD_STRIDE)
    print(f"\n{label} — {GF_ORDER[gf_index]} record @ base+0x{record_offset(gf_index):X}:")
    for row in range(0, len(raw), 16):
        chunk = raw[row:row + 16]
        hexes = " ".join(f"{b:02X}" for b in chunk)
        print(f"  +0x{row:02X}: {hexes}")
    return raw


def main():
    parser = argparse.ArgumentParser(description="FF8 GF grant/revoke live-memory test")
    parser.add_argument("--gf", default="Leviathan", choices=GF_ORDER)
    parser.add_argument("--clear", action="store_true", help="revoke instead of grant")
    parser.add_argument("--dump-only", action="store_true", help="dump records, write nothing")
    args = parser.parse_args()
    gf_index = GF_ORDER.index(args.gf)

    ff8 = memory.FF8Interface()
    print(f"Waiting for {memory.PROCESS_NAME}...")
    while not ff8.attach():
        time.sleep(2)

    owned = [i for i in range(16) if ff8.gf_unlocked(i)]
    print(f"Currently unlocked: {', '.join(GF_ORDER[i] for i in owned) or '-'}")

    reference = next((i for i in owned if i != gf_index), None)
    if reference is not None:
        dump_record(ff8, reference, "REFERENCE (owned)")
    dump_record(ff8, gf_index, "TARGET (before)")

    if args.dump_only:
        return

    if not ff8.is_safe():
        print("\nGame is not in a safe state (menu/battle/title). Get on a field screen "
              "and re-run.")
        return

    if args.clear:
        ff8.set_gf_unlocked(gf_index, False)
        print(f"\nCleared {args.gf}'s unlock flag.")
    else:
        if gf_index in owned:
            print(f"\n{args.gf} is already unlocked — nothing to do "
                  "(use --clear to revoke, or pick another with --gf).")
            return
        ff8.set_gf_unlocked(gf_index, True)
        print(f"\nSet {args.gf}'s unlock flag.")

    dump_record(ff8, gf_index, "TARGET (after)")
    print(f"\nNow open the in-game menu -> GF and check {args.gf}: "
          "present? HP/level sane? junctionable? Then report back.\n"
          "Reload your save (without saving) to undo everything.")


if __name__ == "__main__":
    main()
