"""Fill in where each input of an explanation came from (D-213).

The explanations name an input by its file and path. The project may record a source for it:
the `provenance:` mapping of an entity file, or the `source` and `status` of a sourced number.
This adds them to the quantities, after the explanation is made, so that no explanation builder
needs to know about it.
"""

from __future__ import annotations

from dataclasses import replace

from budget_core.explain.trace import Explanation, Quantity
from budget_core.input_sources import Lookup
from budget_core.model import Project

_SHOWN = frozenset({"estimate", "illustrative", "tbd"})


def add_sources(project: Project, explanation: Explanation) -> Explanation:
    lookup = Lookup(project)

    def annotate(q: Quantity) -> Quantity:
        if not q.origin:
            return q
        found = lookup.find(q.origin)
        if found is None:
            return q
        status = found.status if found.status in _SHOWN else ""
        return replace(q, source=q.source or found.source, status=status)

    steps = tuple(
        replace(
            step,
            inputs=tuple(annotate(q) for q in step.inputs),
            result=annotate(step.result) if not step.inputs else step.result,
        )
        for step in explanation.steps
    )
    return replace(explanation, steps=steps)
