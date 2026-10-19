"""Progress and cancellation of the long computations (D-167)."""

from __future__ import annotations

from pathlib import Path

import pytest

from budget_core.control import Cancelled, RunControl, checkpoint, stage
from budget_core.io.project_loader import load_project
from budget_core.link.evaluate import link_pass_series
from budget_core.power.time_domain import time_domain_budget
from budget_core.scenario.run import run_scenario

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


@pytest.fixture(scope="module")
def project():  # type: ignore[no-untyped-def]
    loaded = load_project(EXAMPLES / "microsat_250kg_eps")
    assert loaded.project is not None
    return loaded.project


def test_a_control_reports_stages_and_stops_at_a_checkpoint() -> None:
    stages: list[str] = []
    stop = False
    control = RunControl(lambda: stop, stages.append)
    control.stage("one")
    control.checkpoint()
    stop = True
    with pytest.raises(Cancelled):
        control.stage("two")
    assert stages == ["one", "two"]  # the stage is named, then the stop is noticed


def test_no_control_means_nothing_is_reported_and_nothing_stops() -> None:
    stage(None, "x")
    checkpoint(None)
    RunControl().stage("x")  # a control with nothing to ask and nobody to tell


def test_the_stages_of_a_run_come_in_order_and_carry_no_project_content(project) -> None:  # type: ignore[no-untyped-def]
    stages: list[str] = []
    control = RunControl(None, stages.append)
    run = run_scenario(project, "one_day", control)
    time_domain_budget(project, run, control=control)
    link_pass_series(project, run, control)
    assert stages == [
        "Orbit, eclipses and passes",
        "Power timeline: loads and array",
        "Power timeline: battery",
        "Power timeline: violations and orbit balance",
        "Link passes",
    ]


def test_a_control_changes_no_result(project) -> None:  # type: ignore[no-untyped-def]
    plain_run = run_scenario(project, "one_day")
    control = RunControl(lambda: False, lambda _t: None)
    run = run_scenario(project, "one_day", control)
    assert run.env.eclipses == plain_run.env.eclipses
    a = time_domain_budget(project, plain_run)
    b = time_domain_budget(project, run, control=control)
    assert a.steps == b.steps and a.violations == b.violations
    assert [c.summary for c in a.cases] == [c.summary for c in b.cases]
    la, lb = link_pass_series(project, plain_run), link_pass_series(project, run, control)
    assert [s.link_id for s in la.series] == [s.link_id for s in lb.series]


def test_a_run_stops_before_it_starts_when_asked_first(project) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(Cancelled):
        run_scenario(project, "one_day", RunControl(lambda: True))


@pytest.mark.parametrize("after", [1, 2, 3, 4])
def test_the_time_domain_stops_at_each_stage(project, after: int) -> None:  # type: ignore[no-untyped-def]
    run = run_scenario(project, "one_day")
    asked = 0

    def should_cancel() -> bool:
        nonlocal asked
        asked += 1
        return asked >= after

    with pytest.raises(Cancelled):
        time_domain_budget(project, run, control=RunControl(should_cancel))


def test_the_link_passes_stop_between_links(project) -> None:  # type: ignore[no-untyped-def]
    run = run_scenario(project, "one_day")
    asked = 0

    def should_cancel() -> bool:
        nonlocal asked
        asked += 1
        return asked >= 2  # the stage, then the first link

    with pytest.raises(Cancelled):
        link_pass_series(project, run, RunControl(should_cancel))
