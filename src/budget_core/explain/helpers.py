# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""Small builders shared by the explanations of the propulsion and pointing budgets (D-255).

Each builds a `Quantity` or a `Step` without computing anything physical itself: the physics is the
function the solver calls, passed in. A step whose input is n/a (a placeholder or a missing input)
has an n/a result and says so, never a zero.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence

from budget_core.explain.trace import Quantity, Step, Value
from budget_core.model import Sourced

Cell = tuple[list[Step], Quantity]


def value_of(item: Sourced | None) -> float | None:
    return None if item is None or item.is_placeholder else item.value


def sourced(name: str, item: Sourced | None, unit: str, file: str, path: str) -> Quantity:
    """An input read from `file` at `path`: its value (None when a placeholder or missing), its
    source text and where it is."""
    return Quantity(
        name,
        value_of(item),
        unit,
        f"{file} {path}" + ("" if item is not None else " (missing)"),
        "" if item is None else item.source,
    )


def read(quantity: Quantity, logic: str = "Not computed: an input.") -> Cell:
    return [Step("Read from the project", (), quantity, logic=logic)], quantity


def number(q: Quantity) -> float | None:
    return float(q.value) if isinstance(q.value, int | float) else None


def apply(
    label: str,
    inputs: Sequence[Quantity],
    function: Callable[..., float],
    result_name: str,
    unit: str,
    equation_id: str | None = None,
    logic: str = "",
) -> Step:
    """The step that applies `function` to the numbers of `inputs` (in order). When one of them is
    n/a the result is n/a and the logic says which."""
    values = [number(q) for q in inputs]
    missing = [q.name for q, v in zip(inputs, values, strict=True) if v is None]
    result: Value
    if missing:
        result = None
        logic = (
            (logic + " " if logic else "")
            + "An input is n/a, so the result is n/a: "
            + (", ".join(missing) + ".")
        )
    else:
        result = function(*[v for v in values if v is not None])
    return Step(
        label,
        tuple(inputs),
        Quantity(result_name, result, unit, "this step"),
        equation_id,
        logic,
    )


def total(label: str, members: Sequence[Quantity], result_name: str, unit: str) -> Step:
    """The sum of `members` (n/a when one is), added with `math.fsum` as the solver does."""
    return apply(
        label,
        members,
        lambda *values: math.fsum(values),
        result_name,
        unit,
        logic="Sum of the values above.",
    )
