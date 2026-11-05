"""The text of an import plan, for the command line and the window (decision D-243).

Names objects by their ids in the model and counts them; never prints a name or a value read from
the model file.
"""

from __future__ import annotations

from collections import Counter

from budget_core.idm import SPEC_VERSION
from budget_core.idm.importer import ImportPlan, sorted_results
from budget_core.problems import Problem

SHOWN_PER_CODE = 5
KINDS = (
    ("unit", "Units"),
    ("mode", "Spacecraft modes"),
    ("expendable", "Expendables"),
    ("component", "Components"),
)


def counts(plan: ImportPlan) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for result in plan.results:
        out.setdefault(result.kind, {}).setdefault(result.action, 0)
        out[result.kind][result.action] += 1
    return out


def plan_summary(plan: ImportPlan, notes: list[Problem], source: str, sha256: str) -> str:
    lines = [
        f"IDM-CIC model {source} (revision {sha256[:12]}), format {SPEC_VERSION}.",
        f"Project: {plan.root} ({'new' if plan.new_project else 'existing'}).",
    ]
    by_kind = counts(plan)
    for kind, label in KINDS:
        if by_kind.get(kind):
            text = ", ".join(f"{n} {action}" for action, n in sorted(by_kind[kind].items()))
            lines.append(f"{label}: {text}.")
    for result in sorted_results(plan):
        if result.kind == "component" and result.action == "detected":
            # proposals are named by the equipment's id in the model, never by its name
            lines.append(f"  component {result.id}: proposed: {', '.join(result.detail)}")
        elif result.action in ("changed", "removed") and result.detail:
            shown = ", ".join(result.detail[:SHOWN_PER_CODE])
            more = len(result.detail) - SHOWN_PER_CODE
            suffix = f" (+{more})" if more > 0 else ""
            lines.append(f"  {result.kind} {result.id}: {result.action}: {shown}{suffix}")
    by_code: dict[str, list[Problem]] = {}
    for note in notes:
        by_code.setdefault(note.code, []).append(note)
    for code in sorted(by_code):
        items = by_code[code]
        lines.append(f"{items[0].severity.value} {code} x{len(items)}: {items[0].message}")
        lines += [f"    {item.path}" for item in items[:SHOWN_PER_CODE]]
        if len(items) > SHOWN_PER_CODE:
            lines.append(f"    ... and {len(items) - SHOWN_PER_CODE} more")
    kinds = Counter(f.action for f in plan.files)
    lines.append(f"Files: {kinds.get('create', 0)} to create, {kinds.get('update', 0)} to update.")
    return "\n".join(lines)
