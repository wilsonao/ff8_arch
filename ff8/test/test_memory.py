"""add_magic stocking order and junction-lock clearing against a fake process
(no AP framework needed).

add_magic covers the two placement rules: top up an existing stack anywhere in
the permanent roster before opening a new one, and never touch the temporary
Seifer/Edea records (6-7) until Squall..Selphie are completely full.
clear_char_junctions covers the block bounds: everything junction goes to
zero, everything else (magic stock, costume byte, compatibility) stays.
"""

import unittest

from ..locations import DRAW_POINT_TABLE, WORLD_DRAW_POINT_TABLE
from ..memory import (CHAR_ABILITIES_OFFSET, CHAR_BASE, CHAR_COUNT, CHAR_GFS_OFFSET,
                      ENC_NONE_ABILITY,
                      CHAR_JUNCTION_BLOCK1_OFFSET, CHAR_JUNCTION_BLOCK2_OFFSET,
                      CHAR_MAGIC_OFFSET, CHAR_MAGIC_SLOTS, CHAR_PERMANENT,
                      CHAR_STRIDE, DRAW_POINT_BOUNTIFUL, DRAW_POINT_DEFS_LEN,
                      DRAW_POINT_DEFS_VANILLA, DRAW_POINT_REFILLS,
                      DRAW_POINT_SLOTS, FF8Interface, draw_point_spells)
from ..text import MAGIC_NAMES


class TestDrawPointDefs(unittest.TestCase):
    """The exe's slot -> spell table (read from the unmodded FF8_EN.exe) is
    the authority on what every draw point gives; the location tables must
    agree with it. Nine world-map spells were wrong before this check."""

    def test_table_shape(self):
        self.assertEqual(len(DRAW_POINT_DEFS_VANILLA), DRAW_POINT_DEFS_LEN)
        self.assertEqual(DRAW_POINT_DEFS_LEN, DRAW_POINT_SLOTS)
        self.assertEqual(DRAW_POINT_DEFS_VANILLA[0], 0x55)      # front gate: Cure, refills
        self.assertTrue(DRAW_POINT_DEFS_VANILLA[0] & DRAW_POINT_REFILLS)
        self.assertTrue(DRAW_POINT_DEFS_VANILLA[2] & DRAW_POINT_BOUNTIFUL)  # MD level Full-life

    def test_every_check_spell_matches_the_exe(self):
        spells = draw_point_spells(DRAW_POINT_DEFS_VANILLA)
        rows = [(slot, spell) for slot, spell, *_ in DRAW_POINT_TABLE]
        rows += [(slot, spell) for slot, spell, *_ in WORLD_DRAW_POINT_TABLE]
        self.assertGreater(len(rows), 200)
        for slot, spell in rows:
            self.assertEqual(MAGIC_NAMES[spells[slot]], spell, f"slot {slot}")

SPELL = 25          # arbitrary spell id under test
OTHER_SPELL = 4     # filler for pre-occupied slots


class FakeFF8(FF8Interface):
    """FF8Interface with read/write primitives backed by a local bytearray
    spanning just the character block (the only region add_magic touches)."""

    ORIGIN = CHAR_BASE
    SIZE = CHAR_COUNT * CHAR_STRIDE

    def __init__(self):
        super().__init__()
        self.mem = bytearray(self.SIZE)

    def read_bytes(self, offset: int, size: int) -> bytes:
        start = offset - self.ORIGIN
        assert 0 <= start and start + size <= self.SIZE
        return bytes(self.mem[start:start + size])

    def write_bytes(self, offset: int, data: bytes) -> None:
        start = offset - self.ORIGIN
        assert 0 <= start and start + len(data) <= self.SIZE
        self.mem[start:start + len(data)] = data

    def read_u8(self, offset: int) -> int:
        return self.read_bytes(offset, 1)[0]

    def write_u8(self, offset: int, value: int) -> None:
        self.write_bytes(offset, bytes([value]))


def slot_addr(char: int, slot: int) -> int:
    return CHAR_BASE + char * CHAR_STRIDE + CHAR_MAGIC_OFFSET + slot * 2


class TestAddMagic(unittest.TestCase):
    def setUp(self):
        self.ff8 = FakeFF8()

    def set_slot(self, char: int, slot: int, sid: int, qty: int):
        self.ff8.write_bytes(slot_addr(char, slot), bytes([sid, qty]))

    def get_slot(self, char: int, slot: int) -> tuple[int, int]:
        raw = self.ff8.read_bytes(slot_addr(char, slot), 2)
        return raw[0], raw[1]

    def fill_char(self, char: int):
        for slot in range(CHAR_MAGIC_SLOTS):
            self.set_slot(char, slot, OTHER_SPELL, 100)

    def char_stock(self, char: int, sid: int) -> int:
        return sum(qty for slot in range(CHAR_MAGIC_SLOTS)
                   for s, qty in [self.get_slot(char, slot)] if s == sid)

    def test_tops_up_other_characters_stack_before_new_slot(self):
        """Zell holding a partial stack (e.g. after a Switch) gets the grant;
        Squall's free slots don't open a duplicate stack."""
        self.set_slot(1, 0, SPELL, 40)
        self.assertTrue(self.ff8.add_magic(SPELL, 30))
        self.assertEqual(self.get_slot(1, 0), (SPELL, 70))
        self.assertEqual(self.char_stock(0, SPELL), 0)

    def test_overflow_past_cap_opens_stack_on_squall(self):
        self.set_slot(1, 0, SPELL, 90)
        self.assertTrue(self.ff8.add_magic(SPELL, 30))
        self.assertEqual(self.get_slot(1, 0), (SPELL, 100))
        self.assertEqual(self.get_slot(0, 0), (SPELL, 20))

    def test_split_lands_across_characters_but_total_is_right(self):
        """A big grant may straddle a top-up and a new stack; the party-wide
        total must come out exact."""
        self.set_slot(4, 3, SPELL, 95)
        self.assertTrue(self.ff8.add_magic(SPELL, 150))
        total = sum(self.char_stock(c, SPELL) for c in range(CHAR_COUNT))
        self.assertEqual(total, 95 + 150)

    def test_seifer_stack_not_topped_up_while_permanents_have_room(self):
        """Stock left on Seifer's record from disc 1 must not attract more."""
        self.set_slot(6, 0, SPELL, 10)
        self.assertTrue(self.ff8.add_magic(SPELL, 50))
        self.assertEqual(self.get_slot(6, 0), (SPELL, 10))
        self.assertEqual(self.get_slot(0, 0), (SPELL, 50))

    def test_spills_to_seifer_only_when_permanents_full(self):
        for char in range(CHAR_PERMANENT):
            self.fill_char(char)
        self.assertTrue(self.ff8.add_magic(SPELL, 25))
        self.assertEqual(self.get_slot(6, 0), (SPELL, 25))
        self.assertEqual(self.char_stock(7, SPELL), 0)

    def test_returns_false_when_everything_full(self):
        for char in range(CHAR_COUNT):
            self.fill_char(char)
        self.assertFalse(self.ff8.add_magic(SPELL, 1))

    def test_partial_placement_still_returns_false(self):
        """One free stack's worth of room, a bigger grant: place what fits,
        report failure so the client can raise the checks-only cap."""
        for char in range(CHAR_COUNT):
            self.fill_char(char)
        self.set_slot(3, 7, 0, 0)
        self.assertFalse(self.ff8.add_magic(SPELL, 150))
        self.assertEqual(self.get_slot(3, 7), (SPELL, 100))

    def test_remove_magic_clears_emptied_stack(self):
        self.set_slot(0, 0, SPELL, 30)
        self.set_slot(2, 5, SPELL, 20)
        self.ff8.remove_magic(SPELL, 40)
        total = sum(self.char_stock(c, SPELL) for c in range(CHAR_COUNT))
        self.assertEqual(total, 10)
        self.assertEqual(self.get_slot(0, 0), (0, 0))


class TestCharJunctionLocks(unittest.TestCase):
    CHAR = 1  # Zell

    def setUp(self):
        self.ff8 = FakeFF8()
        self.base = CHAR_BASE + self.CHAR * CHAR_STRIDE

    def set8(self, offset: int, value: int):
        self.ff8.write_bytes(self.base + offset, bytes([value]))

    def get8(self, offset: int) -> int:
        return self.ff8.read_bytes(self.base + offset, 1)[0]

    def junction_everything(self):
        self.set8(CHAR_JUNCTION_BLOCK1_OFFSET, 2)       # a command
        self.set8(CHAR_JUNCTION_BLOCK1_OFFSET + 4, 5)   # an ability
        self.ff8.write_bytes(self.base + CHAR_GFS_OFFSET,
                             (0x0005).to_bytes(2, "little"))  # two GFs
        self.set8(CHAR_JUNCTION_BLOCK2_OFFSET, 22)      # HP-J: Cura
        self.set8(CHAR_JUNCTION_BLOCK2_OFFSET + 18, 3)  # last elem/status byte

    def test_active_detection(self):
        self.assertFalse(self.ff8.char_junctions_active(self.CHAR))
        self.ff8.write_bytes(self.base + CHAR_GFS_OFFSET, b"\x01\x00")
        self.assertTrue(self.ff8.char_junctions_active(self.CHAR))

    def test_clear_zeroes_whole_junction_block(self):
        self.junction_everything()
        self.ff8.clear_char_junctions(self.CHAR)
        self.assertFalse(self.ff8.char_junctions_active(self.CHAR))

    def test_clear_preserves_non_junction_bytes(self):
        """Magic stock (+0x10), the u2/costume bytes (+0x5A/+0x5B), and the
        compatibility block (+0x70) must survive a clear untouched."""
        self.junction_everything()
        self.ff8.write_bytes(self.base + CHAR_MAGIC_OFFSET, bytes([25, 40]))
        self.set8(0x5A, 0xAB)   # u2
        self.set8(0x5B, 0x01)   # alternative_model (costume)
        self.set8(0x70, 0x7F)   # compatibility[0]
        self.ff8.clear_char_junctions(self.CHAR)
        self.assertEqual(self.ff8.read_bytes(self.base + CHAR_MAGIC_OFFSET, 2),
                         bytes([25, 40]))
        self.assertEqual(self.get8(0x5A), 0xAB)
        self.assertEqual(self.get8(0x5B), 0x01)
        self.assertEqual(self.get8(0x70), 0x7F)

    def test_clear_touches_only_this_character(self):
        squall = CHAR_BASE + 0 * CHAR_STRIDE
        self.ff8.write_bytes(squall + CHAR_GFS_OFFSET, b"\x02\x00")
        self.junction_everything()
        self.ff8.clear_char_junctions(self.CHAR)
        self.assertEqual(self.ff8.read_bytes(squall + CHAR_GFS_OFFSET, 2),
                         b"\x02\x00")

    def test_junction_bytes_follow_hyne_layout(self):
        # Hyne PERSONNAGES: j_attEle, j_attMtl, j_defEle[4], j_defMtl[4].
        # ST-Atk and Elem-Def were swapped until 2026-10-02 (a status-attack
        # junction vanished while Elem-Def-J was still locked).
        from ..memory import JUNCTION_CHAR_BYTES
        self.assertEqual(JUNCTION_CHAR_BYTES[10], (0x65,))                    # Elem-Atk-J
        self.assertEqual(JUNCTION_CHAR_BYTES[11], (0x66,))                    # ST-Atk-J
        self.assertEqual(JUNCTION_CHAR_BYTES[12], (0x67, 0x68, 0x69, 0x6A))   # Elem-Def-J
        self.assertEqual(JUNCTION_CHAR_BYTES[13], (0x6B, 0x6C, 0x6D, 0x6E))   # ST-Def-J
        every = [o for offs in JUNCTION_CHAR_BYTES.values() for o in offs]
        self.assertEqual(sorted(every), list(range(0x5C, 0x6F)))

    def test_strip_elem_def_leaves_status_attack(self):
        from ..memory import JUNCTION_CHAR_BYTES
        self.set8(0x66, 36)   # ST-Atk: Slow
        self.set8(0x67, 30)   # Elem-Def 1: Shell
        self.set8(0x6A, 18)   # Elem-Def 4: Tornado
        out = self.ff8.strip_locked_char_state(JUNCTION_CHAR_BYTES[12], ())
        self.assertEqual(out, [(self.CHAR, [0x67, 0x6A], [])])
        self.assertEqual(self.get8(0x66), 36)
        self.assertEqual(self.get8(0x67), 0)
        self.assertEqual(self.ff8.strip_locked_char_state(JUNCTION_CHAR_BYTES[12], ()), [])

    # Battle Assist `enc` parks Enc-None in an ability slot of every main
    # character, locked ones included; the lock must neither count it as
    # junction state nor strip it (the two passes fought every tick live).
    KEEP = (ENC_NONE_ABILITY,)

    def test_kept_ability_alone_is_not_active(self):
        self.set8(CHAR_ABILITIES_OFFSET + 1, ENC_NONE_ABILITY)
        self.assertTrue(self.ff8.char_junctions_active(self.CHAR))
        self.assertFalse(self.ff8.char_junctions_active(self.CHAR,
                                                        keep_abilities=self.KEEP))

    def test_clear_preserves_kept_ability_and_strips_the_rest(self):
        self.junction_everything()
        self.set8(CHAR_ABILITIES_OFFSET + 1, ENC_NONE_ABILITY)
        self.ff8.clear_char_junctions(self.CHAR, keep_abilities=self.KEEP)
        self.assertEqual(self.ff8.read_bytes(self.base + CHAR_ABILITIES_OFFSET, 4),
                         bytes([0, ENC_NONE_ABILITY, 0, 0]))
        self.assertEqual(self.get8(CHAR_JUNCTION_BLOCK1_OFFSET), 0)      # command gone
        self.assertEqual(self.ff8.read_bytes(self.base + CHAR_GFS_OFFSET, 2),
                         bytes(2))
        self.assertEqual(self.get8(CHAR_JUNCTION_BLOCK2_OFFSET), 0)
        self.assertFalse(self.ff8.char_junctions_active(self.CHAR,
                                                        keep_abilities=self.KEEP))
        # A second pass is a no-op: nothing left to strip, nothing to log.
        self.ff8.clear_char_junctions(self.CHAR, keep_abilities=self.KEEP)
        self.assertEqual(self.get8(CHAR_ABILITIES_OFFSET + 1), ENC_NONE_ABILITY)

    def test_without_keep_enc_none_is_stripped_like_any_ability(self):
        self.set8(CHAR_ABILITIES_OFFSET + 1, ENC_NONE_ABILITY)
        self.ff8.clear_char_junctions(self.CHAR)
        self.assertEqual(self.get8(CHAR_ABILITIES_OFFSET + 1), 0)


if __name__ == "__main__":
    unittest.main()
