"""Renderer-independent plot description shared by the GUI widget and the report renderer.

A plot has stacked panels with a common time axis, step or line series, horizontal limit lines
and shaded bands (eclipses, passes). Series are NumPy arrays; `decimate` reduces them to what a
screen or a page can show without losing peaks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

NDArray = np.ndarray[Any, np.dtype[np.float64]]

# Carbon palette (IBM Design Language) used by every renderer.
INK = "#161616"
BLUE = "#0f62fe"
RED = "#da1e28"
GREEN = "#198038"
PURPLE = "#8a3ffc"
TEAL = "#007d79"
GREY = "#8d8d8d"
BAND_ECLIPSE = "#c6c6c6"
BAND_COLORS = ("#a6c8ff", "#9ef0f0", "#d4bbff", "#ffd6e8", "#ffd9be")


@dataclass(frozen=True, eq=False)
class Series:
    label: str
    x: NDArray
    y: NDArray
    color: str = BLUE
    step: bool = False  # y[i] holds from x[i] to x[i + 1] (the last value to `x_end`)
    x_end: float | None = None


@dataclass(frozen=True)
class HLine:
    label: str
    y: float
    color: str = RED


@dataclass(frozen=True)
class Band:
    label: str
    intervals: tuple[tuple[float, float], ...]
    color: str = BAND_ECLIPSE


@dataclass(frozen=True)
class Panel:
    title: str
    y_label: str
    series: tuple[Series, ...]
    hlines: tuple[HLine, ...] = ()
    y_min: float | None = None
    y_max: float | None = None
    y_scale: float = 1.0  # displayed value = data * y_scale (for example 100 for percent)


@dataclass(frozen=True)
class PlotSpec:
    title: str
    panels: tuple[Panel, ...]
    bands: tuple[Band, ...] = field(default_factory=tuple)
    x_min_s: float = 0.0
    x_max_s: float = 1.0


def time_axis(span_s: float) -> tuple[float, str]:
    """(divisor, unit label) for a time axis of the given span: seconds, minutes, hours, days."""
    if span_s <= 600.0:
        return 1.0, "s"
    if span_s <= 3 * 3600.0:
        return 60.0, "min"
    if span_s <= 3 * 86400.0:
        return 3600.0, "h"
    return 86400.0, "days"


def nice_ticks(lo: float, hi: float, target: int = 6) -> list[float]:
    """Round tick values covering [lo, hi] (1, 2 or 5 times a power of ten)."""
    if hi <= lo:
        return [lo]
    raw = (hi - lo) / max(target, 1)
    magnitude = 10.0 ** np.floor(np.log10(raw))
    step = magnitude
    for factor in (1.0, 2.0, 5.0, 10.0):
        step = factor * magnitude
        if step >= raw:
            break
    first = np.ceil(lo / step - 1e-9) * step
    count = int(np.floor((hi - first) / step + 1e-9)) + 1
    return [float(first + i * step) for i in range(max(count, 1))]


def tick_labels(ticks: list[float]) -> list[str]:
    """Labels for evenly spaced ticks with one number of decimals, enough to tell them apart
    (0.010, 0.015, 0.020, ...); very large or very small values use exponent notation."""
    if not ticks:
        return []
    largest = max(abs(t) for t in ticks)
    smallest = min((abs(t) for t in ticks if t != 0.0), default=1.0)
    if largest >= 1e6 or smallest < 1e-4:
        return [_no_minus_zero(f"{t:.3g}") for t in ticks]
    step = abs(ticks[1] - ticks[0]) if len(ticks) > 1 else smallest
    decimals = 0 if step >= 1.0 else min(int(np.ceil(-np.log10(step) - 1e-9)), 8)
    frac = step * 10**decimals % 1.0
    if step < 1.0 and min(frac, 1.0 - frac) > 1e-6:  # a step such as 0.25 needs one place more
        decimals += 1
    return [_no_minus_zero(f"{t:.{decimals}f}") for t in ticks]


def _no_minus_zero(text: str) -> str:
    return text[1:] if text.startswith("-") and float(text) == 0.0 else text


def finite_runs(x: NDArray, y: NDArray) -> list[tuple[NDArray, NDArray]]:
    """The stretches of consecutive samples where both coordinates are finite. A line is drawn
    through each stretch, never across a missing sample; a stretch of one sample is a marker."""
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.all():
        return [(x, y)] if len(x) else []
    edges = np.flatnonzero(np.diff(np.concatenate(([0], ok.astype(np.int8), [0]))))
    return [(x[a:b], y[a:b]) for a, b in zip(edges[::2], edges[1::2], strict=True)]


def decimate(x: NDArray, y: NDArray, buckets: int) -> tuple[NDArray, NDArray]:
    """Keep the minimum and the maximum of every bucket, in time order, so peaks survive (and the
    first missing sample of a bucket, so a gap survives). Series with at most 2 * buckets points
    are returned unchanged."""
    n = len(x)
    if n <= 2 * buckets:
        return x, y
    edges = np.linspace(0, n, buckets + 1).astype(np.int64)
    keep: list[int] = []
    for a, b in zip(edges[:-1], edges[1:], strict=True):
        if b <= a:
            continue
        window = y[a:b]
        finite = np.isfinite(window)
        if not finite.any():
            keep.append(int(a))  # all missing: one NaN keeps the gap
            continue
        masked = np.where(finite, window, np.nan)
        picks = {int(np.nanargmin(masked)) + a, int(np.nanargmax(masked)) + a}
        if not finite.all():
            picks.add(int(np.argmin(finite)) + a)  # the first missing sample
        keep.extend(sorted(picks))
    index = np.array(keep, dtype=np.int64)
    return x[index], y[index]


def step_points(series: Series, x_max: float) -> tuple[NDArray, NDArray]:
    """Polyline of a step series: a horizontal run per value, joined by vertical risers."""
    if not series.step:
        return series.x, series.y
    end = series.x_end if series.x_end is not None else x_max
    xs = np.append(series.x, end)
    px = np.repeat(xs, 2)[1:-1]
    py = np.repeat(series.y, 2)
    return px, py


def plot_points(
    series: Series, x_lo: float, x_hi: float, x_max: float, buckets: int
) -> tuple[NDArray, NDArray]:
    """The polyline to draw for the window [x_lo, x_hi]. Zoomed out (many samples per pixel) it is
    the min/max envelope; zoomed in it is the exact step or line."""
    x, y = series.x, series.y
    first = max(int(np.searchsorted(x, x_lo, side="right")) - 1, 0)
    last = min(int(np.searchsorted(x, x_hi, side="left")) + 1, len(x))
    xs, ys = x[first:last], y[first:last]
    if len(xs) > 2 * buckets:
        return decimate(xs, ys, buckets)
    end = float(x[last]) if last < len(x) else (series.x_end if series.x_end is not None else x_max)
    window = Series(series.label, xs, ys, series.color, series.step, end)
    return step_points(window, x_max)


def value_at(series: Series, t: float, x_max: float) -> float | None:
    """The series value at time `t` (a step series holds its value; a line is interpolated);
    None outside the series."""
    x, y = series.x, series.y
    if len(x) == 0 or t < float(x[0]):
        return None
    if series.step:
        end = series.x_end if series.x_end is not None else x_max
        if t > end:
            return None
        return float(y[min(int(np.searchsorted(x, t, side="right")) - 1, len(y) - 1)])
    if t > float(x[-1]):
        return None
    return float(np.interp(t, x, y))


def visible_range(values: list[NDArray], lo: float | None, hi: float | None) -> tuple[float, float]:
    if lo is not None and hi is not None:
        return lo, hi
    finite = [v[np.isfinite(v)] for v in values if len(v)]
    finite = [v for v in finite if len(v)]
    if not finite:
        a, b = 0.0, 1.0
    else:
        a = float(min(v.min() for v in finite))
        b = float(max(v.max() for v in finite))
    if lo is not None:
        a = lo
    if hi is not None:
        b = hi
    if b - a < 1e-12:
        b = a + 1.0
    pad = 0.06 * (b - a)
    return (a if lo is not None else a - pad), (b if hi is not None else b + pad)
