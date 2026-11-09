# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""The propulsion and delta-v budget (2.2.0, D-233).

The manoeuvres of `config/propulsion.yaml` are listed in mission order. The mass after the last
one is the dry mass; going backwards, the rocket equation gives the mass before each burn and so
the propellant it uses:

    m_before = m_after * exp(dv / (Isp * g0))      propellant = m_before - m_after

The first manoeuvre therefore starts from the initial (wet) mass. Per system: the propellant, the
burn time at a constant thrust (the mass flow is F / (Isp g0), so t = m_propellant * Isp * g0 / F),
and, for an electric system, the power drawn while thrusting and the energy. The propellant a
system uses is compared with what the mass budget loads in the expendable it names.

A placeholder or missing number gives `None` (n/a), never zero; a burn after an unknown one stays
computable (its mass is known), a burn before it is not.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from budget_core.assumptions import Assumption, incomplete, missing_from
from budget_core.environment.constants import STANDARD_GRAVITY
from budget_core.equation_binding import computes
from budget_core.mass.static_mass import static_mass_budget
from budget_core.model import Project, Sourced
from budget_core.problems import Problem

G0 = STANDARD_GRAVITY.value
FILE = "config/propulsion.yaml"


@dataclass(frozen=True)
class ManeuverRow:
    name: str
    system_id: str
    count: int
    delta_v_m_s: float | None  # of one burn, as given
    delta_v_total_m_s: float | None  # count x delta-v x (1 + margin)
    mass_before_kg: float | None
    mass_after_kg: float | None
    propellant_kg: float | None
    # the time the line's burns last together at the system's constant thrust, and the spacecraft
    # mode and the electrical power during them (2.3.0, for a scenario that places the manoeuvre)
    burn_time_s: float | None = None
    mode: str | None = None
    power_w: float | None = None


@dataclass(frozen=True)
class SystemRow:
    system_id: str
    name: str
    type: str
    isp_s: float | None
    propellant_kg: float | None
    burn_time_s: float | None
    power_w: float | None  # electric only
    energy_wh: float | None  # electric only
    loaded_kg: float | None  # in the expendable the system names
    margin_kg: float | None  # loaded - needed


@dataclass(frozen=True)
class PropulsionResult:
    dry_mass_kg: float | None
    initial_mass_kg: float | None
    total_delta_v_m_s: float | None
    total_propellant_kg: float | None
    delta_v_margin_ratio: float | None
    maneuvers: tuple[ManeuverRow, ...]
    systems: tuple[SystemRow, ...]
    assumptions: tuple[Assumption, ...]
    problems: tuple[Problem, ...]


def _value(item: Sourced | None) -> float | None:
    return None if item is None or item.is_placeholder else item.value


@computes("PROP-ROCKET")
def mass_before_burn_kg(mass_after_kg: float, delta_v_m_s: float, isp_s: float) -> float:
    """PROP-ROCKET: the mass before a burn that ends at `mass_after_kg`, m_after exp(dv /
    (Isp g0))."""
    return mass_after_kg * math.exp(delta_v_m_s / (isp_s * G0))


@computes("PROP-BURN")
def burn_time_s(propellant_kg: float, isp_s: float, thrust_n: float) -> float:
    """PROP-BURN: the time to use a propellant mass at a constant thrust, m Isp g0 / F."""
    return propellant_kg * isp_s * G0 / thrust_n


@computes("PROP-ENERGY")
def thrusting_energy_wh(power_w: float, burn_time_seconds: float) -> float:
    """PROP-ENERGY: the electrical energy of a burn, P t, in watt-hours."""
    return power_w * burn_time_seconds / 3600.0


def propulsion_budget(project: Project) -> PropulsionResult | None:
    """The budget, or None when the project has no `config/propulsion.yaml`."""
    config = project.config.propulsion
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

    margin_item = config.delta_v_margin_ratio
    margin = 0.0
    if margin_item is not None:
        note("Delta-v margin", margin_item, "ratio", "delta_v_margin_ratio", "The delta-v margin")
        value = _value(margin_item)
        margin = value if value is not None else 0.0
    margin_known = margin_item is None or _value(margin_item) is not None

    systems = config.systems
    isp: dict[str, float | None] = {}
    for sid, system in systems.items():
        note(
            f"Specific impulse, {system.name}",
            system.isp_s,
            "s",
            f"systems.{sid}.isp_s",
            "The specific impulse",
        )
        isp[sid] = _value(system.isp_s)
        if system.thrust_n is not None:
            note(
                f"Thrust, {system.name}",
                system.thrust_n,
                "N",
                f"systems.{sid}.thrust_n",
                "The thrust",
            )
        if system.type == "electric":
            note(
                f"Thrusting power, {system.name}",
                system.power_w,
                "W",
                f"systems.{sid}.power_w",
                "The thrusting power",
            )

    # the dry mass
    dry: float | None
    if config.dry_mass_kg is not None:
        note("Dry mass", config.dry_mass_kg, "kg", "dry_mass_kg", "The dry mass")
        dry = _value(config.dry_mass_kg)
    else:
        dry = _dry_mass_from_mass_budget(project, assumptions, problems)

    # manoeuvres, worked backwards
    rows: list[ManeuverRow] = []
    after: float | None = dry
    for index in range(len(config.maneuvers) - 1, -1, -1):
        m = config.maneuvers[index]
        note(
            f"Delta-v, {m.name}",
            m.delta_v_m_s,
            "m/s",
            f"maneuvers[{index}].delta_v_m_s",
            "The delta-v",
        )
        dv_each = _value(m.delta_v_m_s)
        dv_total = None if dv_each is None or not margin_known else dv_each * m.count * (1 + margin)
        i = isp.get(m.system)
        before: float | None = None
        if after is not None and dv_total is not None and i is not None:
            before = mass_before_burn_kg(after, dv_total, i)
        used = None if before is None or after is None else before - after
        engine = systems.get(m.system)
        thrust = _value(engine.thrust_n) if engine else None
        burn = (
            burn_time_s(used, i, thrust)
            if used is not None and i is not None and thrust is not None
            else None
        )
        power: float | None = None
        if engine is not None:
            power = _value(engine.power_w) if engine.type == "electric" else 0.0
        rows.append(
            ManeuverRow(
                m.name,
                m.system,
                m.count,
                dv_each,
                dv_total,
                before,
                after,
                used,
                burn,
                m.mode,
                power,
            )
        )
        after = before  # unknown stays unknown for every earlier burn
    rows.reverse()

    prop_by_system: dict[str, float | None] = {}
    for sid in systems:
        burns = [r for r in rows if r.system_id == sid]
        values = [r.propellant_kg for r in burns]
        prop_by_system[sid] = (
            None
            if any(v is None for v in values)
            else math.fsum(v for v in values if v is not None)
        )
    system_rows = []
    for sid, system in systems.items():
        needed = prop_by_system[sid]
        thrust = _value(system.thrust_n)
        power = _value(system.power_w) if system.type == "electric" else None
        system_isp = isp[sid]
        time = (
            burn_time_s(needed, system_isp, thrust)
            if needed is not None and system_isp is not None and thrust is not None
            else None
        )
        energy = (
            thrusting_energy_wh(power, time) if power is not None and time is not None else None
        )
        loaded = _loaded_kg(project, system.propellant)
        system_rows.append(
            SystemRow(
                sid,
                system.name,
                system.type,
                isp[sid],
                needed,
                time,
                power,
                energy,
                loaded,
                None if loaded is None or needed is None else loaded - needed,
            )
        )
    deltas = [r.delta_v_total_m_s for r in rows]
    total_dv = None if any(v is None for v in deltas) else math.fsum(v for v in deltas if v)
    props = [r.propellant_kg for r in rows]
    total_prop = None if any(v is None for v in props) else math.fsum(v for v in props if v)
    initial = rows[0].mass_before_kg if rows else dry
    return PropulsionResult(
        dry,
        initial,
        total_dv,
        total_prop,
        margin if margin_item is not None and margin_known else None,
        tuple(rows),
        tuple(system_rows),
        tuple(assumptions),
        tuple(problems),
    )


def _loaded_kg(project: Project, expendable_id: str | None) -> float | None:
    if expendable_id is None or expendable_id not in project.expendables:
        return None
    masses = project.expendables[expendable_id].masses_kg
    return max(masses.values()) if masses else None


def _dry_mass_from_mass_budget(
    project: Project, assumptions: list[Assumption], problems: list[Problem]
) -> float | None:
    """The first phase's nominal total less the propellant the systems load in that phase."""
    config = project.config.propulsion
    assert config is not None
    mass = static_mass_budget(project)
    if not mass.phases or mass.phases[0].total_kg is None:
        assumptions.append(
            Assumption("Dry mass", None, "kg", "mass budget (not available)", FILE, "", True)
        )
        problems.append(
            incomplete("The dry mass cannot be taken from the mass budget (no total).", FILE, "")
        )
        return None
    first = mass.phases[0]
    ids = sorted({s.propellant for s in config.systems.values() if s.propellant})
    loaded = math.fsum(
        project.expendables[e].masses_kg.get(first.phase, 0.0)
        for e in ids
        if e in project.expendables
    )
    dry = first.total_kg - loaded
    assumptions.append(
        Assumption(
            f"Dry mass (mass budget, phase {first.phase}, less the propellant)",
            dry,
            "kg",
            "mass budget",
            FILE,
            "",
            False,
        )
    )
    return dry
