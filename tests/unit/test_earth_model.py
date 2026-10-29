"""The Earth model of a scenario (D-219, P5b): WGS-84 (the default) or WGS-72 for the gravity
constants of an orbit given as elements and for the Earth sphere of the shadow geometry.

A TLE is propagated on WGS-72 by definition and an imported environment is not computed here, so
the choice does not apply to them. Ground sites are always WGS-84 geodetic coordinates."""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest
from sgp4.earth_gravity import wgs72, wgs84

from budget_core import model_choices as mc
from budget_core.environment import constants
from budget_core.environment import geometry as geo
from budget_core.environment.data import TimeGrid
from budget_core.environment.elements import ElementsPropagator
from budget_core.io.project_loader import load_project, model_to_data
from budget_core.model import Elements, Orbit, Scenario
from budget_core.scenario.run import environment_key, run_parameters, run_scenario

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "examples" / "microsat_250kg_eps"
START = datetime(2026, 3, 20, 14, 46, tzinfo=UTC)

ISS_TLE = (
    "1 25544U 98067A   19343.69339541  .00001764  00000-0  38792-4 0  9991",
    "2 25544  51.6439 211.2001 0007417  17.6667  85.6398 15.50103472202482",
)
TLE_START = datetime(2019, 12, 10, 12, 0, tzinfo=UTC)


def elements_orbit() -> Orbit:
    return Orbit(
        name="t",
        elements=Elements(
            epoch_utc="2026-03-20T14:46:00Z",
            semi_major_axis_m=constants.EARTH_RADIUS.value + 500_000.0,
            eccentricity_ratio=1e-4,
            inclination_deg=97.4,
            raan_deg=40.0,
            arg_perigee_deg=0.0,
            mean_anomaly_deg=0.0,
        ),
    )


# ---- the sets ---------------------------------------------------------------------------------


def test_the_two_sets_are_the_ones_of_the_sgp4_library() -> None:
    assert set(constants.EARTH_MODELS) == {"wgs84", "wgs72"}
    for name, library in (("wgs84", wgs84), ("wgs72", wgs72)):
        model = constants.EARTH_MODELS[name]
        assert model.radius_m == library.radiusearthkm * 1000.0
        assert model.mu_m3s2 == library.mu * 1.0e9
        assert model.source


def test_the_default_set_is_the_constants_the_code_always_used() -> None:
    assert constants.EARTH_MODELS["wgs84"].radius_m == constants.EARTH_RADIUS.value
    assert constants.EARTH_MODELS["wgs84"].mu_m3s2 == constants.EARTH_MU.value
    assert constants.DEFAULT_EARTH_MODEL == "wgs84"


# ---- the shadow geometry reads the radius -----------------------------------------------------


def test_a_point_between_the_two_radii_is_dark_on_wgs84_and_lit_on_wgs72() -> None:
    """The radii differ by 2 m: a point 1 m outside the WGS-72 sphere is inside the WGS-84 one.
    Reference value: the two radii of the SGP4 library."""
    r72, r84 = constants.EARTH_MODELS["wgs72"].radius_m, constants.EARTH_MODELS["wgs84"].radius_m
    sun = np.array([[1.0, 0.0, 0.0]]) * 1.5e11
    point = np.array([[-7.0e6, r72 + 1.0, 0.0]])  # behind the Earth, 1 m outside the WGS-72 radius
    assert r84 > r72 + 1.0
    for model in ("cylindrical", "conical"):
        dark84 = geo.sun_visibility(point, sun, model, radius_m=r84)[0]
        lit72 = geo.sun_visibility(point, sun, model, radius_m=r72)[0]
        assert dark84 < lit72, model
    assert geo.sun_visibility(point, sun, "cylindrical", radius_m=r72)[0] == 1.0
    assert geo.sun_visibility(point, sun, "cylindrical", radius_m=r84)[0] == 0.0


def test_the_default_radius_is_wgs84() -> None:
    sun = np.array([[1.0, 0.0, 0.0]]) * 1.5e11
    point = np.array([[-7.0e6, 6_378_000.0, 0.0]])
    assert (
        geo.sun_visibility(point, sun, "cylindrical")[0]
        == geo.sun_visibility(point, sun, "cylindrical", radius_m=constants.EARTH_RADIUS.value)[0]
    )
    assert np.array_equal(
        geo.shadow_margins(point, sun, "conical")[0],
        geo.shadow_margins(point, sun, "conical", radius_m=constants.EARTH_RADIUS.value)[0],
    )


# ---- the propagation --------------------------------------------------------------------------


def test_the_default_and_an_explicit_wgs84_are_the_same_environment() -> None:
    grid = TimeGrid(START, 6000.0, 60.0)
    a = ElementsPropagator(elements_orbit()).compute(grid, [], "conical")
    b = ElementsPropagator(elements_orbit(), "wgs84").compute(grid, [], "conical")
    assert np.array_equal(a.position_m, b.position_m)
    assert np.array_equal(a.sunlight_ratio, b.sunlight_ratio)
    assert a.eclipses == b.eclipses


def test_wgs72_changes_the_orbit_by_a_known_small_amount() -> None:
    """The mean motion comes from mu (8e-7 of it differs) and SGP4 uses the set's radius and J2;
    over one orbit the positions differ by metres to a few kilometres, never more."""
    grid = TimeGrid(START, 6000.0, 60.0)
    a = ElementsPropagator(elements_orbit(), "wgs84").compute(grid, [], "cylindrical")
    b = ElementsPropagator(elements_orbit(), "wgs72").compute(grid, [], "cylindrical")
    shift = np.linalg.norm(a.position_m - b.position_m, axis=1)
    assert shift.max() > 1.0  # the choice does something
    assert shift.max() < 5_000.0  # and is small beside the orbit radius
    assert b.earth_model == "wgs72" and a.earth_model == "wgs84"


def test_a_tle_is_propagated_on_wgs72_whatever_the_choice() -> None:
    orbit = Orbit(name="t", tle=ISS_TLE)
    grid = TimeGrid(TLE_START, 3000.0, 60.0)
    a = ElementsPropagator(orbit, "wgs84").compute(grid, [], "cylindrical")
    b = ElementsPropagator(orbit, "wgs72").compute(grid, [], "cylindrical")
    assert np.array_equal(a.position_m, b.position_m)
    assert a.earth_model == b.earth_model == "tle"


# ---- the file ---------------------------------------------------------------------------------


def _scenario(**fields: object) -> Scenario:
    base: dict[str, object] = {
        "name": "s",
        "environment_source": "elements",
        "orbit": "leo",
        "start_utc": "2026-03-20T14:46:00Z",
        "duration_s": 3600.0,
        "step_s": 60.0,
        "default_mode": "nominal",
    }
    return Scenario(**{**base, **fields})  # type: ignore[arg-type]


def test_the_field_defaults_to_wgs84_and_is_left_out_of_the_file_at_the_default() -> None:
    assert _scenario().earth_model == "wgs84"
    assert "earth_model" not in model_to_data(_scenario())
    assert model_to_data(_scenario(earth_model="wgs72"))["earth_model"] == "wgs72"


def test_an_unknown_value_is_refused() -> None:
    with pytest.raises(ValueError, match="earth_model"):
        _scenario(earth_model="wgs66")


def _project_with(tmp_path: Path, scenario_line: str | None, requires: bool) -> Path:
    root = tmp_path / "p"
    shutil.copytree(EXAMPLE, root)
    scenarios = sorted((root / "scenarios").glob("*.yaml"))
    path = scenarios[0]
    text = path.read_text(encoding="utf-8")
    if scenario_line:
        text = text.replace("shadow_model:", f"{scenario_line}\nshadow_model:", 1)
    path.write_text(text, encoding="utf-8")
    if requires:
        project = root / "project.yaml"
        project.write_text(
            project.read_text(encoding="utf-8").rstrip("\n") + "\nrequires:\n  - model_choices\n",
            encoding="utf-8",
        )
    return root


def test_the_feature_is_known(tmp_path: Path) -> None:
    root = _project_with(tmp_path, "earth_model: wgs72", requires=True)
    loaded = load_project(root)
    assert loaded.project is not None
    codes = {p.code for p in loaded.problems}
    assert "FEATURE_UNSUPPORTED" not in codes and "FEATURE_NOT_DECLARED" not in codes


def test_using_the_field_without_declaring_the_feature_is_a_warning(tmp_path: Path) -> None:
    root = _project_with(tmp_path, "earth_model: wgs72", requires=False)
    loaded = load_project(root)
    assert loaded.project is not None
    found = [p for p in loaded.problems if p.code == "FEATURE_NOT_DECLARED"]
    assert len(found) == 1 and found[0].file == "project.yaml"
    assert "model_choices" in found[0].hint


def test_a_default_value_needs_no_declaration(tmp_path: Path) -> None:
    root = _project_with(tmp_path, "earth_model: wgs84", requires=False)
    loaded = load_project(root)
    assert "FEATURE_NOT_DECLARED" not in {p.code for p in loaded.problems}


def test_an_older_scenario_file_reads_unchanged(tmp_path: Path) -> None:
    root = _project_with(tmp_path, None, requires=False)
    path = sorted((root / "scenarios").glob("*.yaml"))[0]
    text = path.read_text(encoding="utf-8")
    assert "schema_version: 4" in text
    path.write_text(text.replace("schema_version: 4", "schema_version: 3", 1), encoding="utf-8")
    loaded = load_project(root)
    assert loaded.project is not None
    assert "FILE_MIGRATED" in {p.code for p in loaded.problems}
    assert all(s.earth_model == "wgs84" for s in loaded.project.scenarios.values())


# ---- a choice that does not apply -------------------------------------------------------------


def test_the_choice_on_a_tle_orbit_is_a_warning(tmp_path: Path) -> None:
    root = _project_with(tmp_path, "earth_model: wgs72", requires=True)
    scenario = sorted((root / "scenarios").glob("*.yaml"))[0]
    orbit_id = None
    for line in scenario.read_text(encoding="utf-8").splitlines():
        if line.startswith("orbit:"):
            orbit_id = line.split(":", 1)[1].strip()
    assert orbit_id
    (root / "orbits" / f"{orbit_id}.yaml").write_text(
        "schema_version: 2\nkind: orbit\nname: ISS\ntle:\n"
        f'  - "{ISS_TLE[0]}"\n  - "{ISS_TLE[1]}"\n',
        encoding="utf-8",
    )
    loaded = load_project(root)
    assert loaded.project is not None
    ignored = [p for p in loaded.problems if p.code == "MODEL_CHOICE_IGNORED"]
    assert len(ignored) == 1
    assert ignored[0].file.startswith("scenarios/") and ignored[0].path == "earth_model"


def test_the_choice_on_elements_is_not_a_warning(tmp_path: Path) -> None:
    root = _project_with(tmp_path, "earth_model: wgs72", requires=True)
    loaded = load_project(root)
    codes = {p.code for p in loaded.problems}
    assert "MODEL_CHOICE_IGNORED" not in codes and "SCENARIO_OPTION_IGNORED" not in codes


# ---- the run ----------------------------------------------------------------------------------


def test_a_run_uses_the_chosen_set_and_says_so(tmp_path: Path) -> None:
    default = load_project(_project_with(tmp_path, None, requires=False)).project
    assert default is not None
    sid = sorted(default.scenarios)[0]
    chosen_root = tmp_path / "q"
    chosen_root.mkdir()
    chosen = load_project(_project_with(chosen_root, "earth_model: wgs72", requires=True)).project
    assert chosen is not None
    a = run_scenario(default, sid)
    b = run_scenario(chosen, sid)
    assert a.env.earth_model == "wgs84" and b.env.earth_model == "wgs72"
    assert not np.array_equal(a.env.position_m, b.env.position_m)
    rows_a, rows_b = dict(run_parameters(a)), dict(run_parameters(b))
    assert rows_a["Earth model"] == "WGS-84" and rows_b["Earth model"] == "WGS-72"
    assert environment_key(default, default.scenarios[sid]) != environment_key(
        chosen, chosen.scenarios[sid]
    )


# ---- the registry -----------------------------------------------------------------------------


def test_the_registry_offers_the_two_sets() -> None:
    entry = mc.BY_ID["environment.earth_model"]
    assert entry.scope == "scenario" and entry.field == "earth_model"
    assert entry.default == "wgs84"
    assert {c.id for c in entry.choices} == {"wgs84", "wgs72"}
    assert "environment.gravity_elements" not in mc.BY_ID  # it is the selectable choice now
    assert mc.BY_ID["environment.gravity_tle"].scope == "fixed"
