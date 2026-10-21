"""Files added and removed in the document (a unit added or removed in the window, D-187):
undo steps, nothing on disk before Save, and Save creates or deletes the file."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from budget_core.io.project_loader import load_project
from budget_core.model import Unit
from budget_core.new_unit import UnitAnswers, unit_data
from budget_gui.model_document import ModelDocument

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
NEW = "units/camera2.yaml"


def new_unit_data(**kw: object) -> dict[str, object]:
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
    return unit_data(UnitAnswers(**{**base, **kw}))  # type: ignore[arg-type]


@pytest.fixture
def project(tmp_path: Path) -> Path:
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", tmp_path / "p")
    return tmp_path / "p"


@pytest.fixture
def doc(project: Path, qtbot) -> ModelDocument:  # type: ignore[no-untyped-def]
    document = ModelDocument()
    document.load(project, load_project(project).project)
    return document


def test_an_added_unit_is_in_the_grid_but_not_on_disk(doc: ModelDocument, project: Path) -> None:
    before = len(doc.rels("units/"))
    assert doc.add_file(NEW, Unit, new_unit_data(), "Add unit camera2")
    assert len(doc.rels("units/")) == before + 1 and NEW in doc.rels("units/")
    assert doc.is_new(NEW) and doc.is_modified() and doc.modified_files() == [NEW]
    assert not doc.problems(NEW)
    assert not (project / NEW).exists()


def test_adding_is_one_undo_step(doc: ModelDocument) -> None:
    doc.add_file(NEW, Unit, new_unit_data(), "Add unit camera2")
    assert doc.undo_stack.undoText() == "Add unit camera2"
    doc.undo_stack.undo()
    assert NEW not in doc.rels("units/") and not doc.is_modified()
    doc.undo_stack.redo()
    assert doc.has(NEW) and doc.is_modified()


def test_a_unit_that_exists_cannot_be_added_again(doc: ModelDocument) -> None:
    assert not doc.add_file("units/radio.yaml", Unit, new_unit_data(), "Add unit radio")
    assert not doc.undo_stack.canUndo()


def test_the_cells_of_an_added_unit_can_be_edited_before_saving(doc: ModelDocument) -> None:
    doc.add_file(NEW, Unit, new_unit_data(), "Add")
    assert doc.set_value(NEW, ("mass_kg",), 3.0, "Edit mass")
    assert doc.value(NEW, ("mass_kg",)) == 3.0
    doc.set_value(NEW, ("mass_kg",), "not a number", "Edit mass")
    assert doc.problems(NEW)


def put_in_every_mode(doc: ModelDocument, unit_id: str = "camera2", mode: str = "imaging") -> None:
    """The loader wants every spacecraft mode to say what every unit does."""
    doc.edit(
        [
            (rel, lambda d: d["assignments"].__setitem__(unit_id, mode))
            for rel in doc.rels("modes/")
        ],
        "Assign",
    )


def test_save_writes_the_new_file_and_the_project_loads_with_it(
    doc: ModelDocument, project: Path
) -> None:
    doc.add_file(NEW, Unit, new_unit_data(), "Add")
    put_in_every_mode(doc)
    report = doc.save()
    assert report.ok and NEW in report.written and "modes/nominal.yaml" in report.written
    assert (project / NEW).is_file()
    assert not doc.is_modified() and not doc.is_new(NEW) and doc.has(NEW)
    loaded = load_project(project).project
    assert loaded is not None and loaded.units["camera2"].mass_kg == 2.5


def test_save_refuses_an_added_unit_whose_file_appeared_meanwhile(
    doc: ModelDocument, project: Path
) -> None:
    doc.add_file(NEW, Unit, new_unit_data(), "Add")
    (project / NEW).write_text("someone else's file\n", encoding="utf-8")
    report = doc.save()
    assert not report.ok and "changed on disk" in report.message
    assert (project / NEW).read_text(encoding="utf-8") == "someone else's file\n"


def test_save_refuses_while_an_added_unit_has_a_wrong_cell(
    doc: ModelDocument, project: Path
) -> None:
    doc.add_file(NEW, Unit, new_unit_data(), "Add")
    doc.set_value(NEW, ("mass_kg",), "x", "bad")
    report = doc.save()
    assert not report.ok and not (project / NEW).exists()


def test_a_removed_unit_leaves_the_grid_but_stays_on_disk_until_save(
    doc: ModelDocument, project: Path
) -> None:
    rel = "units/radio.yaml"
    assert doc.remove_file(rel, "Remove unit radio")
    assert rel not in doc.rels("units/") and not doc.has(rel)
    assert doc.deleted_files() == [rel] and doc.is_modified()
    assert (project / rel).is_file()
    doc.undo_stack.undo()
    assert doc.has(rel) and not doc.is_modified() and doc.deleted_files() == []
    doc.undo_stack.redo()
    assert not doc.has(rel)


def test_save_deletes_the_file_of_a_removed_unit(doc: ModelDocument, project: Path) -> None:
    rel = "units/radio.yaml"
    doc.remove_file(rel, "Remove")
    report = doc.save()
    assert report.ok and rel in report.written
    assert not (project / rel).exists() and not doc.is_modified()
    assert not doc.has(rel)


def test_save_refuses_to_delete_a_file_that_changed_on_disk(
    doc: ModelDocument, project: Path
) -> None:
    rel = "units/radio.yaml"
    doc.remove_file(rel, "Remove")
    path = project / rel
    path.write_text(path.read_text(encoding="utf-8") + "# edited elsewhere\n", encoding="utf-8")
    report = doc.save()
    assert not report.ok and path.is_file()


def test_removing_an_added_unit_just_takes_it_away_and_undo_brings_it_back(
    doc: ModelDocument,
) -> None:
    doc.add_file(NEW, Unit, new_unit_data(), "Add")
    assert doc.remove_file(NEW, "Remove")
    assert not doc.has(NEW) and not doc.is_modified() and doc.deleted_files() == []
    doc.undo_stack.undo()
    assert doc.has(NEW) and doc.is_new(NEW)
    doc.undo_stack.undo()
    assert not doc.has(NEW)
    # the id is free again
    assert doc.add_file(NEW, Unit, new_unit_data(), "Add")


def test_a_removed_unit_cannot_be_added_again_before_save(doc: ModelDocument) -> None:
    rel = "units/radio.yaml"
    doc.remove_file(rel, "Remove")
    assert not doc.add_file(rel, Unit, new_unit_data(), "Add")


def test_removing_what_is_not_there_does_nothing(doc: ModelDocument) -> None:
    assert not doc.remove_file("units/nothing.yaml", "Remove")
    assert not doc.undo_stack.canUndo()


def test_discard_forgets_added_and_removed_units(doc: ModelDocument, project: Path) -> None:
    doc.add_file(NEW, Unit, new_unit_data(), "Add")
    doc.remove_file("units/radio.yaml", "Remove")
    doc.discard()
    assert not doc.has(NEW) and doc.has("units/radio.yaml") and not doc.is_modified()
    assert (project / "units/radio.yaml").is_file() and not (project / NEW).exists()


def test_a_reload_keeps_an_added_unit_that_is_not_saved(doc: ModelDocument, project: Path) -> None:
    doc.add_file(NEW, Unit, new_unit_data(), "Add")
    doc.reload(project, load_project(project).project)
    assert doc.has(NEW) and doc.is_new(NEW)


def test_a_problem_of_a_removed_unit_does_not_block_saving_the_rest(
    doc: ModelDocument, project: Path
) -> None:
    doc.set_value("units/radio.yaml", ("mass_kg",), "x", "bad")
    assert doc.problems("units/radio.yaml")
    doc.remove_file("units/radio.yaml", "Remove")
    assert not doc.has_problems() and not doc.problems()
    assert doc.save().ok
