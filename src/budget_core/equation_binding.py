"""Which code computes which registered equation (D-206).

`@computes("PWR-EFF")` on a function states that it is the one place that applies that equation.
The registry in `budget_core.equations` says what each equation is; this says where it is
applied, so that an explanation and the solver use the same function and a test can list the
registered equations that no code claims.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

F = TypeVar("F", bound=Callable[..., Any])

BOUND: dict[str, list[str]] = {}


def computes(equation_id: str) -> Callable[[F], F]:
    def mark(func: F) -> F:
        BOUND.setdefault(equation_id, []).append(f"{func.__module__}.{func.__qualname__}")
        func.__equation_id__ = equation_id  # type: ignore[attr-defined]
        return func

    return mark


def claim(equation_id: str, where: str) -> None:
    """For an equation applied inline (a sum, a lookup) rather than by a function of its own:
    `where` names the function that applies it."""
    BOUND.setdefault(equation_id, []).append(where)
