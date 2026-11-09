# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""Read an IDM-CIC model file into a typed `IdmModel` (decisions D-237 to D-239).

Rules of the reader:

* it reads values as written, never evaluates a formula and never estimates a missing value;
* an object is identified by its `fullId`; a reference is an object with a `ref` attribute;
* the physical equipment of the model is found by walking from the instances placed in each
  element down through placed assemblies. The instances that sit inside an assembly *definition*
  are templates of the assembly and are not counted (D-238);
* a problem names a field and an object id, never a value read from the file; a field that cannot
  be read makes the whole read fail (`IdmRead.ok` is false) so that nothing is imported half-way.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TypeVar

from budget_core.idm import SPEC_MAJOR_MINOR
from budget_core.idm.archive import IdmReadError, read_model_bytes
from budget_core.idm.model import (
    Assembly,
    Configuration,
    CustomProperty,
    Element,
    ElementMode,
    Equipment,
    Frame,
    IdmModel,
    Inertia,
    Occurrence,
    Point,
    Position,
    PowerMapping,
    PowerMode,
    RelatedSubsystem,
    Shape,
    Subsystem,
    SystemMode,
    TankContent,
    Temperatures,
    ThermalModule,
)
from budget_core.idm.values import (
    IdmValueError,
    parse_bool,
    parse_datetime,
    parse_float,
)
from budget_core.idm.xmltree import parse_model
from budget_core.problems import Problem, Severity

T = TypeVar("T")

_EQUIPMENT_TAGS = ("EquipmentInstance", "EquipmentOccurrence")
_ASSEMBLY_TAGS = ("AssemblyInstance", "AssemblyOccurrence")
# bookkeeping children of a 3D object that are not parameters of its shape
_NOT_PARAMETERS = frozenset({"lastModification", "doInvalidateCacheAction", "hidden"})


@dataclass(frozen=True)
class IdmRead:
    model: IdmModel | None
    problems: tuple[Problem, ...]

    @property
    def ok(self) -> bool:
        return self.model is not None and not any(
            p.severity is Severity.ERROR for p in self.problems
        )


def _problem(
    severity: Severity, code: str, message: str, path: str = "", hint: str = ""
) -> Problem:
    return Problem(severity, code, message, path=path, hint=hint)


@dataclass
class _Reader:
    index: dict[str, ET.Element]
    problems: list[Problem] = field(default_factory=list)
    ignored: dict[str, int] = field(default_factory=dict)

    # ---- low-level access -------------------------------------------------------------------

    def child(self, node: ET.Element, tag: str) -> ET.Element | None:
        return node.find(tag)

    def text(self, node: ET.Element, tag: str) -> str | None:
        found = node.find(tag)
        if found is None or found.text is None:
            return None
        value = found.text.strip()
        return value or None

    def _value(self, node: ET.Element, tag: str, parse: Callable[[str], T], what: str) -> T | None:
        raw = self.text(node, tag)
        if raw is None:
            return None
        try:
            return parse(raw)
        except IdmValueError:
            self.problems.append(
                _problem(
                    Severity.ERROR,
                    "IDM_VALUE_INVALID",
                    f"A {what} field is not in the format of the model file.",
                    path=f"{node.get('fullId', '?')}/{tag}",
                    hint="Numbers use a comma as decimal separator, dates are dd/mm/yyyy hh:mm:ss.",
                )
            )
            return None

    def number(self, node: ET.Element, tag: str) -> float | None:
        return self._value(node, tag, parse_float, "numeric")

    def flag(self, node: ET.Element, tag: str, default: bool = False) -> bool:
        value = self._value(node, tag, parse_bool, "yes/no")
        return default if value is None else value

    def when(self, node: ET.Element, tag: str) -> datetime | None:
        return self._value(node, tag, parse_datetime, "date")

    def items(self, node: ET.Element, tag: str) -> Iterator[ET.Element]:
        """The objects of a dictionary or list property (their `Array` child)."""
        holder = node.find(tag)
        if holder is None:
            return iter(())
        array = holder.find("Array")
        return iter(array) if array is not None else iter(())

    def ref_of(self, node: ET.Element | None) -> str | None:
        if node is None:
            return None
        return node.get("ref") or node.get("fullId")

    def ref_child(self, node: ET.Element, tag: str) -> str | None:
        holder = node.find(tag)
        if holder is None or len(holder) == 0:
            return None
        return self.ref_of(holder[0])

    def ignore(self, kind: str) -> None:
        self.ignored[kind] = self.ignored.get(kind, 0) + 1

    def position(self, node: ET.Element) -> Position | None:
        inner = node.find("position/Position")
        if inner is None:
            return None
        x, y, z = (self.number(inner, axis) for axis in ("x", "y", "z"))
        angles = [self.number(inner, f"rotation{i}") for i in (1, 2, 3)]
        order = self.text(inner, "rotationOrder")
        transformation = self.text(inner, "transformationOrder")
        if None in (x, y, z, order, transformation) or any(a is None for a in angles):
            return None
        assert x is not None and y is not None and z is not None
        assert order is not None and transformation is not None
        return Position(x, y, z, order, (angles[0], angles[1], angles[2]), transformation)  # type: ignore[arg-type]

    def articulation(self, node: ET.Element) -> float | None:
        """The reference value of the articulation of a coordinate system; NaN when it cannot
        be read (it is then treated as not zero); None when there is no articulation."""
        holder = node.find("articulation")
        if holder is None or len(holder) == 0:
            return None
        art = holder[0]
        if art.get("ref"):
            art = self.index.get(art.get("ref", ""), art)
        if art.tag in ("RotationDefinition", "TranslationDefinition", "Rotation", "Translation"):
            value = self.number(art, "defaultValue")  # the reference configuration uses it
            return 0.0 if value is None else value
        return float("nan")

    def frames(self) -> tuple[Frame, ...]:
        out = []
        occurrence_ids = {
            full
            for full, node in self.index.items()
            if node.tag in _EQUIPMENT_TAGS + _ASSEMBLY_TAGS
        }
        for full_id in sorted(self.index):
            node = self.index[full_id]
            if node.tag in _EQUIPMENT_TAGS + _ASSEMBLY_TAGS:
                kind, owner = "occurrence", None
            elif node.tag in ("CoordinateSystem", "CoordinateSystemDefinition"):
                kind = "coordinate_system"
                prefix = full_id.rsplit("_co.", 1)[0]
                owner = prefix if prefix in occurrence_ids else None
            else:
                continue
            out.append(
                Frame(
                    full_id=full_id,
                    kind=kind,
                    position=self.position(node),
                    parent=self.ref_child(node, "parentCoordinateSystem"),
                    origin=self.ref_child(node, "originOccurrence")
                    or self.ref_child(node, "originCoordinateSystem"),
                    owner=owner,
                    articulation=self.articulation(node) if kind == "coordinate_system" else None,
                )
            )
        return tuple(out)

    # ---- definitions ------------------------------------------------------------------------

    def power_modes(self, equipment: ET.Element) -> tuple[PowerMode, ...]:
        out = []
        for node in self.items(equipment, "powerModes"):
            if node.tag != "PowerMode" or node.get("ref"):
                continue
            out.append(
                PowerMode(
                    id=node.get("id", ""),
                    full_id=node.get("fullId", ""),
                    name=self.text(node, "name") or "",
                    power_w=self.number(node, "power"),
                    dissipation_w=self.number(node, "dissipation"),
                )
            )
        return tuple(out)

    def shapes(self, equipment: ET.Element) -> tuple[Shape, ...]:
        out = []
        for node in self.items(equipment, "shapes"):
            if node.tag != "Shape" or node.get("ref"):
                continue
            definition = node.find("shapeDefinition")
            obj = definition[0] if definition is not None and len(definition) else None
            mass = node.find("massDefinition/MassDefinition")
            parameters: list[tuple[str, float]] = []
            if obj is not None:
                for part in obj:
                    if part.tag in _NOT_PARAMETERS or len(part):
                        continue
                    try:  # a parameter that is not a number is simply not a numeric parameter
                        parameters.append((part.tag, parse_float(part.text or "")))
                    except IdmValueError:
                        continue
            out.append(
                Shape(
                    id=node.get("id", ""),
                    full_id=node.get("fullId", ""),
                    name=self.text(node, "name") or "",
                    mass_type=(self.text(mass, "massType") if mass is not None else None) or "",
                    mass_total_kg=self.number(mass, "massTotal") if mass is not None else None,
                    mass_per_m2_kg=self.number(mass, "massPerSquareMeter")
                    if mass is not None
                    else None,
                    mass_per_m3_kg=self.number(mass, "massPerCubeMeter")
                    if mass is not None
                    else None,
                    kind=obj.tag if obj is not None else "",
                    parameters=tuple(parameters),
                    object_full_id=(obj.get("fullId", "") if obj is not None else ""),
                    position=self.position(node),
                )
            )
        return tuple(out)

    def point(self, node: ET.Element, tag: str) -> Point | None:
        holder = node.find(tag)
        inner = holder.find("Point") if holder is not None else None
        if inner is None:
            return None
        x, y, z = (self.number(inner, axis) for axis in ("x", "y", "z"))
        if x is None or y is None or z is None:
            return None
        return Point(x, y, z)

    def inertia(self, node: ET.Element, tag: str) -> Inertia | None:
        holder = node.find(tag)
        inner = holder.find("Matrix") if holder is not None else None
        if inner is None:
            return None
        values = [
            self.number(inner, n) for n in ("xx", "xy", "xz", "yx", "yy", "yz", "zx", "zy", "zz")
        ]
        if any(v is None for v in values):
            return None
        return Inertia(tuple(v for v in values if v is not None))  # type: ignore[arg-type]

    def equipment(self, node: ET.Element, element_id: str, subsystem_id: str) -> Equipment:
        optional_links = []
        for link in self.items(node, "optionalUnitLinks"):
            if link.tag == "OptionalUnitLink" and not link.get("ref"):
                optional_links.append((link.get("id", ""), self.flag(link, "enabled", True)))
        return Equipment(
            full_id=node.get("fullId", ""),
            element_id=element_id,
            subsystem_id=subsystem_id,
            name=self.text(node, "name") or "",
            optional=self.flag(node, "isOptional"),
            default_enabled=self.flag(node, "defaultEnabledValue", True),
            optional_by_configuration=tuple(optional_links),
            mci_origin=self.text(node, "mciDataOrigin") or "",
            maturity=self.text(node, "massMaturityLevel"),
            mass_margin=self.number(node, "massMargin"),
            power_margin=self.number(node, "powerMargin"),
            manual_mass_kg=self.number(node, "manualMass"),
            manual_cog=self.point(node, "manualCog"),
            manual_inertia=self.inertia(node, "manualInertiaMatrix"),
            can_have_custom_power=self.flag(node, "canHaveCustomPower"),
            temperatures=Temperatures(
                operating_min_c=self.number(node, "temperatureOpMin"),
                operating_max_c=self.number(node, "temperatureOpMax"),
                survival_min_c=self.number(node, "temperatureNOpMin"),
                survival_max_c=self.number(node, "temperatureNOpMax"),
            ),
            power_modes=self.power_modes(node),
            shapes=self.shapes(node),
        )

    # ---- occurrences ------------------------------------------------------------------------

    def mappings(self, node: ET.Element, tag: str, kind: str) -> tuple[PowerMapping, ...]:
        out = []
        for item in self.items(node, tag):
            if item.tag != kind or item.get("ref"):
                continue
            out.append(
                PowerMapping(
                    mode_id=item.get("id", ""),
                    power_mode_full_id=self.ref_child(item, "powerMode"),
                    custom_power_w=self.number(item, "customPower"),
                    custom_dissipation_w=self.number(item, "customDissipation"),
                )
            )
        return tuple(out)

    def tank_contents(self, node: ET.Element) -> tuple[TankContent, ...]:
        out = []
        for item in self.items(node, "tankContents"):
            if item.tag != "TankContent" or item.get("ref"):
                continue
            values = []
            for value in self.items(item, "tankContentValues"):
                if value.tag != "TankContentValue" or value.get("ref"):
                    continue
                filling = self.number(value, "fillingPercentage")
                if filling is not None:
                    values.append((value.get("id", ""), filling))
            out.append(
                TankContent(
                    full_id=item.get("fullId", ""),
                    tank_object_full_id=self.ref_child(item, "tank") or "",
                    default_filling=self.number(item, "defaultFillingPercentage"),
                    filling_by_configuration=tuple(values),
                )
            )
        return tuple(out)

    def occurrence(
        self, node: ET.Element, element_id: str, subsystem_id: str, path: tuple[str, ...]
    ) -> Occurrence | None:
        unit = self.ref_child(node, "unit")
        if unit is None or unit not in self.index:
            self.problems.append(
                _problem(
                    Severity.WARNING,
                    "IDM_REF_UNRESOLVED",
                    "An equipment occurrence refers to an equipment that is not in the model.",
                    path=node.get("fullId", "?"),
                    hint="The occurrence is left out; save the model again in IDM-CIC.",
                )
            )
            return None
        return Occurrence(
            full_id=node.get("fullId", ""),
            equipment_full_id=unit,
            element_id=element_id,
            subsystem_id=subsystem_id,
            assembly_path=path,
            thermal_module_full_id=self.ref_child(node, "thermalModule"),
            element_mappings=self.mappings(
                node, "elementToEquipmentPowerModes", "ElementToEquipmentPowerMode"
            ),
            system_mappings=self.mappings(
                node, "systemToEquipmentPowerModes", "SystemToEquipmentPowerMode"
            ),
            tank_contents=self.tank_contents(node),
        )

    def walk(
        self, node: ET.Element, element_id: str, subsystem_id: str, path: tuple[str, ...]
    ) -> Iterator[Occurrence]:
        if node.tag in _EQUIPMENT_TAGS:
            found = self.occurrence(node, element_id, subsystem_id, path)
            if found is not None:
                yield found
        elif node.tag in _ASSEMBLY_TAGS:
            unit = self.ref_child(node, "unit") or ""
            for child in self.items(node, "unitOccurrences"):
                yield from self.walk(child, element_id, subsystem_id, (*path, unit))
        else:
            self.ignore(node.tag)


def _index(root: ET.Element) -> dict[str, ET.Element]:
    """Every object that is defined here (has a `fullId` and is not a reference)."""
    out: dict[str, ET.Element] = {}
    for node in root.iter():
        full = node.get("fullId")
        if full is not None and node.get("ref") is None and full not in out:
            out[full] = node
    return out


def _version_tuple(text: str) -> tuple[int, ...]:
    parts = []
    for piece in text.split("."):
        if not piece.isdigit():
            break
        parts.append(int(piece))
    return tuple(parts)


def build_model(root: ET.Element, source_name: str, sha256: str) -> IdmRead:
    data = root.find("IdmData")
    system = data.find("MainSystem") if data is not None else None
    if root.tag != "IDM" or data is None or system is None:
        error = _problem(
            Severity.ERROR,
            "IDM_STRUCTURE_INVALID",
            "The model does not have the expected structure (IDM, IdmData, MainSystem).",
            hint="The file may be an archive of something else, or a different format version.",
        )
        return IdmRead(None, (error,))
    reader = _Reader(index=_index(root))
    file_version = data.get("version", "")
    if _version_tuple(file_version)[:2] > SPEC_MAJOR_MINOR:
        reader.problems.append(
            _problem(
                Severity.WARNING,
                "IDM_VERSION_NEWER",
                "The file was saved by a newer version of IDM-CIC than the format this tool "
                "was written for.",
                hint="Objects the tool does not know are left out and listed in the summary.",
            )
        )

    subsystems = tuple(
        Subsystem(node.get("id", ""), node.get("fullId", ""), reader.text(node, "name") or "")
        for node in reader.items(system, "subsystems")
        if node.tag == "Subsystem" and not node.get("ref")
    )

    elements: list[Element] = []
    equipment: list[Equipment] = []
    assemblies: list[Assembly] = []
    occurrences: list[Occurrence] = []
    seen: set[str] = set()
    for el in reader.items(system, "elements"):
        if el.tag != "Element" or el.get("ref"):
            continue
        element_id = el.get("id", "")
        related: list[RelatedSubsystem] = []
        for rs in reader.items(el, "relatedSubsystems"):
            if rs.get("ref"):
                continue
            subsystem_id = rs.get("id", "")
            related.append(
                RelatedSubsystem(
                    element_id=element_id,
                    subsystem_id=subsystem_id,
                    forced_mass_kg=reader.number(rs, "forcedMass"),
                    forced_mass_margin=reader.number(rs, "forcedMassMargin"),
                )
            )
            for unit in reader.items(rs, "units"):
                if unit.get("ref"):
                    continue
                if unit.tag == "Equipment":
                    equipment.append(reader.equipment(unit, element_id, subsystem_id))
                elif unit.tag == "Assembly":
                    assemblies.append(
                        Assembly(
                            unit.get("fullId", ""),
                            element_id,
                            subsystem_id,
                            reader.text(unit, "name") or "",
                        )
                    )
                else:
                    reader.problems.append(
                        _problem(
                            Severity.WARNING,
                            "IDM_UNIT_KIND_UNKNOWN",
                            "A unit of a kind this tool does not know is left out.",
                            path=unit.get("fullId", "?"),
                            hint="Only equipment and assemblies are read.",
                        )
                    )
            for placed in reader.items(rs, "unitInstances"):
                for found in reader.walk(placed, element_id, subsystem_id, ()):
                    if found.full_id not in seen:
                        seen.add(found.full_id)
                        occurrences.append(found)
        modes = tuple(
            ElementMode(
                node.get("id", ""),
                node.get("fullId", ""),
                reader.text(node, "name") or "",
                element_id,
            )
            for node in reader.items(el, "elementModes")
            if node.tag == "ElementMode" and not node.get("ref")
        )
        thermal = tuple(
            ThermalModule(
                node.get("id", ""),
                node.get("fullId", ""),
                reader.text(node, "name") or "",
                element_id,
            )
            for node in reader.items(el, "thermalModules")
            if node.tag == "ThermalModule" and not node.get("ref")
        )
        elements.append(
            Element(
                id=element_id,
                full_id=el.get("fullId", ""),
                name=reader.text(el, "name") or "",
                mass_target_kg=reader.number(el, "massTarget"),
                mass_margin=reader.number(el, "massMargin"),
                power_margin=reader.number(el, "powerMargin"),
                forced_propellant_kg=reader.number(el, "forcedPropellantMass"),
                forced_propellant_margin=reader.number(el, "forcedPropellantMassMargin"),
                related=tuple(related),
                modes=modes,
                thermal_modules=thermal,
            )
        )

    system_modes = tuple(
        SystemMode(
            id=node.get("id", ""),
            full_id=node.get("fullId", ""),
            name=reader.text(node, "name") or "",
            duty_cycle=reader.number(node, "dutyCycle"),
            element_mode_full_ids=tuple(
                ref for ref in (reader.ref_of(m) for m in reader.items(node, "elementModes")) if ref
            ),
        )
        for node in reader.items(system, "systemModes")
        if node.tag == "SystemMode" and not node.get("ref")
    )

    by_full_id = {e.full_id: e.id for e in elements}
    configurations = tuple(
        Configuration(
            id=node.get("id", ""),
            full_id=node.get("fullId", ""),
            name=reader.text(node, "name") or "",
            enabled_element_ids=tuple(
                by_full_id[ref]
                for ref in (reader.ref_of(m) for m in reader.items(node, "enabledElements"))
                if ref in by_full_id
            ),
        )
        for node in reader.items(system, "configurations")
        if node.tag == "Configuration" and not node.get("ref")
    )

    known_equipment = {e.full_id for e in equipment}
    kept: list[Occurrence] = []
    for occ in occurrences:
        if occ.equipment_full_id in known_equipment:
            kept.append(occ)
        else:  # an occurrence of an assembly or of something the reader did not take
            reader.ignore("occurrence of an unknown unit")
    stale = tuple(
        reader.text(f, "propertyName") or ""
        for f in reader.items(system, "formulas")
        if f.tag == "Formula"
        and (not reader.flag(f, "isValid", True) or not reader.flag(f, "isConsistent", True))
    )
    custom: list[CustomProperty] = []
    for definition in reader.items(system, "additionalPropertyDefinitions"):
        if definition.tag == "AdditionalPropertyDefinition" and not definition.get("ref"):
            custom.append(
                CustomProperty(
                    "", reader.text(definition, "name") or definition.get("id") or "", None
                )
            )

    model = IdmModel(
        source_name=Path(source_name).name,
        sha256=sha256,
        file_version=file_version,
        project_name=reader.text(system, "projectName"),
        comment=reader.text(system, "comment"),
        system_version=reader.text(system, "systemVersion"),
        last_modification=reader.when(system, "lastModification"),
        propellant_margin=reader.number(system, "propellantMassMargin"),
        subsystems=subsystems,
        elements=tuple(elements),
        equipment=tuple(equipment),
        assemblies=tuple(assemblies),
        occurrences=tuple(kept),
        system_modes=system_modes,
        configurations=configurations,
        custom_properties=tuple(custom),
        stale_formula_targets=tuple(sorted(t for t in stale if t)),
        ignored_counts=tuple(sorted(reader.ignored.items())),
        frames=reader.frames(),
    )
    return IdmRead(model, tuple(reader.problems))


def read_idm(path: Path) -> IdmRead:
    """Read a model file. Never raises for a bad file: the reason is in `problems`."""
    try:
        packed = read_model_bytes(path)
        root = parse_model(packed.data)
    except IdmReadError as error:
        return IdmRead(None, (error.problem,))
    return build_model(root, path.name, packed.sha256)
