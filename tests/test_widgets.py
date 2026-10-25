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
