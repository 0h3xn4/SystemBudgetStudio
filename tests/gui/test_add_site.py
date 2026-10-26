"""Add ground station and Add imaging target in the window (D-198): the form, the two Edit menu
entries and the files that are written."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from budget_core.blank import BlankAnswers, create_blank_project
from budget_core.io.project_loader import load_project
from budget_core.new_site import GROUND_STATION, TARGET, SiteAnswers
from budget_gui.add_site_dialog import AddSiteDialog
from budget_gui.main_window import MainWindow

pytestmark = pytest.mark.gui

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


def _action(window: MainWindow, text: str):  # type: ignore[no-untyped-def]
    for top in window.menuBar().actions():
        menu = top.menu()
        if menu is not None:
            for action in menu.actions():
                if action.text().replace("&", "") == text:
                    return action
    raise AssertionError(f"no menu entry {text!r}")


def site(kind: str = GROUND_STATION, site_id: str = "gs_east") -> SiteAnswers:
    return SiteAnswers(kind, site_id, "East", 52.5, 13.4, 40.0, 8.0)


# ---- the form -------------------------------------------------------------------------------
def test_the_title_and_the_button_say_what_is_added(qtbot) -> None:  # type: ignore[no-untyped-def]
    station = AddSiteDialog(GROUND_STATION, [])
    target = AddSiteDialog(TARGET, [])
    qtbot.addWidget(station)
    qtbot.addWidget(target)
    assert station.windowTitle() == "Add ground station" and "ground station" in (
        station.add_button.text().lower()
    )
    assert target.windowTitle() == "Add imaging target"


def test_the_form_starts_empty_and_takes_no_default_number(qtbot) -> None:  # type: ignore[no-untyped-def]
    dialog = AddSiteDialog(GROUND_STATION, [])
    qtbot.addWidget(dialog)
    for edit in (dialog.latitude_edit, dialog.longitude_edit, dialog.altitude_edit):
        assert edit.text() == ""
    assert dialog.elevation_edit.text() == ""
    assert not dialog.add_button.isEnabled() and dialog.error_label.text() == ""


def test_a_complete_form_can_be_added_and_a_wrong_number_is_named(qtbot) -> None:  # type: ignore[no-untyped-def]
    dialog = AddSiteDialog(GROUND_STATION, ["gs_north"])
    qtbot.addWidget(dialog)
    qtbot.keyClicks(dialog.name_edit, "East station")
    assert dialog.id_edit.text() == "east_station"
    for edit, text in (
        (dialog.latitude_edit, "52,5"),  # a decimal comma is read
        (dialog.longitude_edit, "13.4"),
        (dialog.altitude_edit, "40"),
        (dialog.elevation_edit, "8"),
    ):
        qtbot.keyClicks(edit, text)
    assert dialog.add_button.isEnabled() and dialog.error_label.text() == ""
    assert dialog.answers().latitude_deg == 52.5 and dialog.answers().kind == GROUND_STATION
    dialog.latitude_edit.setText("95")
    assert not dialog.add_button.isEnabled() and "latitude" in dialog.error_label.text()
    dialog.latitude_edit.setText("abc")  # not a number is refused, not read as empty
    assert not dialog.add_button.isEnabled()


def test_an_id_used_by_another_site_is_refused(qtbot) -> None:  # type: ignore[no-untyped-def]
    dialog = AddSiteDialog(TARGET, ["tgt_plains"])
    qtbot.addWidget(dialog)
    qtbot.keyClicks(dialog.name_edit, "Plains")
    dialog.id_edit.setText("TGT_plains")
    for edit, text in (
        (dialog.latitude_edit, "1"),
        (dialog.longitude_edit, "2"),
        (dialog.altitude_edit, "0"),
        (dialog.elevation_edit, "5"),
    ):
        qtbot.keyClicks(edit, text)
    assert not dialog.add_button.isEnabled() and "exists" in dialog.error_label.text()


# ---- the window -----------------------------------------------------------------------------
def test_the_two_entries_have_shortcuts_and_the_palette_lists_them(qtbot) -> None:  # type: ignore[no-untyped-def]
    window = MainWindow()
    qtbot.addWidget(window, before_close_func=lambda w: w.editors.discard_all_changes())
    station = _action(window, "Add ground station…")
    target = _action(window, "Add imaging target…")
    assert station.shortcut().toString() == "Ctrl+Shift+G" and not station.isEnabled()
    assert target.shortcut().toString() == "Ctrl+Shift+T" and not target.isEnabled()
    assert window.add_ground_station() is False and window.add_imaging_target() is False
    window.open_project(EXAMPLES / "microsat_250kg_eps")
    assert station.isEnabled() and target.isEnabled()
    names = {c.text: c.hint for c in window.palette_commands()}
    assert names["Edit > Add ground station"] == "Ctrl+Shift+G"
    assert names["Edit > Add imaging target"] == "Ctrl+Shift+T"


def test_a_station_and_a_target_are_added_in_one_undo_step_each_and_save_writes_them(  # type: ignore[no-untyped-def]
    tmp_path: Path, qtbot
) -> None:
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", tmp_path / "p")
    window = MainWindow()
    qtbot.addWidget(window, before_close_func=lambda w: w.editors.discard_all_changes())
    window.open_project(tmp_path / "p")
    asked: list[tuple[str, list[str]]] = []

    def ask(kind: str, existing: list[str]) -> SiteAnswers:
        asked.append((kind, existing))
        return site(kind, "gs_east" if kind == GROUND_STATION else "tgt_hills")

    window._ask_site = ask  # type: ignore[method-assign]
    assert window.add_ground_station() and window.add_imaging_target()
    assert asked[0][0] == GROUND_STATION and "gs_north" in asked[0][1]  # the loaded ones are known
    assert "tgt_plains" in asked[0][1]  # ... the targets too (a scenario names both by id)
    assert "gs_east" in asked[1][1]  # ... and the one added a moment ago and not saved yet
    document = window.document
    assert document.has("ground_stations/gs_east.yaml") and document.has("targets/tgt_hills.yaml")
    document.undo_stack.undo()
    assert not document.has("targets/tgt_hills.yaml") and document.has(
        "ground_stations/gs_east.yaml"
    )
    document.undo_stack.redo()
    assert window.save_model()
    project = load_project(tmp_path / "p").project
    assert project is not None
    assert "gs_east" in project.ground_stations and "tgt_hills" in project.targets


def test_a_cancel_changes_nothing_and_a_blank_project_takes_a_station(  # type: ignore[no-untyped-def]
    tmp_path: Path, qtbot
) -> None:
    folder = create_blank_project(
        BlankAnswers(project_name="Blank", bus_voltage_v=28.0), tmp_path / "blank"
    )
    window = MainWindow()
    qtbot.addWidget(window, before_close_func=lambda w: w.editors.discard_all_changes())
    window.open_project(folder)
    window._ask_site = lambda *_a: None  # type: ignore[method-assign]
    assert window.add_ground_station() is False
    assert window.document.rels("ground_stations/") == []
    window._ask_site = lambda kind, _e: site(kind, "gs_a")  # type: ignore[method-assign]
    assert window.add_ground_station()
    assert window.document.has("ground_stations/gs_a.yaml")
