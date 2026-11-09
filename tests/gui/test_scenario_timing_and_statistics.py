# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""The scenario editor edits the start, the duration and the step; the Scenario page shows
statistics of the eclipses and passes and a filter on the passes (2.1.0)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from budget_core.io.project_loader import load_project
from budget_core.scenario.statistics import scenario_statistics
from budget_gui.main_window import MainWindow
from budget_gui.scenario_editor import ScenarioEditor

pytestmark = pytest.mark.gui

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
REL = "scenarios/one_day.yaml"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", tmp_path / "p")
    return tmp_path / "p"


@pytest.fixture
def window(qtbot, project: Path):  # type: ignore[no-untyped-def]
    w = MainWindow()
    qtbot.addWidget(w, before_close_func=lambda win: win.editors.discard_all_changes())
    w.open_project(project)
    return w


@pytest.fixture
def editor(window: MainWindow) -> ScenarioEditor:
    return window.scenario_view.editor


def _compute(window: MainWindow, qtbot) -> None:  # type: ignore[no-untyped-def]
    window.scenario_view.compute()
    qtbot.waitUntil(lambda: not window.scenario_view.is_busy(), timeout=120000)
    assert window.scenario_view.last_run is not None


# ---- the time span --------------------------------------------------------------------------


def test_the_editor_shows_the_start_the_duration_and_the_step(
    editor: ScenarioEditor, window: MainWindow
) -> None:
    data = window.document.data(REL)
    assert editor.start_utc.text() == data["start_utc"]
    assert editor.duration_s.value() == pytest.approx(data["duration_s"])
    assert editor.step_s.value() == pytest.approx(data["step_s"])
    assert editor.duration_s.suffix().strip() == "s" and editor.step_s.suffix().strip() == "s"


def test_a_new_duration_is_one_undo_step(editor: ScenarioEditor, window: MainWindow) -> None:
    before = window.document.undo_stack.count()
    old = window.document.data(REL)["duration_s"]
    editor.duration_s.setValue(43200.0)
    editor.duration_s.editingFinished.emit()
    assert window.document.undo_stack.count() == before + 1
    assert window.document.data(REL)["duration_s"] == 43200.0
    window.undo_action.trigger()
    assert window.document.data(REL)["duration_s"] == old
    assert editor.duration_s.value() == pytest.approx(old)


def test_a_new_step_and_a_new_start_are_edits_too(
    editor: ScenarioEditor, window: MainWindow
) -> None:
    editor.step_s.setValue(30.0)
    editor.step_s.editingFinished.emit()
    editor.start_utc.setText("2026-09-01T06:00:00Z")
    editor.start_utc.editingFinished.emit()
    data = window.document.data(REL)
    assert data["step_s"] == 30.0 and data["start_utc"] == "2026-09-01T06:00:00Z"
    assert not window.document.problems(REL)


def test_a_start_that_is_not_a_time_is_kept_with_its_problem_and_can_be_undone(
    editor: ScenarioEditor, window: MainWindow
) -> None:
    old = window.document.data(REL)["start_utc"]
    editor.start_utc.setText("next tuesday")
    editor.start_utc.editingFinished.emit()
    assert window.document.problems(REL)
    assert "start_utc" in editor.error_label.text()
    window.undo_action.trigger()
    assert window.document.data(REL)["start_utc"] == old and not window.document.problems(REL)


def test_a_step_longer_than_the_duration_is_a_problem_not_a_crash(
    editor: ScenarioEditor, window: MainWindow
) -> None:
    editor.duration_s.setValue(600.0)
    editor.duration_s.editingFinished.emit()
    editor.step_s.setValue(1200.0)
    editor.step_s.editingFinished.emit()
    assert window.document.problems(REL)


def test_an_unchanged_value_is_no_undo_step(editor: ScenarioEditor, window: MainWindow) -> None:
    before = window.document.undo_stack.count()
    editor.duration_s.editingFinished.emit()
    editor.step_s.editingFinished.emit()
    editor.start_utc.editingFinished.emit()
    assert window.document.undo_stack.count() == before


def test_save_writes_the_new_span(
    editor: ScenarioEditor, window: MainWindow, project: Path
) -> None:
    editor.duration_s.setValue(43200.0)
    editor.duration_s.editingFinished.emit()
    assert window.save_model()
    assert load_project(project).project.scenarios["one_day"].duration_s == 43200.0  # type: ignore[union-attr]


# ---- the statistics -------------------------------------------------------------------------


def test_the_statistics_tab_has_a_row_per_site_and_the_eclipse_figures(
    window: MainWindow, qtbot
) -> None:  # type: ignore[no-untyped-def]
    _compute(window, qtbot)
    view = window.scenario_view
    run = view.last_run
    assert run is not None
    stats = scenario_statistics(run.env)
    assert view.site_stats_table.rowCount() == len(stats.sites)
    sites = [
        view.site_stats_table.item(r, 0).text() for r in range(view.site_stats_table.rowCount())
    ]
    assert sites == [s.site_id for s in stats.sites]
    text = view.eclipse_stats_label.text()
    assert str(stats.eclipses.durations.count) in text
    assert "longest" in text.lower()


def test_a_site_row_shows_the_passes_the_contact_and_the_largest_gap(
    window: MainWindow, qtbot
) -> None:  # type: ignore[no-untyped-def]
    _compute(window, qtbot)
    view = window.scenario_view
    run = view.last_run
    assert run is not None
    stats = scenario_statistics(run.env)
    headers = [
        view.site_stats_table.horizontalHeaderItem(c).text()
        for c in range(view.site_stats_table.columnCount())
    ]
    assert "Passes" in headers and "Largest gap (s)" in headers
    first = stats.sites[0]
    row = {h: view.site_stats_table.item(0, c).text() for c, h in enumerate(headers)}
    assert row["Passes"] == str(first.passes.count)
    assert float(row["Largest gap (s)"]) == pytest.approx(first.largest_gap_s, abs=0.06)


def test_the_passes_filter_shows_one_site_or_all(window: MainWindow, qtbot) -> None:  # type: ignore[no-untyped-def]
    _compute(window, qtbot)
    view = window.scenario_view
    run = view.last_run
    assert run is not None
    total = sum(len(v.passes) for v in run.env.sites.values())
    assert view.passes_table.rowCount() == total  # all sites by default
    site = next(s for s, v in sorted(run.env.sites.items()) if v.passes)
    view.passes_filter.setCurrentText(site)
    assert view.passes_table.rowCount() == len(run.env.sites[site].passes)
    assert {view.passes_table.item(r, 0).text() for r in range(view.passes_table.rowCount())} == {
        site
    }
    view.passes_filter.setCurrentIndex(0)
    assert view.passes_table.rowCount() == total


def test_a_new_computation_keeps_the_chosen_site_when_it_still_exists(
    window: MainWindow, qtbot
) -> None:  # type: ignore[no-untyped-def]
    _compute(window, qtbot)
    view = window.scenario_view
    assert view.last_run is not None
    site = next(s for s, v in sorted(view.last_run.env.sites.items()) if v.passes)
    view.passes_filter.setCurrentText(site)
    _compute(window, qtbot)
    assert view.passes_filter.currentText() == site


def test_the_json_file_of_a_scenario_has_the_statistics(
    window: MainWindow, qtbot, tmp_path: Path
) -> None:  # type: ignore[no-untyped-def]
    import json

    _compute(window, qtbot)
    files = window.scenario_view.export_to(tmp_path / "out")
    data = json.loads(next(p for p in files if p.name.endswith("_environment.json")).read_text())
    assert "statistics" in data and data["statistics"]["eclipses"]["count"] >= 1
