"""D-209: the explanation of a link pass cell agrees with the table, cell by cell."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest

from budget_core.explain import Explainer, ExplainError, explainable_tables
from budget_core.io.project_loader import load_project
from budget_core.link.evaluate import link_pass_series
from budget_core.model import Project
from budget_core.scenario.run import run_scenario

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


def _project(name: str) -> Project:
    loaded = load_project(EXAMPLES / name)
    assert loaded.project is not None
    return loaded.project


def _explainer(name: str) -> Explainer:
    project = _project(name)
    return Explainer(project, scenario=sorted(project.scenarios)[0])


def _cells(explainer: Explainer) -> Iterator[tuple[str, tuple[str, ...], str, object]]:
    for table_id, _title in explainable_tables(explainer.project):
        if not table_id.startswith("linkpass:"):
            continue
        table = explainer.table(table_id)
        for row in table.rows:
            key = tuple(str(row[i]) for i in table.explain_key)
            for column, value in zip(table.columns, row, strict=True):
                yield table_id, key, column.header, value


@pytest.mark.parametrize("name", ["microsat_250kg_eps", "microsat_250kg", "microsat_150kg"])
def test_every_cell_of_every_pass_table_is_explained_and_agrees(name: str) -> None:
    explainer = _explainer(name)
    count = 0
    for table_id, key, header, value in _cells(explainer):
        explanation = explainer.explain(table_id, key, header)
        assert explanation.result.value == value, (table_id, key, header)
        assert explanation.steps, (table_id, key, header)
        count += 1
    assert count > 20


def test_the_tables_are_listed_for_a_project_with_a_peer_station() -> None:
    ids = [t for t, _ in explainable_tables(_project("microsat_250kg_eps"))]
    assert "linkpass:volume" in ids
    assert any(i.startswith("linkpass:passes:") for i in ids)


def test_a_volume_names_its_equation_and_a_lowest_margin_shows_the_whole_budget() -> None:
    explainer = _explainer("microsat_250kg_eps")
    volume_table = explainer.table("linkpass:volume")
    link = str(volume_table.rows[0][0])
    total = explainer.explain("linkpass:volume", (link,), "Scenario total (Mbit)")
    assert "LNK-VOLUME" in [s.equation_id for s in total.steps]
    pass_table = next(
        t for t, _ in explainable_tables(explainer.project) if t.startswith("linkpass:passes:")
    )
    lowest = explainer.explain(pass_table, ("1",), "Lowest margin (dB)")
    ids = [s.equation_id for s in lowest.steps]
    assert "LNK-CN0" in ids and "LNK-MARGIN" in ids
    assert any("pass 1" in q.origin for s in lowest.steps for q in s.inputs)


def test_the_volume_helper_gives_the_solvers_totals_exactly() -> None:
    project = _project("microsat_250kg_eps")
    series = link_pass_series(project, run_scenario(project, sorted(project.scenarios)[0]))
    for s in series.series:
        if s.volume_bits is None:
            continue
        from budget_core.link.budget import data_volume_bits

        assert data_volume_bits(s.selected_rate_bps, s.weight_s) == s.volume_bits
        assert sum(p.volume_bits or 0.0 for p in s.passes) == pytest.approx(
            s.volume_bits, rel=1e-12
        )


def test_unknown_rows_columns_and_tables_are_refused_in_plain_words() -> None:
    explainer = _explainer("microsat_250kg_eps")
    pass_table = next(
        t for t, _ in explainable_tables(explainer.project) if t.startswith("linkpass:passes:")
    )
    with pytest.raises(ExplainError):
        explainer.explain("linkpass:volume", ("nothing",), "Passes")
    with pytest.raises(ExplainError):
        explainer.explain(pass_table, ("999",), "Pass")
    with pytest.raises(ExplainError):
        explainer.explain(pass_table, ("1",), "Nothing")
    with pytest.raises(ExplainError):
        explainer.explain("linkpass:other", ("1",), "Pass")


def test_a_placeholder_makes_the_cells_n_a_and_the_explanation_says_so() -> None:
    project = _project("microsat_250kg_eps")
    table = project.config.ebn0_table
    assert table is not None
    first = table.entries[0]
    item = first.required_ebn0_db.model_copy(update={"value": None})
    entries = [first.model_copy(update={"required_ebn0_db": item}), *table.entries[1:]]
    broken = replace(
        project,
        config=replace(project.config, ebn0_table=table.model_copy(update={"entries": entries})),
    )
    explainer = Explainer(broken, scenario=sorted(broken.scenarios)[0])
    na = 0
    for table_id, key, header, value in _cells(explainer):
        assert explainer.explain(table_id, key, header).result.value == value, (table_id, key)
        na += value is None
    assert na > 0


def test_a_scenario_shorter_than_a_day_has_no_per_day_value() -> None:
    project = _project("microsat_250kg_eps")
    sid = sorted(project.scenarios)[0]
    short = project.scenarios[sid].model_copy(update={"duration_s": 43200.0})
    project = replace(project, scenarios={**project.scenarios, sid: short})
    explainer = Explainer(project, scenario=sid)
    link = str(explainer.table("linkpass:volume").rows[0][0])
    for column in ("Per day (Mbit)", "Per day (MByte)"):
        e = explainer.explain("linkpass:volume", (link,), column)
        assert e.result.value is None
        assert any("shorter than a day" in s.logic for s in e.steps)
    for table_id, key, header, value in _cells(explainer):
        assert explainer.explain(table_id, key, header).result.value == value
