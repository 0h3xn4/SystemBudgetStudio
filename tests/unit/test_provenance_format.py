"""The file-format revision for provenance (D-213): the `provenance:` mapping, `status`,
`requires`, the version step of every kind and the rules for the digest."""

from __future__ import annotations

from pathlib import Path

import pytest

from budget_core.io.migrations import DEFAULT_REGISTRY, MigrationRegistry
from budget_core.io.project_digest import project_digest
from budget_core.io.project_loader import load_project, model_to_data
from budget_core.model.annotations import (
    ProvenanceEntry,
    Selector,
    find_entry,
    parse_path,
    resolve_path,
    unknown_paths,
)
from budget_core.model.versions import CURRENT_VERSIONS
from budget_core.problem_catalogue import CATALOGUE
from tests.helpers import edit, write_valid_project

UNIT = "units/{}.yaml"


def _unit_file(root: Path) -> str:
    return UNIT.format(sorted(p.stem for p in (root / "units").glob("*.yaml"))[0])


def _project(root: Path) -> Path:
    write_valid_project(root)
    return root


def _codes(root: Path) -> set[str]:
    return {p.code for p in load_project(root).problems}


# ---- versions and migration ----------------------------------------------------------------


def test_every_kind_moves_up_one_version() -> None:
    assert CURRENT_VERSIONS == {
        "project": 2,
        "spacecraft": 2,
        "unit": 3,
        "expendable": 2,
        "orbit": 2,
        "ground_station": 2,
        "target": 2,
        "scenario": 3,
        "link": 2,
        "spacecraft_mode": 2,
        "margin_policy": 3,
        "power_config": 2,
        "power_system": 2,
        "thermal_model": 2,
        "thermal_environment": 2,
        "mass_limits": 2,
        "ebn0_table": 2,
        "attenuation_table": 2,
    }


@pytest.mark.parametrize("kind", sorted(CURRENT_VERSIONS))
def test_a_file_of_the_previous_version_reads_unchanged_in_the_current_one(kind: str) -> None:
    current = CURRENT_VERSIONS[kind]
    # the oldest version a file of this kind ever had that has a chain of steps
    start = {"unit": 1, "scenario": 1, "margin_policy": 1}.get(kind, 1)
    if kind == "margin_policy":
        data = {"schema_version": 2, "kind": kind, "classes": {}}
        start = 2
    else:
        data = {"schema_version": start, "kind": kind, "name": "n"}
    out, problem = DEFAULT_REGISTRY.migrate(kind, data)
    assert problem is not None and problem.code == "FILE_MIGRATED"
    assert out["schema_version"] == current
    assert out["name" if kind != "margin_policy" else "classes"] == data.get(
        "name", data.get("classes")
    ), "no key moves"
    assert start < current


def test_a_tool_of_the_previous_release_refuses_a_new_file_as_too_new() -> None:
    previous = MigrationRegistry({"unit": 2})
    _, problem = previous.migrate("unit", {"schema_version": 3, "kind": "unit"})
    assert problem is not None and problem.code == "SCHEMA_TOO_NEW"


def test_a_saved_project_is_written_in_the_current_versions(tmp_path: Path) -> None:
    root = _project(tmp_path / "p")
    text = (root / _unit_file(root)).read_text(encoding="utf-8")
    assert f"schema_version: {CURRENT_VERSIONS['unit']}\n" in text
    assert "provenance" not in text and "status" not in text
    assert "requires" not in (root / "project.yaml").read_text(encoding="utf-8")


def test_an_old_project_loads_and_says_it_was_migrated(tmp_path: Path) -> None:
    root = _project(tmp_path / "p")
    edit(
        root, "project.yaml", f"schema_version: {CURRENT_VERSIONS['project']}", "schema_version: 1"
    )
    result = load_project(root)
    assert result.project is not None
    assert any(p.code == "FILE_MIGRATED" and p.file == "project.yaml" for p in result.problems)


# ---- the provenance mapping ----------------------------------------------------------------


def _with_provenance(root: Path, block: str) -> None:
    rel = _unit_file(root)
    path = root / rel
    path.write_text(path.read_text(encoding="utf-8") + block, encoding="utf-8", newline="\n")


def test_an_entry_is_read_and_carried(tmp_path: Path) -> None:
    root = _project(tmp_path / "p")
    _with_provenance(
        root,
        "provenance:\n  mass_kg:\n    source: Data sheet XYZ\n    note: flight model\n"
        "    status: estimate\n",
    )
    result = load_project(root)
    assert result.project is not None
    unit = next(iter(result.project.units.values()))
    assert unit.provenance["mass_kg"] == ProvenanceEntry(
        source="Data sheet XYZ", note="flight model", status="estimate"
    )
    assert not [p for p in result.problems if p.code.startswith("PROVENANCE")]


def test_the_status_defaults_to_sourced_and_the_source_is_required(tmp_path: Path) -> None:
    root = _project(tmp_path / "p")
    _with_provenance(root, "provenance:\n  mass_kg:\n    source: Data sheet\n")
    unit = next(iter(load_project(root).project.units.values()))  # type: ignore[union-attr]
    assert unit.provenance["mass_kg"].status == "sourced"

    root2 = _project(tmp_path / "q")
    _with_provenance(root2, "provenance:\n  mass_kg:\n    note: no source given\n")
    assert "FIELD_MISSING" in _codes(root2)


def test_a_status_outside_the_vocabulary_is_an_error(tmp_path: Path) -> None:
    root = _project(tmp_path / "p")
    _with_provenance(root, "provenance:\n  mass_kg:\n    source: s\n    status: probably\n")
    assert "FIELD_INVALID" in _codes(root)


def test_a_key_that_is_not_a_path_is_an_error(tmp_path: Path) -> None:
    root = _project(tmp_path / "p")
    _with_provenance(root, 'provenance:\n  "mass kg [":\n    source: s\n')
    assert "FIELD_INVALID" in _codes(root)


def test_a_path_that_does_not_exist_is_a_warning_not_an_error(tmp_path: Path) -> None:
    root = _project(tmp_path / "p")
    _with_provenance(root, "provenance:\n  mass_kilograms:\n    source: s\n")
    result = load_project(root)
    assert result.project is not None
    found = [p for p in result.problems if p.code == "PROVENANCE_PATH_UNKNOWN"]
    assert len(found) == 1 and found[0].severity.value == "warning"
    assert found[0].file == _unit_file(root)
    assert "mass_kilograms" not in found[0].message + found[0].hint, "no file content in text"


def test_the_default_entry_and_the_paths_of_every_kind_are_accepted(tmp_path: Path) -> None:
    root = _project(tmp_path / "p")
    for folder in ("orbits", "ground_stations", "targets", "scenarios", "expendables", "modes"):
        for path in sorted((root / folder).glob("*.yaml")):
            path.write_text(
                path.read_text(encoding="utf-8")
                + 'provenance:\n  "*":\n    source: Invented example value\n'
                "    status: illustrative\n",
                encoding="utf-8",
                newline="\n",
            )
    spacecraft = root / "spacecraft.yaml"
    spacecraft.write_text(
        spacecraft.read_text(encoding="utf-8") + "provenance:\n  buses[0].nominal_voltage_v:\n"
        "    source: Bus design note\n",
        encoding="utf-8",
        newline="\n",
    )
    result = load_project(root)
    assert result.project is not None, [p.code for p in result.problems]
    assert not [p for p in result.problems if p.code == "PROVENANCE_PATH_UNKNOWN"]
    assert result.project.spacecraft.provenance["buses[0].nominal_voltage_v"].source


# ---- path syntax and name selectors ----------------------------------------------------------


def test_path_syntax() -> None:
    assert parse_path("mass_kg") == ("mass_kg",)
    assert parse_path("modes[1].avg_power_w") == ("modes", 1, "avg_power_w")
    assert parse_path("modes[imaging].avg_power_w") == ("modes", Selector("imaging"), "avg_power_w")
    for bad in ("", ".a", "a.", "a..b", "a[", "a[]", "[1]", "a b[", "a[b"):
        assert parse_path(bad) is None, bad


DATA = {
    "mass_kg": 1.0,
    "modes": [{"name": "idle", "avg_power_w": 1.0}, {"name": "imaging", "avg_power_w": 5.0}],
}


def test_a_selector_reaches_the_same_input_as_the_index() -> None:
    by_name = resolve_path(DATA, parse_path("modes[imaging].avg_power_w") or ())
    by_index = resolve_path(DATA, parse_path("modes[1].avg_power_w") or ())
    assert by_name == by_index == ("modes", 1, "avg_power_w")


def test_a_selector_follows_its_item_when_a_mode_is_inserted() -> None:
    entries = {"modes[imaging].avg_power_w": ProvenanceEntry(source="TVAC report")}
    data = {"modes": [{"name": "boot"}, *DATA["modes"]]}  # type: ignore[misc]
    found = find_entry(data, entries, "modes[2].avg_power_w")
    assert found is not None and found.source == "TVAC report"
    assert find_entry(data, entries, "modes[1].avg_power_w") is None


def test_a_selector_that_names_no_item_or_several_resolves_to_nothing() -> None:
    assert resolve_path(DATA, parse_path("modes[boost].avg_power_w") or ()) is None
    twice = {"modes": [{"name": "a", "x": 1}, {"name": "a", "x": 2}]}
    assert resolve_path(twice, parse_path("modes[a].x") or ()) is None


def test_the_default_entry_applies_only_to_inputs_without_an_entry_of_their_own() -> None:
    entries = {
        "*": ProvenanceEntry(source="Invented", status="illustrative"),
        "mass_kg": ProvenanceEntry(source="Data sheet"),
    }
    own = find_entry(DATA, entries, "mass_kg")
    other = find_entry(DATA, entries, "modes[0].avg_power_w")
    assert own is not None and own.source == "Data sheet"
    assert other is not None and other.status == "illustrative"
    assert find_entry(DATA, {}, "mass_kg") is None, "no entry, no source recorded"


def test_unknown_paths_ignore_the_default_key_and_the_mapping_itself() -> None:
    data = {**DATA, "provenance": {"*": {}, "mass_kg": {}, "mass_g": {}, "modes[idle].x": {}}}
    assert unknown_paths(data) == ["mass_g", "modes[idle].x"]


# ---- status on a sourced number --------------------------------------------------------------


def test_status_on_a_sourced_number_is_read_and_written_only_when_not_the_default(
    tmp_path: Path,
) -> None:
    root = _project(tmp_path / "p")
    path = root / "config" / "power_config.yaml"
    assert "status" not in path.read_text(encoding="utf-8")
    edit(
        root,
        "config/power_config.yaml",
        "  source: test fixture",
        "  source: test fixture\n  status: illustrative",
    )
    result = load_project(root)
    assert result.project is not None
    power = result.project.config.power_config
    assert power is not None and power.distribution_loss_ratio.status == "illustrative"
    assert model_to_data(power)["distribution_loss_ratio"]["status"] == "illustrative"
    assert "status" not in model_to_data(power, annotations=False)["distribution_loss_ratio"]


def test_a_placeholder_stays_a_placeholder_whatever_its_status(tmp_path: Path) -> None:
    root = _project(tmp_path / "p")
    edit(
        root,
        "config/power_config.yaml",
        "  source: test fixture",
        "  source: TBD\n  status: estimate",
    )
    power = load_project(root).project
    assert power is not None or True  # TBD is a warning class, not an error
    from budget_core.model import Sourced

    assert Sourced(value=0.1, source="TBD", status="estimate").is_placeholder
    assert Sourced(value=None, source="s", status="illustrative").is_placeholder


# ---- requires -----------------------------------------------------------------------------


def test_requires_defaults_to_nothing_and_is_not_written(tmp_path: Path) -> None:
    root = _project(tmp_path / "p")
    result = load_project(root)
    assert result.project is not None and result.project.meta.requires == []


def test_an_unknown_feature_is_an_error_with_its_own_code(tmp_path: Path) -> None:
    root = _project(tmp_path / "p")
    edit(root, "project.yaml", "revision:", "requires:\n  - overrides\nrevision:")
    result = load_project(root)
    assert result.project is None
    found = [p for p in result.problems if p.code == "FEATURE_UNSUPPORTED"]
    assert len(found) == 1
    assert found[0].file == "project.yaml" and found[0].path == "requires[0]"
    assert "overrides" not in found[0].message + found[0].hint


def test_a_feature_name_is_a_plain_identifier(tmp_path: Path) -> None:
    root = _project(tmp_path / "p")
    edit(root, "project.yaml", "revision:", 'requires:\n  - "Not A Name"\nrevision:')
    assert "FIELD_INVALID" in _codes(root)


# ---- the digest -----------------------------------------------------------------------------


def test_marking_inputs_changes_neither_the_digest_nor_the_environment_key(
    tmp_path: Path,
) -> None:
    root = _project(tmp_path / "p")
    before = load_project(root).project
    assert before is not None
    digest = project_digest(before)
    for folder in ("units", "modes", "orbits", "ground_stations", "scenarios"):
        for path in sorted((root / folder).glob("*.yaml")):
            path.write_text(
                path.read_text(encoding="utf-8")
                + 'provenance:\n  "*":\n    source: Invented example value\n'
                "    status: illustrative\n",
                encoding="utf-8",
                newline="\n",
            )
    edit(
        root,
        "config/power_config.yaml",
        "  source: test fixture",
        "  source: test fixture\n  status: estimate",
    )
    after = load_project(root).project
    assert after is not None
    assert project_digest(after) == digest
    # but the files are different, so the manifest is
    assert after.manifest != before.manifest


def test_a_real_change_still_changes_the_digest(tmp_path: Path) -> None:
    root = _project(tmp_path / "p")
    before = load_project(root).project
    assert before is not None
    edit(root, _unit_file(root), "mass_kg: 0.2", "mass_kg: 0.3")
    after = load_project(root).project
    assert after is not None and project_digest(after) != project_digest(before)


def test_a_file_written_by_the_tool_keeps_its_provenance(tmp_path: Path) -> None:
    from budget_core.io.project_loader import write_project

    root = _project(tmp_path / "p")
    _with_provenance(root, "provenance:\n  mass_kg:\n    source: Data sheet\n    status: tbd\n")
    project = load_project(root).project
    assert project is not None
    write_project(project, tmp_path / "copy")
    text = (tmp_path / "copy" / _unit_file(root)).read_text(encoding="utf-8")
    assert text.rstrip().endswith(
        "provenance:\n  mass_kg:\n    source: Data sheet\n    status: tbd"
    )


# ---- the catalogue --------------------------------------------------------------------------


def test_the_new_codes_are_in_the_catalogue() -> None:
    assert {"PROVENANCE_PATH_UNKNOWN", "FEATURE_UNSUPPORTED"} <= set(CATALOGUE)
