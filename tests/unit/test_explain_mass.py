"""D-206: the explanation of a static mass cell agrees with the table, cell by cell."""

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
        if not table_id.startswith("mass:"):
            continue
        table = explainer.table(table_id)
        rows = table.rows if limit_rows is None else table.rows[:limit_rows]
        for row in rows:
            key = tuple(str(row[i]) for i in table.key_columns)
            for column, value in zip(table.columns, row, strict=True):
                yield table_id, key, column.header, value


@pytest.mark.parametrize("name", ["microsat_250kg_eps", "microsat_150kg", "microsat_250kg"])
def test_every_cell_of_every_mass_table_is_explained_and_agrees(name: str) -> None:
    explainer = Explainer(_project(name))
    count = 0
    for table_id, key, header, value in _cells(explainer):
        explanation = explainer.explain(table_id, key, header)
        assert explanation.result.value == value, (table_id, key, header)
        assert explanation.steps, (table_id, key, header)
        count += 1
    assert count > 100


def test_the_large_example_agrees_on_its_first_rows() -> None:
    explainer = Explainer(_project("stress_200_units"))
    for table_id, key, header, value in _cells(explainer, limit_rows=3):
        assert explainer.explain(table_id, key, header).result.value == value


def test_a_margined_mass_names_its_equation_and_margin_source() -> None:
    explainer = Explainer(_project("microsat_250kg_eps"))
    phase = explainer.project.phases[0]
    item = sorted(explainer.project.units)[0]
    e = explainer.explain(f"mass:items:{phase}", (item,), "With margin (kg)")
    assert [s.equation_id for s in e.steps] == [None, "MASS-MARGIN"]
    assert e.steps[0].inputs[0].origin.startswith("config/margin_policy.yaml classes.")
    assert e.steps[0].inputs[0].source
    assert e.steps[1].inputs[0].origin.startswith(f"units/{item}.yaml")


def test_the_system_margined_total_and_a_limit_margin_chain_their_steps() -> None:
    explainer = Explainer(_project("microsat_250kg_eps"))
    phase = explainer.project.phases[0]
    totals = explainer.explain(f"mass:totals:{phase}", ("Total, with system margin",), "Value")
    assert [s.equation_id for s in totals.steps] == [None, "MASS-SYSMARGIN"]
    limits = explainer.table("mass:limits")
    row = next(r for r in limits.rows if r[0] == phase)
    margin = explainer.explain("mass:limits", (str(row[0]), str(row[1])), "Margin (kg)")
    assert margin.steps[-1].label == "Margin to the limit"
    assert margin.steps[-1].inputs[0].origin.startswith("config/mass_limits.yaml limits[")
    status = explainer.explain("mass:limits", (str(row[0]), str(row[1])), "Status")
    assert status.result.value == row[5]


def test_the_centre_of_gravity_and_the_inertia_name_their_equations() -> None:
    explainer = Explainer(_project("microsat_250kg_eps"))
    phase = explainer.project.phases[0]
    cg = explainer.explain(f"mass:totals:{phase}", ("Centre of gravity x (m)",), "Value")
    assert [s.equation_id for s in cg.steps] == ["MASS-COG"]
    inertia = explainer.explain(f"mass:inertia:{phase}", ("Ixx",), "About CG (kg m2)")
    ids = {s.equation_id for s in inertia.steps}
    assert {"MASS-COG", "MASS-PARALLEL"} <= ids
    assert {q.id for q in inertia.equations} >= {"MASS-COG", "MASS-PARALLEL"}


def test_a_placeholder_margin_makes_the_mass_n_a_and_says_which_input() -> None:
    explainer = Explainer(_project("microsat_150kg"))
    phase = explainer.project.phases[0]
    item = sorted(explainer.project.units)[0]
    e = explainer.explain(f"mass:items:{phase}", (item,), "With margin (kg)")
    if e.result.value is None:
        assert e.steps[0].inputs[0].source == "TBD"
        assert "n/a" in e.format_text()


def test_a_cell_that_does_not_exist_is_refused_in_plain_words() -> None:
    explainer = Explainer(_project("microsat_250kg_eps"))
    phase = explainer.project.phases[0]
    with pytest.raises(ExplainError):
        explainer.explain(f"mass:items:{phase}", ("no_such_item",), "Mass (kg)")
    with pytest.raises(ExplainError):
        explainer.explain(f"mass:items:{phase}", (sorted(explainer.project.units)[0],), "Nope")
    with pytest.raises(ExplainError):
        explainer.explain("mass:items:no_such_phase", ("x",), "Mass (kg)")
    with pytest.raises(ExplainError):
        explainer.explain("mass:rows", ("x",), "Mass (kg)")


def test_a_mass_explanation_is_plain_data() -> None:
    explainer = Explainer(_project("microsat_250kg_eps"))
    phase = explainer.project.phases[0]
    data = explainer.explain("mass:summary", (phase,), "With system margin (kg)").to_dict()
    assert json.loads(json.dumps(data)) == data
