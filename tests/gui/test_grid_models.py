"""The table models of the Model grids (UX step 2, D-159)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from PySide6.QtCore import Qt

from budget_core.io.project_loader import load_project
from budget_gui.delegates import NUMERIC_ROLE, STATE_ROLE, status_of
from budget_gui.grid_models import (
    PATH_ROLE,
    PowerModesModel,
    SourcedModel,
    UnitsModel,
    is_placeholder,
    sourced_paths,
)
from budget_gui.model_document import ModelDocument
from budget_gui.theme import Status

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


@pytest.fixture
def doc(tmp_path: Path, qtbot) -> ModelDocument:  # type: ignore[no-untyped-def]
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", tmp_path / "p")
    document = ModelDocument()
    document.load(tmp_path / "p", load_project(tmp_path / "p").project)
    return document


def column(model, title: str) -> int:  # type: ignore[no-untyped-def]
    return next(i for i, c in enumerate(model.columns) if c.title.startswith(title))


def row_of(model, text: str) -> int:  # type: ignore[no-untyped-def]
    return next(r for r in range(model.rowCount()) if model.index(r, 0).data() == text)


def cell(model, row: int, col: int, role: int = Qt.ItemDataRole.DisplayRole):  # type: ignore[no-untyped-def]
    value = model.index(row, col).data(role)
    return status_of(value) if role == STATE_ROLE and value is not None else value


# ---- units ----------------------------------------------------------------------------------
def test_units_one_row_per_unit_with_units_in_the_headers(doc: ModelDocument) -> None:
    model = UnitsModel(doc)
    assert model.rowCount() == 18
    titles = [model.headerData(c, Qt.Orientation.Horizontal) for c in range(model.columnCount())]
    assert "mass_kg [kg]" in titles and "operating_max_k [K]" in titles
    radio = row_of(model, "radio")
    assert cell(model, radio, column(model, "name")) == "S-band transceiver"
    assert cell(model, radio, column(model, "mass_kg")) == "4.500"
    assert cell(model, radio, column(model, "mass_kg"), NUMERIC_ROLE) is True
    assert cell(model, radio, column(model, "name"), NUMERIC_ROLE) is False


def test_the_editor_starts_with_the_exact_value_not_the_rounded_one(doc: ModelDocument) -> None:
    model = UnitsModel(doc)
    radio = row_of(model, "radio")
    col = column(model, "operating_max_k")
    assert cell(model, radio, col, Qt.ItemDataRole.EditRole) == "332.15"
    assert cell(model, radio, col) == "332.15"


def test_a_missing_limit_is_not_checked_not_empty(doc: ModelDocument) -> None:
    model = UnitsModel(doc)
    structure = row_of(model, "structure")
    col = column(model, "operating_max_k")
    if cell(model, structure, col, STATE_ROLE) is None:  # the example gives it limits
        doc.set_value("units/structure.yaml", ("temperature_limits", "operating_max_k"), None, "x")
    assert cell(model, structure, col, STATE_ROLE) is Status.NOT_CHECKED
    assert cell(model, structure, col) == "n/a"
    assert "not checked" in cell(model, structure, col, Qt.ItemDataRole.ToolTipRole)


def test_typing_into_a_cell_edits_the_document_with_a_named_undo_step(doc: ModelDocument) -> None:
    model = UnitsModel(doc)
    radio = row_of(model, "radio")
    col = column(model, "mass_kg")
    assert model.setData(model.index(radio, col), "5000 g")
    assert doc.value("units/radio.yaml", ("mass_kg",)) == pytest.approx(5.0)
    assert "radio" in doc.undo_stack.undoText() and "mass_kg" in doc.undo_stack.undoText()
    doc.undo_stack.undo()
    assert cell(model, radio, col, Qt.ItemDataRole.EditRole) == "4.5"


def test_a_limit_typed_into_a_unit_without_limits_makes_the_mapping(doc: ModelDocument) -> None:
    model = UnitsModel(doc)
    unit = "units/structure.yaml"
    for key in ("operating_min_k", "operating_max_k", "survival_min_k", "survival_max_k"):
        doc.set_value(unit, ("temperature_limits", key), None, "clear")
    assert doc.value(unit, ("temperature_limits",)) is None  # no empty mapping left behind
    row = row_of(model, "structure")
    assert model.setData(model.index(row, column(model, "operating_min_k")), "250")
    assert doc.value(unit, ("temperature_limits", "operating_min_k")) == 250.0


def test_a_wrong_cell_is_marked_and_explained_in_words(doc: ModelDocument) -> None:
    model = UnitsModel(doc)
    radio = row_of(model, "radio")
    col = column(model, "mass_kg")
    model.setData(model.index(radio, col), "-3")
    assert cell(model, radio, col, STATE_ROLE) is Status.FAIL
    assert cell(model, radio, col, Qt.ItemDataRole.ToolTipRole)
    lines = model.problem_lines()
    assert len(lines) == 1 and lines[0].startswith("radio, mass_kg")


def test_the_id_column_is_read_only_and_has_no_cell(doc: ModelDocument) -> None:
    model = UnitsModel(doc)
    index = model.index(0, 0)
    assert not model.flags(index) & Qt.ItemFlag.ItemIsEditable
    assert not model.setData(index, "x")
    assert index.data(PATH_ROLE) is None


def test_the_unit_rows_are_found_by_id(doc: ModelDocument) -> None:
    model = UnitsModel(doc)
    assert model.row_of("radio") == row_of(model, "radio") and model.row_of("nope") == -1


# ---- power modes ----------------------------------------------------------------------------
def test_power_modes_one_row_per_mode(doc: ModelDocument) -> None:
    model = PowerModesModel(doc)
    total = sum(len(doc.value(rel, ("modes",))) for rel in doc.rels("units/"))
    assert model.rowCount() == total
    rows = model.rows_of("radio")
    assert [model.index(r, 1).data() for r in rows][-1] == "downlink"
    row = rows[-1]
    assert cell(model, row, column(model, "avg_power_w")) == "28.000"
    assert cell(model, row, column(model, "average x duty")) == "28.000"


def test_the_effective_average_follows_the_duty_cycle(doc: ModelDocument) -> None:
    model = PowerModesModel(doc)
    row = model.rows_of("camera")[-1]
    assert cell(model, row, column(model, "average x duty")) == "36.000"  # 60 W x 0.6


def test_a_missing_heat_ratio_is_not_checked(doc: ModelDocument) -> None:
    model = PowerModesModel(doc)
    row = model.rows_of("radio")[-1]
    col = column(model, "heat_dissipation_ratio")
    doc.set_value("units/radio.yaml", ("modes", 5, "heat_dissipation_ratio"), None, "clear")
    assert cell(model, row, col, STATE_ROLE) is Status.NOT_CHECKED
    assert cell(model, row, column(model, "min_duration_s"), STATE_ROLE) is None  # plain empty


def test_peak_below_average_marks_the_peak_cell(doc: ModelDocument) -> None:
    model = PowerModesModel(doc)
    row = model.rows_of("radio")[-1]
    model.setData(model.index(row, column(model, "peak_power_w")), "10")
    assert cell(model, row, column(model, "peak_power_w"), STATE_ROLE) is Status.FAIL
    assert cell(model, row, column(model, "avg_power_w"), STATE_ROLE) is None


def test_emptying_an_optional_cell_removes_the_field(doc: ModelDocument) -> None:
    model = PowerModesModel(doc)
    row = model.rows_of("radio")[-1]
    col = column(model, "heat_dissipation_ratio")
    assert model.setData(model.index(row, col), "")
    assert doc.value("units/radio.yaml", ("modes", 5, "heat_dissipation_ratio")) is None


def test_adding_and_removing_a_mode_are_undoable_steps(doc: ModelDocument) -> None:
    model = PowerModesModel(doc)
    before = model.rowCount()
    assert model.add_mode("units/radio.yaml")
    assert model.rowCount() == before + 1
    new = model.rows_of("radio")[-1]
    assert model.index(new, 1).data() == "mode_7"
    assert model.remove_mode(new)
    assert model.rowCount() == before
    doc.undo_stack.undo()
    assert model.rowCount() == before + 1
    doc.undo_stack.undo()
    assert model.rowCount() == before and not doc.is_modified()


def test_the_last_mode_of_a_unit_cannot_be_removed(doc: ModelDocument) -> None:
    model = PowerModesModel(doc)
    doc.edit(
        [("units/camera.yaml", lambda data: data["modes"].__delitem__(0))],
        "x",
    )
    (row,) = model.rows_of("camera")[:1]
    assert len(model.rows_of("camera")) == 1 and not model.remove_mode(row)


def test_a_new_mode_name_that_is_taken_is_reported(doc: ModelDocument) -> None:
    model = PowerModesModel(doc)
    row = model.rows_of("radio")[0]
    model.setData(model.index(row, 1), "downlink")
    assert any("radio" in line for line in model.problem_lines())


# ---- sourced inputs -------------------------------------------------------------------------
def test_every_sourced_number_is_a_row(doc: ModelDocument) -> None:
    model = SourcedModel(doc)
    assert model.rowCount() > 40
    labels = [model.index(r, 0).data() for r in range(model.rowCount())]
    assert any(
        label.startswith("margin_policy classes.class_a.mass_margin_ratio") for label in labels
    )
    assert any(label.startswith("sband_down transmitter.power_w") for label in labels)


def test_a_placeholder_row_is_styled_and_a_sourced_one_is_not(doc: ModelDocument) -> None:
    model = SourcedModel(doc)
    placeholder = next(
        r
        for r in range(model.rowCount())
        if model.index(r, 0).data().startswith("margin_policy classes.class_a.mass_margin_ratio")
    )
    sourced = next(
        r
        for r in range(model.rowCount())
        if model.index(r, 0).data().startswith("margin_policy classes.class_a.power_margin_ratio")
    )
    for col in (1, 3):
        assert cell(model, placeholder, col, STATE_ROLE) is Status.PLACEHOLDER
        assert cell(model, sourced, col, STATE_ROLE) is None
    assert "Placeholder" in cell(model, placeholder, 1, Qt.ItemDataRole.ToolTipRole)
    assert cell(model, placeholder, 1) == "" and cell(model, placeholder, 3) == "TBD"
    assert cell(model, sourced, 1) == "0.05" and cell(model, sourced, 2) == "ratio"


def test_marking_a_placeholder_as_sourced_means_a_value_and_a_source(doc: ModelDocument) -> None:
    model = SourcedModel(doc)
    row = next(
        r
        for r in range(model.rowCount())
        if model.index(r, 0).data().startswith("margin_policy classes.class_a.mass_margin_ratio")
    )
    assert model.setData(model.index(row, 1), "0.15")
    assert cell(model, row, 1, STATE_ROLE) is Status.PLACEHOLDER  # still: the source says TBD
    assert model.setData(model.index(row, 3), "Project margin policy rev A")
    assert cell(model, row, 1, STATE_ROLE) is None and cell(model, row, 3, STATE_ROLE) is None
    assert model.index(row, 1).data() == "0.15"
    doc.undo_stack.undo()
    assert cell(model, row, 3, STATE_ROLE) is Status.PLACEHOLDER


def test_emptying_a_value_makes_it_a_placeholder_again(doc: ModelDocument) -> None:
    model = SourcedModel(doc)
    row = next(
        r
        for r in range(model.rowCount())
        if model.index(r, 0).data().startswith("margin_policy classes.class_a.power_margin_ratio")
    )
    assert model.setData(model.index(row, 1), "")
    assert cell(model, row, 1, STATE_ROLE) is Status.PLACEHOLDER
    assert not doc.problems()  # null is allowed: the number is simply not given


def test_an_empty_source_is_refused_and_a_note_can_be_dropped(doc: ModelDocument) -> None:
    model = SourcedModel(doc)
    row = next(
        r
        for r in range(model.rowCount())
        if model.index(r, 0).data().startswith("margin_policy classes.class_a.mass_margin_ratio")
    )
    model.setData(model.index(row, 3), "")
    assert cell(model, row, 3, STATE_ROLE) is Status.FAIL
    doc.undo_stack.undo()
    assert model.setData(model.index(row, 4), "")
    assert cell(model, row, 4) == ""


def test_the_helpers_find_sourced_numbers_and_placeholders() -> None:
    data = {
        "a": {"value": 1.0, "source": "x"},
        "b": [{"value": None, "source": "TBD", "note": "n"}],
        "c": {"d": 2},
    }
    assert sourced_paths(data) == [("a",), ("b", 0)]
    assert not is_placeholder(data["a"]) and is_placeholder(data["b"][0])
