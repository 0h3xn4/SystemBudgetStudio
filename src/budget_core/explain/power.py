"""Explanations of the static power budget (tables of `reports/power_report.py`, D-206).

Each table has an id (`Table.explain_id`): `power:summary`, and per spacecraft mode
`power:units:<mode_id>`, `power:subsystems:<mode_id>`, `power:buses:<mode_id>` and
`power:totals:<mode_id>`. A cell is named by the id, the values of the row's key columns and the
column header. The explanation computes the cell again with the functions the solver uses
(`effective_power_w`, `with_margin_w`, `system_margined_w`, `source_power_w`, `peak_load_w`), so the
numbers agree with the table by construction; a test checks every cell.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import replace

from budget_core.explain.trace import Explanation, Quantity, Step, equations_used, link_steps
from budget_core.model import Project, Sourced
from budget_core.power.static_budget import (
    BusPower,
    ModePowerResult,
    StaticPowerResult,
    UnitPowerRow,
    effective_power_w,
    peak_load_w,
    source_power_w,
    static_power_budget,
    system_margined_w,
    with_margin_w,
)

MARGIN_FILE = "config/margin_policy.yaml"
POWER_FILE = "config/power_config.yaml"


class ExplainError(ValueError):
    """The cell cannot be explained; the message says why in plain words."""


def _src(item: Sourced | None) -> str:
    return "" if item is None else item.source


def _sourced_value(item: Sourced | None) -> float | None:
    return None if item is None or item.is_placeholder else item.value


class _Ctx:
    def __init__(self, project: Project, result: StaticPowerResult, mode: ModePowerResult) -> None:
        self.project = project
        self.result = result
        self.mode = mode
        self.policy = project.config.margin_policy
        self.power = project.config.power_config

    # ---- inputs, each with where it comes from --------------------------------------------
    def unit_input(
        self, row: UnitPowerRow, field: str, value: float, unit: str, name: str
    ) -> Quantity:
        unit_model = self.project.units[row.unit_id]
        index = next(i for i, m in enumerate(unit_model.modes) if m.name == row.power_mode)
        return Quantity(
            f"{name} of {row.unit_id}",
            value,
            unit,
            f"units/{row.unit_id}.yaml modes[{index}].{field}",
        )

    def class_margin(self, maturity: str) -> Quantity:
        item = (
            self.policy.classes[maturity].power_margin_ratio
            if self.policy and maturity in self.policy.classes
            else None
        )
        return Quantity(
            f"margin of maturity class {maturity}",
            _sourced_value(item),
            "ratio",
            f"{MARGIN_FILE} classes.{maturity}.power_margin_ratio" + ("" if item else " (missing)"),
            _src(item),
        )

    def system_margin(self) -> Quantity:
        item = self.policy.system_power_margin_ratio if self.policy else None
        return Quantity(
            "system margin",
            _sourced_value(item),
            "ratio",
            f"{MARGIN_FILE} system_power_margin_ratio" + ("" if item else " (missing)"),
            _src(item),
        )

    def efficiency(self, bus: str) -> Quantity:
        item = self.power.converter_efficiency_ratio.get(bus) if self.power is not None else None
        return Quantity(
            f"converter efficiency of bus {bus}",
            _sourced_value(item),
            "ratio",
            f"{POWER_FILE} converter_efficiency_ratio.{bus}" + ("" if item else " (missing)"),
            _src(item),
        )

    def loss(self) -> Quantity:
        item = self.power.distribution_loss_ratio if self.power is not None else None
        return Quantity(
            "distribution loss",
            _sourced_value(item),
            "ratio",
            f"{POWER_FILE} distribution_loss_ratio" + ("" if item else " (missing)"),
            _src(item),
        )


def _table_ref(mode: ModePowerResult, table: str, column: str) -> str:
    return f"table '{table}', column {column}"


# ---- one unit ---------------------------------------------------------------------------------
def _effective_step(ctx: _Ctx, r: UnitPowerRow) -> Step:
    avg = ctx.unit_input(r, "avg_power_w", r.avg_power_w, "W", "average power")
    duty = ctx.unit_input(r, "duty_cycle_ratio", r.duty_cycle_ratio, "ratio", "duty cycle")
    value = effective_power_w(r.avg_power_w, r.duty_cycle_ratio)
    return Step(
        "Effective power of the unit",
        (avg, duty),
        Quantity(f"effective power of {r.unit_id}", value, "W", "this step"),
        "PWR-EFF",
    )


def _margin_step(ctx: _Ctx, r: UnitPowerRow) -> Step:
    margin = ctx.class_margin(r.maturity)
    return Step(
        "Margin of the unit's maturity class",
        (margin,),
        Quantity(f"margin of {r.unit_id}", r.margin_ratio, "ratio", "this step"),
        logic=f"The unit's maturity class is '{r.maturity}'; its margin is looked up in the "
        "margin policy. A placeholder or a missing class gives n/a.",
    )


def _margined_steps(ctx: _Ctx, r: UnitPowerRow, *, peak: bool) -> list[Step]:
    steps: list[Step] = []
    if peak:
        base = ctx.unit_input(r, "peak_power_w", r.peak_power_w, "W", "peak power")
    else:
        eff = _effective_step(ctx, r)
        steps.append(eff)
        base = eff.result
    steps.append(_margin_step(ctx, r))
    value = with_margin_w(base.value if isinstance(base.value, float) else 0.0, r.margin_ratio)
    steps.append(
        Step(
            "Power with the maturity margin",
            (base, Quantity(f"margin of {r.unit_id}", r.margin_ratio, "ratio", "previous step")),
            Quantity(
                f"{'peak ' if peak else ''}power of {r.unit_id} with margin",
                value,
                "W",
                "this step",
            ),
            "PWR-MARGIN",
        )
    )
    return steps


def _unit_cell(ctx: _Ctx, key: Sequence[str], column: str) -> tuple[list[Step], Quantity]:
    row = next((r for r in ctx.mode.rows if r.unit_id == key[0]), None)
    if row is None:
        raise ExplainError("There is no such unit in this table.")
    plain = {
        "Unit": ("id", row.unit_id),
        "Name": ("name", row.unit_name),
        "Subsystem": ("subsystem", row.subsystem),
        "Bus": ("bus", row.bus),
        "Power mode": ("power mode of this spacecraft mode", row.power_mode),
    }
    if column in plain:
        label, value = plain[column]
        q = Quantity(f"{label} of {row.unit_id}", value, "", f"units/{row.unit_id}.yaml / modes/")
        return [Step("Read from the project", (), q, logic="Not computed: an input.")], q
    if column == "Average (W)":
        q = ctx.unit_input(row, "avg_power_w", row.avg_power_w, "W", "average power")
        return [Step("Read from the project", (), q, logic="Not computed: an input.")], q
    if column == "Duty":
        q = ctx.unit_input(row, "duty_cycle_ratio", row.duty_cycle_ratio, "ratio", "duty cycle")
        return [Step("Read from the project", (), q, logic="Not computed: an input.")], q
    if column == "Peak (W)":
        q = ctx.unit_input(row, "peak_power_w", row.peak_power_w, "W", "peak power")
        return [Step("Read from the project", (), q, logic="Not computed: an input.")], q
    if column == "Effective (W)":
        step = _effective_step(ctx, row)
        return [step], step.result
    if column == "Margin":
        step = _margin_step(ctx, row)
        return [step], step.result
    if column == "With margin (W)":
        steps = _margined_steps(ctx, row, peak=False)
        return steps, steps[-1].result
    raise ExplainError("This column is not explained.")


# ---- sums --------------------------------------------------------------------------------------
def _sum_step(
    label: str,
    members: Sequence[Quantity],
    result_name: str,
    unit: str,
    *,
    equation_id: str | None = None,
    logic: str = "",
) -> Step:
    values = [m.value for m in members]
    total: float | None
    if any(v is None for v in values):
        total = None
    elif equation_id == "PWR-PEAK":
        total = peak_load_w(float(v) for v in values if isinstance(v, float))
    else:
        total = math.fsum(float(v) for v in values if isinstance(v, float))
    note = logic or "Sum of the values above."
    if total is None:
        note += " A member is n/a, so the sum is n/a."
    return Step(
        label, tuple(members), Quantity(result_name, total, unit, "this step"), equation_id, note
    )


def _member(mode: ModePowerResult, r: UnitPowerRow, field: str, column: str) -> Quantity:
    return Quantity(
        r.unit_id,
        getattr(r, field),
        "W",
        _table_ref(mode, f"Units in mode {mode.mode_name}", column),
    )


_SUBSYSTEM = {
    "Effective (W)": ("effective_power_w", "Effective (W)", None),
    "With margin (W)": ("margined_power_w", "With margin (W)", None),
    "Peak (W)": ("peak_power_w", "Peak (W)", "PWR-PEAK"),
    "Peak with margin (W)": ("margined_peak_w", "With margin (W)", None),
}


def _subsystem_cell(ctx: _Ctx, key: Sequence[str], column: str) -> tuple[list[Step], Quantity]:
    name = key[0]
    members = [r for r in ctx.mode.rows if r.subsystem == name]
    if not members:
        raise ExplainError("There is no such subsystem in this table.")
    if column not in _SUBSYSTEM:
        raise ExplainError("This column is not explained.")
    field, source_column, equation = _SUBSYSTEM[column]
    quantities = [_member(ctx.mode, r, field, source_column) for r in members]
    if field == "margined_peak_w":
        quantities = [
            Quantity(
                q.name, r.margined_peak_w, "W", "peak power with the unit's margin (PWR-MARGIN)"
            )
            for q, r in zip(quantities, members, strict=True)
        ]
    step = _sum_step(
        f"Sum over the units of subsystem {name}",
        quantities,
        f"{column.split(' (')[0].lower()} of subsystem {name}",
        "W",
        equation_id=equation,
        logic="Every unit at its peak at once (conservative)." if equation == "PWR-PEAK" else "",
    )
    return [step], step.result


# ---- buses and totals ---------------------------------------------------------------------------
_FLOW_FIELDS = {
    "load_w": "Average load (W)",
    "unit_margined_w": "Average load, with unit margins",
    "system_margined_w": "Average load, with margins (W)",
    "source_w": "Average at source (W)",
    "source_margined_w": "Average at source, with margins (W)",
}


def _bus_flow(ctx: _Ctx, bus: BusPower, which: str, field: str) -> tuple[list[Step], Quantity]:
    """The steps from the units of one bus to one field of its `average` or `peak` flow."""
    members = [r for r in ctx.mode.rows if r.bus == bus.bus]
    peak = which == "peak"
    steps: list[Step] = []

    def load() -> Quantity:
        if peak:
            qs = [_member(ctx.mode, r, "peak_power_w", "Peak (W)") for r in members]
            step = _sum_step(
                f"Peak load of bus {bus.bus}",
                qs,
                f"peak load of bus {bus.bus}",
                "W",
                equation_id="PWR-PEAK",
                logic="Every unit at its peak at once (conservative).",
            )
        else:
            qs = [_member(ctx.mode, r, "effective_power_w", "Effective (W)") for r in members]
            step = _sum_step(
                f"Average load of bus {bus.bus}", qs, f"average load of bus {bus.bus}", "W"
            )
        steps.append(step)
        return step.result

    def unit_margined() -> Quantity:
        field_name = "margined_peak_w" if peak else "margined_power_w"
        column = "With margin (W)"
        qs = [_member(ctx.mode, r, field_name, column) for r in members]
        step = _sum_step(
            f"{'Peak ' if peak else ''}load of bus {bus.bus} with the unit margins",
            qs,
            f"{'peak ' if peak else ''}load of bus {bus.bus} with unit margins",
            "W",
        )
        steps.append(step)
        return step.result

    def system_margined(unit_margined_q: Quantity) -> Quantity:
        margin = ctx.system_margin()
        value = system_margined_w(
            unit_margined_q.value if isinstance(unit_margined_q.value, float) else None,
            margin.value if isinstance(margin.value, float) else None,
        )
        step = Step(
            "System margin on the margined load",
            (unit_margined_q, margin),
            Quantity(f"load of bus {bus.bus} with system margin", value, "W", "this step"),
            "PWR-SYSMARGIN",
        )
        steps.append(step)
        return step.result

    def source(load_q: Quantity, name: str) -> Quantity:
        eta, loss = ctx.efficiency(bus.bus), ctx.loss()
        value = source_power_w(
            load_q.value if isinstance(load_q.value, float) else None,
            eta.value if isinstance(eta.value, float) else None,
            loss.value if isinstance(loss.value, float) else None,
        )
        step = Step(
            "Power at the source, through the converter and the distribution",
            (load_q, eta, loss),
            Quantity(name, value, "W", "this step"),
            "PWR-SOURCE",
        )
        steps.append(step)
        return step.result

    if field == "load_w":
        return steps, load()
    if field == "unit_margined_w":
        return steps, unit_margined()
    if field == "system_margined_w":
        return steps, system_margined(unit_margined())
    if field == "source_w":
        return steps, source(load(), f"source power of bus {bus.bus}")
    return steps, source(
        system_margined(unit_margined()), f"source power of bus {bus.bus} with margins"
    )


_BUS_COLUMNS = {
    "Average load (W)": ("average", "load_w"),
    "Average load, with margins (W)": ("average", "system_margined_w"),
    "Average at source (W)": ("average", "source_w"),
    "Average at source, with margins (W)": ("average", "source_margined_w"),
    "Peak load (W)": ("peak", "load_w"),
    "Peak at source, with margins (W)": ("peak", "source_margined_w"),
}


def _bus_cell(ctx: _Ctx, key: Sequence[str], column: str) -> tuple[list[Step], Quantity]:
    bus = next((b for b in ctx.mode.buses if b.bus == key[0]), None)
    if bus is None:
        raise ExplainError("There is no such bus in this table.")
    if column == "Converter efficiency":
        q = ctx.efficiency(bus.bus)
        return [Step("Read from the configuration", (), q, logic="Not computed: an input.")], q
    if column not in _BUS_COLUMNS:
        raise ExplainError("This column is not explained.")
    which, field = _BUS_COLUMNS[column]
    return _bus_flow(ctx, bus, which, field)


_TOTAL_ROWS = {
    "Load, nominal": "load_w",
    "Load, with unit margins": "unit_margined_w",
    "Load, with system margin": "system_margined_w",
    "Source, nominal": "source_w",
    "Source, with margins": "source_margined_w",
}


def _total(ctx: _Ctx, which: str, field: str) -> tuple[list[Step], Quantity]:
    steps: list[Step] = []
    parts: list[Quantity] = []
    for bus in ctx.mode.buses:
        sub, result = _bus_flow(ctx, bus, which, field)
        steps.extend(sub)
        parts.append(Quantity(f"bus {bus.bus}", result.value, "W", f"step above ({result.name})"))
    total = _sum_step(
        f"Sum over the buses of mode {ctx.mode.mode_name}",
        parts,
        f"{which} {field.replace('_w', '').replace('_', ' ')} of the spacecraft",
        "W",
    )
    steps.append(total)
    return steps, total.result


def _totals_cell(ctx: _Ctx, key: Sequence[str], column: str) -> tuple[list[Step], Quantity]:
    if key[0] not in _TOTAL_ROWS:
        raise ExplainError("There is no such row in this table.")
    which = {"Average": "average", "Peak": "peak"}.get(column.split(" (")[0])
    if which is None:
        raise ExplainError("This column is not explained.")
    return _total(ctx, which, _TOTAL_ROWS[key[0]])


_SUMMARY = {
    "Average load (W)": ("average", "load_w"),
    "Average, unit margins (W)": ("average", "unit_margined_w"),
    "Average, system margin (W)": ("average", "system_margined_w"),
    "Average at source (W)": ("average", "source_w"),
    "Average at source, with margins (W)": ("average", "source_margined_w"),
    "Peak load (W)": ("peak", "load_w"),
    "Peak at source, with margins (W)": ("peak", "source_margined_w"),
}


# ---- entry points -------------------------------------------------------------------------
def table_titles(mode: ModePowerResult) -> dict[str, str]:
    name = mode.mode_name
    return {
        "summary": "Power by spacecraft mode",
        "units": f"Units in mode {name}",
        "subsystems": f"By subsystem (mode {name})",
        "buses": f"By supply bus (mode {name})",
        "totals": f"Totals (mode {name})",
    }


def power_table_ids(project: Project) -> list[tuple[str, str]]:
    """(table id, title) of every explainable static power table."""
    out = [("power:summary", "Power by spacecraft mode")]
    for mode_id in sorted(project.modes):
        name = project.modes[mode_id].name
        out += [
            (f"power:units:{mode_id}", f"Units in mode {name}"),
            (f"power:subsystems:{mode_id}", f"By subsystem (mode {name})"),
            (f"power:buses:{mode_id}", f"By supply bus (mode {name})"),
            (f"power:totals:{mode_id}", f"Totals (mode {name})"),
        ]
    return out


def explain_power(
    project: Project,
    table_id: str,
    key: Sequence[str],
    column: str,
    result: StaticPowerResult | None = None,
) -> Explanation:
    parts = table_id.split(":")
    result = static_power_budget(project) if result is None else result
    kind = parts[1] if len(parts) > 1 else ""
    if kind == "summary":
        mode = next((m for m in result.modes if m.mode_name == key[0]), None)
        if mode is None:
            raise ExplainError("There is no such spacecraft mode in this table.")
    else:
        mode_id = parts[2] if len(parts) > 2 else ""
        mode = next((m for m in result.modes if m.mode_id == mode_id), None)
        if mode is None:
            raise ExplainError("There is no such spacecraft mode.")
    if not key:
        raise ExplainError("Name the row.")
    ctx = _Ctx(project, result, mode)
    handlers: dict[str, Callable[[_Ctx, Sequence[str], str], tuple[list[Step], Quantity]]] = {
        "units": _unit_cell,
        "subsystems": _subsystem_cell,
        "buses": _bus_cell,
        "totals": _totals_cell,
    }
    labels = {
        "summary": ("Mode", "Name of the spacecraft mode", f"modes/{mode.mode_id}.yaml name"),
        "subsystems": ("Subsystem", "Subsystem name", "the subsystem field of the units"),
        "buses": ("Bus", "Supply bus name", "the bus field of the units"),
        "totals": ("Quantity", "Row label", "fixed by the table"),
    }
    if kind in labels and column == labels[kind][0]:
        _, what, origin = labels[kind]
        q = Quantity(what, key[0], "", origin)
        step = Step("A label", (), q, logic="Not computed: it names the row.")
        return Explanation(
            (table_id, tuple(key), column),
            f"{table_titles(mode)[kind]} / {key[0]} / {column}",
            q,
            link_steps((step,)),
        )
    if kind == "summary":
        if column not in _SUMMARY:
            raise ExplainError("This column is not explained.")
        which, field = _SUMMARY[column]
        steps, final = _total(ctx, which, field)
        title = f"Power by spacecraft mode / {mode.mode_name} / {column}"
    elif kind in handlers:
        steps, final = handlers[kind](ctx, key, column)
        table = {
            "units": f"Units in mode {mode.mode_name}",
            "subsystems": f"By subsystem (mode {mode.mode_name})",
            "buses": f"By supply bus (mode {mode.mode_name})",
            "totals": f"Totals (mode {mode.mode_name})",
        }[kind]
        title = f"{table} / {key[0]} / {column}"
    else:
        raise ExplainError("This table cannot be explained.")
    linked = link_steps(tuple(steps))
    return Explanation(
        (table_id, tuple(key), column),
        title,
        replace(final, origin=""),
        linked,
        equations=equations_used(linked),
    )
