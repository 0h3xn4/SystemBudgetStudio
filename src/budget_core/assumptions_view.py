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
from budget_core.model import Project, Scenario
from budget_core.model_choices import REGISTRY, ModelChoice
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
    """One row per scenario for a choice made in the scenario file, one row for a run option,
    and one row for each model the tool fixes (the registry, `model_choices.py`)."""
    rows: list[Row] = []
    for entry in REGISTRY:
        if entry.scope == "scenario":
            for sid, scenario in sorted(project.scenarios.items()):
                rows.append(_scenario_row(entry, sid, scenario))
        elif entry.scope == "run":
            others = ", ".join(c.id for c in entry.choices if c.id != entry.default)
            rows.append(
                Row(
                    CHOICES,
                    entry.title,
                    entry.default,
                    "",
                    f"{entry.where}; the other choice is {others}; shown in the run parameters",
                    "default",
                    "Chosen for each run",
                )
            )
        else:
            rows.append(
                Row(
                    CHOICES,
                    entry.title,
                    entry.active_title(entry.default),
                    "",
                    entry.reference,
                    "fixed",
                    entry.where,
                )
            )
        if entry.id == "environment.shadow_model":
            rows.extend(_mission_phase_rows(project))
    return rows


def _scenario_row(entry: ModelChoice, sid: str, scenario: Scenario) -> Row:
    chosen = str(getattr(scenario, entry.field))
    is_default = entry.field not in scenario.model_fields_set
    return Row(
        CHOICES,
        f"Scenario {sid}: {entry.label}",
        chosen,
        "",
        "the default of the model; the file does not say"
        if is_default and chosen == entry.default
        else entry.active_title(chosen),
        "default" if is_default else "set",
        f"scenarios/{sid}.yaml",
    )


def _mission_phase_rows(project: Project) -> list[Row]:
    return [
        Row(
            CHOICES,
            f"Scenario {sid}: mission phase",
            scenario.mission_phase,
            "",
            "selects the allowed depth of discharge",
            "set",
            f"scenarios/{sid}.yaml",
        )
        for sid, scenario in sorted(project.scenarios.items())
        if scenario.mission_phase
    ]


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
