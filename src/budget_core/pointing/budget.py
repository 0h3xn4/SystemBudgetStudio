# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""The pointing and slew budget (2.2.0, D-234).

A slew is a rest-to-rest rotation about one body axis of angle theta with the actuators' torque T
as the only limit: accelerate at alpha = T / I for half the way, decelerate for the other half,

    t = 2 sqrt(theta / alpha)          peak rate = sqrt(theta alpha)

and, when the spacecraft may not turn faster than w_max (the actuators, the sensors), hold that
rate in between:

    t = theta / w_max + w_max / alpha

The peak momentum the actuators must store is h = I w_peak. The slew is powered at the actuator
set's slew power for the time of the manoeuvre; settling is added to the time of the slew, not to
its energy. The inertia is the one given for the slew or, without it, the diagonal entry of the
mass budget's inertia about the centre of gravity for that axis (a principal axis is assumed).

A placeholder or missing number gives `None` (n/a), never zero.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from budget_core.assumptions import Assumption, incomplete, missing_from
from budget_core.equation_binding import computes
from budget_core.mass.static_mass import static_mass_budget
from budget_core.model import Project, Sourced
from budget_core.problems import Problem, Severity

FILE = "config/pointing.yaml"


@dataclass(frozen=True)
class ModeRow:
    mode_id: str
    name: str
    reference: str
    accuracy_deg: float | None
    actuator: str
    hold_power_w: float | None


@dataclass(frozen=True)
class SlewRow:
    name: str
    from_mode: str
    to_mode: str
    axis: str
    angle_deg: float | None
    inertia_kgm2: float | None
    inertia_source: str
    acceleration_deg_s2: float | None
    slew_time_s: float | None
    total_time_s: float | None  # with the settling time
    peak_rate_deg_s: float | None
    rate_limited: bool
    peak_momentum_nms: float | None
    momentum_margin_nms: float | None  # capacity - peak
    energy_wh: float | None
    per_day: int
    energy_per_day_wh: float | None
    time_per_day_s: float | None


@dataclass(frozen=True)
class PointingResult:
    modes: tuple[ModeRow, ...]
    slews: tuple[SlewRow, ...]
    total_slew_time_per_day_s: float | None
    total_energy_per_day_wh: float | None
    assumptions: tuple[Assumption, ...]
    problems: tuple[Problem, ...]


def _value(item: Sourced | None) -> float | None:
    return None if item is None or item.is_placeholder else item.value


@computes("POINT-SLEW")
def slew_profile(
    angle_rad: float, torque_nm: float, inertia_kgm2: float, max_rate_rad_s: float | None
) -> tuple[float, float]:
    """POINT-SLEW: (time, peak rate) of a rest-to-rest slew, triangular in rate, or trapezoidal
    when the peak would pass `max_rate_rad_s`."""
    alpha = torque_nm / inertia_kgm2
    peak = math.sqrt(angle_rad * alpha)
    if max_rate_rad_s is None or peak <= max_rate_rad_s:
        return 2.0 * math.sqrt(angle_rad / alpha), peak
    return angle_rad / max_rate_rad_s + max_rate_rad_s / alpha, max_rate_rad_s


@computes("POINT-MOMENTUM")
def peak_momentum_nms(inertia_kgm2: float, peak_rate_rad_s: float) -> float:
    """POINT-MOMENTUM: the angular momentum of the spacecraft at the peak rate, I w."""
    return inertia_kgm2 * peak_rate_rad_s


@computes("POINT-ENERGY")
def slew_energy_wh(power_w: float, slew_time_s: float) -> float:
    """POINT-ENERGY: the electrical energy of a slew, P t / 3600 in watt-hours."""
    return power_w * slew_time_s / 3600.0


def pointing_budget(project: Project) -> PointingResult | None:
    """The budget, or None when the project has no `config/pointing.yaml`."""
    config = project.config.pointing
    if config is None:
        return None
    assumptions: list[Assumption] = []
    problems: list[Problem] = []

    def note(name: str, item: Sourced | None, unit: str, path: str, what: str) -> None:
        if item is None:
            assumptions.append(Assumption(name, None, unit, "missing", FILE, path, True))
            where = missing_from(FILE, True)
            problems.append(incomplete(f"{what} is missing {where}.", FILE, path))
            return
        assumptions.append(
            Assumption(
                name, item.value, unit, item.source, FILE, path, item.is_placeholder, item.status
            )
        )
        if item.is_placeholder:
            problems.append(incomplete(f"{what} is a placeholder.", FILE, path))

    for aid, actuator in config.actuators.items():
        note(
            f"Maximum torque, {actuator.name}",
            actuator.max_torque_nm,
            "N m",
            f"actuators.{aid}.max_torque_nm",
            "The maximum torque",
        )
        for field, label, unit in (
            ("max_rate_deg_s", "Maximum slew rate", "deg/s"),
            ("momentum_capacity_nms", "Momentum capacity", "N m s"),
            ("slew_power_w", "Slew power", "W"),
        ):
            item = getattr(actuator, field)
            if item is not None:
                note(
                    f"{label}, {actuator.name}",
                    item,
                    unit,
                    f"actuators.{aid}.{field}",
                    f"The {label.lower()}",
                )

    mode_rows = []
    for mid, mode in config.modes.items():
        if mode.accuracy_deg is not None:
            note(
                f"Pointing accuracy, {mode.name}",
                mode.accuracy_deg,
                "deg",
                f"modes.{mid}.accuracy_deg",
                "The pointing accuracy",
            )
        if mode.hold_power_w is not None:
            note(
                f"Holding power, {mode.name}",
                mode.hold_power_w,
                "W",
                f"modes.{mid}.hold_power_w",
                "The holding power",
            )
        mode_rows.append(
            ModeRow(
                mid,
                mode.name,
                mode.reference,
                _value(mode.accuracy_deg),
                mode.actuator,
                _value(mode.hold_power_w),
            )
        )

    inertia_table = _mass_inertia(project, config.mass_phase)
    slews = []
    for index, s in enumerate(config.slews):
        note(f"Angle, {s.name}", s.angle_deg, "deg", f"slews[{index}].angle_deg", "The slew angle")
        if s.settle_s is not None:
            note(
                f"Settling time, {s.name}",
                s.settle_s,
                "s",
                f"slews[{index}].settle_s",
                "The settling time",
            )
        act = config.actuators.get(s.actuator)
        torque = _value(act.max_torque_nm) if act else None
        rate_limit = _value(act.max_rate_deg_s) if act else None
        capacity = _value(act.momentum_capacity_nms) if act else None
        power = _value(act.slew_power_w) if act else None
        angle = _value(s.angle_deg)

        if s.inertia_kgm2 is not None:
            note(
                f"Inertia, {s.name}",
                s.inertia_kgm2,
                "kg m2",
                f"slews[{index}].inertia_kgm2",
                "The inertia",
            )
            inertia = _value(s.inertia_kgm2)
            source = s.inertia_kgm2.source
        else:
            inertia = inertia_table.get(s.axis)
            source = "mass budget"
            if inertia is None:
                assumptions.append(
                    Assumption(
                        f"Inertia, {s.name}",
                        None,
                        "kg m2",
                        "mass budget (not available)",
                        FILE,
                        f"slews[{index}].inertia_kgm2",
                        True,
                    )
                )
                problems.append(
                    incomplete(
                        "The inertia cannot be taken from the mass budget (no centre of gravity).",
                        FILE,
                        f"slews[{index}].inertia_kgm2",
                    )
                )
            else:
                assumptions.append(
                    Assumption(
                        f"Inertia about {s.axis}, {s.name} (mass budget)",
                        inertia,
                        "kg m2",
                        "mass budget",
                        FILE,
                        "",
                        False,
                    )
                )

        time = peak_rate = None
        limited = False
        if angle is not None and torque is not None and inertia is not None and inertia > 0.0:
            limit_rad = None if rate_limit is None else math.radians(rate_limit)
            time, peak_rate_rad = slew_profile(math.radians(angle), torque, inertia, limit_rad)
            peak_rate = math.degrees(peak_rate_rad)
            limited = limit_rad is not None and peak_rate_rad >= limit_rad - 1e-15
        momentum = (
            peak_momentum_nms(inertia, math.radians(peak_rate))
            if inertia is not None and peak_rate is not None
            else None
        )
        margin = None if capacity is None or momentum is None else capacity - momentum
        if margin is not None and margin < 0.0:
            problems.append(
                Problem(
                    Severity.WARNING,
                    "POINTING_MOMENTUM_EXCEEDED",
                    "A slew needs more angular momentum than the actuators can store.",
                    file=FILE,
                    path=f"slews[{index}]",
                    hint="Lower the rate limit, slew a smaller angle, or use actuators that "
                    "store more momentum.",
                    actual=momentum,
                    limit=capacity,
                    unit="N m s",
                )
            )
        settle = _value(s.settle_s) if s.settle_s is not None else 0.0
        total = None if time is None or settle is None else time + settle
        energy = slew_energy_wh(power, time) if power is not None and time is not None else None
        slews.append(
            SlewRow(
                s.name,
                s.from_mode,
                s.to_mode,
                s.axis,
                angle,
                inertia,
                source,
                None
                if torque is None or inertia is None or inertia <= 0
                else math.degrees(torque / inertia),
                time,
                total,
                peak_rate,
                limited,
                momentum,
                margin,
                energy,
                s.per_day,
                None if energy is None else energy * s.per_day,
                None if total is None else total * s.per_day,
            )
        )

    times = [r.time_per_day_s for r in slews]
    energies = [r.energy_per_day_wh for r in slews]
    return PointingResult(
        tuple(mode_rows),
        tuple(slews),
        None if any(v is None for v in times) else math.fsum(v for v in times if v is not None),
        None
        if any(v is None for v in energies)
        else math.fsum(v for v in energies if v is not None),
        tuple(assumptions),
        tuple(problems),
    )


def _mass_inertia(project: Project, phase: str | None) -> dict[str, float]:
    """Diagonal inertia about the centre of gravity from the mass budget, by body axis (empty
    when the phase has no centre of gravity)."""
    mass = static_mass_budget(project)
    chosen = next((p for p in mass.phases if p.phase == phase), None) if phase else None
    chosen = chosen or (mass.phases[0] if mass.phases else None)
    if chosen is None or chosen.cog is None:
        return {}
    t = chosen.cog.inertia_cg
    return {"x": t.ixx, "y": t.iyy, "z": t.izz}
