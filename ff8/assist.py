"""Battle Assist: the 2013 exe's stand-in for the Remastered boosters.

Three client-side toggles, all off by default, none of which touch logic,
generation, or the save:

- ``atb``  — every living ally's ATB is kept full, so a turn is always ready
  (the Remastered "Battle Assist" bar behaviour).
- ``hp``   — living allies are topped up to max HP each tick. KO'd allies
  stay KO'd: reviving from outside skips the engine's own status bookkeeping.
- ``skip`` — random encounters are auto-won: every enemy's HP is zeroed as
  soon as combat starts, and the game runs its own death, victory, EXP, AP
  and drop handling. Only encounters whose scene.out flags are zero qualify;
  a scripted or boss fight (flags set) is always fought for real, as is any
  encounter on NEVER_SKIP.
- ``enc`` — no random encounters: Enc-None is kept in an empty ability slot
  of every main character (the game honours the equipped id without the GF
  having learned it), and taken back out when the toggle goes off. Only the
  slots the assist filled are ever cleared, so a player's own Enc-None stays.

The assist stands down for a whole battle while a DeathLink is pending or
being delivered, so a received death can never be dodged by an instant win
and an HP top-up can never cancel it; ``enc`` is lifted for as long as a
received death is waiting for a fight to land in.
"""

from dataclasses import dataclass, field
import logging

from . import memory
from .encounters import ENCOUNTER_FLAGS, ENCOUNTER_NAMES

logger = logging.getLogger("Client")

# Random-encounter ids the assist must leave alone even though scene.out marks
# them as ordinary fights. Tonberries: the King joins one of these encounters
# mid-battle after enough kills, and his defeat carries the GF check; an
# instant kill would race the engine's own spawn/reward scripts.
NEVER_SKIP: dict[int, str] = {
    236: "Tonberry (the King may join)",
    237: "Tonberry (the King may join)",
    238: "Tonberry (the King may join)",
}

FEATURES = ("skip", "atb", "hp", "enc")


def encounter_name(encounter_id: int) -> str:
    return ENCOUNTER_NAMES.get(encounter_id, f"encounter {encounter_id}")


def skip_verdict(encounter_id: int) -> str | None:
    """None when the encounter may be auto-won; otherwise why it must be
    fought for real."""
    if encounter_id in NEVER_SKIP:
        return NEVER_SKIP[encounter_id]
    if not 0 <= encounter_id < len(ENCOUNTER_FLAGS):
        return "unknown encounter"
    if ENCOUNTER_FLAGS[encounter_id]:
        return "a scripted or boss fight"
    return None


@dataclass
class AssistState:
    atb: bool = False
    hp: bool = False
    skip: bool = False
    enc: bool = False
    # Per-battle bookkeeping (reset on every non-combat tick).
    announced: int | None = None    # encounter id already logged this battle
    stood_down: bool = False        # DeathLink stand-down logged this battle
    # Session tally for /ff8assist.
    skipped: int = 0
    # Ability slots `enc` filled with Enc-None (character, slot); only these
    # are ever cleared again.
    enc_slots: list = field(default_factory=list)
    enc_lifted: bool = False        # DeathLink lift logged

    @property
    def enabled(self) -> bool:
        return self.atb or self.hp or self.skip

    def describe(self) -> str:
        on = [f for f in FEATURES if getattr(self, f)]
        return "+".join(on) if on else "off"

    def _end_battle(self) -> None:
        self.announced = None
        self.stood_down = False


def apply_assist(ff8: memory.FF8Interface, state: AssistState,
                 encounter_id: int, stand_down: bool = False) -> None:
    """One watcher tick. Writes only during real combat (module 3 with the
    results flag down); every write is re-asserted each tick because battle
    init overwrites anything written during the intro (same lesson as
    DeathLink). ``stand_down`` = a DeathLink owns this battle."""
    if not state.enabled:
        state._end_battle()
        return
    in_combat = (ff8.read_u16(memory.MODULE_DISPATCH) == memory.MODULE_BATTLE
                 and ff8.read_u8(memory.POST_BATTLE) == 0)
    if not in_combat:
        state._end_battle()
        return
    if stand_down:
        if not state.stood_down:
            state.stood_down = True
            logger.info("Assist: standing down this battle (DeathLink)")
        return

    if state.skip:
        verdict = skip_verdict(encounter_id)
        if verdict is None:
            ff8.kill_enemies()
            if state.announced != encounter_id:
                state.announced = encounter_id
                state.skipped += 1
                logger.info(f"Assist: auto-winning {encounter_name(encounter_id)}")
        elif state.announced != encounter_id:
            state.announced = encounter_id
            logger.info(f"Assist: {encounter_name(encounter_id)} is {verdict}; "
                        "fighting it for real")
    if state.atb:
        ff8.fill_ally_atb()
    if state.hp:
        ff8.heal_allies()


def apply_enc_none(ff8: memory.FF8Interface, state: AssistState,
                   safe: bool, stand_down: bool = False) -> None:
    """One watcher tick, outside combat. ``safe`` = a field / world-map tick
    (the caller's is_safe(): no menu, no battle), the only time the character
    records may be written. ``stand_down`` = a received death is waiting for
    a fight: Enc-None comes out until it has landed."""
    if not safe:
        return
    if state.enc and not stand_down:
        written = ff8.equip_enc_none()
        if written:
            if not state.enc_slots:
                logger.info("Assist: Enc-None equipped — no random encounters")
            state.enc_slots += written
        state.enc_lifted = False
        return
    if state.enc_slots:
        ff8.unequip_enc_none(state.enc_slots)
        state.enc_slots = []
        if stand_down and state.enc:
            if not state.enc_lifted:
                state.enc_lifted = True
                logger.info("Assist: Enc-None lifted until the received death lands")
        else:
            logger.info("Assist: Enc-None removed")
