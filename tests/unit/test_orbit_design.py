# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""The orbit design calculator (2.2.0, D-226): LTAN and RAAN, the sun-synchronous orbit, the repeat
ground track. The formulas are the first-order J2 relations; each is held against something that
is not the code under test: the SGP4 propagation of the tool, the mean Sun of the Sun model, and
textbook values."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest
from sgp4.api import Satrec

from budget_core.environment import geometry as geo
from budget_core.environment.constants import EARTH_MODELS
from budget_core.environment.elements import build_satrec
from budget_core.model.environment import Elements, Orbit
from budget_core.orbit_design import (
    OrbitDesignError,
    design_sun_synchronous,
    j2_secular_rates,
    mean_solar_time_of_node_h,
    raan_from_ltan_deg,
    repeat_candidates,
    repeat_ground_track,
    sun_synchronous_altitude_m,
    sun_synchronous_inclination_deg,
)
from budget_core.timeutil import format_utc

EPOCH = datetime(2026, 6, 1, 0, 0, 0, tzinfo=UTC)
RE = EARTH_MODELS["wgs84"].radius_m
MEAN_SUN_DEG_PER_DAY = 360.0 / 365.2421897  # the mean Sun's rate in right ascension


def _satrec(a_m: float, e: float, i_deg: float, raan_deg: float, epoch: datetime = EPOCH) -> Satrec:
    elements = Elements(
        epoch_utc=format_utc(epoch),
        semi_major_axis_m=a_m,
        eccentricity_ratio=e,
        inclination_deg=i_deg,
        raan_deg=raan_deg,
        arg_perigee_deg=0.0,
        mean_anomaly_deg=0.0,
    )
    return build_satrec(Orbit(name="t", elements=elements))


def _raan_deg(sat: Satrec, minutes: float) -> float:
    """The node of the osculating orbit at a time after the epoch, from SGP4's position and
    velocity (the angular momentum vector), not from any formula of the module under test."""
    err, r, v = sat.sgp4(sat.jdsatepoch, sat.jdsatepochF + minutes / 1440.0)
    assert err == 0
    h = np.cross(r, v)
    return math.degrees(math.atan2(h[0], -h[1])) % 360.0


def _unwrap(a: float, b: float) -> float:
    return (b - a + 180.0) % 360.0 - 180.0


# ---- the secular rates ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("alt_km", "e", "i"), [(600.0, 0.0, 97.8), (800.0, 0.001, 98.6), (500.0, 0.05, 51.6)]
)
def test_the_secular_rates_agree_with_sgp4(alt_km: float, e: float, i: float) -> None:
    a = RE + alt_km * 1000.0
    sat = _satrec(a, e, i, 100.0)
    rates = j2_secular_rates(a, e, i)
    assert rates.raan_dot_rad_s * 60.0 == pytest.approx(sat.nodedot, rel=3e-3)
    assert rates.arg_perigee_dot_rad_s * 60.0 == pytest.approx(sat.argpdot, rel=5e-3)


def test_the_rates_have_the_textbook_signs() -> None:
    a = RE + 700e3
    assert j2_secular_rates(a, 0.0, 51.6).raan_dot_rad_s < 0.0  # prograde: the node goes west
    assert j2_secular_rates(a, 0.0, 98.0).raan_dot_rad_s > 0.0  # retrograde: east
    assert j2_secular_rates(a, 0.0, 90.0).raan_dot_rad_s == pytest.approx(0.0, abs=1e-15)
    # the argument of perigee does not move at the critical inclination
    assert j2_secular_rates(
        a, 0.0, math.degrees(math.asin(math.sqrt(0.8)))
    ).arg_perigee_dot_rad_s == (pytest.approx(0.0, abs=1e-12))


# ---- sun-synchronous ------------------------------------------------------------------------


@pytest.mark.parametrize(("alt_km", "inc"), [(600.0, 97.79), (700.0, 98.19), (800.0, 98.60)])
def test_the_inclination_matches_the_textbook_values(alt_km: float, inc: float) -> None:
    assert sun_synchronous_inclination_deg(RE + alt_km * 1000.0, 0.0) == pytest.approx(
        inc, abs=0.05
    )


def test_the_node_of_a_designed_orbit_follows_the_mean_sun_in_sgp4() -> None:
    a = RE + 650e3
    inc = sun_synchronous_inclination_deg(a, 0.0)
    sat = _satrec(a, 0.0, inc, 40.0)
    days = 30.0
    # the same orbital phase at both ends: whole days apart is not whole orbits, so average the
    # osculating node over a day at each end
    start = np.mean([_unwrap(40.0, _raan_deg(sat, m)) for m in np.linspace(0.0, 1440.0, 97)])
    end = np.mean(
        [_unwrap(40.0, _raan_deg(sat, m + days * 1440.0)) for m in np.linspace(0.0, 1440.0, 97)]
    )
    drift_per_day = (end - start) / days
    assert drift_per_day == pytest.approx(MEAN_SUN_DEG_PER_DAY, rel=3e-3)


def test_the_designed_orbit_keeps_its_local_time_in_sgp4() -> None:
    """The local time at the start and 30 days later, each from the node of the osculating orbit
    averaged over a day. The design is a mean orbit, SGP4's osculating node differs from the mean
    one by a fixed offset (about two minutes, DV-E6); what has to hold is that it does not drift."""
    design = design_sun_synchronous(altitude_m=650e3, ltan_h=10.5, epoch=EPOCH)
    sat = _satrec(RE + 650e3, 0.0, design.inclination_deg, design.raan_deg)

    def ltan_on(day: float) -> float:
        node = np.mean([_raan_deg(sat, day * 1440.0 + m) for m in np.linspace(0.0, 1440.0, 97)])
        return mean_solar_time_of_node_h(float(node), EPOCH + timedelta(days=day))

    start, later = ltan_on(0.0), ltan_on(30.0)
    assert _hours_apart(start, 10.5) < 0.05  # the offset between the mean and the osculating node
    assert _hours_apart(later, start) < 0.006  # drift over 30 days: 22 seconds at most


def test_an_orbit_too_high_for_a_sun_synchronous_node_is_refused() -> None:
    with pytest.raises(OrbitDesignError, match="sun-synchronous"):
        sun_synchronous_inclination_deg(RE + 8000e3, 0.0)


def test_the_altitude_of_an_inclination_is_the_inverse() -> None:
    for alt in (400e3, 650e3, 1200e3, 3000e3):
        a = RE + alt
        for e in (0.0, 0.01):
            inc = sun_synchronous_inclination_deg(a, e)
            assert sun_synchronous_altitude_m(inc, e) == pytest.approx(alt, rel=1e-9)


def test_a_prograde_inclination_has_no_sun_synchronous_altitude() -> None:
    with pytest.raises(OrbitDesignError, match="retrograde"):
        sun_synchronous_altitude_m(60.0, 0.0)


def test_the_earth_model_is_used() -> None:
    a = RE + 600e3
    wgs84 = sun_synchronous_inclination_deg(a, 0.0, earth_model="wgs84")
    wgs72 = sun_synchronous_inclination_deg(a, 0.0, earth_model="wgs72")
    assert wgs84 != wgs72 and abs(wgs84 - wgs72) < 0.01


# ---- the local time of the node -------------------------------------------------------------


def test_the_mean_sun_of_the_sun_model_gives_the_same_local_time() -> None:
    """The local mean solar time of the node from Greenwich sidereal time (the module) against
    12 h plus the node's right ascension minus the mean longitude of the Sun (the Sun model)."""
    rng = np.random.default_rng(7)
    for _ in range(40):
        epoch = datetime(2024, 1, 1, tzinfo=UTC) + timedelta(seconds=float(rng.uniform(0, 4e8)))
        raan = float(rng.uniform(0.0, 360.0))
        jd = sum(geo.julian_date_parts(epoch))
        mean_longitude = (280.460 + 0.9856474 * (jd - 2451545.0)) % 360.0
        expected = (12.0 + (raan - mean_longitude) / 15.0) % 24.0
        got = mean_solar_time_of_node_h(raan, epoch)
        assert _hours_apart(got, expected) < 0.02, (epoch, raan)


def _hours_apart(a: float, b: float) -> float:
    return abs((a - b + 12.0) % 24.0 - 12.0)


def test_a_node_at_the_mean_sun_is_at_noon() -> None:
    jd = sum(geo.julian_date_parts(EPOCH))
    mean_longitude = (280.460 + 0.9856474 * (jd - 2451545.0)) % 360.0
    assert _hours_apart(mean_solar_time_of_node_h(mean_longitude, EPOCH), 12.0) < 0.02


def test_ltan_and_raan_are_inverses() -> None:
    for hour in (0.0, 6.25, 10.5, 12.0, 22.5, 23.99):
        for epoch in (EPOCH, EPOCH + timedelta(days=100, hours=7, minutes=13)):
            raan = raan_from_ltan_deg(hour, epoch)
            assert 0.0 <= raan < 360.0
            assert _hours_apart(mean_solar_time_of_node_h(raan, epoch), hour) < 1e-9


def test_the_local_time_is_in_zero_to_twenty_four() -> None:
    for raan in (0.0, 90.0, 180.0, 270.0, 359.999):
        assert 0.0 <= mean_solar_time_of_node_h(raan, EPOCH) < 24.0


def test_the_descending_node_is_twelve_hours_later() -> None:
    design = design_sun_synchronous(altitude_m=700e3, ltan_h=22.5, epoch=EPOCH)
    assert design.ltdn_h == pytest.approx(10.5)
    assert design.ltan_h == pytest.approx(22.5)


def test_a_designed_orbit_reports_what_it_is() -> None:
    design = design_sun_synchronous(altitude_m=800e3, ltan_h=10.5, epoch=EPOCH)
    assert design.inclination_deg == pytest.approx(98.6, abs=0.05)
    assert design.nodal_period_s == pytest.approx(6040.0, rel=0.01)  # about 100.7 min
    assert 14.0 < design.revolutions_per_day < 14.6
    assert 0.0 <= design.raan_deg < 360.0 and design.semi_major_axis_m == pytest.approx(RE + 800e3)


# ---- repeat ground tracks -------------------------------------------------------------------


def test_fifteen_revolutions_a_day_in_a_sun_synchronous_orbit() -> None:
    sol = repeat_ground_track(15, 1, sun_synchronous=True)
    assert sol.altitude_m / 1000.0 == pytest.approx(567.0, abs=10.0)  # the textbook 15 rev/day SSO
    assert sol.inclination_deg == pytest.approx(97.7, abs=0.2)
    assert sol.track_spacing_km == pytest.approx(2.0 * math.pi * RE / 15.0 / 1000.0, rel=1e-6)


def test_the_ground_track_of_the_solution_repeats_in_sgp4() -> None:
    """Propagate the solution: the longitude of the ascending node crossing after N nodal periods
    is the one it started at, to a fraction of the spacing of the tracks."""
    sol = repeat_ground_track(14, 1, sun_synchronous=True)
    sat = _satrec(sol.semi_major_axis_m, 0.0, sol.inclination_deg, 0.0)
    jd0 = sat.jdsatepoch + sat.jdsatepochF

    def crossings(total_min: float) -> list[tuple[float, float]]:
        out: list[tuple[float, float]] = []
        step = 0.25
        prev = None
        for k in range(int(total_min / step)):
            m = k * step
            err, r, _v = sat.sgp4(sat.jdsatepoch, sat.jdsatepochF + m / 1440.0)
            assert err == 0
            if prev is not None and prev[1] < 0.0 <= r[2]:
                lo, hi = prev[0], m
                for _ in range(40):
                    mid = 0.5 * (lo + hi)
                    _e, rm, _vm = sat.sgp4(sat.jdsatepoch, sat.jdsatepochF + mid / 1440.0)
                    lo, hi = (mid, hi) if rm[2] < 0.0 else (lo, mid)
                _e, rn, _vn = sat.sgp4(sat.jdsatepoch, sat.jdsatepochF + hi / 1440.0)
                gmst = math.degrees(float(geo.gmst_rad(np.array([jd0 + hi / 1440.0]))[0]))
                out.append((hi, (math.degrees(math.atan2(rn[1], rn[0])) - gmst) % 360.0))
            prev = (m, float(r[2]))
        return out

    nodes = crossings(2.2 * 1440.0)
    assert len(nodes) >= 15
    first, repeat = nodes[0][1], nodes[14][1]  # 14 revolutions later, one nodal day
    assert abs(_unwrap(first, repeat)) < 0.4  # the spacing of the tracks is 360/14 = 25.7 deg


def test_a_non_sun_synchronous_repeat_with_a_given_inclination() -> None:
    sol = repeat_ground_track(16, 1, inclination_deg=51.6)
    assert 150.0 < sol.altitude_m / 1000.0 < 450.0
    assert sol.inclination_deg == 51.6 and not sol.sun_synchronous


def test_one_of_inclination_or_sun_synchronous_is_needed() -> None:
    with pytest.raises(OrbitDesignError, match="inclination"):
        repeat_ground_track(15, 1)
    with pytest.raises(OrbitDesignError, match="inclination"):
        repeat_ground_track(15, 1, inclination_deg=98.0, sun_synchronous=True)


def test_a_cycle_that_does_not_exist_in_the_search_range_is_refused() -> None:
    with pytest.raises(OrbitDesignError, match="no orbit"):
        repeat_ground_track(60, 1, sun_synchronous=True)  # below the surface


def test_candidates_are_reduced_fractions_in_the_window_sorted_by_altitude() -> None:
    found = repeat_candidates(500e3, 800e3, 10, sun_synchronous=True)
    assert found, "a window of 300 km holds repeat cycles"
    alts = [s.altitude_m for s in found]
    assert alts == sorted(alts)
    for s in found:
        assert 500e3 <= s.altitude_m <= 800e3
        assert s.days <= 10 and math.gcd(s.revolutions, s.days) == 1
    assert any((s.revolutions, s.days) == (15, 1) or s.days > 1 for s in found)


def test_candidates_with_a_fixed_inclination() -> None:
    found = repeat_candidates(400e3, 600e3, 3, inclination_deg=97.0)
    assert all(abs(s.inclination_deg - 97.0) < 1e-9 for s in found)


def test_the_solution_is_deterministic() -> None:
    assert repeat_ground_track(15, 1, sun_synchronous=True) == repeat_ground_track(
        15, 1, sun_synchronous=True
    )
