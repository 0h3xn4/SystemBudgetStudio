# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""Explanations of the pointing and slew budget (tables of `reports/pointing_report.py`, D-255).

Table ids (`Table.explain_id`): `pointing:modes` and `pointing:slews`. A cell is named by the id,
the first column of its row (the mode or slew name) and the column header. The slew is computed
again with the functions of the solver (`slew_profile`, `peak_momentum_nms`, `slew_energy_wh`); the
inertia is the one the slew gives or the mass budget's, and the explanation says which. A test
compares every cell of the example with its explanation.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import replace

from budget_core.explain.helpers import Cell, apply, number, read, sourced
from budget_core.explain.power import ExplainError
from budget_core.explain.trace import Explanation, Quantity, Step, equations_used, link_steps
from budget_core.model import Project
from budget_core.pointing.budget import (
    FILE,
    PointingResult,
    SlewRow,
    peak_momentum_nms,
    slew_energy_wh,
    slew_profile,
)

MODES = "pointing:modes"
SLEWS = "pointing:slews"
TITLES = {MODES: "Pointing modes", SLEWS: "Slews"}


def pointing_table_ids(project: Project) -> list[tuple[str, str]]:
    """(table id, title) of the explainable pointing tables; none without a pointing file."""
    return [(table, TITLES[table]) for table in TITLES] if project.config.pointing else []


def _at(table: str, row: str, column: str) -> str:
    return f"table '{TITLES[table]}', row {row}, column {column} (explain it with {table})"


def _mode_cell(project: Project, result: PointingResult, key: Sequence[str], column: str) -> Cell:
    config = project.config.pointing
    assert config is not None
    row = next((m for m in result.modes if m.name == key[0]), None)
    if row is None:
        raise ExplainError("There is no such pointing mode in this table.")
    mode = config.modes[row.mode_id]
    base = f"modes.{row.mode_id}"
    if column == "Mode":
        return read(Quantity("name of the mode", mode.name, "", f"{FILE} {base}.name"))
    if column == "Reference":
        return read(
            Quantity("reference of the mode", mode.reference, "", f"{FILE} {base}.reference")
        )
    if column == "Accuracy requirement (deg)":
        return read(
            sourced("accuracy requirement", mode.accuracy_deg, "deg", FILE, f"{base}.accuracy_deg")
        )
    if column == "Actuators":
        return read(Quantity("actuators of the mode", mode.actuator, "", f"{FILE} {base}.actuator"))
    if column == "Holding power (W)":
        return read(sourced("holding power", mode.hold_power_w, "W", FILE, f"{base}.hold_power_w"))
    raise ExplainError("This column is not explained.")


class _Slew:
    """The inputs and the first steps of one slew, shared by the columns that follow from them."""

    def __init__(self, project: Project, row: SlewRow, index: int) -> None:
        config = project.config.pointing
        assert config is not None
        self.row = row
        self.s = config.slews[index]
        self.path = f"slews[{index}]"
        self.actuator = config.actuators.get(self.s.actuator)
        self.aid = f"actuators.{self.s.actuator}"
        name = row.name
        self.angle = sourced(
            f"angle of {name}", self.s.angle_deg, "deg", FILE, f"{self.path}.angle_deg"
        )
        self.torque = sourced(
            f"maximum torque of {self.s.actuator}",
            self.actuator.max_torque_nm if self.actuator else None,
            "N m",
            FILE,
            f"{self.aid}.max_torque_nm",
        )
        self.rate_limit = (
            sourced(
                f"rate limit of {self.s.actuator}",
                self.actuator.max_rate_deg_s,
                "deg/s",
                FILE,
                f"{self.aid}.max_rate_deg_s",
            )
            if self.actuator is not None and self.actuator.max_rate_deg_s is not None
            else None
        )
        if self.s.inertia_kgm2 is not None:
            self.inertia = sourced(
                f"inertia of {name}",
                self.s.inertia_kgm2,
                "kg m2",
                FILE,
                f"{self.path}.inertia_kgm2",
            )
        else:
            self.inertia = Quantity(
                f"inertia of {name}",
                row.inertia_kgm2,
                "kg m2",
                f"the mass budget: the diagonal inertia about the centre of gravity for axis "
                f"{self.s.axis}",
            )

    def profile_steps(self) -> tuple[list[Step], Quantity, Quantity]:
        """The steps to the slew time (s) and the peak rate (rad/s)."""
        steps = [
            apply(
                "Angle in radians",
                (self.angle,),
                math.radians,
                "angle",
                "rad",
                logic="Degrees to radians.",
            )
        ]
        angle_rad = steps[0].result
        limit_rad: Quantity | None = None
        if self.rate_limit is not None:
            steps.append(
                apply(
                    "Rate limit in radians per second",
                    (self.rate_limit,),
                    math.radians,
                    "rate limit",
                    "rad/s",
                    logic="Degrees to radians.",
                )
            )
            limit_rad = steps[-1].result
        inputs = [angle_rad, self.torque, self.inertia, *([limit_rad] if limit_rad else [])]
        values = [number(q) for q in inputs]
        known = all(v is not None for v in values)
        time: float | None = None
        peak: float | None = None
        if known and (number(self.inertia) or 0.0) > 0.0:
            limit_value = number(limit_rad) if limit_rad is not None else None
            time, peak = slew_profile(
                float(values[0] or 0.0),
                float(values[1] or 0.0),
                float(values[2] or 0.0),
                limit_value,
            )
        note = (
            "Rest-to-rest about one body axis: accelerate at torque / inertia for half the way and "
            "decelerate for the rest; when the peak rate would pass the rate limit, hold the "
            "limit in between."
        )
        if time is None:
            note += " An input is n/a (or the inertia is not above 0), so the result is n/a."
        profile = Step(
            "Slew time and peak rate",
            tuple(inputs),
            Quantity("slew time", time, "s", "this step"),
            "POINT-SLEW",
            note,
        )
        return [*steps, profile], profile.result, Quantity("peak rate", peak, "rad/s", "this step")


def _slew_cell(project: Project, result: PointingResult, key: Sequence[str], column: str) -> Cell:
    config = project.config.pointing
    assert config is not None
    index = next((i for i, r in enumerate(result.slews) if r.name == key[0]), None)
    if index is None:
        raise ExplainError("There is no such slew in this table.")
    row = result.slews[index]
    ctx = _Slew(project, row, index)
    s = ctx.s
    name = row.name
    simple = {
        "Slew": ("name of the slew", s.name, f"{FILE} {ctx.path}.name"),
        "From": ("pointing mode before", s.from_mode, f"{FILE} {ctx.path}.from_mode"),
        "To": ("pointing mode after", s.to_mode, f"{FILE} {ctx.path}.to_mode"),
        "Axis": ("axis of the slew", s.axis, f"{FILE} {ctx.path}.axis"),
    }
    if column in simple:
        label, value, origin = simple[column]
        return read(Quantity(label, value, "", origin))
    if column == "Angle (deg)":
        return read(ctx.angle)
    if column == "Inertia (kg m2)":
        return read(
            ctx.inertia,
            "Not computed: given for the slew."
            if s.inertia_kgm2 is not None
            else "Taken from the mass budget (diagonal entry about the centre of gravity for the "
            "axis; a principal axis is assumed).",
        )
    if column == "Per day":
        return read(Quantity("slews per day", float(s.per_day), "", f"{FILE} {ctx.path}.per_day"))

    steps, time, peak_rad = ctx.profile_steps()
    if column == "Slew time (s)":
        return steps, time
    peak_deg = apply(
        "Peak rate in degrees per second",
        (peak_rad,),
        math.degrees,
        "peak rate",
        "deg/s",
        logic="Radians to degrees.",
    )
    if column == "Peak rate (deg/s)":
        return [*steps, peak_deg], peak_deg.result
    if column == "With settling (s)":
        settle = (
            sourced(f"settling time of {name}", s.settle_s, "s", FILE, f"{ctx.path}.settle_s")
            if s.settle_s is not None
            else Quantity(f"settling time of {name}", 0.0, "s", "none given: no settling")
        )
        total = apply(
            "Slew time with the settling time",
            (time, settle),
            lambda t, st: t + st,
            f"slew time of {name} with settling",
            "s",
            logic="Settling is added to the time of the slew, not to its energy.",
        )
        return [*steps, total], total.result
    if column == "Rate limited":
        limit = number(ctx.rate_limit) if ctx.rate_limit is not None else None
        peak_value = number(peak_deg.result)
        limited = (
            limit is not None
            and peak_value is not None
            and math.radians(peak_value) >= math.radians(limit) - 1e-15
        )
        step = Step(
            "Is the rate limit reached?",
            (
                peak_deg.result,
                ctx.rate_limit or Quantity("rate limit", None, "deg/s", "none given"),
            ),
            Quantity("rate limited", "yes" if limited else "no", "", "this step"),
            logic="Yes when the peak rate reaches the rate limit of the actuators; no when there "
            "is no limit or the slew is too short to reach it.",
        )
        return [*steps, peak_deg, step], step.result
    if column in ("Peak momentum (N m s)", "Momentum margin (N m s)"):
        peak_radians = apply(
            "Peak rate in radians per second",
            (peak_deg.result,),
            math.radians,
            "peak rate",
            "rad/s",
            logic="Degrees to radians.",
        )
        momentum = apply(
            "Peak angular momentum",
            (ctx.inertia, peak_radians.result),
            peak_momentum_nms,
            "peak momentum",
            "N m s",
            "POINT-MOMENTUM",
        )
        if column == "Peak momentum (N m s)":
            return [*steps, peak_deg, peak_radians, momentum], momentum.result
        capacity = sourced(
            f"momentum capacity of {s.actuator}",
            ctx.actuator.momentum_capacity_nms if ctx.actuator else None,
            "N m s",
            FILE,
            f"{ctx.aid}.momentum_capacity_nms",
        )
        margin = apply(
            "Momentum margin",
            (capacity, momentum.result),
            lambda have, need: have - need,
            f"momentum margin of {name}",
            "N m s",
            logic="Capacity less the peak momentum; negative: the actuators cannot store it.",
        )
        return [*steps, peak_deg, peak_radians, momentum, margin], margin.result
    if column in ("Energy (Wh)", "Energy per day (Wh)"):
        power = sourced(
            f"slewing power of {s.actuator}",
            ctx.actuator.slew_power_w if ctx.actuator else None,
            "W",
            FILE,
            f"{ctx.aid}.slew_power_w",
        )
        energy = apply(
            "Electrical energy of one slew",
            (power, time),
            slew_energy_wh,
            f"energy of {name}",
            "Wh",
            "POINT-ENERGY",
            "The settling time is not powered.",
        )
        if column == "Energy (Wh)":
            return [*steps, energy], energy.result
        per_day = apply(
            "Energy per day",
            (
                energy.result,
                Quantity("slews per day", float(s.per_day), "", f"{FILE} {ctx.path}.per_day"),
            ),
            lambda one, count: one * count,
            f"energy per day of {name}",
            "Wh",
            logic="Energy of one slew x slews per day.",
        )
        return [*steps, energy, per_day], per_day.result
    raise ExplainError("This column is not explained.")


def explain_pointing(
    project: Project,
    table_id: str,
    key: Sequence[str],
    column: str,
    result: PointingResult,
) -> Explanation:
    if not key:
        raise ExplainError("Name the row.")
    if table_id == MODES:
        steps, final = _mode_cell(project, result, key, column)
    elif table_id == SLEWS:
        steps, final = _slew_cell(project, result, key, column)
    else:
        raise ExplainError("This table cannot be explained.")
    linked = link_steps(tuple(steps))
    return Explanation(
        (table_id, tuple(key), column),
        f"{TITLES[table_id]} / {key[0]} / {column}",
        replace(final, origin=""),
        linked,
        equations=equations_used(linked),
    )


__all__ = ["explain_pointing", "pointing_table_ids"]
