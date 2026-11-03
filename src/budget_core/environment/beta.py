"""The beta angle (2.2.0, D-227): the angle between the Sun direction and the orbit plane.

beta = asin(h . s) with h the unit angular momentum of the orbit and s the unit vector to the Sun,
positive when the Sun is on the side the orbit normal points to. It runs from -90 to +90 degrees:
near 0 the Sun lies in the orbit plane (the longest eclipses), near 90 the orbit is a terminator
orbit. With the Earth as a cylinder of shadow an orbit of radius r has no eclipse while
|beta| > asin(Re / r), the critical angle. Read from the computed environment; it changes no
result.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

from budget_core.equation_binding import computes

NDArray = np.ndarray[Any, np.dtype[np.float64]]


@computes("ORB-BETA")
def beta_angle_deg(
    position_m: NDArray,
    velocity_m_s: NDArray | None,
    sun_direction: NDArray,
    times_s: NDArray | None = None,
) -> NDArray:
    """ORB-BETA: beta = asin((r x v) / |r x v| . s) for every sample. Without a velocity (an
    imported environment) it is taken from the positions, v = dr/dt on `times_s`."""
    if velocity_m_s is None:
        if times_s is None or len(times_s) < 2:
            return np.full(len(position_m), np.nan)
        velocity_m_s = np.gradient(position_m, times_s, axis=0)
    h = np.cross(position_m, velocity_m_s)
    norm = np.linalg.norm(h, axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        sin_beta = np.sum(h * sun_direction, axis=1) / norm
    return np.asarray(np.degrees(np.arcsin(np.clip(sin_beta, -1.0, 1.0))))


def critical_beta_deg(orbit_radius_m: float, earth_radius_m: float) -> float:
    """The beta angle above which a circular orbit of this radius has no eclipse (cylindrical
    shadow): asin(Re / r)."""
    return math.degrees(math.asin(min(1.0, earth_radius_m / orbit_radius_m)))


@dataclass(frozen=True)
class BetaStatistics:
    min_deg: float
    mean_deg: float
    max_deg: float
    critical_deg: float  # at the mean orbit radius

    def to_dict(self) -> dict[str, float]:
        return {
            "min_deg": round(self.min_deg, 4),
            "mean_deg": round(self.mean_deg, 4),
            "max_deg": round(self.max_deg, 4),
            "critical_deg": round(self.critical_deg, 4),
        }


def beta_statistics(
    beta_deg: NDArray, *, mean_radius_m: float, earth_radius_m: float
) -> BetaStatistics | None:
    """Minimum, mean and maximum of a series and the critical angle; None without a series."""
    finite = beta_deg[np.isfinite(beta_deg)]
    if finite.size == 0:
        return None
    return BetaStatistics(
        float(finite.min()),
        float(finite.mean()),
        float(finite.max()),
        critical_beta_deg(mean_radius_m, earth_radius_m),
    )
