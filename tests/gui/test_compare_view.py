"""Compare tab: two revisions (project folders) or two scenarios side by side."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from PySide6.QtCore import Qt

from budget_gui import theme
from budget_gui.main_window import MainWindow
from tests.helpers import edit

pytestmark = pytest.mark.gui

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


@pytest.fixture
def window(qtbot) -> MainWindow:  # type: ignore[no-untyped-def]
    w = MainWindow()
    qtbot.addWidget(w, before_close_func=lambda win: win.editors.discard_all_changes())
    return w


@pytest.fixture
def revisions(tmp_path: Path) -> tuple[Path, Path]:
    a, b = tmp_path / "rev1", tmp_path / "rev2"
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", a)
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", b)
    edit(b, "units/adcs.yaml", "avg_power_w: 7.0", "avg_power_w: 9.0")
    edit(b, "project.yaml", "revision: '1'", "revision: '2'")
    return a, b


def run_compare(window: MainWindow, qtbot) -> None:  # type: ignore[no-untyped-def]
    with qtbot.waitSignal(window.compare_view.computed, timeout=120000):
        window.compare_view.compare()


def test_tab_is_disabled_without_a_project(window: MainWindow) -> None:
    view = window.compare_view
    assert not view.compare_button.isEnabled()
    assert view.table.rowCount() == 0


def test_compare_two_revisions_highlights_the_difference(
    window: MainWindow,
    revisions: tuple[Path, Path],
    qtbot,  # type: ignore[no-untyped-def]
) -> None:
    a, b = revisions
    window.open_project(a)
    view = window.compare_view
    assert view.compare_button.isEnabled()
    view.set_other_folder(b)
    run_compare(window, qtbot)
    assert view.table.rowCount() > 0
    assert "differ" in view.status.text()
    statuses = {view.table.item(r, 8).text() for r in range(view.table.rowCount())}
    assert "changed" in statuses
    assert view.export_button.isEnabled()
    # a changed row is tinted so it stands out
    row = next(r for r in range(view.table.rowCount()) if view.table.item(r, 8).text() == "changed")
    assert view.table.item(row, 0).background().color().name() != "#000000"


def test_identical_revisions_report_no_differences(
    window: MainWindow,
    revisions: tuple[Path, Path],
    qtbot,  # type: ignore[no-untyped-def]
) -> None:
    a, _ = revisions
    window.open_project(a)
    window.compare_view.set_other_folder(a)
    run_compare(window, qtbot)
    assert window.compare_view.table.rowCount() == 0
    assert "No differences" in window.compare_view.status.text()


def test_unloadable_other_project_says_so_plainly(
    window: MainWindow,
    revisions: tuple[Path, Path],
    tmp_path: Path,
    qtbot,  # type: ignore[no-untyped-def]
) -> None:
    a, b = revisions
    edit(b, "units/adcs.yaml", "avg_power_w: 9.0", "avg_power_w: 99.9")
    window.open_project(a)
    window.compare_view.set_other_folder(b)
    with qtbot.waitSignal(window.compare_view.compute_failed, timeout=60000):
        window.compare_view.compare()
    assert "cannot be compared" in window.compare_view.status.text()


def test_scenarios_of_one_project(window: MainWindow, tmp_path: Path, qtbot) -> None:  # type: ignore[no-untyped-def]
    root = tmp_path / "p"
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", root)
    shutil.copy(root / "scenarios/one_day.yaml", root / "scenarios/variant.yaml")
    edit(root, "scenarios/variant.yaml", "default_mode: charging", "default_mode: safe")
    window.open_project(root)
    view = window.compare_view
    view.scenario_a.setCurrentText("one_day")
    view.scenario_b.setCurrentText("variant")
    run_compare(window, qtbot)
    assert view.table.rowCount() > 0


def test_export_writes_the_comparison(
    window: MainWindow,
    revisions: tuple[Path, Path],
    tmp_path: Path,
    qtbot,  # type: ignore[no-untyped-def]
) -> None:
    a, b = revisions
    window.open_project(a)
    window.compare_view.set_other_folder(b)
    run_compare(window, qtbot)
    with qtbot.waitSignal(window.compare_view.export_finished, timeout=60000):
        window.compare_view.export_to(tmp_path / "out", {"csv", "json"})
    assert (tmp_path / "out" / "compare_differences.csv").is_file()


def test_the_sides_say_their_revision_and_the_columns_are_named_after_them(
    window: MainWindow,
    revisions: tuple[Path, Path],
    qtbot,  # type: ignore[no-untyped-def]
) -> None:
    a, b = revisions
    window.open_project(a)
    view = window.compare_view
    assert "revision 1" in view.side_a_label.text()
    view.set_other_folder(b)
    run_compare(window, qtbot)
    assert "revision 2" in view.side_b_label.text()
    headers = [view.table.horizontalHeaderItem(c).text() for c in (4, 5)]
    assert headers == ["A: rev 1", "B: rev 2"]


def test_the_filter_shows_one_kind_of_difference(
    window: MainWindow,
    revisions: tuple[Path, Path],
    qtbot,  # type: ignore[no-untyped-def]
) -> None:
    a, b = revisions
    window.open_project(a)
    view = window.compare_view
    assert not view.filter_combo.isEnabled()
    view.set_other_folder(b)
    run_compare(window, qtbot)
    assert view.filter_combo.isEnabled()
    everything = view.table.rowCount()
    view.filter_combo.setCurrentText("added")
    assert view.table.rowCount() < everything
    assert {view.table.item(r, 8).text() for r in range(view.table.rowCount())} <= {"added"}
    view.filter_combo.setCurrentText("All differences")
    assert view.table.rowCount() == everything


def test_the_figures_are_right_aligned_in_the_mono_font(
    window: MainWindow,
    revisions: tuple[Path, Path],
    qtbot,  # type: ignore[no-untyped-def]
) -> None:
    a, b = revisions
    window.open_project(a)
    window.compare_view.set_other_folder(b)
    run_compare(window, qtbot)
    item = window.compare_view.table.item(0, 4)
    assert item.textAlignment() & Qt.AlignmentFlag.AlignRight
    assert item.font().family() == theme.mono_font().family()
