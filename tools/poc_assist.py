"""Drive Battle Assist against the running game with no AP server: the same
apply_assist the client runs, plus a per-tick trace of the slot structs so a
live check shows exactly what the engine did with the writes.

Usage (from the repo root, game running):

    .venv\\Scripts\\python.exe tools\\poc_assist.py [--oneshot] [--atb] [--hp] [--watch]

With no feature flags all three are on. --watch writes nothing and only
traces (module, encounter, ally/enemy HP and ATB) — run it first to see a
fight's natural timeline, then again with the features on.
"""

import argparse
import logging
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "Archipelago"
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

import ModuleUpdate  # noqa: E402

ModuleUpdate.update_ran = True

from worlds.ff8 import memory  # noqa: E402
from worlds.ff8.assist import AssistState, apply_assist, encounter_name, oneshot_verdict  # noqa: E402

POLL = 0.25


def snapshot(ff8: memory.FF8Interface) -> tuple:
    module = ff8.read_u16(memory.MODULE_DISPATCH)
    post = ff8.read_u8(memory.POST_BATTLE)
    enc = ff8.encounter_id()
    allies = []
    for i in range(memory.ALLY_COUNT):
        rec = memory.BATTLE_ALLIES + i * memory.ALLY_STRIDE
        allies.append((ff8.read_u32(rec + memory.SLOT_CUR_HP),
                       ff8.read_u32(rec + memory.SLOT_MAX_HP),
                       ff8.read_u32(rec + memory.SLOT_ATB_CUR)))
    enemies = []
    for i in range(memory.ENEMY_COUNT):
        rec = memory.BATTLE_ENEMIES + i * memory.ENEMY_STRIDE
        enemies.append((ff8.read_u32(rec + memory.SLOT_CUR_HP),
                        ff8.read_u32(rec + memory.SLOT_MAX_HP),
                        ff8.read_u32(rec + 4)))          # status word
    return module, post, enc, tuple(allies), tuple(enemies)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--oneshot", action="store_true")
    ap.add_argument("--atb", action="store_true")
    ap.add_argument("--hp", action="store_true")
    ap.add_argument("--watch", action="store_true", help="trace only, write nothing")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s",
                        datefmt="%H:%M:%S")
    state = AssistState()
    if not args.watch:
        if not (args.oneshot or args.atb or args.hp):
            args.oneshot = args.atb = args.hp = True
        state.oneshot, state.atb, state.hp = args.oneshot, args.atb, args.hp
    print(f"assist: {state.describe()}{' (watch only)' if args.watch else ''}; Ctrl+C to stop")

    ff8 = memory.FF8Interface()
    while not ff8.attach():
        print("waiting for FF8_EN.exe...")
        time.sleep(2)
    last = None
    try:
        while True:
            snap = snapshot(ff8)
            if snap != last:
                module, post, enc, allies, enemies = snap
                verdict = oneshot_verdict(enc)
                print(f"module={module} post={post} enc={enc} "
                      f"[{encounter_name(enc)}: "
                      f"{'random' if verdict is None else verdict}] "
                      f"allies={allies} enemies={enemies}")
                last = snap
            if not args.watch:
                apply_assist(ff8, state, snap[2])
            time.sleep(POLL)
    except KeyboardInterrupt:
        print(f"\nstopped; {state.oneshots} fights one-shot")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
