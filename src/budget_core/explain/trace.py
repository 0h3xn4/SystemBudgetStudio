"""The shape of an explanation: the steps from the inputs to one displayed number (D-206).

An explanation is built by computing the number again, step by step, with the same functions the
solver uses, and carries the equation each step applies (from the registry in
`budget_core.equations`, with its source or its honest `SOURCE_MISSING`), the inputs with units and
where each one comes from (file and path, and the source text of a sourced number), and every
intermediate result. A value that could not be computed because an input is a placeholder is
`None` ("n/a") and the step that needed it says which input it was.

Nothing here reads a file or computes a physical quantity.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from budget_core.equations import EQUATIONS, SOURCE_MISSING, Equation
from budget_core.reports import numfmt

Value = float | str | None


@dataclass(frozen=True)
class Quantity:
    """A named value with its unit and where it comes from.

    `origin` is the file and path of an input (`units/adcs.yaml modes[0].avg_power_w`) or the name
    of the step that produced it (`step 2`). `source` is the source text of a sourced number,
    empty for a plain input whose file does not record one and for a computed value. `status` is
    what the project says the number is (`estimate`, `illustrative`, `tbd`); empty when it says
    nothing or `sourced` (D-213)."""

    name: str
    value: Value
    unit: str = ""
    origin: str = ""
    source: str = ""
    status: str = ""

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "origin": self.origin,
            "source": self.source,
        }
        if self.status:  # absent for the usual case, so existing explanations stay as they are
            out["status"] = self.status
        return out

    def text(self) -> str:
        if self.value is None:
            return "n/a"
        if isinstance(self.value, str):
            return self.value
        shown = numfmt.general(self.value) or "n/a"
        return f"{shown} {self.unit}".rstrip()


@dataclass(frozen=True)
class Step:
    """One computation. `equation_id` names the registry entry it applies; a step with no
    equation (a plain sum, a lookup) says what it does in `logic`."""

    label: str
    inputs: tuple[Quantity, ...]
    result: Quantity
    equation_id: str | None = None
    logic: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "equation_id": self.equation_id,
            "logic": self.logic,
            "inputs": [q.to_dict() for q in self.inputs],
            "result": self.result.to_dict(),
        }


@dataclass(frozen=True)
class Explanation:
    """How one displayed value was obtained. `address` is the table id, row key and column that
    name it; `result` is the value the table shows (before rounding)."""

    address: tuple[str, tuple[str, ...], str]
    title: str
    result: Quantity
    steps: tuple[Step, ...]
    notes: tuple[str, ...] = ()
    equations: tuple[Equation, ...] = field(default=(), compare=False)

    @property
    def complete(self) -> bool:
        return self.result.value is not None

    def to_dict(self) -> dict[str, Any]:
        table, key, column = self.address
        return {
            "address": {"table": table, "row": list(key), "column": column},
            "title": self.title,
            "result": self.result.to_dict(),
            "complete": self.complete,
            "steps": [s.to_dict() for s in self.steps],
            "equations": [
                {
                    "id": e.id,
                    "name": e.name,
                    "formula": e.formula,
                    "source": e.source_text,
                    "notes": e.notes,
                }
                for e in self.equations
            ],
            "notes": list(self.notes),
        }

    def format_text(self) -> str:
        lines = [self.title, f"= {self.result.text()}", ""]
        for number, step in enumerate(self.steps, start=1):
            head = f"Step {number}: {step.label}"
            if step.equation_id:
                head += f"  [{step.equation_id}]"
            lines.append(head)
            if step.logic:
                lines.append(f"  {step.logic}")
            for q in step.inputs:
                where = f"  ({q.origin})" if q.origin else ""
                src = f'  source: "{q.source}"' if q.source else ""
                src += f"  [{q.status}]" if q.status else ""
                lines.append(f"  {q.name} = {q.text()}{where}{src}")
            r = step.result  # a value read from the project says where it was read from
            where = f"  ({r.origin})" if r.origin else ""
            src = f'  source: "{r.source}"' if r.source else ""
            src += f"  [{r.status}]" if r.status else ""
            lines.append(f"  -> {r.name} = {r.text()}{where}{src}")
            lines.append("")
        if self.equations:
            lines.append("Equations")
            for e in self.equations:
                lines.append(f"  {e.id}  {e.name}")
                lines.append(f"    {e.formula}")
                cited = (
                    "none yet (SOURCE_MISSING)"
                    if e.source_text == SOURCE_MISSING
                    else e.source_text
                )
                lines.append(f"    source: {cited}")
            lines.append("")
        for note in self.notes:
            lines.append(note)
        return "\n".join(lines).rstrip() + "\n"


def link_steps(steps: tuple[Step, ...]) -> tuple[Step, ...]:
    """Number the steps and say, for an input that is the result of an earlier step, which one:
    the origin of such an input becomes `result of step N`, and the origin of a computed result is
    empty (the step is where it comes from). A step that computes nothing, only reads an input,
    keeps the origin of what it read."""
    produced: dict[tuple[str, Value], int] = {}
    out: list[Step] = []
    for number, step in enumerate(steps, start=1):
        inputs = tuple(
            replace(q, origin=f"result of step {produced[(q.name, q.value)]}")
            if (q.name, q.value) in produced
            else q
            for q in step.inputs
        )
        result = step.result if not step.inputs else replace(step.result, origin="")
        produced[(result.name, result.value)] = number
        out.append(replace(step, inputs=inputs, result=result))
    return tuple(out)


def equations_used(steps: tuple[Step, ...]) -> tuple[Equation, ...]:
    """The registry entries the steps apply, each once, in the order first used."""
    seen: list[str] = []
    for step in steps:
        if step.equation_id and step.equation_id not in seen:
            seen.append(step.equation_id)
    return tuple(EQUATIONS[i] for i in seen)
