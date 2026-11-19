"""The Ducanator section: prime parts sorted by ducats per plat, so you know what to sell to Baro
instead of to players. Data from voidtrace/ducats.py, fetched when the page is first shown and kept an hour."""

from __future__ import annotations

import time
from typing import Optional, Sequence

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QHeaderView, QLabel, QVBoxLayout, QWidget

from ..ducats import DucatRow, ducat_rows
from ..icons import ducat_icon, platinum_icon
from ..items import CatalogItem
from ..market import MarketClient
from .. import theme
from .widgets import (Section, TableState, header_bar, make_cell, make_table, refresh_button, search_field,
                      set_rows, show_sort)

MAX_AGE = 3600  # seconds; the numbers are daily, an hour is plenty


class DucatPage(QWidget):
    COLUMNS = ["Part", "Ducats", "Plat", "Ducats/plat", "Trades (24h)"]
    NAME, DUCATS, PLAT, PER_PLAT, VOLUME = range(5)
    FIELDS = {NAME: "name", DUCATS: "ducats", PLAT: "plat", PER_PLAT: "per_plat", VOLUME: "volume"}
    open_item = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[DucatRow] = []
        self._visible: list[DucatRow] = []
        self.sort_col, self.sort_desc = self.PER_PLAT, True
        self.table = make_table(self.COLUMNS)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(self.NAME, QHeaderView.ResizeMode.Stretch)
        header.setSectionsClickable(True)
        header.sectionClicked.connect(self.sort_by)
        self.table.horizontalHeaderItem(self.DUCATS).setIcon(QIcon(ducat_icon(14)))
        self.table.horizontalHeaderItem(self.PLAT).setIcon(QIcon(platinum_icon(14)))
        self.table.cellDoubleClicked.connect(self._double_clicked)
        self.state = TableState(self.table)
        self.search = search_field("Search parts")
        self.search.textChanged.connect(lambda _t: self.render())
        self.refresh = refresh_button()
        self.header_actions = header_bar(self.search, self.refresh)
        self.status = QLabel(objectName="status")
        self.status_line = self.status
        layout = QVBoxLayout(self)
        layout.addWidget(self.table, 1)
        show_sort(self.table, self.sort_col, self.sort_desc)

    def sort_by(self, column: int) -> None:
        if column == self.sort_col:
            self.sort_desc = not self.sort_desc
        else:
            self.sort_col, self.sort_desc = column, column != self.NAME
        show_sort(self.table, self.sort_col, self.sort_desc)
        self.render()

    def shown_rows(self) -> list[DucatRow]:
        text = self.search.text().strip().casefold()
        rows = [r for r in self.rows if text in r.name.casefold()]
        field = self.FIELDS[self.sort_col]
        return sorted(rows, key=lambda r: getattr(r, field), reverse=self.sort_desc)

    def render(self) -> None:
        rows = self.shown_rows()
        self._visible = rows
        self.table.setUpdatesEnabled(False)
        set_rows(self.table, len(rows))
        for i, row in enumerate(rows):
            self.table.setItem(i, self.NAME, make_cell(row.name))
            self.table.setItem(i, self.DUCATS, make_cell(str(row.ducats), right=True))
            self.table.setItem(i, self.PLAT, make_cell(f"{row.plat:.1f}", right=True))
            self.table.setItem(i, self.PER_PLAT, make_cell(f"{row.per_plat:.1f}", right=True))
            self.table.setItem(i, self.VOLUME, make_cell(str(row.volume), right=True))
        self.table.setUpdatesEnabled(True)
        if self.rows and not rows:
            self.state.message("No parts match")
        elif self.rows:
            self.state.clear()

    def _double_clicked(self, row: int, _col: int) -> None:
        self.open_item.emit(self._visible[row].slug)


class DucatSection(Section):
    PAGES = {"best": "Best value"}

    def __init__(self, catalog: Sequence[CatalogItem], client: Optional[MarketClient] = None) -> None:
        super().__init__()
        self.catalog = catalog
        self.client = client or MarketClient()
        self.fetched_at = 0.0
        self.loading = False
        self.best = DucatPage()
        self.open_item = self.best.open_item
        self.best.refresh.clicked.connect(self.fetch)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.pages, 1)
        self.add_page("best", self.best)

    def page_shown(self, key: str) -> None:
        if time.time() - self.fetched_at > MAX_AGE and self.isVisible():
            self.fetch()

    def fetch(self) -> None:
        if self.loading:
            return
        self.loading = True
        if not self.best.rows:
            self.best.state.loading()
        self.best.status.setText("Loading ducat prices…")
        self.best.status.setStyleSheet("")
        self.run_async(lambda: ducat_rows(self.client.get_v1("/tools/ducats"), self.catalog),
                       self._loaded, self._failed)

    def _loaded(self, rows: list[DucatRow]) -> None:
        self.loading = False
        self.fetched_at = time.time()
        self.best.rows = rows
        self.best.render()
        if not rows:
            self.best.state.message("No ducat data right now")
        self.best.status.setText(f"{len(rows)} parts · daily trade data")

    def _failed(self, _exc) -> None:
        self.loading = False
        self.best.state.error("Couldn't load ducat prices", retry=self.fetch)
        self.best.status.setText("Couldn't load ducat prices" + (" (showing older ones)" if self.best.rows else ""))
        self.best.status.setStyleSheet(f"color: {theme.WARNING};")
