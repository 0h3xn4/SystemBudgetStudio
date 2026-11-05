"""Components found in an IDM-CIC model, and the skeletons written for them (D-254).

What the model says is the kind of an equipment (`classify.py`), its mass, its power modes and its
tanks. What the simulation models need besides is not in the model: the torque of a wheel, the
specific impulse of a thruster, the capacity of a battery cell, the efficiency of a solar cell.
Those numbers are never invented. They come from the user's **component library**,
`idm/components.yaml`: one entry for each equipment (matched by name) with the values of the data
sheet, each with its source. Where the library has no value, the skeleton has a placeholder
(`source: TBD`), so the budget that needs it says n/a and the project check lists what is missing,
as for any unfinished project.

Skeletons are written into `config/pointing.yaml` (actuators), `config/propulsion.yaml` (systems)
and `config/power_system.yaml` (battery and solar array). The files are the user's: a file that does
not exist is created; a file that exists only gets the entries it does not have yet (a wheel, a
system) and is never changed otherwise; an entry the user deleted is not put back; a battery or a
solar array of an existing power system is never touched. Nothing here reads the model file; the
caller gives the detections.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from budget_core.idm.classify import (
    BATTERY,
    MAGNETORQUER,
    REACTION_WHEEL,
    SOLAR_ARRAY,
    THRUSTER,
    Detection,
    fold,
)
from budget_core.io.project_loader import model_to_data
from budget_core.io.yamlio import dump_yaml
from budget_core.model import (
    Actuator,
    Battery,
    PointingConfig,
    PowerSystem,
    PropulsionConfig,
    PropulsionSystem,
    SolarArray,
    Sourced,
)
from budget_core.model.power_system import ArrayFace, PowerLimits
from budget_core.problems import Problem, Severity

LIBRARY_PATH = "idm/components.yaml"
POINTING_PATH = "config/pointing.yaml"
PROPULSION_PATH = "config/propulsion.yaml"
POWER_PATH = "config/power_system.yaml"

ACTUATOR_KINDS = (REACTION_WHEEL, MAGNETORQUER)
SCAFFOLD_KINDS = (*ACTUATOR_KINDS, THRUSTER, BATTERY, SOLAR_ARRAY)

# a thruster is chemical or electric: only these words say which (the library can say it too)
_ELECTRIC = ("electric", "electrique", "ion", "hall", "plasma", "ppt", "arcjet", "resistojet")
_CHEMICAL = (
    "hydrazine",
    "chemical",
    "monopropellant",
    "bipropellant",
    "cold gas",
    "xenon-free",
    "nitrogen",
    "mmh",
)


@dataclass(frozen=True)
class LibraryEntry:
    """What the user's library says about the equipment whose name matches `match`."""

    match: str  # a pattern (`*` and `?`), accents and case ignored
    kind: str | None  # overrides the kind the name suggests
    values: dict[str, Any]  # fields of the model entry: a sourced number or a plain value


@dataclass
class Library:
    entries: list[LibraryEntry] = field(default_factory=list)
    problems: list[Problem] = field(default_factory=list)

    def find(self, equipment_name: str) -> LibraryEntry | None:
        name = fold(equipment_name)
        return next((e for e in self.entries if fnmatch.fnmatchcase(name, fold(e.match))), None)


def _problem(code: str, path: str) -> Problem:
    from budget_core.idm.mapping import finding

    return finding(Severity.WARNING, code, path)


def parse_library(data: Any) -> Library:
    """The entries of a loaded library file; an entry that is not valid is skipped and named."""
    library = Library()
    if not isinstance(data, dict) or not isinstance(data.get("components", []), list):
        library.problems.append(_problem("IDM_COMPONENT_LIBRARY_INVALID", "components"))
        return library
    for index, raw in enumerate(data.get("components") or []):
        where = f"components[{index}]"
        if not isinstance(raw, dict) or not isinstance(raw.get("match"), str) or not raw["match"]:
            library.problems.append(_problem("IDM_COMPONENT_LIBRARY_INVALID", where))
            continue
        kind = raw.get("kind")
        values = raw.get("values") or {}
        if (kind is not None and kind not in SCAFFOLD_KINDS) or not isinstance(values, dict):
            library.problems.append(_problem("IDM_COMPONENT_LIBRARY_INVALID", where))
            continue
        library.entries.append(LibraryEntry(raw["match"], kind, dict(values)))
    return library


def read_library_text(text: str | None) -> Library:
    """The library from the text of the file (None: there is none)."""
    if text is None:
        return Library()
    from budget_core.io.yamlio import load_yaml_text

    try:
        return parse_library(load_yaml_text(text).data)
    except Exception:  # a file that is not YAML: one finding, the rest of the import goes on
        library = Library()
        library.problems.append(_problem("IDM_COMPONENT_LIBRARY_INVALID", "file"))
        return library


def read_library(root: Path) -> Library:
    path = root / LIBRARY_PATH
    if not path.is_file():
        return Library()
    try:
        return read_library_text(path.read_text(encoding="utf-8-sig"))
    except OSError, UnicodeDecodeError:
        library = Library()
        library.problems.append(_problem("IDM_COMPONENT_LIBRARY_INVALID", "file"))
        return library


TEMPLATE = """\
# Your component library for imports of IDM-CIC models (written once by `budget import idm`;
# the import never changes it afterwards).
#
# An IDM-CIC model has no data-sheet values: the torque of a wheel, the specific impulse of a
# thruster, the capacity of a battery cell... Enter them here once, with their source, and every
# model you import gets them. Where a value is missing the imported project has a placeholder
# (source: TBD) and the budget that needs it says n/a until you enter it.
#
# components:
#   - match: "Inertia Wheel*"     # a pattern for the equipment name (* and ?), case and accents
#                                   # ignored
#     kind: reaction_wheel        # optional: reaction_wheel, magnetorquer, thruster, battery,
#                                 # solar_array
#     values:
#       max_torque_nm: {value: 0.02, source: "Data sheet XYZ, table 3"}
#       momentum_capacity_nms: {value: 0.5, source: "Data sheet XYZ, table 3"}
#
#   - match: "Thruster*"
#     values:
#       type: chemical                    # chemical or electric
#       isp_s: {value: 220, source: "Data sheet ABC, section 2"}
#       thrust_n: {value: 1.0, source: "Data sheet ABC, section 2"}
#
# What each kind takes:
#   reaction_wheel, magnetorquer: max_torque_nm, max_rate_deg_s, momentum_capacity_nms, slew_power_w
#   thruster: type, isp_s, thrust_n, power_w
#   battery: cell_capacity_ah, cell_nominal_voltage_v, cells_in_series, cells_in_parallel,
#            charge_efficiency_ratio, discharge_efficiency_ratio, annual_capacity_fade_ratio,
#            initial_soc_ratio
#   solar_array: cell_area_m2, cell_efficiency_ratio, solar_irradiance_wm2, reference_temperature_k,
#            cell_temperature_k, efficiency_temp_coeff_perk, packing_loss_ratio,
#            harness_loss_ratio, annual_degradation_ratio, faces (a list of name, normal_body,
#            strings, cells_per_string)
# A number has the form {value: 1.5, source: "where it comes from"}; the counts and `type` are
# plain.
components: []
"""


# ---- the skeletons -----------------------------------------------------------------------------
def _tbd(note: str = "") -> Sourced:
    return Sourced(value=None, source="TBD", note=note)


def _sourced_fields(cls: type[Any], values: dict[str, Any]) -> dict[str, Any]:
    """The library values that belong to `cls`: the others are left out (named by the caller)."""
    return {k: v for k, v in values.items() if k in cls.model_fields}


@dataclass
class Skeletons:
    """What to write: the entries by file, and what the library or the model could not give."""

    actuators: dict[str, dict[str, Any]] = field(default_factory=dict)
    systems: dict[str, dict[str, Any]] = field(default_factory=dict)
    power_system: dict[str, Any] | None = None
    sources: dict[str, str] = field(default_factory=dict)  # entry key -> equipment full id
    problems: list[Problem] = field(default_factory=list)


def slug_id(text: str) -> str:
    from budget_core.idm.mapping import slug

    return slug(text).lower()


def _thruster_type(name: str, entry: LibraryEntry | None) -> str | None:
    given = (entry.values.get("type") if entry else None) or None
    if given in ("chemical", "electric"):
        return str(given)
    folded = fold(name)
    from budget_core.idm.classify import _has_word

    if any(_has_word(folded, w) for w in _ELECTRIC):
        return "electric"
    if any(_has_word(folded, w) for w in _CHEMICAL):
        return "chemical"
    return None


def build_skeletons(
    detections: list[tuple[str, str, str, Detection | None]],
    library: Library,
    phases: list[str],
    expendable_ids: list[str],
    source: str,
) -> Skeletons:
    """`detections` are (equipment full id, equipment name, kind, detection) of the equipment
    found in the model, the kind being the library's when it names one. Returns the entries."""
    out = Skeletons()
    note = f"The IDM-CIC model gives no value for this ({source})."
    battery_taken = array_taken = False
    battery: dict[str, Any] = {}
    array: dict[str, Any] = {}
    for full_id, name, kind, _found in detections:
        entry = library.find(name)
        values = entry.values if entry else {}
        key = slug_id(name)
        try:
            if kind in ACTUATOR_KINDS:
                actuator = Actuator(
                    name=name,
                    max_torque_nm=_tbd(note),
                    **{},
                )
                data = {**model_to_data(actuator), **_given(Actuator, values)}
                Actuator.model_validate(data)
                out.actuators[key] = data
                out.sources[f"{POINTING_PATH}:{key}"] = full_id
            elif kind == THRUSTER:
                kind_of = _thruster_type(name, entry)
                if kind_of is None:
                    out.problems.append(_problem("IDM_COMPONENT_NEEDS_TYPE", full_id))
                    continue
                system = PropulsionSystem(
                    name=name,
                    type=kind_of,  # type: ignore[arg-type]
                    isp_s=_tbd(note),
                    propellant=expendable_ids[0] if len(expendable_ids) == 1 else None,
                )
                data = {**model_to_data(system), **_given(PropulsionSystem, values)}
                data["type"] = kind_of
                PropulsionSystem.model_validate(data)
                out.systems[key] = data
                out.sources[f"{PROPULSION_PATH}:{key}"] = full_id
            elif kind == BATTERY and not battery_taken:
                battery_taken = True
                battery = {**_battery_data(phases, note), **_given(Battery, values)}
                Battery.model_validate(battery)
                out.sources[f"{POWER_PATH}:battery"] = full_id
            elif kind == SOLAR_ARRAY and not array_taken:
                array_taken = True
                array = {**_array_data(note), **_given(SolarArray, values)}
                SolarArray.model_validate(array)
                out.sources[f"{POWER_PATH}:solar_array"] = full_id
        except ValidationError, ValueError:
            out.problems.append(_problem("IDM_COMPONENT_LIBRARY_INVALID", full_id))
    if battery or array:
        out.power_system = _power_system(battery, array, phases, note)
    return out


def _given(cls: type[Any], values: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in values.items() if k in cls.model_fields}


def _battery_data(phases: list[str], note: str) -> dict[str, Any]:
    battery = Battery(
        cell_capacity_ah=_tbd(note),
        cell_nominal_voltage_v=_tbd(note),
        cells_in_series=1,  # a count has no placeholder: one cell, until the library says
        cells_in_parallel=1,
        charge_efficiency_ratio=_tbd(note),
        discharge_efficiency_ratio=_tbd(note),
        annual_capacity_fade_ratio=_tbd(note),
        initial_soc_ratio=_tbd(note),
        max_dod_ratio={p: _tbd(note) for p in phases},
    )
    return model_to_data(battery)


def _array_data(note: str) -> dict[str, Any]:
    array = SolarArray(
        faces=[],
        solar_irradiance_wm2=_tbd(note),
        cell_area_m2=_tbd(note),
        cell_efficiency_ratio=_tbd(note),
        reference_temperature_k=_tbd(note),
        cell_temperature_k=_tbd(note),
        efficiency_temp_coeff_perk=_tbd(note),
        packing_loss_ratio=_tbd(note),
        harness_loss_ratio=_tbd(note),
        annual_degradation_ratio=_tbd(note),
    )
    data = model_to_data(array)
    return data


def _power_system(
    battery: dict[str, Any], array: dict[str, Any], phases: list[str], note: str
) -> dict[str, Any]:
    """A whole power system file: the part found, a placeholder skeleton for the other part."""
    system = PowerSystem(
        design_life_yr=_tbd(note),
        solar_array=SolarArray.model_validate(array or _array_data(note)),
        battery=Battery.model_validate(battery or _battery_data(phases, note)),
        limits=PowerLimits(peak_power_w=_tbd(note)),
    )
    return model_to_data(system)


def new_file_text(data: dict[str, Any]) -> str:
    return dump_yaml(data)


__all__ = [
    "Library",
    "LibraryEntry",
    "Skeletons",
    "build_skeletons",
    "parse_library",
    "read_library",
    "read_library_text",
    "slug_id",
]

# kept for the importer: the models a skeleton is checked against
_MODELS = (PointingConfig, PropulsionConfig, ArrayFace)
