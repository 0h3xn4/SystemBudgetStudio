"""A new entry of the Eb/N0 table from a few answers (D-200): what the window's *Add Eb/N0 entry*
turns into a row of `config/ebn0_table.yaml`.

A link names its modulation and coding, and the loader refuses a pair that the table does not
list (`REF_UNKNOWN_MODULATION`) once the table has entries; a blank project has none. Only the pair
is asked for. The Eb/N0 it requires comes from a standard or a data sheet, so it is written as a
placeholder (`source: TBD`) and filled in the inputs grid; the link results that need it are n/a
until then. The loader compares the pair exactly, so the text is kept as typed apart from the
spaces around it; a pair that differs from another only in capitals is refused, as it would
read as the same pair and not match.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from budget_core.io.project_loader import model_to_data
from budget_core.model import Ebn0Entry, Ebn0Table, Sourced
from budget_core.new_unit import MAX_TEXT
from budget_core.wizard import Issue

__all__ = ["Ebn0Answers", "check_ebn0", "ebn0_entry_data", "ebn0_table_data", "rate_of"]


@dataclass(frozen=True)
class Ebn0Answers:
    modulation: str
    coding: str
    # the error rates the entry's Eb/N0 refers to, as text (empty: not given); never invented
    target_ber: str = ""
    target_fer: str = ""


def rate_of(text: str) -> float | None:
    """An error rate typed as text: a number above 0 and below 1, else None."""
    try:
        value = float(text.strip())
    except ValueError:
        return None
    return value if 0.0 < value < 1.0 else None


def _key(modulation: str, coding: str) -> tuple[str, str]:
    return modulation.strip().casefold(), coding.strip().casefold()


def check_ebn0(answers: Ebn0Answers, *, existing_pairs: Collection[tuple[str, str]]) -> list[Issue]:
    """What is wrong with the answers, in words, by field (the first issue is the one to show)."""
    issues: list[Issue] = []
    for field, label, text in (
        ("modulation", "modulation, for example QPSK", answers.modulation),
        ("coding", "coding, for example rate 1/2 or none", answers.coding),
    ):
        if not text.strip():
            issues.append(Issue(field, f"Give the {label}."))
        elif len(text.strip()) > MAX_TEXT:
            issues.append(Issue(field, f"The {field} can have at most {MAX_TEXT} characters."))
    for field, label, text in (
        ("target_ber", "bit error rate", answers.target_ber),
        ("target_fer", "frame error rate", answers.target_fer),
    ):
        if text.strip() and rate_of(text) is None:
            issues.append(
                Issue(field, f"The {label} is a number above 0 and below 1, for example 1e-5.")
            )
    if not issues and _key(answers.modulation, answers.coding) in {
        _key(modulation, coding) for modulation, coding in existing_pairs
    }:
        issues.append(
            Issue(
                "modulation",
                "The table has this modulation and coding already (or one that differs only in "
                "capitals).",
            )
        )
    return issues


def _entry(answers: Ebn0Answers) -> Ebn0Entry:
    return Ebn0Entry(
        modulation=answers.modulation.strip(),
        coding=answers.coding.strip(),
        required_ebn0_db=Sourced(
            value=None, source="TBD", note="Placeholder: supply the project's value."
        ),
        target_ber=rate_of(answers.target_ber) if answers.target_ber.strip() else None,
        target_fer=rate_of(answers.target_fer) if answers.target_fer.strip() else None,
    )


def ebn0_entry_data(answers: Ebn0Answers) -> dict[str, Any]:
    """The plain data of the new row. The answers must have passed `check_ebn0`; the model is the
    last check (a ValueError says the answers do not make a valid entry)."""
    try:
        return model_to_data(_entry(answers))
    except ValidationError as exc:
        raise ValueError("the answers do not make a valid Eb/N0 entry") from exc


def ebn0_table_data(answers: Ebn0Answers) -> dict[str, Any]:
    """The plain data of a whole table of the one entry, for a project that has no table file."""
    try:
        return model_to_data(Ebn0Table(entries=[_entry(answers)]))
    except ValidationError as exc:
        raise ValueError("the answers do not make a valid Eb/N0 entry") from exc
