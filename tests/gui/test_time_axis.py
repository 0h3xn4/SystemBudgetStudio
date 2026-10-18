"""The time axis of the plots: elapsed time, UTC, orbit number (UX step 3b, D-162)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from budget_gui.time_axis import ElapsedAxis, OrbitAxis, UtcAxis, orbit_period_s

ORIGIN = datetime(2026, 6, 1, 0, 0, 0, tzinfo=UTC)


def test_elapsed_ticks_pick_seconds_minutes_hours_or_days() -> None:
    axis = ElapsedAxis()
    ticks = axis.ticks(0.0, 500.0)
    assert axis.title(0.0, 500.0) == "Time since scenario start (s)"
    assert [label for _t, label in ticks][:3] == ["0", "100", "200"]
    assert axis.title(0.0, 86_400.0 * 7) == "Time since scenario start (days)"
    hours = ElapsedAxis().ticks(0.0, 86_400.0)
    assert hours[1] == (5 * 3600.0, "5")  # a day is shown in hours: seconds, and the hour as label


def test_utc_ticks_sit_on_round_times_of_day() -> None:
    axis = UtcAxis(ORIGIN)
    ticks = axis.ticks(0.0, 86_400.0)  # one day
    assert all(t % 3600.0 == 0.0 for t, _label in ticks)
    assert ticks[0][1] == "06-01"  # midnight carries the date
    assert "06:00" in [label for _t, label in ticks]
    assert 4 <= len(ticks) <= 12
    short = axis.ticks(120.0, 900.0)
    assert short[0][1] == "00:05" or short[0][1] == "00:02"  # minutes: round clock times
    week = axis.ticks(0.0, 7 * 86_400.0)
    assert week[0][1] == "06-01" and all(len(label) == 5 for _t, label in week)  # dates only


def test_utc_ticks_follow_an_origin_that_is_not_midnight() -> None:
    axis = UtcAxis(datetime(2026, 6, 1, 0, 17, 30, tzinfo=UTC))
    ticks = axis.ticks(0.0, 4 * 3600.0)  # half-hour ticks
    # the first round time after the origin is 00:30, 750 s after the start of the scenario
    assert ticks[0][0] == pytest.approx(750.0) and ticks[0][1] == "00:30"
    assert ticks[1] == (pytest.approx(2550.0), "01:00")


def test_utc_title_says_what_the_axis_is() -> None:
    assert "UTC" in UtcAxis(ORIGIN).title(0.0, 86_400.0)


def test_orbit_ticks_count_orbits_from_one() -> None:
    axis = OrbitAxis(5700.0)
    ticks = axis.ticks(0.0, 5700.0 * 6)
    assert [label for _t, label in ticks][:3] == ["1", "2", "3"]
    assert ticks[1][0] == 5700.0
    assert axis.title(0.0, 1.0) == "Orbit number (from the spacing of the eclipses)"
    dense = axis.ticks(0.0, 5700.0 * 300)  # many orbits: ticks are thinned, still whole orbits
    assert len(dense) <= 12 and all(float(label).is_integer() for _t, label in dense)


def test_the_orbit_period_comes_from_the_spacing_of_the_eclipses() -> None:
    starts = [100.0 + 5700.0 * k + (3.0 if k % 2 else 0.0) for k in range(10)]
    assert orbit_period_s(starts) == pytest.approx(5700.0, abs=5.0)
    assert orbit_period_s([1.0, 2.0]) is None  # too few to tell
    assert orbit_period_s([]) is None
