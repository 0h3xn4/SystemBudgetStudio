"""Link budgets of a project: the static table at chosen points and the pass time series.

Conventions are in docs/DECISIONS.md D-077 to D-083. A number that is a placeholder or missing
makes every result that needs it `None` (n/a); it is never replaced by zero.
"""

from __future__ import annotations

import csv
import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import numpy as np

from budget_core.assumptions import Assumption, incomplete
from budget_core.control import RunControl, checkpoint, stage
from budget_core.io.paths import resolve_inside
from budget_core.link import budget as lb
from budget_core.model import Antenna, Link, Project, Sourced
from budget_core.power.signals import integral_of_steps
from budget_core.problems import Problem, Severity
from budget_core.scenario.run import ScenarioRun
from budget_core.timeutil import format_utc

NDArray = np.ndarray[Any, np.dtype[np.float64]]
BoolArray = np.ndarray[Any, np.dtype[np.bool_]]
IntArray = np.ndarray[Any, np.dtype[np.int64]]
GainFn = Callable[[NDArray], NDArray]

# A pass is sampled at this step when the environment can give the exact geometry at any time
# (D-057, DV-L3), so the results do not depend on the scenario step; each sample is evaluated at
# the middle of the part of the pass it stands for.
LINK_SAMPLE_S = 5.0
DAY_S = 86400.0

# ---- results --------------------------------------------------------------------------------


@dataclass(frozen=True)
class RateResult:
    data_rate_bps: float
    ebn0_db: float
    margin_db: float
    closes: bool  # margin at least the required margin


@dataclass(frozen=True)
class StaticRow:
    link_id: str
    link_name: str
    direction: str
    point: str
    elevation_deg: float
    range_m: float
    frequency_hz: float
    path_loss_db: float | None
    atmospheric_loss_db: float | None
    other_losses_db: float | None  # pointing, polarisation and implementation
    eirp_dbw: float | None
    g_over_t_dbk: float | None
    cn0_dbhz: float | None
    required_ebn0_db: float | None
    required_margin_db: float | None
    rates: tuple[RateResult, ...]  # empty when n/a
    max_rate_bps: float | None  # highest listed rate that closes; None: none, or n/a
    max_rate_continuous_bps: float | None  # rate at which the margin equals the required margin


@dataclass(frozen=True)
class StaticLinkResult:
    rows: tuple[StaticRow, ...]
    assumptions: tuple[Assumption, ...]
    problems: tuple[Problem, ...]


@dataclass(frozen=True)
class PassSummary:
    index: int
    aos_s: float
    los_s: float
    max_elevation_deg: float
    usable_s: float | None  # time with a rate that closes while the link is active; None: n/a
    minimum_margin_db: float | None  # at the lowest listed rate, over the active samples
    volume_bits: float | None


@dataclass(frozen=True, eq=False)
class LinkSeries:
    """Samples inside the passes of the peer station (K samples, in time order)."""

    link_id: str
    link_name: str
    direction: str
    site: str
    rates_bps: tuple[float, ...]
    required_margin_db: float | None
    times_s: NDArray
    pass_index: IntArray  # which pass each sample belongs to (0-based)
    elevation_deg: NDArray
    range_m: NDArray
    active: BoolArray  # bool: the link is used (active modes) and below the tracking limit
    path_loss_db: NDArray | None
    atmospheric_loss_db: NDArray | None
    eirp_dbw: NDArray | None
    g_over_t_dbk: NDArray | None
    cn0_dbhz: NDArray | None
    margin_db: NDArray | None  # (K, R): margin at each listed rate
    selected_rate_bps: NDArray | None  # highest listed rate that closes (0: none), 0 if inactive
    passes: tuple[PassSummary, ...]
    volume_bits: float | None
    volume_per_day_bits: float | None  # None: n/a, also for a scenario shorter than a day
    # seconds of the pass each sample stands for while the link is active (the weight of its rate
    # in the volume); the sample time is the middle of its part of the pass
    weight_s: NDArray | None = None


@dataclass(frozen=True, eq=False)
class LinkSeriesResult:
    run: ScenarioRun
    series: tuple[LinkSeries, ...]
    assumptions: tuple[Assumption, ...]
    problems: tuple[Problem, ...]


# ---- inputs ---------------------------------------------------------------------------------


class _Notes:
    def __init__(self) -> None:
        self.assumptions: list[Assumption] = []
        self.problems: list[Problem] = []
        self._seen: set[tuple[str, str]] = set()

    def get(
        self, name: str, item: Sourced | None, unit: str, file: str, path: str, what: str
    ) -> float | None:
        key = (file, path)
        first = key not in self._seen
        self._seen.add(key)
        if item is None:
            if first:
                self.assumptions.append(Assumption(name, None, unit, "missing", file, path, True))
                self.problems.append(incomplete(f"{what} is missing.", file, path))
            return None
        if first:
            self.assumptions.append(
                Assumption(name, item.value, unit, item.source, file, path, item.is_placeholder)
            )
            if item.is_placeholder:
                self.problems.append(incomplete(f"{what} is a placeholder.", file, path))
        return None if item.is_placeholder else item.value

    def add_problem(self, problem: Problem) -> None:
        key = (problem.code, problem.file or "", problem.path, problem.message)
        marker = (f"{key[0]}|{key[1]}|{key[2]}|{key[3]}", "")
        if marker not in self._seen:
            self._seen.add(marker)
            self.problems.append(problem)


def _unique(problems: list[Problem]) -> tuple[Problem, ...]:
    seen: set[tuple[str, str | None, str, str]] = set()
    out: list[Problem] = []
    for p in problems:
        key = (p.code, p.file, p.path, p.message)
        if key not in seen:
            seen.add(key)
            out.append(p)
    return tuple(out)


def _constant(value: float) -> GainFn:
    def fn(angle: NDArray) -> NDArray:
        return np.asarray(value + 0.0 * np.asarray(angle), dtype=np.float64)

    return fn


def _table(angles: list[float], gains: list[float]) -> GainFn:
    def fn(angle: NDArray) -> NDArray:
        return np.asarray(lb.interpolate_gain_dbi(angles, gains, angle), dtype=np.float64)

    return fn


def _by_elevation(elevations: list[float], losses: list[float], constant: float) -> GainFn:
    def fn(elevation: NDArray) -> NDArray:
        return np.asarray(
            lb.interpolate_attenuation_db(elevations, losses, elevation) + constant,
            dtype=np.float64,
        )

    return fn


def _summed(parts: list[GainFn]) -> GainFn:
    def fn(elevation: NDArray) -> NDArray:
        total = 0.0 * np.asarray(elevation, dtype=np.float64)
        for part in parts:
            total = total + part(elevation)
        return total

    return fn


@dataclass(frozen=True)
class Resolved:
    link_id: str
    link: Link
    tx_gain: GainFn | None  # by angle from nadir or constant (the angle is ignored then)
    rx_gain: GainFn | None
    tx_power_dbw: float | None
    line_loss_db: float | None
    feed_loss_db: float | None
    tsys_k: float | None
    direct_gt_dbk: float | None
    required_ebn0_db: float | None
    required_margin_db: float | None
    fixed_losses_db: float | None
    attenuation: GainFn | None  # by elevation
    spacecraft_transmits: bool


def _read_pattern(
    project: Project, link_file: str, rel: str, notes: _Notes
) -> tuple[list[float], list[float]] | None:
    path = resolve_inside(project.root, rel)
    if path is None:
        notes.add_problem(
            Problem(
                Severity.ERROR,
                "LINK_INPUT_INVALID",
                "The antenna pattern file must be inside the project folder.",
                file=rel,
                hint="Use a relative path below the project folder; '..', absolute paths and "
                "links that lead out are not followed.",
            )
        )
        return None
    try:
        if not path.is_file():  # a pipe or a device would block the read
            raise OSError("not a regular file")
        with path.open(encoding="utf-8-sig", newline="") as handle:  # Excel writes a BOM
            rows = list(csv.reader(handle))
        header = [c.strip().lower() for c in rows[0]]
        a, g = header.index("angle_deg"), header.index("gain_dbi")
        angles = [float(r[a]) for r in rows[1:] if r]
        gains = [float(r[g]) for r in rows[1:] if r]
        ok = len(angles) >= 2 and all(y > x for x, y in zip(angles, angles[1:], strict=False))
        ok = ok and angles[0] >= 0.0 and angles[-1] <= 180.0
        ok = ok and all(math.isfinite(v) for v in (*angles, *gains))
    except OSError, ValueError, IndexError, UnicodeDecodeError, csv.Error:
        ok = False
    if not ok:
        notes.add_problem(
            Problem(
                Severity.ERROR,
                "LINK_INPUT_INVALID",
                "The antenna pattern file cannot be read as a table of increasing angles.",
                file=rel,
                hint="Expected a comma-separated CSV (UTF-8, with or without a byte order mark) "
                "with the columns angle_deg and gain_dbi: at least two rows, angles between 0 "
                "and 180 and increasing. A semicolon-separated file is not read.",
            )
        )
        return None
    return angles, gains


def _gain_fn(
    project: Project, link_file: str, side: str, antenna: Antenna | None, notes: _Notes
) -> GainFn | None:
    if antenna is None:
        return None
    base = f"{side}.antenna"
    if antenna.gain_dbi is not None:
        value = notes.get(
            f"Antenna gain, {side}",
            antenna.gain_dbi,
            "dBi",
            link_file,
            f"{base}.gain_dbi",
            f"The {side} antenna gain",
        )
        return None if value is None else _constant(value)
    if antenna.pattern is not None:
        pattern = antenna.pattern
        notes.assumptions.append(
            Assumption(
                f"Antenna pattern, {side}",
                None,
                "dBi",
                pattern.source,
                link_file,
                f"{base}.pattern",
                pattern.is_placeholder,
            )
        )
        if pattern.is_placeholder:
            notes.problems.append(
                incomplete(
                    f"The {side} antenna pattern is a placeholder.", link_file, f"{base}.pattern"
                )
            )
            return None
        return _table(pattern.angles_deg, pattern.gains_dbi)
    assert antenna.pattern_file is not None
    placeholder = (antenna.pattern_source or "").strip().upper() == "TBD"
    notes.assumptions.append(
        Assumption(
            f"Antenna pattern file, {side}",
            None,
            "dBi",
            antenna.pattern_source or "",
            link_file,
            f"{base}.pattern_file",
            placeholder,
        )
    )
    if placeholder:
        notes.problems.append(
            incomplete(
                f"The {side} antenna pattern file is a placeholder.",
                link_file,
                f"{base}.pattern_source",
            )
        )
        return None
    table = _read_pattern(project, link_file, antenna.pattern_file, notes)
    if table is None:
        return None
    angles, gains = table
    return _table(angles, gains)


def _attenuation_fn(project: Project, link: Link, link_file: str, notes: _Notes) -> GainFn | None:
    """Sum of the named attenuation entries, each interpolated by elevation. Of the entries of a
    name only those for the link's frequency (within 1 %) count; when none matches, all do and a
    warning says so. Two entries for the same elevation are ambiguous: the larger loss is used."""
    if not link.attenuation:
        return _constant(0.0)
    table = project.config.attenuation_table
    parts: list[GainFn] = []
    ok = True
    tableau = "config/attenuation_table.yaml"
    for i, name in enumerate(link.attenuation):
        entries = [(k, e) for k, e in enumerate(table.entries if table else []) if e.name == name]
        if not entries:
            notes.problems.append(
                incomplete(
                    f"Attenuation number {i + 1} of the link has no entry in {tableau}.",
                    link_file,
                    f"attenuation[{i}]",
                )
            )
            ok = False
            continue
        near = [
            (k, e)
            for k, e in entries
            if abs(e.freq_hz - link.frequency_hz) <= 0.01 * link.frequency_hz
        ]
        chosen = near or entries
        if not near:
            for k, _ in chosen:
                notes.add_problem(
                    Problem(
                        Severity.WARNING,
                        "LINK_ATTENUATION_FREQUENCY",
                        "An attenuation entry used by the link is for a frequency that differs "
                        "from the link's by more than 1 %.",
                        file=tableau,
                        path=f"entries[{k}].freq_hz",
                        hint="Use an entry for the link frequency.",
                    )
                )
        by_elevation: dict[float | None, float] = {}
        for k, e in chosen:
            value = notes.get(
                f"Attenuation {name}"
                + ("" if e.elevation_deg is None else f" at {e.elevation_deg:g} deg"),
                e.loss_db,
                "dB",
                tableau,
                f"entries[{k}].loss_db",
                f"The attenuation loss of table entry {k + 1}",
            )
            if value is None:
                ok = False
                continue
            if e.elevation_deg in by_elevation:
                notes.add_problem(
                    Problem(
                        Severity.WARNING,
                        "LINK_ATTENUATION_DUPLICATE",
                        f"Attenuation number {i + 1} of the link has two entries for the same "
                        "elevation; the larger loss is used.",
                        file=tableau,
                        path=f"entries[{k}]",
                        hint="Keep one entry per elevation.",
                    )
                )
                value = max(value, by_elevation[e.elevation_deg])
            by_elevation[e.elevation_deg] = value
        if not by_elevation:
            continue
        by_el = sorted((e, v) for e, v in by_elevation.items() if e is not None)
        constant = by_elevation.get(None, 0.0)
        els, vals = [e for e, _ in by_el], [v for _, v in by_el]
        parts.append(_by_elevation(els, vals, constant) if by_el else _constant(constant))
    if not ok:
        return None
    return _summed(parts)


def resolve_link(project: Project, link_id: str, notes: _Notes) -> Resolved:
    link = project.links[link_id]
    file = f"links/{link_id}.yaml"
    tx, rx = link.transmitter, link.receiver
    power = notes.get(
        "Transmit power", tx.power_w, "W", file, "transmitter.power_w", "The transmit power"
    )
    line = notes.get(
        "Line loss", tx.line_loss_db, "dB", file, "transmitter.line_loss_db", "The line loss"
    )
    tx_gain = _gain_fn(project, file, "transmitter", tx.antenna, notes)
    rx_gain = _gain_fn(project, file, "receiver", rx.antenna, notes)
    direct = (
        notes.get("G/T", rx.g_over_t_dbk, "dB/K", file, "receiver.g_over_t_dbk", "The receiver G/T")
        if rx.g_over_t_dbk is not None
        else None
    )
    tsys = (
        notes.get(
            "System noise temperature",
            rx.system_noise_temperature_k,
            "K",
            file,
            "receiver.system_noise_temperature_k",
            "The system noise temperature",
        )
        if rx.system_noise_temperature_k is not None
        else None
    )
    feed = (
        notes.get(
            "Feed loss", rx.feed_loss_db, "dB", file, "receiver.feed_loss_db", "The feed loss"
        )
        if rx.feed_loss_db is not None
        else None
    )
    margin = notes.get(
        "Required margin",
        link.required_margin_db,
        "dB",
        file,
        "required_margin_db",
        "The required margin",
    )
    losses = [
        notes.get(
            "Pointing loss",
            link.pointing_loss_db,
            "dB",
            file,
            "pointing_loss_db",
            "The pointing loss",
        ),
        notes.get(
            "Polarisation loss",
            link.polarisation_loss_db,
            "dB",
            file,
            "polarisation_loss_db",
            "The polarisation loss",
        ),
        notes.get(
            "Implementation loss",
            link.implementation_loss_db,
            "dB",
            file,
            "implementation_loss_db",
            "The implementation loss",
        ),
    ]
    fixed = (
        None if any(x is None for x in losses) else float(sum(x for x in losses if x is not None))
    )
    required = _required_ebn0(project, link, file, notes)
    return Resolved(
        link_id,
        link,
        tx_gain,
        rx_gain,
        None if power is None else lb.watt_to_dbw(power),
        line,
        feed,
        tsys,
        direct,
        required,
        margin,
        fixed,
        _attenuation_fn(project, link, file, notes),
        link.direction == "downlink",
    )


def _required_ebn0(project: Project, link: Link, file: str, notes: _Notes) -> float | None:
    table = project.config.ebn0_table
    entries = [
        (i, e)
        for i, e in enumerate(table.entries if table else [])
        if e.modulation == link.modulation and e.coding == link.coding
    ]
    if not entries:
        notes.problems.append(
            incomplete(
                "The Eb/N0 table has no entry for this modulation and coding.",
                "config/ebn0_table.yaml",
                "entries",
            )
        )
        return None
    i, entry = entries[0]
    return notes.get(
        f"Required Eb/N0, {link.modulation} {link.coding}",
        entry.required_ebn0_db,
        "dB",
        "config/ebn0_table.yaml",
        f"entries[{i}].required_ebn0_db",
        "The required Eb/N0",
    )


# ---- evaluation -----------------------------------------------------------------------------


@dataclass(frozen=True, eq=False)
class Evaluation:
    """The terms of the link at the given geometry. Each is computed from its own inputs, so a
    placeholder only blanks the terms that need it (None); C/N0 needs all of them."""

    path_loss_db: NDArray
    atmospheric_loss_db: NDArray | None
    eirp_dbw: NDArray | None
    g_over_t_dbk: NDArray | None
    cn0_dbhz: NDArray | None


def evaluate(res: Resolved, elevation_deg: NDArray, range_m: NDArray) -> Evaluation:
    """The path loss, atmospheric loss, EIRP, G/T and C/N0 at the given geometry."""
    elevation = np.asarray(elevation_deg, dtype=np.float64)
    zero = 0.0 * elevation
    nadir = np.asarray(lb.nadir_angle_deg(elevation, range_m), dtype=np.float64)
    path = np.asarray(lb.free_space_path_loss_db(range_m, res.link.frequency_hz), dtype=np.float64)
    eirp: NDArray | None = None
    if res.tx_gain is not None and res.tx_power_dbw is not None and res.line_loss_db is not None:
        tx_angle = nadir if res.spacecraft_transmits else zero
        eirp = np.asarray(
            res.tx_power_dbw - res.line_loss_db + res.tx_gain(tx_angle), dtype=np.float64
        )
    gt: NDArray | None = None
    if res.direct_gt_dbk is not None:
        gt = np.asarray(res.direct_gt_dbk + zero, dtype=np.float64)
    elif res.rx_gain is not None and res.feed_loss_db is not None and res.tsys_k is not None:
        rx_angle = zero if res.spacecraft_transmits else nadir
        gt = np.asarray(
            lb.g_over_t_dbk(res.rx_gain(rx_angle), res.feed_loss_db, res.tsys_k), dtype=np.float64
        )
    atmos = None if res.attenuation is None else np.asarray(res.attenuation(elevation))
    cn0: NDArray | None = None
    if (
        eirp is not None
        and gt is not None
        and atmos is not None
        and res.fixed_losses_db is not None
    ):
        cn0 = np.asarray(lb.cn0_dbhz(eirp, path, atmos + res.fixed_losses_db, gt), dtype=np.float64)
    return Evaluation(path, atmos, eirp, gt, cn0)


def _not_closed(link_id: str, where: str) -> Problem:
    return Problem(
        Severity.ERROR,
        "LINK_NOT_CLOSED",
        f"Link '{link_id}' closes at none of its listed data rates {where}.",
        file=f"links/{link_id}.yaml",
        path="data_rates_bps",
        hint="Lower the data rates, raise the transmit power or antenna gain, or review the "
        "losses and the required margin.",
    )


def _scalar(x: NDArray) -> float:
    return float(x[0])


def link_static_budget(project: Project) -> StaticLinkResult:
    """The link table at every static point of every link. The project must be valid."""
    notes = _Notes()
    rows: list[StaticRow] = []
    for link_id in sorted(project.links):
        link = project.links[link_id]
        res = resolve_link(project, link_id, notes)
        first_row = len(rows)
        for point in link.static_points:
            el = np.array([point.elevation_deg])
            d = np.array([point.range_m])
            ev = evaluate(res, el, d)
            rates: list[RateResult] = []
            max_rate = cont = None
            if (
                ev.cn0_dbhz is not None
                and res.required_ebn0_db is not None
                and res.required_margin_db is not None
            ):
                for rate in link.data_rates_bps:
                    ebn0 = _scalar(np.asarray(lb.ebn0_db(ev.cn0_dbhz, rate)))
                    m = ebn0 - res.required_ebn0_db
                    rates.append(RateResult(rate, ebn0, m, m >= res.required_margin_db))
                closing = [r.data_rate_bps for r in rates if r.closes]
                max_rate = max(closing) if closing else None
                limit = float(
                    lb.max_rate_for_margin_bps(
                        _scalar(ev.cn0_dbhz), res.required_ebn0_db, res.required_margin_db
                    )
                )
                cont = limit if math.isfinite(limit) else None
            rows.append(
                StaticRow(
                    link_id,
                    link.name,
                    link.direction,
                    point.name,
                    point.elevation_deg,
                    point.range_m,
                    link.frequency_hz,
                    _scalar(ev.path_loss_db),
                    None if ev.atmospheric_loss_db is None else _scalar(ev.atmospheric_loss_db),
                    res.fixed_losses_db,
                    None if ev.eirp_dbw is None else _scalar(ev.eirp_dbw),
                    None if ev.g_over_t_dbk is None else _scalar(ev.g_over_t_dbk),
                    None if ev.cn0_dbhz is None else _scalar(ev.cn0_dbhz),
                    res.required_ebn0_db,
                    res.required_margin_db,
                    tuple(rates),
                    max_rate,
                    cont,
                )
            )
        mine = rows[first_row:]
        if mine and all(r.rates for r in mine) and all(r.max_rate_bps is None for r in mine):
            notes.add_problem(_not_closed(link_id, "at any of its static points"))
        if not link.static_points:
            notes.add_problem(
                Problem(
                    Severity.INFO,
                    "LINK_NO_STATIC_POINTS",
                    f"Link '{link_id}' has no static points; add elevation and range pairs to "
                    "get a static table.",
                    file=f"links/{link_id}.yaml",
                    path="static_points",
                )
            )
    return StaticLinkResult(tuple(rows), tuple(notes.assumptions), _unique(notes.problems))


# ---- pass time series -----------------------------------------------------------------------


def link_pass_series(
    project: Project, run: ScenarioRun, control: RunControl | None = None
) -> LinkSeriesResult:
    """Margin, selected data rate and data volume over every pass of each link's peer station.
    A `control` reports the stage and can stop it between links (D-167)."""
    notes = _Notes()
    env = run.env
    grid_t = env.grid.times_s
    step = env.grid.step_s
    duration = env.grid.duration_s
    series: list[LinkSeries] = []
    stage(control, "Link passes")
    for link_id in sorted(project.links):
        checkpoint(control)
        link = project.links[link_id]
        file = f"links/{link_id}.yaml"
        if link.peer is None:
            continue
        vis = env.sites.get(link.peer)
        if vis is None:
            notes.add_problem(
                Problem(
                    Severity.WARNING,
                    "LINK_SITE_NOT_IN_SCENARIO",
                    f"The peer of link '{link_id}' is not a site of the scenario, so there is no "
                    "pass series for it.",
                    file=f"scenarios/{run.scenario_id}.yaml",
                    path="sites",
                    hint="Add the ground station to 'sites' of the scenario.",
                )
            )
            continue
        res = resolve_link(project, link_id, notes)
        exact = vis.geometry_at is not None
        lows: list[float] = []
        highs: list[float] = []
        pass_of: list[int] = []
        for k, p in enumerate(vis.passes):
            for lo, hi in _pass_pieces(p.aos_s, p.los_s, grid_t, step, duration, exact):
                lows.append(lo)
                highs.append(hi)
                pass_of.append(k)
        low_arr, high_arr = np.array(lows, dtype=np.float64), np.array(highs, dtype=np.float64)
        times = 0.5 * (low_arr + high_arr)  # each piece is evaluated at its middle
        if vis.geometry_at is not None and len(times):
            el, _, rng = vis.geometry_at(times)
        else:
            el = np.interp(times, grid_t, np.asarray(vis.elevation_deg, dtype=np.float64))
            rng = np.interp(times, grid_t, np.asarray(vis.range_m, dtype=np.float64))
        el, rng = np.asarray(el, dtype=np.float64), np.asarray(rng, dtype=np.float64)
        w_arr = high_arr - low_arr
        pass_arr = np.array(pass_of, dtype=np.int64)
        # time of each sample's part of the pass that falls in a mode the link runs in: a mode
        # change inside a sample counts for exactly the time it covers
        if link.active_modes:
            ours = [seg for seg in run.timeline if seg.mode in link.active_modes]
            starts, ends = [seg.start_s for seg in ours], [seg.end_s for seg in ours]
            ones = [1.0] * len(ours)
            span_hi = integral_of_steps(starts, ends, ones, high_arr)
            span_lo = integral_of_steps(starts, ends, ones, low_arr)
            w_arr = np.clip(span_hi - span_lo, 0.0, w_arr)
        active = w_arr > 1e-12
        if link.max_elevation_deg is not None:
            active &= el <= link.max_elevation_deg
        w_arr = np.where(active, w_arr, 0.0)
        ev = evaluate(res, el, rng)
        margins = selected = None
        volume = per_day = None
        summaries: list[PassSummary] = []
        rates = tuple(link.data_rates_bps)
        if (
            ev.cn0_dbhz is not None
            and res.required_ebn0_db is not None
            and res.required_margin_db is not None
        ):
            margins = np.stack(
                [lb.ebn0_db(ev.cn0_dbhz, r) - res.required_ebn0_db for r in rates], axis=1
            )
            closes = margins >= res.required_margin_db
            rate_arr = np.array(rates)
            chosen = np.where(closes, rate_arr[None, :], 0.0).max(axis=1)
            selected = np.where(active, chosen, 0.0)
            bits = selected * w_arr
            volume = float(bits.sum())
            per_day = volume / (duration / DAY_S) if duration >= DAY_S * (1.0 - 1e-9) else None
            if active.any() and not bool((selected > 0).any()):
                notes.add_problem(_not_closed(link_id, "in any pass of this scenario"))
            if not active.any():
                notes.add_problem(
                    Problem(
                        Severity.INFO,
                        "LINK_NEVER_ACTIVE",
                        f"Link '{link_id}' is never active in this scenario: no pass of its "
                        "station falls in an active mode below the tracking limit, so its data "
                        "volume is zero.",
                        file=file,
                        path="active_modes",
                        hint="Check the scenario's sites and rules, 'active_modes' and "
                        "'max_elevation_deg' of the link.",
                    )
                )
        for k, p in enumerate(vis.passes):
            mask = pass_arr == k
            usable = float(w_arr[mask & (selected > 0)].sum()) if selected is not None else None
            low = (
                float(margins[mask & active, 0].min())
                if margins is not None and bool((mask & active).any())
                else None
            )
            summaries.append(
                PassSummary(
                    k + 1,
                    p.aos_s,
                    p.los_s,
                    p.max_elevation_deg,
                    usable,
                    low,
                    None if selected is None else float((selected * w_arr)[mask].sum()),
                )
            )
        series.append(
            LinkSeries(
                link_id,
                link.name,
                link.direction,
                link.peer,
                rates,
                res.required_margin_db,
                times,
                pass_arr,
                el,
                rng,
                active,
                ev.path_loss_db,
                ev.atmospheric_loss_db,
                ev.eirp_dbw,
                ev.g_over_t_dbk,
                ev.cn0_dbhz,
                margins,
                selected,
                tuple(summaries),
                volume,
                per_day,
                w_arr,
            )
        )
    if duration < DAY_S * (1.0 - 1e-9) and any(s.volume_bits is not None for s in series):
        notes.add_problem(
            Problem(
                Severity.INFO,
                "LINK_PER_DAY_NOT_GIVEN",
                "The scenario is shorter than one day, so the data volume per day is not given "
                "(scaling a short scenario to a day would repeat its passes).",
                file=f"scenarios/{run.scenario_id}.yaml",
                path="duration_s",
                hint="Use a scenario of at least one day for a per-day figure.",
            )
        )
    notes.problems.extend(run.problems)
    return LinkSeriesResult(run, tuple(series), tuple(notes.assumptions), _unique(notes.problems))


def _pass_pieces(
    aos_s: float,
    los_s: float,
    grid_t: NDArray,
    step_s: float,
    duration_s: float,
    exact: bool,
) -> list[tuple[float, float]]:
    """The parts of a pass that are sampled: equal pieces of at most `LINK_SAMPLE_S` when the
    geometry can be computed at any time, else the part of the pass in each grid step."""
    if los_s - aos_s <= 1e-12:
        return []
    if exact:
        count = max(1, math.ceil((los_s - aos_s) / LINK_SAMPLE_S - 1e-9))
        bounds = np.linspace(aos_s, los_s, count + 1)
        return [(float(a), float(b)) for a, b in zip(bounds[:-1], bounds[1:], strict=True)]
    pieces: list[tuple[float, float]] = []
    first = max(int(np.searchsorted(grid_t, aos_s, side="right")) - 1, 0)
    last = int(np.searchsorted(grid_t, los_s, side="left"))
    for i in range(first, min(last + 1, len(grid_t))):
        t0, t1 = float(grid_t[i]), min(float(grid_t[i]) + step_s, duration_s)
        lo, hi = max(t0, aos_s), min(t1, los_s)
        if hi - lo > 1e-12:
            pieces.append((lo, hi))
    return pieces


def format_offset_utc(run: ScenarioRun, seconds: float) -> str:
    return format_utc(run.env.grid.start + timedelta(seconds=seconds))
