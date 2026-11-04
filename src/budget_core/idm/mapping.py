"""Map a typed IDM-CIC model onto project data (decisions D-240 to D-243).

A pure function: the same model and options always give the same data, in a fixed order. The
result is *data* (plain dictionaries in the form of the project files) plus the findings that say
what could not be mapped and why. Nothing is estimated: a value the model does not give is left
out, or is a placeholder (`source: TBD`) where the project format has one, and a unit whose mass
cannot be known is not written but listed.

Rules (see docs/models/idm-import.md):

* one project unit per *physical* occurrence; its id is a slug of the occurrence's `fullId`;
* mass is the raw mass of the equipment; the margin is its maturity class (`--margins raw`) or
  is applied here and the class has no margin (`--margins applied`), never both;
* a power mode keeps its power as average and peak (the model has one number) with the peak
  marked as an estimate; the heat share is dissipation / power;
* a configuration becomes a mission phase; the unit lists the phases it is enabled in;
* a tank becomes an expendable whose mass per phase is capacity x filling.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from budget_core.idm.geometry import GeometryError, Placement, occurrence_properties
from budget_core.idm.model import Equipment, IdmModel, Occurrence, PowerMapping, TankContent
from budget_core.io.project_loader import model_to_data
from budget_core.model import (
    Expendable,
    Inertia,
    MassProperties,
    SpacecraftMode,
    TemperatureLimits,
    Unit,
)
from budget_core.model import (
    PowerMode as UnitPowerMode,
)
from budget_core.model.annotations import ProvenanceEntry
from budget_core.problems import Problem, Severity
from budget_core.reports.thermal_report import ABSOLUTE_ZERO_OFFSET_K as CELSIUS_OFFSET_K

MARGINS = ("raw", "applied")
MASS_PROPERTIES = ("geometry", "none")
REFERENCE_PHASE = "reference"
PASSIVE_MODE = "Passive"
UNPLACED_NODE = "idm_unplaced"
CLASS_PREFIX = "idm_"

# The margin that each maturity level stands for. The file also stores the margin itself; this
# table is used only when that number is missing.
_LEVEL_MARGIN = {
    "NoMargin_0": 0.0,
    "FullyDeveloped_5": 0.05,
    "ToBeModified_10": 0.10,
    "Margin_15": 0.15,
    "ToBeDeveloped_20": 0.20,
}


@dataclass(frozen=True)
class ImportOptions:
    margins: str = "raw"  # "raw": the project applies its margin classes; "applied": values here
    bus: str = "main"  # the power bus every imported unit is on
    mass_properties: str = "geometry"  # "geometry": centre of gravity and inertia (D-245); "none"


@dataclass(frozen=True)
class ModeEntry:
    """One row of the mode map: what an IDM-CIC system mode becomes in the project."""

    mode: str | None  # spacecraft mode id (file name); None: the system mode is skipped
    name: str  # name of the spacecraft mode


@dataclass
class Mapped:
    units: dict[str, dict[str, Any]] = field(default_factory=dict)
    unit_keys: dict[str, str] = field(default_factory=dict)  # unit id -> occurrence full id
    unit_equipment: dict[str, str] = field(default_factory=dict)  # unit id -> equipment full id
    modes: dict[str, dict[str, Any]] = field(default_factory=dict)
    mode_system: dict[str, str] = field(default_factory=dict)  # mode id -> system mode id
    expendables: dict[str, dict[str, Any]] = field(default_factory=dict)
    expendable_keys: dict[str, str] = field(default_factory=dict)  # id -> tank content full id
    margin_classes: dict[str, dict[str, Any]] = field(default_factory=dict)
    thermal_nodes: dict[str, dict[str, Any]] = field(default_factory=dict)
    phases: list[str] = field(default_factory=list)
    mode_map: dict[str, ModeEntry] = field(default_factory=dict)
    findings: list[Problem] = field(default_factory=list)


def slug(text: str) -> str:
    """An id made of ASCII letters, digits, `-` and `_` that starts with a letter or digit."""
    cleaned = "".join(
        c if c.isascii() and (c.isalnum() or c in "-_") else "-" for c in text.replace(".", "-")
    )
    cleaned = cleaned.strip("-_") or "x"
    return cleaned if cleaned[0].isalnum() else "x" + cleaned


def _unique(base: str, taken: set[str]) -> str:
    candidate, n = base, 2
    while candidate in taken:
        candidate = f"{base}-{n}"
        n += 1
    taken.add(candidate)
    return candidate


def _percent(value: float | None) -> str:
    if value is None:
        return "tbd"
    return f"{round(value * 100.0, 6):g}".replace(".", "p").replace("-", "m")


def _selector(name: str) -> str:
    """A power mode name as it can appear between brackets in a provenance path."""
    cleaned = name.replace("[", "(").replace("]", ")").strip()
    return cleaned or "mode"


def finding(severity: Severity, code: str, path: str = "") -> Problem:
    from budget_core.problem_catalogue import describe

    info = describe(code)
    assert info is not None, code
    return Problem(severity, code, info.title, path=path, hint=info.fix)


# ---- mass --------------------------------------------------------------------------------------


def equipment_mass_kg(eq: Equipment) -> tuple[float | None, str]:
    """The raw (unmargined) mass of an equipment and how it was found; None when it is unknown."""
    if eq.mci_origin == "ManualInput":
        return eq.manual_mass_kg, "entered in the model"
    if eq.mci_origin == "FromGeometry":
        total = 0.0
        for shape in eq.shapes:
            if shape.mass_type != "Total" or shape.mass_total_kg is None:
                return None, "needs the shape geometry"
            total += shape.mass_total_kg
        return total, "sum of the shape masses (mass type Total)"
    return None, "unknown origin of the mass"


def _margin(eq: Equipment) -> float | None:
    if eq.mass_margin is not None:
        return eq.mass_margin
    return _LEVEL_MARGIN.get(eq.maturity or "")


# ---- the mapping -------------------------------------------------------------------------------


@dataclass
class _Context:
    model: IdmModel
    options: ImportOptions
    out: Mapped
    equipment: dict[str, Equipment]
    element_names: dict[str, str]
    subsystem_names: dict[str, str]
    assembly_names: dict[str, str]
    reported: set[tuple[str, str]] = field(default_factory=set)

    @property
    def source(self) -> str:
        return f"IDM-CIC model {self.model.source_name}, revision {self.model.sha256[:12]}"

    def add(self, severity: Severity, code: str, path: str) -> None:
        if (code, path) in self.reported:  # one finding per object, not one per occurrence
            return
        self.reported.add((code, path))
        self.out.findings.append(finding(severity, code, path))


def _class_for(ctx: _Context, mass_margin: float | None, power_margin: float | None) -> str:
    """The maturity class for an equipment, created on first use."""
    if ctx.options.margins == "applied":
        name = f"{CLASS_PREFIX}applied"
        if name not in ctx.out.margin_classes:
            zero = {"value": 0.0, "source": ctx.source, "note": "IDM-CIC values taken with margins"}
            ctx.out.margin_classes[name] = {
                "power_margin_ratio": dict(zero),
                "mass_margin_ratio": dict(zero),
            }
        return name
    name = f"{CLASS_PREFIX}m{_percent(mass_margin)}_p{_percent(power_margin)}"
    if name not in ctx.out.margin_classes:
        ctx.out.margin_classes[name] = {
            "power_margin_ratio": _margin_value(ctx, power_margin, "equipment power margin"),
            "mass_margin_ratio": _margin_value(ctx, mass_margin, "equipment mass margin"),
        }
    return name


def _margin_value(ctx: _Context, value: float | None, what: str) -> dict[str, Any]:
    if value is None:
        return {"value": None, "source": "TBD", "note": f"The model gives no {what}."}
    return {"value": value, "source": ctx.source, "note": what}


def _present(model: IdmModel, occ: Occurrence, eq: Equipment, phase: str, ref: str) -> bool:
    if phase == ref:
        return (not eq.optional) or eq.default_enabled
    config = next(c for c in model.configurations if c.id == phase)
    if occ.element_id not in config.enabled_element_ids:
        return False
    if not eq.optional:
        return True
    link = dict(eq.optional_by_configuration).get(phase)
    return eq.default_enabled if link is None else link


def _phase_names(model: IdmModel) -> tuple[str, list[str]]:
    if not model.configurations:
        return REFERENCE_PHASE, []
    ref = REFERENCE_PHASE
    ids = {c.id for c in model.configurations}
    while ref in ids:
        ref = f"{CLASS_PREFIX}{ref}"
    return ref, [ref, *[c.id for c in model.configurations]]


def _temperature_limits(ctx: _Context, eq: Equipment) -> TemperatureLimits | None:
    t = eq.temperatures

    def band(low: float | None, high: float | None) -> tuple[float, float] | None:
        if low is None or high is None or low >= high:
            return None
        return low + CELSIUS_OFFSET_K, high + CELSIUS_OFFSET_K

    operating = band(t.operating_min_c, t.operating_max_c)
    survival = band(t.survival_min_c, t.survival_max_c)
    if operating and survival and not (survival[0] <= operating[0] and survival[1] >= operating[1]):
        survival = None
        ctx.add(Severity.INFO, "IDM_TEMPERATURE_IGNORED", eq.full_id)
    elif (operating is None or survival is None) and any(
        v is not None and v != 0.0
        for v in (t.operating_min_c, t.operating_max_c, t.survival_min_c, t.survival_max_c)
    ):
        ctx.add(Severity.INFO, "IDM_TEMPERATURE_IGNORED", eq.full_id)
    if operating is None and survival is None:
        return None
    return TemperatureLimits(
        operating_min_k=operating[0] if operating else None,
        operating_max_k=operating[1] if operating else None,
        survival_min_k=survival[0] if survival else None,
        survival_max_k=survival[1] if survival else None,
    )


def _unit_modes(
    ctx: _Context, occ: Occurrence, eq: Equipment, power_factor: float
) -> tuple[list[UnitPowerMode], dict[str, str], dict[str, ProvenanceEntry], bool]:
    """The power modes of a unit, the name for each IDM power mode full id, the provenance of the
    peak powers, and whether every mode could be written."""
    modes: list[UnitPowerMode] = []
    names: dict[str, str] = {}
    prov: dict[str, ProvenanceEntry] = {}
    taken: set[str] = set()
    ok = True

    def add(name: str, power: float | None, dissipation: float | None, full_id: str) -> None:
        nonlocal ok
        if power is None:
            ctx.add(Severity.WARNING, "IDM_POWER_UNRESOLVED", full_id)
            ok = False
            return
        unique = _unique(_selector(name), taken)
        if dissipation is None:
            ratio: float | None = None
        elif power == 0.0 and dissipation == 0.0:
            ratio = 1.0  # no power, no heat: any share gives the same (zero) heat
        elif power > 0.0 and 0.0 <= dissipation <= power:
            ratio = dissipation / power
        else:
            ratio = None
            ctx.add(Severity.WARNING, "IDM_DISSIPATION_UNRESOLVED", full_id)
        watts = power * power_factor
        modes.append(
            UnitPowerMode(
                name=unique,
                avg_power_w=watts,
                peak_power_w=watts,
                duty_cycle_ratio=1.0,
                heat_dissipation_ratio=ratio,
            )
        )
        names[full_id] = unique
        prov[f"modes[{unique}].peak_power_w"] = ProvenanceEntry(
            source=ctx.source,
            note="The model gives one power value per mode; it is used as average and as peak.",
            status="estimate",
        )

    for pm in eq.power_modes:
        add(pm.name or pm.id, pm.power_w, pm.dissipation_w, pm.full_id)
    # modes created for the custom values of this occurrence
    for mapping in (*occ.element_mappings, *occ.system_mappings):
        if mapping.power_mode_full_id is None and mapping.custom_power_w is not None:
            add(
                f"custom {mapping.mode_id}",
                mapping.custom_power_w,
                mapping.custom_dissipation_w,
                f"{occ.full_id}/{mapping.mode_id}",
            )
    return modes, names, prov, ok


def _passive_mode() -> UnitPowerMode:
    return UnitPowerMode(
        name=PASSIVE_MODE,
        avg_power_w=0.0,
        peak_power_w=0.0,
        duty_cycle_ratio=1.0,
        heat_dissipation_ratio=1.0,
    )


_GEOMETRY_NOTE = (
    "Computed from the placements and shapes of the model with conventions inferred from the "
    "model itself (DV-IDM5); not checked against IDM-CIC."
)


def _mass_properties(
    ctx: _Context, placement: Placement, occ: Occurrence, eq: Equipment
) -> tuple[MassProperties | None, dict[str, ProvenanceEntry]]:
    try:
        found = occurrence_properties(placement, occ, eq)
    except GeometryError as error:
        ctx.add(Severity.INFO, error.code, occ.full_id)
        return None, {}
    if found is None:
        return None, {}
    entry = ProvenanceEntry(source=ctx.source, note=_GEOMETRY_NOTE, status="estimate")
    prov = {"mass_properties.position_m": entry}
    ixx, iyy, izz, ixy, ixz, iyz = found.inertia
    try:
        inertia: Inertia | None = Inertia(
            ixx_kgm2=ixx, iyy_kgm2=iyy, izz_kgm2=izz, ixy_kgm2=ixy, ixz_kgm2=ixz, iyz_kgm2=iyz
        )
    except ValidationError, ValueError:
        inertia = None
        ctx.add(Severity.INFO, "IDM_GEOMETRY_SHAPE", occ.full_id)
    if inertia is not None:
        for name in ("ixx", "iyy", "izz", "ixy", "ixz", "iyz"):
            prov[f"mass_properties.inertia.{name}_kgm2"] = entry
    return MassProperties(position_m=list(found.position_m), inertia=inertia), prov


def map_model(
    model: IdmModel,
    options: ImportOptions,
    mode_map: dict[str, ModeEntry] | None = None,
) -> Mapped:
    out = Mapped()
    ctx = _Context(
        model=model,
        options=options,
        out=out,
        equipment={e.full_id: e for e in model.equipment},
        element_names={e.id: e.name or e.id for e in model.elements},
        subsystem_names={s.id: s.name or s.id for s in model.subsystems},
        assembly_names={a.full_id: a.name for a in model.assemblies},
    )
    ref, phases = _phase_names(model)
    out.phases = phases
    for stale in model.stale_formula_targets:
        ctx.add(Severity.WARNING, "IDM_FORMULA_STALE", stale)

    # thermal modules -> nodes (only those that a mapped unit uses are written, below)
    module_names: dict[str, tuple[str, str]] = {}
    for el in model.elements:
        for module in el.thermal_modules:
            module_names[module.full_id] = (
                slug(module.full_id),
                f"{el.name or el.id} / {module.name or module.id}",
            )

    taken: set[str] = set()
    sources_of_unit: dict[str, tuple[Occurrence, Equipment, dict[str, str]]] = {}
    placement = Placement(model)
    for occ in model.occurrences:
        eq = ctx.equipment[occ.equipment_full_id]
        present = [p for p in phases if _present(model, occ, eq, p, ref)] if phases else []
        enabled = bool(present) if phases else _present(model, occ, eq, ref, ref)
        if not enabled:
            ctx.add(Severity.INFO, "IDM_NEVER_ENABLED", occ.full_id)
            continue
        mass, how = equipment_mass_kg(eq)
        margin = _margin(eq)
        if mass is None or (options.margins == "applied" and margin is None):
            ctx.add(Severity.WARNING, "IDM_MASS_UNRESOLVED", occ.full_id)
            continue
        power_margin = eq.power_margin
        if options.margins == "applied" and power_margin is None and eq.power_modes:
            ctx.add(Severity.WARNING, "IDM_MASS_UNRESOLVED", occ.full_id)
            continue
        applied = options.margins == "applied"
        factor_m = 1.0 + (margin or 0.0) if applied else 1.0
        factor_p = 1.0 + (power_margin or 0.0) if applied else 1.0

        modes, names, prov, ok = _unit_modes(ctx, occ, eq, factor_p)
        if not ok:
            continue
        if not modes:
            modes = [_passive_mode()]
            prov[f"modes[{PASSIVE_MODE}].avg_power_w"] = ProvenanceEntry(
                source=ctx.source,
                note="The equipment has no power mode in the model, so it is treated as drawing "
                "no power.",
                status="estimate",
            )
        unit_id = _unique(slug(occ.full_id), taken)
        node = UNPLACED_NODE
        if occ.thermal_module_full_id in module_names:
            node = module_names[occ.thermal_module_full_id][0]
            out.thermal_nodes.setdefault(
                node, {"name": module_names[occ.thermal_module_full_id][1]}
            )
        elif occ.thermal_module_full_id is not None:
            ctx.add(Severity.WARNING, "IDM_REF_UNRESOLVED", occ.full_id)
        if node == UNPLACED_NODE:
            out.thermal_nodes.setdefault(
                UNPLACED_NODE, {"name": "Not on a thermal module in the IDM-CIC model"}
            )
        margin_note = (
            f"mass margin {_percent(margin)} % applied"
            if applied
            else f"mass margin {_percent(margin)} % of the equipment ({eq.maturity or 'no level'})"
        )
        prov["mass_kg"] = ProvenanceEntry(
            source=ctx.source, note=f"{how}; {margin_note}", status="sourced"
        )
        prov["*"] = ProvenanceEntry(
            source=f"{ctx.source}, {occ.full_id}",
            note="Imported by budget import idm.",
            status="sourced",
        )
        assembly = " > ".join(ctx.assembly_names.get(a, "?") for a in occ.assembly_path)
        label = occ.full_id.rsplit("_eqi.", 1)[-1].rsplit("_eqi.", 1)[-1]
        name = " / ".join(
            part
            for part in (ctx.element_names.get(occ.element_id, occ.element_id), assembly, eq.name)
            if part
        )
        properties = None
        if options.mass_properties == "geometry":
            properties, geometry_prov = _mass_properties(ctx, placement, occ, eq)
            prov.update(geometry_prov)
        try:
            unit = Unit(
                name=f"{name} [{label}]",
                subsystem=ctx.subsystem_names.get(occ.subsystem_id, occ.subsystem_id),
                mass_kg=mass * factor_m,
                mass_properties=properties,
                bus=options.bus,
                maturity=_class_for(ctx, margin, power_margin),
                modes=modes,
                phases=None if not phases or len(present) == len(phases) else [p for p in present],
                thermal_node=node,
                temperature_limits=_temperature_limits(ctx, eq),
                provenance=prov,
            )
        except ValidationError, ValueError:
            ctx.add(Severity.WARNING, "IDM_VALUE_INVALID", occ.full_id)
            continue
        out.units[unit_id] = model_to_data(unit)
        out.unit_keys[unit_id] = occ.full_id
        out.unit_equipment[unit_id] = eq.full_id
        sources_of_unit[unit_id] = (occ, eq, names)

    _map_modes(ctx, sources_of_unit, mode_map)
    _map_tanks(ctx, ref, phases)
    if out.thermal_nodes and not any(
        u.get("thermal_node") == UNPLACED_NODE for u in out.units.values()
    ):
        out.thermal_nodes.pop(UNPLACED_NODE, None)
    _not_mapped(ctx)
    return out


def _mapping_for(occ: Occurrence, ctx: _Context, system_mode_id: str) -> PowerMapping | None:
    sm = next(s for s in ctx.model.system_modes if s.id == system_mode_id)
    element_mode_ids = {
        m.full_id: m.id for el in ctx.model.elements if el.id == occ.element_id for m in el.modes
    }
    for full_id in sm.element_mode_full_ids:
        if full_id in element_mode_ids:
            wanted = element_mode_ids[full_id]
            return next((m for m in occ.element_mappings if m.mode_id == wanted), None)
    return next((m for m in occ.system_mappings if m.mode_id == system_mode_id), None)


def _map_modes(
    ctx: _Context,
    units: dict[str, tuple[Occurrence, Equipment, dict[str, str]]],
    given: dict[str, ModeEntry] | None,
) -> None:
    out = ctx.out
    taken: set[str] = set()
    result: dict[str, ModeEntry] = {}
    for sm in ctx.model.system_modes:
        entry = (given or {}).get(sm.id)
        if entry is None:
            entry = ModeEntry(mode=slug(sm.id).lower(), name=sm.name or sm.id)
        result[sm.id] = entry
    out.mode_map = result
    for sm in ctx.model.system_modes:
        entry = result[sm.id]
        if entry.mode is None:
            continue
        mode_id = _unique(entry.mode, taken)
        assignments: dict[str, str] = {}
        for unit_id in sorted(units):
            occ, eq, names = units[unit_id]
            unit_modes = {m["name"] for m in out.units[unit_id]["modes"]}
            if not eq.power_modes and not any(
                m.custom_power_w is not None for m in (*occ.element_mappings, *occ.system_mappings)
            ):
                assignments[unit_id] = PASSIVE_MODE
                continue
            mapping = _mapping_for(occ, ctx, sm.id)
            chosen: str | None = None
            if mapping is not None:
                if mapping.power_mode_full_id is not None:
                    chosen = names.get(mapping.power_mode_full_id)
                elif mapping.custom_power_w is not None:
                    chosen = names.get(f"{occ.full_id}/{mapping.mode_id}")
            if chosen is None or chosen not in unit_modes:
                ctx.add(Severity.WARNING, "IDM_POWER_UNRESOLVED", f"{occ.full_id}/{sm.id}")
                continue
            assignments[unit_id] = chosen
        if not assignments:
            continue  # nothing could be assigned: the reasons are in the findings
        mode = SpacecraftMode(
            name=entry.name,
            description=f"Imported from system mode {sm.id} of {ctx.source}.",
            assignments=assignments,
        )
        out.modes[mode_id] = model_to_data(mode)
        out.mode_system[mode_id] = sm.id


def _map_tanks(ctx: _Context, ref: str, phases: list[str]) -> None:
    out = ctx.out
    taken: set[str] = set()
    model = ctx.model
    kept = {v: k for k, v in out.unit_keys.items()}
    for occ in model.occurrences:
        if occ.full_id not in kept or not occ.tank_contents:
            continue
        eq = ctx.equipment[occ.equipment_full_id]
        for content in occ.tank_contents:
            _one_tank(ctx, occ, eq, content, ref, phases, taken)


def _one_tank(
    ctx: _Context,
    occ: Occurrence,
    eq: Equipment,
    content: TankContent,
    ref: str,
    phases: list[str],
    taken: set[str],
) -> None:
    model, options, out = ctx.model, ctx.options, ctx.out
    shape = next((s for s in eq.shapes if s.object_full_id == content.tank_object_full_id), None)
    params = dict(shape.parameters) if shape is not None else {}
    capacity = params.get("capacity")
    default = content.default_filling
    if capacity is None or default is None:
        ctx.add(Severity.WARNING, "IDM_TANK_UNRESOLVED", content.full_id)
        return
    element = next((e for e in model.elements if e.id == occ.element_id), None)
    margin = model.propellant_margin
    if element is not None and element.forced_propellant_margin is not None:
        margin = element.forced_propellant_margin
    if element is not None and element.forced_propellant_kg is not None:
        ctx.add(Severity.WARNING, "IDM_FORCED_MASS_IGNORED", element.full_id)
    by_config = dict(content.filling_by_configuration)
    eq_taken = _unique(slug(content.full_id), taken)
    masses: dict[str, float] = {}
    for phase in phases or ["all"]:
        if phases:
            present = _present(model, occ, eq, phase, ref)
            filling = default if phase == ref else by_config.get(phase, default)
        else:
            present = _present(model, occ, eq, ref, ref)
            filling = default
        mass = capacity * filling if present else 0.0
        masses[phase] = mass * (1.0 + (margin or 0.0)) if options.margins == "applied" else mass
    if options.margins == "applied":
        klass = f"{CLASS_PREFIX}applied"
        out.margin_classes.setdefault(
            klass,
            {
                "power_margin_ratio": {"value": 0.0, "source": ctx.source, "note": "applied"},
                "mass_margin_ratio": {"value": 0.0, "source": ctx.source, "note": "applied"},
            },
        )
    else:
        klass = f"{CLASS_PREFIX}propellant_m{_percent(margin)}"
        out.margin_classes.setdefault(
            klass,
            {
                "power_margin_ratio": {
                    "value": 0.0,
                    "source": ctx.source,
                    "note": "Propellant draws no power.",
                },
                "mass_margin_ratio": _margin_value(ctx, margin, "propellant mass margin"),
            },
        )
    try:
        expendable = Expendable(
            name=f"{ctx.element_names.get(occ.element_id, occ.element_id)} / {eq.name} propellant",
            subsystem=ctx.subsystem_names.get(occ.subsystem_id, occ.subsystem_id),
            maturity=klass,
            masses_kg=masses,
            provenance={
                "*": ProvenanceEntry(
                    source=f"{ctx.source}, {content.full_id}",
                    note="Mass = tank capacity x filling of the configuration.",
                    status="sourced",
                )
            },
        )
    except ValidationError, ValueError:
        ctx.add(Severity.WARNING, "IDM_TANK_UNRESOLVED", content.full_id)
        return
    out.expendables[eq_taken] = model_to_data(expendable)
    out.expendable_keys[eq_taken] = content.full_id


def _not_mapped(ctx: _Context) -> None:
    model = ctx.model
    for el in model.elements:
        if el.mass_target_kg or el.mass_margin or el.power_margin:
            ctx.add(Severity.INFO, "IDM_MARGIN_NOT_APPLIED", el.full_id)
        for related in el.related:
            if related.forced_mass_kg is not None or related.forced_mass_margin is not None:
                ctx.add(
                    Severity.WARNING,
                    "IDM_FORCED_MASS_IGNORED",
                    f"el.{el.id}_ss.{related.subsystem_id}",
                )
    for mode in model.system_modes:
        if mode.duty_cycle:
            ctx.add(Severity.INFO, "IDM_CUSTOM_DATA_UNMAPPED", mode.full_id)
    if model.custom_properties:
        ctx.add(Severity.INFO, "IDM_CUSTOM_DATA_UNMAPPED", "additionalPropertyDefinitions")
