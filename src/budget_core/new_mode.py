"""A new spacecraft mode from a few answers (D-188): what the window's *Add spacecraft mode* turns
into a mode file.

A spacecraft mode says which power mode every unit is in, so a project needs its units first. The
assignments are not typed one by one: a new mode starts from a copy of another mode or with every
unit in its `off` power mode, and a unit that has no `off` starts in its first power mode (the
caller is told which, so the person can set them). Nothing here is a number. The id is the file
name `modes/<id>.yaml`.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from budget_core.io.project_loader import model_to_data
from budget_core.model import SpacecraftMode
from budget_core.new_unit import ID_PATTERN, MAX_ID, MAX_TEXT, id_from_name
from budget_core.reports.files import same_name_key
from budget_core.wizard import Issue

OFF_MODE = "off"
__all__ = [
    "OFF_MODE",
    "ModeAnswers",
    "check_mode",
    "id_from_name",
    "mode_data",
    "scenarios_using",
    "starting_assignments",
]


@dataclass(frozen=True)
class ModeAnswers:
    mode_id: str
    name: str
    description: str
    copy_of: str  # the id of the mode whose assignments the new one starts from; "" for none


def starting_assignments(
    unit_modes: Mapping[str, Sequence[str]], copy_of: Mapping[str, str] | None = None
) -> tuple[dict[str, str], list[str]]:
    """The power mode of every unit in a new spacecraft mode, and the units that had to start in
    their first power mode because they have neither the copied mode's choice nor an `off`.

    `unit_modes` maps a unit id to the names of its power modes, in the order of the file. A
    unit without any power mode is left out (the model refuses such a unit anyway)."""
    assignments: dict[str, str] = {}
    first_mode: list[str] = []
    for unit_id in sorted(unit_modes):
        names = list(unit_modes[unit_id])
        if not names:
            continue
        if copy_of is not None and copy_of.get(unit_id) in names:
            assignments[unit_id] = str(copy_of[unit_id])
            continue
        off = next((name for name in names if name.strip().lower() == OFF_MODE), None)
        if off is not None:
            assignments[unit_id] = off
        else:
            assignments[unit_id] = names[0]
            first_mode.append(unit_id)
    return assignments, first_mode


def check_mode(
    mode_id: str,
    name: str,
    description: str,
    *,
    existing_ids: Collection[str],
    unit_ids: Collection[str],
) -> list[Issue]:
    """What is wrong with the answers, in words, by field (the first issue is the one to show)."""
    issues: list[Issue] = []
    mode_id = mode_id.strip()
    if not unit_ids:
        issues.append(
            Issue(
                "units",
                "The project has no unit yet. A spacecraft mode says what every unit is doing, "
                "so add a unit first.",
            )
        )
    if not mode_id:
        issues.append(Issue("mode_id", "Give the mode an id, for example safe."))
    elif len(mode_id) > MAX_ID or not ID_PATTERN.fullmatch(mode_id):
        issues.append(
            Issue(
                "mode_id",
                "The id is the file name: use letters, digits, _ and -, starting with a letter "
                f"or digit, at most {MAX_ID} characters.",
            )
        )
    elif same_name_key(mode_id) in {same_name_key(known) for known in existing_ids}:
        issues.append(
            Issue("mode_id", "A mode with this id (or one that differs only in capitals) exists.")
        )
    if not name.strip():
        issues.append(Issue("name", "Give the mode a name."))
    elif len(name.strip()) > MAX_TEXT:
        issues.append(Issue("name", f"The name can have at most {MAX_TEXT} characters."))
    if len(description.strip()) > 4 * MAX_TEXT:
        issues.append(
            Issue("description", f"The description can have at most {4 * MAX_TEXT} characters.")
        )
    return issues


def mode_data(name: str, description: str, assignments: Mapping[str, str]) -> dict[str, Any]:
    """The plain data of the mode file (a ValueError says the answers make no valid mode)."""
    try:
        mode = SpacecraftMode(
            name=name.strip(), description=description.strip(), assignments=dict(assignments)
        )
    except ValidationError as exc:
        raise ValueError("the answers do not make a valid spacecraft mode") from exc
    return model_to_data(mode)


def scenarios_using(mode_id: str, scenarios: Mapping[str, Mapping[str, Any]]) -> list[str]:
    """The ids of the scenarios that name this spacecraft mode: as the default mode, in a rule or
    in a segment. Removing a mode that a scenario names would leave the scenario with an unknown
    mode."""
    found: list[str] = []
    for scenario_id in sorted(scenarios):
        data = scenarios[scenario_id]
        used = data.get("default_mode") == mode_id
        for key in ("rules", "segments"):
            items = data.get(key)
            if isinstance(items, list):
                used = used or any(isinstance(i, dict) and i.get("mode") == mode_id for i in items)
        if used:
            found.append(scenario_id)
    return found
