"""Add Eb/N0 entry in the window (D-200): the form, the Edit menu entry, the row that is added to
`config/ebn0_table.yaml` and the link form that offers the new pair."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from budget_core.blank import BlankAnswers, create_blank_project
from budget_core.io.project_loader import load_project
from budget_core.new_ebn0 import Ebn0Answers
from budget_core.new_link import LinkAnswers
from budget_core.new_site import SiteAnswers
from budget_gui.add_ebn0_dialog import AddEbn0Dialog
from budget_gui.main_window import MainWindow

pytestmark = pytest.mark.gui

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
REL = "config/ebn0_table.yaml"


def _action(window: MainWindow, text: str):  # type: ignore[no-untyped-def]
    for top in window.menuBar().actions():
        menu = top.menu()
        if menu is not None:
            for action in menu.actions():
                if action.text().replace("&", "") == text:
                    return action
    raise AssertionError(f"no menu entry {text!r}")


def _open(window: MainWindow, folder: Path) -> None:
    window.open_project(folder)
    assert window.session.project is not None


# ---- the form -------------------------------------------------------------------------------
def test_the_form_starts_empty_and_asks_for_the_pair_only(qtbot) -> None:  # type: ignore[no-untyped-def]
    dialog = AddEbn0Dialog([("QPSK", "none")])
    qtbot.addWidget(dialog)
    assert dialog.windowTitle() == "Add Eb/N0 entry"
    assert dialog.modulation_edit.text() == "" and dialog.coding_edit.text() == ""
    assert not dialog.add_button.isEnabled() and dialog.error_label.text() == ""
    assert "source TBD" in dialog.intro.text()  # the required value is a placeholder


def test_a_new_pair_is_accepted_and_one_that_exists_is_refused(qtbot) -> None:  # type: ignore[no-untyped-def]
    dialog = AddEbn0Dialog([("QPSK", "none")])
    qtbot.addWidget(dialog)
    qtbot.keyClicks(dialog.modulation_edit, "BPSK")
    assert not dialog.add_button.isEnabled()  # the coding is still missing
    qtbot.keyClicks(dialog.coding_edit, "rate 1/2")
    assert dialog.add_button.isEnabled() and dialog.error_label.text() == ""
    assert dialog.answers() == Ebn0Answers("BPSK", "rate 1/2")
    dialog.modulation_edit.setText("qpsk")
    dialog.coding_edit.setText("None")
    assert not dialog.add_button.isEnabled() and "already" in dialog.error_label.text()


# ---- the window -----------------------------------------------------------------------------
def test_the_entry_has_a_shortcut_and_the_palette_lists_it(qtbot) -> None:  # type: ignore[no-untyped-def]
    window = MainWindow()
    qtbot.addWidget(window, before_close_func=lambda w: w.editors.discard_all_changes())
    action = _action(window, "Add Eb/N0 entry…")
    assert action.shortcut().toString() == "Ctrl+Shift+B" and not action.isEnabled()
    assert window.add_ebn0_entry() is False
    _open(window, EXAMPLES / "microsat_250kg_eps")
    assert action.isEnabled()
    names = {c.text: c.hint for c in window.palette_commands()}
    assert names["Edit > Add Eb/N0 entry"] == "Ctrl+Shift+B"


def test_a_row_is_added_in_one_undo_step_with_a_placeholder_and_save_writes_it(  # type: ignore[no-untyped-def]
    tmp_path: Path, qtbot
) -> None:
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", tmp_path / "p")
    window = MainWindow()
    qtbot.addWidget(window, before_close_func=lambda w: w.editors.discard_all_changes())
    _open(window, tmp_path / "p")
    asked: list[list[tuple[str, str]]] = []

    def ask(pairs):  # type: ignore[no-untyped-def]
        asked.append(pairs)
        return Ebn0Answers("BPSK", "rate 1/2")

    window._ask_ebn0 = ask  # type: ignore[method-assign]
    before = len(window.document.data(REL)["entries"])
    assert window.add_ebn0_entry()
    assert ("QPSK", "rate 1/2") in asked[0]  # the pairs of the table are known
    entries = window.document.data(REL)["entries"]
    assert len(entries) == before + 1
    assert entries[-1]["required_ebn0_db"]["value"] is None
    assert entries[-1]["required_ebn0_db"]["source"] == "TBD"
    assert window.add_ebn0_entry() is False  # the same pair again is not added a second time
    assert ("BPSK", "rate 1/2") in asked[1]  # the one added and not saved yet is known
    window.document.undo_stack.undo()
    assert len(window.document.data(REL)["entries"]) == before
    window.document.undo_stack.redo()
    assert window.save_model()
    project = load_project(tmp_path / "p").project
    assert project is not None and project.config.ebn0_table is not None
    pairs = [(e.modulation, e.coding) for e in project.config.ebn0_table.entries]
    assert ("BPSK", "rate 1/2") in pairs


def test_a_project_without_a_table_file_gets_one(tmp_path: Path, qtbot) -> None:  # type: ignore[no-untyped-def]
    folder = create_blank_project(
        BlankAnswers(project_name="Blank", bus_voltage_v=28.0), tmp_path / "blank"
    )
    (folder / "config" / "ebn0_table.yaml").unlink()
    window = MainWindow()
    qtbot.addWidget(window, before_close_func=lambda w: w.editors.discard_all_changes())
    _open(window, folder)
    assert not window.document.has(REL)
    window._ask_ebn0 = lambda _pairs: Ebn0Answers("BPSK", "none")  # type: ignore[method-assign]
    assert window.add_ebn0_entry()
    assert window.document.has(REL) and len(window.document.data(REL)["entries"]) == 1
    window.document.undo_stack.undo()
    assert not window.document.has(REL)


def test_the_link_form_offers_a_pair_that_is_added_and_not_saved_yet(  # type: ignore[no-untyped-def]
    tmp_path: Path, qtbot
) -> None:
    folder = create_blank_project(
        BlankAnswers(project_name="Blank", bus_voltage_v=28.0), tmp_path / "blank"
    )
    window = MainWindow()
    qtbot.addWidget(window, before_close_func=lambda w: w.editors.discard_all_changes())
    _open(window, folder)
    window._ask_site = lambda kind, _e: SiteAnswers(kind, "gs_a", "A", 1.0, 2.0, 0.0, 5.0)  # type: ignore[method-assign]
    assert window.add_ground_station()
    window._ask_ebn0 = lambda _pairs: Ebn0Answers("BPSK", "none")  # type: ignore[method-assign]
    assert window.add_ebn0_entry()
    seen: list[list[tuple[str, str]]] = []

    def ask_link(_existing, _stations, pairs):  # type: ignore[no-untyped-def]
        seen.append(pairs)
        return LinkAnswers("l1", "L1", "uplink", "gs_a", 2000.0, "BPSK", "none", (1000.0,))

    window._ask_link = ask_link  # type: ignore[method-assign]
    assert window.add_link()
    assert seen[0] == [("BPSK", "none")]


def test_a_cancel_changes_nothing(tmp_path: Path, qtbot) -> None:  # type: ignore[no-untyped-def]
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", tmp_path / "p")
    window = MainWindow()
    qtbot.addWidget(window, before_close_func=lambda w: w.editors.discard_all_changes())
    _open(window, tmp_path / "p")
    before = window.document.data(REL)["entries"]
    window._ask_ebn0 = lambda _pairs: None  # type: ignore[method-assign]
    assert window.add_ebn0_entry() is False
    assert window.document.data(REL)["entries"] == before
    assert not window.document.is_modified()
