"""Add link in the window (D-199): the form, the Edit menu entry and the file that is written. Only
the structure of the link is asked for; the sourced numbers are placeholders for the inputs grid."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from budget_core.blank import BlankAnswers, create_blank_project
from budget_core.io.project_loader import load_project
from budget_core.new_link import LinkAnswers
from budget_core.new_site import SiteAnswers
from budget_gui.add_link_dialog import AddLinkDialog
from budget_gui.main_window import MainWindow

pytestmark = pytest.mark.gui

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
PAIRS = [("QPSK", "rate 1/2"), ("QPSK", "none")]


def _action(window: MainWindow, text: str):  # type: ignore[no-untyped-def]
    for top in window.menuBar().actions():
        menu = top.menu()
        if menu is not None:
            for action in menu.actions():
                if action.text().replace("&", "") == text:
                    return action
    raise AssertionError(f"no menu entry {text!r}")


def link(link_id: str = "uhf_down") -> LinkAnswers:
    return LinkAnswers(
        link_id, "UHF", "downlink", "gs_north", 437.0, "QPSK", "rate 1/2", (9600.0, 19200.0)
    )


def fill(dialog: AddLinkDialog, qtbot) -> None:  # type: ignore[no-untyped-def]
    qtbot.keyClicks(dialog.name_edit, "UHF downlink")
    dialog.peer_combo.setCurrentIndex(0)
    qtbot.keyClicks(dialog.frequency_edit, "437,5")
    dialog.pair_combo.setCurrentIndex(0)
    qtbot.keyClicks(dialog.rates_edit, "9600; 19200")


# ---- the form -------------------------------------------------------------------------------
def test_the_form_starts_empty_and_the_choices_start_unchosen(qtbot) -> None:  # type: ignore[no-untyped-def]
    dialog = AddLinkDialog([], ["gs_north", "gs_south"], PAIRS)
    qtbot.addWidget(dialog)
    assert dialog.windowTitle() == "Add link"
    assert dialog.frequency_edit.text() == "" and dialog.rates_edit.text() == ""
    assert dialog.peer_combo.currentIndex() == -1 and dialog.pair_combo.currentIndex() == -1
    assert [dialog.peer_combo.itemText(i) for i in range(2)] == ["gs_north", "gs_south"]
    assert not dialog.add_button.isEnabled() and dialog.error_label.text() == ""


def test_a_complete_form_is_added_a_decimal_comma_is_read_and_units_are_converted(  # type: ignore[no-untyped-def]
    qtbot,
) -> None:
    dialog = AddLinkDialog(["sband_down"], ["gs_north"], PAIRS)
    qtbot.addWidget(dialog)
    fill(dialog, qtbot)
    assert dialog.id_edit.text() == "uhf_downlink"
    assert dialog.add_button.isEnabled() and dialog.error_label.text() == ""
    answers = dialog.answers()
    assert answers.frequency_mhz == 437.5 and answers.peer == "gs_north"
    assert answers.direction == "downlink"
    assert (answers.modulation, answers.coding) == ("QPSK", "rate 1/2")
    assert tuple(answers.data_rates_bps) == (9600.0, 19200.0)
    dialog.direction_combo.setCurrentIndex(1)
    assert dialog.answers().direction == "uplink"


def test_wrong_numbers_are_named_and_the_button_stays_off(qtbot) -> None:  # type: ignore[no-untyped-def]
    dialog = AddLinkDialog([], ["gs_north"], PAIRS)
    qtbot.addWidget(dialog)
    fill(dialog, qtbot)
    dialog.frequency_edit.setText("2200000000")  # hertz in a megahertz field
    assert not dialog.add_button.isEnabled() and "megahertz" in dialog.error_label.text()
    dialog.frequency_edit.setText("abc")
    assert not dialog.add_button.isEnabled()
    dialog.frequency_edit.setText("437")
    dialog.rates_edit.setText("9600; x")
    assert not dialog.add_button.isEnabled() and "data rate" in dialog.error_label.text()
    dialog.rates_edit.setText("0")
    assert not dialog.add_button.isEnabled()
    dialog.rates_edit.setText("9600")
    assert dialog.add_button.isEnabled()


def test_an_id_of_another_link_is_refused(qtbot) -> None:  # type: ignore[no-untyped-def]
    dialog = AddLinkDialog(["uhf_down"], ["gs_north"], PAIRS)
    qtbot.addWidget(dialog)
    fill(dialog, qtbot)
    dialog.id_edit.setText("UHF_down")
    assert not dialog.add_button.isEnabled() and "exists" in dialog.error_label.text()


def test_an_empty_eb_n0_table_gives_two_text_fields_and_says_why(qtbot) -> None:  # type: ignore[no-untyped-def]
    dialog = AddLinkDialog([], ["gs_north"], [])
    qtbot.addWidget(dialog)
    assert dialog.pair_combo.isHidden()
    assert not dialog.modulation_edit.isHidden() and not dialog.coding_edit.isHidden()
    assert "ebn0_table" in dialog.table_note.text()
    qtbot.keyClicks(dialog.name_edit, "UHF")
    dialog.peer_combo.setCurrentIndex(0)
    qtbot.keyClicks(dialog.frequency_edit, "437")
    qtbot.keyClicks(dialog.rates_edit, "9600")
    qtbot.keyClicks(dialog.modulation_edit, "BPSK")
    assert not dialog.add_button.isEnabled()  # the coding is still missing
    qtbot.keyClicks(dialog.coding_edit, "none")
    assert dialog.add_button.isEnabled()
    assert (dialog.answers().modulation, dialog.answers().coding) == ("BPSK", "none")


# ---- the window -----------------------------------------------------------------------------
def test_the_entry_has_a_shortcut_and_the_palette_lists_it(qtbot) -> None:  # type: ignore[no-untyped-def]
    window = MainWindow()
    qtbot.addWidget(window, before_close_func=lambda w: w.editors.discard_all_changes())
    action = _action(window, "Add link…")
    assert action.shortcut().toString() == "Ctrl+Shift+L" and not action.isEnabled()
    assert window.add_link() is False
    window.open_project(EXAMPLES / "microsat_250kg_eps")
    assert action.isEnabled()
    names = {c.text: c.hint for c in window.palette_commands()}
    assert names["Edit > Add link"] == "Ctrl+Shift+L"


def test_a_link_is_added_in_one_undo_step_and_save_writes_it(  # type: ignore[no-untyped-def]
    tmp_path: Path, qtbot
) -> None:
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", tmp_path / "p")
    window = MainWindow()
    qtbot.addWidget(window, before_close_func=lambda w: w.editors.discard_all_changes())
    window.open_project(tmp_path / "p")
    asked: list[tuple[list[str], list[str], list[tuple[str, str]]]] = []

    def ask(existing, stations, pairs):  # type: ignore[no-untyped-def]
        asked.append((existing, stations, pairs))
        return link()

    window._ask_link = ask  # type: ignore[method-assign]
    assert window.add_link()
    existing, stations, pairs = asked[0]
    assert "sband_down" in existing and {"gs_north", "gs_south"} <= set(stations)
    assert ("QPSK", "rate 1/2") in pairs
    document = window.document
    assert document.has("links/uhf_down.yaml")
    document.undo_stack.undo()
    assert not document.has("links/uhf_down.yaml")
    document.undo_stack.redo()
    assert window.add_link() is False  # the same id again: the one added and not saved is known
    assert "uhf_down" in asked[1][0]
    assert window.save_model()
    loaded = load_project(tmp_path / "p")
    assert loaded.project is not None
    assert loaded.project.links["uhf_down"].peer == "gs_north"


def test_a_project_without_a_ground_station_is_told_to_add_one_first(  # type: ignore[no-untyped-def]
    tmp_path: Path, qtbot
) -> None:
    folder = create_blank_project(
        BlankAnswers(project_name="Blank", bus_voltage_v=28.0), tmp_path / "blank"
    )
    window = MainWindow()
    qtbot.addWidget(window, before_close_func=lambda w: w.editors.discard_all_changes())
    window.open_project(folder)
    window._ask_link = lambda *_a: pytest.fail("the form must not open")  # type: ignore[method-assign]
    assert window.add_link() is False
    assert "ground station" in window.statusBar().currentMessage()
    window._ask_site = lambda kind, _e: SiteAnswers(kind, "gs_a", "A", 1.0, 2.0, 0.0, 5.0)  # type: ignore[method-assign]
    assert window.add_ground_station()
    window._ask_link = lambda _e, stations, pairs: LinkAnswers(  # type: ignore[method-assign]
        "l1", "L1", "uplink", "gs_a", 2000.0, "BPSK", "none", (1000.0,)
    )
    assert window.add_link()  # an empty Eb/N0 table takes any pair
    assert window.document.has("links/l1.yaml")


def test_a_cancel_changes_nothing(tmp_path: Path, qtbot) -> None:  # type: ignore[no-untyped-def]
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", tmp_path / "p")
    window = MainWindow()
    qtbot.addWidget(window, before_close_func=lambda w: w.editors.discard_all_changes())
    window.open_project(tmp_path / "p")
    before = window.document.rels("links/")
    window._ask_link = lambda *_a: None  # type: ignore[method-assign]
    assert window.add_link() is False
    assert window.document.rels("links/") == before
