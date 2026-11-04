"""The power timeline with placed pointing and burns (2.3.0, D-235): the load is added to the
demand as its own series, step-independent, seen by the peak-power check, unknown where an input is
a placeholder, and absent (byte-identical results) where nothing is placed."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from budget_core.io.project_loader import load_project
from budget_core.model import Project
from budget_core.power.time_domain import time_domain_budget
from budget_core.propulsion.budget import propulsion_budget
from budget_core.scenario.run import run_scenario
from tests.unit.test_extra_loads import make, pointing, sourced

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


@pytest.fixture(scope="module")
def base() -> Project:
    loaded = load_project(EXAMPLES / "microsat_250kg_eps")
    assert loaded.project is not None
    return loaded.project


def solve(project: Project, **kwargs: object):  # type: ignore[no-untyped-def]
    run = run_scenario(project, "one_day")
    return time_domain_budget(project, run, **kwargs)  # type: ignore[arg-type]


def test_nothing_placed_gives_the_same_arrays_as_before(base: Project) -> None:
    plain = make(base)
    with_files = make(base, pointing_default=None)
    a, b = solve(plain), solve(with_files)
    assert a.extra is None and a.extra_w is None
    assert a.demand_w is not None and b.demand_w is not None
    assert np.array_equal(a.demand_w, b.demand_w) and np.array_equal(a.load_w, b.load_w)  # type: ignore[arg-type]


def test_a_hold_adds_its_power_to_load_and_demand_on_every_step(base: Project) -> None:
    plain = solve(make(base))
    held = solve(make(base, pointing_default="nadir"))
    assert plain.demand_w is not None and held.demand_w is not None
    assert plain.load_w is not None and held.load_w is not None
    assert held.extra_w is not None
    assert np.allclose(held.extra_w, 15.0, rtol=0, atol=1e-9)
    assert np.allclose(held.demand_w - plain.demand_w, 15.0, atol=1e-9)
    assert np.allclose(held.load_w - plain.load_w, 15.0, atol=1e-9)


def test_the_extra_energy_is_the_same_whatever_the_step(base: Project) -> None:
    placed = {"maneuvers": [{"name": "Raise", "start_s": 3010.0}], "pointing_default": "nadir"}
    energies = []
    for step in (30.0, 60.0, 90.0):
        result = solve(make(base, step_s=step, **placed))
        assert result.extra_w is not None and result.extra is not None
        dt = np.diff(result.edges_s)
        energies.append(float(np.sum(result.extra_w * dt)) / 3600.0)
        assert result.extra.energy_wh() == pytest.approx(energies[-1], rel=1e-9)
    assert energies[0] == pytest.approx(energies[1], rel=1e-9)
    assert energies[0] == pytest.approx(energies[2], rel=1e-9)
    burn = next(m for m in propulsion_budget(make(base)).maneuvers if m.name == "Raise")  # type: ignore[union-attr]
    assert energies[0] == pytest.approx(
        (15.0 * 21600.0 + 800.0 * burn.burn_time_s) / 3600.0,
        rel=1e-9,  # type: ignore[operator]
    )


def test_the_burn_mode_changes_the_mode_rows(base: Project) -> None:
    result = solve(make(base, maneuvers=[{"name": "Raise", "start_s": 3000.0}]))
    safe = next(m for m in result.modes if m.mode_id == "safe")
    burn = next(m for m in propulsion_budget(make(base)).maneuvers if m.name == "Raise")  # type: ignore[union-attr]
    assert safe.duration_s == pytest.approx(burn.burn_time_s, rel=1e-9)  # type: ignore[arg-type]


def test_a_burn_on_top_of_a_mode_can_break_the_peak_power_limit(base: Project) -> None:
    project = make(base, maneuvers=[{"name": "Kick", "start_s": 3000.0}])
    quiet = solve(project)
    peak = max(m.peak_demand_w for m in quiet.modes if m.peak_demand_w is not None)
    system = base.config.power_system
    assert system is not None
    limits = system.limits.model_copy(
        update={
            "peak_power_w": system.limits.peak_power_w.model_copy(update={"value": peak + 500.0})
        }
    )
    capped = replace(project.config, power_system=system.model_copy(update={"limits": limits}))
    project = replace(project, config=capped)
    assert not [v for v in solve(project).violations if v.code == "PEAK_POWER_EXCEEDED"]
    electric = make(base, maneuvers=[{"name": "Raise", "start_s": 3000.0}])
    electric = replace(electric, config=replace(electric.config, power_system=capped.power_system))
    flagged = [v for v in solve(electric).violations if v.code == "PEAK_POWER_EXCEEDED"]
    # the electric burn adds 800 W to whichever mode the timeline has there: above the cap
    assert flagged, "800 W more than the highest peak must exceed a cap 500 W above that peak"


def test_a_placeholder_power_makes_the_demand_unknown_not_zero(base: Project) -> None:
    cfg = pointing(
        modes={
            "nadir": {
                "name": "Nadir",
                "reference": "nadir",
                "actuator": "wheels",
                "hold_power_w": sourced(None, "TBD"),
            }
        },
        slews=[],
    )
    result = solve(make(base, cfg=cfg, pointing_default="nadir"))
    assert result.demand_w is None and result.load_w is None and result.extra_w is None
    assert any(p.code == "RESULT_INCOMPLETE" for p in result.problems)


def test_the_extra_load_lowers_the_battery_reserve(base: Project) -> None:
    plain = solve(make(base))
    loaded = solve(make(base, maneuvers=[{"name": "Raise", "start_s": 1000.0}]))
    a, b = plain.case("eol"), loaded.case("eol")
    assert a.energy_wh is not None and b.energy_wh is not None
    assert float(np.min(b.energy_wh)) <= float(np.min(a.energy_wh)) + 1e-9
    assert (
        a.summary.minimum_soc_ratio is None
        or b.summary.minimum_soc_ratio is None
        or (b.summary.minimum_soc_ratio <= a.summary.minimum_soc_ratio + 1e-12)
    )
