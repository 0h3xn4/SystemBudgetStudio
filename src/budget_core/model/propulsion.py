# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""Propulsion systems and manoeuvres for the delta-v and propellant budget (2.2.0, D-233).

A system is a chemical or an electric thruster set with its specific impulse; a manoeuvre is a
delta-v taken with one system, in mission order. Every number that comes from a source is a
`Sourced` value; nothing here has a default that looks like data.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_core import PydanticCustomError

from budget_core.model.base import BudgetModel, Sourced
from budget_core.model.versions import CURRENT_VERSIONS


class PropulsionSystem(BudgetModel):
    name: str = Field(min_length=1)
    type: Literal["chemical", "electric"]
    isp_s: Sourced  # specific impulse in seconds (exhaust velocity = isp * g0)
    thrust_n: Sourced | None = None  # for the burn time
    power_w: Sourced | None = None  # electric: the power drawn while thrusting
    propellant: str | None = None  # the id of the expendable that holds this system's propellant
    # the heat a burn puts into a thermal node (2.3.0): the power drawn while thrusting that does
    # not leave as thrust, in the thermal cases of the manoeuvre's spacecraft mode
    thermal_node: str | None = None
    thrust_heat_w: Sourced | None = None

    @model_validator(mode="after")
    def _power_only_electric(self) -> PropulsionSystem:
        if (self.thermal_node is None) != (self.thrust_heat_w is None):
            raise PydanticCustomError(
                "heat_node", "a thrusting heat needs its thermal node and the other way round"
            )
        if self.power_w is not None and self.type != "electric":
            raise PydanticCustomError(
                "power_not_electric", "only an electric system has a thrusting power"
            )
        return self


class Maneuver(BudgetModel):
    name: str = Field(min_length=1)
    system: str = Field(min_length=1)
    delta_v_m_s: Sourced
    count: int = Field(default=1, ge=1)  # identical burns (for example station-keeping)
    # the spacecraft mode during the burn when it is placed in a scenario (2.3.0): the
    # "Manoeuvre" mode; without it the scenario's own mode continues
    mode: str | None = None


class PropulsionConfig(BudgetModel):
    schema_version: int = CURRENT_VERSIONS["propulsion"]
    kind: Literal["propulsion"] = "propulsion"
    systems: dict[str, PropulsionSystem] = Field(default_factory=dict)
    maneuvers: list[Maneuver] = Field(default_factory=list)  # in mission order
    # the mass the manoeuvres end with; without it, the launch-phase mass of the mass budget less
    # the propellant of the systems that name an expendable
    dry_mass_kg: Sourced | None = None
    # extra delta-v on every manoeuvre, as a ratio (0.05 for 5 %); no value is assumed
    delta_v_margin_ratio: Sourced | None = None

    @field_validator("systems")
    @classmethod
    def _sorted(cls, value: dict[str, PropulsionSystem]) -> dict[str, PropulsionSystem]:
        return dict(sorted(value.items()))
