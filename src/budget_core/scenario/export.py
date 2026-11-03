"""Scenario outputs: environment JSON and CSV tables (deterministic, LF, fixed decimals)."""

from __future__ import annotations

import io
import json
import math
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import Any

import numpy as np

from budget_core.environment.ground_track import ground_track
from budget_core.provenance import Provenance
from budget_core.reports.csvutil import csv_writer, provenance_csv
from budget_core.reports.files import write_file
from budget_core.result_format import result_format
from budget_core.scenario.run import ScenarioRun, run_parameters
from budget_core.scenario.statistics import beta_series_deg, scenario_statistics
from budget_core.timeutil import format_utc


def _t(run: ScenarioRun, seconds: float) -> str:
    return format_utc(run.env.grid.start + timedelta(seconds=seconds))


def _s(value: float) -> str:
    return "" if value != value else f"{value:.3f}"  # NaN: unknown (an imported pass has no peak)


def _csv(header: list[str], rows: list[list[str]]) -> str:
    buffer = io.StringIO()
    writer = csv_writer(buffer)
    writer.writerow(header)
    writer.writerows(rows)
    return buffer.getvalue()


def eclipses_csv(run: ScenarioRun) -> str:
    return _csv(
        ["start_s", "end_s", "duration_s", "start_utc", "end_utc"],
        [
            [_s(e.start_s), _s(e.end_s), _s(e.duration_s), _t(run, e.start_s), _t(run, e.end_s)]
            for e in run.env.eclipses
        ],
    )


def passes_csv(run: ScenarioRun) -> str:
    rows = []
    for site_id, vis in sorted(run.env.sites.items()):
        for p in vis.passes:
            rows.append(
                [
                    site_id,
                    vis.site.kind,
                    _s(p.aos_s),
                    _s(p.los_s),
                    _s(p.duration_s),
                    f"{p.max_elevation_deg:.4f}",
                    _s(p.time_of_max_s),
                    _t(run, p.aos_s),
                    _t(run, p.los_s),
                    str(p.partial_start).lower(),
                    str(p.partial_end).lower(),
                ]
            )
    return _csv(
        [
            "site",
            "kind",
            "aos_s",
            "los_s",
            "duration_s",
            "max_elevation_deg",
            "time_of_max_s",
            "aos_utc",
            "los_utc",
            "partial_start",
            "partial_end",
        ],
        rows,
    )


BETA_CSV_SAMPLE_S = 600.0  # the rows of the beta angle file: no finer than this (settings.py)


def beta_csv(run: ScenarioRun) -> str | None:
    """The beta angle over the scenario, one row every ten minutes or every step if that is
    longer, the last time included; None when the orbit plane is not known."""
    series = beta_series_deg(run.env)
    if series is None or not np.isfinite(series).any():
        return None
    grid = run.env.grid
    stride = max(1, math.ceil(BETA_CSV_SAMPLE_S / grid.step_s))
    picks = sorted(set(range(0, len(series), stride)) | {len(series) - 1})
    times = grid.times_s
    return _csv(
        ["time_s", "utc", "beta_deg"],
        [
            [f"{times[k]:.3f}", _t(run, float(times[k])), f"{series[k]:.4f}"]
            for k in picks
            if np.isfinite(series[k])
        ],
    )


GROUND_TRACK_CSV_SAMPLE_S = 60.0  # the rows of the ground track file: no finer than this


def ground_track_csv(run: ScenarioRun) -> str | None:
    """The sub-satellite point (geodetic latitude, longitude east positive, height above the
    WGS-84 ellipsoid), one row every minute or every step if that is longer, the last time
    included; None for an environment without positions."""
    track = ground_track(run.env)
    if track is None:
        return None
    grid = run.env.grid
    stride = max(1, math.ceil(GROUND_TRACK_CSV_SAMPLE_S / grid.step_s))
    picks = sorted(set(range(0, len(track.latitude_deg), stride)) | {len(track.latitude_deg) - 1})
    times = grid.times_s
    return _csv(
        ["time_s", "utc", "latitude_deg", "longitude_deg", "altitude_m"],
        [
            [
                f"{times[k]:.3f}",
                _t(run, float(times[k])),
                f"{track.latitude_deg[k]:.5f}",
                f"{track.longitude_deg[k]:.5f}",
                f"{track.altitude_m[k]:.1f}",
            ]
            for k in picks
        ],
    )


def timeline_csv(run: ScenarioRun) -> str:
    return _csv(
        ["start_s", "end_s", "duration_s", "mode", "start_utc", "end_utc"],
        [
            [
                _s(s.start_s),
                _s(s.end_s),
                _s(s.duration_s),
                s.mode,
                _t(run, s.start_s),
                _t(run, s.end_s),
            ]
            for s in run.timeline
        ],
    )


def environment_json(run: ScenarioRun, provenance: Provenance) -> str:
    env = run.env
    data: dict[str, Any] = {
        "scenario": run.scenario_id,
        "source": env.source,
        "shadow_model": env.shadow_model,
        "earth_model": env.earth_model,
        "irradiance_model": run.scenario.irradiance_model,
        "grid": {
            "start_utc": format_utc(env.grid.start),
            "duration_s": env.grid.duration_s,
            "step_s": env.grid.step_s,
            "samples": env.grid.count,
        },
        "eclipse_fraction": round(env.eclipse_fraction, 6),
        "statistics": scenario_statistics(env).to_dict(),
        "eclipses": [
            {
                "start_s": round(e.start_s, 3),
                "end_s": round(e.end_s, 3),
                "duration_s": round(e.duration_s, 3),
            }
            for e in env.eclipses
        ],
        "umbras": [
            {
                "start_s": round(e.start_s, 3),
                "end_s": round(e.end_s, 3),
                "duration_s": round(e.duration_s, 3),
            }
            for e in env.umbras
        ],
        "sites": {
            site_id: {
                "kind": vis.site.kind,
                "passes": [
                    {
                        "aos_s": round(p.aos_s, 3),
                        "los_s": round(p.los_s, 3),
                        "duration_s": round(p.duration_s, 3),
                        "max_elevation_deg": round(p.max_elevation_deg, 4),
                        "time_of_max_s": None
                        if p.time_of_max_s != p.time_of_max_s
                        else round(p.time_of_max_s, 3),
                        "partial_start": p.partial_start,
                        "partial_end": p.partial_end,
                    }
                    for p in vis.passes
                ],
            }
            for site_id, vis in sorted(env.sites.items())
        },
        "timeline": [
            {"start_s": round(s.start_s, 3), "end_s": round(s.end_s, 3), "mode": s.mode}
            for s in run.timeline
        ],
        "notes": list(run.notes),
        "result_format": result_format("scenario_environment"),
        "provenance": {
            "tool": provenance.tool,
            "tool_version": provenance.tool_version,
            "python_version": provenance.python_version,
            "libraries": [list(item) for item in provenance.libraries],
            "project_name": provenance.project_name,
            "project_revision": provenance.project_revision,
            "scenario": run.scenario_id,
            "generated": provenance.generated,
            "user": provenance.user,
            "inputs_digest": provenance.inputs_digest,
            "input_files": [e.to_dict() for e in provenance.input_files],
            "parameters": [list(item) for item in provenance.parameters],
            **(
                {}
                if provenance.illustrative_inputs is None
                else {"illustrative_inputs": provenance.illustrative_inputs}
            ),
        },
    }
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


def write_scenario_outputs(run: ScenarioRun, provenance: Provenance, out_dir: Path) -> list[Path]:
    provenance = replace(provenance, parameters=run_parameters(run))
    sid = run.scenario_id
    files = {
        f"{sid}_environment.json": environment_json(run, provenance),
        f"{sid}_eclipses.csv": eclipses_csv(run),
        f"{sid}_passes.csv": passes_csv(run),
        f"{sid}_timeline.csv": timeline_csv(run),
    }
    beta = beta_csv(run)
    if beta is not None:
        files[f"{sid}_beta.csv"] = beta
    ground = ground_track_csv(run)
    if ground is not None:
        files[f"{sid}_groundtrack.csv"] = ground
    files[f"{sid}_provenance.csv"] = provenance_csv(provenance)
    return [write_file(out_dir, name, text) for name, text in files.items()]
