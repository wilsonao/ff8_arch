"""add_magic stocking order and junction-lock clearing against a fake process
(no AP framework needed).

add_magic covers the two placement rules: top up an existing stack anywhere in
the permanent roster before opening a new one, and never touch the temporary
Seifer/Edea records (6-7) until Squall..Selphie are completely full.
clear_char_junctions covers the block bounds: everything junction goes to
zero, everything else (magic stock, costume byte, compatibility) stays.
"""

import unittest

from ..memory import (CHAR_BASE, CHAR_COUNT, CHAR_GFS_OFFSET,
                      CHAR_JUNCTION_BLOCK1_OFFSET, CHAR_JUNCTION_BLOCK2_OFFSET,
                      CHAR_MAGIC_OFFSET, CHAR_MAGIC_SLOTS, CHAR_PERMANENT,
                      CHAR_STRIDE, FF8Interface)

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


if __name__ == "__main__":
    unittest.main()
