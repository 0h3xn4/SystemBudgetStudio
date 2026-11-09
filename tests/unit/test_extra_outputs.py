# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""The pointing and propulsion load in the results (2.3.0): an extra series in the plot and the CSV,
a key in the JSON and a table in the report, only where the scenario places something."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from budget_core.io.project_loader import load_project
from budget_core.model import Project
from budget_core.plots.power import power_plot
from budget_core.power.time_domain import time_domain_budget
from budget_core.provenance import make_provenance
from budget_core.reports.timeline_export import SERIES_COLUMNS, series_csv, timeline_json
from budget_core.reports.timeline_report import build_timeline_report
from budget_core.scenario.run import run_scenario
from tests.unit.test_extra_loads import make

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


@pytest.fixture(scope="module")
def base() -> Project:
    loaded = load_project(EXAMPLES / "microsat_250kg_eps")
    assert loaded.project is not None
    return loaded.project


def solve(project: Project):  # type: ignore[no-untyped-def]
    return time_domain_budget(project, run_scenario(project, "one_day"))


PLACED = {"pointing_default": "nadir", "maneuvers": [{"name": "Raise", "start_s": 3010.0}]}


def test_without_placed_loads_nothing_new_appears(base: Project) -> None:
    result = solve(make(base))
    text = series_csv(result, "eol")
    assert text.splitlines()[0].split(",") == list(SERIES_COLUMNS)
    series = [s.label for s in power_plot(result, "eol").panels[0].series]
    assert "Pointing and propulsion load" not in series
    data = json.loads(timeline_json(result, make_provenance(make(base)), incomplete=False))
    assert "pointing_propulsion" not in data


def test_the_csv_gets_one_more_column_at_the_end(base: Project) -> None:
    project = make(base, **PLACED)
    result = solve(project)
    rows = list(csv.reader(series_csv(result, "eol").splitlines()))
    assert rows[0] == [*SERIES_COLUMNS, "pointing_propulsion_w"]
    column = [float(r[-1]) for r in rows[1:]]
    assert len(column) == result.steps
    assert min(column) == pytest.approx(15.0, abs=1e-6)
    assert max(column) == pytest.approx(15.0 + 800.0, abs=1e-6)
    demand = rows[0].index("demand_w")
    plain = list(csv.reader(series_csv(solve(make(base)), "eol").splitlines()))
    mode = rows[0].index("mode")
    same = 0
    for placed, quiet in zip(rows[1:], plain[1:], strict=True):
        # the burn switches the spacecraft mode, so the steps around it are not comparable
        if placed[mode] != quiet[mode] or 2970.0 <= float(placed[0]) <= 5000.0:
            continue
        same += 1
        assert float(placed[demand]) - float(quiet[demand]) == pytest.approx(
            float(placed[-1]), abs=1e-5
        )
    assert same > 0.9 * result.steps


def test_the_plot_has_the_load_as_its_own_series(base: Project) -> None:
    result = solve(make(base, **PLACED))
    labels = [s.label for s in power_plot(result, "eol").panels[0].series]
    assert "Pointing and propulsion load" in labels and "Demand at source" in labels


def test_the_json_lists_the_events_and_the_energy(base: Project) -> None:
    project = make(base, **PLACED)
    data = json.loads(timeline_json(solve(project), make_provenance(project), incomplete=False))
    block = data["pointing_propulsion"]
    assert [e["kind"] for e in block["events"]] == ["hold", "burn"] or {
        e["kind"] for e in block["events"]
    } == {"hold", "burn"}
    burn = next(e for e in block["events"] if e["kind"] == "burn")
    assert burn["power_w"] == 800.0 and burn["start_s"] == 3010.0
    assert block["energy_wh"] == pytest.approx(
        (15.0 * 21600.0 + 800.0 * burn["duration_s"]) / 3600.0, rel=1e-9
    )


def test_the_report_has_a_table_of_the_events(base: Project) -> None:
    project = make(base, **PLACED)
    document = build_timeline_report(project, solve(project), make_provenance(project), plots=False)
    titles = [t.title for s in document.sections for t in s.tables]
    assert "Pointing and propulsion load" in titles
    table = next(
        t
        for s in document.sections
        for t in s.tables
        if t.title == titles[titles.index("Pointing and propulsion load")]
    )
    assert len(table.rows) == 2
    plain = build_timeline_report(
        make(base), solve(make(base)), make_provenance(make(base)), plots=False
    )
    assert "Pointing and propulsion load" not in [t.title for s in plain.sections for t in s.tables]
