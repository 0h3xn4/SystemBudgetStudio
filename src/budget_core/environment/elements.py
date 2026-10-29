"""ElementsPropagator: TLE or mean elements propagated with sgp4 (no own propagator, spec).

Elements are used as SGP4 mean elements; the semi-major axis becomes mean motion by Kepler's third
law (DEVIATIONS DV-E2). Interval edges are refined by bisection (decision D-057).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
from typing import Any

import numpy as np
from sgp4.api import WGS72, WGS84, Satrec, SatrecArray

from budget_core.environment import geometry as geo
from budget_core.environment.constants import DEFAULT_EARTH_MODEL, EARTH_MODELS
from budget_core.environment.data import (
    EnvironmentData,
    GeometryFn,
    Pass,
    PropagationError,
    SiteDef,
    SiteVisibility,
    TimeGrid,
)
from budget_core.environment.intervals import BoolArray, Interval, bisect_edge, mask_to_intervals
from budget_core.model import Orbit
from budget_core.model.environment import DETECTION_STEP_S, tle_epoch
from budget_core.problems import Problem, Severity
from budget_core.slices import SLICE
from budget_core.timeutil import parse_utc

NDArray = np.ndarray[Any, np.dtype[np.float64]]
# Passes and eclipses are detected on this fixed grid, whatever the scenario step (D-057): a pass
# that rises above its minimum elevation between two samples is found from the local maximum of
# the elevation, and an eclipse or an umbra shorter than the grid from the local maximum of how
# far inside the shadow the satellite is (D-146, DEVIATIONS DV-E4).
LIT = 1.0 - 1e-12
UMBRA = 1e-12
EDGE_TOLERANCE_S = 1e-3


_SGP4_SETS = {"wgs84": WGS84, "wgs72": WGS72}


def build_satrec(orbit: Orbit, earth_model: str = DEFAULT_EARTH_MODEL) -> Satrec:
    """Create the sgp4 satellite record of an orbit definition. Elements use the gravity set of
    `earth_model` (D-219); a TLE is on WGS-72, the set SGP4 is defined on, whatever the choice."""
    if orbit.tle is not None:
        return Satrec.twoline2rv(orbit.tle[0], orbit.tle[1])
    el = orbit.elements
    assert el is not None  # validated: exactly one source
    jd, fr = geo.julian_date_parts(parse_utc(el.epoch_utc))
    motion_rad_per_min = (
        math.sqrt(EARTH_MODELS[earth_model].mu_m3s2 / el.semi_major_axis_m**3) * 60.0
    )
    sat = Satrec()
    sat.sgp4init(
        _SGP4_SETS[earth_model],
        "i",
        1,
        (jd + fr) - 2433281.5,
        0.0,
        0.0,
        0.0,
        el.eccentricity_ratio,
        math.radians(el.arg_perigee_deg),
        math.radians(el.inclination_deg),
        math.radians(el.mean_anomaly_deg),
        motion_rad_per_min,
        math.radians(el.raan_deg),
    )
    return sat


MAX_TLE_AGE_DAYS = 30.0


def orbit_age_problem(
    orbit: Orbit, scenario_start: datetime, orbit_id: str, scenario_id: str
) -> Problem | None:
    """A warning when a TLE's epoch is more than 30 days from the scenario start (a TLE is a fit
    to observations around its epoch; without drag it ages quickly). Elements are the user's
    own reference and have no such age."""
    if orbit.tle is None:
        return None
    epoch = tle_epoch(orbit.tle[0])
    if epoch is None:
        return None
    age_days = abs((scenario_start - epoch).total_seconds()) / 86400.0
    if age_days <= MAX_TLE_AGE_DAYS:
        return None
    return Problem(
        Severity.WARNING,
        "ORBIT_EPOCH_FAR",
        f"The TLE epoch of the orbit used by scenario '{scenario_id}' is more than "
        f"{MAX_TLE_AGE_DAYS:g} days from the scenario start; the orbit may be inaccurate.",
        file=f"orbits/{orbit_id}.yaml",
        path="tle",
        hint="Use a TLE with an epoch close to the scenario start, or elements.",
        actual=age_days,
        limit=MAX_TLE_AGE_DAYS,
        unit="days",
    )


def check_orbit(orbit: Orbit) -> str | None:
    """None if the orbit can be propagated at its own epoch, else a short reason."""
    try:
        sat = build_satrec(orbit)
        error, _, _ = sat.sgp4(sat.jdsatepoch, sat.jdsatepochF)
    except Exception:  # sgp4 raises ValueError for malformed element sets
        return "the element set cannot be read by SGP4"
    return f"SGP4 cannot propagate this orbit at its epoch (error {error})" if error else None


class ElementsPropagator:
    name = "elements"

    def __init__(self, orbit: Orbit, earth_model: str = DEFAULT_EARTH_MODEL) -> None:
        self.orbit = orbit
        # a TLE is on WGS-72 and its geometry stays on the default sphere: the choice does not
        # apply to it (D-219)
        self.earth_model = "tle" if orbit.tle is not None else earth_model
        self.earth_radius_m = EARTH_MODELS[
            DEFAULT_EARTH_MODEL if orbit.tle is not None else earth_model
        ].radius_m
        self.sat = build_satrec(orbit, earth_model)

    # ---- states --------------------------------------------------------------------------------
    def state_teme(self, start: datetime, t_s: float) -> tuple[NDArray, NDArray]:
        """Position (m) and velocity (m/s) in TEME at `t_s` seconds after `start`."""
        jd, fr = geo.julian_date_parts(start + timedelta(seconds=t_s))
        error, r, v = self.sat.sgp4(jd, fr)
        if error:
            raise PropagationError(f"the orbit cannot be propagated (SGP4 error {error})")
        return np.array(r) * 1000.0, np.array(v) * 1000.0

    def _positions(self, start: datetime, times_s: NDArray) -> tuple[NDArray, NDArray]:
        """TEME positions (N, 3) in m and the Julian dates (N,) of a set of times."""
        jd0, fr0 = geo.julian_date_parts(start)
        fractions = fr0 + times_s / 86400.0
        satellites = SatrecArray([self.sat])
        parts = []
        for first in range(0, len(times_s), SLICE):  # one call over a week holds the lock 0.4 s
            part = fractions[first : first + SLICE]
            error, pos, _ = satellites.sgp4(np.full(len(part), jd0), part)
            if np.any(error):
                raise PropagationError("the orbit cannot be propagated over the whole scenario")
            parts.append(np.asarray(pos[0]))
        positions = np.concatenate(parts) if parts else np.empty((0, 3))
        return positions * 1000.0, jd0 + fractions

    # ---- environment ---------------------------------------------------------------------------
    def compute(
        self, grid: TimeGrid, sites: Sequence[SiteDef], shadow_model: str
    ) -> EnvironmentData:
        times = grid.times_s
        pos, jd = self._positions(grid.start, times)
        sun_dir, sun_dist = geo.sun_direction_and_distance(jd)
        ratio = geo.sun_visibility(
            pos, sun_dir * sun_dist[:, None], shadow_model, self.earth_radius_m
        )

        def sun_state(t: float) -> tuple[NDArray, NDArray]:
            r, _ = self.state_teme(grid.start, t)
            jd_t = np.array([sum(geo.julian_date_parts(grid.start + timedelta(seconds=t)))])
            d, dist = geo.sun_direction_and_distance(jd_t)
            return r[None, :], d * dist[:, None]

        def nu_at(t: float) -> float:
            return float(geo.sun_visibility(*sun_state(t), shadow_model, self.earth_radius_m)[0])

        def eclipse_margin_at(t: float) -> float:
            return float(geo.shadow_margins(*sun_state(t), shadow_model, self.earth_radius_m)[0][0])

        def umbra_margin_at(t: float) -> float:
            return float(geo.shadow_margins(*sun_state(t), shadow_model, self.earth_radius_m)[1][0])

        detect = _detection_times(grid)
        det_pos, det_jd = self._positions(grid.start, detect)
        det_dir, det_dist = geo.sun_direction_and_distance(det_jd)
        det_ratio = geo.sun_visibility(
            det_pos, det_dir * det_dist[:, None], shadow_model, self.earth_radius_m
        )
        eclipse_margin, umbra_margin = geo.shadow_margins(
            det_pos, det_dir * det_dist[:, None], shadow_model, self.earth_radius_m
        )
        in_eclipse = det_ratio < LIT
        in_umbra = det_ratio <= UMBRA

        def eclipsed(t: float) -> bool:
            return nu_at(t) < LIT

        def umbral(t: float) -> bool:
            return nu_at(t) <= UMBRA

        eclipses = sorted(
            _intervals(detect, in_eclipse, eclipsed, grid.duration_s)
            + _short_intervals(detect, eclipse_margin, in_eclipse, eclipse_margin_at, eclipsed),
            key=lambda i: i.start_s,
        )
        umbras = sorted(
            _intervals(detect, in_umbra, umbral, grid.duration_s)
            + _short_intervals(detect, umbra_margin, in_umbra, umbra_margin_at, umbral),
            key=lambda i: i.start_s,
        )

        visibility: dict[str, SiteVisibility] = {}
        gmst = geo.gmst_rad(jd)
        det_gmst = geo.gmst_rad(det_jd)
        for site in sites:
            site_ecef = geo.geodetic_to_ecef(site.latitude_deg, site.longitude_deg, site.altitude_m)

            def elevation_at(t: float, _site: SiteDef = site, _ecef: NDArray = site_ecef) -> float:
                r, _ = self.state_teme(grid.start, t)
                jd_t = np.array([sum(geo.julian_date_parts(grid.start + timedelta(seconds=t)))])
                ecef = geo.eci_to_ecef(r[None, :], geo.gmst_rad(jd_t))
                el, _, _ = geo.topocentric(ecef, _ecef, _site.latitude_deg, _site.longitude_deg)
                return float(el[0])

            det_ecef = geo.eci_to_ecef(det_pos, det_gmst)
            det_el, _, _ = geo.topocentric(
                det_ecef, site_ecef, site.latitude_deg, site.longitude_deg
            )
            passes = _passes(detect, det_el, site.min_elevation_deg, elevation_at, grid.duration_s)
            el, az, rng = geo.topocentric(
                geo.eci_to_ecef(pos, gmst), site_ecef, site.latitude_deg, site.longitude_deg
            )
            visibility[site.site_id] = SiteVisibility(
                site,
                tuple(passes),
                el,
                az,
                rng,
                self._geometry_function(grid, site, site_ecef),
            )

        return EnvironmentData(
            grid=grid,
            source=self.name,
            shadow_model=shadow_model,
            earth_model=self.earth_model,
            sun_distance_m=sun_dist,
            position_m=pos,
            sun_direction=sun_dir,
            sunlight_ratio=ratio,
            eclipses=tuple(eclipses),
            umbras=tuple(umbras),
            sites=visibility,
        )

    def _geometry_function(self, grid: TimeGrid, site: SiteDef, site_ecef: NDArray) -> GeometryFn:
        """Elevation, azimuth and range of the site at any times (the same arithmetic as the
        grid arrays, so the two agree at the grid times)."""

        def geometry(times_s: NDArray) -> tuple[NDArray, NDArray, NDArray]:
            pos, jd = self._positions(grid.start, np.asarray(times_s, dtype=np.float64))
            ecef = geo.eci_to_ecef(pos, geo.gmst_rad(jd))
            return geo.topocentric(ecef, site_ecef, site.latitude_deg, site.longitude_deg)

        return geometry


def _detection_times(grid: TimeGrid) -> NDArray:
    times = np.arange(0.0, grid.duration_s, DETECTION_STEP_S)
    return np.append(times, grid.duration_s)


def _edges(
    detect: NDArray,
    mask: BoolArray,
    predicate: Callable[[float], bool],
    duration_s: float,
) -> list[tuple[float, float, bool, bool]]:
    """(start, end, partial_start, partial_end) of the runs of `mask`, edges refined."""
    out = []
    for start, end in mask_to_intervals(detect, mask):
        s = 0.0 if start is None else bisect_edge(predicate, start[0], start[1], EDGE_TOLERANCE_S)
        e = duration_s if end is None else bisect_edge(predicate, end[0], end[1], EDGE_TOLERANCE_S)
        out.append((s, e, start is None, end is None))
    return out


def _intervals(
    detect: NDArray, mask: BoolArray, predicate: Callable[[float], bool], duration_s: float
) -> list[Interval]:
    return [Interval(s, e) for s, e, _, _ in _edges(detect, mask, predicate, duration_s)]


def _short_intervals(
    detect: NDArray,
    margin: NDArray,
    mask: BoolArray,
    margin_at: Callable[[float], float],
    predicate: Callable[[float], bool],
) -> list[Interval]:
    """Shadows (or umbras) that begin and end between two detection samples. `margin` is how far
    inside the shadow the satellite is (positive inside, see `geo.shadow_margins`). Each local
    maximum of the sampled margin whose neighbours are all outside the shadow, and that could
    still reach it, is refined on its two intervals; an interval found there is as exact as any
    other (edges to about 1 ms)."""
    out: list[Interval] = []
    for k in range(1, len(detect) - 1):
        if mask[k - 1] or mask[k] or mask[k + 1]:
            continue
        if not (margin[k] >= margin[k - 1] and margin[k] > margin[k + 1]):
            continue
        before, after = float(detect[k - 1]), float(detect[k + 1])
        # the margin cannot rise much faster than it did over the two intervals
        rate = max(
            abs(margin[k] - margin[k - 1]) / (detect[k] - detect[k - 1]),
            abs(margin[k + 1] - margin[k]) / (detect[k + 1] - detect[k]),
        )
        if margin[k] + rate * (after - before) < 0.0:
            continue
        t_max, _ = _maximise(margin_at, before, after)
        if not predicate(t_max) or predicate(before) or predicate(after):
            continue
        start = bisect_edge(predicate, before, t_max, EDGE_TOLERANCE_S)
        end = bisect_edge(predicate, t_max, after, EDGE_TOLERANCE_S)
        out.append(Interval(start, end))
    return out


def _passes(
    detect: NDArray,
    elevation: NDArray,
    min_elevation: float,
    elevation_at: Callable[[float], float],
    duration_s: float,
) -> list[Pass]:
    mask = elevation >= min_elevation
    out: list[Pass] = []
    for start, end, partial_start, partial_end in _edges(
        detect, mask, lambda t: elevation_at(t) >= min_elevation, duration_s
    ):
        inside = (detect >= start) & (detect <= end)
        k = int(np.argmax(np.where(inside, elevation, -np.inf)))
        lo = float(detect[max(k - 1, 0)])
        hi = float(detect[min(k + 1, len(detect) - 1)])
        t_max, el_max = _maximise(elevation_at, max(lo, start), min(hi, end))
        out.append(Pass(start, end, max(el_max, min_elevation), t_max, partial_start, partial_end))
    out += _short_passes(detect, elevation, mask, min_elevation, elevation_at)
    return sorted(out, key=lambda p: p.aos_s)


def _short_passes(
    detect: NDArray,
    elevation: NDArray,
    mask: BoolArray,
    min_elevation: float,
    elevation_at: Callable[[float], float],
) -> list[Pass]:
    """Passes that rise above the minimum elevation between two detection samples. Each local
    maximum of the sampled elevation that could still reach the minimum is refined on its two
    intervals; a pass found there is as exact as any other (edges to about 1 ms)."""
    out: list[Pass] = []
    for k in range(1, len(detect) - 1):
        if mask[k - 1] or mask[k] or mask[k + 1]:
            continue
        if not (elevation[k] >= elevation[k - 1] and elevation[k] > elevation[k + 1]):
            continue
        before, after = float(detect[k - 1]), float(detect[k + 1])
        # the elevation cannot rise much faster than it did over the two intervals
        rate = max(
            abs(elevation[k] - elevation[k - 1]) / (detect[k] - detect[k - 1]),
            abs(elevation[k + 1] - elevation[k]) / (detect[k + 1] - detect[k]),
        )
        if elevation[k] + rate * (after - before) < min_elevation:
            continue
        t_max, el_max = _maximise(elevation_at, before, after)
        if el_max < min_elevation:
            continue

        def above(t: float) -> bool:
            return elevation_at(t) >= min_elevation

        start = bisect_edge(above, before, t_max, EDGE_TOLERANCE_S)
        end = bisect_edge(above, t_max, after, EDGE_TOLERANCE_S)
        out.append(Pass(start, end, el_max, t_max, False, False))
    return out


def _maximise(f: Callable[[float], float], lo: float, hi: float) -> tuple[float, float]:
    """Golden-section search for the maximum of a unimodal function on [lo, hi]."""
    ratio = (math.sqrt(5.0) - 1.0) / 2.0
    c, d = hi - ratio * (hi - lo), lo + ratio * (hi - lo)
    fc, fd = f(c), f(d)
    while hi - lo > 1e-2:
        if fc > fd:
            hi, d, fd = d, c, fc
            c = hi - ratio * (hi - lo)
            fc = f(c)
        else:
            lo, c, fc = c, d, fd
            d = lo + ratio * (hi - lo)
            fd = f(d)
    t = 0.5 * (lo + hi)
    return t, f(t)
