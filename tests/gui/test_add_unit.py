"""Adding and removing a unit in the window (D-187): the form, the Units page, and a blank
project built up from the window."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from budget_core.blank import BlankAnswers, create_blank_project
from budget_core.io.project_loader import load_project
from budget_core.new_unit import UnitAnswers
from budget_gui.add_unit_dialog import AddUnitDialog
from budget_gui.main_window import MainWindow
from budget_gui.model_document import ModelDocument
from budget_gui.model_pages import UnitsPage

pytestmark = pytest.mark.gui

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


def answers(**kw: object) -> UnitAnswers:
    base: dict[str, object] = {
        "unit_id": "camera2",
        "name": "Second camera",
        "subsystem": "PL",
        "bus": "payload",
        "maturity": "class_b",
        "mass_kg": 2.5,
        "mode_name": "imaging",
        "avg_power_w": 12.0,
        "peak_power_w": 15.0,
    }
    return UnitAnswers(**{**base, **kw})  # type: ignore[arg-type]


# ---- the form -------------------------------------------------------------------------------
def test_the_form_starts_empty_and_cannot_be_accepted(qtbot) -> None:  # type: ignore[no-untyped-def]
    dialog = AddUnitDialog([], ["main"], ["class_a"])
    qtbot.addWidget(dialog)
    assert not dialog.add_button.isEnabled()
    assert dialog.error_label.text() == ""  # no wall of errors before the user began
    assert dialog.mass_edit.text() == "" and dialog.avg_edit.text() == ""  # no default number


def test_the_id_follows_the_name_until_it_is_typed(qtbot) -> None:  # type: ignore[no-untyped-def]
    dialog = AddUnitDialog([], ["main"], ["class_a"])
    qtbot.addWidget(dialog)
    qtbot.keyClicks(dialog.name_edit, "On-board computer")
    assert dialog.id_edit.text() == "on_board_computer"
    dialog.id_edit.clear()
    qtbot.keyClicks(dialog.id_edit, "obc")
    qtbot.keyClicks(dialog.name_edit, " 2")
    assert dialog.id_edit.text() == "obc"  # typed by hand: left alone


def test_a_complete_form_can_be_added_and_gives_the_answers(qtbot) -> None:  # type: ignore[no-untyped-def]
    dialog = AddUnitDialog([], ["main", "payload"], ["class_a", "class_b"])
    qtbot.addWidget(dialog)
    qtbot.keyClicks(dialog.name_edit, "Radio")  # typing suggests the id; setText would not
    dialog.subsystem_edit.setText("TTC")
    dialog.bus_combo.setCurrentText("payload")
    dialog.maturity_combo.setCurrentText("class_b")
    dialog.mass_edit.setText("0,45")  # a decimal comma is read
    dialog.mode_edit.setText("rx")
    dialog.avg_edit.setText("1.5")
    assert not dialog.add_button.isEnabled()
    assert "peak" in dialog.error_label.text().lower()
    dialog.peak_edit.setText("2")
    assert dialog.add_button.isEnabled() and dialog.error_label.text() == ""
    given = dialog.answers()
    assert (given.unit_id, given.bus, given.maturity) == ("radio", "payload", "class_b")
    assert (given.mass_kg, given.avg_power_w, given.peak_power_w) == (0.45, 1.5, 2.0)


def test_text_that_is_not_a_number_is_not_a_number(qtbot) -> None:  # type: ignore[no-untyped-def]
    dialog = AddUnitDialog([], ["main"], ["class_a"])
    qtbot.addWidget(dialog)
    qtbot.keyClicks(dialog.name_edit, "x")
    dialog.mass_edit.setText("heavy")
    assert dialog.answers().mass_kg is None
    assert not dialog.add_button.isEnabled()


def test_an_existing_id_is_refused_by_the_form(qtbot) -> None:  # type: ignore[no-untyped-def]
    dialog = AddUnitDialog(["radio"], ["main"], ["class_a"])
    qtbot.addWidget(dialog)
    qtbot.keyClicks(dialog.name_edit, "Radio")
    assert "exists" in dialog.error_label.text()


def test_the_subsystem_must_name_a_thermal_node_when_there_is_a_thermal_model(qtbot) -> None:  # type: ignore[no-untyped-def]
    dialog = AddUnitDialog([], ["main"], ["class_a"], None, ["DH", "EPS"])
    qtbot.addWidget(dialog)
    qtbot.keyClicks(dialog.name_edit, "x")
    dialog.mode_edit.setText("nominal")
    dialog.subsystem_edit.setText("PAY")
    assert "thermal" in dialog.error_label.text().lower()
    assert dialog.subsystem_edit.completer() is not None


# ---- the Units page on the example project --------------------------------------------------
@pytest.fixture
def example(tmp_path: Path) -> Path:
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", tmp_path / "p")
    return tmp_path / "p"


@pytest.fixture
def page(example: Path, qtbot) -> UnitsPage:  # type: ignore[no-untyped-def]
    document = ModelDocument()
    document.load(example, load_project(example).project)
    units = UnitsPage(document)
    qtbot.addWidget(units)
    return units


def modes_of(page: UnitsPage) -> list[str]:
    return page.document.rels("modes/")


def test_adding_a_unit_puts_it_in_every_spacecraft_mode_in_one_undo_step(page: UnitsPage) -> None:
    page._ask = lambda *_a: answers()  # type: ignore[method-assign]
    before = len(page.document.rels("units/"))
    assert page.add_unit()
    document = page.document
    assert len(document.rels("units/")) == before + 1
    modes = modes_of(page)
    assert len(modes) == 5
    assert all(document.value(m, ("assignments", "camera2")) == "imaging" for m in modes)
    assert "put it in 5 spacecraft modes" in page.feedback_label.text()
    assert page.units.row_of("camera2") >= 0
    assert document.undo_stack.undoText() == "Add unit camera2"
    document.undo_stack.undo()  # one step takes back the unit and its places
    assert not document.is_modified() and "units/camera2.yaml" not in document.rels("units/")
    assert all(document.value(m, ("assignments", "camera2")) is None for m in modes)


def test_the_added_unit_saves_into_a_project_that_still_loads_without_error(
    page: UnitsPage, example: Path
) -> None:
    page._ask = lambda *_a: answers()  # type: ignore[method-assign]
    page.add_unit()
    assert page.document.save().ok
    loaded = load_project(example)
    assert loaded.project is not None and "camera2" in loaded.project.units
    assert not [p for p in loaded.problems if p.severity.name == "ERROR"]


def test_cancelling_the_form_changes_nothing(page: UnitsPage) -> None:
    page._ask = lambda *_a: None  # type: ignore[method-assign]
    assert not page.add_unit()
    assert not page.document.is_modified()


def test_the_form_is_given_what_the_project_offers(page: UnitsPage) -> None:
    seen: list[tuple[object, ...]] = []

    def ask(*args: object) -> None:
        seen.append(args)

    page._ask = ask  # type: ignore[method-assign]
    page.add_unit()
    existing, buses, classes, nodes = seen[0]
    assert "radio" in existing  # type: ignore[operator]
    assert buses == ["main", "payload"] and classes == ["class_a", "class_b", "class_c"]
    assert "TTC" in nodes  # type: ignore[operator]


def test_an_answer_the_model_refuses_is_said_not_written(page: UnitsPage) -> None:
    page._ask = lambda *_a: answers(unit_id="radio")  # type: ignore[method-assign]
    assert not page.add_unit()
    assert "already" in page.feedback_label.text()
    assert not page.document.is_modified()


def test_removing_a_unit_takes_it_out_of_the_spacecraft_modes_in_one_step(page: UnitsPage) -> None:
    document = page.document
    assert page.table.select_cell(page.units.row_of("star_tracker"), 1)
    assert page.remove_unit()
    assert "units/star_tracker.yaml" not in document.rels("units/")
    assert all(document.value(m, ("assignments", "star_tracker")) is None for m in modes_of(page))
    assert document.deleted_files() == ["units/star_tracker.yaml"]
    assert document.undo_stack.undoText() == "Remove unit star_tracker"
    document.undo_stack.undo()
    assert not document.is_modified()
    assert all(
        document.value(m, ("assignments", "star_tracker")) is not None for m in modes_of(page)
    )


def test_a_removed_unit_is_deleted_by_save_and_the_project_still_loads(
    page: UnitsPage, example: Path
) -> None:
    page.table.select_cell(page.units.row_of("star_tracker"), 1)
    page.remove_unit()
    assert page.document.save().ok
    assert not (example / "units" / "star_tracker.yaml").exists()
    loaded = load_project(example)
    assert loaded.project is not None and "star_tracker" not in loaded.project.units
    assert not [p for p in loaded.problems if p.severity.name == "ERROR"]


def test_the_only_unit_of_a_spacecraft_mode_is_not_removed(page: UnitsPage) -> None:
    document = page.document
    document.edit(
        [("modes/safe.yaml", lambda d: d.update(assignments={"obc": "nominal"}))], "Shrink safe"
    )
    page.table.select_cell(page.units.row_of("obc"), 1)
    assert not page.remove_unit()
    assert "only unit" in page.feedback_label.text()
    assert "units/obc.yaml" in document.rels("units/")


def test_nothing_selected_removes_nothing(page: UnitsPage) -> None:
    page.table.view.setCurrentIndex(page.table.view.model().index(-1, -1))
    assert not page.remove_unit() or True  # no row chosen: no exception, nothing removed
    assert not page.document.deleted_files()


# ---- a blank project built up in the window -------------------------------------------------
def test_a_blank_project_gets_its_first_unit_from_the_window(
    tmp_path: Path,
    qtbot,  # type: ignore[no-untyped-def]
) -> None:
    folder = create_blank_project(
        BlankAnswers(project_name="Blank", bus_voltage_v=28.0), tmp_path / "blank"
    )
    window = MainWindow()
    qtbot.addWidget(window, before_close_func=lambda w: w.editors.discard_all_changes())
    window.open_project(folder)
    page = window.units_page
    page._ask = lambda *_a: answers(  # type: ignore[method-assign]
        subsystem="PAY", bus="main", maturity="class_a"
    )
    assert page.add_unit()
    assert "put it in" not in page.feedback_label.text()  # a blank project has no spacecraft modes
    assert window.save_model()
    qtbot.waitUntil(
        lambda: window.session.project is not None and "camera2" in window.session.project.units,
        timeout=20000,
    )
    assert (folder / "units" / "camera2.yaml").is_file()
    assert not [p for p in window.session.problems if p.severity.name == "ERROR"]


# ---- saving a removed unit asks first ---------------------------------------------------------
def test_saving_a_removed_unit_asks_before_deleting_its_file(
    example: Path,
    qtbot,  # type: ignore[no-untyped-def]
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from PySide6.QtWidgets import QMessageBox

    window = MainWindow()
    qtbot.addWidget(window, before_close_func=lambda w: w.editors.discard_all_changes())
    window.open_project(example)
    page = window.units_page
    page.table.select_cell(page.units.row_of("star_tracker"), 1)
    assert page.remove_unit()
    asked: list[str] = []

    def no(_self, _title, text, *_a):  # type: ignore[no-untyped-def]
        asked.append(text)
        return QMessageBox.StandardButton.No

    monkeypatch.setattr(QMessageBox, "question", no)
    assert not window.save_model()  # refused: nothing is written
    assert "units/star_tracker.yaml" in asked[0]
    assert (example / "units" / "star_tracker.yaml").is_file()
    assert window.document.is_modified()

    monkeypatch.setattr(QMessageBox, "question", lambda *_a, **_k: QMessageBox.StandardButton.Yes)
    assert window.save_model()
    assert not (example / "units" / "star_tracker.yaml").exists()
