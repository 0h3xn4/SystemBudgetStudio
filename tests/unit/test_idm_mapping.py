"""Mapping a synthetic IDM-CIC model onto project data (decisions D-240 to D-243)."""

from __future__ import annotations

from pathlib import Path

import pytest

from budget_core.idm.mapping import ImportOptions, Mapped, ModeEntry, map_model
from budget_core.idm.model import IdmModel
from budget_core.idm.reader import read_idm
from budget_core.reports.thermal_report import ABSOLUTE_ZERO_OFFSET_K
from tests.idm.fixtures import EL, model_xml, write_idm

WIDGET_1 = "el-1_ss-SS1_eqi-1-1"
SLAB = "el-1_ss-SS1_eqi-2-1"
NESTED = "el-1_ss-SS1_assi-5-1_eqi-1-1"
TANK = "el-1_ss-SS1_eqi-4-1"


def load(tmp_path: Path, xml: str | None = None) -> IdmModel:
    read = read_idm(write_idm(tmp_path / "synthetic.idm", xml))
    assert read.ok, [p.format() for p in read.problems]
    assert read.model is not None
    return read.model


def mapped(tmp_path: Path, xml: str | None = None, **options: str) -> Mapped:
    return map_model(load(tmp_path, xml), ImportOptions(**options))


def codes(result: Mapped) -> list[str]:
    return [f.code for f in result.findings]


def test_one_unit_per_physical_occurrence_with_stable_ids(tmp_path: Path) -> None:
    result = mapped(tmp_path)
    assert sorted(result.units) == sorted([WIDGET_1, "el-1_ss-SS1_eqi-1-2", SLAB, TANK, NESTED])
    assert result.unit_keys[WIDGET_1] == f"{EL}_eqi.1-1"
    assert result.unit_equipment[NESTED] == f"{EL}_eq.1"
    again = mapped(tmp_path)
    assert list(again.units) == list(result.units)  # same ids, same order


def test_names_subsystems_and_the_bus(tmp_path: Path) -> None:
    units = mapped(tmp_path, bus="power").units
    assert units[WIDGET_1]["name"] == "Alpha / Widget [1-1]"
    assert units[NESTED]["name"] == "Alpha / Rack / Widget [1-1]"
    assert {u["subsystem"] for u in units.values()} == {"Subsystem One"}
    assert {u["bus"] for u in units.values()} == {"power"}


def test_mass_is_the_raw_mass_and_the_margin_is_a_class(tmp_path: Path) -> None:
    result = mapped(tmp_path)
    assert result.units[WIDGET_1]["mass_kg"] == 2.5  # entered in the model
    assert result.units[SLAB]["mass_kg"] == 3.25  # sum of shape masses
    klass = result.units[WIDGET_1]["maturity"]
    assert klass == "idm_m10_p5"
    assert result.margin_classes[klass]["mass_margin_ratio"]["value"] == pytest.approx(0.1)
    assert result.margin_classes[klass]["power_margin_ratio"]["value"] == pytest.approx(0.05)
    assert result.units[WIDGET_1]["provenance"]["mass_kg"]["note"].startswith("entered in")


def test_applied_margins_are_in_the_values_and_never_in_the_class(tmp_path: Path) -> None:
    result = mapped(tmp_path, margins="applied")
    assert result.units[WIDGET_1]["mass_kg"] == pytest.approx(2.5 * 1.1)
    on = next(m for m in result.units[WIDGET_1]["modes"] if m["name"] == "On")
    assert on["avg_power_w"] == pytest.approx(15.0 * 1.05)
    assert set(result.margin_classes) >= {"idm_applied"}
    for name, klass in result.margin_classes.items():
        assert klass["mass_margin_ratio"]["value"] == 0.0, name  # applied once, not twice
        assert klass["power_margin_ratio"]["value"] == 0.0, name
    assert {u["maturity"] for u in result.units.values()} == {"idm_applied"}


def test_power_modes_peak_heat_share_and_passive_units(tmp_path: Path) -> None:
    units = mapped(tmp_path).units
    on, off = units[WIDGET_1]["modes"]
    assert (on["name"], on["avg_power_w"], on["peak_power_w"]) == ("On", 15.0, 15.0)
    assert on["heat_dissipation_ratio"] == pytest.approx(0.8)  # 12 W of 15 W
    assert off["heat_dissipation_ratio"] == 1.0  # no power, no heat
    peak = units[WIDGET_1]["provenance"]["modes[On].peak_power_w"]
    assert peak["status"] == "estimate"
    (passive,) = units[SLAB]["modes"]
    assert (passive["name"], passive["avg_power_w"]) == ("Passive", 0.0)
    assert units[SLAB]["provenance"]["modes[Passive].avg_power_w"]["status"] == "estimate"


def test_a_spacecraft_mode_assigns_every_unit(tmp_path: Path) -> None:
    result = mapped(tmp_path)
    (mode_id,) = result.modes
    assert mode_id == "m1"
    mode = result.modes[mode_id]
    assert mode["name"] == "Mode one"
    assert mode["assignments"][WIDGET_1] == "On"  # through the element mode
    assert mode["assignments"][SLAB] == "Passive"
    assert set(mode["assignments"]) == set(result.units)
    assert result.mode_system == {"m1": "M1"}


def test_the_mode_map_renames_or_skips(tmp_path: Path) -> None:
    model = load(tmp_path)
    renamed = map_model(model, ImportOptions(), {"M1": ModeEntry(mode="orbit", name="Orbit")})
    assert list(renamed.modes) == ["orbit"] and renamed.modes["orbit"]["name"] == "Orbit"
    skipped = map_model(model, ImportOptions(), {"M1": ModeEntry(mode=None, name="Mode one")})
    assert skipped.modes == {}


def test_a_custom_power_becomes_a_mode_of_that_unit(tmp_path: Path) -> None:
    xml = model_xml().replace(
        f'<powerMode><PowerMode ref="{EL}_eq.1_pm.1" /></powerMode></ElementToEquipmentPowerMode>',
        "<customPower>7,5</customPower><customDissipation>5</customDissipation>"
        "</ElementToEquipmentPowerMode>",
        1,
    )
    result = mapped(tmp_path, xml)
    modes = {m["name"]: m for m in result.units[WIDGET_1]["modes"]}
    assert modes["custom ON"]["avg_power_w"] == 7.5
    assert modes["custom ON"]["heat_dissipation_ratio"] == pytest.approx(5 / 7.5)
    assert result.modes["m1"]["assignments"][WIDGET_1] == "custom ON"


def test_a_missing_mapping_gives_the_unit_a_zero_watt_mode_and_one_finding_per_mode(
    tmp_path: Path,
) -> None:
    xml = model_xml().replace(
        '<ElementMode ref="el.1_elm.ON" />', '<ElementMode ref="el.2_elm.NONE" />'
    )
    result = mapped(tmp_path, xml)
    assert result.modes["m1"]["assignments"][WIDGET_1] == "Not mapped"
    assert set(result.modes["m1"]["assignments"]) == set(result.units)  # no unit is left out
    modes = {m["name"]: m for m in result.units[WIDGET_1]["modes"]}
    assert (modes["Not mapped"]["avg_power_w"], modes["Not mapped"]["peak_power_w"]) == (0.0, 0.0)
    assert result.units[WIDGET_1]["provenance"]["modes[Not mapped].avg_power_w"]["status"] == (
        "estimate"
    )
    found = [p for p in result.findings if p.code == "IDM_POWER_UNMAPPED"]
    count = sum(1 for v in result.modes["m1"]["assignments"].values() if v == "Not mapped")
    assert count >= 1
    assert [(p.path, p.actual, p.unit) for p in found] == [("M1", float(count), "units")]
    assert "IDM_POWER_UNRESOLVED" not in codes(result)


def test_the_project_check_finds_no_unit_without_a_power_mode_after_such_an_import(
    tmp_path: Path,
) -> None:
    xml = model_xml().replace(
        '<ElementMode ref="el.1_elm.ON" />', '<ElementMode ref="el.2_elm.NONE" />'
    )
    result = mapped(tmp_path, xml)
    for unit_id in result.units:
        names = {m["name"] for m in result.units[unit_id]["modes"]}
        assert result.modes["m1"]["assignments"][unit_id] in names


def test_dissipation_above_power_is_not_a_share(tmp_path: Path) -> None:
    xml = model_xml().replace("<dissipation>1,2E1</dissipation>", "<dissipation>2E1</dissipation>")
    result = mapped(tmp_path, xml)
    on = next(m for m in result.units[WIDGET_1]["modes"] if m["name"] == "On")
    assert "heat_dissipation_ratio" not in on
    assert "IDM_DISSIPATION_UNRESOLVED" in codes(result)


def test_temperature_limits_in_kelvin_and_unset_bands_are_left_out(tmp_path: Path) -> None:
    result = mapped(tmp_path)
    limits = result.units[WIDGET_1]["temperature_limits"]
    assert limits["operating_min_k"] == pytest.approx(-20.0 + ABSOLUTE_ZERO_OFFSET_K)
    assert limits["survival_max_k"] == pytest.approx(60.0 + ABSOLUTE_ZERO_OFFSET_K)
    assert "temperature_limits" not in result.units[SLAB]  # 0, 0, 0, 0: not set


def test_a_survival_band_that_does_not_enclose_the_operating_band_is_dropped(
    tmp_path: Path,
) -> None:
    xml = model_xml().replace(
        "<temperatureNOpMin>-30</temperatureNOpMin><temperatureNOpMax>60</temperatureNOpMax>",
        "<temperatureNOpMin>-10</temperatureNOpMin><temperatureNOpMax>40</temperatureNOpMax>",
    )
    result = mapped(tmp_path, xml)
    limits = result.units[WIDGET_1]["temperature_limits"]
    assert "survival_min_k" not in limits and "operating_min_k" in limits
    assert "IDM_TEMPERATURE_IGNORED" in codes(result)


def test_thermal_modules_become_nodes_and_the_rest_go_to_one_unplaced_node(
    tmp_path: Path,
) -> None:
    result = mapped(tmp_path)
    assert result.units[WIDGET_1]["thermal_node"] == "el-1_thm-1"
    assert result.units[SLAB]["thermal_node"] == "idm_unplaced"
    assert set(result.thermal_nodes) == {"el-1_thm-1", "idm_unplaced"}
    assert result.thermal_nodes["el-1_thm-1"]["name"] == "Alpha / Panel node"


def test_a_tank_becomes_an_expendable_per_phase(tmp_path: Path) -> None:
    result = mapped(tmp_path)
    (key,) = result.expendables
    exp = result.expendables[key]
    assert exp["masses_kg"] == {"C1": 2.0, "reference": 8.0}  # capacity x filling
    assert exp["maturity"] == "idm_propellant_m2"
    assert result.margin_classes["idm_propellant_m2"]["mass_margin_ratio"]["value"] == 0.02
    assert result.expendable_keys[key] == f"{EL}_eqi.4-1_tk.1"


def test_configurations_become_phases(tmp_path: Path) -> None:
    result = mapped(tmp_path)
    assert result.phases == ["reference", "C1"]
    assert all(u.get("phases") is None for u in result.units.values())  # present everywhere


def test_an_optional_unit_follows_its_default_and_its_configurations(tmp_path: Path) -> None:
    placed = (
        f'<EquipmentInstance id="3-1" fullId="{EL}_eqi.3-1">'
        f'<unit><Equipment ref="{EL}_eq.3" /></unit></EquipmentInstance>'
    )
    xml = model_xml().replace(
        '<AssemblyInstance id="5-1"', placed + '<AssemblyInstance id="5-1"', 1
    )
    result = mapped(tmp_path, xml)
    assert result.units["el-1_ss-SS1_eqi-3-1"]["phases"] == ["C1"]  # off by default, on in C1
    off = xml.replace("<enabled>True</enabled>", "<enabled>False</enabled>")
    gone = mapped(tmp_path, off)
    assert "el-1_ss-SS1_eqi-3-1" not in gone.units
    assert "IDM_NEVER_ENABLED" in codes(gone)


def test_a_mass_that_needs_geometry_is_not_estimated(tmp_path: Path) -> None:
    xml = model_xml().replace("<massType>Total</massType>", "<massType>Area</massType>", 1)
    result = mapped(tmp_path, xml)
    assert SLAB not in result.units
    assert "IDM_MASS_UNRESOLVED" in codes(result)
    assert SLAB not in result.modes["m1"]["assignments"]


def test_unmapped_data_is_reported(tmp_path: Path) -> None:
    result = mapped(tmp_path)
    found = codes(result)
    assert "IDM_MARGIN_NOT_APPLIED" in found  # the element's margins
    assert "IDM_CUSTOM_DATA_UNMAPPED" in found
    assert "IDM_FORMULA_STALE" in found
    assert all("Alpha" not in f.format() and "Widget" not in f.format() for f in result.findings)


def test_the_output_is_deterministic(tmp_path: Path) -> None:
    a, b = mapped(tmp_path), mapped(tmp_path)
    assert a.units == b.units and a.modes == b.modes and a.expendables == b.expendables
    assert a.margin_classes == b.margin_classes and a.thermal_nodes == b.thermal_nodes
