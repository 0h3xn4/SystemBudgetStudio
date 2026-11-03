"""The ground track (2.2.0, D-232): the sub-satellite point over the scenario.

The inertial (TEME) positions of the environment are turned to Earth-fixed by the same rotation
about the polar axis as the stations' geometry (ENV-GMST, no polar motion) and then to WGS-84
geodetic latitude, longitude and height (ENV-SUBPOINT). The statistics give the latitude range,
the ascending equator crossings and the shift of the longitude between them: the quantities a
mission designer reads off a ground track. Read from the computed environment; it changes no
result.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from budget_core.environment import geometry as geo
from budget_core.environment.data import EnvironmentData
from budget_core.equation_binding import computes

NDArray = np.ndarray[Any, np.dtype[np.float64]]


@computes("ENV-SUBPOINT")
def ecef_to_geodetic(r_ecef: NDArray) -> tuple[NDArray, NDArray, NDArray]:
    """ENV-SUBPOINT: Earth-fixed Cartesian metres to WGS-84 geodetic latitude and longitude
    (degrees, east positive, -180 to 180) and height above the ellipsoid (m). The latitude is
    found by the fixed-point iteration of the textbook relation
    tan(phi) = (z + e2 N sin(phi)) / p, which gains a factor e2 (0.0067) per step (four steps
    leave under a tenth of a millimetre); the height is taken from the form that is stable at
    the poles."""
    a = geo.EARTH_RADIUS_M
    e2 = geo.EARTH_FLATTENING * (2.0 - geo.EARTH_FLATTENING)
    x, y, z = r_ecef[:, 0], r_ecef[:, 1], r_ecef[:, 2]
    p = np.hypot(x, y)
    lat = np.arctan2(z, p * (1.0 - e2))
    for _ in range(4):
        sin_lat = np.sin(lat)
        n = a / np.sqrt(1.0 - e2 * sin_lat**2)
        lat = np.arctan2(z + e2 * n * sin_lat, p)
    sin_lat, cos_lat = np.sin(lat), np.cos(lat)
    height = p * cos_lat + z * sin_lat - a * np.sqrt(1.0 - e2 * sin_lat**2)
    return (
        np.asarray(np.degrees(lat)),
        np.asarray(np.degrees(np.arctan2(y, x))),
        np.asarray(height),
    )


@dataclass(frozen=True, eq=False)
class GroundTrack:
    latitude_deg: NDArray
    longitude_deg: NDArray
    altitude_m: NDArray


def ground_track(env: EnvironmentData) -> GroundTrack | None:
    """The sub-satellite point on the scenario grid; None for an environment without positions."""
    if len(env.position_m) == 0:
        return None
    whole, fraction = geo.julian_date_parts(env.grid.start)
    jd = whole + fraction + np.asarray(env.grid.times_s, dtype=np.float64) / 86400.0
    r_ecef = geo.eci_to_ecef(env.position_m, geo.gmst_rad(jd))
    lat, lon, alt = ecef_to_geodetic(r_ecef)
    return GroundTrack(lat, lon, alt)


@dataclass(frozen=True)
class Crossing:
    time_s: float
    longitude_deg: float
    ascending: bool


def _wrap_deg(delta: float) -> float:
    return (delta + 180.0) % 360.0 - 180.0


def equator_crossings(
    times_s: Sequence[float] | NDArray, latitude_deg: NDArray, longitude_deg: NDArray
) -> list[Crossing]:
    """The times and longitudes at which the latitude changes sign, by linear interpolation
    between the two samples around it; a longitude is interpolated through the date line."""
    out: list[Crossing] = []
    for k in range(len(latitude_deg) - 1):
        a, b = float(latitude_deg[k]), float(latitude_deg[k + 1])
        if a < 0.0 <= b:
            ascending = True
        elif a >= 0.0 > b:
            ascending = False
        else:
            continue
        fraction = -a / (b - a)
        t = float(times_s[k]) + fraction * (float(times_s[k + 1]) - float(times_s[k]))
        lon0, lon1 = float(longitude_deg[k]), float(longitude_deg[k + 1])
        lon = _wrap_deg(lon0 + fraction * _wrap_deg(lon1 - lon0))
        out.append(Crossing(t, lon, ascending))
    return out


@dataclass(frozen=True)
class GroundTrackStatistics:
    min_latitude_deg: float
    max_latitude_deg: float
    ascending_nodes: int
    # mean shift of the longitude from one ascending node to the next (east positive; a low
    # orbit's is about -24 degrees), and the mean time between them (the nodal period); None
    # with fewer than two ascending nodes
    mean_node_shift_deg: float | None
    mean_node_spacing_s: float | None

    def to_dict(self) -> dict[str, Any]:
        def r(value: float | None, digits: int) -> float | None:
            return None if value is None else round(value, digits)

        return {
            "min_latitude_deg": round(self.min_latitude_deg, 4),
            "max_latitude_deg": round(self.max_latitude_deg, 4),
            "ascending_nodes": self.ascending_nodes,
            "mean_node_shift_deg": r(self.mean_node_shift_deg, 4),
            "mean_node_spacing_s": r(self.mean_node_spacing_s, 3),
        }


def ground_track_statistics(
    times_s: Sequence[float] | NDArray, track: GroundTrack
) -> GroundTrackStatistics:
    nodes = [
        c
        for c in equator_crossings(times_s, track.latitude_deg, track.longitude_deg)
        if c.ascending
    ]
    shifts = [
        _wrap_deg(b.longitude_deg - a.longitude_deg) for a, b in zip(nodes, nodes[1:], strict=False)
    ]
    gaps = [b.time_s - a.time_s for a, b in zip(nodes, nodes[1:], strict=False)]
    return GroundTrackStatistics(
        float(np.min(track.latitude_deg)),
        float(np.max(track.latitude_deg)),
        len(nodes),
        math.fsum(shifts) / len(shifts) if shifts else None,
        math.fsum(gaps) / len(gaps) if gaps else None,
    )
