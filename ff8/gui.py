"""The client window's FF8 tab: every command the client has as a button,
beside the text client's own log.

Nothing here decides anything. gui_state.panel_state() says what to show, and
a click sends one of its slash commands through the command processor exactly
as if it had been typed, echo included. The log beside the buttons therefore
reads the same either way, and the prompt at the bottom of the window keeps
working from this tab.
"""

# kvui first: it configures kivy, and must load before any kivy module does.
from kvui import (ButtonsPrompt, GameManager, ResizableTextField, ScrollBox,
                  SelectableLabel, ToggleButton, UILog)

import copy
import logging

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import NumericProperty
from kivymd.icon_definitions import md_icons
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDButton, MDButtonText
from kivymd.uix.gridlayout import MDGridLayout
from kivymd.uix.label import MDLabel

from . import gui_state as gs

logger = logging.getLogger("Client")

REFRESH_SECONDS = 0.5
BUTTON_HEIGHT = dp(34)
SIDE_BY_SIDE_WIDTH = dp(880)    # narrower than this, the log goes under the controls
WINDOW_SIZE = (1100, 680)       # opening size; kivy's own 800x600 stacks the tab
DOT = "[font=Icons][size=11sp][color={}]" + md_icons["circle"] + "[/color][/size][/font]  "

# The labels size themselves in the rule (not adaptive_height, which leaves a
# label that starts out empty at the 100px widget default).
Builder.load_string("""
<FF8Heading,FF8Text,FF8Note>:
    size_hint_y: None
    height: self.texture_size[1]
<FF8Heading>:
    font_style: "Title"
    role: "medium"
    color: app.theme_cls.onSurfaceColor
<FF8Text>:
    font_style: "Body"
    role: "medium"
    color: app.theme_cls.onSurfaceColor
<FF8Note>:
    font_style: "Body"
    role: "small"
    color: app.theme_cls.onSurfaceVariantColor
<FF8Section>:
    orientation: "vertical"
    adaptive_height: True
    padding: "12dp"
    spacing: "8dp"
    radius: [dp(10)]
    md_bg_color: app.theme_cls.surfaceContainerColor
<FF8Tile>:
    orientation: "vertical"
    adaptive_height: True
    padding: "10dp", "8dp"
    spacing: "2dp"
    radius: [dp(8)]
    md_bg_color: app.theme_cls.surfaceContainerHighestColor
<FF8Alert>:
    orientation: "vertical"
    adaptive_height: True
    padding: "12dp"
    spacing: "8dp"
    radius: [dp(10)]
    md_bg_color: app.theme_cls.errorContainerColor
<FF8LogBox>:
    padding: "6dp"
    radius: [dp(10)]
    md_bg_color: app.theme_cls.surfaceContainerLowestColor
<FF8LogLine>:
    font_size: "16dp"
<FF8Log>:
    viewclass: "FF8LogLine"
<FF8Grid>:
    cols: 1
    adaptive_height: True
    spacing: "6dp"
<FF8Row>:
    adaptive_height: True
    spacing: "10dp"
<FF8TextInput>:
    size_hint_y: None
    height: "30dp"
    multiline: False
    write_tab: False
    pos_hint: {"center_y": 0.5}
""")


class FF8Heading(MDLabel):
    pass


class FF8Text(MDLabel):
    pass


class FF8Note(MDLabel):
    pass


class FF8Section(MDBoxLayout):
    pass


class FF8Tile(MDBoxLayout):
    pass


class FF8Alert(MDBoxLayout):
    pass


class FF8LogBox(MDBoxLayout):
    pass


class FF8LogLine(SelectableLabel):
    """The stock log line, a size down: this log shares the tab's width."""


class FF8Log(UILog):
    pass


class FF8Row(MDBoxLayout):
    pass


class FF8TextInput(ResizableTextField):
    pass


class FF8Grid(MDGridLayout):
    """Equal-width cells, as many to a row as fit."""
    cell = NumericProperty(dp(150))     # the narrowest a cell may get

    def on_width(self, _grid, width):
        self.cols = max(1, int(width // self.cell))


def make_button(text: str, on_release, style: str = "tonal", **kwargs) -> MDButton:
    kwargs.setdefault("size_hint_x", 1)
    button = MDButton(
        MDButtonText(text=text, pos_hint={"center_x": 0.5, "center_y": 0.5}),
        style=style, theme_width="Custom", radius=[dp(8)], **kwargs)
    button.height = BUTTON_HEIGHT
    button.bind(on_release=on_release)
    return button


def make_toggle(text: str, on_release) -> ToggleButton:
    toggle = ToggleButton(
        MDButtonText(text=text, pos_hint={"center_x": 0.5, "center_y": 0.5}),
        theme_width="Custom", size_hint_x=None, width=dp(150), radius=[dp(8)])
    toggle.height = BUTTON_HEIGHT
    toggle.bind(on_release=on_release)
    return toggle


class FF8Panel(MDBoxLayout):
    def __init__(self, manager: "FF8Manager", **kwargs):
        super().__init__(spacing=dp(8), padding=dp(8), **kwargs)
        self.manager = manager
        self.state: gs.PanelState | None = None
        self.refresh_failed = False
        self.action_buttons: list[tuple[gs.Action, MDButton]] = []
        self.tile_values: list[FF8Heading] = []
        self.warp_buttons: dict[str, MDButton] = {}
        colors = manager.json_to_kivy_parser.color_codes
        self.dot_ok, self.dot_waiting = colors["green"], colors["orange"]

        self.controls = ScrollBox()
        self.controls.layout.padding = (0, 0, dp(16), 0)    # clear of the scrollbar
        self.status = self.build_status()
        self.alerts = MDBoxLayout(orientation="vertical", adaptive_height=True,
                                  spacing=dp(8))
        self.travel = self.build_travel()
        self.unlocks = FF8Section()
        # top to bottom; apply() leaves out the ones with nothing to show
        self.sections = [self.status, self.alerts, self.build_assist(),
                         self.build_deathlink(), self.travel,
                         self.build_actions("Look things up", gs.LOOKUPS),
                         self.build_actions("Multiworld", gs.MULTIWORLD),
                         self.unlocks, self.build_repair()]
        self.shown: list = []
        self.add_widget(self.controls)

        self.log = FF8Log(logging.getLogger("Client"))
        self.log.on_log("The buttons on this tab send the same commands you "
                        "can type in the prompt below. Their answers land here.")
        self.log_box = FF8LogBox()
        self.log_box.add_widget(self.log)
        self.add_widget(self.log_box)
        self.on_size()
        self.refresh()

    # --- building -------------------------------------------------------
    def build_status(self) -> FF8Section:
        box = FF8Section()
        self.game_label = FF8Heading(markup=True)
        self.detail_label = FF8Note()
        self.server_label = FF8Text(markup=True)
        self.tiles = FF8Grid(cell=dp(118))
        for widget in (self.game_label, self.detail_label, self.server_label,
                       self.tiles):
            box.add_widget(widget)
        return box

    def build_assist(self) -> FF8Section:
        box = FF8Section()
        box.add_widget(FF8Heading(text="Battle Assist"))
        box.add_widget(FF8Note(
            text="Off until you turn it on, and never touches logic or the "
                 "save. Bosses and scripted fights are always fought for real."))
        self.assist_toggles = []
        for feature, label, what in gs.ASSIST_BUTTONS:
            toggle = make_toggle(label, lambda btn, f=feature: self.run(
                gs.assist_command(f, btn.state == "down")))
            self.assist_toggles.append(toggle)
            box.add_widget(self.toggle_row(toggle, what))
        row = FF8Row()
        for label, on in (("All on", True), ("All off", False)):
            row.add_widget(make_button(
                label, lambda _btn, on=on: self.run(gs.assist_command(None, on)),
                style="outlined", size_hint_x=None, width=dp(150)))
        box.add_widget(row)
        self.assist_note = FF8Note()
        box.add_widget(self.assist_note)
        return box

    def build_deathlink(self) -> FF8Section:
        box = FF8Section()
        box.add_widget(FF8Heading(text="DeathLink"))
        self.deathlink_toggle = make_toggle(
            "DeathLink", lambda _btn: self.run("/deathlink"))
        box.add_widget(self.toggle_row(
            self.deathlink_toggle,
            "A party wipe reaches every linked player, and theirs reach you"))
        return box

    def build_travel(self) -> FF8Section:
        box = FF8Section()
        box.add_widget(FF8Heading(text="Fast travel"))
        self.warp_grid = FF8Grid()
        self.warp_note = FF8Note()
        box.add_widget(self.warp_grid)
        box.add_widget(self.warp_note)
        return box

    def build_actions(self, title: str, actions) -> FF8Section:
        box = FF8Section()
        box.add_widget(FF8Heading(text=title))
        grid = FF8Grid()
        for action in actions:
            button = make_button(action.label,
                                 lambda _btn, a=action: self.press(a),
                                 style="outlined" if action.confirm else "tonal")
            self.action_buttons.append((action, button))
            grid.add_widget(button)
        box.add_widget(grid)
        return box

    def build_repair(self) -> FF8Section:
        box = FF8Section()
        box.add_widget(FF8Heading(text="Repair tools"))
        box.add_widget(FF8Note(
            text="Send a check the client provably missed, such as a boss "
                 "beaten while it was closed. Type the location's name, or "
                 "any part of it that fits only one."))
        box.add_widget(self.input_row("Send check", gs.check_action))
        box.add_widget(FF8Note(
            text="Write the story moment, for a save that kept a vehicle "
                 "window's temporary value (3167 on Disc 1 or 2)."))
        box.add_widget(self.input_row("Write moment", gs.moment_action))
        return box

    @staticmethod
    def toggle_row(toggle: ToggleButton, what: str) -> FF8Row:
        row = FF8Row()
        row.add_widget(toggle)
        row.add_widget(FF8Note(text=what, pos_hint={"center_y": 0.5}))
        return row

    def input_row(self, label: str, make_action) -> FF8Row:
        """A text box and its button; `make_action` turns the text into the
        Action to run, or None while the text isn't usable."""
        row = FF8Row()
        field = FF8TextInput()

        def submit(*_):
            action = make_action(field.text)
            if action:
                field.text = ""
                self.press(action)

        button = make_button(label, submit, size_hint_x=None, width=dp(150),
                             disabled=True)
        field.bind(on_text_validate=submit,
                   text=lambda _field, text: setattr(
                       button, "disabled", make_action(text) is None))
        row.add_widget(field)
        row.add_widget(button)
        return row

    # --- running commands -----------------------------------------------
    def run(self, command: str) -> None:
        ui = self.manager
        try:
            ui.ctx.on_ui_command(command)       # the echo typed input gets
            ui.commandprocessor(command)
        except Exception as e:
            logger.exception(e)
        self.refresh()

    def press(self, action: gs.Action) -> None:
        if not action.confirm:
            self.run(action.command)
            return

        def answer(choice: str) -> None:
            prompt.dismiss()
            if choice == action.label:
                self.run(action.command)

        prompt = ButtonsPrompt(action.label, action.confirm, answer,
                               action.label, "Cancel")
        prompt.open()

    # --- showing state --------------------------------------------------
    def refresh(self, *_) -> None:
        try:
            state = gs.panel_state(self.manager.ctx)
            if state != self.state:
                self.apply(state)
            self.refresh_failed = False
        except Exception as e:
            if not self.refresh_failed:     # once, not twice a second
                self.refresh_failed = True
                logger.exception(e)

    def apply(self, state: gs.PanelState) -> None:
        old, self.state = self.state, state
        self.game_label.text = DOT.format(
            self.dot_ok if state.game_ok else self.dot_waiting) + state.game
        self.detail_label.text = state.detail
        self.server_label.text = DOT.format(
            self.dot_ok if state.connected else self.dot_waiting) + state.server
        if len(self.tile_values) != len(state.tiles):
            self.tiles.clear_widgets()
            self.tile_values = []
            for caption, _value in state.tiles:
                tile = FF8Tile()
                self.tile_values.append(FF8Heading())
                tile.add_widget(self.tile_values[-1])
                tile.add_widget(FF8Note(text=caption))
                self.tiles.add_widget(tile)
        for label, (_caption, value) in zip(self.tile_values, state.tiles):
            label.text = value

        if old is None or old.alerts != state.alerts:
            self.alerts.clear_widgets()
            for alert in state.alerts:
                self.alerts.add_widget(self.make_alert(alert))

        for toggle, on in zip(self.assist_toggles, state.assist):
            toggle.state = "down" if on else "normal"
        self.assist_note.text = state.assist_note
        self.deathlink_toggle.state = "down" if state.deathlink else "normal"

        if old is None or ([w.key for w in old.warps]
                           != [w.key for w in state.warps]):
            self.warp_grid.clear_widgets()
            self.warp_buttons = {}
            for warp in state.warps:
                button = make_button(warp.name, lambda _btn, k=warp.key: self.run(
                    gs.warp_command(k)))
                self.warp_buttons[warp.key] = button
                self.warp_grid.add_widget(button)
        for warp in state.warps:
            self.warp_buttons[warp.key].disabled = not warp.enabled
        self.warp_note.text = state.warp_note

        if old is None or old.unlocks != state.unlocks:
            self.unlocks.clear_widgets()
            self.unlocks.add_widget(FF8Heading(text="Unlocks"))
            for line in state.unlocks:
                self.unlocks.add_widget(FF8Text(text=line))

        for action, button in self.action_buttons:
            button.disabled = not state.allows(action)

        hidden = set()
        if not state.alerts:
            hidden.add(self.alerts)
        if not state.warp_section:
            hidden.add(self.travel)
        if not state.unlocks:
            hidden.add(self.unlocks)
        shown = [s for s in self.sections if s not in hidden]
        if shown != self.shown:
            self.shown = shown
            self.controls.layout.clear_widgets()
            for section in shown:
                self.controls.layout.add_widget(section)

    def make_alert(self, alert: gs.Alert) -> FF8Alert:
        box = FF8Alert()
        text = FF8Text(text=alert.text)
        if alert.urgent:
            text.color = self.theme_cls.onErrorContainerColor
        else:
            box.md_bg_color = self.theme_cls.secondaryContainerColor
        box.add_widget(text)
        if alert.action:
            box.add_widget(make_button(
                alert.action.label, lambda _btn, a=alert.action: self.press(a),
                style="filled", size_hint_x=None, width=dp(190)))
        return box

    # --- layout ---------------------------------------------------------
    def on_size(self, *_) -> None:
        wide = self.width >= SIDE_BY_SIDE_WIDTH
        self.orientation = "horizontal" if wide else "vertical"
        self.controls.size_hint = (0.54, 1) if wide else (1, 0.62)
        self.log_box.size_hint = (0.46, 1) if wide else (1, 0.38)

    def fix_heights(self) -> None:
        """GameManager.update_texts calls this on the tab in view (the stock
        log's workaround for label heights drifting from their textures)."""
        self.log.fix_heights()


class FF8Manager(GameManager):
    base_title = "Archipelago Final Fantasy VIII Client"
    ff8_panel: FF8Panel | None = None

    def build(self):
        container = super().build()
        # The tab is an extra: if a future kvui breaks it, the stock text
        # client underneath must still come up.
        try:
            self.widen_window()
            self.ff8_panel = FF8Panel(self)
            self.ff8_tab = self.add_client_tab("FF8", self.ff8_panel)
            Clock.schedule_once(self.show_ff8_tab)
            Clock.schedule_interval(self.refresh_ff8_tab, REFRESH_SECONDS)
        except Exception as e:
            self.ff8_panel = None
            logger.exception(e)
            logger.warning("The FF8 tab could not be built; every command "
                           "still works from the prompt.")
        return container

    @staticmethod
    def widen_window() -> None:
        """Open wide enough for the buttons and the log side by side, growing
        around the window's centre."""
        width, height = Window.size
        if width >= WINDOW_SIZE[0]:
            return
        new_height = max(height, WINDOW_SIZE[1])
        left, top = Window.left, Window.top
        Window.size = (WINDOW_SIZE[0], new_height)
        Window.left = max(0, left - (WINDOW_SIZE[0] - width) // 2)
        Window.top = max(dp(30), top - (new_height - height) // 2)   # title bar stays on screen

    def show_ff8_tab(self, *_) -> None:
        self.screens.current_tab.active = False
        self.screens.switch_screens(self.ff8_tab)
        self.ff8_tab.active = True

    def refresh_ff8_tab(self, *_) -> None:
        if self.screens.current_tab is self.ff8_tab:
            self.ff8_panel.refresh()

    def print_json(self, data):
        if self.ff8_panel is not None:
            # a copy: the parser rewrites the message parts it is handed
            self.ff8_panel.log.on_message_markup(
                self.json_to_kivy_parser(copy.deepcopy(data)))
        super().print_json(data)
