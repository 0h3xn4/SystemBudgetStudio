"""D-206: the explanation of a static thermal cell agrees with the table, cell by cell."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from budget_core.explain import Explainer, ExplainError, explainable_tables
from budget_core.io.project_loader import load_project
from budget_core.model import Project

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


def _project(name: str) -> Project:
    loaded = load_project(EXAMPLES / name)
    assert loaded.project is not None
    return loaded.project


def _cells(explainer: Explainer, limit_rows: int | None = None):  # type: ignore[no-untyped-def]
    for table_id, _title in explainable_tables(explainer.project):
        if not table_id.startswith("thermal:"):
            continue
        table = explainer.table(table_id)
        rows = table.rows if limit_rows is None else table.rows[:limit_rows]
        for row in rows:
            key = tuple(str(row[i]) for i in table.key_columns)
            for column, value in zip(table.columns, row, strict=True):
                yield table_id, key, column.header, value


@pytest.mark.parametrize("name", ["microsat_250kg_eps", "microsat_250kg", "microsat_150kg"])
def test_every_cell_of_every_thermal_table_is_explained_and_agrees(name: str) -> None:
    explainer = Explainer(_project(name))
    count = 0
    for table_id, key, header, value in _cells(explainer):
        explanation = explainer.explain(table_id, key, header)
        assert explanation.result.value == value, (table_id, key, header)
        assert explanation.steps, (table_id, key, header)
        count += 1
    assert count > 50


def test_the_large_example_agrees_on_its_first_rows() -> None:
    explainer = Explainer(_project("stress_200_units"))
    for table_id, key, header, value in _cells(explainer, limit_rows=3):
        assert explainer.explain(table_id, key, header).result.value == value


def _case(explainer: Explainer) -> str:
    return next(c.case for c in explainer.thermal_result().cases if c.complete)


def test_a_dissipation_names_its_equation_and_the_ratio_it_came_from() -> None:
    explainer = Explainer(_project("microsat_250kg_eps"))
    mode = sorted(explainer.project.modes)[0]
    unit = sorted(explainer.project.units)[0]
    e = explainer.explain(f"thermal:units:{mode}", (unit,), "Dissipation (W)")
    assert [s.equation_id for s in e.steps] == ["TH-DISS"]
    assert e.steps[0].inputs[1].origin.startswith(f"units/{unit}.yaml modes[")


def test_a_node_temperature_shows_its_balance_and_that_it_closes() -> None:
    explainer = Explainer(_project("microsat_250kg_eps"))
    case = _case(explainer)
    node = explainer.thermal_result().cases[0].nodes[0].node
    e = explainer.explain(f"thermal:temperatures:{case}", (node,), "Temperature (K)")
    ids = [s.equation_id for s in e.steps]
    assert "TH-ABS" in ids and "TH-SB" in ids and ids.count("TH-BAL") >= 3
    assert e.steps[-1].label.startswith("Check:")
    assert abs(float(e.steps[-1].result.value)) < 1e-6  # type: ignore[arg-type]
    assert "damped Newton" in e.format_text()


def test_a_limit_check_names_the_limits_and_the_margin() -> None:
    explainer = Explainer(_project("microsat_250kg_eps"))
    case = _case(explainer)
    check = next(k for k in explainer.thermal_result().cases[0].checks if k.temperature_k)
    e = explainer.explain(f"thermal:limits:{case}", (check.unit_id,), "Status")
    assert e.steps[0].equation_id == "TH-LIMIT"
    assert e.result.value == check.status
    assert e.steps[0].inputs[3].origin.startswith("config/thermal_environment.yaml")


def test_a_case_that_could_not_be_solved_lists_the_missing_inputs() -> None:
    explainer = Explainer(_project("microsat_150kg"))
    cases = explainer.thermal_result().cases
    incomplete = next((c for c in cases if not c.complete), None)
    if incomplete is None:
        pytest.skip("every case of this example is complete")
    e = explainer.explain(
        f"thermal:temperatures:{incomplete.case}",
        ("not computed (inputs missing, see Problems)",),
        "Temperature (K)",
    )
    assert e.result.value is None and "never replaced by zero" in e.format_text()


def test_a_cell_that_does_not_exist_is_refused_in_plain_words() -> None:
    explainer = Explainer(_project("microsat_250kg_eps"))
    case = _case(explainer)
    mode = sorted(explainer.project.modes)[0]
    with pytest.raises(ExplainError):
        explainer.explain(f"thermal:units:{mode}", ("no_such_unit",), "Dissipation (W)")
    with pytest.raises(ExplainError):
        explainer.explain(f"thermal:temperatures:{case}", ("no_such_node",), "Temperature (K)")
    with pytest.raises(ExplainError):
        explainer.explain("thermal:temperatures:no_such_case", ("x",), "Temperature (K)")
    with pytest.raises(ExplainError):
        explainer.explain("thermal:rows", ("x",), "Temperature (K)")


def test_a_thermal_explanation_is_plain_data() -> None:
    explainer = Explainer(_project("microsat_250kg_eps"))
    case = _case(explainer)
    node = explainer.thermal_result().cases[0].nodes[0].node
    data = explainer.explain(
        f"thermal:temperatures:{case}", (node,), "Radiated to space (W)"
    ).to_dict()
    assert json.loads(json.dumps(data)) == data
