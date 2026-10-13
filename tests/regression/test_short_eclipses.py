"""Eclipses and umbras shorter than the 20 s detection grid are found (audit DV-E4, D-146).

A sun-synchronous orbit at 500 km (inclination 97.4 degrees, eccentricity 0.001) whose ascending
node is tuned to the edge of the shadow season crosses the shadow for a few seconds only. The
numbers below come from a search over the right ascension of the node; the truth is the sampled
sunlight ratio on a 1 s grid, which cannot miss a shadow of 3 s. The start of the scenario is
moved in steps so that the fixed 20 s detection grid meets the shadow at every phase."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from budget_core.environment import geometry as geo
from budget_core.environment.data import EnvironmentData, TimeGrid
from budget_core.environment.elements import LIT, UMBRA, ElementsPropagator
from budget_core.model import Elements, Orbit

EPOCH = datetime(2026, 6, 1, tzinfo=UTC)
OFFSETS_S = range(0, 21, 2)  # start of the scenario after the epoch of the elements


def orbit(raan_deg: float) -> Orbit:
    return Orbit(
        name="o",
        elements=Elements(
            epoch_utc="2026-06-01T00:00:00Z",
            semi_major_axis_m=6878137.0,
            eccentricity_ratio=0.001,
            inclination_deg=97.4,
            raan_deg=raan_deg,
            arg_perigee_deg=90.0,
            mean_anomaly_deg=0.0,
        ),
    )


def environment(raan_deg: float, model: str, offset_s: int, step_s: float = 1.0) -> EnvironmentData:
    grid = TimeGrid(EPOCH + timedelta(seconds=offset_s), 5800.0, step_s)
    return ElementsPropagator(orbit(raan_deg)).compute(grid, [], model)


# (shadow model, node, what the 1 s grid shows)
SHORT_ECLIPSE = [("conical", 321.959, 12.0), ("cylindrical", 321.594, 8.0)]


@pytest.mark.parametrize(("model", "raan", "seconds"), SHORT_ECLIPSE)
@pytest.mark.parametrize("offset", OFFSETS_S)
def test_a_short_eclipse_is_found_at_every_phase_of_the_detection_grid(
    model: str, raan: float, seconds: float, offset: int
) -> None:
    env = environment(raan, model, offset)
    truth = int(np.count_nonzero(env.sunlight_ratio < LIT))
    assert truth == seconds
    assert len(env.eclipses) == 1
    eclipse = env.eclipses[0]
    assert eclipse.duration_s == pytest.approx(truth, abs=1.0)  # the 1 s grid counts to a second
    assert eclipse.duration_s < 20.0
    middle = 0.5 * (eclipse.start_s + eclipse.end_s)
    index = int(round(middle))
    assert env.sunlight_ratio[index] < LIT  # the interval lies where the shadow is


@pytest.mark.parametrize("offset", [0, 5, 10, 15])
def test_a_short_umbra_inside_a_long_penumbra_is_found(offset: int) -> None:
    env = environment(321.2386, "conical", offset)
    truth = int(np.count_nonzero(env.sunlight_ratio <= UMBRA))
    assert 0 < truth < 20
    assert len(env.umbras) == 1
    umbra = env.umbras[0]
    assert umbra.duration_s == pytest.approx(truth, abs=1.0)
    (eclipse,) = env.eclipses
    assert eclipse.start_s < umbra.start_s < umbra.end_s < eclipse.end_s


@pytest.mark.parametrize("model", ["conical", "cylindrical"])
@pytest.mark.parametrize("offset", [0, 7, 14])
def test_no_shadow_is_not_invented(model: str, offset: int) -> None:
    env = environment(322.5, model, offset)
    assert not np.any(env.sunlight_ratio < LIT)
    assert env.eclipses == () and env.umbras == ()


@pytest.mark.parametrize("model", ["conical", "cylindrical"])
def test_the_scenario_step_does_not_change_the_eclipses(model: str) -> None:
    fine = environment(321.959 if model == "conical" else 321.594, model, 10, 1.0)
    coarse = environment(321.959 if model == "conical" else 321.594, model, 10, 60.0)
    assert fine.eclipses == coarse.eclipses and fine.umbras == coarse.umbras


@pytest.mark.parametrize("model", ["conical", "cylindrical"])
def test_the_shadow_margin_is_positive_exactly_where_the_sun_is_hidden(model: str) -> None:
    rng = np.random.default_rng(7)
    directions = rng.normal(size=(4000, 3))
    directions /= np.linalg.norm(directions, axis=1, keepdims=True)
    radius = (geo.EARTH_RADIUS_M + rng.uniform(300e3, 40000e3, size=4000))[:, None]
    positions = directions * radius
    sun = np.tile(np.array([[1.496e11, 0.0, 0.0]]), (4000, 1))
    margin, umbra_margin = geo.shadow_margins(positions, sun, model)
    ratio = geo.sun_visibility(positions, sun, model)
    away = np.abs(margin) > 1e-6 * (1.0 if model == "conical" else geo.EARTH_RADIUS_M)
    assert np.all((margin[away] > 0.0) == (ratio[away] < 1.0))
    deep = np.abs(umbra_margin) > 1e-6 * (1.0 if model == "conical" else geo.EARTH_RADIUS_M)
    assert np.all((umbra_margin[deep] > 0.0) == (ratio[deep] <= 0.0))
