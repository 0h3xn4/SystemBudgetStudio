"""D-208: the explanation of a power timeline cell agrees with the table, cell by cell."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from budget_core.explain import Explainer, ExplainError, explainable_tables
from budget_core.io.project_loader import load_project
from budget_core.model import Project
from budget_core.power.battery import integrate_battery
from budget_core.power.time_domain import time_domain_budget
from budget_core.scenario.run import run_scenario

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


def _project(name: str) -> Project:
    loaded = load_project(EXAMPLES / name)
    assert loaded.project is not None
    return loaded.project


def _explainer(name: str, basis: str = "nominal") -> Explainer:
    project = _project(name)
    return Explainer(project, scenario=sorted(project.scenarios)[0], load_basis=basis)  # type: ignore[arg-type]


def _cells(explainer: Explainer) -> Iterator[tuple[str, tuple[str, ...], str, object]]:
    for table_id, _title in explainable_tables(explainer.project):
        if not table_id.startswith("timeline:"):
            continue
        if table_id.startswith("timeline:balance:"):
            case = table_id.rsplit(":", 1)[1]
            if case not in {c.case for c in explainer.timeline_result().cases}:
                continue
        table = explainer.table(table_id)
        for row in table.rows:
            key = tuple(str(row[i]) for i in table.explain_key)
            for column, value in zip(table.columns, row, strict=True):
                yield table_id, key, column.header, value


@pytest.mark.parametrize("basis", ["nominal", "margined"])
@pytest.mark.parametrize("name", ["microsat_250kg_eps", "microsat_250kg", "microsat_150kg"])
def test_every_cell_of_every_timeline_table_is_explained_and_agrees(name: str, basis: str) -> None:
    explainer = _explainer(name, basis)
    count = 0
    for table_id, key, header, value in _cells(explainer):
        explanation = explainer.explain(table_id, key, header)
        assert explanation.result.value == value, (table_id, key, header)
        assert explanation.steps, (table_id, key, header)
        count += 1
    assert count > 60


def test_the_tables_are_listed_for_a_project_with_a_scenario() -> None:
    ids = [t for t, _ in explainable_tables(_project("microsat_250kg_eps"))]
    assert "timeline:cases" in ids and "timeline:violations" in ids
    assert "timeline:balance:bol" in ids and "timeline:balance:eol" in ids


def test_the_one_step_battery_update_equals_the_solvers_loop_on_every_step() -> None:
    from budget_core.explain.timeline import _battery_step_wh

    project = _project("microsat_250kg_eps")
    run = run_scenario(project, sorted(project.scenarios)[0])
    result = time_domain_budget(project, run, keep_detail=True)
    detail = result.detail
    assert detail is not None and detail.battery is not None
    b = detail.battery
    for case in result.cases:
        trace = detail.trace(case.case)
        generation = detail.generation_w(case.case)
        assert trace is not None and generation is not None and detail.demand_w is not None
        capacity = detail.setup(case.case).capacity_wh
        assert capacity
        net = generation - detail.demand_w
        for i in range(len(net)):
            after = _battery_step_wh(
                float(trace.energy_wh[i]),
                float(net[i]),
                float(detail.rdt_s[i]),
                capacity,
                b.eta_c,
                b.eta_d,
            )
            assert after == trace.energy_wh[i + 1], (case.case, i)
        again = integrate_battery(
            detail.rdt_s,
            generation,
            detail.demand_w,
            capacity,
            b.eta_c,
            b.eta_d,
            float(trace.energy_wh[0]),
        )
        assert np.array_equal(again.energy_wh, trace.energy_wh)


def test_keeping_the_detail_changes_no_number() -> None:
    project = _project("microsat_250kg_eps")
    run = run_scenario(project, sorted(project.scenarios)[0])
    plain = time_domain_budget(project, run)
    kept = time_domain_budget(project, run, keep_detail=True)
    assert plain.detail is None and kept.detail is not None
    for a, b in zip(plain.cases, kept.cases, strict=True):
        assert a.summary == b.summary and a.balances == b.balances and a.violations == b.violations


def test_a_summary_cell_names_its_equation_and_where_the_inputs_come_from() -> None:
    explainer = _explainer("microsat_250kg_eps")
    capacity = explainer.explain("timeline:cases", ("Battery capacity",), "EOL")
    assert [s.equation_id for s in capacity.steps] == ["TDP-CAP"]
    origins = {q.name: q.origin for q in capacity.steps[0].inputs}
    assert origins["cell capacity"].startswith("config/power_system.yaml battery.cell_capacity_ah")
    assert origins["design life"].startswith("config/power_system.yaml design_life_yr")
    generated = explainer.explain("timeline:cases", ("Energy generated",), "EOL")
    ids = [s.equation_id for s in generated.steps]
    assert ids[:3] == ["TDP-TEMP", "TDP-ARRAY", "TDP-AGE"]
    assert {e.id for e in generated.equations} >= {"TDP-ARRAY", "TDP-AGE", "TDP-COS", "TDP-LIT"}


def test_the_demand_of_the_run_agrees_with_the_modes_to_rounding() -> None:
    explainer = _explainer("microsat_250kg_eps")
    e = explainer.explain("timeline:cases", ("Energy demanded",), "BOL")
    modes = explainer.timeline_result().modes
    by_mode = sum(float(m.demand_w or 0.0) * m.duration_s for m in modes) / 3600.0
    assert e.result.value == pytest.approx(by_mode, rel=1e-9)
    assert "Cross-check" in e.steps[-1].logic


def test_a_mode_cell_delegates_to_the_static_power_budget() -> None:
    explainer = _explainer("microsat_250kg_eps")
    mode = explainer.timeline_result().modes[0]
    e = explainer.explain("timeline:modes", (mode.mode_id,), "Demand at source (W)")
    assert e.steps[-1].label == "Value in the timeline table"
    assert any(s.equation_id for s in e.steps[:-1])


def test_a_battery_state_shows_the_step_that_ends_at_the_lowest_point() -> None:
    explainer = _explainer("microsat_250kg_eps")
    e = explainer.explain("timeline:cases", ("Lowest state of charge",), "EOL")
    assert [s.equation_id for s in e.steps][:1] in (["TDP-SOC"], [None])
    dod = explainer.explain("timeline:cases", ("Deepest depth of discharge",), "EOL")
    assert "TDP-DOD" in [s.equation_id for s in dod.steps]


def test_unknown_rows_columns_and_tables_are_refused_in_plain_words() -> None:
    explainer = _explainer("microsat_250kg_eps")
    with pytest.raises(ExplainError):
        explainer.explain("timeline:cases", ("Nothing",), "BOL")
    with pytest.raises(ExplainError):
        explainer.explain("timeline:cases", ("Battery capacity",), "MOL")
    with pytest.raises(ExplainError):
        explainer.explain("timeline:balance:bol", ("99",), "Orbit")
    with pytest.raises(ExplainError):
        explainer.explain("timeline:violations", ("a", "b", "c", "d"), "Case")


def test_a_project_without_scenario_cannot_explain_the_timeline() -> None:
    project = _project("microsat_250kg_eps")
    explainer = Explainer(replace(project, scenarios={}))
    with pytest.raises(ExplainError):
        explainer.explain("timeline:cases", ("Battery capacity",), "BOL")


def _stressed(name: str = "microsat_250kg_eps") -> Project:
    """The example with a small battery and a weak array: every kind of finding appears."""
    project = _project(name)
    system = project.config.power_system
    assert system is not None
    battery = system.battery.model_copy(
        update={
            "cell_capacity_ah": system.battery.cell_capacity_ah.model_copy(update={"value": 0.4})
        }
    )
    array = system.solar_array.model_copy(
        update={
            "cell_efficiency_ratio": system.solar_array.cell_efficiency_ratio.model_copy(
                update={"value": 0.04}
            )
        }
    )
    power = system.model_copy(update={"battery": battery, "solar_array": array})
    return replace(project, config=replace(project.config, power_system=power))


def test_every_kind_of_finding_is_explained_and_agrees() -> None:
    project = _stressed()
    explainer = Explainer(project, scenario=sorted(project.scenarios)[0])
    codes = {v.code for v in explainer.timeline_result().violations}
    assert {
        "BATTERY_DOD_EXCEEDED",
        "BATTERY_DEPLETED",
        "ORBIT_BALANCE_NEGATIVE",
        "PEAK_POWER_EXCEEDED",
    } <= codes
    count = 0
    for table_id, key, header, value in _cells(explainer):
        explanation = explainer.explain(table_id, key, header)
        assert explanation.result.value == value, (table_id, key, header)
        count += 1
    assert count > 200
    worst = [
        explainer.explain("timeline:violations", key, "Worst value")
        for table_id, key, header, _ in _cells(explainer)
        if table_id == "timeline:violations" and header == "Case"
    ]
    assert {e.steps[0].equation_id for e in worst} >= {
        "TDP-DOD",
        "TDP-SOC",
        "TDP-BALANCE",
        "TDP-PEAK",
    }


@pytest.mark.parametrize("missing", ["battery", "array", "demand"])
def test_a_placeholder_input_makes_the_cells_n_a_and_the_explanation_says_so(missing: str) -> None:
    project = _project("microsat_250kg_eps")
    system = project.config.power_system
    assert system is not None
    if missing == "battery":
        item = system.battery.cell_capacity_ah.model_copy(update={"value": None})
        power = system.model_copy(
            update={"battery": system.battery.model_copy(update={"cell_capacity_ah": item})}
        )
    elif missing == "array":
        item = system.solar_array.solar_irradiance_wm2.model_copy(update={"value": None})
        power = system.model_copy(
            update={
                "solar_array": system.solar_array.model_copy(update={"solar_irradiance_wm2": item})
            }
        )
    else:
        power = system
    project = replace(project, config=replace(project.config, power_system=power))
    explainer = Explainer(project, scenario=sorted(project.scenarios)[0])
    na = 0
    for table_id, key, header, value in _cells(explainer):
        explanation = explainer.explain(table_id, key, header)
        assert explanation.result.value == value, (table_id, key, header)
        na += value is None
    if missing != "demand":
        assert na > 0
    capacity = explainer.explain("timeline:cases", ("Battery capacity",), "BOL")
    assert capacity.complete is (missing != "battery")
