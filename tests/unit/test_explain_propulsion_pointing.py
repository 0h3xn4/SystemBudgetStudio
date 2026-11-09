# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""Explain for the propulsion and pointing budgets (D-255): every cell of every table has an
explanation whose result is the value the table shows, and a number that is n/a says why."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from budget_core.explain import Explainer, ExplainError, explainable_tables
from budget_core.io.project_loader import load_project

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
IDS = {
    "propulsion:summary",
    "propulsion:systems",
    "propulsion:maneuvers",
    "pointing:modes",
    "pointing:slews",
}


def _project(name: str):  # type: ignore[no-untyped-def]
    project = load_project(EXAMPLES / name).project
    assert project is not None
    return project


@pytest.mark.parametrize("name", ["microsat_250kg_eps", "microsat_250kg", "microsat_250kg_clean"])
def test_every_cell_is_explained_with_the_value_the_table_shows(name: str) -> None:
    project = _project(name)
    assert {table_id for table_id, _ in explainable_tables(project)} >= IDS
    explainer = Explainer(project)
    checked = 0
    for table_id in sorted(IDS):
        table = explainer.table(table_id)
        for row in table.rows:
            key = [str(row[i]) for i in table.explain_key]
            for column, shown in zip(table.columns, row, strict=True):
                explanation = explainer.explain(table_id, key, column.header)
                got = explanation.result.value
                if shown is None:
                    assert got is None, (table_id, key, column.header)
                elif isinstance(shown, int | float) and not isinstance(shown, bool):
                    assert isinstance(got, int | float), (table_id, key, column.header, got)
                    assert math.isclose(float(got), float(shown), rel_tol=1e-9, abs_tol=1e-12), (
                        table_id,
                        key,
                        column.header,
                        got,
                        shown,
                    )
                else:
                    assert got == shown, (table_id, key, column.header, got, shown)
                assert explanation.steps
                checked += 1
    assert checked > 40


def test_a_burn_is_traced_to_the_rocket_equation_and_the_next_burn() -> None:
    project = _project("microsat_250kg_eps")
    explainer = Explainer(project)
    table = explainer.table("propulsion:maneuvers")
    name = str(table.rows[0][0])
    explanation = explainer.explain("propulsion:maneuvers", [name], "Mass before (kg)")
    assert [s.equation_id for s in explanation.steps] == ["PROP-ROCKET"]
    names = {q.name for q in explanation.steps[0].inputs}
    assert any(n.startswith("specific impulse") for n in names)
    assert {e.id for e in explanation.equations} == {"PROP-ROCKET"}
    after = explainer.explain("propulsion:maneuvers", [name], "Mass after (kg)")
    assert "next burn" in after.steps[0].result.origin or "dry mass" in str(after.steps[0].inputs)


def test_a_slew_is_traced_to_its_equations_and_its_inertia_source() -> None:
    project = _project("microsat_250kg_eps")
    explainer = Explainer(project)
    table = explainer.table("pointing:slews")
    name = str(table.rows[0][0])
    time = explainer.explain("pointing:slews", [name], "Slew time (s)")
    assert "POINT-SLEW" in {s.equation_id for s in time.steps}
    energy = explainer.explain("pointing:slews", [name], "Energy (Wh)")
    assert {"POINT-SLEW", "POINT-ENERGY"} <= {s.equation_id for s in energy.steps}
    inertia = explainer.explain("pointing:slews", [name], "Inertia (kg m2)")
    assert (
        "mass budget" in inertia.steps[0].result.origin
        or "slews[" in inertia.steps[0].result.origin
    )


def test_a_placeholder_gives_n_a_and_names_the_input() -> None:
    explainer = Explainer(_project("microsat_250kg"))
    table = explainer.table("pointing:slews")
    name = str(table.rows[0][0])
    explanation = explainer.explain("pointing:slews", [name], "Slew time (s)")
    assert not explanation.complete
    assert "n/a" in explanation.format_text()
    system_table = explainer.table("propulsion:systems")
    system = str(system_table.rows[0][0])
    burn = explainer.explain("propulsion:systems", [system], "Burn time (h)")
    assert not burn.complete


@pytest.mark.parametrize(
    ("table", "key", "column", "message"),
    [
        ("propulsion:maneuvers", ["nope"], "Mass before (kg)", "no such manoeuvre"),
        ("propulsion:systems", ["nope"], "Isp (s)", "no such system"),
        ("propulsion:summary", ["nope"], "Value", "no such row"),
        ("pointing:slews", ["nope"], "Slew time (s)", "no such slew"),
        ("pointing:modes", ["nope"], "Reference", "no such pointing mode"),
    ],
)
def test_a_wrong_address_is_refused_in_words(
    table: str, key: list[str], column: str, message: str
) -> None:
    with pytest.raises(ExplainError, match=message):
        Explainer(_project("microsat_250kg_eps")).explain(table, key, column)


def test_the_tables_are_not_offered_without_their_files(tmp_path: Path) -> None:
    project = _project("microsat_250kg_eps")
    from dataclasses import replace

    bare = replace(project, config=replace(project.config, propulsion=None, pointing=None))
    assert not {t for t, _ in explainable_tables(bare)} & IDS
    with pytest.raises(ExplainError, match="no propulsion file"):
        Explainer(bare).table("propulsion:summary")
