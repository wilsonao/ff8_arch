"""DeathLink test probe for the FF8 apworld.

Connects to an Archipelago server as a SECOND connection on an existing slot
(trackers do the same, so this is allowed) with the DeathLink tag set, letting
you test the FF8 client's DeathLink handling without a second player:

  - received DeathLinks are printed as  [PROBE] DeathLink received ...
  - type  d  + Enter to send a death (the FF8 client should wipe the party)
  - type  q  + Enter to quit

Run from the repo root:

    .venv/Scripts/python.exe tools/deathlink_probe.py --connect localhost:38281 --name Wilson

Or pass --send-once to fire a single death and exit (for scripted tests).
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "Archipelago"))

import ModuleUpdate
ModuleUpdate.update_ran = True

from CommonClient import CommonContext, get_base_parser, server_loop  # noqa: E402


class ProbeContext(CommonContext):
    game = "Final Fantasy VIII"
    items_handling = 0b000  # never touch items from this connection

    def __init__(self, server_address, password):
        super().__init__(server_address, password)
        self.tags.add("DeathLink")

    async def server_auth(self, password_requested: bool = False):
        if password_requested and not self.password:
            await super().server_auth(password_requested)
        await self.get_username()
        await self.send_connect()

    def on_deathlink(self, data: dict) -> None:
        super().on_deathlink(data)
        print(f"[PROBE] DeathLink received from '{data.get('source', '?')}': "
              f"{data.get('cause', '(no cause)')}", flush=True)


async def main():
    parser = get_base_parser(description="FF8 DeathLink probe")
    parser.add_argument("--name", default=None, help="slot name to attach to")
    parser.add_argument("--send-once", action="store_true",
                        help="send one death, then exit")
    args = parser.parse_args()

    ctx = ProbeContext(args.connect, args.password)
    if args.name:
        ctx.auth = args.name
    ctx.server_task = asyncio.create_task(server_loop(ctx), name="server loop")

    # Wait for the slot connection.
    for _ in range(100):
        if ctx.slot:
            break
        await asyncio.sleep(0.2)
    if not ctx.slot:
        print("[PROBE] could not connect/authenticate in 20s", flush=True)
        await ctx.shutdown()
        return
    print(f"[PROBE] connected as '{ctx.auth}' with DeathLink tag", flush=True)

    if args.send_once:
        await ctx.send_death("Probe test death")
        print("[PROBE] death sent", flush=True)
        await asyncio.sleep(1)  # let the bounce flush
        await ctx.shutdown()
        return

    print("[PROBE] commands: d = send death, q = quit", flush=True)
    loop = asyncio.get_event_loop()
    while not ctx.exit_event.is_set():
        line = await loop.run_in_executor(None, sys.stdin.readline)
        if not line:  # stdin EOF (e.g. running detached): just listen forever
            await asyncio.sleep(3600)
            continue
        cmd = line.strip().lower()
        if cmd == "d":
            await ctx.send_death("Probe test death")
            print("[PROBE] death sent", flush=True)
        elif cmd == "q":
            break
    await ctx.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
