"""Build the propulsion and delta-v budget report document (renderer independent)."""

from __future__ import annotations

from budget_core.model import Project
from budget_core.problems import Problem
from budget_core.propulsion.budget import PropulsionResult
from budget_core.provenance import Provenance
from budget_core.reports.common import BANNER, closing_sections, sheet_name
from budget_core.reports.document import Cell, Column, ReportDocument, Section, Table


def _summary(result: PropulsionResult) -> Table:
    margin = result.delta_v_margin_ratio
    rows: tuple[tuple[Cell, ...], ...] = (
        ("Dry mass", result.dry_mass_kg, "kg"),
        ("Initial mass (dry mass and propellant)", result.initial_mass_kg, "kg"),
        ("Delta-v margin applied", None if margin is None else margin * 100.0, "%"),
        ("Total delta-v", result.total_delta_v_m_s, "m/s"),
        ("Total propellant", result.total_propellant_kg, "kg"),
    )
    return Table(
        "Propulsion budget",
        (Column("Quantity"), Column("Value", "number", 3), Column("Unit")),
        rows,
        note="The manoeuvres are worked backwards from the dry mass with the rocket equation; "
        "n/a: an input is a placeholder or missing.",
    )


def _systems(result: PropulsionResult) -> Table:
    return Table(
        "Propellant, burn time and electric power by system",
        (
            Column("System"),
            Column("Type"),
            Column("Isp (s)", "number", 1, "s"),
            Column("Propellant (kg)", "number", 3, "kg"),
            Column("Loaded (kg)", "number", 3, "kg"),
            Column("Margin (kg)", "number", 3, "kg"),
            Column("Burn time (h)", "number", 2, "h"),
            Column("Power (W)", "number", 1, "W"),
            Column("Energy (Wh)", "number", 1, "Wh"),
        ),
        tuple(
            (
                s.name,
                s.type,
                s.isp_s,
                s.propellant_kg,
                s.loaded_kg,
                s.margin_kg,
                None if s.burn_time_s is None else s.burn_time_s / 3600.0,
                s.power_w,
                s.energy_wh,
            )
            for s in result.systems
        ),
        note="Loaded: the largest mass of the expendable the system names, from the mass budget; "
        "margin: loaded less needed (negative: not enough propellant). The burn time is at "
        "constant thrust; the power and energy are for electric systems.",
    )


def _maneuvers(result: PropulsionResult) -> Table:
    return Table(
        "Manoeuvres in mission order",
        (
            Column("Manoeuvre"),
            Column("System"),
            Column("Burns", "number", 0),
            Column("Delta-v with margin (m/s)", "number", 2, "m/s"),
            Column("Mass before (kg)", "number", 3, "kg"),
            Column("Mass after (kg)", "number", 3, "kg"),
            Column("Propellant (kg)", "number", 3, "kg"),
        ),
        tuple(
            (
                m.name,
                m.system_id,
                m.count,
                m.delta_v_total_m_s,
                m.mass_before_kg,
                m.mass_after_kg,
                m.propellant_kg,
            )
            for m in result.maneuvers
        ),
        note="Delta-v: the burns of the line together, with the margin. Impulsive burns; no "
        "gravity, steering or pointing loss (deviation DV-P1).",
    )


def build_propulsion_report(
    project: Project,
    result: PropulsionResult,
    provenance: Provenance,
    load_problems: list[Problem] | tuple[Problem, ...] = (),
) -> ReportDocument:
    used: set[str] = set()
    sections = [
        Section(
            "Summary",
            sheet_name("Summary", used),
            tables=(_summary(result), _systems(result), _maneuvers(result)),
        )
    ]
    sections += closing_sections(
        used, result.assumptions, "PROP-", [*load_problems, *result.problems], provenance
    )
    incomplete = any(a.placeholder for a in result.assumptions)
    return ReportDocument(
        title=f"Propulsion and delta-v budget: {project.meta.name}",
        provenance=provenance,
        sections=tuple(sections),
        banner=BANNER if incomplete else "",
    )
