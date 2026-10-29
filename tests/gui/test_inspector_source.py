"""The Source field of the Inspector (D-213, P3b-2): see where a number came from, record it in
one undo step."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from budget_core.io.project_loader import load_project
from budget_gui.main_window import MainWindow
from tests.gui_helpers import mode_column, mode_row, unit_column

pytestmark = pytest.mark.gui

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
OTHER_MODE = "off"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """The example without its marking, so a number starts with no recorded source."""
    root = tmp_path / "p"
    shutil.copytree(EXAMPLES / "microsat_250kg", root)
    for path in root.rglob("*.yaml"):
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        if "provenance:\n" in lines:
            lines = lines[: lines.index("provenance:\n")]
        lines = [line for line in lines if line.strip() != "status: illustrative"]
        path.write_text("".join(lines), encoding="utf-8", newline="\n")
    return root


@pytest.fixture
def window(qtbot, project: Path):  # type: ignore[no-untyped-def]
    w = MainWindow()
    qtbot.addWidget(w, before_close_func=lambda win: win.editors.discard_all_changes())
    w.open_project(project)
    return w


def _on_unit_cell(window: MainWindow, unit: str, field: str) -> None:
    window.editors.setCurrentWidget(window.units_page)
    model = window.units_page.units
    assert window.units_page.table.select_cell(model.row_of(unit), unit_column(window, field))
    window._inspect_cell()


def _on_mode_cell(window: MainWindow, unit: str, mode: str, field: str) -> None:
    window.editors.setCurrentWidget(window.modes_page)
    assert window.modes_page.table.select_cell(
        mode_row(window, unit, mode), mode_column(window, field)
    )
    window._inspect_cell()


def _provenance(project: Path, unit: str) -> dict:  # type: ignore[type-arg]
    loaded = load_project(project).project
    assert loaded is not None
    return {k: v.model_dump() for k, v in loaded.units[unit].provenance.items()}


def test_a_number_without_a_source_says_so_and_offers_to_record_one(window: MainWindow) -> None:
    _on_unit_cell(window, "camera", "mass_kg")
    inspector = window.inspector
    assert not inspector.source_box.isHidden()
    assert "No source is recorded" in inspector.source_summary.text()
    assert inspector.source_edit.text() == "" and not inspector.source_remove.isEnabled()


def test_a_cell_that_is_not_a_number_has_no_source_field(window: MainWindow) -> None:
    _on_unit_cell(window, "camera", "subsystem")
    assert window.inspector.source_box.isHidden()


def test_setting_a_source_is_one_undo_step_and_is_saved_in_the_file(
    window: MainWindow, project: Path
) -> None:
    _on_unit_cell(window, "camera", "mass_kg")
    inspector = window.inspector
    inspector.source_edit.setText("Data sheet XYZ rev C")
    inspector.note_edit.setText("flight model")
    inspector.status_combo.setCurrentIndex(inspector.status_combo.findData("estimate"))
    steps = window.document.undo_stack.count()
    inspector.source_set.click()
    assert window.document.undo_stack.count() == steps + 1
    assert window.document.is_modified()
    assert "Recorded for this input" in inspector.source_summary.text()
    assert inspector.source_remove.isEnabled()
    assert window.save_model() is True
    assert _provenance(project, "camera") == {
        "mass_kg": {"source": "Data sheet XYZ rev C", "note": "flight model", "status": "estimate"}
    }
    window.document.undo_stack.undo()
    assert not window.document.data("units/camera.yaml").get("provenance")


def test_a_mode_is_recorded_by_its_name_so_the_entry_follows_it(window: MainWindow) -> None:
    _on_mode_cell(window, "camera", "imaging", "avg_power_w")
    window.inspector.source_edit.setText("TVAC report")
    window.inspector.source_set.click()
    keys = list(window.document.data("units/camera.yaml")["provenance"])
    assert keys == ["modes[imaging].avg_power_w"]
    # the same entry is found from the same cell again
    _on_mode_cell(window, "camera", "imaging", "avg_power_w")
    assert window.inspector.source_edit.text() == "TVAC report"
    assert "Recorded for this input" in window.inspector.source_summary.text()
    # and not for another mode
    _on_mode_cell(window, "camera", OTHER_MODE, "avg_power_w")
    assert window.inspector.source_edit.text() == ""


def test_the_whole_file_scope_writes_the_default_entry_and_covers_other_numbers(
    window: MainWindow,
) -> None:
    _on_unit_cell(window, "camera", "mass_kg")
    inspector = window.inspector
    inspector.source_scope.set_current("file")
    inspector.source_edit.setText("Invented example value")
    inspector.status_combo.setCurrentIndex(inspector.status_combo.findData("illustrative"))
    inspector.source_set.click()
    assert list(window.document.data("units/camera.yaml")["provenance"]) == ["*"]
    _on_mode_cell(window, "camera", "imaging", "avg_power_w")
    assert window.inspector.source_scope.current() == "file", "the default covers this number"
    assert window.inspector.source_edit.text() == "Invented example value"
    assert "Recorded for the whole file" in window.inspector.source_summary.text()
    window.inspector.source_scope.set_current("input")
    assert "follows the entry for the whole file" in window.inspector.source_summary.text()
    assert (
        window.inspector.source_edit.text() == "" and not window.inspector.source_remove.isEnabled()
    )


def test_remove_deletes_the_entry_and_an_empty_mapping_goes_with_it(window: MainWindow) -> None:
    _on_unit_cell(window, "camera", "mass_kg")
    window.inspector.source_edit.setText("A")
    window.inspector.source_set.click()
    assert "provenance" in window.document.data("units/camera.yaml")
    window.inspector.source_remove.click()
    assert "provenance" not in window.document.data("units/camera.yaml")
    assert "No source is recorded" in window.inspector.source_summary.text()


def test_an_empty_source_is_not_recorded(window: MainWindow) -> None:
    _on_unit_cell(window, "camera", "mass_kg")
    steps = window.document.undo_stack.count()
    window.inspector.source_edit.setText("   ")
    window.inspector.source_set.click()
    assert window.document.undo_stack.count() == steps
    assert "Write where the number comes from" in window.inspector.source_summary.text()


def test_the_inputs_grid_has_no_source_field_because_it_shows_the_source_itself(
    window: MainWindow,
) -> None:
    window.editors.setCurrentWidget(window.inputs_page)
    assert window.inputs_page.table.select_cell(0, 1)
    window._inspect_cell()
    assert window.inspector.source_box.isHidden()


def test_the_source_field_is_hidden_when_the_inspector_follows_the_tree(
    window: MainWindow,
) -> None:
    _on_unit_cell(window, "camera", "mass_kg")
    assert not window.inspector.source_box.isHidden()
    window._inspect()
    assert window.inspector.source_box.isHidden()
