"""D-250: the Sun on the faces of a nadir-pointing spacecraft, by beta angle.

Three kinds of check: closed forms (beta 90 degrees, beta 0 and the textbook eclipse), the same
integral by brute-force sampling, and the orbit the tool itself propagates (SGP4, its own eclipse
finder, the Sun of its own model) in the local-vertical frame."""

from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from budget_core.environment.constants import EARTH_MODELS
from budget_core.io.project_loader import load_project
from budget_core.model import Project
from budget_core.scenario.run import run_scenario
from budget_core.thermal.beta import (
    eclipse_half_angle_rad,
    face_exposure,
    peak_instant,
    sun_vector_lvlh,
    sunlit_fraction,
)

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
RE = EARTH_MODELS["wgs84"].radius_m
R700 = RE + 700e3
FACES = {
    "+x": (1.0, 0.0, 0.0),
    "-x": (-1.0, 0.0, 0.0),
    "+y": (0.0, 1.0, 0.0),
    "-y": (0.0, -1.0, 0.0),
    "+z": (0.0, 0.0, 1.0),
    "-z": (0.0, 0.0, -1.0),
}


# ---- closed forms ------------------------------------------------------------------------------


def test_with_the_sun_along_the_orbit_normal_one_face_gets_it_all_and_there_is_no_eclipse() -> None:
    for name, normal in FACES.items():
        got = face_exposure(normal, 90.0, RE, R700)
        assert got.sunlit_fraction == 1.0
        # the Sun is along +h, which is -y of the local-vertical frame
        assert got.average == pytest.approx(1.0 if name == "-y" else 0.0, abs=1e-12)
        assert got.peak == pytest.approx(1.0 if name == "-y" else 0.0, abs=1e-12)


def test_the_eclipse_at_beta_zero_is_the_textbook_one() -> None:
    assert sunlit_fraction(0.0, RE, R700) == pytest.approx(1.0 - math.asin(RE / R700) / math.pi)
    assert sunlit_fraction(0.0, RE, R700) == pytest.approx(0.6430, abs=5e-4)  # 35.7 % in eclipse
    assert eclipse_half_angle_rad(0.0, RE, R700) == pytest.approx(math.asin(RE / R700))


def test_the_eclipse_ends_at_the_critical_beta_angle() -> None:
    critical = math.degrees(math.asin(RE / R700))
    assert sunlit_fraction(critical - 0.01, RE, R700) < 1.0
    assert sunlit_fraction(critical + 0.01, RE, R700) == 1.0
    assert sunlit_fraction(-critical - 0.01, RE, R700) == 1.0


def test_faces_along_the_flight_direction_get_the_same_and_the_beta_sign_swaps_y() -> None:
    a, b = face_exposure(FACES["+x"], 20.0, RE, R700), face_exposure(FACES["-x"], 20.0, RE, R700)
    assert a.average == pytest.approx(b.average, rel=1e-12)
    for beta in (15.0, 40.0, 75.0):
        plus = face_exposure(FACES["+y"], beta, RE, R700).average
        minus = face_exposure(FACES["-y"], -beta, RE, R700).average
        assert plus == pytest.approx(minus, rel=1e-12)
    assert face_exposure(FACES["+y"], 30.0, RE, R700).average == 0.0  # the Sun is on the -y side


def test_the_zenith_face_at_beta_zero_has_a_known_value() -> None:
    # beta 0: sun . z = -cos(u), lit for |u| < pi - phi ... the average of the positive part of
    # -cos u over the part of the orbit outside the shadow, computed by hand:
    phi = math.asin(RE / R700)
    # lit arc from pi + phi to 3 pi - phi; -n_z... the zenith face has n = (0, 0, -1): n . s = cos u
    # positive for u in (-pi/2, pi/2) which is inside the sunlit arc: integral = 2
    assert face_exposure(FACES["-z"], 0.0, RE, R700).average == pytest.approx(2.0 / (2 * math.pi))
    assert phi > 0.0


def test_the_sun_vector_is_a_unit_vector() -> None:
    for beta in (-80.0, 0.0, 33.0, 90.0):
        for u in (0.0, 1.0, 3.0, 5.5):
            assert np.linalg.norm(sun_vector_lvlh(beta, u)) == pytest.approx(1.0)


def test_an_orbit_that_is_not_above_the_earth_or_a_beta_out_of_range_is_refused() -> None:
    with pytest.raises(ValueError):
        sunlit_fraction(0.0, RE, RE)
    with pytest.raises(ValueError):
        sunlit_fraction(95.0, RE, R700)


# ---- the same integral by brute-force sampling -------------------------------------------------


def _sampled(normal: tuple[float, ...], beta: float, samples: int = 400_000) -> tuple[float, float]:
    u = (np.arange(samples) + 0.5) * (2.0 * math.pi / samples)
    b = math.radians(beta)
    s = np.stack(
        [-math.cos(b) * np.sin(u), -math.sin(b) * np.ones_like(u), -math.cos(b) * np.cos(u)]
    )
    rs = math.cos(b) * np.cos(u)  # (position unit vector) . (Sun)
    k = RE / R700
    shadow = (rs < 0.0) & ((1.0 - rs**2) < k * k)
    value = np.maximum(0.0, np.array(normal) @ s) * (~shadow)
    return float(value.mean()), float(value.max())


@pytest.mark.parametrize("beta", [-85.0, -64.0, -30.0, 0.0, 12.5, 45.0, 63.9, 64.8, 78.0, 90.0])
@pytest.mark.parametrize(
    "normal",
    [
        FACES["+x"],
        FACES["-y"],
        FACES["+z"],
        FACES["-z"],
        (0.6, -0.8, 0.0),
        (0.0, 0.6, -0.8),
        (1 / math.sqrt(3),) * 3,
    ],
)
def test_the_closed_form_agrees_with_sampling(normal: tuple[float, ...], beta: float) -> None:
    got = face_exposure(normal, beta, RE, R700)
    average, peak = _sampled(normal, beta)
    assert got.average == pytest.approx(average, abs=2e-5)
    assert got.peak == pytest.approx(peak, abs=2e-5)


def test_the_peak_instant_is_the_largest_total_and_each_exposure_is_that_of_its_face() -> None:
    normals = [FACES["+x"], FACES["-z"], (0.0, -0.6, -0.8)]
    weights = [0.3, 0.5, 0.2]
    for beta in (0.0, 30.0, 60.0, 80.0):
        got = peak_instant(normals, weights, beta, RE, R700)
        u = np.linspace(0.0, 2.0 * math.pi, 20000)
        totals = []
        for ui in u:
            s = sun_vector_lvlh(beta, float(ui))
            rs = math.cos(math.radians(beta)) * math.cos(ui)
            k = RE / R700
            if rs < 0.0 and (1.0 - rs**2) < k * k:
                totals.append(0.0)
                continue
            totals.append(
                sum(
                    w * max(0.0, float(np.dot(n, s))) for n, w in zip(normals, weights, strict=True)
                )
            )
        assert got.total >= max(totals) - 1e-9
        assert got.total == pytest.approx(max(totals), abs=1e-5)
        s = sun_vector_lvlh(beta, got.u_rad)
        for n, e in zip(normals, got.exposures, strict=True):
            assert e == pytest.approx(max(0.0, float(np.dot(n, s))))


# ---- the orbit the tool propagates -------------------------------------------------------------


def _project_with_raan(base: Project, raan_deg: float) -> Project:
    orbit_id = next(iter(base.orbits))
    orbit = base.orbits[orbit_id]
    assert orbit.elements is not None
    elements = orbit.elements.model_copy(update={"raan_deg": raan_deg})
    return replace(
        base, orbits={**base.orbits, orbit_id: orbit.model_copy(update={"elements": elements})}
    )


@pytest.mark.parametrize("raan", [100.0, 160.0, 280.0, 340.0])
def test_the_average_agrees_with_the_orbit_the_tool_propagates(raan: float) -> None:
    loaded = load_project(EXAMPLES / "microsat_250kg_eps")
    assert loaded.project is not None
    env = run_scenario(_project_with_raan(loaded.project, raan), "one_day").env
    times = np.asarray(env.grid.times_s)
    r, v, sun = (np.asarray(a) for a in (env.position_m, env.velocity_m_s, env.sun_direction))
    radius = np.linalg.norm(r, axis=1)
    mean_radius = float(radius.mean())
    period = 2.0 * math.pi * math.sqrt(mean_radius**3 / EARTH_MODELS["wgs84"].mu_m3s2)
    window = slice(100, 100 + int(period / env.grid.step_s))
    r_hat = r[window] / radius[window, None]
    h_hat = np.cross(r[window], v[window])
    h_hat /= np.linalg.norm(h_hat, axis=1)[:, None]
    x_axis, y_axis, z_axis = np.cross(h_hat, r_hat), -h_hat, -r_hat  # velocity, -normal, nadir
    sun_local = np.stack([(sun[window] * a).sum(axis=1) for a in (x_axis, y_axis, z_axis)], axis=1)
    lit = np.ones(sun_local.shape[0], dtype=bool)
    for eclipse in env.eclipses:  # the tool's own eclipse finder
        lit &= ~((times[window] >= eclipse.start_s) & (times[window] < eclipse.end_s))
    beta = float(np.degrees(np.arcsin((sun[window] * h_hat).sum(axis=1))).mean())
    assert lit.mean() == pytest.approx(sunlit_fraction(beta, RE, mean_radius), abs=0.01)
    for normal in FACES.values():
        propagated = float((np.maximum(0.0, sun_local @ np.array(normal)) * lit).mean())
        assert face_exposure(normal, beta, RE, mean_radius).average == pytest.approx(
            propagated, abs=0.004
        )
