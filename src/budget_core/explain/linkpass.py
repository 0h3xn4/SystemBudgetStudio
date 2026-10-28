"""Explanations of the link pass tables (tables of `reports/link_report.py`, D-209).

Table ids (`Table.explain_id`): `linkpass:volume` (the data volume of each link; a row is named by
the link) and `linkpass:passes:<link>` (the passes of one link; a row is named by the pass number).

A pass is sampled in pieces (equal pieces of at most the sample length when the geometry can be
computed at any time, else the part of the pass in each grid step); every piece is evaluated at its
middle and stands for the seconds of the piece in which the link is active (its modes, below its
tracking limit). The series of the solver (`LinkSeries`) holds the per-sample geometry, margins,
chosen rate and weight, so the pass numbers are computed again from it with the functions the solver
uses (`data_volume_bits`, and the link budget chain for the margin of a sample); a test checks every
cell. The lowest margin of a pass is explained as the whole link budget at the sample where it
occurs.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import timedelta

import numpy as np

from budget_core.explain.link import Cell, _Chain, _read
from budget_core.explain.power import ExplainError
from budget_core.explain.trace import Explanation, Quantity, Step, equations_used, link_steps
from budget_core.link.budget import data_volume_bits
from budget_core.link.evaluate import DAY_S, LinkSeries, LinkSeriesResult, StaticRow
from budget_core.model import Project
from budget_core.power.time_domain import format_offset
from budget_core.timeutil import format_utc


def linkpass_table_ids(project: Project) -> list[tuple[str, str]]:
    """(table id, title) of every explainable link pass table; a link has one when it has a peer
    station."""
    peers = {i: link.peer for i, link in sorted(project.links.items()) if link.peer}
    if not peers:
        return []
    return [
        ("linkpass:volume", "Data volume per link"),
        *((f"linkpass:passes:{i}", f"Passes of link {i} over {site}") for i, site in peers.items()),
    ]


@dataclass
class _SampleChain(_Chain):
    """The link budget at one sample of a pass: the elevation and range come from the series."""

    origin: str = ""

    def elevation(self) -> Quantity:
        return Quantity(
            f"elevation at {self.row.point}", self.row.elevation_deg, "deg", self.origin
        )

    def distance(self) -> Quantity:
        return Quantity(f"range at {self.row.point}", self.row.range_m, "m", self.origin)


def _row(
    s: LinkSeries, point: str, elevation_deg: float, range_m: float, frequency_hz: float
) -> StaticRow:
    return StaticRow(
        s.link_id,
        s.link_name,
        s.direction,
        point,
        elevation_deg,
        range_m,
        frequency_hz,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        s.required_margin_db,
        (),
        None,
        None,
    )


class _Ctx:
    def __init__(self, project: Project, result: LinkSeriesResult, s: LinkSeries) -> None:
        self.project = project
        self.result = result
        self.s = s
        self.link = project.links[s.link_id]
        self.file = f"links/{s.link_id}.yaml"
        self.run = result.run

    def utc(self, seconds: float) -> str:
        return format_utc(self.run.env.grid.start + timedelta(seconds=seconds))

    def chain(self, i: int | None) -> _SampleChain:
        """The budget at sample `i` (the first sample, or a geometry of zero, when `i` is None: for
        the terms that do not depend on the geometry)."""
        s = self.s
        if i is None:
            point, el, rng, origin = "no sample", 0.0, 0.0, ""
        else:
            t = float(s.times_s[i])
            point = f"the sample at {format_offset(t)}"
            el, rng = float(s.elevation_deg[i]), float(s.range_m[i])
            origin = (
                f"pass {int(s.pass_index[i]) + 1} of {s.site}, sample at {format_offset(t)} "
                "(middle of its part of the pass)"
            )
        return _SampleChain(
            self.project,
            _row(s, point, el, rng, self.link.frequency_hz),
            origin=origin,
        )

    # ---- the terms of the volume ---------------------------------------------------------------
    def active_seconds(
        self, mask: np.ndarray | None = None
    ) -> tuple[Quantity, tuple[Quantity, ...]]:
        s = self.s
        weight = s.weight_s
        link = self.link
        modes = ", ".join(link.active_modes) if link.active_modes else "all modes"
        limit = link.max_elevation_deg
        inputs = (
            Quantity(
                "samples",
                float(len(s.times_s) if mask is None else int(mask.sum())),
                "",
                "pass series",
            ),
            Quantity("active modes", modes, "", f"{self.file} active_modes"),
            Quantity(
                "tracking limit (maximum elevation)",
                limit,
                "deg",
                f"{self.file} max_elevation_deg" + ("" if limit is not None else " (not set)"),
            ),
        )
        value = None
        if weight is not None:
            value = float((weight if mask is None else weight[mask]).sum())
        return Quantity("active seconds", value, "s", "this step"), inputs


def _active_step(ctx: _Ctx, mask: np.ndarray | None) -> Step:
    q, inputs = ctx.active_seconds(mask)
    return Step(
        "Seconds the link is active",
        inputs,
        q,
        logic="Every sample stands for the seconds of its part of the pass in which the link is "
        "used: a mode listed in 'active_modes' and an elevation not above the tracking limit; "
        "the rest of the sample counts as zero.",
    )


def _rate_step(ctx: _Ctx, mask: np.ndarray | None, ref: Quantity) -> Step:
    s = ctx.s
    selected = s.selected_rate_bps
    chain = ctx.chain(None)
    need = chain.required_margin()
    rates = ", ".join(f"{r / 1000.0:g}" for r in s.rates_bps)
    best = None
    closing = None
    if selected is not None:
        chosen = selected if mask is None else selected[mask]
        best = float(chosen.max()) if len(chosen) else 0.0
        closing = float(np.count_nonzero(chosen > 0.0))
    return Step(
        "Data rate chosen at each active sample",
        (
            Quantity("listed data rates", rates, "kbit/s", f"{ctx.file} data_rates_bps"),
            need,
            Quantity("samples with a rate that closes", closing, "", "pass series"),
            ref,
        ),
        Quantity("highest chosen rate", best, "bit/s", "this step"),
        "LNK-MARGIN",
        "At each active sample the highest listed rate whose margin is at least the required "
        "margin; zero when none closes or the link is not active. The margin of a sample is "
        "explained in the cell 'Lowest margin' of the pass table.",
    )


def _volume_steps(ctx: _Ctx, mask: np.ndarray | None) -> tuple[list[Step], Quantity]:
    s = ctx.s
    selected = s.selected_rate_bps
    if selected is None or s.weight_s is None:
        q = Quantity("data volume", None, "bit")
        return [
            Step(
                "Data volume",
                (),
                q,
                logic="n/a: the link budget at the samples is n/a (an input is a placeholder or "
                "missing, see Problems).",
            )
        ], q
    active = _active_step(ctx, mask)
    rate = _rate_step(ctx, mask, active.result)
    volume = data_volume_bits(
        selected if mask is None else selected[mask],
        s.weight_s if mask is None else s.weight_s[mask],
    )
    step = Step(
        "Bits sent",
        (
            replace(rate.result, origin="previous step"),
            replace(active.result, origin="previous step"),
        ),
        Quantity("data volume", volume, "bit", "this step"),
        "LNK-VOLUME",
        "Sum over the samples of the chosen rate x the seconds the sample stands for (samples "
        "differ in rate, so the figures above are the largest rate and the total seconds).",
    )
    return [active, rate, step], step.result


def _megabit(volume: Quantity, name: str) -> Step:
    value = None if volume.value is None else float(volume.value) / 1e6
    return Step(
        "In megabits",
        (volume,),
        Quantity(name, value, "Mbit", "this step"),
        logic="Bits divided by 10^6.",
    )


# ---- the cells ----------------------------------------------------------------------------------
def _volume_cell(ctx: _Ctx, column: str) -> Cell:
    s = ctx.s
    if column == "Link":
        return _read(Quantity("link id", s.link_id, "", ctx.file))
    if column == "Station":
        return _read(Quantity("peer station", s.site, "", f"{ctx.file} peer"))
    if column == "Passes":
        q = Quantity("passes", float(len(s.passes)), "", "this step")
        return [
            Step(
                "Count the passes of the station",
                (
                    Quantity("station", s.site, "", f"{ctx.file} peer"),
                    Quantity(
                        "passes found in the scenario",
                        float(len(s.passes)),
                        "",
                        f"scenarios/{ctx.run.scenario_id}.yaml (orbit, station, minimum elevation)",
                    ),
                ),
                q,
                logic="The passes of the peer station above its minimum elevation, found by the "
                "environment of the scenario.",
            )
        ], q
    steps, volume = _volume_steps(ctx, None)
    if column == "Scenario total (Mbit)":
        steps.append(_megabit(volume, "scenario total"))
        return steps, steps[-1].result
    if column in ("Per day (Mbit)", "Per day (MByte)"):
        duration = ctx.run.env.grid.duration_s
        value = None
        if volume.value is not None and duration >= DAY_S * (1.0 - 1e-9):
            value = float(volume.value) / (duration / DAY_S)
        per_day = Step(
            "Scaled to one day",
            (
                replace(volume, origin="previous step"),
                Quantity(
                    "duration of the scenario",
                    duration,
                    "s",
                    f"scenarios/{ctx.run.scenario_id}.yaml",
                ),
                Quantity("seconds in a day", DAY_S, "s", "fixed"),
            ),
            Quantity("data volume per day", value, "bit", "this step"),
            logic="Volume / (duration / 86 400 s). n/a for a scenario shorter than a day: scaling "
            "it would repeat its passes.",
        )
        steps.append(per_day)
        if column == "Per day (Mbit)":
            steps.append(_megabit(per_day.result, "data volume per day"))
        else:
            q = Quantity(
                "data volume per day",
                None if value is None else value / 8e6,
                "MByte",
                "this step",
            )
            steps.append(
                Step(
                    "In megabytes",
                    (per_day.result,),
                    q,
                    logic="Bits divided by 8 x 10^6.",
                )
            )
        return steps, steps[-1].result
    raise ExplainError("This column is not explained.")


def _pass_cell(ctx: _Ctx, number: int, column: str) -> Cell:
    s = ctx.s
    p = s.passes[number - 1]
    mask = s.pass_index == (p.index - 1)
    where = f"environment of scenarios/{ctx.run.scenario_id}.yaml, pass {p.index} of {s.site}"
    if column == "Pass":
        return _read(Quantity("pass number", str(p.index), "", where))
    if column == "AOS (T+)":
        return _read(Quantity("acquisition of signal", format_offset(p.aos_s), "", where))
    if column == "AOS (UTC)":
        return _read(Quantity("acquisition of signal", ctx.utc(p.aos_s), "", where))
    if column == "Max elevation (deg)":
        return _read(Quantity("highest elevation of the pass", p.max_elevation_deg, "deg", where))
    if column == "Duration (s)":
        q = Quantity("duration", p.los_s - p.aos_s, "s", "this step")
        return [
            Step(
                "Length of the pass",
                (
                    Quantity("acquisition of signal", p.aos_s, "s", where),
                    Quantity("loss of signal", p.los_s, "s", where),
                ),
                q,
                logic="Loss of signal - acquisition of signal.",
            )
        ], q
    selected = s.selected_rate_bps
    if column == "Usable (s)":
        if selected is None or s.weight_s is None:
            q = Quantity("usable time", None, "s")
            return [Step("Usable time", (), q, logic="n/a: the link budget is n/a.")], q
        closing = mask & (selected > 0)
        q = Quantity("usable time", float(s.weight_s[closing].sum()), "s", "this step")
        return [
            Step(
                "Seconds with a rate that closes",
                (
                    Quantity("samples in the pass", float(mask.sum()), "", "pass series"),
                    Quantity(
                        "samples with a rate that closes", float(closing.sum()), "", "pass series"
                    ),
                ),
                q,
                logic="Sum of the seconds the samples stand for, over the samples of the pass at "
                "which some listed rate closes while the link is active.",
            )
        ], q
    if column == "Volume (Mbit)":
        steps, volume = _volume_steps(ctx, mask)
        steps.append(_megabit(volume, "volume of the pass"))
        return steps, steps[-1].result
    if column == "Lowest margin (dB)":
        margins = s.margin_db
        active = mask & s.active
        if margins is None or not bool(active.any()):
            q = Quantity("lowest margin", None, "dB")
            return [
                Step(
                    "Lowest margin of the pass",
                    (),
                    q,
                    logic="n/a: the link budget is n/a, or the link is not active in this pass.",
                )
            ], q
        candidates = np.nonzero(active)[0]
        i = int(candidates[np.argmin(margins[candidates, 0])])
        chain = ctx.chain(i)
        bps = s.rates_bps[0]
        margin = chain.margin(bps)
        steps = list(chain.steps)
        final = Quantity("lowest margin", float(margins[i, 0]), "dB", "this step")
        steps.append(
            Step(
                "Lowest margin of the pass",
                (
                    replace(margin, origin="previous step"),
                    Quantity("active samples in the pass", float(active.sum()), "", "pass series"),
                ),
                final,
                logic=f"The margin at the lowest listed rate ({bps / 1000.0:g} kbit/s) is worked "
                "out "
                "at every active sample of the pass; the smallest is shown, with the whole link "
                "budget at that sample above.",
            )
        )
        return steps, final
    raise ExplainError("This column is not explained.")


# ---- entry point --------------------------------------------------------------------------------
def explain_linkpass(
    project: Project,
    table_id: str,
    key: Sequence[str],
    column: str,
    result: LinkSeriesResult,
) -> Explanation:
    parts = table_id.split(":")
    kind = parts[1] if len(parts) > 1 else ""
    if not key:
        raise ExplainError("Name the row.")
    address = (table_id, tuple(key), column)
    if kind == "volume":
        s = next((x for x in result.series if x.link_id == key[0]), None)
        if s is None:
            raise ExplainError("There is no such link in this table.")
        steps, final = _volume_cell(_Ctx(project, result, s), column)
        title = f"Data volume per link / {key[0]} / {column}"
    elif kind == "passes":
        link_id = parts[2] if len(parts) > 2 else ""
        s = next((x for x in result.series if x.link_id == link_id), None)
        if s is None:
            raise ExplainError("There is no such link in this scenario.")
        if not key[0].isdigit() or not 1 <= int(key[0]) <= len(s.passes):
            raise ExplainError("There is no such pass in this table.")
        steps, final = _pass_cell(_Ctx(project, result, s), int(key[0]), column)
        title = f"Passes of link {link_id} over {s.site} / pass {key[0]} / {column}"
    else:
        raise ExplainError("This table cannot be explained.")
    linked = link_steps(tuple(steps))
    return Explanation(
        address, title, replace(final, origin=""), linked, equations=equations_used(linked)
    )


__all__ = ["explain_linkpass", "linkpass_table_ids"]
