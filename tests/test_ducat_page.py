import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication

from voidtrace.items import CatalogItem
from voidtrace.ui.ducats import DucatSection

CATALOG = [
    CatalogItem("Paris Prime Grip", "paris_prime_grip", None, ("prime", "component"), "id-grip"),
    CatalogItem("Caliban Prime Blueprint", "caliban_prime_blueprint", None, ("prime", "blueprint"), "id-bp"),
]
PAYLOAD = {"previous_day": [
    {"item": "id-grip", "ducats": 45, "wa_price": 4.0, "ducats_per_platinum_wa": 11.25, "volume": 234},
    {"item": "id-bp", "ducats": 45, "wa_price": 3.6, "ducats_per_platinum_wa": 12.5, "volume": 517},
]}


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class FakeClient:
    def __init__(self, fail=False):
        self.fail = fail
        self.calls = 0

    def get_v1(self, path):
        assert path == "/tools/ducats"
        self.calls += 1
        if self.fail:
            raise ConnectionError("offline")
        return PAYLOAD


def settle(qapp, condition, timeout=3.0):
    end = time.monotonic() + timeout
    while not condition() and time.monotonic() < end:
        qapp.processEvents()
        time.sleep(0.01)
    return condition()


def opened(qapp, client):
    section = DucatSection(CATALOG, client=client)
    section.show()
    section.page_shown("best")
    settle(qapp, lambda: not section.loading)
    return section


def names(page):
    return [page.table.item(i, page.NAME).text() for i in range(page.table.rowCount())]


def test_loads_best_ducats_per_plat_first(qapp):
    section = opened(qapp, FakeClient())
    assert names(section.best) == ["Caliban Prime Blueprint", "Paris Prime Grip"]
    assert section.best.status.text() == "2 parts · daily trade data"
    section.page_shown("best")  # within the hour: no second fetch
    assert section.client.calls == 1


def test_error_then_retry_loads(qapp):
    client = FakeClient(fail=True)
    section = opened(qapp, client)
    assert section.best.table.rowCount() == 0
    assert section.best.state.mode == "message" and section.best.state.button.isVisible()
    client.fail = False
    section.best.state.button.click()
    assert settle(qapp, lambda: section.best.table.rowCount() == 2)


def test_search_filters_and_says_when_nothing_matches(qapp):
    section = opened(qapp, FakeClient())
    section.best.search.setText("paris")
    assert names(section.best) == ["Paris Prime Grip"]
    section.best.search.setText("zzz")
    assert section.best.table.rowCount() == 0
    assert section.best.state.text.text() == "No parts match"


def test_sort_by_header_and_double_click_opens_item(qapp):
    section = opened(qapp, FakeClient())
    section.best.sort_by(section.best.NAME)
    assert names(section.best) == ["Caliban Prime Blueprint", "Paris Prime Grip"]
    section.best.sort_by(section.best.NAME)
    assert names(section.best) == ["Paris Prime Grip", "Caliban Prime Blueprint"]
    opened_slugs = []
    section.open_item.connect(opened_slugs.append)
    section.best.table.cellDoubleClicked.emit(0, 0)
    assert opened_slugs == ["paris_prime_grip"]


def test_empty_answer_says_so_instead_of_loading_forever(qapp):
    client = FakeClient()
    client.get_v1 = lambda path: {"previous_day": []}
    section = opened(qapp, client)
    assert section.best.state.mode == "message"
    assert section.best.state.text.text() == "No ducat data right now"
