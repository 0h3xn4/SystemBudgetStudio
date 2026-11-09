# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""A state vector to the mean elements the tool propagates (2.2.0, D-229).

An orbit may be given as a position and velocity at an epoch, in J2000 (the frame most tools
export) or in TEME (the frame SGP4 works in). The scenario propagates mean elements with SGP4, so
the state has to become mean elements. This module does it in two steps:

1. the frame: J2000 to TEME is the IAU-76 precession, the first ten terms of the IAU-1980
   nutation and the equation of the equinoxes (the same rotation, to about two metres at the
   radius of a low orbit in 2026, as the full models of astropy: DEVIATIONS DV-E7);
2. the elements: the six mean elements are found for which SGP4's own state at the epoch equals the
   given one (Newton's method on the equinoctial elements, so that circular and equatorial
   orbits are not singular). The given state is therefore reproduced at the epoch to better than a
   millimetre; after the epoch the orbit is SGP4's.

Nothing here reads a project file. UTC stands for TT and UT1 in the frame (a minute of time is
2e-5 arcseconds of precession, far below the other errors).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import numpy as np

from budget_core.environment import geometry as geo
from budget_core.environment.constants import DEFAULT_EARTH_MODEL, EARTH_MODELS
from budget_core.environment.elements import satrec_from_values
from budget_core.equation_binding import computes

NDArray = np.ndarray[Any, np.dtype[np.float64]]

__all__ = [
    "MeanElementsFit",
    "StateConversionError",
    "j2000_to_teme_matrix",
    "mean_elements_from_state",
    "osculating_elements",
    "teme_state",
]

_ARCSEC = math.pi / 180.0 / 3600.0


class StateConversionError(ValueError):
    """The state cannot be made into an orbit; the message says why in words (no values)."""


# ---- the frame ------------------------------------------------------------------------------


def _r1(a: float) -> NDArray:
    c, s = math.cos(a), math.sin(a)
    return np.array([[1.0, 0.0, 0.0], [0.0, c, s], [0.0, -s, c]])


def _r2(a: float) -> NDArray:
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0.0, -s], [0.0, 1.0, 0.0], [s, 0.0, c]])


def _r3(a: float) -> NDArray:
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, s, 0.0], [-s, c, 0.0], [0.0, 0.0, 1.0]])


# the ten largest terms of the IAU-1980 nutation series (l, l', F, D, Omega; the coefficients of
# the longitude A + A' T and of the obliquity B + B' T, in units of 1e-4 arcsecond)
_NUTATION = (
    (0, 0, 0, 0, 1, -171996.0, -174.2, 92025.0, 8.9),
    (0, 0, 2, -2, 2, -13187.0, -1.6, 5736.0, -3.1),
    (0, 0, 2, 0, 2, -2274.0, -0.2, 977.0, -0.5),
    (0, 0, 0, 0, 2, 2062.0, 0.2, -895.0, 0.5),
    (0, 1, 0, 0, 0, 1426.0, -3.4, 54.0, -0.1),
    (1, 0, 0, 0, 0, 712.0, 0.1, -7.0, 0.0),
    (0, 1, 2, -2, 2, -517.0, 1.2, 224.0, -0.6),
    (0, 0, 2, 0, 1, -386.0, -0.4, 200.0, 0.0),
    (1, 0, 2, 0, 2, -301.0, 0.0, 129.0, -0.1),
    (0, -1, 2, -2, 2, 217.0, -0.5, -95.0, 0.3),
)


def _nutation(t: float) -> tuple[float, float]:
    """Nutation in longitude and obliquity (rad) at `t` Julian centuries from J2000."""
    d = math.radians(297.85036 + 445267.111480 * t - 0.0019142 * t**2)
    m = math.radians(357.52772 + 35999.050340 * t - 0.0001603 * t**2)
    mp = math.radians(134.96298 + 477198.867398 * t + 0.0086972 * t**2)
    f = math.radians(93.27191 + 483202.017538 * t - 0.0036825 * t**2)
    om = math.radians(125.04452 - 1934.136261 * t + 0.0020708 * t**2)
    dpsi = deps = 0.0
    for l_, lp, ff, dd, oo, a, a1, b, b1 in _NUTATION:
        arg = l_ * mp + lp * m + ff * f + dd * d + oo * om
        dpsi += (a + a1 * t) * math.sin(arg)
        deps += (b + b1 * t) * math.cos(arg)
    return dpsi * 1e-4 * _ARCSEC, deps * 1e-4 * _ARCSEC


@computes("ORB-FRAME")
def j2000_to_teme_matrix(moment: datetime) -> NDArray:
    """ORB-FRAME: the rotation from J2000 to TEME at a UTC time: IAU-76 precession, the leading
    terms of the IAU-1980 nutation, and the equation of the equinoxes (TOD to TEME)."""
    jd, fr = geo.julian_date_parts(moment)
    t = (jd + fr - 2451545.0) / 36525.0
    zeta = (2306.2181 * t + 0.30188 * t**2 + 0.017998 * t**3) * _ARCSEC
    theta = (2004.3109 * t - 0.42665 * t**2 - 0.041833 * t**3) * _ARCSEC
    z = (2306.2181 * t + 1.09468 * t**2 + 0.018203 * t**3) * _ARCSEC
    precession = _r3(-z) @ _r2(theta) @ _r3(-zeta)
    dpsi, deps = _nutation(t)
    eps = (84381.448 - 46.8150 * t - 0.00059 * t**2 + 0.001813 * t**3) * _ARCSEC
    nutation = _r1(-(eps + deps)) @ _r3(-dpsi) @ _r1(eps)
    equinoxes = dpsi * math.cos(eps)
    matrix: NDArray = _r3(equinoxes) @ nutation @ precession
    return matrix


def teme_state(
    frame: str, epoch: datetime, position_m: NDArray, velocity_m_s: NDArray
) -> tuple[NDArray, NDArray]:
    """The state in TEME. `frame` is `teme` (as it is) or `j2000`."""
    if frame == "teme":
        return np.asarray(position_m, dtype=np.float64), np.asarray(velocity_m_s, dtype=np.float64)
    if frame != "j2000":
        raise StateConversionError("The frame is j2000 or teme.")
    matrix = j2000_to_teme_matrix(epoch)
    return matrix @ position_m, matrix @ velocity_m_s


# ---- osculating elements --------------------------------------------------------------------


@dataclass(frozen=True)
class Equinoctial:
    a_m: float
    f: float
    g: float
    h: float
    k: float
    long_rad: float  # true longitude for an osculating set, mean longitude for a mean one

    def vector(self) -> NDArray:
        return np.array([self.a_m, self.f, self.g, self.h, self.k, self.long_rad])


def osculating_elements(r: NDArray, v: NDArray, mu: float) -> tuple[float, float, float]:
    """(semi-major axis in m, eccentricity, inclination in degrees) of the osculating orbit of a
    state, for the checks and for the report of how far the mean orbit is from it."""
    rn = float(np.linalg.norm(r))
    energy = float(np.dot(v, v)) / 2.0 - mu / rn
    if energy >= 0.0:
        raise StateConversionError(
            "The state is not a bound orbit: its speed is at or above the escape speed."
        )
    a = -mu / (2.0 * energy)
    h = np.cross(r, v)
    ecc = np.cross(v, h) / mu - r / rn
    return a, float(np.linalg.norm(ecc)), math.degrees(math.acos(h[2] / np.linalg.norm(h)))


def _equinoctial_of_state(r: NDArray, v: NDArray, mu: float) -> Equinoctial:
    """The osculating equinoctial elements of a state (Newton's start); the longitude is the
    mean longitude. With h = tan(i/2) cos(RAAN), k = tan(i/2) sin(RAAN), f = e cos(RAAN + argp),
    g = e sin(RAAN + argp), and the true longitude measured from the equinoctial axis
    Q x, Q = Rz(RAAN) Rx(i) Rz(-RAAN)."""
    a, e, _ = osculating_elements(r, v, mu)
    h_vec = np.cross(r, v)
    w = h_vec / float(np.linalg.norm(h_vec))
    if w[2] < -1.0 + 1e-9:
        raise StateConversionError(
            "A retrograde orbit in the equatorial plane is not supported: give the state with a "
            "small inclination, or the elements."
        )
    inc = math.acos(max(-1.0, min(1.0, float(w[2]))))
    raan = math.atan2(float(w[0]), -float(w[1])) if math.sin(inc) > 1e-12 else 0.0
    t = math.tan(inc / 2.0)
    h_, k_ = t * math.cos(raan), t * math.sin(raan)
    q = _rz(raan) @ _rx(inc) @ _rz(-raan)
    f_hat, g_hat = q[:, 0], q[:, 1]
    rn = float(np.linalg.norm(r))
    ecc_vec = np.cross(v, h_vec) / mu - r / rn
    f, g = float(np.dot(ecc_vec, f_hat)), float(np.dot(ecc_vec, g_hat))
    true_long = math.atan2(float(np.dot(r, g_hat)), float(np.dot(r, f_hat)))
    varpi = math.atan2(g, f) if e > 0.0 else 0.0
    nu = true_long - varpi
    big_e = 2.0 * math.atan2(
        math.sqrt(1.0 - e) * math.sin(nu / 2.0), math.sqrt(1.0 + e) * math.cos(nu / 2.0)
    )
    mean_anomaly = big_e - e * math.sin(big_e)
    return Equinoctial(a, f, g, h_, k_, varpi + mean_anomaly)


def _rz(a: float) -> NDArray:
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


def _rx(a: float) -> NDArray:
    c, s = math.cos(a), math.sin(a)
    return np.array([[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]])


def _keplerian_of(x: NDArray) -> tuple[float, float, float, float, float, float]:
    """(a, e, i, raan, argp, M) in metres and radians of an equinoctial vector with the mean
    longitude."""
    a, f, g, h, k, long_ = (float(c) for c in x)
    e = math.hypot(f, g)
    varpi = math.atan2(g, f) if e > 0.0 else 0.0
    inc = 2.0 * math.atan(math.hypot(h, k))
    raan = math.atan2(k, h) if (h or k) else 0.0
    argp = varpi - raan
    mean = long_ - varpi
    return a, e, inc, raan % (2.0 * math.pi), argp % (2.0 * math.pi), mean % (2.0 * math.pi)


# ---- the mean elements ----------------------------------------------------------------------


@dataclass(frozen=True)
class MeanElementsFit:
    """The mean elements whose SGP4 state at the epoch is the given one."""

    semi_major_axis_m: float
    eccentricity_ratio: float
    inclination_deg: float
    raan_deg: float
    arg_perigee_deg: float
    mean_anomaly_deg: float
    iterations: int
    position_residual_m: float
    velocity_residual_m_s: float
    osculating_semi_major_axis_m: float  # of the given state, to see how far the mean one is
    osculating_eccentricity_ratio: float


def _state_of(x: NDArray, epoch: datetime, earth_model: str) -> NDArray:
    a, e, inc, raan, argp, mean = _keplerian_of(x)
    jd, fr = geo.julian_date_parts(epoch)
    sat = satrec_from_values(jd, fr, a, e, inc, raan, argp, mean, earth_model)
    error, pos, vel = sat.sgp4(jd, fr)
    if error:
        raise StateConversionError(
            "SGP4 cannot propagate the orbit these elements give at the epoch of the state."
        )
    return np.concatenate([np.array(pos) * 1000.0, np.array(vel) * 1000.0])


@computes("ORB-STATE-FIT")
def mean_elements_from_state(
    epoch: datetime,
    frame: str,
    position_m: NDArray,
    velocity_m_s: NDArray,
    earth_model: str = DEFAULT_EARTH_MODEL,
    *,
    max_iterations: int = 40,
    position_tolerance_m: float = 1e-4,
    velocity_tolerance_m_s: float = 1e-7,
) -> MeanElementsFit:
    """ORB-STATE-FIT: Newton's method on the equinoctial elements (a, f, g, h, k, L) for the
    mean elements whose SGP4 state at the epoch is the given state, with a finite-difference
    Jacobian and a halved step while the residual grows."""
    if earth_model not in EARTH_MODELS:
        raise StateConversionError("The Earth model is wgs84 or wgs72.")
    r = np.asarray(position_m, dtype=np.float64)
    v = np.asarray(velocity_m_s, dtype=np.float64)
    if (
        r.shape != (3,)
        or v.shape != (3,)
        or not (np.all(np.isfinite(r)) and np.all(np.isfinite(v)))
    ):
        raise StateConversionError("A position and a velocity are three finite numbers each.")
    earth = EARTH_MODELS[earth_model]
    radius = float(np.linalg.norm(r))
    if radius <= earth.radius_m:
        raise StateConversionError("The position is inside the Earth.")
    teme_r, teme_v = teme_state(frame, epoch, r, v)
    a0, e0, _ = osculating_elements(teme_r, teme_v, earth.mu_m3s2)
    if a0 * (1.0 - e0) <= earth.radius_m:
        raise StateConversionError("The osculating perigee of the state is below the surface.")
    target = np.concatenate([teme_r, teme_v * 1000.0])  # the velocity weighs like a position
    x = _equinoctial_of_state(teme_r, teme_v, earth.mu_m3s2).vector()
    scale = np.array([1.0e3, 1e-3, 1e-3, 1e-3, 1e-3, 1e-3])

    def residual(vec: NDArray) -> NDArray:
        got = _state_of(vec, epoch, earth_model)
        diff: NDArray = np.concatenate([got[:3], got[3:] * 1000.0]) - target
        return diff

    res = residual(x)
    iterations = 0
    for iteration in range(1, max_iterations + 1):
        iterations = iteration
        jac = np.empty((6, 6))
        for j in range(6):
            step = np.zeros(6)
            step[j] = scale[j] * 1e-3
            jac[:, j] = (residual(x + step) - res) / step[j]
        try:
            delta = np.linalg.solve(jac, -res)
        except np.linalg.LinAlgError:
            raise StateConversionError("The state gives no unique mean orbit.") from None
        factor = 1.0
        for _ in range(8):
            trial = x + factor * delta
            try:
                trial_res = residual(trial)
            except StateConversionError:
                factor /= 2.0
                continue
            if np.linalg.norm(trial_res) <= np.linalg.norm(res) or factor < 1e-3:
                break
            factor /= 2.0
        else:
            raise StateConversionError("The mean elements of this state could not be found.")
        x, res = trial, trial_res
        if (
            np.linalg.norm(res[:3]) < position_tolerance_m
            and np.linalg.norm(res[3:]) / 1000.0 < velocity_tolerance_m_s
        ):
            break
    else:
        raise StateConversionError("The mean elements of this state could not be found.")
    a, e, inc, raan, argp, mean = _keplerian_of(x)
    return MeanElementsFit(
        a,
        e,
        math.degrees(inc),
        math.degrees(raan),
        math.degrees(argp),
        math.degrees(mean),
        iterations,
        float(np.linalg.norm(res[:3])),
        float(np.linalg.norm(res[3:]) / 1000.0),
        a0,
        e0,
    )
