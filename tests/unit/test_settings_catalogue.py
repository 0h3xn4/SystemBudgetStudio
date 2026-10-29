"""The catalogue of settings, tolerances and constants (D-217): the table and the code agree, no
constant is missing, the generated page is current, and the assumptions list is built."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

import pytest

from budget_cli.main import main
from budget_core import settings
from budget_core.assumptions_view import (
    ASSUMPTION_SECTIONS,
    CHOICES,
    CONFIGURATION,
    CREATION,
    FIXED_CHOICES,
    SECTIONS,
    SETTINGS,
    assumptions,
    counts,
)
from budget_core.input_sources import project_files, sourced_nodes
from budget_core.io.project_loader import load_project, model_to_data

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "budget_core"
EXAMPLES = ROOT / "examples"


def _binding(spec: settings.SettingSpec) -> tuple[str, str]:
    module, _, name = spec.binding.partition(":")
    return module, name


# ---- the table ---------------------------------------------------------------------------------


def test_ids_are_unique_and_kinds_and_groups_are_known() -> None:
    ids = [s.id for s in settings.CATALOGUE]
    assert len(ids) == len(set(ids))
    for s in settings.CATALOGUE:
        assert s.kind in settings.KINDS, s.id
        assert s.group in settings._GROUP_TITLE, s.id
        assert s.id.startswith(s.group + "."), s.id
        assert s.title and s.reason and s.acts_on and s.unit, s.id


def test_the_bindings_are_unique() -> None:
    bindings = [s.binding for s in settings.CATALOGUE]
    assert len(bindings) == len(set(bindings))


@pytest.mark.parametrize("spec", settings.CATALOGUE, ids=lambda s: s.id)
def test_every_default_is_the_value_the_code_uses(spec: settings.SettingSpec) -> None:
    module, name = _binding(spec)
    live = getattr(importlib.import_module(f"budget_core.{module}"), name)
    assert live == spec.default, f"{spec.binding} is {live!r}, the catalogue says {spec.default!r}"


def _numeric_constants() -> set[str]:
    found: set[str] = set()
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        module = ".".join(path.relative_to(SRC).with_suffix("").parts)
        for node in tree.body:
            if isinstance(node, ast.Assign):
                targets, value = [t for t in node.targets if isinstance(t, ast.Name)], node.value
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                targets, value = [node.target], node.value
            else:
                continue
            for target in targets:
                if not target.id.isupper() or value is None:
                    continue
                try:
                    constant = ast.literal_eval(value)
                except ValueError, SyntaxError:
                    try:
                        constant = eval(  # noqa: S307 - a constant expression of numbers
                            compile(ast.Expression(value), "x", "eval"), {"__builtins__": {}}, {}
                        )
                    except Exception:
                        continue
                if isinstance(constant, int | float) and not isinstance(constant, bool):
                    found.add(f"{module}:{target.id}")
    return found


def test_every_numeric_constant_of_the_code_has_an_entry_or_a_reason() -> None:
    known = {s.binding for s in settings.CATALOGUE} | set(settings.NOT_SETTINGS)
    missing = sorted(_numeric_constants() - known)
    assert missing == [], (
        "These constants are in the code but not in budget_core/settings.py: add an entry "
        "(or a reason in NOT_SETTINGS): " + ", ".join(missing)
    )


def test_every_entry_names_a_constant_that_exists() -> None:
    constants = _numeric_constants()
    stale = sorted(s.binding for s in settings.CATALOGUE if s.binding not in constants)
    assert stale == [], "These entries name a constant that is not in the code: " + ", ".join(stale)


# ---- the page ----------------------------------------------------------------------------------


def test_the_settings_page_is_current() -> None:
    page = (ROOT / "docs" / "models" / "settings.md").read_text(encoding="utf-8")
    assert page == settings.render_markdown(), (
        "run: budget settings --markdown > docs/models/settings.md"
    )


def test_the_page_lists_every_entry_once() -> None:
    page = settings.render_markdown()
    for s in settings.CATALOGUE:
        assert page.count(f"| `{s.id}` |") == 1, s.id


def test_values_are_shown_exactly() -> None:
    assert settings.format_value(20.0) == "20"
    assert settings.format_value(1_000_000) == "1 000 000"
    assert settings.format_value(1e-12) == "1e-12"
    assert settings.format_value(1.0 - 1e-12) == "0.999999999999"
    assert float(settings.format_value(5.670374419e-8)) == 5.670374419e-8


# ---- the command `budget settings` -------------------------------------------------------------


def test_settings_lists_explains_and_suggests(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["settings"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == len(settings.CATALOGUE)
    assert any(line.startswith("environment.detection_step_s\tsetting\t20 s") for line in lines)
    assert main(["settings", "environment.detection_step_s"]) == 0
    out = capsys.readouterr().out
    assert (
        "Value.           20 s" in out and "budget_core.model.environment.DETECTION_STEP_S" in out
    )
    assert main(["settings", "environment.detection_step"]) == 1
    assert "Did you mean environment.detection_step_s" in capsys.readouterr().err
    assert main(["settings", "--markdown"]) == 0
    assert capsys.readouterr().out == settings.render_markdown()


# ---- the assumptions of a project --------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(p.name for p in EXAMPLES.iterdir() if p.is_dir()))
def test_the_assumptions_of_an_example_have_every_section(name: str) -> None:
    project = load_project(EXAMPLES / name).project
    assert project is not None
    rows = assumptions(project)
    n = counts(rows)
    assert set(n) == set(SECTIONS) and all(n[s] > 0 for s in SECTIONS)
    configured = sum(
        len(list(sourced_nodes(model_to_data(model), ())))
        for rel, model in project_files(project)
        if rel.startswith(("config/", "links/"))
    )
    assert n[CONFIGURATION] == configured
    assert n[CREATION] == len(settings.of_kind("creation"))
    assert n[SETTINGS] == len(
        [s for s in settings.CATALOGUE if s.kind not in ("creation", "internal")]
    )
    assert n[CHOICES] >= len(FIXED_CHOICES)
    assert {r.status for r in rows if r.section == CONFIGURATION} <= {
        "sourced",
        "estimate",
        "illustrative",
        "placeholder",
    }


def test_a_placeholder_is_marked_and_its_value_is_not_available() -> None:
    project = load_project(EXAMPLES / "microsat_250kg").project
    assert project is not None
    rows = [r for r in assumptions(project) if r.section == CONFIGURATION]
    placeholders = [r for r in rows if r.status == "placeholder"]
    assert placeholders and all(r.value == "n/a" or r.source == "TBD" for r in placeholders)
    assert all(r.where.startswith(("config/", "links/")) for r in rows)


def test_a_scenario_that_leaves_the_shadow_model_out_says_it_is_the_default(
    tmp_path: Path,
) -> None:
    import shutil

    root = tmp_path / "p"
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", root)
    path = root / "scenarios" / "one_day.yaml"
    path.write_text(
        "".join(
            line
            for line in path.read_text(encoding="utf-8").splitlines(keepends=True)
            if not line.startswith("shadow_model")
        ),
        encoding="utf-8",
    )
    project = load_project(root).project
    assert project is not None
    row = next(r for r in assumptions(project) if r.name.endswith("shadow model"))
    assert row.value == "cylindrical" and row.status == "default"


def test_the_command_lists_sections_and_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["assumptions", str(EXAMPLES / "microsat_250kg_eps")]) == 0
    text = capsys.readouterr().out
    for section in SECTIONS:
        assert f"\n{section}\n" in text
    assert main(["assumptions", str(EXAMPLES / "microsat_250kg_eps"), "--format", "json"]) == 0
    rows = json.loads(capsys.readouterr().out)
    assert {r["section"] for r in rows} == set(SECTIONS)
    assert all(
        set(r) == {"section", "name", "value", "unit", "source", "status", "where"} for r in rows
    )
    assert main(["assumptions", str(EXAMPLES / "microsat_250kg_eps"), "--section", "creation"]) == 0
    only = capsys.readouterr().out
    assert CREATION in only and CONFIGURATION not in only
    assert set(ASSUMPTION_SECTIONS.values()) == set(SECTIONS)


def test_the_command_refuses_a_project_with_errors(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "project.yaml").write_text("kind: project\n: broken\n", encoding="utf-8")
    assert main(["assumptions", str(tmp_path)]) == 1
