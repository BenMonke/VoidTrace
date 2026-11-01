"""Posting and managing your own Warframe.Market orders from the Market section.

  * SignInDialog    - email/username + password, sent only to Warframe.Market (see account.py)
  * PostOrderPanel  - top 5 sell/buy orders for one rank (like warframe.market's "Edit order"
                      panel) and a one-click Post with "match lowest", "lowest +/- offset" or a
                      custom price
  * MyOrdersPanel   - your live orders: reprice to the current lowest, or delete
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon
from PyQt6.QtWidgets import (
    QBoxLayout,
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .. import svg_icons, theme
from ..account import MarketError, MyOrder, NotSignedIn, TopOrder, suggested_price, top_orders
from ..icons import platinum_icon
from .widgets import (BUTTON_STYLE, STYLE, Notice, Segmented, Stepper, card, form_rows, header_bar, icon_button,
                      make_cell,
                      make_table, refresh_button, set_rows, show_sort)

if TYPE_CHECKING:
    from .market import MarketSection

TOP_COLUMNS = ["Player", "Rep", "Price", "Rank", "Qty"]
STATUS_DOT = {"ingame": QColor(theme.POSITIVE), "online": QColor(theme.STATUS_ONLINE)}


class SignInDialog(QDialog):
    def __init__(self, window: "MarketSection") -> None:
        super().__init__(window)
        self.window_ = window
        self.setWindowTitle("Sign in to Warframe.Market")
        self.setStyleSheet(theme.apply(STYLE + BUTTON_STYLE))
        self.email = QLineEdit(placeholderText="Email or username")
        self.password = QLineEdit(placeholderText="Password")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.message = QLabel(objectName="muted")
        self.message.setWordWrap(True)
        self.message.setText("Your password goes only to warframe.market and is not saved. "
                             "VoidTrace keeps the session in Windows Credential Manager.")
        self.button = QPushButton("Sign in", objectName="primary")
        self.button.setDefault(True)
        self.button.setMinimumWidth(110)  # "Signing in…" doesn't make it jump
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        for field in (self.email, self.password):
            field.setFixedWidth(theme.FIELD_MAX_WIDTH)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(cancel)
        buttons.addWidget(self.button)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(theme.SPACE_6, theme.SPACE_6, theme.SPACE_6, theme.SPACE_6)
        layout.setSpacing(theme.SPACE_2)
        layout.addLayout(form_rows([("Email", self.email), ("Password", self.password)]))
        layout.addWidget(self.message)
        layout.addSpacing(theme.SPACE_2)
        layout.addLayout(buttons)
        self.button.clicked.connect(self.submit)
        self.password.returnPressed.connect(self.submit)
        self.resize(380, 0)

    def submit(self) -> None:
        email, password = self.email.text().strip(), self.password.text()
        if not email or not password:
            self.message.setText("Enter your email (or username) and password.")
            return
        self.button.setEnabled(False)
        self.button.setText("Signing in…")
        self.message.setStyleSheet("")
        self.message.setText("")
        self.window_.run_async(lambda: self.window_.account.sign_in(email, password),
                               self._done, self._failed)

    def _done(self, name: str) -> None:
        self.password.clear()
        self.window_.account_changed()
        self.accept()

    def _failed(self, exc: Exception) -> None:
        self.password.clear()
        self.button.setEnabled(True)
        self.button.setText("Sign in")
        self.message.setStyleSheet(f"color: {theme.NEGATIVE};")
        self.message.setText(str(exc) if isinstance(exc, (MarketError, NotSignedIn)) else
                             "Could not reach Warframe.Market. Try again in a moment.")


class PostOrderPanel(QWidget):
    """Market > Sell: the top 5 sell and buy orders in two cards, and the order form pinned below."""

    WIDE = 1100  # cards side by side from this width, stacked below it

    def __init__(self, window: "MarketSection") -> None:
        super().__init__()
        self.window_ = window
        self.top: dict[str, list[TopOrder]] = {"sell": [], "buy": []}
        self._request = 0
        self._loaded = False
        theme.follow(self, BUTTON_STYLE)

        self.side = Segmented([("Sell", "sell"), ("Buy", "buy")])
        self.rank = QComboBox()
        # Grow with "Maxed rank" instead of cutting it to "Maxed r" / "Ma...nk".
        self.rank.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.rank.view().setTextElideMode(Qt.TextElideMode.ElideNone)
        self.quantity = Stepper(1, 999, 1)
        self.visible = QCheckBox("Visible")
        self.visible.setChecked(True)

        self.mode = Segmented([("Match lowest", "match"), ("Lowest ±", "offset"), ("Custom", "custom")])
        self.mode_match, self.mode_offset, self.mode_custom = self.mode.buttons
        self.offset = Stepper(-1000, 1000, -1)
        self.custom = Stepper(1, 100000, 10)
        self.price_label = QLabel(objectName="pricetag")
        self.post = QPushButton("Post", objectName="primary")
        self.post.setCursor(Qt.CursorShape.PointingHandCursor)
        self.post.setMinimumWidth(120)  # "Posting…" and "Sign in to post" don't make the row jump
        self.result = QLabel(objectName="status")
        self.result.setWordWrap(True)
        self.notice = Notice()

        self.sell_table = make_table(TOP_COLUMNS)
        self.buy_table = make_table(TOP_COLUMNS)
        for t in (self.sell_table, self.buy_table):
            t.horizontalHeaderItem(2).setIcon(QIcon(platinum_icon(14)))
            t.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            t.setFixedHeight(32 + 5 * theme.ROW_HEIGHT + 2)
            t.state.message("Search an item to see its orders", "search")
        sell_card, sell_layout = card("Top 5 sell orders")
        buy_card, buy_layout = card("Top 5 buy orders")
        self.sell_title, self.buy_title = sell_card.heading, buy_card.heading
        sell_layout.addWidget(self.sell_table)
        buy_layout.addWidget(self.buy_table)
        self.cards = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.cards.setSpacing(theme.SPACE_4)
        self.cards.addWidget(sell_card)
        self.cards.addWidget(buy_card)

        self.order_card, order = card()
        row0 = QHBoxLayout()
        row0.setSpacing(theme.SPACE_2)
        self.rank_label = QLabel("Rank", objectName="muted")
        for w in (QLabel("Type", objectName="muted"), self.side, self.rank_label, self.rank,
                  QLabel("Qty", objectName="muted"), self.quantity, self.visible):
            row0.addWidget(w)
        row0.addStretch(1)
        row1 = QHBoxLayout()
        row1.setSpacing(theme.SPACE_2)
        for w in (QLabel("Price", objectName="muted"), self.mode, self.offset, self.custom, self.price_label):
            row1.addWidget(w)
        row1.addStretch(1)
        row1.addWidget(self.post)
        order.addLayout(row0)
        order.addLayout(row1)

        layout = QVBoxLayout(self)
        layout.setSpacing(theme.SPACE_4)
        layout.addLayout(self.cards)
        layout.addStretch(1)
        layout.addWidget(self.notice)
        layout.addWidget(self.order_card)
        self.status_line = self.result

        self.side.currentIndexChanged.connect(lambda _: self.update_price())
        self.rank.currentIndexChanged.connect(lambda _: self.refresh())
        self.mode.currentIndexChanged.connect(lambda _: self.update_price())
        self.offset.valueChanged.connect(lambda _: self.update_price())
        self.custom.valueChanged.connect(lambda _: self.update_price())
        self.post.clicked.connect(self.post_order)
        self.update_price()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        wide = self.width() >= self.WIDE
        self.cards.setDirection(QBoxLayout.Direction.LeftToRight if wide else QBoxLayout.Direction.TopToBottom)

    # --- item / rank -----------------------------------------------------------------

    def set_item(self, rank: Optional[int] = None) -> None:
        item = self.window_.item
        self.rank.blockSignals(True)
        self.rank.clear()
        if item is not None and item.max_rank is not None:
            for r in range(item.max_rank + 1):
                self.rank.addItem("Maxed rank" if r == item.max_rank else f"Rank {r}", r)
            # Default to max rank, like warframe.market; follow the rank chosen in the seller list.
            self.rank.setCurrentIndex(item.max_rank if rank is None else rank)
        ranked = item is not None and item.max_rank is not None
        self.rank.setVisible(ranked)
        self.rank_label.setVisible(ranked)
        view = self.rank.view()
        view.setMinimumWidth(view.sizeHintForColumn(0) + 24)
        self.rank.blockSignals(False)
        self.result.setText("")
        self.notice.show_text("")
        self.refresh()

    def selected_rank(self) -> Optional[int]:
        item = self.window_.item
        return self.rank.currentData() if item is not None and item.max_rank is not None else None

    def refresh(self) -> None:
        item = self.window_.item
        if item is None:
            return
        self._request += 1
        request, rank = self._request, self.selected_rank()
        label = "" if rank is None else (" · maxed rank" if rank == item.max_rank else f" · rank {rank}")
        self.sell_title.setText(f"Top 5 sell orders{label}")
        self.buy_title.setText(f"Top 5 buy orders{label}")
        for t in (self.sell_table, self.buy_table):
            t.state.loading(5)
        self.price_label.setText("")
        self._loaded = False
        self.window_.run_async(lambda: top_orders(self.window_.sellers.client, item.slug, rank),
                               lambda top: self._on_top(request, top),
                               lambda exc: self._on_top_failed(request))

    def _on_top(self, request: int, top: dict) -> None:
        if request != self._request:
            return
        self.top = top
        self._loaded = True
        for table, rows, nobody in ((self.sell_table, top["sell"], "Nobody's selling this right now"),
                                    (self.buy_table, top["buy"], "Nobody's buying this right now")):
            set_rows(table, len(rows))
            if not rows:
                table.state.message(nobody)
                continue
            for r, o in enumerate(rows):
                table.setItem(r, 0, make_cell(f"●  {o.ingame_name}", color=STATUS_DOT.get(o.status)))
                table.setItem(r, 1, make_cell(str(o.reputation), right=True))
                table.setItem(r, 2, make_cell(str(o.platinum), right=True, icon=platinum_icon(14)))
                table.setItem(r, 3, make_cell("" if o.rank is None else str(o.rank), right=True))
                table.setItem(r, 4, make_cell(str(o.quantity), right=True))
        if self.price() is None and not self.mode_custom.isChecked():
            self.mode_custom.setChecked(True)  # nothing to match: start from a custom price
        self.update_price()

    def _on_top_failed(self, request: int) -> None:
        if request == self._request:
            for t in (self.sell_table, self.buy_table):
                t.state.error(retry=self.refresh)

    # --- price + post -----------------------------------------------------------------------

    def price(self) -> Optional[int]:
        if self.mode_custom.isChecked():
            return self.custom.value()
        offset = self.offset.value() if self.mode_offset.isChecked() else 0
        return suggested_price(self.top, self.side.currentData(), offset,
                               exclude=self.window_.account.ingame_name)

    def update_price(self) -> None:
        price = self.price()
        side = self.side.currentData()
        self.offset.setVisible(self.mode_offset.isChecked())
        self.custom.setVisible(self.mode_custom.isChecked())
        has_item = self.window_.item is not None
        if price is None:
            self.price_label.setText("")
            nobody = "Nobody is selling" if side == "sell" else "Nobody is buying"
            if has_item and self._loaded:
                self.notice.show_text(f"{nobody} right now. Set a custom price.")
        else:
            self.price_label.setText(f"= {price}p")
            if self.notice.tone == "info":
                self.notice.show_text("")
        for w in (self.side, self.rank, self.quantity, self.visible, self.mode, self.offset, self.custom):
            w.setEnabled(has_item)
        signed_in = self.window_.account.signed_in
        self.post.setText("Post" if signed_in else "Sign in to post")
        self.post.setEnabled(not signed_in or (has_item and price is not None))

    def post_order(self) -> None:
        if not self.window_.account.signed_in:
            self.window_.show_sign_in()
            return
        item, price = self.window_.item, self.price()
        if item is None or price is None or not item.id:
            return
        side, rank, qty, visible = self.side.currentData(), self.selected_rank(), self.quantity.value(), self.visible.isChecked()
        self.post.setEnabled(False)
        self.post.setText("Posting…")
        self.notice.show_text("")
        rank_text = "" if rank is None else f" (rank {rank})"

        def done(order: MyOrder) -> None:
            self.update_price()
            self.result.setText(f"Posted: {side} {item.name}{rank_text} for {order.platinum}p, quantity {order.quantity}.")
            self.window_.show_toast(f"Posted {item.name} for {order.platinum}p.")
            self.window_.orders_panel.refresh()

        def failed(exc: Exception) -> None:
            self.update_price()
            if isinstance(exc, NotSignedIn):
                self.window_.account_changed()
            message = (str(exc) if isinstance(exc, (MarketError, NotSignedIn)) else
                       "Could not reach Warframe.Market. Nothing was posted.")
            self.result.setText(message)
            self.notice.show_text(message, "error")

        self.window_.run_async(lambda: self.window_.account.create_order(item.id, side, price, qty, rank, visible),
                               done, failed)


class MyOrdersPanel(QWidget):
    COLUMNS = ["", "Item", "Type", "Rank", "Price", "Qty", "", ""]
    EYE, ITEM, TYPE, RANK, PRICE, QTY, MATCH, DELETE = range(8)

    def __init__(self, window: "MarketSection") -> None:
        super().__init__()
        self.window_ = window
        self.orders: list[MyOrder] = []
        self.shown: list[MyOrder] = []
        theme.follow(self, BUTTON_STYLE)
        self.table = make_table(self.COLUMNS)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(self.EYE, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(self.ITEM, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeaderItem(self.PRICE).setIcon(QIcon(platinum_icon(14)))
        self.table.horizontalHeaderItem(self.EYE).setIcon(svg_icons.icon("eye", theme.TEXT_SECONDARY, 14))
        self.status = QLabel(objectName="status")
        self.state_filter = QComboBox()
        for label, value in (("All orders", None), ("Visible", True), ("Hidden", False)):
            self.state_filter.addItem(label, value)
        self.type_filter = QComboBox()
        for label, value in (("Sell and buy", None), ("Sell", "sell"), ("Buy", "buy")):
            self.type_filter.addItem(label, value)
        for box in (self.state_filter, self.type_filter):
            box.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
            box.currentIndexChanged.connect(lambda _: self._render())
        self.reload = refresh_button()
        self.header_actions = header_bar(self.state_filter, self.type_filter, self.reload)
        self.status_line = self.status
        layout = QVBoxLayout(self)
        layout.addWidget(self.table, 1)
        self.reload.clicked.connect(self.refresh)
        # Click a column header to sort by it; click again to flip. Default: visible orders first.
        self.sort_col, self.sort_desc = self.EYE, False
        header.setSectionsClickable(True)
        header.sectionClicked.connect(self.sort_by)
        self._update_header()

    def refresh(self) -> None:
        if not self.window_.account.signed_in:
            self.orders = []
            self._render()
            self.status.setText("Sign in to see your orders.")
            self.table.state.message("Sign in to see your orders", "user", button="Sign in",
                                     on_click=self.window_.show_sign_in, primary=True)
            return
        self.status.setText("Loading your orders\…")
        if not self.orders:
            self.table.state.loading()
        self.window_.run_async(self.window_.account.my_orders, self._show, self._failed)

    def _failed(self, exc: Exception) -> None:
        if isinstance(exc, NotSignedIn):
            self.window_.account_changed()
        self.status.setText(str(exc) if isinstance(exc, (MarketError, NotSignedIn)) else
                            "Could not reach Warframe.Market.")
        self.table.state.error(retry=self.refresh)

    def _show(self, orders: list) -> None:
        self.orders = orders
        self._render()

    SORTABLE = {EYE, ITEM, TYPE, RANK, PRICE, QTY}

    def sort_by(self, column: int) -> None:
        if column not in self.SORTABLE:
            return
        if column == self.sort_col:
            self.sort_desc = not self.sort_desc
        else:
            # Numbers start highest first (price, rank, quantity); names and state start A-Z / visible first.
            self.sort_col, self.sort_desc = column, column in (self.PRICE, self.RANK, self.QTY)
        self._update_header()
        self._render()

    def _update_header(self) -> None:
        show_sort(self.table, self.sort_col, self.sort_desc)

    def sort_key(self, order: MyOrder):
        item = self.window_.by_id.get(order.item_id)
        name = (item.name if item else order.item_id).casefold()
        value = {
            self.EYE: 0 if order.visible else 1,
            self.ITEM: name,
            self.TYPE: order.type,
            self.RANK: -1 if order.rank is None else order.rank,
            self.PRICE: order.platinum,
            self.QTY: order.quantity,
        }[self.sort_col]
        return value

    def sorted_orders(self, orders: list[MyOrder]) -> list[MyOrder]:
        """Sort by the chosen column; ties keep visible orders first, then go by name."""
        def tie(o: MyOrder):
            item = self.window_.by_id.get(o.item_id)
            return (0 if o.visible else 1, (item.name if item else o.item_id).casefold())
        ordered = sorted(orders, key=tie)  # stable sorts: the tie order survives the main sort
        return sorted(ordered, key=self.sort_key, reverse=self.sort_desc)

    def filtered(self) -> list[MyOrder]:
        state, kind = self.state_filter.currentData(), self.type_filter.currentData()
        return [o for o in self.orders
                if (state is None or o.visible == state) and (kind is None or o.type == kind)]

    def _small_button(self, text: str, name: str = "ghost") -> QPushButton:
        b = QPushButton(text, objectName=name)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        return b

    def _render(self) -> None:
        self.shown = self.sorted_orders(self.filtered())
        # Drop the old rows (and their eye/button widgets) first: replacing widgets in place left
        # the previous row's eye drawn under the new one after a re-sort.
        for r in range(self.table.rowCount()):
            for c in (self.EYE, self.MATCH, self.DELETE):
                old = self.table.cellWidget(r, c)
                if old is not None:
                    old.hide()
        self.table.setRowCount(0)
        set_rows(self.table, len(self.shown))
        widths = {self.MATCH: 0, self.DELETE: 0}
        for r, o in enumerate(self.shown):
            item = self.window_.by_id.get(o.item_id)
            eye = icon_button("eye" if o.visible else "eye-off",
                              "Visible on Warframe.Market. Click to hide." if o.visible else
                              "Hidden from Warframe.Market. Click to show.")
            eye.clicked.connect(lambda _=False, order=o: self.toggle_visible(order))
            self.table.setCellWidget(r, self.EYE, eye)
            self.table.setItem(r, self.ITEM, make_cell(item.name if item else o.item_id,
                                                   color=None if o.visible else QColor(theme.TEXT_MUTED)))
            self.table.setItem(r, self.TYPE, make_cell(o.type.capitalize(), color=QColor(
                theme.POSITIVE if o.type == "sell" else theme.STATUS_ONLINE)))
            self.table.setItem(r, self.RANK, make_cell("" if o.rank is None else str(o.rank), right=True))
            self.table.setItem(r, self.PRICE, make_cell(str(o.platinum), right=True, icon=platinum_icon(14)))
            self.table.setItem(r, self.QTY, make_cell(str(o.quantity), right=True))
            match = self._small_button("Match lowest" if o.type == "sell" else "Match highest")
            match.clicked.connect(lambda _=False, order=o, b=match: (b.setText("Matching\…"), self.reprice(order)))
            delete = icon_button("trash", "Delete", theme.NEGATIVE)
            delete.clicked.connect(lambda _=False, order=o: self.delete(order))
            self.table.setCellWidget(r, self.MATCH, match)
            self.table.setCellWidget(r, self.DELETE, delete)
            for col, button in ((self.MATCH, match), (self.DELETE, delete)):
                button.ensurePolished()  # measure with the stylesheet applied, or "Match lowest" clips
                widths[col] = max(widths[col], button.sizeHint().width())
        # Size columns and rows to the buttons: the table only measures cell text, so buttons
        # placed in cells were clipped ("Match lowes", "Delet").
        header = self.table.horizontalHeader()
        for col, width in widths.items():
            if width:
                header.setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
                self.table.setColumnWidth(col, width + 40)  # room for the cell margins Qt adds
        self.table.setColumnWidth(self.EYE, 56)
        hidden = sum(not o.visible for o in self.orders)
        total = f"{len(self.orders)} orders" + (f", {hidden} hidden" if hidden else "")
        if not self.orders:
            if self.window_.account.signed_in:
                self.status.setText("You have no orders.")
                self.table.state.message("No orders yet. Post one from Sell.")
        elif not self.shown:
            self.status.setText(f"Showing 0 of {total}")
            self.table.state.message("No orders match these filters.")
        elif len(self.shown) != len(self.orders):
            self.status.setText(f"Showing {len(self.shown)} of {total}")
        else:
            self.status.setText(total)

    def toggle_visible(self, order: MyOrder) -> None:
        item = self.window_.by_id.get(order.item_id)
        name = item.name if item else "order"
        self.status.setText(f"{'Hiding' if order.visible else 'Showing'} {name}\…")
        self.window_.run_async(lambda: self.window_.account.update_order(order.id, visible=not order.visible),
                               lambda _: self.refresh(), self._failed)

    def reprice(self, order: MyOrder) -> None:
        item = self.window_.by_id.get(order.item_id)
        if item is None:
            return
        me = self.window_.account.ingame_name
        self.status.setText(f"Repricing {item.name}…")

        def work():
            top = top_orders(self.window_.sellers.client, item.slug, order.rank)
            price = suggested_price(top, order.type, 0, exclude=me)
            if price is None or price == order.platinum:
                return order, False
            return self.window_.account.update_order(order.id, platinum=price), True

        def done(result) -> None:
            updated, changed = result
            self.status.setText(f"{item.name}: now {updated.platinum}p." if changed else
                                f"{item.name}: already at the best price ({updated.platinum}p).")
            self.refresh()

        self.window_.run_async(work, done, self._failed)

    def delete(self, order: MyOrder) -> None:
        item = self.window_.by_id.get(order.item_id)
        self.status.setText("Deleting…")
        self.window_.run_async(lambda: self.window_.account.delete_order(order.id),
                               lambda _: (self.status.setText(f"Deleted {item.name if item else 'order'}."),
                                          self.refresh()),
                               self._failed)
