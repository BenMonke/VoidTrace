"""The riven popup: a compact panel at the right edge of the screen, shown while a riven card is open
in Item Details or on the Cycle screen.

It shows the riven, each stat with how well it rolled, and the price estimate. Clicking it opens the
Rivens > Price check on that riven. It never takes keyboard focus from the game.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Callable, Optional

from PyQt6.QtCore import QObject, QRect, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from . import theme
from .cv_cleaner import keep_capture
from .icons import draw_amount, platinum_icon
from .ui.widgets import Pulse, Skeleton
from .rivens import (
    PriceCheck,
    RivenCatalog,
    RivenDraft,
    attr_rolls,
    grade,
    grade_from_percent,
    grade_letter,
    grading_weapon,
    price_check,
    riven_grade,
)

if TYPE_CHECKING:
    from .rivens import RivenService

log = logging.getLogger(__name__)

WIDTH = 330
PANEL = QColor(theme.BG_PANEL)
PANEL.setAlphaF(0.94)
BORDER = QColor(theme.BORDER_STRONG)
TEXT = QColor(theme.TEXT_PRIMARY)
MUTED = QColor(theme.TEXT_SECONDARY)
FAINT = QColor(theme.TEXT_MUTED)
BUFF = QColor(theme.POSITIVE)
CURSE = QColor(theme.NEGATIVE)
AMBER = QColor(theme.WARNING)


def grade_color(value: int) -> QColor:
    """Red (0) through amber to green (100)."""
    from .ui.riven_find import grade_color as color

    return color(value)


class GradeBar(QWidget):
    """A thin bar filled to the stat's grade (0-100% of its range), with its letter beside it."""

    def __init__(self, value: Optional[int], letter: Optional[str] = None) -> None:
        super().__init__()
        self.value = value
        self.letter = letter
        self.setFixedSize(84, 16)
        if value is not None:
            self.setToolTip(f"{value}% of the way from the worst possible roll to the best")

    def paintEvent(self, _event) -> None:
        if self.value is None:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = grade_color(self.value)
        p.setPen(color)
        p.setFont(_font(12, True))
        p.drawText(QRect(0, 0, 22, 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   self.letter or f"{self.value}%")
        bar = QRectF(28, 6, 56, 4)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(theme.BG_RAISED))
        p.drawRoundedRect(bar, 2, 2)
        p.setBrush(color)
        p.drawRoundedRect(QRectF(bar.x(), bar.y(), max(4.0, bar.width() * self.value / 100), bar.height()), 2, 2)
        p.end()


def _font(px: int, bold: bool = False) -> QFont:
    font = QFont(theme.FONT_FAMILY)
    font.setPixelSize(px)
    font.setWeight(QFont.Weight.DemiBold if bold else QFont.Weight.Normal)
    return font


class PriceLine(QWidget):
    """The estimate with the platinum icon, in the accent: a pulsing bar while it loads."""

    def __init__(self) -> None:
        super().__init__()
        self.text = ""
        self.loading = False
        self.setFixedHeight(36)
        Pulse.shared().tick.connect(lambda: self.update() if self.loading else None)

    def set_text(self, text: str) -> None:
        self.text, self.loading = text, False
        self.update()

    def set_loading(self) -> None:
        self.text, self.loading = "", True
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.loading:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(Pulse.shared().color())
            p.drawRoundedRect(QRectF(0, 9, 96, 18), theme.RADIUS_SM, theme.RADIUS_SM)
        elif self.text:
            draw_amount(p, self.rect(), platinum_icon(22, self.devicePixelRatioF()), self.text, _font(28, True),
                        theme.accent(), Qt.AlignmentFlag.AlignLeft)
        p.end()


class RivenPopup(QWidget):
    clicked = pyqtSignal()

    def __init__(self, screen_geometry: QRect) -> None:
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                            | Qt.WindowType.Tool | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedWidth(WIDTH)
        self.screen_geometry = screen_geometry
        self.draft: Optional[RivenDraft] = None
        self.check: Optional[PriceCheck] = None
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(16, 16, 16, 16)
        self.body.setSpacing(6)
        self.price = PriceLine()
        self.price_detail = self._label("", MUTED, 12)
        self.price_detail.setWordWrap(True)
        self.detail_skeleton = Skeleton(160, 10)

    # --- content ------------------------------------------------------------------------

    def _label(self, text: str, color: QColor, size: int = 12, bold: bool = False) -> QLabel:
        """`size` in pixels."""
        label = QLabel(text)
        label.setStyleSheet(f"color: {color.name()}; background: transparent;")
        label.setFont(_font(size, bold))
        return label

    def _clear(self) -> None:
        # Detach at once: deleteLater alone left the previous riven's rows drawn under the new ones.
        while self.body.count():
            item = self.body.takeAt(0)
            if item.widget() is not None and item.widget() not in (self.price, self.price_detail,
                                                                   self.detail_skeleton):
                _drop(item.widget())
            elif item.layout() is not None:
                _delete_layout(item.layout())

    def show_reading(self) -> None:
        self.draft, self.check = None, None
        self._clear()
        self.body.addLayout(self._header("Reading riven…", "", None))
        self._place()

    def show_read(self, catalog: RivenCatalog, draft: RivenDraft, warnings: list[str]) -> None:
        """Fill in the riven; the price follows with show_price()."""
        self.draft, self.check = draft, None
        self._clear()
        weapon = grading_weapon(catalog, draft)
        title = f"{weapon.name if weapon else draft.weapon} {draft.name[:1].upper()}{draft.name[1:]}".strip()
        meta = f"MR {draft.mr} · {draft.rolls} rolls"
        if weapon is not None:
            from .ui.riven_find import disposition_dots

            meta = f"{disposition_dots(weapon.disposition)}  {meta}"
        if draft.shown_for and weapon is not None and draft.shown_for.lower() != weapon.name.lower():
            meta += f"\nValues as shown for {draft.shown_for} (riven strength {draft.shown_disposition:g})"
        overall = riven_grade(catalog, weapon, draft.attrs, draft.rank) if weapon else None
        self.body.addLayout(self._header(title or "Riven", meta, overall))
        # Price first: what the player came for.
        self.price.set_loading()
        self.price_detail.setText("Checking listings…")
        self.price_detail.hide()
        self.detail_skeleton.show()
        self.body.addWidget(self.price)
        self.body.addWidget(self.price_detail)
        self.body.addWidget(self.detail_skeleton)
        self.body.addSpacing(6)
        self.body.addWidget(self._divider())
        rolls = attr_rolls(catalog, weapon, draft.attrs, draft.rank) if weapon else [None] * len(draft.attrs)
        for attr, roll in zip(draft.attrs, rolls):
            g = grade(roll) if roll is not None and 0.85 <= roll <= 1.15 else None
            letter = grade_letter(roll, attr.positive) if g is not None else None
            if g is not None and not attr.positive:
                g = 100 - g  # a smaller curse is the better roll
            row = QHBoxLayout()
            row.addWidget(self._label(catalog.format_attr(attr), BUFF if attr.positive else CURSE, 12), 1)
            row.addWidget(GradeBar(g, letter))
            self.body.addLayout(row)
        for warning in warnings[:2]:
            w = self._label(warning, AMBER, 12)
            w.setWordWrap(True)
            self.body.addWidget(w)
        self.body.addSpacing(4)
        self.body.addWidget(self._label("Click to open in Price check", FAINT, 11))
        self._place()

    def show_price(self, check: Optional[PriceCheck], error: str = "") -> None:
        self.check = check
        self.detail_skeleton.hide()
        self.price_detail.show()
        if error:
            self.price.set_text("")
            self.price_detail.setText("No price right now")
            self.price_detail.setToolTip(error)
        elif check is None or check.estimate is None:
            self.price.set_text("")
            self.price_detail.setText("Nobody is selling a riven for this weapon right now.")
        else:
            self.price.set_text(f"~{check.estimate:g}")
            similar = " that rolled alike" if check.similar_rolls else ""
            self.price_detail.setText(f"{check.low} to {check.high}p · {check.count} similar listings{similar}")
            self.price_detail.setToolTip(f"Compared with listings with {check.tier}.")
        self._place()

    def show_failed(self, message: str) -> None:
        self.draft, self.check = None, None
        self._clear()
        self.body.addLayout(self._header("Riven not read", "", None))
        w = self._label(message, AMBER, 12)
        w.setWordWrap(True)
        self.body.addWidget(w)
        self.body.addWidget(self._label("Click to open in Price check", FAINT, 11))
        self._place()

    def _header(self, title: str, meta: str, overall: Optional[int]) -> QHBoxLayout:
        """Weapon and riven name, the disposition and MR under it, the overall grade in a tile."""
        row = QHBoxLayout()
        text = QVBoxLayout()
        text.setSpacing(2)
        name = self._label(title, TEXT, 15, bold=True)
        name.setWordWrap(True)
        text.addWidget(name)
        if meta:
            text.addWidget(self._label(meta, MUTED, 12))
        row.addLayout(text, 1)
        if overall is not None:
            color = grade_color(overall)
            tile = self._label(grade_from_percent(overall), color, 15, bold=True)
            tile.setAlignment(Qt.AlignmentFlag.AlignCenter)
            tile.setFixedSize(40, 40)
            tile.setToolTip("Overall roll: A+ best, B+ average, C worst")
            tile.setStyleSheet(f"color: {color.name()}; border-radius: 8px;"
                               f" background: rgba({color.red()}, {color.green()}, {color.blue()}, 36);")
            row.addWidget(tile, 0, Qt.AlignmentFlag.AlignTop)
        return row

    @staticmethod
    def _divider() -> QWidget:
        line = QWidget()
        line.setFixedHeight(1)
        line.setStyleSheet(f"background: {theme.BORDER_SUBTLE};")
        return line

    # --- window -------------------------------------------------------------------------

    def _place(self) -> None:
        """Right edge, a fifth of the way down: clear of the card in the middle and AlecaFrame on the left."""
        self.adjustSize()
        g = self.screen_geometry
        self.move(g.right() - self.width() - 28, g.top() + int(g.height() * 0.2))
        if not self.isVisible():
            self.show()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(BORDER, 1))
        p.setBrush(PANEL)
        p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), theme.RADIUS_MD, theme.RADIUS_MD)
        p.end()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()


def _drop(widget: QWidget) -> None:
    widget.hide()
    widget.setParent(None)
    widget.deleteLater()


def _delete_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        if item.widget() is not None:
            _drop(item.widget())
        elif item.layout() is not None:
            _delete_layout(item.layout())


class RivenAssistant(QObject):
    """Ties the screen watcher to the popup: read the card off the screen, price it, show both."""

    _done = pyqtSignal(object, object)  # (callback, result) back on the UI thread

    def __init__(self, data: Callable[[], tuple[RivenCatalog, "RivenService"]], popup: RivenPopup,
                 my_name: Callable[[], Optional[str]], open_window: Callable[[Optional[RivenDraft], Optional[PriceCheck]], None],
                 read: Optional[Callable] = None) -> None:
        super().__init__()
        from .riven_ocr import read_riven

        self.data = data
        self.popup = popup
        self.my_name = my_name
        self.open_window = open_window
        self.read = read or read_riven
        self._generation = 0
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._done.connect(lambda callback, result: callback(result))
        popup.clicked.connect(self._clicked)

    def card_shown(self, frame, _layout=None) -> None:
        self._generation += 1
        generation = self._generation
        keep_capture(frame, "riven", _layout)
        if self.popup.draft is None or not self.popup.isVisible():
            self.popup.show_reading()  # a re-read of a showing riven happens quietly behind it

        def work():
            catalog, _ = self.data()
            return catalog, self.read(frame, catalog)

        self._run(work, lambda result: self._read_done(generation, *result), generation)

    def card_hidden(self) -> None:
        self._generation += 1  # results still on their way are dropped
        self.popup.hide()

    def card_back(self) -> None:
        """The same riven is showing again after a short gap: bring the popup back as it was."""
        if self.popup.draft is not None:
            self.popup.show()

    def _read_done(self, generation: int, catalog: RivenCatalog, read) -> None:
        if generation != self._generation:
            return
        current = self.popup.draft
        if not read.ok:
            if current is not None:  # keep the good read rather than flash "not read"
                self.popup.show()
                return
            self.popup.show_failed(" ".join(read.warnings) or "Could not read this riven.")
            return
        draft = read.draft
        if current is not None and (draft.weapon, draft.name, draft.attrs) == (current.weapon, current.name, current.attrs):
            self.popup.show()  # same riven read again: nothing on screen changes
            return
        self.popup.show_read(catalog, draft, read.warnings)
        me = self.my_name()

        def work():
            _, service = self.data()
            weapon = grading_weapon(catalog, draft)
            mine = riven_grade(catalog, weapon, draft.attrs, draft.rank) if weapon else None
            return price_check(service.search(draft.weapon), draft.positives, draft.negative, exclude_seller=me,
                               catalog=catalog, my_grade=mine)

        self._run(work, lambda check: generation == self._generation and self.popup.show_price(check), generation,
                  on_error=lambda exc: self.popup.show_price(None, str(exc)))

    def _run(self, fn, on_ok, generation: int, on_error=None) -> None:
        def task():
            try:
                self._done.emit(on_ok, fn())
            except Exception as exc:
                log.warning("riven popup: %s", exc)
                if generation == self._generation:
                    self._done.emit(on_error or (lambda e: self.popup.show_failed(str(e))), exc)

        self._executor.submit(task)

    def _clicked(self) -> None:
        draft, check = self.popup.draft, self.popup.check
        self.popup.hide()
        self.open_window(draft, check)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)
