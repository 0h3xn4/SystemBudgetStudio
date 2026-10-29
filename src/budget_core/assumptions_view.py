"""Everything that is active for a project, in one list (D-217).

Five kinds of rows, each with its source and where it is edited: the sourced numbers of the
configuration and the links; the settings, tolerances, limits and constants of the catalogue
(`settings.py`); the model choices of the scenarios and the choices the tool makes for every
project; and the defaults the forms write. The list is built from the loaded project and the
catalogue; it changes nothing and no equation reads it.
"""

from __future__ import annotations

from dataclasses import dataclass

from budget_core.input_sources import project_files, sourced_nodes
from budget_core.io.project_loader import model_to_data
from budget_core.io.yamlio import format_path
from budget_core.model import Project
from budget_core.reports import numfmt
from budget_core.settings import CATALOGUE, KIND_TEXT, format_value
from budget_core.units.quantity import canonical_unit

CONFIGURATION = "Configuration numbers"
SETTINGS = "Model settings"
CHOICES = "Model choices"
CREATION = "Defaults written by forms"
SECTIONS = (CONFIGURATION, SETTINGS, CHOICES, CREATION)
# the names of the sections on the command line
ASSUMPTION_SECTIONS = {
    "configuration": CONFIGURATION,
    "settings": SETTINGS,
    "choices": CHOICES,
    "creation": CREATION,
}


@dataclass(frozen=True)
class Row:
    section: str
    name: str
    value: str
    unit: str
    source: str  # where the number or the choice comes from, or why it is what it is
    status: str  # sourced, estimate, illustrative, placeholder, default, fixed
    where: str  # where it is edited, or why it cannot be

    def to_dict(self) -> dict[str, str]:
        return {
            "section": self.section,
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "source": self.source,
            "status": self.status,
            "where": self.where,
        }


# Choices the tool makes for every project, with the reference that describes them. They are
# facts of the code (audit appendix A); the panel names them so that none is hidden.
FIXED_CHOICES: tuple[tuple[str, str, str], ...] = (
    (
        "Orbit propagation",
        "SGP4 on mean elements",
        "DEVIATIONS DV-E2: elements are used as mean elements, without drag (B* = 0)",
    ),
    (
        "Gravity model of a TLE",
        "WGS-72",
        "DEVIATIONS DV-E5: the SGP4 library's default constants, the usual pairing for TLEs",
    ),
    (
        "Gravity model of orbital elements",
        "WGS-84",
        "DEVIATIONS DV-E5: Earth radius and mu of the SGP4 library's WGS-84 set",
    ),
    (
        "Sun position",
        "Low-precision almanac formulae (about 0.01 degree)",
        "DEVIATIONS DV-E1; equation ENV-SUN",
    ),
    (
        "Earth rotation",
        "GMST only, UTC treated as UT1",
        "DEVIATIONS DV-E1: up to 0.9 s, about 400 m on the ground",
    ),
    (
        "Earth in the shadow geometry",
        "Sphere of the equatorial radius",
        "DEVIATIONS DV-P1: no oblateness, no atmosphere",
    ),
    (
        "Eclipse",
        "Any shadow, penumbra included",
        "DEVIATIONS DV-E4: the sunlight ratio is below 1 by more than 1e-12",
    ),
    (
        "Power cases",
        "BOL and EOL (EOL at the design life)",
        "DEVIATIONS DV-P2; power_system.design_life_yr",
    ),
    (
        "Load basis of a run",
        "Nominal unless the run asks for margined",
        "Option --load-basis of budget power-timeline; shown in the run parameters",
    ),
    (
        "Thermal model",
        "Steady state, isothermal nodes, radiation to one sink",
        "DEVIATIONS DV-T1",
    ),
)


def assumptions(project: Project) -> list[Row]:
    """All rows for `project`, in the order of `SECTIONS`."""
    return [*_configuration(project), *_settings(), *_choices(project), *_creation()]


def _configuration(project: Project) -> list[Row]:
    rows: list[Row] = []
    for rel, model in project_files(project):
        if not (rel.startswith("config/") or rel.startswith("links/")):
            continue
        for parts, node in sourced_nodes(model_to_data(model), ()):
            path = format_path(parts)
            placeholder = node.get("value") is None or str(node["source"]).strip() == "TBD"
            value = node.get("value")
            names = [p for p in parts if isinstance(p, str)]
            rows.append(
                Row(
                    CONFIGURATION,
                    f"{rel.split('/')[-1].removesuffix('.yaml')} {path}",
                    "n/a" if value is None else numfmt.general(float(value)),
                    (canonical_unit(names[-1]) or "") if names else "",
                    str(node["source"]),
                    "placeholder" if placeholder else str(node.get("status", "sourced")),
                    f"{rel} {path}",
                )
            )
    return rows


def _settings() -> list[Row]:
    return [
        Row(
            SETTINGS,
            f"{s.title} ({s.id})",
            format_value(s.default),
            s.unit,
            s.reason,
            "default",
            "Meant to be changed per project (not yet possible)"
            if s.kind == "setting"
            else f"{KIND_TEXT[s.kind]}: fixed in this version",
        )
        for s in CATALOGUE
        if s.kind not in ("creation", "internal")
    ]


def _choices(project: Project) -> list[Row]:
    rows: list[Row] = []
    for sid, scenario in sorted(project.scenarios.items()):
        where = f"scenarios/{sid}.yaml"
        shadow_default = "shadow_model" not in scenario.model_fields_set
        rows.append(
            Row(
                CHOICES,
                f"Scenario {sid}: environment",
                scenario.environment_source,
                "",
                "",
                "set",
                where,
            )
        )
        rows.append(
            Row(
                CHOICES,
                f"Scenario {sid}: shadow model",
                scenario.shadow_model,
                "",
                "the default of the model; the file does not say" if shadow_default else "",
                "default" if shadow_default else "set",
                where,
            )
        )
        if scenario.mission_phase:
            rows.append(
                Row(
                    CHOICES,
                    f"Scenario {sid}: mission phase",
                    scenario.mission_phase,
                    "",
                    "selects the allowed depth of discharge",
                    "set",
                    where,
                )
            )
    for name, value, reference in FIXED_CHOICES:
        rows.append(
            Row(CHOICES, name, value, "", reference, "fixed", "Not selectable in this version")
        )
    return rows


def _creation() -> list[Row]:
    return [
        Row(
            CREATION,
            f"{s.title} ({s.id})",
            format_value(s.default),
            s.unit,
            s.reason,
            "default",
            s.acts_on,
        )
        for s in CATALOGUE
        if s.kind == "creation"
    ]


def counts(rows: list[Row]) -> dict[str, int]:
    return {section: sum(1 for r in rows if r.section == section) for section in SECTIONS}
