"""D-206: the explanation of a static link cell agrees with the table, cell by cell."""

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


def _cells(explainer: Explainer):  # type: ignore[no-untyped-def]
    for table_id, _title in explainable_tables(explainer.project):
        if not table_id.startswith("link:"):
            continue
        table = explainer.table(table_id)
        for row in table.rows:
            key = tuple(str(row[i]) for i in table.key_columns)
            for column, value in zip(table.columns, row, strict=True):
                yield table_id, key, column.header, value


@pytest.mark.parametrize("name", ["microsat_250kg_eps", "microsat_250kg", "microsat_150kg"])
def test_every_cell_of_every_link_table_is_explained_and_agrees(name: str) -> None:
    explainer = Explainer(_project(name))
    count = 0
    for table_id, key, header, value in _cells(explainer):
        explanation = explainer.explain(table_id, key, header)
        assert explanation.result.value == value, (table_id, key, header)
        assert explanation.steps, (table_id, key, header)
        count += 1
    assert count > 30


def _first_row(explainer: Explainer):  # type: ignore[no-untyped-def]
    return explainer.link_result().rows[0]


def test_c_n0_names_each_term_with_its_equation_and_source() -> None:
    explainer = Explainer(_project("microsat_250kg_eps"))
    row = _first_row(explainer)
    e = explainer.explain("link:static", (row.link_id, row.point), "C/N0 (dBHz)")
    ids = [s.equation_id for s in e.steps]
    assert ids[-1] == "LNK-CN0"
    assert {"LNK-EIRP", "LNK-FSPL", "LNK-ATT"} <= set(ids)  # this example gives G/T directly
    assert {q.id for q in e.equations} >= {"LNK-CN0", "LNK-EIRP", "LNK-FSPL"}
    origins = " ".join(q.origin for s in e.steps for q in s.inputs)
    assert f"links/{row.link_id}.yaml transmitter.power_w" in origins
    assert any(q.source for s in e.steps for q in s.inputs)  # a sourced input carries its source


def test_a_margin_and_its_closing_decision_chain_from_the_cn0() -> None:
    explainer = Explainer(_project("microsat_250kg_eps"))
    row = _first_row(explainer)
    rate = row.rates[0]
    key = (row.link_id, row.point, f"{rate.data_rate_bps / 1000.0}")
    margin = explainer.explain("link:rates", key, "Margin (dB)")
    assert [s.equation_id for s in margin.steps][-3:] == ["LNK-EBN0", None, "LNK-MARGIN"]
    closes = explainer.explain("link:rates", key, "Closes")
    assert closes.result.value == ("yes" if rate.closes else "no")


def test_a_placeholder_makes_the_value_n_a_and_the_step_says_which_input() -> None:
    explainer = Explainer(_project("microsat_150kg"))
    row = next((r for r in explainer.link_result().rows if r.cn0_dbhz is None), None)
    if row is None:
        pytest.skip("every link of this example is complete")
    e = explainer.explain("link:static", (row.link_id, row.point), "C/N0 (dBHz)")
    assert e.result.value is None
    assert "n/a" in e.format_text()


def test_a_cell_that_does_not_exist_is_refused_in_plain_words() -> None:
    explainer = Explainer(_project("microsat_250kg_eps"))
    row = _first_row(explainer)
    with pytest.raises(ExplainError):
        explainer.explain("link:static", ("no_such_link", row.point), "C/N0 (dBHz)")
    with pytest.raises(ExplainError):
        explainer.explain("link:static", (row.link_id, row.point), "Nope")
    with pytest.raises(ExplainError):
        explainer.explain("link:static", (row.link_id,), "C/N0 (dBHz)")
    with pytest.raises(ExplainError):
        explainer.explain("link:rates", (row.link_id, row.point, "12345"), "Margin (dB)")
    with pytest.raises(ExplainError):
        explainer.explain("link:rows", ("x", "y"), "C/N0 (dBHz)")


def test_a_link_explanation_is_plain_data() -> None:
    explainer = Explainer(_project("microsat_250kg_eps"))
    row = _first_row(explainer)
    data = explainer.explain("link:static", (row.link_id, row.point), "EIRP (dBW)").to_dict()
    assert json.loads(json.dumps(data)) == data
