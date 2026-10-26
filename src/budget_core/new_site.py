"""A new ground station or imaging target from a few answers (D-198): what the window's *Add
ground station* and *Add imaging target* turn into a file.

Both are a point on the ground with a minimum elevation: a ground station is a link peer and a
place where a scenario rule can start a mode during a pass, an imaging target is a point whose
passes count for imaging. A scenario names either one in its `sites`, so an id may not be used by
both. None of the numbers has a default (the minimum elevation is an operational choice) and a
number that is missing is refused, not read as zero. The id is the file name
`ground_stations/<id>.yaml` or `targets/<id>.yaml`.
"""

from __future__ import annotations

import math
from collections.abc import Collection
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from budget_core.io.project_loader import model_to_data
from budget_core.model import GroundStation, Target
from budget_core.new_unit import ID_PATTERN, MAX_ID, MAX_TEXT, id_from_name
from budget_core.reports.files import same_name_key
from budget_core.wizard import Issue

__all__ = [
    "GROUND_STATION",
    "TARGET",
    "SiteAnswers",
    "check_site",
    "id_from_name",
    "site_data",
]

GROUND_STATION = "ground_station"
TARGET = "target"
KINDS = (GROUND_STATION, TARGET)
LATITUDE_RANGE = (-90.0, 90.0)
LONGITUDE_RANGE = (-180.0, 180.0)
ALTITUDE_RANGE_M = (-1000.0, 100000.0)  # as the model takes it


@dataclass(frozen=True)
class SiteAnswers:
    kind: str  # GROUND_STATION or TARGET
    site_id: str
    name: str
    latitude_deg: float | None
    longitude_deg: float | None
    altitude_m: float | None
    min_elevation_deg: float | None


def _number(value: float | None) -> bool:
    return value is not None and not isinstance(value, bool) and math.isfinite(value)


def check_site(answers: SiteAnswers, *, existing_ids: Collection[str]) -> list[Issue]:
    """What is wrong with the answers, in words, by field (the first issue is the one to show).
    `existing_ids` are the ids of the ground stations and of the targets together."""
    issues: list[Issue] = []
    if answers.kind not in KINDS:
        issues.append(Issue("kind", "Choose a ground station or an imaging target."))
    site_id = answers.site_id.strip()
    if not site_id:
        issues.append(Issue("site_id", "Give the site an id, for example gs_north."))
    elif len(site_id) > MAX_ID or not ID_PATTERN.fullmatch(site_id):
        issues.append(
            Issue(
                "site_id",
                "The id is the file name: use letters, digits, _ and -, starting with a letter "
                f"or digit, at most {MAX_ID} characters.",
            )
        )
    elif same_name_key(site_id) in {same_name_key(known) for known in existing_ids}:
        issues.append(
            Issue(
                "site_id",
                "A ground station or target with this id (or one that differs only in capitals) "
                "exists: a scenario names both by id.",
            )
        )
    if not answers.name.strip():
        issues.append(Issue("name", "Give the site a name."))
    elif len(answers.name.strip()) > MAX_TEXT:
        issues.append(Issue("name", f"The name can have at most {MAX_TEXT} characters."))
    for field, label, value, low, high, unit in (
        ("latitude_deg", "latitude", answers.latitude_deg, *LATITUDE_RANGE, "degrees"),
        ("longitude_deg", "longitude", answers.longitude_deg, *LONGITUDE_RANGE, "degrees"),
        ("altitude_m", "altitude", answers.altitude_m, *ALTITUDE_RANGE_M, "metres"),
    ):
        if not _number(value):
            issues.append(Issue(field, f"Give the {label} in {unit}."))
        elif value is not None and not low <= value <= high:
            issues.append(Issue(field, f"The {label} must be between {low:g} and {high:g} {unit}."))
    elevation = answers.min_elevation_deg
    if not _number(elevation):
        issues.append(
            Issue("min_elevation_deg", "Give the minimum elevation in degrees (0 up to, not 90).")
        )
    elif elevation is not None and not 0.0 <= elevation < 90.0:
        issues.append(
            Issue(
                "min_elevation_deg",
                "The minimum elevation must be at least 0 and less than 90 degrees.",
            )
        )
    return issues


def site_data(answers: SiteAnswers) -> dict[str, Any]:
    """The plain data of the site file. The answers must have passed `check_site`; the model is
    the last check (a ValueError says the answers do not make a valid site)."""
    assert answers.latitude_deg is not None and answers.longitude_deg is not None
    assert answers.altitude_m is not None and answers.min_elevation_deg is not None
    cls = GroundStation if answers.kind == GROUND_STATION else Target
    try:
        site = cls(
            name=answers.name.strip(),
            latitude_deg=answers.latitude_deg,
            longitude_deg=answers.longitude_deg,
            altitude_m=answers.altitude_m,
            min_elevation_deg=answers.min_elevation_deg,
        )
    except ValidationError as exc:
        raise ValueError("the answers do not make a valid site") from exc
    return model_to_data(site)
