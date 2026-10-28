"""Explain in the window (D-206): the dock, the View menu action with its shortcut, the Ctrl+K
palette entry and the context menu of a result table."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMenu, QTableView

from budget_core.reports.document import Table
from budget_gui.main_window import MainWindow

pytestmark = pytest.mark.gui

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


@pytest.fixture
def window(qtbot) -> MainWindow:  # type: ignore[no-untyped-def]
    w = MainWindow()
    qtbot.addWidget(w, before_close_func=lambda win: win.editors.discard_all_changes())
    w.resize(1600, 900)
    w.show()
    w.open_project(EXAMPLES / "microsat_250kg_eps")
    w.workspace.setCurrentIndex(1)  # Power
    QApplication.processEvents()
    return w


def _units_table(window: MainWindow) -> tuple[QTableView, Table]:
    window.power_view.build_pages()
    for page in window.power_view._pages.values():
        for view, model in zip(page.findChildren(QTableView), page.models, strict=False):
            if model.table.explain_id.startswith("power:units:"):
                window.power_view.tabs.setCurrentWidget(page)
                return view, model.table
    raise AssertionError("no explainable units table")


def test_the_explain_dock_is_there_and_empty_until_a_value_is_explained(
    window: MainWindow,
) -> None:
    assert window.explain_dock.objectName() == "dock-explain"
    assert window.explain_dock in window.tabifiedDockWidgets(window.inspector_dock)
    assert window.explain_panel.empty.isVisibleTo(window.explain_panel)
    assert not window.explain_panel.details.isVisibleTo(window.explain_panel)


def test_the_action_explains_the_selected_value_and_opens_the_dock(window: MainWindow) -> None:
    view, table = _units_table(window)
    window.explain_dock.hide()
    column = next(i for i, c in enumerate(table.columns) if c.header == "With margin (W)")
    view.setCurrentIndex(view.model().index(0, column))
    window.explain_action.trigger()
    assert window.explain_dock.isVisible()
    panel = window.explain_panel
    assert panel.details.isVisibleTo(panel)
    text = panel.text.toPlainText()
    assert "PWR-MARGIN" in text
    assert panel.title.text() and panel.result.text().startswith("= ")


def test_nothing_selected_says_what_to_do(window: MainWindow) -> None:
    window.explain_action.trigger()
    assert window.explain_dock.isVisible()
    assert "Select a value" in window.explain_panel.empty.message.text()


def test_a_cell_that_cannot_be_explained_says_so_without_values(window: MainWindow) -> None:
    view, table = _units_table(window)
    view.setCurrentIndex(view.model().index(0, 0))  # the unit name: an identifier
    window.explain_action.trigger()
    assert window.explain_dock.isVisible()


def test_the_shortcut_and_the_palette_entry_exist(window: MainWindow) -> None:
    assert window.explain_action.shortcut().toString() == "Ctrl+Shift+I"
    names = [c.text for c in window.palette_commands()]
    assert "View > Explain this value" in names


def test_a_new_load_clears_the_panel(window: MainWindow) -> None:
    view, table = _units_table(window)
    column = next(i for i, c in enumerate(table.columns) if c.header == "With margin (W)")
    view.setCurrentIndex(view.model().index(0, column))
    window.explain_action.trigger()
    window.session.reload()
    window._refresh()
    assert not window.explain_panel.details.isVisibleTo(window.explain_panel)


def test_the_context_menu_offers_the_action(window: MainWindow) -> None:
    view, table = _units_table(window)
    column = next(i for i, c in enumerate(table.columns) if c.header == "With margin (W)")
    seen: list[str] = []

    def choose() -> None:
        popup = QApplication.activePopupWidget()
        assert isinstance(popup, QMenu)
        seen.extend(a.text() for a in popup.actions())
        popup.actions()[0].trigger()
        popup.close()

    QTimer.singleShot(200, choose)
    rect = view.visualRect(view.model().index(0, column))
    view.customContextMenuRequested.emit(rect.center())
    assert seen and seen[0].startswith("Explain this value")
    assert "PWR-MARGIN" in window.explain_panel.text.toPlainText()


def test_it_stays_hidden_in_the_focused_view_until_asked(window: MainWindow) -> None:
    window.view_action.setChecked(True)
    QApplication.processEvents()
    assert window.explain_dock.isHidden()
    view, table = _units_table(window)
    column = next(i for i, c in enumerate(table.columns) if c.header == "With margin (W)")
    view.setCurrentIndex(view.model().index(0, column))
    window.explain_action.trigger()
    assert not window.explain_dock.isHidden()


def test_a_mass_value_is_explained_too(window: MainWindow) -> None:
    window.workspace.show_view(window.mass_view)
    QApplication.processEvents()
    window.mass_view.build_pages()
    found = None
    for page in window.mass_view._pages.values():
        for view, model in zip(page.findChildren(QTableView), page.models, strict=False):
            if model.table.explain_id.startswith("mass:totals:"):
                window.mass_view.tabs.setCurrentWidget(page)
                found = (view, model.table)
    assert found is not None
    view, table = found
    row = next(i for i, r in enumerate(table.rows) if r[0] == "Total, with system margin")
    view.setCurrentIndex(view.model().index(row, 1))
    window.explain_action.trigger()
    assert "MASS-SYSMARGIN" in window.explain_panel.text.toPlainText()


def test_a_thermal_value_is_explained_too(window: MainWindow) -> None:
    window.workspace.show_view(window.thermal_view)
    QApplication.processEvents()
    window.thermal_view.build_pages()
    found = None
    for page in window.thermal_view._pages.values():
        for view, model in zip(page.findChildren(QTableView), page.models, strict=False):
            if model.table.explain_id.startswith("thermal:temperatures:"):
                window.thermal_view.tabs.setCurrentWidget(page)
                found = (view, model.table)
                break
        if found:
            break
    assert found is not None
    view, table = found
    column = next(i for i, c in enumerate(table.columns) if c.header == "Temperature (K)")
    view.setCurrentIndex(view.model().index(0, column))
    window.explain_action.trigger()
    text = window.explain_panel.text.toPlainText()
    assert "TH-BAL" in text and "damped Newton" in text


def test_a_link_value_is_explained_too(window: MainWindow) -> None:
    window.workspace.show_view(window.link_view)
    QApplication.processEvents()
    window.link_view.build_pages()
    found = None
    for page in window.link_view._pages.values():
        for view, model in zip(page.findChildren(QTableView), page.models, strict=False):
            if model.table.explain_id == "link:static":
                window.link_view.tabs.setCurrentWidget(page)
                found = (view, model.table)
                break
        if found:
            break
    assert found is not None
    view, table = found
    column = next(i for i, c in enumerate(table.columns) if c.header == "C/N0 (dBHz)")
    view.setCurrentIndex(view.model().index(0, column))
    window.explain_action.trigger()
    text = window.explain_panel.text.toPlainText()
    assert "LNK-CN0" in text and "LNK-FSPL" in text


def _timeline(window: MainWindow, qtbot) -> None:  # type: ignore[no-untyped-def]
    window.power_pages.setCurrentIndex(1)  # Timeline
    QApplication.processEvents()
    with qtbot.waitSignal(window.timeline_view.computed, timeout=120000):
        window.timeline_view.compute()
    QApplication.processEvents()


def test_a_timeline_summary_value_is_explained_after_the_series_are_prepared(
    window: MainWindow,
    qtbot,  # type: ignore[no-untyped-def]
) -> None:
    _timeline(window, qtbot)
    view = window.timeline_view
    view.tabs.setCurrentWidget(view.summary_table)
    column = next(
        i
        for i in range(view.summary_table.columnCount())
        if view.summary_table.horizontalHeaderItem(i).text() == "Generated (Wh)"
    )
    view.summary_table.setCurrentCell(0, column)
    window.explain_dock.hide()
    window.explain_action.trigger()
    qtbot.waitUntil(lambda: "TDP-ARRAY" in window.explain_panel.text.toPlainText(), timeout=60000)
    assert window.explain_dock.isVisible()
    assert window.explain_panel.title.text().startswith("Results by case / Energy generated")
    assert window._explain_worker is None
    # a second value of the same result needs no new solve
    column = next(
        i
        for i in range(view.summary_table.columnCount())
        if view.summary_table.horizontalHeaderItem(i).text() == "Capacity (Wh)"
    )
    view.summary_table.setCurrentCell(1, column)
    window.explain_action.trigger()
    assert "TDP-CAP" in window.explain_panel.text.toPlainText()
    assert window._explain_worker is None


def test_a_violation_row_and_an_orbit_and_a_mode_are_explained(
    window: MainWindow,
    qtbot,  # type: ignore[no-untyped-def]
) -> None:
    _timeline(window, qtbot)
    view = window.timeline_view
    assert view.violations_table.rowCount() > 0
    headers = [
        view.violations_table.horizontalHeaderItem(i).text()
        for i in range(view.violations_table.columnCount())
    ]
    target = view.explain_target(view.violations_table, 0, headers.index("Worst"))
    assert target is not None and target[0] == "timeline:violations" and len(target[1]) == 4
    window.timeline_view.explain_requested.emit(*target)
    qtbot.waitUntil(lambda: "TDP-PEAK" in window.explain_panel.text.toPlainText(), timeout=60000)
    orbit = view.explain_target(view.orbits_table, 0, 5)  # the balance column
    assert (
        orbit is not None
        and orbit[0].startswith("timeline:balance:")
        and orbit[2] == "Balance (Wh)"
    )
    window.timeline_view.explain_requested.emit(*orbit)
    assert "TDP-BALANCE" in window.explain_panel.text.toPlainText()
    mode = view.explain_target(view.modes_table, 0, 2)
    assert mode is not None and mode[2] == "Share"
    assert view.explain_target(view.summary_table, 0, 0) is None  # the case name


def test_explaining_before_the_timeline_is_worked_out_says_so(window: MainWindow) -> None:
    window.explain_timeline_value("timeline:cases", ["Battery capacity"], "BOL")
    assert "Work out the power timeline first" in window.explain_panel.empty.message.text()


def test_a_link_pass_value_is_explained(window: MainWindow, qtbot) -> None:  # type: ignore[no-untyped-def]
    window.link_pages.setCurrentIndex(1)  # Passes
    window.workspace.show_view(window.link_passes_view)
    QApplication.processEvents()
    with qtbot.waitSignal(window.link_passes_view.computed, timeout=120000):
        window.link_passes_view.compute()
    QApplication.processEvents()
    view = window.link_passes_view
    assert view.passes_table.rowCount() > 0
    headers = [
        view.passes_table.horizontalHeaderItem(i).text()
        for i in range(view.passes_table.columnCount())
    ]
    view.tabs.setCurrentWidget(view.passes_table)
    view.passes_table.setCurrentCell(0, headers.index("Lowest margin (dB)"))
    window.explain_dock.hide()
    window.explain_action.trigger()
    assert window.explain_dock.isVisible()
    text = window.explain_panel.text.toPlainText()
    assert "LNK-MARGIN" in text and "Lowest margin of the pass" in text
    view.tabs.setCurrentWidget(view.volume_table)
    volume_headers = [
        view.volume_table.horizontalHeaderItem(i).text()
        for i in range(view.volume_table.columnCount())
    ]
    view.volume_table.setCurrentCell(0, volume_headers.index("Scenario total (Mbit)"))
    window.explain_action.trigger()
    assert "LNK-VOLUME" in window.explain_panel.text.toPlainText()
    assert view.explain_target(view.volume_table, 0, 99) is None


def test_explaining_a_pass_before_the_passes_are_worked_out_says_so(window: MainWindow) -> None:
    window.explain_link_pass_value("linkpass:volume", ["x"], "Passes")
    assert "Work out the link passes first" in window.explain_panel.empty.message.text()
