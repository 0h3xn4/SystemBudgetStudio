"""The top bar, the run controller and the shared scenario (UX step 1, D-151)."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtCore import QObject, Qt, Signal

from budget_gui.main_window import MainWindow
from budget_gui.run_controller import STATE_TEXT, RunController, RunState
from budget_gui.top_bar import StatusChip, TopBar

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


# ---- the controller, with stand-in views ----------------------------------------------------
class FakeView(QObject):
    computed = Signal(object)
    compute_failed = Signal(str)

    def __init__(self, name: str, log: list[str]) -> None:
        super().__init__()
        self.name, self.log = name, log
        self.project: Any = None
        self.busy = False
        self.last_run: Any = None
        self.result: Any = None
        self.is_stale = False

    def selected_id(self) -> str:
        return "s1"

    def is_busy(self) -> bool:
        return self.busy

    def compute(self) -> None:
        self.log.append(self.name)
        self.busy = True

    def finish(self) -> None:
        self.busy = False
        self.last_run = self.result = object()
        self.computed.emit(self.result)


class Project:
    def __init__(self, links: bool) -> None:
        self.links = {"l": 1} if links else {}


def controller(links: bool = True) -> tuple[RunController, list[FakeView], list[str]]:
    log: list[str] = []
    views = [FakeView(n, log) for n in ("scenario", "timeline", "passes")]
    for view in views:
        view.project = Project(links)
    return RunController(*views), views, log


def test_run_goes_through_the_steps_in_order() -> None:
    run, (scenario, timeline, passes), log = controller()
    assert run.state() is RunState.NOT_RUN and run.can_run()
    assert run.run() is True
    assert log == ["scenario"] and run.state() is RunState.RUNNING
    assert not run.can_run() and run.run() is False  # a run in progress is not started twice
    scenario.finish()
    assert log == ["scenario", "timeline"]
    timeline.finish()
    assert log == ["scenario", "timeline", "passes"]
    passes.finish()
    assert run.state() is RunState.OK


def test_a_project_without_links_has_no_passes_step() -> None:
    run, (scenario, timeline, passes), log = controller(links=False)
    run.run()
    scenario.finish()
    timeline.finish()
    assert log == ["scenario", "timeline"] and run.state() is RunState.OK
    assert not passes.is_busy()


def test_a_failure_stops_the_run_and_is_reported() -> None:
    run, (scenario, timeline, passes), log = controller()
    run.run()
    scenario.busy = False
    scenario.compute_failed.emit("The orbit has no epoch.")
    assert run.state() is RunState.FAILED and run.failure == "The orbit has no epoch."
    assert log == ["scenario"]  # nothing after the failed step was started
    run.reset_failure()
    assert run.state() is RunState.NOT_RUN


def test_results_that_are_stale_say_out_of_date() -> None:
    run, (scenario, timeline, passes), _log = controller()
    run.run()
    scenario.finish()
    timeline.finish()
    passes.finish()
    timeline.is_stale = True
    assert run.state() is RunState.STALE


def test_nothing_to_run_without_a_project_or_a_scenario() -> None:
    run, (scenario, *_rest), _log = controller()
    scenario.project = None
    assert not run.can_run() and run.run() is False and run.state() is RunState.NOT_RUN


# ---- the widgets ----------------------------------------------------------------------------
def test_the_chip_says_a_word_and_shows_an_icon_for_every_state(qtbot) -> None:  # type: ignore[no-untyped-def]
    chip = StatusChip()
    qtbot.addWidget(chip)
    seen = set()
    for state in RunState:
        chip.set_state(state, tooltip="why")
        assert chip.text().startswith(STATE_TEXT[state])
        assert chip._icon.pixmap() is not None and not chip._icon.pixmap().isNull()
        seen.add(chip.text())
    assert len(seen) == len(RunState)  # a different word for each state: never colour alone


def test_the_top_bar_shows_project_revision_and_the_unsaved_marker(qtbot) -> None:  # type: ignore[no-untyped-def]
    bar = TopBar()
    qtbot.addWidget(bar)
    bar.set_project("Example 250 kg minisatellite", "A")
    assert (
        bar.name_label.text() == "Example 250 kg minisatellite"
        and bar.revision_label.text() == "rev A"
    )
    bar.set_dirty(True)
    assert "Unsaved changes" in bar.dirty_label.text()
    bar.set_dirty(False)
    assert bar.dirty_label.text() == ""


def test_the_case_toggle_is_exclusive_and_starts_at_bol(qtbot) -> None:  # type: ignore[no-untyped-def]
    bar = TopBar()
    qtbot.addWidget(bar)
    assert bar.case() == "BOL"
    with qtbot.waitSignal(bar.case_chosen, timeout=1000) as blocker:
        bar.case_buttons["EOL"].click()
    assert blocker.args == ["EOL"] and bar.case() == "EOL"
    bar.set_case("bol")
    assert bar.case() == "BOL"


# ---- in the window --------------------------------------------------------------------------
@pytest.fixture
def window(qtbot, tmp_path: Path) -> MainWindow:  # type: ignore[no-untyped-def]
    project = tmp_path / "p"
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", project)
    shutil.copy(project / "scenarios" / "one_day.yaml", project / "scenarios" / "second.yaml")
    w = MainWindow()
    qtbot.addWidget(w)
    w.show()
    w.open_project(project)
    return w


def test_the_top_bar_shows_the_open_project(window: MainWindow) -> None:
    bar = window.top_bar
    assert (
        "Example 250 kg minisatellite" in bar.name_label.text()
        and bar.revision_label.text().startswith("rev ")
    )
    assert [bar.scenario_combo.itemText(i) for i in range(bar.scenario_combo.count())] == [
        "one_day",
        "second",
    ]
    assert bar.chip.state is RunState.NOT_RUN and bar.run_button.isEnabled()


def test_the_tabs_have_no_selector_of_their_own(window: MainWindow) -> None:
    for widget in (
        window.scenario_view.combo,
        window.timeline_view.scenario_combo,
        window.timeline_view.case_combo,
        window.link_passes_view.scenario_combo,
    ):
        assert widget.isHidden()  # hidden on purpose (a tab page that is not in front is not)
    assert not window.timeline_view.basis_combo.isHidden()  # the demand basis stays


def test_one_scenario_for_every_tab(window: MainWindow) -> None:
    window.top_bar.scenario_combo.setCurrentText("second")
    window.top_bar.scenario_chosen.emit("second")
    assert window.scenario_view.selected_id() == "second"
    assert window.timeline_view.selected_id() == "second"
    assert window.link_passes_view.selected_id() == "second"
    assert window.top_bar.scenario_combo.currentText() == "second"


def test_opening_a_scenario_in_the_tree_selects_it(window: MainWindow) -> None:
    window.tree.request_file("scenarios/second.yaml")
    assert window.top_bar.scenario_combo.currentText() == "second"
    assert window.timeline_view.selected_id() == "second"


def test_bol_eol_in_the_bar_drives_the_timeline_and_back(window: MainWindow) -> None:
    window.top_bar.case_buttons["EOL"].click()
    assert window.timeline_view.case_combo.currentText() == "EOL"
    window.timeline_view.case_combo.setCurrentText("BOL")
    assert window.top_bar.case() == "BOL"


def test_run_works_out_every_step_and_the_chip_says_so(window: MainWindow, qtbot) -> None:  # type: ignore[no-untyped-def]
    assert window.run_all() is True
    assert (
        window.top_bar.chip.state is RunState.RUNNING and not window.top_bar.run_button.isEnabled()
    )
    assert window.wait_for_jobs(180)
    assert window.scenario_view.last_run is not None
    assert window.timeline_view.is_valid() and window.link_passes_view.is_valid()
    chip = window.top_bar.chip
    assert chip.state is RunState.OK and chip.text().startswith("Up to date · ")
    assert window.top_bar.run_button.isEnabled()
    assert window.status_bar.last_run_label.text().startswith("Last run ")


def test_a_reload_makes_the_results_out_of_date(window: MainWindow) -> None:
    window.run_all()
    window.wait_for_jobs(180)
    window.session.reload()
    assert window.top_bar.chip.state is RunState.STALE


def test_ctrl_r_runs(window: MainWindow, qtbot) -> None:  # type: ignore[no-untyped-def]
    window.activateWindow()
    qtbot.keyClick(window, Qt.Key.Key_R, Qt.KeyboardModifier.ControlModifier)
    assert window.run_controller.is_running()
    window.wait_for_jobs(180)


def test_unsaved_edits_show_in_the_bar_and_the_title(window: MainWindow) -> None:
    window.open_file("units/obc.yaml")
    editor = window.editors.current_editor()
    assert editor is not None
    cursor = editor.textCursor()
    cursor.insertText("# note\n")
    assert "Unsaved changes" in window.top_bar.dirty_label.text()
    assert window.windowTitle().startswith("● ")
    window.save_current()
    assert window.top_bar.dirty_label.text() == ""
    assert not window.windowTitle().startswith("● ")
