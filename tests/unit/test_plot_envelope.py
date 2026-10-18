"""The fast envelope of the plot window (D-161): the peaks of the exact reduction, far less work."""

from __future__ import annotations

import time

import numpy as np
import pytest

from budget_core.plots.envelope import BLOCK, EnvelopeCache, reduce_samples, summarise
from budget_core.plots.spec import Series, plot_points

N = 604_801


def week(seed: int = 1) -> Series:
    rng = np.random.default_rng(seed)
    x = np.arange(N, dtype=float)
    y = np.sin(x / 900.0) * 10.0 + rng.normal(0.0, 0.5, N)
    return Series("s", x, y)


def test_a_summary_has_the_smallest_and_largest_value_of_every_block() -> None:
    y = np.arange(200, dtype=float)[::-1].copy()
    blocks = summarise(y)
    assert len(blocks.low) == -(-200 // BLOCK)
    assert blocks.low[0] == y[:BLOCK].min() and blocks.high[0] == y[:BLOCK].max()
    assert blocks.low[-1] == y[-(200 % BLOCK) :].min()  # the last block is the short one


def test_reducing_samples_keeps_the_extremes_of_every_bucket_in_time_order() -> None:
    rng = np.random.default_rng(3)
    x = np.arange(10_000, dtype=float)
    y = rng.normal(size=10_000)
    px, py = reduce_samples(x, y, 100)
    assert np.all(np.diff(px) >= 0) and len(px) == 2 * 100
    size = 10_000 // 100
    for bucket in range(100):
        window = y[bucket * size : (bucket + 1) * size]
        inside = (px >= bucket * size) & (px < (bucket + 1) * size)
        assert py[inside].min() == window.min() and py[inside].max() == window.max()


def test_a_short_window_is_the_exact_polyline() -> None:
    series = week()
    cache = EnvelopeCache()
    a = cache.points(series, 1000.0, 1100.0, float(N - 1), 1100)
    b = plot_points(series, 1000.0, 1100.0, float(N - 1), 1100)
    assert not a.pairs and np.array_equal(a.x, b[0]) and np.array_equal(a.y, b[1])


@pytest.mark.parametrize("window", [(0.0, float(N - 1)), (100_000.0, 400_000.0), (5.0, 300_000.5)])
def test_a_zoomed_out_window_keeps_the_peaks(window: tuple[float, float]) -> None:
    series = week()
    series.y[250_000] = 99.0  # one spike
    series.y[251_111] = -99.0
    cache = EnvelopeCache()
    drawn = cache.points(series, window[0], window[1], float(N - 1), 1100)
    px, py = drawn.x, drawn.y
    assert drawn.pairs and len(px) % 2 == 0
    first = max(int(np.searchsorted(series.x, window[0], side="right")) - 1, 0)
    last = min(int(np.searchsorted(series.x, window[1], side="left")) + 1, N)
    shown = series.y[first:last]
    assert py.max() == shown.max() and py.min() == shown.min()
    assert len(px) <= 2 * 1100 + 4 and len(px) == len(py)
    assert px.min() >= series.x[first] and px.max() <= series.x[last - 1]
    assert np.all(px[1::2] >= px[0::2])  # inside a pair, time runs forward


def test_a_medium_window_is_reduced_from_the_samples() -> None:
    series = week()
    cache = EnvelopeCache()
    drawn = cache.points(series, 0.0, 60_000.0, float(N - 1), 1100)
    assert drawn.pairs and len(drawn.x) <= 2 * 1100 + 2
    assert drawn.y.max() == series.y[:60_002].max()


def test_a_series_with_a_gap_keeps_the_exact_path_and_its_gap() -> None:
    series = week()
    series.y[300_000] = np.nan
    cache = EnvelopeCache()
    a = cache.points(series, 0.0, float(N - 1), float(N - 1), 1100)
    b = plot_points(series, 0.0, float(N - 1), float(N - 1), 1100)
    assert not a.pairs and np.array_equal(a.x, b[0]) and np.array_equal(a.y, b[1], equal_nan=True)
    assert np.isnan(a.y).any()


def test_a_step_series_of_many_samples_is_an_envelope_too() -> None:
    x = np.arange(N, dtype=float)
    y = (x // 5000) % 2
    step = Series("mode", x, y, step=True)
    drawn = EnvelopeCache().points(step, 0.0, float(N - 1), float(N - 1), 1100)
    assert drawn.y.min() == 0.0 and drawn.y.max() == 1.0 and len(drawn.x) <= 2 * 1100 + 4


def test_an_empty_series_and_a_window_outside_it_do_not_fail() -> None:
    empty = Series("e", np.array([]), np.array([]))
    drawn = EnvelopeCache().points(empty, 0.0, 10.0, 10.0, 100)
    assert len(drawn.x) == len(drawn.y) == 0
    series = week()
    drawn = EnvelopeCache().points(series, 1e9, 2e9, float(N - 1), 1100)
    assert len(drawn.x) == len(drawn.y)


def test_the_summary_is_made_once_per_series() -> None:
    series = week()
    cache = EnvelopeCache()
    cache.points(series, 0.0, float(N - 1), float(N - 1), 1100)
    entry = cache._entries[id(series)]
    cache.points(series, 0.0, 1e5, float(N - 1), 1100)
    assert cache._entries[id(series)] is entry
    cache.clear()
    assert not cache._entries


def test_twenty_series_of_a_week_are_reduced_in_a_blink() -> None:
    cache = EnvelopeCache()
    many = [week(i) for i in range(20)]
    for s in many:  # the first look summarises
        cache.points(s, 0.0, float(N - 1), float(N - 1), 1100)
    start = time.perf_counter()
    for k in range(5):  # panning and zooming
        lo = 10_000.0 * k
        for s in many:
            cache.points(s, lo, lo + 400_000.0, float(N - 1), 1100)
    per_view = (time.perf_counter() - start) / 5
    assert per_view < 0.25  # about 0.02 s here; the exact loop needed seconds
