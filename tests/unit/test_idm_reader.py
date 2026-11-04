"""The reader turns a synthetic model into the typed model (D-237 to D-239)."""

from __future__ import annotations

from pathlib import Path

import pytest

from budget_core.idm.model import IdmModel
from budget_core.idm.reader import read_idm
from tests.idm.fixtures import EL, model_xml, write_idm


@pytest.fixture
def model(tmp_path: Path) -> IdmModel:
    read = read_idm(write_idm(tmp_path / "synthetic.idm"))
    assert read.ok, [p.format() for p in read.problems]
    assert read.model is not None
    return read.model


def test_system_and_elements(model: IdmModel) -> None:
    assert model.source_name == "synthetic.idm"
    assert model.file_version == "3.4.1.1"
    assert model.project_name == "Test system"
    assert model.propellant_margin == pytest.approx(0.02)
    assert model.last_modification is not None and model.last_modification.year == 2023
    alpha, beta = model.elements
    assert (alpha.id, alpha.name, alpha.mass_target_kg, alpha.mass_margin) == (
        "1",
        "Alpha",
        12.5,
        0.5,
    )
    assert alpha.power_margin == pytest.approx(0.1)
    assert beta.mass_target_kg == 0.0
    assert [(s.id, s.name) for s in model.subsystems] == [("SS1", "Subsystem One")]
    assert [m.id for m in alpha.modes] == ["OFF", "ON"]
    assert [(t.id, t.name) for t in alpha.thermal_modules] == [("1", "Panel node")]


def test_equipment_definitions(model: IdmModel) -> None:
    by_name = {e.name: e for e in model.equipment}
    assert set(by_name) == {"Widget", "Slab", "Spare", "Reservoir"}
    widget = by_name["Widget"]
    assert widget.mci_origin == "ManualInput"
    assert widget.manual_mass_kg == 2.5
    assert widget.maturity == "ToBeModified_10"
    assert widget.mass_margin == pytest.approx(0.1)
    assert widget.power_margin == pytest.approx(0.05)
    assert widget.manual_cog is not None and widget.manual_cog.z_m == 0.25
    assert widget.manual_inertia is not None and widget.manual_inertia.entries[4] == 2.0
    assert widget.temperatures.operating_min_c == -20.0
    assert widget.temperatures.survival_max_c == 60.0
    assert [(m.name, m.power_w, m.dissipation_w) for m in widget.power_modes] == [
        ("On", 15.0, 12.0),
        ("Off", 0.0, 0.0),
    ]
    slab = by_name["Slab"]
    assert slab.mci_origin == "FromGeometry"
    (shape,) = slab.shapes
    assert (shape.mass_type, shape.mass_total_kg, shape.kind) == ("Total", 3.25, "FilledBox")
    assert dict(shape.parameters) == {"d1": 0.1, "d2": 0.2, "d3": 0.02}


def test_optional_units(model: IdmModel) -> None:
    spare = next(e for e in model.equipment if e.name == "Spare")
    assert spare.optional and not spare.default_enabled
    assert spare.optional_by_configuration == (("C1", True),)
    widget = next(e for e in model.equipment if e.name == "Widget")
    assert not widget.optional and widget.default_enabled


def test_only_physical_occurrences_are_counted(model: IdmModel) -> None:
    """The copy inside the assembly definition is a template; its placed copy is physical."""
    ids = [o.full_id for o in model.occurrences]
    assert ids == [
        f"{EL}_eqi.1-1",
        f"{EL}_eqi.1-2",
        f"{EL}_eqi.2-1",
        f"{EL}_eqi.4-1",
        f"{EL}_assi.5-1_eqi.1-1",
    ]
    assert f"{EL}_ass.5_eqi.1-1" not in ids
    nested = model.occurrences[-1]
    assert nested.assembly_path == (f"{EL}_ass.5",)
    assert model.occurrences[0].assembly_path == ()
    assert [a.name for a in model.assemblies] == ["Rack"]
    assert all(o.element_id == "1" and o.subsystem_id == "SS1" for o in model.occurrences)


def test_power_mappings_and_thermal_module(model: IdmModel) -> None:
    first = model.occurrences[0]
    assert first.thermal_module_full_id == "el.1_thm.1"
    assert [(m.mode_id, m.power_mode_full_id) for m in first.element_mappings] == [
        ("OFF", f"{EL}_eq.1_pm.2"),
        ("ON", f"{EL}_eq.1_pm.1"),
    ]
    assert first.element_mappings[0].custom_power_w is None
    assert model.occurrences[2].element_mappings == ()  # the slab has no power modes
    assert model.occurrences[2].thermal_module_full_id is None


def test_tank_content(model: IdmModel) -> None:
    reservoir = model.occurrences[3]
    (content,) = reservoir.tank_contents
    assert content.default_filling == 1.0
    assert content.filling_by_configuration == (("C1", 0.25),)
    tank = next(e for e in model.equipment if e.name == "Reservoir").shapes[0]
    assert tank.object_full_id == content.tank_object_full_id
    assert dict(tank.parameters)["capacity"] == 8.0
    assert dict(tank.parameters)["maximalFilling"] == 0.95


def test_modes_configurations_and_custom_data(model: IdmModel) -> None:
    (mode,) = model.system_modes
    assert (mode.id, mode.name, mode.duty_cycle) == ("M1", "Mode one", 0.0)
    assert mode.element_mode_full_ids == ("el.1_elm.ON",)
    (config,) = model.configurations
    assert (config.id, config.enabled_element_ids) == ("C1", ("1",))
    assert [c.name for c in model.custom_properties] == ["Free note"]


def test_a_formula_flagged_not_valid_is_listed_not_evaluated(model: IdmModel) -> None:
    assert model.stale_formula_targets == ("el.1_ss.SS1_eq.2_sh.1_fbox_d1",)


@pytest.mark.parametrize(
    ("find", "replace", "field"),
    [
        ("<massTarget>12,5</massTarget>", "<massTarget>12.5</massTarget>", "massTarget"),
        ("<manualMass>2,5</manualMass>", "<manualMass>two</manualMass>", "manualMass"),
        ("<isOptional>False</isOptional>", "<isOptional>maybe</isOptional>", "isOptional"),
        (
            "<lastModification>06/09/2023 08:38:12</lastModification>",
            "<lastModification>2023-09-06</lastModification>",
            "lastModification",
        ),
    ],
)
def test_a_value_in_another_format_makes_the_read_fail_without_echoing_it(
    tmp_path: Path, find: str, replace: str, field: str
) -> None:
    xml = model_xml()
    assert find in xml
    read = read_idm(write_idm(tmp_path / "x.idm", xml.replace(find, replace, 1)))
    assert not read.ok
    bad = [p for p in read.problems if p.code == "IDM_VALUE_INVALID"]
    assert len(bad) == 1 and field in bad[0].path
    for text in ("12.5", "two", "maybe", "2023-09-06"):
        assert all(text not in p.format() for p in read.problems)


def test_an_occurrence_of_an_unknown_equipment_is_left_out_with_a_warning(tmp_path: Path) -> None:
    xml = model_xml().replace(
        f'<Equipment ref="{EL}_eq.2" />', '<Equipment ref="el.9_ss.X_eq.1" />'
    )
    read = read_idm(write_idm(tmp_path / "x.idm", xml))
    assert read.ok
    assert [p.code for p in read.problems] == ["IDM_REF_UNRESOLVED"]
    assert read.model is not None
    assert len(read.model.occurrences) == 4


def test_a_unit_of_another_kind_is_left_out_with_a_warning(tmp_path: Path) -> None:
    extra = f'<Gadget id="9" fullId="{EL}_gad.9"><name>Odd</name></Gadget>'
    read = read_idm(write_idm(tmp_path / "x.idm", model_xml(extra_units=extra)))
    assert read.ok
    assert [p.code for p in read.problems] == ["IDM_UNIT_KIND_UNKNOWN"]
    assert read.problems[0].path == f"{EL}_gad.9"


def test_no_message_contains_text_of_the_file(tmp_path: Path) -> None:
    xml = (
        model_xml()
        .replace("Widget", "WidgetSecretName")
        .replace("<massTarget>12,5", "<massTarget>x")
    )
    read = read_idm(write_idm(tmp_path / "x.idm", xml))
    assert not read.ok
    assert all("WidgetSecretName" not in p.format() for p in read.problems)
