"""The Reports page: what can be exported, formats, folder, progress, results (D-165)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from budget_core.reports.run import REPORT_KINDS
from budget_gui.main_window import MainWindow
from budget_gui.reports_view import ReportItem, ReportsView
from budget_gui.theme import Status

pytestmark = pytest.mark.gui

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", tmp_path / "p")
    return tmp_path / "p"


@pytest.fixture
def window(qtbot, project: Path) -> MainWindow:  # type: ignore[no-untyped-def]
    w = MainWindow()
    qtbot.addWidget(w, before_close_func=lambda win: win.editors.discard_all_changes())
    w.open_project(project)
    return w


def wait_idle(qtbot, window: MainWindow) -> None:  # type: ignore[no-untyped-def]
    qtbot.waitUntil(lambda: not window._queue_active, timeout=60000)


def item(key: str, ready: bool = True, formats: bool = True) -> ReportItem:
    status = Status.PASS if ready else Status.NOT_CHECKED
    return ReportItem(key, key.title(), "files", status, "Ready" if ready else "No", ready, formats)


def test_a_view_on_its_own_says_why_export_does_nothing(qtbot) -> None:  # type: ignore[no-untyped-def]
    view = ReportsView()
    qtbot.addWidget(view)
    assert not view.export_button.isEnabled()
    assert "Nothing is ready" in view.export_button.toolTip()
    view.set_items([item("budgets"), item("timeline", ready=False)])
    assert "Choose the folder" in view.export_button.toolTip()
    view.set_folder("/somewhere")
    assert view.export_button.isEnabled()
    for box in view.format_boxes.values():
        box.setChecked(False)
    assert not view.export_button.isEnabled() and "format" in view.export_button.toolTip()


def test_an_item_that_is_not_ready_cannot_be_ticked_and_choices_are_kept(qtbot) -> None:  # type: ignore[no-untyped-def]
    view = ReportsView()
    qtbot.addWidget(view)
    view.set_items([item("budgets"), item("timeline", ready=False)])
    assert view.selected_items() == {"budgets"}
    view._boxes["budgets"].setChecked(False)  # the user's choice
    view.set_items([item("budgets"), item("timeline")])  # the timeline is worked out
    assert view.selected_items() == {"timeline"}  # budgets stay unticked; the new item is ticked


def test_the_scenario_alone_needs_no_format(qtbot) -> None:  # type: ignore[no-untyped-def]
    view = ReportsView()
    qtbot.addWidget(view)
    view.set_items([item("budgets"), item("scenario", formats=False)])
    view.set_folder("/x")
    view._boxes["budgets"].setChecked(False)
    for box in view.format_boxes.values():
        box.setChecked(False)
    assert view.export_button.isEnabled()


def test_the_page_lists_what_the_project_can_write_and_the_provenance(window: MainWindow) -> None:
    view = window.reports_view
    assert [i.key for i in view._items] == ["budgets", "timeline", "scenario"]
    budgets, timeline, scenario = view._items
    assert budgets.ready and budgets.status is Status.NEAR  # placeholders in the mass margins
    assert not timeline.ready and "press Run" in timeline.status_text
    assert not scenario.ready and not scenario.formats
    names = [
        view.provenance_table.item(r, 0).text() for r in range(view.provenance_table.rowCount())
    ]
    assert names == ["Tool", "Project", "Project revision", "Scenario", "Generated (UTC)", "User"]


def test_run_makes_the_timeline_and_scenario_ready(window: MainWindow, qtbot) -> None:  # type: ignore[no-untyped-def]
    window.run_all()
    qtbot.waitUntil(lambda: all(i.ready for i in window.reports_view._items), timeout=120000)
    assert window.reports_view.selected_items() == {"budgets", "timeline", "scenario"}


def test_export_writes_the_chosen_parts_in_the_chosen_formats(
    window: MainWindow, qtbot, tmp_path: Path
) -> None:  # type: ignore[no-untyped-def]
    view = window.reports_view
    out = tmp_path / "out"
    view.set_folder(out)
    for kind in REPORT_KINDS:
        view.format_boxes[kind].setChecked(kind == "csv")
    view.export_button.click()
    assert view.progress.isVisibleTo(view) and not view.export_button.isEnabled()
    wait_idle(qtbot, window)
    files = sorted(p.name for p in out.iterdir())
    assert files and all(name.endswith(".csv") for name in files)
    assert view.results.rowCount() == len(files)
    assert view.reveal_button.isEnabled() and not view.progress.isVisibleTo(view)
    assert str(len(files)) in view.status.text()
    assert view.export_button.isEnabled()  # ready for another


def test_a_run_then_export_of_everything_writes_the_timeline_and_scenario_too(
    window: MainWindow, qtbot, tmp_path: Path
) -> None:  # type: ignore[no-untyped-def]
    window.run_all()
    qtbot.waitUntil(lambda: all(i.ready for i in window.reports_view._items), timeout=120000)
    view = window.reports_view
    out = tmp_path / "all"
    view.set_folder(out)
    for kind in REPORT_KINDS:
        view.format_boxes[kind].setChecked(kind in ("csv", "json"))
    view.export_button.click()
    wait_idle(qtbot, window)
    names = {p.name for p in out.iterdir()}
    assert any(n.startswith("power_time_") for n in names)
    assert "one_day_environment.json" in names and "one_day_passes.csv" in names
    assert any(n.startswith("power_budget") or "power" in n for n in names)


def test_a_failure_to_write_is_said_on_the_page_not_in_a_box(
    window: MainWindow, qtbot, tmp_path: Path
) -> None:  # type: ignore[no-untyped-def]
    blocker = tmp_path / "file"
    blocker.write_text("not a folder")
    view = window.reports_view
    view.set_folder(blocker / "inside")
    view.export_button.click()
    wait_idle(qtbot, window)
    assert view.status.text() and "Wrote" not in view.status.text()
    assert view.export_button.isEnabled()


def test_reveal_opens_the_folder_of_the_files(
    window: MainWindow, qtbot, tmp_path: Path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    from PySide6.QtGui import QDesktopServices

    opened: list[str] = []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened.append(url.toLocalFile()))
    view = window.reports_view
    out = tmp_path / "r"
    view.set_folder(out)
    for kind in REPORT_KINDS:
        view.format_boxes[kind].setChecked(kind == "json")
    view.export_button.click()
    wait_idle(qtbot, window)
    view.reveal_button.click()
    assert [Path(p) for p in opened] == [out]  # Qt gives forward slashes, also on Windows
