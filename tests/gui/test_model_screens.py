"""The Model screens after the overhaul: the toolbar above the grid, the frozen identifier
column, the problem marker in the row, row height 26 and the cost of scrolling (D-176, D-177)."""

from __future__ import annotations

import shutil
import time
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from budget_core.io.project_loader import load_project
from budget_gui import theme
from budget_gui.delegates import CELL_ROLE, STATE_ROLE
from budget_gui.grid_view import GridPage
from budget_gui.model_document import ModelDocument
from budget_gui.model_pages import InputsPage, PowerModesPage, UnitsPage
from budget_gui.theme import Status

pytestmark = pytest.mark.gui
EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


def document(tmp_path: Path, name: str = "microsat_250kg_eps") -> ModelDocument:
    shutil.copytree(EXAMPLES / name, tmp_path / "p")
    doc = ModelDocument()
    doc.load(tmp_path / "p", load_project(tmp_path / "p").project)
    return doc


@pytest.fixture
def doc(tmp_path: Path, qtbot) -> ModelDocument:  # type: ignore[no-untyped-def]
    return document(tmp_path)


def pages(doc: ModelDocument, qtbot) -> list[GridPage]:  # type: ignore[no-untyped-def]
    found: list[GridPage] = [UnitsPage(doc), PowerModesPage(doc), InputsPage(doc)]
    for page in found:
        qtbot.addWidget(page)
        page.resize(500, 400)  # narrow: the grid has to scroll sideways
        page.show()
    return found


def test_the_toolbar_is_above_the_grid_with_save_as_the_one_primary_action(  # type: ignore[no-untyped-def]
    doc: ModelDocument, qtbot
) -> None:
    for page in pages(doc, qtbot):
        top = page.table.mapTo(page, page.table.rect().topLeft()).y()
        for button in (page.undo_button, page.redo_button, page.legend_button, page.save_button):
            assert button.mapTo(page, button.rect().bottomLeft()).y() <= top
        assert page.filter.mapTo(page, page.filter.rect().bottomLeft()).y() <= top
        assert page.save_button.kind == "primary"
        assert [b.kind for b in (page.undo_button, page.redo_button, page.legend_button)] == [
            "secondary"
        ] * 3
        assert "Ctrl+S" in page.save_button.toolTip() and "Ctrl+Z" in page.undo_button.toolTip()


def test_a_row_is_26_px_high(doc: ModelDocument, qtbot) -> None:  # type: ignore[no-untyped-def]
    for page in pages(doc, qtbot):
        assert page.table.view.rowHeight(0) == theme.px(theme.ROW_HEIGHT)
        assert page.table.view.frozen.rowHeight(0) == theme.px(theme.ROW_HEIGHT)


def test_the_identifier_column_stays_when_the_grid_scrolls_sideways(  # type: ignore[no-untyped-def]
    doc: ModelDocument, qtbot
) -> None:
    for page in pages(doc, qtbot):
        view = page.table.view
        frozen = view.frozen
        assert frozen.isVisible() and not frozen.isColumnHidden(0)
        assert all(frozen.isColumnHidden(c) for c in range(1, page.model.columnCount()))
        bar = view.horizontalScrollBar()
        assert bar.maximum() > 0, "the page is narrow: it scrolls"
        bar.setValue(bar.maximum())
        QApplication.processEvents()
        assert frozen.isVisible() and frozen.width() == view.columnWidth(0)
        # same rows, same selection, one selection model
        assert frozen.selectionModel() is view.selectionModel()
        assert frozen.model() is view.model()


def test_the_keyboard_never_leaves_the_current_cell_under_the_frozen_column(  # type: ignore[no-untyped-def]
    doc: ModelDocument, qtbot
) -> None:
    page = pages(doc, qtbot)[0]
    view = page.table.view
    page.table.select_cell(0, 1)
    view.horizontalScrollBar().setValue(view.horizontalScrollBar().maximum())
    view.scrollTo(view.model().index(0, 1))
    QApplication.processEvents()
    assert view.visualRect(view.model().index(0, 1)).left() >= view.frozen_width()
    view.scrollTo(view.model().index(0, 0))  # the frozen column itself is always in view
    assert view.horizontalScrollBar().value() >= 0


def test_a_click_in_the_frozen_column_selects_the_row_cell(  # type: ignore[no-untyped-def]
    doc: ModelDocument, qtbot
) -> None:
    from PySide6.QtCore import Qt

    page = pages(doc, qtbot)[0]
    frozen = page.table.view.frozen
    rect = frozen.visualRect(frozen.model().index(1, 0))
    qtbot.mouseClick(frozen.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())
    assert (
        page.table.view.currentIndex().row() == 1 and page.table.view.currentIndex().column() == 0
    )


def test_a_wrong_cell_marks_its_row_in_the_identifier_column(  # type: ignore[no-untyped-def]
    doc: ModelDocument, qtbot
) -> None:
    page = pages(doc, qtbot)[0]
    model = page.model
    row = model.row_of("radio")
    mass = next(i for i, c in enumerate(model.columns) if c.title.startswith("mass_kg"))
    assert model.data(model.index(row, 0), STATE_ROLE) is None
    model.setData(model.index(row, mass), "-1")
    assert model.data(model.index(row, 0), STATE_ROLE) is Status.FAIL
    other = model.row_of("adcs")
    assert model.data(model.index(other, 0), STATE_ROLE) is None
    assert "needs correcting" in model.data(model.index(row, 0), 3)  # the tooltip
    page.undo_button.click()
    assert model.data(model.index(row, 0), STATE_ROLE) is None


def test_a_cell_answers_everything_the_delegate_asks_in_one_call(  # type: ignore[no-untyped-def]
    doc: ModelDocument, qtbot
) -> None:
    for page in pages(doc, qtbot):
        model = page.model
        for row in range(min(model.rowCount(), 5)):
            for column in range(model.columnCount()):
                index = model.index(row, column)
                text, state, numeric, total, share = model.data(index, CELL_ROLE)
                assert text == model.data(index, 0)
                assert state == model.data(index, STATE_ROLE) or column == 0
                assert isinstance(numeric, bool) and total is False and share is None


def test_scrolling_a_grid_of_200_units_stays_under_the_budget(  # type: ignore[no-untyped-def]
    tmp_path: Path, qtbot
) -> None:
    doc = document(tmp_path, "stress_200_units")
    page = UnitsPage(doc)
    qtbot.addWidget(page)
    page.resize(1100, 700)
    page.show()
    QApplication.processEvents()
    bar = page.table.view.verticalScrollBar()
    steps = 40
    times = []
    for _ in range(3):
        bar.setValue(0)
        QApplication.processEvents()
        start = time.perf_counter()
        for value in range(0, bar.maximum(), max(1, bar.maximum() // steps)):
            bar.setValue(value)
            QApplication.processEvents()
        times.append((time.perf_counter() - start) * 1000 / steps)
    # the aim is 33 ms a step on the reference machine (D-177); a loaded CI machine gets 3 times
    assert min(times) < 100, times


# ---- the scenario editor, the timeline axis, the tabs of files, the project tree ----------------
def test_a_rule_is_moved_and_removed_with_icon_buttons_that_have_names(  # type: ignore[no-untyped-def]
    tmp_path: Path, qtbot
) -> None:
    from budget_gui.main_window import MainWindow

    shutil.copytree(EXAMPLES / "microsat_250kg_eps", tmp_path / "p")
    window = MainWindow()
    qtbot.addWidget(window, before_close_func=lambda win: win.editors.discard_all_changes())
    window.open_project(tmp_path / "p")
    editor = window.scenario_view.editor
    rows = [*editor.rule_rows, *editor.segment_rows]
    assert rows
    for row in rows:
        for button in (row.up, row.down, row.remove):
            assert button.text() == "" and button.accessibleName() and button.toolTip()
    assert editor.add_rule_button.kind == "secondary" and editor.save_requested is not None


def test_a_tick_label_that_would_run_over_the_edge_is_left_out(  # type: ignore[no-untyped-def]
    qtbot,
) -> None:
    from budget_core.scenario.run import run_scenario
    from budget_gui.plot_metrics import STRIPS
    from budget_gui.timeline import TimelineWidget

    project = load_project(EXAMPLES / "microsat_250kg_eps").project
    assert project is not None
    widget = TimelineWidget()
    qtbot.addWidget(widget)
    widget.resize(1100, 240)
    widget.set_run(run_scenario(project, "one_day"))
    widget.show()
    labels: list[tuple[float, float]] = []
    from PySide6.QtGui import QPainter

    original = QPainter.drawText

    def spy(self, *args):  # type: ignore[no-untyped-def]
        if len(args) == 2 and hasattr(args[0], "x") and isinstance(args[1], str):
            width = self.fontMetrics().horizontalAdvance(args[1])
            labels.append((args[0].x(), args[0].x() + width))
        return original(self, *args)

    QPainter.drawText = spy  # type: ignore[method-assign]
    try:
        widget.grab()
    finally:
        QPainter.drawText = original  # type: ignore[method-assign]
    assert labels
    assert max(right for _left, right in labels) <= widget.width() - STRIPS.right // 2


def test_the_close_mark_of_a_file_tab_is_the_themed_x() -> None:
    from budget_gui.theme import LIGHT

    sheet = theme.stylesheet(LIGHT)
    assert "QTabBar::close-button" in sheet and "x-light.png" in sheet


def test_a_row_of_the_project_tree_is_as_high_as_a_table_row(  # type: ignore[no-untyped-def]
    tmp_path: Path, qtbot
) -> None:
    from budget_gui.main_window import MainWindow

    shutil.copytree(EXAMPLES / "microsat_250kg_eps", tmp_path / "p")
    window = MainWindow()
    qtbot.addWidget(window, before_close_func=lambda win: win.editors.discard_all_changes())
    window.show()
    window.open_project(tmp_path / "p")
    tree = window.tree
    item = tree.topLevelItem(0)
    assert item is not None
    assert tree.visualItemRect(item).height() >= theme.px(theme.ROW_HEIGHT)
