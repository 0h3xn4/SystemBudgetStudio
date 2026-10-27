"""Remove from project in the window (D-201): the dialog, the Edit menu entry, the files that
are removed and the ones that cannot be."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from budget_core.blank import BlankAnswers, create_blank_project
from budget_core.io.project_loader import load_project
from budget_core.new_site import SiteAnswers
from budget_gui.main_window import MainWindow
from budget_gui.remove_item_dialog import RemoveItemDialog

pytestmark = pytest.mark.gui

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
BLOCKED = "The ground station gs_north is used by the scenario(s) one_day: change them first."


def _action(window: MainWindow, text: str):  # type: ignore[no-untyped-def]
    for top in window.menuBar().actions():
        menu = top.menu()
        if menu is not None:
            for action in menu.actions():
                if action.text().replace("&", "") == text:
                    return action
    raise AssertionError(f"no menu entry {text!r}")


def _window(qtbot, folder: Path) -> MainWindow:  # type: ignore[no-untyped-def]
    window = MainWindow()
    qtbot.addWidget(window, before_close_func=lambda w: w.editors.discard_all_changes())
    window.open_project(folder)
    assert window.session.project is not None
    return window


@pytest.fixture
def project(tmp_path: Path) -> Path:
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", tmp_path / "p")
    return tmp_path / "p"


# ---- the dialog -----------------------------------------------------------------------------
def test_the_dialog_offers_the_kinds_that_have_items_and_their_ids(qtbot) -> None:  # type: ignore[no-untyped-def]
    dialog = RemoveItemDialog({"link": {"a": "", "b": ""}, "ground_station": {"gs_north": BLOCKED}})
    qtbot.addWidget(dialog)
    assert dialog.windowTitle() == "Remove from project"
    assert [dialog.kind_combo.itemText(i) for i in range(dialog.kind_combo.count())] == [
        "ground station",
        "link",
    ]  # in the order of the kinds, only those that have items
    assert dialog.choice() == ("ground_station", "gs_north")
    dialog.kind_combo.setCurrentIndex(1)
    assert [dialog.id_combo.itemText(i) for i in range(dialog.id_combo.count())] == ["a", "b"]
    assert dialog.choice() == ("link", "a")


def test_a_used_item_shows_why_and_cannot_be_removed(qtbot) -> None:  # type: ignore[no-untyped-def]
    dialog = RemoveItemDialog({"ground_station": {"gs_a": BLOCKED, "gs_b": ""}})
    qtbot.addWidget(dialog)
    assert not dialog.remove_button.isEnabled() and "one_day" in dialog.note_label.text()
    dialog.id_combo.setCurrentIndex(1)
    assert dialog.remove_button.isEnabled() and dialog.note_label.text() == ""


# ---- the window -----------------------------------------------------------------------------
def test_the_entry_has_a_shortcut_and_the_palette_lists_it(qtbot, project: Path) -> None:  # type: ignore[no-untyped-def]
    window = MainWindow()
    qtbot.addWidget(window, before_close_func=lambda w: w.editors.discard_all_changes())
    action = _action(window, "Remove from project…")
    assert action.shortcut().toString() == "Ctrl+Shift+R" and not action.isEnabled()
    assert window.remove_item() is False
    window.open_project(project)
    assert action.isEnabled()
    names = {c.text: c.hint for c in window.palette_commands()}
    assert names["Edit > Remove from project"] == "Ctrl+Shift+R"


def test_the_document_holds_the_stations_targets_and_expendables_of_the_project(  # type: ignore[no-untyped-def]
    qtbot, project: Path
) -> None:
    window = _window(qtbot, project)
    document = window.document
    assert document.rels("ground_stations/") == [
        "ground_stations/gs_north.yaml",
        "ground_stations/gs_south.yaml",
    ]
    assert document.rels("targets/") == ["targets/tgt_plains.yaml"]
    assert document.rels("expendables/") == ["expendables/propellant.yaml"]
    assert not document.is_modified()


def test_the_dialog_gets_every_item_with_the_reason_for_those_that_are_used(  # type: ignore[no-untyped-def]
    qtbot, project: Path
) -> None:
    window = _window(qtbot, project)
    seen: list[dict[str, dict[str, str]]] = []

    def ask(items):  # type: ignore[no-untyped-def]
        seen.append(items)
        return None

    window._ask_removal = ask  # type: ignore[method-assign]
    assert window.remove_item() is False
    items = seen[0]
    assert items["expendable"] == {"propellant": ""}
    assert items["link"] == {"sband_down": "", "xband_down": ""}
    assert "one_day" in items["ground_station"]["gs_north"]
    assert "sband_down" in items["ground_station"]["gs_north"]
    assert items["ground_station"]["gs_south"] != ""  # the scenario and the other link
    assert "one_day" in items["target"]["tgt_plains"]


def test_a_used_item_is_not_removed_even_if_the_dialog_returned_it(  # type: ignore[no-untyped-def]
    qtbot, project: Path
) -> None:
    window = _window(qtbot, project)
    window._ask_removal = lambda _items: ("ground_station", "gs_north")  # type: ignore[method-assign]
    assert window.remove_item() is False
    assert "one_day" in window.statusBar().currentMessage()
    assert window.document.has("ground_stations/gs_north.yaml")
    assert not window.document.is_modified()


def test_an_unused_expendable_and_link_are_removed_in_one_undo_step_each_and_save_deletes_them(  # type: ignore[no-untyped-def]
    qtbot, project: Path
) -> None:
    window = _window(qtbot, project)
    document = window.document
    window._ask_removal = lambda _items: ("expendable", "propellant")  # type: ignore[method-assign]
    assert window.remove_item()
    window._ask_removal = lambda _items: ("link", "xband_down")  # type: ignore[method-assign]
    assert window.remove_item()
    assert not document.has("expendables/propellant.yaml") and not document.has(
        "links/xband_down.yaml"
    )
    assert document.deleted_files() == ["expendables/propellant.yaml", "links/xband_down.yaml"]
    document.undo_stack.undo()
    assert document.has("links/xband_down.yaml")
    document.undo_stack.redo()
    window._confirm_deletion = lambda files: True  # type: ignore[method-assign]
    assert window.save_model()
    assert not (project / "expendables" / "propellant.yaml").exists()
    assert not (project / "links" / "xband_down.yaml").exists()
    assert (project / "links" / "sband_down.yaml").exists()
    loaded = load_project(project).project
    assert loaded is not None and "xband_down" not in loaded.links
    assert "propellant" not in loaded.expendables


def test_a_station_that_was_added_and_not_saved_can_be_removed_again(  # type: ignore[no-untyped-def]
    qtbot, project: Path
) -> None:
    window = _window(qtbot, project)
    window._ask_site = lambda kind, _e: SiteAnswers(kind, "gs_extra", "Extra", 1.0, 2.0, 0.0, 5.0)  # type: ignore[method-assign]
    assert window.add_ground_station()
    window._ask_removal = lambda _items: ("ground_station", "gs_extra")  # type: ignore[method-assign]
    assert window.remove_item()
    assert not window.document.has("ground_stations/gs_extra.yaml")
    assert window.document.deleted_files() == []  # nothing was ever on disk: nothing to delete


def test_a_station_becomes_free_when_the_scenario_and_the_link_that_name_it_are_gone(  # type: ignore[no-untyped-def]
    qtbot, project: Path
) -> None:
    window = _window(qtbot, project)
    # gs_south: named by one_day (sites) and by xband_down (peer)
    window._ask_removal = lambda _items: ("ground_station", "gs_south")  # type: ignore[method-assign]
    assert window.remove_item() is False
    window._ask_removal = lambda _items: ("link", "xband_down")  # type: ignore[method-assign]
    assert window.remove_item()
    window._ask_removal = lambda _items: ("ground_station", "gs_south")  # type: ignore[method-assign]
    assert window.remove_item() is False  # the scenario still lists it
    assert "one_day" in window.statusBar().currentMessage()
    assert "xband_down" not in window.statusBar().currentMessage()  # the link is gone


def test_nothing_to_remove_and_a_cancel_change_nothing(qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    folder = create_blank_project(
        BlankAnswers(project_name="Blank", bus_voltage_v=28.0), tmp_path / "blank"
    )
    window = _window(qtbot, folder)
    window._ask_removal = lambda _items: pytest.fail("the dialog must not open")  # type: ignore[method-assign]
    assert window.remove_item() is False
    assert "nothing" in window.statusBar().currentMessage().lower()
    assert not window.document.is_modified()


def test_a_station_that_is_removed_is_no_longer_offered_as_the_peer_of_a_new_link(  # type: ignore[no-untyped-def]
    qtbot, project: Path
) -> None:
    from budget_core.new_link import LinkAnswers

    window = _window(qtbot, project)
    # free gs_south: remove the link that names it, then take it out of the scenario's sites
    window._ask_removal = lambda _items: ("link", "xband_down")  # type: ignore[method-assign]
    assert window.remove_item()
    window.document.set_value(
        "scenarios/one_day.yaml", ("sites",), ["gs_north", "tgt_plains"], "Edit sites"
    )
    # the rule that names gs_south has to go too for the station to be free
    rules = [
        r
        for r in window.document.data("scenarios/one_day.yaml")["rules"]
        if r.get("site") != "gs_south"
    ]
    window.document.set_value("scenarios/one_day.yaml", ("rules",), rules, "Edit rules")
    window._ask_removal = lambda _items: ("ground_station", "gs_south")  # type: ignore[method-assign]
    assert window.remove_item()
    seen: list[list[str]] = []

    def ask_link(_existing, stations, _pairs):  # type: ignore[no-untyped-def]
        seen.append(stations)
        return LinkAnswers("l9", "L9", "downlink", "gs_north", 437.0, "QPSK", "rate 1/2", (9600.0,))

    window._ask_link = ask_link  # type: ignore[method-assign]
    assert window.add_link()
    assert seen[0] == ["gs_north"]
