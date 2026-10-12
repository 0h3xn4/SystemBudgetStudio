"""Time-domain power budget over a scenario: generation, demand, battery state, violations.

Pipeline (decisions D-061 to D-066): the mode timeline gives the demand of each step (exact
overlap with the mode segments), the environment gives sunlight and the Sun direction, the array
model gives generation, the battery integrates the surplus or deficit. Two cases are solved from
the same inputs: beginning of life (BOL) and end of life (EOL). A number that is a placeholder or
missing makes the results that need it `None` (n/a); it is never replaced by zero.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np

from budget_core.assumptions import Assumption, incomplete, missing_from
from budget_core.environment.intervals import Interval, merge_intervals
from budget_core.model import Project, Sourced
from budget_core.model.power_system import PowerSystem
from budget_core.power import array as arr
from budget_core.power.attitude import sun_in_orbital_frame
from budget_core.power.battery import BatteryTrace, integrate_battery, pack_capacity_wh
from budget_core.power.orbits import orbit_windows_with_reason
from budget_core.power.signals import integral_of_steps, step_edges, step_means
from budget_core.power.static_budget import ModePowerResult, static_power_budget
from budget_core.problems import Problem, Severity
from budget_core.scenario.run import ScenarioRun
from budget_core.scenario.timeline import mode_index_on_grid

NDArray = np.ndarray[Any, np.dtype[np.float64]]
BoolArray = np.ndarray[Any, np.dtype[np.bool_]]
IntArray = np.ndarray[Any, np.dtype[np.intp]]
LoadBasis = Literal["nominal", "margined"]
CASES = ("bol", "eol")
FILE = "config/power_system.yaml"

# Violation codes
DOD_EXCEEDED = "BATTERY_DOD_EXCEEDED"
BATTERY_DEPLETED = "BATTERY_DEPLETED"
ORBIT_BALANCE_NEGATIVE = "ORBIT_BALANCE_NEGATIVE"
PEAK_POWER_EXCEEDED = "PEAK_POWER_EXCEEDED"

# Tolerances: a limit that is met exactly must not be reported because of rounding noise.
RATIO_TOL = 1e-9  # state of charge, depth of discharge
POWER_TOL_W = 1e-9
ENERGY_TOL_WH = 1e-6
REFINE_TOL_S = 1e-6  # refinement instants closer than this to an existing edge are the same edge
PENUMBRA_MIN_S = 0.01  # a ramp from sunlight to umbra shorter than this is a sharp edge
MAX_REFINE_ROUNDS = 4  # battery saturation instants are found on a grid that already holds them

CODES_TEXT = {
    DOD_EXCEEDED: "Depth of discharge above the allowed limit",
    BATTERY_DEPLETED: "Battery empty, demand not supplied",
    ORBIT_BALANCE_NEGATIVE: "Negative energy balance over an orbit",
    PEAK_POWER_EXCEEDED: "Peak power above the limit",
}

_MESSAGES = {
    DOD_EXCEEDED: "The battery depth of discharge exceeds the limit of the mission phase.",
    BATTERY_DEPLETED: "The battery is empty and the demand is not fully supplied.",
    ORBIT_BALANCE_NEGATIVE: "The energy generated over an orbit is less than the energy demanded.",
    PEAK_POWER_EXCEEDED: "The peak power demand at the source exceeds the power limit.",
}


@dataclass(frozen=True)
class Violation:
    case: str | None  # None when the finding does not depend on the case
    code: str
    start_s: float
    end_s: float
    extreme: float | None  # worst value inside the interval
    limit: float | None
    unit: str
    file: str  # input to change, for the jump link
    path: str


@dataclass(frozen=True)
class NotEvaluated:
    """A check that could not run (a placeholder, no phase, no complete orbit): its absence from
    the violations is not a pass."""

    case: str | None  # None when the check does not depend on the case
    code: str  # the finding the check would report
    reason: str


@dataclass(frozen=True)
class OrbitBalance:
    index: int  # 1-based
    start_s: float
    end_s: float
    eclipse_s: float
    generation_wh: float | None
    demand_wh: float | None
    balance_wh: float | None
    battery_change_wh: float | None


@dataclass(frozen=True)
class CaseSummary:
    average_generation_w: float | None
    average_demand_w: float | None
    generated_wh: float | None
    demanded_wh: float | None
    minimum_margin_w: float | None
    minimum_soc_ratio: float | None
    maximum_dod_ratio: float | None
    unmet_wh: float | None
    curtailed_wh: float | None
    energy_change_wh: float | None


@dataclass(frozen=True, eq=False)
class CaseResult:
    case: str
    age_years: float | None
    capacity_wh: float | None
    generation_w: NDArray | None  # per step
    margin_w: NDArray | None  # generation minus demand, per step
    energy_wh: NDArray | None  # stored energy at the step edges (N + 1)
    soc_ratio: NDArray | None  # (N + 1)
    dod_ratio: NDArray | None  # (N + 1)
    battery_power_w: NDArray | None
    unmet_w: NDArray | None
    curtailed_w: NDArray | None
    summary: CaseSummary
    balances: tuple[OrbitBalance, ...]
    violations: tuple[Violation, ...]


@dataclass(frozen=True)
class ModeRow:
    mode_id: str
    mode_name: str
    duration_s: float
    load_w: float | None
    demand_w: float | None
    peak_demand_w: float | None


@dataclass(frozen=True, eq=False)
class TimeDomainResult:
    run: ScenarioRun
    load_basis: str
    mission_phase: str | None
    edges_s: NDArray
    mode_ids: tuple[str, ...]  # index space of `step_mode`
    step_mode: NDArray  # mode at the start of each step (index into mode_ids)
    lit_ratio: NDArray  # share of each step in sunlight
    load_w: NDArray | None  # sum of unit loads, per step
    demand_w: NDArray | None  # demand at the source (after converter and distribution losses)
    cases: tuple[CaseResult, ...]
    modes: tuple[ModeRow, ...]
    windows: tuple[tuple[float, float], ...]
    assumptions: tuple[Assumption, ...]
    problems: tuple[Problem, ...]
    violations: tuple[Violation, ...] = field(default_factory=tuple)
    peak_limit_w: float | None = None
    dod_limit_ratio: float | None = None
    not_evaluated: tuple[NotEvaluated, ...] = field(default_factory=tuple)

    @property
    def steps(self) -> int:
        return len(self.edges_s) - 1

    def violation_count(self, case: str) -> int:
        """Findings of a case, including those that do not depend on the case (peak power)."""
        return len(self.case(case).violations) + sum(1 for v in self.violations if v.case is None)

    def case(self, name: str) -> CaseResult:
        return next(c for c in self.cases if c.case == name)

    def not_evaluated_text(self, case: str | None = None) -> str:
        """The checks that did not run, for one case (and the case-independent ones) or all;
        checks that share a reason are listed once with their cases."""
        groups: dict[tuple[str, str], list[str]] = {}
        for n in self.not_evaluated:
            if case is None or n.case in (None, case):
                cases = groups.setdefault((n.code, n.reason), [])
                if n.case:
                    cases.append(n.case.upper())
        return "; ".join(
            f"{CODES_TEXT[code]}{' in ' + ' and '.join(cases) if cases else ''} ({reason})"
            for (code, reason), cases in groups.items()
        )


# ---- inputs ---------------------------------------------------------------------------------


@dataclass
class _Collector:
    assumptions: list[Assumption] = field(default_factory=list)
    problems: list[Problem] = field(default_factory=list)
    file_present: bool = True  # False: the whole power system file is missing

    def get(self, name: str, item: Sourced | None, unit: str, path: str, what: str) -> float | None:
        if item is None:
            self.assumptions.append(Assumption(name, None, unit, "missing", FILE, path, True))
            where = missing_from(FILE, self.file_present)
            self.problems.append(incomplete(f"{what} is missing {where}.", FILE, path))
            return None
        self.assumptions.append(
            Assumption(name, item.value, unit, item.source, FILE, path, item.is_placeholder)
        )
        if item.is_placeholder:
            self.problems.append(incomplete(f"{what} is a placeholder.", FILE, path))
            return None
        return item.value


def _mode_flow(mode: ModePowerResult, basis: LoadBasis) -> tuple[float | None, ...]:
    """(load_w, demand_w, peak_demand_w) of a mode on the chosen basis."""
    if basis == "margined":
        return (
            mode.average.system_margined_w,
            mode.average.source_margined_w,
            (mode.peak.source_margined_w),
        )
    return mode.average.load_w, mode.average.source_w, mode.peak.source_w


def refined_edges(edges: NDArray, extra_s: list[float]) -> NDArray:
    """The scenario grid plus the given instants (eclipse edges, mode-segment edges). The grid
    edges are kept exactly; an instant within `REFINE_TOL_S` of one is the same edge."""
    inner = np.asarray(sorted(extra_s), dtype=np.float64)
    inner = inner[(inner > edges[0] + REFINE_TOL_S) & (inner < edges[-1] - REFINE_TOL_S)]
    if len(inner) == 0:
        return edges
    nearest = np.minimum(
        np.abs(inner - edges[np.clip(np.searchsorted(edges, inner) - 1, 0, len(edges) - 1)]),
        np.abs(inner - edges[np.clip(np.searchsorted(edges, inner), 0, len(edges) - 1)]),
    )
    inner = inner[nearest > REFINE_TOL_S]
    if len(inner) > 1:
        inner = inner[np.concatenate(([True], np.diff(inner) > REFINE_TOL_S))]
    return np.asarray(np.union1d(edges, inner), dtype=np.float64)


def _lit_ratio(run: ScenarioRun, edges: NDArray, shadows: list[Interval]) -> NDArray:
    """Share of each step in sunlight, independent of the steps. A sharp shadow is exact. A soft
    one is built from the eclipse and umbra intervals, which do not depend on the step: the
    ratio ramps linearly from 1 at the start of an eclipse to 0 at the start of its umbra and
    back to 1 at the end of the eclipse, so any sub-step gets its exact trapezoid mean."""
    knots = _penumbra_knots(run)
    if knots is None:
        starts = [e.start_s for e in shadows]
        ends = [e.end_s for e in shadows]
        shadow = step_means(starts, ends, [1.0] * len(starts), edges)
        return np.asarray(1.0 - shadow, dtype=np.float64)
    times, dark = knots
    segment = (dark[:-1] + dark[1:]) * 0.5 * np.diff(times)
    cumulative = np.concatenate(([0.0], np.cumsum(segment)))
    at = np.clip(np.searchsorted(times, edges, side="right") - 1, 0, len(times) - 1)
    inside = np.clip(edges, times[0], times[-1])
    width = np.diff(times)[np.minimum(at, len(times) - 2)]
    slope = np.diff(dark)[np.minimum(at, len(times) - 2)] / np.where(width > 0.0, width, 1.0)
    slope = np.where(width > 0.0, slope, 0.0)
    level = dark[at] + slope * (inside - times[at])
    integral = cumulative[at] + (dark[at] + level) * 0.5 * (inside - times[at])
    return np.asarray(1.0 - np.diff(integral) / np.diff(edges), dtype=np.float64)


def _penumbra_knots(run: ScenarioRun) -> tuple[NDArray, NDArray] | None:
    """(times, dark ratio) of the piecewise linear shadow: 0 in sunlight, 1 in the umbra, a ramp
    over the penumbra. None when no eclipse has a penumbra (sharp shadow)."""
    env = run.env
    umbras = merge_intervals(list(env.umbras))
    ratio = np.asarray(env.sunlight_ratio, dtype=np.float64)
    sample_t = np.asarray(env.grid.times_s, dtype=np.float64)
    tol = PENUMBRA_MIN_S
    times: list[float] = []
    dark: list[float] = []
    soft = False
    for e in merge_intervals(list(env.eclipses)):
        inner = [u for u in umbras if u.start_s >= e.start_s - tol and u.end_s <= e.end_s + tol]
        first = 1.0 - float(ratio[0]) if e.start_s <= tol else 0.0
        last = 1.0 - float(ratio[-1]) if e.end_s >= env.grid.duration_s - tol else 0.0
        times.append(e.start_s)
        dark.append(first)
        if inner:
            for u in inner:
                times += [max(u.start_s, e.start_s), min(u.end_s, e.end_s)]
                dark += [1.0, 1.0]
            soft = soft or inner[0].start_s - e.start_s > tol or e.end_s - inner[-1].end_s > tol
        else:
            # penumbra only (a grazing orbit): ramp to the deepest sample inside, else halfway
            inside = ratio[(sample_t >= e.start_s) & (sample_t <= e.end_s)]
            deepest = 1.0 - float(inside.min()) if len(inside) else 0.5
            times.append(0.5 * (e.start_s + e.end_s))
            dark.append(deepest)
            soft = True
        times.append(e.end_s)
        dark.append(last)
    if not soft:
        return None
    return np.asarray(times, dtype=np.float64), np.asarray(dark, dtype=np.float64)


# ---- violations -----------------------------------------------------------------------------


def _runs(mask: BoolArray) -> list[tuple[int, int]]:
    """Inclusive index ranges where `mask` is True."""
    if not mask.any():
        return []
    padded = np.concatenate(([False], mask, [False]))
    change = np.flatnonzero(padded[1:] != padded[:-1])
    return [(int(a), int(b) - 1) for a, b in zip(change[::2], change[1::2], strict=True)]


def _crossing(t0: float, v0: float, t1: float, v1: float, level: float) -> float:
    if v1 == v0:
        return float(t1)
    return float(t0 + (level - v0) / (v1 - v0) * (t1 - t0))


def _exceeding(edges: NDArray, values: NDArray, limit: float) -> list[tuple[float, float, float]]:
    """Intervals where the state `values` (at the edges) is above `limit`, as (start, end, worst);
    the ends are interpolated linearly between the edges."""
    out: list[tuple[float, float, float]] = []
    last = len(values) - 1
    for a, b in _runs(values > limit + RATIO_TOL):
        start = (
            float(edges[0])
            if a == 0
            else _crossing(edges[a - 1], values[a - 1], edges[a], values[a], limit)
        )
        end = (
            float(edges[last])
            if b == last
            else _crossing(edges[b], values[b], edges[b + 1], values[b + 1], limit)
        )
        out.append((start, end, float(values[a : b + 1].max())))
    return out


# ---- main entry -----------------------------------------------------------------------------


@dataclass(frozen=True)
class _Prepared:
    """The solver inputs on one set of refined edges."""

    grid: _GridMap
    demand_w: NDArray | None
    base_generation: NDArray | None


def time_domain_budget(
    project: Project,
    run: ScenarioRun,
    *,
    load_basis: LoadBasis = "nominal",
    cases: tuple[str, ...] = CASES,
    mission_phase: str | None = None,
) -> TimeDomainResult:
    """Solve the scenario. The project must be valid; `run` is its computed scenario."""
    if any(name not in CASES for name in cases):
        raise ValueError("a power case must be 'bol' or 'eol'")
    scenario = run.scenario
    env = run.env
    system: PowerSystem | None = project.config.power_system
    static = static_power_budget(project)
    col = _Collector(file_present=system is not None)
    for assumption in static.assumptions:
        col.assumptions.append(assumption)
    col.problems.extend(static.problems)
    col.problems.extend(run.problems)

    # Reported series live on the scenario grid; the battery is integrated on the grid refined by
    # every eclipse edge, mode-segment edge, orbit window edge and the instants at which the
    # battery becomes full or empty, so a coarse step cannot average a discharge away.
    edges = step_edges(env.grid.duration_s, env.grid.step_s)
    dt = np.diff(edges)
    shadows = merge_intervals(list(env.eclipses))
    timeline = run.timeline
    windows_found, windows_why = orbit_windows_with_reason(
        env.grid.times_s, env.position_m, env.grid.duration_s
    )
    windows = tuple(windows_found)
    cuts = [t for e in shadows for t in (e.start_s, e.end_s)]
    cuts += [t for s in timeline for t in (s.start_s, s.end_s)]
    cuts += [t for pair in windows for t in pair]
    redges = refined_edges(edges, cuts)

    # --- modes, demand ------------------------------------------------------------------
    mode_ids = tuple(sorted({s.mode for s in timeline}))
    by_mode = {m.mode_id: m for m in static.modes}
    flows = {m: _mode_flow(by_mode[m], load_basis) for m in mode_ids}
    seg_starts = [s.start_s for s in timeline]
    seg_ends = [s.end_s for s in timeline]

    def per_step(index: int, at: NDArray) -> NDArray | None:
        if any(flows[s.mode][index] is None for s in timeline):
            return None
        values = [float(flows[s.mode][index] or 0.0) for s in timeline]
        return step_means(seg_starts, seg_ends, values, at)

    load_w = per_step(0, edges)
    demand_w = per_step(1, edges)
    step_mode = mode_index_on_grid(timeline, edges[:-1], list(mode_ids))
    durations = {m: sum(s.duration_s for s in timeline if s.mode == m) for m in mode_ids}
    mode_rows = tuple(
        ModeRow(
            m,
            by_mode[m].mode_name,
            durations[m],
            flows[m][0],
            flows[m][1],
            flows[m][2],
        )
        for m in mode_ids
    )
    lit = _lit_ratio(run, edges, shadows)

    phase = mission_phase or scenario.mission_phase
    if phase is None and len(project.phases) == 1:
        phase = project.phases[0]

    def prepare(at: NDArray, collector: _Collector) -> _Prepared:
        grid_edge_at = np.searchsorted(at, edges)  # index of each grid edge in the refined edges
        grid_of = np.searchsorted(edges, at[:-1], side="right") - 1  # grid step of a refined step
        solve_mode = mode_index_on_grid(timeline, at[:-1], list(mode_ids))
        generation = _base_generation(
            project,
            system,
            run,
            grid_of,
            solve_mode,
            mode_ids,
            _lit_ratio(run, at, shadows),
            collector,
        )
        return _Prepared(
            _GridMap(edges, dt, at, np.diff(at), grid_edge_at), per_step(1, at), generation
        )

    # --- array ----------------------------------------------------------------------------
    prepared = prepare(redges, col)
    life = col.get(
        "Design life",
        system.design_life_yr if system else None,
        "yr",
        "design_life_yr",
        "The design life",
    )

    # --- battery limits -------------------------------------------------------------------
    battery_inputs = _battery_inputs(system, phase, col, f"scenarios/{run.scenario_id}.yaml")
    annual = col.get(
        "Array annual degradation",
        system.solar_array.annual_degradation_ratio if system else None,
        "ratio",
        "solar_array.annual_degradation_ratio",
        "The array annual degradation",
    )
    peak_limit = col.get(
        "Peak power limit",
        system.limits.peak_power_w if system else None,
        "W",
        "limits.peak_power_w",
        "The peak power limit",
    )

    peak_violations = _peak_violations(run, mode_rows, peak_limit)

    # The instants at which the battery becomes full or empty are edges too. They depend on the
    # state, so they are found by solving and then added; adding an edge inside a step of
    # constant power leaves the solution before and after it unchanged.
    setups = tuple(_case_setup(name, battery_inputs, life, annual) for name in cases)
    traces: list[BatteryTrace | None] = []
    for _ in range(MAX_REFINE_ROUNDS):
        traces = [_integrate(setup, battery_inputs, prepared) for setup in setups]
        g = prepared.grid
        extra = [
            float(g.redges[i] + f * g.rdt[i])
            for trace in traces
            if trace is not None
            for i, f in enumerate(trace.saturation_fraction)
            if not math.isnan(f)
        ]
        finer = refined_edges(g.redges, extra)
        if len(finer) == len(g.redges):
            break
        prepared = prepare(finer, _Collector(file_present=system is not None))
    case_results = tuple(
        _solve_case(setup, prepared, battery_inputs, trace, phase, windows, run)
        for setup, trace in zip(setups, traces, strict=True)
    )
    violations = tuple(
        sorted(
            peak_violations + [v for c in case_results for v in c.violations],
            key=lambda v: (v.start_s, v.code, v.case or ""),
        )
    )
    dod_limit = None if battery_inputs is None else battery_inputs.dod_limit
    not_evaluated = _not_evaluated(
        case_results, dod_limit, peak_limit, mode_rows, run, windows, windows_why
    )
    if windows_why in ("coarse", "plane"):
        col.problems.append(_windows_problem(windows_why, run))
    return TimeDomainResult(
        run=run,
        load_basis=load_basis,
        mission_phase=phase,
        edges_s=edges,
        mode_ids=mode_ids,
        step_mode=step_mode,
        lit_ratio=lit,
        load_w=load_w,
        demand_w=demand_w,
        cases=case_results,
        modes=mode_rows,
        windows=windows,
        assumptions=tuple(_unique(col.assumptions)),
        problems=tuple(_unique_problems(col.problems)),
        violations=violations,
        peak_limit_w=peak_limit,
        dod_limit_ratio=dod_limit,
        not_evaluated=not_evaluated,
    )


def _windows_problem(why: str, run: ScenarioRun) -> Problem:
    """Orbit windows that could not be found for a reason the user can change."""
    scenario_file = f"scenarios/{run.scenario_id}.yaml"
    if why == "coarse":
        return Problem(
            Severity.WARNING,
            "ORBIT_BALANCE_NOT_EVALUATED",
            "The orbit energy balance is not evaluated: the scenario step is longer than a "
            "quarter of the orbit period, too coarse to find the orbits.",
            file=scenario_file,
            path="step_s",
            hint="Use a step of at most a quarter of the orbit period (the battery, depletion "
            "and peak-power checks do not depend on the step).",
        )
    return Problem(
        Severity.WARNING,
        "ORBIT_BALANCE_NOT_EVALUATED",
        "The orbit energy balance is not evaluated: the orbit plane cannot be found from the "
        "scenario's positions.",
        file=scenario_file,
        path="duration_s",
        hint="Use a step of at most a quarter of the orbit period and a scenario of at least "
        "three steps.",
    )


def _not_evaluated(
    cases: tuple[CaseResult, ...],
    dod_limit: float | None,
    peak_limit: float | None,
    modes: tuple[ModeRow, ...],
    run: ScenarioRun,
    windows: tuple[tuple[float, float], ...],
    windows_why: str | None,
) -> tuple[NotEvaluated, ...]:
    """The checks that did not run, so that an empty violation list is not read as a pass."""
    out: list[NotEvaluated] = []
    used = {s.mode for s in run.timeline}
    missing = "an input of the array or battery is missing"
    if peak_limit is None:
        out.append(NotEvaluated(None, PEAK_POWER_EXCEEDED, "the peak power limit is missing"))
    elif any(m.peak_demand_w is None for m in modes if m.mode_id in used):
        out.append(NotEvaluated(None, PEAK_POWER_EXCEEDED, "a mode's peak demand is unknown"))
    for c in cases:
        if c.dod_ratio is None:
            out.append(NotEvaluated(c.case, DOD_EXCEEDED, missing))
        elif dod_limit is None:
            out.append(
                NotEvaluated(c.case, DOD_EXCEEDED, "the allowed depth of discharge is unknown")
            )
        if c.unmet_w is None:
            out.append(NotEvaluated(c.case, BATTERY_DEPLETED, missing))
        if not windows:
            reason = {
                "coarse": "the step is too coarse to find the orbits",
                "plane": "the orbit plane cannot be found",
            }.get(windows_why or "", "the scenario has no complete orbit")
            out.append(NotEvaluated(c.case, ORBIT_BALANCE_NEGATIVE, reason))
        elif any(b.balance_wh is None for b in c.balances):
            out.append(
                NotEvaluated(
                    c.case, ORBIT_BALANCE_NEGATIVE, "an input of the array or demand is missing"
                )
            )
    return tuple(out)


def _unique(items: list[Assumption]) -> list[Assumption]:
    seen: set[tuple[str, str]] = set()
    out: list[Assumption] = []
    for a in items:
        key = (a.file, a.path or a.name)
        if key not in seen:
            seen.add(key)
            out.append(a)
    return out


def _unique_problems(items: list[Problem]) -> list[Problem]:
    seen: set[tuple[str, str | None, str, str]] = set()
    out: list[Problem] = []
    for p in items:
        key = (p.code, p.file, p.path, p.message)
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


@dataclass(frozen=True)
class _BatteryInputs:
    cell_capacity_ah: float
    cell_voltage_v: float
    series: int
    parallel: int
    fade: float | None  # not needed at beginning of life
    eta_c: float
    eta_d: float
    initial_soc: float
    dod_limit: float | None


def _battery_inputs(
    system: PowerSystem | None, phase: str | None, col: _Collector, scenario_file: str
) -> _BatteryInputs | None:
    b = system.battery if system else None
    cap = col.get(
        "Battery cell capacity",
        b.cell_capacity_ah if b else None,
        "Ah",
        "battery.cell_capacity_ah",
        "The battery cell capacity",
    )
    volt = col.get(
        "Battery cell voltage",
        b.cell_nominal_voltage_v if b else None,
        "V",
        "battery.cell_nominal_voltage_v",
        "The battery cell voltage",
    )
    eta_c = col.get(
        "Battery charge efficiency",
        b.charge_efficiency_ratio if b else None,
        "ratio",
        "battery.charge_efficiency_ratio",
        "The battery charge efficiency",
    )
    eta_d = col.get(
        "Battery discharge efficiency",
        b.discharge_efficiency_ratio if b else None,
        "ratio",
        "battery.discharge_efficiency_ratio",
        "The battery discharge efficiency",
    )
    fade = col.get(
        "Battery annual capacity fade",
        b.annual_capacity_fade_ratio if b else None,
        "ratio",
        "battery.annual_capacity_fade_ratio",
        "The battery capacity fade",
    )
    soc0 = col.get(
        "Battery initial state of charge",
        b.initial_soc_ratio if b else None,
        "ratio",
        "battery.initial_soc_ratio",
        "The initial state of charge",
    )
    dod: float | None = None
    if phase is None:
        col.problems.append(
            incomplete(
                "The scenario has no mission phase, so the allowed depth of discharge is unknown.",
                scenario_file,
                "mission_phase",
            )
        )
    elif b is not None:
        item = b.max_dod_ratio.get(phase)
        dod = col.get(
            f"Allowed depth of discharge, phase {phase}",
            item,
            "ratio",
            f"battery.max_dod_ratio.{phase}",
            "The allowed depth of discharge of the phase",
        )
    if b is None or None in (cap, volt, eta_c, eta_d, soc0):
        return None
    assert cap is not None and volt is not None and eta_c is not None
    assert eta_d is not None and soc0 is not None
    return _BatteryInputs(
        cap, volt, b.cells_in_series, b.cells_in_parallel, fade, eta_c, eta_d, soc0, dod
    )


def _base_generation(
    project: Project,
    system: PowerSystem | None,
    run: ScenarioRun,
    grid_of: IntArray,
    step_mode: NDArray,
    mode_ids: tuple[str, ...],
    lit: NDArray,
    col: _Collector,
) -> NDArray | None:
    """Generation per solver step at beginning of life, or None when an input is missing.
    `grid_of[i]` is the scenario-grid step that contains solver step i: the Sun direction is
    sampled at the start of that grid step."""
    a = system.solar_array if system else None
    base = "solar_array."
    irradiance = col.get(
        "Solar irradiance",
        a.solar_irradiance_wm2 if a else None,
        "W/m2",
        base + "solar_irradiance_wm2",
        "The solar irradiance",
    )
    area = col.get(
        "Cell area", a.cell_area_m2 if a else None, "m2", base + "cell_area_m2", "The cell area"
    )
    eff = col.get(
        "Cell efficiency",
        a.cell_efficiency_ratio if a else None,
        "ratio",
        base + "cell_efficiency_ratio",
        "The cell efficiency",
    )
    tref = col.get(
        "Reference temperature",
        a.reference_temperature_k if a else None,
        "K",
        base + "reference_temperature_k",
        "The reference temperature",
    )
    tcell = col.get(
        "Cell temperature",
        a.cell_temperature_k if a else None,
        "K",
        base + "cell_temperature_k",
        "The cell temperature",
    )
    coeff = col.get(
        "Efficiency temperature coefficient",
        a.efficiency_temp_coeff_perk if a else None,
        "1/K",
        base + "efficiency_temp_coeff_perk",
        "The temperature coefficient",
    )
    packing = col.get(
        "Packing loss",
        a.packing_loss_ratio if a else None,
        "ratio",
        base + "packing_loss_ratio",
        "The packing loss",
    )
    harness = col.get(
        "Harness loss",
        a.harness_loss_ratio if a else None,
        "ratio",
        base + "harness_loss_ratio",
        "The harness loss",
    )
    # annual degradation is used by the end-of-life case; it is reported there
    if a is None or not a.faces:
        if a is not None:
            col.problems.append(
                incomplete("The solar array has no faces.", FILE, "solar_array.faces")
            )
        return None
    if None in (irradiance, area, eff, tref, tcell, coeff, packing, harness):
        return None
    assert irradiance is not None and area is not None and eff is not None
    assert tref is not None and tcell is not None and coeff is not None
    assert packing is not None and harness is not None

    # attitude: which direction does the Sun have in the body frame, per step
    att = system.attitude if system else None
    assert att is not None
    pointing = [att.by_mode.get(m, att.default) for m in mode_ids]
    missing = [m for m, p in zip(mode_ids, pointing, strict=True) if p is None]
    if missing:
        col.problems.append(
            incomplete(
                "Some spacecraft modes of the scenario have no pointing and there is no default.",
                FILE,
                "attitude.default",
            )
        )
        return None
    if "sun" in pointing and att.sun_direction_body is None:
        col.problems.append(
            incomplete(
                "A sun-pointing mode is used but the Sun direction in the body frame is missing.",
                FILE,
                "attitude.sun_direction_body",
            )
        )
        return None

    env = run.env
    steps = len(grid_of)
    kinds = np.array([p == "sun" for p in pointing])[step_mode]
    sun_body = np.empty((steps, 3), dtype=np.float64)
    if kinds.any():
        assert att.sun_direction_body is not None
        sun_body[kinds] = np.asarray(att.sun_direction_body, dtype=np.float64)
    if (~kinds).any():
        orbital = sun_in_orbital_frame(env.sun_direction, env.position_m, env.grid.times_s)
        sun_body[~kinds] = orbital[grid_of][~kinds]
    normals = np.array([f.normal_body for f in a.faces], dtype=np.float64)
    counts = np.array([f.cell_count for f in a.faces], dtype=np.float64)
    cosines = arr.face_cosines(normals, sun_body)
    return arr.array_power_w(
        irradiance_wm2=irradiance,
        cell_counts=counts,
        cell_area_m2=area,
        efficiency_ratio=eff,
        temperature_factor_ratio=arr.temperature_factor(tcell, tref, coeff),
        packing_loss_ratio=packing,
        harness_loss_ratio=harness,
        age_factor_ratio=1.0,
        cosines=cosines,
        lit_ratio=lit,
    )


def _peak_violations(
    run: ScenarioRun, modes: tuple[ModeRow, ...], limit: float | None
) -> list[Violation]:
    if limit is None:
        return []
    over = {m.mode_id: m.peak_demand_w for m in modes if m.peak_demand_w is not None}
    out: list[Violation] = []
    for seg in run.timeline:
        peak = over.get(seg.mode)
        if peak is None or peak <= limit + POWER_TOL_W:
            continue
        if out and out[-1].end_s >= seg.start_s - 1e-9:
            previous = out[-1]
            out[-1] = Violation(
                None,
                PEAK_POWER_EXCEEDED,
                previous.start_s,
                seg.end_s,
                max(previous.extreme or 0.0, peak),
                limit,
                "W",
                previous.file,
                previous.path,
            )
        else:
            out.append(
                Violation(
                    None,
                    PEAK_POWER_EXCEEDED,
                    seg.start_s,
                    seg.end_s,
                    peak,
                    limit,
                    "W",
                    FILE,
                    "limits.peak_power_w",
                )
            )
    return out


@dataclass(frozen=True)
class _GridMap:
    """The scenario grid, the refined edges the battery is solved on, and the mapping between."""

    edges: NDArray
    dt: NDArray
    redges: NDArray
    rdt: NDArray
    edge_at: IntArray  # index of each grid edge among the refined edges

    def mean(self, values: NDArray) -> NDArray:
        """Time-weighted mean of a per-refined-step quantity over each grid step."""
        weighted = np.add.reduceat(values * self.rdt, self.edge_at[:-1])
        return np.asarray(weighted / self.dt, dtype=np.float64)

    def at_edges(self, values: NDArray) -> NDArray:
        """A state defined at the refined edges, read at the grid edges (exact: they coincide)."""
        return np.asarray(values[self.edge_at], dtype=np.float64)


@dataclass(frozen=True)
class _CaseSetup:
    """What a case needs besides the time series: its age, array factor and pack capacity."""

    name: str
    years: float | None
    age_factor: float | None
    capacity_wh: float | None


def _case_setup(
    name: str, battery: _BatteryInputs | None, life_yr: float | None, annual: float | None
) -> _CaseSetup:
    """Beginning of life (age 0) needs neither the array degradation nor the battery fade."""
    years = life_yr if name == "eol" else 0.0
    age = None
    if years == 0.0:
        age = 1.0
    elif years is not None and annual is not None:
        age = arr.degradation_factor(annual, years)
    capacity = None
    if battery is not None and years is not None and (years == 0.0 or battery.fade is not None):
        capacity = pack_capacity_wh(
            battery.cell_capacity_ah,
            battery.cell_voltage_v,
            battery.series,
            battery.parallel,
            battery.fade or 0.0,
            years,
        )
    return _CaseSetup(name, years, age, capacity)


def _generation(prepared: _Prepared, setup: _CaseSetup) -> NDArray | None:
    if prepared.base_generation is None or setup.age_factor is None:
        return None
    return prepared.base_generation * setup.age_factor


def _integrate(
    setup: _CaseSetup, battery: _BatteryInputs | None, prepared: _Prepared
) -> BatteryTrace | None:
    generation = _generation(prepared, setup)
    capacity = setup.capacity_wh
    if generation is None or prepared.demand_w is None or battery is None or not capacity:
        return None
    return integrate_battery(
        prepared.grid.rdt,
        generation,
        prepared.demand_w,
        capacity,
        battery.eta_c,
        battery.eta_d,
        battery.initial_soc * capacity,
    )


def _solve_case(
    setup: _CaseSetup,
    prepared: _Prepared,
    battery: _BatteryInputs | None,
    trace: BatteryTrace | None,
    phase: str | None,
    windows: tuple[tuple[float, float], ...],
    run: ScenarioRun,
) -> CaseResult:
    """Describe one case on the refined edges; the series are reported on the scenario grid while
    the extremes, violations and balances come from the refined solution."""
    grid, name, years, capacity = prepared.grid, setup.name, setup.years, setup.capacity_wh
    edges, dt = grid.redges, grid.rdt
    demand_w = prepared.demand_w
    generation = _generation(prepared, setup)

    margin = None if generation is None or demand_w is None else generation - demand_w
    energy = soc = dod = bat_power = unmet = curtailed = None
    if trace is not None and capacity:
        energy = trace.energy_wh
        soc = energy / capacity
        dod = 1.0 - soc
        bat_power, unmet, curtailed = trace.battery_power_w, trace.unmet_w, trace.curtailed_w

    violations: list[Violation] = []
    if dod is not None and battery is not None and battery.dod_limit is not None:
        for start, end, worst in _exceeding(edges, dod, battery.dod_limit):
            violations.append(
                Violation(
                    name,
                    DOD_EXCEEDED,
                    start,
                    end,
                    worst,
                    battery.dod_limit,
                    "ratio",
                    FILE,
                    f"battery.max_dod_ratio.{phase}",
                )
            )
    if unmet is not None:
        # a tolerance relative to the power flowing: the step means carry rounding noise that
        # grows with the length of the run
        assert demand_w is not None and generation is not None
        scale = max(1.0, float(np.max(demand_w)), float(np.max(generation)))
        for a, b in _runs(unmet > POWER_TOL_W * scale):
            violations.append(
                Violation(
                    name,
                    BATTERY_DEPLETED,
                    float(edges[a]),
                    float(edges[b + 1]),
                    float(unmet[a : b + 1].max()),
                    0.0,
                    "W",
                    FILE,
                    "battery",
                )
            )

    balances = _balances(edges, dt, generation, demand_w, energy, windows, run)
    for balance in balances:
        if balance.balance_wh is not None and balance.balance_wh < -ENERGY_TOL_WH:
            violations.append(
                Violation(
                    name,
                    ORBIT_BALANCE_NEGATIVE,
                    balance.start_s,
                    balance.end_s,
                    balance.balance_wh,
                    0.0,
                    "Wh",
                    FILE,
                    "solar_array",
                )
            )
    summary = _summary(dt, generation, demand_w, margin, soc, dod, unmet, curtailed, energy)

    def on_grid(values: NDArray | None) -> NDArray | None:
        return None if values is None else grid.mean(values)

    def at_grid_edges(values: NDArray | None) -> NDArray | None:
        return None if values is None else grid.at_edges(values)

    return CaseResult(
        name,
        years,
        capacity,
        on_grid(generation),
        on_grid(margin),
        at_grid_edges(energy),
        at_grid_edges(soc),
        at_grid_edges(dod),
        on_grid(bat_power),
        on_grid(unmet),
        on_grid(curtailed),
        summary,
        tuple(balances),
        tuple(violations),
    )


def _wh(power_w: NDArray | None, dt: NDArray) -> float | None:
    return None if power_w is None else float(np.sum(power_w * dt) / 3600.0)


def _summary(
    dt: NDArray,
    generation: NDArray | None,
    demand: NDArray | None,
    margin: NDArray | None,
    soc: NDArray | None,
    dod: NDArray | None,
    unmet: NDArray | None,
    curtailed: NDArray | None,
    energy: NDArray | None,
) -> CaseSummary:
    total = float(np.sum(dt))
    gen_wh, dem_wh = _wh(generation, dt), _wh(demand, dt)
    return CaseSummary(
        average_generation_w=None if gen_wh is None else gen_wh * 3600.0 / total,
        average_demand_w=None if dem_wh is None else dem_wh * 3600.0 / total,
        generated_wh=gen_wh,
        demanded_wh=dem_wh,
        minimum_margin_w=None if margin is None else float(margin.min()),
        minimum_soc_ratio=None if soc is None else float(soc.min()),
        maximum_dod_ratio=None if dod is None else float(dod.max()),
        unmet_wh=_wh(unmet, dt),
        curtailed_wh=_wh(curtailed, dt),
        energy_change_wh=None if energy is None else float(energy[-1] - energy[0]),
    )


def _balances(
    edges: NDArray,
    dt: NDArray,
    generation: NDArray | None,
    demand: NDArray | None,
    energy: NDArray | None,
    windows: tuple[tuple[float, float], ...],
    run: ScenarioRun,
) -> list[OrbitBalance]:
    if not windows:
        return []
    bounds = np.array([w for pair in windows for w in pair], dtype=np.float64)
    shadows = merge_intervals(list(run.env.eclipses))
    ecl_s = [e.start_s for e in shadows]
    ecl_e = [e.end_s for e in shadows]
    shadow = integral_of_steps(ecl_s, ecl_e, [1.0] * len(ecl_s), bounds)

    def at(power: NDArray | None) -> NDArray | None:
        if power is None:
            return None
        cumulative = np.concatenate(([0.0], np.cumsum(power * dt))) / 3600.0
        return np.asarray(np.interp(bounds, edges, cumulative), dtype=np.float64)

    gen, dem = at(generation), at(demand)
    stored = None if energy is None else np.interp(bounds, edges, energy)
    out: list[OrbitBalance] = []
    for k, (start, end) in enumerate(windows):
        i0, i1 = 2 * k, 2 * k + 1
        g = None if gen is None else float(gen[i1] - gen[i0])
        d = None if dem is None else float(dem[i1] - dem[i0])
        out.append(
            OrbitBalance(
                k + 1,
                start,
                end,
                float(shadow[i1] - shadow[i0]),
                g,
                d,
                None if g is None or d is None else g - d,
                None if stored is None else float(stored[i1] - stored[i0]),
            )
        )
    return out


def violation_problems(result: TimeDomainResult) -> list[Problem]:
    """One Problem per finding kind and case, with the count, the first time and a jump link.
    The full list of intervals stays in the result."""
    groups: dict[tuple[str, str | None], list[Violation]] = {}
    for v in result.violations:
        groups.setdefault((v.code, v.case), []).append(v)
    out: list[Problem] = []
    for (code, case), items in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1] or "")):
        first = min(items, key=lambda v: v.start_s)
        where = f" Case {case.upper()}." if case else ""
        out.append(
            Problem(
                Severity.ERROR,
                code,
                f"{_MESSAGES[code]}{where} {len(items)} interval(s), the first at "
                f"{format_offset(first.start_s)}.",
                file=first.file,
                path=first.path,
                hint="Open the violations table for every interval; change the input named "
                "here or the scenario.",
            )
        )
    return out


def format_offset(seconds: float) -> str:
    """T+hh:mm:ss from the scenario start (days are folded into the hours)."""
    total = int(math.floor(seconds + 1e-9))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return f"T+{hours:02d}:{minutes:02d}:{secs:02d}"
