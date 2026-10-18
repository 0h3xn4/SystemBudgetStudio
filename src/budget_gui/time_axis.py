"""What the time axis of a plot shows: elapsed time, UTC or the orbit number (D-162).

Each axis says where the ticks are (in seconds since the scenario start), what they are called,
and what the axis is called. They are plain Python (no Qt), so they are tested on their own.
"""

from __future__ import annotations

import statistics
from datetime import datetime, timedelta
from typing import Protocol

from budget_core.plots.spec import nice_ticks, time_axis

Ticks = list[tuple[float, str]]
UTC_STEPS_S = (
    60.0,
    120.0,
    300.0,
    600.0,
    900.0,
    1800.0,
    3600.0,
    7200.0,
    10800.0,
    21600.0,
    43200.0,
    86400.0,
    172800.0,
    604800.0,
)
MAX_TICKS = 10


class TimeAxis(Protocol):
    name: str

    def ticks(self, start_s: float, end_s: float) -> Ticks: ...

    def title(self, start_s: float, end_s: float) -> str: ...


def _text(value: float) -> str:
    return f"{value:.6g}"


class ElapsedAxis:
    """Seconds, minutes, hours or days since the scenario start (the default)."""

    name = "elapsed"

    def ticks(self, start_s: float, end_s: float) -> Ticks:
        divisor, _unit = time_axis(end_s - start_s)
        return [
            (tick * divisor, _text(tick))
            for tick in nice_ticks(start_s / divisor, end_s / divisor, 8)
            if start_s - 1e-9 <= tick * divisor <= end_s + 1e-9
        ]

    def title(self, start_s: float, end_s: float) -> str:
        return f"Time since scenario start ({time_axis(end_s - start_s)[1]})"


class UtcAxis:
    """Clock times (UTC) on round minutes, hours or days; midnight carries the date."""

    name = "utc"

    def __init__(self, origin: datetime) -> None:
        self.origin = origin
        self._offset = (
            origin - origin.replace(hour=0, minute=0, second=0, microsecond=0)
        ).total_seconds()

    def _step(self, span_s: float) -> float:
        for step in UTC_STEPS_S:
            if span_s / step <= MAX_TICKS:
                return step
        return UTC_STEPS_S[-1]

    def ticks(self, start_s: float, end_s: float) -> Ticks:
        step = self._step(end_s - start_s)
        # seconds since the scenario start of a round time: round on the UTC clock, not on T+
        first = -(-(start_s + self._offset) // step) * step - self._offset
        found: Ticks = []
        t = first
        while t <= end_s + 1e-6:
            moment = self.origin + timedelta(seconds=t)
            at_midnight = (moment.hour, moment.minute, moment.second) == (0, 0, 0)
            if step >= 86_400.0 or at_midnight:
                label = moment.strftime("%m-%d")
            else:
                label = moment.strftime("%H:%M")
            found.append((t, label))
            t += step
        return found

    def title(self, start_s: float, end_s: float) -> str:
        return "UTC (a date marks midnight)" if end_s - start_s < 7 * 86_400.0 else "UTC date"


class OrbitAxis:
    """Whole orbits counted from 1, the period taken from the spacing of the eclipses."""

    name = "orbit"

    def __init__(self, period_s: float) -> None:
        self.period_s = period_s

    def ticks(self, start_s: float, end_s: float) -> Ticks:
        first = max(int(start_s // self.period_s), 0)
        last = int(end_s // self.period_s)
        every = max(1, -(-(last - first + 1) // MAX_TICKS))
        return [
            (n * self.period_s, str(n + 1))
            for n in range(first, last + 1)
            if n % every == 0 and start_s - 1e-9 <= n * self.period_s <= end_s + 1e-9
        ]

    def title(self, start_s: float, end_s: float) -> str:
        return "Orbit number (from the spacing of the eclipses)"


def orbit_period_s(eclipse_starts_s: list[float]) -> float | None:
    """The orbit period from when the eclipses begin (their median spacing); None when there are
    too few eclipses to tell (fewer than three)."""
    if len(eclipse_starts_s) < 3:
        return None
    gaps = [b - a for a, b in zip(eclipse_starts_s, eclipse_starts_s[1:], strict=False) if b > a]
    return statistics.median(gaps) if gaps else None
