"""DeathLink receive/send state machine against a fake process.

Hdot's sync (2026-09-10) showed two dodges: a death that lands as the last
enemy dies leaves the party at 0 HP on the field with the battle counted as a
win, and Phoenix Downs then undo it. The rule now: a received death is retired
only by an observed wipe in real combat, never in the victory phase, and a
battle that ends any other way keeps it pending for the next fight.
"""

import asyncio
import unittest

from ..memory import (ALLY_COUNT, ALLY_CUR_HP, ALLY_MAX_HP, ALLY_STRIDE,
                      BATTLE_ALLIES, MODULE_BATTLE, MODULE_DISPATCH,
                      MODULE_WORLDMAP, POST_BATTLE)
from ..client import handle_deathlink, track_battle
from .test_vehicle_window import FakeProc

MODULE_VICTORY = 100
MODULE_RESULTS = 4


class FakeCtx:
    """Just the attributes track_battle and handle_deathlink touch."""

    def __init__(self):
        self.ff8 = FakeProc()
        self.tags = {"DeathLink"}
        self.player_names = {1: "Wilson"}
        self.slot = 1
        self.battle_active = False
        self.last_encounter = 0
        self.won_encounters = set()
        self.party_alive_seen = False
        self.battle_wiped = False
        self.results_seen = False
        self.last_battle_outcome = ""
        self.pending_deathlink = False
        self.death_sent_this_battle = False
        self.deathlink_received_this_battle = False
        self.deathlink_battle_seen = False
        self.deaths_sent = []

    async def send_death(self, text=""):
        self.deaths_sent.append(text)

    # -- game state helpers --
    def allies(self, hp, mx=1000):
        for i in range(ALLY_COUNT):
            rec = BATTLE_ALLIES + i * ALLY_STRIDE
            self.ff8.write_u16(rec + ALLY_MAX_HP, mx)
            self.ff8.write_u16(rec + ALLY_CUR_HP, hp)

    def hps(self):
        return [self.ff8.read_u16(BATTLE_ALLIES + i * ALLY_STRIDE + ALLY_CUR_HP)
                for i in range(ALLY_COUNT)]

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
        self.ff8.write_u16(MODULE_DISPATCH, MODULE_WORLDMAP)
        self.ff8.write_u8(POST_BATTLE, 0)

    def tick(self, n=1):
        for _ in range(n):
            track_battle(self)
            asyncio.run(handle_deathlink(self))


class TestDeathLinkReceive(unittest.TestCase):
    def setUp(self):
        self.ctx = FakeCtx()
        self.ctx.field()
        self.ctx.tick()

    def test_death_in_combat_wipes_and_retires(self):
        c = self.ctx
        c.combat(); c.allies(hp=500); c.tick()
        c.pending_deathlink = True
        c.tick()                                   # arm + kill
        self.assertEqual(c.hps(), [0, 0, 0])
        self.assertTrue(c.pending_deathlink)       # not yet observed by track_battle
        c.tick()                                   # track_battle sees the wipe
        self.assertFalse(c.pending_deathlink)
        self.assertTrue(c.battle_wiped)
        c.field(); c.tick()
        self.assertEqual(c.deaths_sent, [])        # never echoed back
        self.assertNotIn(0, c.won_encounters)

    def test_death_on_killing_blow_stays_pending_and_win_is_credited(self):
        c = self.ctx
        c.ff8.write_u16(0x1996DA8, 321)            # ENCOUNTER_ID
        c.combat(); c.allies(hp=500); c.tick()
        c.pending_deathlink = True
        c.tick()                                   # armed, party zeroed
        c.victory(); c.tick()                      # engine finished the fight anyway
        c.results(); c.tick(3)
        self.assertTrue(c.pending_deathlink)       # zero HP in the win phase is no wipe
        self.assertFalse(c.battle_wiped)
        c.field(); c.tick()
        self.assertIn(321, c.won_encounters)       # the win is still credited
        # next battle: delivered for real
        c.combat(); c.allies(hp=500); c.tick(3)
        self.assertFalse(c.pending_deathlink)
        self.assertEqual(c.hps(), [0, 0, 0])

    def test_death_during_results_is_deferred(self):
        c = self.ctx
        c.combat(); c.allies(hp=500); c.tick()
        c.results()
        c.pending_deathlink = True
        c.tick(3)
        self.assertEqual(c.hps(), [500, 500, 500])  # untouched
        self.assertTrue(c.pending_deathlink)
        c.field(); c.tick()
        self.assertTrue(c.pending_deathlink)
        c.combat(); c.allies(hp=500); c.tick(3)
        self.assertFalse(c.pending_deathlink)

    def test_death_during_intro_waits_for_live_party(self):
        c = self.ctx
        c.combat(); c.allies(hp=0, mx=0)           # stale structs during init
        c.pending_deathlink = True
        c.tick(2)
        self.assertTrue(c.pending_deathlink)
        self.assertFalse(c.deathlink_received_this_battle)
        c.allies(hp=500); c.tick(3)                # init done, party live
        self.assertFalse(c.pending_deathlink)
        self.assertEqual(c.hps(), [0, 0, 0])

    def test_armed_battle_ending_in_loss_counts_as_delivered(self):
        # The engine can leave combat on the same tick we zero the party, so
        # no tick observes the all-zero party. A non-win end while armed is
        # the game over.
        c = self.ctx
        c.combat(); c.allies(hp=500); c.tick()
        c.pending_deathlink = True
        c.tick()                                   # armed + zeroed
        c.field(); c.tick()                        # module left combat at once
        self.assertFalse(c.pending_deathlink)
        self.assertEqual(c.deaths_sent, [])

    def test_field_revive_does_not_bring_the_death_back(self):
        c = self.ctx
        c.combat(); c.allies(hp=500); c.tick()
        c.pending_deathlink = True
        c.tick(3)
        self.assertFalse(c.pending_deathlink)
        c.field(); c.tick()
        c.combat(); c.allies(hp=500); c.tick(3)    # revived, next fight
        self.assertEqual(c.hps(), [500, 500, 500])
        self.assertEqual(c.deaths_sent, [])


class TestDeathLinkSend(unittest.TestCase):
    def test_own_wipe_sends_once(self):
        c = FakeCtx(); c.field(); c.tick()
        c.combat(); c.allies(hp=500); c.tick()
        c.allies(hp=0); c.tick(3)
        self.assertEqual(len(c.deaths_sent), 1)
        self.assertIn("Wilson", c.deaths_sent[0])
        c.field(); c.tick()
        self.assertEqual(len(c.deaths_sent), 1)

    def test_tag_off_does_nothing(self):
        c = FakeCtx(); c.tags = set(); c.field(); c.tick()
        c.combat(); c.allies(hp=500); c.pending_deathlink = True; c.tick(3)
        self.assertEqual(c.hps(), [500, 500, 500])
        c.allies(hp=0); c.tick(3)
        self.assertEqual(c.deaths_sent, [])
