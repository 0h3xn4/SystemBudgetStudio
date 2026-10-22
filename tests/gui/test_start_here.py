"""The Start here panel (D-190): four steps to a first result, one button each, hidden when the
person wants it hidden, back with Help > Start here."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtGui import QAction

from budget_core.blank import BlankAnswers, create_blank_project
from budget_core.new_mode import ModeAnswers
from budget_core.new_scenario import ScenarioAnswers
from budget_core.new_unit import UnitAnswers
from budget_gui.layout_settings import LayoutSettings
from budget_gui.main_window import MainWindow
from budget_gui.start_here import MODE, RUN, SCENARIO, STEP_TEXTS, UNIT, progress

pytestmark = pytest.mark.gui


def _window(qtbot, folder: Path, layout: LayoutSettings | None = None) -> MainWindow:  # type: ignore[no-untyped-def]
    window = MainWindow(layout)
    qtbot.addWidget(window, before_close_func=lambda w: w.editors.discard_all_changes())
    window.open_project(folder)
    window.show()
    return window


def _blank(tmp_path: Path) -> Path:
    return create_blank_project(
        BlankAnswers(project_name="Blank", bus_voltage_v=28.0), tmp_path / "blank"
    )


def _help_entry(window: MainWindow, text: str) -> QAction:
    for top in window.menuBar().actions():
        menu = top.menu()
        if menu is not None and top.text().replace("&", "") == "Help":
            for action in menu.actions():
                if action.text().replace("&", "") == text:
                    return action
    raise AssertionError(f"Help > {text} is missing")


# ---- the steps, without a window ------------------------------------------------------------
def test_nothing_is_done_in_an_empty_project() -> None:
    state = progress(units=0, modes=0, scenarios=0, saved=True, ran=False)
    assert state.done == frozenset() and state.current == UNIT and not state.finished


def test_each_step_is_done_by_what_the_files_say() -> None:
    assert progress(units=2, modes=0, scenarios=0, saved=True, ran=False).current == MODE
    assert progress(units=2, modes=1, scenarios=0, saved=True, ran=False).current == SCENARIO
    assert progress(units=2, modes=1, scenarios=1, saved=True, ran=False).current == RUN
    assert progress(units=2, modes=1, scenarios=1, saved=False, ran=True).current == RUN
    assert progress(units=2, modes=1, scenarios=1, saved=True, ran=True).finished


def test_a_step_can_start_only_when_the_steps_before_it_are_done() -> None:
    state = progress(units=1, modes=0, scenarios=0, saved=True, ran=False)
    assert state.can_start(UNIT) and state.can_start(MODE)
    assert not state.can_start(SCENARIO) and not state.can_start(RUN)


def test_the_steps_are_the_four_of_the_plan_in_order() -> None:
    assert [t.key for t in STEP_TEXTS] == [UNIT, MODE, SCENARIO, RUN]
    for text in STEP_TEXTS:
        assert text.title and text.hint and text.button and text.shortcut


# ---- the panel in the window ----------------------------------------------------------------
def test_a_blank_project_shows_the_panel_with_the_first_step_to_do(
    tmp_path: Path,
    qtbot,  # type: ignore[no-untyped-def]
) -> None:
    window = _window(qtbot, _blank(tmp_path))
    panel = window.start_here
    assert not panel.isHidden()
    assert panel.buttons[UNIT].kind == "primary" and panel.buttons[UNIT].isEnabled()
    assert panel.buttons[MODE].kind == "secondary" and not panel.buttons[MODE].isEnabled()
    assert "Add a unit first" in panel.buttons[MODE].toolTip()
    assert not panel.buttons[SCENARIO].isEnabled() and not panel.buttons[RUN].isEnabled()
    for key in panel.step_keys():
        assert panel.buttons[key].accessibleName()


def test_the_panel_is_not_there_before_a_project_is_open(qtbot) -> None:  # type: ignore[no-untyped-def]
    window = MainWindow()
    qtbot.addWidget(window)
    assert window.start_here.isHidden()
    assert not _help_entry(window, "Start here").isEnabled()


def test_the_steps_tick_as_the_model_is_built_and_the_panel_goes_when_all_are_done(
    tmp_path: Path,
    qtbot,  # type: ignore[no-untyped-def]
) -> None:
    window = _window(qtbot, _blank(tmp_path))
    panel = window.start_here
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
    panel.buttons[UNIT].click()  # the button does what Edit > Add unit does
    assert UNIT in panel.done_keys() and panel.buttons[MODE].isEnabled()
    assert panel.buttons[MODE].kind == "primary" and panel.buttons[UNIT].isHidden()

    window.spacecraft_modes_page._ask = lambda *_a: ModeAnswers(  # type: ignore[method-assign]
        "nominal", "Nominal", "", ""
    )
    panel.buttons[MODE].click()
    assert MODE in panel.done_keys() and panel.buttons[SCENARIO].isEnabled()

    window._ask_scenario = lambda *_a: ScenarioAnswers(  # type: ignore[method-assign]
        "first", "First day", 550.0, 97.6, 100.0, "2026-06-01T00:00:00Z", 1.0, "nominal"
    )
    panel.buttons[SCENARIO].click()
    assert SCENARIO in panel.done_keys() and RUN not in panel.done_keys()
    assert panel.buttons[RUN].isEnabled() and panel.buttons[RUN].kind == "primary"

    # Save and run: the files are written, the project loads again and the run follows
    panel.buttons[RUN].click()
    qtbot.waitUntil(lambda: window.start_here.isHidden(), timeout=90000)
    assert (tmp_path / "blank" / "scenarios" / "first.yaml").is_file()
    assert window.scenario_view.last_run is not None
    assert not window._run_after_load
    assert panel.done_keys() == {UNIT, MODE, SCENARIO, RUN}


def test_an_undo_takes_a_tick_back(tmp_path: Path, qtbot) -> None:  # type: ignore[no-untyped-def]
    window = _window(qtbot, _blank(tmp_path))
    window.units_page._ask = lambda *_a: UnitAnswers(  # type: ignore[method-assign]
        "obc", "Computer", "DH", "main", "class_a", 0.5, "on", 1.0, 2.0
    )
    assert window.add_unit()
    assert UNIT in window.start_here.done_keys()
    window.document.undo_stack.undo()
    assert UNIT not in window.start_here.done_keys()


def test_hiding_is_kept_and_help_start_here_brings_it_back(
    tmp_path: Path,
    qtbot,  # type: ignore[no-untyped-def]
) -> None:
    layout_file = tmp_path / "config" / "layout.ini"
    window = _window(qtbot, _blank(tmp_path), LayoutSettings(layout_file))
    window.start_here.hide_button.click()
    assert window.start_here.isHidden()
    assert "Help > Start here" in window.statusBar().currentMessage()
    assert "start_here=hidden" in layout_file.read_text()

    again = _window(qtbot, tmp_path / "blank", LayoutSettings(layout_file))
    assert again.start_here.isHidden()  # the choice is remembered
    _help_entry(again, "Start here").trigger()
    assert not again.start_here.isHidden()
    again.save_layout()
    assert "start_here=shown" in layout_file.read_text()


def test_help_start_here_shows_the_panel_also_when_everything_is_done(
    qtbot,  # type: ignore[no-untyped-def]
) -> None:
    example = Path(__file__).resolve().parents[2] / "examples" / "microsat_150kg"
    window = _window(qtbot, example)
    window.run_all()
    qtbot.waitUntil(lambda: window.start_here.isHidden(), timeout=90000)
    _help_entry(window, "Start here").trigger()
    assert not window.start_here.isHidden()
    assert "all done" in window.start_here.title.text()


def test_the_help_entry_is_in_the_palette(
    tmp_path: Path,
    qtbot,  # type: ignore[no-untyped-def]
) -> None:
    window = _window(qtbot, _blank(tmp_path))
    names = [command.text for command in window.palette_commands()]
    assert "Help > Start here" in names
