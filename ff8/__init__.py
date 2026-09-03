"""Final Fantasy VIII Archipelago world (Steam 2013 PC version).

The story plays out vanilla; the game's reward moments (GF acquisitions, story/boss
beats, unique item handouts) become multiworld checks, and the bundled memory-hook
client suppresses vanilla rewards and delivers the multiworld's items instead.
"""

import json
import pkgutil
from typing import Any, ClassVar

from BaseClasses import ItemClassification, LocationProgressType, Region, Tutorial
from Options import OptionError
from worlds.AutoWorld import WebWorld, World
from worlds.generic.Rules import add_rule, set_rule
from worlds.LauncherComponents import Component, Type, components, launch_subprocess

from .abilities import (COMMAND_ABILITY_IDS, GF_ABILITY_NAMES,
                        GF_LEARN_LISTS, GF_SIGNATURE_ABILITIES,
                        JUNCTION_LOCK_GROUPS)
from .items import (ABILITY_LOCK_TABLE, COMMAND_LOCK_TABLE, DEFAULT_FILLER,
                    FILLER_TABLE, FILLER_WEIGHTS, FILLER_WEIGHTS_CHECKS_ONLY,
                    FILLER_WEIGHTS_PROGRESSIVE, GAME_NAME, GF_ORDER,
                    ITEM_DATA_BY_NAME, ITEM_TABLE, JUNCTION_LOCK_TABLE,
                    MAGIC_TIERS, PROGRESSIVE_MAGIC_COUNTS, PROGRESSIVE_TABLE,
                    TRAP_TABLE, TRAP_WEIGHTS, FF8Item, item_name_groups,
                    item_name_to_id, starter_magic_kit)
from .locations import (LOCATION_DATA_BY_NAME, LOCATIONS_BY_GROUP,
                        FF8Location, location_name_groups, location_name_to_id)
from .options import FF8Options, OPTION_GROUPS, OPTION_PRESETS
from . import memory

# Story-ordered region chain; entering region N+1 requires the "Cleared: N" event.
REGION_CHAIN = [
    "Balamb Prologue", "Fire Cavern", "Dollet Exam", "SeeD",
    "Timber", "Galbadia", "Disc 2", "Disc 3", "Disc 4",
]


def _reads_magic_drawn(kind: str, value) -> bool:
    """True when a trigger reads the magic_drawn_once bitmask — i.e. the check
    can only be satisfied by drawing magic (First Draw marquees are flag_bit
    on its bytes, the magic-collection ladder is popcount_ge over it)."""
    if kind == "flag_bit":
        return (memory.MAGIC_DRAWN <= value[0]
                < memory.MAGIC_DRAWN + memory.MAGIC_DRAWN_LEN)
    if kind == "popcount_ge":
        return value[0] == memory.MAGIC_DRAWN
    return False


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

    def _progressive_magic_active(self) -> bool:
        # Progressive magic only means something where granted caps are the
        # magic economy; under vanilla draws it would just be worse filler.
        return bool(self.options.progressive_magic) \
            and self.options.magic_mode == "checks_only"

    def create_items(self) -> None:
        # Option-conditional tables stay out of the base pool and join below.
        conditional = ({d.name for d in PROGRESSIVE_TABLE}
                       | {d.name for d in ABILITY_LOCK_TABLE}
                       | {d.name for d in JUNCTION_LOCK_TABLE}
                       | {d.name for d in COMMAND_LOCK_TABLE})
        pool_names = [d.name for d in ITEM_TABLE
                      if d.name not in {f.name for f in FILLER_TABLE}
                      and d.name not in {t.name for t in TRAP_TABLE}
                      and d.name not in conditional]

        gf_names = sorted(item_name_groups["GFs"])
        for gf in self.random.sample(gf_names, self.options.starting_gfs.value):
            pool_names.remove(gf)
            self.multiworld.push_precollected(self.create_item(gf))

        progressive = self._progressive_magic_active()
        if self.options.magic_mode == "checks_only":
            # Starter junction fuel: draws yield nothing in this mode, so
            # without it the early game has no magic at all. starter_magic
            # scales it (none / basic / generous); progressive_magic swaps in
            # the stage-1 chain items.
            starter_kit = starter_magic_kit(self.options.starter_magic.value,
                                            progressive)
            for name in starter_kit:
                self.multiworld.push_precollected(self.create_item(name))
        else:
            starter_kit = []
        if progressive:
            # Fixed copy counts (not filler weights): the pool always carries
            # every not-precollected stage, so full power is always reachable.
            counts = dict(PROGRESSIVE_MAGIC_COUNTS)
            for name in starter_kit:
                if name in counts:
                    counts[name] -= 1
            for name, count in counts.items():
                pool_names += [name] * count

        char_names = sorted(item_name_groups["Character Unlocks"])
        if self.options.character_locks:
            # One random character junctions from the start so the party is
            # never Squall-only power; the other four unlocks are in the pool.
            starter = self.random.choice(char_names)
            pool_names.remove(starter)
            self.multiworld.push_precollected(self.create_item(starter))
        else:
            for name in char_names:
                pool_names.remove(name)

        if self.options.ability_locks:
            pool_names += [d.name for d in ABILITY_LOCK_TABLE]
        if self.options.junction_locks:
            # One random junction right from the start: something is always
            # junctionable once a GF arrives, and the guaranteed precollect
            # keeps the client's lock enforcement armed from the first sync.
            junction_names = [d.name for d in JUNCTION_LOCK_TABLE]
            starter = self.random.choice(junction_names)
            junction_names.remove(starter)
            self.multiworld.push_precollected(self.create_item(starter))
            pool_names += junction_names
        if self.options.command_locks:
            # Draw Command comes precollected: drawing gates the draw-point
            # economy (~224 checks all-on) and the magic-drawn/scanned stats,
            # so shipping without it leaves too much of the world dark and
            # makes accidental self-droughts easy. Magic/GF/Item are the pool
            # items; the Draw logic rules stay as belt-and-braces.
            self.multiworld.push_precollected(self.create_item("Draw Command"))
            pool_names += [d.name for d in COMMAND_LOCK_TABLE
                           if d.name != "Draw Command"]

        pool = [self.create_item(name) for name in pool_names]

        total_locations = len(self.multiworld.get_unfilled_locations(self.player))
        if len(pool) > total_locations:
            raise OptionError(
                f"FF8 ({self.player_name}): {len(pool)} non-filler items but "
                f"only {total_locations} locations. The lock options "
                "(ability/junction/command locks) add many items — enable "
                "more check groups (GF ability checks, draw points, ...) or "
                "turn a lock option off.")
        while len(pool) < total_locations:
            pool.append(self.create_item(self.get_filler_item_name()))
        self.multiworld.itempool += pool

    def post_fill(self) -> None:
        """Tiered magic: re-sort this world's magic items among the multiworld
        locations fill scattered them to, so lower tiers land in earlier
        logical spheres. Only our own magic moves, and only between locations
        that already held it, so every other placement — and all logic — is
        untouched. (Progression balancing runs after this and can nudge sphere
        boundaries, but it never moves filler, so the ordering keeps.)"""
        if not self.options.tiered_magic:
            return
        sphere_of: dict[Any, int] = {}
        for index, sphere in enumerate(self.multiworld.get_spheres()):
            for location in sphere:
                sphere_of[location] = index
        unreachable = len(sphere_of) + 1

        locations = [loc for loc in self.multiworld.get_filled_locations()
                     if loc.item.player == self.player
                     and loc.item.name in MAGIC_TIERS and not loc.locked]
        # Shuffle before the stable sort so same-sphere order carries no
        # fill-order bias, then selection-sort items by tier along the
        # sphere order. A swap only happens when both locations accept the
        # exchanged items (excluded slots hold filler only, and foreign
        # item_rules are honored), so the result is always as valid as the
        # fill we started from.
        self.random.shuffle(locations)
        locations.sort(key=lambda loc: sphere_of.get(loc, unreachable))

        def accepts(location, item) -> bool:
            if (location.progress_type == LocationProgressType.EXCLUDED
                    and ItemClassification.useful in item.classification):
                return False
            return location.item_rule(item)

        items = [loc.item for loc in locations]
        for i, location in enumerate(locations):
            best = i if accepts(location, items[i]) else None
            for j in range(i + 1, len(items)):
                if (best is not None
                        and MAGIC_TIERS[items[j].name] >= MAGIC_TIERS[items[best].name]):
                    continue
                if not accepts(location, items[j]):
                    continue
                if not accepts(locations[j], items[i]):
                    continue
                best = j
                if MAGIC_TIERS[items[j].name] == 0:
                    break
            if best is not None and best != i:
                items[i], items[best] = items[best], items[i]
                locations[i].item, locations[best].item = items[i], items[best]
                items[i].location, items[best].location = locations[i], locations[best]

    def set_rules(self) -> None:
        set_rule(self.get_location("Magical Lamp: Diablos"),
                 lambda state: state.has("Magical Lamp", self.player))
        set_rule(self.get_location("Solomon Ring: Doomtrain"),
                 lambda state: state.has("Solomon Ring", self.player))
        # GF ability checks need the GF itself in hand; draw-dependent checks
        # need someone who can actually draw. Using a draw point (or drawing
        # in battle) requires a party member with the Draw command, i.e. at
        # least one junctioned GF — and under command_locks, the "Draw
        # Command" item too, else fill could bury Draw Command behind a draw
        # point (a genuine soft-lock). The enemies-scanned ladder additionally
        # needs Magic: Scan has no multiworld item, so the route is
        # draw-Scan-in-battle and cast it before the field-tick clamp.
        command_locks = bool(self.options.command_locks)
        for location in self.multiworld.get_locations(self.player):
            if location.address is None:
                continue
            data = LOCATION_DATA_BY_NAME[location.name]
            if data.requires_gf is not None:
                set_rule(location, lambda state, item=f"GF {GF_ORDER[data.requires_gf]}":
                         state.has(item, self.player))
            draw_dep = (data.group in ("draw", "world_draw")
                        or any(_reads_magic_drawn(k, v) for k, v in data.triggers))
            scan_dep = any(k == "popcount_ge" and v[0] == memory.ENEMIES_SCANNED
                           for k, v in data.triggers)
            if draw_dep or scan_dep:
                add_rule(location, lambda state:
                         state.has_group("GFs", self.player, 1))
                if command_locks:
                    needed = (("Draw Command", "Magic Command") if scan_dep
                              else ("Draw Command",))
                    add_rule(location, lambda state, req=needed:
                             state.has_all(req, self.player))
        # Lock options hold completeAbilities bits down, so a "GF Mastered"
        # check (bits_all over the 22-ability learn list) additionally needs
        # every lock item covering a bit in that list. The signature LEARN
        # checks need no rule — the learn edge fires before the revocation —
        # and the party ladder keeps enough headroom without items
        # (test_abilities asserts >= 150 uninterceptable).
        if self.options.gf_ability_checks:
            for gf, gf_name in enumerate(GF_ORDER):
                needed: list[str] = []
                if self.options.ability_locks:
                    needed += [f"{gf_name}: {GF_ABILITY_NAMES[aid]}"
                               for aid in GF_SIGNATURE_ABILITIES[gf]]
                learn = set(GF_LEARN_LISTS[gf])
                if self.options.junction_locks:
                    needed += [GF_ABILITY_NAMES[primary]
                               for primary, bits in JUNCTION_LOCK_GROUPS.items()
                               if learn & set(bits)]
                if self.options.command_locks:
                    # The four command abilities are in every learn list.
                    needed += [f"{name} Command" for name in COMMAND_ABILITY_IDS]
                if needed:
                    add_rule(self.get_location(f"{gf_name} Mastered"),
                             lambda state, req=tuple(needed):
                             state.has_all(req, self.player))

    def get_filler_item_name(self) -> str:
        if self.random.randrange(100) < self.options.trap_chance.value:
            names = [t.name for t in TRAP_TABLE]
            return self.random.choices(names, weights=[TRAP_WEIGHTS[n] for n in names])[0]
        if self.options.magic_mode == "checks_only":
            weights = (FILLER_WEIGHTS_PROGRESSIVE
                       if self._progressive_magic_active()
                       else FILLER_WEIGHTS_CHECKS_ONLY)
        else:
            weights = FILLER_WEIGHTS
        names = [f.name for f in FILLER_TABLE if weights[f.name] > 0]
        return self.random.choices(names, weights=[weights[n] for n in names])[0]

    def fill_slot_data(self) -> dict:
        return self.options.as_dict(
            "goal", "starting_gfs", "gfs_required_for_disc3", "magic_mode",
            "starter_magic", "progressive_magic", "tiered_magic",
            "character_locks", "ability_locks", "junction_locks",
            "command_locks", "trap_chance",
            "draw_point_checks", "world_draw_point_checks",
            "triple_triad_checks", "optional_boss_checks", "rare_card_checks",
            "sidequest_checks", "magazine_checks", "stat_checks",
            "gf_ability_checks", "death_link",
        )
