"""Final Fantasy VIII Archipelago world (Steam 2013 PC version).

The story plays out vanilla; the game's reward moments (GF acquisitions, story/boss
beats, unique item handouts) become multiworld checks, and the bundled memory-hook
client suppresses vanilla rewards and delivers the multiworld's items instead.
"""

import json
import pkgutil
from typing import Any, ClassVar

from BaseClasses import ItemClassification, LocationProgressType, Region, Tutorial
from worlds.AutoWorld import WebWorld, World
from worlds.generic.Rules import set_rule
from worlds.LauncherComponents import Component, Type, components, launch_subprocess

from .items import (DEFAULT_FILLER, FILLER_TABLE, FILLER_WEIGHTS,
                    FILLER_WEIGHTS_CHECKS_ONLY, GAME_NAME, GF_ORDER,
                    ITEM_DATA_BY_NAME, ITEM_TABLE, STARTER_MAGIC, TRAP_TABLE,
                    TRAP_WEIGHTS, FF8Item, item_name_groups, item_name_to_id)
from .locations import (LOCATION_DATA_BY_NAME, LOCATIONS_BY_GROUP,
                        FF8Location, location_name_groups, location_name_to_id)
from .options import FF8Options, OPTION_GROUPS, OPTION_PRESETS

# Story-ordered region chain; entering region N+1 requires the "Cleared: N" event.
REGION_CHAIN = [
    "Balamb Prologue", "Fire Cavern", "Dollet Exam", "SeeD",
    "Timber", "Galbadia", "Disc 2", "Disc 3", "Disc 4",
]


def _notify_client_starting():
    """Tell the Launcher user the click worked. The spawned client re-imports
    every installed world before its window appears (tens of seconds on a cold
    antivirus cache), and the WebHost link's client-picker dialog gives no
    feedback of its own, so a silent gap here reads as "nothing happened".
    Best-effort: purely cosmetic, must never block or fail the launch."""
    try:
        from Utils import is_kivy_running
        if not is_kivy_running():
            return
        from kivy.metrics import dp
        from kivymd.uix.snackbar import MDSnackbar, MDSnackbarText
        MDSnackbar(
            MDSnackbarText(text="FF8 Client is starting — its window can take a minute to appear."),
            y=dp(24), pos_hint={"center_x": 0.5}, size_hint_x=0.8,
        ).open()
    except Exception:
        pass


def launch_client(*args):
    _notify_client_starting()
    try:
        from .client import launch
        launch_subprocess(launch, name="FF8Client", args=args)
    except Exception:
        # A failure here is otherwise invisible: the Launcher swallows it and
        # the click just "does nothing". Surface it and keep it in the log.
        import logging
        import traceback
        logging.exception("FF8 Client failed to start")
        try:
            from Utils import messagebox
            messagebox("FF8 Client failed to start", traceback.format_exc(), error=True)
        except Exception:
            pass
        raise


components.append(Component(
    "FF8 Client", func=launch_client, component_type=Type.CLIENT,
    game_name=GAME_NAME, supports_uri=True,
    description="Client for Final Fantasy VIII (Steam 2013)",
))


class FF8Web(WebWorld):
    theme = "ocean"
    option_groups = OPTION_GROUPS
    options_presets = OPTION_PRESETS
    tutorials = [Tutorial(
        "Setup Guide",
        "A guide to setting up Final Fantasy VIII for Archipelago.",
        "English", "setup_en.md", "setup/en", ["ff8_arch"],
    )]


def _ut_name_mapping() -> dict[str, int]:
    """Universal Tracker node/section -> AP location id (generated alongside
    the PopTracker pack by tools/gen_tracker_pack.py)."""
    try:
        raw = pkgutil.get_data(__name__, "tracker/ut_name_mapping.json")
    except (OSError, ImportError):
        raw = None
    return json.loads(raw.decode("utf-8")) if raw else {}


class FF8World(World):
    """Final Fantasy VIII follows SeeD mercenary Squall Leonhart against the sorceress
    Ultimecia. Guardian Forces, key items, and story rewards are shuffled into the
    multiworld; junction what the multiworld gives you and finish the war."""

    game = GAME_NAME
    web = FF8Web()
    options_dataclass = FF8Options
    options: FF8Options
    topology_present = True

    # --- Universal Tracker (FarisTheAncient) integration ---
    # Regenerates from slot data alone (every option that shapes the world is
    # in fill_slot_data and re-applied in generate_early), and shows the
    # PopTracker pack's three maps (world / region board / GF abilities) as
    # UT map pages straight from the apworld package.
    ut_can_gen_without_yaml = True
    tracker_world: ClassVar[dict[str, Any]] = {
        "map_page_folder": "tracker",
        "map_page_maps": "maps/maps.json",
        "map_page_locations": "locations/locations.json",
        "poptracker_name_mapping": _ut_name_mapping(),
    }

    @staticmethod
    def interpret_slot_data(slot_data: dict[str, Any]) -> dict[str, Any]:
        return slot_data

    def generate_early(self) -> None:
        passthrough = getattr(self.multiworld, "re_gen_passthrough", None)
        if passthrough and self.game in passthrough:
            # UT regeneration: our slot data IS the option dict.
            for key, value in passthrough[self.game].items():
                option = getattr(self.options, key, None)
                if option is not None and hasattr(type(option), "from_any"):
                    setattr(self.options, key, type(option).from_any(value))

    item_name_to_id = item_name_to_id
    location_name_to_id = location_name_to_id
    item_name_groups = item_name_groups
    location_name_groups = location_name_groups

    def create_item(self, name: str) -> FF8Item:
        data = ITEM_DATA_BY_NAME[name]
        return FF8Item(name, data.classification, item_name_to_id[name], self.player)

    def create_event(self, name: str) -> FF8Item:
        return FF8Item(name, ItemClassification.progression, None, self.player)

    def create_regions(self) -> None:
        menu = Region("Menu", self.player, self.multiworld)
        self.multiworld.regions.append(menu)

        enabled_groups = ["core"]
        if self.options.draw_point_checks:
            enabled_groups.append("draw")
        if self.options.world_draw_point_checks:
            enabled_groups.append("world_draw")
        if self.options.triple_triad_checks:
            enabled_groups.append("tt")
        if self.options.optional_boss_checks:
            enabled_groups.append("boss_extra")
        if self.options.rare_card_checks:
            enabled_groups.append("cards")
        if self.options.sidequest_checks:
            enabled_groups.append("sidequest")
        if self.options.magazine_checks:
            enabled_groups.append("magazine")
        if self.options.stat_checks:
            enabled_groups.append("stats")
        if self.options.gf_ability_checks:
            enabled_groups.append("abilities")

        regions: dict[str, Region] = {}
        for region_name in REGION_CHAIN:
            region = Region(region_name, self.player, self.multiworld)
            regions[region_name] = region
            self.multiworld.regions.append(region)
            loc_names = [name for group in enabled_groups
                         for name in LOCATIONS_BY_GROUP.get(group, {}).get(region_name, [])]
            for loc_name in loc_names:
                region.add_locations({loc_name: location_name_to_id[loc_name]}, FF8Location)
                if LOCATION_DATA_BY_NAME[loc_name].missable:
                    # One-window draw points only ever hold filler; a missed
                    # sparkle must never strand another world's progression.
                    self.get_location(loc_name).progress_type = LocationProgressType.EXCLUDED

        # Story-gate events: "Cleared: X" sits in X and unlocks the next region.
        for region_name in REGION_CHAIN[:-1]:
            event = FF8Location(self.player, f"Cleared: {region_name}", None, regions[region_name])
            event.place_locked_item(self.create_event(f"Cleared: {region_name}"))
            regions[region_name].locations.append(event)

        goal_event = ("Omega Weapon Defeated" if self.options.goal == "omega"
                      else "Ultimecia Defeated")
        victory = FF8Location(self.player, goal_event, None, regions["Disc 4"])
        victory.place_locked_item(self.create_event("Victory"))
        regions["Disc 4"].locations.append(victory)

        menu.connect(regions[REGION_CHAIN[0]])
        for prev, nxt in zip(REGION_CHAIN, REGION_CHAIN[1:]):
            rule = (lambda state, p=prev: state.has(f"Cleared: {p}", self.player))
            if nxt == "Disc 3":
                gf_count = self.options.gfs_required_for_disc3.value
                rule = (lambda state, p=prev, n=gf_count:
                        state.has(f"Cleared: {p}", self.player)
                        and state.has_group("GFs", self.player, n))
            regions[prev].connect(regions[nxt], rule=rule)

        self.multiworld.completion_condition[self.player] = \
            lambda state: state.has("Victory", self.player)

    def create_items(self) -> None:
        pool_names = [d.name for d in ITEM_TABLE
                      if d.name not in {f.name for f in FILLER_TABLE}
                      and d.name not in {t.name for t in TRAP_TABLE}]

        gf_names = sorted(item_name_groups["GFs"])
        for gf in self.random.sample(gf_names, self.options.starting_gfs.value):
            pool_names.remove(gf)
            self.multiworld.push_precollected(self.create_item(gf))

        if self.options.magic_mode == "checks_only":
            # Starter junction fuel: draws yield nothing in this mode, so
            # without it the early game would have no magic at all.
            for name in STARTER_MAGIC:
                self.multiworld.push_precollected(self.create_item(name))

        pool = [self.create_item(name) for name in pool_names]

        total_locations = len(self.multiworld.get_unfilled_locations(self.player))
        while len(pool) < total_locations:
            pool.append(self.create_item(self.get_filler_item_name()))
        self.multiworld.itempool += pool

    def set_rules(self) -> None:
        set_rule(self.get_location("Magical Lamp: Diablos"),
                 lambda state: state.has("Magical Lamp", self.player))
        set_rule(self.get_location("Solomon Ring: Doomtrain"),
                 lambda state: state.has("Solomon Ring", self.player))
        # GF ability checks need the GF itself in hand.
        for location in self.multiworld.get_locations(self.player):
            if location.address is None:
                continue
            gf = LOCATION_DATA_BY_NAME[location.name].requires_gf
            if gf is not None:
                set_rule(location, lambda state, item=f"GF {GF_ORDER[gf]}":
                         state.has(item, self.player))

    def get_filler_item_name(self) -> str:
        if self.random.randrange(100) < self.options.trap_chance.value:
            names = [t.name for t in TRAP_TABLE]
            return self.random.choices(names, weights=[TRAP_WEIGHTS[n] for n in names])[0]
        weights = (FILLER_WEIGHTS_CHECKS_ONLY
                   if self.options.magic_mode == "checks_only" else FILLER_WEIGHTS)
        names = [f.name for f in FILLER_TABLE if weights[f.name] > 0]
        return self.random.choices(names, weights=[weights[n] for n in names])[0]

    def fill_slot_data(self) -> dict:
        return self.options.as_dict(
            "goal", "starting_gfs", "gfs_required_for_disc3", "magic_mode",
            "trap_chance", "draw_point_checks", "world_draw_point_checks",
            "triple_triad_checks", "optional_boss_checks", "rare_card_checks",
            "sidequest_checks", "magazine_checks", "stat_checks",
            "gf_ability_checks", "death_link",
        )
