"""GF ability-check table invariants (static) and the library-backed default
mask verification (skipped when the save library is not on this machine)."""

import unittest
from pathlib import Path

from . import FF8TestBase
from .. import memory
from ..locations import (GF_ABILITIES_BASE, GF_ABILITY_AP, GF_ABILITY_NAMES,
                         GF_LEARN_LISTS, GF_SIGNATURE_ABILITIES, LOCATION_TABLE)

LIBRARY = Path("F:/ff8_saves/library")


class TestGFAbilityTables(FF8TestBase):
    auto_construct = False

    def test_learn_lists_are_22_unique_known_ids(self):
        self.assertEqual(len(GF_LEARN_LISTS), 16)
        for gf, ids in enumerate(GF_LEARN_LISTS):
            self.assertEqual(len(ids), 22, gf)
            self.assertEqual(len(set(ids)), 22, gf)
            for aid in ids:
                self.assertTrue(0 < aid < len(GF_ABILITY_NAMES), aid)
                self.assertTrue(GF_ABILITY_NAMES[aid], aid)
            # the four command abilities are in every list
            self.assertTrue({20, 21, 22, 23} <= set(ids), gf)

    def test_defaults_subset_of_learn_lists(self):
        for gf, ids in enumerate(GF_LEARN_LISTS):
            mask = memory.GF_ABILITY_DEFAULTS[gf]
            default_ids = {i for i in range(128) if mask >> i & 1}
            self.assertTrue(default_ids <= set(ids), (gf, default_ids - set(ids)))
            self.assertEqual(len(default_ids), memory.GF_ABILITY_DEFAULT_BITS[gf])

    def test_signature_abilities_learnable_and_not_default(self):
        for gf, ids in GF_SIGNATURE_ABILITIES.items():
            for aid in ids:
                self.assertIn(aid, GF_LEARN_LISTS[gf], (gf, GF_ABILITY_NAMES[aid]))
                self.assertFalse(memory.GF_ABILITY_DEFAULTS[gf] >> aid & 1,
                                 (gf, GF_ABILITY_NAMES[aid]))
                self.assertGreater(GF_ABILITY_AP[aid], 0, aid)

    def test_ability_location_shapes(self):
        self.assertEqual(GF_ABILITIES_BASE, memory.gf_abilities_addr(0))
        locs = [d for d in LOCATION_TABLE if d.group == "abilities"]
        self.assertEqual(len(locs), 49 + 16 + 6)
        for d in locs:
            kind, value = d.triggers[0]
            if kind == "flag_bit":
                self.assertIsNotNone(d.requires_gf)
                off, mask = value
                rec = (off - GF_ABILITIES_BASE) // memory.GF_RECORD_STRIDE
                self.assertEqual(rec, d.requires_gf, d.name)
                self.assertEqual(mask.bit_count(), 1)
            elif kind == "bits_all":
                off, length, mask = value
                self.assertEqual(off, memory.gf_abilities_addr(d.requires_gf))
                self.assertEqual(length, memory.GF_ABILITIES_LEN)
                self.assertEqual(mask.bit_count(), 22)
                self.assertEqual(mask & memory.GF_ABILITY_DEFAULTS[d.requires_gf],
                                 memory.GF_ABILITY_DEFAULTS[d.requires_gf])
            else:
                self.assertEqual(kind, "gf_abilities_ge")
                self.assertIsNone(d.requires_gf)
                self.assertTrue(0 < value <= 244)

    def test_junction_and_command_lock_tables(self):
        """Lock groups govern known ability ids, never overlap each other or
        the signature items, and every junction primary has char-record bytes
        inside the verified junction block."""
        from ..abilities import COMMAND_ABILITY_IDS, JUNCTION_LOCK_GROUPS
        junction_bits = [b for g in JUNCTION_LOCK_GROUPS.values() for b in g]
        self.assertEqual(len(junction_bits), len(set(junction_bits)))
        command_bits = set(COMMAND_ABILITY_IDS.values())
        self.assertEqual(command_bits, {20, 21, 22, 23})
        all_signature_ids = {aid for ids in GF_SIGNATURE_ABILITIES.values()
                             for aid in ids}
        for primary, bits in JUNCTION_LOCK_GROUPS.items():
            self.assertIn(primary, bits)
            for aid in bits:
                self.assertTrue(0 < aid < len(GF_ABILITY_NAMES), aid)
                self.assertNotIn(aid, all_signature_ids,
                                 f"junction bit {aid} is also a signature")
                self.assertNotIn(aid, command_bits)
            byte_offsets = memory.JUNCTION_CHAR_BYTES[primary]
            for off in byte_offsets:
                self.assertTrue(memory.CHAR_JUNCTION_BLOCK2_OFFSET <= off
                                < memory.CHAR_JUNCTION_BLOCK2_OFFSET
                                + memory.CHAR_JUNCTION_BLOCK2_LEN, (primary, off))
        # Luck-J (9) stays unlocked: it is Cactuar's signature check/item.
        self.assertNotIn(9, JUNCTION_LOCK_GROUPS)
        # Commands are in every default mask (the restore path depends on it).
        for gf in range(16):
            for cid in command_bits:
                self.assertTrue(memory.GF_ABILITY_DEFAULTS[gf] >> cid & 1,
                                (gf, cid))

    def test_ladder_headroom_under_all_locks(self):
        """With every lock option on, at least 150 beyond-default abilities
        must stay uninterceptable — the highest in-logic party-ladder tier
        (GF Abilities Learned: 150) never needs a lock item."""
        from ..abilities import COMMAND_ABILITY_IDS, JUNCTION_LOCK_GROUPS
        lockable = ({b for g in JUNCTION_LOCK_GROUPS.values() for b in g}
                    | set(COMMAND_ABILITY_IDS.values()))
        free = 0
        for gf, learn in enumerate(GF_LEARN_LISTS):
            defaults = {i for i in range(128)
                        if memory.GF_ABILITY_DEFAULTS[gf] >> i & 1}
            beyond = set(learn) - defaults
            free += len(beyond - lockable - set(GF_SIGNATURE_ABILITIES[gf]))
        self.assertGreaterEqual(free, 150)

    @unittest.skipUnless(LIBRARY.is_dir(), "save library not present")
    def test_defaults_match_save_library(self):
        """Every not-yet-owned GF record in every legit library save carries
        exactly the default mask (the whole premise of these checks)."""
        import sys
        tools = Path(__file__).resolve().parents[2] / "tools"
        sys.path.insert(0, str(tools))
        import save_scan  # noqa: E402
        checked = 0
        for save in save_scan.load_all([str(LIBRARY)]):
            if not save.crc_ok:
                continue
            for gf in range(16):
                rec = memory.GF_RECORD_BASE + gf * memory.GF_RECORD_STRIDE
                if save.u8(rec + 0x11):
                    continue
                mask = int.from_bytes(save.bytes_at(rec + 20, 16), "little")
                self.assertEqual(mask, memory.GF_ABILITY_DEFAULTS[gf],
                                 (save.path.name, gf))
                checked += 1
        self.assertGreater(checked, 1000)
