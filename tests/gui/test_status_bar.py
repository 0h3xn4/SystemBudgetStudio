"""The status bar: path, last run, version and the not-checked link (UX step 1, D-151)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from budget_core import __version__
from budget_gui.main_window import MainWindow
from budget_gui.problem_class import ProblemClass
from budget_gui.status_bar import AppStatusBar

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


def test_the_segments_say_what_they_hold(qtbot) -> None:  # type: ignore[no-untyped-def]
    bar = AppStatusBar()
    qtbot.addWidget(bar)
    assert bar.path_label.text() == "No project open" and not bar.last_run_label.text()
    assert f"{__version__}" in bar.version_label.text()
    folder = Path("/work/projects/satellite")
    bar.set_project_path(folder)
    assert bar.path_label.text() == str(folder)  # the platform's own separators
    bar.set_last_run(datetime(2026, 10, 13, 14, 2, 11))
    assert bar.last_run_label.text() == "Last run 14:02:11"
    assert "2026-10-13 14:02:11" in bar.last_run_label.toolTip()


def test_a_long_path_keeps_its_end_and_the_tooltip_has_all_of_it(qtbot) -> None:  # type: ignore[no-untyped-def]
    bar = AppStatusBar()
    qtbot.addWidget(bar)
    path = Path("/very/long/" + "folder/" * 20 + "my_satellite")
    bar.set_project_path(path)
    assert bar.path_label.text().startswith("…") and bar.path_label.text().endswith("my_satellite")
    assert bar.path_label.toolTip() == str(path)


def test_the_not_checked_link_appears_only_when_there_is_something_to_list(qtbot) -> None:  # type: ignore[no-untyped-def]
    bar = AppStatusBar()
    qtbot.addWidget(bar)
    bar.show()
    bar.set_not_checked(0)
    assert not bar.not_checked.isVisible()
    bar.set_not_checked(3)
    assert bar.not_checked.isVisible() and bar.not_checked.text() == "3 not checked"
    with qtbot.waitSignal(bar.not_checked_requested, timeout=1000):
        bar.not_checked.click()


@pytest.fixture
def window(qtbot) -> MainWindow:  # type: ignore[no-untyped-def]
    w = MainWindow()
    qtbot.addWidget(w)
    w.show()
    w.open_project(EXAMPLES / "microsat_250kg_eps")
    return w


def test_a_loaded_project_fills_the_segments(window: MainWindow) -> None:
    bar = window.status_bar
    assert bar.path_label.toolTip() == str(EXAMPLES / "microsat_250kg_eps")
    assert bar.last_run_label.text().startswith("Last run ")
    assert bar.not_checked.isVisible()
    expected = window.problems_panel.counts()[ProblemClass.NOT_CHECKED]
    assert bar.not_checked.text() == f"{expected} not checked" and expected > 0


def test_the_not_checked_link_filters_the_problems_panel(window: MainWindow) -> None:
    window.status_bar.not_checked.click()
    panel = window.problems_panel
    assert panel.class_filter() is ProblemClass.NOT_CHECKED
    assert panel.visible_problems and all(
        p.code in {"CONFIG_PLACEHOLDER", "RESULT_INCOMPLETE", "THERMAL_NO_LIMITS"}
        for p in panel.visible_problems
    )
    assert window.problems_dock.isVisible()


def test_closing_the_project_state_clears_the_run_time(window: MainWindow, tmp_path: Path) -> None:
    window.open_project(tmp_path / "does_not_exist")
    assert window.status_bar.last_run_label.text() == ""
