"""Phase 4 options from the Sep 2026 beta thread: card rules kept in force,
enemy power scaling, the AP multiplier, and the Triple Triad rule-check split.
Memory-side behaviour runs against the fake process; generation-side against
the world."""

import unittest

from .. import memory
from ..client import (apply_ap_multiplier, apply_enemy_power, enforce_tt_rules,
                      TT_RULES_NO_RANDOM, TT_RULES_OPEN_NO_RANDOM)
from ..locations import RANDOM_ABOLITION_LOCATIONS
from . import ALL_TOGGLES_ON, FF8TestBase
from .test_vehicle_window import FakeProc

VIRGIN_RULES = bytes.fromhex("01020c0e8890dfc0")


class Ctx:
    def __init__(self, **slot_data):
        self.ff8 = FakeProc()
        self.slot_data = slot_data
        self.tt_rules_logged = False
        self.enemy_power_written = {}
        self.enemy_power_logged = False
        self.gf_ap_prev = None
        self.gf_mask_prev = None


class TestTripleTriadRules(unittest.TestCase):
    def test_no_random_clears_bit_everywhere_and_keeps_others(self):
        ctx = Ctx(triple_triad_rules=TT_RULES_NO_RANDOM)
        ctx.ff8.write_bytes(memory.TT_RULES, VIRGIN_RULES)
        enforce_tt_rules(ctx)
        out = ctx.ff8.read_bytes(memory.TT_RULES, 8)
        for a, b in zip(VIRGIN_RULES, out):
            self.assertEqual(b, a & ~memory.TT_RULE_RANDOM)
        self.assertTrue(ctx.tt_rules_logged)
        # a game spread Random back into Balamb: re-applied on the next tick
        ctx.ff8.write_u8(memory.TT_RULES, 0x01 | memory.TT_RULE_RANDOM)
        enforce_tt_rules(ctx)
        self.assertEqual(ctx.ff8.read_u8(memory.TT_RULES), 0x01)

    def test_open_no_random_sets_open(self):
        ctx = Ctx(triple_triad_rules=TT_RULES_OPEN_NO_RANDOM)
        ctx.ff8.write_bytes(memory.TT_RULES, VIRGIN_RULES)
        enforce_tt_rules(ctx)
        out = ctx.ff8.read_bytes(memory.TT_RULES, 8)
        self.assertTrue(all(b & memory.TT_RULE_OPEN for b in out))
        self.assertFalse(any(b & memory.TT_RULE_RANDOM for b in out))

    def test_vanilla_touches_nothing(self):
        ctx = Ctx(triple_triad_rules=0)
        ctx.ff8.write_bytes(memory.TT_RULES, VIRGIN_RULES)
        enforce_tt_rules(ctx)
        self.assertEqual(ctx.ff8.read_bytes(memory.TT_RULES, 8), VIRGIN_RULES)


class TestEnemyPower(unittest.TestCase):
    def _enemy(self, ctx, slot, max_hp, cur_hp, stats):
        rec = memory.BATTLE_ENEMIES + slot * memory.ENEMY_STRIDE
        ctx.ff8.write_u32(rec + memory.SLOT_MAX_HP, max_hp)
        ctx.ff8.write_u32(rec + memory.SLOT_CUR_HP, cur_hp)
        for off, v in zip((memory.SLOT_STR, memory.SLOT_VIT, memory.SLOT_MAG, memory.SLOT_SPR), stats):
            ctx.ff8.write_u8(rec + off, v)

    def _read(self, ctx, slot):
        rec = memory.BATTLE_ENEMIES + slot * memory.ENEMY_STRIDE
        return (ctx.ff8.read_u32(rec + memory.SLOT_MAX_HP), ctx.ff8.read_u32(rec + memory.SLOT_CUR_HP),
                [ctx.ff8.read_u8(rec + off) for off in
                 (memory.SLOT_STR, memory.SLOT_VIT, memory.SLOT_MAG, memory.SLOT_SPR)])

    def test_scales_once_per_battle(self):
        ctx = Ctx(enemy_power=50)
        ctx.ff8.write_u16(memory.MODULE_DISPATCH, memory.MODULE_BATTLE)
        self._enemy(ctx, 0, 1000, 1000, (40, 20, 30, 0))
        apply_enemy_power(ctx)
        self.assertEqual(self._read(ctx, 0), (500, 500, [20, 10, 15, 0]))   # 0 Vit stays 0
        apply_enemy_power(ctx)                                             # not scaled again
        self.assertEqual(self._read(ctx, 0), (500, 500, [20, 10, 15, 0]))
        self.assertEqual(self._read(ctx, 1)[0], 0)                         # empty slot untouched

    def test_rescales_a_replacement_enemy_and_resets_out_of_combat(self):
        ctx = Ctx(enemy_power=50)
        ctx.ff8.write_u16(memory.MODULE_DISPATCH, memory.MODULE_BATTLE)
        self._enemy(ctx, 0, 1000, 1000, (40, 20, 30, 10))
        apply_enemy_power(ctx)
        self._enemy(ctx, 0, 3000, 3000, (80, 80, 80, 80))     # the King joins
        apply_enemy_power(ctx)
        self.assertEqual(self._read(ctx, 0), (1500, 1500, [40, 40, 40, 40]))
        ctx.ff8.write_u16(memory.MODULE_DISPATCH, memory.MODULE_WORLDMAP)
        apply_enemy_power(ctx)
        self.assertEqual(ctx.enemy_power_written, {})

    def test_hundred_percent_is_a_no_op(self):
        ctx = Ctx(enemy_power=100)
        ctx.ff8.write_u16(memory.MODULE_DISPATCH, memory.MODULE_BATTLE)
        self._enemy(ctx, 0, 1000, 700, (40, 20, 30, 10))
        apply_enemy_power(ctx)
        self.assertEqual(self._read(ctx, 0), (1000, 700, [40, 20, 30, 10]))


class TestAPMultiplier(unittest.TestCase):
    def _ap(self, ctx, gf, slot):
        return ctx.ff8.read_u8(memory.GF_RECORD_BASE + gf * memory.GF_RECORD_STRIDE
                               + memory.GF_AP_OFFSET + slot)

    def test_tops_up_the_battle_award(self):
        ctx = Ctx(ap_multiplier=3)
        ctx.ff8.write_gf_ap(2, 5, 10)
        apply_ap_multiplier(ctx)            # baseline
        ctx.ff8.write_gf_ap(2, 5, 14)       # the game awarded 4 AP
        apply_ap_multiplier(ctx)
        self.assertEqual(self._ap(ctx, 2, 5), 14 + 8)
        apply_ap_multiplier(ctx)            # our own write is not an award
        self.assertEqual(self._ap(ctx, 2, 5), 22)

    def test_caps_at_byte_and_skips_a_gf_that_learned(self):
        ctx = Ctx(ap_multiplier=4)
        ctx.ff8.write_gf_ap(0, 1, 250)
        ctx.ff8.write_gf_ap(1, 0, 10)
        apply_ap_multiplier(ctx)
        ctx.ff8.write_gf_ap(0, 1, 254)                     # +4, would overflow
        ctx.ff8.write_gf_ap(1, 0, 20)                      # +10 but...
        addr = memory.gf_abilities_addr(1)
        ctx.ff8.write_u8(addr, ctx.ff8.read_u8(addr) | 0x40)   # ...this GF learned something
        apply_ap_multiplier(ctx)
        self.assertEqual(self._ap(ctx, 0, 1), 255)
        self.assertEqual(self._ap(ctx, 1, 0), 20)

    def test_multiplier_one_is_a_no_op(self):
        ctx = Ctx(ap_multiplier=1)
        ctx.ff8.write_gf_ap(0, 0, 5)
        apply_ap_multiplier(ctx)
        ctx.ff8.write_gf_ap(0, 0, 9)
        apply_ap_multiplier(ctx)
        self.assertEqual(self._ap(ctx, 0, 0), 9)
        self.assertIsNone(ctx.gf_ap_prev)


class TestRuleCheckSplit(FF8TestBase):
    options = {**ALL_TOGGLES_ON, "triple_triad_rule_checks": False}

    def test_rule_checks_off_removes_the_eight(self):
        names = {loc.name for loc in self.multiworld.get_locations(self.player)}
        self.assertFalse(any(n.startswith("Balamb Garden:") and "Card Wins" in n for n in names))
        self.assertFalse(set(RANDOM_ABOLITION_LOCATIONS) & names)


class TestFixedRulesDropAbolitions(FF8TestBase):
    options = {**ALL_TOGGLES_ON, "triple_triad_rules": "no_random"}

    def test_abolitions_gone_but_garden_wins_stay(self):
        names = {loc.name for loc in self.multiworld.get_locations(self.player)}
        self.assertFalse(set(RANDOM_ABOLITION_LOCATIONS) & names)
        self.assertIn("Balamb Garden: 15 Card Wins", names)


if __name__ == "__main__":
    unittest.main()
