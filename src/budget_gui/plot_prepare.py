"""Everything a plot needs before its first paint, worked out in the worker thread (D-182).

The first paint of a week at 1 s scans 600,000 samples per series for the y range and summarises
each series in blocks (`budget_core.plots.envelope`). Done in the worker, right after the numbers,
the window thread only draws. This module has no Qt import: a worker thread calls it.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from budget_core.plots.envelope import EnvelopeCache
from budget_core.plots.spec import Panel, PlotSpec, visible_range


def panel_y_range(panel: Panel) -> tuple[float, float]:
    """The y range of a panel, in displayed units. It depends on the data only (not on the view)."""
    lo, hi = visible_range(
        [s.y * panel.y_scale for s in panel.series]
        + [np.array([h.y * panel.y_scale]) for h in panel.hlines],
        None if panel.y_min is None else panel.y_min * panel.y_scale,
        None if panel.y_max is None else panel.y_max * panel.y_scale,
    )
    if hi - lo <= 0.0:  # equal fixed limits would divide by zero when drawing
        hi = lo + 1.0
    return lo, hi


@dataclass
class PreparedPlot:
    """A plot description with what the widget would otherwise work out on first paint. The widget
    takes it over; it must not be changed by the thread that made it afterwards."""

    spec: PlotSpec
    ranges: dict[int, tuple[float, float]]  # id(panel) -> y range
    envelopes: EnvelopeCache


def prepare(spec: PlotSpec) -> PreparedPlot:
    envelopes = EnvelopeCache()
    ranges: dict[int, tuple[float, float]] = {}
    for panel in spec.panels:
        ranges[id(panel)] = panel_y_range(panel)
        for series in panel.series:
            envelopes.warm(series)
    return PreparedPlot(spec, ranges, envelopes)
