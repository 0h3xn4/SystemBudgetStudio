# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""The plot of node temperatures against the beta angle (2.7.0, D-250)."""

from __future__ import annotations

import numpy as np

from budget_core.plots.spec import BLUE, GREEN, GREY, PURPLE, RED, TEAL, Panel, PlotSpec, Series
from budget_core.thermal.beta_sweep import BetaSweep

_COLORS = (BLUE, RED, GREEN, PURPLE, TEAL, "#b28600", "#ee5396", "#005d5d", GREY)


def thermal_beta_plot(sweep: BetaSweep) -> PlotSpec:
    """One line for each node (kelvin) against the beta angle, and a line for the sunlit part of
    the orbit; only the points the solver could complete are drawn."""
    done = [p for p in sweep.points if p.case.complete]
    x = np.array([p.beta_deg for p in done], dtype=np.float64)
    series = []
    for index, node in enumerate(sorted({n.node for p in done for n in p.case.nodes})):
        y = np.array(
            [next(n.temperature_k for n in p.case.nodes if n.node == node) for p in done],
            dtype=np.float64,
        )
        series.append(Series(node, x, y, _COLORS[index % len(_COLORS)]))
    lit = Series(
        "Sunlit part of the orbit",
        x,
        np.array([p.sunlit_fraction for p in sweep.points if p.case.complete], dtype=np.float64),
        GREY,
    )
    low = float(x.min()) if len(x) else 0.0
    high = float(x.max()) if len(x) else 1.0
    what = "orbit average" if sweep.mode == "average" else "worst instant"
    return PlotSpec(
        f"Node temperatures against the beta angle, case {sweep.case} ({what})",
        (
            Panel("Node temperature", "K", tuple(series)),
            Panel("Sunlit part of the orbit", "ratio", (lit,), y_min=0.0, y_max=1.05),
        ),
        x_min_s=low,
        x_max_s=high if high > low else low + 1.0,
        x_label="Beta angle (deg)",
    )
