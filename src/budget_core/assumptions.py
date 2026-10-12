"""Configuration numbers a result depends on, and the 'result is incomplete' problem."""

from __future__ import annotations

from dataclasses import dataclass

from budget_core.problems import Problem, Severity


@dataclass(frozen=True)
class Assumption:
    """A configuration number used by a budget, with its source and placeholder status."""

    name: str
    value: float | None
    unit: str
    source: str
    file: str
    path: str
    placeholder: bool


def missing_from(file: str, file_present: bool) -> str:
    """`from <file>` when the file exists but lacks the key, `(<file> not provided)` when the
    whole file is absent."""
    return f"from {file}" if file_present else f"({file} not provided)"


def incomplete(message: str, file: str, path: str) -> Problem:
    return Problem(
        Severity.WARNING,
        "RESULT_INCOMPLETE",
        message,
        file=file,
        path=path,
        hint="Replace the placeholder with a sourced value; results that need it show n/a.",
    )
