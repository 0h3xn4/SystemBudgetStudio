"""The irradiance model of a scenario (D-219, P5c): `constant` (the default, the configured
irradiance as it is) or `seasonal` (the configured irradiance is the value at 1 AU, scaled by the
inverse square of the Earth-Sun distance the Sun model computes)."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest

from budget_core import model_choices as mc
from budget_core.environment import constants
from budget_core.environment import geometry as geo
from budget_core.equations import EQUATIONS
from budget_core.io.project_loader import load_project, model_to_data
from budget_core.model import Project, Scenario
from budget_core.power import array as arr
from budget_core.power.time_domain import time_domain_budget
from budget_core.scenario.run import run_parameters, run_scenario

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "examples" / "microsat_250kg_eps"
AU = constants.ASTRONOMICAL_UNIT.value


def _jd(when: datetime) -> np.ndarray:
    whole, fraction = geo.julian_date_parts(when)
    return np.array([whole + fraction])


# ---- the factor ---------------------------------------------------------------------------------


def test_the_factor_is_one_at_one_astronomical_unit() -> None:
    assert arr.distance_factor_ratio(np.array([AU]))[0] == 1.0


def test_perihelion_over_aphelion_is_the_inverse_square_of_the_distances() -> None:
    """Reference values: the Earth is at 0.9833 AU in early January and 1.0167 AU in early July,
    so the irradiance is 1.034 and 0.967 of the value at 1 AU, a ratio of about 1.069."""
    peri = geo.sun_direction_and_distance(_jd(datetime(2026, 1, 3, 12, tzinfo=UTC)))[1]
    aph = geo.sun_direction_and_distance(_jd(datetime(2026, 7, 6, 12, tzinfo=UTC)))[1]
    f_peri, f_aph = arr.distance_factor_ratio(peri)[0], arr.distance_factor_ratio(aph)[0]
    assert f_peri == pytest.approx((AU / peri[0]) ** 2, rel=1e-15)
    assert f_peri / f_aph == pytest.approx((aph[0] / peri[0]) ** 2, rel=1e-12)
    assert f_peri == pytest.approx(1.034, abs=0.002)
    assert f_aph == pytest.approx(0.967, abs=0.002)
    assert f_peri / f_aph == pytest.approx(1.069, abs=0.003)


def test_the_array_output_is_linear_in_the_factor_and_one_changes_nothing() -> None:
    kwargs = {
        "irradiance_wm2": 1360.0,
        "cell_counts": np.array([100.0, 50.0]),
        "cell_area_m2": 0.003,
        "efficiency_ratio": 0.3,
        "temperature_factor_ratio": 0.95,
        "packing_loss_ratio": 0.02,
        "harness_loss_ratio": 0.01,
        "age_factor_ratio": 1.0,
        "cosines": np.array([[1.0, 0.0], [0.5, 0.5], [0.0, 1.0]]),
        "lit_ratio": np.array([1.0, 1.0, 0.0]),
    }
    plain = arr.array_power_w(**kwargs)  # type: ignore[arg-type]
    assert np.array_equal(arr.array_power_w(**kwargs, distance_factor=1.0), plain)  # type: ignore[arg-type]
    scaled = arr.array_power_w(**kwargs, distance_factor=np.array([1.1, 0.9, 1.0]))  # type: ignore[arg-type]
    assert np.allclose(scaled, plain * np.array([1.1, 0.9, 1.0]), rtol=1e-15)


def test_the_equation_is_registered() -> None:
    assert "ENV-IRRADIANCE" in EQUATIONS
    assert "ENV-IRRADIANCE" in {
        e for c in mc.BY_ID["power.array_irradiance"].choices for e in c.equations
    }


# ---- the file -----------------------------------------------------------------------------------


def _scenario(**fields: object) -> Scenario:
    base: dict[str, object] = {
        "name": "s",
        "environment_source": "elements",
        "orbit": "leo",
        "start_utc": "2026-01-03T00:00:00Z",
        "duration_s": 3600.0,
        "step_s": 60.0,
        "default_mode": "nominal",
    }
    return Scenario(**{**base, **fields})  # type: ignore[arg-type]


def test_the_field_defaults_to_constant_and_is_left_out_of_the_file_at_the_default() -> None:
    assert _scenario().irradiance_model == "constant"
    assert "irradiance_model" not in model_to_data(_scenario())
    assert model_to_data(_scenario(irradiance_model="seasonal"))["irradiance_model"] == "seasonal"


def test_an_unknown_value_is_refused() -> None:
    with pytest.raises(ValueError, match="irradiance_model"):
        _scenario(irradiance_model="monthly")


def test_the_choice_needs_the_feature_declared(tmp_path: Path) -> None:
    import shutil

    root = tmp_path / "p"
    shutil.copytree(EXAMPLE, root)
    path = sorted((root / "scenarios").glob("*.yaml"))[0]
    text = path.read_text(encoding="utf-8")
    path.write_text(
        text.replace("shadow_model:", "irradiance_model: seasonal\nshadow_model:", 1),
        encoding="utf-8",
    )
    codes = [p.code for p in load_project(root).problems]
    assert codes.count("FEATURE_NOT_DECLARED") == 1


# ---- the run ------------------------------------------------------------------------------------


def _project(model: str, start: str) -> Project:
    project = load_project(EXAMPLE).project
    assert project is not None
    sid = sorted(project.scenarios)[0]
    scenario = project.scenarios[sid].model_copy(
        update={"irradiance_model": model, "start_utc": start}
    )
    return replace(project, scenarios={**project.scenarios, sid: scenario})


def _generation(model: str, start: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    project = _project(model, start)
    run = run_scenario(project, sorted(project.scenarios)[0])
    result = time_domain_budget(project, run, keep_detail=True)
    assert result.detail is not None and result.detail.base_generation_w is not None
    assert run.env.sun_distance_m is not None
    return result.detail.base_generation_w, result.detail.redges_s, run.env.sun_distance_m


def test_the_default_and_an_explicit_constant_are_the_same_run() -> None:
    project = load_project(EXAMPLE).project
    assert project is not None
    sid = sorted(project.scenarios)[0]
    assert project.scenarios[sid].irradiance_model == "constant"
    explicit = replace(
        project,
        scenarios={
            **project.scenarios,
            sid: project.scenarios[sid].model_copy(update={"irradiance_model": "constant"}),
        },
    )
    a = time_domain_budget(project, run_scenario(project, sid), keep_detail=True)
    b = time_domain_budget(explicit, run_scenario(explicit, sid), keep_detail=True)
    assert a.detail is not None and b.detail is not None
    assert np.array_equal(a.detail.base_generation_w, b.detail.base_generation_w)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("start", "expected"),
    [("2026-01-03T00:00:00Z", 1.034), ("2026-07-06T00:00:00Z", 0.967)],
)
def test_seasonal_energy_is_the_constant_one_times_the_distance_factor(
    start: str, expected: float
) -> None:
    """The refined steps differ between the two runs (the battery edges move with the energy), so
    the generated energy over the scenario is compared, not the steps."""
    constant, edges_c, distance = _generation("constant", start)
    seasonal, edges_s, _ = _generation("seasonal", start)
    energy_c = float(np.sum(constant * np.diff(edges_c)))
    energy_s = float(np.sum(seasonal * np.diff(edges_s)))
    assert energy_c > 0.0
    assert energy_s / energy_c == pytest.approx((AU / distance.mean()) ** 2, rel=2e-4)
    assert energy_s / energy_c == pytest.approx(expected, abs=0.002)


def test_the_run_says_which_irradiance_model_and_the_factor() -> None:
    project = _project("seasonal", "2026-01-03T00:00:00Z")
    run = run_scenario(project, sorted(project.scenarios)[0])
    rows = dict(run_parameters(run))
    assert rows["Irradiance model"].startswith("seasonal")
    assert "1.03" in rows["Irradiance model"]  # the mean factor over the scenario, near perihelion
    constant = _project("constant", "2026-01-03T00:00:00Z")
    rows = dict(run_parameters(run_scenario(constant, sorted(constant.scenarios)[0])))
    assert rows["Irradiance model"] == "constant"


# ---- the registry -------------------------------------------------------------------------------


def test_the_registry_offers_the_two_models() -> None:
    entry = mc.BY_ID["power.array_irradiance"]
    assert entry.scope == "scenario" and entry.field == "irradiance_model"
    assert entry.default == "constant"
    assert {c.id for c in entry.choices} == {"constant", "seasonal"}


# ---- Explain -----------------------------------------------------------------------------------


def test_explain_agrees_with_the_tables_and_names_the_factor_step() -> None:
    from budget_core.explain import Explainer, explainable_tables

    project = _project("seasonal", "2026-01-03T00:00:00Z")
    explainer = Explainer(project, scenario=sorted(project.scenarios)[0], load_basis="nominal")
    seen_step = False
    checked = 0
    for table_id, _title in explainable_tables(project):
        if not table_id.startswith("timeline:"):
            continue
        case = table_id.rsplit(":", 1)[1]
        if table_id.startswith("timeline:balance:") and case not in {
            c.case for c in explainer.timeline_result().cases
        }:
            continue
        table = explainer.table(table_id)
        for row in table.rows:
            key = tuple(str(row[i]) for i in table.explain_key)
            for column, value in zip(table.columns, row, strict=True):
                explanation = explainer.explain(table_id, key, column.header)
                assert explanation.result.value == value, (table_id, key, column.header)
                checked += 1
                seen_step = seen_step or any(
                    "Earth-Sun distance" in step.label for step in explanation.steps
                )
    assert checked > 60 and seen_step
