# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""Thermal model and environment cases for the steady-state budget (decisions D-071 to D-075).

Every number that comes from a source (optical properties, fluxes, conductances, margins) is a
`Sourced` value; nothing here has a default that looks like data. A node is an isothermal lump;
units sit on nodes (`Unit.thermal_node`, default: the node named like the unit's subsystem).
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_core import PydanticCustomError

from budget_core.model.base import BudgetModel, Sourced
from budget_core.model.versions import CURRENT_VERSIONS


class ThermalNode(BudgetModel):
    name: str = Field(min_length=1)
    heat_capacity_jperk: float | None = Field(default=None, gt=0)  # reserved for transient work


class Conductance(BudgetModel):
    """Linear conduction between two nodes: heat flow = conductance * (T_a - T_b)."""

    first_node: str = Field(min_length=1)
    second_node: str = Field(min_length=1)
    conductance_wk: Sourced

    @model_validator(mode="after")
    def _two_nodes(self) -> Conductance:
        if self.first_node == self.second_node:
            raise PydanticCustomError(
                "conductance_nodes", "a conductance connects two different nodes"
            )
        return self


class Exposure(BudgetModel):
    """The share of a surface that sees the Sun, and the share that sees the Earth, in one case."""

    solar_view_ratio: Sourced
    earth_view_ratio: Sourced


FACES: dict[str, tuple[float, float, float]] = {
    "+x": (1.0, 0.0, 0.0),
    "-x": (-1.0, 0.0, 0.0),
    "+y": (0.0, 1.0, 0.0),
    "-y": (0.0, -1.0, 0.0),
    "+z": (0.0, 0.0, 1.0),
    "-z": (0.0, 0.0, -1.0),
}
NORMAL_TOLERANCE = 1e-6  # how far from length 1 a `normal_lvlh` may be


def _normal(value: object) -> object:
    """A face name (`+x` ... `-z`) is the unit vector of that axis; anything else is checked."""
    if isinstance(value, str):
        try:
            return FACES[value.strip().lower()]
        except KeyError:
            raise PydanticCustomError(
                "normal_face", "a face is one of +x, -x, +y, -y, +z, -z"
            ) from None
    return value


class Surface(BudgetModel):
    """An outer surface of a node: radiates to space, absorbs sunlight, albedo, Earth infrared.

    `normal_lvlh` is the outward unit normal of a flat surface in the local-vertical frame of a
    spacecraft that points to nadir (x along the velocity, y opposite to the orbit normal, z to
    nadir), given as three numbers or as a face name. With it, `budget thermal-beta` takes the
    solar exposure of the surface from the beta angle; without it the typed view ratios are used
    (D-250). It is a design input (a direction), not a sourced property."""

    name: str = Field(min_length=1)
    node: str = Field(min_length=1)
    area_m2: float = Field(gt=0)
    emissivity_ratio: Sourced  # infrared
    absorptivity_ratio: Sourced  # solar
    exposure: dict[str, Exposure] = Field(default_factory=dict)  # by case name
    normal_lvlh: tuple[float, float, float] | None = None

    @field_validator("normal_lvlh", mode="before")
    @classmethod
    def _face_name(cls, value: object) -> object:
        return _normal(value)

    @field_validator("normal_lvlh")
    @classmethod
    def _unit_length(
        cls, value: tuple[float, float, float] | None
    ) -> tuple[float, float, float] | None:
        if value is not None:
            length = (value[0] ** 2 + value[1] ** 2 + value[2] ** 2) ** 0.5
            if abs(length - 1.0) > NORMAL_TOLERANCE:
                raise PydanticCustomError(
                    "normal_length", "a surface normal is a unit vector (length 1)"
                )
        return value

    @field_validator("exposure")
    @classmethod
    def _sorted(cls, value: dict[str, Exposure]) -> dict[str, Exposure]:
        return dict(sorted(value.items()))


class ThermalModel(BudgetModel):
    schema_version: int = CURRENT_VERSIONS["thermal_model"]
    kind: Literal["thermal_model"] = "thermal_model"
    nodes: dict[str, ThermalNode] = Field(min_length=1)
    conductances: list[Conductance] = Field(default_factory=list)
    surfaces: list[Surface] = Field(default_factory=list)

    @field_validator("nodes")
    @classmethod
    def _sorted_nodes(cls, value: dict[str, ThermalNode]) -> dict[str, ThermalNode]:
        return dict(sorted(value.items()))


class ThermalCase(BudgetModel):
    """A named load case (for example hot or cold): which spacecraft mode dissipates, and the
    environment. `limit_set` chooses the unit temperature limits the result is checked against."""

    description: str = ""
    spacecraft_mode: str = Field(min_length=1)
    limit_set: Literal["operating", "survival"] = "operating"
    solar_flux_wm2: Sourced
    albedo_ratio: Sourced
    earth_ir_wm2: Sourced


class ThermalEnvironment(BudgetModel):
    schema_version: int = CURRENT_VERSIONS["thermal_environment"]
    kind: Literal["thermal_environment"] = "thermal_environment"
    space_temperature_k: Sourced
    temperature_margin_k: Sourced  # required headroom to the unit limits
    cases: dict[str, ThermalCase] = Field(default_factory=dict)

    @field_validator("cases")
    @classmethod
    def _sorted_cases(cls, value: dict[str, ThermalCase]) -> dict[str, ThermalCase]:
        return dict(sorted(value.items()))
