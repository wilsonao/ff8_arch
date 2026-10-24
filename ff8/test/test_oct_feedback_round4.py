"""Regression tests for the Discord report of 17 Oct 2026.

1. "First Draw: Flare" could not be earned once the multiworld had sent Flare.
   The game sets magic_drawn_once only in battle (FF8_EN.exe 0x48B7A0, and the
   battle start/end sweeps at 0x48B7E0 / 0x48B8B0 over the party's stock), so
   a draw point or a refine never raised the bit on the tick of the draw, and
   the client cleared the next battle's bit as housekeeping. Drawing from a
   world-map point, refining a Flare Stone and receiving Flare all failed.
2. A Ragnarok sent with !getitem promised to appear and never did; a
   /ff8warp left the story's ship behind for good.
"""

import asyncio
import struct
import unittest
from unittest import mock

from .. import memory
from ..client import (FF8Context, VEHICLE_PARK_NUDGE, grant_items,
                      resolve_pending_draws, seed_vehicles, slot_spell,
                      warp_player)
from ..items import BASE_ID, ITEM_TABLE
from ..memory import (DREAM_ACTIVE, DREAM_FLAGS, GAME_MOMENT, MODULE_DISPATCH,
                      WM_CHAR_POS, WM_RAGNAROK_POS)
from ..warp import WARP_BY_KEY
from .test_feedback_fixes import DrawCtx
from .test_oct_feedback_round3 import fires
from .test_vehicle_window import RAG_ITEM, RAG_THRESHOLD, FakeCtx, FakeProc

FLARE = 15
SOLLET = 253            # vanilla world-map draw point: Flare, Sollet Mountains
FLARE_X5 = next(BASE_ID + d.id_offset for d in ITEM_TABLE if d.name == "Flare x5")


def granted_flare():
    """Flare x5 came from the multiworld before Flare was ever drawn."""
    ctx = DrawCtx()
    ctx.set_stock(0, 0, FLARE, 5)
    ctx.magic_pending.add(FLARE)
    ctx.tick()
    return ctx


class TestFirstDrawWithoutABattle(unittest.TestCase):
    def test_the_sollet_point_gives_flare(self):
        self.assertEqual(slot_spell(DrawCtx(), SOLLET), FLARE)

    def test_a_world_draw_point_counts_at_once(self):
        ctx = granted_flare()
        ctx.set_draw_state(SOLLET, 2)            # drawn; the game sets no bit
        ctx.tick()
        self.assertTrue(ctx.drawn(FLARE))
        self.assertNotIn(FLARE, ctx.magic_pending)
        self.assertTrue(fires(ctx.ff8, "First Draw: Flare"))
        ctx.tick()                               # the next battle's sweep: kept
        self.assertTrue(ctx.drawn(FLARE))

    def test_a_refine_counts_and_survives_the_clamp(self):
        ctx = granted_flare()
        ctx.set_stock(0, 0, FLARE, 6)            # Flare Stone -> Flare (F Mag-RF)
        ctx.tick()
        self.assertTrue(ctx.drawn(FLARE))
        self.assertNotIn(FLARE, ctx.magic_pending)
        ctx.set_stock(0, 0, FLARE, 5)            # checks-only takes the 6th back
        ctx.tick()
        self.assertTrue(ctx.drawn(FLARE))

    def test_a_draw_the_clamp_takes_away_entirely_still_counts(self):
        # checks-only, Flare never received (cap 0): the stock is repossessed
        # before any battle, so the game's sweep would never see it
        ctx = DrawCtx()
        ctx.tick()
        ctx.set_stock(0, 0, FLARE, 3)
        ctx.set_draw_state(SOLLET, 1)
        ctx.tick()
        ctx.set_stock(0, 0, 0, 0)
        ctx.tick()
        self.assertTrue(ctx.drawn(FLARE))
        self.assertTrue(fires(ctx.ff8, "First Draw: Flare"))

    def test_a_refill_is_not_a_draw(self):
        ctx = DrawCtx()
        ctx.set_stock(0, 0, FLARE, 5)
        ctx.set_draw_state(SOLLET, 2)            # drawn long ago
        ctx.magic_pending.add(FLARE)
        ctx.tick()
        ctx.set_draw_state(SOLLET, 0)            # the point refilled
        ctx.tick()
        self.assertFalse(ctx.drawn(FLARE))
        self.assertIn(FLARE, ctx.magic_pending)

    def test_stock_back_from_a_dream_is_not_a_draw(self):
        ctx = granted_flare()
        ctx.ff8.write_u8(DREAM_FLAGS, DREAM_ACTIVE)
        ctx.set_stock(0, 0, 0, 0)                # Laguna's party holds it now
        ctx.tick()
        ctx.ff8.write_u8(DREAM_FLAGS, 0)
        ctx.set_stock(0, 0, FLARE, 5)            # back with Squall's party
        ctx.tick()
        self.assertFalse(ctx.drawn(FLARE))
        self.assertIn(FLARE, ctx.magic_pending)
        ctx.set_drawn(FLARE)                     # battle sweep: still housekeeping
        ctx.tick()
        self.assertFalse(ctx.drawn(FLARE))


def real_ctx(steps, items, slot_data=None, moment=1400):
    """Run steps(ctx) on a real context with `items` received."""
    async def go():
        ctx = FF8Context(None, None)
        ctx.ff8 = FakeProc()
        ctx.slot = 1
        ctx.slot_data = slot_data or {}
        ctx.send_msgs = mock.AsyncMock()
        ctx.save_fingerprint = 0x1234
        ctx.items_received = [mock.Mock(item=i, player=1) for i in items]
        ctx.ff8.write_u16(GAME_MOMENT, moment)
        ctx.ff8.write_u16(MODULE_DISPATCH, memory.MODULE_FIELD)
        try:
            await steps(ctx)
        finally:
            await ctx.shutdown()
        return ctx
    return asyncio.run(go())


class TestGrantIsNotADraw(unittest.TestCase):
    def test_flare_from_the_multiworld_does_not_count(self):
        async def steps(ctx):
            resolve_pending_draws(ctx, ctx.ff8.snapshot())   # this tick's detect
            await grant_items(ctx)
            resolve_pending_draws(ctx, ctx.ff8.snapshot())   # the next tick
        ctx = real_ctx(steps, [FLARE_X5])
        self.assertEqual(ctx.ff8.snapshot().magic_totals().get(FLARE), 5)
        self.assertIn(FLARE, ctx.magic_pending)
        self.assertFalse(fires(ctx.ff8, "First Draw: Flare"))

    def test_a_draw_after_the_grant_counts(self):
        async def steps(ctx):
            resolve_pending_draws(ctx, ctx.ff8.snapshot())
            await grant_items(ctx)
            resolve_pending_draws(ctx, ctx.ff8.snapshot())
            ctx.ff8.write_u8(memory.DRAW_POINTS + SOLLET // 4, 2 << (SOLLET % 4) * 2)
            resolve_pending_draws(ctx, ctx.ff8.snapshot())
        ctx = real_ctx(steps, [FLARE_X5])
        self.assertNotIn(FLARE, ctx.magic_pending)
        self.assertTrue(fires(ctx.ff8, "First Draw: Flare"))


class TestRagnarokMessage(unittest.TestCase):
    def logged(self, slot_data, moment):
        out = []

        async def steps(ctx):
            with self.assertLogs("Client", level="INFO") as logs:
                await grant_items(ctx)
            out.extend(logs.output)
        real_ctx(steps, [RAG_ITEM], slot_data, moment)
        return " ".join(out)

    def test_option_off_says_it_does_nothing(self):
        self.assertIn("Vehicle Unlocks is off", self.logged({}, 3300))

    def test_past_the_hand_over_says_the_ship_is_already_yours(self):
        self.assertIn("already yours", self.logged({"vehicle_unlocks": 1}, 3300))

    def test_early_still_promises_the_ship(self):
        self.assertIn("appear beside you", self.logged({"vehicle_unlocks": 1}, 205))

    def test_withheld_ship_still_promises_it(self):
        text = self.logged({"vehicle_unlocks": 1, "vehicle_gates": 1}, 3300)
        self.assertIn("appear beside you", text)


class TestShipFollowsAWarp(unittest.TestCase):
    """Past the story's hand-over the ship stays where it was left, so a warp
    used to strand it. A client warp on foot now brings it along."""

    def setUp(self):
        self.ctx = FakeCtx()
        self.ctx.ff8.write_bytes(WM_RAGNAROK_POS, struct.pack("<iihh", 100, 200, -400, 0))
        self.ctx.set_state(module=2, moment=RAG_THRESHOLD + 50)
        self.dest = WARP_BY_KEY["esthar"]

    def rag_xy(self):
        return struct.unpack("<ii", self.ctx.ff8.read_bytes(WM_RAGNAROK_POS, 8))

    def arrive(self):
        # the game mirrors the warped position into the savemap
        self.ctx.ff8.write_bytes(WM_CHAR_POS, struct.pack(
            "<iihh", self.dest.x, self.dest.y, self.dest.z, 0))

    def test_the_next_battle_brings_it_beside_you(self):
        self.assertTrue(warp_player(self.ctx, self.dest))
        self.arrive()
        seed_vehicles(self.ctx)                          # still on the map: no park
        self.assertEqual(self.rag_xy(), (100, 200))
        self.ctx.ff8.write_u16(MODULE_DISPATCH, 3)       # a battle
        seed_vehicles(self.ctx)
        self.assertEqual(self.rag_xy(),
                         (self.dest.x + VEHICLE_PARK_NUDGE["ragnarok"], self.dest.y))
        self.assertFalse(self.ctx.vehicle_follow)

    def test_without_a_warp_it_stays_put(self):
        self.arrive()                                    # walked here
        self.ctx.ff8.write_u16(MODULE_DISPATCH, 3)
        seed_vehicles(self.ctx)
        self.assertEqual(self.rag_xy(), (100, 200))

    def test_a_warp_while_flying_moves_the_ship_itself(self):
        self.ctx.set_state(module=2, moment=RAG_THRESHOLD + 50, avatar=0x31)
        self.assertTrue(warp_player(self.ctx, self.dest))
        self.assertFalse(getattr(self.ctx, "vehicle_follow", False))


if __name__ == "__main__":
    unittest.main()
