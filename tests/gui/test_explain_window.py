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
