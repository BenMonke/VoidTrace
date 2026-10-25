"""The VoidTrace window: an icon rail on the left (Market, Rivens, Relics; Discord, settings and the
account at the bottom), and on the right the section's header line (title and page tabs) above the
chosen page.

Every page is addressed by a key such as "market/buy" or "rivens/price". The last page you used is
remembered (settings `last_page`), so is the last tab of each section (`last_tabs`), and the window
size (`window_size`). Riven data is a second download, so the Rivens section is built the first time
one of its pages is opened.
"""

from __future__ import annotations

import logging
import threading
import weakref
from typing import Callable, Optional

from PyQt6.QtCore import QEvent, QRectF, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QActionGroup, QColor, QFont, QIcon, QPainter
from PyQt6.QtWidgets import (QButtonGroup, QColorDialog, QFrame, QHBoxLayout, QLabel, QMenu, QPushButton,
                             QStackedWidget, QToolButton, QVBoxLayout, QWidget)

from .. import online_status, settings, svg_icons
from .. import theme as T
from .market import MarketSection
from .relics import RelicSection
from .widgets import BUTTON_STYLE, STYLE, Section

log = logging.getLogger(__name__)

RIVEN_PAGES = {"find": "Find", "price": "Price check", "sell": "Sell", "mine": "My rivens"}
SECTIONS = (("market", "Market", MarketSection.PAGES),
            ("rivens", "Rivens", RIVEN_PAGES),
            ("relics", "Relics", RelicSection.PAGES))
PAGE_KEYS = [f"{section}/{page}" for section, _title, pages in SECTIONS for page in pages]
DEFAULT_PAGE = "market/buy"
DEFAULT_SIZE = (1280, 800)
STATUS_DOT = {"ingame": T.POSITIVE, "online": T.STATUS_ONLINE}

SHELL_STYLE = f"""
QWidget#rail {{ background: {T.BG_PANEL}; border-right: 1px solid {T.BORDER_SUBTLE}; }}
QWidget#rail QLabel {{ background: transparent; }}
QFrame#raildiv {{ background: {T.BORDER_STRONG}; border: none; }}
QToolButton#tile {{ background: transparent; border: 1px solid transparent; border-radius: 12px; }}
QToolButton#tile:hover {{ background: {T.BG_HOVER}; }}
QToolButton#tile:checked {{ background: {T.DEFAULT_ACCENT}; }}
QToolButton#tile:focus {{ border-color: {T.TEXT_PRIMARY}; }}
QToolButton#tile::menu-indicator {{ image: none; width: 0; }}
QPushButton#tab {{ background: transparent; border: none; border-bottom: 2px solid transparent; border-radius: 0;
    color: {T.TEXT_SECONDARY}; padding: 0 10px; min-height: 30px; }}
QPushButton#tab:hover {{ color: {T.TEXT_PRIMARY}; background: transparent; }}
QPushButton#tab:checked {{ color: {T.TEXT_PRIMARY}; border-bottom-color: {T.DEFAULT_ACCENT}; }}
QPushButton#tab:focus {{ color: {T.TEXT_PRIMARY}; background: {T.BG_RAISED}; border-radius: 4px; }}
"""


def accent_menu(parent: QWidget) -> QMenu:
    """Accent colour: presets, or any colour; remembered, and every window follows at once."""
    menu = QMenu("Accent colour", parent)
    group = QActionGroup(menu)
    current = T.accent_hex().lower()
    for name, color in T.PRESETS.items():
        action = menu.addAction(name)
        action.setCheckable(True)
        action.setChecked(color.lower() == current)
        action.setActionGroup(group)
        action.triggered.connect(lambda _=False, c=color: T.set_accent(c))
    menu.addSeparator()

    def pick() -> None:
        chosen = QColorDialog.getColor(T.accent(), None, "VoidTrace accent colour")
        if chosen.isValid():
            for action in group.actions():
                action.setChecked(False)
            T.set_accent(chosen.name())

    menu.addAction("Custom…", pick)
    return menu


class RailTile(QToolButton):
    """A 44px rail tile: icon only, tinted for its state (hover lightens, selected sits on the accent)."""

    def __init__(self, icon_name: str, label: str, checkable: bool = False) -> None:
        super().__init__(objectName="tile")
        self.icon_name = icon_name
        self.hovered = False
        self.setCheckable(checkable)
        self.setToolTip(label)
        self.setAccessibleName(label)
        self.setFixedSize(T.RAIL_TILE, T.RAIL_TILE)
        self.setIconSize(QSize(22, 22))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggled.connect(lambda _on: self.retint())
        self.retint()

    def retint(self) -> None:
        if self.isChecked():
            color = T.on_accent_hex()
        else:
            color = T.TEXT_PRIMARY if self.hovered else T.RAIL_ICON
        self.setIcon(QIcon(svg_icons.pixmap(self.icon_name, color, 22)))

    def enterEvent(self, event) -> None:  # noqa: N802
        self.hovered = True
        self.retint()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self.hovered = False
        self.retint()
        super().leaveEvent(event)


class AvatarButton(QToolButton):
    """The account: first initial in a circle with the Warframe.Market status dot, or a user icon."""

    def __init__(self) -> None:
        super().__init__(objectName="tile")
        self.initial = ""
        self.status: Optional[str] = None
        self.setFixedSize(T.RAIL_TILE, T.RAIL_TILE)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)  # the tile's hover and focus
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        circle = QRectF(6, 6, 32, 32)
        if not self.initial:
            p.drawPixmap(11, 11, svg_icons.pixmap("user", T.RAIL_ICON, 22))
            return
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(T.BG_HOVER))
        p.drawEllipse(circle)
        font = QFont(self.font())
        font.setPixelSize(T.TYPE_BODY)
        font.setWeight(QFont.Weight.DemiBold)
        p.setFont(font)
        p.setPen(QColor(T.TEXT_PRIMARY))
        p.drawText(circle, Qt.AlignmentFlag.AlignCenter, self.initial)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(T.BG_PANEL))  # the 2px ring that separates the dot from the circle
        p.drawEllipse(QRectF(28, 28, 14, 14))
        p.setBrush(QColor(STATUS_DOT.get(self.status or "", T.TEXT_MUTED)))
        p.drawEllipse(QRectF(30, 30, 10, 10))


class MainWindow(QWidget):
    _rivens_loaded = pyqtSignal(object)
    _rivens_failed = pyqtSignal(str)

    def __init__(self, market: MarketSection, relics: RelicSection,
                 load_riven_data: Callable[[], object], make_rivens: Callable[[object], Section],
                 discord=None) -> None:
        super().__init__()
        self.setWindowTitle("VoidTrace")
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
        T.follow(self, STYLE + BUTTON_STYLE + SHELL_STYLE)
        self.market, self.relics = market, relics
        self.account = market.account
        self.load_riven_data, self.make_rivens = load_riven_data, make_rivens
        self._rivens: Optional[Section] = None
        self._rivens_loading = False
        self._riven_page = "find"
        self._riven_waiting: list[Callable[[Section], None]] = []
        self._current = ""
        self.status_keeper = None
        saved = settings.get("last_tabs")
        self._last_tab: dict[str, str] = saved if isinstance(saved, dict) else {}

        # --- rail
        self.logo = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.logo.setFixedSize(T.RAIL_TILE, 32)
        self.logo.setAccessibleName("VoidTrace")
        self.tiles: dict[str, RailTile] = {}
        self._tile_group = QButtonGroup(self)
        for name, title, _pages in SECTIONS:
            tile = RailTile(name, title, checkable=True)
            tile.clicked.connect(lambda _=False, n=name: self.open_section(n))
            tile.installEventFilter(self)
            self._tile_group.addButton(tile)
            self.tiles[name] = tile
        self.ducats_tile = RailTile("ducats", "Ducanator (coming soon)")
        self.ducats_tile.setCursor(Qt.CursorShape.ArrowCursor)
        self.discord_button = RailTile("bell", "Discord notifications")
        self.discord_button.setVisible(discord is not None)
        self.discord_button.clicked.connect(lambda: self._open_discord(discord))
        self.settings_button = RailTile("settings", "Settings")
        self.settings_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.settings_menu = QMenu(self)
        self.settings_menu.addMenu(accent_menu(self.settings_menu))
        self.settings_button.setMenu(self.settings_menu)
        self.account_button = AvatarButton()
        self.account_menu = QMenu(self)
        self.account_button.setMenu(self.account_menu)
        self.ingame_action = QAction("Show me in game on Warframe.Market while playing", self)
        self.ingame_action.setCheckable(True)
        self.ingame_action.setChecked(online_status.enabled())
        self.ingame_action.toggled.connect(self._ingame_toggled)

        rail = QWidget(objectName="rail")
        rail.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        rail.setFixedWidth(T.RAIL_WIDTH)
        left = QVBoxLayout(rail)
        left.setContentsMargins(10, 14, 10, 12)
        left.setSpacing(8)
        left.addWidget(self.logo, 0, Qt.AlignmentFlag.AlignHCenter)
        divider = QFrame(objectName="raildiv")
        divider.setFixedSize(28, 1)
        left.addSpacing(8)
        left.addWidget(divider, 0, Qt.AlignmentFlag.AlignHCenter)
        left.addSpacing(8)
        for tile in (*self.tiles.values(), self.ducats_tile):
            left.addWidget(tile, 0, Qt.AlignmentFlag.AlignHCenter)
        left.addStretch(1)
        for tile in (self.discord_button, self.settings_button, self.account_button):
            left.addWidget(tile, 0, Qt.AlignmentFlag.AlignHCenter)

        # --- header line: section title, page tabs, the page's toast
        self.section_title = QLabel(objectName="title")
        self.tab_rows = QStackedWidget()
        self.tabs: dict[str, QPushButton] = {}
        self._tab_row: dict[str, QWidget] = {}
        for section, _title, pages in SECTIONS:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(4)
            group = QButtonGroup(row)
            for page, label in pages.items():
                key = f"{section}/{page}"
                tab = QPushButton(label, objectName="tab", checkable=True)
                tab.setCursor(Qt.CursorShape.PointingHandCursor)
                tab.clicked.connect(lambda _=False, k=key: self.show_page(k))
                tab.installEventFilter(self)
                group.addButton(tab)
                row_layout.addWidget(tab)
                self.tabs[key] = tab
            row_layout.addStretch(1)
            self.tab_rows.addWidget(row)
            self._tab_row[section] = row
        self.toast_slot = QHBoxLayout()
        self.toast_slot.setContentsMargins(0, 0, 0, 0)
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(T.SPACE_4)
        header.addWidget(self.section_title)
        header.addWidget(self.tab_rows, 1)
        header.addLayout(self.toast_slot)

        self.riven_placeholder = QLabel(objectName="muted", alignment=Qt.AlignmentFlag.AlignCenter, wordWrap=True)
        self.stack = QStackedWidget()
        for widget in (market, relics, self.riven_placeholder):
            self.stack.addWidget(widget)
        for section in (market, relics):
            self._watch(section)

        content = QVBoxLayout()
        content.setContentsMargins(T.SPACE_6, T.SPACE_8, T.SPACE_6, T.SPACE_6)
        content.setSpacing(0)
        content.addLayout(header)
        content.addWidget(self.stack, 1)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(rail)
        layout.addLayout(content, 1)

        self._rivens_loaded.connect(self._on_rivens_loaded)
        self._rivens_failed.connect(self._on_rivens_failed)
        self._save_size = QTimer(self, singleShot=True, interval=500)
        self._save_size.timeout.connect(lambda: settings.put("window_size", [self.width(), self.height()]))
        size = settings.get("window_size")
        try:
            self.resize(int(size[0]), int(size[1]))
        except (TypeError, ValueError, IndexError):
            self.resize(*DEFAULT_SIZE)
        self._retint()
        retint = weakref.WeakMethod(self._accent_changed)  # a listener must not keep the window alive
        T.on_change(lambda: retint() and retint()())
        self.refresh_account_button()
        last = settings.get("last_page")
        self.show_page(last if last in PAGE_KEYS else DEFAULT_PAGE)

    # --- pages ------------------------------------------------------------------------------------

    def section(self, name: str) -> Optional[Section]:
        return {"market": self.market, "relics": self.relics, "rivens": self._rivens}.get(name)

    def rivens(self) -> Optional[Section]:
        return self._rivens

    def current_page(self) -> str:
        return self._current

    def open_page(self, key: Optional[str] = None) -> None:
        """Bring the window up, maximized, on `key` (e.g. "market/buy") or on the last page used."""
        self.showMaximized()
        self.raise_()
        self.activateWindow()
        self.show_page(key or self.current_page())

    def open_section(self, name: str) -> None:
        """A rail tile: the section on the tab it was last left on."""
        pages = dict((s, p) for s, _t, p in SECTIONS)[name]
        page = self._last_tab.get(name)
        self.show_page(f"{name}/{page if page in pages else next(iter(pages))}")

    def open_item(self, slug: str) -> None:
        """A reward card was clicked: Market > Buy on that item."""
        self.open_page("market/buy")
        self.market.open_item(slug)

    def read_riven(self, frame) -> None:
        """Ctrl+Shift+R in game: read the riven on this screenshot into Rivens > Price check."""
        self.open_page("rivens/price")
        self.with_rivens(lambda rivens: rivens.read_from_frame(frame))

    def open_riven_draft(self, draft) -> None:
        """The riven popup was clicked: Rivens > Price check on that riven, checked at once."""
        self.open_page("rivens/price")
        if draft is not None:
            self.with_rivens(lambda rivens: (rivens.load_draft(draft), rivens.price_panel.run_check()))

    def tab_keys(self) -> list[str]:
        return list(self.tabs)

    def tab_labels(self) -> list[str]:
        return [tab.text() for tab in self.tabs.values()]

    def show_page(self, key: str) -> None:
        if key not in PAGE_KEYS:
            key = DEFAULT_PAGE
        name, page = key.split("/")
        self._current = key
        settings.put("last_page", key)
        self._select(key)
        if name == "rivens" and self._rivens is None:
            self._riven_page = page
            self.stack.setCurrentWidget(self.riven_placeholder)
            self._load_rivens()
            return
        section = self.section(name)
        self.stack.setCurrentWidget(section)
        self._dock_toast(section)
        section.show_page(page)

    def _select(self, key: str) -> None:
        section, page = key.split("/")
        self.section_title.setText(dict((s, t) for s, t, _p in SECTIONS)[section])
        self.tab_rows.setCurrentWidget(self._tab_row[section])
        self.tiles[section].setChecked(True)
        self.tabs[key].setChecked(True)
        if self._last_tab.get(section) != page:
            self._last_tab[section] = page
            settings.put("last_tabs", dict(self._last_tab))

    def _dock_toast(self, section: Section) -> None:
        """The section's toast sits at the right end of the header line."""
        if section.toast.parent() is not self:
            self.toast_slot.addWidget(section.toast)
        for i in range(self.toast_slot.count()):
            widget = self.toast_slot.itemAt(i).widget()
            widget.setVisible(widget is section.toast)

    def _watch(self, section: Section) -> None:
        name = next(n for n in ("market", "relics", "rivens") if self.section(n) is section)
        section.account_switched.connect(self.account_changed)
        section.page_changed.connect(lambda page, n=name: self._section_moved(f"{n}/{page}"))

    def _section_moved(self, key: str) -> None:
        """A section switched page by itself (e.g. Price check -> Sell): keep the tabs in step."""
        if key in PAGE_KEYS and key != self._current and self.stack.currentWidget() is self.section(key.split("/")[0]):
            self._current = key
            settings.put("last_page", key)
            self._select(key)

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 (Qt naming)
        """Arrow keys: Left/Right move between page tabs, Up/Down between rail sections."""
        if event.type() != QEvent.Type.KeyPress:
            return False
        keys = {Qt.Key.Key_Left: -1, Qt.Key.Key_Right: 1} if obj in self.tabs.values() else \
            {Qt.Key.Key_Up: -1, Qt.Key.Key_Down: 1}
        step = keys.get(event.key())
        if step is None:
            return False
        if obj in self.tabs.values():
            section = self._current.split("/")[0]
            row = [k for k in PAGE_KEYS if k.startswith(section + "/")]
            key = row[(row.index(self._current) + step) % len(row)]
            self.show_page(key)
            self.tabs[key].setFocus()
        else:
            names = list(self.tiles)
            name = names[(names.index(self._current.split("/")[0]) + step) % len(names)]
            self.open_section(name)
            self.tiles[name].setFocus()
        return True

    # --- rivens, loaded on first use -----------------------------------------------------------------

    def with_rivens(self, callback: Callable[[Section], None]) -> None:
        """Call `callback(rivens_section)` now, or once riven data has loaded (it starts loading)."""
        if self._rivens is not None:
            callback(self._rivens)
            return
        self._riven_waiting.append(callback)
        self._load_rivens()

    def _load_rivens(self) -> None:
        if self._rivens_loading:
            return
        self._rivens_loading = True
        self.riven_placeholder.setText("Loading riven data…")

        def work() -> None:
            try:
                self._rivens_loaded.emit(self.load_riven_data())
            except Exception as exc:
                log.warning("could not load riven data: %s", exc)
                self._rivens_failed.emit(str(exc))

        threading.Thread(target=work, name="VoidTrace-RivenData", daemon=True).start()

    def _on_rivens_loaded(self, data) -> None:
        self._rivens_loading = False
        try:
            self._rivens = self.make_rivens(data)
        except Exception as exc:
            log.warning("could not build the Rivens section: %s", exc)
            self._on_rivens_failed(str(exc))
            return
        self.stack.addWidget(self._rivens)
        self._watch(self._rivens)
        if self._current.startswith("rivens/"):
            self.show_page(f"rivens/{self._riven_page}")
        waiting, self._riven_waiting = self._riven_waiting, []
        for callback in waiting:
            callback(self._rivens)

    def _on_rivens_failed(self, message: str) -> None:
        self._rivens_loading = False
        self._riven_waiting.clear()
        self.riven_placeholder.setText(f"Could not load riven data from Warframe.Market: {message}\n\n"
                                       "Open a Rivens page again to retry.")

    def _open_discord(self, notifier) -> None:
        from .discord import DiscordDialog

        DiscordDialog(self, notifier).exec()

    # --- accent ------------------------------------------------------------------------------------

    def _retint(self) -> None:
        self.logo.setPixmap(svg_icons.logo(T.accent_hex(), T.TEXT_PRIMARY, 32))
        for tile in (*self.tiles.values(), self.ducats_tile, self.discord_button, self.settings_button):
            tile.retint()

    def _accent_changed(self) -> None:
        try:
            self._retint()
        except RuntimeError:  # this window is gone
            pass

    # --- account -----------------------------------------------------------------------------------

    def set_status_keeper(self, keeper) -> None:
        """The online_status.StatusKeeper: the avatar's dot shows what it last set."""
        self.status_keeper = keeper
        keeper.changed.connect(lambda _line: self.refresh_account_button())
        self.refresh_account_button()

    def _status(self) -> Optional[str]:
        shown = getattr(self.status_keeper, "shown", None)
        return shown if shown in online_status.LABEL else None

    def refresh_account_button(self) -> None:
        button, menu = self.account_button, self.account_menu
        menu.clear()
        if self.account.signed_in:
            name = self.account.ingame_name or "You"
            status = self._status()
            label = online_status.LABEL[status] if status else "Status not set by VoidTrace"
            if status == "ingame":
                label += " (automatic while Warframe runs)"
            button.initial, button.status = name[:1].upper(), status
            button.setToolTip(f"{name} · {label}")
            button.setAccessibleName(f"Account: {name}, {label}")
            menu.addAction(f"{name} · {label}").setEnabled(False)
            menu.addSeparator()
            menu.addAction(self.ingame_action)
            menu.addSeparator()
            menu.addAction(svg_icons.icon("log-out", T.TEXT_SECONDARY), "Sign out", self._sign_out)
        else:
            button.initial, button.status = "", None
            button.setToolTip("Sign in to Warframe.Market")
            button.setAccessibleName("Sign in to Warframe.Market")
            menu.addAction(svg_icons.icon("user", T.TEXT_SECONDARY), "Sign in to Warframe.Market",
                           self.market.show_sign_in)
            menu.addSeparator()
            menu.addAction(self.ingame_action)
        button.update()

    def _ingame_toggled(self, on: bool) -> None:
        settings.put(online_status.SETTING, on)
        log.info("in-game status on Warframe.Market %s", "on" if on else "off")
        if self.status_keeper is not None:
            self.status_keeper.tick()

    def account_changed(self) -> None:
        """Signed in or out somewhere: update the avatar and every other section."""
        origin = self.sender()
        self.refresh_account_button()
        for name in ("market", "rivens", "relics"):
            section = self.section(name)
            if section is not None and section is not origin:
                section.refresh_account()

    def _sign_out(self) -> None:
        self.account.sign_out()
        self.account_changed()

    # --- window ------------------------------------------------------------------------------------

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        section = self.stack.currentWidget()
        if isinstance(section, Section) and section.current_page():
            section.page_shown(section.current_page())  # pages wait until they are on screen to load

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if not self.isMaximized():  # remember the size it is put back to, not the maximized one
            self._save_size.start()

    def closeEvent(self, event) -> None:  # noqa: N802
        event.ignore()  # closing only hides it; VoidTrace keeps running in the tray
        self.hide()

    def shutdown(self) -> None:
        for name in ("market", "rivens", "relics"):
            section = self.section(name)
            if section is not None:
                section.shutdown()
