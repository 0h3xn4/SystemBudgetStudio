"""Statistics of the eclipses and passes of a scenario (2.1.0): count, shortest, mean and longest
duration, the time in contact, the largest gap without a pass and the elevation of the passes."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from budget_core.environment.data import Pass
from budget_core.environment.intervals import Interval
from budget_core.io.project_loader import load_project
from budget_core.scenario import statistics as st
from budget_core.scenario.run import run_scenario

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


def test_duration_statistics_of_known_durations() -> None:
    s = st.duration_stats([30.0, 10.0, 20.0])
    assert (s.count, s.total_s, s.min_s, s.mean_s, s.max_s) == (3, 60.0, 10.0, 20.0, 30.0)


def test_no_duration_has_no_minimum_mean_or_maximum() -> None:
    s = st.duration_stats([])
    assert s.count == 0 and s.total_s == 0.0
    assert s.min_s is None and s.mean_s is None and s.max_s is None


def test_the_largest_gap_counts_the_start_the_end_and_between() -> None:
    span = 1000.0
    # gaps: 0 to 100, 150 to 400, 450 to 1000
    items = [Interval(100.0, 150.0), Interval(400.0, 450.0)]
    assert st.largest_gap_s(items, span) == 550.0
    # nothing at all: the whole span
    assert st.largest_gap_s([], span) == span
    # covered from the very start to the very end
    assert st.largest_gap_s([Interval(0.0, 1000.0)], span) == 0.0


def test_overlapping_intervals_are_counted_once_in_the_gap() -> None:
    items = [Interval(100.0, 300.0), Interval(200.0, 500.0)]
    assert st.largest_gap_s(items, 1000.0) == 500.0  # 500 to 1000


def test_intervals_beyond_the_span_are_clipped() -> None:
    assert st.largest_gap_s([Interval(-50.0, 100.0), Interval(900.0, 1200.0)], 1000.0) == 800.0


def _pass(aos: float, los: float, elevation: float) -> Pass:
    return Pass(aos, los, elevation, (aos + los) / 2.0)


def test_site_statistics_of_known_passes() -> None:
    passes = [_pass(100.0, 400.0, 20.0), _pass(1000.0, 1200.0, 60.0)]
    site = st.site_statistics("gs", "ground_station", passes, 2000.0)
    assert site.passes.count == 2 and site.passes.total_s == 500.0
    assert site.passes.min_s == 200.0 and site.passes.max_s == 300.0 and site.passes.mean_s == 250.0
    assert site.contact_fraction == pytest.approx(0.25)
    assert site.largest_gap_s == 800.0  # 1200 to 2000
    assert (site.elevation_min_deg, site.elevation_mean_deg, site.elevation_max_deg) == (
        20.0,
        40.0,
        60.0,
    )


def test_a_site_without_a_pass_is_in_contact_zero_of_the_time() -> None:
    site = st.site_statistics("tgt", "target", [], 3600.0)
    assert site.passes.count == 0 and site.contact_fraction == 0.0
    assert site.largest_gap_s == 3600.0 and site.elevation_max_deg is None


def test_an_unknown_peak_elevation_is_left_out_of_the_elevation_statistics() -> None:
    passes = [_pass(0.0, 10.0, math.nan), _pass(20.0, 30.0, 45.0)]
    site = st.site_statistics("gs", "ground_station", passes, 100.0)
    assert site.elevation_min_deg == site.elevation_mean_deg == site.elevation_max_deg == 45.0


def test_a_scenario_of_the_example_has_consistent_statistics() -> None:
    project = load_project(EXAMPLES / "microsat_250kg_eps").project
    assert project is not None
    run = run_scenario(project, sorted(project.scenarios)[0])
    stats = st.scenario_statistics(run.env)
    assert stats.eclipses.durations.count == len(run.env.eclipses)
    assert stats.eclipses.fraction == pytest.approx(run.env.eclipse_fraction)
    assert [s.site_id for s in stats.sites] == sorted(run.env.sites)
    for site in stats.sites:
        passes = run.env.sites[site.site_id].passes
        assert site.passes.count == len(passes)
        assert site.contact_fraction == pytest.approx(
            sum(p.duration_s for p in passes) / run.env.grid.duration_s
        )
        assert 0.0 <= site.largest_gap_s <= run.env.grid.duration_s
    # eclipses and sunlight share the scenario
    longest_eclipse = stats.eclipses.durations.max_s
    assert longest_eclipse is not None and stats.eclipses.longest_sunlight_s > 0.0


def test_the_statistics_are_in_the_dictionary_for_the_json_file() -> None:
    project = load_project(EXAMPLES / "microsat_250kg_eps").project
    assert project is not None
    run = run_scenario(project, sorted(project.scenarios)[0])
    data = st.scenario_statistics(run.env).to_dict()
    assert set(data) == {"duration_s", "eclipses", "sites", "beta", "ground_track"}
    assert set(data["eclipses"]) >= {"count", "min_s", "mean_s", "max_s", "fraction"}
    assert all(
        set(s) >= {"site", "kind", "passes", "contact_fraction", "largest_gap_s"}
        for s in data["sites"]
    )
