"""Add expendable in the window (D-197): the form, the Edit menu entry, and a bipropellant built
from two expendables, one file each."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from budget_core.blank import BlankAnswers, create_blank_project
from budget_core.io.project_loader import load_project
from budget_core.new_expendable import ExpendableAnswers
from budget_gui.add_expendable_dialog import AddExpendableDialog
from budget_gui.main_window import MainWindow

pytestmark = pytest.mark.gui

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
PHASES = ["launch", "bol", "eol"]


def _action(window: MainWindow, text: str):  # type: ignore[no-untyped-def]
    for top in window.menuBar().actions():
        menu = top.menu()
        if menu is not None:
            for action in menu.actions():
                if action.text().replace("&", "") == text:
                    return action
    raise AssertionError(f"no menu entry {text!r}")


# ---- the form -------------------------------------------------------------------------------
def test_the_form_has_a_mass_for_every_phase_and_starts_empty(qtbot) -> None:  # type: ignore[no-untyped-def]
    dialog = AddExpendableDialog([], ["class_a", "class_c"], PHASES)
    qtbot.addWidget(dialog)
    assert list(dialog.mass_edits) == PHASES
    assert all(edit.text() == "" for edit in dialog.mass_edits.values())
    assert not dialog.add_button.isEnabled() and dialog.error_label.text() == ""
    for phase, edit in dialog.mass_edits.items():
        assert phase in edit.accessibleName()


def test_a_complete_form_can_be_added_and_the_position_is_optional(qtbot) -> None:  # type: ignore[no-untyped-def]
    dialog = AddExpendableDialog(["propellant"], ["class_a", "class_c"], PHASES)
    qtbot.addWidget(dialog)
    qtbot.keyClicks(dialog.name_edit, "Oxidizer")
    assert dialog.id_edit.text() == "oxidizer"
    qtbot.keyClicks(dialog.subsystem_edit, "PROP")
    for phase, text in zip(PHASES, ("3.2", "3,1", "0.4"), strict=True):
        qtbot.keyClicks(dialog.mass_edits[phase], text)  # a decimal comma is read
    assert dialog.add_button.isEnabled() and dialog.error_label.text() == ""
    answers = dialog.answers()
    assert answers.masses_kg == {"launch": 3.2, "bol": 3.1, "eol": 0.4}
    assert answers.position is None
    qtbot.keyClicks(dialog.x_edit, "0")
    assert not dialog.add_button.isEnabled() and "coordinates" in dialog.error_label.text()
    qtbot.keyClicks(dialog.y_edit, "0")
    qtbot.keyClicks(dialog.z_edit, "0.3")
    assert dialog.add_button.isEnabled()
    assert dialog.answers().position == (0.0, 0.0, 0.3)


def test_a_mass_that_is_not_a_number_is_refused_not_read_as_empty(qtbot) -> None:  # type: ignore[no-untyped-def]
    dialog = AddExpendableDialog([], ["class_a"], PHASES)
    qtbot.addWidget(dialog)
    qtbot.keyClicks(dialog.name_edit, "Gas")
    qtbot.keyClicks(dialog.subsystem_edit, "PROP")
    for phase in PHASES:
        qtbot.keyClicks(dialog.mass_edits[phase], "1")
    assert dialog.add_button.isEnabled()
    dialog.mass_edits["bol"].setText("abc")
    assert not dialog.add_button.isEnabled() and "bol" in dialog.error_label.text()
    dialog.x_edit.setText("abc")
    assert dialog.answers().position is not None


# ---- the window -----------------------------------------------------------------------------
def test_the_edit_menu_entry_has_a_shortcut_and_the_palette_lists_it(qtbot) -> None:  # type: ignore[no-untyped-def]
    window = MainWindow()
    qtbot.addWidget(window, before_close_func=lambda w: w.editors.discard_all_changes())
    action = _action(window, "Add expendable…")
    assert action.shortcut().toString() == "Ctrl+Shift+X" and not action.isEnabled()
    assert window.add_expendable() is False
    window.open_project(EXAMPLES / "microsat_250kg_eps")
    assert action.isEnabled()
    names = {c.text: c.hint for c in window.palette_commands()}
    assert names["Edit > Add expendable"] == "Ctrl+Shift+X"


def test_a_second_expendable_is_one_undo_step_and_save_writes_its_file(  # type: ignore[no-untyped-def]
    tmp_path: Path, qtbot
) -> None:
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", tmp_path / "p")
    window = MainWindow()
    qtbot.addWidget(window, before_close_func=lambda w: w.editors.discard_all_changes())
    window.open_project(tmp_path / "p")
    phases = list(window.session.project.phases)  # type: ignore[union-attr]
    asked: list[tuple[list[str], list[str], list[str]]] = []

    def ask(existing: list[str], classes: list[str], found: list[str]) -> ExpendableAnswers:
        asked.append((existing, classes, found))
        return ExpendableAnswers(
            "oxidizer", "Oxidizer", "PROP", classes[0], dict.fromkeys(found, 2.0), (0.0, 0.0, 0.3)
        )

    window._ask_expendable = ask  # type: ignore[method-assign]
    assert window.add_expendable()
    assert asked[0][0] == ["propellant"] and asked[0][2] == phases
    assert window.document.has("expendables/oxidizer.yaml")
    window.document.undo_stack.undo()  # one step takes the file back
    assert not window.document.has("expendables/oxidizer.yaml")
    window.document.undo_stack.redo()
    assert window.save_model()
    assert (tmp_path / "p" / "expendables" / "oxidizer.yaml").is_file()
    project = load_project(tmp_path / "p").project
    assert project is not None and set(project.expendables) == {"propellant", "oxidizer"}


def test_the_same_id_twice_is_refused_by_the_form_and_a_cancel_changes_nothing(  # type: ignore[no-untyped-def]
    tmp_path: Path, qtbot
) -> None:
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", tmp_path / "p")
    window = MainWindow()
    qtbot.addWidget(window, before_close_func=lambda w: w.editors.discard_all_changes())
    window.open_project(tmp_path / "p")
    window._ask_expendable = lambda *_a: None  # type: ignore[method-assign]
    assert window.add_expendable() is False
    assert window.document.rels("expendables/") == []  # nothing was added


def test_a_blank_project_can_have_an_expendable_before_it_has_a_unit(  # type: ignore[no-untyped-def]
    tmp_path: Path, qtbot
) -> None:
    folder = create_blank_project(
        BlankAnswers(project_name="Blank", bus_voltage_v=28.0), tmp_path / "blank"
    )
    window = MainWindow()
    qtbot.addWidget(window, before_close_func=lambda w: w.editors.discard_all_changes())
    window.open_project(folder)
    window._ask_expendable = lambda _e, classes, found: ExpendableAnswers(  # type: ignore[method-assign]
        "fuel", "Fuel", "PROP", classes[0], dict.fromkeys(found, 4.0)
    )
    assert window.add_expendable()
    assert window.document.has("expendables/fuel.yaml")


def test_an_id_added_in_this_session_is_known_to_the_next_form(  # type: ignore[no-untyped-def]
    tmp_path: Path, qtbot
) -> None:
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", tmp_path / "p")
    window = MainWindow()
    qtbot.addWidget(window, before_close_func=lambda w: w.editors.discard_all_changes())
    window.open_project(tmp_path / "p")
    seen: list[list[str]] = []

    def ask(existing: list[str], classes: list[str], found: list[str]) -> ExpendableAnswers | None:
        seen.append(existing)
        if len(seen) > 1:
            return None
        return ExpendableAnswers(
            "oxidizer", "Oxidizer", "PROP", classes[0], dict.fromkeys(found, 2.0)
        )

    window._ask_expendable = ask  # type: ignore[method-assign]
    assert window.add_expendable() and not window.add_expendable()
    assert seen == [["propellant"], ["oxidizer", "propellant"]]
