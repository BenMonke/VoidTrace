"""The theme: one accent colour on near-black greys, changeable from the tray (Accent colour).

Every colour, size and spacing value the UI uses lives here as a token (docs/design/DESIGN-SYSTEM.md).

Stylesheets are written with the default accent (#4fa3ff, the logo's void blue) and its hover shade;
`apply()` swaps in the chosen accent. Windows register with `follow()` so a new accent shows at once,
and painted parts (the riven popup's border and price, the best reward card) read `accent()` when
they draw.
"""

from __future__ import annotations

import weakref
from typing import Callable

from PyQt6.QtGui import QColor, QGuiApplication

from . import settings

# Surfaces: depth comes from page -> panel -> raised, never from shadows.
BG_PAGE = "#0f1115"
BG_PANEL = "#16191f"
BG_RAISED = "#1d2129"
BG_HOVER = "#242934"
BORDER_SUBTLE = "#232831"
BORDER_STRONG = "#2f3541"

TEXT_PRIMARY = "#e8eaee"
TEXT_SECONDARY = "#a3a9b5"
TEXT_MUTED = "#7a8190"
RAIL_ICON = "#c4c8d0"

# Semantic colours never follow the accent.
POSITIVE = "#5ccf8f"
NEGATIVE = "#f0705a"
WARNING = "#e6b450"
STATUS_ONLINE = "#78b9ff"

RARITY_COMMON = "#c7925a"
RARITY_UNCOMMON = "#c0c6d0"
RARITY_RARE = "#e6c25a"

FONT_FAMILY = "Segoe UI Variable Text"
FONT_STACK = "'Segoe UI Variable Text', 'Segoe UI'"
TYPE_BODY = 13

SPACE_1, SPACE_2, SPACE_3, SPACE_4, SPACE_6, SPACE_8 = 4, 8, 12, 16, 24, 32
CONTROL_HEIGHT = 32
ROW_HEIGHT = 36
RAIL_WIDTH = 64
RAIL_TILE = 44
RADIUS_SM, RADIUS_MD = 4, 8
FIELD_MAX_WIDTH = 320
SEARCH_MAX_WIDTH = 640

# Stylesheets are written with these literals; apply() swaps them for the chosen accent's shades.
DEFAULT_ACCENT = "#4fa3ff"
DEFAULT_HOVER = "#6eb3ff"      # accent lightened 12%
DEFAULT_PRESSED = "#4793e6"    # accent darkened 10%
DEFAULT_SOFT = "#243347"       # accent at 14% over BG_RAISED: selected rows and items
DEFAULT_ON_ACCENT = "#0b0d10"  # text on accent fills
PRESETS = {
    "Void blue": DEFAULT_ACCENT,
    "Teal": "#5fd0c8",
    "Gold": "#d4b46a",
    "Crimson": "#e0524f",
    "Amber": "#e8955a",
}

_listeners: list[Callable[[], None]] = []


def accent() -> QColor:
    color = QColor(settings.get("accent", DEFAULT_ACCENT))
    return color if color.isValid() else QColor(DEFAULT_ACCENT)


def accent_hex() -> str:
    return accent().name()


def hover_hex() -> str:
    return accent().lighter(112).name()


def pressed_hex() -> str:
    return accent().darker(111).name()


def soft_hex() -> str:
    return mix(accent(), QColor(BG_RAISED), 0.14).name()


def mix(top: QColor, base: QColor, amount: float) -> QColor:
    """`top` laid over `base` at `amount` opacity."""
    return QColor(*(round(b + (t - b) * amount) for t, b in
                    zip(top.getRgb()[:3], base.getRgb()[:3])))


def on_accent_hex() -> str:
    """Dark text on a light accent, white on a dark one."""
    return DEFAULT_ON_ACCENT if accent().lightness() > 110 else "#ffffff"


def apply(stylesheet: str) -> str:
    """A stylesheet written with the default accent, in the chosen one."""
    return (stylesheet.replace(DEFAULT_HOVER, hover_hex())
            .replace(DEFAULT_PRESSED, pressed_hex())
            .replace(DEFAULT_SOFT, soft_hex())
            .replace(DEFAULT_ACCENT, accent_hex())
            .replace(DEFAULT_ON_ACCENT, on_accent_hex())
            .replace(f"check-{DEFAULT_ON_ACCENT[1:]}", f"check-{on_accent_hex()[1:]}"))  # svg_icons.file()


def set_accent(color: str) -> None:
    if not QColor(color).isValid():
        raise ValueError(f"not a colour: {color}")
    settings.put("accent", QColor(color).name())
    if QGuiApplication.instance() is None:  # nothing on screen; restyling orphaned widgets would crash
        return
    for listener in list(_listeners):
        listener()


def follow(widget, stylesheet: str) -> None:
    """Style `widget` with the accent now, and again whenever it changes."""
    widget.setStyleSheet(apply(stylesheet))
    ref = weakref.ref(widget)

    def restyle() -> None:
        w = ref()
        if w is None:
            _listeners.remove(restyle)
            return
        try:
            w.setStyleSheet(apply(stylesheet))
            w.update()
        except RuntimeError:  # the Qt object is gone
            _listeners.remove(restyle)

    _listeners.append(restyle)


def on_change(callback: Callable[[], None]) -> None:
    _listeners.append(callback)
