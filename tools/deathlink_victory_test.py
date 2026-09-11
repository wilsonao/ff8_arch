"""Live DeathLink race test (the dodge Hdot reported, 2026-09-10).

Watches the running game. On the first battle, the moment the engine enters
the victory phase (module 100/4) it sends a DeathLink from a probe
connection. Expected: the client defers it (the party leaves the battle
alive, the win is credited) and the SECOND battle is wiped by the client.
The verdict is read from the newest FF8Client log.

Run from the repo root with the server and the FF8 client already up:

    .venv/Scripts/python.exe tools/deathlink_victory_test.py --connect localhost:38281 --name Wilson

Then fight two battles (any random encounter). Takes as long as the fights.
"""

import asyncio
import glob
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "Archipelago"))
sys.path.insert(0, str(ROOT / "tools"))

import ModuleUpdate
ModuleUpdate.update_ran = True

from CommonClient import get_base_parser, server_loop  # noqa: E402
from worlds.ff8.memory import (FF8Interface, MODULE_DISPATCH, MODULE_BATTLE,  # noqa: E402
                               MODULE_BATTLE_WON, POST_BATTLE)
from deathlink_probe import ProbeContext  # noqa: E402

PENDING_LINE = "DeathLink: pending; applies to the next battle"
DELIVERED_LINE = "DeathLink: delivered (party wiped)"
TIMEOUT = 900.0


def newest_log() -> Path | None:
    logs = sorted(glob.glob(str(ROOT / "Archipelago" / "logs" / "FF8Client*.txt")),
                  key=os.path.getmtime)
    return Path(logs[-1]) if logs else None


def log_has(path: Path | None, needle: str, since: int) -> bool:
    if not path:
        return False
    data = path.read_text(encoding="utf-8", errors="replace")
    return needle in data[since:]


async def wait_for(pred, what, timeout=TIMEOUT):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if pred():
            return True
        await asyncio.sleep(0.05)
    print(f"[TEST] timeout waiting for {what}", flush=True)
    return False


async def main() -> int:
    parser = get_base_parser(description="FF8 DeathLink victory-phase race test")
    parser.add_argument("--name", default="Wilson")
    args = parser.parse_args()

    ff8 = FF8Interface()
    if not ff8.attach():
        print("[TEST] FF8 not running", flush=True)
        return 2
    log = newest_log()
    mark = len(log.read_text(encoding="utf-8", errors="replace")) if log else 0
    print(f"[TEST] client log: {log}", flush=True)

    ctx = ProbeContext(args.connect, args.password)
    ctx.auth = args.name
    ctx.server_task = asyncio.create_task(server_loop(ctx), name="server loop")
    if not await wait_for(lambda: bool(ctx.slot), "slot connection", 20):
        await ctx.shutdown()
        return 2
    print("[TEST] probe connected. Fight battle 1 now (win it).", flush=True)

    module = lambda: ff8.read_u16(MODULE_DISPATCH)  # noqa: E731
    in_battle = lambda: module() == MODULE_BATTLE or ff8.read_u8(POST_BATTLE) != 0  # noqa: E731

    if not await wait_for(lambda: module() == MODULE_BATTLE, "battle 1 start"):
        return 1
    print("[TEST] battle 1: combat. Waiting for the victory phase...", flush=True)
    if not await wait_for(lambda: module() in MODULE_BATTLE_WON, "battle 1 victory phase"):
        return 1
    await ctx.send_death("victory-phase race test")
    print(f"[TEST] death sent at module {module()} (victory phase)", flush=True)
    if not await wait_for(lambda: not in_battle(), "battle 1 end"):
        return 1
    await asyncio.sleep(2.0)
    log = newest_log()
    deferred = log_has(log, PENDING_LINE, mark)
    print(f"[TEST] battle 1 over. client deferred the death: {deferred}", flush=True)
    print("[TEST] Check the party is ALIVE on the field. Then fight battle 2.", flush=True)

    if not await wait_for(lambda: module() == MODULE_BATTLE, "battle 2 start"):
        return 1
    print("[TEST] battle 2: combat. Expecting the wipe...", flush=True)
    ok = await wait_for(lambda: log_has(newest_log(), DELIVERED_LINE, mark), "delivery", 120)
    print(f"[TEST] battle 2 wiped by the client: {ok}", flush=True)
    verdict = "PASS" if (deferred and ok) else "FAIL"
    print(f"[TEST] RESULT: {verdict} (deferred={deferred}, delivered={ok})", flush=True)
    await ctx.shutdown()
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
