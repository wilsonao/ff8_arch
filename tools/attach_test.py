"""Standalone smoke test: attach to FF8_EN.exe and read live state.

Run with the game open (any loaded save, on a field screen):
    f:\\ff8_arch\\.venv\\Scripts\\python.exe f:\\ff8_arch\\tools\\attach_test.py

Loops until the process is found, then prints gil / game moment / field ID / safe-state
once per second, plus GF unlock flags. Ctrl+C to stop. Purely read-only.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# memory.py imports nothing from Archipelago, so we can load it directly from the
# package sources without an AP environment.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ff8"))
import memory  # noqa: E402

GF_ORDER = [
    "Quezacotl", "Shiva", "Ifrit", "Siren",
    "Brothers", "Diablos", "Carbuncle", "Leviathan",
    "Pandemona", "Cerberus", "Alexander", "Doomtrain",
    "Bahamut", "Cactuar", "Tonberry", "Eden",
]


def main():
    ff8 = memory.FF8Interface()
    print(f"Waiting for {memory.PROCESS_NAME}...")
    while not ff8.attach():
        time.sleep(2)

    last_moment = None
    while True:
        try:
            moment = ff8.game_moment()
            unlocked = [GF_ORDER[i] for i in range(16) if ff8.gf_unlocked(i)]
            line = (f"gil={ff8.gil():>8}  moment={moment:>5}  field={ff8.field_id():>4}  "
                    f"safe={ff8.is_safe()!s:5}  GFs={','.join(unlocked) or '-'}")
            if moment != last_moment:
                print(f"\n[game moment changed -> {moment}]")
                last_moment = moment
            print(line, end="\r", flush=True)
        except Exception as e:
            print(f"\nRead failed ({type(e).__name__}) — game closed? Re-attaching...")
            ff8.detach()
            while not ff8.attach():
                time.sleep(2)
        time.sleep(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nDone.")
