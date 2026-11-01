"""The main window: how pages get opened, relic pages loading lazily, arrow-key navigation."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QLabel

from voidtrace import settings
from tests.test_relic_pages import ITEMS, OLD, OPEN, FakePrices
from voidtrace.items import CatalogItem
from voidtrace.ui.relics import RelicSection
from voidtrace.ui.widgets import Section


@pytest.fixture(autouse=True)
def own_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    return tmp_path


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


# --- relic prices: one cache read, nothing fetched while hidden ---

class CountingPrices(FakePrices):
    def __init__(self):
        super().__init__()
        self.cache_reads = 0

    def cached(self, slug):
        raise AssertionError("cached() once per slug: use cached_many()")

    def cached_many(self, slugs):
        self.cache_reads += 1
        return {}


def test_relic_table_reads_the_price_cache_once(qapp):
    prices = CountingPrices()
    section = RelicSection(ITEMS, prices, [OPEN, OLD])
    section.show()
    section.show_page("unvaulted")
    assert prices.cache_reads == 1
    section.shutdown()


def test_hidden_relic_pages_fetch_nothing(qapp):
    prices = FakePrices()
    section = RelicSection(ITEMS, prices, [OPEN, OLD])  # the Look up page picks a relic at start
    section.show_page("vaulted")
    assert section.data.requested == set() and prices.asked == []
    section.show()
    section.show_page("vaulted")
    assert section.data.requested
    section.shutdown()


# --- the main window's entry points ---

class FakeAccount:
    signed_in = False
    ingame_name = None


class FakeSellers:
    client = None

    def sellers(self, slug, rank=None, include_online=True):
        return []


class FakeRivens(Section):
    PAGES = {"find": "Find", "price": "Price check", "sell": "Sell", "mine": "My rivens"}

    def __init__(self):
        super().__init__()
        self.calls = []
        for key in self.PAGES:
            self.add_page(key, QLabel(key))

        class Panel:
            def run_check(inner):
                self.calls.append("run_check")

        self.price_panel = Panel()

    def load_draft(self, draft):
        self.calls.append(("draft", draft))

    def read_from_frame(self, frame):
        self.calls.append(("frame", frame))


def make_window(prices=None, last=None):
    from voidtrace.ui.main_window import MainWindow
    from voidtrace.ui.market import MarketSection

    if last:
        settings.put("last_page", last)
    item = CatalogItem("Volt Prime Set", "volt_prime_set", None, ("set",), "id")
    market = MarketSection([item], FakeSellers(), account=FakeAccount())
    relics = RelicSection(ITEMS, prices or FakePrices(), [OPEN, OLD])
    rivens = FakeRivens()
    return MainWindow(market, relics, load_riven_data=lambda: "d", make_rivens=lambda d: rivens), rivens


def wait(qapp, cond, timeout=3.0):
    import time

    end = time.monotonic() + timeout
    while not cond() and time.monotonic() < end:
        qapp.processEvents()
        time.sleep(0.01)
    return cond()


def test_hidden_window_on_a_relic_page_fetches_nothing_until_shown(qapp):
    prices = FakePrices()
    window, _ = make_window(prices, last="relics/vaulted")
    assert window.relics.data.requested == set()
    window.open_page()
    assert wait(qapp, lambda: bool(prices.asked))
    window.shutdown()


def test_riven_hotkey_reads_into_price_check(qapp):
    window, rivens = make_window()
    window.read_riven("FRAME")
    assert wait(qapp, lambda: ("frame", "FRAME") in rivens.calls)
    assert window.current_page() == "rivens/price" and window.isVisible()
    window.hide()


def test_riven_popup_opens_price_check_with_the_draft(qapp):
    window, rivens = make_window()
    window.open_riven_draft("DRAFT")
    assert wait(qapp, lambda: rivens.calls[-2:] == [("draft", "DRAFT"), "run_check"])
    assert window.current_page() == "rivens/price"
    window.hide()


def test_reward_card_opens_its_item_on_buy(qapp):
    window, _ = make_window(last="relics/vaulted")
    window.open_item("volt_prime_set")
    assert window.current_page() == "market/buy"
    assert window.market.item.slug == "volt_prime_set"
    window.hide()


def test_open_page_without_a_key_reopens_the_last_page(qapp):
    window, _ = make_window(last="market/trades")
    window.open_page()
    assert window.current_page() == "market/trades" and window.isVisible()
    window.hide()


# --- the status line only mentions missing prices when some are missing ---

def test_relic_status_line_without_missing_prices(qapp):
    section = RelicSection(ITEMS, FakePrices(), [OPEN])
    section.show()
    section.show_page("unvaulted")
    section.data.executor.shutdown(wait=True)
    qapp.processEvents()
    section.unvaulted.render()
    assert section.unvaulted.status.text() == "1 relics · double-click one for its rewards"
    section.shutdown()


# --- keyboard: arrow keys move between page tabs and rail sections ---

def test_tab_arrow_keys_open_the_page(qapp):
    window, _ = make_window(last="market/buy")
    tab = window.tabs["market/buy"]
    tab.setFocus()
    QTest.keyClick(tab, Qt.Key.Key_Right)
    assert window.current_page() == "market/sell"
    QTest.keyClick(window.tabs["market/sell"], Qt.Key.Key_Left)
    assert window.current_page() == "market/buy"
    window.hide()


def test_rail_arrow_keys_open_the_next_section(qapp):
    window, _ = make_window(last="market/buy")
    QTest.keyClick(window.tiles["market"], Qt.Key.Key_Down)
    assert window.current_page().startswith("rivens/")
    QTest.keyClick(window.tiles["rivens"], Qt.Key.Key_Down)
    assert window.current_page().startswith("relics/")


# --- searching from another Market page shows the item ---

def test_search_from_trades_page_shows_buy(qapp):
    window, _ = make_window(last="market/trades")
    window.market.open_item("volt_prime_set")
    assert window.market.current_page() == "buy"
    assert window.current_page() == "market/buy"


def test_window_opens_maximized(qapp):
    window, _ = make_window()
    window.open_page("market/buy")
    assert window.windowState() & Qt.WindowState.WindowMaximized
    window.hide()
