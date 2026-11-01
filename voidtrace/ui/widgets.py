"""Shared look and building blocks for every VoidTrace page: the stylesheets, table and cell helpers,
the number box with -/+ buttons, the mouse-wheel guard, the colours used across pages, and `Section`,
the base of the Market, Rivens and Relics sections of the main window."""

from __future__ import annotations

import logging
import math
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional

from PyQt6 import sip
from PyQt6.QtCore import QEvent, QObject, QRectF, QSize, Qt, QTimer, QVariantAnimation, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QAbstractSpinBox,
    QButtonGroup,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
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
QLabel#pricetag {{ font-weight: 600; }}
QLabel#stat {{ font-size: 24px; font-weight: 600; }}
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

    def eventFilter(self, obj, event) -> bool:
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

    def eventFilter(self, obj, event) -> bool:
        if event.type() in (QEvent.Type.FocusIn, QEvent.Type.FocusOut):
            self.setProperty("focused", event.type() == QEvent.Type.FocusIn)
            self.style().unpolish(self)
            self.style().polish(self)
        return False

    def value(self) -> int:
        return self.box.value()

    def setValue(self, value: int) -> None:
        self.box.setValue(value)


def animations_enabled() -> bool:
    """Windows' "Show animations" setting (SPI_GETCLIENTAREAANIMATION); on elsewhere."""
    try:
        import ctypes

        on = ctypes.c_int(1)
        ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(on), 0)
        return bool(on.value)
    except (AttributeError, OSError):
        return True


class Pulse(QObject):
    """The one animation every skeleton follows: 1.2 s between BG_RAISED and BG_HOVER, in sync.

    It runs only while something keeps drawing skeletons (`color()` marks it used), and stops by
    itself a few frames after the last one is gone. Static when Windows animations are off.
    """

    tick = pyqtSignal()
    _shared: Optional["Pulse"] = None

    def __init__(self) -> None:
        super().__init__()
        self.anim = QVariantAnimation(self, startValue=0.0, endValue=1.0, duration=1200, loopCount=-1)
        self.anim.valueChanged.connect(self._tick)
        self.used = False
        self.idle = 0
        self.raised, self.hover = QColor(T.BG_RAISED), QColor(T.BG_HOVER)

    @classmethod
    def shared(cls) -> "Pulse":
        if cls._shared is None or sip.isdeleted(cls._shared):  # a new QApplication (tests) starts afresh
            cls._shared = cls()
        return cls._shared

    def color(self) -> QColor:
        self.used = True
        if self.anim.state() != QVariantAnimation.State.Running:
            if not animations_enabled():
                return self.raised
            self.idle = 0
            self.anim.start()
        t = self.anim.currentValue() or 0.0
        return T.mix(self.hover, self.raised, 0.5 - 0.5 * math.cos(2 * math.pi * t))  # sine in-out

    def _tick(self, _value) -> None:
        self.idle = 0 if self.used else self.idle + 1
        self.used = False
        if self.idle > 3:
            self.anim.stop()
        self.tick.emit()


class Skeleton(QWidget):
    """A pulsing placeholder bar in the shape of the content it stands in for."""

    def __init__(self, width: int = 80, height: int = 10, radius: int = T.RADIUS_SM) -> None:
        super().__init__()
        self.radius = radius
        self.setFixedHeight(height)
        self.setMinimumWidth(width)
        self.setMaximumWidth(width)
        Pulse.shared().tick.connect(self.update)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(Pulse.shared().color())
        p.drawRoundedRect(QRectF(self.rect()), self.radius, self.radius)


SKELETON = Qt.ItemDataRole.UserRole + 50  # a cell whose value is still loading: drawn as a pulsing bar


def skeleton_cell(width: int = 36) -> QTableWidgetItem:
    item = QTableWidgetItem("")
    item.setData(SKELETON, width)
    return item


class RowHover(QStyledItemDelegate):
    """Lights the whole row under the mouse (a stylesheet can only light one cell), and draws
    skeleton cells."""

    def __init__(self, table: QTableWidget) -> None:
        super().__init__(table)
        self.row = -1
        self.fill = QColor(T.BG_HOVER)
        self.pulsing = False
        table.setMouseTracking(True)
        table.entered.connect(lambda index: self._set(index.row()))
        table.viewport().installEventFilter(self)
        Pulse.shared().tick.connect(self._pulse)

    def _set(self, row: int) -> None:
        if row != self.row:
            self.row = row
            self.parent().viewport().update()

    def _pulse(self) -> None:
        if self.pulsing:  # only while the last paint drew a skeleton cell
            self.pulsing = False
            self.parent().viewport().update()

    def eventFilter(self, obj, event) -> bool:
        if event.type() == QEvent.Type.Leave:
            self._set(-1)
        return False

    def paint(self, painter, option, index) -> None:
        if index.row() == self.row:
            painter.fillRect(option.rect, self.fill)
        width = index.data(SKELETON)
        if width:
            self.pulsing = True
            r = option.rect
            w = min(int(width), r.width() - 24)
            right = index.data(Qt.ItemDataRole.TextAlignmentRole)
            x = r.right() - 12 - w if right and int(right) & int(Qt.AlignmentFlag.AlignRight) else r.left() + 12
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(Pulse.shared().color())
            painter.drawRoundedRect(QRectF(x, r.center().y() - 4, w, 10), T.RADIUS_SM, T.RADIUS_SM)
            painter.restore()
            painter.setPen(QColor(T.BORDER_SUBTLE))
            painter.drawLine(r.bottomLeft(), r.bottomRight())
            return
        super().paint(painter, option, index)


class TableState(QWidget):
    """What a table shows instead of rows: loading skeleton rows, or one centred message (empty,
    nothing asked yet, error) with an optional button. The header stays real."""

    def __init__(self, table: QTableWidget) -> None:
        super().__init__(table.viewport())
        self.table = table
        self.mode = ""
        self.rows = 8
        self.icon = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.text = QLabel(objectName="muted", alignment=Qt.AlignmentFlag.AlignCenter)
        self.text.setStyleSheet(f"font-size: 13px; color: {T.TEXT_SECONDARY};")
        self.button = QPushButton()
        self.button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.button.hide()
        self._on_click: Optional[Callable[[], None]] = None
        self.button.clicked.connect(lambda: self._on_click() if self._on_click else None)
        box = QVBoxLayout(self)
        box.addStretch(1)
        line = QHBoxLayout()
        line.addStretch(1)
        line.addWidget(self.icon)
        line.addWidget(self.text)
        line.addStretch(1)
        line.setSpacing(T.SPACE_2)
        box.addLayout(line)
        box.addSpacing(T.SPACE_3)
        box.addWidget(self.button, 0, Qt.AlignmentFlag.AlignHCenter)
        box.addStretch(1)
        table.viewport().installEventFilter(self)
        Pulse.shared().tick.connect(lambda: self.update() if self.mode == "loading" and self.isVisible() else None)
        self.hide()

    def eventFilter(self, obj, event) -> bool:
        if event.type() == QEvent.Type.Resize:
            self.setGeometry(self.parent().rect())
        return False

    def loading(self, rows: int = 8) -> None:
        self.mode, self.rows = "loading", rows
        set_rows(self.table, 0)
        for w in (self.icon, self.text, self.button):
            w.hide()
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._show()

    def message(self, text: str, icon: str = "info", tone: str = T.TEXT_SECONDARY,
                button: str = "", on_click: Optional[Callable[[], None]] = None, primary: bool = False) -> None:
        """Empty or error: icon + one line, and a button for the next step."""
        self.mode = "message"
        self.icon.setPixmap(svg_icons.pixmap(icon, tone, 16))
        self.text.setText(text)
        self.icon.show()
        self.text.show()
        self.button.setText(button)
        self.button.setObjectName("primary" if primary else "")
        self.button.style().unpolish(self.button)
        self.button.style().polish(self.button)
        self.button.setVisible(bool(button))
        self._on_click = on_click
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self._show()

    def error(self, text: str = "Couldn't reach Warframe.Market.", retry: Optional[Callable[[], None]] = None) -> None:
        if self.table.rowCount():  # rows already shown stay; the page's status line says what failed
            self.clear()
            return
        self.message(text, "alert", T.NEGATIVE, "Retry" if retry else "", retry)

    def clear(self) -> None:
        self.mode = ""
        self.hide()

    def _show(self) -> None:
        self.setGeometry(self.parent().rect())
        self.show()
        self.raise_()
        self.update()

    def paintEvent(self, event) -> None:
        if self.mode != "loading":
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = Pulse.shared().color()
        line = QColor(T.BORDER_SUBTLE)
        header = self.table.horizontalHeader()
        for row in range(self.rows):
            top = row * T.ROW_HEIGHT
            for col in range(self.table.columnCount()):
                if self.table.isColumnHidden(col) or header.sectionSize(col) < 28:
                    continue
                width = header.sectionSize(col) - 24
                share = 0.6 + 0.2 * (((row * 7 + col * 3) % 5) / 4)  # 60 to 80%, varied per row
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(color)
                p.drawRoundedRect(QRectF(header.sectionViewportPosition(col) + 12, top + 13,
                                         max(12, width * share), 10), T.RADIUS_SM, T.RADIUS_SM)
            p.setPen(line)
            p.drawLine(0, top + T.ROW_HEIGHT - 1, self.width(), top + T.ROW_HEIGHT - 1)


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
    t.state = TableState(t)
    return t


def set_rows(table: QTableWidget, count: int) -> None:
    """Size `table` for a refill. Emptying it first matters: refilling rows that still hold text made
    the fit-to-contents columns re-measure every row for each new cell (752 relics froze the window)."""
    table.setRowCount(0)
    table.setRowCount(count)
    state = getattr(table, "state", None)
    if count and state is not None and state.mode:
        state.clear()  # rows arrived: they replace the skeleton or message in place


def make_cell(text: str, right: bool = False, icon=None, color: Optional[QColor] = None) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    if right:
        item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    if icon is not None:
        item.setIcon(QIcon(icon))
    if color is not None:
        item.setForeground(color)
    return item


def icon_button(name: str, tip: str, hover: str = T.TEXT_PRIMARY) -> QToolButton:
    """A 32px icon-only ghost button; the icon lightens (or turns `hover`) under the mouse."""
    button = QToolButton(objectName="icon")
    icon = QIcon(svg_icons.pixmap(name, T.TEXT_SECONDARY, 16))
    icon.addPixmap(svg_icons.pixmap(name, hover, 16), QIcon.Mode.Active)
    button.setIcon(icon)
    button.setIconSize(QSize(16, 16))
    button.setAutoRaise(True)
    button.setToolTip(tip)
    button.setAccessibleName(tip)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button


def refresh_button() -> QPushButton:
    button = QPushButton(svg_icons.icon("refresh", T.TEXT_SECONDARY), " Refresh")
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button


def show_sort(table: QTableWidget, column: int, descending: bool) -> None:
    """Mark the sorted column: a chevron in the header and its label in TEXT_PRIMARY. The pages
    sort the rows themselves."""
    header = table.horizontalHeader()
    header.setSortIndicatorShown(True)
    header.setSortIndicator(column, Qt.SortOrder.DescendingOrder if descending else Qt.SortOrder.AscendingOrder)
    for col in range(table.columnCount()):
        item = table.horizontalHeaderItem(col)
        if item is not None:
            item.setForeground(QColor(T.TEXT_PRIMARY if col == column else T.TEXT_SECONDARY))
            item.setToolTip("Click to sort")


def search_field(example: str) -> QLineEdit:
    """A search box: leading search icon, a clear (x) button once there's text, up to 640px wide."""
    field = QLineEdit(placeholderText=example)
    field.addAction(svg_icons.icon("search", T.TEXT_SECONDARY), QLineEdit.ActionPosition.LeadingPosition)
    clear = field.addAction(svg_icons.icon("x", T.TEXT_SECONDARY), QLineEdit.ActionPosition.TrailingPosition)
    clear.setToolTip("Clear")
    clear.setVisible(False)
    clear.triggered.connect(lambda: (field.clear(), field.textEdited.emit(""), field.setFocus()))
    field.textChanged.connect(lambda text: clear.setVisible(bool(text)))
    field.setMaximumWidth(T.SEARCH_MAX_WIDTH)
    return field


def header_bar(*widgets: QWidget) -> QWidget:
    """A page's filters and actions for the header line, 8px apart."""
    bar = QWidget()
    layout = QHBoxLayout(bar)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(T.SPACE_2)
    for widget in widgets:
        layout.addWidget(widget)
    return bar


def form_rows(rows: list[tuple[str, object]]) -> QGridLayout:
    """Field rows: labels right-aligned in their own column, 8px to the field, rows 8px apart.
    A row's field may be a widget or a layout."""
    grid = QGridLayout()
    grid.setHorizontalSpacing(T.SPACE_2)
    grid.setVerticalSpacing(T.SPACE_2)
    for r, (label, field) in enumerate(rows):
        if label:
            grid.addWidget(QLabel(label, objectName="muted"), r, 0,
                           Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if isinstance(field, QWidget):
            grid.addWidget(field, r, 1, Qt.AlignmentFlag.AlignLeft)
        else:
            grid.addLayout(field, r, 1)
    grid.setColumnStretch(2, 1)
    return grid


class StatTile(QFrame):
    """A stat tile: caption, a big value, and a detail line."""

    def __init__(self, caption: str) -> None:
        super().__init__(objectName="card")
        self.value = QLabel(objectName="stat")
        self.detail = QLabel(objectName="status")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(T.SPACE_4, T.SPACE_4, T.SPACE_4, T.SPACE_4)
        layout.setSpacing(T.SPACE_1)
        title = QLabel(caption.upper(), objectName="caption")
        layout.addWidget(title)
        layout.addWidget(self.value)
        layout.addWidget(self.detail)

    def set(self, value: str, detail: str, color: str = T.TEXT_PRIMARY) -> None:
        self.value.setText(value)
        self.value.setStyleSheet(f"color: {color};")
        self.detail.setText(detail)


def card(heading: str = "") -> tuple[QFrame, QVBoxLayout]:
    """A panel card (16px padding), with an optional heading 12px above its content."""
    frame = QFrame(objectName="card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(T.SPACE_4, T.SPACE_4, T.SPACE_4, T.SPACE_4)
    layout.setSpacing(T.SPACE_2)
    if heading:
        frame.heading = QLabel(heading, objectName="heading")
        layout.addWidget(frame.heading)
        layout.addSpacing(T.SPACE_1)
    return frame, layout


class Notice(QFrame):
    """An inline notice: a strip with a 2px bar in the tone colour, an icon and one sentence."""

    TONES = {"info": (T.DEFAULT_ACCENT, "info"), "warning": (T.WARNING, "alert"), "error": (T.NEGATIVE, "alert")}

    def __init__(self, tone: str = "info") -> None:
        super().__init__(objectName="notice")
        self.tone = ""
        self.default_tone = tone
        self.icon = QLabel()
        self.label = QLabel(wordWrap=True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(T.SPACE_3, T.SPACE_2, T.SPACE_3, T.SPACE_2)
        layout.setSpacing(T.SPACE_2)
        layout.addWidget(self.icon, 0, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.label, 1)
        self.hide()

    def text(self) -> str:
        return self.label.text() if self.tone else ""

    def setText(self, text: str) -> None:
        self.show_text(text, self.default_tone)

    def show_text(self, text: str, tone: str = "info") -> None:
        self.tone = tone if text else ""
        if not text:
            self.hide()
            return
        color, icon = self.TONES[tone]
        self.setStyleSheet(f"QFrame#notice {{ background: {T.BG_RAISED}; border: none; border-left: 2px solid {color};"
                           f" border-radius: 4px; }} QFrame#notice QLabel {{ background: transparent; }}")
        self.icon.setPixmap(svg_icons.pixmap(icon, T.accent_hex() if tone == "info" else color, 16))
        self.label.setText(text)
        self.show()


class Segmented(QFrame):
    """A segmented control: 2 to 4 always-visible exclusive options. Reads like a QComboBox
    (currentIndex, currentData, currentIndexChanged); `buttons` are the segments."""

    currentIndexChanged = pyqtSignal(int)

    def __init__(self, options: list[tuple[str, object]]) -> None:
        super().__init__(objectName="segmented")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)
        self.group = QButtonGroup(self)
        self.buttons: list[QPushButton] = []
        self.values = [value for _label, value in options]
        for i, (label, _value) in enumerate(options):
            button = QPushButton(label, objectName="segment", checkable=True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.group.addButton(button, i)
            self.buttons.append(button)
            layout.addWidget(button)
        self.buttons[0].setChecked(True)
        self.group.idToggled.connect(lambda i, on: self.currentIndexChanged.emit(i) if on else None)
        self.setFixedHeight(T.CONTROL_HEIGHT)

    def currentIndex(self) -> int:
        return self.group.checkedId()

    def setCurrentIndex(self, index: int) -> None:
        self.buttons[index].setChecked(True)

    def currentData(self):
        return self.values[self.currentIndex()]


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
            widget.layout().setContentsMargins(0, T.SPACE_4, 0, 0)
        for part in (getattr(widget, "header_actions", None), getattr(widget, "status_line", None)):
            if part is not None and part.parent() is None:
                part.setParent(widget)  # a child until the window docks it, so guard_wheel finds it
                part.hide()
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
