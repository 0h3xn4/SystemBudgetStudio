"""Pre-release audit fixes in the environment (TL-6/MI-7, MI-5, MI-6, MI-8, MI-9, PWR-8)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

from budget_core.environment.data import EnvironmentData, SiteDef, TimeGrid
from budget_core.environment.elements import ElementsPropagator, orbit_age_problem
from budget_core.environment.intervals import Interval
from budget_core.io.project_loader import load_project
from budget_core.model import Elements, Orbit, Scenario
from budget_core.scenario import run as scenario_run
from budget_core.scenario.run import ScenarioRunError, run_scenario
from budget_core.timeutil import parse_utc
from tests.power_helpers import START, synthetic_env

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
LEO = Orbit(
    name="LEO",
    elements=Elements(
        epoch_utc="2026-06-01T00:00:00Z",
        semi_major_axis_m=6.78e6,
        eccentricity_ratio=0.001,
        inclination_deg=51.6,
        raan_deg=40.0,
        arg_perigee_deg=90.0,
        mean_anomaly_deg=0.0,
    ),
)
SITE = SiteDef("gs", "ground_station", 45.0, 10.0, 100.0, 10.0)
START_UTC = datetime(2026, 6, 1, tzinfo=UTC)


# ---- TL-6 / MI-7: short passes are found at every step ---------------------------------------


def passes_at(step_s: float, site: SiteDef, duration_s: float = 86400.0):  # type: ignore[no-untyped-def]
    env = ElementsPropagator(LEO).compute(
        TimeGrid(START_UTC, duration_s, step_s), [site], "cylindrical"
    )
    return env.sites[site.site_id].passes


def test_a_pass_of_a_few_seconds_is_found_at_every_step() -> None:
    reference = passes_at(20.0, SITE)
    top = max(reference, key=lambda p: p.max_elevation_deg)
    grazing = SiteDef("gs", "ground_station", 45.0, 10.0, 100.0, top.max_elevation_deg - 0.02)
    found = {step: passes_at(step, grazing) for step in (0.5, 1.0, 5.0, 20.0, 60.0, 300.0)}
    short = {
        step: [p for p in ps if abs(p.time_of_max_s - top.time_of_max_s) < 5.0]
        for step, ps in found.items()
    }
    assert all(len(v) == 1 for v in short.values()), short
    assert 0.5 < short[20.0][0].duration_s < 20.0  # shorter than the detection step
    for step, (p,) in short.items():
        assert p.aos_s == pytest.approx(short[20.0][0].aos_s, abs=0.01), step
        assert p.los_s == pytest.approx(short[20.0][0].los_s, abs=0.01), step
    # the number of passes does not depend on the step either
    assert len({len(ps) for ps in found.values()}) == 1


def test_the_passes_of_a_site_do_not_depend_on_the_step() -> None:
    reference = [(p.aos_s, p.los_s) for p in passes_at(10.0, SITE)]
    for step in (1.0, 60.0, 600.0):
        got = [(p.aos_s, p.los_s) for p in passes_at(step, SITE)]
        assert got == pytest.approx(reference, abs=0.01), step


def test_site_geometry_at_the_grid_times_matches_the_grid_arrays() -> None:
    env = ElementsPropagator(LEO).compute(TimeGrid(START_UTC, 3600.0, 60.0), [SITE], "cylindrical")
    vis = env.sites["gs"]
    assert vis.geometry_at is not None
    el, az, rng = vis.geometry_at(env.grid.times_s)
    assert el == pytest.approx(vis.elevation_deg, abs=1e-9)
    assert rng == pytest.approx(vis.range_m, abs=1e-6)


# ---- MI-6: the last sample of a decimal step ---------------------------------------------------


@pytest.mark.parametrize(
    ("duration", "step", "count"),
    [(1.0, 0.1, 11), (0.7, 0.1, 8), (0.3, 0.1, 4), (3600.0, 60.0, 61), (100.0, 30.0, 4)],
)
def test_time_grid_includes_the_last_decimal_step(duration: float, step: float, count: int) -> None:
    grid = TimeGrid(START, duration, step)
    assert grid.count == count
    times = grid.times_s
    assert len(times) == count and times[-1] <= duration
    assert times[-1] == pytest.approx(min((count - 1) * step, duration))


# ---- PWR-8: overlapping eclipses count once ------------------------------------------------------


def test_eclipse_fraction_counts_overlapping_intervals_once() -> None:
    env = synthetic_env(900.0, 10.0, [(100.0, 400.0)])
    overlapping = (Interval(100.0, 400.0), Interval(200.0, 500.0), Interval(850.0, 1000.0))
    env2 = EnvironmentData(**{**env.__dict__, "eclipses": overlapping})
    # 100..500 (400 s) and 850..900 inside the scenario (50 s)
    assert env2.eclipse_fraction == pytest.approx(450.0 / 900.0)


# ---- MI-5, MI-8: limits on cost and on dates -----------------------------------------------------

BASE = {
    "name": "S",
    "orbit": "leo",
    "start_utc": "2026-06-01T00:00:00Z",
    "duration_s": 3600.0,
    "step_s": 60.0,
    "default_mode": "m",
}


def scenario(**changes: object) -> Scenario:
    return Scenario(**{**BASE, **changes})  # type: ignore[arg-type]


def test_the_cost_limit_covers_the_detection_grid() -> None:
    # four years at 1 h gives only 35,000 output steps but 6.3 million detection samples
    with pytest.raises(ValidationError, match="too many"):
        scenario(duration_s=4 * 365 * 86400.0, step_s=3600.0)
    scenario(duration_s=7 * 86400.0, step_s=3600.0)  # a week is fine


@pytest.mark.parametrize(
    "start",
    [
        "0001-01-01T00:00:00Z",
        "1949-12-31T23:59:59Z",
        "2101-01-01T00:00:00Z",
        "9999-12-31T23:59:59Z",
    ],
)
def test_a_scenario_start_outside_1950_to_2100_is_refused(start: str) -> None:
    with pytest.raises(ValidationError) as caught:
        scenario(start_utc=start)
    assert "1950" in str(caught.value) and "2100" in str(caught.value)


@pytest.mark.parametrize(
    "start", ["1950-01-01T00:00:00Z", "2026-06-01T00:00:00Z", "2100-12-31T23:59:59Z"]
)
def test_a_scenario_start_inside_the_range_is_accepted(start: str) -> None:
    assert scenario(start_utc=start).start_utc == start


def load_example() -> object:
    project = load_project(EXAMPLES / "microsat_250kg_eps").project
    assert project is not None
    return project


@pytest.mark.parametrize("error", [MemoryError(), OverflowError("x"), ValueError("year 0")])
def test_run_scenario_turns_resource_and_range_errors_into_plain_messages(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    project = load_example()

    class Failing:
        notes: tuple[str, ...] = ()

        def compute(self, *args: object) -> None:
            raise error

    monkeypatch.setattr(scenario_run, "environment_for", lambda *_: Failing())
    with pytest.raises(ScenarioRunError) as caught:
        run_scenario(project, "one_day")  # type: ignore[arg-type]
    problem = caught.value.problem
    assert problem.code in ("ENV_PROPAGATION_FAILED", "SCENARIO_TOO_LARGE")
    assert problem.hint and "SECRET" not in problem.message


# ---- MI-9: elements and TLEs -----------------------------------------------------------------

ISS_L1 = "1 25544U 98067A   20194.88612269 -.00002218  00000-0 -31515-4 0  9992"
ISS_L2 = "2 25544  51.6461 221.2784 0001413  89.1723 280.4625 15.49507896236008"


def with_checksum(line: str) -> str:
    total = sum(int(c) if c in "0123456789" else (1 if c == "-" else 0) for c in line[:68])
    return line[:68] + str(total % 10)


def tle_orbit(line1: str = ISS_L1, line2: str = ISS_L2) -> Orbit:
    return Orbit(name="ISS", tle=[with_checksum(line1), with_checksum(line2)])


def test_a_good_tle_is_accepted() -> None:
    assert tle_orbit().tle is not None


def test_tle_satellite_numbers_must_match() -> None:
    with pytest.raises(ValidationError, match="satellite number"):
        tle_orbit(line2=ISS_L2[:2] + "25545" + ISS_L2[7:])


def test_a_tle_epoch_that_is_not_a_date_is_refused() -> None:
    with pytest.raises(ValidationError, match="epoch"):
        tle_orbit(line1=ISS_L1[:18] + "20999.88612269" + ISS_L1[32:])  # day 999
    with pytest.raises(ValidationError, match="epoch"):
        tle_orbit(line1=ISS_L1[:18] + "2019x.88612269" + ISS_L1[32:])


def test_a_superscript_digit_in_a_tle_does_not_leak_into_the_message() -> None:
    line = ISS_L1[:10] + "²" + ISS_L1[11:]
    with pytest.raises(ValidationError) as caught:
        Orbit(name="x", tle=[line, ISS_L2])
    messages = " ".join(e["msg"] for e in caught.value.errors())
    assert "²" not in messages and "invalid literal" not in messages


@pytest.mark.parametrize("axis", [1.0e5, 6.0e6, 1.0e9, 1.0e12])
def test_semi_major_axis_must_be_sane(axis: float) -> None:
    with pytest.raises(ValidationError):
        Elements(**{**LEO.elements.model_dump(), "semi_major_axis_m": axis})  # type: ignore[union-attr]


def test_elements_epoch_outside_the_range_is_refused() -> None:
    with pytest.raises(ValidationError, match="1950"):
        Elements(**{**LEO.elements.model_dump(), "epoch_utc": "1900-01-01T00:00:00Z"})  # type: ignore[union-attr]


def test_a_stale_tle_warns_and_elements_never_do() -> None:
    old = tle_orbit()  # epoch 2020-07-12
    assert orbit_age_problem(old, parse_utc("2020-07-20T00:00:00Z"), "iss", "sc") is None  # 8 days
    assert orbit_age_problem(old, parse_utc("2020-06-20T00:00:00Z"), "iss", "sc") is None  # 22 days
    far = orbit_age_problem(old, parse_utc("2026-06-01T00:00:00Z"), "iss", "sc")
    assert far is not None and far.severity.value == "warning" and far.code == "ORBIT_EPOCH_FAR"
    assert far.file == "orbits/iss.yaml"
    assert orbit_age_problem(old, parse_utc("2020-05-01T00:00:00Z"), "iss", "sc") is not None
    assert orbit_age_problem(LEO, parse_utc("2030-01-01T00:00:00Z"), "leo", "sc") is None


def test_the_run_carries_the_stale_orbit_warning() -> None:
    project = load_example()
    project.orbits["leo"] = tle_orbit()  # type: ignore[attr-defined]
    run = run_scenario(project, "one_day")  # type: ignore[arg-type]
    assert [p.code for p in run.problems] == ["ORBIT_EPOCH_FAR"]
    assert np.isfinite(run.env.position_m).all()
