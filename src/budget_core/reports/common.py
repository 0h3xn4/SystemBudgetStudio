"""Report parts shared by every budget: sheet names, assumptions, problems, provenance."""

from __future__ import annotations

import re
from collections.abc import Collection, Sequence

from budget_core.assumptions import Assumption
from budget_core.equations import EQUATIONS
from budget_core.problems import Problem, sort_problems
from budget_core.provenance import Provenance
from budget_core.reports.document import Column, Section, Table

BANNER = (
    "INCOMPLETE: some inputs are placeholders (source TBD or missing). Entries marked n/a depend "
    "on them and are not computed. Do not use this report as evidence until the placeholders are "
    "replaced with sourced values."
)


RESERVED_SHEET_NAMES = frozenset({"history"})  # Excel keeps this one for itself


def sheet_name(raw: str, used: set[str]) -> str:
    """A valid, unique sheet name of at most 31 characters. Excel compares names without regard
    to case and does not allow an apostrophe at either end, so `used` holds the lower-case names
    taken so far."""
    base = re.sub(r"[\[\]:*?/\\]", "_", raw).strip("'")[:31].strip("'") or "Sheet"
    if base.lower() in RESERVED_SHEET_NAMES:
        base += "_"
    name, i = base, 2
    while name.lower() in used:
        suffix = f" {i}"
        name = base[: 31 - len(suffix)].rstrip("'") + suffix
        i += 1
    used.add(name.lower())
    return name


def equation_ids(*prefixes: str) -> list[str]:
    """The ids of the registered equations that start with one of the prefixes."""
    return [e.id for e in EQUATIONS.values() if e.id.startswith(prefixes)]


def environment_equations(shadow_model: str | None, with_sites: bool) -> list[str]:
    """The environment equations a result relies on: the Sun and the Earth shadow of the model in
    use (`None`: no eclipse analysis), and the geometry of the pass analysis."""
    ids: list[str] = []
    if shadow_model is not None:
        ids += ["ENV-SUN", "ENV-SHADOW-CON" if shadow_model == "conical" else "ENV-SHADOW-CYL"]
    if with_sites:
        ids += ["ENV-GMST", "ENV-GEODETIC", "ENV-TOPO"]
    return ids


def closing_sections(
    used: set[str],
    assumptions: Sequence[Assumption],
    equation_prefix: str,
    problems: Sequence[Problem],
    provenance: Provenance,
    extra_equations: Collection[str] = (),
) -> list[Section]:
    """Assumptions (numbers and equations), Problems and Provenance sections. The equation table
    lists the equations whose id starts with `equation_prefix` and those named in
    `extra_equations` (the power and environment equations a time-domain result relies on)."""
    assumption_table = Table(
        "Configuration numbers used",
        (
            Column("Name"),
            Column("Value", "number", -1),
            Column("Unit"),
            Column("Source"),
            Column("Status"),
        ),
        tuple(
            (a.name, a.value, a.unit, a.source, "PLACEHOLDER" if a.placeholder else a.status)
            for a in assumptions
        ),
    )
    equation_table = Table(
        "Equations",
        (Column("ID"), Column("Name"), Column("Formula"), Column("Source")),
        tuple(
            (e.id, e.name, e.formula, e.source_text)
            for e in EQUATIONS.values()
            if e.id.startswith(equation_prefix) or e.id in extra_equations
        ),
        note="SOURCE_MISSING: the formula is a project convention or textbook definition whose "
        "reference text is not available to the tool yet (see docs/DECISIONS.md).",
    )
    problem_table = Table(
        "Problems and open items",
        (
            Column("Severity"),
            Column("Code"),
            Column("Location"),
            Column("Path"),
            Column("Message"),
            Column("Hint"),
        ),
        tuple(
            (
                p.severity.value,
                p.code,
                (p.file or "") + (f":{p.line}" if p.line is not None else ""),
                p.path,
                p.message,
                p.hint,
            )
            for p in sort_problems(problems)
        ),
    )
    provenance_table = Table(
        "Provenance", (Column("Item"), Column("Value")), tuple(provenance.rows())
    )
    return [
        Section(
            "Assumptions",
            sheet_name("Assumptions", used),
            tables=(assumption_table, equation_table),
        ),
        Section("Problems", sheet_name("Problems", used), tables=(problem_table,)),
        Section("Provenance", sheet_name("Provenance", used), tables=(provenance_table,)),
    ]
