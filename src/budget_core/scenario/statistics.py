"""Statistics of the eclipses and passes of a scenario (2.1.0).

For every scenario: how many eclipses, the shortest, mean and longest, the share of the time in
eclipse and the longest stretch of sunlight; for every site: how many passes, the time in contact,
the largest gap without a pass, and the shortest, mean and longest pass and peak elevation. They
are read from the computed environment, change no result, and give a quick insight while the
inputs are being filled in. An imported pass without a peak elevation is left out of the
elevation figures. A pass cut by the start or the end of the scenario counts with its clipped
length.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from budget_core.environment.beta import BetaStatistics, beta_angle_deg, beta_statistics
from budget_core.environment.constants import EARTH_MODELS
from budget_core.environment.data import EnvironmentData, Pass
from budget_core.environment.ground_track import (
    GroundTrack,
    GroundTrackStatistics,
    ground_track,
    ground_track_statistics,
)
from budget_core.environment.intervals import Interval, merge_intervals


@dataclass(frozen=True)
class DurationStats:
    count: int
    total_s: float
    min_s: float | None
    mean_s: float | None
    max_s: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "total_s": round(self.total_s, 3),
            "min_s": _r(self.min_s),
            "mean_s": _r(self.mean_s),
            "max_s": _r(self.max_s),
        }


@dataclass(frozen=True)
class EclipseStats:
    durations: DurationStats
    fraction: float  # the share of the scenario in eclipse
    longest_sunlight_s: float  # the longest stretch with no eclipse

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.durations.to_dict(),
            "fraction": round(self.fraction, 6),
            "longest_sunlight_s": round(self.longest_sunlight_s, 3),
        }


@dataclass(frozen=True)
class SiteStats:
    site_id: str
    kind: str
    passes: DurationStats
    contact_fraction: float  # the time above the minimum elevation over the scenario
    largest_gap_s: float  # the longest stretch with no pass, the start and the end included
    elevation_min_deg: float | None
    elevation_mean_deg: float | None
    elevation_max_deg: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "site": self.site_id,
            "kind": self.kind,
            "passes": self.passes.to_dict(),
            "contact_fraction": round(self.contact_fraction, 6),
            "largest_gap_s": round(self.largest_gap_s, 3),
            "elevation_min_deg": _r(self.elevation_min_deg),
            "elevation_mean_deg": _r(self.elevation_mean_deg),
            "elevation_max_deg": _r(self.elevation_max_deg),
        }


@dataclass(frozen=True)
class ScenarioStatistics:
    duration_s: float
    eclipses: EclipseStats
    sites: tuple[SiteStats, ...]
    beta: BetaStatistics | None = None  # None: no orbit plane known (nothing to compute from)
    ground_track: GroundTrackStatistics | None = None  # None: no positions

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "duration_s": round(self.duration_s, 3),
            "eclipses": self.eclipses.to_dict(),
            "sites": [s.to_dict() for s in self.sites],
        }
        if self.beta is not None:
            out["beta"] = self.beta.to_dict()
        if self.ground_track is not None:
            out["ground_track"] = self.ground_track.to_dict()
        return out


def _r(value: float | None) -> float | None:
    return None if value is None else round(value, 4)


def duration_stats(durations: Iterable[float]) -> DurationStats:
    values = [float(d) for d in durations]
    if not values:
        return DurationStats(0, 0.0, None, None, None)
    total = sum(values)
    return DurationStats(len(values), total, min(values), total / len(values), max(values))


def largest_gap_s(intervals: Sequence[Interval], span_s: float) -> float:
    """The longest stretch of [0, span_s] that no interval covers. Overlapping intervals count
    once, and the parts of an interval outside the span are ignored."""
    if span_s <= 0.0:
        return 0.0
    clipped = [
        Interval(max(i.start_s, 0.0), min(i.end_s, span_s))
        for i in merge_intervals(list(intervals))
        if i.end_s > 0.0 and i.start_s < span_s
    ]
    gap, cursor = 0.0, 0.0
    for item in clipped:
        gap = max(gap, item.start_s - cursor)
        cursor = max(cursor, item.end_s)
    return max(gap, span_s - cursor)


def site_statistics(site_id: str, kind: str, passes: Sequence[Pass], span_s: float) -> SiteStats:
    intervals = [Interval(p.aos_s, p.los_s) for p in passes]
    durations = duration_stats(p.duration_s for p in passes)
    elevations = [p.max_elevation_deg for p in passes if not math.isnan(p.max_elevation_deg)]
    contact = durations.total_s / span_s if span_s > 0.0 else 0.0
    return SiteStats(
        site_id,
        kind,
        durations,
        contact,
        largest_gap_s(intervals, span_s),
        min(elevations) if elevations else None,
        sum(elevations) / len(elevations) if elevations else None,
        max(elevations) if elevations else None,
    )


def scenario_statistics(
    env: EnvironmentData, track: GroundTrack | None = None
) -> ScenarioStatistics:
    """All the statistics of a computed environment. A caller that already has the ground track
    passes it, so the sub-satellite point is not worked out twice."""
    span = env.grid.duration_s
    eclipses = EclipseStats(
        duration_stats(e.duration_s for e in env.eclipses),
        env.eclipse_fraction,
        largest_gap_s(list(env.eclipses), span),
    )
    sites = tuple(
        site_statistics(site_id, vis.site.kind, vis.passes, span)
        for site_id, vis in sorted(env.sites.items())
    )
    return ScenarioStatistics(span, eclipses, sites, beta_of(env), ground_track_of(env, track))


def beta_series_deg(env: EnvironmentData) -> Any:
    """The beta angle on the scenario grid (NaN where the orbit plane is not known)."""
    if len(env.position_m) == 0:
        return None
    return beta_angle_deg(env.position_m, env.velocity_m_s, env.sun_direction, env.grid.times_s)


def _earth_radius_m(env: EnvironmentData) -> float:
    model = env.earth_model if env.earth_model in EARTH_MODELS else "wgs84"
    return EARTH_MODELS[model].radius_m


def beta_of(env: EnvironmentData) -> BetaStatistics | None:
    series = beta_series_deg(env)
    if series is None:
        return None
    radius = float(np.mean(np.linalg.norm(env.position_m, axis=1)))
    return beta_statistics(series, mean_radius_m=radius, earth_radius_m=_earth_radius_m(env))


def ground_track_of(
    env: EnvironmentData, track: GroundTrack | None = None
) -> GroundTrackStatistics | None:
    track = track or ground_track(env)
    if track is None:
        return None
    return ground_track_statistics(env.grid.times_s, track)
