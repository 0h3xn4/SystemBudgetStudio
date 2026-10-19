"""Progress and Cancel of the long computations (UX step 3d, D-167)."""

from __future__ import annotations

import shutil
import time
from pathlib import Path

import pytest

from budget_core.control import RunControl
from budget_gui.cancel_support import CANCEL_TEXT, COMPUTE_TEXT
from budget_gui.main_window import MainWindow
from budget_gui.run_controller import RunState
from budget_gui.top_bar import TopBar

pytestmark = pytest.mark.gui

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


@pytest.fixture
def window(qtbot, tmp_path: Path) -> MainWindow:  # type: ignore[no-untyped-def]
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", tmp_path / "p")
    w = MainWindow()
    qtbot.addWidget(w, before_close_func=lambda win: win.editors.discard_all_changes())
    w.open_project(tmp_path / "p")
    return w


def slow(control: RunControl | None, stage: str = "Slow step") -> None:
    """Work that never ends by itself: it only stops when asked to."""
    assert control is not None
    control.stage(stage)
    while True:
        time.sleep(0.01)
        control.checkpoint()


def test_the_top_bar_run_button_is_cancel_while_a_run_is_in_progress(qtbot) -> None:  # type: ignore[no-untyped-def]
    bar = TopBar()
    qtbot.addWidget(bar)
    bar.show()
    bar.set_run_state(RunState.NOT_RUN, True)
    assert bar.run_button.text() == "Run" and not bar.progress.isVisible()
    bar.set_run_state(RunState.RUNNING, True, "Link passes")
    assert bar.run_button.text() == "Cancel" and bar.run_button.isEnabled()
    assert bar.progress.isVisible() and "Link passes" in bar.chip.text()
    with qtbot.waitSignal(bar.cancel_requested, timeout=500):
        bar.run_button.click()
    bar.set_run_state(RunState.RUNNING, True, "cancelling", cancelling=True)
    assert bar.run_button.text() == "Cancelling…" and not bar.run_button.isEnabled()
    bar.set_run_state(RunState.NOT_RUN, True)
    assert bar.run_button.text() == "Run" and not bar.progress.isVisible()
    with qtbot.waitSignal(bar.run_requested, timeout=500):
        bar.run_button.click()


def test_cancelling_the_timeline_keeps_the_result_on_screen(
    window: MainWindow, qtbot, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    view = window.timeline_view
    with qtbot.waitSignal(view.computed, timeout=120000):
        view.compute()
    before = view.result
    assert before is not None and view.is_valid()
    monkeypatch.setattr(
        "budget_gui.timeline_view.time_domain_budget",
        lambda *_a, control=None, **_k: slow(control, "Power timeline: battery"),
    )
    stages: list[str] = []
    view.stage_changed.connect(stages.append)
    view.compute()
    assert view.compute_button.text() == CANCEL_TEXT and view.compute_button.isEnabled()
    qtbot.waitUntil(lambda: "Power timeline: battery" in view.status.text(), timeout=20000)
    assert stages[0] == "Orbit, eclipses and passes"  # no scenario run to reuse: made first
    with qtbot.waitSignal(view.cancelled, timeout=10000):
        view.compute_button.click()  # the button cancels while it computes
    assert view.compute_button.text() == COMPUTE_TEXT and view.compute_button.isEnabled()
    assert view.result is before and view.is_valid()
    assert view.status.text() == "Cancelled. The results shown are from before."
    assert not view.is_busy()


def test_cancelling_a_first_computation_leaves_nothing_and_says_so(
    window: MainWindow, qtbot, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    view = window.link_passes_view
    monkeypatch.setattr(
        "budget_gui.link_view.link_pass_series",
        lambda _project, _run, control=None: slow(control, "Link passes"),
    )
    monkeypatch.setattr(
        "budget_gui.link_view.run_scenario",
        lambda *_a, **_k: object(),  # not used by the fake
    )
    view.compute()
    qtbot.waitUntil(lambda: "Link passes" in view.status.text(), timeout=10000)
    with qtbot.waitSignal(view.cancelled, timeout=10000):
        view.cancel()
    assert view.result is None and view.status.text() == "Cancelled."
    assert view.compute_button.isEnabled()


def test_cancelling_the_scenario_keeps_its_last_run(window: MainWindow, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    view = window.scenario_view
    with qtbot.waitSignal(view.computed, timeout=120000):
        view.compute()
    before = view.last_run
    monkeypatch.setattr(
        "budget_gui.scenario_view.run_scenario",
        lambda _p, _s, control=None: slow(control, "Orbit, eclipses and passes"),
    )
    view.compute()
    qtbot.waitUntil(lambda: "Orbit" in view.status.text(), timeout=10000)
    with qtbot.waitSignal(view.cancelled, timeout=10000):
        view.cancel()
    assert view.last_run is before and not view.is_stale


def test_cancelling_a_run_stops_the_steps_that_were_to_follow(
    window: MainWindow, qtbot, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(
        "budget_gui.scenario_view.run_scenario",
        lambda _p, _s, control=None: slow(control, "Orbit, eclipses and passes"),
    )
    assert window.run_all()
    controller = window.run_controller
    qtbot.waitUntil(lambda: controller.stage != "", timeout=10000)
    assert window.top_bar.run_button.text() == "Cancel" and window.top_bar.progress.isVisibleTo(
        window.top_bar
    )
    assert "Orbit, eclipses and passes" in window.top_bar.chip.text()
    window.top_bar.run_button.click()
    assert "Cancelling" in window.top_bar.run_button.text() or not controller.is_running()
    qtbot.waitUntil(lambda: not controller.is_running(), timeout=10000)
    assert window.timeline_view.result is None and not window.timeline_view.is_busy()
    assert window.link_passes_view.result is None and not window.link_passes_view.is_busy()
    assert controller.state() is RunState.NOT_RUN
    assert window.top_bar.run_button.text() == "Run" and window.top_bar.run_button.isEnabled()
    assert not window.top_bar.progress.isVisibleTo(window.top_bar)
    # and a new run works
    monkeypatch.undo()
    assert window.run_all()
    qtbot.waitUntil(lambda: controller.state() is RunState.OK, timeout=180000)


def test_cancel_with_nothing_running_does_nothing(window: MainWindow) -> None:
    assert window.run_controller.cancel() is False
