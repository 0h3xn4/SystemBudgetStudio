# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""A state vector as an orbit (2.2.0, D-229): the frame from J2000 to TEME, and the mean elements
whose SGP4 state at the epoch is the given state."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from budget_core.environment import geometry as geo
from budget_core.environment.constants import EARTH_MODELS
from budget_core.environment.elements import satrec_from_values
from budget_core.orbit_state import (
    StateConversionError,
    j2000_to_teme_matrix,
    mean_elements_from_state,
    osculating_elements,
    teme_state,
)

RE = EARTH_MODELS["wgs84"].radius_m
EPOCH = datetime(2026, 6, 1, tzinfo=UTC)

# astropy 8.0.2: the TEME position of the J2000 (GCRS) vector below at each time
_VECTOR = np.array([7000e3, 1000e3, 2000e3])
_ASTROPY_TEME = {
    datetime(2000, 1, 1, 12, tzinfo=UTC): [7000053.9, 1000055.936, 1999783.37],
    datetime(2010, 6, 1, tzinfo=UTC): [6995562.928, 1016278.743, 2007305.866],
    datetime(2026, 6, 1, tzinfo=UTC): [6988790.088, 1041240.744, 2018076.021],
    datetime(2040, 3, 20, 6, 30, tzinfo=UTC): [6982916.479, 1062841.118, 2027127.576],
}


# ---- the frame ------------------------------------------------------------------------------


@pytest.mark.parametrize("moment", sorted(_ASTROPY_TEME))
def test_the_frame_agrees_with_astropy_to_a_few_metres(moment: datetime) -> None:
    got = j2000_to_teme_matrix(moment) @ _VECTOR
    assert np.linalg.norm(got - np.array(_ASTROPY_TEME[moment])) < 5.0


@pytest.mark.parametrize("moment", sorted(_ASTROPY_TEME))
def test_the_frame_is_a_rotation(moment: datetime) -> None:
    m = j2000_to_teme_matrix(moment)
    assert np.allclose(m @ m.T, np.eye(3), atol=1e-14)
    assert np.linalg.det(m) == pytest.approx(1.0)


def test_the_frame_is_the_identity_at_j2000_to_the_precession_of_a_day() -> None:
    # at 2000-01-01 12:00 the rotation is the nutation and equinox term only: arcseconds
    m = j2000_to_teme_matrix(datetime(2000, 1, 1, 12, tzinfo=UTC))
    assert np.linalg.norm(m - np.eye(3)) < 2e-4


def test_teme_is_left_alone_and_the_frame_is_checked() -> None:
    r, v = np.array([7e6, 0.0, 0.0]), np.array([0.0, 7.5e3, 0.0])
    got_r, got_v = teme_state("teme", EPOCH, r, v)
    assert np.array_equal(got_r, r) and np.array_equal(got_v, v)
    with pytest.raises(StateConversionError, match="frame"):
        teme_state("ecef", EPOCH, r, v)


# ---- the mean elements ----------------------------------------------------------------------

CASES = {
    "leo_sun_synchronous": (RE + 600e3, 0.0011, 97.8, 40.0, 90.0, 10.0),
    "elliptical": (RE + 1500e3, 0.1, 63.4, 200.0, 270.0, 123.0),
    "near_circular": (RE + 800e3, 1e-5, 51.6, 10.0, 0.0, 300.0),
    "retrograde": (RE + 500e3, 0.002, 130.0, 300.0, 45.0, 200.0),
    "nearly_equatorial": (RE + 550e3, 0.0005, 0.02, 0.0, 30.0, 70.0),
    "geostationary_like": (42164e3, 0.0003, 0.05, 80.0, 10.0, 350.0),
}


def _state_of_elements(
    a: float, e: float, i: float, raan: float, argp: float, mean: float
) -> tuple[np.ndarray, np.ndarray]:
    jd, fr = geo.julian_date_parts(EPOCH)
    sat = satrec_from_values(
        jd,
        fr,
        a,
        e,
        math.radians(i),
        math.radians(raan),
        math.radians(argp),
        math.radians(mean),
        "wgs84",
    )
    err, r, v = sat.sgp4(jd, fr)
    assert err == 0
    return np.array(r) * 1000.0, np.array(v) * 1000.0


@pytest.mark.parametrize("name", sorted(CASES))
def test_the_elements_that_made_a_state_are_found_again(name: str) -> None:
    a, e, i, raan, argp, mean = CASES[name]
    r, v = _state_of_elements(a, e, i, raan, argp, mean)
    fit = mean_elements_from_state(EPOCH, "teme", r, v)
    assert fit.semi_major_axis_m == pytest.approx(a, rel=1e-9)
    assert fit.eccentricity_ratio == pytest.approx(e, abs=1e-9)
    assert fit.inclination_deg == pytest.approx(i, abs=1e-6)
    # what is determined for a circular or an equatorial orbit is the sum of the angles
    total = (fit.raan_deg + fit.arg_perigee_deg + fit.mean_anomaly_deg) % 360.0
    assert total == pytest.approx((raan + argp + mean) % 360.0, abs=1e-6)
    if e > 1e-3 and i > 1.0:
        assert fit.raan_deg == pytest.approx(raan, abs=1e-6)
        assert fit.arg_perigee_deg == pytest.approx(argp, abs=1e-5)
    assert fit.position_residual_m < 1e-3 and fit.velocity_residual_m_s < 1e-6
    assert fit.iterations < 20


@pytest.mark.parametrize("name", sorted(CASES))
def test_the_state_is_reproduced_by_sgp4_at_the_epoch(name: str) -> None:
    a, e, i, raan, argp, mean = CASES[name]
    r, v = _state_of_elements(a, e, i, raan, argp, mean)
    # a state in J2000 is the same state: it comes out as the same orbit in the end
    matrix = j2000_to_teme_matrix(EPOCH)
    fit = mean_elements_from_state(EPOCH, "j2000", matrix.T @ r, matrix.T @ v)
    jd, fr = geo.julian_date_parts(EPOCH)
    sat = satrec_from_values(
        jd,
        fr,
        fit.semi_major_axis_m,
        fit.eccentricity_ratio,
        math.radians(fit.inclination_deg),
        math.radians(fit.raan_deg),
        math.radians(fit.arg_perigee_deg),
        math.radians(fit.mean_anomaly_deg),
        "wgs84",
    )
    err, pos, vel = sat.sgp4(jd, fr)
    assert err == 0
    assert np.linalg.norm(np.array(pos) * 1000.0 - r) < 1e-3
    assert np.linalg.norm(np.array(vel) * 1000.0 - v) < 1e-6


def test_the_orbit_after_the_epoch_is_the_one_of_the_original_elements() -> None:
    a, e, i, raan, argp, mean = CASES["leo_sun_synchronous"]
    r, v = _state_of_elements(a, e, i, raan, argp, mean)
    fit = mean_elements_from_state(EPOCH, "teme", r, v)
    jd, fr = geo.julian_date_parts(EPOCH)

    def sat_of(*values: float):  # type: ignore[no-untyped-def]
        return satrec_from_values(jd, fr, *values, "wgs84")

    original = sat_of(
        a, e, math.radians(i), math.radians(raan), math.radians(argp), math.radians(mean)
    )
    fitted = sat_of(
        fit.semi_major_axis_m,
        fit.eccentricity_ratio,
        math.radians(fit.inclination_deg),
        math.radians(fit.raan_deg),
        math.radians(fit.arg_perigee_deg),
        math.radians(fit.mean_anomaly_deg),
    )
    _, p1, _ = original.sgp4(jd, fr + 1.0)
    _, p2, _ = fitted.sgp4(jd, fr + 1.0)
    assert np.linalg.norm((np.array(p1) - np.array(p2)) * 1000.0) < 0.01  # metres, a day later


def test_the_osculating_orbit_is_reported_next_to_the_mean_one() -> None:
    a, e, i, raan, argp, mean = CASES["leo_sun_synchronous"]
    r, v = _state_of_elements(a, e, i, raan, argp, mean)
    fit = mean_elements_from_state(EPOCH, "teme", r, v)
    osc_a, osc_e, osc_i = osculating_elements(r, v, EARTH_MODELS["wgs84"].mu_m3s2)
    assert fit.osculating_semi_major_axis_m == pytest.approx(osc_a)
    assert fit.osculating_eccentricity_ratio == pytest.approx(osc_e)
    # J2 short-period terms: the mean and osculating semi-major axes differ by kilometres
    assert 1e2 < abs(fit.semi_major_axis_m - osc_a) < 2e4
    assert osc_i == pytest.approx(i, abs=0.1)


# ---- what is refused ------------------------------------------------------------------------


def test_a_state_above_the_escape_speed_is_refused() -> None:
    with pytest.raises(StateConversionError, match="bound"):
        mean_elements_from_state(
            EPOCH, "teme", np.array([7e6, 0.0, 0.0]), np.array([0.0, 12e3, 0.0])
        )


def test_a_perigee_below_the_surface_is_refused() -> None:
    with pytest.raises(StateConversionError, match="surface"):
        mean_elements_from_state(
            EPOCH, "teme", np.array([RE + 400e3, 0.0, 0.0]), np.array([0.0, 4e3, 0.0])
        )


def test_a_position_inside_the_earth_is_refused() -> None:
    with pytest.raises(StateConversionError, match="inside"):
        mean_elements_from_state(
            EPOCH, "teme", np.array([3e6, 0.0, 0.0]), np.array([0.0, 7e3, 0.0])
        )


@pytest.mark.parametrize(
    "bad", [np.array([np.nan, 0.0, 0.0]), np.array([1.0, 2.0]), np.array([np.inf, 0.0, 0.0])]
)
def test_a_state_that_is_not_three_finite_numbers_is_refused(bad: np.ndarray) -> None:
    with pytest.raises(StateConversionError, match="three finite"):
        mean_elements_from_state(EPOCH, "teme", bad, np.array([0.0, 7.5e3, 0.0]))


def test_the_message_does_not_carry_the_values() -> None:
    with pytest.raises(StateConversionError) as caught:
        mean_elements_from_state(
            EPOCH, "teme", np.array([7.123e6, 0.0, 0.0]), np.array([0.0, 12.345e3, 0.0])
        )
    assert "7.123" not in str(caught.value) and "12.345" not in str(caught.value)


def test_the_conversion_is_deterministic() -> None:
    a, e, i, raan, argp, mean = CASES["elliptical"]
    r, v = _state_of_elements(a, e, i, raan, argp, mean)
    assert mean_elements_from_state(EPOCH, "teme", r, v) == mean_elements_from_state(
        EPOCH, "teme", r, v
    )


def test_a_later_epoch_works_too() -> None:
    a, e, i, raan, argp, mean = CASES["leo_sun_synchronous"]
    later = EPOCH + timedelta(days=400, hours=3)
    jd, fr = geo.julian_date_parts(later)
    sat = satrec_from_values(
        jd,
        fr,
        a,
        e,
        math.radians(i),
        math.radians(raan),
        math.radians(argp),
        math.radians(mean),
        "wgs84",
    )
    _, r, v = sat.sgp4(jd, fr)
    fit = mean_elements_from_state(later, "teme", np.array(r) * 1000.0, np.array(v) * 1000.0)
    assert fit.semi_major_axis_m == pytest.approx(a, rel=1e-9)


# ---- as an orbit of a scenario --------------------------------------------------------------


def _project_with_state(tmp_path):  # type: ignore[no-untyped-def]
    """The 250 kg example whose orbit is replaced by the state of its own elements at the epoch."""
    import shutil
    from pathlib import Path

    from budget_core.io.project_loader import load_project

    examples = Path(__file__).resolve().parents[2] / "examples"
    elements_root = tmp_path / "elements"
    state_root = tmp_path / "state"
    shutil.copytree(examples / "microsat_250kg_eps", elements_root)
    shutil.copytree(examples / "microsat_250kg_eps", state_root)
    loaded = load_project(elements_root)
    orbit = next(iter(loaded.project.orbits.values()))  # type: ignore[union-attr]
    el = orbit.elements
    jd, fr = geo.julian_date_parts(datetime.fromisoformat(el.epoch_utc.replace("Z", "+00:00")))
    sat = satrec_from_values(
        jd,
        fr,
        el.semi_major_axis_m,
        el.eccentricity_ratio,
        math.radians(el.inclination_deg),
        math.radians(el.raan_deg),
        math.radians(el.arg_perigee_deg),
        math.radians(el.mean_anomaly_deg),
        "wgs84",
    )
    _, r, v = sat.sgp4(jd, fr)
    path = next((state_root / "orbits").glob("*.yaml"))
    path.write_text(
        "schema_version: 3\nkind: orbit\nname: From a state\nstate:\n"
        f"  epoch_utc: '{el.epoch_utc}'\n  frame: teme\n"
        f"  position_m: [{r[0] * 1000.0!r}, {r[1] * 1000.0!r}, {r[2] * 1000.0!r}]\n"
        f"  velocity_m_s: [{v[0] * 1000.0!r}, {v[1] * 1000.0!r}, {v[2] * 1000.0!r}]\n",
        encoding="utf-8",
        newline="\n",
    )
    return elements_root, state_root


def test_a_scenario_on_a_state_gives_the_results_of_the_elements(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from budget_core.io.project_loader import load_project
    from budget_core.scenario.run import run_scenario

    elements_root, state_root = _project_with_state(tmp_path)
    runs = []
    for root in (elements_root, state_root):
        loaded = load_project(root)
        assert loaded.project is not None, [
            p.message for p in loaded.problems if p.severity.value == "error"
        ]
        assert not [p for p in loaded.problems if p.severity.value == "error"]
        runs.append(run_scenario(loaded.project, sorted(loaded.project.scenarios)[0]))
    a, b = runs
    assert len(a.env.eclipses) == len(b.env.eclipses) > 5
    for ea, eb in zip(a.env.eclipses, b.env.eclipses, strict=True):
        assert abs(ea.start_s - eb.start_s) < 0.01 and abs(ea.end_s - eb.end_s) < 0.01
    assert np.max(np.abs(a.env.position_m - b.env.position_m)) < 0.01  # metres, a whole day


def test_exactly_one_source_of_an_orbit(tmp_path) -> None:  # type: ignore[no-untyped-def]
    import pytest as _pytest
    from pydantic import ValidationError

    from budget_core.model import Elements, Orbit, StateVector

    state = StateVector(
        epoch_utc="2026-06-01T00:00:00Z",
        frame="j2000",
        position_m=[7e6, 0.0, 0.0],
        velocity_m_s=[0.0, 7.5e3, 0.0],
    )
    elements = Elements(
        epoch_utc="2026-06-01T00:00:00Z",
        semi_major_axis_m=7e6,
        eccentricity_ratio=0.0,
        inclination_deg=10.0,
        raan_deg=0.0,
        arg_perigee_deg=0.0,
        mean_anomaly_deg=0.0,
    )
    assert Orbit(name="s", state=state).state is not None
    with _pytest.raises(ValidationError):
        Orbit(name="both", state=state, elements=elements)
    with _pytest.raises(ValidationError):
        Orbit(name="none")


@pytest.mark.parametrize(
    "bad",
    [
        {"frame": "ecef"},
        {"position_m": [1.0, 2.0]},
        {"position_m": [1e3, 0.0, 0.0]},  # inside the Earth: outside the supported range
        {"velocity_m_s": [0.0, 0.0, 0.0]},
        {"velocity_m_s": [0.0, 3e4, 0.0]},
        {"position_m": [float("nan"), 0.0, 7e6]},
    ],
)
def test_a_state_block_that_is_not_valid_is_refused(bad: dict) -> None:
    from pydantic import ValidationError

    from budget_core.model import StateVector

    base = {
        "epoch_utc": "2026-06-01T00:00:00Z",
        "frame": "teme",
        "position_m": [7e6, 0.0, 0.0],
        "velocity_m_s": [0.0, 7.5e3, 0.0],
    }
    with pytest.raises(ValidationError):
        StateVector(**{**base, **bad})


def test_the_frame_is_required() -> None:
    from pydantic import ValidationError

    from budget_core.model import StateVector

    with pytest.raises(ValidationError):
        StateVector(  # type: ignore[call-arg]
            epoch_utc="2026-06-01T00:00:00Z", position_m=[7e6, 0, 0], velocity_m_s=[0, 7.5e3, 0]
        )
