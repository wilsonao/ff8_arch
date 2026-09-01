"""Automated live self-test for the FF8 apworld client.

Simulates game events by writing FF8_EN.exe memory directly, then watches the
AP server to confirm the running FF8 client detected each event and sent the
right check. Covers every trigger family: draw points, TT win ladder, CC Group
bits, Timber Maniacs, rare cards, blue magic, Zell duels, Angelo tricks,
Tonberry King flag, unique-card ladder (cards_owned), magazines (item_own),
battles-won + SeeD-test + Squall-level ladders (u32_ge/u8_ge), escapes +
SeeD rank (u16_ge), magic-drawn ladder + marquee first-draws (popcount_ge/flag_bit),
weapon remodel + castle seals (bits_ge), cameo-GF edge (dream_flag),
vanilla-item interception (item), checks-only magic enforcement (skipped on
vanilla-magic seeds), boss victory, loss-no-credit, and DeathLink send +
receive.

What it does NOT prove: that the *game* writes these addresses on real events
(that needs real play or savemap_diff.py sessions), the Ultimecia goal
machine, or in-game visibility of granted items.

Setup (then walk away — takes ~4 minutes):
  1. FF8 running, save loaded, standing on a FIELD screen (not menu/battle/cutscene).
  2. MultiServer running a test seed generated with ALL check groups enabled
     (draw/tt/boss/cards/sidequest/magazine) — tests for locations the seed
     lacks report SKIP.
  3. The FF8 client running and connected.
  4. From the Archipelago directory:
     ..\\.venv\\Scripts\\python.exe ..\\tools\\live_selftest.py --connect localhost:38281 --name Wilson

NOTE: consumes a handful of the test seed's checks (that is the point) and the
items they contain get granted to the save. Use on a test seed/save only.
Restores every memory value it changes (except state the game itself owns,
like checks already sent).
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "Archipelago"))

import ModuleUpdate
ModuleUpdate.update_ran = True

from CommonClient import CommonContext, get_base_parser, server_loop  # noqa: E402
from worlds.ff8 import memory as M  # noqa: E402
from worlds.ff8.locations import location_name_to_id  # noqa: E402
from worlds.ff8.memory import FF8Interface  # noqa: E402

POLL = 0.4
CHECK_TIMEOUT = 10.0
SETTLE = 1.6          # > 2 client ticks, so the client definitely observes a phase

# Battle-fake encounters (UFO sightings: excluded-tier, cheap to consume).
ENC_WIN, ENC_LOSS, ENC_RECV = 745, 746, 747
LOC_WIN = location_name_to_id["UFO Sighting: Beach (Moai)"]
LOC_LOSS = location_name_to_id["UFO Sighting: Plains (Cow)"]


class Observer(CommonContext):
    game = "Final Fantasy VIII"
    items_handling = 0b000

    def __init__(self, server_address, password):
        super().__init__(server_address, password)
        self.tags.add("DeathLink")
        self.deaths_received = 0
        self.slot_data_seen: dict = {}

    def on_package(self, cmd: str, args: dict):
        super().on_package(cmd, args)
        if cmd == "Connected":
            self.slot_data_seen = args.get("slot_data") or {}

    async def server_auth(self, password_requested: bool = False):
        if password_requested and not self.password:
            await super().server_auth(password_requested)
        await self.get_username()
        await self.send_connect()

    def on_deathlink(self, data: dict) -> None:
        super().on_deathlink(data)
        self.deaths_received += 1
        print(f"    (deathlink received from '{data.get('source', '?')}')")


async def wait_checked(ctx: Observer, loc_id: int, timeout: float = CHECK_TIMEOUT) -> bool:
    end = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < end:
        if loc_id in ctx.checked_locations:
            return True
        await asyncio.sleep(POLL)
    return False


class Harness:
    def __init__(self, ctx: Observer, ff8: FF8Interface):
        self.ctx, self.ff8 = ctx, ff8
        self.results: list[tuple[str, str, str]] = []

    def record(self, name: str, status: str, detail: str = ""):
        self.results.append((name, status, detail))
        print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))

    async def expect_check(self, name: str, loc_name: str, restore=None):
        loc_id = location_name_to_id[loc_name]
        if loc_id in self.ctx.checked_locations:
            self.record(name, "SKIP", "already checked before test")
        elif await wait_checked(self.ctx, loc_id):
            self.record(name, "PASS")
        else:
            self.record(name, "FAIL", f"no check for '{loc_name}' in {CHECK_TIMEOUT}s")
        if restore:
            restore()

    # ---- state-trigger tests ------------------------------------------------

    async def test_draw_point(self):
        # First unchecked draw location whose slot is still Full.
        from worlds.ff8.locations import LOCATION_TABLE
        from worlds.ff8.items import BASE_ID
        states = self.ff8.read_draw_states()
        for d in LOCATION_TABLE:
            if d.group != "draw":
                continue
            slot = d.triggers[0][1]
            if BASE_ID + d.id_offset in self.ctx.checked_locations or states[slot] != 0:
                continue
            byte_off = M.DRAW_POINTS + slot // 4
            shift = (slot % 4) * 2
            orig = self.ff8.read_u8(byte_off)
            self.ff8.write_u8(byte_off, orig | (2 << shift))  # Empty = drawn
            await self.expect_check("draw point (state write)", d.name,
                                    restore=lambda: self.ff8.write_u8(byte_off, orig))
            return
        self.record("draw point (state write)", "SKIP", "no untouched unchecked draw point")

    async def test_tt_wins(self):
        orig = self.ff8.read_u16(M.TT_WINS)
        if orig >= 100:
            self.record("tt wins ladder", "SKIP", f"already {orig} wins")
            return
        self.ff8.write_u16(M.TT_WINS, 100)
        await self.expect_check("tt wins ladder (write 100)", "Triple Triad: 100 Wins",
                                restore=lambda: self.ff8.write_u16(M.TT_WINS, orig))

    async def test_cc_group(self):
        # (The old King-bit test is gone with the King check: 0x18FDD0B turned
        # out to be Shiva's GF record, and the location was removed.)
        orig = self.ff8.read_u8(M.CC_GROUP_FLAGS)
        self.ff8.write_u8(M.CC_GROUP_FLAGS, 0x1F)
        await self.expect_check(
            "cc group (Hearts bit)", "CC Group: Heart Defeated",
            restore=lambda: self.ff8.write_u8(M.CC_GROUP_FLAGS, orig))

    async def test_timber_maniacs(self):
        orig = self.ff8.read_u16(M.TIMBER_MANIACS)
        self.ff8.write_u16(M.TIMBER_MANIACS, 0x0FFF)
        await self.expect_check("timber maniacs (12 bits)", "Timber Maniacs: 12 Issues",
                                restore=lambda: self.ff8.write_u16(M.TIMBER_MANIACS, orig))

    async def test_rare_card(self):
        # Squall card = rare index 32 -> byte 4 bit 0.
        off = M.CARDS_RARE + 4
        orig = self.ff8.read_u8(off)
        if orig & 0x01:
            self.record("rare card (Squall bit)", "SKIP", "already owned")
            return
        self.ff8.write_u8(off, orig | 0x01)
        await self.expect_check("rare card (Squall bit)", "Rare Card: Squall",
                                restore=lambda: self.ff8.write_u8(off, orig))

    async def test_blue_magic(self):
        orig = self.ff8.read_u16(M.QUISTIS_LIMITS)
        if orig & 0x8000:
            self.record("blue magic (Shockwave bit)", "SKIP", "already known")
            return
        self.ff8.write_u16(M.QUISTIS_LIMITS, orig | 0x8000)
        await self.expect_check("blue magic (Shockwave bit)", "Blue Magic: Shockwave Pulsar",
                                restore=lambda: self.ff8.write_u16(M.QUISTIS_LIMITS, orig))

    async def test_angelo(self):
        orig = self.ff8.read_u8(M.ANGELO_KNOWN)
        if orig & 0x08:
            self.record("angelo (Search bit)", "SKIP", "already read")
            return
        self.ff8.write_u8(M.ANGELO_KNOWN, orig | 0x08)
        await self.expect_check("angelo (Search bit)", "Angelo Trick: Angelo Search",
                                restore=lambda: self.ff8.write_u8(M.ANGELO_KNOWN, orig))

    async def test_tonberry_flag(self):
        orig = self.ff8.read_u32(M.TONBERRY_KING_FLAG)
        if orig:
            self.record("tonberry king flag", "SKIP", f"already {orig}")
            return
        self.ff8.write_u32(M.TONBERRY_KING_FLAG, 1)
        await self.expect_check("tonberry king flag", "Centra Ruins: Tonberry King",
                                restore=lambda: self.ff8.write_u32(M.TONBERRY_KING_FLAG, 0))

    def _in_seed(self, loc_name: str) -> bool:
        loc_id = location_name_to_id[loc_name]
        return (loc_id in self.ctx.missing_locations
                or loc_id in self.ctx.checked_locations)

    async def test_battles_won(self):
        if not self._in_seed("Battles Won: 200"):
            self.record("battles won (u32 write 200)", "SKIP", "not in seed (sidequests off?)")
            return
        orig = self.ff8.read_u32(M.BATTLES_WON)
        if orig >= 200:
            self.record("battles won (u32 write 200)", "SKIP", f"already {orig}")
            return
        self.ff8.write_u32(M.BATTLES_WON, 200)
        await self.expect_check("battles won (u32 write 200)", "Battles Won: 200",
                                restore=lambda: self.ff8.write_u32(M.BATTLES_WON, orig))

    async def test_seed_tests(self):
        if not self._in_seed("SeeD Tests: Level 30"):
            self.record("seed tests (u8 write 30)", "SKIP", "not in seed (sidequests off?)")
            return
        orig = self.ff8.read_u8(M.SEED_TEST_LEVEL)
        if orig >= 30:
            self.record("seed tests (u8 write 30)", "SKIP", f"already {orig}")
            return
        self.ff8.write_u8(M.SEED_TEST_LEVEL, 30)
        await self.expect_check("seed tests (u8 write 30)", "SeeD Tests: Level 30",
                                restore=lambda: self.ff8.write_u8(M.SEED_TEST_LEVEL, orig))

    async def test_weapon_remodel(self):
        if not self._in_seed("Weapon Remodel: Squall"):
            self.record("weapon remodel (Squall bit 1)", "SKIP", "not in seed (sidequests off?)")
            return
        orig = self.ff8.read_u32(M.WEAPONS_UNLOCKED)
        if (orig & 0x7F).bit_count() >= 2:
            self.record("weapon remodel (Squall bit 1)", "SKIP",
                        f"Squall already remodeled (mask 0x{orig:08X})")
            return
        self.ff8.write_u32(M.WEAPONS_UNLOCKED, orig | 0x02)   # Shear Trigger made
        await self.expect_check("weapon remodel (Squall bit 1)", "Weapon Remodel: Squall",
                                restore=lambda: self.ff8.write_u32(M.WEAPONS_UNLOCKED, orig))

    async def test_seal_ladder(self):
        if not self._in_seed("Ultimecia Castle: First Seal Broken"):
            self.record("castle seal (bit write)", "SKIP", "not in seed (optional bosses off?)")
            return
        orig = self.ff8.read_u8(M.SEAL_FLAGS)
        if orig:
            self.record("castle seal (bit write)", "SKIP", f"seals already 0x{orig:02X}")
            return
        self.ff8.write_u8(M.SEAL_FLAGS, 0x20)   # any single bit = one seal broken
        await self.expect_check("castle seal (bit write)", "Ultimecia Castle: First Seal Broken",
                                restore=lambda: self.ff8.write_u8(M.SEAL_FLAGS, orig))

    async def test_magazine(self):
        if not self._in_seed("Magazine: Occult Fan I"):
            self.record("magazine (item_own)", "SKIP", "not in seed (magazines off?)")
            return
        mag_id = 195  # Occult Fan I
        if self.ff8.count_item(mag_id):
            self.record("magazine (item_own)", "SKIP", "already owned")
            return
        inv = self.ff8.read_inventory()
        slot = next((i for i, (iid, qty) in enumerate(inv) if iid == 0 or qty == 0), None)
        if slot is None:
            self.record("magazine (item_own)", "SKIP", "inventory full")
            return
        off = M.INVENTORY + slot * 2
        self.ff8.write_bytes(off, bytes([mag_id, 1]))
        await self.expect_check("magazine (item_own)", "Magazine: Occult Fan I",
                                restore=lambda: self.ff8.write_bytes(off, bytes([0, 0])))

    async def test_unique_cards(self):
        if not self._in_seed("Triple Triad: 70 Unique Cards"):
            self.record("unique cards (write 70)", "SKIP", "not in seed (tt off?)")
            return
        if self.ff8.unique_cards_owned() >= 70:
            self.record("unique cards (write 70)", "SKIP", "already >= 70")
            return
        orig = self.ff8.read_bytes(M.TT_CARDS, M.TT_CARDS_COMMON)
        new = bytearray(orig)
        owned = self.ff8.unique_cards_owned()
        for i in range(M.TT_CARDS_COMMON):
            if owned >= 70:
                break
            if not (new[i] & M.TT_CARD_SEEN):
                new[i] |= M.TT_CARD_SEEN   # "obtained once" flag; qty untouched
                owned += 1
        self.ff8.write_bytes(M.TT_CARDS, bytes(new))
        await self.expect_check("unique cards (write 70)", "Triple Triad: 70 Unique Cards",
                                restore=lambda: self.ff8.write_bytes(M.TT_CARDS, orig))

    async def test_zell_duel(self):
        if not self._in_seed("Zell Duel: Different Beat"):
            self.record("zell duel (bit 8)", "SKIP", "not in seed (sidequests off?)")
            return
        orig = self.ff8.read_u16(M.ZELL_DUELS)
        if orig & 0x0100:
            self.record("zell duel (bit 8)", "SKIP", "already known")
            return
        self.ff8.write_u16(M.ZELL_DUELS, orig | 0x0100)
        await self.expect_check("zell duel (bit 8)", "Zell Duel: Different Beat",
                                restore=lambda: self.ff8.write_u16(M.ZELL_DUELS, orig))

    async def test_battles_escaped(self):
        if not self._in_seed("Battles Escaped: 30"):
            self.record("escapes (u16 write 30)", "SKIP", "not in seed (stats off?)")
            return
        orig = self.ff8.read_u16(M.BATTLES_ESCAPED)
        if orig >= 30:
            self.record("escapes (u16 write 30)", "SKIP", f"already {orig}")
            return
        self.ff8.write_u16(M.BATTLES_ESCAPED, 30)
        await self.expect_check("escapes (u16 write 30)", "Battles Escaped: 30",
                                restore=lambda: self.ff8.write_u16(M.BATTLES_ESCAPED, orig))

    async def test_seed_rank(self):
        # seedExp is the one non-monotonic stat: write rank 10 (1000), rely on
        # the check latch, restore the real value (decay-safe by design).
        if not self._in_seed("SeeD Rank: 10"):
            self.record("seed rank (u16 write 1000)", "SKIP", "not in seed (stats off?)")
            return
        orig = self.ff8.read_u16(M.SEED_EXP)
        if orig >= 1000:
            self.record("seed rank (u16 write 1000)", "SKIP", f"already {orig}")
            return
        self.ff8.write_u16(M.SEED_EXP, 1000)
        await self.expect_check("seed rank (u16 write 1000)", "SeeD Rank: 10",
                                restore=lambda: self.ff8.write_u16(M.SEED_EXP, orig))

    async def test_magic_drawn(self):
        # One write covers both new families on the same bitmask: popcount_ge
        # (Magic Collection: 40 Kinds) and a marquee flag_bit (First Draw:
        # Ultima, spell id 19 -> bit 18).
        if not self._in_seed("Magic Collection: 40 Kinds"):
            self.record("magic drawn (popcount)", "SKIP", "not in seed (stats off?)")
            return
        orig = self.ff8.read_bytes(M.MAGIC_DRAWN, M.MAGIC_DRAWN_LEN)
        if sum(b.bit_count() for b in orig) >= 40:
            self.record("magic drawn (popcount)", "SKIP", "already >= 40 kinds")
            return
        new = bytearray(orig)
        new[18 // 8] |= 1 << (18 % 8)   # Ultima's bit, for the marquee check
        need = 40 - sum(b.bit_count() for b in new)
        for bit in range(56):
            if need <= 0:
                break
            if not (new[bit // 8] & (1 << (bit % 8))):
                new[bit // 8] |= 1 << (bit % 8)
                need -= 1
        self.ff8.write_bytes(M.MAGIC_DRAWN, bytes(new))
        await self.expect_check("magic drawn (popcount write 40)",
                                "Magic Collection: 40 Kinds", restore=None)
        await self.expect_check(
            "first draw (Ultima bit)", "First Draw: Ultima",
            restore=lambda: self.ff8.write_bytes(M.MAGIC_DRAWN, orig))

    async def test_squall_level(self):
        if not self._in_seed("Squall: Level 40"):
            self.record("squall level (exp write)", "SKIP", "not in seed (stats off?)")
            return
        orig = self.ff8.read_u32(M.SQUALL_EXP)
        if orig >= 39000:
            self.record("squall level (exp write)", "SKIP", f"already exp {orig}")
            return
        self.ff8.write_u32(M.SQUALL_EXP, 39000)
        await self.expect_check("squall level (exp write 39000)", "Squall: Level 40",
                                restore=lambda: self.ff8.write_u32(M.SQUALL_EXP, orig))

    async def test_gf_ability(self):
        """Set one unlearned signature-ability bit in a GF's completeAbilities
        mask (prefer a GF the party owns) and expect its check."""
        from worlds.ff8.locations import LOCATION_TABLE
        from worlds.ff8.items import BASE_ID
        if not self._in_seed("Quezacotl Learns Card"):
            self.record("gf ability (bit write)", "SKIP", "not in seed (gf abilities off?)")
            return
        cands = [d for d in LOCATION_TABLE
                 if d.group == "abilities" and d.triggers[0][0] == "flag_bit"
                 and BASE_ID + d.id_offset not in self.ctx.checked_locations]
        cands.sort(key=lambda d: not self.ff8.gf_unlocked(d.requires_gf))
        for d in cands:
            off, mask = d.triggers[0][1]
            orig = self.ff8.read_u8(off)
            if orig & mask:
                continue
            self.ff8.write_u8(off, orig | mask)
            await self.expect_check("gf ability (bit write)", d.name,
                                    restore=lambda: self.ff8.write_u8(off, orig))
            return
        self.record("gf ability (bit write)", "SKIP", "every signature ability already learned")

    async def test_rule_abolition(self):
        # bits_clear family: clear Dollet's Random bit (virgin 0x88 -> 0x80).
        if not self._in_seed("Rule Abolished: Random (Dollet)"):
            self.record("rule abolition (Dollet Random)", "SKIP", "not in seed (tt off?)")
            return
        if self.ff8.game_moment() < 20:
            self.record("rule abolition (Dollet Random)", "SKIP",
                        "moment < 20 (bits_clear init guard active)")
            return
        orig = self.ff8.read_u8(M.TT_RULES + 4)
        if not orig & M.TT_RULE_RANDOM:
            self.record("rule abolition (Dollet Random)", "SKIP", "already abolished")
            return
        self.ff8.write_u8(M.TT_RULES + 4, orig & ~M.TT_RULE_RANDOM)
        await self.expect_check(
            "rule abolition (Dollet Random)", "Rule Abolished: Random (Dollet)",
            restore=lambda: self.ff8.write_u8(M.TT_RULES + 4, orig))

    async def test_level_set(self):
        # cards_seen_range family: mark all 11 Level 1 commons "obtained once".
        if not self._in_seed("Card Compendium: Level 1 Set"):
            self.record("card level set (L1)", "SKIP", "not in seed (tt off?)")
            return
        orig = self.ff8.read_bytes(M.TT_CARDS, 11)
        if all(b & M.TT_CARD_SEEN for b in orig):
            self.record("card level set (L1)", "SKIP", "already complete")
            return
        self.ff8.write_bytes(M.TT_CARDS,
                             bytes(b | M.TT_CARD_SEEN for b in orig))
        await self.expect_check("card level set (L1 seen bits)",
                                "Card Compendium: Level 1 Set",
                                restore=lambda: self.ff8.write_bytes(M.TT_CARDS, orig))

    async def test_garden_wins(self):
        if not self._in_seed("Balamb Garden: 100 Card Wins"):
            self.record("garden wins (u8 write 100)", "SKIP", "not in seed (tt off?)")
            return
        orig = self.ff8.read_u8(M.BGU_WINS)
        if orig >= 100:
            self.record("garden wins (u8 write 100)", "SKIP", f"already {orig}")
            return
        self.ff8.write_u8(M.BGU_WINS, 100)
        await self.expect_check("garden wins (u8 write 100)",
                                "Balamb Garden: 100 Card Wins",
                                restore=lambda: self.ff8.write_u8(M.BGU_WINS, orig))

    async def test_dream_flag_edge(self):
        if not self._in_seed("Phoenix Summoned"):
            self.record("dream flag edge (Phoenix bit)", "SKIP", "not in seed (sidequests off?)")
            return
        orig = self.ff8.read_u8(M.DREAM_FLAGS)
        if orig & M.DREAM_PHOENIX:
            self.record("dream flag edge (Phoenix bit)", "SKIP", "bit already set")
            return
        self.ff8.write_u8(M.DREAM_FLAGS, orig | M.DREAM_PHOENIX)
        await self.expect_check("dream flag edge (Phoenix bit)", "Phoenix Summoned",
                                restore=lambda: self.ff8.write_u8(M.DREAM_FLAGS, orig))

    async def test_item_interception(self):
        """Write a vanilla Magical Lamp into the inventory; the client must
        send Cid's Parting Gift AND remove the lamp (vanilla-reward suppression)."""
        lamp = 168
        loc = "Cid's Parting Gift"
        if location_name_to_id[loc] in self.ctx.checked_locations:
            self.record("item interception (lamp)", "SKIP", "already checked before test")
            return
        if self.ff8.count_item(lamp):
            self.record("item interception (lamp)", "SKIP", "lamp already in inventory")
            return
        inv = self.ff8.read_inventory()
        slot = next((i for i, (iid, qty) in enumerate(inv) if iid == 0 or qty == 0), None)
        if slot is None:
            self.record("item interception (lamp)", "SKIP", "inventory full")
            return
        self.ff8.write_bytes(M.INVENTORY + slot * 2, bytes([lamp, 1]))
        await self.expect_check("item interception (lamp check)", loc)
        end = asyncio.get_event_loop().time() + CHECK_TIMEOUT
        removed = False
        while asyncio.get_event_loop().time() < end:
            if self.ff8.count_item(lamp) == 0:
                removed = True
                break
            await asyncio.sleep(POLL)
        if not removed:  # clean up ourselves so the save isn't polluted
            self.ff8.write_bytes(M.INVENTORY + slot * 2, bytes([0, 0]))
        self.record("item interception (lamp removed)", "PASS" if removed else "FAIL",
                    "" if removed else "client did not suppress the vanilla lamp")

    async def test_magic_enforcement(self):
        """checks_only seeds: inject 30 Cura into a free Squall slot; the
        client must repossess the excess (party totals return to the
        pre-inject value — on an idle save totals equal the cap, since grants
        raise stock and cap together and nothing has been cast mid-test)."""
        name = "magic enforcement (inject 30 Cura)"
        if self.ctx.slot_data_seen.get("magic_mode") != 1:
            self.record(name, "SKIP", "magic_mode is vanilla in this seed")
            return
        base = M.CHAR_BASE + M.CHAR_MAGIC_OFFSET   # Squall's magic list
        raw = self.ff8.read_bytes(base, M.CHAR_MAGIC_SLOTS * 2)
        slot = next((s for s in range(M.CHAR_MAGIC_SLOTS)
                     if raw[s * 2] == 0 or raw[s * 2 + 1] == 0), None)
        if slot is None:
            self.record(name, "SKIP", "Squall's magic list is full")
            return
        before = self.ff8.snapshot().magic_totals().get(22, 0)   # Cura, id 22
        self.ff8.write_bytes(base + slot * 2, bytes([22, 30]))
        end = asyncio.get_event_loop().time() + CHECK_TIMEOUT
        clamped = False
        while asyncio.get_event_loop().time() < end:
            if self.ff8.snapshot().magic_totals().get(22, 0) <= before:
                clamped = True
                break
            await asyncio.sleep(POLL)
        if not clamped:  # clean up ourselves so the save keeps no free magic
            self.ff8.write_bytes(base + slot * 2, raw[slot * 2:slot * 2 + 2])
        self.record(name, "PASS" if clamped else "FAIL",
                    "" if clamped else "injected stock was not repossessed")

    # ---- fake-battle tests --------------------------------------------------

    def _allies(self, hp: int, max_hp: int = 1000):
        for i in range(M.ALLY_COUNT):
            rec = M.BATTLE_ALLIES + i * M.ALLY_STRIDE
            self.ff8.write_u16(rec + M.ALLY_MAX_HP, max_hp)
            self.ff8.write_u16(rec + M.ALLY_CUR_HP, hp)

    async def _battle_flags_stick(self) -> bool:
        self.ff8.write_u8(M.POST_BATTLE, 1)
        await asyncio.sleep(0.4)
        ok = self.ff8.read_u8(M.POST_BATTLE) == 1
        if not ok:
            self.ff8.write_u8(M.POST_BATTLE, 0)
        return ok

    async def test_boss_win(self):
        if not await self._battle_flags_stick():
            self.record("boss win (fake battle)", "SKIP", "engine overwrites fight flag on field")
            return False
        self.ff8.write_u16(M.ENCOUNTER_ID, ENC_WIN)
        self._allies(hp=1000)
        await asyncio.sleep(SETTLE)
        self.ff8.write_u8(M.POST_BATTLE, 0)          # battle ends, party alive -> win
        await self.expect_check("boss win (fake battle, enc 745)", "UFO Sighting: Beach (Moai)")
        return True

    async def test_deathlink_receive(self):
        self.ff8.write_u8(M.POST_BATTLE, 1)
        self.ff8.write_u16(M.ENCOUNTER_ID, ENC_RECV)
        self._allies(hp=1000)
        await asyncio.sleep(SETTLE)
        await self.ctx.send_death("selftest death")
        end = asyncio.get_event_loop().time() + CHECK_TIMEOUT
        wiped = False
        while asyncio.get_event_loop().time() < end:
            hps = [self.ff8.read_u16(M.BATTLE_ALLIES + i * M.ALLY_STRIDE + M.ALLY_CUR_HP)
                   for i in range(M.ALLY_COUNT)]
            if all(h == 0 for h in hps):
                wiped = True
                break
            await asyncio.sleep(POLL)
        self.ff8.write_u8(M.POST_BATTLE, 0)          # end battle (as a loss)
        self.record("deathlink receive (client zeroes HP)", "PASS" if wiped else "FAIL")
        await asyncio.sleep(SETTLE)

    async def test_deathlink_send_and_loss(self):
        before = self.ctx.deaths_received
        self.ff8.write_u8(M.POST_BATTLE, 1)
        self.ff8.write_u16(M.ENCOUNTER_ID, ENC_LOSS)
        self._allies(hp=1000)
        await asyncio.sleep(SETTLE)                  # client sees party alive
        self._allies(hp=0)                           # wipe
        end = asyncio.get_event_loop().time() + CHECK_TIMEOUT
        while asyncio.get_event_loop().time() < end and self.ctx.deaths_received == before:
            await asyncio.sleep(POLL)
        got_death = self.ctx.deaths_received > before
        self.ff8.write_u8(M.POST_BATTLE, 0)          # battle ends as a loss
        self.record("deathlink send (party wipe)", "PASS" if got_death else "FAIL")
        await asyncio.sleep(SETTLE + 2)
        if location_name_to_id["UFO Sighting: Plains (Cow)"] in self.ctx.checked_locations:
            self.record("loss gives no win credit", "FAIL", "loss was credited as a win!")
        else:
            self.record("loss gives no win credit", "PASS")


async def main():
    parser = get_base_parser(description="FF8 apworld live self-test")
    parser.add_argument("--name", default=None, help="slot name")
    parser.add_argument("--skip-battle", action="store_true",
                        help="skip the fake-battle tests")
    args = parser.parse_args()

    ff8 = FF8Interface()
    if not ff8.attach():
        print("FATAL: FF8_EN.exe not running / not attachable")
        return
    if ff8.read_u8(M.IN_MENU) or ff8.read_u8(M.POST_BATTLE):
        print("FATAL: game must be idle on a field screen (not menu/battle)")
        return

    ctx = Observer(args.connect, args.password)
    if args.name:
        ctx.auth = args.name
    ctx.server_task = asyncio.create_task(server_loop(ctx), name="server loop")
    for _ in range(100):
        if ctx.slot:
            break
        await asyncio.sleep(0.2)
    if not ctx.slot:
        print("FATAL: could not connect to the AP server in 20s")
        await ctx.shutdown()
        return
    print(f"Connected as '{ctx.auth}'. Running self-tests "
          f"({len(ctx.checked_locations)} checks already sent)...")

    h = Harness(ctx, ff8)
    await h.test_draw_point()
    await h.test_tt_wins()
    await h.test_cc_group()
    await h.test_timber_maniacs()
    await h.test_rare_card()
    await h.test_blue_magic()
    await h.test_angelo()
    await h.test_tonberry_flag()
    await h.test_battles_won()
    await h.test_seed_tests()
    await h.test_weapon_remodel()
    await h.test_seal_ladder()
    await h.test_magazine()
    await h.test_unique_cards()
    await h.test_zell_duel()
    await h.test_battles_escaped()
    await h.test_seed_rank()
    await h.test_magic_drawn()
    await h.test_squall_level()
    await h.test_gf_ability()
    await h.test_rule_abolition()
    await h.test_level_set()
    await h.test_garden_wins()
    await h.test_dream_flag_edge()
    await h.test_item_interception()
    await h.test_magic_enforcement()
    if not args.skip_battle:
        if await h.test_boss_win():
            await h.test_deathlink_receive()
            await h.test_deathlink_send_and_loss()

    print("\n===== RESULTS =====")
    counts = {"PASS": 0, "FAIL": 0, "SKIP": 0}
    for name, status, detail in h.results:
        counts[status] = counts.get(status, 0) + 1
        print(f"{status:4} | {name}" + (f" — {detail}" if detail else ""))
    print(f"\n{counts.get('PASS', 0)} passed, {counts.get('FAIL', 0)} failed, "
          f"{counts.get('SKIP', 0)} skipped")
    report = Path(__file__).resolve().parent.parent / "output" / "live_test" / "selftest_report.txt"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(f"{s} | {n} | {d}" for n, s, d in h.results), encoding="utf-8")
    print(f"Report written to {report}")
    await ctx.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
