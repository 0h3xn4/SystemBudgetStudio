"""Orbit design helpers (2.2.0, D-226): from what a mission analyst asks for (the local time of the
ascending node, a sun-synchronous orbit, a repeat ground track) to the elements the tool takes.

The relations are the first-order secular J2 ones of the textbooks: the rates of the node, of the
argument of perigee and of the mean anomaly of a mean orbit, and what follows from them. They use
the Earth radius, the gravitational parameter and J2 of the Earth model that the scenario uses
(WGS-84 or WGS-72), and the rate of the mean Sun of the Sun model of the tool. The local time is
the *mean* local solar time of the node (the equation of time is not applied, D-226); it is worked
out from Greenwich mean sidereal time and so agrees with the Earth rotation the tool uses for
passes. Nothing here reads a project file, and nothing is a standards value: each number is a
definition, a constant of the Earth model or an input of the user.

Accuracy: SGP4 includes terms of higher order than J2, so the node of a designed orbit moves in the
tool at the designed rate to a few parts in a thousand (DEVIATIONS DV-E6; the tests measure it).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime

import numpy as np

from budget_core.environment import geometry as geo
from budget_core.environment.constants import (
    DEFAULT_EARTH_MODEL,
    EARTH_MODELS,
    EARTH_ROTATION_RATE,
    MEAN_SUN_LONGITUDE_RATE,
    EarthModel,
)
from budget_core.equation_binding import computes

__all__ = [
    "OrbitDesignError",
    "RepeatSolution",
    "SecularRates",
    "SunSynchronousDesign",
    "design_sun_synchronous",
    "j2_secular_rates",
    "mean_solar_time_of_node_h",
    "raan_from_ltan_deg",
    "repeat_candidates",
    "repeat_ground_track",
    "sun_synchronous_altitude_m",
    "sun_synchronous_inclination_deg",
]


class OrbitDesignError(ValueError):
    """The request has no solution, or an input is out of range. The message says why in words."""


def _earth(earth_model: str) -> EarthModel:
    try:
        return EARTH_MODELS[earth_model]
    except KeyError:
        raise OrbitDesignError(
            f"The Earth model is one of {', '.join(sorted(EARTH_MODELS))}."
        ) from None


def _sun_rate_rad_s() -> float:
    """The rate of the mean Sun in right ascension (and the rate a sun-synchronous node needs)."""
    return math.radians(MEAN_SUN_LONGITUDE_RATE.value) / 86400.0


def _check_shape(a_m: float, e: float, earth: EarthModel) -> None:
    if not 0.0 <= e < 1.0:
        raise OrbitDesignError("The eccentricity is at least 0 and below 1.")
    if a_m * (1.0 - e) <= earth.radius_m:
        raise OrbitDesignError("The perigee is below the surface of the Earth.")


# ---- the secular rates ---------------------------------------------------------------------


@dataclass(frozen=True)
class SecularRates:
    """Secular rates of a mean orbit under J2 (rad/s) and the mean motion (rad/s)."""

    mean_motion_rad_s: float
    raan_dot_rad_s: float
    arg_perigee_dot_rad_s: float
    mean_anomaly_dot_rad_s: float  # n plus the J2 correction

    @property
    def argument_of_latitude_dot_rad_s(self) -> float:
        """The rate of the angle from the ascending node: what the nodal period is made of."""
        return self.arg_perigee_dot_rad_s + self.mean_anomaly_dot_rad_s

    @property
    def nodal_period_s(self) -> float:
        return 2.0 * math.pi / self.argument_of_latitude_dot_rad_s


@computes("ORB-J2-RATES")
def j2_secular_rates(
    a_m: float, e: float, i_deg: float, earth_model: str = DEFAULT_EARTH_MODEL
) -> SecularRates:
    """ORB-J2-RATES: the first-order secular rates of the node, the argument of perigee and the
    mean anomaly under J2, with p = a (1 - e^2) and n = sqrt(mu / a^3)."""
    earth = _earth(earth_model)
    _check_shape(a_m, e, earth)
    if not 0.0 <= i_deg <= 180.0:
        raise OrbitDesignError("The inclination is between 0 and 180 degrees.")
    n = math.sqrt(earth.mu_m3s2 / a_m**3)
    p = a_m * (1.0 - e * e)
    k = 1.5 * earth.j2 * (earth.radius_m / p) ** 2 * n
    i = math.radians(i_deg)
    sin2 = math.sin(i) ** 2
    return SecularRates(
        n,
        -k * math.cos(i),
        k * (2.0 - 2.5 * sin2),
        n + k * math.sqrt(1.0 - e * e) * (1.0 - 1.5 * sin2),
    )


# ---- sun-synchronous orbits -----------------------------------------------------------------


@computes("ORB-SSO")
def sun_synchronous_inclination_deg(
    a_m: float, e: float = 0.0, earth_model: str = DEFAULT_EARTH_MODEL
) -> float:
    """ORB-SSO: the inclination at which the node moves at the rate of the mean Sun,
    cos i = -w_sun / (1.5 J2 (Re / p)^2 n)."""
    earth = _earth(earth_model)
    _check_shape(a_m, e, earth)
    n = math.sqrt(earth.mu_m3s2 / a_m**3)
    p = a_m * (1.0 - e * e)
    cos_i = -_sun_rate_rad_s() / (1.5 * earth.j2 * (earth.radius_m / p) ** 2 * n)
    if cos_i < -1.0:
        raise OrbitDesignError(
            "There is no sun-synchronous orbit at this altitude: the node cannot move fast "
            "enough, even in a polar orbit, so it has to be lower."
        )
    return math.degrees(math.acos(cos_i))


def sun_synchronous_altitude_m(
    i_deg: float, e: float = 0.0, earth_model: str = DEFAULT_EARTH_MODEL
) -> float:
    """The altitude (semi-major axis minus the equatorial radius) of the sun-synchronous orbit of
    an inclination, from ORB-SSO solved for a."""
    earth = _earth(earth_model)
    if not 0.0 <= e < 1.0:
        raise OrbitDesignError("The eccentricity is at least 0 and below 1.")
    if not 90.0 < i_deg <= 180.0:
        raise OrbitDesignError(
            "A sun-synchronous orbit is retrograde: the inclination is above 90 degrees."
        )
    cos_i = abs(math.cos(math.radians(i_deg)))
    a = float(
        (
            1.5
            * earth.j2
            * earth.radius_m**2
            * math.sqrt(earth.mu_m3s2)
            * cos_i
            / (_sun_rate_rad_s() * (1.0 - e * e) ** 2)
        )
        ** (2.0 / 7.0)
    )
    if a * (1.0 - e) <= earth.radius_m:
        raise OrbitDesignError("The perigee of this orbit is below the surface of the Earth.")
    return a - earth.radius_m


# ---- the local time of the node -------------------------------------------------------------


def _day_fraction_h(moment: datetime) -> float:
    utc = moment.astimezone(UTC)
    return utc.hour + utc.minute / 60.0 + (utc.second + utc.microsecond * 1e-6) / 3600.0


def _gmst_deg(moment: datetime) -> float:
    jd, fr = geo.julian_date_parts(moment)
    return math.degrees(float(geo.gmst_rad(np.array([jd + fr]))[0]))


@computes("ORB-LTAN")
def mean_solar_time_of_node_h(raan_deg: float, epoch: datetime) -> float:
    """ORB-LTAN: the mean local solar time of the ascending node in hours, 0 up to 24, from its
    right ascension at a UTC time: UT plus the longitude of the node over 15 degrees per hour,
    where the longitude of the node is its right ascension minus Greenwich sidereal time."""
    return (_day_fraction_h(epoch) + (raan_deg - _gmst_deg(epoch)) / 15.0) % 24.0


def raan_from_ltan_deg(ltan_h: float, epoch: datetime) -> float:
    """The right ascension of the ascending node (0 up to 360 degrees) whose mean local solar time
    at a UTC time is `ltan_h` hours: the inverse of ORB-LTAN."""
    return (_gmst_deg(epoch) + 15.0 * (ltan_h - _day_fraction_h(epoch))) % 360.0


@dataclass(frozen=True)
class SunSynchronousDesign:
    epoch: datetime
    semi_major_axis_m: float
    altitude_m: float  # the semi-major axis minus the equatorial radius
    eccentricity_ratio: float
    inclination_deg: float
    raan_deg: float
    ltan_h: float
    ltdn_h: float  # the descending node is twelve hours later
    nodal_period_s: float
    revolutions_per_day: float  # of the nodal period, in a mean solar day
    earth_model: str


def design_sun_synchronous(
    *,
    altitude_m: float,
    ltan_h: float,
    epoch: datetime,
    eccentricity: float = 0.0,
    earth_model: str = DEFAULT_EARTH_MODEL,
) -> SunSynchronousDesign:
    """A sun-synchronous orbit at an altitude whose ascending node is at `ltan_h` (mean local
    solar time) at `epoch`: the inclination and the right ascension to write into the orbit."""
    earth = _earth(earth_model)
    if not 0.0 <= ltan_h < 24.0:
        raise OrbitDesignError("The local time of the node is from 0 up to 24 hours.")
    a = earth.radius_m + altitude_m
    inclination = sun_synchronous_inclination_deg(a, eccentricity, earth_model)
    period = j2_secular_rates(a, eccentricity, inclination, earth_model).nodal_period_s
    return SunSynchronousDesign(
        epoch,
        a,
        altitude_m,
        eccentricity,
        inclination,
        raan_from_ltan_deg(ltan_h, epoch),
        ltan_h,
        (ltan_h + 12.0) % 24.0,
        period,
        86400.0 / period,
        earth_model,
    )


# ---- repeat ground tracks -------------------------------------------------------------------


@dataclass(frozen=True)
class RepeatSolution:
    """N revolutions in D nodal days (a nodal day: the Earth turns once relative to the node)."""

    revolutions: int
    days: int
    semi_major_axis_m: float
    altitude_m: float
    eccentricity_ratio: float
    inclination_deg: float
    sun_synchronous: bool
    nodal_period_s: float
    track_spacing_km: float  # between neighbouring tracks at the equator, 2 pi Re / N
    earth_model: str


def _orbits_per_nodal_day(
    a_m: float, e: float, i_deg: float | None, earth_model: str
) -> tuple[float, float, float]:
    """(orbits per nodal day, inclination in degrees, nodal period in seconds) of a mean orbit.
    `i_deg` None means sun-synchronous."""
    if i_deg is None:
        inclination = sun_synchronous_inclination_deg(a_m, e, earth_model)
        node_rate = _sun_rate_rad_s()
    else:
        inclination = i_deg
        node_rate = j2_secular_rates(a_m, e, inclination, earth_model).raan_dot_rad_s
    rates = j2_secular_rates(a_m, e, inclination, earth_model)
    ratio = rates.argument_of_latitude_dot_rad_s / (EARTH_ROTATION_RATE.value - node_rate)
    return ratio, inclination, rates.nodal_period_s


def _lowest_a_m(earth: EarthModel, e: float) -> float:
    return (earth.radius_m + 100e3) / (1.0 - e)  # a perigee 100 km above the surface


def _highest_a_m(earth: EarthModel, e: float, i_deg: float | None) -> float:
    if i_deg is not None:
        return 20.0 * earth.radius_m
    # the highest sun-synchronous orbit: the one with cos i = -1
    p = ((1.5 * earth.j2 * earth.radius_m**2 * math.sqrt(earth.mu_m3s2)) / _sun_rate_rad_s()) ** (
        2.0 / 7.0
    )
    return float(p / (1.0 - e * e) ** (4.0 / 7.0) * (1.0 - 1e-9))


@computes("ORB-REPEAT")
def repeat_ground_track(
    revolutions: int,
    days: int,
    *,
    eccentricity: float = 0.0,
    inclination_deg: float | None = None,
    sun_synchronous: bool = False,
    earth_model: str = DEFAULT_EARTH_MODEL,
) -> RepeatSolution:
    """ORB-REPEAT: the orbit whose ground track repeats after `revolutions` nodal periods in `days`
    nodal days, (w_arglat) / (w_earth - w_node) = N / D, solved for the semi-major axis by
    bisection. Give an inclination, or ask for a sun-synchronous orbit, not both."""
    if (inclination_deg is None) == (not sun_synchronous):
        raise OrbitDesignError(
            "Give either an inclination or ask for a sun-synchronous orbit, not both and not "
            "neither."
        )
    if revolutions < 1 or days < 1:
        raise OrbitDesignError("The number of revolutions and of days is at least 1.")
    earth = _earth(earth_model)
    if not 0.0 <= eccentricity < 1.0:
        raise OrbitDesignError("The eccentricity is at least 0 and below 1.")
    target = revolutions / days
    lo, hi = _lowest_a_m(earth, eccentricity), _highest_a_m(earth, eccentricity, inclination_deg)

    def excess(a: float) -> float:
        return _orbits_per_nodal_day(a, eccentricity, inclination_deg, earth_model)[0] - target

    try:
        at_lo, at_hi = excess(lo), excess(hi)
    except OrbitDesignError:
        at_lo = at_hi = math.nan
    if not (at_lo >= 0.0 >= at_hi):
        raise OrbitDesignError(
            f"There is no orbit with {revolutions} revolutions in {days} day(s) between a perigee "
            "100 km above the surface and the highest orbit that fits the request."
        )
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if excess(mid) >= 0.0:
            lo = mid
        else:
            hi = mid
    a = 0.5 * (lo + hi)
    _, inclination, period = _orbits_per_nodal_day(a, eccentricity, inclination_deg, earth_model)
    return RepeatSolution(
        revolutions,
        days,
        a,
        a - earth.radius_m,
        eccentricity,
        inclination,
        sun_synchronous,
        period,
        2.0 * math.pi * earth.radius_m / revolutions / 1000.0,
        earth_model,
    )


def repeat_candidates(
    altitude_min_m: float,
    altitude_max_m: float,
    max_days: int,
    *,
    eccentricity: float = 0.0,
    inclination_deg: float | None = None,
    sun_synchronous: bool = False,
    earth_model: str = DEFAULT_EARTH_MODEL,
) -> list[RepeatSolution]:
    """Every repeat cycle N/D (a reduced fraction, D up to `max_days`) with an orbit in the
    altitude window, by increasing altitude."""
    if (inclination_deg is None) == (not sun_synchronous):
        raise OrbitDesignError(
            "Give either an inclination or ask for a sun-synchronous orbit, not both and not "
            "neither."
        )
    if altitude_min_m >= altitude_max_m:
        raise OrbitDesignError("The lowest altitude is below the highest.")
    earth = _earth(earth_model)
    try:
        q_low_alt = _orbits_per_nodal_day(
            earth.radius_m + altitude_min_m, eccentricity, inclination_deg, earth_model
        )[0]
        q_high_alt = _orbits_per_nodal_day(
            earth.radius_m + altitude_max_m, eccentricity, inclination_deg, earth_model
        )[0]
    except OrbitDesignError:
        return []
    found: list[RepeatSolution] = []
    for days in range(1, max_days + 1):
        first = math.ceil(q_high_alt * days - 1e-9)
        last = math.floor(q_low_alt * days + 1e-9)
        for revolutions in range(first, last + 1):
            if revolutions < 1 or math.gcd(revolutions, days) != 1:
                continue
            try:
                solution = repeat_ground_track(
                    revolutions,
                    days,
                    eccentricity=eccentricity,
                    inclination_deg=inclination_deg,
                    sun_synchronous=sun_synchronous,
                    earth_model=earth_model,
                )
            except OrbitDesignError:
                continue
            if altitude_min_m <= solution.altitude_m <= altitude_max_m:
                found.append(solution)
    return sorted(found, key=lambda s: (s.altitude_m, s.days))
