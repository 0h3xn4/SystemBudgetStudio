"""User-facing problems (errors, warnings, info) shared by loaders, validation and solvers.

A Problem says what is wrong, where (file, YAML path, line) and what to do (hint). It never
contains values read from project files (spec constraint 11); only field names and types.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True)
class Problem:
    severity: Severity
    code: str
    message: str
    file: str | None = None
    path: str = ""
    line: int | None = None
    hint: str = ""
    # For a finding that compares a number with a limit: the number found, the limit and the unit.
    # They come from the project, so they are shown to the user (window, result files) and are
    # never part of `message` or `hint` (D-207).
    actual: float | None = None
    limit: float | None = None
    unit: str = ""

    def values_text(self) -> str:
        """`found 12.5 kg, limit 10 kg`, or empty when the finding has no numbers."""
        if self.actual is None and self.limit is None:
            return ""
        unit = f" {self.unit}" if self.unit else ""
        parts = []
        if self.actual is not None:
            parts.append(f"found {self.actual:.6g}{unit}")
        if self.limit is not None:
            parts.append(f"limit {self.limit:.6g}{unit}")
        return ", ".join(parts)

    def format(self) -> str:
        where = self.file or "<project>"
        if self.line is not None:
            where = f"{where}:{self.line}"
        text = f"{where}: {self.severity.value} {self.code}: {self.message}"
        if self.path:
            text += f" (at {self.path})"
        if self.hint:
            text += f"\n    {self.hint}"
        return text

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "severity": self.severity.value,
            "code": self.code,
            "message": self.message,
            "file": self.file,
            "path": self.path,
            "line": self.line,
            "hint": self.hint,
        }
        if self.actual is not None or self.limit is not None:  # only a numeric finding has them
            out.update({"actual": self.actual, "limit": self.limit, "unit": self.unit})
        return out


def _key(p: Problem) -> tuple[str, int, str, str, str, str]:
    return (p.file or "", p.line or 0, p.path, p.code, p.severity.value, p.message)


def sort_problems(problems: Iterable[Problem]) -> list[Problem]:
    """Deterministic order: by file (project-level first), line, path, code."""
    return sorted(problems, key=_key)
