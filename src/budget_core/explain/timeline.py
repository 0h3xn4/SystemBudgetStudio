"""Explanations of the power timeline (tables of `reports/timeline_report.py`, D-208).

Table ids: `timeline:cases` (results by case), `timeline:modes` (the modes of the scenario),
`timeline:balance:<case>` (the orbit energy balance of a case) and `timeline:violations`. A cell is
named by the id, the values of the row's key columns and the column header.

The solver integrates on a time grid refined by every eclipse, mode and orbit edge (D-N1); the
explanation takes the solver's own series (`TimeDomainResult.detail`, kept on request) and applies
the functions the solver applies to them (`integral_wh`, `pack_capacity_wh`, `degradation_factor`,
`temperature_factor`, `balance_cumulatives`, `exceeding_intervals`), so a number agrees with the
table by construction; a test checks every cell. A sum over thousands of steps is shown as the
equation, the number of steps, the duration and the largest step, and the steps it ran over are
the series of the solver (`budget power-timeline` writes them with `--series-every`).

A battery state has no closed form: it follows from integrating from the initial charge. The
explanation shows the step that ends at the instant asked about, with the state before it, and says
that the state before follows from all the steps before.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Any

import numpy as np

from budget_core.environment.constants import ASTRONOMICAL_UNIT
from budget_core.equations import EQUATIONS
from budget_core.explain.power import ExplainError, explain_power
from budget_core.explain.trace import Explanation, Quantity, Step, equations_used, link_steps
from budget_core.model import Project, Sourced
from budget_core.model.power_system import PowerSystem
from budget_core.power import array as arr
from budget_core.power.battery import pack_capacity_wh
from budget_core.power.static_budget import StaticPowerResult
from budget_core.power.time_domain import (
    BATTERY_DEPLETED,
    DOD_EXCEEDED,
    ORBIT_BALANCE_NEGATIVE,
    PEAK_POWER_EXCEEDED,
    POWER_TOL_W,
    CaseResult,
    SolveDetail,
    TimeDomainResult,
    Violation,
    balance_cumulatives,
    exceeding_intervals,
    format_offset,
    integral_wh,
)
from budget_core.reports.timeline_report import violation_row

NDArray = np.ndarray[Any, np.dtype[np.float64]]
Cell = tuple[list[Step], Quantity]

POWER_SYSTEM = "config/power_system.yaml"


def timeline_table_ids(result: TimeDomainResult | None = None) -> list[tuple[str, str]]:
    """(table id, title) of every explainable timeline table; the balance tables are those of the
    cases solved (both, when the result is not known)."""
    cases = ("bol", "eol") if result is None else tuple(c.case for c in result.cases)
    return [
        ("timeline:cases", "Results by case"),
        ("timeline:modes", "Spacecraft modes in the scenario"),
        *((f"timeline:balance:{c}", f"Orbit energy balance, {c.upper()}") for c in cases),
        ("timeline:violations", "Violations"),
    ]


def _read(q: Quantity) -> Cell:
    return [Step("Read from the project", (), q, logic="Not computed: an input.")], q


def _sourced(name: str, item: Sourced | None, unit: str, path: str) -> Quantity:
    value = None if item is None or item.is_placeholder else item.value
    return Quantity(
        name,
        value,
        unit,
        f"{POWER_SYSTEM} {path}" + ("" if item is not None else " (missing)"),
        "" if item is None else item.source,
    )


def _plain(name: str, value: float | None, unit: str, path: str) -> Quantity:
    return Quantity(name, value, unit, f"{POWER_SYSTEM} {path}")


def _num(q: Quantity) -> float | None:
    return None if q.value is None or isinstance(q.value, str) else float(q.value)


@dataclass
class _Ctx:
    project: Project
    result: TimeDomainResult
    detail: SolveDetail
    case: CaseResult
    power: StaticPowerResult

    @property
    def system(self) -> PowerSystem | None:
        return self.project.config.power_system

    @property
    def name(self) -> str:
        return self.case.case.upper()

    @property
    def bol(self) -> bool:
        return self.case.case == "bol"

    def generation(self) -> NDArray | None:
        return self.detail.generation_w(self.case.case)

    def demand(self) -> NDArray | None:
        return self.detail.demand_w

    def trace_energy(self) -> NDArray | None:
        trace = self.detail.trace(self.case.case)
        return None if trace is None else trace.energy_wh

    def years(self) -> Quantity:
        if self.bol:
            return Quantity("age", 0.0, "yr", "beginning of life: age 0")
        s = self.system
        return _sourced("design life", s.design_life_yr if s else None, "yr", "design_life_yr")


# ---- the battery pack, the array and the age ---------------------------------------------------
def _capacity_step(ctx: _Ctx) -> Step:
    b = ctx.system.battery if ctx.system else None
    cap = _sourced(
        "cell capacity", b.cell_capacity_ah if b else None, "Ah", "battery.cell_capacity_ah"
    )
    volt = _sourced(
        "cell voltage",
        b.cell_nominal_voltage_v if b else None,
        "V",
        "battery.cell_nominal_voltage_v",
    )
    series = _plain(
        "cells in series",
        None if b is None else float(b.cells_in_series),
        "",
        "battery.cells_in_series",
    )
    parallel = _plain(
        "cells in parallel",
        None if b is None else float(b.cells_in_parallel),
        "",
        "battery.cells_in_parallel",
    )
    fade = _sourced(
        "annual capacity fade",
        b.annual_capacity_fade_ratio if b else None,
        "ratio",
        "battery.annual_capacity_fade_ratio",
    )
    if ctx.bol and fade.value is None:
        fade = replace(fade, value=0.0)  # age 0: the fade has no effect, as the solver reads it
    years = ctx.years()
    parts = (cap, volt, series, parallel, fade, years)
    value = None
    if all(_num(q) is not None for q in parts):
        value = pack_capacity_wh(
            float(_num(cap) or 0.0),
            float(_num(volt) or 0.0),
            int(_num(series) or 0),
            int(_num(parallel) or 0),
            float(_num(fade) or 0.0),
            float(_num(years) or 0.0),
        )
    return Step(
        "Usable energy of the battery pack",
        parts,
        Quantity("battery capacity", value, "Wh", "this step"),
        "TDP-CAP",
        "" if value is not None else "An input is n/a, so the capacity is n/a.",
    )


def _age_step(ctx: _Ctx) -> Step:
    years = ctx.years()
    if ctx.bol:
        return Step(
            "Array age factor",
            (years,),
            Quantity("array age factor", ctx.detail.setup(ctx.case.case).age_factor, "ratio"),
            logic="Beginning of life: age 0, no degradation, factor 1.",
        )
    a = ctx.system.solar_array if ctx.system else None
    annual = _sourced(
        "annual array degradation",
        a.annual_degradation_ratio if a else None,
        "ratio",
        "solar_array.annual_degradation_ratio",
    )
    value = None
    if _num(annual) is not None and _num(years) is not None:
        value = arr.degradation_factor(float(_num(annual) or 0.0), float(_num(years) or 0.0))
    return Step(
        "Array age factor",
        (annual, years),
        Quantity("array age factor", value, "ratio", "this step"),
        "TDP-AGE",
        "" if value is not None else "An input is n/a, so the age factor is n/a.",
    )


def _array_steps(ctx: _Ctx) -> list[Step]:
    a = ctx.system.solar_array if ctx.system else None
    base = "solar_array."
    irradiance = _sourced(
        "solar irradiance",
        a.solar_irradiance_wm2 if a else None,
        "W/m2",
        base + "solar_irradiance_wm2",
    )
    area = _sourced("cell area", a.cell_area_m2 if a else None, "m2", base + "cell_area_m2")
    eff = _sourced(
        "cell efficiency",
        a.cell_efficiency_ratio if a else None,
        "ratio",
        base + "cell_efficiency_ratio",
    )
    tref = _sourced(
        "reference temperature",
        a.reference_temperature_k if a else None,
        "K",
        base + "reference_temperature_k",
    )
    tcell = _sourced(
        "cell temperature", a.cell_temperature_k if a else None, "K", base + "cell_temperature_k"
    )
    coeff = _sourced(
        "efficiency temperature coefficient",
        a.efficiency_temp_coeff_perk if a else None,
        "1/K",
        base + "efficiency_temp_coeff_perk",
    )
    packing = _sourced(
        "packing loss", a.packing_loss_ratio if a else None, "ratio", base + "packing_loss_ratio"
    )
    harness = _sourced(
        "harness loss", a.harness_loss_ratio if a else None, "ratio", base + "harness_loss_ratio"
    )
    cells = Quantity(
        "cells on all faces",
        None if a is None else float(sum(f.cell_count for f in a.faces)),
        "",
        f"{POWER_SYSTEM} solar_array.faces (strings x cells_per_string)",
    )
    k_t = None
    if None not in (_num(tcell), _num(tref), _num(coeff)):
        k_t = arr.temperature_factor(
            float(_num(tcell) or 0.0), float(_num(tref) or 0.0), float(_num(coeff) or 0.0)
        )
    temp = Step(
        "Efficiency factor of the cell temperature",
        (tcell, tref, coeff),
        Quantity("temperature factor", k_t, "ratio", "this step"),
        "TDP-TEMP",
    )
    base_generation = ctx.detail.base_generation_w
    peak = None if base_generation is None else float(np.max(base_generation))
    distance_steps: list[Step] = []
    distance_inputs: tuple[Quantity, ...] = ()
    run = ctx.result.run
    if run.scenario.irradiance_model == "seasonal" and run.env.sun_distance_m is not None:
        factors = arr.distance_factor_ratio(run.env.sun_distance_m)
        mean_factor = Quantity(
            "irradiance factor (AU / R)^2, mean over the scenario",
            float(np.mean(factors)),
            "ratio",
            "this step",
        )
        distance_steps.append(
            Step(
                "Irradiance at the Earth-Sun distance (seasonal model)",
                (
                    Quantity(
                        "Earth-Sun distance, mean over the scenario",
                        float(np.mean(run.env.sun_distance_m)),
                        "m",
                        "the Sun model (ENV-SUN)",
                    ),
                    Quantity("astronomical unit", ASTRONOMICAL_UNIT.value, "m", "constant"),
                ),
                mean_factor,
                "ENV-IRRADIANCE",
                "The scenario chooses the seasonal irradiance model: the configured irradiance is "
                "the value at 1 AU and every step is scaled by (AU / R)^2 with the distance R of "
                "its grid step.",
            )
        )
        distance_inputs = (replace(mean_factor, origin="previous step"),)
    output = Step(
        "Array output at beginning of life",
        (
            irradiance,
            *distance_inputs,
            cells,
            area,
            eff,
            replace(temp.result, origin="previous step"),
            packing,
            harness,
        ),
        Quantity("largest array output of any step, beginning of life", peak, "W", "this step"),
        "TDP-ARRAY",
        "Each solver step: irradiance x cells x cell area x efficiency x temperature factor x "
        "(1 - packing loss) x (1 - harness loss), summed over the faces with the cosine of the "
        "angle between the Sun and the face normal (TDP-COS, zero on the back side) and "
        "multiplied by the share of the step in sunlight (TDP-LIT). The largest step is shown; "
        "the other steps follow the Sun direction and the eclipses. n/a when an array input, a "
        "face or the pointing of a mode is missing (see Problems).",
    )
    return [temp, *distance_steps, output, _age_step(ctx)]


def _total_duration(ctx: _Ctx) -> Quantity:
    return Quantity("duration of the scenario", float(np.sum(ctx.detail.rdt_s)), "s", "scenario")


def _steps_count(ctx: _Ctx) -> Quantity:
    return Quantity(
        "solver steps",
        float(len(ctx.detail.rdt_s)),
        "",
        "the scenario grid plus every eclipse, mode and orbit edge and every instant the battery "
        "becomes full or empty",
    )


def _energy_step(
    ctx: _Ctx, label: str, series: NDArray | None, name: str, largest: Quantity
) -> Step:
    value = integral_wh(series, ctx.detail.rdt_s)
    return Step(
        label,
        (_steps_count(ctx), _total_duration(ctx), largest),
        Quantity(name, value, "Wh", "this step"),
        logic="Sum over the solver steps of power x step length / 3600.",
    )


def _average_step(ctx: _Ctx, energy: Quantity, name: str) -> Step:
    total = float(np.sum(ctx.detail.rdt_s))
    value = None if energy.value is None else float(energy.value) * 3600.0 / total
    return Step(
        f"Average {name}",
        (replace(energy, origin="previous step"), _total_duration(ctx)),
        Quantity(f"average {name}", value, "W", "this step"),
        logic="Energy x 3600 / duration.",
    )


def _generation_cell(ctx: _Ctx, average: bool) -> Cell:
    steps = _array_steps(ctx)
    generation = ctx.generation()
    largest = Quantity(
        "largest array output of any step",
        None if generation is None else float(np.max(generation)),
        "W",
        "this case",
    )
    steps.append(
        Step(
            "Array output in this case",
            (steps[1].result, steps[2].result),
            largest,
            logic="Beginning-of-life output x age factor, every step.",
        )
    )
    energy = _energy_step(ctx, "Energy generated", generation, "energy generated", largest)
    steps.append(energy)
    if average:
        steps.append(_average_step(ctx, energy.result, "generation"))
    return steps, steps[-1].result


def _mode_rows(ctx: _Ctx) -> tuple[str, str, str]:
    """(row of the totals table for the load, for the source, name of the basis)."""
    if ctx.result.load_basis == "margined":
        return "Load, with system margin", "Source, with margins", "with margins"
    return "Load, nominal", "Source, nominal", "nominal"


def _demand_cell(ctx: _Ctx, average: bool) -> Cell:
    _load_row, source_row, basis = _mode_rows(ctx)
    inputs: list[Quantity] = []
    for m in ctx.result.modes:
        inputs.append(
            Quantity(
                f"demand at the source in mode {m.mode_id}",
                m.demand_w,
                "W",
                f"table power:totals:{m.mode_id}, row '{source_row}', column Average (W)",
            )
        )
        inputs.append(Quantity(f"time in mode {m.mode_id}", m.duration_s, "s", "scenario timeline"))
    demand = ctx.demand()
    largest = Quantity(
        "largest demand of any step",
        None if demand is None else float(np.max(demand)),
        "W",
        "this step",
    )
    steps = [
        Step(
            "Demand at the source of each step",
            tuple(inputs),
            largest,
            "TDP-DEMAND",
            f"Basis: {basis}. Every solver step lies in one mode (steps are cut at each mode "
            "change), so its demand is the demand at the source of that mode (converter "
            "efficiency and distribution loss applied, explained in the static power budget).",
        )
    ]
    energy = _energy_step(ctx, "Energy demanded", demand, "energy demanded", largest)
    steps.append(energy)
    note = ""
    if all(m.demand_w is not None for m in ctx.result.modes):
        by_mode = math.fsum(float(m.demand_w or 0.0) * m.duration_s for m in ctx.result.modes)
        note = (
            f" Cross-check: the mode table gives {by_mode / 3600.0:.6g} Wh "
            "(demand x time of each mode), the same to rounding."
        )
    steps[-1] = replace(energy, logic=energy.logic + note)
    if average:
        steps.append(_average_step(ctx, energy.result, "demand at the source"))
    return steps, steps[-1].result


# ---- margin and battery state -----------------------------------------------------------------
def _margin_cell(ctx: _Ctx) -> Cell:
    g, d = ctx.generation(), ctx.demand()
    if g is None or d is None:
        q = Quantity("smallest margin", None, "W")
        return [
            Step(
                "Margin of the worst step",
                (),
                q,
                logic="n/a: the generation or the demand is n/a (see the cells above).",
            )
        ], q
    margin = g - d
    i = int(np.argmin(margin))
    edges = ctx.detail.redges_s
    inputs = (
        Quantity("step starts", format_offset(float(edges[i])), "", "solver steps"),
        Quantity("step length", float(ctx.detail.rdt_s[i]), "s", "solver steps"),
        Quantity("array output in the step", float(g[i]), "W", "see 'Average generation'"),
        Quantity("demand at the source in the step", float(d[i]), "W", "see 'Average demand'"),
    )
    result = Quantity("smallest margin", float(margin[i]), "W", "this step")
    return [
        Step(
            "Margin of the worst step",
            inputs,
            result,
            logic="Margin = array output - demand at the source, in every solver step; the "
            "smallest is shown with the step it occurs in.",
        )
    ], result


def _initial_energy_inputs(ctx: _Ctx) -> tuple[Quantity, ...]:
    b = ctx.system.battery if ctx.system else None
    return (
        _sourced(
            "initial state of charge",
            b.initial_soc_ratio if b else None,
            "ratio",
            "battery.initial_soc_ratio",
        ),
    )


def _battery_step_wh(
    energy_wh: float, net_w: float, seconds: float, capacity_wh: float, eta_c: float, eta_d: float
) -> float:
    """The stored energy after one step: TDP-SOC for a step (`integrate_battery` applies it to
    every step in a loop of its own, kept apart for speed; a test checks that the two agree on
    every step of the examples)."""
    hours = seconds / 3600.0
    e = energy_wh
    if net_w >= 0.0:
        offered = net_w * hours
        room = (capacity_wh - e) / eta_c
        accepted = offered if offered <= room else room
        if accepted < 0.0:
            accepted = 0.0
        e += eta_c * accepted
        if e > capacity_wh:
            e = capacity_wh
        return e
    needed = -net_w * hours
    available = e * eta_d
    supplied = needed if needed <= available else available
    e -= supplied / eta_d
    return 0.0 if e < 0.0 else e


def _state_steps(ctx: _Ctx, which: str) -> tuple[list[Step], Quantity]:
    """Steps that end at the stored energy at the instant the state of charge is lowest."""
    energy = ctx.trace_energy()
    capacity = ctx.case.capacity_wh
    if energy is None or not capacity:
        q = Quantity("stored energy", None, "Wh")
        return [
            Step(
                "Stored energy at the lowest point",
                (),
                q,
                logic="n/a: the battery or an input of the power balance is n/a (see Problems).",
            )
        ], q
    soc = energy / capacity
    j = int(np.argmin(soc))
    t_j = format_offset(float(ctx.detail.redges_s[j]))
    cap_q = Quantity("battery capacity", capacity, "Wh", "see 'Battery capacity'")
    steps: list[Step] = []
    if j == 0:
        init = _initial_energy_inputs(ctx)
        e0 = float(energy[0])
        steps.append(
            Step(
                "Stored energy at the start",
                (*init, cap_q),
                Quantity("stored energy", e0, "Wh", "this step"),
                logic="Initial state of charge x capacity.",
            )
        )
    else:
        b = ctx.system.battery if ctx.system else None
        eta_c = _sourced(
            "charge efficiency",
            b.charge_efficiency_ratio if b else None,
            "ratio",
            "battery.charge_efficiency_ratio",
        )
        eta_d = _sourced(
            "discharge efficiency",
            b.discharge_efficiency_ratio if b else None,
            "ratio",
            "battery.discharge_efficiency_ratio",
        )
        g, d = ctx.generation(), ctx.demand()
        assert g is not None and d is not None
        net = float(g[j - 1] - d[j - 1])
        seconds = float(ctx.detail.rdt_s[j - 1])
        before = float(energy[j - 1])
        after = _battery_step_wh(
            before, net, seconds, capacity, float(_num(eta_c) or 1.0), float(_num(eta_d) or 1.0)
        )
        steps.append(
            Step(
                "Stored energy at the lowest point",
                (
                    Quantity(
                        "stored energy before the step",
                        before,
                        "Wh",
                        "the integration from the initial charge over all the steps before",
                    ),
                    Quantity("array output - demand in the step", net, "W", "solver step"),
                    Quantity("step length", seconds, "s", "solver step"),
                    cap_q,
                    eta_c,
                    eta_d,
                ),
                Quantity("stored energy", after, "Wh", "this step"),
                "TDP-SOC",
                f"The instant is {t_j}. A surplus charges (x charge efficiency, up to the "
                "capacity); a deficit discharges (/ discharge efficiency, down to empty).",
            )
        )
    stored = steps[-1].result
    value = float(stored.value or 0.0) / capacity
    steps.append(
        Step(
            "State of charge",
            (replace(stored, origin="previous step"), cap_q),
            Quantity("lowest state of charge", value, "ratio", "this step"),
            logic=f"Stored energy / capacity, at {t_j}, the lowest of all instants.",
        )
    )
    if which == "dod":
        dod = 1.0 - value
        steps.append(
            Step(
                "Depth of discharge",
                (replace(steps[-1].result, origin="previous step"),),
                Quantity("deepest depth of discharge", dod, "ratio", "this step"),
                "TDP-DOD",
            )
        )
    return steps, steps[-1].result


def _state_cell(ctx: _Ctx, which: str) -> Cell:
    steps, q = _state_steps(ctx, which)
    value = None if q.value is None else float(q.value) * 100.0
    steps.append(
        Step(
            "As a percentage",
            (replace(q, origin="previous step"),),
            Quantity(q.name + " (%)", value, "%", "this step"),
            logic="x 100.",
        )
    )
    return steps, steps[-1].result


def _series_cell(ctx: _Ctx, series: NDArray | None, name: str, what: str) -> Cell:
    """Energy of a power series over the solver steps (not supplied, curtailed)."""
    if series is None:
        q = Quantity(name, None, "Wh")
        return [Step(name, (), q, logic="n/a: the battery is n/a (see Problems).")], q
    over = int(np.count_nonzero(series > 0.0))
    largest = Quantity(f"largest {what}", float(np.max(series)), "W", "solver steps")
    step = _energy_step(ctx, name[0].upper() + name[1:], series, name, largest)
    step = replace(
        step,
        inputs=(*step.inputs, Quantity(f"steps with {what}", float(over), "", "solver steps")),
    )
    return [step], step.result


def _trace_series(ctx: _Ctx, field: str) -> NDArray | None:
    trace = ctx.detail.trace(ctx.case.case)
    return None if trace is None else getattr(trace, field)


def _change_cell(ctx: _Ctx) -> Cell:
    energy = ctx.trace_energy()
    if energy is None:
        q = Quantity("stored energy change", None, "Wh")
        return [Step("Stored energy change", (), q, logic="n/a: the battery is n/a.")], q
    t0 = format_offset(float(ctx.detail.redges_s[0]))
    t1 = format_offset(float(ctx.detail.redges_s[-1]))
    q = Quantity("stored energy change", float(energy[-1] - energy[0]), "Wh", "this step")
    return [
        Step(
            "Stored energy change",
            (
                Quantity("stored energy at " + t0, float(energy[0]), "Wh", "initial charge"),
                Quantity(
                    "stored energy at " + t1,
                    float(energy[-1]),
                    "Wh",
                    "the integration over all the steps (TDP-SOC)",
                ),
            ),
            q,
            logic="Final - initial.",
        )
    ], q


def _violation_count_cell(ctx: _Ctx) -> Cell:
    own = len(ctx.case.violations)
    free = sum(1 for v in ctx.result.violations if v.case is None)
    q = Quantity("violations", str(ctx.result.violation_count(ctx.case.case)), "", "this step")
    return [
        Step(
            "Count the findings",
            (
                Quantity(f"findings of the case {ctx.name}", float(own), "", "table Violations"),
                Quantity(
                    "findings that do not depend on the case", float(free), "", "table Violations"
                ),
            ),
            q,
            logic="The findings of the case plus those that do not depend on it (peak power).",
        )
    ], q


_CASE_UNITS = {
    "Battery capacity": "Wh",
    "Average generation": "W",
    "Average demand at source": "W",
    "Energy generated": "Wh",
    "Energy demanded": "Wh",
    "Smallest margin (generation - demand)": "W",
    "Lowest state of charge": "%",
    "Deepest depth of discharge": "%",
    "Energy not supplied": "Wh",
    "Energy curtailed (battery full)": "Wh",
    "Stored energy change over the scenario": "Wh",
    "Violations": "count",
}


def _case_cell(ctx: _Ctx, key: Sequence[str], column: str) -> Cell:
    label = key[0]
    if label not in _CASE_UNITS:
        raise ExplainError("There is no such row in this table.")
    if column == "Quantity":
        return _read(Quantity("row label", label, "", "fixed by the table"))
    if column == "Unit":
        return _read(Quantity(f"unit of {label}", _CASE_UNITS[label], "", "fixed by the table"))
    if label == "Battery capacity":
        step = _capacity_step(ctx)
        return [step], step.result
    if label == "Average generation":
        return _generation_cell(ctx, True)
    if label == "Energy generated":
        return _generation_cell(ctx, False)
    if label == "Average demand at source":
        return _demand_cell(ctx, True)
    if label == "Energy demanded":
        return _demand_cell(ctx, False)
    if label == "Smallest margin (generation - demand)":
        return _margin_cell(ctx)
    if label == "Lowest state of charge":
        return _state_cell(ctx, "soc")
    if label == "Deepest depth of discharge":
        return _state_cell(ctx, "dod")
    if label == "Energy not supplied":
        return _series_cell(
            ctx, _trace_series(ctx, "unmet_w"), "energy not supplied", "unmet power"
        )
    if label == "Energy curtailed (battery full)":
        return _series_cell(
            ctx, _trace_series(ctx, "curtailed_w"), "energy curtailed", "curtailed power"
        )
    if label == "Stored energy change over the scenario":
        return _change_cell(ctx)
    if label == "Violations":
        return _violation_count_cell(ctx)
    raise ExplainError("There is no such row in this table.")


# ---- modes -------------------------------------------------------------------------------------
def _mode_cell(
    project: Project,
    result: TimeDomainResult,
    power: StaticPowerResult,
    key: Sequence[str],
    column: str,
) -> Cell:
    row = next((m for m in result.modes if m.mode_id == key[0]), None)
    if row is None:
        raise ExplainError("There is no such spacecraft mode in this table.")
    if column == "Mode":
        return _read(Quantity("mode id", row.mode_id, "", "scenario timeline"))
    if column == "Name":
        return _read(Quantity("mode name", row.mode_name, "", f"modes/{row.mode_id}.yaml name"))
    segments = [s for s in result.run.timeline if s.mode == row.mode_id]
    scenario = result.run.scenario
    time_q = Quantity(
        f"time in mode {row.mode_id}",
        sum(s.duration_s for s in segments),
        "s",
        f"{len(segments)} segment(s) of the scenario timeline",
    )
    if column == "Time (s)":
        step = Step(
            "Time in the mode",
            (Quantity("segments in the mode", float(len(segments)), "", "scenario timeline"),),
            time_q,
            logic="Sum of the lengths of the segments of the timeline in this mode.",
        )
        return [step], step.result
    if column == "Share":
        total = Quantity(
            "duration of the scenario",
            scenario.duration_s,
            "s",
            f"scenarios/{result.run.scenario_id}.yaml",
        )
        step = Step(
            "Share of the scenario",
            (time_q, total),
            Quantity("share", row.duration_s / scenario.duration_s, "ratio", "this step"),
            logic="Time in the mode / duration of the scenario (shown as a percentage).",
        )
        return [step], step.result
    load_row = {
        "nominal": ("Load, nominal", "Source, nominal"),
        "margined": ("Load, with system margin", "Source, with margins"),
    }[result.load_basis]
    pick = {
        "Load (W)": (load_row[0], "Average (W)"),
        "Demand at source (W)": (load_row[1], "Average (W)"),
        "Peak at source (W)": (load_row[1], "Peak (W)"),
    }.get(column)
    if pick is None:
        raise ExplainError("This column is not explained.")
    inner = explain_power(project, f"power:totals:{row.mode_id}", (pick[0],), pick[1], power)
    note = (
        f"This is the static power budget of the mode, row '{pick[0]}', column {pick[1]} "
        f"(basis: {result.load_basis})."
    )
    return [
        *inner.steps,
        Step("Value in the timeline table", (inner.result,), replace(inner.result), logic=note),
    ], inner.result


# ---- orbit balance -----------------------------------------------------------------------------
def _balance_cell(ctx: _Ctx, key: Sequence[str], column: str) -> Cell:
    windows = ctx.result.windows
    if not key or not key[0].isdigit() or not 1 <= int(key[0]) <= len(windows):
        raise ExplainError("There is no such orbit in this table.")
    k = int(key[0]) - 1
    start, end = windows[k]
    if column == "Orbit":
        return _read(Quantity("orbit number", key[0], "", "complete orbits of the scenario"))
    window_q = (
        Quantity("orbit starts", format_offset(start), "", "window of one revolution"),
        Quantity("orbit ends", format_offset(end), "", "window of one revolution"),
    )
    if column == "Start (T+)":
        return _read(window_q[0])
    if column == "Length (s)":
        q = Quantity("length", end - start, "s", "this step")
        return [
            Step(
                "Length of the orbit",
                (
                    Quantity("orbit start", start, "s", "window"),
                    Quantity("orbit end", end, "s", "window"),
                ),
                q,
                logic="End - start. A window is one revolution of the angle in the orbit plane, "
                "counted from the start of the scenario; only complete revolutions count.",
            )
        ], q
    cum = balance_cumulatives(
        ctx.detail.redges_s,
        ctx.detail.rdt_s,
        ctx.generation(),
        ctx.demand(),
        ctx.trace_energy(),
        windows,
        ctx.result.run,
    )
    i0, i1 = 2 * k, 2 * k + 1

    def difference(label: str, series: NDArray | None, name: str, unit: str, at: str) -> Cell:
        if series is None:
            q = Quantity(name, None, unit)
            return [Step(label, (), q, logic="n/a: an input of the power balance is n/a.")], q
        q = Quantity(name, float(series[i1] - series[i0]), unit, "this step")
        return [
            Step(
                label,
                (
                    Quantity(f"{at} up to the orbit end", float(series[i1]), unit, "cumulative"),
                    Quantity(f"{at} up to the orbit start", float(series[i0]), unit, "cumulative"),
                ),
                q,
                "TDP-BALANCE" if name != "eclipse time" else None,
                "Accumulated from the start of the scenario over the solver steps (interpolated "
                "inside a step), end of the orbit minus start.",
            )
        ], q

    if column == "Eclipse (s)":
        return difference("Time in eclipse", cum.eclipse_s, "eclipse time", "s", "eclipse time")
    if column == "Generated (Wh)":
        return difference(
            "Energy generated", cum.generated_wh, "energy generated", "Wh", "generated"
        )
    if column == "Demanded (Wh)":
        return difference("Energy demanded", cum.demanded_wh, "energy demanded", "Wh", "demanded")
    if column == "Stored change (Wh)":
        return difference(
            "Stored energy change", cum.stored_wh, "stored change", "Wh", "stored energy"
        )
    if column == "Balance (Wh)":
        gen_steps, gen = difference("g", cum.generated_wh, "energy generated", "Wh", "generated")
        dem_steps, dem = difference("d", cum.demanded_wh, "energy demanded", "Wh", "demanded")
        value = (
            None if gen.value is None or dem.value is None else float(gen.value) - float(dem.value)
        )
        q = Quantity("balance", value, "Wh", "this step")
        steps = [
            replace(gen_steps[0], label="Energy generated in the orbit"),
            replace(dem_steps[0], label="Energy demanded in the orbit"),
            Step(
                "Balance of the orbit",
                (replace(gen, origin="step 1"), replace(dem, origin="step 2")),
                q,
                "TDP-BALANCE",
                "Generated - demanded at the source; negative is a finding.",
            ),
        ]
        return steps, q
    raise ExplainError("This column is not explained.")


# ---- violations --------------------------------------------------------------------------------
def _find_violation(result: TimeDomainResult, key: Sequence[str]) -> Violation:
    if len(key) != 4:
        raise ExplainError("Name the case, the finding, and when it starts and ends.")
    for v in result.violations:
        if tuple(str(c) for c in violation_row(result, v)[:4]) == tuple(key):
            return v
    raise ExplainError("There is no such finding in this table.")


def _limit_quantity(
    ctx: _Ctx | None, result: TimeDomainResult, v: Violation, project: Project
) -> Quantity:
    system = project.config.power_system
    if v.code == DOD_EXCEEDED:
        item = None
        if system is not None and result.mission_phase is not None:
            item = system.battery.max_dod_ratio.get(result.mission_phase)
        return _sourced("allowed depth of discharge", item, "ratio", v.path)
    if v.code == PEAK_POWER_EXCEEDED:
        return _sourced(
            "peak power limit", system.limits.peak_power_w if system else None, "W", v.path
        )
    return Quantity("limit", v.limit, v.unit, "fixed: the finding is any shortfall")


def _worst_cell(
    project: Project, result: TimeDomainResult, power: StaticPowerResult, v: Violation
) -> Cell:
    detail = result.detail
    assert detail is not None
    interval = (
        Quantity("from", format_offset(v.start_s), "", "table Violations"),
        Quantity("to", format_offset(v.end_s), "", "table Violations"),
    )
    limit = _limit_quantity(None, result, v, project)
    case = result.case(v.case) if v.case else None
    ctx = None if case is None else _Ctx(project, result, detail, case, power)
    if v.code == DOD_EXCEEDED and ctx is not None and ctx.case.capacity_wh:
        energy = ctx.trace_energy()
        assert energy is not None and v.limit is not None
        dod = 1.0 - energy / ctx.case.capacity_wh
        found = [
            w
            for s, e, w in exceeding_intervals(detail.redges_s, dod, v.limit)
            if (s, e) == (v.start_s, v.end_s)
        ]
        q = Quantity(
            "worst depth of discharge", found[0] if found else v.extreme, "ratio", "this step"
        )
        return [
            Step(
                "Deepest depth of discharge in the interval",
                (*interval, limit),
                q,
                "TDP-DOD",
                "Depth of discharge = 1 - stored energy / capacity at every instant; the finding "
                "starts and ends where it crosses the limit, the worst value is the largest "
                "inside.",
            )
        ], q
    if v.code == BATTERY_DEPLETED and ctx is not None:
        unmet = _trace_series(ctx, "unmet_w")
        assert unmet is not None
        a = int(np.searchsorted(detail.redges_s, v.start_s))
        b = int(np.searchsorted(detail.redges_s, v.end_s))
        q = Quantity("worst unmet power", float(unmet[a:b].max()), "W", "this step")
        return [
            Step(
                "Largest unmet power in the interval",
                (*interval, limit),
                q,
                "TDP-SOC",
                "The battery was empty and could not supply the demand; the largest shortfall of "
                "a solver step inside the interval.",
            )
        ], q
    if v.code == ORBIT_BALANCE_NEGATIVE and ctx is not None:
        index = next(
            (b.index for b in ctx.case.balances if (b.start_s, b.end_s) == (v.start_s, v.end_s)),
            None,
        )
        if index is None:
            raise ExplainError("The orbit of this finding was not found.")
        return _balance_cell(ctx, (str(index),), "Balance (Wh)")
    if v.code == PEAK_POWER_EXCEEDED:
        tol = POWER_TOL_W
        limit_w = float(v.limit or 0.0)
        over = [
            (s.mode, m.peak_demand_w)
            for s in result.run.timeline
            for m in result.modes
            if m.mode_id == s.mode
            and m.peak_demand_w is not None
            and m.peak_demand_w > limit_w + tol
            and s.start_s >= v.start_s - 1e-9
            and s.end_s <= v.end_s + 1e-9
        ]
        modes = sorted({mode for mode, _ in over})
        inputs = [
            Quantity(
                f"peak demand at the source in mode {m.mode_id}",
                m.peak_demand_w,
                "W",
                f"table power:totals:{m.mode_id}",
            )
            for m in result.modes
            if m.mode_id in modes
        ]
        q = Quantity("worst peak", max((p for _, p in over), default=v.extreme), "W", "this step")
        return [
            Step(
                "Largest peak demand of the modes in the interval",
                (*inputs, limit),
                q,
                "TDP-PEAK",
                "A mode whose peak demand at the source is above the limit is a finding for as "
                "long as the timeline stays in it (neighbouring segments are one finding).",
            )
        ], q
    q = Quantity("worst value", v.extreme, v.unit, "result")
    return [Step("Worst value of the finding", (*interval, limit), q)], q


def _violation_cell(
    project: Project,
    result: TimeDomainResult,
    power: StaticPowerResult,
    key: Sequence[str],
    column: str,
) -> Cell:
    v = _find_violation(result, key)
    row = violation_row(result, v)
    headers = (
        "Case",
        "Finding",
        "From (T+)",
        "To (T+)",
        "Duration (s)",
        "Worst value",
        "Limit",
        "Unit",
        "Input to change",
    )
    if column not in headers:
        raise ExplainError("This column is not explained.")
    index = headers.index(column)
    if column == "Duration (s)":
        q = Quantity("duration", v.end_s - v.start_s, "s", "this step")
        return [
            Step(
                "Length of the finding",
                (
                    Quantity("start", v.start_s, "s", "table Violations"),
                    Quantity("end", v.end_s, "s", "table Violations"),
                ),
                q,
                logic="End - start.",
            )
        ], q
    if column == "Worst value":
        return _worst_cell(project, result, power, v)
    if column == "Limit":
        limit = _limit_quantity(None, result, v, project)
        return [Step("Limit of the check", (), limit, logic="Not computed: an input.")], limit
    cell = row[index]
    return _read(Quantity(column, cell if isinstance(cell, str) else None, "", "result of the run"))


# ---- entry point -------------------------------------------------------------------------------
def explain_timeline(
    project: Project,
    table_id: str,
    key: Sequence[str],
    column: str,
    result: TimeDomainResult,
    power: StaticPowerResult,
) -> Explanation:
    """Explain a cell of a timeline table. `result` must have been solved with `keep_detail`."""
    detail = result.detail
    if detail is None:
        raise ExplainError("The timeline was solved without its detail; solve it again.")
    parts = table_id.split(":")
    kind = parts[1] if len(parts) > 1 else ""
    if not key:
        raise ExplainError("Name the row.")
    address = (table_id, tuple(key), column)
    if kind == "modes":
        steps, final = _mode_cell(project, result, power, key, column)
        title = f"Spacecraft modes in the scenario / {key[0]} / {column}"
    elif kind in ("cases", "balance"):
        case_id = column.lower() if kind == "cases" else (parts[2] if len(parts) > 2 else "")
        if kind == "cases" and column in ("Quantity", "Unit"):
            case_id = result.cases[0].case
        case = next((c for c in result.cases if c.case == case_id), None)
        if case is None:
            raise ExplainError("There is no such case in this table.")
        ctx = _Ctx(project, result, detail, case, power)
        if kind == "cases":
            steps, final = _case_cell(ctx, key, column)
            title = f"Results by case / {key[0]} / {column}"
        else:
            steps, final = _balance_cell(ctx, key, column)
            title = f"Orbit energy balance, {case.case.upper()} / orbit {key[0]} / {column}"
    elif kind == "violations":
        steps, final = _violation_cell(project, result, power, key, column)
        title = f"Violations / {' / '.join(key)} / {column}"
    else:
        raise ExplainError("This table cannot be explained.")
    linked = link_steps(tuple(steps))
    equations = list(equations_used(linked))
    if any(s.equation_id == "TDP-ARRAY" for s in linked):
        equations += [EQUATIONS[i] for i in ("TDP-COS", "TDP-LIT") if EQUATIONS[i] not in equations]
    return Explanation(
        address, title, replace(final, origin=""), linked, equations=tuple(equations)
    )


__all__ = ["explain_timeline", "timeline_table_ids"]
