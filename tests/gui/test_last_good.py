"""An error does not blank the window: the last good results stay, marked as old (UX-10, D-151)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from budget_gui.main_window import MainWindow
from budget_gui.run_controller import RunState

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", tmp_path / "p")
    return tmp_path / "p"


@pytest.fixture
def window(qtbot, project: Path) -> MainWindow:  # type: ignore[no-untyped-def]
    w = MainWindow()
    qtbot.addWidget(w)
    w.show()
    w.open_project(project)
    return w


def break_it(project: Path) -> None:
    path = project / "units" / "obc.yaml"
    path.write_text(path.read_text().replace("bus: main", "bus: nope", 1))


def test_the_budgets_stay_after_an_error_and_a_banner_says_so(
    window: MainWindow, project: Path
) -> None:
    before = window.power_view.count()
    assert before > 0 and window.stale_banner.isHidden()
    break_it(project)
    window.session.reload()
    assert window.session.showing_last_good and window.session.project is None
    assert window.power_view.count() == before  # the tables did not go
    assert window.mass_view.count() > 0 and window.thermal_view.count() > 0
    assert not window.stale_banner.isHidden()
    assert "1 error" in window.stale_banner.text_label.text()
    assert "before the error" in window.stale_banner.text_label.text()


def test_the_tree_keeps_the_unit_names_while_the_project_has_an_error(
    window: MainWindow, project: Path
) -> None:
    break_it(project)
    window.session.reload()
    item = window.tree.find_item("units/radio.yaml", kind="unit")
    assert item is not None and item.text(0) == "S-band transceiver"


def test_nothing_old_can_be_exported(window: MainWindow, project: Path) -> None:
    break_it(project)
    window.session.reload()
    assert window.session.outputs == []  # an export would describe inputs that are gone


def test_fixing_the_error_brings_the_results_back_and_hides_the_banner(
    window: MainWindow, project: Path
) -> None:
    break_it(project)
    window.session.reload()
    path = project / "units" / "obc.yaml"
    path.write_text(path.read_text().replace("bus: nope", "bus: main", 1))
    window.session.reload()
    assert not window.session.showing_last_good and window.session.project is not None
    assert window.stale_banner.isHidden()


def test_the_banner_button_goes_to_the_first_error(window: MainWindow, project: Path) -> None:
    break_it(project)
    window.session.reload()
    window.stale_banner.action_button.click()
    editor = window.editors.current_editor()
    assert editor is not None and editor.rel_path == "units/obc.yaml"
    problem = window.problems_panel.current_problem()
    assert problem is not None and problem.code == "REF_UNKNOWN_BUS"


def test_another_project_does_not_inherit_the_old_results(
    window: MainWindow, tmp_path: Path
) -> None:
    broken = tmp_path / "other"
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", broken)
    break_it(broken)
    window.open_project(broken)
    assert not window.session.showing_last_good
    assert window.power_view.count() == 0 and window.stale_banner.isHidden()


def test_an_empty_view_says_why(window: MainWindow, tmp_path: Path) -> None:
    broken = tmp_path / "other"
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", broken)
    break_it(broken)
    window.open_project(broken)
    for view in (window.power_view, window.scenario_view, window.timeline_view):
        text = view.empty_label.text()
        assert "1 error" in text and "Problems" in text, text


def test_a_project_without_a_scenario_says_what_to_add(window: MainWindow, project: Path) -> None:
    shutil.rmtree(project / "scenarios")
    window.session.reload()
    assert "no scenario" in window.timeline_view.empty_label.text()
    assert "Add scenario" in window.timeline_view.empty_label.text()
    assert "no scenario yet" in window.scenario_view.empty_label.text()
    assert not window.scenario_view.add_button.isHidden()  # the page offers the way to add one


def test_a_failed_run_stays_visible_until_it_is_run_again(window: MainWindow) -> None:
    controller = window.run_controller
    controller._failed = "The orbit has no epoch."
    window._update_run_state()
    assert controller.state() is RunState.FAILED
    assert not window.failed_banner.isHidden()
    assert "did not finish: The orbit has no epoch." in window.failed_banner.text_label.text()
    controller.reset_failure()
    window._update_run_state()
    assert window.failed_banner.isHidden()
