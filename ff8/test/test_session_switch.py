"""Reusing one client for a different seed/slot. AP 0.6.8 core clears its
session state before replaying the old session's checks and goal on Connected;
0.6.7 replayed them into the new seed. The client hooks the 0.6.8 reset for its
own per-seed state (the goal, the Ultimecia state machine, a pending DeathLink)
and backports it to 0.6.7 from RoomInfo."""

import asyncio
import unittest
from unittest import mock

import Utils
from CommonClient import process_server_cmd
from NetUtils import NetworkPlayer, NetworkSlot, SlotType

from .. import client
from ..client import FF8Context
from ..items import BASE_ID

GAME = "Final Fantasy VIII"
OLD_CHECK = BASE_ID + 1


def run(steps):
    """Run steps(ctx) against a fresh, unattached FF8Context."""
    async def go():
        ctx = FF8Context(None, None)
        ctx.auth = "Squall"
        ctx.send_msgs = mock.AsyncMock()
        try:
            await steps(ctx)
        finally:
            await ctx.shutdown()
        return ctx
    return asyncio.run(go())


def finish_old_session(ctx, seed="A"):
    """ctx as a client that played (and goaled) seed `seed` as Squall."""
    ctx.ff8_server_seed_name = seed
    ctx.ff8_session_identity = (seed, "Squall")
    ctx.locations_checked = {OLD_CHECK}
    ctx.finished_game = True
    ctx.goal_sent = True
    ctx.ult_phase = 3
    ctx.pending_deathlink = True


def connected_packet():
    return {"cmd": "Connected", "team": 0, "slot": 1,
            "slot_info": {"1": NetworkSlot("Squall", GAME, SlotType.player)},
            "players": [NetworkPlayer(0, 1, "Squall", "Squall")],
            "missing_locations": [OLD_CHECK], "checked_locations": [],
            "slot_data": {}, "hint_points": 0}


class TestResetSessionState(unittest.TestCase):
    def test_reset_clears_core_and_ff8_session_state(self):
        async def steps(ctx):
            finish_old_session(ctx)
            ctx.reset_session_state()
        ctx = run(steps)
        self.assertEqual(ctx.locations_checked, set())
        self.assertFalse(ctx.finished_game)
        self.assertFalse(ctx.goal_sent)
        self.assertEqual(ctx.ult_phase, -1)
        self.assertFalse(ctx.pending_deathlink)
        self.assertTrue(ctx.session_switched)


class TestRoomInfoBackport(unittest.TestCase):
    """AP 0.6.7 has no core reset: the client runs its own from RoomInfo."""

    def roominfo(self, seed, core_resets=False):
        async def steps(ctx):
            finish_old_session(ctx, seed="A")
            with mock.patch.object(client, "CORE_RESETS_SESSION", core_resets):
                ctx.on_package("RoomInfo", {"seed_name": seed})
        return run(steps)

    def test_different_seed_resets_before_connected(self):
        ctx = self.roominfo("B")
        self.assertEqual(ctx.locations_checked, set())
        self.assertFalse(ctx.finished_game)
        self.assertFalse(ctx.goal_sent)

    def test_reconnect_to_same_seed_keeps_state(self):
        ctx = self.roominfo("A")
        self.assertEqual(ctx.locations_checked, {OLD_CHECK})
        self.assertTrue(ctx.goal_sent)

    def test_core_0_6_8_owns_the_reset(self):
        ctx = self.roominfo("B", core_resets=True)
        self.assertEqual(ctx.locations_checked, {OLD_CHECK})   # left to Connected
        self.assertTrue(ctx.goal_sent)


class TestConnectedAfterSwitch(unittest.TestCase):
    def test_deathlink_does_not_carry_into_a_slot_without_it(self):
        async def steps(ctx):
            ctx.tags.add("DeathLink")
            ctx.session_switched = True
            with mock.patch.object(ctx, "load_sidecar"):
                ctx.on_package("Connected", connected_packet())
            await asyncio.sleep(0)   # let update_death_link run
        ctx = run(steps)
        self.assertNotIn("DeathLink", ctx.tags)
        self.assertFalse(ctx.session_switched)

    def test_reconnect_keeps_manual_deathlink(self):
        async def steps(ctx):
            ctx.tags.add("DeathLink")
            with mock.patch.object(ctx, "load_sidecar"):
                ctx.on_package("Connected", connected_packet())
            await asyncio.sleep(0)
        self.assertIn("DeathLink", run(steps).tags)


@unittest.skipUnless(client.CORE_RESETS_SESSION, "core session reset is AP 0.6.8+")
class TestCoreConnectedReplay(unittest.TestCase):
    """Drive core's own Connected handler (AP 0.6.8+)."""

    def connect(self, new_seed):
        async def steps(ctx):
            finish_old_session(ctx)
            ctx.server_address = "localhost:38281"
            ctx.connected_identity = ("A", 0, 1)
            ctx.server_seed_name = ctx.ff8_server_seed_name = new_seed
            with mock.patch.object(Utils, "persistent_store"), \
                    mock.patch.object(ctx, "load_sidecar"):
                await process_server_cmd(ctx, connected_packet())
        ctx = run(steps)
        sent = [msg["cmd"] for call in ctx.send_msgs.await_args_list for msg in call.args[0]]
        return ctx, sent

    def test_switch_does_not_replay_old_checks_or_goal(self):
        ctx, sent = self.connect("B")
        self.assertNotIn("LocationChecks", sent)
        self.assertNotIn("StatusUpdate", sent)
        self.assertFalse(ctx.goal_sent)
        self.assertEqual(ctx.ff8_session_identity, ("B", "Squall"))

    def test_reconnect_replays_offline_checks_and_goal(self):
        ctx, sent = self.connect("A")
        self.assertIn("LocationChecks", sent)
        self.assertIn("StatusUpdate", sent)
        self.assertTrue(ctx.goal_sent)
