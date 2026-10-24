"""Open the client window against a FAKE game and slot, to look at the FF8 tab
without FF8 or a server running. Nothing real is touched: memory is a
bytearray, nothing is sent, no sidecar or lock file is written.

Usage:  python tools\\gui_preview.py [--scenario idle|play|trouble]
                                    [--size 1120x720] [--shot out.png]
  idle     no game, no server (what a player sees on first launch)
  play     attached on the world map, connected, warps and locks in play
  trouble  play, plus a held save, a held story jump and a waiting DeathLink
--shot saves a picture of the window after a moment and exits; without it the
window stays open and the buttons run their commands against the fake.
--click LABEL presses the button with that label first (repeatable).
"""

import argparse
import asyncio
import os
import sys
import types
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "Archipelago"
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

import ModuleUpdate

ModuleUpdate.update_ran = True

parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
parser.add_argument("--scenario", choices=("idle", "play", "trouble"), default="play")
parser.add_argument("--size", default="", help="window size, e.g. 800x600")
parser.add_argument("--shot", default="", help="save a picture here and exit")
parser.add_argument("--click", action="append", default=[],
                    help="press the button with this label before the picture")
parser.add_argument("--scroll", type=float, default=1.0,
                    help="with --shot: how far down the controls are scrolled "
                         "(1 = top, 0 = bottom)")
opts = parser.parse_args()
sys.argv = sys.argv[:1]         # kivy and CommonClient read sys.argv too

import Utils  # noqa: E402
from NetUtils import NetworkItem, NetworkSlot, SlotType  # noqa: E402
from Utils import Version  # noqa: E402
from worlds.ff8 import memory  # noqa: E402
from worlds.ff8.client import (BASE_ID, ITEM_TABLE, LOCATION_TABLE,  # noqa: E402
                               FF8Context)
from worlds.ff8.test.test_vehicle_window import FakeProc  # noqa: E402

RECEIVED = ("Warp: Balamb", "Warp: Balamb Garden", "Warp: Dollet", "Warp: Timber",
            "Warp: Deling City", "Warp: Esthar", "Ragnarok")


class Detached(memory.FF8Interface):
    """Never finds the game."""

    def attach(self) -> bool:
        return False


def fake_context() -> FF8Context:
    ctx = FF8Context(None, None)
    ctx.save_sidecar = lambda: None
    if opts.scenario == "idle":
        ctx.ff8 = Detached()
        return ctx

    ctx.ff8 = ff8 = FakeProc()
    ctx.auth = "Wilson"
    ctx.slot, ctx.team = 1, 0
    ctx.server = types.SimpleNamespace(      # "connected", and sends go nowhere
        socket=types.SimpleNamespace(open=False, closed=True))
    ctx.server_address = "localhost:38281"
    ctx.save_fingerprint = zlib.crc32(b"preview:Wilson")
    ctx.slot_data = {"fast_travel": 1, "character_locks": 1, "junction_locks": 1,
                     "command_locks": 1, "ability_locks": 1, "vehicle_unlocks": 1}
    # What a real Connected leaves behind for the stock window and commands
    # (the "Server:" tooltip, /received, /missing) to read.
    ids = {d.name: BASE_ID + d.id_offset for d in ITEM_TABLE}
    locations = {loc.name: BASE_ID + loc.id_offset for loc in LOCATION_TABLE}
    ctx.item_names.update_game(ctx.game, ids)
    ctx.location_names.update_game(ctx.game, locations)
    ctx.player_names[1] = "Wilson"
    ctx.slot_info = {1: NetworkSlot("Wilson", ctx.game, SlotType.player)}
    ctx.server_version = Version(0, 6, 8)
    ctx.hint_cost, ctx.hint_points = 10, 21
    found_at = list(locations.values())
    ctx.checked_locations = set(found_at[:212])
    ctx.missing_locations = set(found_at[212:])
    ctx.server_locations = set(found_at)
    names = RECEIVED + tuple(d.name for d in ITEM_TABLE
                             if d.grant[0] in ("char", "junction"))[:7]
    ctx.items_received = [NetworkItem(ids[name], found_at[i], 1, 0)
                          for i, name in enumerate(names)]
    ctx.items_synced = True
    ctx.assist.oneshot = ctx.assist.enc = True
    ctx.assist.oneshots = 14

    ff8.write_u16(memory.MODULE_DISPATCH, memory.MODULE_WORLDMAP)
    ff8.write_u16(memory.GAME_MOMENT, 233)
    ff8.write_u16(memory.FIELD_ID, 157)
    ff8.write_u32(memory.GIL, 48250)
    ff8.write_u16(memory.AP_STATE_MAGIC_OFF, memory.AP_STATE_MAGIC)
    ff8.write_u32(memory.AP_STATE_FINGERPRINT_OFF, ctx.save_fingerprint)
    ff8.write_u16(memory.AP_STATE_APPLIED_OFF, len(ctx.items_received) - 2)

    if opts.scenario == "trouble":
        ctx.tags = ctx.tags | {"DeathLink"}
        ctx.pending_deathlink = True
        ctx.save_frozen = ("it would send 41 checks at once but was never part "
                           "of this campaign")
        ctx.story_hold = (20, 233)
    return ctx


async def main() -> None:
    ctx = fake_context()
    ctx.run_gui()
    if opts.size or opts.shot or opts.click:
        from kivy.clock import Clock
        from kivy.core.window import Window
        from kivymd.uix.button import MDButton

        def labelled(widget, label):
            text = getattr(widget, "_button_text", None)
            return isinstance(widget, MDButton) and text and text.text == label

        def click(label):
            for top in Window.children:         # a dialog sits above the app
                for widget in top.walk():
                    if labelled(widget, label):
                        widget.trigger_action(0.05)
                        return
            print(f"no button labelled {label!r}")

        def resize(_dt):
            width, height = opts.size.lower().split("x")
            Window.size = (int(width), int(height))

        def scroll(_dt):
            ctx.ui.ff8_panel.controls.scroll_y = opts.scroll

        def shoot(_dt):
            # kivy numbers the file it writes (name0001.png)
            os.replace(Window.screenshot(name=opts.shot), opts.shot)
            ctx.ui.stop()

        def script(*_):                         # timed from the first frame
            if opts.size:
                Clock.schedule_once(resize, 0.3)
            Clock.schedule_once(scroll, 1.0)
            for i, label in enumerate(opts.click):
                Clock.schedule_once(lambda _dt, label=label: click(label),
                                    1.5 + 0.5 * i)
            if opts.shot:
                Clock.schedule_once(shoot, 2.5 + 0.5 * len(opts.click))

        ctx.ui.bind(on_start=script)
    await ctx.exit_event.wait()
    ctx.server = None
    await ctx.ui_task


Utils.init_logging("FF8GuiPreview")
asyncio.run(main())
