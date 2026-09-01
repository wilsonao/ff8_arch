"""Arm the live self-test: wait for FF8 to be running with a save loaded on a
field screen (stable for a few polls), then run tools/live_selftest.py against
the local server and exit with its status. Meant to run in the background so
the whole live-test needs exactly one human action: launch the game and load a
save.

Usage:  python tools/await_selftest.py [--connect localhost:38281] [--name Wilson]
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))
import savemap_map as SM  # noqa: E402

M = SM.M
PY = ROOT / ".venv" / "Scripts" / "python.exe"
POLL = 3.0
STABLE_POLLS = 4          # ~12 s of continuous field-idle before firing
NOT_FIELD = {0, 2, 3, 4, 100}   # title/worldmap/battle/results/victory


def field_ready(ff8) -> bool:
    try:
        moment = ff8.game_moment()
        module = ff8.read_u16(M.MODULE_DISPATCH)
        return moment > 0 and ff8.is_safe() and module not in NOT_FIELD
    except Exception:
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--connect", default="localhost:38281")
    ap.add_argument("--name", default="Wilson")
    ap.add_argument("--skip-battle", action="store_true")
    args = ap.parse_args()

    ff8 = M.FF8Interface()
    print("[await] waiting for FF8_EN.exe ...", flush=True)
    while not ff8.attach():
        time.sleep(5)
    print("[await] attached; waiting for a loaded save idle on a field screen ...",
          flush=True)

    stable = 0
    while stable < STABLE_POLLS:
        time.sleep(POLL)
        if field_ready(ff8):
            stable += 1
        else:
            stable = 0
            if not ff8.attached or not ff8.attach():
                print("[await] lost the process; waiting for relaunch ...", flush=True)
                while not ff8.attach():
                    time.sleep(5)

    print(f"[await] field stable (moment={ff8.game_moment()}); "
          "extra 5 s grace for the client to attach, then running self-test",
          flush=True)
    time.sleep(5)

    cmd = [str(PY), str(TOOLS / "live_selftest.py"),
           "--connect", args.connect, "--name", args.name]
    if args.skip_battle:
        cmd.append("--skip-battle")
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    print(proc.stdout)
    if proc.stderr:
        print("--- selftest stderr ---")
        print(proc.stderr[-4000:])
    print(f"[await] selftest exited {proc.returncode}")
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
