"""The editable model behind the grids: edits, undo, validation, Save (UX step 2, D-159)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from budget_core.io.project_loader import load_project
from budget_gui.model_document import ModelDocument, set_at, value_at

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
RADIO = "units/radio.yaml"
DOWNLINK = ("modes", 5)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", tmp_path / "p")
    return tmp_path / "p"


@pytest.fixture
def doc(project: Path, qtbot) -> ModelDocument:  # type: ignore[no-untyped-def]
    document = ModelDocument()
    document.load(project, load_project(project).project)
    return document


def avg(doc: ModelDocument) -> object:
    return doc.value(RADIO, (*DOWNLINK, "avg_power_w"))


def test_it_holds_every_unit_link_and_configuration_file(doc: ModelDocument) -> None:
    assert len(doc.rels("units/")) == 18 and len(doc.rels("links/")) == 2
    assert "config/margin_policy.yaml" in doc.rels("config/")
    assert avg(doc) == 28.0 and not doc.is_modified()


def test_an_edit_is_one_undo_step_and_marks_the_document_modified(doc: ModelDocument) -> None:
    dirty: list[bool] = []
    doc.dirty_changed.connect(dirty.append)
    assert doc.set_value(RADIO, (*DOWNLINK, "avg_power_w"), 30.0, "Edit radio")
    assert avg(doc) == 30.0 and doc.is_modified() and doc.modified_files() == [RADIO]
    assert doc.undo_stack.undoText() == "Edit radio"
    doc.undo_stack.undo()
    assert avg(doc) == 28.0 and not doc.is_modified()
    doc.undo_stack.redo()
    assert avg(doc) == 30.0 and dirty == [True, False, True]


def test_an_edit_that_changes_nothing_is_not_a_step(doc: ModelDocument) -> None:
    assert not doc.set_value(RADIO, (*DOWNLINK, "avg_power_w"), 28.0, "same")
    assert not doc.undo_stack.canUndo()


def test_a_value_with_a_unit_is_converted_when_it_is_valid(doc: ModelDocument) -> None:
    doc.set_value(RADIO, (*DOWNLINK, "avg_power_w"), "30000 mW", "Edit")
    assert avg(doc) == pytest.approx(30.0) and not doc.problems(RADIO)


def test_a_value_that_breaks_the_model_is_kept_and_explained(doc: ModelDocument) -> None:
    doc.set_value(RADIO, (*DOWNLINK, "peak_power_w"), 10.0, "Edit")  # below the average
    problem = doc.problem_at(RADIO, (*DOWNLINK, "peak_power_w"))
    assert problem is not None and "peak" in problem.message.lower()
    assert doc.value(RADIO, (*DOWNLINK, "peak_power_w")) == 10.0  # kept, so it can be corrected
    doc.set_value(RADIO, (*DOWNLINK, "peak_power_w"), 45.0, "Edit")
    assert not doc.problems(RADIO)


def test_a_message_never_holds_the_typed_text(doc: ModelDocument) -> None:
    doc.set_value(RADIO, (*DOWNLINK, "avg_power_w"), "secret-text", "Edit")
    for problem in doc.problems(RADIO):
        assert "secret-text" not in problem.format()


def test_a_paste_of_many_cells_is_one_step_across_files(doc: ModelDocument) -> None:
    changes = [
        (rel, lambda data: set_at(data, ("mass_kg",), 9.0))
        for rel in ("units/obc.yaml", "units/gnss.yaml")
    ]
    assert doc.edit(changes, "Paste 2 cells")
    assert doc.value("units/obc.yaml", ("mass_kg",)) == 9.0
    assert doc.value("units/gnss.yaml", ("mass_kg",)) == 9.0
    doc.undo_stack.undo()
    assert not doc.is_modified()


def test_none_removes_an_optional_field(doc: ModelDocument) -> None:
    path = ("temperature_limits", "operating_max_k")
    assert doc.value(RADIO, path) is not None
    doc.set_value(RADIO, path, None, "Clear")
    assert doc.value(RADIO, path) is None and not doc.problems(RADIO)


def test_save_writes_only_the_changed_file_and_keeps_comments(
    doc: ModelDocument, project: Path
) -> None:
    path = project / RADIO
    path.write_text("# data sheet rev B\n" + path.read_text(encoding="utf-8"), encoding="utf-8")
    doc.load(project, load_project(project).project)
    other = (project / "units" / "obc.yaml").read_bytes()
    doc.set_value(RADIO, (*DOWNLINK, "avg_power_w"), 30.0, "Edit")
    report = doc.save()
    assert report.ok and report.written == (RADIO,)
    text = path.read_text(encoding="utf-8")
    assert text.startswith("# data sheet rev B") and "avg_power_w: 30.0" in text
    assert (project / "units" / "obc.yaml").read_bytes() == other
    assert not doc.is_modified()
    assert load_project(project).project.units["radio"].modes[5].avg_power_w == 30.0  # type: ignore[union-attr]


def test_undo_after_save_makes_the_document_modified_again(
    doc: ModelDocument, project: Path
) -> None:
    doc.set_value(RADIO, (*DOWNLINK, "avg_power_w"), 30.0, "Edit")
    assert doc.save().ok
    doc.undo_stack.undo()
    assert avg(doc) == 28.0 and doc.is_modified()
    assert doc.save().ok
    assert load_project(project).project.units["radio"].modes[5].avg_power_w == 28.0  # type: ignore[union-attr]


def test_nothing_is_written_while_a_cell_is_wrong(doc: ModelDocument, project: Path) -> None:
    before = (project / RADIO).read_bytes()
    doc.set_value(RADIO, (*DOWNLINK, "avg_power_w"), -1.0, "Edit")
    report = doc.save()
    assert not report.ok and "need correcting" in report.message
    assert (project / RADIO).read_bytes() == before


def test_nothing_is_written_over_a_file_that_changed_on_disk(
    doc: ModelDocument, project: Path
) -> None:
    doc.set_value(RADIO, (*DOWNLINK, "avg_power_w"), 30.0, "Edit")
    path = project / RADIO
    path.write_text(path.read_text(encoding="utf-8") + "\n# edited elsewhere\n", encoding="utf-8")
    report = doc.save()
    assert not report.ok and "changed on disk" in report.message and RADIO in report.message
    assert "avg_power_w: 28.0" in path.read_text(encoding="utf-8")


def test_discard_forgets_the_edits_and_the_history(doc: ModelDocument) -> None:
    doc.set_value(RADIO, (*DOWNLINK, "avg_power_w"), 30.0, "Edit")
    doc.discard()
    assert avg(doc) == 28.0 and not doc.is_modified() and not doc.undo_stack.canUndo()


def test_a_reload_keeps_pending_edits_and_refreshes_the_rest(
    doc: ModelDocument, project: Path
) -> None:
    doc.set_value(RADIO, (*DOWNLINK, "avg_power_w"), 30.0, "Edit")
    obc = project / "units" / "obc.yaml"
    obc.write_text(obc.read_text(encoding="utf-8").replace("mass_kg: 3.0", "mass_kg: 3.6"))
    doc.reload(project, load_project(project).project)
    assert avg(doc) == 30.0  # the pending edit stays
    assert doc.value("units/obc.yaml", ("mass_kg",)) == pytest.approx(3.6)  # the file shows
    assert doc.modified_files() == [RADIO]


def test_a_reload_after_save_keeps_the_undo_history(doc: ModelDocument, project: Path) -> None:
    doc.set_value(RADIO, (*DOWNLINK, "avg_power_w"), 30.0, "Edit")
    doc.save()
    doc.reload(project, load_project(project).project)
    assert doc.undo_stack.canUndo() and avg(doc) == 30.0


def test_a_reload_of_another_project_starts_again(
    doc: ModelDocument, tmp_path: Path, project: Path
) -> None:
    other = tmp_path / "q"
    shutil.copytree(EXAMPLES / "microsat_250kg", other)
    doc.set_value(RADIO, (*DOWNLINK, "avg_power_w"), 30.0, "Edit")
    doc.discard()
    doc.reload(other, load_project(other).project)
    assert doc.root == other and not doc.undo_stack.canUndo()


def test_value_helpers() -> None:
    data = {"a": {"b": [1, {"c": 2}]}}
    assert value_at(data, ("a", "b", 1, "c")) == 2 and value_at(data, ("a", "x")) is None
    set_at(data, ("a", "b", 1, "c"), 5)
    assert data["a"]["b"][1]["c"] == 5
    set_at(data, ("a", "b", 1, "c"), None)
    assert data["a"]["b"][1] == {}
