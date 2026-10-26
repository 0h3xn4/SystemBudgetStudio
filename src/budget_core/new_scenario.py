"""A new orbit and scenario from a few answers (D-189): what the window's *Add orbit and scenario*
turns into an orbit file and a scenario file.

The scenario is the simplest one that can be computed: a near-circular orbit from three elements
(altitude, inclination, RAAN), a start time, a length, and one spacecraft mode for the whole time.
There are no ground stations and no rules yet (those are edited in the scenario editor), so the
power timeline of the first run has eclipses but no passes. None of the numbers has a default:
the answers must give them. The id is the file name `scenarios/<id>.yaml`; the orbit gets the same
id (`orbits/<id>.yaml`).
"""

from __future__ import annotations

import math
from collections.abc import Collection
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from budget_core.environment.constants import EARTH_RADIUS
from budget_core.io.project_loader import model_to_data
from budget_core.model import Elements, Orbit, Scenario
from budget_core.new_unit import ID_PATTERN, MAX_ID, MAX_TEXT, id_from_name
from budget_core.reports.files import same_name_key
from budget_core.timeutil import end_in_range, parse_utc
from budget_core.wizard import (
    ALTITUDE_RANGE_KM,
    ECCENTRICITY_RATIO,
    MAX_DAYS,
    Issue,
    first_run_step_s,
)

MIN_STEP_S = 10.0  # the first run stays quick; a longer scenario gets a coarser step
APOGEE_RANGE_KM = (160.0, 40000.0)  # up to a Molniya or a geostationary transfer orbit
__all__ = [
    "APOGEE_RANGE_KM",
    "MIN_STEP_S",
    "ScenarioAnswers",
    "check_scenario",
    "id_from_name",
    "scenario_data",
]


@dataclass(frozen=True)
class ScenarioAnswers:
    scenario_id: str
    name: str
    altitude_km: float | None
    inclination_deg: float | None
    raan_deg: float | None
    start_utc: str
    duration_days: float | None
    default_mode: str
    # None: a near-circular orbit; else `altitude_km` is the perigee altitude
    apogee_altitude_km: float | None = None
    arg_perigee_deg: float | None = None  # needed with an apogee altitude


def _number(value: float | None) -> bool:
    return value is not None and not isinstance(value, bool) and math.isfinite(value)


def _check_ellipse(answers: ScenarioAnswers) -> list[Issue]:
    """The extra answers of an elliptical orbit: the apogee altitude and the argument of perigee."""
    found: list[Issue] = []
    low, high = APOGEE_RANGE_KM
    apogee = answers.apogee_altitude_km
    if not _number(apogee) or apogee is None:
        found.append(
            Issue(
                "apogee_altitude_km",
                "Give the apogee altitude in kilometres, or leave it empty for a near-circular "
                "orbit.",
            )
        )
    elif (
        _number(answers.altitude_km)
        and answers.altitude_km is not None
        and (apogee < answers.altitude_km)
    ):
        found.append(
            Issue(
                "apogee_altitude_km",
                "The apogee altitude must be at least the altitude (with an apogee, the altitude "
                "is the perigee altitude).",
            )
        )
    elif not low <= apogee <= high:
        found.append(
            Issue(
                "apogee_altitude_km",
                f"The apogee altitude must be between {low:g} and {high:g} km.",
            )
        )
    argument = answers.arg_perigee_deg
    if not _number(argument) or argument is None:
        found.append(
            Issue("arg_perigee_deg", "Give the argument of perigee in degrees (0 to 360).")
        )
    elif not 0.0 <= argument < 360.0:
        found.append(
            Issue(
                "arg_perigee_deg",
                "The argument of perigee must be at least 0 and less than 360 degrees.",
            )
        )
    return found


def check_scenario(
    answers: ScenarioAnswers,
    *,
    existing_scenario_ids: Collection[str],
    existing_orbit_ids: Collection[str],
    mode_ids: Collection[str],
) -> list[Issue]:
    """What is wrong with the answers, in words, by field (the first issue is the one to show)."""
    issues: list[Issue] = []
    if not mode_ids:
        issues.append(
            Issue(
                "default_mode",
                "The project has no spacecraft mode yet. A scenario says which mode is active, "
                "so add a spacecraft mode first.",
            )
        )
    scenario_id = answers.scenario_id.strip()
    if not scenario_id:
        issues.append(Issue("scenario_id", "Give the scenario an id, for example first."))
    elif len(scenario_id) > MAX_ID or not ID_PATTERN.fullmatch(scenario_id):
        issues.append(
            Issue(
                "scenario_id",
                "The id is the file name: use letters, digits, _ and -, starting with a letter "
                f"or digit, at most {MAX_ID} characters.",
            )
        )
    else:
        key = same_name_key(scenario_id)
        if key in {same_name_key(known) for known in existing_scenario_ids}:
            issues.append(
                Issue(
                    "scenario_id",
                    "A scenario with this id (or one that differs only in capitals) exists.",
                )
            )
        elif key in {same_name_key(known) for known in existing_orbit_ids}:
            issues.append(
                Issue(
                    "scenario_id",
                    "An orbit with this id exists: the new orbit gets the id of the scenario. "
                    "Choose another id.",
                )
            )
    if not answers.name.strip():
        issues.append(Issue("name", "Give the scenario a name."))
    elif len(answers.name.strip()) > MAX_TEXT:
        issues.append(Issue("name", f"The name can have at most {MAX_TEXT} characters."))
    low, high = ALTITUDE_RANGE_KM
    if not _number(answers.altitude_km):
        issues.append(Issue("altitude_km", "Give the altitude of the orbit in kilometres."))
    elif answers.altitude_km is not None and not low <= answers.altitude_km <= high:
        issues.append(
            Issue("altitude_km", f"The altitude must be between {low:g} and {high:g} km.")
        )
    if not _number(answers.inclination_deg):
        issues.append(Issue("inclination_deg", "Give the inclination in degrees."))
    elif answers.inclination_deg is not None and not 0.0 <= answers.inclination_deg <= 180.0:
        issues.append(
            Issue("inclination_deg", "The inclination must be between 0 and 180 degrees.")
        )
    if not _number(answers.raan_deg):
        issues.append(Issue("raan_deg", "Give the RAAN (right ascension of the ascending node)."))
    elif answers.raan_deg is not None and not 0.0 <= answers.raan_deg < 360.0:
        issues.append(Issue("raan_deg", "The RAAN must be at least 0 and less than 360 degrees."))
    if answers.apogee_altitude_km is not None:
        issues.extend(_check_ellipse(answers))
    start = None
    if not answers.start_utc.strip():
        issues.append(Issue("start_utc", "Give the start, for example 2026-06-01T00:00:00Z."))
    else:
        try:
            start = parse_utc(answers.start_utc)
        except ValueError as exc:
            issues.append(Issue("start_utc", f"The start is not valid: {exc}."))
    if not _number(answers.duration_days):
        issues.append(Issue("duration_days", "Give how long to simulate, in days."))
    elif answers.duration_days is not None and not 0.0 < answers.duration_days <= MAX_DAYS:
        issues.append(
            Issue(
                "duration_days",
                f"The scenario length must be above 0 and at most {MAX_DAYS:g} days.",
            )
        )
    elif (
        start is not None
        and answers.duration_days is not None
        and not end_in_range(start, answers.duration_days * 86400.0)
    ):
        issues.append(Issue("duration_days", "The scenario must end before the year 2101."))
    if mode_ids and answers.default_mode not in mode_ids:
        issues.append(Issue("default_mode", "Choose one of the spacecraft modes of the project."))
    return issues


def scenario_data(answers: ScenarioAnswers) -> tuple[dict[str, Any], dict[str, Any]]:
    """The plain data of the orbit file and of the scenario file. The answers must have passed
    `check_scenario`; the model is the last check (a ValueError says they make no valid
    scenario)."""
    assert answers.altitude_km is not None and answers.inclination_deg is not None
    assert answers.raan_deg is not None and answers.duration_days is not None
    start_text = parse_utc(answers.start_utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    duration_s = answers.duration_days * 86400.0
    apogee = answers.apogee_altitude_km
    if apogee is None:
        orbit_name = f"{answers.altitude_km:g} km, {answers.inclination_deg:g} deg inclination"
        semi_major_axis_m = EARTH_RADIUS.value + answers.altitude_km * 1000.0
        eccentricity = ECCENTRICITY_RATIO
        arg_perigee = 90.0
        about = (
            f"A near-circular orbit (eccentricity {ECCENTRICITY_RATIO:g}) from the altitude, "
            "inclination and RAAN given in the window; no ground stations and no rules yet."
        )
    else:
        assert answers.arg_perigee_deg is not None
        perigee_m = answers.altitude_km * 1000.0
        apogee_m = apogee * 1000.0
        radius = EARTH_RADIUS.value
        orbit_name = (
            f"{answers.altitude_km:g} x {apogee:g} km, {answers.inclination_deg:g} deg inclination"
        )
        semi_major_axis_m = radius + (perigee_m + apogee_m) / 2.0
        eccentricity = (apogee_m - perigee_m) / (2.0 * radius + perigee_m + apogee_m)
        arg_perigee = answers.arg_perigee_deg
        about = (
            f"An elliptical orbit with a perigee altitude of {answers.altitude_km:g} km and an "
            f"apogee altitude of {apogee:g} km, starting at perigee, from the values given in the "
            "window; no ground stations and no rules yet."
        )
    try:
        orbit = Orbit(
            name=orbit_name,
            elements=Elements(
                epoch_utc=start_text,
                semi_major_axis_m=semi_major_axis_m,
                eccentricity_ratio=eccentricity,
                inclination_deg=answers.inclination_deg,
                raan_deg=answers.raan_deg,
                arg_perigee_deg=arg_perigee,
                mean_anomaly_deg=0.0,
            ),
        )
        scenario = Scenario(
            name=answers.name.strip(),
            description=about,
            environment_source="elements",
            orbit=answers.scenario_id.strip(),
            start_utc=start_text,
            duration_s=duration_s,
            step_s=first_run_step_s(duration_s, MIN_STEP_S),
            default_mode=answers.default_mode,
        )
    except ValidationError as exc:
        raise ValueError("the answers do not make a valid scenario") from exc
    return model_to_data(orbit), model_to_data(scenario)
