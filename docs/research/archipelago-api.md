# Archipelago Developer API — Technical Report (current as of Aug 2026)

> Research report generated 2026-08-26 from the ArchipelagoMW/Archipelago repo docs and worked examples.

**Version context:** Latest stable release is **Archipelago 0.6.7** (2026-04-01); prior releases 0.6.6
(2026-01-19), 0.6.5 (2025-12-17), 0.6.4 (2025-11-07). Core supports **Python 3.11–3.13** (3.10 dropped
in 0.6.4). Sources: [GitHub releases](https://github.com/ArchipelagoMW/Archipelago/releases).

Primary sources read in full: `docs/world api.md`, `docs/adding games.md`, `docs/options api.md`,
`docs/apworld specification.md`, `docs/network protocol.md`, `docs/apworld_dev_faq.md`,
`docs/entrance randomization.md`, `CommonClient.py`; `worlds/kh2/` (main repo);
`worlds/ff12_open_world/` from [Bartz24/Archipelago@ff12_openworld](https://github.com/Bartz24/Archipelago/tree/ff12_openworld).

---

## 1. apworld structure (the World package)

A world is a Python package under `worlds/<game>/` whose `__init__.py` defines a subclass of
`worlds.AutoWorld.World`. AP auto-discovers it via the `AutoWorld` metaclass — no registration call
needed. One `World` instance is created **per player** per generated multiworld.

### Required members

```python
# worlds/mygame/__init__.py
import settings, typing
from worlds.AutoWorld import World, WebWorld
from BaseClasses import Region, Location, Item, ItemClassification

class MyGameItem(Item):
    game = "My Game"

class MyGameLocation(Location):
    game = "My Game"

class MyGameWorld(World):
    """Docstring becomes the game description on the AP website."""
    game = "My Game"                          # unique game name; must match client's Connect "game"
    options_dataclass = MyGameOptions         # dataclass of options (see below)
    options: MyGameOptions                    # type hint; instance auto-populated per player
    settings: typing.ClassVar[MyGameSettings] # host.yaml settings group (settings api.md)
    web = MyGameWeb()                         # WebWorld instance
    topology_present = True                   # show path in spoiler
    origin_region_name = "Menu"               # default; configurable since ~0.5.x

    base_id = 1234
    item_name_to_id = {name: id for id, name in enumerate(mygame_items, base_id)}
    location_name_to_id = {name: id for id, name in enumerate(mygame_locations, base_id)}
    item_name_groups = {"weapons": {"sword", "lance"}}
```

- **IDs**: must be unique per game, in range 1 to 2^53−1 (≤0 reserved); recommended to stay within
  32-bit. Items and locations may share IDs; names must be unique per game and non-numeric.
- **Item classifications** (`ItemClassification`): `progression`, `filler`, `useful`, `trap`,
  `skip_balancing`, `progression_skip_balancing`, plus newer `deprioritized` /
  `progression_deprioritized` / `progression_deprioritized_skip_balancing` (keeps currency/token
  progression off priority locations).
- **Hard requirements** per `docs/adding games.md`: unique `game` name; `WebWorld` instance with
  tutorials; `item_name_to_id`/`location_name_to_id`; `create_item`; at least one Region named
  `origin_region_name` ("Menu" by default — AP assumes the player can always return to it, e.g.
  save+quit); item count **equal** to location count in the itempool; and a completion condition:
  `self.multiworld.completion_condition[self.player] = lambda state: state.has("Victory", self.player)`.

### Generation lifecycle hooks (called in this order)

`stage_assert_generate(cls, multiworld)` → `generate_early(self)` (options/RNG available; earliest
setup) → `create_regions(self)` → `create_items(self)` (after this step regions/locations/items are
frozen) → `set_rules(self)` → `connect_entrances(self)` (**newer step**: all entrances must exist and
be connected by its end; generic ER goes here) → `generate_basic(self)` (non-logic randomization) →
`pre_fill` / `fill_hook` / `post_fill` (+ `get_pre_fill_items`) → `generate_output(self,
output_directory)` → `fill_slot_data(self)` and `modify_multidata(self, multidata)`. Any instance
method may have a `stage_`-prefixed classmethod that runs after all per-player instances finish.
0.6.7 also added `finalize_multiworld` and `pre_output` stages.

Regions/Entrances: `Region(name, player, multiworld)`, `region.add_locations({name: id},
MyGameLocation)`, `menu_region.connect(main_region)`, `main_region.add_exits({"Boss Room": "Boss
Door"}, {"Boss Room": lambda state: state.has("Sword", self.player)})`. Rules via
`worlds.generic.Rules`: `set_rule`, `add_rule`, `forbid_item`, `add_item_rule`; state helpers
`state.has(name, player, count)`, `has_any`, `has_all`, `has_group`, `count`, `can_reach_region`.
**Important caveat**: using `state.can_reach` inside an *entrance* access rule requires
`multiworld.register_indirect_condition(region, entrance)` (or `world.explicit_indirect_conditions =
False`). Events = item/location pairs with `id=None` + `place_locked_item()`; they exist only during
generation — goal completion at runtime is signaled via `StatusUpdate`, *not* "victory events".

### Options (`PerGameCommonOptions` dataclass — the current system)

The old `self.multiworld.option_name[self.player]` access is gone; options are a typed dataclass since
0.4.x and this is the only supported style now:

```python
# options.py
from dataclasses import dataclass
from Options import Toggle, Range, Choice, PerGameCommonOptions

class StartingSword(Toggle):
    """Adds a sword to your starting inventory."""
    display_name = "Start With Sword"

class Difficulty(Choice):
    """Sets overall game difficulty."""
    display_name = "Difficulty"
    option_easy = 0; option_normal = 1; option_hard = 2
    default = 1

@dataclass
class MyGameOptions(PerGameCommonOptions):
    starting_sword: StartingSword
    difficulty: Difficulty
```

Access via `self.options.difficulty` (compare to int/str/class attrs), raw value via `.value`, dict
export via `self.options.as_dict("difficulty", ...)` (use this in `fill_slot_data` — putting Option
*instances* in slot_data breaks multidata pickling, per `docs/apworld_dev_faq.md`). Option types:
`Toggle`, `DefaultOnToggle`, `Choice`, `TextChoice`, `Range`, `NamedRange` (`special_range_names`),
`FreeText`, `OptionDict` (+ `schema`), `OptionCounter`, `ItemDict`, `OptionList`, `OptionSet`,
`ItemSet`, `PlandoBosses`. Extras: `Visibility` IntFlag, `OptionGroup` lists on WebWorld,
`rich_text_doc`, aliases (`alias_x = option_y`), universal `random` value.

### WebWorld

`WebWorld` subclass carries webhost presentation: `tutorials` (list of `Tutorial`), `theme`,
`bug_report_page`, `options_presets` (dict of preset name → option dict), `option_groups`,
`rich_text_options_doc`, `location_descriptions`/`item_descriptions`, `game_info_languages`. Docs live
in `worlds/<game>/docs/` as `<lang>_<Game Name>.md` (game info) plus setup tutorials.

### Recent API changes worth knowing

- **`origin_region_name`** class attribute replaces hardcoded "Menu".
- **`connect_entrances`** lifecycle step + **Generic Entrance Randomization** (`entrance_rando.py`):
  call `randomize_entrances(world, coupled, get_target_groups)` inside `connect_entrances`; returns an
  `ERPlacementState` whose `pairings` you typically stash for slot_data.
- **`archipelago.json` manifest** (0.6.4+) — see §2.
- **`.apignore`**, apworlds importable via importlib, `finalize_multiworld`/`pre_output` (0.6.7).
- New **Rule Builder** (`docs/rule builder.md`) exists as an alternative declarative rules API.
- `worlds/apquest` is the maintained "reference/tutorial" world implementation.

---

## 2. Distribution of .apworld files

- An APWorld is either a folder in `worlds/` (source checkout) / `<install>/lib/worlds/` (installed),
  or a **zip archive named `<name>.apworld`** (all lowercase — uppercase breaks import in frozen
  Python 3.10+). The zip must contain a folder with the **same name** as the zip: `ror2.apworld` →
  `ror2/__init__.py`. Users install via the Launcher's **"Install APWorld"** component (or by dropping
  the file in `custom_worlds`).
- **Imports**: intra-world imports must be *relative* (`from .options import MyGameOptions`); imports
  from AP core must be *absolute* (`from Options import Toggle`). This is what makes zipped worlds work.
- **Dependencies**: `worlds/<game>/requirements.txt` is auto-installed by `ModuleUpdate.py` (e.g. KH2
  and FF12 both ship `Pymem>=1.10.0`). Pure-python deps can alternatively be vendored inside the
  apworld (Metroid Prime bundles `dolphin_memory_engine` inside its apworld).
- **Manifest (`archipelago.json`)** — since 0.6.4. In a world folder only `"game"` is required.
  Optional: `minimum_ap_version` / `maximum_ap_version` (compared against the running AP version to
  filter loading), `world_version` (`"major.minor.build"`; versionless is treated as older), `authors`
  (list, displayed on WebHost). Packaged .apworlds additionally carry `version`/`compatible_version`
  (APContainer packaging scheme from `worlds/Files.py`) — added automatically by the **"Build
  APWorlds" Launcher component** (source-only; also CLI: `Launcher.py "Build APWorlds" -- "Game
  Name"`, output in `build/apworlds`); never write them by hand. `.apignore` (gitignore syntax)
  excludes files from the build. Real examples: KH2 ships `{"game": "Kingdom Hearts 2",
  "minimum_ap_version": "0.6.3", "world_version": "2.0.0"}`.
- **Min-version practice**: set `minimum_ap_version` to the latest stable when you create the world;
  raise it only when you deliberately adopt a newer core feature. `maximum_ap_version` is rarely needed.
- **Merged vs. custom worlds**: worlds do **not** have to be merged into the main repo. The .apworld
  format explicitly exists "to package and ship an APWorld that is not part of the main distribution."
  Custom/unsupported worlds generate locally, and the generated output can be uploaded to
  archipelago.gg for room hosting — the server is game-agnostic; the only pitfall is putting
  unpicklable custom classes (Option instances, enums) into slot_data/multidata. FF12 Open World lives
  entirely out-of-repo in Bartz24's fork and is distributed as `.apworld` releases; same for Metroid
  Prime pre-merge.

---

## 3. Client architecture for native PC games via memory hooking

The canonical pattern for a native Windows game with no mod API is: **a Python client bundled inside
the apworld**, subclassing `CommonClient.CommonContext`, using **pymem** to attach to the process and
read/write memory, with an async "game watcher" loop. Two complete worked examples:

- **Kingdom Hearts 2** (main repo, `worlds/kh2/ClientStuff/Client.py` + `ReadAndWrite.py`,
  `SendChecks.py`, `RecieveItems.py`, `WorldLocations.py`) — hooks the KH2 process, pure pymem
  address-based read/write plus a companion Lua script for popups/death flag.
- **FF12 Open World** (custom apworld, `worlds/ff12_open_world/Client.py`) — hooks `FFXII_TZA`, reads
  memory for checks/state, but *grants* items by writing `items_received_####.txt` files consumed by
  the game's mod scripts (hybrid memory-read / file-write).

### Context subclass pattern

```python
class KH2Context(CommonContext):
    command_processor = KH2CommandProcessor      # ClientCommandProcessor subclass (/commands)
    game = "Kingdom Hearts 2"
    items_handling = 0b111                       # others + own world + starting inventory

    def __init__(self, server_address, password):
        super().__init__(server_address, password)
        self.kh2 = None                          # pymem.Pymem handle
        self.kh2connected = False

    async def server_auth(self, password_requested=False):
        await self.get_username()
        await self.send_connect()                # sends the Connect packet
```

Key `CommonContext` class attributes: `game`, `items_handling`, `tags` (default `{"AP"}`),
`want_slot_data` (default True). `CommonContext` already provides: websocket `server_loop` with
auto-reconnect, `send_msgs`, `check_locations()` helper (filters against `missing_locations` before
sending `LocationChecks`), datapackage caching (`ctx.item_names` / `ctx.location_names`),
`stored_data`/`set_notify`, DeathLink helpers, Kivy GUI (`run_gui`/`make_gui`) and CLI (`run_cli`).
Subclasses override `on_package(cmd, args)` for raw packet access and/or `on_deathlink`. FF12 also
subclasses `ClientCommandProcessor` to add commands like `/list_processes` and `/set_process_by_id`
(manual pymem attach fallback).

### Process hooking

```python
def find_game(self):
    if not self.ff12connected:
        try:
            self.ff12 = pymem.Pymem(process_name="FFXII_TZA")
            self.ff12connected = True
        except Exception:
            logger.info("Game is not open (Try running the client as an admin).")

# reads: self.ff12.read_bytes(self.ff12.base_address + offset, n)
```

KH2 detects the game build by reading a version signature string, and if unknown, downloads a JSON of
per-version memory addresses from a companion GitHub repo — a nice pattern for surviving game patches
without shipping a new apworld. FF12 snapshot-reads whole save-struct segments per tick into a state
cache to minimize `ReadProcessMemory` calls.

### The async game_watcher loop

Both clients run a polling coroutine next to `server_loop`, started in `launch()`:

```python
async def kh2_watcher(ctx: KH2Context):
    while not ctx.exit_event.is_set():
        try:
            if ctx.kh2connected and ctx.serverconnected:
                ctx.sending = []
                await ctx.checkWorldLocations()   # read flags/bitmasks -> ctx.sending
                await ctx.verifyItems()           # re-assert received items in memory
                await ctx.is_dead()               # DeathLink send detection
                if finishedGame(ctx) and not ctx.kh2_finished_game:
                    await ctx.send_msgs([{"cmd": "StatusUpdate", "status": ClientStatus.CLIENT_GOAL}])
                    ctx.kh2_finished_game = True
                if ctx.sending:
                    await ctx.send_msgs([{"cmd": "LocationChecks", "locations": ctx.sending}])
            elif not ctx.kh2connected and ctx.serverconnected:
                ...  # re-hook loop: retry pymem.Pymem(process_name=...) every 5s
        except Exception:
            ctx.kh2connected = False
        await asyncio.sleep(0.5)                  # ~2 Hz poll rate (FF12 identical)
```

### Location checks (detection → send)

Locations are detected by reading save/flag memory (chest bitmasks, level counters, treasure bit
arrays). FF12: each location has a `type`; treasure checks read a bit array indexed via slot_data's
`treasures` list; ids already in `self.locations_checked` are skipped, new ones are sent as one
`LocationChecks` packet, and the client guards against invalid game states (title screen, cutscene
maps) before trusting memory. `Connected`'s `checked_locations` seeds `locations_checked` so
previously-sent checks aren't resent; `RoomUpdate.checked_locations` merges server-side collects.

### Idempotent item granting (received-item index)

The server's `ReceivedItems` list is an ordered, append-only log; idempotency comes from persisting a
"last processed index":

- **KH2**: keeps `itemIndex` inside a per-seed-per-slot JSON save file
  (`%localappdata%\KH2AP\kh2save2<seed><slot>.json`, written on disconnect/shutdown). In
  `on_package("ReceivedItems")`: `index == 0` resets the cache (full inventory replay), and items are
  granted (direct memory writes) only when `start_index > itemIndex`. The watcher's `verifyItems()`
  continuously re-asserts amounts in memory, so re-grants are safe.
- **FF12**: stores the index *in the game's save file itself* (a counter maintained by the game mod),
  so items survive save reloads correctly and are never double-granted.
- The generic contract: any item may arrive any number of times, at any time, including while
  disconnected; the client must key off the guaranteed-ordered index, and must send never-repeatable
  location checks discovered offline on reconnect.

### DeathLink

Enable by adding the `DeathLink` tag (helper `ctx.update_death_link(bool)` sends `ConnectUpdate` when
toggled at runtime). Sending: `await ctx.send_death("PlayerX died to ...")` → a `Bounce` packet with
`tags: ["DeathLink"]` and `{time, source, cause}`. Receiving: override `on_deathlink(data)` — KH2
kills the player by writing a flag byte consumed per-frame.

### Slot data usage

`Connected.slot_data` (requested via `want_slot_data=True`) carries option results and seed-specific
layout the client needs. Fill it server-side in `fill_slot_data`. For item-on-location info, prefer
`LocationScouts` over bloating slot_data.

### Distribution / Launcher integration

The client ships **inside the apworld** and registers a Launcher component at world-import time:

```python
# worlds/kh2/__init__.py
from worlds.LauncherComponents import Component, components, icon_paths, Type, launch as launch_component

def launch_client():
    from .ClientStuff.Client import launch
    launch_component(launch, name="KH2Client")

icon_paths['kh2apicon'] = f"ap:{__name__}/data/khapicon.png"
components.append(Component("KH2 Client", func=launch_client, component_type=Type.CLIENT, icon='kh2apicon'))
```

FF12 uses `launch_subprocess(launch, name=...)` and adds `game_name="Final Fantasy 12 Open World",
supports_uri=True` so archipelago.gg room links can deep-launch the client. Component options:
`display_name`, `func`, `supports_uri`, `game_name`, `icon` (48x48), `description`,
`file_identifier`. The client's `launch()` builds the ctx, starts `server_loop`,
`run_gui()`/`run_cli()`, and the watcher task, then awaits `ctx.exit_event`. No separate exe is
needed; users install the .apworld and pick the client in the Launcher.

---

## 4. Key protocol concepts (`docs/network protocol.md`)

**Handshake:** WebSocket connect → server sends `RoomInfo` (seed_name, version, datapackage
checksums) → client optionally `GetDataPackage` → server `DataPackage` → client `Connect` → server
`Connected` or `ConnectionRefused` (`InvalidSlot`, `InvalidGame`, `IncompatibleVersion`,
`InvalidPassword`, `InvalidItemsHandling`; connection stays open for retry) → server may immediately
send queued `ReceivedItems`.

**Connect** args: `password`, `game`, `name` (slot name), `uuid`, `version` (`{"class": "Version",
major, minor, build}` for hand-rolled clients), `items_handling` (0b001 items from other worlds; 0b010
own-world items, requires 0b001; 0b100 starting inventory, requires 0b001 — memory-hook clients
typically use `0b111`), `tags`, `slot_data: bool`. `CommonContext.send_connect()` assembles this from
class attributes.

**Connected** returns: `team`, `slot`, `players`, **`missing_locations`** and **`checked_locations`**
(the authoritative server view — use these to avoid resending and to resume offline progress),
`slot_data`, `slot_info`, `hint_points`.

**ReceivedItems and index-based resume:** each packet carries `index` = position of its first item in
the slot's cumulative ordered item log, and `items: list[NetworkItem(item, location, player, flags)]`.
Rules: `index == 0` means "this is your entire inventory, replace everything"; if `index !=
len(local_list)` the client should resync (`Sync` packet, then re-send `LocationChecks` for everything
it has locally) but may still apply the items; otherwise append. The client must persist a "last
processed item index" (savegame, sidecar JSON, or in-game counter) and skip already-granted entries
after reconnect. `CommonClient.process_server_cmd` implements exactly this, and on `Connected` it
automatically replays `ctx.locations_checked` / `ctx.locations_scouted` and re-sends `StatusUpdate:
CLIENT_GOAL` if `ctx.finished_game` was set while disconnected — the built-in "nothing gets lost on
reconnect" mechanism.

**LocationChecks:** `{"cmd": "LocationChecks", "locations": [ids...]}` — duplicates are harmless
server-side; `CommonContext.check_locations()` additionally intersects with `missing_locations`
client-side. `RoomUpdate` delivers incremental `checked_locations` (e.g. coop partner on the same
slot, `!collect`). `LocationScouts` (`create_as_hint` 0/1/2) retrieves item info per location
(`LocationInfo` reply) for display purposes.

**Goal completion:** send `{"cmd": "StatusUpdate", "status": ClientStatus.CLIENT_GOAL}` (=30; enum
also has `CLIENT_UNKNOWN` 0, `CLIENT_CONNECTED` 5, `CLIENT_READY` 10, `CLIENT_PLAYING` 20). The server
sets CLIENT_CONNECTED automatically; the *client* is responsible for detecting the in-game goal (both
KH2 and FF12 detect it in the watcher by reading memory) and must guard with a local flag so it sends
once, plus `finished_game` for reconnect replay. Generation-time "victory events" are unrelated to
this runtime signal.

**Other essentials:** `Sync` (request full `ReceivedItems` re-send), `Bounce`/`Bounced` (tag- or
slot-targeted broadcast; DeathLink rides on it), `Get`/`Set`/`SetNotify`/`Retrieved`/`SetReply`
(server key-value data storage), `PrintJSON` (chat/item-send messages — KH2 parses `type ==
"ItemSend"` to build in-game popups), tags (`AP`, `DeathLink`, `Tracker`, `TextOnly`, `NoText`), and
the 16 MB max packet size / per-message compression notes.

---

## Practical takeaways for the FF8 apworld

1. Ship one package: world logic + `client.py` (CommonContext subclass) + `requirements.txt`
   (`Pymem>=1.10.0`) + `archipelago.json` (`game`, `authors`, `world_version`, `minimum_ap_version` =
   current stable, e.g. `0.6.7`), packaged with the "Build APWorlds" Launcher component; register a
   `Component(..., component_type=Type.CLIENT, game_name=..., supports_uri=True)`.
2. Follow the FF12/KH2 split: `on_package` handles `Connected`/`ReceivedItems`/`RoomUpdate` state
   mirroring; a 0.5 s `game_watcher` does memory polling, `LocationChecks`, idempotent item grants
   keyed on a persisted received-index (in-save counter is the most robust, per FF12), goal detection
   → `StatusUpdate(CLIENT_GOAL)`, and process re-hook on crash.
3. Keep slot_data to option results + layout the client can't get from `LocationScouts`; export via
   `self.options.as_dict(...)` only (plain JSON types).
