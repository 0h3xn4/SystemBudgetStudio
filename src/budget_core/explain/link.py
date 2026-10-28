"""Explanations of the static link budget (tables of `reports/link_report.py`, D-206).

Table ids (`Table.explain_id`): `link:static` (rows named by the link and the point) and
`link:rates` (rows named by the link, the point and the data rate in kbit/s). The explanation
computes each term again from the link file and the configuration with the functions of
`budget_core.link.budget` that the solver uses (`eirp_from_dbw`, `free_space_path_loss_db`,
`g_over_t_dbk`, `cn0_dbhz`, `ebn0_db`, `margin_db`, `nadir_angle_deg`), so the numbers agree
with the table by construction; a test checks every cell. The pass series (margin over time,
data volume) is not explained yet.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace

import numpy as np

from budget_core.explain.power import ExplainError
from budget_core.explain.trace import Explanation, Quantity, Step, equations_used, link_steps
from budget_core.link import budget as lb
from budget_core.link.constants import (
    BOLTZMANN_DBW_HZ_K,
    BOLTZMANN_SOURCE,
    EARTH_RADIUS_M,
    EARTH_RADIUS_SOURCE,
    SPEED_OF_LIGHT_MS,
    SPEED_OF_LIGHT_SOURCE,
)
from budget_core.link.evaluate import (
    Resolved,
    StaticLinkResult,
    StaticRow,
    link_static_budget,
    resolve_for_explain,
)
from budget_core.model import Antenna, Project, Sourced

EBN0_FILE = "config/ebn0_table.yaml"
ATT_FILE = "config/attenuation_table.yaml"

Cell = tuple[list[Step], Quantity]


def _value(item: Sourced | None) -> float | None:
    return None if item is None or item.is_placeholder else item.value


def _src(item: Sourced | None) -> str:
    return "" if item is None else item.source


def _sourced(name: str, item: Sourced | None, unit: str, file: str, path: str) -> Quantity:
    return Quantity(
        name,
        _value(item),
        unit,
        f"{file} {path}" + ("" if item is not None else " (missing)"),
        _src(item),
    )


def _read(q: Quantity, logic: str = "Not computed: an input.") -> Cell:
    return [Step("Read from the project", (), q, logic=logic)], q


def _f(q: Quantity) -> float | None:
    return q.value if isinstance(q.value, float) else None


def _all(*values: float | None) -> bool:
    return all(v is not None for v in values)


@dataclass
class _Chain:
    """The terms of one link at one static point, each made once (steps are kept in order)."""

    project: Project
    row: StaticRow
    steps: list[Step] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.link = self.project.links[self.row.link_id]
        self.file = f"links/{self.row.link_id}.yaml"
        self.res: Resolved = resolve_for_explain(self.project, self.row.link_id)
        self.index = next(
            (i for i, p in enumerate(self.link.static_points) if p.name == self.row.point), 0
        )
        self.el = np.array([self.row.elevation_deg])
        self.dist = np.array([self.row.range_m])
        self._memo: dict[str, Quantity] = {}

    # ---- helpers -----------------------------------------------------------------------------
    def _once(self, key: str, make: Callable[[], Quantity]) -> Quantity:
        if key not in self._memo:
            self._memo[key] = make()
        return self._memo[key]

    def _add(self, step: Step) -> Quantity:
        self.steps.append(step)
        return step.result

    # ---- the geometry -----------------------------------------------------------------------
    def elevation(self) -> Quantity:
        return Quantity(
            f"elevation of {self.row.point}",
            self.row.elevation_deg,
            "deg",
            f"{self.file} static_points[{self.index}].elevation_deg",
        )

    def distance(self) -> Quantity:
        return Quantity(
            f"range of {self.row.point}",
            self.row.range_m,
            "m",
            f"{self.file} static_points[{self.index}].range_m",
        )

    def frequency(self) -> Quantity:
        return Quantity("link frequency", self.link.frequency_hz, "Hz", f"{self.file} frequency_hz")

    def nadir(self) -> Quantity:
        def make() -> Quantity:
            value = float(np.asarray(lb.nadir_angle_deg(self.el, self.dist), dtype=np.float64)[0])
            return self._add(
                Step(
                    "Angle from nadir at the spacecraft",
                    (
                        self.elevation(),
                        self.distance(),
                        Quantity(
                            "Earth radius", EARTH_RADIUS_M, "m", "constant", EARTH_RADIUS_SOURCE
                        ),
                    ),
                    Quantity("angle from nadir", value, "deg", "this step"),
                    "LNK-NADIR",
                    "Spherical Earth; the spacecraft antenna is assumed to point at nadir "
                    "(DEVIATIONS DV-L2).",
                )
            )

        return self._once("nadir", make)

    # ---- transmitter ------------------------------------------------------------------------
    def tx_power_dbw(self) -> Quantity:
        def make() -> Quantity:
            tx = self.link.transmitter
            power = _sourced("transmit power", tx.power_w, "W", self.file, "transmitter.power_w")
            return self._add(
                Step(
                    "Transmit power in dBW",
                    (power,),
                    Quantity("transmit power", self.res.tx_power_dbw, "dBW", "this step"),
                    logic="10 log10(P / 1 W).",
                )
            )

        return self._once("txp", make)

    def gain(self, side: str) -> Quantity:
        def make() -> Quantity:
            transmitter = side == "transmitter"
            antenna: Antenna | None = (
                self.link.transmitter.antenna if transmitter else self.link.receiver.antenna
            )
            fn = self.res.tx_gain if transmitter else self.res.rx_gain
            name = f"{side} antenna gain"
            if antenna is None or fn is None:
                return Quantity(name, None, "dBi", f"{self.file} {side}.antenna (missing)")
            base = f"{side}.antenna"
            if antenna.gain_dbi is not None:
                return self._add(
                    Step(
                        "Antenna gain",
                        (_sourced(name, antenna.gain_dbi, "dBi", self.file, f"{base}.gain_dbi"),),
                        Quantity(name, _value(antenna.gain_dbi), "dBi", "this step"),
                        logic="A constant gain, the same at every angle.",
                    )
                )
            spacecraft_side = transmitter == (self.link.direction == "downlink")
            if spacecraft_side:
                angle = self.nadir()
            else:
                angle = Quantity(
                    "angle from boresight",
                    0.0,
                    "deg",
                    "the ground antenna points at the spacecraft",
                )
            if antenna.pattern is not None:
                what = Quantity(
                    f"{side} antenna pattern",
                    f"table of {len(antenna.pattern.angles_deg)} angles",
                    "",
                    f"{self.file} {base}.pattern",
                    antenna.pattern.source,
                )
            else:
                what = Quantity(
                    f"{side} antenna pattern",
                    "table read from a file",
                    "",
                    f"{self.file} {base}.pattern_file = {antenna.pattern_file}",
                    antenna.pattern_source or "",
                )
            value = float(np.asarray(fn(np.array([angle.value])), dtype=np.float64)[0])
            return self._add(
                Step(
                    "Antenna gain at the angle",
                    (angle, what),
                    Quantity(name, value, "dBi", "this step"),
                    logic="Linear interpolation in the pattern table; beyond the ends of the "
                    "table the end values are used.",
                )
            )

        return self._once(f"gain-{side}", make)

    def eirp(self) -> Quantity:
        def make() -> Quantity:
            tx = self.link.transmitter
            power = self.tx_power_dbw()
            line = _sourced(
                "line loss", tx.line_loss_db, "dB", self.file, "transmitter.line_loss_db"
            )
            gain = self.gain("transmitter")
            p, ll, g = _f(power), _f(line), _f(gain)
            value = (
                float(np.asarray(lb.eirp_from_dbw(p, ll, np.array([g])), dtype=np.float64)[0])
                if p is not None and ll is not None and g is not None
                else None
            )
            return self._add(
                Step(
                    "Effective isotropic radiated power",
                    (power, line, gain),
                    Quantity("EIRP", value, "dBW", "this step"),
                    "LNK-EIRP",
                )
            )

        return self._once("eirp", make)

    # ---- receiver ---------------------------------------------------------------------------
    def g_over_t(self) -> Quantity:
        def make() -> Quantity:
            rx = self.link.receiver
            if rx.g_over_t_dbk is not None:
                return self._add(
                    Step(
                        "Receiver G/T",
                        (
                            _sourced(
                                "G/T", rx.g_over_t_dbk, "dB/K", self.file, "receiver.g_over_t_dbk"
                            ),
                        ),
                        Quantity("G/T", _value(rx.g_over_t_dbk), "dB/K", "this step"),
                        logic="Given directly in the link file.",
                    )
                )
            gain = self.gain("receiver")
            feed = _sourced("feed loss", rx.feed_loss_db, "dB", self.file, "receiver.feed_loss_db")
            tsys = _sourced(
                "system noise temperature",
                rx.system_noise_temperature_k,
                "K",
                self.file,
                "receiver.system_noise_temperature_k",
            )
            g, fl, t = _f(gain), _f(feed), _f(tsys)
            value = (
                float(np.asarray(lb.g_over_t_dbk(np.array([g]), fl, t), dtype=np.float64)[0])
                if g is not None and fl is not None and t is not None
                else None
            )
            return self._add(
                Step(
                    "Receiver figure of merit",
                    (gain, feed, tsys),
                    Quantity("G/T", value, "dB/K", "this step"),
                    "LNK-GT",
                )
            )

        return self._once("gt", make)

    # ---- path -------------------------------------------------------------------------------
    def path_loss(self) -> Quantity:
        def make() -> Quantity:
            value = float(
                np.asarray(
                    lb.free_space_path_loss_db(self.dist, self.link.frequency_hz), dtype=np.float64
                )[0]
            )
            return self._add(
                Step(
                    "Free-space path loss",
                    (
                        self.distance(),
                        self.frequency(),
                        Quantity(
                            "speed of light",
                            SPEED_OF_LIGHT_MS,
                            "m/s",
                            "constant",
                            SPEED_OF_LIGHT_SOURCE,
                        ),
                    ),
                    Quantity("free-space path loss", value, "dB", "this step"),
                    "LNK-FSPL",
                )
            )

        return self._once("fspl", make)

    def atmospheric(self) -> Quantity:
        def make() -> Quantity:
            link = self.link
            table = self.project.config.attenuation_table
            inputs: list[Quantity] = [self.elevation()]
            for name in link.attenuation:
                entries = [
                    (k, e) for k, e in enumerate(table.entries if table else []) if e.name == name
                ]
                near = [
                    (k, e)
                    for k, e in entries
                    if abs(e.freq_hz - link.frequency_hz) <= 0.01 * link.frequency_hz
                ]
                for k, e in near or entries:
                    where = "" if e.elevation_deg is None else f" at {e.elevation_deg:g} deg"
                    inputs.append(
                        _sourced(
                            f"attenuation {name}{where}",
                            e.loss_db,
                            "dB",
                            ATT_FILE,
                            f"entries[{k}].loss_db",
                        )
                    )
            value = (
                None
                if self.res.attenuation is None
                else float(np.asarray(self.res.attenuation(self.el))[0])
            )
            return self._add(
                Step(
                    "Atmospheric attenuation",
                    tuple(inputs),
                    Quantity("atmospheric loss", value, "dB", "this step"),
                    "LNK-ATT",
                    "Sum of the table entries the link names (those for its frequency, within "
                    "1 %), each interpolated linearly by elevation. The tool has no propagation "
                    "model of its own."
                    if link.attenuation
                    else "The link names no attenuation, so it is 0 dB.",
                )
            )

        return self._once("att", make)

    def fixed_losses(self) -> Quantity:
        def make() -> Quantity:
            link = self.link
            parts = (
                _sourced(
                    "pointing loss", link.pointing_loss_db, "dB", self.file, "pointing_loss_db"
                ),
                _sourced(
                    "polarisation loss",
                    link.polarisation_loss_db,
                    "dB",
                    self.file,
                    "polarisation_loss_db",
                ),
                _sourced(
                    "implementation loss",
                    link.implementation_loss_db,
                    "dB",
                    self.file,
                    "implementation_loss_db",
                ),
            )
            values = [_f(p) for p in parts]
            known = [v for v in values if v is not None]
            value = float(sum(known)) if len(known) == len(values) else None
            return self._add(
                Step(
                    "Pointing, polarisation and implementation losses",
                    parts,
                    Quantity("other losses", value, "dB", "this step"),
                    logic="Sum of the three losses of the link file.",
                )
            )

        return self._once("fixed", make)

    # ---- carrier to noise ---------------------------------------------------------------------
    def cn0(self) -> Quantity:
        def make() -> Quantity:
            eirp, path, gt = self.eirp(), self.path_loss(), self.g_over_t()
            atm, fixed = self.atmospheric(), self.fixed_losses()
            a, fx = _f(atm), _f(fixed)
            other_value = None if a is None or fx is None else float(np.array([a])[0] + fx)
            other = self._add(
                Step(
                    "All losses besides the path loss",
                    (atm, fixed),
                    Quantity("atmospheric and other losses", other_value, "dB", "this step"),
                    logic="Atmospheric loss plus the pointing, polarisation and implementation "
                    "losses.",
                )
            )
            e, p, o, g = _f(eirp), _f(path), _f(other), _f(gt)
            value = (
                float(
                    np.asarray(
                        lb.cn0_dbhz(np.array([e]), np.array([p]), np.array([o]), np.array([g])),
                        dtype=np.float64,
                    )[0]
                )
                if e is not None and o is not None and g is not None and p is not None
                else None
            )
            return self._add(
                Step(
                    "Carrier to noise density",
                    (
                        eirp,
                        path,
                        other,
                        gt,
                        Quantity(
                            "10 log10 of the Boltzmann constant",
                            BOLTZMANN_DBW_HZ_K,
                            "dBW/(Hz K)",
                            "constant",
                            BOLTZMANN_SOURCE,
                        ),
                    ),
                    Quantity("C/N0", value, "dBHz", "this step"),
                    "LNK-CN0",
                )
            )

        return self._once("cn0", make)

    # ---- the requirement ----------------------------------------------------------------------
    def required_ebn0(self) -> Quantity:
        def make() -> Quantity:
            table = self.project.config.ebn0_table
            link = self.link
            found = next(
                (
                    (i, e)
                    for i, e in enumerate(table.entries if table else [])
                    if e.modulation == link.modulation and e.coding == link.coding
                ),
                None,
            )
            if found is None:
                q = Quantity(
                    "required Eb/N0", None, "dB", f"{EBN0_FILE} (no entry for this modulation)"
                )
            else:
                i, entry = found
                q = _sourced(
                    f"required Eb/N0, {link.modulation} {link.coding}",
                    entry.required_ebn0_db,
                    "dB",
                    EBN0_FILE,
                    f"entries[{i}].required_ebn0_db",
                )
            return self._add(
                Step(
                    "Required Eb/N0 of the modulation and coding",
                    (q,),
                    replace(q, origin="this step"),
                    logic=f"The entry of {EBN0_FILE} for {link.modulation} with {link.coding}.",
                )
            )

        return self._once("req", make)

    def required_margin(self) -> Quantity:
        return _sourced(
            "required margin",
            self.link.required_margin_db,
            "dB",
            self.file,
            "required_margin_db",
        )

    # ---- one data rate -------------------------------------------------------------------------
    def rate(self, bps: float) -> Quantity:
        index = self.link.data_rates_bps.index(bps)
        return Quantity("data rate", bps, "bit/s", f"{self.file} data_rates_bps[{index}]")

    def ebn0(self, bps: float) -> Quantity:
        def make() -> Quantity:
            cn0 = self.cn0()
            c = _f(cn0)
            value = (
                float(np.asarray(lb.ebn0_db(np.array([c]), bps), dtype=np.float64)[0])
                if c is not None
                else None
            )
            return self._add(
                Step(
                    f"Eb/N0 at {bps:g} bit/s",
                    (cn0, self.rate(bps)),
                    Quantity(f"Eb/N0 at {bps:g} bit/s", value, "dB", "this step"),
                    "LNK-EBN0",
                )
            )

        return self._once(f"ebn0-{bps}", make)

    def margin(self, bps: float) -> Quantity:
        def make() -> Quantity:
            ebn0, req = self.ebn0(bps), self.required_ebn0()
            e, r = _f(ebn0), _f(req)
            value = None if e is None or r is None else float(lb.margin_db(e, r))
            return self._add(
                Step(
                    f"Margin at {bps:g} bit/s",
                    (ebn0, replace(req, name="required Eb/N0")),
                    Quantity(f"margin at {bps:g} bit/s", value, "dB", "this step"),
                    "LNK-MARGIN",
                )
            )

        return self._once(f"margin-{bps}", make)

    def closes(self, bps: float) -> Quantity:
        def make() -> Quantity:
            margin, need = self.margin(bps), self.required_margin()
            m, n = _f(margin), _f(need)
            value = None if m is None or n is None else ("yes" if m >= n else "no")
            return self._add(
                Step(
                    f"Does the link close at {bps:g} bit/s",
                    (margin, need),
                    Quantity(f"closes at {bps:g} bit/s", value, "", "this step"),
                    logic="Yes when the margin is at least the required margin of the link.",
                )
            )

        return self._once(f"closes-{bps}", make)


# ---- the cells ------------------------------------------------------------------------------
def _static_cell(chain: _Chain, column: str) -> Cell:
    row, link = chain.row, chain.link
    plain = {
        "Link": ("link id", row.link_id, chain.file),
        "Direction": ("direction", row.direction, f"{chain.file} direction"),
        "Point": (
            "static point",
            row.point,
            f"{chain.file} static_points[{chain.index}].name",
        ),
    }
    if column in plain:
        label, text, origin = plain[column]
        return _read(Quantity(label, text, "", origin))
    if column == "Elevation (deg)":
        return _read(chain.elevation())
    if column == "Range (km)":
        metres = chain.distance()
        step = Step(
            "Range in kilometres",
            (metres,),
            Quantity("range", row.range_m / 1000.0, "km", "this step"),
            logic="Metres divided by 1000.",
        )
        return [step], step.result
    simple = {
        "EIRP (dBW)": chain.eirp,
        "G/T (dB/K)": chain.g_over_t,
        "Path loss (dB)": chain.path_loss,
        "Atmospheric (dB)": chain.atmospheric,
        "Other losses (dB)": chain.fixed_losses,
        "C/N0 (dBHz)": chain.cn0,
        "Required Eb/N0 (dB)": chain.required_ebn0,
    }
    if column in simple:
        result = simple[column]()
        return chain.steps, result
    if column == "Highest closing rate (kbit/s)":
        cn0, req, need = chain.cn0(), chain.required_ebn0(), chain.required_margin()
        available = all(_f(q) is not None for q in (cn0, req, need))
        members = [chain.closes(r) for r in link.data_rates_bps] if available else []
        closing = [
            r for r, m in zip(link.data_rates_bps, members, strict=False) if m.value == "yes"
        ]
        value = max(closing) / 1000.0 if closing else None
        step = Step(
            "Highest listed rate that closes",
            tuple(members) if members else (cn0, req, need),
            Quantity("highest closing rate", value, "kbit/s", "this step"),
            logic="The highest of the listed data rates at which the link closes, in kbit/s. "
            "n/a when an input is missing; also n/a when no listed rate closes.",
        )
        chain.steps.append(step)
        return chain.steps, step.result
    if column == "Rate at required margin (kbit/s)":
        cn0, req, need = chain.cn0(), chain.required_ebn0(), chain.required_margin()
        c, r, n = _f(cn0), _f(req), _f(need)
        value = None
        if c is not None and r is not None and n is not None:
            limit = float(lb.max_rate_for_margin_bps(c, r, n))
            value = limit / 1000.0 if math.isfinite(limit) else None
        step = Step(
            "Data rate at which the margin equals the required margin",
            (cn0, replace(req, name="required Eb/N0"), need),
            Quantity("rate at required margin", value, "kbit/s", "this step"),
            logic="10 ^ ((C/N0 - required Eb/N0 - required margin) / 10), in kbit/s; n/a when it "
            "is not finite.",
        )
        chain.steps.append(step)
        return chain.steps, step.result
    raise ExplainError("This column is not explained.")


def _rate_cell(chain: _Chain, bps: float, column: str) -> Cell:
    if column == "Data rate (kbit/s)":
        return _read(
            Quantity(
                "data rate",
                bps / 1000.0,
                "kbit/s",
                f"{chain.file} data_rates_bps[{chain.link.data_rates_bps.index(bps)}] (÷ 1000)",
            )
        )
    if column in ("Link", "Point"):
        q = (
            Quantity("link id", chain.row.link_id, "", chain.file)
            if column == "Link"
            else Quantity("static point", chain.row.point, "", chain.file)
        )
        return _read(q)
    if column == "Eb/N0 (dB)":
        result = chain.ebn0(bps)
    elif column == "Margin (dB)":
        result = chain.margin(bps)
    elif column == "Required margin (dB)":
        return _read(chain.required_margin())
    elif column == "Closes":
        result = chain.closes(bps)
    else:
        raise ExplainError("This column is not explained.")
    return chain.steps, result


# ---- entry points -------------------------------------------------------------------------
def link_table_ids(project: Project) -> list[tuple[str, str]]:
    if not project.links:
        return []
    return [
        ("link:static", "Link budget at the static points"),
        ("link:rates", "Margin by data rate"),
    ]


def explain_link(
    project: Project,
    table_id: str,
    key: Sequence[str],
    column: str,
    result: StaticLinkResult | None = None,
) -> Explanation:
    result = link_static_budget(project) if result is None else result
    kind = table_id.split(":", 1)[1] if ":" in table_id else ""
    if kind not in ("static", "rates"):
        raise ExplainError("This table cannot be explained.")
    need = 2 if kind == "static" else 3
    if len(key) < need:
        raise ExplainError(
            "Name the link, the point" + (" and the data rate." if need == 3 else ".")
        )
    row = next((r for r in result.rows if r.link_id == key[0] and r.point == key[1]), None)
    if row is None:
        raise ExplainError("There is no such link and point in this table.")
    chain = _Chain(project, row)
    if kind == "static":
        steps, final = _static_cell(chain, column)
        title = f"Link budget at the static points / {key[0]} / {key[1]} / {column}"
    else:
        try:
            wanted = float(key[2])
        except ValueError:
            raise ExplainError("The data rate is a number in kbit/s.") from None
        bps = next(
            (
                r.data_rate_bps
                for r in row.rates
                if abs(r.data_rate_bps / 1000.0 - wanted) <= 1e-9 * max(1.0, abs(wanted))
            ),
            None,
        )
        if bps is None:
            raise ExplainError("There is no such data rate for this link and point.")
        steps, final = _rate_cell(chain, bps, column)
        title = f"Margin by data rate / {key[0]} / {key[1]} / {key[2]} kbit/s / {column}"
    linked = link_steps(tuple(steps))
    return Explanation(
        (table_id, tuple(key), column),
        title,
        replace(final, origin=""),
        linked,
        equations=equations_used(linked),
    )
