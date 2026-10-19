"""The sizes of the painted plots at the UI scale in use (D-178).

The plot and the strips are painted by hand, so their margins cannot come from a style sheet. The
base sizes are in `theme/scale.py`; this makes them whole pixels for the scale in use once, and
again when the theme manager says the scale (or the theme) changed, so a paint that asks for them
for every point of a series pays an attribute read and not a conversion.
"""

from __future__ import annotations

from budget_gui import theme


class PlotMetrics:
    """Margins, gaps and bars of `PlotWidget` (`left` is where the plot area begins)."""

    def __init__(self) -> None:
        self.refresh()

    def refresh(self) -> None:
        left, right, top, bottom = (theme.px(v) for v in theme.PLOT_MARGINS)
        self.left, self.right, self.top, self.bottom = left, right, top, bottom
        self.gap = theme.px(theme.PLOT_GAP)
        self.title = theme.px(theme.PLOT_TITLE)
        self.min_panel = theme.px(theme.PLOT_MIN_PANEL)
        self.marker_bar = theme.px(theme.MARKER_BAR)
        self.marker_hit = theme.px(theme.MARKER_HIT)


class StripMetrics:
    """Margins and rows of the scenario strips."""

    def __init__(self) -> None:
        self.refresh()

    def refresh(self) -> None:
        left, right, top, bottom = (theme.px(v) for v in theme.STRIP_MARGINS)
        self.left, self.right, self.top, self.bottom = left, right, top, bottom
        self.row = theme.px(theme.STRIP_ROW)
        self.gap = theme.px(theme.STRIP_GAP)


PLOT = PlotMetrics()
STRIPS = StripMetrics()


def _refresh() -> None:
    PLOT.refresh()
    STRIPS.refresh()


theme.manager().changed.connect(_refresh)  # first in line: the widgets that repaint come later
