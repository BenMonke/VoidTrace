import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication

from voidtrace.ui.widgets import Segmented, Stepper, make_table, set_rows


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_table_state_shows_loading_then_rows_replace_it(qapp):
    table = make_table(["A", "B"])
    table.state.loading()
    assert table.state.mode == "loading" and table.rowCount() == 0
    set_rows(table, 2)
    assert table.state.mode == ""


def test_table_error_keeps_rows_already_shown(qapp):
    table = make_table(["A"])
    retried = []
    table.state.error(retry=lambda: retried.append(1))
    assert table.state.mode == "message" and table.state.button.text() == "Retry"
    table.state.button.click()
    assert retried == [1]
    set_rows(table, 1)
    table.state.error()
    assert table.state.mode == ""  # the rows stay; no message over them


def test_stepper_disables_the_button_at_its_limit(qapp):
    stepper = Stepper(1, 3, 1)
    assert not stepper.minus.isEnabled() and stepper.plus.isEnabled()
    stepper.setValue(3)
    assert stepper.minus.isEnabled() and not stepper.plus.isEnabled()


def test_segmented_reads_like_a_combo(qapp):
    seg = Segmented([("Sell", "sell"), ("Buy", "buy")])
    seen = []
    seg.currentIndexChanged.connect(seen.append)
    assert seg.currentData() == "sell"
    seg.setCurrentIndex(1)
    assert seg.currentData() == "buy" and seen == [1]


def test_confirm_price_only_asks_about_big_jumps(qapp, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox, QWidget

    from voidtrace.ui.widgets import confirm_price

    asked = []
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: asked.append(a) or QMessageBox.StandardButton.No)
    parent = QWidget()
    assert confirm_price(parent, "Volt Prime Set", 100, 60)       # small change: no question
    assert confirm_price(parent, "Volt Prime Set", 100, 190)
    assert not confirm_price(parent, "Volt Prime Set", 100, 1)    # troll price: asked, said no
    assert not confirm_price(parent, "Volt Prime Set", 100, 500)
    assert len(asked) == 2 and "100p to 1p" in asked[0][2]
