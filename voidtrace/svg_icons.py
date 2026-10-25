"""Line icons as SVG strings, tinted when drawn: the rail's section icons, the flat VoidTrace mark,
and a small set of Lucide icons (MIT licence, lucide.dev) for buttons, fields and states.

Kept as code like icons.py, so the build needs no image files. `icon()` and `pixmap()` draw one in
any colour; `file()` writes a tinted copy to the temp folder for stylesheets, which only take urls.
"""

from __future__ import annotations

import os
import tempfile
from functools import lru_cache

from PyQt6.QtCore import QByteArray, QRectF, Qt
from PyQt6.QtGui import QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer

PATHS = {
    # rail (docs/design/mockups/Sidebar.dc.html)
    "market": '<path d="M3 9l1.8-5h14.4L21 9"/><path d="M3 9h18v1.5a3 3 0 0 1-6 0 3 3 0 0 1-6 0 3 3 0 0 1-6 0z"/>'
              '<path d="M5 13v7h14v-7"/><path d="M10 20v-4h4v4"/>',
    "rivens": '<path d="M12 4l8.5 14.5h-17z"/><path d="M6.5 10.5h11L12 20z"/>',
    "relics": '<path d="M4 10a4 4 0 0 1 4-4h8a4 4 0 0 1 4 4v1H4z"/><path d="M4 11h16v8H4z"/><path d="M10 11v3h4v-3"/>',
    "ducats": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4.5"/>',
    "bell": '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10 21a2 2 0 0 0 4 0"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1'
                'a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3'
                'l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1'
                'a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9'
                'a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8'
                'l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
    # Lucide
    "search": '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    "x": '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    "copy": '<rect width="14" height="14" x="8" y="8" rx="2" ry="2"/>'
            '<path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>',
    "eye": '<path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>',
    "eye-off": '<path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"/>'
               '<path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68"/>'
               '<path d="M6.61 6.61A13.53 13.53 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61"/>'
               '<path d="M2 2l20 20"/>',
    "trash": '<path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/>'
             '<path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/><path d="M10 11v6"/><path d="M14 11v6"/>',
    "refresh": '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/>'
               '<path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/>',
    "user": '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    "log-out": '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="M16 17l5-5-5-5"/><path d="M21 12H9"/>',
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "alert": '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/>'
             '<path d="M12 9v4"/><path d="M12 17h.01"/>',
    "info": '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
    "chevron-down": '<path d="m6 9 6 6 6-6"/>',
    "chevron-up": '<path d="m18 15-6-6-6 6"/>',
    "undo": '<path d="M9 14 4 9l5-5"/><path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11"/>',
    "external": '<path d="M15 3h6v6"/><path d="M10 14 21 3"/>'
                '<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
    "minus": '<path d="M5 12h14"/>',
    "plus": '<path d="M5 12h14"/><path d="M12 5v14"/>',
}

LOGO = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
        '<path d="M5.5 12.5C7.5 7 13 3.8 19 4.6c-5 .9-9.2 4-11.3 8.6z" fill="{fg}"/>'
        '<path d="M26.5 19.5C24.5 25 19 28.2 13 27.4c5-.9 9.2-4 11.3-8.6z" fill="{fg}"/>'
        '<circle cx="16" cy="16" r="5" fill="{accent}"/>'
        '<circle cx="7" cy="23" r="1.2" fill="{fg}" fill-opacity=".6"/>'
        '<circle cx="25" cy="8.5" r="1.2" fill="{fg}" fill-opacity=".6"/></svg>')


def svg(name: str, color: str, stroke: float = 1.75) -> str:
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
            f'stroke="{color}" stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round">'
            f'{PATHS[name]}</svg>')


def render(source: str, size: int, ratio: float = 2.0) -> QPixmap:
    px = QPixmap(round(size * ratio), round(size * ratio))
    px.setDevicePixelRatio(ratio)
    px.fill(Qt.GlobalColor.transparent)
    painter = QPainter(px)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    QSvgRenderer(QByteArray(source.encode())).render(painter, QRectF(0, 0, size, size))
    painter.end()
    return px


@lru_cache(maxsize=256)
def pixmap(name: str, color: str, size: int = 16, stroke: float = 1.75) -> QPixmap:
    return render(svg(name, color, stroke), size)


def icon(name: str, color: str, size: int = 16) -> QIcon:
    return QIcon(pixmap(name, color, size))


def logo(accent: str, fg: str, size: int = 32) -> QPixmap:
    return render(LOGO.format(accent=accent, fg=fg), size)


@lru_cache(maxsize=64)
def file(name: str, color: str, stroke: float = 2.0) -> str:
    """A tinted copy on disk, as a forward-slash path for a stylesheet `url()`."""
    folder = os.path.join(tempfile.gettempdir(), "VoidTrace-icons")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"{name}-{color.lstrip('#')}-{stroke}.svg")
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg(name, color, stroke))
    return path.replace("\\", "/")
