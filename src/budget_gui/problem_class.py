"""The four classes a problem is shown in: error, warning, not checked and information (D-151).

The core knows three severities. The window adds one class on top: a *not checked* finding says
that a result could not be worked out because an input is a placeholder (`source: TBD` or no
value) or missing. That is not a defect of the model to fix first, and it is not a harmless
warning either: the result shows `n/a`. Showing it apart keeps real warnings visible in a project
with a hundred placeholders. The class is chosen from the code of the problem, nothing else.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from enum import StrEnum

from budget_core.problems import Problem, Severity
from budget_gui import theme
from budget_gui.theme import Status

# Findings that say "this was not checked": an unsourced or missing number (placeholder), a result
# that is incomplete because of one, and a unit without temperature limits.
NOT_CHECKED_CODES = frozenset({"CONFIG_PLACEHOLDER", "RESULT_INCOMPLETE", "THERMAL_NO_LIMITS"})


class ProblemClass(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    NOT_CHECKED = "not_checked"
    INFO = "info"


ORDER = (ProblemClass.ERROR, ProblemClass.WARNING, ProblemClass.NOT_CHECKED, ProblemClass.INFO)
RANK = {cls: index for index, cls in enumerate(ORDER)}
LABELS = {
    ProblemClass.ERROR: "Error",
    ProblemClass.WARNING: "Warning",
    ProblemClass.NOT_CHECKED: "Not checked",
    ProblemClass.INFO: "Info",
}
ICONS = {
    ProblemClass.ERROR: "circle-x",
    ProblemClass.WARNING: "triangle-alert",
    ProblemClass.NOT_CHECKED: "circle-minus",
    ProblemClass.INFO: "info",
}
EXPLANATIONS = {
    ProblemClass.ERROR: "Error: the project cannot be used as it is, or a limit is broken.",
    ProblemClass.WARNING: "Warning: results are produced, but something needs a look.",
    ProblemClass.NOT_CHECKED: (
        "Not checked: an input is a placeholder or missing, so a result is n/a "
        "(it is neither a pass nor a fail)."
    ),
    ProblemClass.INFO: "Information: nothing to fix.",
}


def classify(problem: Problem) -> ProblemClass:
    if problem.severity is Severity.ERROR:
        return ProblemClass.ERROR
    if problem.code in NOT_CHECKED_CODES:
        return ProblemClass.NOT_CHECKED
    if problem.severity is Severity.WARNING:
        return ProblemClass.WARNING
    return ProblemClass.INFO


def colour(cls: ProblemClass, tokens: theme.Tokens | None = None) -> str:
    """Text and icon colour of a class (4.5 : 1 on the surfaces, see the theme tests)."""
    t = tokens or theme.tokens()
    if cls is ProblemClass.ERROR:
        return t.status(Status.FAIL).fg
    if cls is ProblemClass.WARNING:
        return t.status(Status.NEAR).fg
    if cls is ProblemClass.NOT_CHECKED:
        return t.status(Status.NOT_CHECKED).fg
    return t.info


def counts(problems: Iterable[Problem]) -> dict[ProblemClass, int]:
    found = Counter(classify(p) for p in problems)
    return {cls: found.get(cls, 0) for cls in ORDER}


def summary(by_class: dict[ProblemClass, int]) -> str:
    """'1 error, 11 warnings, 3 not checked, 1 info'; the last two only when there are any."""
    errors, warnings = by_class[ProblemClass.ERROR], by_class[ProblemClass.WARNING]
    parts = [
        f"{errors} error{'s' if errors != 1 else ''}",
        f"{warnings} warning{'s' if warnings != 1 else ''}",
    ]
    if by_class[ProblemClass.NOT_CHECKED]:
        parts.append(f"{by_class[ProblemClass.NOT_CHECKED]} not checked")
    if by_class[ProblemClass.INFO]:
        parts.append(f"{by_class[ProblemClass.INFO]} info")
    return ", ".join(parts)
