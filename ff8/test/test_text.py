"""In-game text: the FF8 codec, kernel table re-packing, and the live
rewrite/restore guard, against a fake process holding a vanilla kernel."""

import struct
import unittest
from unittest import mock

from ..items import BASE_ID
from ..kernel_text_vanilla import SECTION_OFFSETS, VANILLA
from ..locations import LOCATION_TABLE
from .. import text
from ..client import (TEXT_CHECK_ITEMS, TEXT_DRAW_POINTS, TEXT_PICKUP_LINES,
                      REAL_ITEM_DESCRIPTIONS, maintain_pickup_text, pickup_message,
                      text_overrides, text_spell_overrides)
from ..memory import FIELD_MSD_PTR
from ..fields import DRAW_POINT_FIELDS, FIELD_NAMES
from .test_vehicle_window import FakeProc


class TestCodec(unittest.TestCase):
    def test_vanilla_names_decode(self):
        items = text.vanilla_table("items")
        self.assertEqual(items.name(195 - 33), "Occult Fan I")
        self.assertEqual(items.name(168 - 33), "Magical Lamp")
        self.assertEqual(text.vanilla_table("battle_items").name(1), "Potion")
        self.assertEqual(text.vanilla_table("magic").name(1), "Fire")

    def test_round_trip_and_pairs(self):
        s = "Restores HP to all members!"
        self.assertEqual(text.decode(text.encode(s)), s)
        self.assertEqual(text.decode(text.encode(s, pairs=False)), s)
        # dictionary pairs shrink the encoding ("re" is one byte)
        self.assertLess(len(text.encode(s)), len(text.encode(s, pairs=False)))

    def test_unknown_characters_fold(self):
        self.assertEqual(text.decode(text.encode("a\"b")), "a'b")
        self.assertEqual(text.decode(text.encode("日本")), "??")

    def test_fit(self):
        self.assertEqual(text.fit("Progressive Sword of Destiny", 17),
                         "Progressive Sword")
        self.assertEqual(text.fit("Short", 17), "Short")
        self.assertNotIn("…", text.fit("Progressive Sword of Destiny", 12))

    def test_name_bytes_are_vanilla_safe(self):
        # names: no dictionary pairs, no glyphs vanilla names never use
        raw = text.encode_name("AP Potion: Bob's… {x}")
        self.assertTrue(all(b < 0xE8 for b in raw))
        self.assertEqual(text.decode(raw), "AP Potion  Bob's...  x ")
        every = text.encode_name("".join(sorted(text.NAME_ALPHABET)))
        self.assertTrue(all(0x20 <= b < 0xE8 for b in every))
        self.assertNotIn(0x30, every)                     # the "…" glyph
        # descriptions may use the pairs vanilla descriptions use
        raw = text.encode_desc("Restores HP to all")
        self.assertIn(text._ENC2["HP"], raw)
        self.assertNotIn(text._ENC2["EC"], text.encode_desc("SPECIAL"))


class TestTables(unittest.TestCase):
    def test_repack_reproduces_vanilla(self):
        for name, (ds, ts, stride) in text.TABLES.items():
            table = text.TextTable(VANILLA[ds], VANILLA[ts], stride)
            data, packed = table.render({})
            self.assertEqual(data, VANILLA[ds], name)
            self.assertEqual(packed, VANILLA[ts], name)

    def test_override_and_overflow(self):
        table = text.vanilla_table("items")
        idx = 195 - 33
        data, packed = table.render({idx: (text.encode("Hookshot"), None)})
        again = text.TextTable(data, packed, 4)
        self.assertEqual(again.name(idx), "Hookshot")
        self.assertEqual(again.description(idx), table.description(idx))
        self.assertEqual(again.name(idx + 1), "Occult Fan II")
        with self.assertRaises(ValueError):
            table.render({idx: (text.encode("x" * 6000), None)})


def kernel_proc() -> FakeProc:
    proc = FakeProc()
    hdr = struct.pack("<I", text.KERNEL_SECTIONS)
    hdr += struct.pack("<%dI" % text.KERNEL_SECTIONS, *SECTION_OFFSETS)
    proc.write_bytes(text.KERNEL_BASE, hdr)
    for sec, blob in VANILLA.items():
        proc.write_bytes(text.section_offset(sec), blob)
    return proc


class TestKernelText(unittest.TestCase):
    def test_apply_restore(self):
        proc = kernel_proc()
        kt = text.KernelText(proc)
        self.assertTrue(kt.header_ok())
        self.assertEqual(kt.state("items"), "vanilla")
        idx = 168 - 33
        self.assertTrue(kt.apply("items", {idx: ("Hookshot", "For Bob - Hookshot")}))
        self.assertEqual(kt.state("items"), "ours")
        live = text.TextTable(*kt.read_sections("items"), 4)
        self.assertEqual(live.name(idx), "Hookshot")
        self.assertEqual(live.description(idx), "For Bob - Hookshot")
        # idempotent: a second apply is a no-op write-wise
        with mock.patch.object(proc, "write_bytes", wraps=proc.write_bytes) as w:
            self.assertTrue(kt.apply("items", {idx: ("Hookshot", "For Bob - Hookshot")}))
            self.assertEqual(w.call_count, 0)
        kt.restore()
        self.assertEqual(kt.state("items"), "vanilla")

    def test_packed_section_shrinks_to_fit(self):
        # battle_items text has zero slack: a longer name must still land,
        # at a tighter description budget rather than failing
        proc = kernel_proc()
        kt = text.KernelText(proc)
        self.assertTrue(kt.apply("battle_items",
                                 {1: ("AP Potion", "For Bob - Progressive Hookshot")}))
        live = text.TextTable(*kt.read_sections("battle_items"), 24)
        self.assertEqual(live.name(1), "AP Potion")
        self.assertTrue(live.description(1).startswith("For Bob"))
        self.assertEqual(live.name(2), "Potion+")
        # all 22 item checks with long names still fit the items section
        long = {k: ("Progressive Hookshot of the Ancients",
                    "For Somebody Long: Progressive Hookshot of the Ancients")
                for k in range(160 - 33, 199 - 33)}
        self.assertTrue(kt.apply("items", long))
        live = text.TextTable(*kt.read_sections("items"), 4)
        self.assertTrue(live.name(195 - 33).startswith("Progressive"))
        self.assertEqual(live.name(34 - 33), "Pet House")
        # every record long: falls down the budget ladder instead of failing
        self.assertTrue(kt.apply("items", {k: ("x" * 17, "y" * 44) for k in range(166)}))
        live = text.TextTable(*kt.read_sections("items"), 4)
        self.assertEqual(live.name(5), "x" * 17)          # names are protected
        self.assertLess(len(live.description(5)), 44)     # descriptions give way

    def test_game_restart_reapplies(self):
        proc = kernel_proc()
        kt = text.KernelText(proc)
        idx = 168 - 33
        kt.apply("items", {idx: ("Hookshot", None)})
        ds, ts, _ = text.TABLES["items"]
        proc.write_bytes(text.section_offset(ts), VANILLA[ts])   # game reloaded
        proc.write_bytes(text.section_offset(ds), VANILLA[ds])
        self.assertEqual(kt.state("items"), "vanilla")
        self.assertTrue(kt.apply("items", {idx: ("Hookshot", None)}))
        self.assertEqual(kt.state("items"), "ours")

    def test_earlier_run_rename_is_adopted(self):
        proc = kernel_proc()
        first = text.KernelText(proc)
        first.apply("items", {0: ("Old Name", "was Tent")})
        second = text.KernelText(proc)                    # client restarted
        self.assertEqual(second.state("items"), "renamed")
        self.assertTrue(second.apply("items", {1: ("New Name", "was Pet House")}))
        live = text.TextTable(*second.read_sections("items"), 4)
        self.assertEqual((live.name(0), live.name(1)), ("Tent", "New Name"))
        second.restore()
        self.assertEqual(second.state("items"), "vanilla")

    def test_foreign_kernel_left_alone(self):
        proc = kernel_proc()
        ds, ts, _ = text.TABLES["battle_items"]
        proc.write_u8(text.section_offset(ds) + 24 + 9, 0x45)  # a modded item stat
        kt = text.KernelText(proc)
        self.assertEqual(kt.state("battle_items"), "foreign")
        before = kt.read_sections("battle_items")
        self.assertFalse(kt.apply("battle_items", {1: ("X", "y")}))
        self.assertTrue(kt.foreign)
        self.assertEqual(kt.read_sections("battle_items"), before)
        kt.restore()                                       # no-op, not ours
        self.assertEqual(kt.read_sections("battle_items"), before)

    def test_bad_header_refuses(self):
        proc = kernel_proc()
        proc.write_u32(text.KERNEL_BASE, 55)
        kt = text.KernelText(proc)
        self.assertFalse(kt.apply("items", {0: ("X", None)}))


class _Info:
    def __init__(self, item, player):
        self.item = item
        self.player = player


class _Names:
    def lookup_in_slot(self, code, slot=None):
        return {1: "Hookshot", 2: "Bomb Bag"}[code]


class TestClientMapping(unittest.TestCase):
    def test_injective_item_checks(self):
        by_name = {BASE_ID + d.id_offset: d for d in LOCATION_TABLE}
        names = {by_name[loc].name for loc in TEXT_CHECK_ITEMS}
        self.assertIn("Magazine: Occult Fan I", names)
        self.assertIn("Cid's Parting Gift", names)
        self.assertIn("Tears Point: Fallen Relic", names)
        # every mapped item id is used by exactly one location
        self.assertEqual(len(set(TEXT_CHECK_ITEMS.values())), len(TEXT_CHECK_ITEMS))
        for loc, item in TEXT_CHECK_ITEMS.items():
            self.assertEqual(by_name[loc].triggers[0][1], item)

    def test_overrides_from_scouts(self):
        lamp = next(loc for loc, item in TEXT_CHECK_ITEMS.items() if item == 168)
        ring = next(loc for loc, item in TEXT_CHECK_ITEMS.items() if item == 167)
        ctx = mock.Mock()
        ctx.slot = 1
        ctx.missing_locations = {lamp, ring}
        ctx.checked_locations = set()
        ctx.items_received = []
        ctx.locations_info = {lamp: _Info(1, 2), ring: _Info(2, 1)}
        ctx.item_names = _Names()
        ctx.player_names = {1: "Me", 2: "Bob"}
        ov = text_overrides(ctx)
        self.assertEqual(ov, {"items": {168 - 33: ("Hookshot", "For Bob - Hookshot"),
                                        167 - 33: ("Bomb Bag", "Your Bomb Bag")}})
        # a location the server doesn't know (option off) is skipped
        ctx.missing_locations = set()
        ctx.checked_locations = set()
        self.assertEqual(text_overrides(ctx), {})

    def test_real_key_item_keeps_its_name(self):
        """Once the handout check is sent, or the multiworld delivers the real
        Lamp / Ring, the item in the menu is the real one: vanilla name, and a
        description saying what using it does (the check rename would
        otherwise relabel the real Magical Lamp as, say, "Lute Tablet")."""
        lamp = next(loc for loc, item in TEXT_CHECK_ITEMS.items() if item == 168)
        ring = next(loc for loc, item in TEXT_CHECK_ITEMS.items() if item == 167)
        ctx = mock.Mock()
        ctx.slot = 1
        ctx.missing_locations = {lamp}
        ctx.checked_locations = {ring}
        ctx.items_received = []
        ctx.locations_info = {lamp: _Info(1, 2), ring: _Info(2, 1)}
        ctx.item_names = _Names()
        ctx.player_names = {1: "Me", 2: "Bob"}
        ov = text_overrides(ctx)["items"]
        self.assertEqual(ov[168 - 33], ("Hookshot", "For Bob - Hookshot"))
        self.assertEqual(ov[167 - 33], (None, REAL_ITEM_DESCRIPTIONS[167]))
        # the real Lamp arrives before Cid's handout: it must read Magical Lamp
        ctx.items_received = [mock.Mock(item=BASE_ID + 100)]
        ov = text_overrides(ctx)["items"]
        self.assertEqual(ov[168 - 33], (None, REAL_ITEM_DESCRIPTIONS[168]))
        for desc in REAL_ITEM_DESCRIPTIONS.values():
            self.assertLessEqual(len(desc), 44)     # widest description budget
        # the unchecked check still says what it sends at the pickup itself
        self.assertEqual(pickup_message(ctx, lamp, ctx.locations_info[lamp], 30, False),
                         text.encode_field("Sent [Hookshot]\nto Bob!"))


class TestDrawPointText(unittest.TestCase):
    def test_every_field_draw_point_resolves(self):
        draw_locs = {BASE_ID + d.id_offset for d in LOCATION_TABLE if d.group == "draw"}
        self.assertEqual(set(TEXT_DRAW_POINTS), draw_locs)
        for spell, fields in TEXT_DRAW_POINTS.values():
            self.assertGreater(spell, 0)
            self.assertTrue(fields)
            for f in fields:
                self.assertLess(f, len(FIELD_NAMES))

    def test_known_screens(self):
        # slot 1 = Balamb Garden Training Center Blizzard: drawn live from
        # field 217 (bgmon_4) on 2026-09-10; slot 0 = the front gate Cure
        self.assertEqual(DRAW_POINT_FIELDS[1], (217,))
        self.assertEqual(FIELD_NAMES[217], "bgmon_4")
        self.assertIn(160, DRAW_POINT_FIELDS[0])
        self.assertEqual(FIELD_NAMES[160], "bggate_2")
        self.assertEqual(FIELD_NAMES[573], "felast1")     # ULTIMECIA_FIELD

    def test_spell_overrides_follow_field(self):
        training = BASE_ID + 300 + 1
        spell = TEXT_DRAW_POINTS[training][0]
        self.assertEqual(text.MAGIC_NAMES[spell], "Blizzard")
        ctx = mock.Mock()
        ctx.slot = 1
        ctx.missing_locations = {training}
        ctx.locations_info = {training: _Info(1, 2)}
        ctx.item_names = _Names()
        ctx.player_names = {1: "Me", 2: "Bob"}
        self.assertEqual(text_spell_overrides(ctx, 217),
                         {spell: ("Hookshot", "Blizzard - for Bob")})
        self.assertEqual(text_spell_overrides(ctx, 160), {})     # front gate
        ctx.missing_locations = set()                            # already drawn
        self.assertEqual(text_spell_overrides(ctx, 217), {})

    def test_shared_spell_on_one_screen_stays_vanilla(self):
        shared = [(a, b) for a, (sa, fa) in TEXT_DRAW_POINTS.items()
                  for b, (sb, fb) in TEXT_DRAW_POINTS.items()
                  if a < b and sa == sb and set(fa) & set(fb)]
        if not shared:
            self.skipTest("no two same-spell draw points share a screen")
        a, b = shared[0]
        field = (set(TEXT_DRAW_POINTS[a][1]) & set(TEXT_DRAW_POINTS[b][1])).pop()
        ctx = mock.Mock()
        ctx.slot = 1
        ctx.missing_locations = {a, b}
        ctx.locations_info = {a: _Info(1, 2), b: _Info(1, 2)}
        ctx.item_names = _Names()
        ctx.player_names = {1: "Me", 2: "Bob"}
        self.assertNotIn(TEXT_DRAW_POINTS[a][0], text_spell_overrides(ctx, field))


def msd_with(index: int, raw: bytes, count: int = None) -> bytes:
    """A minimal message table: `count` entries, entry `index` = raw."""
    count = count or index + 1
    strings = [b"" if k != index else raw for k in range(count)]
    offs = []
    body = b""
    for st in strings:
        offs.append(4 * count + len(body))
        body += st + b"\x00"
    return b"".join(struct.pack("<I", o) for o in offs) + body


class TestPickupText(unittest.TestCase):
    def setUp(self):
        self.lamp = next(loc for loc, item in TEXT_CHECK_ITEMS.items() if item == 168)
        self.lines = TEXT_PICKUP_LINES[self.lamp]
        self.assertEqual({f for f, _, _ in self.lines}, {162, 251})    # bggate_5, bgsido_2
        self.fid, self.idx, self.vanilla = self.lines[0]
        self.assertEqual(text.decode(self.vanilla), "Received [Magical Lamp]!")
        self.proc = FakeProc()
        self.table = 0x1000000
        self.proc.write_bytes(self.table, msd_with(self.idx, self.vanilla))
        self.proc.write_u32(FIELD_MSD_PTR, self.table)
        self.ctx = mock.Mock()
        self.ctx.slot = 1
        self.ctx.ff8 = self.proc
        self.ctx.missing_locations = {self.lamp}
        self.ctx.locations_info = {self.lamp: _Info(1, 2)}
        self.ctx.item_names = _Names()
        self.ctx.player_names = {1: "Me", 2: "Bob"}

    def line(self):
        off = self.proc.read_u32(self.table + 4 * self.idx)
        raw = self.proc.read_bytes(self.table + off, len(self.vanilla) + 1)
        return text.decode(raw), raw

    def test_rewrites_within_vanilla_length(self):
        maintain_pickup_text(self.ctx, self.fid)
        shown, raw = self.line()
        self.assertEqual(shown, "Sent [Hookshot]\nto Bob!")
        self.assertEqual(raw[-1], 0)                        # still terminated
        self.assertLessEqual(len(raw.rstrip(b"\x00")), len(self.vanilla))

    def test_other_field_and_checked_leave_it(self):
        maintain_pickup_text(self.ctx, 999)
        self.assertEqual(self.line()[0], "Received [Magical Lamp]!")
        self.ctx.missing_locations = set()
        maintain_pickup_text(self.ctx, self.fid)
        self.assertEqual(self.line()[0], "Received [Magical Lamp]!")

    def test_reapplies_after_reload_and_never_twice(self):
        maintain_pickup_text(self.ctx, self.fid)
        with mock.patch.object(self.proc, "write_bytes", wraps=self.proc.write_bytes) as w:
            maintain_pickup_text(self.ctx, self.fid)
            self.assertEqual(w.call_count, 0)
        self.proc.write_bytes(self.table, msd_with(self.idx, self.vanilla))   # field reloaded
        maintain_pickup_text(self.ctx, self.fid)
        self.assertEqual(self.line()[0], "Sent [Hookshot]\nto Bob!")

    def test_foreign_table_untouched(self):
        self.proc.write_bytes(self.table, msd_with(self.idx, text.encode_field("Something else")))
        maintain_pickup_text(self.ctx, self.fid)
        self.assertEqual(self.line()[0][:14], "Something else")
        self.proc.write_u32(FIELD_MSD_PTR, 0)                # no table yet
        maintain_pickup_text(self.ctx, self.fid)

    def test_message_ladder(self):
        long = _Info(1, 2)
        self.ctx.item_names = mock.Mock()
        self.ctx.item_names.lookup_in_slot.return_value = "Progressive Hookshot of Time"
        for budget in (40, 24, 14, 6):
            raw = pickup_message(self.ctx, self.lamp, long, budget, False)
            self.assertLessEqual(len(raw), budget)
            self.assertTrue(all(0x20 <= b < 0xE8 or b == 0x02 for b in raw))
        self.assertEqual(text.decode(pickup_message(self.ctx, self.lamp, long, 48, False)),
                         "Sent [Progressive Hookshot of Time]\nto Bob!")
        own = pickup_message(self.ctx, self.lamp, _Info(1, 1), 24, False)
        self.assertEqual(text.decode(own), "Got Progressive Hooks!")
        tm = pickup_message(self.ctx, self.lamp, long, 90, True)
        self.assertTrue(text.decode(tm).startswith("Found an old issue of\n[Timber Maniacs]!\n"))

    def test_every_line_budget_can_name_the_player(self):
        # the shortest vanilla line still fits "Sent to <8 chars>!"
        self.assertGreaterEqual(min(len(v) for lines in TEXT_PICKUP_LINES.values()
                                    for _, _, v in lines), 22)
