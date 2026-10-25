"""Shared look and building blocks for every VoidTrace page: the stylesheets, table and cell helpers,
the number box with -/+ buttons, the mouse-wheel guard, the colours used across pages, and `Section`,
the base of the Market, Rivens and Relics sections of the main window."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from PyQt6.QtCore import QEvent, QObject, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QAbstractSpinBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QSpinBox,
    QStackedWidget,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QWidget,
)

from .. import svg_icons
from .. import theme as T

log = logging.getLogger(__name__)

LINE_HOVER = "#3c4351"  # input and stepper borders lighten one step on hover
CHEVRON = svg_icons.file("chevron-down", T.TEXT_SECONDARY)
CHEVRON_UP = svg_icons.file("chevron-up", T.TEXT_PRIMARY)
CHEVRON_DOWN = svg_icons.file("chevron-down", T.TEXT_PRIMARY)
CHECK = svg_icons.file("check", T.DEFAULT_ON_ACCENT, 3.0)
svg_icons.file("check", "#ffffff", 3.0)  # theme.apply() switches to it for a dark custom accent
MENU_CHECK = svg_icons.file("check", T.TEXT_PRIMARY, 2.5)

STYLE = f"""
QWidget {{ background: {T.BG_PAGE}; color: {T.TEXT_PRIMARY}; font-family: {T.FONT_STACK}; font-size: 13px; }}
QToolTip {{ background: {T.BG_RAISED}; color: {T.TEXT_PRIMARY}; border: 1px solid {T.BORDER_STRONG};
    border-radius: 4px; padding: 4px 8px; }}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{ background: {T.BG_RAISED}; border: 1px solid {T.BORDER_STRONG};
    border-radius: 4px; padding: 0 8px; min-height: 30px; selection-background-color: {T.DEFAULT_ACCENT};
    selection-color: {T.DEFAULT_ON_ACCENT}; }}
QLineEdit:hover, QComboBox:hover, QSpinBox:hover {{ border-color: {LINE_HOVER}; }}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{ border-color: {T.DEFAULT_ACCENT}; }}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled {{ color: {T.TEXT_MUTED}; background: {T.BG_PANEL};
    border-color: {T.BORDER_SUBTLE}; }}
QLineEdit[error="true"] {{ border-color: {T.NEGATIVE}; }}
QComboBox {{ padding-right: 28px; }}
QComboBox::drop-down {{ border: none; width: 28px; }}
QComboBox::down-arrow {{ image: url({CHEVRON}); width: 16px; height: 16px; }}
QComboBox QAbstractItemView {{ background: {T.BG_PANEL}; border: 1px solid {T.BORDER_STRONG}; outline: none;
    padding: 4px; selection-background-color: {T.BG_HOVER}; selection-color: {T.TEXT_PRIMARY}; }}
QComboBox QAbstractItemView::item {{ min-height: 32px; padding: 0 8px; }}
QListWidget {{ background: {T.BG_PANEL}; border: 1px solid {T.BORDER_STRONG}; border-radius: 8px; padding: 4px;
    outline: none; }}
QListWidget::item {{ min-height: 32px; padding: 0 8px; border-radius: 4px; color: {T.TEXT_SECONDARY}; }}
QListWidget::item:hover:!selected {{ background: {T.BG_HOVER}; color: {T.TEXT_PRIMARY}; }}
QListWidget::item:selected {{ background: {T.DEFAULT_SOFT}; color: {T.TEXT_PRIMARY}; }}
QTableWidget {{ background: {T.BG_PAGE}; border: 1px solid {T.BORDER_SUBTLE}; border-radius: 8px;
    gridline-color: transparent; outline: none; selection-background-color: {T.DEFAULT_SOFT};
    selection-color: {T.TEXT_PRIMARY}; }}
QTableWidget::item {{ padding: 0 12px; border: none; border-bottom: 1px solid {T.BORDER_SUBTLE}; }}
QTableCornerButton::section {{ background: {T.BG_PANEL}; border: none; }}
QHeaderView {{ background: transparent; border: none; }}
QHeaderView::section {{ background: {T.BG_PANEL}; color: {T.TEXT_SECONDARY}; border: none;
    border-bottom: 1px solid {T.BORDER_SUBTLE}; padding: 0 12px; height: 32px; font-size: 11px; font-weight: 600; }}
QHeaderView::up-arrow {{ image: url({CHEVRON_UP}); width: 12px; height: 12px; subcontrol-position: center right; }}
QHeaderView::down-arrow {{ image: url({CHEVRON_DOWN}); width: 12px; height: 12px; subcontrol-position: center right; }}
QLabel {{ background: transparent; }}
QLabel#title {{ font-size: 20px; font-weight: 600; }}
QLabel#heading {{ font-size: 15px; font-weight: 600; }}
QLabel#caption {{ font-size: 11px; font-weight: 600; color: {T.TEXT_SECONDARY}; letter-spacing: 0.4px; }}
QLabel#toast {{ color: {T.TEXT_PRIMARY}; font-size: 12px; border: 1px solid transparent; padding: 4px 12px; }}
QLabel#toast[shown="true"] {{ background: {T.BG_RAISED}; border-color: {T.BORDER_STRONG}; border-radius: 4px; }}
QLabel#muted, QLabel#status {{ color: {T.TEXT_SECONDARY}; font-size: 12px; }}
QLabel#footnote {{ color: {T.TEXT_MUTED}; font-size: 12px; }}
QLabel#error {{ color: {T.NEGATIVE}; font-size: 12px; }}
QLabel#warning {{ color: {T.WARNING}; font-size: 12px; }}
QFrame#card {{ background: {T.BG_PANEL}; border: 1px solid {T.BORDER_SUBTLE}; border-radius: 8px; }}
QFrame#card QLabel, QFrame#card QCheckBox, QFrame#card QRadioButton {{ background: transparent; }}
QCheckBox, QRadioButton {{ spacing: 8px; background: transparent; }}
QCheckBox:disabled, QRadioButton:disabled {{ color: {T.TEXT_MUTED}; }}
QScrollArea {{ border: none; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px 2px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px 4px; }}
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{ background: {T.BORDER_STRONG}; border-radius: 3px;
    min-height: 30px; min-width: 30px; }}
QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {{ background: {LINE_HOVER}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}
QMenu {{ background: {T.BG_PANEL}; border: 1px solid {T.BORDER_STRONG}; border-radius: 8px; padding: 4px; }}
QMenu::item {{ padding: 0 24px 0 28px; min-height: 32px; border-radius: 4px; color: {T.TEXT_PRIMARY};
    background: transparent; }}
QMenu::item:selected {{ background: {T.BG_HOVER}; }}
QMenu::item:disabled {{ color: {T.TEXT_SECONDARY}; }}
QMenu::separator {{ height: 1px; background: {T.BORDER_SUBTLE}; margin: 4px 8px; }}
QMenu::indicator {{ width: 14px; height: 14px; left: 8px; }}
QMenu::indicator:checked {{ image: url({MENU_CHECK}); }}
"""

BUTTON_STYLE = f"""
QPushButton {{ background: {T.BG_RAISED}; color: {T.TEXT_PRIMARY}; border: 1px solid {T.BORDER_STRONG};
    border-radius: 4px; padding: 0 12px; min-height: 30px; }}
QPushButton:hover {{ background: {T.BG_HOVER}; }}
QPushButton:pressed {{ background: {T.BG_PANEL}; }}
QPushButton:focus {{ border-color: {T.DEFAULT_ACCENT}; }}
QPushButton:disabled {{ color: {T.TEXT_MUTED}; background: {T.BG_PANEL}; border-color: {T.BORDER_SUBTLE}; }}
QPushButton#primary {{ background: {T.DEFAULT_ACCENT}; color: {T.DEFAULT_ON_ACCENT}; border: none; font-weight: 600;
    min-height: 32px; }}
QPushButton#primary:hover {{ background: {T.DEFAULT_HOVER}; }}
QPushButton#primary:pressed {{ background: {T.DEFAULT_PRESSED}; }}
QPushButton#primary:focus {{ border: 2px solid {T.TEXT_PRIMARY}; }}
QPushButton#primary:disabled {{ background: {T.BG_RAISED}; color: {T.TEXT_MUTED}; }}
QPushButton#ghost, QPushButton#danger {{ background: transparent; border: 1px solid transparent;
    color: {T.TEXT_SECONDARY}; padding: 0 8px; }}
QPushButton#ghost:hover {{ background: {T.BG_HOVER}; color: {T.TEXT_PRIMARY}; }}
QPushButton#danger:hover {{ background: {T.BG_HOVER}; color: {T.NEGATIVE}; }}
QPushButton#ghost:pressed, QPushButton#danger:pressed {{ background: {T.BG_RAISED}; }}
QPushButton#ghost:focus, QPushButton#danger:focus {{ border-color: {T.DEFAULT_ACCENT}; }}
QPushButton#ghost:disabled, QPushButton#danger:disabled {{ background: transparent; border-color: transparent; }}
QToolButton#eye, QToolButton#icon {{ background: transparent; border: 1px solid transparent; border-radius: 4px;
    min-width: 30px; min-height: 30px; }}
QToolButton#eye:hover, QToolButton#icon:hover {{ background: {T.BG_HOVER}; }}
QToolButton#eye:focus, QToolButton#icon:focus {{ border-color: {T.DEFAULT_ACCENT}; }}
QFrame#stepper {{ background: {T.BG_RAISED}; border: 1px solid {T.BORDER_STRONG}; border-radius: 4px; }}
QFrame#stepper:hover {{ border-color: {LINE_HOVER}; }}
QFrame#stepper[focused="true"] {{ border-color: {T.DEFAULT_ACCENT}; }}
QFrame#stepper:disabled {{ background: {T.BG_PANEL}; border-color: {T.BORDER_SUBTLE}; }}
QFrame#stepper QSpinBox {{ background: transparent; border: none; padding: 0 2px; min-height: 30px; }}
QFrame#stepper QSpinBox:disabled {{ color: {T.TEXT_MUTED}; }}
QToolButton#step {{ background: transparent; border: none; color: {T.TEXT_SECONDARY}; min-width: 28px;
    max-width: 28px; min-height: 30px; font-size: 15px; }}
QToolButton#step:hover {{ background: {T.BG_HOVER}; color: {T.TEXT_PRIMARY}; }}
QToolButton#step:pressed {{ background: {T.BG_PANEL}; }}
QToolButton#step:disabled {{ color: {T.TEXT_MUTED}; background: transparent; }}
QFrame#stepdiv {{ background: {T.BORDER_SUBTLE}; border: none; }}
QCheckBox::indicator, QRadioButton::indicator {{ width: 12px; height: 12px; border: 2px solid {T.BORDER_STRONG};
    background: {T.BG_RAISED}; }}
QCheckBox::indicator {{ border-radius: 4px; }}
QRadioButton::indicator {{ border-radius: 8px; }}
QCheckBox::indicator:hover, QRadioButton::indicator:hover {{ border-color: {LINE_HOVER}; }}
QCheckBox:focus, QRadioButton:focus {{ color: {T.TEXT_PRIMARY}; }}
QCheckBox::indicator:focus, QRadioButton::indicator:focus {{ border-color: {T.DEFAULT_ACCENT}; }}
QCheckBox::indicator:checked {{ background: {T.DEFAULT_ACCENT}; border-color: {T.DEFAULT_ACCENT}; image: url({CHECK}); }}
QRadioButton::indicator:checked {{ border: 2px solid {T.DEFAULT_ACCENT};
    background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5,
                                stop:0 {T.DEFAULT_ACCENT}, stop:0.45 {T.DEFAULT_ACCENT}, stop:0.55 {T.BG_RAISED},
                                stop:1 {T.BG_RAISED}); }}
QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {{ background: {T.BG_PANEL};
    border-color: {T.BORDER_SUBTLE}; }}
QFrame#segmented {{ background: {T.BG_RAISED}; border: 1px solid {T.BORDER_STRONG}; border-radius: 4px; }}
QFrame#segmented:disabled {{ background: {T.BG_PANEL}; border-color: {T.BORDER_SUBTLE}; }}
QPushButton#segment {{ background: transparent; border: 1px solid transparent; border-radius: 3px;
    color: {T.TEXT_SECONDARY}; min-height: 28px; padding: 0 12px; }}
QPushButton#segment:hover {{ color: {T.TEXT_PRIMARY}; }}
QPushButton#segment:checked {{ background: {T.BG_HOVER}; color: {T.TEXT_PRIMARY}; }}
QPushButton#segment:focus {{ border-color: {T.DEFAULT_ACCENT}; }}
QPushButton#segment:disabled {{ color: {T.TEXT_MUTED}; background: transparent; }}
"""

MUTED = QColor(T.TEXT_SECONDARY)
GREEN = QColor(T.POSITIVE)
RED = QColor(T.NEGATIVE)
BUFF_COLOR = QColor(T.POSITIVE)
CURSE_COLOR = QColor(T.NEGATIVE)
STATUS_LABEL = {"ingame": "In game", "online": "Online", "offline": "Offline"}
STATUS_COLOR = {"ingame": QColor(T.POSITIVE), "online": QColor(T.STATUS_ONLINE), "offline": QColor(T.TEXT_MUTED)}


class WheelGuard(QObject):
    """Dropdowns and number boxes ignore the mouse wheel until clicked.

    Qt changes a hovered dropdown on every wheel notch, so scrolling the window over the price
    check silently turned Puncture into the next stat in the list, Radiation.
    """

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 (Qt naming)
        if event.type() == QEvent.Type.Wheel and not obj.hasFocus():
            event.ignore()  # lets the window scroll instead
            return True
        return False


def guard_wheel(root: QWidget) -> WheelGuard:
    guard = WheelGuard(root)
    for widget in root.findChildren((QComboBox, QAbstractSpinBox)):
        widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        widget.installEventFilter(guard)
    return guard


class Stepper(QFrame):
    """A number box with its own - and + buttons, all inside one bordered box.

    The dark theme's QSpinBox styling made Qt misplace the built-in arrows' click areas: the up
    arrow drew in one place and listened in another, so it never responded. Typing, the arrow keys
    and the mouse wheel still work on the box itself. Mirrors QSpinBox's value()/setValue()/valueChanged.
    """

    def __init__(self, minimum: int, maximum: int, value: int, step: int = 1) -> None:
        super().__init__(objectName="stepper")
        self.box = QSpinBox(minimum=minimum, maximum=maximum, value=value, singleStep=step)
        self.box.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.box.setMinimumWidth(40)
        self.minus = QToolButton(text="−", objectName="step")
        self.plus = QToolButton(text="+", objectName="step")
        self.minus.setAccessibleName("Decrease")
        self.plus.setAccessibleName("Increase")
        for button, delta in ((self.minus, -step), (self.plus, step)):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # the box takes the arrow keys
            button.setAutoRepeat(True)  # hold to keep stepping
            button.clicked.connect(lambda _=False, d=delta: self.box.setValue(self.box.value() + d))
        layout = QHBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)
        layout.addWidget(self.minus)
        layout.addWidget(self._divider())
        layout.addWidget(self.box, 1)
        layout.addWidget(self._divider())
        layout.addWidget(self.plus)
        self.setFixedHeight(T.CONTROL_HEIGHT)
        self.setMinimumWidth(104)
        self.setMaximumWidth(136)
        self.valueChanged = self.box.valueChanged
        self.box.valueChanged.connect(self._limits)
        self.box.installEventFilter(self)
        self._limits()

    @staticmethod
    def _divider() -> QFrame:
        line = QFrame(objectName="stepdiv")
        line.setFixedWidth(1)
        return line

    def _limits(self, *_args) -> None:
        self.minus.setEnabled(self.box.value() > self.box.minimum())
        self.plus.setEnabled(self.box.value() < self.box.maximum())

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 (Qt naming)
        if event.type() in (QEvent.Type.FocusIn, QEvent.Type.FocusOut):
            self.setProperty("focused", event.type() == QEvent.Type.FocusIn)
            self.style().unpolish(self)
            self.style().polish(self)
        return False

    def setRange(self, minimum: int, maximum: int) -> None:  # noqa: N802 (Qt naming)
        self.box.setRange(minimum, maximum)
        self._limits()

    def value(self) -> int:
        return self.box.value()

    def setValue(self, value: int) -> None:  # noqa: N802 (Qt naming)
        self.box.setValue(value)


class RowHover(QStyledItemDelegate):
    """Lights the whole row under the mouse; a stylesheet can only light one cell."""

    def __init__(self, table: QTableWidget) -> None:
        super().__init__(table)
        self.row = -1
        self.fill = QColor(T.BG_HOVER)
        table.setMouseTracking(True)
        table.entered.connect(lambda index: self._set(index.row()))
        table.viewport().installEventFilter(self)

    def _set(self, row: int) -> None:
        if row != self.row:
            self.row = row
            self.parent().viewport().update()

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 (Qt naming)
        if event.type() == QEvent.Type.Leave:
            self._set(-1)
        return False

    def paint(self, painter, option, index) -> None:
        if index.row() == self.row:
            painter.fillRect(option.rect, self.fill)
        super().paint(painter, option, index)


def make_table(columns: list[str]) -> QTableWidget:
    t = QTableWidget(0, len(columns))
    t.setHorizontalHeaderLabels(columns)
    t.verticalHeader().hide()
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
    t.setShowGrid(False)
    t.setIconSize(QSize(14, 14))
    t.setItemDelegate(RowHover(t))
    t.verticalHeader().setDefaultSectionSize(T.ROW_HEIGHT)
    header = t.horizontalHeader()
    header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    header.setHighlightSections(False)
    header.setFixedHeight(32)
    header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
    for c in range(1, len(columns)):
        header.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
    font = header.font()  # captions are uppercase; stylesheets can't transform text, fonts can
    font.setCapitalization(QFont.Capitalization.AllUppercase)
    font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.4)
    header.setFont(font)
    return t


def set_rows(table: QTableWidget, count: int) -> None:
    """Size `table` for a refill. Emptying it first matters: refilling rows that still hold text made
    the fit-to-contents columns re-measure every row for each new cell (752 relics froze the window)."""
    table.setRowCount(0)
    table.setRowCount(count)


def make_cell(text: str, right: bool = False, icon=None, color: Optional[QColor] = None) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    if right:
        item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    if icon is not None:
        item.setIcon(QIcon(icon))
    if color is not None:
        item.setForeground(color)
    return item


class Section(QWidget):
    """One part of the main window (Market, Rivens or Relics): a stack of pages, one shown at a time.

    Subclasses fill `PAGES` (page key -> sidebar label, in order), call `add_page` for each, and
    override `page_shown` (refresh a page when it appears) and `refresh_account` (after sign in/out).
    Panels call `run_async` for network work, `show_toast` for a short message, `show_sign_in`, and
    `account_changed` after signing in or out, which also tells the main window (`account_switched`).
    """

    PAGES: dict[str, str] = {}
    _async_done = pyqtSignal(object, object)  # (callback, result), run on the UI thread
    account_switched = pyqtSignal()
    page_changed = pyqtSignal(str)  # a page key, when the section switches page itself

    def __init__(self) -> None:
        super().__init__()
        self.pages = QStackedWidget()
        self._page_by_key: dict[str, QWidget] = {}
        self.toast = QLabel(objectName="toast")
        self._toast_timer = QTimer(self, singleShot=True, interval=4000)
        self._toast_timer.timeout.connect(lambda: self.show_toast(""))
        self._executor = ThreadPoolExecutor(max_workers=2)
        self._async_done.connect(lambda callback, result: callback(result))

    def add_page(self, key: str, widget: QWidget) -> None:
        if widget.layout() is not None:  # pages line up with the section's own controls
            widget.layout().setContentsMargins(0, 14, 0, 0)
        self._page_by_key[key] = widget
        self.pages.addWidget(widget)

    def page(self, key: str) -> QWidget:
        return self._page_by_key[key]

    def show_page(self, key: str) -> None:
        self.pages.setCurrentWidget(self._page_by_key[key])
        self.page_shown(key)
        self.page_changed.emit(key)

    def current_page(self) -> str:
        current = self.pages.currentWidget()
        return next((k for k, w in self._page_by_key.items() if w is current), "")

    def page_shown(self, key: str) -> None:
        """A page came into view (override to refresh it)."""

    def refresh_account(self) -> None:
        """Signed in or out (override to update the pages)."""

    def account_changed(self) -> None:
        self.refresh_account()
        self.account_switched.emit()

    def show_sign_in(self) -> None:
        from .orders import SignInDialog

        SignInDialog(self).exec()

    def show_toast(self, text: str) -> None:
        self.toast.setText(text)
        self.toast.setProperty("shown", bool(text))  # the pill only draws around a message
        self.toast.style().unpolish(self.toast)
        self.toast.style().polish(self.toast)
        if text:
            self._toast_timer.start()

    def run_async(self, fn, on_ok, on_err=None) -> None:
        """Run `fn` off the UI thread; call on_ok(result) or on_err(exception) back on the UI thread."""
        def work():
            try:
                self._async_done.emit(on_ok, fn())
            except Exception as exc:  # reported to the page that asked, never crashes the UI
                log.warning("%s request failed: %s", type(self).__name__, exc)
                if on_err is not None:
                    self._async_done.emit(on_err, exc)

        self._executor.submit(work)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)
