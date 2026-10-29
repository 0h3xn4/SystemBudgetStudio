"""The registry of model choices (D-219): every entry is bound to the field or option it names,
every alternative names real equations, the generated page is current, and the assumptions list
and the command are built from it."""

from __future__ import annotations

import json
import typing
from pathlib import Path

import pytest

from budget_cli.main import main
from budget_core import model_choices as mc
from budget_core.assumptions_view import CHOICES, assumptions
from budget_core.equations import EQUATIONS
from budget_core.io.project_loader import load_project
from budget_core.model import Scenario
from budget_core.power.time_domain import LoadBasis

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "examples"


def test_ids_are_unique_and_well_formed() -> None:
    ids = [m.id for m in mc.REGISTRY]
    assert len(ids) == len(set(ids))
    for m in mc.REGISTRY:
        assert m.area in mc.AREAS, m.id
        assert m.id.startswith(m.area + "."), m.id
        assert m.scope in mc.SCOPES, m.id
        assert m.title and m.label and m.acts_on and m.where and m.reference, m.id
        assert m.default in {c.id for c in m.choices}, m.id
        assert len({c.id for c in m.choices}) == len(m.choices), m.id


def test_a_fixed_model_has_one_alternative_and_a_selectable_one_has_two_or_more() -> None:
    for m in mc.REGISTRY:
        if m.scope == "fixed":
            assert len(m.choices) == 1 and not m.field, m.id
        else:
            assert len(m.choices) >= 2 and m.field, m.id


def test_every_equation_named_exists() -> None:
    for m in mc.REGISTRY:
        for c in m.choices:
            for equation in c.equations:
                assert equation in EQUATIONS, (m.id, c.id, equation)


def test_every_alternative_of_a_selectable_choice_has_a_note_or_a_source() -> None:
    for m in mc.of_scope("scenario") + mc.of_scope("run"):
        for c in m.choices:
            assert c.note or mc.source_of(c), (m.id, c.id)


@pytest.mark.parametrize("entry", mc.of_scope("scenario"), ids=lambda m: m.id)
def test_a_scenario_choice_is_a_field_of_the_scenario_with_the_same_values(
    entry: mc.ModelChoice,
) -> None:
    info = Scenario.model_fields[entry.field]
    assert set(typing.get_args(info.annotation)) == {c.id for c in entry.choices}
    assert info.default == entry.default


def test_the_load_basis_choice_is_the_values_of_the_run_option() -> None:
    (entry,) = mc.of_scope("run")
    assert entry.id == "power.load_basis"
    assert {c.id for c in entry.choices} == set(typing.get_args(LoadBasis))
    assert entry.default == "nominal"


def test_the_page_is_current() -> None:
    page = (ROOT / "docs" / "models" / "choices.md").read_text(encoding="utf-8")
    assert page == mc.render_markdown(), "run: budget choices --markdown > docs/models/choices.md"


def test_the_page_lists_every_entry_once() -> None:
    page = mc.render_markdown()
    for m in mc.REGISTRY:
        assert page.count(f"| `{m.id}` |") == 1, m.id


@pytest.mark.parametrize("name", sorted(p.name for p in EXAMPLES.iterdir() if p.is_dir()))
def test_the_assumptions_list_the_registry(name: str) -> None:
    project = load_project(EXAMPLES / name).project
    assert project is not None
    rows = [r for r in assumptions(project) if r.section == CHOICES]
    n_scenarios = len(project.scenarios)
    expected = (
        len(mc.of_scope("scenario")) * n_scenarios
        + len(mc.of_scope("run"))
        + len(mc.of_scope("fixed"))
    )
    phases = sum(1 for s in project.scenarios.values() if s.mission_phase)
    assert len(rows) == expected + phases
    fixed_titles = {m.title for m in mc.of_scope("fixed")}
    assert {r.name for r in rows if r.status == "fixed"} == fixed_titles


def test_a_scenario_row_says_when_the_value_is_the_default(tmp_path: Path) -> None:
    project = load_project(EXAMPLES / "microsat_250kg_eps").project
    assert project is not None
    rows = {r.name: r for r in assumptions(project) if r.section == CHOICES}
    scenario_id = sorted(project.scenarios)[0]
    shadow = rows[f"Scenario {scenario_id}: shadow model"]
    assert shadow.value == project.scenarios[scenario_id].shadow_model
    assert shadow.where == f"scenarios/{scenario_id}.yaml"
    assert rows["Load basis of the power timeline"].value == "nominal"


def test_the_command_lists_explains_and_suggests(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["choices"]) == 0
    listed = capsys.readouterr().out
    assert all(m.id in listed for m in mc.REGISTRY)

    assert main(["choices", "environment.shadow_model"]) == 0
    text = capsys.readouterr().out
    assert "cylindrical" in text and "conical" in text and "ENV-SHADOW-CON" in text

    assert main(["choices", "thermal.model"]) == 0
    assert "Alternatives" not in capsys.readouterr().out  # a fixed model has none

    assert main(["choices", "environment.shadw"]) == 1
    assert "environment.shadow_model" in capsys.readouterr().err

    assert main(["choices", "--markdown"]) == 0
    assert capsys.readouterr().out == mc.render_markdown()


def test_the_assumptions_command_still_lists_the_choices(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert (
        main(
            [
                "assumptions",
                str(EXAMPLES / "microsat_250kg_eps"),
                "--section",
                "choices",
                "--format",
                "json",
            ]
        )
        == 0
    )
    rows = json.loads(capsys.readouterr().out)
    assert {r["section"] for r in rows} == {CHOICES}
    assert any(r["name"] == "Orbit propagation" and r["status"] == "fixed" for r in rows)
