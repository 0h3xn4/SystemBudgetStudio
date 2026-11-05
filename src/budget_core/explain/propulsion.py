"""Explanations of the propulsion and delta-v budget (tables of `reports/propulsion_report.py`,
D-255).

Table ids (`Table.explain_id`): `propulsion:summary`, `propulsion:systems` and
`propulsion:maneuvers`. A cell is named by the id, the first column of its row and the column
header. Every cell is computed again with the functions the solver calls (`mass_before_burn_kg`,
`burn_time_s`, `thrusting_energy_wh`), so the explanation agrees with the table by construction; a
test compares every cell of the example with its explanation. The manoeuvres are worked backwards:
the mass after the last burn is the dry mass, and the mass before a burn is the mass after the
next. A value that is n/a because an input is a placeholder says which input it was.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from budget_core.explain.helpers import Cell, apply, read, sourced, total
from budget_core.explain.power import ExplainError
from budget_core.explain.trace import Explanation, Quantity, Step, equations_used, link_steps
from budget_core.model import Project
from budget_core.propulsion.budget import (
    FILE,
    ManeuverRow,
    PropulsionResult,
    SystemRow,
    burn_time_s,
    mass_before_burn_kg,
    thrusting_energy_wh,
)

SUMMARY = "propulsion:summary"
SYSTEMS = "propulsion:systems"
MANEUVERS = "propulsion:maneuvers"
TITLES = {
    SUMMARY: "Propulsion budget",
    SYSTEMS: "Propellant, burn time and electric power by system",
    MANEUVERS: "Manoeuvres in mission order",
}


def propulsion_table_ids(project: Project) -> list[tuple[str, str]]:
    """(table id, title) of the explainable propulsion tables; none without a propulsion file."""
    return [(table, TITLES[table]) for table in TITLES] if project.config.propulsion else []


def _at(table: str, row: str, column: str) -> str:
    return f"table '{TITLES[table]}', row {row}, column {column} (explain it with {table})"


def _maneuver_cell(
    project: Project, result: PropulsionResult, key: Sequence[str], column: str
) -> Cell:
    config = project.config.propulsion
    assert config is not None
    index = next((i for i, m in enumerate(config.maneuvers) if m.name == key[0]), None)
    if index is None:
        raise ExplainError("There is no such manoeuvre in this table.")
    m, row = config.maneuvers[index], result.maneuvers[index]
    path = f"maneuvers[{index}]"
    system = config.systems.get(m.system)
    isp = sourced(
        f"specific impulse of {m.system}",
        system.isp_s if system else None,
        "s",
        FILE,
        f"systems.{m.system}.isp_s",
    )
    if column == "Manoeuvre":
        return read(Quantity("name of the manoeuvre", m.name, "", f"{FILE} {path}.name"))
    if column == "System":
        return read(Quantity("system of the manoeuvre", m.system, "", f"{FILE} {path}.system"))
    if column == "Burns":
        return read(Quantity("burns", float(m.count), "", f"{FILE} {path}.count"))
    if column == "Delta-v with margin (m/s)":
        margin_item = config.delta_v_margin_ratio
        margin = (
            sourced("delta-v margin", margin_item, "ratio", FILE, "delta_v_margin_ratio")
            if margin_item is not None
            else Quantity("delta-v margin", 0.0, "ratio", "none given: no margin is added")
        )
        step = apply(
            "Delta-v of the line with the margin",
            (
                sourced(
                    f"delta-v of one burn, {m.name}",
                    m.delta_v_m_s,
                    "m/s",
                    FILE,
                    f"{path}.delta_v_m_s",
                ),
                Quantity("burns", float(m.count), "", f"{FILE} {path}.count"),
                margin,
            ),
            lambda dv, burns, mar: dv * burns * (1 + mar),
            f"delta-v of {m.name}",
            "m/s",
            logic="Delta-v of one burn x burns x (1 + margin).",
        )
        return [step], step.result
    if column == "Mass after (kg)":
        if index == len(config.maneuvers) - 1:
            origin = "the dry mass: " + _at(SUMMARY, "Dry mass", "Value")
        else:
            nxt = config.maneuvers[index + 1].name
            origin = "the mass before the next burn: " + _at(MANEUVERS, nxt, "Mass before (kg)")
        return read(
            Quantity(f"mass after {m.name}", row.mass_after_kg, "kg", origin),
            "Worked backwards: the mass after a burn is the mass before the next one (the dry "
            "mass after the last).",
        )
    after = Quantity(
        f"mass after {m.name}", row.mass_after_kg, "kg", _at(MANEUVERS, m.name, "Mass after (kg)")
    )
    if column == "Mass before (kg)":
        step = apply(
            "Mass before the burn",
            (
                after,
                Quantity(
                    f"delta-v of {m.name}",
                    row.delta_v_total_m_s,
                    "m/s",
                    _at(MANEUVERS, m.name, "Delta-v with margin (m/s)"),
                ),
                isp,
            ),
            mass_before_burn_kg,
            f"mass before {m.name}",
            "kg",
            "PROP-ROCKET",
            "m_before = m_after exp(dv / (Isp g0)).",
        )
        return [step], step.result
    if column == "Propellant (kg)":
        step = apply(
            "Propellant of the burns",
            (
                Quantity(
                    f"mass before {m.name}",
                    row.mass_before_kg,
                    "kg",
                    _at(MANEUVERS, m.name, "Mass before (kg)"),
                ),
                after,
            ),
            lambda before, after_: before - after_,
            f"propellant of {m.name}",
            "kg",
            logic="Mass before less mass after.",
        )
        return [step], step.result
    raise ExplainError("This column is not explained.")


def _system_cell(
    project: Project, result: PropulsionResult, key: Sequence[str], column: str
) -> Cell:
    config = project.config.propulsion
    assert config is not None
    srow: SystemRow | None = next((s for s in result.systems if s.name == key[0]), None)
    if srow is None:
        raise ExplainError("There is no such system in this table.")
    sid = srow.system_id
    system = config.systems[sid]
    base = f"systems.{sid}"
    isp = sourced(f"specific impulse of {sid}", system.isp_s, "s", FILE, f"{base}.isp_s")
    burns: list[ManeuverRow] = [r for r in result.maneuvers if r.system_id == sid]
    needed = Quantity(
        f"propellant of {sid}", srow.propellant_kg, "kg", _at(SYSTEMS, srow.name, "Propellant (kg)")
    )
    if column == "System":
        return read(Quantity("name of the system", system.name, "", f"{FILE} {base}.name"))
    if column == "Type":
        return read(Quantity("type of the system", system.type, "", f"{FILE} {base}.type"))
    if column == "Isp (s)":
        return read(isp)
    if column == "Propellant (kg)":
        members = [
            Quantity(
                f"propellant of {b.name}",
                b.propellant_kg,
                "kg",
                _at(MANEUVERS, b.name, "Propellant (kg)"),
            )
            for b in burns
        ]
        step = total(f"Propellant of the burns of {sid}", members, f"propellant of {sid}", "kg")
        return [step], step.result
    if column == "Loaded (kg)":
        expendable = project.expendables.get(system.propellant or "")
        if expendable is None or not expendable.masses_kg:
            step = Step(
                "Propellant loaded",
                (),
                Quantity(f"loaded propellant of {sid}", None, "kg", "this step"),
                logic="The system names no expendable with a mass in the mass budget, so the "
                "loaded propellant is n/a.",
            )
            return [step], step.result
        members = [
            Quantity(
                f"mass in phase {phase}",
                float(mass),
                "kg",
                f"expendables/{system.propellant}.yaml masses_kg.{phase}",
            )
            for phase, mass in expendable.masses_kg.items()
        ]
        step = apply(
            "Largest mass of the expendable",
            members,
            lambda *values: max(values),
            f"loaded propellant of {sid}",
            "kg",
            logic="The expendable the system names, in the phase in which it holds the most.",
        )
        return [step], step.result
    loaded = Quantity(
        f"loaded propellant of {sid}", srow.loaded_kg, "kg", _at(SYSTEMS, srow.name, "Loaded (kg)")
    )
    if column == "Margin (kg)":
        step = apply(
            "Margin of the propellant",
            (loaded, needed),
            lambda have, need: have - need,
            f"propellant margin of {sid}",
            "kg",
            logic="Loaded less needed; negative: not enough propellant.",
        )
        return [step], step.result
    thrust = sourced(f"thrust of {sid}", system.thrust_n, "N", FILE, f"{base}.thrust_n")
    if column in ("Burn time (h)", "Energy (Wh)"):
        seconds = apply(
            "Burn time at a constant thrust",
            (needed, isp, thrust),
            burn_time_s,
            f"burn time of {sid}",
            "s",
            "PROP-BURN",
            "t = m Isp g0 / F.",
        )
        if column == "Burn time (h)":
            hours = apply(
                "Burn time in hours",
                (seconds.result,),
                lambda s: s / 3600.0,
                f"burn time of {sid}",
                "h",
                logic="Seconds divided by 3600.",
            )
            return [seconds, hours], hours.result
        power = (
            sourced(f"thrusting power of {sid}", system.power_w, "W", FILE, f"{base}.power_w")
            if system.type == "electric"
            else Quantity(f"thrusting power of {sid}", None, "W", "only an electric system has one")
        )
        energy = apply(
            "Electrical energy of the burns",
            (power, seconds.result),
            thrusting_energy_wh,
            f"energy of {sid}",
            "Wh",
            "PROP-ENERGY",
            "E = P t / 3600; only an electric system has a thrusting power.",
        )
        return [seconds, energy], energy.result
    if column == "Power (W)":
        if system.type != "electric":
            return read(
                Quantity(f"thrusting power of {sid}", None, "W", "only an electric system has one"),
                "A chemical system draws no electrical power while thrusting: n/a.",
            )
        return read(
            sourced(f"thrusting power of {sid}", system.power_w, "W", FILE, f"{base}.power_w")
        )
    raise ExplainError("This column is not explained.")


def _summary_cell(
    project: Project, result: PropulsionResult, key: Sequence[str], column: str
) -> Cell:
    config = project.config.propulsion
    assert config is not None
    label = key[0]
    if column == "Quantity":
        return read(Quantity("row label", label, "", "fixed by the table"), "Names the row.")
    if column == "Unit":
        units = {
            "Dry mass": "kg",
            "Delta-v margin applied": "%",
            "Total delta-v": "m/s",
            "Total propellant": "kg",
        }
        unit = "kg" if label.startswith("Initial mass") else units.get(label)
        if unit is None:
            raise ExplainError("There is no such row in this table.")
        return read(Quantity("unit", unit, "", "fixed by the table"), "Names the unit of the row.")
    if column != "Value":
        raise ExplainError("This column is not explained.")
    if label == "Dry mass":
        if config.dry_mass_kg is not None:
            return read(sourced("dry mass", config.dry_mass_kg, "kg", FILE, "dry_mass_kg"))
        return read(
            Quantity(
                "dry mass",
                result.dry_mass_kg,
                "kg",
                "the mass budget: the total of the first mass phase less the propellant the "
                "systems load in it",
            ),
            "The file gives no dry mass, so it is taken from the mass budget (D-233).",
        )
    if label == "Delta-v margin applied":
        item = config.delta_v_margin_ratio
        margin = sourced("delta-v margin", item, "ratio", FILE, "delta_v_margin_ratio")
        step = apply(
            "Delta-v margin as a percentage",
            (margin,),
            lambda ratio: ratio * 100.0,
            "delta-v margin",
            "%",
            logic="The ratio times 100; n/a when no margin is given.",
        )
        return [step], step.result
    if label.startswith("Initial mass"):
        first = result.maneuvers[0] if result.maneuvers else None
        origin = (
            _at(MANEUVERS, first.name, "Mass before (kg)")
            if first is not None
            else "the dry mass (no manoeuvre)"
        )
        return read(
            Quantity("initial mass", result.initial_mass_kg, "kg", origin),
            "The mass before the first manoeuvre: the dry mass and all the propellant.",
        )
    if label == "Total delta-v":
        members = [
            Quantity(
                f"delta-v of {r.name}",
                r.delta_v_total_m_s,
                "m/s",
                _at(MANEUVERS, r.name, "Delta-v with margin (m/s)"),
            )
            for r in result.maneuvers
        ]
        step = total("Delta-v of all the manoeuvres", members, "total delta-v", "m/s")
        return [step], step.result
    if label == "Total propellant":
        members = [
            Quantity(
                f"propellant of {r.name}",
                r.propellant_kg,
                "kg",
                _at(MANEUVERS, r.name, "Propellant (kg)"),
            )
            for r in result.maneuvers
        ]
        step = total("Propellant of all the manoeuvres", members, "total propellant", "kg")
        return [step], step.result
    raise ExplainError("There is no such row in this table.")


def explain_propulsion(
    project: Project,
    table_id: str,
    key: Sequence[str],
    column: str,
    result: PropulsionResult,
) -> Explanation:
    if not key:
        raise ExplainError("Name the row.")
    if table_id == MANEUVERS:
        steps, final = _maneuver_cell(project, result, key, column)
    elif table_id == SYSTEMS:
        steps, final = _system_cell(project, result, key, column)
    elif table_id == SUMMARY:
        steps, final = _summary_cell(project, result, key, column)
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


__all__ = ["explain_propulsion", "propulsion_table_ids"]
