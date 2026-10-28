"""Explanations of the static thermal budget (tables of `reports/thermal_report.py`, D-206).

Table ids (`Table.explain_id`): `thermal:summary`, and per spacecraft mode
`thermal:units:<mode_id>`, `thermal:subsystems:<mode_id>` and `thermal:nodes:<mode_id>` (the
dissipation), and per thermal case `thermal:temperatures:<case>` and `thermal:limits:<case>`.

The dissipation and the limit checks are computed again with the functions of the solver
(`dissipation_w`, `limit_status`). A node temperature is not: the temperatures of all nodes are
found together by an iteration (`solve_steady_state`, TH-BAL), so no formula gives one of them
from its own inputs. Its explanation shows every term of the node's heat balance (heat
dissipated, absorbed from the environment, radiated to space, conducted to the neighbours), each
computed again from the inputs with the solver's functions, takes the temperature from the solver
and checks that the balance closes at it. A test compares every cell of every table with its
explanation.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace

import numpy as np

from budget_core.explain.power import ExplainError
from budget_core.explain.trace import Explanation, Quantity, Step, equations_used, link_steps
from budget_core.model import Project, Sourced, ThermalCase
from budget_core.model.thermal import Surface
from budget_core.reports.thermal_report import ABSOLUTE_ZERO_OFFSET_K
from budget_core.thermal.static_thermal import (
    CaseThermal,
    ModeHeat,
    NodeTemperature,
    StaticThermalResult,
    UnitHeat,
    absorbed_w,
    dissipation_w,
    limit_status,
    radiation_coefficient_wk4,
    static_thermal_budget,
)
from budget_core.thermal.steady_state import STEFAN_BOLTZMANN_SOURCE, STEFAN_BOLTZMANN_WM2K4

MODEL_FILE = "config/thermal_model.yaml"
ENV_FILE = "config/thermal_environment.yaml"

Cell = tuple[list[Step], Quantity]


def _src(item: Sourced | None) -> str:
    return "" if item is None else item.source


def _value(item: Sourced | None) -> float | None:
    return None if item is None or item.is_placeholder else item.value


def _read(q: Quantity, logic: str = "Not computed: an input.") -> Cell:
    return [Step("Read from the project", (), q, logic=logic)], q


def _float(q: Quantity) -> float | None:
    return q.value if isinstance(q.value, float) else None


def _sourced(name: str, item: Sourced | None, unit: str, file: str, path: str) -> Quantity:
    return Quantity(
        name,
        _value(item),
        unit,
        f"{file} {path}" + ("" if item is not None else " (missing)"),
        _src(item),
    )


def _sequential(values: Sequence[float]) -> float:
    """The sum in the order given, one addition at a time, as the solver accumulates it."""
    total = 0.0
    for v in values:
        total += v
    return total


# ---- dissipation ------------------------------------------------------------------------------
@dataclass
class _HeatCtx:
    project: Project
    mode: ModeHeat

    def ratio(self, row: UnitHeat) -> Quantity:
        unit = self.project.units[row.unit_id]
        index = next(i for i, m in enumerate(unit.modes) if m.name == row.power_mode)
        return Quantity(
            f"heat dissipation ratio of {row.unit_id}",
            row.heat_dissipation_ratio,
            "ratio",
            f"units/{row.unit_id}.yaml modes[{index}].heat_dissipation_ratio"
            + ("" if row.heat_dissipation_ratio is not None else " (not given)"),
        )

    def table(self) -> str:
        return f"table 'Units in mode {self.mode.mode_name}'"


def _dissipation_step(ctx: _HeatCtx, row: UnitHeat, *, peak: bool) -> Step:
    power_name, column, power = (
        ("peak power", "Peak power (W) of the power table", row.peak_power_w)
        if peak
        else ("effective power", "Effective (W) of the power table", row.effective_power_w)
    )
    power_q = Quantity(
        f"{power_name} of {row.unit_id}",
        power,
        "W",
        f"{column}, mode {ctx.mode.mode_name} (explain it with power:units:{ctx.mode.mode_id})",
    )
    ratio = ctx.ratio(row)
    value = dissipation_w(power, row.heat_dissipation_ratio)
    return Step(
        "Heat dissipated in the unit",
        (power_q, ratio),
        Quantity(f"{'peak ' if peak else ''}dissipation of {row.unit_id}", value, "W", "this step"),
        "TH-DISS",
        "A unit with no heat dissipation ratio for its power mode gives n/a: the ratio is never "
        "assumed."
        if row.heat_dissipation_ratio is None
        else "",
    )


def _unit_cell(ctx: _HeatCtx, key: Sequence[str], column: str) -> Cell:
    row = next((r for r in ctx.mode.rows if r.unit_id == key[0]), None)
    if row is None:
        raise ExplainError("There is no such unit in this table.")
    plain = {
        "Unit": ("id", row.unit_id, f"units/{row.unit_id}.yaml"),
        "Name": ("name", row.unit_name, f"units/{row.unit_id}.yaml name"),
        "Subsystem": ("subsystem", row.subsystem, f"units/{row.unit_id}.yaml subsystem"),
        "Node": (
            "thermal node",
            row.node,
            f"units/{row.unit_id}.yaml thermal_node (the subsystem when it names none)",
        ),
        "Power mode": ("power mode of this spacecraft mode", row.power_mode, "modes/"),
    }
    if column in plain:
        label, value, origin = plain[column]
        return _read(Quantity(f"{label} of {row.unit_id}", value, "", origin))
    if column == "Effective power (W)":
        return _read(
            Quantity(
                f"effective power of {row.unit_id}",
                row.effective_power_w,
                "W",
                f"power table, mode {ctx.mode.mode_name} (explain it with "
                f"power:units:{ctx.mode.mode_id})",
            ),
            "Taken from the power budget.",
        )
    if column == "Dissipation ratio":
        return _read(ctx.ratio(row))
    if column in ("Dissipation (W)", "Peak dissipation (W)"):
        step = _dissipation_step(ctx, row, peak=column.startswith("Peak"))
        return [step], step.result
    raise ExplainError("This column is not explained.")


def _fsum_step(label: str, members: Sequence[Quantity], name: str) -> Step:
    values = [m.value for m in members]
    total = (
        None
        if any(v is None for v in values)
        else math.fsum(float(v) for v in values if isinstance(v, float))
    )
    note = "Sum of the values above."
    if total is None:
        note += " A member is n/a, so the sum is n/a."
    return Step(label, tuple(members), Quantity(name, total, "W", "this step"), None, note)


def _members(ctx: _HeatCtx, rows: Sequence[UnitHeat], *, peak: bool) -> list[Quantity]:
    column = "Peak dissipation (W)" if peak else "Dissipation (W)"
    return [
        Quantity(
            r.unit_id,
            r.peak_dissipation_w if peak else r.dissipation_w,
            "W",
            f"{ctx.table()}, column {column}",
        )
        for r in rows
    ]


def _group_cell(ctx: _HeatCtx, key: Sequence[str], column: str, *, nodes: bool) -> Cell:
    groups = ctx.mode.nodes if nodes else ctx.mode.subsystems
    if not any(g.name == key[0] for g in groups):
        raise ExplainError("There is no such row in this table.")
    attr = "node" if nodes else "subsystem"
    rows = [r for r in ctx.mode.rows if getattr(r, attr) == key[0]]
    if column not in ("Dissipation (W)", "Peak dissipation (W)"):
        raise ExplainError("This column is not explained.")
    step = _fsum_step(
        f"Sum over the units of {attr} {key[0]}",
        _members(ctx, rows, peak=column.startswith("Peak")),
        f"{'peak ' if column.startswith('Peak') else ''}dissipation of {attr} {key[0]}",
    )
    return [step], step.result


def _summary_cell(ctx: _HeatCtx, column: str) -> Cell:
    if column not in ("Average (W)", "Peak (W)"):
        raise ExplainError("This column is not explained.")
    peak = column == "Peak (W)"
    step = _fsum_step(
        f"Sum over the units in mode {ctx.mode.mode_name}",
        _members(ctx, ctx.mode.rows, peak=peak),
        f"{'peak ' if peak else 'average '}dissipation of the spacecraft",
    )
    return [step], step.result


# ---- node temperatures ---------------------------------------------------------------------------
@dataclass
class _CaseCtx:
    project: Project
    result: StaticThermalResult
    case: CaseThermal
    definition: ThermalCase

    @property
    def heat(self) -> ModeHeat:
        return next(m for m in self.result.modes if m.mode_id == self.case.mode_id)

    def node(self, name: str) -> NodeTemperature:
        found = next((n for n in self.case.nodes if n.node == name), None)
        if found is None:
            raise ExplainError("There is no such node in this table.")
        return found

    def space(self) -> Quantity:
        env = self.project.config.thermal_environment
        item = env.space_temperature_k if env else None
        return _sourced("space temperature", item, "K", ENV_FILE, "space_temperature_k")

    def margin(self) -> Quantity:
        env = self.project.config.thermal_environment
        item = env.temperature_margin_k if env else None
        return _sourced("required temperature margin", item, "K", ENV_FILE, "temperature_margin_k")

    def environment(self, field: str, name: str, unit: str) -> Quantity:
        item = getattr(self.definition, field)
        return _sourced(
            f"{name}, case {self.case.case}",
            item,
            unit,
            ENV_FILE,
            f"cases.{self.case.case}.{field}",
        )


def _not_computed(ctx: _CaseCtx, what: str) -> Cell:
    """The case could not be solved: say which inputs are placeholders or missing."""
    missing = [
        Quantity(a.name, None, a.unit, f"{a.file} {a.path}", a.source)
        for a in ctx.result.assumptions
        if a.placeholder
    ]
    step = Step(
        f"{what} not computed",
        tuple(missing),
        Quantity(what, None, "", "this step"),
        logic="A number the case needs is a placeholder or missing, so no temperature is "
        "computed (never replaced by zero). The placeholders of the thermal configuration are "
        "listed; a case may also fail for another reason, see the Problems panel.",
    )
    return [step], step.result


def _dissipated_cell(ctx: _CaseCtx, node: NodeTemperature) -> Cell:
    heat = ctx.heat
    rows = [r for r in heat.rows if r.node == node.node]
    members = [
        Quantity(
            r.unit_id,
            r.dissipation_w,
            "W",
            f"table 'Units in mode {heat.mode_name}', column Dissipation (W)",
        )
        for r in rows
    ]
    total = _sequential([float(r.dissipation_w) for r in rows if r.dissipation_w is not None])
    step = Step(
        f"Heat dissipated in node {node.node}",
        tuple(members),
        Quantity(f"heat dissipated in node {node.node}", total, "W", "this step"),
        logic=f"The units on the node, in the spacecraft mode of case {ctx.case.case} "
        f"({heat.mode_name}).",
    )
    return [step], step.result


def _surfaces(ctx: _CaseCtx, node: str) -> list[tuple[int, Surface]]:
    model = ctx.project.config.thermal_model
    assert model is not None
    return [(i, s) for i, s in enumerate(model.surfaces) if s.node == node]


def _absorbed_cell(ctx: _CaseCtx, node: NodeTemperature) -> Cell:
    steps: list[Step] = []
    contributions: list[Quantity] = []
    for index, s in _surfaces(ctx, node.node):
        path = f"surfaces[{index}]"
        exposure = s.exposure[ctx.case.case]
        alpha, eps = _value(s.absorptivity_ratio), _value(s.emissivity_ratio)
        sun, earth = _value(exposure.solar_view_ratio), _value(exposure.earth_view_ratio)
        flux, albedo, ir = (
            _value(ctx.definition.solar_flux_wm2),
            _value(ctx.definition.albedo_ratio),
            _value(ctx.definition.earth_ir_wm2),
        )
        assert alpha is not None and eps is not None and sun is not None and earth is not None
        assert flux is not None and albedo is not None and ir is not None
        value = absorbed_w(s.area_m2, alpha, eps, sun, earth, flux, albedo, ir)
        expo = f"{path}.exposure.{ctx.case.case}"
        result = Quantity(f"heat absorbed by surface {s.name}", value, "W", "this step")
        steps.append(
            Step(
                f"Heat absorbed by surface {s.name}",
                (
                    Quantity(f"area of {s.name}", s.area_m2, "m2", f"{MODEL_FILE} {path}.area_m2"),
                    _sourced(
                        f"absorptivity of {s.name}",
                        s.absorptivity_ratio,
                        "ratio",
                        MODEL_FILE,
                        f"{path}.absorptivity_ratio",
                    ),
                    _sourced(
                        f"emissivity of {s.name}",
                        s.emissivity_ratio,
                        "ratio",
                        MODEL_FILE,
                        f"{path}.emissivity_ratio",
                    ),
                    _sourced(
                        f"solar view of {s.name}",
                        exposure.solar_view_ratio,
                        "ratio",
                        MODEL_FILE,
                        f"{expo}.solar_view_ratio",
                    ),
                    _sourced(
                        f"Earth view of {s.name}",
                        exposure.earth_view_ratio,
                        "ratio",
                        MODEL_FILE,
                        f"{expo}.earth_view_ratio",
                    ),
                    ctx.environment("solar_flux_wm2", "solar flux", "W/m2"),
                    ctx.environment("albedo_ratio", "albedo", "ratio"),
                    ctx.environment("earth_ir_wm2", "Earth infrared", "W/m2"),
                ),
                result,
                "TH-ABS",
            )
        )
        contributions.append(replace(result, origin="step above"))
    total = _sequential([float(c.value) for c in contributions if isinstance(c.value, float)])
    final = Step(
        f"Heat absorbed by node {node.node}",
        tuple(contributions),
        Quantity(f"heat absorbed by node {node.node}", total, "W", "this step"),
        logic="Sum over the surfaces of the node; a node with no surface absorbs nothing.",
    )
    return [*steps, final], final.result


def _radiation_cell(ctx: _CaseCtx, node: NodeTemperature) -> Cell:
    steps: list[Step] = []
    parts: list[Quantity] = []
    sigma = Quantity(
        "Stefan-Boltzmann constant",
        STEFAN_BOLTZMANN_WM2K4,
        "W/m2/K4",
        "constant (TH-SB)",
        STEFAN_BOLTZMANN_SOURCE,
    )
    for index, s in _surfaces(ctx, node.node):
        eps = _value(s.emissivity_ratio)
        assert eps is not None
        value = radiation_coefficient_wk4(eps, s.area_m2)
        result = Quantity(f"radiation coefficient of {s.name}", value, "W/K4", "this step")
        steps.append(
            Step(
                f"Radiation of surface {s.name} to space, per T^4",
                (
                    _sourced(
                        f"emissivity of {s.name}",
                        s.emissivity_ratio,
                        "ratio",
                        MODEL_FILE,
                        f"surfaces[{index}].emissivity_ratio",
                    ),
                    sigma,
                    Quantity(
                        f"area of {s.name}",
                        s.area_m2,
                        "m2",
                        f"{MODEL_FILE} surfaces[{index}].area_m2",
                    ),
                ),
                result,
                "TH-SB",
                "emissivity x sigma x area.",
            )
        )
        parts.append(replace(result, origin="step above"))
    total = _sequential([float(p.value) for p in parts if isinstance(p.value, float)])
    steps.append(
        Step(
            f"Radiation coefficient of node {node.node}",
            tuple(parts),
            Quantity(f"radiation coefficient of node {node.node}", total, "W/K4", "this step"),
            logic="Sum over the surfaces of the node.",
        )
    )
    return steps, steps[-1].result


def _temperature_input(node: NodeTemperature) -> Quantity:
    return Quantity(
        f"temperature of node {node.node}",
        node.temperature_k,
        "K",
        "the solver's result for the node (see the step that closes the balance)",
    )


def _radiated_cell(ctx: _CaseCtx, node: NodeTemperature) -> Cell:
    steps, coefficient = _radiation_cell(ctx, node)
    space = ctx.space()
    # numpy scalars, as the solver evaluates it
    value = float(
        coefficient.value * (np.float64(node.temperature_k) ** 4 - (_float(space) or 0.0) ** 4)  # type: ignore[operator]
    )
    value = 0.0 if abs(value) < 1e-9 else value
    step = Step(
        f"Heat radiated to space by node {node.node}",
        (coefficient, _temperature_input(node), space),
        Quantity(f"heat radiated by node {node.node}", value, "W", "this step"),
        "TH-BAL",
        "radiation coefficient x (T^4 - T_space^4); below a nano-watt it is rounding noise and "
        "shown as zero.",
    )
    return [*steps, step], step.result


def _conduction(ctx: _CaseCtx, node: NodeTemperature) -> tuple[list[Quantity], Quantity]:
    model = ctx.project.config.thermal_model
    assert model is not None
    by_node = {n.node: n.temperature_k for n in ctx.case.nodes}
    terms: list[Quantity] = []
    for index, link in enumerate(model.conductances):
        if node.node not in (link.first_node, link.second_node):
            continue
        other = link.second_node if link.first_node == node.node else link.first_node
        g = _value(link.conductance_wk)
        assert g is not None
        terms.append(
            Quantity(
                f"conductance {node.node} - {other}",
                g,
                "W/K",
                f"{MODEL_FILE} conductances[{index}].conductance_wk",
                _src(link.conductance_wk),
            )
        )
        terms.append(
            Quantity(f"temperature of node {other}", by_node[other], "K", "the solver's result")
        )
    out = Quantity(
        f"heat conducted out of node {node.node}", node.conducted_out_w, "W", "this step"
    )
    return terms, out


def _conducted_cell(ctx: _CaseCtx, node: NodeTemperature) -> Cell:
    terms, out = _conduction(ctx, node)
    step = Step(
        f"Heat conducted from node {node.node} to the other nodes",
        (_temperature_input(node), *terms),
        out,
        "TH-BAL",
        "Sum over the neighbours of conductance x (T_node - T_neighbour); a negative value is "
        "heat conducted in. The solver forms it as a matrix product, so it can differ from a "
        "hand sum of the terms in the last digits.",
    )
    return [step], step.result


def _heat_in_steps(ctx: _CaseCtx, node: NodeTemperature) -> tuple[list[Step], Quantity]:
    dis_steps, dissipated = _dissipated_cell(ctx, node)
    abs_steps, absorbed = _absorbed_cell(ctx, node)
    heat_in = Step(
        f"Heat into node {node.node}",
        (dissipated, absorbed),
        Quantity(
            f"heat into node {node.node}",
            float(np.float64(dissipated.value) + np.float64(absorbed.value)),
            "W",
            "this step",
        ),
        logic="Dissipated plus absorbed from the environment.",
    )
    return [*dis_steps, *abs_steps, heat_in], heat_in.result


def _temperature_cell(ctx: _CaseCtx, node: NodeTemperature) -> Cell:
    steps, heat_in = _heat_in_steps(ctx, node)
    rad_steps, radiated = _radiated_cell(ctx, node)
    cond_steps, conducted = _conducted_cell(ctx, node)
    solve = Step(
        f"Temperature of node {node.node}",
        (heat_in, ctx.space()),
        Quantity(f"temperature of node {node.node}", node.temperature_k, "K", "this step"),
        "TH-BAL",
        "The temperatures of all nodes are found together, by a damped Newton iteration "
        "(tolerance 1e-10 K), so that every node's heat balance is zero; no formula gives one "
        "node's temperature from its own inputs. The next steps show the terms of this node's "
        "balance at that temperature.",
    )
    close = Step(
        f"Check: the heat balance of node {node.node} closes",
        (heat_in, radiated, conducted),
        Quantity(
            f"imbalance of node {node.node}",
            float(heat_in.value) - float(radiated.value) - float(conducted.value),  # type: ignore[arg-type]
            "W",
            "this step",
        ),
        "TH-BAL",
        "Heat in minus heat radiated minus heat conducted out; zero at equilibrium (rounding "
        "aside). The imbalance of the worst node is in the note of the temperature table.",
    )
    return [*steps, solve, *rad_steps, *cond_steps, close], solve.result


def _celsius_cell(ctx: _CaseCtx, node: NodeTemperature) -> Cell:
    kelvin = Quantity(
        f"temperature of node {node.node}",
        node.temperature_k,
        "K",
        "column Temperature (K) of this table (explain it with the same row)",
    )
    step = Step(
        "Temperature in degrees Celsius",
        (kelvin, Quantity("offset", ABSOLUTE_ZERO_OFFSET_K, "K", "constant")),
        Quantity(
            f"temperature of node {node.node}", node.temperature_k - ABSOLUTE_ZERO_OFFSET_K, "C", ""
        ),
        logic="Kelvin minus 273.15 (display only: the model works in kelvin).",
    )
    return [step], step.result


def _temperatures_cell(ctx: _CaseCtx, key: Sequence[str], column: str) -> Cell:
    if column == "Node":
        return _read(Quantity("thermal node", key[0], "", f"{MODEL_FILE} nodes"), "Names the row.")
    node = ctx.node(key[0])
    handlers: dict[str, Callable[[_CaseCtx, NodeTemperature], Cell]] = {
        "Temperature (K)": _temperature_cell,
        "Temperature (C)": _celsius_cell,
        "Dissipated (W)": _dissipated_cell,
        "Absorbed from environment (W)": _absorbed_cell,
        "Radiated to space (W)": _radiated_cell,
        "Conducted to other nodes (W)": _conducted_cell,
    }
    if column not in handlers:
        raise ExplainError("This column is not explained.")
    return handlers[column](ctx, node)


# ---- unit limit checks -------------------------------------------------------------------------
def _limits_cell(ctx: _CaseCtx, key: Sequence[str], column: str) -> Cell:
    check = next((k for k in ctx.case.checks if k.unit_id == key[0]), None)
    if check is None:
        raise ExplainError("There is no such unit in this table.")
    set_name = ctx.case.limit_set
    lo_path = f"temperature_limits.{'operating' if set_name == 'operating' else 'survival'}_min_k"
    hi_path = lo_path.replace("_min_k", "_max_k")
    file = f"units/{check.unit_id}.yaml"
    if column == "Unit":
        return _read(Quantity("unit id", check.unit_id, "", file), "Names the row.")
    if column == "Node":
        return _read(
            Quantity(
                f"thermal node of {check.unit_id}",
                check.node,
                "",
                f"{file} thermal_node (the subsystem when it names none)",
            )
        )
    lower = Quantity(
        f"{set_name} lower limit of {check.unit_id}",
        check.lower_limit_k,
        "K",
        f"{file} {lo_path}" + ("" if check.lower_limit_k is not None else " (not given)"),
    )
    upper = Quantity(
        f"{set_name} upper limit of {check.unit_id}",
        check.upper_limit_k,
        "K",
        f"{file} {hi_path}" + ("" if check.upper_limit_k is not None else " (not given)"),
    )
    if column == "Lower limit (K)":
        return _read(lower)
    if column == "Upper limit (K)":
        return _read(upper)
    temperature = Quantity(
        f"temperature of node {check.node}",
        check.temperature_k,
        "K",
        f"table 'Node temperatures, case {ctx.case.case}' (explain it with "
        f"thermal:temperatures:{ctx.case.case})",
    )
    if column == "Temperature (K)":
        return _read(temperature, "Taken from the node temperature table.")
    if column not in (
        "Headroom to lower (K)",
        "Headroom to upper (K)",
        "Status",
    ):
        raise ExplainError("This column is not explained.")
    margin = ctx.margin()
    if check.temperature_k is None:
        what = "no limits for this set" if check.status == "no limits" else "no temperature"
        step = Step(
            "Unit temperature limit check",
            (temperature, lower, upper),
            Quantity("result", check.status if column == "Status" else None, "", "this step"),
            "TH-LIMIT",
            f"Not checked: the unit has {what}.",
        )
        return [step], step.result
    down, up, status = limit_status(
        check.temperature_k, check.lower_limit_k, check.upper_limit_k, _float(margin)
    )
    result_value: float | str | None = {
        "Headroom to lower (K)": down,
        "Headroom to upper (K)": up,
        "Status": status,
    }[column]
    step = Step(
        "Unit temperature limit check",
        (temperature, lower, upper, margin),
        Quantity(
            {"Status": "status"}.get(column, column.replace(" (K)", "").lower()),
            result_value,
            "" if column == "Status" else "K",
            "this step",
        ),
        "TH-LIMIT",
        "Headroom to the lower limit is the temperature minus the limit, to the upper limit the "
        "limit minus the temperature. Exceeded when either is negative; margin when within the "
        "limits but closer than the required margin; ok (margin not checked) when no margin is "
        "given.",
    )
    return [step], step.result


# ---- entry points -------------------------------------------------------------------------
def thermal_table_ids(project: Project) -> list[tuple[str, str]]:
    """(table id, title) of every explainable static thermal table."""
    out = [("thermal:summary", "Heat dissipation by spacecraft mode")]
    for mode_id in sorted(project.modes):
        name = project.modes[mode_id].name
        out += [
            (f"thermal:units:{mode_id}", f"Units in mode {name}"),
            (f"thermal:subsystems:{mode_id}", f"By subsystem (mode {name})"),
            (f"thermal:nodes:{mode_id}", f"By thermal node (mode {name})"),
        ]
    env = project.config.thermal_environment
    for case in sorted(env.cases) if env else []:
        out += [
            (f"thermal:temperatures:{case}", f"Node temperatures, case {case}"),
            (f"thermal:limits:{case}", f"Unit temperature limits, case {case}"),
        ]
    return out


_HEAT_KINDS = {
    "units": ("Units in mode", _unit_cell),
    "subsystems": ("By subsystem", None),
    "nodes": ("By thermal node", None),
}


def explain_thermal(
    project: Project,
    table_id: str,
    key: Sequence[str],
    column: str,
    result: StaticThermalResult | None = None,
) -> Explanation:
    result = static_thermal_budget(project) if result is None else result
    parts = table_id.split(":", 2)
    kind = parts[1] if len(parts) > 1 else ""
    if not key:
        raise ExplainError("Name the row.")
    name = parts[2] if len(parts) > 2 else ""
    address = (table_id, tuple(key), column)
    if kind == "summary" or kind in _HEAT_KINDS:
        if kind == "summary":
            mode = next((m for m in result.modes if m.mode_name == key[0]), None)
        else:
            mode = next((m for m in result.modes if m.mode_id == name), None)
        if mode is None:
            raise ExplainError("There is no such spacecraft mode.")
        hctx = _HeatCtx(project, mode)
        if kind == "summary":
            if column == "Mode":
                steps, final = _read(
                    Quantity("name of the spacecraft mode", mode.mode_name, "", "modes/")
                )
            else:
                steps, final = _summary_cell(hctx, column)
            title = f"Heat dissipation by spacecraft mode / {key[0]} / {column}"
        else:
            labels = {"subsystems": "Subsystem", "nodes": "Node"}
            if kind in labels and column == labels[kind]:
                steps, final = _read(Quantity("row label", key[0], "", "the units' fields"))
            elif kind == "units":
                steps, final = _unit_cell(hctx, key, column)
            else:
                steps, final = _group_cell(hctx, key, column, nodes=kind == "nodes")
            title = f"{_HEAT_KINDS[kind][0]} {mode.mode_name} / {key[0]} / {column}"
    elif kind in ("temperatures", "limits"):
        case = next((c for c in result.cases if c.case == name), None)
        env = project.config.thermal_environment
        if case is None or env is None or name not in env.cases:
            raise ExplainError("There is no such thermal case.")
        ctx = _CaseCtx(project, result, case, env.cases[name])
        if kind == "temperatures":
            if not case.complete and column == "Node":
                steps, final = _read(Quantity("row label", key[0], "", "fixed by the table"))
            elif not case.complete:
                steps, final = _not_computed(ctx, "node temperatures")
            else:
                steps, final = _temperatures_cell(ctx, key, column)
            title = f"Node temperatures, case {name} / {key[0]} / {column}"
        else:
            steps, final = _limits_cell(ctx, key, column)
            title = f"Unit temperature limits, case {name} / {key[0]} / {column}"
    else:
        raise ExplainError("This table cannot be explained.")
    linked = link_steps(tuple(steps))
    return Explanation(
        address, title, replace(final, origin=""), linked, equations=equations_used(linked)
    )
