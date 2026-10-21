"""A blank project: the folder a new spacecraft starts from (D-185).

It holds what every project needs and nothing the user has not said: the name, one bus with the
voltage the user gives, the configuration files with every number a placeholder (`source: TBD`)
and empty tables. There are no units, modes, orbits, scenarios or links, and no invented values.
The Problems panel and the INCOMPLETE banner list what is still to be filled in, so the result is
a project that opens, validates and computes (to `n/a`) from the first minute.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from budget_core.model import (
    AttenuationTable,
    Bus,
    Ebn0Table,
    MarginPolicy,
    MassLimits,
    MaturityClass,
    PowerConfig,
    Project,
    ProjectConfig,
    ProjectMeta,
    Spacecraft,
)
from budget_core.model.base import Sourced
from budget_core.wizard import Issue, WizardError, folder_name, write_new_project

MATURITY_CLASSES = ("class_a", "class_b", "class_c")  # labels only; their margins are TBD
BUS_VOLTAGE_RANGE_V = (1.0, 1000.0)
MAX_NAME = 120
DESCRIPTION = (
    "A blank project: every configuration number is a placeholder (source TBD) and the tables "
    "are empty. Add units, power modes, an orbit and a scenario, and replace each placeholder "
    "with a sourced value; the Problems panel lists what is still open."
)


@dataclass(frozen=True)
class BlankAnswers:
    project_name: str
    bus_voltage_v: float | None = None  # required: the one number a spacecraft cannot do without
    bus_name: str = "main"
    spacecraft_name: str = ""  # empty: the project name


def _tbd() -> Sourced:
    return Sourced(value=None, source="TBD", note="Placeholder: supply the project's value.")


def check_blank(answers: BlankAnswers) -> list[Issue]:
    issues: list[Issue] = []
    if not answers.project_name.strip():
        issues.append(Issue("project_name", "Give the project a name."))
    elif len(answers.project_name.strip()) > MAX_NAME:
        issues.append(Issue("project_name", f"The name can have at most {MAX_NAME} characters."))
    if not answers.bus_name.strip():
        issues.append(Issue("bus_name", "Give the bus a name, for example main."))
    elif len(answers.bus_name.strip()) > MAX_NAME:
        issues.append(Issue("bus_name", f"The bus name can have at most {MAX_NAME} characters."))
    low, high = BUS_VOLTAGE_RANGE_V
    voltage = answers.bus_voltage_v
    if voltage is None or isinstance(voltage, bool) or not math.isfinite(voltage):
        issues.append(Issue("bus_voltage_v", "Give the nominal voltage of the bus, in volts."))
    elif not low <= voltage <= high:
        issues.append(
            Issue("bus_voltage_v", f"The bus voltage must be between {low:g} and {high:g} V.")
        )
    if len(answers.spacecraft_name.strip()) > MAX_NAME:
        issues.append(Issue("spacecraft_name", f"The name can have at most {MAX_NAME} characters."))
    return issues


def build_blank(answers: BlankAnswers, folder: Path) -> Project:
    """The project model, not yet written. The answers must have passed `check_blank`."""
    assert answers.bus_voltage_v is not None
    name = answers.project_name.strip()
    bus = answers.bus_name.strip()
    return Project(
        root=folder,
        meta=ProjectMeta(name=name, revision="1", description=DESCRIPTION),
        spacecraft=Spacecraft(
            name=answers.spacecraft_name.strip() or name,
            buses=[Bus(name=bus, nominal_voltage_v=answers.bus_voltage_v)],
        ),
        config=ProjectConfig(
            margin_policy=MarginPolicy(
                classes={
                    label: MaturityClass(power_margin_ratio=_tbd(), mass_margin_ratio=_tbd())
                    for label in MATURITY_CLASSES
                },
                system_power_margin_ratio=_tbd(),
                system_mass_margin_ratio=_tbd(),
            ),
            power_config=PowerConfig(
                distribution_loss_ratio=_tbd(), converter_efficiency_ratio={bus: _tbd()}
            ),
            ebn0_table=Ebn0Table(),
            attenuation_table=AttenuationTable(),
            mass_limits=MassLimits(limits=[]),
        ),
    )


def create_blank_project(answers: BlankAnswers, folder: Path) -> Path:
    """Write a blank project into `folder`, which must not exist yet, and return it. Whatever
    goes wrong becomes a WizardError (a plain-language reason); an existing folder is never
    touched and a folder that could not be written completely is removed again."""
    issues = check_blank(answers)
    if issues:
        raise WizardError(issues[0].message)
    return write_new_project(Path(folder), lambda: build_blank(answers, Path(folder)))


def create_blank_in(answers: BlankAnswers, parent: Path) -> Path:
    """As `create_blank_project`, in a new folder named after the project inside `parent`."""
    return create_blank_project(answers, Path(parent) / folder_name(answers.project_name))
