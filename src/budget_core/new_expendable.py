"""A new expendable from a few answers (D-197): what the window's *Add expendable* turns into an
expendable file.

An expendable is propellant, an oxidizer, a pressurant, a consumable or jettisoned equipment: its
mass differs per mission phase. A bipropellant is two expendables (fuel and oxidizer), each with
its own masses and position, one file each. Every mission phase of the spacecraft needs a mass
(write 0 if the item is not on board then); none of the numbers has a default, and a number that
is missing is refused, not read as zero. The position of the centre of mass (x, y, z in metres,
body frame) is optional: without it the mass is counted but the centre of mass of the spacecraft
does not include the item. The id is the file name `expendables/<id>.yaml`.
"""

from __future__ import annotations

import math
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from budget_core.io.project_loader import model_to_data
from budget_core.model import Expendable, MassProperties
from budget_core.new_unit import ID_PATTERN, MAX_ID, MAX_TEXT, id_from_name
from budget_core.reports.files import same_name_key
from budget_core.wizard import Issue

__all__ = [
    "ExpendableAnswers",
    "check_expendable",
    "expendable_data",
    "id_from_name",
]


@dataclass(frozen=True)
class ExpendableAnswers:
    expendable_id: str
    name: str
    subsystem: str
    maturity: str
    masses_kg: Mapping[str, float | None]  # one mass per mission phase
    # x, y, z in metres, or None when the position is not given (all three or none)
    position: tuple[float | None, float | None, float | None] | None = None


def _number(value: float | None) -> bool:
    return value is not None and not isinstance(value, bool) and math.isfinite(value)


def check_expendable(
    answers: ExpendableAnswers,
    *,
    existing_ids: Collection[str],
    classes: Collection[str],
    phases: Sequence[str],
) -> list[Issue]:
    """What is wrong with the answers, in words, by field (the first issue is the one to show).
    The mass fields are `masses_kg.<phase>`; the position is one field, `position`."""
    issues: list[Issue] = []
    expendable_id = answers.expendable_id.strip()
    if not expendable_id:
        issues.append(Issue("expendable_id", "Give the expendable an id, for example oxidizer."))
    elif len(expendable_id) > MAX_ID or not ID_PATTERN.fullmatch(expendable_id):
        issues.append(
            Issue(
                "expendable_id",
                "The id is the file name: use letters, digits, _ and -, starting with a letter "
                f"or digit, at most {MAX_ID} characters.",
            )
        )
    elif same_name_key(expendable_id) in {same_name_key(known) for known in existing_ids}:
        issues.append(
            Issue(
                "expendable_id",
                "An expendable with this id (or one that differs only in capitals) exists.",
            )
        )
    for field, label, text in (
        ("name", "name", answers.name),
        ("subsystem", "subsystem", answers.subsystem),
    ):
        if not text.strip():
            issues.append(Issue(field, f"Give the {label}."))
        elif len(text.strip()) > MAX_TEXT:
            issues.append(Issue(field, f"The {label} can have at most {MAX_TEXT} characters."))
    if answers.maturity not in classes:
        issues.append(Issue("maturity", "Choose one of the maturity classes of the margin policy."))
    for phase in phases:
        mass = answers.masses_kg.get(phase)
        field = f"masses_kg.{phase}"
        if not _number(mass):
            issues.append(
                Issue(
                    field, f"Give the mass in kilograms in the phase {phase} (0 if not on board)."
                )
            )
        elif mass is not None and mass < 0:
            issues.append(Issue(field, f"The mass in the phase {phase} cannot be negative."))
    position = answers.position
    given = position is not None and any(c is not None for c in position)
    if position is not None and given and not all(_number(c) for c in position):
        issues.append(
            Issue(
                "position",
                "Give all three coordinates (x, y, z in metres) of the centre of mass or none.",
            )
        )
    return issues


def expendable_data(answers: ExpendableAnswers) -> dict[str, Any]:
    """The plain data of the expendable file. The answers must have passed `check_expendable`;
    the model is the last check (a ValueError says the answers do not make a valid expendable)."""
    masses = {phase: float(mass) for phase, mass in answers.masses_kg.items() if mass is not None}
    properties = None
    position = answers.position
    if position is not None and all(c is not None for c in position):
        properties = MassProperties(position_m=[float(c) for c in position if c is not None])
    try:
        expendable = Expendable(
            name=answers.name.strip(),
            subsystem=answers.subsystem.strip(),
            maturity=answers.maturity,
            masses_kg=masses,
            mass_properties=properties,
        )
    except ValidationError as exc:
        raise ValueError("the answers do not make a valid expendable") from exc
    return model_to_data(expendable)
