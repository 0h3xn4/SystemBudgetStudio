"""What every problem code means: the rule, why it matters and how to resolve it (D-207).

A `Problem` says what is wrong and where; this catalogue says what the rule is. One entry per code,
written for a systems engineer, free of values from any project (the texts are the same for every
project, so they can be printed, documented and tested). `docs/PROBLEMS.md` is generated from it
(`budget problems --markdown`) and a test fails when the two differ, when a code that the tool can
raise has no entry, or when an entry has no code that the tool can raise.
"""

from __future__ import annotations

from dataclasses import dataclass

from budget_core.problems import Severity


@dataclass(frozen=True)
class ProblemInfo:
    code: str
    severity: Severity  # the usual severity (a few codes are raised at two levels)
    area: str
    title: str
    rule: str  # what the tool checks
    why: str  # why it matters
    fix: str  # how to resolve it


ERR, WARN, INFO = Severity.ERROR, Severity.WARNING, Severity.INFO

_READ = "Reading the files"
_FIELDS = "Fields and units"
_CONF = "Configuration"
_REF = "References between files"
_SCEN = "Scenarios and environment"
_MASS = "Mass budget"
_THERM = "Thermal budget"
_POWER = "Power timeline"
_LINK = "Link budget"
_IMPORT = "Unit tables (import)"
_OTHER = "Other"


def _e(
    code: str, severity: Severity, area: str, title: str, rule: str, why: str, fix: str
) -> ProblemInfo:
    return ProblemInfo(code, severity, area, title, rule, why, fix)


_ENTRIES: tuple[ProblemInfo, ...] = (
    # ---- reading the files ----
    _e(
        "YAML_SYNTAX",
        ERR,
        _READ,
        "The file is not valid YAML",
        "Every project file must be readable YAML within the tool's size and structure limits "
        "(no aliases that expand without bound, no oversized files).",
        "Nothing in a file that cannot be read is used; a result that needs it is missing.",
        "Fix the syntax at the line shown (indentation, colons, quotes). If the message names a "
        "size or alias limit, shorten the file or remove the aliases instead.",
    ),
    _e(
        "FILE_NOT_FOUND",
        ERR,
        _READ,
        "A file or folder is missing",
        "The project folder, and every file that the project names, must exist and be readable.",
        "A missing file is a missing input; whatever needs it cannot be worked out.",
        "Check the path and the permissions. A project is a folder that holds project.yaml.",
    ),
    _e(
        "FILE_INVALID",
        ERR,
        _READ,
        "The file cannot be used as a project file",
        "A project file must be a mapping of fields (name: value), and must lie inside the "
        "project folder (links that lead out are not followed).",
        "A file outside the folder would make the project depend on something the export does "
        "not contain.",
        "Write the file as fields, and keep it inside the project folder.",
    ),
    _e(
        "KIND_MISMATCH",
        ERR,
        _READ,
        "The file has the wrong kind",
        "The location of a file decides its kind (a file in units/ is a unit); the `kind:` line "
        "must agree.",
        "A file read as the wrong kind would be checked against the wrong fields.",
        "Set `kind:` to the one the message names, or move the file to the right folder.",
    ),
    _e(
        "ID_INVALID",
        ERR,
        _READ,
        "The id of a file is not valid",
        "The id (the file name without .yaml) must not be empty, must not start with a dot and "
        "must be valid text.",
        "Other files refer to a file by its id; an invalid id cannot be referred to reliably.",
        "Rename the file with letters, digits, `_` and `-`.",
    ),
    _e(
        "ID_UNUSUAL",
        WARN,
        _READ,
        "The id of a file has unusual characters",
        "An id should consist of ASCII letters, digits, `_` and `-`.",
        "Spaces, accents and look-alike letters make ids hard to type and to tell apart.",
        "Rename the file, and every reference to it, with letters, digits, `_` and `-`.",
    ),
    _e(
        "ID_COLLISION",
        WARN,
        _READ,
        "Two ids differ only by capitals or accent encoding",
        "Two ids in one folder must differ in more than capital letters or the way an accent is "
        "encoded.",
        "On some file systems (Windows among them) such names are one file, so the project would "
        "change meaning between computers.",
        "Rename one of the files.",
    ),
    _e(
        "FILE_IGNORED",
        WARN,
        _READ,
        "A file is not used",
        "Files that are not part of the project layout are not read.",
        "A value you wrote in an ignored file has no effect on any result.",
        "Move the file to the folder it belongs in, or delete it.",
    ),
    _e(
        "FILE_MIGRATED",
        INFO,
        _READ,
        "The file was read from an older format",
        "A file with an older schema version is converted in memory when it is loaded.",
        "Nothing changes in your results; the file on disk is still the old version.",
        "Save the project to write the file in the current format.",
    ),
    _e(
        "FEATURE_UNSUPPORTED",
        ERR,
        _READ,
        "The project needs a feature this version does not have",
        "`project.yaml` lists in `requires:` the features the project uses that an older tool "
        "would ignore; a name this version does not know is refused.",
        "A tool that ignored the feature would give results the project did not ask for.",
        "Open the project with a newer release of the tool.",
    ),
    _e(
        "FEATURE_NOT_DECLARED",
        WARN,
        _READ,
        "The project uses a feature it does not list in requires",
        "A model choice that older versions do not know (the Earth model of a scenario) should "
        "be listed in `requires:` of `project.yaml`, so that an older tool refuses the project.",
        "An older tool would otherwise read the project and could give results for a different "
        "model than the one chosen.",
        "Add `model_choices` to `requires:` in project.yaml.",
    ),
    _e(
        "PROVENANCE_PATH_UNKNOWN",
        WARN,
        _READ,
        "A source is recorded for an input that does not exist",
        "A key of the `provenance:` mapping must be the path of an input of the same file.",
        "The source belongs to a field that was renamed or removed, so it describes nothing; "
        "the results are not affected.",
        "Correct the key to the current path, or delete the entry.",
    ),
    _e(
        "SCHEMA_VERSION_MISSING",
        ERR,
        _READ,
        "The file has no valid schema version",
        "Every file starts with `schema_version:`, a whole number from 1.",
        "The version tells the tool how to read the file.",
        "Add `schema_version:` with the number that the documentation names for the file kind.",
    ),
    _e(
        "SCHEMA_TOO_NEW",
        ERR,
        _READ,
        "The file is from a newer version of the tool",
        "The schema version of a file must not be newer than the tool supports.",
        "A newer file may hold fields this version would silently misread.",
        "Open the project with a newer release of the tool.",
    ),
    _e(
        "SCHEMA_MIGRATION_MISSING",
        ERR,
        _READ,
        "No migration exists for this old version",
        "Each old schema version needs a migration to the current one.",
        "Without it the file cannot be converted.",
        "Open the file with an older release of the tool, save it, and retry.",
    ),
    _e(
        "SCHEMA_MIGRATION_FAILED",
        ERR,
        _READ,
        "The migration of the file failed",
        "A file of an old version must have the layout of that version to be converted.",
        "A file that does not match its stated version cannot be converted safely.",
        "Check `schema_version:` and the layout of the file against the documentation of that "
        "version.",
    ),
    # ---- fields and units ----
    _e(
        "FIELD_MISSING",
        ERR,
        _FIELDS,
        "A required field is missing",
        "Each file kind has fields that must be present.",
        "A missing input would otherwise be silently replaced by a default; the tool never does "
        "that.",
        "Add the field. The hint names its unit when it has one.",
    ),
    _e(
        "FIELD_UNKNOWN",
        ERR,
        _FIELDS,
        "A field is not known",
        "Only the fields of the file kind are accepted.",
        "A misspelled field would be ignored and its default used, with no sign of it in the "
        "results.",
        "Correct the spelling (the hint suggests the nearest field) or remove the field.",
    ),
    _e(
        "FIELD_INVALID",
        ERR,
        _FIELDS,
        "A field has a value that cannot be used",
        "A value must have the type, range and unit of its field.",
        "A value outside what the model accepts would give a result that means nothing.",
        "Correct the value as the message says. A bare number is in the unit named in the field "
        "name (`power_w` is in watts); a value with a unit is converted.",
    ),
    _e(
        "UNIT_INVALID",
        ERR,
        _FIELDS,
        "A unit is not accepted",
        "A value with a unit must use a unit of the dimension of its field.",
        "A unit of another dimension, or an ambiguous one (the word `ton`), would change the "
        "number by a hidden factor.",
        "Write the unit the field expects, or a number in the field's unit.",
    ),
    _e(
        "DUPLICATE_NAME",
        ERR,
        _FIELDS,
        "A name is used twice",
        "Names that are looked up (power modes, buses, nodes, limits) must be unique in their "
        "list.",
        "A reference to a repeated name would be ambiguous.",
        "Rename one of the entries.",
    ),
    _e(
        "DUPLICATE_ID",
        ERR,
        _FIELDS,
        "An id is used twice",
        "Site ids must be unique across ground_stations/ and targets/.",
        "A scenario names a site by its id; two sites with one id cannot be told apart.",
        "Rename one of the files.",
    ),
    _e(
        "SOURCE_MISSING",
        ERR,
        _CONF,
        "A configuration number has no source",
        "Every configuration number carries a non-empty `source`.",
        "A number without a source cannot be reviewed; the tool never invents standards values.",
        "Cite the standard or data sheet, or write `TBD` to mark a placeholder.",
    ),
    _e(
        "CONFIG_VALUE_INVALID",
        ERR,
        _CONF,
        "A configuration number is out of range",
        "Each configuration number has a range in which it makes physical sense.",
        "A ratio above 1 or a negative temperature would produce results that look valid.",
        "Check the value and its unit. Ratios are fractions (0.1 means 10 %), temperatures are "
        "in kelvin, gains and losses in decibels.",
    ),
    _e(
        "CONFIG_MISSING",
        WARN,
        _CONF,
        "A configuration file is missing",
        "A budget needs the configuration files it reads (margin policy, power configuration, "
        "mass limits, thermal files, tables).",
        "The results that need it are not computed (n/a); they are never filled with defaults.",
        "Create the file with every number sourced, or `TBD` for the ones you do not have yet.",
    ),
    _e(
        "CONFIG_EMPTY_TABLE",
        WARN,
        _CONF,
        "A configuration table has no entries",
        "A table that a budget reads (mass limits, Eb/N0, attenuation) should have entries.",
        "With no entries the checks that use the table cannot run.",
        "Add entries from a cited source, or import them from a file.",
    ),
    _e(
        "CONFIG_PLACEHOLDER",
        WARN,
        _CONF,
        "A configuration number is a placeholder",
        "A number whose source is `TBD`, or that has no value, is a placeholder.",
        "Every result that needs it is n/a; a result built on a guess would look like a pass.",
        "Replace it with a value from your margin policy, standard or data sheet and cite the "
        "source.",
    ),
    _e(
        "RESULT_INCOMPLETE",
        WARN,
        _CONF,
        "A result needs a placeholder",
        "A result that depends on a placeholder or missing input is shown as n/a.",
        "It is neither a pass nor a fail; it has not been checked.",
        "Replace the placeholder named in the same report with a sourced value.",
    ),
    # ---- references ----
    _e(
        "REF_UNKNOWN_BUS",
        ERR,
        _REF,
        "A unit names a supply bus that is not defined",
        "The bus of a unit must be one of the buses listed in spacecraft.yaml.",
        "Power is summed by bus and each bus has its converter efficiency.",
        "Use the name of a bus listed under `buses`, or add the bus.",
    ),
    _e(
        "REF_UNKNOWN_MATURITY",
        ERR,
        _REF,
        "A maturity class is not defined",
        "The maturity class of a unit or expendable must be a class of the margin policy.",
        "The class decides the margin applied to its power and mass.",
        "Use a class listed under `classes` in config/margin_policy.yaml, or add the class.",
    ),
    _e(
        "REF_UNKNOWN_UNIT",
        ERR,
        _REF,
        "A spacecraft mode names a unit that does not exist",
        "Every unit named in a spacecraft mode must be a file in units/.",
        "The mode's total would silently leave the unit out.",
        "Use the file name (without .yaml) of a unit.",
    ),
    _e(
        "REF_UNKNOWN_UNIT_MODE",
        ERR,
        _REF,
        "A spacecraft mode names a power mode the unit does not have",
        "The power mode assigned to a unit must be one of the unit's own power modes.",
        "Without it the unit's power in that spacecraft mode is not known.",
        "Use a power mode listed under `modes` in the unit file, or add it.",
    ),
    _e(
        "UNIT_NOT_MAPPED",
        ERR,
        _REF,
        "A unit has no power mode in a spacecraft mode",
        "Every unit must be assigned a power mode in every spacecraft mode.",
        "A unit left out would be counted as drawing nothing.",
        "Add `<unit>: <power mode name>` under `assignments` of the spacecraft mode.",
    ),
    _e(
        "REF_UNKNOWN_PHASE",
        ERR,
        _REF,
        "A mission phase is not defined",
        "A phase named in a file must be one of `mission_phases` in spacecraft.yaml.",
        "Limits and masses are tied to phases.",
        "Use a name listed under `mission_phases`, or add the phase.",
    ),
    _e(
        "PHASE_MASS_MISSING",
        ERR,
        _REF,
        "An expendable has no mass for a phase",
        "An expendable needs a mass for every mission phase.",
        "A missing phase would count the item as massless in that phase.",
        "Add an entry named like the phase, with its mass in kg (0.0 if it is not aboard).",
    ),
    _e(
        "MASS_FRAME_UNDEFINED",
        WARN,
        _MASS,
        "Positions are given but the body frame is not described",
        "If any item has a position, `body_frame` in spacecraft.yaml should describe the axes "
        "and the origin.",
        "A centre of gravity is only meaningful in a stated frame.",
        "Describe the axes and origin in `body_frame`.",
    ),
    _e(
        "REF_UNKNOWN_MODE",
        ERR,
        _REF,
        "A spacecraft mode is not defined",
        "A spacecraft mode named in a file (a thermal case, a link, a scenario rule) must be a "
        "file in modes/.",
        "The mode decides which power modes, and so which dissipation, apply.",
        "Use the id of a mode in modes/.",
    ),
    _e(
        "REF_UNKNOWN_CASE",
        ERR,
        _THERM,
        "A thermal case is not defined",
        "A surface exposure must name a case defined in the thermal environment.",
        "An exposure for an unknown case would never be used.",
        "Use a case listed under `cases` in config/thermal_environment.yaml.",
    ),
    _e(
        "THERMAL_NODE_UNKNOWN",
        ERR,
        _THERM,
        "A thermal node is not defined",
        "The node named by a unit or a surface must be a node of the thermal model.",
        "Heat put into an undefined node would be lost from the balance.",
        "Use a node listed under `nodes` in config/thermal_model.yaml.",
    ),
    _e(
        "REF_UNKNOWN_ATTENUATION",
        ERR,
        _LINK,
        "A link names an attenuation that has no table entry",
        "Each attenuation a link names must have an entry in config/attenuation_table.yaml.",
        "The tool has no propagation model of its own; the loss comes only from the table.",
        "Use a name listed under `entries`, or add the entry with its source.",
    ),
    _e(
        "REF_UNKNOWN_MODULATION",
        ERR,
        _LINK,
        "The Eb/N0 table has no entry for the modulation and coding",
        "A link's modulation and coding must be a pair in config/ebn0_table.yaml.",
        "The required Eb/N0 decides whether the link closes.",
        "Add the entry with its source (Edit, Add Eb/N0 entry in the window), or correct the "
        "names.",
    ),
    _e(
        "REF_UNKNOWN_STATION",
        ERR,
        _LINK,
        "The peer of a link is not a ground station",
        "A link's peer must be a file in ground_stations/.",
        "The peer decides where the passes of the link are computed.",
        "Use the id of a ground station.",
    ),
    _e(
        "LINK_ANTENNA_PATTERN_GROUND",
        ERR,
        _LINK,
        "A ground antenna has a pattern",
        "A ground antenna has a constant gain; patterns are for the spacecraft end.",
        "The tool assumes the ground antenna tracks the spacecraft.",
        "Use `gain_dbi` for the ground antenna.",
    ),
    _e(
        "LINK_PATTERN_FILE_MISSING",
        ERR,
        _LINK,
        "An antenna pattern file is missing",
        "A `pattern_file` must exist and lie inside the project folder.",
        "Without it the antenna gain is not known.",
        "Give a path relative to the project folder, to an existing CSV file.",
    ),
    _e(
        "REF_UNKNOWN_ORBIT",
        ERR,
        _SCEN,
        "A scenario names an orbit that does not exist",
        "The orbit of a scenario must be a file in orbits/.",
        "The orbit decides every geometry in the scenario.",
        "Use the id of an orbit in orbits/.",
    ),
    _e(
        "REF_UNKNOWN_SITE",
        ERR,
        _SCEN,
        "A site is not defined or not listed",
        "A site named by a scenario or one of its rules must exist, and a rule's site must be "
        "listed in the scenario's `sites`.",
        "A pass cannot be computed for a site the scenario does not have.",
        "Use the id of a ground station or target, and list it under `sites`.",
    ),
    # ---- scenarios and environment ----
    _e(
        "SCENARIO_UNKNOWN",
        ERR,
        _SCEN,
        "The scenario does not exist",
        "The scenario asked for must be a file in scenarios/.",
        "Nothing can be run without a scenario.",
        "Use one of the scenarios the message lists.",
    ),
    _e(
        "SCENARIO_TOO_LARGE",
        ERR,
        _SCEN,
        "The scenario is too large",
        "The number of samples (duration over step) must fit the memory that is available.",
        "A run that exhausts memory would fail without a result.",
        "Increase `step_s` or shorten `duration_s`.",
    ),
    _e(
        "SCENARIO_OPTION_IGNORED",
        WARN,
        _SCEN,
        "A scenario option has no effect",
        "An option that belongs to another environment source is not used.",
        "You may believe a setting is in force that is not.",
        "Remove the option, or change `environment_source`.",
    ),
    _e(
        "SCENARIO_PHASE_NO_DOD",
        WARN,
        _SCEN,
        "The battery has no depth-of-discharge limit for this phase",
        "The scenario's mission phase must have an entry in `battery.max_dod_ratio`.",
        "Without it the depth-of-discharge check is not evaluated, which is not a pass.",
        "Add the phase under `battery.max_dod_ratio` in config/power_system.yaml.",
    ),
    _e(
        "IMPORT_DIR_MISSING",
        ERR,
        _SCEN,
        "The import folder is missing",
        "The SpaceMissionStudio import folder must be an existing folder inside the project "
        "folder.",
        "Without it the imported positions cannot be read.",
        "Give a path relative to the project folder to an existing folder.",
    ),
    _e(
        "ENV_INPUT_INVALID",
        ERR,
        _SCEN,
        "The imported environment files cannot be read",
        "The imported files must have the layout of docs/ENVIRONMENT_FORMAT.md.",
        "Positions that cannot be read would leave the scenario without an environment.",
        "Check the files against the format description.",
    ),
    _e(
        "ENV_PROPAGATION_FAILED",
        ERR,
        _SCEN,
        "The orbit cannot be computed",
        "The orbit must be computable for the scenario dates (years 1950 to 2100; no decay).",
        "Without positions there are no passes, eclipses or Sun directions.",
        "Check the scenario start and duration, and the orbit; very low or very eccentric "
        "orbits decay.",
    ),
    _e(
        "ORBIT_INVALID",
        ERR,
        _SCEN,
        "The orbit definition is not valid",
        "The elements or the TLE must describe an orbit above the Earth's surface.",
        "An orbit that touches the Earth cannot be propagated.",
        "Check the elements (a perigee below the surface is not valid) or the TLE lines.",
    ),
    _e(
        "MODEL_CHOICE_IGNORED",
        WARN,
        _SCEN,
        "A model choice does not apply to this orbit",
        "The Earth model of a scenario applies to an orbit given as elements; a TLE is "
        "propagated on WGS-72, the set SGP4 is defined on.",
        "You may believe the TLE was propagated on the model you chose.",
        "Remove the option, or give the orbit as elements.",
    ),
    _e(
        "ORBIT_EPOCH_FAR",
        WARN,
        _SCEN,
        "The TLE is far from the scenario",
        "A TLE should be within 30 days of the scenario start.",
        "An old TLE drifts: the passes and eclipses may be wrong in time.",
        "Use a TLE from near the scenario dates, or an orbit given by elements.",
    ),
    # ---- mass ----
    _e(
        "MASS_LIMIT_EXCEEDED",
        ERR,
        _MASS,
        "A mass limit is exceeded",
        "The system-margined total mass of a phase must not exceed any mass limit that applies "
        "to the phase.",
        "The limit is a requirement on the design (a launcher capacity, a budget allocation).",
        "Reduce mass, review the margins, or change the limit (and cite its source).",
    ),
    _e(
        "MASS_PROPS_MISSING",
        WARN,
        _MASS,
        "An item has no position",
        "An item with a mass should have `mass_properties.position_m`.",
        "Without it the item is left out of the centre of gravity and the inertia (it is never "
        "counted at the origin), so those results cover only part of the mass.",
        "Add `mass_properties` with `position_m: [x, y, z]` in the body frame.",
    ),
    _e(
        "MASS_INERTIA_POINT_MASS",
        INFO,
        _MASS,
        "An item is treated as a point mass",
        "An item with a position but no own inertia contributes only the parallel-axis term.",
        "The inertia of the spacecraft is a little low by the item's own inertia.",
        "Add `mass_properties.inertia` if the item's own inertia matters.",
    ),
    _e(
        "MASS_INERTIA_NOT_SCALED",
        WARN,
        _MASS,
        "An expendable's inertia does not follow its mass",
        "An expendable with an own inertia and more than one mass uses the same inertia in "
        "every phase (DEVIATIONS DV-M4).",
        "The inertia is wrong in the phases where the mass differs.",
        "Remove the own inertia (point mass) or accept the error; per-phase inertia is not "
        "modelled.",
    ),
    # ---- thermal ----
    _e(
        "THERMAL_LIMIT_EXCEEDED",
        ERR,
        _THERM,
        "A unit is outside its temperature limits",
        "In every thermal case the temperature of a unit's node must lie between the lower and "
        "the upper limit of the limit set the case uses (operating or survival).",
        "The limits come from the unit's data sheet; outside them it is not qualified.",
        "Change the design (conduction, radiator area, dissipation) or the limit, citing its "
        "source.",
    ),
    _e(
        "THERMAL_MARGIN_INSUFFICIENT",
        ERR,
        _THERM,
        "A unit is closer to its limit than the required margin",
        "The headroom to each temperature limit must be at least `temperature_margin_k`.",
        "The margin covers the uncertainty of the model.",
        "Change the design, or review the required margin in config/thermal_environment.yaml.",
    ),
    _e(
        "THERMAL_NO_LIMITS",
        WARN,
        _THERM,
        "A unit has no temperature limits",
        "A unit should have limits for the set a case checks.",
        "It is not checked, which is not a pass.",
        "Add `temperature_limits` from the unit's data sheet.",
    ),
    _e(
        "THERMAL_SOLVE_FAILED",
        ERR,
        _THERM,
        "The node temperatures cannot be solved",
        "Every group of connected nodes needs a path to space (a surface that radiates), "
        "otherwise there is no equilibrium.",
        "Without an equilibrium no temperature is computed.",
        "Give every group of connected nodes a surface that radiates to space.",
    ),
    # ---- power timeline ----
    _e(
        "BATTERY_DOD_EXCEEDED",
        ERR,
        _POWER,
        "The battery discharges deeper than allowed",
        "The depth of discharge must not exceed `battery.max_dod_ratio` of the mission phase.",
        "Deep cycling shortens the battery life; the limit is the requirement on the design.",
        "Reduce the demand, add capacity or generation, or review the limit (cite its source).",
    ),
    _e(
        "BATTERY_DEPLETED",
        ERR,
        _POWER,
        "The battery is empty and the demand is not supplied",
        "The demand not supplied by the array or the battery must stay at zero.",
        "In flight the loads would drop out.",
        "Reduce the demand, add generation or battery capacity, or change the scenario.",
    ),
    _e(
        "ORBIT_BALANCE_NEGATIVE",
        ERR,
        _POWER,
        "An orbit generates less energy than it uses",
        "Over each orbit the energy generated must be at least the energy demanded.",
        "The battery would be drained orbit after orbit.",
        "Increase the array or reduce the demand; the table of orbit balances shows each orbit.",
    ),
    _e(
        "PEAK_POWER_EXCEEDED",
        ERR,
        _POWER,
        "The peak demand exceeds the power limit",
        "The peak power demand at the source must not exceed `limits.peak_power_w`.",
        "The limit is what the power system can deliver at once.",
        "Reduce the peak demand, or review the limit (cite its source).",
    ),
    _e(
        "ORBIT_BALANCE_NOT_EVALUATED",
        WARN,
        _POWER,
        "The orbit energy balance was not evaluated",
        "The energy balance needs a step of at most a quarter of the orbit period to find the "
        "orbits.",
        "Its absence is not a pass; the other checks do not depend on it.",
        "Use a shorter step.",
    ),
    _e(
        "POWER_REFINEMENT_INCOMPLETE",
        WARN,
        _POWER,
        "The battery full and empty instants were still moving",
        "The instants at which the battery becomes full or empty are refined in rounds; they "
        "should settle within four.",
        "The energy results are accurate to the last edges found, not exact.",
        "Use a shorter step; report the project if it persists.",
    ),
    # ---- links ----
    _e(
        "LINK_NOT_CLOSED",
        ERR,
        _LINK,
        "A link closes at none of its data rates",
        "At least one listed data rate must give a margin of at least the required margin.",
        "A link that never closes cannot carry data.",
        "Lower the data rates, raise the transmit power or antenna gain, or review the losses "
        "and the required margin.",
    ),
    _e(
        "LINK_INPUT_INVALID",
        ERR,
        _LINK,
        "A link input cannot be used",
        "An antenna pattern file must lie inside the project folder and be a CSV table of "
        "increasing angles (`angle_deg`, `gain_dbi`).",
        "A pattern that cannot be read leaves the antenna gain unknown.",
        "Use a relative path and a comma-separated UTF-8 file with the two columns.",
    ),
    _e(
        "LINK_ATTENUATION_FREQUENCY",
        WARN,
        _LINK,
        "An attenuation entry is for another frequency",
        "An attenuation entry used by a link should be for the link's frequency (within 1 %).",
        "A loss at the wrong frequency may be far from the loss at the link frequency.",
        "Use an entry for the link frequency.",
    ),
    _e(
        "LINK_ATTENUATION_DUPLICATE",
        WARN,
        _LINK,
        "Two attenuation entries for one elevation",
        "A named attenuation should have one entry per elevation.",
        "The larger loss is used, which may not be the one intended.",
        "Keep one entry per elevation.",
    ),
    _e(
        "LINK_NO_STATIC_POINTS",
        INFO,
        _LINK,
        "A link has no static points",
        "A link with no static points has no static table.",
        "Nothing is wrong; only the pass series (with a scenario) is available.",
        "Add elevation and range pairs under `static_points`.",
    ),
    _e(
        "LINK_SITE_NOT_IN_SCENARIO",
        WARN,
        _LINK,
        "The peer of a link is not a site of the scenario",
        "The ground station a link names must be listed in the scenario's `sites`.",
        "Without it there is no pass series for the link.",
        "Add the ground station to `sites` of the scenario.",
    ),
    _e(
        "LINK_NEVER_ACTIVE",
        INFO,
        _LINK,
        "A link is never active in the scenario",
        "A link is active when a pass of its station falls in an active mode below the "
        "tracking limit.",
        "With no active time its data volume is zero.",
        "Check the scenario's sites and rules, `active_modes` and `max_elevation_deg` of the link.",
    ),
    _e(
        "LINK_PER_DAY_NOT_GIVEN",
        INFO,
        _LINK,
        "No data volume per day for a short scenario",
        "A per-day figure needs a scenario of at least one day.",
        "Scaling a short scenario to a day would repeat its passes.",
        "Use a scenario of at least one day.",
    ),
    # ---- unit tables ----
    _e(
        "IMPORT_FILE_UNREADABLE",
        ERR,
        _IMPORT,
        "The unit table cannot be read",
        "A unit table is a .csv file (UTF-8) or an .xlsx workbook with at least a header row.",
        "Nothing can be imported from a file that cannot be read.",
        "Start from the template written by `budget units-export`.",
    ),
    _e(
        "IMPORT_FILE_TOO_LARGE",
        ERR,
        _IMPORT,
        "The unit table is too large",
        "A unit table is a few kilobytes.",
        "A very large file is probably not a unit table.",
        "Check that this is the right file.",
    ),
    _e(
        "IMPORT_COLUMN_MISSING",
        ERR,
        _IMPORT,
        "A column of the template is missing",
        "The table must have the columns of the template.",
        "Without a required column the rows cannot be understood.",
        "Start from the template written by `budget units-export`.",
    ),
    _e(
        "IMPORT_COLUMN_IGNORED",
        WARN,
        _IMPORT,
        "A column is not used",
        "Columns that are not in the template are ignored.",
        "Values in them have no effect.",
        "Remove the column or move the value to a column of the template.",
    ),
    _e(
        "IMPORT_UNKNOWN_UNIT",
        ERR,
        _IMPORT,
        "A row names a unit the project does not have",
        "An import changes existing units only.",
        "A new unit needs more than the power table gives.",
        "Use the ids of the exported template.",
    ),
    _e(
        "IMPORT_FIELD_MISSING",
        ERR,
        _IMPORT,
        "A row has no power mode name",
        "Each row names the power mode it describes.",
        "A row without it cannot be matched.",
        "Give the name of the power mode, as in the exported template.",
    ),
    _e(
        "IMPORT_DUPLICATE_ROW",
        ERR,
        _IMPORT,
        "A unit and power mode appear twice",
        "A unit and power mode pair may appear once.",
        "Two rows would disagree about the same numbers.",
        "Keep one row per power mode.",
    ),
    _e(
        "IMPORT_VALUE_INVALID",
        ERR,
        _IMPORT,
        "A value in the table cannot be used",
        "Each cell must be a number, or a number with a unit of the right dimension.",
        "The value would otherwise change the unit's power silently.",
        "Write a number or a value with a matching unit such as `2.5 W`; the message says what "
        "the field requires.",
    ),
    # ---- other ----
    _e(
        "INTERNAL_ERROR",
        ERR,
        _OTHER,
        "The tool failed unexpectedly",
        "The tool did not expect this failure; it reports only its kind, never project content.",
        "Whatever was being computed has no result.",
        "Run `budget validate` on the folder to see the details, then report it.",
    ),
)

CATALOGUE: dict[str, ProblemInfo] = {entry.code: entry for entry in _ENTRIES}
assert len(CATALOGUE) == len(_ENTRIES), "a code appears twice in the problem catalogue"


def describe(code: str) -> ProblemInfo | None:
    """The catalogue entry of a problem code, or None for a code that has none."""
    return CATALOGUE.get(code)


def render_markdown() -> str:
    """The generated page `docs/PROBLEMS.md`: one section per code, grouped by area."""
    lines = [
        "# Problem codes",
        "",
        "<!-- Generated by `budget problems --markdown` from problem_catalogue.py. -->",
        "",
        "Every finding the tool reports has a **code**. This page says, for each code, what the "
        "rule is, why it matters and how to resolve it. The texts are the same for every project; "
        "they never contain a value from your files. A finding shows the file and the place in "
        "it; in the window and in the result files it also carries the value and the limit when "
        "the finding is a comparison (for example a mass over its limit). See "
        "[Read and fix problems](user-manual/read-and-fix-problems.md) for how to work through "
        "them and `budget problems CODE` for this text on the command line.",
        "",
        "Severity is the usual one: **error** (the project cannot be used as it is, or a limit is "
        "broken), **warning** (results are produced, but something needs a look), **info** "
        "(nothing to fix). A finding that a result is *n/a* because of a placeholder is shown as "
        "*not checked* in the window.",
        "",
    ]
    areas: list[str] = []
    for entry in _ENTRIES:
        if entry.area not in areas:
            areas.append(entry.area)
    for area in areas:
        lines += [f"## {area}", ""]
        for entry in (e for e in _ENTRIES if e.area == area):
            lines += [
                f"### {entry.code}",
                "",
                f"**{entry.title}** ({entry.severity.value})",
                "",
                f"- **Rule.** {entry.rule}",
                f"- **Why it matters.** {entry.why}",
                f"- **What to do.** {entry.fix}",
                "",
            ]
    return "\n".join(lines).rstrip() + "\n"
