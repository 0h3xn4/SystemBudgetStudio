# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""The plot of the beta angle of a scenario (2.2.0, D-227)."""

from __future__ import annotations

import numpy as np

from budget_core.environment.data import EnvironmentData
from budget_core.plots.spec import BLUE, GREY, HLine, Panel, PlotSpec, Series
from budget_core.scenario.statistics import beta_of, beta_series_deg


def beta_plot(env: EnvironmentData) -> PlotSpec | None:
    """The beta angle against time with the critical angle above which a circular orbit of the
    mean radius has no eclipse; None when the orbit plane is not known."""
    series = beta_series_deg(env)
    stats = beta_of(env)
    if series is None or stats is None:
        return None
    times = np.asarray(env.grid.times_s, dtype=np.float64)
    panel = Panel(
        "Beta angle",
        "deg",
        (Series("Beta angle", times, np.asarray(series, dtype=np.float64), BLUE),),
        hlines=(
            HLine("Critical beta (no eclipse above)", stats.critical_deg, GREY),
            HLine("Critical beta (no eclipse below)", -stats.critical_deg, GREY),
        ),
        y_min=-90.0,
        y_max=90.0,
    )
    return PlotSpec("Beta angle", (panel,), x_min_s=0.0, x_max_s=float(env.grid.duration_s))
