"""Pointing modes, actuators and slews for the pointing and slew budget (2.2.0, D-234).

A pointing mode says what the spacecraft points at and how well; it is kept apart from the
spacecraft modes (which choose the power mode of every unit) and the scenario's mode rules. A slew
turns the spacecraft from one pointing mode to another. Every number that comes from a source is a
`Sourced` value; nothing here has a default that looks like data.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from budget_core.model.base import BudgetModel, Sourced
from budget_core.model.versions import CURRENT_VERSIONS


class Actuator(BudgetModel):
    name: str = Field(min_length=1)
    max_torque_nm: Sourced  # per axis
    max_rate_deg_s: Sourced | None = None  # a limit of the spacecraft's slew rate (sensors, wheels)
    momentum_capacity_nms: Sourced | None = None  # per axis
    slew_power_w: Sourced | None = None  # mean electrical power while slewing


class PointingMode(BudgetModel):
    name: str = Field(min_length=1)
    reference: Literal["nadir", "sun", "inertial", "target", "other"]
    accuracy_deg: Sourced | None = None  # the requirement, not a result
    actuator: str = Field(min_length=1)
    hold_power_w: Sourced | None = None  # mean electrical power to hold the mode


class Slew(BudgetModel):
    name: str = Field(min_length=1)
    from_mode: str = Field(min_length=1)
    to_mode: str = Field(min_length=1)
    angle_deg: Sourced  # the rotation about the axis
    axis: Literal["x", "y", "z"]  # a body axis (a principal axis is assumed)
    actuator: str = Field(min_length=1)
    inertia_kgm2: Sourced | None = None  # about the axis; else from the mass budget
    settle_s: Sourced | None = None  # settling time added after the slew
    per_day: int = Field(default=1, ge=1)  # how often it is done in a day


class PointingConfig(BudgetModel):
    schema_version: int = CURRENT_VERSIONS["pointing"]
    kind: Literal["pointing"] = "pointing"
    actuators: dict[str, Actuator] = Field(default_factory=dict)
    modes: dict[str, PointingMode] = Field(default_factory=dict)
    slews: list[Slew] = Field(default_factory=list)
    # the mission phase whose mass-budget inertia is used for a slew without its own inertia
    mass_phase: str | None = None

    @field_validator("actuators", "modes")
    @classmethod
    def _sorted(cls, value: dict[str, object]) -> dict[str, object]:
        return dict(sorted(value.items()))
