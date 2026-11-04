"""The Sun on the faces of a nadir-pointing spacecraft, by beta angle (2.7.0, D-250).

A circular orbit, a spacecraft pointing to nadir and flat faces: the position of the Sun in the
local-vertical frame (x along the velocity, y opposite to the orbit normal, z to nadir) at the
orbit angle `u` from noon, for the beta angle `b`, is

    s = (-cos b sin u, -sin b, -cos b cos u)

and a face with outward unit normal `n` is lit by `max(0, n . s)` while the spacecraft is outside
the cylindrical shadow of the Earth. The shadow, centred on `u = pi`, has the half-angle
`phi = acos(sqrt(1 - (Re / r)^2) / cos b)` when `|sin b| < Re / r` and does not exist otherwise.
On the sunlit arc `n . s` is `R cos(u - d) + c` with `c = -n_y sin b`, so the average and the
largest value of its positive part are closed forms (no sampling). Everything here is geometry:
no file is read and no number is a standards value. What the geometry leaves out is recorded as
DEVIATIONS DV-T4 and DV-T5.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from budget_core.equation_binding import computes

__all__ = [
    "FaceExposure",
    "PeakInstant",
    "eclipse_half_angle_rad",
    "face_exposure",
    "peak_instant",
    "sun_vector_lvlh",
    "sunlit_fraction",
]

TWO_PI = 2.0 * math.pi


def sun_vector_lvlh(beta_deg: float, u_rad: float) -> tuple[float, float, float]:
    """The unit vector to the Sun in the local-vertical frame at the orbit angle `u` from noon."""
    b = math.radians(beta_deg)
    return (-math.cos(b) * math.sin(u_rad), -math.sin(b), -math.cos(b) * math.cos(u_rad))


def _check(beta_deg: float, radius_ratio: float) -> None:
    if not -90.0 <= beta_deg <= 90.0:
        raise ValueError("The beta angle is between -90 and 90 degrees.")
    if not 0.0 < radius_ratio < 1.0:
        raise ValueError("The orbit radius is above the Earth radius.")


def eclipse_half_angle_rad(beta_deg: float, earth_radius_m: float, orbit_radius_m: float) -> float:
    """The half-angle of the arc of the orbit in shadow (0 when there is no eclipse)."""
    k = earth_radius_m / orbit_radius_m
    _check(beta_deg, k)
    cos_b = math.cos(math.radians(beta_deg))
    low = math.sqrt(1.0 - k * k)
    if cos_b <= low or cos_b < 1e-12:
        return 0.0
    return math.acos(low / cos_b)


@computes("TH-BETA-LIT")
def sunlit_fraction(beta_deg: float, earth_radius_m: float, orbit_radius_m: float) -> float:
    """TH-BETA-LIT: the part of a circular orbit that is outside the cylindrical shadow."""
    return 1.0 - eclipse_half_angle_rad(beta_deg, earth_radius_m, orbit_radius_m) / math.pi


def _lit_arc(beta_deg: float, earth_radius_m: float, orbit_radius_m: float) -> tuple[float, float]:
    """(start, end) of the sunlit arc, `end - start` at most one turn, starting after the
    eclipse, which is centred on `u = pi`."""
    phi = eclipse_half_angle_rad(beta_deg, earth_radius_m, orbit_radius_m)
    return math.pi + phi, 3.0 * math.pi - phi


@dataclass(frozen=True)
class FaceExposure:
    average: float  # of max(0, n . s) over the whole orbit, the eclipse counted as 0
    peak: float  # the largest value of max(0, n . s) while sunlit
    sunlit_fraction: float


def _coefficients(
    normal: Sequence[float], beta_deg: float
) -> tuple[float, float, float, float, float]:
    """(R, d, c, a, b) with n . s = a cos u + b sin u + c = R cos(u - d) + c."""
    b_rad = math.radians(beta_deg)
    a = -normal[2] * math.cos(b_rad)
    b = -normal[0] * math.cos(b_rad)
    c = -normal[1] * math.sin(b_rad)
    return math.hypot(a, b), math.atan2(b, a), c, a, b


def _positive_integral(r: float, d: float, c: float, lo: float, hi: float) -> float:
    """The integral over [lo, hi] of max(0, R cos(u - d) + c)."""
    if hi <= lo:
        return 0.0
    cuts = [lo, hi]
    if r > 1e-15 and abs(c) < r:
        half = math.acos(-c / r)
        for root in (d + half, d - half):
            first = lo + ((root - lo) % TWO_PI)
            while first < hi:
                cuts.append(first)
                first += TWO_PI
    cuts = sorted(cuts)
    total = 0.0
    for u0, u1 in zip(cuts[:-1], cuts[1:], strict=True):
        if u1 - u0 <= 0.0:
            continue
        mid = 0.5 * (u0 + u1)
        if r * math.cos(mid - d) + c > 0.0:
            total += c * (u1 - u0) + r * (math.sin(u1 - d) - math.sin(u0 - d))
    return total


@computes("TH-BETA-SUN")
def face_exposure(
    normal: Sequence[float], beta_deg: float, earth_radius_m: float, orbit_radius_m: float
) -> FaceExposure:
    """TH-BETA-SUN: the orbit-average and the largest solar exposure of a flat face with the
    outward unit normal `normal` in the local-vertical frame."""
    lo, hi = _lit_arc(beta_deg, earth_radius_m, orbit_radius_m)
    r, d, c, _a, _b = _coefficients(normal, beta_deg)
    average = _positive_integral(r, d, c, lo, hi) / TWO_PI
    candidates = [r * math.cos(lo - d) + c, r * math.cos(hi - d) + c]
    first = lo + ((d - lo) % TWO_PI)
    if first <= hi:
        candidates.append(r + c)
    return FaceExposure(
        average,
        max(0.0, *candidates),
        sunlit_fraction(beta_deg, earth_radius_m, orbit_radius_m),
    )


@dataclass(frozen=True)
class PeakInstant:
    u_rad: float  # the orbit angle from noon
    exposures: tuple[float, ...]  # max(0, n . s) of every face at that angle
    total: float  # sum of weight * exposure


def _exposures_at(normals: Sequence[Sequence[float]], beta_deg: float, u: float) -> list[float]:
    s = sun_vector_lvlh(beta_deg, u)
    return [max(0.0, n[0] * s[0] + n[1] * s[1] + n[2] * s[2]) for n in normals]


def peak_instant(
    normals: Sequence[Sequence[float]],
    weights: Sequence[float],
    beta_deg: float,
    earth_radius_m: float,
    orbit_radius_m: float,
    samples: int = 7200,
) -> PeakInstant:
    """The orbit angle, on the sunlit arc, at which the weighted sum of the exposures of the
    faces is largest (the weights are the absorptivity times the area of each face, so the sum is
    the sunlight the spacecraft absorbs per unit of solar flux), found on a fine grid and refined
    by golden-section search around the best sample."""
    lo, hi = _lit_arc(beta_deg, earth_radius_m, orbit_radius_m)
    w = np.asarray(weights, dtype=float)

    def total(u: float) -> float:
        return float(np.dot(w, _exposures_at(normals, beta_deg, u)))

    grid = np.linspace(lo, hi, samples + 1)
    values = [total(float(u)) for u in grid]
    best = int(np.argmax(values))
    a, b = float(grid[max(best - 1, 0)]), float(grid[min(best + 1, samples)])
    ratio = (math.sqrt(5.0) - 1.0) / 2.0
    x1, x2 = b - ratio * (b - a), a + ratio * (b - a)
    f1, f2 = total(x1), total(x2)
    for _ in range(80):
        if f1 < f2:
            a, x1, f1 = x1, x2, f2
            x2 = a + ratio * (b - a)
            f2 = total(x2)
        else:
            b, x2, f2 = x2, x1, f1
            x1 = b - ratio * (b - a)
            f1 = total(x1)
    u_best = 0.5 * (a + b)
    # the refinement can only equal or improve the best sample (and keeps the arc's ends)
    candidates = [(values[best], float(grid[best])), (total(u_best), u_best)]
    value, u_star = max(candidates)
    exposures = _exposures_at(normals, beta_deg, u_star)
    return PeakInstant(u_star % TWO_PI, tuple(exposures), value)
