"""Solar array, battery, attitude and limits for the time-domain power budget (D-061 to D-066).

Every electrical number is a `Sourced` value from a data sheet or a requirement. Nothing here has a
default: an input that is not supplied is a placeholder and the results that need it show n/a.
"""

from __future__ import annotations

import math
from typing import Literal

from pydantic import Field, field_validator
from pydantic_core import PydanticCustomError

from budget_core.model.base import BudgetModel, Sourced
from budget_core.model.versions import CURRENT_VERSIONS

Pointing = Literal["sun", "nadir"]

# Counts that give an absurd array or pack are refused (a count of 10**400 overflows when the
# cells are added up). The limits are far above any real spacecraft.
MAX_STRINGS = 10_000
MAX_CELLS_PER_STRING = 10_000
MAX_CELLS_IN_SERIES = 1_000
MAX_CELLS_IN_PARALLEL = 10_000
MAX_DIRECTION_COMPONENT = 1.0e6  # a direction is a direction: its length is not a quantity
MIN_DIRECTION_LENGTH = 1.0e-6


def _direction(value: list[float] | None) -> list[float] | None:
    if value is None:
        return None
    if len(value) != 3:
        raise PydanticCustomError("vector_invalid", "a direction has exactly three components")
    if any(abs(c) > MAX_DIRECTION_COMPONENT for c in value):
        raise PydanticCustomError(
            "vector_invalid",
            "a direction component must not exceed {limit}",
            {"limit": MAX_DIRECTION_COMPONENT},
        )
    if math.hypot(*value) < MIN_DIRECTION_LENGTH:
        raise PydanticCustomError("vector_invalid", "a direction must not be (almost) zero")
    return value


class ArrayFace(BudgetModel):
    """One array panel: its outward normal in the body frame and its cell count."""

    name: str = Field(min_length=1)
    normal_body: list[float]
    strings: int = Field(ge=1, le=MAX_STRINGS)
    cells_per_string: int = Field(ge=1, le=MAX_CELLS_PER_STRING)

    @field_validator("normal_body")
    @classmethod
    def _normal(cls, value: list[float]) -> list[float]:
        checked = _direction(value)
        assert checked is not None
        return checked

    @property
    def cell_count(self) -> int:
        return self.strings * self.cells_per_string


class SolarArray(BudgetModel):
    faces: list[ArrayFace] = Field(default_factory=list)
    solar_irradiance_wm2: Sourced
    cell_area_m2: Sourced
    cell_efficiency_ratio: Sourced  # at the reference temperature
    reference_temperature_k: Sourced
    cell_temperature_k: Sourced  # operating temperature, one value for the whole array
    efficiency_temp_coeff_perk: Sourced  # relative change of efficiency per kelvin (negative)
    packing_loss_ratio: Sourced
    harness_loss_ratio: Sourced
    annual_degradation_ratio: Sourced  # fraction of output lost per year

    @field_validator("faces")
    @classmethod
    def _unique(cls, faces: list[ArrayFace]) -> list[ArrayFace]:
        names = [f.name for f in faces]
        if len(set(names)) != len(names):
            raise PydanticCustomError("duplicate_name", "face names must be unique")
        return faces


class Battery(BudgetModel):
    cell_capacity_ah: Sourced
    cell_nominal_voltage_v: Sourced
    cells_in_series: int = Field(ge=1, le=MAX_CELLS_IN_SERIES)
    cells_in_parallel: int = Field(ge=1, le=MAX_CELLS_IN_PARALLEL)
    charge_efficiency_ratio: Sourced
    discharge_efficiency_ratio: Sourced
    annual_capacity_fade_ratio: Sourced
    initial_soc_ratio: Sourced
    max_dod_ratio: dict[str, Sourced] = Field(default_factory=dict)  # by mission phase

    @field_validator("max_dod_ratio")
    @classmethod
    def _sorted(cls, value: dict[str, Sourced]) -> dict[str, Sourced]:
        return dict(sorted(value.items()))


class Attitude(BudgetModel):
    """Pointing per spacecraft mode. `sun`: the Sun is along `sun_direction_body`. `nadir`: the
    body frame is aligned with the local orbital frame (+Z to the Earth, +X along track,
    +Y opposite the orbit normal)."""

    default: Pointing | None = None
    by_mode: dict[str, Pointing] = Field(default_factory=dict)
    sun_direction_body: list[float] | None = None

    @field_validator("sun_direction_body")
    @classmethod
    def _sun(cls, value: list[float] | None) -> list[float] | None:
        return _direction(value)

    @field_validator("by_mode")
    @classmethod
    def _sorted(cls, value: dict[str, Pointing]) -> dict[str, Pointing]:
        return dict(sorted(value.items()))


class PowerLimits(BudgetModel):
    peak_power_w: Sourced  # most power the power system can supply at the bus input


class PowerSystem(BudgetModel):
    schema_version: int = CURRENT_VERSIONS["power_system"]
    kind: Literal["power_system"] = "power_system"
    design_life_yr: Sourced
    solar_array: SolarArray
    battery: Battery
    attitude: Attitude = Field(default_factory=Attitude)
    limits: PowerLimits
