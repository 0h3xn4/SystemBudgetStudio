"""The grid table and its page: copy, paste, fill-down, clear, keys, filter (UX step 2, D-159)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QLineEdit

from budget_core.io.project_loader import load_project
from budget_gui.grid_view import GridPage, GridTable, parse_clipboard
from budget_gui.model_document import ModelDocument
from budget_gui.model_pages import InputsPage, PowerModesPage, UnitsPage

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


@pytest.fixture
def doc(tmp_path: Path, qtbot) -> ModelDocument:  # type: ignore[no-untyped-def]
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", tmp_path / "p")
    document = ModelDocument()
    document.load(tmp_path / "p", load_project(tmp_path / "p").project)
    return document


@pytest.fixture
def units(doc: ModelDocument, qtbot) -> UnitsPage:  # type: ignore[no-untyped-def]
    page = UnitsPage(doc)
    qtbot.addWidget(page)
    page.resize(900, 500)
    return page


def col(page: GridPage, title: str) -> int:
    return next(i for i, c in enumerate(page.model.columns) if c.title.startswith(title))


def select(table: GridTable, row: int, column: int, row2: int | None = None) -> None:
    """Select a block of cells in view coordinates (and make the first one current)."""
    view = table.view
    view.setCurrentIndex(table.proxy.index(row, column))
    if row2 is not None:
        from PySide6.QtCore import QItemSelection, QItemSelectionModel

        selection = QItemSelection(table.proxy.index(row, column), table.proxy.index(row2, column))
        view.selectionModel().select(selection, QItemSelectionModel.SelectionFlag.ClearAndSelect)


def test_parse_clipboard_reads_tabs_and_lines() -> None:
    assert parse_clipboard("a\tb\r\nc\td\r\n") == [["a", "b"], ["c", "d"]]
    assert parse_clipboard("x") == [["x"]] and parse_clipboard("") == []


def test_copy_gives_the_exact_values_with_tabs(units: UnitsPage) -> None:
    table = units.table
    mass = col(units, "mass_kg")
    select(table, 0, col(units, "name"), None)
    assert table.copy_text() == "Separation adapter"
    select(table, 0, mass, 1)
    assert table.copy_text() == "4\n3"  # adapter, adcs: the exact value, not "4.000"


def test_paste_of_a_column_writes_one_undo_step(units: UnitsPage, doc: ModelDocument) -> None:
    table = units.table
    select(table, 0, col(units, "mass_kg"))
    plan = table.plan_paste("5\n6\n7")
    assert [c[2] for c in plan.cells] == ["5", "6", "7"] and plan.clipped == 0
    assert table.apply_cells(plan.cells, "Paste")
    assert [doc.value(f"units/{u}.yaml", ("mass_kg",)) for u in ("adapter", "adcs", "battery")] == [
        5.0,
        6.0,
        7.0,
    ]
    assert doc.undo_stack.undoText() == "Paste 3 cells"
    doc.undo_stack.undo()
    assert not doc.is_modified()


def test_a_block_with_units_and_columns_is_pasted_as_typed(
    units: UnitsPage, doc: ModelDocument
) -> None:
    select(units.table, 0, col(units, "name"))
    plan = units.table.plan_paste("Adapter A\tSTRUCT\tmain\tclass_b\t4500 g")
    units.table.apply_cells(plan.cells, "Paste")
    assert doc.value("units/adapter.yaml", ("name",)) == "Adapter A"
    assert doc.value("units/adapter.yaml", ("mass_kg",)) == pytest.approx(4.5)


def test_one_value_pasted_over_a_selection_fills_it(units: UnitsPage) -> None:
    select(units.table, 0, col(units, "mass_kg"), 2)
    plan = units.table.plan_paste("9")
    assert len(plan.cells) == 3


def test_cells_that_cannot_be_edited_and_cells_outside_are_counted(units: UnitsPage) -> None:
    select(units.table, units.table.visible_rows() - 1, 0)  # the id column of the last row
    plan = units.table.plan_paste("x\tname\tsub\nz\tz\tz")
    assert plan.skipped == 1 and plan.clipped == 3 and len(plan.cells) == 2


def test_pasting_many_cells_shows_a_preview_and_cancel_changes_nothing(
    units: UnitsPage, doc: ModelDocument, monkeypatch: pytest.MonkeyPatch
) -> None:
    shown: list[tuple[list[tuple[str, str, str]], int]] = []

    def cancel(rows, total):  # type: ignore[no-untyped-def]
        shown.append((rows, total))
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(units.table, "preview", cancel)
    select(units.table, 0, col(units, "mass_kg"))
    QApplication.clipboard().setText("5\n6")
    assert not units.table.paste()
    assert shown and shown[0][1] == 2 and "mass_kg" in shown[0][0][0][0]
    assert not doc.is_modified()
    monkeypatch.setattr(units.table, "preview", lambda rows, total: QDialog.DialogCode.Accepted)
    assert units.table.paste() and doc.is_modified()
    assert "Pasted 2 cells" in units.feedback_label.text()


def test_pasting_one_cell_needs_no_preview(
    units: UnitsPage, doc: ModelDocument, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(units.table, "preview", lambda *a: pytest.fail("no preview for one cell"))
    select(units.table, 0, col(units, "mass_kg"))
    QApplication.clipboard().setText("8")
    assert units.table.paste()
    assert doc.value("units/adapter.yaml", ("mass_kg",)) == 8.0


def test_the_preview_dialog_lists_old_and_new(units: UnitsPage, qtbot) -> None:  # type: ignore[no-untyped-def]
    from budget_gui.grid_view import PastePreview

    dialog = PastePreview([("adapter, mass_kg", "4.0", "5")], 3, None)
    qtbot.addWidget(dialog)
    assert (
        "3 cells would change"
        in dialog.findChildren(type(dialog.layout().itemAt(0).widget()))[0].text()
    )
    assert dialog.apply_button.text() == "Paste 3 cells"


def test_fill_down_copies_the_top_cell(units: UnitsPage, doc: ModelDocument) -> None:
    mass = col(units, "mass_kg")
    doc.set_value("units/adapter.yaml", ("mass_kg",), 12.0, "x")
    select(units.table, 0, mass, 3)
    assert units.table.fill_down()
    assert [doc.value(f"units/{u}.yaml", ("mass_kg",)) for u in ("adcs", "battery", "camera")] == [
        12.0,
        12.0,
        12.0,
    ]
    assert doc.undo_stack.undoText() == "Fill down 3 cells"


def test_fill_down_with_one_row_says_what_to_select(units: UnitsPage) -> None:
    select(units.table, 0, col(units, "mass_kg"))
    assert not units.table.fill_down()
    assert "select" in units.feedback_label.text().lower()


def test_delete_empties_optional_cells_only(units: UnitsPage, doc: ModelDocument) -> None:
    select(units.table, 0, col(units, "mass_kg"))
    assert not units.table.clear_cells()
    assert "optional" in units.feedback_label.text()
    row = units.model.row_of("radio")
    select(units.table, row, col(units, "survival_max_k"))
    assert units.table.clear_cells()
    assert doc.value("units/radio.yaml", ("temperature_limits", "survival_max_k")) is None


def test_an_edit_with_enter_moves_down(units: UnitsPage, doc: ModelDocument, qtbot) -> None:  # type: ignore[no-untyped-def]
    units.show()
    table = units.table
    select(table, 0, col(units, "mass_kg"))
    table.view.setFocus()
    table.view.edit(table.view.currentIndex())
    editor = table.view.viewport().findChild(QLineEdit)
    assert editor is not None
    qtbot.keyClicks(editor, "7")
    qtbot.keyClick(editor, Qt.Key.Key_Return)
    qtbot.wait(50)  # Qt commits and closes the editor from the event loop
    assert doc.value("units/adapter.yaml", ("mass_kg",)) == 7.0
    assert table.view.currentIndex().row() == 1


def test_escape_cancels_an_edit(units: UnitsPage, doc: ModelDocument, qtbot) -> None:  # type: ignore[no-untyped-def]
    units.show()
    table = units.table
    select(table, 0, col(units, "mass_kg"))
    table.view.setFocus()
    table.view.edit(table.view.currentIndex())
    editor = table.view.viewport().findChild(QLineEdit)
    assert editor is not None
    qtbot.keyClicks(editor, "99")
    qtbot.keyClick(editor, Qt.Key.Key_Escape)
    assert not doc.is_modified()


def test_tab_leaves_the_grid_after_the_last_cell(units: UnitsPage, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    units.show()
    table = units.table
    moved: list[str] = []
    monkeypatch.setattr(table.view, "focusNextChild", lambda: moved.append("next") or True)
    monkeypatch.setattr(table.view, "focusPreviousChild", lambda: moved.append("previous") or True)
    last = table.proxy.index(table.proxy.rowCount() - 1, table.proxy.columnCount() - 1)
    table.view.setCurrentIndex(last)
    table.view.setFocus()
    qtbot.keyClick(table.view, Qt.Key.Key_Tab)
    table.view.setCurrentIndex(table.proxy.index(0, 0))
    qtbot.keyClick(table.view, Qt.Key.Key_Backtab)
    assert moved == ["next", "previous"]


def test_copy_and_paste_keys_use_the_clipboard(units: UnitsPage, doc: ModelDocument, qtbot) -> None:  # type: ignore[no-untyped-def]
    units.show()
    table = units.table
    mass = col(units, "mass_kg")
    select(table, 0, mass)
    table.view.setFocus()
    qtbot.keyClick(table.view, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
    assert QApplication.clipboard().text() == "4"
    select(table, 1, mass)
    qtbot.keyClick(table.view, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
    assert doc.value("units/adcs.yaml", ("mass_kg",)) == 4.0


def test_the_filter_narrows_the_rows_and_says_so(units: UnitsPage) -> None:
    units.filter.setText("radio")
    assert units.table.visible_rows() == 1
    assert "Showing 1 of 18 units" in units.count_label.text()
    units.filter.setText("")
    assert units.count_label.text() == "18 units"


def test_a_paste_goes_to_the_rows_that_are_shown(units: UnitsPage, doc: ModelDocument) -> None:
    units.filter.setText("radio")
    select(units.table, 0, col(units, "mass_kg"))
    plan = units.table.plan_paste("6")
    units.table.apply_cells(plan.cells, "Paste")
    assert doc.value("units/radio.yaml", ("mass_kg",)) == 6.0
    assert doc.modified_files() == ["units/radio.yaml"]


def test_the_buttons_follow_the_undo_stack(units: UnitsPage, doc: ModelDocument) -> None:
    assert not units.undo_button.isEnabled() and not units.redo_button.isEnabled()
    doc.set_value("units/radio.yaml", ("mass_kg",), 5.0, "Edit radio: mass_kg")
    assert units.undo_button.isEnabled() and "Edit radio: mass_kg" in units.undo_button.toolTip()
    units.undo_button.click()
    assert units.redo_button.isEnabled() and not doc.is_modified()


def test_a_wrong_cell_shows_a_sentence_under_the_grid(units: UnitsPage) -> None:
    row = units.model.row_of("radio")
    units.model.setData(units.model.index(row, col(units, "mass_kg")), "-1")
    assert not units.problem_label.isHidden()
    assert "correcting" in units.problem_label.text() and "radio" in units.problem_label.text()
    units.undo_button.click()
    assert units.problem_label.isHidden()


def test_save_asks_for_a_save(units: UnitsPage, qtbot) -> None:  # type: ignore[no-untyped-def]
    with qtbot.waitSignal(units.save_requested, timeout=500):
        units.save_button.click()


# ---- power modes page -----------------------------------------------------------------------
@pytest.fixture
def modes(doc: ModelDocument, qtbot) -> PowerModesPage:  # type: ignore[no-untyped-def]
    page = PowerModesPage(doc)
    qtbot.addWidget(page)
    page.resize(900, 500)
    return page


def test_add_a_mode_to_the_unit_of_the_current_row_and_remove_it(
    modes: PowerModesPage, doc: ModelDocument
) -> None:
    assert not modes.add_mode() and "Select a row" in modes.feedback_label.text()
    assert modes.select_unit("radio")
    before = modes.modes.rowCount()
    assert modes.add_mode() and modes.modes.rowCount() == before + 1
    new = modes.modes.rows_of("radio")[-1]
    modes.table.select_cell(new, 1)
    assert modes.remove_mode() and modes.modes.rowCount() == before
    assert "Undo" in modes.feedback_label.text()
    doc.undo_stack.undo()
    assert modes.modes.rowCount() == before + 1


def test_the_last_mode_of_a_unit_is_kept(modes: PowerModesPage, doc: ModelDocument) -> None:
    doc.edit([("units/camera.yaml", lambda d: d["modes"].__delitem__(0))], "x")
    assert modes.select_unit("camera")
    assert not modes.remove_mode() and "at least one" in modes.feedback_label.text()


def test_select_unit_clears_the_filter_and_lands_on_its_first_mode(modes: PowerModesPage) -> None:
    modes.filter.setText("zzz")
    assert modes.table.visible_rows() == 0
    assert modes.select_unit("radio")
    assert modes.filter.text() == ""
    assert modes.table.current_cell() == (modes.modes.rows_of("radio")[0], 1)


def test_units_page_selects_a_unit_by_id(units: UnitsPage) -> None:
    assert units.select_unit("gnss") and units.table.current_cell() == (
        units.model.row_of("gnss"),
        1,
    )
    assert not units.select_unit("nope")


# ---- inputs page ----------------------------------------------------------------------------
@pytest.fixture
def inputs(doc: ModelDocument, qtbot) -> InputsPage:  # type: ignore[no-untyped-def]
    page = InputsPage(doc)
    qtbot.addWidget(page)
    page.resize(900, 500)
    return page


def test_the_placeholder_filter_shows_only_placeholders_and_counts_them(inputs: InputsPage) -> None:
    total = inputs.model.rowCount()
    assert inputs.placeholder_count() == 5
    assert "(5)" in inputs.only_placeholders.text()
    inputs.only_placeholders.setChecked(True)
    assert inputs.table.visible_rows() == 5
    assert f"Showing 5 of {total} inputs" in inputs.count_label.text()
    inputs.only_placeholders.setChecked(False)
    assert inputs.table.visible_rows() == total


def test_filling_a_placeholder_updates_the_count(inputs: InputsPage, doc: ModelDocument) -> None:
    row = next(r for r in range(inputs.model.rowCount()) if inputs.inputs.is_placeholder_row(r))
    inputs.inputs.setData(inputs.inputs.index(row, 1), "0.2")
    inputs.inputs.setData(inputs.inputs.index(row, 3), "Project policy")
    assert inputs.placeholder_count() == 4


def test_mark_as_sourced_starts_editing_what_is_missing(inputs: InputsPage, qtbot) -> None:  # type: ignore[no-untyped-def]
    inputs.show()
    row = next(r for r in range(inputs.model.rowCount()) if inputs.inputs.is_placeholder_row(r))
    assert inputs.mark_as_sourced(row)
    assert inputs.table.current_cell() == (row, 1)  # the value is missing, so start there
    assert "source" in inputs.feedback_label.text()
    assert inputs.table.view.viewport().findChild(QLineEdit) is not None  # an editor is open


def test_the_icons_follow_the_theme(units: UnitsPage) -> None:
    from budget_gui import theme

    def pixel_sum() -> int:
        image = units.save_button.icon().pixmap(16, 16).toImage()
        return sum(image.pixelColor(x, y).red() for x in range(16) for y in range(16))

    light = pixel_sum()
    theme.manager().set_mode("dark")
    try:
        assert pixel_sum() != light  # drawn again in the light-on-dark colour
    finally:
        theme.manager().set_mode("light")


def test_an_empty_grid_says_what_to_do(qtbot) -> None:  # type: ignore[no-untyped-def]
    page = UnitsPage(ModelDocument())
    qtbot.addWidget(page)
    assert page.count_label.text() == "Open a project to see its units."
    assert page.table.visible_rows() == 0


def test_a_project_without_units_says_so(tmp_path: Path, qtbot) -> None:  # type: ignore[no-untyped-def]
    shutil.copytree(EXAMPLES / "microsat_250kg", tmp_path / "p")
    document = ModelDocument()
    document.load(tmp_path / "p", load_project(tmp_path / "p").project)
    page = PowerModesPage(document)
    qtbot.addWidget(page)
    for rel in document.rels("units/"):
        document._files.pop(rel)  # a project whose unit files are gone
    document.changed.emit()
    assert page.count_label.text() == "No power modes in this project."
