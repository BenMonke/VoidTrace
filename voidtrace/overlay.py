"""Phase 5: transparent, always-on-top overlay for Borderless Fullscreen.

Nothing is injected into the game: this is an ordinary top-level window drawn above it. A window
mask limits mouse input to the price cards themselves, so every click elsewhere (including on the
game's own reward cards) goes straight to Warframe. Clicking a card asks for that item's sellers.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QEasingCurve, QPointF, QPropertyAnimation, QRect, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QRegion
from PyQt6.QtWidgets import QWidget

from . import theme
from .cv_cleaner import reward_band, reward_slots
from .icons import ducat_icon, platinum_icon
from .pipeline import RewardCard
from .price_cleaner import few_sales, price_basis_label
from .ui.widgets import Pulse, animations_enabled

CARD_WIDTH_RATIO = 0.95   # card width as a share of one reward slot
CARD_HEIGHT = 112         # reference pixels at 1080p; scaled with the screen
# Gap between the reward-name band and the cards. Under each reward the game lists the
# squad members who picked it (up to 4 names, ~110 px at 1080p); the first live test
# showed cards placed right under the names covering that list, so they sit below it.
GAP_BELOW_NAMES = 130

BG = QColor(theme.BG_PANEL)
BG.setAlphaF(0.94)
BORDER = QColor(theme.BORDER_STRONG)
TEXT = QColor(theme.TEXT_PRIMARY)
MUTED = QColor(theme.TEXT_SECONDARY)
MUTED_LOW = QColor(theme.TEXT_MUTED)
WARN = QColor(theme.WARNING)
GOLD = QColor(theme.RARITY_RARE)
FADE_IN_MS = 120


class OverlayWindow(QWidget):
    card_clicked = pyqtSignal(int)  # slot index of a tradable card the player clicked

    def __init__(self, screen_geometry: QRect, device_pixel_ratio: float = 1.0, ui_scale: float = 1.0,
                 hide_after_ms: int = 20000) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool                       # no taskbar entry
            | Qt.WindowType.WindowDoesNotAcceptFocus   # clicks arrive, focus stays with the game
        )
        self.setMouseTracking(True)
        self.hovered: Optional[int] = None
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setGeometry(screen_geometry)
        self.dpr = device_pixel_ratio
        self.ui_scale = ui_scale
        self.cards: list[RewardCard] = []
        self.card_rects: list[QRect] = []
        self._hide_timer = QTimer(self, singleShot=True, interval=hide_after_ms)
        self._hide_timer.timeout.connect(self.clear)
        self._fade = QPropertyAnimation(self, b"windowOpacity", self, duration=FADE_IN_MS, startValue=0.0, endValue=1.0)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        Pulse.shared().tick.connect(lambda: self.update() if any(c.pending for c in self.cards) else None)

    # Geometry works in physical pixels (what the screenshot sees), then converts to Qt's
    # logical pixels so it lines up under Windows display scaling.
    def layout_cards(self, count: int) -> list[QRect]:
        phys_w = round(self.width() * self.dpr)
        phys_h = round(self.height() * self.dpr)
        band = reward_band(phys_w, phys_h, self.ui_scale)
        scale = phys_h / 1080 * self.ui_scale
        rects = []
        for box in reward_slots(phys_w, phys_h, count, self.ui_scale):
            w = box.w * CARD_WIDTH_RATIO
            x = box.x + (box.w - w) / 2
            y = band.y + band.h + GAP_BELOW_NAMES * scale
            h = CARD_HEIGHT * scale
            rects.append(QRect(*(round(v / self.dpr) for v in (x, y, w, h))))
        return rects

    def show_cards(self, cards: list[RewardCard]) -> None:
        self.cards = cards
        self.card_rects = self.layout_cards(len(cards)) if cards else []
        self.setMask(self.input_region())
        if not self.isVisible() and animations_enabled():
            self.setWindowOpacity(0.0)
            self._fade.start()
        self.show()
        self.raise_()
        self.update()
        self._hide_timer.start()

    def clear(self) -> None:
        self.cards, self.card_rects, self.hovered = [], [], None
        self.update()
        self.hide()

    def input_region(self) -> QRegion:
        """Only the card rectangles take mouse input; the rest of the screen stays the game's."""
        region = QRegion()
        for rect in self.card_rects:
            region = region.united(QRegion(rect.adjusted(-2, -2, 2, 2)))
        return region if not region.isEmpty() else QRegion(0, 0, 1, 1)

    def clickable(self, index: int) -> bool:
        card = self.cards[index]
        return card.resolution.item is not None and card.resolution.item.slug is not None

    def card_at(self, x: float, y: float) -> Optional[int]:
        for i, rect in enumerate(self.card_rects):
            if rect.contains(round(x), round(y)):
                return i
        return None

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        index = self.card_at(event.position().x(), event.position().y())
        index = index if index is not None and self.clickable(index) else None
        if index != self.hovered:
            self.hovered = index
            self.setCursor(Qt.CursorShape.PointingHandCursor if index is not None else Qt.CursorShape.ArrowCursor)
            self.update()

    def leaveEvent(self, event) -> None:  # noqa: N802
        if self.hovered is not None:
            self.hovered = None
            self.update()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        index = self.card_at(event.position().x(), event.position().y())
        if index is not None and self.clickable(index) and event.button() == Qt.MouseButton.LeftButton:
            self.card_clicked.emit(index)

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        for i, (card, rect) in enumerate(zip(self.cards, self.card_rects)):
            self._paint_card(painter, card, rect, hovered=(i == self.hovered))
        painter.end()

    def _paint_card(self, p: QPainter, card: RewardCard, rect: QRect, hovered: bool = False) -> None:
        """OCR'd name (small, to check the scan), the price as the one big thing, ducats, then tags
        that apply. The best card gets an accent border and price."""
        accent = theme.accent()
        k = rect.height() / CARD_HEIGHT  # everything scales with the card
        border = accent if card.best else (TEXT if hovered else BORDER)
        p.setPen(QPen(border, 2 if card.best or hovered else 1))
        p.setBrush(BG)
        r = QRectF(rect).adjusted(0.5, 0.5, -0.5, -0.5)
        p.drawRoundedRect(r, theme.RADIUS_MD, theme.RADIUS_MD)
        inner = rect.adjusted(round(12 * k), round(10 * k), -round(12 * k), -round(10 * k))
        ratio = float(self.dpr)
        rows = {"name": (0, 16), "price": (18, 34), "ducats": (52, 16), "tags": (72, 20)}  # (top, height) at k=1

        def area(name: str) -> QRectF:
            top, height = rows[name]
            return QRectF(inner.x(), inner.y() + top * k, inner.width(), height * k)

        def font(size: float, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
            f = QFont(theme.FONT_FAMILY)
            f.setPixelSize(max(8, round(size * k)))
            f.setWeight(weight)
            return f

        def text(name: str, value: str, color: QColor, f: QFont) -> None:
            p.setFont(f)
            p.setPen(color)
            box = area(name)
            elided = p.fontMetrics().elidedText(value, Qt.TextElideMode.ElideRight, round(box.width()))
            p.drawText(box, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter, elided)

        def amount(name: str, icon, value: str, color: QColor, f: QFont) -> None:
            p.setFont(f)
            metrics = p.fontMetrics()
            box = area(name)
            icon_px = round(f.pixelSize() * (0.8 if f.pixelSize() > 20 else 1.0))
            gap = max(2, icon_px // 4)
            width = icon_px + gap + metrics.horizontalAdvance(value)
            x = box.x() + (box.width() - width) / 2
            p.drawPixmap(QPointF(x, box.y() + (box.height() - icon_px) / 2), icon(icon_px, ratio))
            p.setPen(color)
            p.drawText(QRectF(x + icon_px + gap, box.y(), width, box.height()), Qt.AlignmentFlag.AlignVCenter, value)

        def bar(name: str, width: float, height: float) -> None:
            box = area(name)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(Pulse.shared().color())
            p.drawRoundedRect(QRectF(box.center().x() - width * k / 2, box.center().y() - height * k / 2,
                                     width * k, height * k), theme.RADIUS_SM, theme.RADIUS_SM)

        if card.name is None:
            # Never echo raw OCR: on a wrong screen it is junk (live test 2 printed terminal text).
            text("price", "Couldn't read this one", MUTED_LOW, font(12))
            return
        text("name", card.name, MUTED, font(12))
        if card.pending:
            bar("price", 72, 18)
            bar("ducats", 40, 10)
            bar("tags", 56, 10)
            return
        price_color = accent if card.best else TEXT
        big = font(28, QFont.Weight.DemiBold)
        if card.resolution.item.slug is None:
            text("price", "Untradable", price_color, font(18, QFont.Weight.DemiBold))
        elif card.price is None:
            text("price", "No price", MUTED, font(18, QFont.Weight.DemiBold))
        else:
            amount("price", platinum_icon, f"{card.price.price:g}", price_color, big)
        amount("ducats", ducat_icon, str(card.ducats), MUTED, font(12))
        if hovered:
            text("tags", "Click for sellers", TEXT, font(11, QFont.Weight.DemiBold))
            return
        self._paint_tags(p, card_tags(card), area("tags"), font(11, QFont.Weight.DemiBold), k)

    @staticmethod
    def _paint_tags(p: QPainter, tags: list[tuple[str, QColor, QColor]], box: QRectF, f: QFont, k: float) -> None:
        """Small pills, centred in one row."""
        if not tags:
            return
        p.setFont(f)
        metrics = p.fontMetrics()
        pad, gap = 6 * k, 4 * k
        widths = [metrics.horizontalAdvance(label) + 2 * pad for label, _fg, _bg in tags]
        x = box.x() + (box.width() - sum(widths) - gap * (len(tags) - 1)) / 2
        for (label, fg, bg), w in zip(tags, widths):
            pill = QRectF(x, box.y(), w, box.height())
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(bg)
            p.drawRoundedRect(pill, theme.RADIUS_SM, theme.RADIUS_SM)
            p.setPen(fg)
            p.drawText(pill, Qt.AlignmentFlag.AlignCenter, label)
            x += w + gap


def card_tags(card: RewardCard) -> list[tuple[str, QColor, QColor]]:
    """(label, text colour, fill) for each tag that applies to this card.

    Ducats: selling for ducats pays at least 10 per plat. Few sales: the price rests on under 5
    trades or listings. Stale and Unsure match keep the old warnings. A Vaulted tag waits on the
    pipeline knowing a reward's vault status.
    """
    tags = []
    if card.price is not None and card.price.price > 0 and card.ducats / card.price.price >= 10:
        tags.append(("Ducats", GOLD, QColor(GOLD.red(), GOLD.green(), GOLD.blue(), 41)))
    if card.price is not None and few_sales(card.price):
        tags.append(("Few sales", WARN, QColor(WARN.red(), WARN.green(), WARN.blue(), 36)))
    if card.price is not None and card.price.stale:
        tags.append(("Stale", WARN, QColor(WARN.red(), WARN.green(), WARN.blue(), 36)))
    if card.resolution.ambiguous:
        tags.append(("Unsure match", WARN, QColor(WARN.red(), WARN.green(), WARN.blue(), 36)))
    return tags


def cards_summary(cards: Optional[list[RewardCard]]) -> str:
    """One line per card, used for console logging alongside the overlay."""
    lines = []
    for card in cards or []:
        plat = f"{card.price.price:g}p ({price_basis_label(card.price)})" if card.price else "-"
        star = " *" if card.best else ""
        lines.append(f"  slot {card.slot}: {card.name or '<unreadable>'} {plat} {card.ducats}d{star}")
    return "\n".join(lines)
