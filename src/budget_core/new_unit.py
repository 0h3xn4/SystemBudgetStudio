"""A new unit from a few answers (D-187): what the window's *Add unit* turns into a unit file.

A unit needs a mass, a bus, a maturity class and at least one power mode with its powers. None of
those has a sensible default and none is invented here: the answers must give them (a number that
is missing is refused, not read as zero). The id is the file name `units/<id>.yaml`.
"""

from __future__ import annotations

import math
import re
from collections.abc import Collection
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from budget_core.io.project_loader import model_to_data
from budget_core.model import PowerMode, Unit
from budget_core.reports.files import same_name_key
from budget_core.wizard import Issue

MAX_ID = 60
MAX_TEXT = 120
ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")  # what the loader takes without a warning


@dataclass(frozen=True)
class UnitAnswers:
    unit_id: str
    name: str
    subsystem: str
    bus: str
    maturity: str
    mass_kg: float | None
    mode_name: str
    avg_power_w: float | None
    peak_power_w: float | None


def id_from_name(name: str) -> str:
    """A suggestion for the id: letters and digits of the name, separated by single underscores."""
    slug = re.sub(r"[^A-Za-z0-9]+", "_", name.strip().lower()).strip("_")
    return slug[:MAX_ID].strip("_")


def _number(value: float | None) -> bool:
    return value is not None and not isinstance(value, bool) and math.isfinite(value)


def check_unit(
    answers: UnitAnswers,
    *,
    existing_ids: Collection[str],
    buses: Collection[str],
    classes: Collection[str],
    thermal_nodes: Collection[str] | None = None,
) -> list[Issue]:
    """What is wrong with the answers, in words, by field (the first issue is the one to show).
    `thermal_nodes` is None when the project has no thermal model; with one, the unit's thermal
    node (the subsystem, unless the unit says otherwise) must be one of its nodes, as the loader
    requires."""
    issues: list[Issue] = []
    unit_id = answers.unit_id.strip()
    if not unit_id:
        issues.append(Issue("unit_id", "Give the unit an id, for example obc."))
    elif len(unit_id) > MAX_ID or not ID_PATTERN.fullmatch(unit_id):
        issues.append(
            Issue(
                "unit_id",
                "The id is the file name: use letters, digits, _ and -, starting with a letter "
                f"or digit, at most {MAX_ID} characters.",
            )
        )
    elif same_name_key(unit_id) in {same_name_key(known) for known in existing_ids}:
        issues.append(
            Issue("unit_id", "A unit with this id (or one that differs only in capitals) exists.")
        )
    for field, label, text in (
        ("name", "name", answers.name),
        ("subsystem", "subsystem", answers.subsystem),
        ("mode_name", "power mode name", answers.mode_name),
    ):
        if not text.strip():
            issues.append(Issue(field, f"Give the {label}."))
        elif len(text.strip()) > MAX_TEXT:
            issues.append(Issue(field, f"The {label} can have at most {MAX_TEXT} characters."))
    if (
        thermal_nodes is not None
        and answers.subsystem.strip()
        and answers.subsystem.strip() not in thermal_nodes
    ):
        issues.append(
            Issue(
                "subsystem",
                "The thermal model has no node with this name: use the name of one of its nodes "
                "as the subsystem (the suggestions list them), or add the node to "
                "config/thermal_model.yaml first.",
            )
        )
    if answers.bus not in buses:
        issues.append(Issue("bus", "Choose one of the buses of the spacecraft."))
    if answers.maturity not in classes:
        issues.append(Issue("maturity", "Choose one of the maturity classes of the margin policy."))
    if not _number(answers.mass_kg):
        issues.append(Issue("mass_kg", "Give the mass of the unit in kilograms."))
    elif answers.mass_kg is not None and answers.mass_kg < 0:
        issues.append(Issue("mass_kg", "The mass cannot be negative."))
    if not _number(answers.avg_power_w):
        issues.append(Issue("avg_power_w", "Give the average power of the mode in watts."))
    elif answers.avg_power_w is not None and answers.avg_power_w < 0:
        issues.append(Issue("avg_power_w", "The average power cannot be negative."))
    if not _number(answers.peak_power_w):
        issues.append(Issue("peak_power_w", "Give the peak power of the mode in watts."))
    elif (
        _number(answers.avg_power_w)
        and answers.peak_power_w is not None
        and answers.avg_power_w is not None
        and answers.peak_power_w < answers.avg_power_w
    ):
        issues.append(Issue("peak_power_w", "The peak power cannot be below the average power."))
    return issues


def unit_data(answers: UnitAnswers) -> dict[str, Any]:
    """The plain data of the unit file. The answers must have passed `check_unit`; the model is
    the last check (a ValueError says the answers do not make a valid unit)."""
    assert answers.mass_kg is not None
    assert answers.avg_power_w is not None and answers.peak_power_w is not None
    try:
        unit = Unit(
            name=answers.name.strip(),
            subsystem=answers.subsystem.strip(),
            mass_kg=answers.mass_kg,
            bus=answers.bus,
            maturity=answers.maturity,
            modes=[
                PowerMode(
                    name=answers.mode_name.strip(),
                    avg_power_w=answers.avg_power_w,
                    peak_power_w=answers.peak_power_w,
                )
            ],
        )
    except ValidationError as exc:
        raise ValueError("the answers do not make a valid unit") from exc
    return model_to_data(unit)
