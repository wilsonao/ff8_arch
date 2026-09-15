"""Battle Assist against a fake process: which encounters may be auto-won,
and that the three toggles write only during real combat, never over a
DeathLink, and never revive anyone.

The encounter table is generated from the game's scene.out; the tests pin
the property the assist relies on — every boss the randomizer tracks is
flagged, ordinary wild fights are not.
"""

import unittest

from .. import locations as L
from ..assist import (NEVER_SKIP, AssistState, apply_assist, apply_enc_none,
                      skip_verdict)
from ..encounters import ENCOUNTER_COUNT, ENCOUNTER_FLAGS, ENCOUNTER_NAMES
from ..memory import (ALLY_COUNT, ALLY_STRIDE, BATTLE_ALLIES, BATTLE_ENEMIES,
                      CHAR_ABILITIES_LEN, CHAR_ABILITIES_OFFSET, CHAR_BASE,
                      CHAR_STRIDE, ENC_NONE_ABILITY, ENEMY_COUNT, ENEMY_STRIDE,
                      MODULE_BATTLE, MODULE_DISPATCH, MODULE_FIELD, POST_BATTLE,
                      SLOT_ATB_CUR, SLOT_ATB_MAX, SLOT_CUR_HP, SLOT_MAX_HP)
from .test_vehicle_window import FakeProc

MODULE_VICTORY = 100
MODULE_RESULTS = 4
ENC_MESMERIZE_SNOW = 593    # plain wild fight (the live probe's last battle)
ENC_GEEZARD_CLIFFS = 22
ATB_MAX = 12000


class TestEncounterTable(unittest.TestCase):
    def test_table_shape(self):
        self.assertEqual(len(ENCOUNTER_FLAGS), ENCOUNTER_COUNT)
        self.assertGreater(sum(1 for f in ENCOUNTER_FLAGS if f), 100)
        self.assertGreater(len(ENCOUNTER_NAMES), 800)
        self.assertEqual(ENCOUNTER_NAMES[ENC_MESMERIZE_SNOW], "Mesmerize (Snow)")

    def test_every_tracked_boss_is_flagged(self):
        ids = {name: v for name, v in vars(L).items()
               if name.startswith("ENC_") and isinstance(v, int)}
        for table in (L.ENC_CASTLE_BOSSES, L.ENC_PROPAGATORS, L.ENC_UFO_SIGHTINGS):
            ids.update(table)
        self.assertGreater(len(ids), 30)
        unflagged = [n for n, v in ids.items() if not ENCOUNTER_FLAGS[v]]
        self.assertEqual(unflagged, [])

    def test_wild_fights_are_not_flagged(self):
        for enc in (ENC_MESMERIZE_SNOW, ENC_GEEZARD_CLIFFS):
            self.assertEqual(ENCOUNTER_FLAGS[enc], 0)


class TestSkipVerdict(unittest.TestCase):
    def test_random_encounter_is_skippable(self):
        self.assertIsNone(skip_verdict(ENC_MESMERIZE_SNOW))

    def test_bosses_are_not(self):
        for enc in (L.ENC_IFRIT, L.ENC_OMEGA, L.ENC_ODIN, L.ENC_PUPU):
            self.assertIn("scripted", skip_verdict(enc))

    def test_tonberries_are_exempt(self):
        for enc in NEVER_SKIP:
            self.assertEqual(ENCOUNTER_FLAGS[enc], 0)       # would otherwise qualify
            self.assertIn("Tonberry", skip_verdict(enc))

    def test_out_of_range(self):
        self.assertIsNotNone(skip_verdict(ENCOUNTER_COUNT))
        self.assertIsNotNone(skip_verdict(-1))


class Battle:
    """FakeProc plus helpers for the slot structs the assist touches."""

    def __init__(self):
        self.ff8 = FakeProc()
        self.state = AssistState()
        # allies: two wounded, one KO'd
        self.ally(0, hp=500, mx=1000, atb=100)
        self.ally(1, hp=1000, mx=1000, atb=ATB_MAX)
        self.ally(2, hp=0, mx=900, atb=0)
        # enemies: two alive, one dead, one empty slot
        self.enemy(0, hp=800, mx=800)
        self.enemy(1, hp=70000, mx=70000)          # needs the u32 path
        self.enemy(2, hp=0, mx=500)
        self.combat()

    def ally(self, i, hp, mx, atb):
        rec = BATTLE_ALLIES + i * ALLY_STRIDE
        self.ff8.write_u32(rec + SLOT_MAX_HP, mx)
        self.ff8.write_u32(rec + SLOT_CUR_HP, hp)
        self.ff8.write_u32(rec + SLOT_ATB_MAX, ATB_MAX if mx else 0)
        self.ff8.write_u32(rec + SLOT_ATB_CUR, atb)

    def enemy(self, i, hp, mx):
        rec = BATTLE_ENEMIES + i * ENEMY_STRIDE
        self.ff8.write_u32(rec + SLOT_MAX_HP, mx)
        self.ff8.write_u32(rec + SLOT_CUR_HP, hp)

    def ally_hps(self):
        return [self.ff8.read_u32(BATTLE_ALLIES + i * ALLY_STRIDE + SLOT_CUR_HP)
                for i in range(ALLY_COUNT)]

    def ally_atbs(self):
        return [self.ff8.read_u32(BATTLE_ALLIES + i * ALLY_STRIDE + SLOT_ATB_CUR)
                for i in range(ALLY_COUNT)]

    def enemy_hps(self):
        return [self.ff8.read_u32(BATTLE_ENEMIES + i * ENEMY_STRIDE + SLOT_CUR_HP)
                for i in range(ENEMY_COUNT)]

    def combat(self):
        self.ff8.write_u16(MODULE_DISPATCH, MODULE_BATTLE)
        self.ff8.write_u8(POST_BATTLE, 0)

    def victory(self):
        self.ff8.write_u16(MODULE_DISPATCH, MODULE_VICTORY)
        self.ff8.write_u8(POST_BATTLE, 1)

    def results(self):
        self.ff8.write_u16(MODULE_DISPATCH, MODULE_RESULTS)
        self.ff8.write_u8(POST_BATTLE, 1)

    def field(self):
        self.ff8.write_u16(MODULE_DISPATCH, MODULE_FIELD)
        self.ff8.write_u8(POST_BATTLE, 0)

    def tick(self, encounter=ENC_MESMERIZE_SNOW, n=1, stand_down=False):
        for _ in range(n):
            apply_assist(self.ff8, self.state, encounter, stand_down=stand_down)


UNTOUCHED_ENEMIES = [800, 70000, 0, 0]
UNTOUCHED_ALLIES = [500, 1000, 0]
UNTOUCHED_ATBS = [100, ATB_MAX, 0]


class TestApplyAssist(unittest.TestCase):
    def test_disabled_writes_nothing(self):
        b = Battle()
        b.tick(n=3)
        self.assertEqual(b.enemy_hps(), UNTOUCHED_ENEMIES)
        self.assertEqual(b.ally_hps(), UNTOUCHED_ALLIES)
        self.assertEqual(b.ally_atbs(), UNTOUCHED_ATBS)

    def test_skip_zeroes_living_enemies_only(self):
        b = Battle()
        b.state.skip = True
        with self.assertLogs("Client", level="INFO") as logs:
            b.tick(n=3)
        self.assertEqual(b.enemy_hps(), [0, 0, 0, 0])
        self.assertEqual(b.ally_hps(), UNTOUCHED_ALLIES)      # skip alone heals nobody
        self.assertEqual(b.ally_atbs(), UNTOUCHED_ATBS)
        self.assertEqual(b.state.skipped, 1)                  # counted once per battle
        self.assertEqual(len(logs.output), 1)
        self.assertIn("Mesmerize (Snow)", logs.output[0])

    def test_skip_leaves_bosses_alone(self):
        b = Battle()
        b.state.skip = True
        with self.assertLogs("Client", level="INFO") as logs:
            b.tick(encounter=L.ENC_IFRIT, n=2)
        self.assertEqual(b.enemy_hps(), UNTOUCHED_ENEMIES)
        self.assertEqual(b.state.skipped, 0)
        self.assertEqual(len(logs.output), 1)
        self.assertIn("fighting it for real", logs.output[0])

    def test_skip_leaves_tonberries_alone(self):
        b = Battle()
        b.state.skip = True
        b.tick(encounter=236)
        self.assertEqual(b.enemy_hps(), UNTOUCHED_ENEMIES)

    def test_no_writes_outside_real_combat(self):
        b = Battle()
        b.state.skip = b.state.atb = b.state.hp = True
        for phase in (b.victory, b.results, b.field):
            phase()
            b.tick()
            self.assertEqual(b.enemy_hps(), UNTOUCHED_ENEMIES, phase.__name__)
            self.assertEqual(b.ally_hps(), UNTOUCHED_ALLIES, phase.__name__)
            self.assertEqual(b.ally_atbs(), UNTOUCHED_ATBS, phase.__name__)
        # the self-test's fake battle: results flag up with the module still 3
        b.combat()
        b.ff8.write_u8(POST_BATTLE, 1)
        b.tick()
        self.assertEqual(b.enemy_hps(), UNTOUCHED_ENEMIES)

    def test_each_battle_is_announced_and_counted_once(self):
        b = Battle()
        b.state.skip = True
        b.tick(n=2)
        b.field()
        b.tick()
        b.combat()
        b.enemy(0, hp=300, mx=300)
        with self.assertLogs("Client", level="INFO") as logs:
            b.tick(n=2)
        self.assertEqual(b.state.skipped, 2)
        self.assertEqual(len(logs.output), 1)
        self.assertEqual(b.enemy_hps()[0], 0)

    def test_deathlink_stand_down(self):
        b = Battle()
        b.state.skip = b.state.atb = b.state.hp = True
        with self.assertLogs("Client", level="INFO") as logs:
            b.tick(n=3, stand_down=True)
        self.assertEqual(b.enemy_hps(), UNTOUCHED_ENEMIES)
        self.assertEqual(b.ally_hps(), UNTOUCHED_ALLIES)
        self.assertEqual(b.ally_atbs(), UNTOUCHED_ATBS)
        self.assertEqual(b.state.skipped, 0)
        self.assertEqual(len(logs.output), 1)
        self.assertIn("DeathLink", logs.output[0])

    def test_atb_fills_living_allies(self):
        b = Battle()
        b.state.atb = True
        b.tick()
        self.assertEqual(b.ally_atbs(), [ATB_MAX, ATB_MAX, 0])   # KO'd ally untouched
        self.assertEqual(b.ally_hps(), UNTOUCHED_ALLIES)
        self.assertEqual(b.enemy_hps(), UNTOUCHED_ENEMIES)

    def test_hp_heals_but_never_revives(self):
        b = Battle()
        b.state.hp = True
        b.tick()
        self.assertEqual(b.ally_hps(), [1000, 1000, 0])
        self.assertEqual(b.ally_atbs(), UNTOUCHED_ATBS)
        self.assertEqual(b.enemy_hps(), UNTOUCHED_ENEMIES)

    def test_describe(self):
        s = AssistState()
        self.assertEqual(s.describe(), "off")
        s.skip = s.hp = True
        self.assertEqual(s.describe(), "skip+hp")
        s.enc = True
        self.assertEqual(s.describe(), "skip+hp+enc")


class TestEncNone(unittest.TestCase):
    """`enc`: Enc-None goes into the first empty ability slot of every main
    character on a safe tick, only the slots the assist filled are cleared
    again, and a pending DeathLink lifts it."""

    def setUp(self):
        self.ff8 = FakeProc()
        self.state = AssistState(enc=True)
        # Squall: one ability equipped; Zell: full; Irvine: empty record;
        # Quistis already has her own Enc-None in slot 0.
        self.set_abilities(0, [42, 0, 0, 0])
        self.set_abilities(1, [42, 43, 44, 45])
        self.set_abilities(2, [0, 0, 0, 0])
        self.set_abilities(3, [ENC_NONE_ABILITY, 0, 0, 0])

    def rec(self, i):
        return CHAR_BASE + i * CHAR_STRIDE + CHAR_ABILITIES_OFFSET

    def set_abilities(self, i, slots):
        self.ff8.write_bytes(self.rec(i), bytes(slots))

    def abilities(self, i):
        return list(self.ff8.read_bytes(self.rec(i), CHAR_ABILITIES_LEN))

    def tick(self, safe=True, stand_down=False):
        apply_enc_none(self.ff8, self.state, safe, stand_down=stand_down)

    def test_fills_first_empty_slot_on_a_safe_tick(self):
        self.tick()
        self.assertEqual(self.abilities(0), [42, ENC_NONE_ABILITY, 0, 0])
        self.assertEqual(self.abilities(1), [42, 43, 44, 45])        # no room
        self.assertEqual(self.abilities(2), [ENC_NONE_ABILITY, 0, 0, 0])
        self.assertEqual(self.abilities(3), [ENC_NONE_ABILITY, 0, 0, 0])  # already
        self.assertEqual(sorted(self.state.enc_slots), [(0, 1), (2, 0), (4, 0), (5, 0)])

    def test_idempotent(self):
        self.tick()
        slots = list(self.state.enc_slots)
        self.tick()
        self.assertEqual(self.state.enc_slots, slots)
        self.assertEqual(self.abilities(0), [42, ENC_NONE_ABILITY, 0, 0])

    def test_unsafe_tick_writes_nothing(self):
        self.tick(safe=False)
        self.assertEqual(self.abilities(0), [42, 0, 0, 0])
        self.assertEqual(self.state.enc_slots, [])

    def test_off_clears_only_what_it_wrote(self):
        self.tick()
        self.state.enc = False
        self.tick()
        self.assertEqual(self.abilities(0), [42, 0, 0, 0])
        self.assertEqual(self.abilities(2), [0, 0, 0, 0])
        self.assertEqual(self.abilities(3), [ENC_NONE_ABILITY, 0, 0, 0])  # the player's own
        self.assertEqual(self.state.enc_slots, [])

    def test_player_change_is_respected_on_removal(self):
        self.tick()
        self.set_abilities(0, [42, 60, 0, 0])      # player swapped the slot
        self.state.enc = False
        self.tick()
        self.assertEqual(self.abilities(0), [42, 60, 0, 0])

    def test_deathlink_lifts_and_restores(self):
        self.tick()
        self.tick(stand_down=True)
        self.assertEqual(self.abilities(0), [42, 0, 0, 0])
        self.assertTrue(self.state.enc)
        self.tick()
        self.assertEqual(self.abilities(0), [42, ENC_NONE_ABILITY, 0, 0])

    def test_disabled_never_touches_records(self):
        self.state.enc = False
        self.tick()
        self.assertEqual(self.abilities(0), [42, 0, 0, 0])
        self.assertEqual(self.abilities(2), [0, 0, 0, 0])


if __name__ == "__main__":
    unittest.main()
