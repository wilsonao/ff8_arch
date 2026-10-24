"""The client window's FF8 tab, without a window (gui_state has no kivy in
it): every button must be a command that really exists, and panel_state must
read a fake process the way /ff8 would."""

import unittest

from MultiServer import ClientMessageProcessor

from .. import gui_state as gs
from ..assist import AssistState
from ..client import BASE_ID, ITEM_TABLE, FF8CommandProcessor, unlock_summary
from ..memory import (AP_STATE_APPLIED_OFF, AP_STATE_FINGERPRINT_OFF,
                      AP_STATE_MAGIC, AP_STATE_MAGIC_OFF, FIELD_ID, GAME_MOMENT,
                      GIL, IN_MENU, MODULE_BATTLE, MODULE_CARD_GAME,
                      MODULE_DISPATCH, MODULE_FIELD, MODULE_MENU, MODULE_TITLE,
                      MODULE_WORLDMAP, POST_BATTLE, FF8Interface)
from .test_vehicle_window import FakeProc, _Item

ITEM_IDS = {d.name: BASE_ID + d.id_offset for d in ITEM_TABLE}
FINGERPRINT = 0x1234ABCD


class DeadProc(FakeProc):
    """Attached to a process that has just gone away."""

    def read_u16(self, off):
        raise OSError("process gone")


class PanelCtx:
    def __init__(self, attached=True, connected=True, moment=233, items=()):
        self.ff8 = FakeProc() if attached else FF8Interface()
        self.server = object() if connected else None
        self.slot = 1 if connected else None
        self.auth = "Squall"
        self.finished_game = False
        self.slot_data = {}
        self.items_received = [_Item(ITEM_IDS[name]) for name in items]
        self.checked_locations = set(range(40))
        self.missing_locations = set(range(40, 580))
        self.tags = {"AP"}
        self.assist = AssistState()
        self.save_fingerprint = FINGERPRINT
        self.legacy_fingerprint = 0
        self.save_frozen = None
        self.story_hold = None
        self.stood_down_logged = False
        self.pending_deathlink = False
        self.attach_hint_logged = None
        self.moment_faked = False
        self.true_moment = None
        if attached:
            self.ff8.write_u16(MODULE_DISPATCH, MODULE_WORLDMAP)
            self.ff8.write_u16(GAME_MOMENT, moment)
            self.ff8.write_u16(FIELD_ID, 157)
            self.ff8.write_u32(GIL, 48250)

    def stamp_save(self, applied):
        self.ff8.write_u16(AP_STATE_MAGIC_OFF, AP_STATE_MAGIC)
        self.ff8.write_u32(AP_STATE_FINGERPRINT_OFF, FINGERPRINT)
        self.ff8.write_u16(AP_STATE_APPLIED_OFF, applied)


def tiles(state):
    return dict(state.tiles)


class TestButtonsAreCommands(unittest.TestCase):
    def assert_command(self, text):
        word = text.split()[0]
        table = (FF8CommandProcessor if word[0] == "/"
                 else ClientMessageProcessor).commands
        self.assertIn(word[0], "/!", text)
        self.assertIn(word[1:], table, text)

    def test_every_button(self):
        commands = [a.command for a in (*gs.LOOKUPS, *gs.MULTIWORLD,
                                        gs.ADOPT, gs.KEEP_STORY)]
        commands += [gs.assist_command(f, on) for f, *_ in gs.ASSIST_BUTTONS
                     for on in (True, False)]
        commands += [gs.assist_command(None, True), gs.warp_command("balamb"),
                     gs.check_action("Ifrit").command,
                     gs.moment_action("205").command, "/deathlink"]
        for text in commands:
            self.assert_command(text)

    def test_what_cannot_be_undone_asks_first(self):
        for action in (gs.ADOPT, gs.KEEP_STORY, gs.check_action("Ifrit"),
                       gs.moment_action("205"),
                       *(a for a in gs.MULTIWORLD
                         if a.command in ("!release", "!collect"))):
            self.assertTrue(action.confirm, action.label)
        for action in gs.LOOKUPS:
            self.assertFalse(action.confirm, action.label)

    def test_assist_commands(self):
        self.assertEqual(gs.assist_command("enc", True), "/ff8assist enc on")
        self.assertEqual(gs.assist_command("hp", False), "/ff8assist hp off")
        self.assertEqual(gs.assist_command(None, False), "/ff8assist off")

    def test_check_box(self):
        self.assertIsNone(gs.check_action("   "))
        self.assertEqual(gs.check_action("  Fire  Cavern: Ifrit ").command,
                         "/ff8check Fire Cavern: Ifrit")

    def test_moment_box_takes_only_a_16_bit_number(self):
        for text in ("", "abc", "-5", "20.5", "65536", "3167x"):
            self.assertIsNone(gs.moment_action(text), text)
        self.assertEqual(gs.moment_action(" 0205 ").command, "/ff8moment 205")
        self.assertEqual(gs.moment_action("65535").command, "/ff8moment 65535")


class TestGameMode(unittest.TestCase):
    def mode(self, module, in_menu=0, post_battle=0):
        ff8 = FakeProc()
        ff8.write_u16(MODULE_DISPATCH, module)
        ff8.write_u8(IN_MENU, in_menu)
        ff8.write_u8(POST_BATTLE, post_battle)
        return gs.game_mode(ff8)

    def test_modes(self):
        self.assertEqual(self.mode(MODULE_TITLE), "Title screen")
        self.assertEqual(self.mode(MODULE_FIELD), "Field")
        self.assertEqual(self.mode(MODULE_WORLDMAP), "World map")
        self.assertEqual(self.mode(MODULE_BATTLE), "Battle")
        self.assertEqual(self.mode(4, post_battle=1), "Battle")     # results
        self.assertEqual(self.mode(MODULE_MENU), "Menu")
        self.assertEqual(self.mode(MODULE_WORLDMAP, in_menu=1), "Menu")
        # POST_BATTLE pulses junk all through a card game
        self.assertEqual(self.mode(MODULE_CARD_GAME, post_battle=1), "Triple Triad")


class TestPanelState(unittest.TestCase):
    def test_nothing_running(self):
        ctx = PanelCtx(attached=False, connected=False)
        state = gs.panel_state(ctx)
        self.assertEqual(state.game, "Waiting for FF8_EN.exe")
        self.assertFalse(state.game_ok)
        self.assertFalse(state.connected)
        self.assertEqual(set(tiles(state).values()), {"–"})
        self.assertEqual(state.alerts, ())
        self.assertFalse(state.warp_section)
        self.assertEqual(state.unlocks, ())
        self.assertTrue(state.allows(gs.LOOKUPS[0]))            # /ff8 always answers
        self.assertFalse(state.allows(gs.Action("x", "/ff8missed", needs="game")))
        self.assertFalse(state.allows(gs.MULTIWORLD[0]))

    def test_attach_hint_is_shown(self):
        ctx = PanelCtx(attached=False)
        ctx.attach_hint_logged = "FF8_EN.exe is running but could not be opened."
        self.assertEqual([a.text for a in gs.panel_state(ctx).alerts],
                         [ctx.attach_hint_logged])

    def test_playing(self):
        ctx = PanelCtx(items=("Warp: Balamb", "Warp: Dollet"))
        ctx.stamp_save(1)
        state = gs.panel_state(ctx)
        self.assertTrue(state.game_ok and state.connected)
        self.assertEqual(state.server, "Connected as Squall")
        self.assertEqual(tiles(state), {"Checks sent": "40/580",
                                        "Items in this save": "1/2",
                                        "Story moment": "233",
                                        "Game screen": "World map"})
        self.assertIn("48,250 gil", state.detail)
        self.assertTrue(all(state.allows(a) for a in (*gs.LOOKUPS, *gs.MULTIWORLD)))

    def test_unstamped_save(self):
        ctx = PanelCtx(items=("Warp: Balamb",))
        self.assertEqual(tiles(gs.panel_state(ctx))["Items in this save"], "1 waiting")

    def test_attached_without_a_server(self):
        state = gs.panel_state(PanelCtx(connected=False))
        self.assertTrue(state.game_ok)
        self.assertEqual(tiles(state)["Checks sent"], "–")
        self.assertEqual(tiles(state)["Story moment"], "233")
        self.assertIn("connect to a multiworld", state.detail)

    def test_true_moment_while_a_vehicle_window_is_open(self):
        ctx = PanelCtx(moment=3167)
        ctx.moment_faked, ctx.true_moment = True, 205
        state = gs.panel_state(ctx)
        self.assertEqual(tiles(state)["Story moment"], "205")
        self.assertIn("vehicle spawn window", state.detail)

    def test_reads_failing(self):
        ctx = PanelCtx()
        ctx.ff8 = DeadProc()
        state = gs.panel_state(ctx)
        self.assertFalse(state.game_ok)
        self.assertIn("reads are failing", state.game)
        self.assertEqual(tiles(state)["Story moment"], "–")
        self.assertFalse(state.allows(gs.Action("x", "/ff8missed", needs="game")))

    def test_goal(self):
        ctx = PanelCtx()
        ctx.finished_game = True
        self.assertIn("goal complete", gs.panel_state(ctx).server)

    def test_toggles(self):
        ctx = PanelCtx()
        self.assertEqual(gs.panel_state(ctx).assist, (False,) * 4)
        self.assertFalse(gs.panel_state(ctx).deathlink)
        ctx.assist.atb = ctx.assist.enc = True
        ctx.assist.oneshots = 1
        ctx.tags.add("DeathLink")
        state = gs.panel_state(ctx)
        self.assertEqual(dict(zip((f for f, *_ in gs.ASSIST_BUTTONS), state.assist)),
                         {"oneshot": False, "atb": True, "hp": False, "enc": True})
        self.assertEqual(state.assist_note, "1 fight one-shot this session")
        self.assertTrue(state.deathlink)

    def test_alerts(self):
        ctx = PanelCtx()
        ctx.stood_down_logged = True
        ctx.save_frozen = "it belongs to a DIFFERENT AP campaign"
        ctx.story_hold = (20, 233)
        ctx.pending_deathlink = True
        alerts = gs.panel_state(ctx).alerts
        self.assertEqual([a.action for a in alerts],
                         [None, gs.ADOPT, gs.KEEP_STORY, None])
        self.assertEqual([a.urgent for a in alerts], [True, True, True, False])
        self.assertIn("DIFFERENT AP campaign", alerts[1].text)
        self.assertIn("from 20 to 233", alerts[2].text)


class TestWarps(unittest.TestCase):
    OWNED = ("Warp: Esthar", "Warp: Balamb", "Warp: Dollet")

    def ctx(self, **kwargs):
        ctx = PanelCtx(items=self.OWNED, **kwargs)
        ctx.slot_data = {"fast_travel": 1}
        return ctx

    def test_hidden_unless_the_slot_plays_with_warps(self):
        ctx = self.ctx()
        ctx.slot_data = {}
        state = gs.panel_state(ctx)
        self.assertFalse(state.warp_section)
        self.assertEqual(state.warps, ())

    def test_nothing_unlocked_yet(self):
        ctx = self.ctx()
        ctx.items_received = []
        state = gs.panel_state(ctx)
        self.assertTrue(state.warp_section)
        self.assertEqual(state.warps, ())
        self.assertIn("No destinations yet", state.warp_note)

    def test_on_the_world_map(self):
        state = gs.panel_state(self.ctx(moment=233))
        # canonical order, not the order received; Esthar's chapter is far off
        self.assertEqual([(w.name, w.enabled) for w in state.warps],
                         [("Balamb", True), ("Dollet", True), ("Esthar", False)])
        self.assertIn("Esthar (the Esthar chapter)", state.warp_note)
        self.assertNotIn("world map", state.warp_note)

    def test_not_on_the_world_map(self):
        for setup in (lambda f: f.write_u16(MODULE_DISPATCH, MODULE_FIELD),
                      lambda f: f.write_u8(IN_MENU, 1)):
            ctx = self.ctx()
            setup(ctx.ff8)
            state = gs.panel_state(ctx)
            self.assertFalse(any(w.enabled for w in state.warps))
            self.assertIn("from the world map", state.warp_note)

    def test_game_not_running(self):
        ctx = self.ctx(attached=False)
        state = gs.panel_state(ctx)
        self.assertEqual([w.name for w in state.warps], ["Balamb", "Dollet", "Esthar"])
        self.assertFalse(any(w.enabled for w in state.warps))
        self.assertEqual(state.warp_note, "Warps need the game running.")


class TestUnlockSummary(unittest.TestCase):
    def test_quiet_without_lock_options(self):
        self.assertEqual(unlock_summary(PanelCtx(), 233), [])

    def test_lists_each_lock_option_in_play(self):
        ctx = PanelCtx()
        ctx.slot_data = {"character_locks": 1, "command_locks": 1, "ability_locks": 1}
        lines = unlock_summary(ctx, 233)
        self.assertEqual(lines[0], "Character locks on — junction rights: Squall")
        self.assertEqual(lines[1], "Command locks — still locked: Magic, GF, Draw, Item")
        self.assertEqual(lines[2], "GF ability locks — 0/50 signature abilities unlocked")
        self.assertEqual(tuple(lines), gs.panel_state(ctx).unlocks)
