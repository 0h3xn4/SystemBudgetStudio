# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""CSV and JSON of the node temperatures against the beta angle (2.7.0, D-250)."""

from __future__ import annotations

import io
import json
from collections.abc import Sequence
from dataclasses import asdict
from typing import Any

from budget_core.problems import Problem, sort_problems
from budget_core.provenance import Provenance
from budget_core.reports.csvutil import csv_writer, defuse
from budget_core.reports.numfmt import clean_numbers
from budget_core.result_format import result_format
from budget_core.thermal.beta_sweep import BetaPoint, BetaSweep

FIXED_COLUMNS = (
    "beta_deg",
    "sunlit_fraction",
    "orbit_angle_deg",
    "complete",
    "units_exceeded",
    "smallest_upper_headroom_k",
    "smallest_lower_headroom_k",
)


def _nodes(sweep: BetaSweep) -> list[str]:
    return sorted({n.node for p in sweep.points for n in p.case.nodes})


def _headroom(point: BetaPoint, which: str) -> float | None:
    values = [getattr(c, which) for c in point.case.checks if getattr(c, which) is not None]
    return min(values) if values else None


def _exceeded(point: BetaPoint) -> int:
    return sum(1 for c in point.case.checks if c.status == "exceeded")


def _cell(value: float | None) -> str:
    return "" if value is None else f"{value:.6f}"


def beta_csv(sweep: BetaSweep) -> str:
    """One row for each beta angle; an incomplete point has empty temperature cells."""
    nodes = _nodes(sweep)
    handle = io.StringIO()
    writer = csv_writer(handle)
    writer.writerow([*FIXED_COLUMNS, *(f"temperature_{defuse(n)}_k" for n in nodes)])
    for p in sweep.points:
        temps = {n.node: n.temperature_k for n in p.case.nodes}
        writer.writerow(
            [
                f"{p.beta_deg:.6f}",
                f"{p.sunlit_fraction:.6f}",
                _cell(p.u_deg),
                "yes" if p.case.complete else "no",
                _exceeded(p) if p.case.complete else "",
                _cell(_headroom(p, "upper_headroom_k")),
                _cell(_headroom(p, "lower_headroom_k")),
                *(_cell(temps.get(n)) for n in nodes),
            ]
        )
    return handle.getvalue()


def beta_json(
    sweep: BetaSweep, provenance: Provenance, load_problems: Sequence[Problem] = ()
) -> str:
    data: dict[str, Any] = {
        "case": sweep.case,
        "mode": sweep.mode,
        "orbit": {
            "earth_radius_m": sweep.earth_radius_m,
            "orbit_radius_m": sweep.orbit_radius_m,
            "altitude_m": sweep.altitude_m,
            "model": "circular orbit, nadir pointing, flat faces, no thermal capacity",
        },
        "surfaces_from_beta": list(sweep.surfaces_from_beta),
        "surfaces_typed": list(sweep.surfaces_typed),
        "points": [
            {
                "beta_deg": p.beta_deg,
                "sunlit_fraction": p.sunlit_fraction,
                "orbit_angle_deg": p.u_deg,
                "complete": p.case.complete,
                "solar_view_ratio": dict(sorted(p.solar_view.items())),
                "nodes": [
                    {
                        "node": n.node,
                        "temperature_k": n.temperature_k,
                        "dissipation_w": n.dissipation_w,
                        "absorbed_w": n.absorbed_w,
                        "radiated_w": n.radiated_w,
                        "conducted_out_w": n.conducted_out_w,
                    }
                    for n in p.case.nodes
                ],
                "units": [
                    {
                        "unit_id": c.unit_id,
                        "node": c.node,
                        "temperature_k": c.temperature_k,
                        "lower_headroom_k": c.lower_headroom_k,
                        "upper_headroom_k": c.upper_headroom_k,
                        "status": c.status,
                    }
                    for c in p.case.checks
                ],
            }
            for p in sweep.points
        ],
        "problems": [p.to_dict() for p in sort_problems([*load_problems, *sweep.problems])],
        "provenance": asdict(provenance),
        "result_format": result_format("thermal_beta"),
    }
    return json.dumps(clean_numbers(data), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def beta_files(
    sweep: BetaSweep,
    provenance: Provenance,
    load_problems: Sequence[Problem] = (),
    *,
    plots: bool = True,
) -> list[tuple[str, bytes | str]]:
    """The files of one sweep as (name, content): the CSV, the JSON, the provenance CSV and the
    plot. The command line and the window write the same files."""
    from budget_core.plots.render import render_png
    from budget_core.plots.thermal_beta import thermal_beta_plot
    from budget_core.reports.csvutil import provenance_csv

    stem = f"thermal_beta_{sweep.case}_{sweep.mode}"
    incomplete = any(not p.case.complete for p in sweep.points)
    files: list[tuple[str, bytes | str]] = [
        (f"{stem}.csv", "\ufeff" + beta_csv(sweep)),
        (f"{stem}.json", beta_json(sweep, provenance, load_problems)),
        (f"{stem}_provenance.csv", provenance_csv(provenance, incomplete=incomplete)),
    ]
    if plots:
        files.append((f"{stem}.png", render_png(thermal_beta_plot(sweep))))
    return files
