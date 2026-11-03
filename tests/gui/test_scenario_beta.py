"""The beta angle in the scenario window (2.2.0): a plot tab and a line in the Statistics tab."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from PySide6.QtWidgets import QTabWidget

from budget_core.scenario.statistics import scenario_statistics
from budget_gui.main_window import MainWindow

pytestmark = pytest.mark.gui

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


@pytest.fixture
def window(qtbot, tmp_path: Path):  # type: ignore[no-untyped-def]
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", tmp_path / "p")
    w = MainWindow()
    qtbot.addWidget(w, before_close_func=lambda win: win.editors.discard_all_changes())
    w.open_project(tmp_path / "p")
    return w


def _compute(window: MainWindow, qtbot) -> None:  # type: ignore[no-untyped-def]
    window.scenario_view.compute()
    qtbot.waitUntil(lambda: not window.scenario_view.is_busy(), timeout=120000)
    assert window.scenario_view.last_run is not None


def _tab_names(view) -> list[str]:  # type: ignore[no-untyped-def]
    tabs = view.findChildren(QTabWidget)[0]
    return [tabs.tabText(i) for i in range(tabs.count())]


def test_there_is_a_beta_angle_tab(window: MainWindow) -> None:
    assert "Beta angle" in _tab_names(window.scenario_view)


def test_the_plot_shows_the_series_after_compute(window: MainWindow, qtbot) -> None:  # type: ignore[no-untyped-def]
    _compute(window, qtbot)
    plot = window.scenario_view.beta_plot_widget
    assert plot.accessibleName() == "Beta angle plot"
    spec = plot._spec
    assert spec is not None and len(spec.panels[0].series) == 1


def test_the_statistics_say_the_beta_angle_and_the_critical_one(  # type: ignore[no-untyped-def]
    window: MainWindow, qtbot
) -> None:
    _compute(window, qtbot)
    view = window.scenario_view
    run = view.last_run
    assert run is not None
    stats = scenario_statistics(run.env).beta
    assert stats is not None
    text = view.beta_label.text()
    assert "Beta angle" in text and f"{stats.critical_deg:.1f}" in text
    assert f"{stats.min_deg:.1f}" in text and f"{stats.max_deg:.1f}" in text


def test_the_plot_and_the_line_clear_with_the_results(window: MainWindow, qtbot) -> None:  # type: ignore[no-untyped-def]
    _compute(window, qtbot)
    window.scenario_view._show_run(None)
    assert window.scenario_view.beta_label.text() == ""
    assert window.scenario_view.beta_plot_widget._spec is None
