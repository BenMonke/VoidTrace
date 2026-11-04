"""After a trade: update your Warframe.Market orders by themselves, and show a small card with Undo.

`TradeTracker.feed` gets every game log line (on the log thread). When `TradeReader` sees a trade go
through, the order changes run in the background and `TradeToast` shows what changed, top right,
for 10 seconds. Undo puts the orders back. Turned on and off from the tray ("Update orders after
trades"); it only acts while you are signed in to Warframe.Market.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional, Sequence

from PyQt6.QtCore import (QEasingCurve, QObject, QParallelAnimationGroup, QPoint, QPropertyAnimation, QRect, Qt,
                          QTimer, pyqtSignal)
from PyQt6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout, QWidget

from . import settings, theme
from .account import Account
from .items import CatalogItem
from .price_cleaner import PriceService, overpaying, paid_text, trade_price
from .ui.widgets import animations_enabled
from .trades import (PLATINUM, OrderChange, Trade, TradeHistory, TradeReader, apply_changes, item_finder,
                     plan_changes, summary, undo)

log = logging.getLogger(__name__)

SETTING = "trade_updates"
SHOW_MS = 10_000
NOTE_MS = 4_000

TOAST_STYLE = f"""
QFrame#toast {{ background: rgba(22, 25, 31, 240); border: 1px solid {theme.BORDER_STRONG};
    border-left: 2px solid {theme.DEFAULT_ACCENT}; border-radius: 8px; }}
QLabel {{ color: {theme.TEXT_PRIMARY}; background: transparent; font-family: {theme.FONT_STACK}; font-size: 12px; }}
QLabel#title {{ font-size: 13px; font-weight: 600; }}
QLabel#title[error="true"] {{ color: {theme.NEGATIVE}; }}
QLabel#title[warning="true"] {{ color: {theme.WARNING}; }}
QPushButton {{ background: {theme.BG_RAISED}; color: {theme.TEXT_PRIMARY}; border: 1px solid {theme.BORDER_STRONG};
    border-radius: 4px; padding: 0 12px; min-height: 30px; font-family: {theme.FONT_STACK}; font-size: 13px; }}
QPushButton:hover {{ background: {theme.BG_HOVER}; }}
QPushButton:pressed {{ background: {theme.BG_PANEL}; }}
QPushButton:disabled {{ color: {theme.TEXT_MUTED}; }}
"""
WIDTH = 320
SLIDE = 12  # px the card travels as it slides in and out


def enabled() -> bool:
    return bool(settings.get(SETTING, True))


class TradeToast(QWidget):
    """The small card: what the trade changed, and an Undo button. Slides in at the top right."""

    def __init__(self, screen: QRect) -> None:
        super().__init__(None)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                            | Qt.WindowType.Tool | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)  # the card is 94% opaque
        self.screen_rect = screen
        self.card = QFrame(objectName="toast")
        self.title = QLabel("Orders updated", objectName="title")
        self.text = QLabel(wordWrap=True)
        self.undo_button = QPushButton("Undo")
        self.undo_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.undo_button.clicked.connect(self._undo_clicked)
        inner = QVBoxLayout(self.card)
        inner.setContentsMargins(12, 12, 12, 12)
        inner.setSpacing(4)
        inner.addWidget(self.title)
        inner.addWidget(self.text)
        inner.addWidget(self.undo_button, 0, Qt.AlignmentFlag.AlignRight)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.card)
        self.setFixedWidth(WIDTH)
        theme.follow(self, TOAST_STYLE)
        self._on_undo: Optional[Callable[[], None]] = None
        self._timer = QTimer(self, singleShot=True)
        self._timer.timeout.connect(self.slide_out)
        self._slide = QPropertyAnimation(self, b"pos", self)
        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._motion = QParallelAnimationGroup(self)
        self._motion.addAnimation(self._slide)
        self._motion.addAnimation(self._fade)
        self._motion.finished.connect(lambda: self.hide() if self._leaving else None)
        self._leaving = False

    def show_changes(self, text: str, on_undo: Callable[[], None]) -> None:
        self._set_title("Orders updated")
        self.text.setText(text)
        self._on_undo = on_undo
        self.undo_button.setEnabled(True)
        self.undo_button.show()
        self._pop(SHOW_MS)

    def show_note(self, text: str, error: bool = False) -> None:
        """A short message without Undo (the undo result, or why nothing was changed)."""
        self._set_title("Couldn't update orders" if error else "Undone")
        self.text.setText(text)
        self.undo_button.hide()
        self._on_undo = None
        self._pop(NOTE_MS)

    def show_warning(self, text: str) -> None:
        """Shown while the trade confirm dialog is still open, so there is time to cancel."""
        self._set_title("Check the price", warning=True)
        self.text.setText(text)
        self.undo_button.hide()
        self._on_undo = None
        self._pop(SHOW_MS)

    def _set_title(self, text: str, warning: bool = False) -> None:
        self.title.setText(text)
        self.title.setProperty("error", text.startswith("Couldn't"))
        self.title.setProperty("warning", warning)
        self.title.style().unpolish(self.title)
        self.title.style().polish(self.title)

    def _undo_clicked(self) -> None:
        if self._on_undo is not None:
            self.undo_button.setEnabled(False)
            self.undo_button.setText("Undoing…")
            callback, self._on_undo = self._on_undo, None
            callback()

    def _home(self) -> QPoint:
        return QPoint(self.screen_rect.right() - self.width() - 24, self.screen_rect.top() + 24)

    def _animate(self, start: QPoint, end: QPoint, opacity: tuple[float, float], ms: int,
                 curve: QEasingCurve.Type) -> None:
        self._motion.stop()
        for anim, a, b in ((self._slide, start, end), (self._fade, *opacity)):
            anim.setStartValue(a)
            anim.setEndValue(b)
            anim.setDuration(ms)
            anim.setEasingCurve(curve)
        self._motion.start()

    def _pop(self, ms: int) -> None:
        self.undo_button.setText("Undo")
        self.adjustSize()
        home = self._home()
        self._leaving = False
        if not self.isVisible() and animations_enabled():
            self.move(home + QPoint(SLIDE, 0))
            self.setWindowOpacity(0.0)
            self.show()
            self._animate(home + QPoint(SLIDE, 0), home, (0.0, 1.0), 150, QEasingCurve.Type.OutCubic)
        else:
            self._motion.stop()
            self.move(home)
            self.setWindowOpacity(1.0)
            self.show()
        self.raise_()
        self._timer.start(ms)

    def slide_out(self) -> None:
        if not self.isVisible():
            return
        if not animations_enabled():
            self.hide()
            return
        self._leaving = True
        self._animate(self.pos(), self.pos() + QPoint(SLIDE, 0), (1.0, 0.0), 120, QEasingCurve.Type.InCubic)


class TradeTracker(QObject):
    """Reads trades from the log lines and updates the matching orders (see trades.py)."""

    applied = pyqtSignal(object, object)  # trade, the changes that went through
    note = pyqtSignal(str)
    warn = pyqtSignal(str)  # "you're overpaying", while the trade can still be cancelled
    recorded = pyqtSignal(object)  # a TradeRecord, saved to the history

    def __init__(self, account: Account, catalog: Sequence[CatalogItem], toast: TradeToast,
                 is_enabled: Callable[[], bool] = enabled, on_orders_changed: Callable[[], None] = lambda: None,
                 history: Optional[TradeHistory] = None, prices: Optional[PriceService] = None) -> None:
        super().__init__()
        self.prices = prices  # real sales, for the overpaying warning; None turns it off
        self.account = account
        self.find = item_finder(catalog)
        self.toast = toast
        self.is_enabled = is_enabled
        self.on_orders_changed = on_orders_changed
        self.reader = TradeReader()
        self.history = history or TradeHistory()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="VoidTrace-Trades")
        self.applied.connect(self._show)
        self.note.connect(self._note)
        self.warn.connect(self.toast.show_warning)

    def feed(self, line: str) -> None:
        """Every game log line (log thread)."""
        trade = self.reader.feed(line)
        if self.reader.offered is not None and self.prices is not None:
            self.executor.submit(self.check_price, self.reader.offered)
        if trade is None:
            return
        log.info("trade with %s: gave %s; got %s", trade.partner, trade.gave, trade.got)
        self.executor.submit(self.record, trade)  # kept whether or not orders are updated
        if self.is_enabled() and self.account.signed_in:
            self.executor.submit(self.handle, trade)

    def check_price(self, trade: Trade) -> Optional[str]:
        """Warn while the confirm dialog is open if you are paying far more than people paid lately.
        Only plat for one kind of item: with several, nobody knows how the plat splits."""
        got = [i for i in trade.got if i.name.casefold() != PLATINUM]
        if not trade.plat_given or trade.plat_got or len(got) != 1:
            return None
        item = self.find(got[0].name)
        if item is None or (item.max_rank is not None and got[0].rank is None):
            return None
        try:
            paid, _, _ = trade_price(self.prices.sales(item.slug), rank=got[0].rank if item.max_rank is not None else None)
        except Exception as exc:
            log.warning("trade: price check failed for %s: %s", item.slug, exc)
            return None
        each = trade.plat_given / got[0].quantity
        if not overpaying(each, paid):
            return None
        text = f"{paid_text(paid, item.name)} You're paying {round(each)}."
        self.warn.emit(text)
        return text

    def record(self, trade: Trade) -> None:
        self.recorded.emit(self.history.add(trade))

    def handle(self, trade: Trade) -> list[OrderChange]:
        try:
            changes = plan_changes(trade, self.account.my_orders(), self.find)
            done = apply_changes(self.account, changes)
        except Exception as exc:
            log.warning("trade: could not check your orders: %s", exc)
            self.note.emit(f"Could not check your orders: {exc}")
            return []
        if done:
            log.info("trade: updated %d order(s)", len(done))
            self.applied.emit(trade, done)
        return done

    def undo(self, changes: Sequence[OrderChange]) -> None:
        try:
            undo(self.account, changes)
        except Exception as exc:
            log.warning("trade: undo failed: %s", exc)
            self.note.emit(f"Could not put the orders back: {exc}")
            return
        log.info("trade: undid %d order change(s)", len(changes))
        self.note.emit("Orders put back as they were.")

    def _show(self, trade: Trade, changes: list) -> None:
        self.toast.show_changes(summary(trade, changes), lambda: self.executor.submit(self.undo, changes))
        self.on_orders_changed()

    def _note(self, text: str) -> None:
        self.toast.show_note(text, error=text.startswith("Could not"))
        self.on_orders_changed()

    def shutdown(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=True)
