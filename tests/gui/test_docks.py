"""The right-hand docks, the Inspector, the Provenance panel and the saved layout (UX step 1)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from budget_gui.layout_settings import LayoutSettings
from budget_gui.main_window import MainWindow
from budget_gui.problem_class import ProblemClass

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


@pytest.fixture
def window(qtbot) -> MainWindow:  # type: ignore[no-untyped-def]
    w = MainWindow()
    qtbot.addWidget(w)
    w.resize(1400, 860)
    w.show()
    w.open_project(EXAMPLES / "microsat_250kg_eps")
    return w


def test_the_inspector_and_provenance_share_the_right_panel_and_problems_runs_along_the_bottom(
    window: MainWindow,
) -> None:
    window.resize(1600, 900)  # the inspector waits below 1520 px
    QApplication.processEvents()
    right = Qt.DockWidgetArea.RightDockWidgetArea
    for dock in (window.inspector_dock, window.provenance_dock):
        assert window.dockWidgetArea(dock) is right
    assert window.provenance_dock in window.tabifiedDockWidgets(window.inspector_dock)
    assert window.dockWidgetArea(window.problems_dock) is Qt.DockWidgetArea.BottomDockWidgetArea
    assert window.dockWidgetArea(window.project_dock) is Qt.DockWidgetArea.LeftDockWidgetArea
    # the bottom panel runs under the side panels, the full width of the window
    assert window.problems_dock.width() > window.width() - 2 * window.rail.width()


def test_every_dock_has_a_name_for_the_saved_layout(window: MainWindow) -> None:
    names = {
        d.objectName()
        for d in (
            window.project_dock,
            window.inspector_dock,
            window.problems_dock,
            window.provenance_dock,
            window.explain_dock,
        )
    }
    assert names == {
        "dock-project",
        "dock-inspector",
        "dock-problems",
        "dock-provenance",
        "dock-explain",
    }


def test_the_inspector_follows_the_tree(window: MainWindow) -> None:
    assert not window.inspector.details.isHidden() or window.inspector.empty.isHidden() is False
    item = window.tree.find_item("units/radio.yaml", kind="unit")
    assert item is not None
    window.tree.setCurrentItem(item)
    inspector = window.inspector
    assert inspector.title.text() == "S-band transceiver  ·  radio"
    assert inspector.file_label.text() == "File: units/radio.yaml"
    assert inspector.problems.count() == 1 and "1 error" in inspector.counts_label.text()
    assert not inspector.empty.isVisibleTo(window)


def test_the_inspector_lists_what_is_wrong_and_jumps(window: MainWindow) -> None:
    item = window.tree.find_item("units/radio.yaml", kind="unit")
    assert item is not None
    window.tree.setCurrentItem(item)
    window.inspector.problems.setCurrentRow(0)
    window.inspector._problem_activated(window.inspector.problems.item(0))
    editor = window.editors.current_editor()
    assert editor is not None and editor.rel_path == "units/radio.yaml"


def test_the_inspector_open_button_opens_the_node(window: MainWindow) -> None:
    item = window.tree.find_item("config/power_system.yaml", "solar_array", kind="field")
    assert item is not None
    window.tree.setCurrentItem(item)
    window.inspector.open_button.click()
    editor = window.editors.current_editor()
    assert editor is not None and editor.rel_path == "config/power_system.yaml"


def test_a_unit_node_offers_its_power_modes(window: MainWindow) -> None:
    item = window.tree.find_item("units/radio.yaml", kind="unit")
    assert item is not None
    window.tree.setCurrentItem(item)
    assert not window.inspector.modes_button.isHidden()
    window.inspector.modes_button.click()
    assert window.editors.currentWidget() is window.modes_page


def test_a_group_node_shows_the_problems_of_its_children(window: MainWindow) -> None:
    top = window.tree.topLevelItem(0)
    assert top is not None
    window.tree.setCurrentItem(top)
    counts = window.problems_panel.counts()
    assert window.inspector.problems.count() == sum(counts.values())


def test_the_provenance_panel_shows_the_rows_every_export_carries(window: MainWindow) -> None:
    table = window.provenance_panel.table
    names = [table.item(r, 0).text() for r in range(table.rowCount())]
    assert names[0] == "Tool" and "Project revision" in names and "Libraries" in names


def test_the_status_link_raises_the_problems_tab(window: MainWindow) -> None:
    window.inspector_dock.raise_()
    window.status_bar.not_checked.click()
    assert window.problems_dock.isVisible()
    assert window.problems_panel.class_filter() is ProblemClass.NOT_CHECKED


def test_next_and_previous_problem_open_the_file(window: MainWindow) -> None:
    window.next_problem(1)
    editor = window.editors.current_editor()
    first = window.problems_panel.current_problem()
    assert first is not None and first.file == "units/radio.yaml"  # the error comes first
    assert editor is not None and editor.rel_path == first.file
    window.next_problem(-1)  # wraps to the last one
    last = window.problems_panel.current_problem()
    assert last is window.problems_panel.visible_problems[-1]


def test_the_view_menu_has_the_docks_the_reset_and_the_problem_keys(window: MainWindow) -> None:
    view = window.view_menu
    texts = [a.text().replace("&", "") for a in view.actions()]
    for wanted in (
        "Project",
        "Inspector",
        "Problems",
        "Provenance",
        "Reset layout",
        "Next problem",
        "Previous problem",
    ):
        assert wanted in texts, wanted
    shortcuts = {a.text().replace("&", ""): a.shortcut().toString() for a in view.actions()}
    assert shortcuts["Next problem"] == "F8" and shortcuts["Previous problem"] == "Shift+F8"


# ---- the saved layout ------------------------------------------------------------------------
def test_the_layout_is_kept_between_two_windows(qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "layout.ini"
    first = MainWindow(LayoutSettings(path))
    qtbot.addWidget(first)
    first.resize(1100, 700)
    first.show()
    first.provenance_dock.hide()
    first.problems_panel.set_column_widths([40, 0, 200, 160])
    first.close()
    assert path.is_file()

    second = MainWindow(LayoutSettings(path))
    qtbot.addWidget(second)
    second.show()
    assert second.provenance_dock.isHidden()
    # the saved size, not the 1400 x 860 of a new window (the platform may adjust it a little)
    assert second.width() < 1300 and second.height() < 800
    assert second.problems_panel.column_widths()[2:] == [200, 160]


def test_the_layout_file_holds_no_project_content(qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "layout.ini"
    window = MainWindow(LayoutSettings(path))
    qtbot.addWidget(window)
    window.show()
    window.open_project(EXAMPLES / "microsat_250kg_eps")
    window.close()
    text = path.read_text(encoding="utf-8")
    assert "cubesat" not in text.lower() and str(EXAMPLES) not in text
    assert {line.split("=")[0].split("\\")[0] for line in text.splitlines() if "=" in line} <= {
        "geometry",
        "state",
        "problems",
        "rail",
        "start_here",
        "view",
        "open_with",
    }


def test_reset_layout_goes_back_and_forgets_the_saved_one(qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "layout.ini"
    window = MainWindow(LayoutSettings(path))
    qtbot.addWidget(window)
    window.show()
    window.provenance_dock.hide()
    window.inspector_dock.setFloating(True)
    window.save_layout()
    assert "dock" in path.read_text(encoding="utf-8")
    window.reset_layout()
    assert window.provenance_dock.isVisible() and not window.inspector_dock.isFloating()
    assert window.size().width() == 1400
    assert "state" not in path.read_text(encoding="utf-8")


def test_a_broken_layout_file_does_not_stop_the_window(qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "layout.ini"
    path.write_text("[dock]\nstate=@ByteArray(garbage)\n[window]\ngeometry=nonsense\n")
    window = MainWindow(LayoutSettings(path))
    qtbot.addWidget(window)
    window.show()
    window.open_project(EXAMPLES / "microsat_250kg_eps")  # the first screen has no panels
    assert window.problems_dock.isVisible() and window.project_dock.isVisible()
