"""Audit TL-10 / MI-17 / MI-15: range checks, duplicates, blank names, temperature bands, ignored
scenario options, booleans and numeric strings."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from budget_core.io.project_loader import load_project, write_project
from budget_core.model import (
    AttenuationEntry,
    AttenuationTable,
    Ebn0Entry,
    Ebn0Table,
    MassLimit,
    MassLimits,
    Sourced,
    TemperatureLimits,
    Unit,
)
from budget_core.problems import Problem, Severity
from tests.helpers import edit, write_valid_project
from tests.link_helpers import link_project

LINK = "links/dl.yaml"


def sv(value: float | None) -> Sourced:
    return Sourced(value=value, source="test fixture")


def of(problems: list[Problem], code: str) -> list[Problem]:
    return [p for p in problems if p.code == code]


@pytest.fixture
def link_root(tmp_path: Path) -> Path:
    write_project(link_project(tmp_path), tmp_path)
    return tmp_path


@pytest.fixture
def root(tmp_path: Path) -> Path:
    write_valid_project(tmp_path / "p")
    return tmp_path / "p"


# ---- ranges ----------------------------------------------------------------------------------
@pytest.mark.parametrize("gain", ["5000", "-300", "150"])
def test_antenna_gain_must_be_plausible(link_root: Path, gain: str) -> None:
    edit(link_root, LINK, "value: 6.0", f"value: {gain}")
    (problem,) = of(load_project(link_root).problems, "CONFIG_VALUE_INVALID")
    assert problem.path == "transmitter.antenna.gain_dbi.value" and problem.line is not None


def test_g_over_t_must_be_plausible(link_root: Path) -> None:
    edit(link_root, LINK, "value: -7.4897", "value: 400")
    (problem,) = of(load_project(link_root).problems, "CONFIG_VALUE_INVALID")
    assert problem.path == "receiver.g_over_t_dbk.value"


def test_required_ebn0_must_be_plausible(link_root: Path) -> None:
    edit(link_root, "config/ebn0_table.yaml", "value: 10.0", "value: 900.0")
    (problem,) = of(load_project(link_root).problems, "CONFIG_VALUE_INVALID")
    assert problem.file == "config/ebn0_table.yaml"
    assert problem.path == "entries[0].required_ebn0_db.value"


def test_a_negative_atmospheric_loss_is_refused(link_root: Path) -> None:
    edit(link_root, "config/attenuation_table.yaml", "value: 3.0", "value: -10.0")
    problems = of(load_project(link_root).problems, "CONFIG_VALUE_INVALID")
    assert problems and problems[0].file == "config/attenuation_table.yaml"
    assert problems[0].path.endswith("loss_db.value")


def test_ordinary_values_in_range_still_load(link_root: Path) -> None:
    assert not of(load_project(link_root).problems, "CONFIG_VALUE_INVALID")


# ---- duplicates ------------------------------------------------------------------------------
def test_duplicate_ebn0_entries_are_an_error() -> None:
    entry = Ebn0Entry(modulation="BPSK", coding="none", required_ebn0_db=sv(9.6))
    with pytest.raises(ValidationError, match="unique"):
        Ebn0Table(entries=[entry, entry.model_copy(update={"required_ebn0_db": sv(8.0)})])
    other = Ebn0Entry(modulation="BPSK", coding="rate 1/2", required_ebn0_db=sv(4.0))
    assert len(Ebn0Table(entries=[entry, other]).entries) == 2


def test_duplicate_attenuation_name_and_elevation_is_an_error() -> None:
    def rain(elevation: float | None, loss: float) -> AttenuationEntry:
        return AttenuationEntry(
            name="rain",
            attenuation_kind="rain",
            freq_hz=2e9,
            elevation_deg=elevation,
            loss_db=sv(loss),
        )

    with pytest.raises(ValidationError, match="unique"):
        AttenuationTable(entries=[rain(5.0, 1.0), rain(5.0, 2.0)])
    with pytest.raises(ValidationError, match="unique"):
        AttenuationTable(entries=[rain(None, 1.0), rain(None, 2.0)])
    assert (
        len(AttenuationTable(entries=[rain(5.0, 1.0), rain(10.0, 0.5), rain(None, 0.1)]).entries)
        == 3
    )


def test_duplicate_mass_limit_names_in_one_phase_are_an_error() -> None:
    def limit(name: str, phase: str | None) -> MassLimit:
        return MassLimit(name=name, phase=phase, limit_kg=sv(10.0))

    with pytest.raises(ValidationError, match="unique"):
        MassLimits(limits=[limit("cap", None), limit("cap", None)])
    with pytest.raises(ValidationError, match="unique"):
        MassLimits(limits=[limit("cap", "launch"), limit("cap", "launch")])
    with pytest.raises(ValidationError, match="unique"):  # None applies to every phase
        MassLimits(limits=[limit("cap", "launch"), limit("cap", None)])
    assert len(MassLimits(limits=[limit("cap", "launch"), limit("cap", "eol")]).limits) == 2


def test_duplicates_are_reported_with_the_duplicate_code(root: Path) -> None:
    path = root / "config" / "mass_limits.yaml"
    text = path.read_text(encoding="utf-8")
    body = text.split("limits:\n", 1)[1]
    path.write_text(text + body, encoding="utf-8", newline="\n")
    problems = of(load_project(root).problems, "DUPLICATE_NAME")
    assert problems and problems[0].file == "config/mass_limits.yaml"
    assert problems[0].path == "limits"


# ---- blank names -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("rel", "old", "new"),
    [
        ("project.yaml", "name: Test project", "name: '   '"),
        ("units/obc.yaml", "name: OBC", "name: ' '"),
        ("spacecraft.yaml", "- launch", "- '  '"),
        ("modes/nominal.yaml", "name: Nominal", "name: '\t '"),
    ],
)
def test_whitespace_only_text_is_refused(root: Path, rel: str, old: str, new: str) -> None:
    edit(root, rel, old, new)
    problems = [p for p in load_project(root).problems if p.file == rel]
    assert problems and all(p.severity is Severity.ERROR for p in problems)
    assert problems[0].line is not None


def test_empty_description_is_still_fine(root: Path) -> None:
    edit(root, "project.yaml", "name: Test project", "name: Test project\ndescription: ''")
    assert load_project(root).project is not None


# ---- temperature bands -----------------------------------------------------------------------
def test_survival_band_must_enclose_the_operating_band() -> None:
    TemperatureLimits(
        operating_min_k=250, operating_max_k=320, survival_min_k=230, survival_max_k=340
    )
    TemperatureLimits(
        operating_min_k=250, operating_max_k=320, survival_min_k=250, survival_max_k=320
    )
    TemperatureLimits(operating_min_k=250, operating_max_k=320)  # no survival band: not checked
    TemperatureLimits(operating_min_k=250, survival_max_k=340)  # one-sided bands
    for changes in (
        {"survival_min_k": 260.0},  # survival starts above operating
        {"survival_max_k": 310.0},  # survival ends below operating
        {"survival_min_k": 400.0, "survival_max_k": 500.0},  # disjoint
    ):
        with pytest.raises(ValidationError, match="survival"):
            TemperatureLimits(
                **{
                    "operating_min_k": 250.0,
                    "operating_max_k": 320.0,
                    "survival_min_k": 230.0,
                    "survival_max_k": 340.0,
                    **changes,
                }
            )


def test_temperature_band_error_in_a_file_names_the_field(root: Path) -> None:
    text = (root / "units" / "obc.yaml").read_text(encoding="utf-8")
    (root / "units" / "obc.yaml").write_text(
        text + "temperature_limits:\n  operating_min_k: 250\n  operating_max_k: 320\n"
        "  survival_min_k: 300\n  survival_max_k: 340\n",
        encoding="utf-8",
    )
    problems = [p for p in load_project(root).problems if p.file == "units/obc.yaml"]
    assert problems and problems[0].path.startswith("temperature_limits")


# ---- ignored scenario options ----------------------------------------------------------------
def test_options_that_the_chosen_environment_ignores_are_warned(root: Path) -> None:
    edit(root, "scenarios/day.yaml", "orbit: leo", "orbit: leo\nimport_dir: somewhere")
    warnings = of(load_project(root).problems, "SCENARIO_OPTION_IGNORED")
    assert [w.path for w in warnings] == ["import_dir"]
    assert warnings[0].severity is Severity.WARNING and warnings[0].line is not None


def test_spacemissionstudio_ignores_orbit_and_shadow_model(root: Path) -> None:
    (root / "imports").mkdir()
    edit(
        root,
        "scenarios/day.yaml",
        "environment_source: elements",
        "environment_source: spacemissionstudio\nimport_dir: imports",
    )
    edit(root, "scenarios/day.yaml", "shadow_model: cylindrical", "shadow_model: conical")
    warnings = of(load_project(root).problems, "SCENARIO_OPTION_IGNORED")
    assert sorted(w.path for w in warnings) == ["orbit", "shadow_model"]


def test_a_clean_scenario_has_no_such_warning(root: Path) -> None:
    assert not of(load_project(root).problems, "SCENARIO_OPTION_IGNORED")


# ---- booleans and numeric strings (MI-15) ------------------------------------------------------
def unit_with(**changes: object) -> dict[str, object]:
    data: dict[str, object] = {
        "name": "U",
        "subsystem": "S",
        "mass_kg": 1.0,
        "bus": "main",
        "maturity": "m1",
        "modes": [{"name": "on", "avg_power_w": 1.0, "peak_power_w": 2.0}],
    }
    data.update(changes)
    return data


@pytest.mark.parametrize(
    "changes",
    [
        {"mass_properties": {"position_m": [True, False, 0.5]}},
        {"mass_properties": {"position_m": [0.1, 0.2, True]}},
        {"mass_kg": True},
        {"modes": [{"name": "on", "avg_power_w": True, "peak_power_w": 2.0}]},
        {
            "modes": [
                {"name": "on", "avg_power_w": 1.0, "peak_power_w": 2.0, "duty_cycle_ratio": True}
            ]
        },
    ],
)
def test_booleans_are_not_numbers(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Unit.model_validate(unit_with(**changes))


def test_numeric_strings_are_not_numbers_in_plain_numeric_fields() -> None:
    from budget_core.model import ArrayFace

    for bad in ("3", True, "3.0"):
        with pytest.raises(ValidationError):
            Sourced.model_validate({"value": bad, "source": "s"})
    assert Sourced.model_validate({"value": 3, "source": "s"}).value == 3.0
    face = {"name": "x", "normal_body": [1, 0, 0], "strings": 2, "cells_per_string": 3}
    assert ArrayFace.model_validate(face).strings == 2
    for bad in ("3", True, "3.0"):
        with pytest.raises(ValidationError):
            ArrayFace.model_validate({**face, "strings": bad})


def test_unit_strings_still_work_in_unit_suffixed_fields() -> None:
    unit = Unit.model_validate(
        unit_with(
            mass_kg="1500 g",
            mass_properties={"position_m": ["10 cm", 0.2, "1 m"]},
            modes=[{"name": "on", "avg_power_w": "2 W", "peak_power_w": "1 kW"}],
        )
    )
    assert unit.mass_kg == pytest.approx(1.5)
    assert unit.mass_properties is not None
    assert unit.mass_properties.position_m == pytest.approx([0.1, 0.2, 1.0])


# ---- a phase without an allowed depth of discharge (audit PWR-10) -----------------------------
def test_a_scenario_phase_without_a_depth_of_discharge_entry_is_warned(tmp_path: Path) -> None:
    import shutil

    examples = Path(__file__).resolve().parents[2] / "examples"
    dest = tmp_path / "p"
    shutil.copytree(examples / "cubesat_3u_eps", dest)
    assert not of(load_project(dest).problems, "SCENARIO_PHASE_NO_DOD")  # eol has an entry
    edit(
        dest,
        "config/power_system.yaml",
        "    eol:\n      value: 0.3\n      source: Synthetic example value; "
        "not from a data sheet or a standard.\n",
        "",
    )
    warnings = of(load_project(dest).problems, "SCENARIO_PHASE_NO_DOD")
    assert [w.path for w in warnings] == ["mission_phase"]
    assert warnings[0].severity is Severity.WARNING and warnings[0].file == "scenarios/one_day.yaml"
    assert "eol" not in warnings[0].message + warnings[0].hint  # names stay out of the text
