"""A fast min/max envelope for the plot window of the GUI (D-161).

`spec.decimate` reduces a series to what a screen can show, bucket by bucket, in a Python loop: for
a week at 1 s (604,801 samples) and 20 series that is seconds for every pan or zoom. This module
does the same job with NumPy only:

* a series is summarised **once** in blocks of `BLOCK` samples (the smallest and the largest value
  of each block);
* zoomed out (many samples per pixel) the plot window is drawn from those blocks, so the work per
  redraw depends on the width of the window in pixels, not on the number of samples;
* zoomed in (fewer samples per pixel) the visible samples themselves are reduced, with one
  `reshape` and two `argmin`/`argmax` calls instead of a loop.

A series with a missing sample (NaN) keeps the old path, which keeps the gap. The report renderers
still use `spec.plot_points`, so every written figure is unchanged.

The result says whether it is a **polyline** or a list of **pairs**. A reduced series is pairs: the
smallest and the largest value of each bucket, to be drawn as one short line per bucket. (A thick
pen along a polyline that zigzags over the full height of a panel is what made a week of data slow
to draw: about 0.4 s a series; the same picture as separate lines takes 2 ms.)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple

import numpy as np

from budget_core.plots.spec import NDArray, Series, plot_points

BLOCK = 64  # samples summarised by one block
BLOCKS_PER_BUCKET = 2  # use the blocks when a bucket holds at least this many blocks


class Drawn(NamedTuple):
    """What to draw for a series: the coordinates, and whether they are pairs (see the module)."""

    x: NDArray
    y: NDArray
    pairs: bool


@dataclass(frozen=True)
class Blocks:
    """The smallest and largest value of every block of `BLOCK` samples of a series."""

    low: NDArray
    high: NDArray


def summarise(y: NDArray) -> Blocks:
    starts = np.arange(0, len(y), BLOCK)
    return Blocks(np.minimum.reduceat(y, starts), np.maximum.reduceat(y, starts))


def reduce_samples(x: NDArray, y: NDArray, buckets: int) -> tuple[NDArray, NDArray]:
    """The smallest and the largest sample of every bucket, as a pair per bucket in time order
    (finite data). The samples left over after the equal buckets make a last pair."""
    n = len(x)
    size = n // buckets
    if size < 2:
        return x, y
    head = size * buckets
    rows = y[:head].reshape(buckets, size)
    base = np.arange(buckets, dtype=np.int64) * size
    picks = np.stack([base + rows.argmin(axis=1), base + rows.argmax(axis=1)], axis=1)
    picks.sort(axis=1)
    index = picks.reshape(-1)
    if head < n:
        tail = y[head:]
        extra = np.sort(np.array([head + int(tail.argmin()), head + int(tail.argmax())]))
        index = np.concatenate([index, extra])
    return x[index], y[index]


class EnvelopeCache:
    """Summaries of the series of one plot, made the first time a series is drawn."""

    def __init__(self) -> None:
        self._entries: dict[int, tuple[Series, bool, Blocks | None]] = {}

    def clear(self) -> None:
        self._entries.clear()

    def _entry(self, series: Series) -> tuple[bool, Blocks | None]:
        found = self._entries.get(id(series))
        if found is not None and found[0] is series:
            return found[1], found[2]
        finite = bool(np.isfinite(series.y).all())
        blocks = summarise(series.y) if finite and len(series.y) else None
        self._entries[id(series)] = (series, finite, blocks)
        return finite, blocks

    def points(self, series: Series, x_lo: float, x_hi: float, x_max: float, buckets: int) -> Drawn:
        """What to draw for [x_lo, x_hi]: `spec.plot_points` (a polyline) when the window holds
        few samples or a gap, else the reduced pairs, quickly."""
        x, y = series.x, series.y
        first = max(int(np.searchsorted(x, x_lo, side="right")) - 1, 0)
        last = min(int(np.searchsorted(x, x_hi, side="left")) + 1, len(x))
        n = last - first
        finite, blocks = self._entry(series)
        if n <= 2 * buckets or not finite or blocks is None:
            px, py = plot_points(series, x_lo, x_hi, x_max, buckets)  # exact, or keeps the gaps
            return Drawn(px, py, False)
        if n < BLOCK * BLOCKS_PER_BUCKET * buckets + 2 * BLOCK:
            rx, ry = reduce_samples(x[first:last], y[first:last], buckets)
            return Drawn(rx, ry, True)
        bx, by = self._from_blocks(x, y, blocks, first, last, buckets)
        return Drawn(bx, by, True)

    @staticmethod
    def _from_blocks(
        x: NDArray, y: NDArray, blocks: Blocks, first: int, last: int, buckets: int
    ) -> tuple[NDArray, NDArray]:
        lo_block = -(-first // BLOCK)  # the first block that lies wholly inside the window
        hi_block = last // BLOCK
        count = hi_block - lo_block
        buckets = min(buckets, count // BLOCKS_PER_BUCKET)
        edges = np.linspace(0, count, buckets + 1).astype(np.int64)
        starts = edges[:-1]
        low = np.minimum.reduceat(blocks.low[lo_block:hi_block], starts)
        high = np.maximum.reduceat(blocks.high[lo_block:hi_block], starts)
        begin = x[(lo_block + starts) * BLOCK]
        finish = x[np.minimum((lo_block + edges[1:]) * BLOCK - 1, len(x) - 1)]
        px = np.stack([begin, finish], axis=1).reshape(-1)
        py = np.stack([low, high], axis=1).reshape(-1)
        parts_x, parts_y = [px], [py]
        for lo, hi in ((first, lo_block * BLOCK), (hi_block * BLOCK, last)):
            if hi > lo:  # the short stretches at the ends of the window, one pair each
                parts_x.append(np.array([x[lo], x[hi - 1]]))
                parts_y.append(_extremes(y[lo:hi]))
        return np.concatenate(parts_x), np.concatenate(parts_y)


def _extremes(y: NDArray) -> NDArray:
    """The smallest and the largest value of a short stretch (empty for none)."""
    return np.array([y.min(), y.max()]) if len(y) else y
