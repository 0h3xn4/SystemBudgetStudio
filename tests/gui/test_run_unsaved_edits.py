"""V9: a run reads the saved files, so a result is not "up to date" while edits are not saved, and
the window says so instead of claiming the result is from the inputs on screen."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from budget_gui.main_window import MainWindow
from budget_gui.run_controller import RunState
from tests.gui_helpers import set_mode_value

pytestmark = pytest.mark.gui

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


@pytest.fixture
def window(qtbot, tmp_path: Path):  # type: ignore[no-untyped-def]
    shutil.copytree(EXAMPLES / "microsat_250kg", tmp_path / "p")
    w = MainWindow()
    qtbot.addWidget(w, before_close_func=lambda win: win.editors.discard_all_changes())
    w.open_project(tmp_path / "p")
    return w


def _run(window: MainWindow) -> None:
    assert window.run_all() is True
    assert window.wait_for_jobs(180)


def test_a_clean_run_is_up_to_date_from_the_saved_files(window: MainWindow) -> None:
    _run(window)
    chip = window.top_bar.chip
    assert chip.state is RunState.OK
    assert "saved project files" in chip.toolTip()
    assert "on screen" not in chip.toolTip()


def test_an_unsaved_edit_makes_the_run_out_of_date_and_undo_brings_it_back(
    window: MainWindow,
) -> None:
    _run(window)
    assert set_mode_value(window, "camera", "imaging", "avg_power_w", "62.5 W")
    chip = window.top_bar.chip
    assert chip.state is RunState.STALE and chip.text().startswith("Out of date")
    assert "not saved" in chip.toolTip() and "Save (Ctrl+S)" in chip.toolTip()
    window.document.undo_stack.undo()
    assert chip.state is RunState.OK


def test_running_with_unsaved_edits_says_it_runs_on_the_saved_files(window: MainWindow) -> None:
    assert set_mode_value(window, "camera", "imaging", "avg_power_w", "62.5 W")
    assert window.run_all() is True
    assert "saved files" in window.status_bar.currentMessage()
    assert window.wait_for_jobs(180)
    assert window.top_bar.chip.state is RunState.STALE  # still: the edit is not in the result


def test_saving_the_edit_and_running_again_is_up_to_date(window: MainWindow) -> None:
    assert set_mode_value(window, "camera", "imaging", "avg_power_w", "62.5 W")
    assert window.save_model() is True
    window.wait_for_jobs(60)
    _run(window)
    assert window.top_bar.chip.state is RunState.OK
