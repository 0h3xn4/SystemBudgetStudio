"""D-206: the explanation of a static power cell agrees with the table, cell by cell."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from budget_cli.main import main
from budget_core.equation_binding import BOUND
from budget_core.equations import EQUATIONS
from budget_core.explain import Explainer, ExplainError
from budget_core.io.project_loader import load_project
from budget_core.model import Project
from budget_core.power.static_budget import static_power_budget  # noqa: F401  (binds the equations)

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


def _project(name: str) -> Project:
    loaded = load_project(EXAMPLES / name)
    assert loaded.project is not None
    return loaded.project


def _cells(explainer: Explainer, limit_rows: int | None = None):  # type: ignore[no-untyped-def]
    for table_id, _title in _tables(explainer):
        table = explainer.table(table_id)
        rows = table.rows if limit_rows is None else table.rows[:limit_rows]
        for row in rows:
            key = tuple(str(row[i]) for i in table.key_columns)
            for column, value in zip(table.columns, row, strict=True):
                yield table_id, key, column.header, value


def _tables(explainer: Explainer):  # type: ignore[no-untyped-def]
    from budget_core.explain import explainable_tables

    return explainable_tables(explainer.project)


@pytest.mark.parametrize("name", ["microsat_250kg_eps", "microsat_150kg", "microsat_250kg"])
def test_every_cell_of_every_table_is_explained_and_agrees_with_the_table(name: str) -> None:
    explainer = Explainer(_project(name))
    count = 0
    for table_id, key, header, value in _cells(explainer):
        explanation = explainer.explain(table_id, key, header)
        assert explanation.result.value == value, (table_id, key, header)
        assert explanation.steps, (table_id, key, header)
        count += 1
    assert count > 100


def test_the_large_example_agrees_too_on_its_first_rows() -> None:
    explainer = Explainer(_project("stress_200_units"))
    for table_id, key, header, value in _cells(explainer, limit_rows=3):
        assert explainer.explain(table_id, key, header).result.value == value


def test_a_derived_value_names_its_equations_inputs_and_sources() -> None:
    explainer = Explainer(_project("microsat_250kg_eps"))
    unit = sorted(explainer.project.units)[0]
    mode = sorted(explainer.project.modes)[0]
    e = explainer.explain(f"power:units:{mode}", (unit,), "With margin (W)")
    assert [s.equation_id for s in e.steps] == ["PWR-EFF", None, "PWR-MARGIN"]
    assert [q.id for q in e.equations] == ["PWR-EFF", "PWR-MARGIN"]
    first = e.steps[0]
    assert first.inputs[0].origin.startswith(f"units/{unit}.yaml modes[")
    margin = e.steps[1].inputs[0]
    assert margin.origin.startswith("config/margin_policy.yaml classes.")
    assert margin.source  # the source text of the sourced number
    assert e.steps[2].inputs[0].origin == "result of step 1"


def test_a_placeholder_makes_the_value_n_a_and_the_step_says_which_input() -> None:
    explainer = Explainer(_project("microsat_150kg"))  # the margin policy holds placeholders
    unit = sorted(explainer.project.units)[0]
    mode = sorted(explainer.project.modes)[0]
    e = explainer.explain(f"power:units:{mode}", (unit,), "With margin (W)")
    assert e.result.value is None and not e.complete
    margin = e.steps[1].inputs[0]
    assert margin.value is None and margin.source == "TBD"
    assert "n/a" in e.format_text()


def test_a_bus_total_goes_through_margin_converter_and_distribution() -> None:
    explainer = Explainer(_project("microsat_250kg_eps"))
    mode = sorted(explainer.project.modes)[0]
    bus = sorted({u.bus for u in explainer.project.units.values()})[0]
    e = explainer.explain(f"power:buses:{mode}", (bus,), "Average at source, with margins (W)")
    assert [s.equation_id for s in e.steps] == [None, "PWR-SYSMARGIN", "PWR-SOURCE"]
    origins = [q.origin for q in e.steps[2].inputs]
    assert "result of step 2" in origins
    assert any(
        o.startswith("config/power_config.yaml converter_efficiency_ratio.") for o in origins
    )


def test_a_cell_that_does_not_exist_is_refused_in_plain_words() -> None:
    explainer = Explainer(_project("microsat_250kg_eps"))
    mode = sorted(explainer.project.modes)[0]
    with pytest.raises(ExplainError):
        explainer.explain(f"power:units:{mode}", ("no_such_unit",), "Effective (W)")
    with pytest.raises(ExplainError):
        explainer.explain(f"power:units:{mode}", (sorted(explainer.project.units)[0],), "Nope")
    with pytest.raises(ExplainError):
        explainer.explain("power:units:no_such_mode", ("x",), "Effective (W)")
    with pytest.raises(ExplainError):
        explainer.explain("mass:rows", ("x",), "Effective (W)")


def test_an_explanation_is_plain_data_for_other_tools() -> None:
    explainer = Explainer(_project("microsat_250kg_eps"))
    mode = sorted(explainer.project.modes)[0]
    data = explainer.explain(f"power:totals:{mode}", ("Load, nominal",), "Average (W)").to_dict()
    assert json.loads(json.dumps(data)) == data
    assert data["address"]["table"] == f"power:totals:{mode}"


# ---- the equations are bound to the code that applies them ---------------------------------
def test_the_power_equations_are_bound_to_functions() -> None:
    for equation_id in ("PWR-EFF", "PWR-MARGIN", "PWR-SYSMARGIN", "PWR-SOURCE", "PWR-PEAK"):
        assert BOUND.get(equation_id), equation_id
    for names in BOUND.values():
        assert all(n.startswith("budget_core.") for n in names)


def test_every_bound_equation_is_in_the_registry() -> None:
    assert set(BOUND) <= set(EQUATIONS)


# ---- the command ---------------------------------------------------------------------------
@pytest.fixture()
def eps(tmp_path: Path) -> Path:
    root = tmp_path / "eps"
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", root)
    return root


def test_the_command_lists_tables_columns_and_explains_a_cell(
    eps: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["explain", str(eps)]) == 0
    listing = capsys.readouterr().out
    assert "power:units:nominal\tUnits in mode Nominal" in listing

    assert main(["explain", str(eps), "power:totals:nominal"]) == 0
    columns = capsys.readouterr().out
    assert "columns: Quantity | Average (W) | Peak (W)" in columns

    args = ["explain", str(eps), "power:totals:nominal", "--row", "Source, nominal"]
    assert main([*args, "--column", "Peak (W)"]) == 0
    text = capsys.readouterr().out
    assert "PWR-SOURCE" in text and "config/power_config.yaml" in text

    assert main([*args, "--column", "Peak (W)", "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["result"]["unit"] == "W"


def test_the_command_refuses_an_unknown_cell_and_an_incomplete_address(
    eps: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    capsys.readouterr()
    assert (
        main(["explain", str(eps), "power:units:nominal", "--row", "nope", "--column", "Duty"]) == 1
    )
    assert "no such unit" in capsys.readouterr().err.lower()
    assert main(["explain", str(eps), "power:units:nominal", "--row", "adcs"]) == 2
