# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""The propulsion and pointing budgets in the window (2.3.0): a page each, in the Mass and Power
areas, with the tables of their reports and an honest empty sentence for a project without the
file."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from PySide6.QtWidgets import QTabWidget

from budget_gui.main_window import NO_POINTING_TEXT, NO_PROPULSION_TEXT, MainWindow

pytestmark = pytest.mark.gui

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


def _window(qtbot, folder: Path) -> MainWindow:  # type: ignore[no-untyped-def]
    window = MainWindow()
    qtbot.addWidget(window, before_close_func=lambda w: w.editors.discard_all_changes())
    window.show()
    window.open_project(folder)
    assert window.session.project is not None
    return window


def test_the_pages_sit_in_the_mass_and_power_areas(qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", tmp_path / "p")
    window = _window(qtbot, tmp_path / "p")
    mass, power = window.workspace.widget(2), window.workspace.widget(1)
    assert isinstance(mass, QTabWidget) and isinstance(power, QTabWidget)
    assert [mass.tabText(i) for i in range(mass.count())] == ["Budget", "Propulsion"]
    assert [power.tabText(i) for i in range(power.count())] == ["Budget", "Timeline", "Pointing"]
    for view in (window.propulsion_view, window.pointing_view):
        assert window.show_view(view)
        assert window.workspace.is_showing(view) and view.isVisible()


def test_the_pages_show_the_tables_of_the_reports(qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", tmp_path / "p")
    window = _window(qtbot, tmp_path / "p")
    assert window.propulsion_view.count() > 0 and window.pointing_view.count() > 0
    titles = [window.propulsion_view.tabText(i) for i in range(window.propulsion_view.count())]
    assert "Summary" in titles
    assert window.session.propulsion_document is not None
    assert window.session.pointing_document is not None
    assert not window.propulsion_view.empty_label.isVisibleTo(window.propulsion_view)


def test_a_project_without_the_files_says_so(qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", tmp_path / "p")
    (tmp_path / "p" / "config" / "propulsion.yaml").unlink()
    (tmp_path / "p" / "config" / "pointing.yaml").unlink()
    window = _window(qtbot, tmp_path / "p")
    assert window.propulsion_view.count() == 0 and window.pointing_view.count() == 0
    assert window.propulsion_view.empty_label.text() == NO_PROPULSION_TEXT
    assert window.pointing_view.empty_label.text() == NO_POINTING_TEXT


def test_the_reports_page_writes_both(qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", tmp_path / "p")
    window = _window(qtbot, tmp_path / "p")
    prefixes = {o.prefix for o in window.session.outputs}
    assert {"propulsion", "pointing"} <= prefixes
