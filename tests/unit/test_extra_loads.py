"""Pointing and manoeuvres on the scenario (2.3.0, D-235): a pointing mode held over the scenario
with rules, the slew between two modes where the mode changes, the burns the scenario places, the
spacecraft mode a burn switches to. The load they put on the power budget is a separate series;
hand calculations decide every expectation."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from budget_core.io.project_loader import load_project
from budget_core.model import Project
from budget_core.model.pointing import PointingConfig
from budget_core.model.propulsion import PropulsionConfig
from budget_core.pointing.budget import pointing_budget
from budget_core.propulsion.budget import propulsion_budget
from budget_core.scenario.extra_loads import extra_loads, maneuver_segments
from budget_core.scenario.run import run_scenario

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


def sourced(value: float | None, source: str = "data sheet") -> dict[str, object]:
    return {"value": value, "source": source}


def pointing(**over: object) -> PointingConfig:
    data: dict[str, object] = {
        "actuators": {
            "wheels": {
                "name": "Reaction wheels",
                "max_torque_nm": sourced(0.05),
                "max_rate_deg_s": sourced(1.5),
                "slew_power_w": sourced(45.0),
            }
        },
        "modes": {
            "nadir": {
                "name": "Nadir",
                "reference": "nadir",
                "actuator": "wheels",
                "hold_power_w": sourced(15.0),
            },
            "target": {
                "name": "Target",
                "reference": "target",
                "actuator": "wheels",
                "hold_power_w": sourced(30.0),
            },
        },
        "slews": [
            {
                "name": "out",
                "from_mode": "nadir",
                "to_mode": "target",
                "angle_deg": sourced(30.0),
                "axis": "y",
                "actuator": "wheels",
                "inertia_kgm2": sourced(95.0),
            },
            {
                "name": "back",
                "from_mode": "target",
                "to_mode": "nadir",
                "angle_deg": sourced(30.0),
                "axis": "y",
                "actuator": "wheels",
                "inertia_kgm2": sourced(95.0),
            },
        ],
    }
    data.update(over)
    return PointingConfig.model_validate(data)


def propulsion(**over: object) -> PropulsionConfig:
    data: dict[str, object] = {
        "systems": {
            "ion": {
                "name": "Ion",
                "type": "electric",
                "isp_s": sourced(1500.0),
                "thrust_n": sourced(0.5),
                "power_w": sourced(800.0),
            },
            "chem": {
                "name": "Chem",
                "type": "chemical",
                "isp_s": sourced(220.0),
                "thrust_n": sourced(20.0),
            },
        },
        "maneuvers": [
            {"name": "Raise", "system": "ion", "delta_v_m_s": sourced(4.0), "mode": "safe"},
            {"name": "Kick", "system": "chem", "delta_v_m_s": sourced(2.0)},
        ],
        "dry_mass_kg": sourced(236.0),
    }
    data.update(over)
    return PropulsionConfig.model_validate(data)


@pytest.fixture(scope="module")
def base() -> Project:
    loaded = load_project(EXAMPLES / "microsat_250kg_eps")
    assert loaded.project is not None
    return loaded.project


def make(
    base: Project,
    *,
    cfg: PointingConfig | None = None,
    prop: PropulsionConfig | None = None,
    **scenario: object,
) -> Project:
    original = base.scenarios["one_day"]
    sc = type(original).model_validate(
        {**original.model_dump(), "duration_s": 21600.0, "step_s": 30.0, **scenario}
    )
    config = replace(base.config, pointing=cfg or pointing(), propulsion=prop or propulsion())
    return replace(base, config=config, scenarios={"one_day": sc}, units=base.units)


# ---- nothing placed: nothing changes -----------------------------------------------------------


def test_a_scenario_without_pointing_or_manoeuvres_has_no_extra_load(base: Project) -> None:
    project = make(base)
    run = run_scenario(project, "one_day")
    assert extra_loads(project, run) is None
    assert maneuver_segments(project, project.scenarios["one_day"]) == []


# ---- the pointing timeline ---------------------------------------------------------------------


def test_one_pointing_mode_over_the_scenario_is_a_constant_hold(base: Project) -> None:
    project = make(base, pointing_default="nadir")
    run = run_scenario(project, "one_day")
    loads = extra_loads(project, run)
    assert loads is not None and not loads.problems
    assert [(e.kind, e.start_s, e.end_s, e.power_w) for e in loads.events] == [
        ("hold", 0.0, 21600.0, 15.0)
    ]
    assert loads.energy_wh() == pytest.approx(15.0 * 21600.0 / 3600.0)


def test_a_rule_changes_the_mode_and_each_change_costs_its_slew(base: Project) -> None:
    project = make(
        base,
        pointing_default="nadir",
        pointing_rules=[{"kind": "in_eclipse", "mode": "target"}],
    )
    run = run_scenario(project, "one_day")
    limit = 21600.0
    eclipses = [
        (max(e.start_s, 0.0), min(e.end_s, limit))
        for e in run.env.eclipses
        if e.end_s > 0.0 and e.start_s < limit
    ]
    assert eclipses, "the example has eclipses in six hours"
    loads = extra_loads(project, run)
    assert loads is not None and not loads.problems
    slews = {r.name: r for r in pointing_budget(project).slews}  # type: ignore[union-attr]
    # the pointing mode over time, written out by hand from the eclipses
    segments: list[tuple[float, float, str]] = []
    cursor = 0.0
    for a, b in eclipses:
        if a > cursor:
            segments.append((cursor, a, "nadir"))
        segments.append((a, b, "target"))
        cursor = b
    if cursor < limit:
        segments.append((cursor, limit, "nadir"))
    expected = 0.0
    changes = 0
    for k, (a, b, mode) in enumerate(segments):
        hold_from = a
        if k > 0:
            name = "out" if mode == "target" else "back"
            t = slews[name].slew_time_s
            assert t is not None and t < b - a
            expected += 45.0 * t / 3600.0
            hold_from = a + t
            changes += 1
        expected += (15.0 if mode == "nadir" else 30.0) * (b - hold_from) / 3600.0
    assert loads.energy_wh() == pytest.approx(expected, rel=1e-9)
    assert [e.kind for e in loads.events].count("slew") == changes


def test_the_events_do_not_overlap_and_cover_the_scenario(base: Project) -> None:
    project = make(
        base,
        pointing_default="nadir",
        pointing_rules=[{"kind": "in_eclipse", "mode": "target"}],
    )
    loads = extra_loads(project, run_scenario(project, "one_day"))
    assert loads is not None
    ordered = sorted(loads.events, key=lambda e: e.start_s)
    assert ordered[0].start_s == 0.0 and ordered[-1].end_s == pytest.approx(21600.0)
    for a, b in zip(ordered, ordered[1:], strict=False):
        assert a.end_s <= b.start_s + 1e-9


def test_a_change_with_no_slew_defined_warns_and_costs_nothing(base: Project) -> None:
    cfg = pointing(slews=[])
    project = make(
        base,
        cfg=cfg,
        pointing_default="nadir",
        pointing_rules=[{"kind": "in_eclipse", "mode": "target"}],
    )
    loads = extra_loads(project, run_scenario(project, "one_day"))
    assert loads is not None
    assert any(p.code == "POINTING_SLEW_MISSING" for p in loads.problems)
    assert all(e.kind != "slew" for e in loads.events)


def test_a_placeholder_hold_power_makes_the_load_unknown_not_zero(base: Project) -> None:
    cfg = pointing(
        modes={
            "nadir": {
                "name": "Nadir",
                "reference": "nadir",
                "actuator": "wheels",
                "hold_power_w": sourced(None, "TBD"),
            },
        },
        slews=[],
    )
    project = make(base, cfg=cfg, pointing_default="nadir")
    loads = extra_loads(project, run_scenario(project, "one_day"))
    assert loads is not None and loads.events[0].power_w is None
    assert loads.energy_wh() is None
    assert loads.mean_power(__import__("numpy").array([0.0, 30.0])) is None
    assert any(p.code == "RESULT_INCOMPLETE" for p in loads.problems)


def test_a_mode_without_a_hold_power_is_not_modelled_and_holds_no_event(base: Project) -> None:
    cfg = pointing(
        modes={"nadir": {"name": "Nadir", "reference": "nadir", "actuator": "wheels"}}, slews=[]
    )
    project = make(base, cfg=cfg, pointing_default="nadir")
    loads = extra_loads(project, run_scenario(project, "one_day"))
    assert loads is not None and loads.events == ()


# ---- the burns ----------------------------------------------------------------------------------


def test_an_electric_burn_draws_its_power_for_its_burn_time(base: Project) -> None:
    project = make(base, maneuvers=[{"name": "Raise", "start_s": 3000.0}])
    run = run_scenario(project, "one_day")
    loads = extra_loads(project, run)
    row = next(m for m in propulsion_budget(project).maneuvers if m.name == "Raise")  # type: ignore[union-attr]
    assert row.burn_time_s is not None
    assert loads is not None and not loads.problems
    (event,) = [e for e in loads.events if e.kind == "burn"]
    assert event.start_s == 3000.0 and event.end_s == pytest.approx(3000.0 + row.burn_time_s)
    assert event.power_w == 800.0
    assert loads.energy_wh() == pytest.approx(800.0 * row.burn_time_s / 3600.0, rel=1e-12)


def test_a_chemical_burn_is_listed_with_no_power(base: Project) -> None:
    project = make(base, maneuvers=[{"name": "Kick", "start_s": 100.0}])
    loads = extra_loads(project, run_scenario(project, "one_day"))
    assert loads is not None
    (event,) = loads.events
    assert event.kind == "burn" and event.power_w == 0.0
    assert loads.energy_wh() == 0.0


def test_the_burn_switches_the_spacecraft_mode_when_the_manoeuvre_names_one(base: Project) -> None:
    project = make(base, maneuvers=[{"name": "Raise", "start_s": 3000.0}])
    (segment,) = maneuver_segments(project, project.scenarios["one_day"])
    row = next(m for m in propulsion_budget(project).maneuvers if m.name == "Raise")  # type: ignore[union-attr]
    assert segment.mode == "safe" and segment.start_s == 3000.0
    assert segment.duration_s == pytest.approx(row.burn_time_s)
    run = run_scenario(project, "one_day")
    inside = next(s for s in run.timeline if s.start_s <= 3000.0 + 1.0 < s.end_s)
    assert inside.mode == "safe"
    # a manoeuvre with no mode leaves the timeline alone
    other = make(base, maneuvers=[{"name": "Kick", "start_s": 100.0}])
    assert maneuver_segments(other, other.scenarios["one_day"]) == []


def test_a_burn_past_the_end_is_cut_and_one_that_starts_after_it_is_dropped(base: Project) -> None:
    row = next(m for m in propulsion_budget(make(base)).maneuvers if m.name == "Raise")  # type: ignore[union-attr]
    start = 21600.0 - row.burn_time_s / 2
    cut = make(base, maneuvers=[{"name": "Raise", "start_s": start}])
    loads = extra_loads(cut, run_scenario(cut, "one_day"))
    assert loads is not None
    (event,) = loads.events
    assert event.end_s == pytest.approx(21600.0)
    assert any(p.code == "MANEUVER_CUT" for p in loads.problems)
    late = make(base, maneuvers=[{"name": "Raise", "start_s": 30000.0}])
    loads = extra_loads(late, run_scenario(late, "one_day"))
    assert loads is not None and loads.events == ()
    assert any(p.code == "MANEUVER_CUT" for p in loads.problems)


def test_a_burn_with_an_unknown_burn_time_cannot_be_placed(base: Project) -> None:
    prop = propulsion(
        systems={
            "ion": {
                "name": "Ion",
                "type": "electric",
                "isp_s": sourced(1500.0),
                "power_w": sourced(800.0),
            },  # no thrust: no burn time
            "chem": {"name": "Chem", "type": "chemical", "isp_s": sourced(220.0)},
        }
    )
    project = make(base, prop=prop, maneuvers=[{"name": "Raise", "start_s": 3000.0}])
    loads = extra_loads(project, run_scenario(project, "one_day"))
    assert loads is not None and loads.events == ()
    assert any(p.code == "RESULT_INCOMPLETE" for p in loads.problems)
    assert loads.mean_power(__import__("numpy").array([0.0, 30.0])) is None


# ---- the mean power on solver steps -------------------------------------------------------------


def test_the_mean_power_of_a_step_is_the_exact_overlap(base: Project) -> None:
    import numpy as np

    project = make(base, maneuvers=[{"name": "Raise", "start_s": 3010.0}], pointing_default="nadir")
    run = run_scenario(project, "one_day")
    loads = extra_loads(project, run)
    assert loads is not None
    edges = np.array([3000.0, 3030.0, 3060.0])
    mean = loads.mean_power(edges)
    assert mean is not None
    # the first step: 15 W for 30 s, plus 800 W for the last 20 s of it
    assert mean[0] == pytest.approx(15.0 + 800.0 * 20.0 / 30.0, rel=1e-12)
    assert mean[1] == pytest.approx(15.0 + 800.0, rel=1e-12)


# ---- the files ----------------------------------------------------------------------------------


def test_a_scenario_that_names_something_unknown_is_refused(tmp_path: Path) -> None:
    import shutil

    root = tmp_path / "p"
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", root)
    scenario = root / "scenarios" / "one_day.yaml"
    text = scenario.read_text(encoding="utf-8")
    scenario.write_text(
        text + "pointing_default: nope\nmaneuvers:\n  - {name: Nope, start_s: 10}\n",
        encoding="utf-8",
    )
    codes = {p.code for p in load_project(root).problems}
    assert {"REF_UNKNOWN_POINTING_MODE", "REF_UNKNOWN_MANEUVER"} <= codes
    scenario.write_text(
        text + "pointing_default: nadir\nmaneuvers:\n  - {name: Orbit trim, start_s: 10}\n",
        encoding="utf-8",
    )
    loaded = load_project(root)
    assert loaded.project is not None
    assert loaded.project.scenarios["one_day"].pointing_default == "nadir"


def test_pointing_rules_need_a_default(base: Project) -> None:
    with pytest.raises(ValueError):
        base.scenarios["one_day"].model_validate(
            {
                **base.scenarios["one_day"].model_dump(),
                "pointing_rules": [{"kind": "in_eclipse", "mode": "nadir"}],
            }
        )
