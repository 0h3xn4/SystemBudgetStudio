"""Spacecraft modes in the window (D-188): the grid of assignments, Add and Remove spacecraft mode,
the Edit menu entries, and a blank project built up until it loads."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from budget_core.blank import BlankAnswers, create_blank_project
from budget_core.io.project_loader import load_project
from budget_core.new_mode import ModeAnswers
from budget_core.new_unit import UnitAnswers
from budget_gui.add_mode_dialog import AddModeDialog
from budget_gui.main_window import MainWindow
from budget_gui.model_document import ModelDocument
from budget_gui.model_pages import SpacecraftModesPage

pytestmark = pytest.mark.gui

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


@pytest.fixture
def example(tmp_path: Path) -> Path:
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", tmp_path / "p")
    return tmp_path / "p"


@pytest.fixture
def page(example: Path, qtbot) -> SpacecraftModesPage:  # type: ignore[no-untyped-def]
    document = ModelDocument()
    document.load(example, load_project(example).project)
    widget = SpacecraftModesPage(document)
    qtbot.addWidget(widget)
    return widget


def answers(mode_id: str = "detumble", copy_of: str = "") -> ModeAnswers:
    return ModeAnswers(mode_id, "Detumble", "Slow the tumbling.", copy_of)


# ---- the form -------------------------------------------------------------------------------
def test_the_form_needs_a_name_and_an_id(qtbot) -> None:  # type: ignore[no-untyped-def]
    dialog = AddModeDialog(["safe"], ["obc"])
    qtbot.addWidget(dialog)
    assert not dialog.add_button.isEnabled() and dialog.error_label.text() == ""
    qtbot.keyClicks(dialog.name_edit, "Detumble")
    assert dialog.id_edit.text() == "detumble" and dialog.add_button.isEnabled()
    assert dialog.answers() == ModeAnswers("detumble", "Detumble", "", "")
    dialog.start_combo.setCurrentIndex(1)
    assert dialog.answers().copy_of == "safe"


def test_the_form_says_at_once_that_a_project_without_units_has_no_mode(qtbot) -> None:  # type: ignore[no-untyped-def]
    dialog = AddModeDialog([], [])
    qtbot.addWidget(dialog)
    assert "add a unit first" in dialog.error_label.text()
    assert not dialog.add_button.isEnabled()


# ---- the page -------------------------------------------------------------------------------
def test_the_grid_has_a_row_for_every_unit_in_every_mode(page: SpacecraftModesPage) -> None:
    modes = page.mode_ids()
    units = page.unit_power_modes()
    assert modes and units
    assert page.assignments.rowCount() == len(modes) * len(units)
    row = page.assignments.rows_of(modes[0])[0]
    assert page.assignments.id_text(row, 0) == modes[0]
    assert page.assignments.id_text(row, 1) in units


def test_add_mode_starts_every_unit_off_and_is_one_undo_step(page: SpacecraftModesPage) -> None:
    page._ask = lambda *_a: answers()  # type: ignore[method-assign]
    before = page.assignments.rowCount()
    assert page.add_mode()
    units = page.unit_power_modes()
    assert page.assignments.rowCount() == before + len(units)
    assigned = page.document.value("modes/detumble.yaml", ("assignments",))
    assert set(assigned) == set(units)
    for unit_id, names in units.items():
        wanted = next((n for n in names if n.lower() == "off"), names[0])
        assert assigned[unit_id] == wanted
    assert "Added detumble" in page.feedback_label.text()
    page.document.undo_stack.undo()
    assert page.assignments.rowCount() == before and not page.document.has("modes/detumble.yaml")


def test_add_mode_can_copy_another_mode(page: SpacecraftModesPage) -> None:
    source = page.mode_ids()[0]
    page._ask = lambda *_a: answers(copy_of=source)  # type: ignore[method-assign]
    assert page.add_mode()
    copied = page.document.value(f"modes/{source}.yaml", ("assignments",))
    assert page.document.value("modes/detumble.yaml", ("assignments",)) == copied
    assert "a copy of" in page.feedback_label.text()


def test_add_mode_refuses_a_project_without_units(tmp_path: Path, qtbot) -> None:  # type: ignore[no-untyped-def]
    folder = create_blank_project(
        BlankAnswers(project_name="Blank", bus_voltage_v=28.0), tmp_path / "blank"
    )
    document = ModelDocument()
    document.load(folder, load_project(folder).project)
    widget = SpacecraftModesPage(document)
    qtbot.addWidget(widget)
    assert not widget.add_mode()
    assert "add a unit first" in widget.feedback_label.text()


def test_a_cell_takes_a_power_mode_of_the_unit_and_refuses_another(
    page: SpacecraftModesPage,
) -> None:
    modes = page.assignments
    rows = modes.rows_of(page.mode_ids()[0])
    row = next(r for r in rows if len(modes.power_modes_of(modes.id_text(r, 1))) > 1)
    unit = modes.id_text(row, 1)
    names = modes.power_modes_of(unit)
    other = next(n for n in names if n != modes.display(row, 2))
    assert modes.set_text(row, 2, other)
    assert modes.display(row, 2) == other
    assert not modes.set_text(row, 2, "no_such_mode")
    assert modes.display(row, 2) == other  # unchanged
    assert unit in page.feedback_label.text() and "no power mode of that name" in (
        page.feedback_label.text()
    )


def test_remove_mode_is_refused_while_a_scenario_names_it(page: SpacecraftModesPage) -> None:
    used = page.document.value("scenarios/one_day.yaml", ("default_mode",))
    page.table.select_cell(page.assignments.rows_of(used)[0], 2)
    assert not page.remove_mode()
    assert "one_day" in page.feedback_label.text() and page.document.has(f"modes/{used}.yaml")


def test_remove_mode_deletes_the_file_on_save_after_asking(
    example: Path,
    qtbot,  # type: ignore[no-untyped-def]
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from PySide6.QtWidgets import QMessageBox

    window = MainWindow()
    qtbot.addWidget(window, before_close_func=lambda w: w.editors.discard_all_changes())
    window.open_project(example)
    page = window.spacecraft_modes_page
    page._ask = lambda *_a: answers()  # type: ignore[method-assign]
    assert page.add_mode()
    assert window.save_model()
    assert (example / "modes" / "detumble.yaml").is_file()
    qtbot.waitUntil(
        lambda: window.session.project is not None and "detumble" in window.session.project.modes,
        timeout=20000,
    )

    page.table.select_cell(page.assignments.rows_of("detumble")[0], 2)
    assert page.remove_mode()
    assert page.document.deleted_files() == ["modes/detumble.yaml"]
    monkeypatch.setattr(QMessageBox, "question", lambda *_a, **_k: QMessageBox.StandardButton.Yes)
    assert window.save_model()
    assert not (example / "modes" / "detumble.yaml").exists()


# ---- the Edit menu and Ctrl+K ---------------------------------------------------------------
def _action(window: MainWindow, text: str):  # type: ignore[no-untyped-def]
    for top in window.menuBar().actions():
        menu = top.menu()
        if menu is not None:
            for action in menu.actions():
                if action.text().replace("&", "") == text:
                    return action
    raise AssertionError(f"no menu entry {text!r}")


def test_the_edit_menu_has_the_two_entries_with_shortcuts_and_the_palette_lists_them(
    example: Path,
    qtbot,  # type: ignore[no-untyped-def]
) -> None:
    window = MainWindow()
    qtbot.addWidget(window, before_close_func=lambda w: w.editors.discard_all_changes())
    add, remove = _action(window, "Add spacecraft mode…"), _action(window, "Remove spacecraft mode")
    assert add.shortcut().toString() == "Ctrl+Shift+M"
    assert remove.shortcut().toString() == "Ctrl+Shift+Backspace"
    assert not add.isEnabled() and not remove.isEnabled()
    assert window.add_spacecraft_mode() is False and window.remove_spacecraft_mode() is False
    window.open_project(example)
    assert add.isEnabled() and remove.isEnabled()
    names = {c.text: c.hint for c in window.palette_commands()}
    assert names["Edit > Add spacecraft mode"] == "Ctrl+Shift+M"
    assert "Edit > Remove spacecraft mode" in names
    assert "Ctrl+Shift+M" in window.spacecraft_modes_page.add_button.toolTip()


def test_add_mode_from_another_area_brings_the_grid_to_the_front(
    example: Path,
    qtbot,  # type: ignore[no-untyped-def]
) -> None:
    window = MainWindow()
    qtbot.addWidget(window, before_close_func=lambda w: w.editors.discard_all_changes())
    window.open_project(example)
    window.show_view(window.mass_view)
    window.spacecraft_modes_page._ask = lambda *_a: answers()  # type: ignore[method-assign]
    _action(window, "Add spacecraft mode…").trigger()
    assert window.workspace.currentWidget() is window.editors
    assert window.editors.currentWidget() is window.spacecraft_modes_page
    assert "modes/detumble.yaml" in window.document.rels("modes/")


# ---- a blank project, built up in the window ------------------------------------------------
def test_a_blank_project_gets_a_unit_and_a_mode_and_loads_without_errors(
    tmp_path: Path,
    qtbot,  # type: ignore[no-untyped-def]
) -> None:
    folder = create_blank_project(
        BlankAnswers(project_name="Blank", bus_voltage_v=28.0), tmp_path / "blank"
    )
    window = MainWindow()
    qtbot.addWidget(window, before_close_func=lambda w: w.editors.discard_all_changes())
    window.open_project(folder)
    unit = UnitAnswers(
        unit_id="obc",
        name="Computer",
        subsystem="DH",
        bus="main",
        maturity="class_a",
        mass_kg=0.5,
        mode_name="on",
        avg_power_w=1.0,
        peak_power_w=2.0,
    )
    window.units_page._ask = lambda *_a: unit  # type: ignore[method-assign]
    assert window.add_unit()
    window.spacecraft_modes_page._ask = lambda *_a: answers("nominal")  # type: ignore[method-assign]
    assert window.add_spacecraft_mode()
    # the unit starts in its first power mode (it has no "off"), and the message says so
    assert "first" in window.spacecraft_modes_page.feedback_label.text()
    assert window.save_model()
    qtbot.waitUntil(
        lambda: window.session.project is not None and "nominal" in window.session.project.modes,
        timeout=20000,
    )
    assert (folder / "modes" / "nominal.yaml").is_file()
    assert not [p for p in window.session.problems if p.severity.name == "ERROR"]
