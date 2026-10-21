"""A blank project (D-185): a folder that opens, validates and computes (to n/a) with no units and
no invented number."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from budget_core import blank
from budget_core.blank import BlankAnswers, check_blank, create_blank_in, create_blank_project
from budget_core.io.project_loader import load_project
from budget_core.link.evaluate import link_static_budget
from budget_core.mass.static_mass import static_mass_budget
from budget_core.power.static_budget import static_power_budget
from budget_core.problems import Severity
from budget_core.wizard import WizardError


def answers(**kw: object) -> BlankAnswers:
    base: dict[str, object] = {"project_name": "My satellite", "bus_voltage_v": 28.0}
    return BlankAnswers(**{**base, **kw})  # type: ignore[arg-type]


def files(folder: Path) -> list[str]:
    return sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file())


def test_the_files_of_a_blank_project(tmp_path: Path) -> None:
    folder = create_blank_project(answers(), tmp_path / "sat")
    assert files(folder) == [
        "config/attenuation_table.yaml",
        "config/ebn0_table.yaml",
        "config/margin_policy.yaml",
        "config/mass_limits.yaml",
        "config/power_config.yaml",
        "project.yaml",
        "spacecraft.yaml",
    ]


def test_it_loads_without_an_error_and_has_nothing_but_the_spacecraft(tmp_path: Path) -> None:
    loaded = load_project(create_blank_project(answers(), tmp_path / "sat"))
    assert loaded.project is not None
    assert not [p for p in loaded.problems if p.severity is Severity.ERROR]
    project = loaded.project
    assert project.meta.name == "My satellite" and project.meta.revision == "1"
    assert project.spacecraft.name == "My satellite"
    assert [(b.name, b.nominal_voltage_v) for b in project.spacecraft.buses] == [("main", 28.0)]
    assert not (
        project.units
        or project.modes
        or project.orbits
        or project.scenarios
        or project.links
        or project.ground_stations
        or project.targets
        or project.expendables
    )


def test_the_only_warnings_are_the_things_still_to_fill_in(tmp_path: Path) -> None:
    loaded = load_project(create_blank_project(answers(), tmp_path / "sat"))
    codes = {p.code for p in loaded.problems}
    assert codes == {"CONFIG_PLACEHOLDER", "CONFIG_EMPTY_TABLE"}
    assert all(p.severity is Severity.WARNING for p in loaded.problems)


def test_every_configuration_number_is_a_placeholder(tmp_path: Path) -> None:
    folder = create_blank_project(answers(), tmp_path / "sat")
    for name in ("margin_policy", "power_config"):
        data = yaml.safe_load((folder / "config" / f"{name}.yaml").read_text(encoding="utf-8"))
        sourced: list[dict[str, object]] = []

        def walk(node: object, found: list[dict[str, object]] = sourced) -> None:
            if isinstance(node, dict):
                if "source" in node:
                    found.append(node)
                for child in node.values():
                    walk(child)

        walk(data)
        assert sourced, name
        assert all(item["source"] == "TBD" and item.get("value") is None for item in sourced)


def test_no_number_is_invented(tmp_path: Path) -> None:
    """Besides the schema version, the revision and the voltage the user gave, the spacecraft and
    project files hold no number at all."""
    folder = create_blank_project(answers(bus_voltage_v=42.5), tmp_path / "sat")
    numbers: list[float] = []

    def walk(node: object) -> None:
        if isinstance(node, dict):
            for key, child in node.items():
                if key != "schema_version":
                    walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)
        elif isinstance(node, (int, float)) and not isinstance(node, bool):
            numbers.append(float(node))

    for name in ("project.yaml", "spacecraft.yaml"):
        walk(yaml.safe_load((folder / name).read_text(encoding="utf-8")))
    assert numbers == [42.5]


def test_the_static_budgets_compute_to_nothing_and_say_so(tmp_path: Path) -> None:
    project = load_project(create_blank_project(answers(), tmp_path / "sat")).project
    assert project is not None
    for compute in (static_power_budget, static_mass_budget, link_static_budget):
        compute(project)  # no unit, no link: nothing to add up, and no exception


def test_the_command_line_runs_it_to_an_incomplete_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from budget_cli.main import main

    folder = create_blank_project(answers(), tmp_path / "sat")
    assert main(["run", str(folder), "--out", str(tmp_path / "out")]) == 0
    assert "INCOMPLETE" in capsys.readouterr().out


def test_the_same_answers_give_the_same_bytes(tmp_path: Path) -> None:
    one = create_blank_project(answers(), tmp_path / "one")
    two = create_blank_project(answers(), tmp_path / "two")
    for rel in files(one):
        assert (one / rel).read_bytes() == (two / rel).read_bytes(), rel


def test_a_folder_that_exists_is_never_touched(tmp_path: Path) -> None:
    folder = tmp_path / "sat"
    folder.mkdir()
    (folder / "keep.txt").write_text("mine", encoding="utf-8")
    with pytest.raises(WizardError, match="already exists"):
        create_blank_project(answers(), folder)
    assert files(folder) == ["keep.txt"]


def test_a_failed_write_leaves_no_folder_behind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from budget_core import wizard

    def boom(*_args: object, **_kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(wizard, "write_project", boom)
    with pytest.raises(WizardError, match="could not be written"):
        create_blank_project(answers(), tmp_path / "sat")
    assert not (tmp_path / "sat").exists()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("project_name", "   "),
        ("project_name", "x" * (blank.MAX_NAME + 1)),
        ("bus_name", ""),
        ("bus_voltage_v", None),
        ("bus_voltage_v", 0.0),
        ("bus_voltage_v", -28.0),
        ("bus_voltage_v", float("nan")),
        ("bus_voltage_v", float("inf")),
        ("bus_voltage_v", 5000.0),
        ("spacecraft_name", "y" * (blank.MAX_NAME + 1)),
    ],
)
def test_a_wrong_answer_is_named_by_its_field_and_nothing_is_written(
    tmp_path: Path, field: str, value: object
) -> None:
    given = answers(**{field: value})
    issues = check_blank(given)
    assert [i.field for i in issues] == [field]
    with pytest.raises(WizardError):
        create_blank_project(given, tmp_path / "sat")
    assert not (tmp_path / "sat").exists()


def test_the_voltage_has_no_default() -> None:
    assert [i.field for i in check_blank(BlankAnswers(project_name="x"))] == ["bus_voltage_v"]


def test_names_are_used_as_given_and_trimmed(tmp_path: Path) -> None:
    given = answers(bus_name=" power ", spacecraft_name=" Flight model ", project_name=" Ünï ")
    project = load_project(create_blank_project(given, tmp_path / "sat")).project
    assert project is not None
    assert project.meta.name == "Ünï"
    assert project.spacecraft.name == "Flight model"
    assert [b.name for b in project.spacecraft.buses] == ["power"]
    assert set(project.config.power_config.converter_efficiency_ratio) == {"power"}  # type: ignore[union-attr]


def test_create_in_a_parent_names_the_folder_after_the_project(tmp_path: Path) -> None:
    folder = create_blank_in(answers(project_name="Cubesat 2U / flight"), tmp_path)
    assert folder == tmp_path / "cubesat-2u-flight"
    assert (folder / "project.yaml").is_file()
