# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""Creating and updating a project from a model, and the rules of a re-import (D-240 to D-243)."""

from __future__ import annotations

from pathlib import Path

import pytest

from budget_core.idm.importer import (
    MODE_MAP_PATH,
    STATE_PATH,
    ImportPlan,
    apply_plan,
    digest_of,
    plan_import,
)
from budget_core.idm.mapping import ImportOptions
from budget_core.idm.reader import read_idm
from budget_core.io.project_loader import load_project
from budget_core.io.yamlio import dump_yaml, load_yaml_text
from budget_core.problems import Severity
from tests.idm.fixtures import model_xml, write_idm

WIDGET = "el-1_ss-SS1_eqi-1-1"
SLAB = "el-1_ss-SS1_eqi-2-1"


def plan(
    tmp_path: Path,
    xml: str | None = None,
    root: Path | None = None,
    voltage: float | None = 28.0,
    **options: str,
) -> ImportPlan:
    read = read_idm(write_idm(tmp_path / "synthetic.idm", xml))
    assert read.model is not None
    return plan_import(
        read.model, root or tmp_path / "project", ImportOptions(**options), bus_voltage_v=voltage
    )


def run(tmp_path: Path, xml: str | None = None, **kwargs: object) -> ImportPlan:
    result = plan(tmp_path, xml, **kwargs)  # type: ignore[arg-type]
    assert result.ok, [p.format() for p in result.problems if p.severity is Severity.ERROR]
    apply_plan(result)
    return result


def data(root: Path, rel: str) -> dict[str, object]:
    loaded = load_yaml_text((root / rel).read_text(encoding="utf-8")).data
    assert isinstance(loaded, dict)
    return loaded


def edit(root: Path, rel: str, change: object) -> None:
    current = data(root, rel)
    assert callable(change)
    change(current)
    (root / rel).write_text(dump_yaml(current), encoding="utf-8")


def test_a_new_project_is_created_and_loads_without_errors(tmp_path: Path) -> None:
    result = run(tmp_path)
    assert result.new_project
    root = tmp_path / "project"
    loaded = load_project(root)
    assert loaded.project is not None
    assert [p for p in loaded.problems if p.severity is Severity.ERROR] == []
    project = loaded.project
    assert len(project.units) == 5 and set(project.modes) == {"m1"}
    assert project.spacecraft.mission_phases == ["reference", "C1"]
    assert [b.name for b in project.spacecraft.buses] == ["main"]
    assert project.config.margin_policy is not None
    assert "idm_m10_p5" in project.config.margin_policy.classes
    assert project.config.thermal_model is not None
    assert (root / STATE_PATH).is_file() and (root / MODE_MAP_PATH).is_file()


def test_a_new_project_needs_the_bus_voltage(tmp_path: Path) -> None:
    result = plan(tmp_path, voltage=None)
    assert not result.ok
    assert [p.code for p in result.problems if p.severity is Severity.ERROR] == [
        "IDM_NEW_PROJECT_INCOMPLETE"
    ]
    assert not (tmp_path / "project").exists()


def test_nothing_is_written_by_planning(tmp_path: Path) -> None:
    result = plan(tmp_path)
    assert result.files and not (tmp_path / "project").exists()
    with pytest.raises(ValueError):
        apply_plan(plan(tmp_path, voltage=None))


def test_the_same_input_gives_the_same_bytes(tmp_path: Path) -> None:
    a = plan(tmp_path, root=tmp_path / "a")
    b = plan(tmp_path, root=tmp_path / "b")
    assert digest_of(a) == digest_of(b)


def test_importing_again_changes_nothing(tmp_path: Path) -> None:
    run(tmp_path)
    again = plan(tmp_path)
    assert again.ok and again.files == []
    assert {r.action for r in again.results if r.action != "detected"} == {"unchanged"}


def test_the_model_changed_a_value_the_file_still_holds(tmp_path: Path) -> None:
    run(tmp_path)
    xml = model_xml().replace("<manualMass>2,5</manualMass>", "<manualMass>3</manualMass>")
    result = run(tmp_path, xml)
    changed = {r.id: r.detail for r in result.results if r.action == "changed"}
    assert changed[WIDGET] == ("mass_kg",)
    assert data(tmp_path / "project", f"units/{WIDGET}.yaml")["mass_kg"] == 3.0


def test_a_value_the_user_changed_is_kept(tmp_path: Path) -> None:
    run(tmp_path)
    root = tmp_path / "project"
    edit(root, f"units/{WIDGET}.yaml", lambda d: d.update(mass_kg=9.0))
    xml = model_xml().replace("<manualMass>2,5</manualMass>", "<manualMass>3</manualMass>")
    result = run(tmp_path, xml)
    assert data(root, f"units/{WIDGET}.yaml")["mass_kg"] == 9.0
    kept = [p for p in result.problems if p.code == "IDM_KEPT_USER_VALUE"]
    assert len(kept) == 1 and "mass_kg" in kept[0].path
    # and what the model did not change is not touched
    assert data(root, f"units/{WIDGET}.yaml")["bus"] == "main"


def test_a_value_the_user_changed_that_the_model_did_not_is_not_even_mentioned(
    tmp_path: Path,
) -> None:
    run(tmp_path)
    root = tmp_path / "project"
    edit(root, f"units/{WIDGET}.yaml", lambda d: d.update(bus="main", name="My widget"))
    again = plan(tmp_path)
    assert again.files == [] and not [p for p in again.problems if p.code == "IDM_KEPT_USER_VALUE"]


def test_what_the_user_added_is_never_touched(tmp_path: Path) -> None:
    run(tmp_path)
    root = tmp_path / "project"
    mine = data(root, f"units/{WIDGET}.yaml")
    (root / "units" / "my_unit.yaml").write_text(dump_yaml(mine), encoding="utf-8")
    edit(
        root,
        "modes/m1.yaml",
        lambda d: d["assignments"].update({"my_unit": "On"}),  # type: ignore[attr-defined]
    )
    xml = model_xml().replace("<manualMass>2,5</manualMass>", "<manualMass>3</manualMass>")
    run(tmp_path, xml)
    assert (root / "units" / "my_unit.yaml").read_text(encoding="utf-8") == dump_yaml(mine)
    assert data(root, "modes/m1.yaml")["assignments"]["my_unit"] == "On"  # type: ignore[index]


def test_an_object_removed_from_the_model_is_flagged_not_deleted(tmp_path: Path) -> None:
    run(tmp_path)
    placed = '<EquipmentInstance id="2-1" fullId="el.1_ss.SS1_eqi.2-1">'
    xml = model_xml()
    start = xml.index(placed)
    end = xml.index("</EquipmentInstance>", start) + len("</EquipmentInstance>")
    result = run(tmp_path, xml[:start] + xml[end:])
    assert (tmp_path / "project" / "units" / f"{SLAB}.yaml").is_file()
    assert [r.id for r in result.results if r.action == "removed"] == [SLAB]
    assert "IDM_REMOVED_IN_MODEL" in [p.code for p in result.problems]
    state = data(tmp_path / "project", STATE_PATH)
    assert state["units"][SLAB]["status"] == "removed"  # type: ignore[index]
    # the next import does not shout again
    again = plan(tmp_path, xml[:start] + xml[end:])
    assert "IDM_REMOVED_IN_MODEL" not in [p.code for p in again.problems]


def test_a_file_the_user_deleted_is_not_recreated(tmp_path: Path) -> None:
    run(tmp_path)
    root = tmp_path / "project"
    (root / "units" / f"{WIDGET}.yaml").unlink()
    edit(root, "modes/m1.yaml", lambda d: d["assignments"].pop(WIDGET))  # type: ignore[attr-defined]
    result = run(tmp_path)
    assert WIDGET not in data(root, "modes/m1.yaml")["assignments"]  # type: ignore[operator]
    assert not (tmp_path / "project" / "units" / f"{WIDGET}.yaml").exists()
    assert "IDM_DELETED_BY_USER" in [p.code for p in result.problems]


def test_a_file_with_the_same_name_that_the_import_did_not_write_is_left_alone(
    tmp_path: Path,
) -> None:
    read = read_idm(write_idm(tmp_path / "synthetic.idm"))
    assert read.model is not None
    first = run(tmp_path)
    root = tmp_path / "project"
    (root / STATE_PATH).unlink()  # the import forgets what it wrote
    mine = (root / "units" / f"{WIDGET}.yaml").read_text(encoding="utf-8")
    result = plan(tmp_path)
    assert "IDM_FILE_EXISTS_NOT_IMPORTED" in [p.code for p in result.problems]
    assert first.ok and (root / "units" / f"{WIDGET}.yaml").read_text(encoding="utf-8") == mine


def test_comments_in_a_merged_file_survive(tmp_path: Path) -> None:
    run(tmp_path)
    path = tmp_path / "project" / "units" / f"{WIDGET}.yaml"
    path.write_text("# checked with the supplier\n" + path.read_text(encoding="utf-8"))
    xml = model_xml().replace("<manualMass>2,5</manualMass>", "<manualMass>3</manualMass>")
    run(tmp_path, xml)
    text = path.read_text(encoding="utf-8")
    assert text.startswith("# checked with the supplier")
    assert "mass_kg: 3.0" in text


def test_the_mode_map_is_drafted_once_and_then_belongs_to_the_user(tmp_path: Path) -> None:
    run(tmp_path)
    root = tmp_path / "project"
    assert data(root, MODE_MAP_PATH)["system_modes"] == {  # type: ignore[comparison-overlap]
        "M1": {"mode": "m1", "name": "Mode one"}
    }
    edit(
        root,
        MODE_MAP_PATH,
        lambda d: d["system_modes"].update({"M1": {"mode": "orbit", "name": "Orbit"}}),  # type: ignore[attr-defined]
    )
    result = run(tmp_path)
    assert (root / "modes" / "orbit.yaml").is_file()
    assert data(root, MODE_MAP_PATH)["system_modes"]["M1"]["mode"] == "orbit"  # type: ignore[index]
    assert result.count("mode", "added") == 1
    # the old mode file is flagged, not deleted
    assert (root / "modes" / "m1.yaml").is_file()
    assert "IDM_REMOVED_IN_MODEL" in [p.code for p in result.problems]


def test_a_broken_mode_map_is_an_error(tmp_path: Path) -> None:
    run(tmp_path)
    (tmp_path / "project" / MODE_MAP_PATH).write_text("kind: other\n", encoding="utf-8")
    result = plan(tmp_path)
    assert [p.code for p in result.problems if p.severity is Severity.ERROR] == [
        "IDM_MODE_MAP_INVALID"
    ]


def test_an_unknown_bus_is_an_error_for_an_existing_project(tmp_path: Path) -> None:
    run(tmp_path)
    result = plan(tmp_path, bus="nope")
    assert [p.code for p in result.problems if p.severity is Severity.ERROR] == ["IDM_BUS_UNKNOWN"]


def test_margin_option_must_be_known(tmp_path: Path) -> None:
    result = plan(tmp_path, margins="both")
    assert [p.code for p in result.problems if p.severity is Severity.ERROR] == [
        "IDM_OPTION_INVALID"
    ]


def test_a_project_with_errors_is_not_merged_into(tmp_path: Path) -> None:
    run(tmp_path)
    (tmp_path / "project" / "spacecraft.yaml").write_text("not: a spacecraft\n", encoding="utf-8")
    result = plan(tmp_path)
    assert "IDM_PROJECT_UNUSABLE" in [p.code for p in result.problems]
    assert not result.ok


def test_margin_classes_added_to_a_project_keep_the_users_classes(tmp_path: Path) -> None:
    run(tmp_path)
    root = tmp_path / "project"
    edit(
        root,
        "config/margin_policy.yaml",
        lambda d: d["classes"].update(  # type: ignore[attr-defined]
            {
                "mine": {
                    "power_margin_ratio": {"value": 0.3, "source": "mine"},
                    "mass_margin_ratio": {"value": 0.2, "source": "mine"},
                }
            }
        ),
    )
    xml = model_xml().replace("<massMargin>0,1</massMargin>", "<massMargin>0,25</massMargin>", 1)
    run(tmp_path, xml)
    classes = data(root, "config/margin_policy.yaml")["classes"]
    assert "mine" in classes and "idm_m25_p5" in classes  # type: ignore[operator]


def test_phases_the_user_has_are_kept_and_missing_ones_added(tmp_path: Path) -> None:
    run(tmp_path)
    root = tmp_path / "project"
    edit(root, "spacecraft.yaml", lambda d: d.update(mission_phases=["C1", "reference"]))
    xml = model_xml().replace('<Configuration id="C1"', '<Configuration id="C2"')
    run(tmp_path, xml)
    phases = data(root, "spacecraft.yaml")["mission_phases"]
    assert phases == ["C1", "reference", "C2"]
