"""The typed, unit-normalised model that `read_idm` produces.

Plain frozen dataclasses. Lengths are metres, angles degrees, masses kilograms, power and
dissipation watts, temperatures degrees Celsius (as the file gives them; the mapping layer
converts), margins and filling levels fractions (0.1 = 10 %). A value the file does not give is
`None`. Objects are identified by `full_id`, the path-like identifier the program gives every
object; names are for display only (decision D-238).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

Pairs = tuple[tuple[str, float], ...]


@dataclass(frozen=True)
class Subsystem:
    id: str
    full_id: str
    name: str


@dataclass(frozen=True)
class PowerMode:
    id: str
    full_id: str
    name: str
    power_w: float | None
    dissipation_w: float | None


@dataclass(frozen=True)
class Position:
    """Where an object is in its parent frame: a translation and three rotations (degrees)."""

    x_m: float
    y_m: float
    z_m: float
    rotation_order: str  # for example "Rx_Ry_Rz"
    rotations_deg: tuple[float, float, float]
    transformation_order: str  # for example "Translation_Rotation"


@dataclass(frozen=True)
class Frame:
    """A coordinate system or an occurrence: the nodes of the chain that places an equipment."""

    full_id: str
    kind: str  # "coordinate_system" or "occurrence"
    position: Position | None  # None: take it from `origin`
    parent: str | None  # full id of the coordinate system it is placed on
    origin: str | None  # the object it was copied from (definition or template instance)
    owner: str | None  # for a coordinate system of an occurrence: that occurrence
    articulation: float | None  # reference value of its articulation; None: it has none


@dataclass(frozen=True)
class Shape:
    """A shape of an equipment. Only what the mass needs is kept; the geometry is read later."""

    id: str
    full_id: str
    name: str
    mass_type: str  # "Total", "Area" or "Volume"
    mass_total_kg: float | None
    mass_per_m2_kg: float | None
    mass_per_m3_kg: float | None
    kind: str  # tag of the 3D object, for example "FilledCylinder"
    parameters: Pairs  # numeric children of the 3D object, for example ("capacity", 10.0)
    object_full_id: str  # full id of the 3D object (a tank content refers to it)
    position: Position | None = None  # in the frame of the equipment


@dataclass(frozen=True)
class Point:
    x_m: float
    y_m: float
    z_m: float


@dataclass(frozen=True)
class Inertia:
    """The nine entries of the 3x3 matrix, in kg m^2, row by row (xx xy xz yx yy yz zx zy zz)."""

    entries: tuple[float, float, float, float, float, float, float, float, float]


@dataclass(frozen=True)
class Temperatures:
    operating_min_c: float | None
    operating_max_c: float | None
    survival_min_c: float | None
    survival_max_c: float | None


@dataclass(frozen=True)
class Equipment:
    """An equipment definition (the template that occurrences are made from)."""

    full_id: str
    element_id: str
    subsystem_id: str
    name: str
    optional: bool
    default_enabled: bool
    optional_by_configuration: tuple[tuple[str, bool], ...]
    mci_origin: str  # "FromGeometry" or "ManualInput"
    maturity: str | None
    mass_margin: float | None
    power_margin: float | None
    manual_mass_kg: float | None
    manual_cog: Point | None
    manual_inertia: Inertia | None
    can_have_custom_power: bool
    temperatures: Temperatures
    power_modes: tuple[PowerMode, ...]
    shapes: tuple[Shape, ...]


@dataclass(frozen=True)
class Assembly:
    full_id: str
    element_id: str
    subsystem_id: str
    name: str


@dataclass(frozen=True)
class PowerMapping:
    """What one occurrence does in one element mode or system mode."""

    mode_id: str  # id of the element mode or system mode (also the id of the mapping)
    power_mode_full_id: str | None
    custom_power_w: float | None
    custom_dissipation_w: float | None


@dataclass(frozen=True)
class TankContent:
    full_id: str
    tank_object_full_id: str
    default_filling: float | None  # fraction of the maximal fill, reference configuration
    filling_by_configuration: tuple[tuple[str, float], ...]


@dataclass(frozen=True)
class Occurrence:
    """One physical copy of an equipment: it counts once in every budget."""

    full_id: str
    equipment_full_id: str
    element_id: str
    subsystem_id: str
    assembly_path: tuple[str, ...]  # full ids of the assemblies it sits in, outermost first
    thermal_module_full_id: str | None
    element_mappings: tuple[PowerMapping, ...]
    system_mappings: tuple[PowerMapping, ...]
    tank_contents: tuple[TankContent, ...]


@dataclass(frozen=True)
class ElementMode:
    id: str
    full_id: str
    name: str
    element_id: str


@dataclass(frozen=True)
class ThermalModule:
    id: str
    full_id: str
    name: str
    element_id: str


@dataclass(frozen=True)
class RelatedSubsystem:
    element_id: str
    subsystem_id: str
    forced_mass_kg: float | None
    forced_mass_margin: float | None


@dataclass(frozen=True)
class Element:
    id: str
    full_id: str
    name: str
    mass_target_kg: float | None
    mass_margin: float | None
    power_margin: float | None
    forced_propellant_kg: float | None
    forced_propellant_margin: float | None
    related: tuple[RelatedSubsystem, ...]
    modes: tuple[ElementMode, ...]
    thermal_modules: tuple[ThermalModule, ...]


@dataclass(frozen=True)
class SystemMode:
    id: str
    full_id: str
    name: str
    duty_cycle: float | None
    element_mode_full_ids: tuple[str, ...]


@dataclass(frozen=True)
class Configuration:
    id: str
    full_id: str
    name: str
    enabled_element_ids: tuple[str, ...]


@dataclass(frozen=True)
class CustomProperty:
    """A user-defined extra value on an object; reported, not mapped by default."""

    owner_full_id: str
    name: str
    value: str | None  # as written in the file


@dataclass(frozen=True)
class IdmModel:
    source_name: str  # file name, no folders
    sha256: str  # of model.xml: the revision of the model
    file_version: str  # version written in the file (the program that saved it)
    project_name: str | None
    comment: str | None
    system_version: str | None
    last_modification: datetime | None
    propellant_margin: float | None
    subsystems: tuple[Subsystem, ...]
    elements: tuple[Element, ...]
    equipment: tuple[Equipment, ...]
    assemblies: tuple[Assembly, ...]
    occurrences: tuple[Occurrence, ...]
    system_modes: tuple[SystemMode, ...]
    configurations: tuple[Configuration, ...]
    custom_properties: tuple[CustomProperty, ...] = field(default=())
    stale_formula_targets: tuple[str, ...] = field(default=())  # formulas flagged not valid
    ignored_counts: tuple[tuple[str, int], ...] = field(default=())  # kind of object, how many
    frames: tuple[Frame, ...] = field(default=())  # the chain of placements (D-245)
