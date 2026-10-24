"""What the client window's FF8 tab shows and runs, with no GUI toolkit in
sight (ff8/gui.py draws it; the tests read it directly).

The tab adds no behaviour of its own: every button is one of the slash
commands below, sent through the same command processor as typed input, so a
click can never do something the text client can't. `panel_state` reads the
context — and, while attached, a handful of live values — into a frozen
PanelState that the window redraws only when it changes.
"""

from dataclasses import dataclass

from . import memory
from .assist import FEATURES as ASSIST_FEATURES
from .client import (moment_true, read_save_state, received_warp_keys,
                     story_key_table, unlock_summary, warp_open)
from .warp import WARP_DESTINATIONS


@dataclass(frozen=True)
class Action:
    label: str
    command: str        # what a click sends to the command processor
    needs: str = ""     # "" always | "game" attached and readable | "server" connected
    confirm: str = ""   # asked before running; "" runs at once


# feature (assist.FEATURES order), button label, what it does
ASSIST_BUTTONS = (
    ("oneshot", "One Shot", "Random encounters die to the first hit"),
    ("atb", "ATB full", "A turn is always ready"),
    ("hp", "HP full", "Living allies are kept topped up"),
    ("enc", "No encounters", "Enc-None stays equipped"),
)
assert tuple(b[0] for b in ASSIST_BUTTONS) == ASSIST_FEATURES

LOOKUPS = (
    Action("Status", "/ff8"),
    Action("Unsent checks", "/ff8missed", needs="game"),
    Action("Magic ledger", "/ff8magic", needs="game"),
    Action("Story moment", "/ff8moment", needs="game"),
    Action("Warp list", "/ff8warp"),
    Action("Raw values", "/ff8verify", needs="game"),
)

MULTIWORLD = (
    Action("Received items", "/received", needs="server"),
    Action("Missing checks", "/missing", needs="server"),
    Action("My hints", "!hint", needs="server"),
    Action("Remaining items", "!remaining", needs="server"),
    Action("Players", "!players", needs="server"),
    Action("Team status", "!status", needs="server"),
    Action("Release", "!release", needs="server",
           confirm="Release sends every item still in your world to its "
                   "owner. It can't be undone."),
    Action("Collect", "!collect", needs="server",
           confirm="Collect brings in every item of yours still sitting in "
                   "other worlds. It can't be undone."),
)

ADOPT = Action(
    "Adopt this save", "/ff8adopt",
    confirm="Adopt the loaded save into this campaign? The checks it holds "
            "go out to the multiworld and can't be taken back. If this is "
            "the wrong save, load the right one instead.")
KEEP_STORY = Action(
    "Keep the jump", "/ff8keepstory",
    confirm="Send the held story checks and keep playing from here? Loading "
            "a save from before the jump is usually the better fix.")


def assist_command(feature: str | None, on: bool) -> str:
    """`feature` None = all four at once."""
    word = "on" if on else "off"
    return f"/ff8assist {feature} {word}" if feature else f"/ff8assist {word}"


def warp_command(key: str) -> str:
    return f"/ff8warp {key}"


def check_action(query: str) -> Action | None:
    """The rescue box's "Send check" button, or None while the box is empty."""
    query = " ".join(query.split())
    if not query:
        return None
    return Action("Send check", f"/ff8check {query}",
                  confirm=f"Send the check matching \"{query}\" by hand? It "
                          "goes out to the multiworld and can't be taken "
                          "back. Nothing is sent if the name fits no "
                          "unchecked location, or more than one.")


def moment_action(value: str) -> Action | None:
    """The rescue box's "Write moment" button, or None unless the box holds a
    16-bit number."""
    value = value.strip()
    if not value.isdecimal() or int(value) > 0xFFFF:
        return None
    return Action("Write moment", f"/ff8moment {int(value)}",
                  confirm=f"Write story moment {int(value)} into the running "
                          "game? This repairs a save that kept a vehicle "
                          "window's temporary value. Take the number from a "
                          "healthy save at the same point, and save the game "
                          "afterwards to keep it.")


@dataclass(frozen=True)
class Alert:
    text: str
    action: Action | None = None
    urgent: bool = True     # False = worth knowing, nothing to fix


@dataclass(frozen=True)
class WarpRow:
    key: str
    name: str
    enabled: bool       # on the world map, and the story has reached it


@dataclass(frozen=True)
class PanelState:
    server: str
    connected: bool
    game: str
    game_ok: bool                           # attached and readable
    detail: str
    tiles: tuple[tuple[str, str], ...]      # (caption, value)
    alerts: tuple[Alert, ...]
    assist: tuple[bool, ...]                # parallel to ASSIST_BUTTONS
    assist_note: str
    deathlink: bool
    warp_section: bool                      # the slot plays with warps at all
    warps: tuple[WarpRow, ...]
    warp_note: str
    unlocks: tuple[str, ...]

    def allows(self, action: Action) -> bool:
        return {"": True, "game": self.game_ok,
                "server": self.connected}[action.needs]


def game_mode(ff8) -> str:
    module = ff8.read_u16(memory.MODULE_DISPATCH)
    if module == memory.MODULE_TITLE:
        return "Title screen"
    if module == memory.MODULE_CARD_GAME:   # before POST_BATTLE: it pulses junk here
        return "Triple Triad"
    if (module == memory.MODULE_BATTLE or module in memory.MODULE_BATTLE_WON
            or ff8.read_u8(memory.POST_BATTLE)):
        return "Battle"
    if module == memory.MODULE_MENU or ff8.read_u8(memory.IN_MENU):
        return "Menu"
    if module == memory.MODULE_WORLDMAP:
        return "World map"
    if module == memory.MODULE_FIELD:
        return "Field"
    return f"Module {module}"


def _warps(ctx, game_ok: bool, mode: str) -> tuple[bool, tuple[WarpRow, ...], str]:
    if not ctx.slot_data.get("fast_travel") and not story_key_table(ctx):
        return False, (), ""
    unlocked = received_warp_keys(ctx)
    if not unlocked:
        return True, (), ("No destinations yet. Each \"Warp: <place>\" or "
                          "\"Key: <area>\" item you receive opens one.")
    ready = game_ok and mode == "World map"
    rows, later = [], []
    for dest in WARP_DESTINATIONS:
        if dest.key not in unlocked:
            continue
        reached = not game_ok or warp_open(ctx, dest)
        rows.append(WarpRow(dest.key, dest.name, ready and reached))
        if not reached:
            later.append(f"{dest.name} (the {dest.region} chapter)")
    notes = []
    if not game_ok:
        notes.append("Warps need the game running.")
    elif not ready:
        notes.append("Warps work from the world map, with no menu open.")
    if later:
        notes.append("Not open until the story gets there: " + ", ".join(later) + ".")
    return True, tuple(rows), " ".join(notes)


def panel_state(ctx) -> PanelState:
    connected = bool(ctx.server and ctx.slot)
    if connected:
        server = f"Connected as {ctx.auth}"
        if ctx.finished_game:
            server += " · goal complete"
    else:
        server = "Connecting…" if ctx.server else "Not connected to a multiworld"

    done = len(ctx.checked_locations)
    total = done + len(ctx.missing_locations)
    checks = f"{done}/{total}" if connected and total else "–"
    items = moment_text = mode = "–"
    game_ok = False
    unlocks: tuple[str, ...] = ()
    alerts = []

    if not ctx.ff8.attached:
        game = "Waiting for FF8_EN.exe"
        detail = "Start the game and the client hooks into it by itself."
        if ctx.attach_hint_logged:
            alerts.append(Alert(ctx.attach_hint_logged))
    else:
        try:
            mode = game_mode(ctx.ff8)
            moment = moment_true(ctx)
            field, gil = ctx.ff8.field_id(), ctx.ff8.gil()
            if connected:
                in_save = read_save_state(ctx)
                items = (f"{len(ctx.items_received)} waiting" if in_save is None
                         else f"{in_save}/{len(ctx.items_received)}")
                unlocks = tuple(unlock_summary(ctx, moment))
            warps = _warps(ctx, True, mode)
            game_ok = True
        except Exception:       # the process went away mid-read
            items = mode = "–"
            unlocks = ()
        if game_ok:
            game = "Attached to FF8"
            moment_text = str(moment)
            detail = f"Field {field} · {gil:,} gil"
            if ctx.moment_faked:
                detail += " · vehicle spawn window open"
            if not connected:
                detail += " · connect to a multiworld to start tracking"
        else:
            game = "Attached, but reads are failing"
            detail = "Did the game close? The client re-hooks by itself."

    if ctx.stood_down_logged:
        alerts.append(Alert(
            "Another FF8 client is already attached to the game, so this one "
            "is standing down. Close the other client to take over here."))
    if ctx.save_frozen:
        alerts.append(Alert(f"Holding this save: {ctx.save_frozen}", ADOPT))
    if ctx.story_hold:
        frm, to = ctx.story_hold
        alerts.append(Alert(
            f"Story jump held: the story moment went from {frm} to {to} in "
            f"one step. Story checks past {frm} wait until you load a save "
            "from before the jump.", KEEP_STORY))
    if ctx.pending_deathlink:
        alerts.append(Alert("A DeathLink is waiting: the party falls in the "
                            "next battle.", urgent=False))

    warp_section, warp_rows, warp_note = warps if game_ok else _warps(ctx, False, mode)
    shots = ctx.assist.oneshots
    return PanelState(
        server=server, connected=connected, game=game, game_ok=game_ok,
        detail=detail,
        tiles=(("Checks sent", checks), ("Items in this save", items),
               ("Story moment", moment_text), ("Game screen", mode)),
        alerts=tuple(alerts),
        assist=tuple(getattr(ctx.assist, f) for f in ASSIST_FEATURES),
        assist_note=(f"{shots} fight{'s' if shots != 1 else ''} one-shot this "
                     "session" if shots else ""),
        deathlink="DeathLink" in ctx.tags,
        warp_section=warp_section, warps=warp_rows, warp_note=warp_note,
        unlocks=unlocks,
    )
