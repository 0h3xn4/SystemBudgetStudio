"""Explanations of the static mass budget (tables of `reports/mass_report.py`, D-206).

Table ids (`Table.explain_id`): `mass:summary`, `mass:limits`, and per mission phase
`mass:items:<phase>`, `mass:subsystems:<phase>`, `mass:totals:<phase>` and `mass:inertia:<phase>`.
A cell is named by the id, the values of the row's key columns and the column header. The
explanation computes the cell again with the functions the solver uses (`margined_mass_kg`,
`system_margined_kg`, `limit_margin_kg`, `center_of_gravity`, `parallel_axis`), so the numbers
agree with the table by construction; a test checks every cell.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace

from budget_core.explain.power import ExplainError
from budget_core.explain.trace import Explanation, Quantity, Step, equations_used, link_steps
from budget_core.mass.mass_properties import ZERO, Vec3, center_of_gravity, parallel_axis
from budget_core.mass.static_mass import (
    LimitCheck,
    MassRow,
    PhaseMass,
    StaticMassResult,
    limit_margin_kg,
    margined_mass_kg,
    static_mass_budget,
    system_margined_kg,
)
from budget_core.model import Project, Sourced

MARGIN_FILE = "config/margin_policy.yaml"
LIMITS_FILE = "config/mass_limits.yaml"
AXES = "xyz"
TENSOR_FIELDS = ("ixx_kgm2", "iyy_kgm2", "izz_kgm2", "ixy_kgm2", "ixz_kgm2", "iyz_kgm2")
TENSOR_NAMES = ("Ixx", "Iyy", "Izz", "Ixy", "Ixz", "Iyz")

Cell = tuple[list[Step], Quantity]


def _src(item: Sourced | None) -> str:
    return "" if item is None else item.source


def _sourced_value(item: Sourced | None) -> float | None:
    return None if item is None or item.is_placeholder else item.value


def _read(q: Quantity) -> Cell:
    return [Step("Read from the project", (), q, logic="Not computed: an input.")], q


def _float(q: Quantity) -> float | None:
    return q.value if isinstance(q.value, float) else None


@dataclass
class _Ctx:
    project: Project
    result: StaticMassResult
    phase: PhaseMass

    @property
    def policy(self):  # type: ignore[no-untyped-def]
        return self.project.config.margin_policy

    # ---- inputs, each with where it comes from --------------------------------------------
    def mass(self, row: MassRow) -> Quantity:
        if row.kind == "unit":
            origin = f"{row.file} mass_kg"
        else:
            origin = f"{row.file} masses_kg.{self.phase.phase}"
        return Quantity(f"mass of {row.item_id}", row.mass_kg, "kg", origin)

    def class_margin(self, maturity: str) -> Quantity:
        policy = self.policy
        item = (
            policy.classes[maturity].mass_margin_ratio
            if policy and maturity in policy.classes
            else None
        )
        return Quantity(
            f"mass margin of maturity class {maturity}",
            _sourced_value(item),
            "ratio",
            f"{MARGIN_FILE} classes.{maturity}.mass_margin_ratio" + ("" if item else " (missing)"),
            _src(item),
        )

    def system_margin(self) -> Quantity:
        item = self.policy.system_mass_margin_ratio if self.policy else None
        return Quantity(
            "system mass margin",
            _sourced_value(item),
            "ratio",
            f"{MARGIN_FILE} system_mass_margin_ratio" + ("" if item else " (missing)"),
            _src(item),
        )

    def position(self, row: MassRow, axis: int) -> Quantity:
        value = None if row.position_m is None else row.position_m[axis]
        origin = f"{row.file} mass_properties.position_m[{axis}]"
        if value is None:
            origin = f"{row.file} (no mass_properties)"
        return Quantity(f"{AXES[axis]} position of {row.item_id}", value, "m", origin)

    def own_inertia(self, row: MassRow, entry: int) -> Quantity:
        if row.own_inertia is None:
            return Quantity(
                f"{TENSOR_NAMES[entry]} of {row.item_id} itself",
                0.0,
                "kg m2",
                f"{row.file} (no own inertia: a point mass)",
            )
        return Quantity(
            f"{TENSOR_NAMES[entry]} of {row.item_id} itself",
            row.own_inertia.entries()[entry],
            "kg m2",
            f"{row.file} mass_properties.inertia.{TENSOR_FIELDS[entry]}",
        )

    # ---- values the tables show ------------------------------------------------------------
    def items_ref(self, column: str) -> str:
        return f"phase {self.phase.phase}, table Items, column {column}"

    def placed(self) -> list[MassRow]:
        """The items of the centre of gravity: a position and a mass (as the solver selects)."""
        return [r for r in self.phase.rows if r.position_m is not None and r.mass_kg > 0.0]


# ---- one item -----------------------------------------------------------------------------------
def _margin_lookup(ctx: _Ctx, row: MassRow) -> Step:
    return Step(
        "Margin of the item's maturity class",
        (ctx.class_margin(row.maturity),),
        Quantity(f"mass margin of {row.item_id}", row.margin_ratio, "ratio", "this step"),
        logic=f"The item's maturity class is '{row.maturity}'; its margin is looked up in the "
        "margin policy. A placeholder or a missing class gives n/a.",
    )


def _margined_steps(ctx: _Ctx, row: MassRow) -> list[Step]:
    lookup = _margin_lookup(ctx, row)
    value = margined_mass_kg(row.mass_kg, row.margin_ratio)
    return [
        lookup,
        Step(
            "Mass with the maturity margin",
            (ctx.mass(row), replace(lookup.result, origin="previous step")),
            Quantity(f"mass of {row.item_id} with margin", value, "kg", "this step"),
            "MASS-MARGIN",
        ),
    ]


def _item_cell(ctx: _Ctx, key: Sequence[str], column: str) -> Cell:
    row = next((r for r in ctx.phase.rows if r.item_id == key[0]), None)
    if row is None:
        raise ExplainError("There is no such item in this table.")
    plain = {
        "Item": ("id", row.item_id, ""),
        "Name": ("name", row.name, f"{row.file} name"),
        "Kind": ("kind", row.kind, f"{row.file}"),
        "Subsystem": ("subsystem", row.subsystem, f"{row.file} subsystem"),
        "Maturity": ("maturity class", row.maturity, f"{row.file} maturity"),
        "Own inertia": (
            "whether it has an own inertia",
            "yes" if row.has_inertia else "no",
            f"{row.file} mass_properties.inertia",
        ),
    }
    if column in plain:
        label, value, origin = plain[column]
        return _read(Quantity(f"{label} of {row.item_id}", value, "", origin or row.file))
    if column == "Mass (kg)":
        return _read(ctx.mass(row))
    if column == "Margin":
        step = _margin_lookup(ctx, row)
        return [step], step.result
    if column == "With margin (kg)":
        steps = _margined_steps(ctx, row)
        return steps, steps[-1].result
    for axis in range(3):
        if column == f"{AXES[axis]} (m)":
            return _read(ctx.position(row, axis))
    raise ExplainError("This column is not explained.")


# ---- sums ---------------------------------------------------------------------------------------
def _sum_step(label: str, members: Sequence[Quantity], result_name: str, logic: str = "") -> Step:
    values = [m.value for m in members]
    total = (
        None
        if any(v is None for v in values)
        else math.fsum(float(v) for v in values if isinstance(v, float))
    )
    note = logic or "Sum of the values above."
    if total is None:
        note += " A member is n/a, so the sum is n/a."
    return Step(label, tuple(members), Quantity(result_name, total, "kg", "this step"), None, note)


def _nominal_members(ctx: _Ctx, rows: Sequence[MassRow]) -> list[Quantity]:
    return [Quantity(r.item_id, r.mass_kg, "kg", ctx.items_ref("Mass (kg)")) for r in rows]


def _margined_members(ctx: _Ctx, rows: Sequence[MassRow]) -> list[Quantity]:
    return [
        Quantity(r.item_id, r.margined_mass_kg, "kg", ctx.items_ref("With margin (kg)"))
        for r in rows
    ]


def _subsystem_cell(ctx: _Ctx, key: Sequence[str], column: str) -> Cell:
    name = key[0]
    rows = [r for r in ctx.phase.rows if r.subsystem == name]
    if not rows:
        raise ExplainError("There is no such subsystem in this table.")
    if column == "Mass (kg)":
        step = _sum_step(
            f"Sum over the items of subsystem {name}",
            _nominal_members(ctx, rows),
            f"mass of subsystem {name}",
        )
    elif column == "With margin (kg)":
        step = _sum_step(
            f"Sum over the items of subsystem {name}",
            _margined_members(ctx, rows),
            f"mass of subsystem {name} with margins",
        )
    else:
        raise ExplainError("This column is not explained.")
    return [step], step.result


# ---- totals -------------------------------------------------------------------------------------
def _nominal_total(ctx: _Ctx) -> Cell:
    step = _sum_step(
        f"Total mass in phase {ctx.phase.phase}",
        _nominal_members(ctx, ctx.phase.rows),
        "total mass",
    )
    return [step], step.result


def _unit_margined_total(ctx: _Ctx) -> Cell:
    step = _sum_step(
        f"Total mass with the unit margins in phase {ctx.phase.phase}",
        _margined_members(ctx, ctx.phase.rows),
        "total mass with unit margins",
    )
    return [step], step.result


def _system_margined_total(ctx: _Ctx) -> Cell:
    steps, unit_margined = _unit_margined_total(ctx)
    margin = ctx.system_margin()
    value = system_margined_kg(_float(unit_margined), _float(margin))
    step = Step(
        "System margin on the margined total",
        (unit_margined, margin),
        Quantity("total mass with system margin", value, "kg", "this step"),
        "MASS-SYSMARGIN",
    )
    return [*steps, step], step.result


def _cog_axis(ctx: _Ctx, axis: int) -> Cell:
    placed = ctx.placed()
    left_out = [r.item_id for r in ctx.phase.rows if r.position_m is None and r.mass_kg > 0.0]
    inputs: list[Quantity] = []
    pairs: list[tuple[float, Vec3]] = []
    for r in placed:
        assert r.position_m is not None
        inputs.append(ctx.mass(r))
        inputs.append(ctx.position(r, axis))
        pairs.append((r.mass_kg, r.position_m))
    found = center_of_gravity(pairs)
    value = None if found is None else found[1][axis]
    logic = "Nominal masses (without margins) of the items that have a position."
    if left_out:
        logic += f" Left out, because they have no position: {', '.join(left_out)}."
    if found is None:
        logic += " No item has both a position and a mass, so the centre of gravity is n/a."
    step = Step(
        f"Centre of gravity, {AXES[axis]} coordinate",
        tuple(inputs),
        Quantity(f"centre of gravity {AXES[axis]}", value, "m", "this step"),
        "MASS-COG",
        logic,
    )
    return [step], step.result


def _cog_mass(ctx: _Ctx) -> Cell:
    placed = ctx.placed()
    found = center_of_gravity([(r.mass_kg, r.position_m) for r in placed if r.position_m])
    members = [Quantity(r.item_id, r.mass_kg, "kg", ctx.items_ref("Mass (kg)")) for r in placed]
    step = Step(
        "Mass in the centre of gravity calculation",
        tuple(members),
        Quantity(
            "mass in the centre of gravity calculation",
            None if found is None else found[0],
            "kg",
            "this step",
        ),
        logic="Sum of the nominal masses of the items that have a position and a mass.",
    )
    return [step], step.result


def _cog_coverage(ctx: _Ctx) -> Cell:
    steps, included = _cog_mass(ctx)
    nominal_steps, nominal = _nominal_total(ctx)
    cog = ctx.phase.cog
    value = None if cog is None else cog.coverage_ratio
    step = Step(
        "Share of the nominal total that is in the calculation",
        (included, nominal),
        Quantity("centre of gravity coverage", value, "ratio", "this step"),
        logic="Mass in the calculation divided by the nominal total (0 when the total is 0).",
    )
    return [*steps, *nominal_steps, step], step.result


_TOTAL_ROWS: dict[str, Callable[[_Ctx], Cell]] = {
    "Total, nominal": _nominal_total,
    "Total, with unit margins": _unit_margined_total,
    "Total, with system margin": _system_margined_total,
    "Mass in the CG calculation (kg)": _cog_mass,
}


def _totals_cell(ctx: _Ctx, key: Sequence[str], column: str) -> Cell:
    if column != "Value":
        raise ExplainError("This column is not explained.")
    label = key[0]
    if label in _TOTAL_ROWS:
        return _TOTAL_ROWS[label](ctx)
    for axis in range(3):
        if label == f"Centre of gravity {AXES[axis]} (m)":
            return _cog_axis(ctx, axis)
    if label == "Centre of gravity" and ctx.phase.cog is None:
        step = Step(
            "Centre of gravity",
            (),
            Quantity("centre of gravity", None, "m", "this step"),
            "MASS-COG",
            "No item has both a position and a mass, so the centre of gravity is n/a.",
        )
        return [step], step.result
    raise ExplainError("There is no such row in this table.")


# ---- inertia ------------------------------------------------------------------------------------
def _inertia_cell(ctx: _Ctx, key: Sequence[str], column: str) -> Cell:
    if key[0] not in TENSOR_NAMES:
        raise ExplainError("There is no such entry in this table.")
    entry = TENSOR_NAMES.index(key[0])
    about_cg = column == "About CG (kg m2)"
    if not about_cg and column != "About origin (kg m2)":
        raise ExplainError("This column is not explained.")
    cog = ctx.phase.cog
    steps: list[Step] = []
    point: Vec3 = (0.0, 0.0, 0.0)
    refs: list[Quantity] = [
        Quantity(f"{AXES[a]} of the origin", 0.0, "m", "the origin of the body frame")
        for a in range(3)
    ]
    if about_cg:
        refs = []
        for axis in range(3):
            sub, q = _cog_axis(ctx, axis)
            steps.extend(sub)
            refs.append(q)
        if cog is None:
            end = Step(
                "Inertia about the centre of gravity",
                tuple(refs),
                Quantity(f"{key[0]} about the centre of gravity", None, "kg m2", "this step"),
                logic="There is no centre of gravity, so the inertia is n/a.",
            )
            return [*steps, end], end.result
        point = cog.position_m
    elif cog is None:
        end = Step(
            "Inertia about the origin",
            (),
            Quantity(f"{key[0]} about the origin", None, "kg m2", "this step"),
            logic="No item has both a position and a mass, so the inertia is n/a.",
        )
        return [end], end.result
    contributions: list[Quantity] = []
    for r in ctx.placed():
        assert r.position_m is not None
        d = (
            r.position_m[0] - point[0],
            r.position_m[1] - point[1],
            r.position_m[2] - point[2],
        )
        own = r.own_inertia or ZERO
        value = parallel_axis(own, r.mass_kg, d).entries()[entry]
        result = Quantity(f"{key[0]} of {r.item_id} about the reference point", value, "kg m2")
        steps.append(
            Step(
                f"Inertia of {r.item_id} about the reference point",
                (
                    ctx.own_inertia(r, entry),
                    ctx.mass(r),
                    *(ctx.position(r, a) for a in range(3)),
                    *refs,
                ),
                replace(result, origin="this step"),
                "MASS-PARALLEL",
                "d is the position of the item minus the reference point."
                + ("" if r.own_inertia else " The item has no own inertia: a point mass."),
            )
        )
        contributions.append(replace(result, origin="step above"))
    total = math.fsum(float(c.value) for c in contributions if isinstance(c.value, float))
    name = "centre of gravity" if about_cg else "origin"
    final = Step(
        f"Sum over the items: {key[0]} about the {name}",
        tuple(contributions),
        Quantity(f"{key[0]} about the {name}", total, "kg m2", "this step"),
        logic="Sum of the contributions above.",
    )
    return [*steps, final], final.result


# ---- the summary and the limits --------------------------------------------------------------
def _summary_cell(ctx: _Ctx, column: str) -> Cell:
    if column == "Total (kg)":
        return _nominal_total(ctx)
    if column == "With unit margins (kg)":
        return _unit_margined_total(ctx)
    if column == "With system margin (kg)":
        return _system_margined_total(ctx)
    for axis in range(3):
        if column == f"CG {AXES[axis]} (m)":
            return _cog_axis(ctx, axis)
    if column == "CG coverage":
        return _cog_coverage(ctx)
    raise ExplainError("This column is not explained.")


def _limit_index(project: Project, phase: str, name: str) -> int:
    limits = project.config.mass_limits
    for index, limit in enumerate(limits.limits if limits else []):
        if limit.name == name and (limit.phase is None or limit.phase == phase):
            return index
    raise ExplainError("There is no such limit in this table.")


def _limits_cell(
    project: Project, result: StaticMassResult, key: Sequence[str], column: str
) -> Cell:
    if len(key) < 2:
        raise ExplainError("Name the phase and the limit.")
    phase = next((p for p in result.phases if p.phase == key[0]), None)
    if phase is None:
        raise ExplainError("There is no such mission phase.")
    check = next((c for c in phase.limits if c.name == key[1]), None)
    if check is None:
        raise ExplainError("There is no such limit in this phase.")
    ctx = _Ctx(project, result, phase)
    index = _limit_index(project, phase.phase, check.name)
    item = project.config.mass_limits.limits[index].limit_kg if project.config.mass_limits else None
    limit_q = Quantity(
        f"limit {check.name}",
        _sourced_value(item),
        "kg",
        f"{LIMITS_FILE} limits[{index}].limit_kg",
        _src(item),
    )
    if column in ("Phase", "Limit"):
        label, value = (
            ("mission phase", phase.phase) if column == "Phase" else ("limit name", check.name)
        )
        return _read(Quantity(label, value, "", f"{LIMITS_FILE} limits[{index}]"))
    if column == "Limit value (kg)":
        return _read(limit_q)
    steps, total = _system_margined_total(ctx)
    if column == "Total (kg)":
        return steps, total
    margin = _limit_margin(check, limit_q, total)
    if column == "Margin (kg)":
        return [*steps, margin], margin.result
    if column == "Status":
        status = Step(
            "Status against the limit",
            (margin.result,),
            Quantity("status", check.status, "", "this step"),
            logic="ok when the margin is zero or positive, exceeded when it is negative, n/a when "
            "the limit or the total is n/a.",
        )
        return [*steps, margin, status], status.result
    raise ExplainError("This column is not explained.")


def _limit_margin(check: LimitCheck, limit_q: Quantity, total: Quantity) -> Step:
    limit, mass = _float(limit_q), _float(total)
    value = None if limit is None or mass is None else limit_margin_kg(limit, mass)
    return Step(
        "Margin to the limit",
        (limit_q, total),
        Quantity(f"margin to limit {check.name}", value, "kg", "this step"),
        logic="Limit minus the system-margined total; a margin within 1e-9 of the limit "
        "(relative) is taken as 0, since the sum of the masses carries rounding noise.",
    )


# ---- entry points -------------------------------------------------------------------------
def mass_table_ids(project: Project) -> list[tuple[str, str]]:
    """(table id, title) of every explainable static mass table."""
    out = [
        ("mass:summary", "Mass and centre of gravity by mission phase"),
        ("mass:limits", "Mass limits (checked against the system-margined total)"),
    ]
    for phase in project.phases:
        out += [
            (f"mass:items:{phase}", f"Items (phase {phase})"),
            (f"mass:subsystems:{phase}", f"By subsystem (phase {phase})"),
            (f"mass:totals:{phase}", f"Totals and centre of gravity (phase {phase})"),
            (f"mass:inertia:{phase}", f"Inertia tensor (phase {phase})"),
        ]
    return out


_TITLES = {
    "items": "Items",
    "subsystems": "By subsystem",
    "totals": "Totals and centre of gravity",
    "inertia": "Inertia tensor",
}


def explain_mass(
    project: Project,
    table_id: str,
    key: Sequence[str],
    column: str,
    result: StaticMassResult | None = None,
) -> Explanation:
    result = static_mass_budget(project) if result is None else result
    parts = table_id.split(":", 2)
    kind = parts[1] if len(parts) > 1 else ""
    if not key:
        raise ExplainError("Name the row.")
    address = (table_id, tuple(key), column)
    if kind == "limits":
        steps, final = _limits_cell(project, result, key, column)
        title = f"Mass limits / {' / '.join(key)} / {column}"
    elif kind == "summary":
        phase = next((p for p in result.phases if p.phase == key[0]), None)
        if phase is None:
            raise ExplainError("There is no such mission phase in this table.")
        ctx = _Ctx(project, result, phase)
        if column == "Phase":
            steps, final = _read(Quantity("mission phase", phase.phase, "", "spacecraft.yaml"))
        else:
            steps, final = _summary_cell(ctx, column)
        title = f"Mass by mission phase / {key[0]} / {column}"
    elif kind in _TITLES:
        phase_id = parts[2] if len(parts) > 2 else ""
        phase = next((p for p in result.phases if p.phase == phase_id), None)
        if phase is None:
            raise ExplainError("There is no such mission phase.")
        ctx = _Ctx(project, result, phase)
        labels = {"subsystems": "Subsystem", "totals": "Quantity", "inertia": "Entry"}
        if kind in labels and column == labels[kind]:
            steps, final = _read(Quantity("row label", key[0], "", "fixed by the table"))
        elif kind == "items":
            steps, final = _item_cell(ctx, key, column)
        elif kind == "subsystems":
            steps, final = _subsystem_cell(ctx, key, column)
        elif kind == "totals":
            steps, final = _totals_cell(ctx, key, column)
        else:
            steps, final = _inertia_cell(ctx, key, column)
        title = f"{_TITLES[kind]} (phase {phase.phase}) / {key[0]} / {column}"
    else:
        raise ExplainError("This table cannot be explained.")
    linked = link_steps(tuple(steps))
    return Explanation(
        address, title, replace(final, origin=""), linked, equations=equations_used(linked)
    )
