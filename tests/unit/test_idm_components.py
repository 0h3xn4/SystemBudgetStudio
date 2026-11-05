"""Components of an IDM-CIC model (D-254): the kind of an equipment is proposed from its name, the
skeletons of the simulation models are written with placeholders, and the user's component library
brings the data-sheet values in. Existing files and edits are the user's."""

from __future__ import annotations

from pathlib import Path

import pytest

from budget_cli.main import main
from budget_core.idm.components import parse_library, read_library_text
from budget_core.io.project_loader import load_project
from budget_core.io.yamlio import load_yaml_text
from budget_core.problems import Severity
from tests.idm.fixtures import model_xml, write_idm

ARGS = ["--bus-voltage-v", "28"]


def _xml(renames: dict[str, str] | None = None, subsystem: str = "AOCS") -> str:
    xml = model_xml().replace("Subsystem SS1", subsystem)
    for old, new in (renames or {}).items():
        xml = xml.replace(f"<name>{old}</name>", f"<name>{new}</name>", 1)
    return xml


def _import(tmp_path: Path, xml: str, *extra: str, root: str = "p") -> Path:
    model = write_idm(tmp_path / "m.idm", xml)
    project = tmp_path / root
    args = ["import", "idm", str(model), "--project", str(project), *extra, "--apply"]
    if not (project / "project.yaml").exists():
        args += ARGS
    assert main(args) == 0
    return project


def _data(path: Path) -> dict:  # type: ignore[type-arg]
    return load_yaml_text(path.read_text(encoding="utf-8")).data  # type: ignore[no-any-return]


def test_a_wheel_gets_a_skeleton_with_placeholders_and_the_library_template(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project = _import(tmp_path, _xml({"Widget": "Inertia Wheel A", "Slab": "Battery"}, "Power"))
    capsys.readouterr()
    pointing = _data(project / "config" / "pointing.yaml")
    wheel = pointing["actuators"]["inertia-wheel-a"]
    assert wheel["name"] == "Inertia Wheel A"
    assert wheel["max_torque_nm"]["value"] is None and wheel["max_torque_nm"]["source"] == "TBD"
    power = _data(project / "config" / "power_system.yaml")
    assert power["battery"]["cells_in_series"] == 1
    assert power["battery"]["cell_capacity_ah"]["source"] == "TBD"
    assert power["solar_array"]["faces"] == []
    template = (project / "idm" / "components.yaml").read_text(encoding="utf-8")
    assert "components: []" in template and "max_torque_nm" in template
    loaded = load_project(project)
    assert not [p for p in loaded.problems if p.severity is Severity.ERROR]


def test_the_plan_names_proposals_by_id_never_by_name(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    model = write_idm(tmp_path / "m.idm", _xml({"Widget": "Inertia Wheel A"}))
    assert main(["import", "idm", str(model), "--project", str(tmp_path / "p"), *ARGS]) == 0
    out = capsys.readouterr().out
    assert "reaction_wheel" in out and "el.1_ss.SS1_eq.1" in out
    assert "Inertia" not in out and "Components:" in out


def test_the_library_values_arrive_on_the_next_import_with_their_source(tmp_path: Path) -> None:
    xml = _xml({"Widget": "Inertia Wheel A"})
    project = _import(tmp_path, xml)
    (project / "idm" / "components.yaml").write_text(
        "schema_version: 1\nkind: idm_components\ncomponents:\n"
        '  - match: "Inertia Wheel*"\n    values:\n'
        '      max_torque_nm: {value: 0.02, source: "Data sheet XYZ, table 3"}\n'
        '      momentum_capacity_nms: {value: 0.5, source: "Data sheet XYZ, table 3"}\n',
        encoding="utf-8",
    )
    _import(tmp_path, xml)
    wheel = _data(project / "config" / "pointing.yaml")["actuators"]["inertia-wheel-a"]
    assert wheel["max_torque_nm"]["value"] == 0.02
    assert wheel["max_torque_nm"]["source"] == "Data sheet XYZ, table 3"
    assert wheel["momentum_capacity_nms"]["value"] == 0.5


def test_a_value_the_user_changed_is_kept(tmp_path: Path) -> None:
    xml = _xml({"Widget": "Inertia Wheel A"})
    project = _import(tmp_path, xml)
    path = project / "config" / "pointing.yaml"
    text = path.read_text(encoding="utf-8")
    edited = text.replace(
        "      value: null\n      source: TBD", "      value: 0.5\n      source: mine", 1
    )
    assert edited != text
    path.write_text(edited, encoding="utf-8")
    (project / "idm" / "components.yaml").write_text(
        "components:\n  - match: 'inertia wheel*'\n    values:\n"
        '      max_torque_nm: {value: 0.02, source: "Data sheet"}\n',
        encoding="utf-8",
    )
    _import(tmp_path, xml)
    wheel = _data(path)["actuators"]["inertia-wheel-a"]
    assert (wheel["max_torque_nm"]["value"], wheel["max_torque_nm"]["source"]) == (0.5, "mine")


def test_the_users_own_entries_and_files_are_never_changed(tmp_path: Path) -> None:
    project = _import(tmp_path, _xml())  # no component in it
    assert not (project / "config" / "pointing.yaml").exists()
    own = (
        "schema_version: 2\nkind: pointing\nactuators:\n  mine:\n    name: My wheel\n"
        "    max_torque_nm: {value: 0.1, source: Data sheet}\nmodes: {}\nslews: []\n"
    )
    (project / "config" / "pointing.yaml").write_text(own, encoding="utf-8")
    from budget_core.idm.components import _power_system
    from budget_core.io.project_loader import dump_model
    from budget_core.model import PowerSystem

    mine = PowerSystem.model_validate(_power_system({}, {}, [], "my own"))
    power = dump_model(mine)
    (project / "config" / "power_system.yaml").write_text(power, encoding="utf-8")
    _import(tmp_path, _xml({"Widget": "Inertia Wheel A", "Slab": "Battery"}, "Power"))
    actuators = _data(project / "config" / "pointing.yaml")["actuators"]
    assert set(actuators) == {"mine", "inertia-wheel-a"}
    assert actuators["mine"]["max_torque_nm"]["value"] == 0.1
    assert (project / "config" / "power_system.yaml").read_text(encoding="utf-8") == power


def test_an_entry_the_user_deleted_is_not_put_back(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    xml = _xml({"Widget": "Inertia Wheel A"})
    project = _import(tmp_path, xml)
    path = project / "config" / "pointing.yaml"
    path.write_text("schema_version: 2\nkind: pointing\nactuators: {}\nmodes: {}\nslews: []\n")
    capsys.readouterr()
    _import(tmp_path, xml)
    assert _data(path)["actuators"] == {}
    assert "IDM_DELETED_BY_USER" in capsys.readouterr().out


def test_a_second_import_changes_nothing(tmp_path: Path) -> None:
    xml = _xml({"Widget": "Inertia Wheel A", "Slab": "Battery"}, "Power")
    project = _import(tmp_path, xml)
    before = {p: p.read_bytes() for p in project.rglob("*.yaml")}
    _import(tmp_path, xml)
    assert {p: p.read_bytes() for p in project.rglob("*.yaml")} == before


@pytest.mark.parametrize(
    ("name", "kind"),
    [("Thruster_1N_hydrazine", "chemical"), ("Ion Thruster", "electric")],
)
def test_a_thruster_is_chemical_or_electric_by_its_name(
    tmp_path: Path, name: str, kind: str
) -> None:
    project = _import(tmp_path, _xml({"Slab": name}, "Propulsion"))
    (system,) = _data(project / "config" / "propulsion.yaml")["systems"].values()
    assert system["type"] == kind and system["isp_s"]["source"] == "TBD"


def test_a_thruster_that_is_not_known_to_be_either_gets_no_system_and_a_note(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    model = write_idm(tmp_path / "m.idm", _xml({"Slab": "Thruster X"}, "Propulsion"))
    assert main(["import", "idm", str(model), "--project", str(tmp_path / "p"), *ARGS]) == 0
    assert "IDM_COMPONENT_NEEDS_TYPE" in capsys.readouterr().out
    xml = _xml({"Slab": "Thruster X"}, "Propulsion")
    project = _import(tmp_path, xml, root="q")
    assert not (project / "config" / "propulsion.yaml").exists()
    (project / "idm" / "components.yaml").write_text(
        "components:\n  - match: 'Thruster X'\n    values:\n      type: electric\n"
        '      isp_s: {value: 1500, source: "Data sheet"}\n',
        encoding="utf-8",
    )
    _import(tmp_path, xml, root="q")
    (system,) = _data(project / "config" / "propulsion.yaml")["systems"].values()
    assert (system["type"], system["isp_s"]["value"]) == ("electric", 1500)


def test_a_library_can_name_the_kind_of_an_equipment_the_words_do_not_catch(
    tmp_path: Path,
) -> None:
    xml = _xml({"Widget": "RW-4B"})
    project = _import(tmp_path, xml)
    assert not (project / "config" / "pointing.yaml").exists()
    (project / "idm" / "components.yaml").write_text(
        "components:\n  - match: 'RW-*'\n    kind: reaction_wheel\n    values:\n"
        '      max_torque_nm: {value: 0.01, source: "Data sheet"}\n',
        encoding="utf-8",
    )
    _import(tmp_path, xml)
    wheel = _data(project / "config" / "pointing.yaml")["actuators"]["rw-4b"]
    assert wheel["max_torque_nm"]["value"] == 0.01


def test_an_invalid_library_entry_is_named_and_skipped(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    xml = _xml({"Widget": "Inertia Wheel A"})
    project = _import(tmp_path, xml)
    (project / "idm" / "components.yaml").write_text(
        "components:\n  - match: 'Inertia*'\n    kind: toaster\n    values: {}\n", encoding="utf-8"
    )
    capsys.readouterr()
    _import(tmp_path, xml)
    assert "IDM_COMPONENT_LIBRARY_INVALID" in capsys.readouterr().out


def test_the_library_parser_checks_each_entry() -> None:
    library = parse_library(
        {"components": [{"match": "A*"}, {"match": ""}, {"match": "B", "kind": "nope"}, 3]}
    )
    assert [e.match for e in library.entries] == ["A*"]
    assert len(library.problems) == 3
    assert read_library_text(None).entries == []
    assert read_library_text("{{{").problems
