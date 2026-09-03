"""Archipelago client for Final Fantasy VIII (Steam 2013).

Polls FF8_EN.exe memory (~2 Hz) to detect checks, suppresses vanilla rewards, and
writes received multiworld items into the live savemap. Pattern follows the KH2 /
FF12 Open World clients; battle-victory and endgame detection follow the speedrun
autosplitter (see docs/research/ in the repo).
"""

import asyncio
import json
import os
import zlib

import Utils
from BaseClasses import ItemClassification
from CommonClient import (ClientCommandProcessor, CommonContext, get_base_parser,
                          gui_enabled, handle_url_arg, logger, server_loop)
from NetUtils import ClientStatus
from Utils import user_path

from .abilities import (COMMAND_ABILITY_IDS, GF_ABILITY_NAMES,
                        GF_SIGNATURE_ABILITIES, JUNCTION_LOCK_GROUPS,
                        ability_mask)
from .areas import AREA_BY_LOCATION
from .items import (BASE_ID, ITEM_TABLE, GF_ORDER, MAGICAL_LAMP_GAME_ID,
                    PROGRESSIVE_MAGIC_STAGES, SOLOMON_RING_GAME_ID)
from .locations import ENC_OMEGA, LOCATION_TABLE
from . import memory
from .memory import FF8Interface

ITEM_DATA_BY_ID = {BASE_ID + d.id_offset: d for d in ITEM_TABLE}
POLL_SECONDS = 0.5
REHOOK_SECONDS = 5.0
GOAL_OMEGA = 1                  # options.Goal.option_omega, via slot_data
MAGIC_CHECKS_ONLY = 1           # options.MagicMode.option_checks_only, via slot_data

# spell id -> display name, for checks-only enforcement logs ("Firaga", not
# "spell 3"); derived from the magic items' grant payloads, plus the
# progressive base tiers (Fire/Blizzard/Thunder have no flat item).
SPELL_NAMES = {d.grant[1]: d.name.rsplit(" x", 1)[0]
               for d in ITEM_TABLE if d.grant[0] == "magic"}
SPELL_NAMES.update({1: "Fire", 4: "Blizzard", 7: "Thunder"})

# game item id -> the location its use/consumption feeds. Once that check is
# sent, the item was spent on purpose and must not be re-asserted.
KEY_ITEM_GATES = {
    MAGICAL_LAMP_GAME_ID: BASE_ID + 5,    # "Magical Lamp: Diablos"
    SOLOMON_RING_GAME_ID: BASE_ID + 11,   # "Solomon Ring: Doomtrain"
}


class FF8CommandProcessor(ClientCommandProcessor):
    def _cmd_ff8(self):
        """Show FF8 game connection status."""
        ctx = self.ctx
        if ctx.ff8.attached:
            try:
                self.output(f"Attached. game_moment={ctx.ff8.game_moment()} "
                            f"field={ctx.ff8.field_id()} gil={ctx.ff8.gil()} "
                            f"safe={ctx.ff8.is_safe()} in_battle={ctx.ff8.in_battle()} "
                            f"encounter={ctx.ff8.encounter_id()}")
                in_save = read_save_state(ctx)
                save_desc = "no AP header yet" if in_save is None else str(in_save)
                self.output(f"Items in this save: {save_desc}/{len(ctx.items_received)} "
                            f"(session high-water {ctx.applied_item_count}) · "
                            f"checks sent: {len(ctx.checked_locations)} · "
                            f"last_encounter={ctx.last_encounter} · "
                            f"DeathLink {'on' if 'DeathLink' in ctx.tags else 'off'}"
                            f"{' (death pending)' if ctx.pending_deathlink else ''} · "
                            f"magic {'checks_only' if magic_checks_only(ctx) else 'vanilla'}")
                if ctx.slot_data.get("character_locks"):
                    names = [memory.CHAR_NAMES[i]
                             for i in sorted(unlocked_char_indices(ctx))]
                    self.output("Character locks on — junction rights: "
                                + ", ".join(["Squall"] + names))
                if ctx.slot_data.get("junction_locks"):
                    have = received_junction_primaries(ctx)
                    missing = [GF_ABILITY_NAMES[p] for p in JUNCTION_LOCK_GROUPS
                               if p not in have]
                    self.output("Junction locks — still locked: "
                                + (", ".join(missing) if missing else "none"))
                if ctx.slot_data.get("command_locks"):
                    have = received_command_ids(ctx)
                    missing = [name for name, cid in COMMAND_ABILITY_IDS.items()
                               if cid not in have]
                    self.output("Command locks — still locked: "
                                + (", ".join(missing) if missing else "none"))
                if ctx.slot_data.get("ability_locks"):
                    unlocked = sum(mask.bit_count() for mask in
                                   permitted_signature_bits(ctx).values())
                    self.output(f"GF ability locks — {unlocked}/49 signature "
                                "abilities unlocked")
            except Exception:
                self.output("Attached, but reads are failing (game closed?).")
        else:
            self.output("Not attached to FF8_EN.exe. Is the game running?")

    def _cmd_ff8verify(self):
        """Dump the raw VERIFY-offset values (research aid, one savemap snapshot)."""
        ctx = self.ctx
        if not ctx.ff8.attached:
            self.output("Not attached to FF8_EN.exe. Is the game running?")
            return
        try:
            snap = ctx.ff8.snapshot()
        except Exception:
            self.output("Attached, but reads are failing (game closed?).")
            return
        rare = snap.read_bytes(memory.CARDS_RARE, 5)
        self.output(f"[verify] tt_wins={snap.read_u16(memory.TT_WINS)} "
                    f"dream=0x{snap.read_u8(memory.DREAM_FLAGS):02X} "
                    f"tonberry_king={snap.read_u32(memory.TONBERRY_KING_FLAG)} "
                    f"blue_magic=0x{snap.read_u16(memory.QUISTIS_LIMITS):04X} "
                    f"angelo=0x{snap.read_u8(memory.ANGELO_KNOWN):02X} "
                    f"angelo_done=0x{snap.read_u8(memory.ANGELO_COMPLETED):02X} "
                    f"timber_maniacs=0x{snap.read_u16(memory.TIMBER_MANIACS):04X} "
                    f"cc=0x{snap.read_u8(memory.CC_GROUP_FLAGS):02X} "
                    f"rare_cards={rare.hex()}")
        weapons = [snap.char_weapon(i) for i in range(6)]
        self.output(f"[verify] battles_won={snap.read_u32(memory.BATTLES_WON)} "
                    f"seed_tests={snap.read_u8(memory.SEED_TEST_LEVEL)} "
                    f"unique_cards={snap.unique_cards_owned()} "
                    f"seals=0x{snap.read_u8(memory.SEAL_FLAGS):02X} "
                    f"weapons={weapons} "
                    f"weapons_made=0x{snap.read_u32(memory.WEAPONS_UNLOCKED):08X}")
        self.output(f"[verify] cc2=0x{snap.read_u8(memory.CC_DIALOGS2):02X} "
                    f"queen={snap.read_u8(memory.QUEEN_QUEST)} "
                    f"pupu=0x{snap.read_u8(memory.PUPU_QUEST):02X} "
                    f"ufo_killed={snap.read_u32(memory.UFO_KILLED) & 1} "
                    f"obel={snap.read_bytes(memory.VAR_BLOCK + 1398, 8).hex()} "
                    f"choco={snap.read_bytes(memory.VAR_BLOCK + 616, 7).hex()}")
        magic_drawn = sum(b.bit_count() for b in
                          snap.read_bytes(memory.MAGIC_DRAWN, memory.MAGIC_DRAWN_LEN))
        scanned = sum(b.bit_count() for b in
                      snap.read_bytes(memory.ENEMIES_SCANNED, memory.ENEMIES_SCANNED_LEN))
        squall_exp = snap.read_u32(memory.SQUALL_EXP)
        self.output(f"[verify] zell=0x{snap.read_u16(memory.ZELL_DUELS):04X} "
                    f"squall_lv={min(100, squall_exp // 1000 + 1)} (exp={squall_exp}) "
                    f"magic_drawn={magic_drawn} scanned={scanned} "
                    f"escaped={snap.read_u16(memory.BATTLES_ESCAPED)} "
                    f"steps={snap.read_u32(memory.STEPS)} "
                    f"monster_kills={snap.read_u32(memory.MONSTER_KILLS)} "
                    f"tonberries={snap.read_u32(memory.TONBERRY_KILLS)} "
                    f"seed_exp={snap.read_u16(memory.SEED_EXP)}")
        lvl_sets = [sum(1 for i in range(11)
                        if snap.read_u8(memory.TT_CARDS + lvl * 11 + i)
                        & memory.TT_CARD_SEEN)
                    for lvl in range(7)]
        self.output(f"[verify] tt_rules={snap.read_bytes(memory.TT_RULES, 8).hex()} "
                    f"(virgin 01020c0e8890dfc0) "
                    f"bgu_wins={snap.read_u8(memory.BGU_WINS)} "
                    f"level_sets={'/'.join(str(n) for n in lvl_sets)}")
        learned = [snap.gf_abilities_learned(i) for i in range(memory.GF_COUNT)]
        self.output(f"[verify] gf_abilities_beyond_default={learned} "
                    f"total={sum(learned)} "
                    f"quezacotl_mask={snap.gf_abilities(0):032x}")

    def _cmd_ff8magic(self):
        """Show the checks-only magic ledger: current stock vs. granted cap
        per spell."""
        ctx = self.ctx
        if not magic_checks_only(ctx):
            self.output("Magic mode is vanilla for this slot; no ledger.")
            return
        if not ctx.ff8.attached:
            self.output("Not attached to FF8_EN.exe. Is the game running?")
            return
        if ctx.magic_expected is None:
            self.output("Ledger not baselined yet (needs one safe field tick).")
            return
        try:
            totals = ctx.ff8.snapshot().magic_totals()
        except Exception:
            self.output("Attached, but reads are failing (game closed?).")
            return
        sids = sorted(set(ctx.magic_expected) | set(totals))
        lines = [f"{SPELL_NAMES.get(sid, f'spell {sid}')} "
                 f"{totals.get(sid, 0)}/{ctx.magic_expected.get(sid, 0)}"
                 for sid in sids]
        self.output("Stock/cap: " + (", ".join(lines) if lines
                                     else "nothing stocked or granted yet"))
        if ctx.slot_data.get("progressive_magic"):
            counts: dict[str, int] = {}
            for net_item in ctx.items_received:
                data = ITEM_DATA_BY_ID.get(net_item.item)
                if data and data.grant[0] == "prog_magic":
                    counts[data.name] = counts.get(data.name, 0) + 1
            self.output("Progressive stages: " + ", ".join(
                f"{name.removeprefix('Progressive ')} "
                f"{min(counts.get(name, 0), len(stages))}/{len(stages)}"
                for name, stages in PROGRESSIVE_MAGIC_STAGES.items()))

    def _cmd_deathlink(self):
        """Toggle DeathLink on/off for this session."""
        ctx = self.ctx
        enable = "DeathLink" not in ctx.tags
        Utils.async_start(ctx.update_death_link(enable))
        self.output(f"DeathLink {'enabled' if enable else 'disabled'}.")

    STATE_KINDS = ("story", "draw", "tt_wins", "flag_bit", "popcount16_ge",
                   "item_own", "u8_ge", "u16_ge", "u32_ge", "bits_ge",
                   "popcount_ge", "byteflag_ge", "bits_clear",
                   "cards_seen_range", "cards_owned", "bits_all",
                   "gf_abilities_ge")

    def _cmd_ff8adopt(self):
        """Adopt the currently loaded save into this campaign (answers the
        HOLDING warning): send its held bulk catch-up checks, or claim a save
        stamped by another seed (its old header is discarded)."""
        ctx = self.ctx
        if not ctx.save_frozen:
            self.output("Nothing is held right now — the loaded save is "
                        "already tracking normally.")
            return
        ctx.adopt_confirmed = True
        self.output("Adopt armed: the next tick accepts the loaded save.")

    def _cmd_ff8missed(self):
        """Diagnose unchecked locations: list any whose state-based condition
        already reads satisfied (they should fire within a tick — if they
        persist here, something is wrong)."""
        ctx = self.ctx
        if not ctx.ff8.attached:
            self.output("Not attached to FF8_EN.exe.")
            return
        try:
            snap = ctx.ff8.snapshot()
        except Exception:
            self.output("Reads are failing (game closed?).")
            return
        satisfied, pending_state, pending_edge = [], 0, 0
        for loc in LOCATION_TABLE:
            loc_id = BASE_ID + loc.id_offset
            if loc_id not in ctx.missing_locations or loc_id in ctx.locations_checked:
                continue
            state_triggers = [(k, v) for k, v in loc.triggers if k in self.STATE_KINDS]
            if not state_triggers:
                pending_edge += 1
                continue
            if any(trigger_satisfied(ctx, k, v, snap, [], {})
                   for k, v in state_triggers):
                satisfied.append(loc.name)
            else:
                pending_state += 1
        self.output(f"Unchecked: {pending_state} state-based not yet met, "
                    f"{pending_edge} edge-based (fire only while watching), "
                    f"{len(satisfied)} satisfied-but-unsent.")
        for name in satisfied[:20]:
            self.output(f"  SATISFIED but unsent: {name}")
        if len(satisfied) > 20:
            self.output(f"  ... and {len(satisfied) - 20} more")
        if satisfied:
            self.output("These should send within a second on a field screen; "
                        "if they persist, use /ff8check or report a bug.")

    def _cmd_ff8check(self, *location_words: str):
        """Manually send a check by (partial) location name — a rescue for an
        edge-based check the client provably missed (e.g. a boss killed while
        the client was disconnected). Usage: /ff8check <name>"""
        ctx = self.ctx
        query = " ".join(location_words).strip().lower()
        if not query:
            self.output("Usage: /ff8check <location name (or unique part of it)>")
            return
        missing = [loc for loc in LOCATION_TABLE
                   if BASE_ID + loc.id_offset in ctx.missing_locations]
        matches = [loc for loc in missing if loc.name.lower() == query]
        if not matches:
            matches = [loc for loc in missing if query in loc.name.lower()]
        if not matches:
            self.output(f"No unchecked location matches '{query}'.")
            return
        if len(matches) > 1:
            self.output(f"Ambiguous ({len(matches)} matches): "
                        + "; ".join(loc.name for loc in matches[:6]))
            return
        loc = matches[0]
        Utils.async_start(ctx.check_locations([BASE_ID + loc.id_offset]))
        self.output(f"Manually sent: {loc.name}")


class FF8Context(CommonContext):
    command_processor = FF8CommandProcessor
    game = "Final Fantasy VIII"
    items_handling = 0b111
    want_slot_data = True

    def __init__(self, server_address, password):
        super().__init__(server_address, password)
        self.ff8 = FF8Interface()
        self.slot_data: dict = {}
        self.save_fingerprint = 0       # crc32(seed:slot); set on Connected
        self.applied_item_count = 0     # sidecar high-water mark of granted items
        self.ap_set_gf_flags: set[int] = set()  # GF flags we wrote (vs. vanilla writes)
        self.prev_gf_flags: list[bool] | None = None
        self.ap_set_dream_bits = 0      # cameo-GF bits we wrote (vs. vanilla)
        self.prev_dream_flags = 0
        self.prev_item_counts: dict[int, int] = {}
        self.goal_sent = False
        self.max_moment = 0             # highest game moment ever seen (sidecar)
        self._sidecar_loaded = False
        # Seed name the server reports in RoomInfo, captured ourselves: core's
        # CommonContext.server_seed_name only exists in AP 0.6.8+, and this
        # world supports 0.6.7 (minimum_ap_version), where reading it crashes.
        self.ff8_server_seed_name: str | None = None
        # True once this connection's ReceivedItems sync has landed. Lock
        # enforcement (ability/junction/command) waits for it: revoking with a
        # stale-empty items_received would strip abilities the player has
        # legitimately unlocked — and an F1 revocation costs a relearn, so it
        # must never fire on a race. (junction_locks guarantees a precollected
        # item, so a fresh campaign syncs immediately.)
        self.items_synced = False
        # Foreign-save guards (2026-08-31): freeze reason (None = tracking
        # normally), the last logged reason (log-once), and the one-shot
        # /ff8adopt confirmation that lets a held save into the campaign.
        self.save_frozen: str | None = None
        self.last_freeze_log: str | None = None
        self.attach_hint_logged: str | None = None  # log-once wrong-exe/attach-denied hint
        self.adopt_confirmed = False
        # Checks-only magic mode: per-spell caps = baseline stock + granted
        # magic items. None = not yet baselined; reset whenever a different
        # save may have loaded (attach, title screen, adopt, reconnect).
        self.magic_expected: dict[int, int] | None = None
        self.magic_last_moment = 0
        # battle tracking
        self.battle_active = False
        self.last_encounter = 0
        self.won_encounters: set[int] = set()
        self.party_alive_seen = False   # guards against stale HP at battle start
        self.battle_wiped = False       # all occupied ally slots at 0 HP = loss
        self.results_seen = False       # victory/results flag pulsed this battle
        # DeathLink
        self.pending_deathlink = False  # received; apply at next battle tick
        self.death_sent_this_battle = False
        self.deathlink_received_this_battle = False
        # Map area last published to data storage (tracker follow-the-player)
        self.sent_area: str | None = None
        # Ultimecia endgame state machine (autosplitter logic)
        self.ult_phase = -1
        self.prev_field = -1
        self.prev_p1m = 0
        self.prev_final = 0

    async def server_auth(self, password_requested: bool = False):
        if password_requested and not self.password:
            await super().server_auth(password_requested)
        await self.get_username()
        await self.send_connect()

    # --- sidecar persistence (idempotent consumable grants across reconnects) ---
    def _sidecar_path(self) -> str:
        # Keyed by the SERVER's seed name: CommonContext.seed_name stays None
        # for patchless clients (it is only filled from a patch file), which
        # used to collapse every campaign onto one "None_<slot>.json" and leak
        # applied counts / max_moment across seeds (found live 2026-08-31: a
        # fresh seed inherited max_moment 4050 from the previous test seed).
        folder = user_path("FF8AP")
        os.makedirs(folder, exist_ok=True)
        return os.path.join(folder, f"{self.ff8_server_seed_name}_{self.auth}.json")

    def load_sidecar(self):
        try:
            with open(self._sidecar_path(), encoding="utf-8") as f:
                data = json.load(f)
            self.applied_item_count = data.get("applied_item_count", 0)
            self.max_moment = data.get("max_moment", 0)
        except FileNotFoundError:
            self.applied_item_count = 0
            self.max_moment = 0
        self._sidecar_loaded = True

    def save_sidecar(self):
        if not self._sidecar_loaded:
            return
        with open(self._sidecar_path(), "w", encoding="utf-8") as f:
            json.dump({"applied_item_count": self.applied_item_count,
                       "max_moment": self.max_moment}, f)

    def on_package(self, cmd: str, args: dict):
        if cmd == "RoomInfo":
            # Captured here (not from core's 0.6.8-only server_seed_name) so the
            # sidecar can be keyed by seed on 0.6.7 too. RoomInfo precedes
            # Connected, so it is set before load_sidecar() reads it.
            self.ff8_server_seed_name = args.get("seed_name")
        if cmd == "Connected":
            self.slot_data = args.get("slot_data", {})
            self.save_fingerprint = zlib.crc32(
                f"{self.seed_name}:{self.auth}".encode()) & 0xFFFFFFFF
            self.magic_expected = None   # new slot/seed: never reuse a ledger
            self.sent_area = None        # republish the area for the tracker
            self.items_synced = False    # wait for this connection's item sync
            self.load_sidecar()
            if self.slot_data.get("death_link"):
                Utils.async_start(self.update_death_link(True))
        if cmd == "ReceivedItems":
            self.items_synced = True

    def on_deathlink(self, data: dict) -> None:
        super().on_deathlink(data)
        self.pending_deathlink = True

    async def shutdown(self):
        self.save_sidecar()
        await super().shutdown()


def expected_gf_indices(ctx: FF8Context) -> set[int]:
    """GF indices the player should have: everything received from the server."""
    out = set()
    for net_item in ctx.items_received:
        data = ITEM_DATA_BY_ID.get(net_item.item)
        if data and data.grant[0] == "gf":
            out.add(data.grant[1])
    return out


def expected_dream_mask(ctx: FF8Context) -> int:
    """Cameo-GF (dream byte) bits received from the server."""
    mask = 0
    for net_item in ctx.items_received:
        data = ITEM_DATA_BY_ID.get(net_item.item)
        if data and data.grant[0] == "bit" and data.grant[1] == memory.DREAM_FLAGS:
            mask |= data.grant[2]
    return mask


def unlocked_char_indices(ctx: FF8Context) -> set[int]:
    """Character record indices whose junction locks are lifted: everything
    received from the server (character_locks option)."""
    out = set()
    for net_item in ctx.items_received:
        data = ITEM_DATA_BY_ID.get(net_item.item)
        if data and data.grant[0] == "char":
            out.add(data.grant[1])
    return out


def permitted_signature_bits(ctx: FF8Context) -> dict[int, int]:
    """Per-GF mask of signature-ability bits whose lock item arrived
    (ability_locks option)."""
    out: dict[int, int] = {}
    for net_item in ctx.items_received:
        data = ITEM_DATA_BY_ID.get(net_item.item)
        if data and data.grant[0] == "ability":
            out[data.grant[1]] = out.get(data.grant[1], 0) | (1 << data.grant[2])
    return out


def received_junction_primaries(ctx: FF8Context) -> set[int]:
    """Primary ability ids of the junction-lock items received."""
    return {data.grant[1] for net_item in ctx.items_received
            if (data := ITEM_DATA_BY_ID.get(net_item.item))
            and data.grant[0] == "junction"}


def received_command_ids(ctx: FF8Context) -> set[int]:
    """Command ability ids (20-23) whose lock items were received."""
    return {data.grant[1] for net_item in ctx.items_received
            if (data := ITEM_DATA_BY_ID.get(net_item.item))
            and data.grant[0] == "command"}


def magic_checks_only(ctx: FF8Context) -> bool:
    return ctx.slot_data.get("magic_mode") == MAGIC_CHECKS_ONLY


def enforce_magic(ctx: FF8Context):
    """Checks-only magic mode, run every safe tick: total stock per spell may
    never exceed its cap (stock at baseline + magic items granted). Anything
    above cap — draws, refines — is repossessed; stock below cap is left
    alone, so casting is normal and drawing can refill spent stock back up to
    the cap. The cap model (rather than a strict ledger that ratchets down on
    every cast) is deliberate: party shuffles and Laguna dreams can make
    magic vanish and reappear wholesale, and a cap can never destroy stock
    that merely came back. Re-baselines whenever a different save may be
    loaded: attach, the title screen (only route to the load menu), a
    game-moment regression, adopt, reconnect."""
    if not magic_checks_only(ctx) or ctx.save_frozen:
        return
    snap = ctx.ff8.snapshot()
    totals = snap.magic_totals()
    moment = snap.game_moment()
    if ctx.magic_expected is None or moment < ctx.magic_last_moment:
        if ctx.magic_expected is not None:
            logger.info("Checks-only magic: ledger re-baselined "
                        "(an earlier save was loaded).")
        ctx.magic_expected = totals
        ctx.magic_last_moment = moment
        return
    ctx.magic_last_moment = moment
    for sid, total in totals.items():
        excess = total - ctx.magic_expected.get(sid, 0)
        if excess > 0:
            ctx.ff8.remove_magic(sid, excess)
            logger.info(f"Checks-only magic: repossessed {excess} "
                        f"{SPELL_NAMES.get(sid, f'spell {sid}')} "
                        f"(stock {total} > cap {total - excess})")


def track_battle(ctx: FF8Context):
    """Runs every tick. in_battle() spans real combat (module 3) plus the
    victory/results phase (POST_BATTLE pulse). Confirmed live 2026-08-28:
    combat = module 3 / POST_BATTLE 0; a win passes through module 100 -> 4
    with POST_BATTLE=1; a wipe or escape never raises POST_BATTLE. So a win
    is credited only when the results flag was seen and the party was not
    wiped — an escape ends the battle with neither, and gets no credit.
    `party_alive_seen` guards against stale battle memory at start."""
    fighting = ctx.ff8.in_battle()
    if fighting:
        ctx.last_encounter = ctx.ff8.encounter_id()
        if ctx.ff8.battle_results():
            ctx.results_seen = True
        present = [(cur, mx) for cur, mx in ctx.ff8.ally_hps() if mx > 0]
        if any(cur > 0 for cur, _ in present):
            ctx.party_alive_seen = True
            ctx.battle_wiped = False
        elif present and ctx.party_alive_seen:
            ctx.battle_wiped = True
    elif ctx.battle_active:
        if ctx.battle_wiped:
            logger.info(f"Battle lost: encounter {ctx.last_encounter} (no win credit)")
        elif ctx.results_seen:
            ctx.won_encounters.add(ctx.last_encounter)
            logger.info(f"Battle won: encounter {ctx.last_encounter}")
        else:
            logger.info(f"Battle exited without results (escaped?): "
                        f"encounter {ctx.last_encounter} (no win credit)")
        ctx.party_alive_seen = False
        ctx.battle_wiped = False
        ctx.results_seen = False
    ctx.battle_active = fighting


async def handle_deathlink(ctx: FF8Context):
    """Runs every tick after track_battle (which maintains battle_wiped). Sends a
    DeathLink on a party wipe and applies received DeathLinks by zeroing party
    HP — deferred to the next battle if one arrives on the field. A wipe we
    caused ourselves is not echoed back."""
    if "DeathLink" not in ctx.tags:
        return
    if not ctx.battle_active:
        if ctx.pending_deathlink and ctx.deathlink_received_this_battle:
            ctx.pending_deathlink = False   # battle over; the death was delivered
        ctx.death_sent_this_battle = False
        ctx.deathlink_received_this_battle = False
        return

    if ctx.pending_deathlink:
        # Re-assert the wipe EVERY tick for the whole battle: writes during
        # the intro land in stale structs that battle init overwrites, and
        # reading our own zeros back is no proof the engine saw them
        # (observed live 2026-08-28, twice). Continuous assertion means the
        # engine can never see the party alive post-init; the death retires
        # when the battle ends (game over included) in the branch above.
        if not ctx.deathlink_received_this_battle:
            ctx.deathlink_received_this_battle = True
            logger.info("DeathLink: received — wiping party until battle ends")
        ctx.ff8.kill_party()
        return

    if ctx.battle_wiped and not ctx.death_sent_this_battle:
        ctx.death_sent_this_battle = True
        if not ctx.deathlink_received_this_battle:
            name = ctx.player_names.get(ctx.slot, "The party")
            await ctx.send_death(f"{name}'s party fell in battle.")
            logger.info("DeathLink: party wipe sent")


async def publish_area(ctx: FF8Context):
    """Publish the party's current map area to AP data storage so the tracker
    pack can follow the player (it activates the matching world-map area tab).
    MISC2.location is the save-preview location id; ids that don't pin the
    party to one area (trains, chocobo forests) map to nothing and keep the
    last published area."""
    area = AREA_BY_LOCATION.get(ctx.ff8.location_id())
    if area is None or area == ctx.sent_area:
        return
    ctx.sent_area = area
    await ctx.send_msgs([{
        "cmd": "Set",
        "key": f"ff8_area_{ctx.team}_{ctx.slot}",
        "default": "",
        "want_reply": False,
        "operations": [{"operation": "replace", "value": area}],
    }])


async def send_goal(ctx: FF8Context):
    await ctx.send_msgs([{"cmd": "StatusUpdate", "status": ClientStatus.CLIENT_GOAL}])
    ctx.finished_game = True
    ctx.goal_sent = True


async def track_goal(ctx: FF8Context):
    """Goal detection. Omega goal: Omega Weapon (enc 462) victory via the
    standard battle tracker. Ultimecia goal: the endgame state machine ported
    from FF8Autosplitter.asl — on the final-battle field (573), phases advance
    via her three HP pools; FINAL_BLOW 0->1 in the last phase is the kill."""
    if ctx.goal_sent:
        return
    if ctx.slot_data.get("goal") == GOAL_OMEGA:
        if ENC_OMEGA in ctx.won_encounters:
            logger.info("Omega Weapon defeated — sending goal!")
            await send_goal(ctx)
        return
    field = ctx.ff8.field_id()
    p1m = ctx.ff8.read_u32(memory.ENEMY_HP_P1M)
    final = ctx.ff8.read_u8(memory.FINAL_BLOW)
    try:
        if field == memory.ULTIMECIA_FIELD:
            if ctx.prev_field != memory.ULTIMECIA_FIELD:
                ctx.ult_phase = 0
            if ctx.ult_phase == 0 and p1m > 0 and ctx.prev_p1m == 0:
                ctx.ult_phase = 1
                logger.info("Final battle: phase 1")
            if ctx.ult_phase == 1 and ctx.ff8.read_u32(memory.ENEMY_HP_P2) > 1000:
                ctx.ult_phase = 2
                logger.info("Final battle: phase 2")
            if ctx.ult_phase == 2 and ctx.ff8.read_u32(memory.ENEMY_HP_P3) > 1000:
                ctx.ult_phase = 3
                logger.info("Final battle: phase 3")
            if ctx.ult_phase == 3 and final == 1 and ctx.prev_final == 0:
                logger.info("Ultimecia defeated (killing blow) — sending goal!")
                await send_goal(ctx)
        if ctx.ult_phase == 3 and not ctx.goal_sent and not ctx.ff8.in_battle():
            # The final battle cannot be escaped, so leaving it alive == won.
            # FINAL_BLOW proved unreliable live 2026-08-28 (reads garbage,
            # missed the kill); battle-exit-alive is poll-rate-proof. Post-
            # battle ally structs keep end-of-battle HPs: zeros mean a wipe.
            if any(cur > 0 for cur, mx in ctx.ff8.ally_hps() if mx > 0):
                logger.info("Ultimecia defeated (final battle exited alive) "
                            "— sending goal!")
                await send_goal(ctx)
            else:
                logger.info("Final battle ended in a wipe; goal not sent.")
            ctx.ult_phase = -1
    finally:
        ctx.prev_field = field
        ctx.prev_p1m = p1m
        ctx.prev_final = final


def trigger_satisfied(ctx: FF8Context, kind: str, value, snap: memory.SavemapSnapshot,
                      gf_flags: list[bool], item_counts: dict[int, int]) -> bool:
    if kind == "story":
        return snap.game_moment() >= value
    if kind == "boss":
        return value in ctx.won_encounters
    if kind == "gf_flag":
        # rising edge not caused by our own write = the vanilla game granted it
        return (gf_flags[value] and not ctx.prev_gf_flags[value]
                and value not in ctx.ap_set_gf_flags)
    if kind == "item":
        count = item_counts.setdefault(value, snap.count_item(value))
        return count > ctx.prev_item_counts.get(value, 0)
    if kind == "item_gone":
        # Count fell without us removing it = the player used the item. Our own
        # interceptions update prev via item_counts in the same tick, so they
        # never look like a use.
        count = item_counts.setdefault(value, snap.count_item(value))
        return count < ctx.prev_item_counts.get(value, 0)
    if kind == "draw":
        # Nonzero state = drawn (possibly while offline; states start 0 at new
        # game). A point that refilled to Full before we ever saw it nonzero is
        # simply caught the next time the player draws it.
        return snap.draw_states()[value] != 0
    if kind == "tt_wins":
        return snap.read_u16(memory.TT_WINS) >= value
    if kind == "flag_bit":
        offset, mask = value
        return (snap.read_u8(offset) & mask) == mask
    if kind == "popcount16_ge":
        offset, n = value
        return snap.read_u16(offset).bit_count() >= n
    if kind == "dream_flag":
        # Per-bit rising edge on the cameo-GF byte, ignoring bits we set
        # ourselves. Evaluated bit by bit (not mask-wide) so a multi-bit mask
        # like Odin's (Odin|Gilgamesh: Gilgamesh replaces Odin and clears his
        # bit, but implies he was earned) still fires on the vanilla bit even
        # when the multiworld granted the other one.
        byte = snap.read_u8(memory.DREAM_FLAGS)
        rising = byte & ~ctx.prev_dream_flags & value & ~ctx.ap_set_dream_bits
        return rising != 0
    if kind == "item_own":
        # non-intercepting: the magazine stays in the inventory
        return snap.count_item(value) > 0
    if kind == "u8_ge":
        offset, n = value
        return snap.read_u8(offset) >= n
    if kind == "u16_ge":
        offset, n = value
        return snap.read_u16(offset) >= n
    if kind == "u32_ge":
        offset, n = value
        return snap.read_u32(offset) >= n
    if kind == "popcount_ge":
        # total set bits across LEN bytes: magics-drawn / enemies-scanned
        # ladders (bit-order agnostic, like popcount16_ge but arbitrary width)
        offset, length, n = value
        return sum(b.bit_count() for b in snap.read_bytes(offset, length)) >= n
    if kind == "byteflag_ge":
        # count of bytes in [OFF, OFF+LEN) with all MASK bits set >= n:
        # chocobo-forests solved ladder (7 quest vars, 0x80 = solved)
        offset, length, mask, n = value
        return sum(1 for b in snap.read_bytes(offset, length)
                   if b & mask == mask) >= n
    if kind == "bits_ge":
        # popcount of (u32 at offset & mask) >= n: castle-seal ladder (u8
        # bitmask, mask 0xFF), weapon remodels (misc1.unlocked_weapons)
        offset, mask, n = value
        return (snap.read_u32(offset) & mask).bit_count() >= n
    if kind == "bits_clear":
        # every one of LEN bytes has all MASK bits clear: TT Random-rule
        # abolition (virgin rule bytes carry the bit; spreading only adds
        # bits, so clear == abolished). The moment gate is insurance against
        # a hypothetically not-yet-initialized savemap reading as all-zero
        # right at New Game — no abolition is possible before Fire Cavern.
        offset, length, mask = value
        if snap.game_moment() < 20:
            return False
        return all((b & mask) == 0 for b in snap.read_bytes(offset, length))
    if kind == "cards_seen_range":
        # >= n of the COUNT common-card bytes from TTCARDS+START carry the
        # bit-7 "obtained once" flag (card-level sets; refining-proof)
        start, count, n = value
        raw = snap.read_bytes(memory.TT_CARDS + start, count)
        return sum(1 for b in raw if b & memory.TT_CARD_SEEN) >= n
    if kind == "cards_owned":
        return snap.unique_cards_owned() >= value
    if kind == "bits_all":
        # every bit of MASK set across LEN bytes (little-endian): a GF's full
        # 22-ability learn list in its completeAbilities mask
        offset, length, mask = value
        raw = int.from_bytes(snap.read_bytes(offset, length), "little")
        return (raw & mask) == mask
    if kind == "gf_abilities_ge":
        # abilities learned beyond each GF's new-game default, summed
        return snap.gf_abilities_learned_total() >= value
    return False


BULK_GATE = 8   # >= this many checks in one tick from an unstamped save = held


def _freeze(ctx: FF8Context, reason: str) -> None:
    ctx.save_frozen = reason
    if ctx.last_freeze_log != reason:
        ctx.last_freeze_log = reason
        logger.warning(f"HOLDING this save: {reason}")


def _thaw(ctx: FF8Context) -> None:
    if ctx.last_freeze_log:
        logger.info("Campaign save active again — resuming normal tracking.")
        ctx.last_freeze_log = None


def _bulk_gated(ctx: FF8Context, count: int, header_ours: bool) -> bool:
    """Hold a suspicious mass of checks: >= BULK_GATE at once from a save this
    campaign never stamped is a foreign/library save until the player says
    otherwise. Genuine offline catch-up (hours played without the client)
    trips this exactly once — /ff8adopt sends the held checks."""
    if count < BULK_GATE or header_ours:
        return False
    if ctx.adopt_confirmed:
        ctx.adopt_confirmed = False
        logger.info(f"/ff8adopt: accepting this save — sending {count} "
                    "held catch-up checks.")
        ctx.magic_expected = None   # its stock is the new checks-only baseline
        return False
    _freeze(ctx, f"it would send {count} checks at once but was never part of "
                 "this campaign (no AP header). If this is your real progress "
                 "(played offline), run /ff8adopt to send them; otherwise load "
                 "a campaign save.")
    return True


async def detect_checks(ctx: FF8Context) -> list[int]:
    """Read the savemap (one snapshot per tick — every trigger sees the same
    instant) and return newly completed location IDs, suppressing vanilla
    rewards as we go."""
    new_checks: list[int] = []
    snap = ctx.ff8.snapshot()
    moment = snap.game_moment()
    expected = expected_gf_indices(ctx)
    gf_flags = [snap.gf_unlocked(i) for i in range(len(GF_ORDER))]
    item_counts: dict[int, int] = {}

    # --- Foreign-save guard #1: a save stamped by a DIFFERENT seed+slot
    # (test seeds, other campaigns). The 2026-08-31 incident: the fresh
    # campaign's client connected while the previous seed's test save was
    # still loaded and fired 6 checks + revoked 4 GFs before the player ever
    # played. A wrong fingerprint is definitive — freeze, touch nothing.
    hdr_magic = snap.read_u16(memory.AP_STATE_MAGIC_OFF) == memory.AP_STATE_MAGIC
    ctx.save_frozen = None
    if hdr_magic and snap.read_u32(memory.AP_STATE_FINGERPRINT_OFF) != ctx.save_fingerprint:
        if ctx.adopt_confirmed:
            ctx.adopt_confirmed = False
            logger.info("/ff8adopt: claiming this save for the campaign — its "
                        "old AP header is discarded; delivery restarts from 0.")
            ctx.ff8.write_u16(memory.AP_STATE_MAGIC_OFF, 0)
            ctx.prev_gf_flags = None   # re-baseline as an adopted save
            ctx.magic_expected = None
            return []
        _freeze(ctx, "it belongs to a DIFFERENT AP campaign (header fingerprint "
                     f"0x{snap.read_u32(memory.AP_STATE_FINGERPRINT_OFF):08X} != "
                     f"ours 0x{ctx.save_fingerprint:08X}). No checks sent, no "
                     "items granted. Load a campaign save, or /ff8adopt to "
                     "claim this one.")
        return []

    if ctx.prev_gf_flags is None:
        # First safe tick after (re)attach: record a baseline. Offline catch-up: an
        # unchecked GF location whose flag is set without the multiworld having sent
        # that GF means the vanilla game granted it while we weren't watching.
        if ctx.applied_item_count > 0 and moment + 200 < ctx.max_moment:
            logger.warning(
                f"This save (moment {moment}) is well behind the furthest point this "
                f"slot has reached (moment {ctx.max_moment}). GFs and key items will "
                "self-heal, but already-applied consumables (gil/item packs) are not "
                "re-granted on an older or fresh save.")
        ctx.prev_gf_flags = gf_flags
        ctx.prev_dream_flags = snap.read_u8(memory.DREAM_FLAGS)
        ctx.prev_item_counts = {
            v: snap.count_item(v)
            for loc in LOCATION_TABLE for k, v in loc.triggers
            if k in ("item", "item_gone")
        }
        # Offline catch-up for cameo-GF checks: bit set, unchecked, not granted
        # by the multiworld -> the vanilla game granted it while we were away.
        expected_dream = expected_dream_mask(ctx)
        for loc in LOCATION_TABLE:
            loc_id = BASE_ID + loc.id_offset
            for k, v in loc.triggers:
                if (k == "dream_flag" and loc_id in ctx.missing_locations
                        and loc_id not in ctx.locations_checked
                        and (ctx.prev_dream_flags & v & ~expected_dream
                             & ~ctx.ap_set_dream_bits)):
                    new_checks.append(loc_id)
        gf_catchup = [
            (BASE_ID + loc.id_offset, loc.gf) for loc in LOCATION_TABLE
            if (loc.gf is not None
                and BASE_ID + loc.id_offset in ctx.missing_locations
                and BASE_ID + loc.id_offset not in ctx.locations_checked
                and gf_flags[loc.gf] and loc.gf not in expected
                and loc.gf not in ctx.ap_set_gf_flags)
        ]
        # Foreign-save guard #2 (baseline): a headerless save that would
        # catch-up a pile of checks at first sight is held for /ff8adopt.
        if _bulk_gated(ctx, len(new_checks) + len(gf_catchup), hdr_magic):
            ctx.prev_gf_flags = None   # keep re-baselining until adopted
            return []
        for loc_id, gf in gf_catchup:
            new_checks.append(loc_id)
            ctx.ff8.set_gf_unlocked(gf, False)
            ctx.prev_gf_flags[gf] = False
            logger.info(f"Offline catch-up: vanilla GF {GF_ORDER[gf]} "
                        "intercepted -> check sent")
        _thaw(ctx)
        return new_checks

    satisfied: list[tuple] = []
    for loc in LOCATION_TABLE:
        loc_id = BASE_ID + loc.id_offset
        if loc_id in ctx.locations_checked or loc_id not in ctx.missing_locations:
            continue
        if any(trigger_satisfied(ctx, k, v, snap, gf_flags, item_counts)
               for k, v in loc.triggers):
            satisfied.append((loc, loc_id))

    # Foreign-save guard #2 (mid-session): a load-menu switch to a headerless
    # library save fires state triggers on the very next tick — gather first,
    # gate, and only then touch the game, so a held tick has no side effects
    # and prev_* baselines stay those of the real campaign save.
    if _bulk_gated(ctx, len(satisfied), hdr_magic):
        return []

    for loc, loc_id in satisfied:
        new_checks.append(loc_id)
        if loc.gf is not None and loc.gf not in expected and gf_flags[loc.gf]:
            ctx.ff8.set_gf_unlocked(loc.gf, False)
            gf_flags[loc.gf] = False
            logger.info(f"Vanilla GF {GF_ORDER[loc.gf]} intercepted -> check sent")
        for k, v in loc.triggers:
            if k == "item":
                ctx.ff8.remove_item(v)
                item_counts[v] = 0
                logger.info(f"Vanilla item {v} intercepted -> check sent")

    ctx.prev_gf_flags = gf_flags
    ctx.prev_item_counts.update(item_counts)
    ctx.prev_dream_flags = snap.read_u8(memory.DREAM_FLAGS)
    ctx.max_moment = max(ctx.max_moment, moment)
    _thaw(ctx)
    return new_checks


def notify_item(ctx: FF8Context, data, sender: str):
    # Plain text on purpose: the GUI log escapes all markup from logger records
    # (kvui UILog.on_log), so kivy [color]/[b] tags would show up literally.
    # Colored item names still come through AP's own ItemSend line in the log.
    logger.info(f"Received {data.name} from {sender}")


def read_save_state(ctx: FF8Context) -> int | None:
    """Items-applied count stored inside the loaded save's free field vars
    (vars 1000+, verified script/EXE-free and inside the save's checksummed
    span — they persist through the game's own save/load). None = this save
    has no valid AP header for this seed+slot."""
    if ctx.ff8.read_u16(memory.AP_STATE_MAGIC_OFF) != memory.AP_STATE_MAGIC:
        return None
    if ctx.ff8.read_u32(memory.AP_STATE_FINGERPRINT_OFF) != ctx.save_fingerprint:
        return None
    return ctx.ff8.read_u16(memory.AP_STATE_APPLIED_OFF)


def write_save_state(ctx: FF8Context, applied: int) -> None:
    ctx.ff8.write_u16(memory.AP_STATE_MAGIC_OFF, memory.AP_STATE_MAGIC)
    ctx.ff8.write_u32(memory.AP_STATE_FINGERPRINT_OFF, ctx.save_fingerprint)
    ctx.ff8.write_u16(memory.AP_STATE_APPLIED_OFF, applied)


async def grant_items(ctx: FF8Context):
    """Apply received items this save hasn't gotten yet; re-assert
    non-consumables (self-heals reloads).

    The delivery cursor lives IN the save (read_save_state), so reloading an
    older save — or starting a new game on the same slot — re-delivers
    exactly the items that save is missing. The sidecar keeps a machine-local
    high-water mark for the save-regression warning."""
    if ctx.save_frozen:
        return
    if (ctx.ff8.read_u16(memory.AP_STATE_MAGIC_OFF) == memory.AP_STATE_MAGIC
            and ctx.ff8.read_u32(memory.AP_STATE_FINGERPRINT_OFF)
            != ctx.save_fingerprint):
        # Another campaign's save: granting would dump our whole item list
        # into it and stamp our header over theirs. detect_checks owns the
        # messaging; independently hard-stop here in case of ordering.
        return
    saved = read_save_state(ctx)
    header_missing = saved is None
    if header_missing:
        # No header = a save this campaign has never touched (fresh file,
        # library save, new game): deliver from item 0. Non-consumables are
        # idempotent and consumables are exactly what such a save lacks. The
        # old "migrate from the sidecar high-water" path mis-fired on every
        # foreign save once the session had granted anything (2026-08-31,
        # skipped the starting GFs); no real campaign save predates the
        # in-save header, so headerless always means start from zero.
        saved = 0
    start = min(saved, len(ctx.items_received))
    applied = start
    applied_this_tick = 0
    for idx, net_item in enumerate(ctx.items_received[start:], start=start):
        data = ITEM_DATA_BY_ID.get(net_item.item)
        if data is None:
            logger.warning(f"Received unknown item id {net_item.item}")
        else:
            kind = data.grant[0]
            magic_grant = None
            if kind == "magic":
                magic_grant = (data.grant[1], data.grant[2])
            elif kind == "prog_magic":
                # The Nth copy of a family delivers its Nth stage; count is by
                # position in items_received, so redelivery to an older save
                # replays the exact same stages.
                stages = PROGRESSIVE_MAGIC_STAGES[data.grant[1]]
                stage = min(sum(1 for prev in ctx.items_received[:idx]
                                if prev.item == net_item.item), len(stages) - 1)
                magic_grant = stages[stage]
                logger.info(f"{data.name} stage {stage + 1}: "
                            f"{SPELL_NAMES.get(magic_grant[0])} x{magic_grant[1]}")
            if kind == "gf":
                ctx.ap_set_gf_flags.add(data.grant[1])
                ctx.ff8.set_gf_unlocked(data.grant[1], True)
            elif kind == "item":
                ctx.ff8.add_item(data.grant[1], data.grant[2])
                # Attribute the inventory rise to ourselves so the item trigger
                # doesn't mistake our grant for a vanilla handout and intercept it.
                if data.grant[1] in ctx.prev_item_counts:
                    ctx.prev_item_counts[data.grant[1]] += data.grant[2]
            elif kind == "gil":
                ctx.ff8.add_gil(data.grant[1])
            elif magic_grant is not None:
                spell_id, spell_qty = magic_grant
                if ctx.magic_expected is not None:
                    # Raise the cap by the full grant even if stocking fell
                    # short: under checks_only an unstocked remainder stays
                    # drawable, so nothing is ever lost.
                    ctx.magic_expected[spell_id] = (
                        ctx.magic_expected.get(spell_id, 0) + spell_qty)
                if not ctx.ff8.add_magic(spell_id, spell_qty):
                    if magic_checks_only(ctx):
                        logger.warning(
                            f"Magic inventory full; {data.name} raised your draw "
                            "cap instead — cast to make room, then draw it back")
                    else:
                        logger.warning(f"Magic inventory full; could not stock {data.name}")
            elif kind == "bit":
                if data.grant[1] == memory.DREAM_FLAGS:
                    ctx.ap_set_dream_bits |= data.grant[2]
                ctx.ff8.set_bits(data.grant[1], data.grant[2])
            elif kind == "char":
                # Nothing to write: the unlock is client state — the junction
                # enforcement below simply stops stripping this character.
                pass
            elif kind in ("ability", "junction", "command"):
                # Client state too: enforce_gf_locks stops revoking the bit(s)
                # — and for junction/command items restores the GFs' default
                # bits — on the next safe tick.
                pass
            elif kind == "trap_gil":
                taken = ctx.ff8.take_gil(data.grant[1])
                logger.info(f"Trap: {taken} gil snatched")
            elif kind == "trap_hp":
                hit = ctx.ff8.ambush_party(data.grant[1])
                logger.info(f"Trap: ambushed — {hit} party members at {data.grant[1]} HP")
            elif kind == "trap_magic":
                leaked = ctx.ff8.leak_magic(data.grant[1])
                if leaked:
                    sid, taken = leaked
                    logger.info(f"Trap: {taken} {SPELL_NAMES.get(sid, f'spell {sid}')} leaked away")
            sender = ctx.player_names.get(net_item.player, f"slot {net_item.player}")
            notify_item(ctx, data, sender)
            applied_this_tick += 1
        applied += 1
    if header_missing or applied != saved:
        write_save_state(ctx, applied)
    if applied_this_tick > 5:
        logger.info(f"Applied {applied_this_tick} multiworld items "
                    f"({applied}/{len(ctx.items_received)} total in this save)")
    if applied > ctx.applied_item_count:
        ctx.applied_item_count = applied
        ctx.save_sidecar()

    # Re-assert GFs and unique key items every tick (KH2 verifyItems pattern).
    gf_flags = ctx.ff8.gf_flags_all()
    for gf in expected_gf_indices(ctx):
        if not gf_flags[gf]:
            ctx.ap_set_gf_flags.add(gf)
            ctx.ff8.set_gf_unlocked(gf, True)
    # Cameo GFs self-heal too, except Odin once Gilgamesh exists — the game
    # converts one into the other at the Disc 3 Seifer fight, and re-asserting
    # Odin past that point is an untested double-summon state.
    expected_dream = expected_dream_mask(ctx)
    if expected_dream:
        cur = ctx.ff8.read_u8(memory.DREAM_FLAGS)
        if cur & memory.DREAM_GILGAMESH:
            expected_dream &= ~memory.DREAM_ODIN
        if (cur & expected_dream) != expected_dream:
            ctx.ap_set_dream_bits |= expected_dream
            ctx.ff8.set_bits(memory.DREAM_FLAGS, expected_dream)
    for net_item in ctx.items_received[:ctx.applied_item_count]:
        data = ITEM_DATA_BY_ID.get(net_item.item)
        if (data and data.grant[0] == "item"
                and ItemClassification.progression in data.classification):
            gate = KEY_ITEM_GATES.get(data.grant[1])
            if gate is not None and (gate in ctx.checked_locations
                                     or gate in ctx.locations_checked):
                continue  # spent on purpose (its check is sent); stay gone
            if ctx.ff8.count_item(data.grant[1]) == 0:
                ctx.ff8.add_item(data.grant[1], data.grant[2])
                if data.grant[1] in ctx.prev_item_counts:
                    ctx.prev_item_counts[data.grant[1]] += data.grant[2]

    # Character junction locks: strip junctions from characters whose unlock
    # item hasn't arrived. Only runs on safe ticks (never mid-battle, so a
    # fight in progress is never destabilized; the cleared state applies from
    # the next battle) and only touches the junction block — magic stock, HP,
    # EXP, and costumes stay. A GF freed this way is unjunctioned, not lost.
    # items_received guard: right after connect, slot_data can be set before
    # the ReceivedItems sync lands; enforcing then would strip characters the
    # player has legitimately unlocked. This slot always has precollected
    # items (one character unlock at minimum), so an empty list means unsynced.
    if ctx.slot_data.get("character_locks") and ctx.items_received:
        unlocked = unlocked_char_indices(ctx)
        for ci in memory.LOCKABLE_CHARS:
            if ci in unlocked:
                continue
            if ctx.ff8.char_junctions_active(ci):
                ctx.ff8.clear_char_junctions(ci)
                name = memory.CHAR_NAMES[ci]
                logger.info(f"{name} is locked — junctions removed "
                            f"(find {name}'s Junctions to unlock)")


def enforce_gf_locks(ctx: FF8Context):
    """ability_locks / junction_locks / command_locks enforcement, run every
    safe tick AFTER detect_checks (detect first, revoke second — a learn edge
    always sends its check before the bit is taken back).

    Three lock families share one write pattern on each GF record's
    completeAbilities mask:
      - ability_locks: per-GF signature bits stay cleared until that exact
        "GF: Ability" item arrives; once permitted, the bit is never granted —
        the player (re)learns it, keeping every mask-derived trigger honest.
      - junction_locks / command_locks: party-wide bits (a stat junction or a
        battle command) stay cleared on ALL GFs until the item arrives; then
        the GFs' DEFAULT bits are re-asserted every tick (vanilla state,
        self-heals reloads). Restores touch only option-governed bits, so
        nothing else is ever force-set.
    Char-record leftovers (magic junctioned to a now-locked stat, an equipped
    locked command) are stripped in the same pass. Waits for items_synced so a
    reconnect race can never revoke a permitted ability."""
    o = ctx.slot_data
    ability = o.get("ability_locks")
    junction = o.get("junction_locks")
    command = o.get("command_locks")
    if not (ability or junction or command):
        return
    if ctx.save_frozen or not ctx.items_synced:
        return

    governed = 0        # bits a lock option owns (restore domain)
    shared_locked = 0   # bits locked on every GF
    locked_junction_bytes: list[int] = []
    locked_command_ids: list[int] = []
    if junction:
        have = received_junction_primaries(ctx)
        for primary, bits in JUNCTION_LOCK_GROUPS.items():
            group = ability_mask(bits)
            governed |= group
            if primary not in have:
                shared_locked |= group
                locked_junction_bytes += memory.JUNCTION_CHAR_BYTES[primary]
    if command:
        have = received_command_ids(ctx)
        for cid in COMMAND_ABILITY_IDS.values():
            governed |= 1 << cid
            if cid not in have:
                shared_locked |= 1 << cid
                locked_command_ids.append(cid)
    signature_locked: dict[int, int] = {}
    if ability:
        permitted = permitted_signature_bits(ctx)
        for gf, ids in GF_SIGNATURE_ABILITIES.items():
            locked = ability_mask(ids) & ~permitted.get(gf, 0)
            if locked:
                signature_locked[gf] = locked

    masks = ctx.ff8.gf_ability_masks_all()
    for gf in range(memory.GF_COUNT):
        locked = shared_locked | signature_locked.get(gf, 0)
        restore = memory.GF_ABILITY_DEFAULTS[gf] & governed & ~locked
        want = (masks[gf] & ~locked) | restore
        if want == masks[gf]:
            continue
        revoked = masks[gf] & ~want
        ctx.ff8.write_gf_abilities(gf, want)
        if revoked:
            names = [GF_ABILITY_NAMES[i] for i in range(revoked.bit_length())
                     if revoked >> i & 1]
            logger.info(f"{GF_ORDER[gf]}: locked — {', '.join(names)} revoked "
                        "(the matching multiworld item unlocks it)")

    stripped = ctx.ff8.strip_locked_char_state(
        tuple(locked_junction_bytes), tuple(locked_command_ids))
    if stripped:
        logger.info(f"Locked junction/command state stripped from "
                    f"{stripped} character record(s)")


async def game_watcher(ctx: FF8Context):
    logger.info("FF8 watcher started; waiting for FF8_EN.exe...")
    while not ctx.exit_event.is_set():
        try:
            if not ctx.ff8.attached:
                if ctx.ff8.attach():
                    ctx.attach_hint_logged = None
                    ctx.prev_gf_flags = None  # fresh baseline; no false edges
                    ctx.magic_expected = None
                    ctx.battle_active = False
                    ctx.party_alive_seen = False
                    ctx.battle_wiped = False
                    ctx.results_seen = False
                else:
                    # Say WHY, once per distinct cause: FF8_EN.exe present but
                    # unopenable, or a near-miss exe (Remastered, non-English,
                    # launcher-only) running instead.
                    hint = ctx.ff8.last_attach_error or memory.find_wrong_process()
                    if hint and hint != ctx.attach_hint_logged:
                        logger.warning(hint)
                        ctx.attach_hint_logged = hint
                    await asyncio.sleep(REHOOK_SECONDS)
                    continue

            if ctx.server and ctx.slot:
                if (ctx.magic_expected is not None
                        and ctx.ff8.read_u16(memory.MODULE_DISPATCH)
                        == memory.MODULE_TITLE):
                    ctx.magic_expected = None   # load menu ahead: re-baseline
                track_battle(ctx)
                await handle_deathlink(ctx)
                await track_goal(ctx)
                await publish_area(ctx)
                if ctx.ff8.is_safe():
                    new_checks = await detect_checks(ctx)
                    enforce_magic(ctx)
                    if new_checks:
                        await ctx.check_locations(new_checks)
                    await grant_items(ctx)
                    enforce_gf_locks(ctx)
        except Exception as e:
            logger.info(f"Lost FF8 process ({type(e).__name__}); re-hooking...")
            ctx.ff8.detach()
        await asyncio.sleep(POLL_SECONDS)


def launch(*launch_args):
    async def main(args):
        ctx = FF8Context(args.connect, args.password)
        if args.name:
            ctx.auth = args.name
        ctx.server_task = asyncio.create_task(server_loop(ctx), name="server loop")
        # get_base_parser only defines --nogui when the process has a console
        # (sys.stdout); under the windowed ArchipelagoLauncher.exe it doesn't
        # exist, so args.nogui would raise AttributeError and kill the client
        # before its window opens.
        if gui_enabled and not getattr(args, "nogui", False):
            ctx.run_gui()
        ctx.run_cli()
        watcher = asyncio.create_task(game_watcher(ctx), name="FF8Watcher")
        await ctx.exit_event.wait()
        watcher.cancel()
        await ctx.shutdown()

    import colorama
    import Utils
    Utils.init_logging("FF8Client")
    parser = get_base_parser(description="Final Fantasy VIII Archipelago Client")
    parser.add_argument("--name", default=None, help="slot name (skips the prompt)")
    # The Launcher passes the WebHost room page's archipelago://slot:pass@host:port
    # link as a positional arg (Component.supports_uri); handle_url_arg turns it
    # into --connect / --name / --password so the client opens pre-connected.
    parser.add_argument("url", nargs="?", help="archipelago:// connection link (from the room page)")
    args = handle_url_arg(parser.parse_args(launch_args), parser=parser)  # base parser provides --nogui
    colorama.init()
    asyncio.run(main(args))
    colorama.deinit()


if __name__ == "__main__":
    launch()
