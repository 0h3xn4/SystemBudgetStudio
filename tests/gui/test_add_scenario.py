"""Add orbit and scenario in the window (D-189): the form, the Edit menu entry, and a blank project
built up from nothing until it computes."""

from __future__ import annotations

from pathlib import Path

import pytest

from budget_core.blank import BlankAnswers, create_blank_project
from budget_core.new_mode import ModeAnswers
from budget_core.new_scenario import ScenarioAnswers
from budget_core.new_unit import UnitAnswers
from budget_gui.add_scenario_dialog import AddScenarioDialog
from budget_gui.main_window import MainWindow

pytestmark = pytest.mark.gui


def scenario_answers(**kw: object) -> ScenarioAnswers:
    base: dict[str, object] = {
        "scenario_id": "first",
        "name": "First day",
        "altitude_km": 550.0,
        "inclination_deg": 97.6,
        "raan_deg": 100.0,
        "start_utc": "2026-06-01T00:00:00Z",
        "duration_days": 1.0,
        "default_mode": "nominal",
    }
    return ScenarioAnswers(**{**base, **kw})  # type: ignore[arg-type]


# ---- the form -------------------------------------------------------------------------------
def test_the_form_starts_empty_and_takes_no_default_number(qtbot) -> None:  # type: ignore[no-untyped-def]
    dialog = AddScenarioDialog([], [], ["nominal"])
    qtbot.addWidget(dialog)
    assert not dialog.add_button.isEnabled() and dialog.error_label.text() == ""
    for edit in (dialog.altitude_edit, dialog.inclination_edit, dialog.raan_edit):
        assert edit.text() == ""
    assert dialog.answers().altitude_km is None


def test_a_complete_form_can_be_added(qtbot) -> None:  # type: ignore[no-untyped-def]
    dialog = AddScenarioDialog(["old"], [], ["nominal", "safe"])
    qtbot.addWidget(dialog)
    qtbot.keyClicks(dialog.name_edit, "First day")
    assert dialog.id_edit.text() == "first_day"
    for edit, text in (
        (dialog.altitude_edit, "550"),
        (dialog.inclination_edit, "97,6"),  # a decimal comma is read
        (dialog.raan_edit, "100"),
        (dialog.start_edit, "2026-06-01T00:00:00Z"),
        (dialog.duration_edit, "1"),
    ):
        qtbot.keyClicks(edit, text)
    assert dialog.add_button.isEnabled() and dialog.error_label.text() == ""
    assert dialog.answers().inclination_deg == 97.6
    dialog.altitude_edit.setText("5")
    assert not dialog.add_button.isEnabled() and "altitude" in dialog.error_label.text()


def _filled(dialog: AddScenarioDialog, qtbot) -> None:  # type: ignore[no-untyped-def]
    qtbot.keyClicks(dialog.name_edit, "Transfer")
    for edit, text in (
        (dialog.altitude_edit, "500"),
        (dialog.inclination_edit, "63.4"),
        (dialog.raan_edit, "100"),
        (dialog.start_edit, "2026-06-01T00:00:00Z"),
        (dialog.duration_edit, "1"),
    ):
        qtbot.keyClicks(edit, text)


def test_an_empty_apogee_is_a_near_circular_orbit_and_the_argument_of_perigee_waits(  # type: ignore[no-untyped-def]
    qtbot,
) -> None:
    dialog = AddScenarioDialog([], [], ["nominal"])
    qtbot.addWidget(dialog)
    _filled(dialog, qtbot)
    assert dialog.apogee_edit.text() == "" and dialog.arg_perigee_edit.text() == ""
    assert dialog.add_button.isEnabled()  # no extra answer is needed
    answers = dialog.answers()
    assert answers.apogee_altitude_km is None and answers.arg_perigee_deg is None


def test_an_apogee_makes_an_elliptical_orbit_and_asks_for_the_argument_of_perigee(  # type: ignore[no-untyped-def]
    qtbot,
) -> None:
    dialog = AddScenarioDialog([], [], ["nominal"])
    qtbot.addWidget(dialog)
    _filled(dialog, qtbot)
    qtbot.keyClicks(dialog.apogee_edit, "20000")
    assert not dialog.add_button.isEnabled()
    assert "argument of perigee" in dialog.error_label.text().lower()
    qtbot.keyClicks(dialog.arg_perigee_edit, "270")
    assert dialog.add_button.isEnabled() and dialog.error_label.text() == ""
    answers = dialog.answers()
    assert answers.apogee_altitude_km == 20000.0 and answers.arg_perigee_deg == 270.0
    dialog.apogee_edit.setText("400")  # below the perigee altitude
    assert not dialog.add_button.isEnabled() and "apogee" in dialog.error_label.text().lower()


def test_the_form_takes_a_length_of_180_days_and_refuses_more(qtbot) -> None:  # type: ignore[no-untyped-def]
    dialog = AddScenarioDialog([], [], ["nominal"])
    qtbot.addWidget(dialog)
    _filled(dialog, qtbot)
    dialog.duration_edit.setText("180")
    assert dialog.add_button.isEnabled()
    dialog.duration_edit.setText("181")
    assert not dialog.add_button.isEnabled() and "180" in dialog.error_label.text()


def test_the_form_says_at_once_that_a_project_without_a_mode_has_no_scenario(qtbot) -> None:  # type: ignore[no-untyped-def]
    dialog = AddScenarioDialog([], [], [])
    qtbot.addWidget(dialog)
    assert "spacecraft mode first" in dialog.error_label.text()
    assert not dialog.add_button.isEnabled()


# ---- the window -----------------------------------------------------------------------------
def _action(window: MainWindow, text: str):  # type: ignore[no-untyped-def]
    for top in window.menuBar().actions():
        menu = top.menu()
        if menu is not None:
            for action in menu.actions():
                if action.text().replace("&", "") == text:
                    return action
    raise AssertionError(f"no menu entry {text!r}")


def test_the_edit_menu_entry_has_a_shortcut_and_the_palette_lists_it(
    tmp_path: Path,
    qtbot,  # type: ignore[no-untyped-def]
) -> None:
    window = MainWindow()
    qtbot.addWidget(window, before_close_func=lambda w: w.editors.discard_all_changes())
    action = _action(window, "Add scenario…")
    assert action.shortcut().toString() == "Ctrl+Shift+O" and not action.isEnabled()
    assert window.add_scenario() is False
    folder = create_blank_project(
        BlankAnswers(project_name="Blank", bus_voltage_v=28.0), tmp_path / "blank"
    )
    window.open_project(folder)
    assert action.isEnabled()
    names = {c.text: c.hint for c in window.palette_commands()}
    assert names["Edit > Add scenario"] == "Ctrl+Shift+O"


def test_the_empty_scenario_page_offers_the_button(
    tmp_path: Path,
    qtbot,  # type: ignore[no-untyped-def]
) -> None:
    folder = create_blank_project(
        BlankAnswers(project_name="Blank", bus_voltage_v=28.0), tmp_path / "blank"
    )
    window = MainWindow()
    qtbot.addWidget(window, before_close_func=lambda w: w.editors.discard_all_changes())
    window.open_project(folder)
    window.show()
    assert not window.scenario_view.add_button.isHidden()
    assert "no scenario yet" in window.scenario_view.empty_label.text()


def test_without_a_spacecraft_mode_the_button_says_to_add_one_first(
    tmp_path: Path,
    qtbot,  # type: ignore[no-untyped-def]
) -> None:
    folder = create_blank_project(
        BlankAnswers(project_name="Blank", bus_voltage_v=28.0), tmp_path / "blank"
    )
    window = MainWindow()
    qtbot.addWidget(window, before_close_func=lambda w: w.editors.discard_all_changes())
    window.open_project(folder)
    window.scenario_view.add_button.click()
    assert "add a spacecraft mode first" in window.statusBar().currentMessage()
    assert window.document.rels("scenarios/") == []


def test_a_blank_project_is_built_up_in_the_window_until_it_computes(
    tmp_path: Path,
    qtbot,  # type: ignore[no-untyped-def]
) -> None:
    folder = create_blank_project(
        BlankAnswers(project_name="Blank", bus_voltage_v=28.0), tmp_path / "blank"
    )
    window = MainWindow()
    qtbot.addWidget(window, before_close_func=lambda w: w.editors.discard_all_changes())
    window.open_project(folder)
    window.units_page._ask = lambda *_a: UnitAnswers(  # type: ignore[method-assign]
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
    assert window.add_unit()
    window.spacecraft_modes_page._ask = lambda *_a: ModeAnswers(  # type: ignore[method-assign]
        "nominal", "Nominal", "", ""
    )
    assert window.add_spacecraft_mode()
    window._ask_scenario = lambda *_a: scenario_answers()  # type: ignore[method-assign]
    assert window.add_scenario()
    assert {"orbits/first.yaml", "scenarios/first.yaml"} <= set(
        window.document.rels("orbits/") + window.document.rels("scenarios/")
    )
    assert "Save (Ctrl+S)" in window.statusBar().currentMessage()
    window.document.undo_stack.undo()  # one undo step takes both files back
    assert window.document.rels("scenarios/") == [] and window.document.rels("orbits/") == []
    window.document.undo_stack.redo()

    assert window.save_model()
    qtbot.waitUntil(
        lambda: (
            window.session.project is not None
            and "first" in window.session.project.scenarios
            and "first" in window.session.project.orbits
        ),
        timeout=20000,
    )
    assert (folder / "scenarios" / "first.yaml").is_file()
    assert (folder / "orbits" / "first.yaml").is_file()
    assert not [p for p in window.session.problems if p.severity.name == "ERROR"]

    window.scenario_view.compute()
    qtbot.waitUntil(lambda: not window.scenario_view.is_busy(), timeout=60000)
    assert window.scenario_view.last_run is not None
    assert window.scenario_view.last_run.scenario_id == "first"
