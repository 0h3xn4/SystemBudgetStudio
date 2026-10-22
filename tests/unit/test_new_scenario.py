"""A new orbit and scenario from a few answers (D-189): the checks and the data of the two files."""

from __future__ import annotations

import pytest

from budget_core.new_scenario import ScenarioAnswers, check_scenario, scenario_data


def answers(**kw: object) -> ScenarioAnswers:
    base: dict[str, object] = {
        "scenario_id": "first",
        "name": "First day",
        "altitude_km": 550.0,
        "inclination_deg": 97.6,
        "raan_deg": 100.0,
        "start_utc": "2026-06-01T00:00:00Z",
        "duration_days": 1.0,
        "default_mode": "nominal",
    }
    return ScenarioAnswers(**{**base, **kw})  # type: ignore[arg-type]


def issues(a: ScenarioAnswers, *, scenarios=(), orbits=(), modes=("nominal",)):  # type: ignore[no-untyped-def]
    return check_scenario(
        a,
        existing_scenario_ids=list(scenarios),
        existing_orbit_ids=list(orbits),
        mode_ids=list(modes),
    )


def test_good_answers_have_no_issue() -> None:
    assert issues(answers()) == []


@pytest.mark.parametrize(
    ("kw", "field"),
    [
        ({"scenario_id": ""}, "scenario_id"),
        ({"scenario_id": "a b"}, "scenario_id"),
        ({"name": " "}, "name"),
        ({"altitude_km": None}, "altitude_km"),
        ({"altitude_km": 100.0}, "altitude_km"),
        ({"altitude_km": 5000.0}, "altitude_km"),
        ({"inclination_deg": None}, "inclination_deg"),
        ({"inclination_deg": 181.0}, "inclination_deg"),
        ({"raan_deg": None}, "raan_deg"),
        ({"raan_deg": 360.0}, "raan_deg"),
        ({"start_utc": ""}, "start_utc"),
        ({"start_utc": "yesterday"}, "start_utc"),
        ({"start_utc": "2026-06-01T00:00:00+02:00"}, "start_utc"),
        ({"start_utc": "2200-01-01T00:00:00Z"}, "start_utc"),
        ({"duration_days": None}, "duration_days"),
        ({"duration_days": 0.0}, "duration_days"),
        ({"duration_days": 31.0}, "duration_days"),
        ({"default_mode": "unknown"}, "default_mode"),
    ],
)
def test_each_wrong_answer_names_its_field(kw: dict[str, object], field: str) -> None:
    found = issues(answers(**kw))
    assert found and found[0].field == field


def test_a_scenario_that_would_end_after_the_supported_years_is_refused() -> None:
    found = issues(answers(start_utc="2100-12-31T00:00:00Z", duration_days=5.0))
    assert [i.field for i in found] == ["duration_days"]


def test_an_existing_id_is_refused_also_as_an_orbit_or_in_other_capitals() -> None:
    assert issues(answers(), scenarios=["First"])[0].field == "scenario_id"
    orbit = issues(answers(), orbits=["first"])
    assert orbit[0].field == "scenario_id" and "orbit" in orbit[0].message


def test_without_a_spacecraft_mode_the_first_issue_says_to_add_one() -> None:
    found = issues(answers(), modes=())
    assert found[0].field == "default_mode" and "add a spacecraft mode first" in found[0].message


def test_the_data_makes_a_near_circular_orbit_and_a_scenario_that_names_it() -> None:
    orbit, scenario = scenario_data(answers())
    assert orbit["kind"] == "orbit" and orbit["name"] == "550 km, 97.6 deg inclination"
    assert orbit["elements"]["inclination_deg"] == 97.6
    assert orbit["elements"]["eccentricity_ratio"] == 0.001
    assert abs(orbit["elements"]["semi_major_axis_m"] - (6378137.0 + 550000.0)) < 1.0
    assert scenario["kind"] == "scenario" and scenario["orbit"] == "first"
    assert scenario["default_mode"] == "nominal" and scenario["duration_s"] == 86400.0
    assert scenario["step_s"] == 10.0 and scenario["rules"] == [] and scenario["sites"] == []
    assert "no ground stations" in scenario["description"]


def test_a_long_scenario_gets_a_coarser_step() -> None:
    _orbit, scenario = scenario_data(answers(duration_days=30.0))
    assert scenario["step_s"] == 300.0  # 2,592,000 s in at most 8,640 steps
