# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""Clear words for the two kinds of mode, the rules of a scenario and two column headers (2.1.0).

A *power mode* is an operating state of one unit; a *spacecraft mode* sets the power mode of every
unit at once. The buttons, the pages and the rules say which one they mean."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from PySide6.QtCore import Qt

from budget_gui.main_window import MainWindow
from budget_gui.scenario_editor import RULE_KINDS, WHEN, rule_sentence

pytestmark = pytest.mark.gui

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


@pytest.fixture
def window(qtbot, tmp_path: Path):  # type: ignore[no-untyped-def]
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", tmp_path / "p")
    w = MainWindow()
    qtbot.addWidget(w, before_close_func=lambda win: win.editors.discard_all_changes())
    w.open_project(tmp_path / "p")
    return w


def _header_tip(model, title_part: str) -> str:  # type: ignore[no-untyped-def]
    for section in range(model.columnCount()):
        title = str(model.headerData(section, Qt.Orientation.Horizontal))
        if title_part in title:
            return str(
                model.headerData(section, Qt.Orientation.Horizontal, Qt.ItemDataRole.ToolTipRole)
            )
    raise AssertionError(f"no column {title_part!r}")


def test_the_buttons_say_which_mode_they_add_and_remove(window: MainWindow) -> None:
    power, spacecraft = window.modes_page, window.spacecraft_modes_page
    assert power.add_button.text() == "Add power mode"
    assert power.remove_button.text() == "Remove power mode"
    assert spacecraft.add_button.text() == "Add spacecraft mode"
    assert spacecraft.remove_button.text() == "Remove spacecraft mode"
    assert window.units_page.add_button.text() == "Add unit"


def test_each_modes_page_says_what_its_mode_is(window: MainWindow) -> None:
    power = window.modes_page.hint_label.text()
    spacecraft = window.spacecraft_modes_page.hint_label.text()
    assert "operating state of one unit" in power and "spacecraft mode" in power
    assert "every unit" in spacecraft and "power mode" in spacecraft


def test_the_hint_is_not_a_status_message(window: MainWindow) -> None:
    page = window.modes_page
    page.show_message("Added a mode.")
    assert page.hint_label.text()  # the hint stays when a message is shown


def test_a_rule_in_eclipse_says_it_lasts_the_whole_eclipse() -> None:
    assert rule_sentence({"kind": "in_eclipse", "mode": "imaging"}) == (
        "Imaging throughout every eclipse"
    )
    assert rule_sentence({"kind": "in_sunlight", "mode": "charging"}) == (
        "Charging throughout every sunlit period"
    )
    assert WHEN["during_pass"] == "during every pass over"
    assert set(WHEN) == set(RULE_KINDS)


def test_the_when_drop_down_explains_the_kinds(window: MainWindow) -> None:
    window.scenario_view.editor.add_rule()
    row = window.scenario_view.editor.rule_rows[-1]
    tip = row.when.toolTip()
    assert "whole" in tip and "eclipse" in tip and "manual segment" in tip
    assert "spacecraft mode" in row.mode.toolTip()


def test_the_mass_column_says_it_is_the_nominal_mass_before_margin(window: MainWindow) -> None:
    tip = _header_tip(window.units_page.units, "mass_kg")
    assert "nominal" in tip.lower() and "before margin" in tip


def test_the_bus_column_says_what_a_bus_is(window: MainWindow) -> None:
    tip = _header_tip(window.units_page.units, "bus")
    assert "power bus" in tip and "converter efficiency" in tip
    assert "inside a unit" in tip  # a voltage inside the unit is not modelled
