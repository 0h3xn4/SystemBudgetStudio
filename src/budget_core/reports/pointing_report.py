"""Build the pointing and slew budget report document (renderer independent)."""

from __future__ import annotations

from budget_core.model import Project
from budget_core.pointing.budget import PointingResult
from budget_core.problems import Problem
from budget_core.provenance import Provenance
from budget_core.reports.common import BANNER, closing_sections, sheet_name
from budget_core.reports.document import Column, ReportDocument, Section, Table


def _modes(result: PointingResult) -> Table:
    return Table(
        "Pointing modes",
        (
            Column("Mode"),
            Column("Reference"),
            Column("Accuracy requirement (deg)", "number", 3, "deg"),
            Column("Actuators"),
            Column("Holding power (W)", "number", 1, "W"),
        ),
        tuple(
            (m.name, m.reference, m.accuracy_deg, m.actuator, m.hold_power_w) for m in result.modes
        ),
        note="A pointing mode is not a spacecraft mode: it says what the spacecraft points at and "
        "how well. The holding power is reported here; to count it in the power budget, give it "
        "to the units that draw it (for example the wheels) in their power modes.",
    )


def _slews(result: PointingResult) -> Table:
    return Table(
        "Slews",
        (
            Column("Slew"),
            Column("From"),
            Column("To"),
            Column("Axis"),
            Column("Angle (deg)", "number", 1, "deg"),
            Column("Inertia (kg m2)", "number", 2, "kg m2"),
            Column("Slew time (s)", "number", 1, "s"),
            Column("With settling (s)", "number", 1, "s"),
            Column("Peak rate (deg/s)", "number", 3, "deg/s"),
            Column("Rate limited"),
            Column("Peak momentum (N m s)", "number", 3, "N m s"),
            Column("Momentum margin (N m s)", "number", 3, "N m s"),
            Column("Energy (Wh)", "number", 3, "Wh"),
            Column("Per day", "number", 0),
            Column("Energy per day (Wh)", "number", 3, "Wh"),
        ),
        tuple(
            (
                s.name,
                s.from_mode,
                s.to_mode,
                s.axis,
                s.angle_deg,
                s.inertia_kgm2,
                s.slew_time_s,
                s.total_time_s,
                s.peak_rate_deg_s,
                "yes" if s.rate_limited else "no",
                s.peak_momentum_nms,
                s.momentum_margin_nms,
                s.energy_wh,
                s.per_day,
                s.energy_per_day_wh,
            )
            for s in result.slews
        ),
        note="Rest-to-rest bang-bang slew about a body axis, limited by the actuators' torque and, "
        "where given, a rate limit; the inertia is the one given or the mass budget's about the "
        "centre of gravity. Impulsive torque changes, no flexible modes (deviation DV-P2).",
    )


def build_pointing_report(
    project: Project,
    result: PointingResult,
    provenance: Provenance,
    load_problems: list[Problem] | tuple[Problem, ...] = (),
) -> ReportDocument:
    used: set[str] = set()
    sections = [
        Section(
            "Summary",
            sheet_name("Summary", used),
            tables=(_modes(result), _slews(result)),
            paragraphs=(
                "Slew time per day: "
                + (
                    "n/a"
                    if result.total_slew_time_per_day_s is None
                    else f"{result.total_slew_time_per_day_s:.1f} s"
                )
                + "; slew energy per day: "
                + (
                    "n/a"
                    if result.total_energy_per_day_wh is None
                    else f"{result.total_energy_per_day_wh:.3f} Wh"
                ),
            ),
        )
    ]
    sections += closing_sections(
        used, result.assumptions, "POINT-", [*load_problems, *result.problems], provenance
    )
    incomplete = any(a.placeholder for a in result.assumptions)
    return ReportDocument(
        title=f"Pointing and slew budget: {project.meta.name}",
        provenance=provenance,
        sections=tuple(sections),
        banner=BANNER if incomplete else "",
    )
