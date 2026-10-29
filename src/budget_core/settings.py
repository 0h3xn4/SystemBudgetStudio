"""The catalogue of the numbers the tool applies that no project file shows (D-217).

Every numeric constant of the code that decides, limits or formats a result has one entry here: its
id, group, kind, value, unit, why it is what it is, and where it acts. The values are pinned here
and a test compares each with the constant in its module, so the table and the code cannot drift;
a test also finds a constant that has no entry.

Kinds:
- `setting`: meant to be changed for one project (the project file that changes it comes in a later
  step; until then every setting is at its default);
- `tolerance`: a numerical tolerance or an algorithm limit; changing it changes roundings, not
  engineering;
- `limit`: a limit on the size of an input or a file, against hostile or absurd files;
- `constant`: a physical constant or a definition;
- `format`: how a result is written (digits, sizes of a figure or a cell);
- `creation`: a default the guided mode or a form writes into a new project;
- `internal`: a performance or bookkeeping value with no effect on a result.

Nothing here reads a project, and nothing here changes a result.
"""

from __future__ import annotations

from dataclasses import dataclass

KINDS = ("setting", "tolerance", "limit", "constant", "format", "creation", "internal")
KIND_TEXT = {
    "setting": "Setting (per project)",
    "tolerance": "Numerical tolerance",
    "limit": "Input limit",
    "constant": "Constant",
    "format": "Output format",
    "creation": "Creation default",
    "internal": "Internal",
}


@dataclass(frozen=True)
class SettingSpec:
    """One entry of the catalogue. `binding` is `module:NAME` below `budget_core`."""

    id: str
    kind: str
    title: str
    unit: str
    default: float
    binding: str
    reason: str
    acts_on: str

    @property
    def group(self) -> str:
        return self.id.partition(".")[0]


def _s(
    id: str,
    kind: str,
    title: str,
    unit: str,
    default: float,
    binding: str,
    reason: str,
    acts_on: str,
) -> SettingSpec:
    return SettingSpec(id, kind, title, unit, default, binding, reason, acts_on)


_EDGES = "D-146, DEVIATIONS DV-E4"

CATALOGUE: tuple[SettingSpec, ...] = (
    # ---- environment -------------------------------------------------------------------------
    _s(
        "environment.detection_step_s",
        "setting",
        "Detection grid of passes and eclipses",
        "s",
        20.0,
        "model.environment:DETECTION_STEP_S",
        "Fine enough to find every pass and eclipse of a low orbit, whatever the scenario step.",
        "The grid on which passes and eclipses are found; also sets the largest scenario "
        "(max_samples).",
    ),
    _s(
        "environment.tle_max_age_days",
        "setting",
        "Age of a TLE that is warned about",
        "d",
        30.0,
        "environment.elements:MAX_TLE_AGE_DAYS",
        "A TLE is accurate for days to a few weeks; older ones give the warning ORBIT_EPOCH_FAR.",
        "The warning ORBIT_EPOCH_FAR (a TLE epoch this far from the scenario start).",
    ),
    _s(
        "environment.max_samples",
        "setting",
        "Largest scenario",
        "samples",
        1_000_000,
        "model.environment:MAX_SAMPLES",
        "About 11 days at 1 s; a week at 1 s (604,801) is the design case.",
        "Refuses a scenario with more time steps (duration over the finer of the step and the "
        "detection grid).",
    ),
    _s(
        "environment.sunlight_threshold_ratio",
        "tolerance",
        "Sunlight ratio below which the satellite is in eclipse",
        "ratio",
        1.0 - 1e-12,
        "environment.elements:LIT",
        f"Any shadow counts as eclipse, penumbra included ({_EDGES}).",
        "The edges of eclipses and the umbra.",
    ),
    _s(
        "environment.umbra_ratio",
        "tolerance",
        "Sunlight ratio at or below which the satellite is in umbra",
        "ratio",
        1e-12,
        "environment.elements:UMBRA",
        f"Numerical zero of the sunlight ratio ({_EDGES}).",
        "The umbra.",
    ),
    _s(
        "environment.edge_tolerance_s",
        "tolerance",
        "Accuracy of the edges of passes and eclipses",
        "s",
        1e-3,
        "environment.elements:EDGE_TOLERANCE_S",
        "About 1 ms: far below any step and any time the results show.",
        "Bisection of every pass and eclipse edge.",
    ),
    _s(
        "environment.max_rules",
        "limit",
        "Rules and segments per scenario",
        "count",
        10_000,
        "model.environment:MAX_RULES",
        "Keeps the timeline of a scenario small enough to build and show.",
        "Refuses a scenario with more rules or segments.",
    ),
    _s(
        "environment.min_year",
        "limit",
        "Earliest accepted year",
        "year",
        1950,
        "timeutil:MIN_YEAR",
        "The Sun and Earth models and the TLE epoch convention are meant for this range (D-120).",
        "Dates of scenarios and element epochs.",
    ),
    _s(
        "environment.max_year",
        "limit",
        "Latest accepted year",
        "year",
        2100,
        "timeutil:MAX_YEAR",
        "The Sun and Earth models and the TLE epoch convention are meant for this range (D-120).",
        "Dates of scenarios and element epochs.",
    ),
    _s(
        "environment.timeline_epsilon_s",
        "tolerance",
        "Merge distance of mode boundaries",
        "s",
        1e-9,
        "scenario.timeline:EPS",
        "A gap or overlap this small between modes is rounding, not a sliver of time.",
        "The mode timeline of a scenario.",
    ),
    _s(
        "environment.imported_file_max_bytes",
        "limit",
        "Largest imported environment file",
        "bytes",
        250_000_000,
        "environment.spacemissionstudio:MAX_FILE_BYTES",
        "A file is read whole: a week at 1 s is 604,801 rows of about 120 bytes.",
        "Import of SpaceMissionStudio files.",
    ),
    _s(
        "environment.imported_max_rows",
        "limit",
        "Most rows of an imported orbit or profile file",
        "rows",
        2_000_000,
        "environment.spacemissionstudio:MAX_ROWS",
        "A file is read whole, so it is bounded.",
        "Import of orbit.csv and profile_<site>.csv.",
    ),
    _s(
        "environment.imported_max_pass_rows",
        "limit",
        "Most rows of an imported eclipse or pass file",
        "rows",
        100_000,
        "environment.spacemissionstudio:MAX_PASS_ROWS",
        "A file is read whole, so it is bounded.",
        "Import of eclipse.csv and passes_<site>.csv.",
    ),
    _s(
        "environment.full_hash_bytes",
        "internal",
        "Largest imported file identified by its whole content",
        "bytes",
        16 * 1024 * 1024,
        "scenario.run:FULL_HASH_BYTES",
        "Up to this size the content is hashed whole (D-212); larger files by size, time and ends.",
        "Whether a computed environment can be reused.",
    ),
    _s(
        "environment.edge_hash_bytes",
        "internal",
        "Part of a large imported file that is hashed at each end",
        "bytes",
        1024 * 1024,
        "scenario.run:EDGE_HASH_BYTES",
        "A large file is identified by its size, time and its first and last megabyte (D-212).",
        "Whether a computed environment can be reused.",
    ),
    # ---- power -------------------------------------------------------------------------------
    _s(
        "power.ratio_tolerance",
        "tolerance",
        "Tolerance of state-of-charge and depth-of-discharge tests",
        "ratio",
        1e-9,
        "power.time_domain:RATIO_TOL",
        "A limit that is met exactly must not be reported because of rounding noise.",
        "The depth-of-discharge finding of the power timeline.",
    ),
    _s(
        "power.power_tolerance_w",
        "tolerance",
        "Tolerance of power tests",
        "W",
        1e-9,
        "power.time_domain:POWER_TOL_W",
        "A limit that is met exactly must not be reported because of rounding noise.",
        "The peak-power finding and the test for an empty battery.",
    ),
    _s(
        "power.energy_tolerance_wh",
        "tolerance",
        "Tolerance of the orbit energy balance",
        "Wh",
        1e-6,
        "power.time_domain:ENERGY_TOL_WH",
        "A balance that is zero within rounding is not negative.",
        "The negative orbit balance finding.",
    ),
    _s(
        "power.refine_tolerance_s",
        "tolerance",
        "Distance under which two refinement instants are one edge",
        "s",
        1e-6,
        "power.time_domain:REFINE_TOL_S",
        "Instants closer than this to an existing edge are the same edge.",
        "The refinement of the power timeline.",
    ),
    _s(
        "power.penumbra_min_s",
        "tolerance",
        "Shortest penumbra ramp that is a ramp",
        "s",
        0.01,
        "power.time_domain:PENUMBRA_MIN_S",
        "A ramp from sunlight to umbra shorter than this is a sharp edge.",
        "How the array output changes at an eclipse edge.",
    ),
    _s(
        "power.max_refine_rounds",
        "tolerance",
        "Rounds of finding battery saturation instants",
        "rounds",
        4,
        "power.time_domain:MAX_REFINE_ROUNDS",
        "The instants are found on a grid that already holds them; four rounds are enough in "
        "practice and POWER_REFINEMENT_INCOMPLETE says when they were not.",
        "The refinement of the power timeline.",
    ),
    _s(
        "power.max_strings",
        "limit",
        "Most strings of a solar array face",
        "count",
        10_000,
        "model.power_system:MAX_STRINGS",
        "Input sanity: far beyond any array.",
        "Validation of power_system.yaml.",
    ),
    _s(
        "power.max_cells_per_string",
        "limit",
        "Most cells of a string",
        "count",
        10_000,
        "model.power_system:MAX_CELLS_PER_STRING",
        "Input sanity: far beyond any array.",
        "Validation of power_system.yaml.",
    ),
    _s(
        "power.max_cells_in_series",
        "limit",
        "Most battery cells in series",
        "count",
        1_000,
        "model.power_system:MAX_CELLS_IN_SERIES",
        "Input sanity: far beyond any battery.",
        "Validation of power_system.yaml.",
    ),
    _s(
        "power.max_cells_in_parallel",
        "limit",
        "Most battery cells in parallel",
        "count",
        10_000,
        "model.power_system:MAX_CELLS_IN_PARALLEL",
        "Input sanity: far beyond any battery.",
        "Validation of power_system.yaml.",
    ),
    _s(
        "power.max_direction_component",
        "limit",
        "Largest component of a pointing direction",
        "ratio",
        1.0e6,
        "model.power_system:MAX_DIRECTION_COMPONENT",
        "Input sanity: a direction is normalised, so a huge component is a slip.",
        "Validation of power_system.yaml.",
    ),
    _s(
        "power.min_direction_length",
        "limit",
        "Shortest pointing direction",
        "ratio",
        1.0e-6,
        "model.power_system:MIN_DIRECTION_LENGTH",
        "A direction of nearly zero length has no direction.",
        "Validation of power_system.yaml.",
    ),
    # ---- thermal -----------------------------------------------------------------------------
    _s(
        "thermal.accuracy_k",
        "tolerance",
        "Accuracy of the node temperatures",
        "K",
        1e-4,
        "thermal.steady_state:ACCURACY_K",
        "Far below the accuracy of any thermal input.",
        "The steady-state solution of the thermal network.",
    ),
    _s(
        "thermal.refine_rounds",
        "tolerance",
        "Rounds of refining the temperatures",
        "rounds",
        8,
        "thermal.steady_state:REFINE_ROUNDS",
        "The Newton solution is refined until a correction is rounding.",
        "The steady-state solution of the thermal network.",
    ),
    _s(
        "thermal.refined_k",
        "tolerance",
        "Correction below which the temperatures are final",
        "K",
        1e-7,
        "thermal.steady_state:REFINED_K",
        "A correction below this is rounding: the temperatures are as good as they get.",
        "The steady-state solution of the thermal network.",
    ),
    _s(
        "thermal.stefan_boltzmann_wm2k4",
        "constant",
        "Stefan-Boltzmann constant",
        "W/(m2 K4)",
        5.670374419e-8,
        "thermal.steady_state:STEFAN_BOLTZMANN_WM2K4",
        "Exact in the 2019 SI (defined from h, k and c).",
        "Radiation of every surface (TH-RAD).",
    ),
    _s(
        "thermal.celsius_offset_k",
        "format",
        "Offset between kelvin and degrees Celsius",
        "K",
        273.15,
        "reports.thermal_report:ABSOLUTE_ZERO_OFFSET_K",
        "Definition of the Celsius scale; used for display only, the model works in kelvin.",
        "The Celsius columns of the thermal report.",
    ),
    # ---- mass --------------------------------------------------------------------------------
    _s(
        "mass.limit_tolerance_ratio",
        "tolerance",
        "Tolerance of the mass limit test",
        "ratio",
        1e-9,
        "mass.static_mass:LIMIT_TOLERANCE_RATIO",
        "A limit met to within rounding noise is met (as in D-097).",
        "The status of a mass limit.",
    ),
    # ---- link --------------------------------------------------------------------------------
    _s(
        "link.pass_sample_s",
        "tolerance",
        "Sampling step of a link pass",
        "s",
        5.0,
        "link.evaluate:LINK_SAMPLE_S",
        "A pass is sampled at this step when the environment gives the exact geometry, so the "
        "results do not depend on the scenario step (D-057, DV-L3).",
        "The margin and rate over a pass, and the data volume.",
    ),
    _s(
        "link.day_s",
        "constant",
        "Seconds in a day",
        "s",
        86400.0,
        "link.evaluate:DAY_S",
        "Definition; the data volume per day is scaled with it.",
        "The data volume per day.",
    ),
    _s(
        "link.speed_of_light_ms",
        "constant",
        "Speed of light",
        "m/s",
        299_792_458.0,
        "link.constants:SPEED_OF_LIGHT_MS",
        "Exact by the definition of the metre (SI).",
        "Free-space path loss and wavelength.",
    ),
    _s(
        "link.boltzmann_jk",
        "constant",
        "Boltzmann constant",
        "J/K",
        1.380649e-23,
        "link.constants:BOLTZMANN_JK",
        "Exact in the 2019 SI.",
        "C/N0 (noise power density).",
    ),
    _s(
        "link.earth_radius_m",
        "constant",
        "Earth radius used by the link budget",
        "m",
        6_378_137.0,
        "link.constants:EARTH_RADIUS_M",
        "WGS-84 equatorial radius; the same value as the environment module.",
        "Geometry of the link when it is not given by the environment.",
    ),
    # ---- compare -----------------------------------------------------------------------------
    _s(
        "compare.max_rows",
        "setting",
        "Differences listed per budget in a comparison",
        "rows",
        200,
        "compare:DEFAULT_MAX_ROWS",
        "Keeps a report readable; the CSV and JSON files list every difference.",
        "The comparison report and the Compare page (option --max-rows).",
    ),
    # ---- reports -----------------------------------------------------------------------------
    _s(
        "reports.general_digits",
        "format",
        "Significant digits of a general number",
        "digits",
        10,
        "reports.numfmt:GENERAL_DIGITS",
        "Byte-identical reports need a fixed precision; ten digits show every input exactly.",
        "Columns without a fixed number of decimals.",
    ),
    _s(
        "reports.pdf_cell_limit",
        "format",
        "Characters in a PDF table cell",
        "characters",
        400,
        "reports.pdf:CELL_LIMIT",
        "A longer text would make a row taller than a page.",
        "PDF tables.",
    ),
    _s(
        "reports.xlsx_cell_limit",
        "format",
        "Characters in a spreadsheet cell",
        "characters",
        32000,
        "reports.xlsx:CELL_LIMIT",
        "A spreadsheet cell holds 32,767 characters.",
        "XLSX tables.",
    ),
    _s(
        "reports.xlsx_figure_width_px",
        "format",
        "Width of a figure in a spreadsheet",
        "px",
        1100,
        "reports.xlsx:FIGURE_WIDTH_PX",
        "Fits a normal screen.",
        "Figures in XLSX reports.",
    ),
    _s(
        "reports.xlsx_row_px",
        "format",
        "Row height assumed under a figure",
        "px",
        20,
        "reports.xlsx:ROW_PX",
        "The default row height of a spreadsheet.",
        "Where tables start below a figure in XLSX reports.",
    ),
    _s(
        "reports.docx_property_limit",
        "format",
        "Characters in a document property",
        "characters",
        255,
        "reports.docx:CORE_PROPERTY_LIMIT",
        "The limit of a Word core property.",
        "Title and other properties of DOCX reports.",
    ),
    _s(
        "reports.plot_scale",
        "format",
        "Pixel scale of a plot",
        "factor",
        2,
        "plots.render:SCALE",
        "Sharp plots on high-resolution screens and in print.",
        "Plots in reports.",
    ),
    _s(
        "reports.plot_width_px",
        "format",
        "Width of a plot",
        "px",
        1400,
        "plots.render:WIDTH_PX",
        "A full page width at the plot scale.",
        "Plots in reports.",
    ),
    _s(
        "reports.plot_panel_height_px",
        "format",
        "Height of one panel of a plot",
        "px",
        260,
        "plots.render:PANEL_HEIGHT_PX",
        "Several panels fit one page.",
        "Plots in reports.",
    ),
    _s(
        "reports.plot_block",
        "internal",
        "Samples summarised by one block of a plot",
        "samples",
        64,
        "plots.envelope:BLOCK",
        "Keeps zooming and panning fast (D-182).",
        "How a long series is drawn; the numbers are not changed.",
    ),
    _s(
        "reports.plot_blocks_per_bucket",
        "internal",
        "Blocks summarised by one pixel bucket of a plot",
        "blocks",
        2,
        "plots.envelope:BLOCKS_PER_BUCKET",
        "Keeps zooming and panning fast (D-182).",
        "How a long series is drawn; the numbers are not changed.",
    ),
    _s(
        "reports.result_file_max_bytes",
        "limit",
        "Largest result file that budget verify reads",
        "bytes",
        200_000_000,
        "verify:MAX_EXPORT_BYTES",
        "A result file with long series; far beyond a normal export.",
        "budget verify.",
    ),
    # ---- files and units ---------------------------------------------------------------------
    _s(
        "files.max_yaml_bytes",
        "limit",
        "Largest project file",
        "bytes",
        1_000_000,
        "io.yamlio:MAX_YAML_BYTES",
        "A project file is a few kB; this stops memory and time exhaustion.",
        "Loading every project file.",
    ),
    _s(
        "files.max_yaml_lines",
        "limit",
        "Most lines in a project file",
        "lines",
        20_000,
        "io.yamlio:MAX_YAML_LINES",
        "Checked on the raw text before parsing, so a hostile file is refused quickly.",
        "Loading every project file.",
    ),
    _s(
        "files.max_yaml_line_chars",
        "limit",
        "Most characters in a line of a project file",
        "characters",
        50_000,
        "io.yamlio:MAX_YAML_LINE_CHARS",
        "Checked on the raw text before parsing.",
        "Loading every project file.",
    ),
    _s(
        "files.max_flow_depth",
        "limit",
        "Deepest nesting of [ and { in a project file",
        "levels",
        32,
        "io.yamlio:MAX_FLOW_DEPTH",
        "The YAML scanner is quadratic in the depth of flow nesting.",
        "Loading every project file.",
    ),
    _s(
        "files.max_flow_brackets",
        "limit",
        "Most of each bracket character in a project file",
        "count",
        2_000,
        "io.yamlio:MAX_FLOW_BRACKETS",
        "Checked on the raw text before parsing.",
        "Loading every project file.",
    ),
    _s(
        "files.max_flow_items",
        "limit",
        "Most commas in a project file",
        "count",
        30_000,
        "io.yamlio:MAX_FLOW_ITEMS",
        "Checked on the raw text before parsing.",
        "Loading every project file.",
    ),
    _s(
        "files.max_yaml_depth",
        "limit",
        "Deepest nesting of a project file",
        "levels",
        64,
        "io.yamlio:MAX_YAML_DEPTH",
        "No project file is nested this deep.",
        "Loading every project file.",
    ),
    _s(
        "files.max_yaml_nodes",
        "limit",
        "Most entries in a project file",
        "count",
        60_000,
        "io.yamlio:MAX_YAML_NODES",
        "Parsing costs about 60 microseconds per node.",
        "Loading every project file.",
    ),
    _s(
        "files.unit_table_max_bytes",
        "limit",
        "Largest unit table file",
        "bytes",
        5_000_000,
        "io.unit_table:MAX_FILE_BYTES",
        "A table of a few hundred units is far smaller.",
        "budget units-import and the window's import.",
    ),
    _s(
        "files.unit_table_max_unpacked_bytes",
        "limit",
        "Largest unpacked size of an .xlsx unit table",
        "bytes",
        50_000_000,
        "io.unit_table:MAX_UNPACKED_BYTES",
        "An .xlsx is a zip; one that unpacks to something huge is refused.",
        "budget units-import and the window's import.",
    ),
    _s(
        "files.unit_table_max_rows",
        "limit",
        "Most rows of a unit table",
        "rows",
        100_000,
        "io.unit_table:MAX_ROWS",
        "Far beyond any spacecraft.",
        "budget units-import and the window's import.",
    ),
    _s(
        "files.unit_table_max_columns",
        "limit",
        "Most columns of a unit table",
        "columns",
        50,
        "io.unit_table:MAX_COLUMNS",
        "Far beyond the columns the table has.",
        "budget units-import and the window's import.",
    ),
    _s(
        "units.max_magnitude",
        "limit",
        "Largest magnitude of a number with a unit",
        "canonical unit",
        1.0e20,
        "units.quantity:MAX_MAGNITUDE",
        "Far beyond every physical quantity here, but small enough that squares stay finite.",
        "Every field whose name carries a unit.",
    ),
    # ---- creation defaults and limits of the forms -------------------------------------------
    _s(
        "creation.wizard_eccentricity_ratio",
        "creation",
        "Eccentricity written by the guided mode",
        "ratio",
        0.001,
        "wizard:ECCENTRICITY_RATIO",
        "Near circular, as in the sample orbits.",
        "The orbit file the guided mode writes.",
    ),
    _s(
        "creation.wizard_max_days",
        "creation",
        "Longest scenario the guided mode offers",
        "d",
        180.0,
        "wizard:MAX_DAYS",
        "A run of this length takes under a minute (D-196).",
        "The scenario the guided mode writes.",
    ),
    _s(
        "creation.wizard_max_steps",
        "creation",
        "Most steps in a scenario of the guided mode",
        "steps",
        8640,
        "wizard:MAX_STEPS",
        "A longer scenario gets a coarser step so the first run stays quick.",
        "The step the guided mode writes.",
    ),
    _s(
        "creation.wizard_max_step_s",
        "creation",
        "Coarsest step of the guided mode",
        "s",
        600.0,
        "wizard:MAX_STEP_S",
        "Never so coarse that the orbits are missed (a quarter period).",
        "The step the guided mode writes.",
    ),
    _s(
        "creation.wizard_max_slug",
        "creation",
        "Longest folder name written by the guided mode",
        "characters",
        60,
        "wizard:MAX_SLUG",
        "Fits every file system and keeps paths short.",
        "The project folder the guided mode creates.",
    ),
    _s(
        "creation.min_step_s",
        "creation",
        "Finest step offered by the Add scenario form",
        "s",
        10.0,
        "new_scenario:MIN_STEP_S",
        "The first run stays quick; a longer scenario gets a coarser step.",
        "The scenario the form writes.",
    ),
    _s(
        "creation.max_id",
        "creation",
        "Longest id of a new unit",
        "characters",
        60,
        "new_unit:MAX_ID",
        "The id is a file name: short, typable, portable.",
        "Add unit and the other forms that create a file.",
    ),
    _s(
        "creation.max_text",
        "creation",
        "Longest name or text in a form",
        "characters",
        120,
        "new_unit:MAX_TEXT",
        "Names are labels, not documents.",
        "The forms.",
    ),
    _s(
        "creation.max_name",
        "creation",
        "Longest name of a blank project",
        "characters",
        120,
        "blank:MAX_NAME",
        "Names are labels, not documents.",
        "budget new and the guided mode.",
    ),
    _s(
        "creation.max_file_name",
        "creation",
        "Longest file name written by the tool",
        "characters",
        120,
        "reports.files:MAX_NAME",
        "Fits every file system.",
        "Names of report and result files.",
    ),
    _s(
        "internal.slice",
        "internal",
        "Elements per call of a long computation",
        "elements",
        2048,
        "slices:SLICE",
        "About a millisecond for a conversion or SGP4, so the window stays responsive (D-183).",
        "How long computations are cut; the numbers are bit-identical.",
    ),
)

# Numeric constants of the code that are not settings, with the reason (the completeness test
# knows them): a format version, and example data.
NOT_SETTINGS: dict[str, str] = {
    "result_format:RESULT_FORMAT_VERSION": "The version of the JSON result layout.",
    "examples:MINISAT_PEAK_POWER_W": "Invented example data.",
}

BY_ID: dict[str, SettingSpec] = {spec.id: spec for spec in CATALOGUE}


def spec(setting_id: str) -> SettingSpec | None:
    return BY_ID.get(setting_id)


def of_kind(kind: str) -> tuple[SettingSpec, ...]:
    return tuple(s for s in CATALOGUE if s.kind == kind)


def render_markdown() -> str:
    """The page `docs/models/settings.md`, written from the catalogue."""
    lines = [
        "# Settings, tolerances and constants",
        "",
        "Generated from the catalogue in `budget_core/settings.py` "
        "(`budget settings --markdown`); a test fails when this page is out of date. "
        "Every number the tool applies that no project file shows is listed here with its "
        "value, unit, why it is what it is, and where it acts. Nothing on this page changes "
        "a result by being listed; the values are the ones the code uses.",
        "",
        "**Kinds.** " + " ".join(f"**{KIND_TEXT[k]}**: {_KIND_HELP[k]}" for k in KINDS),
        "",
        "Today every setting is at its default: the project file that changes the settings "
        "meant to be changed (kind *Setting*) is a later step of the plan "
        "([transparency_p4_design.md](../transparency_p4_design.md)).",
        "",
        "**Contents:** " + " · ".join(f"[{_GROUP_TITLE[g]}](#{_anchor(g)})" for g in _groups()),
    ]
    for group in _groups():
        lines += ["", f"## {_GROUP_TITLE[group]}", ""]
        lines += ["| Id | Kind | Value | Unit | Why | Acts on |", "|---|---|---|---|---|---|"]
        for s in CATALOGUE:
            if s.group == group:
                lines.append(
                    f"| `{s.id}` | {KIND_TEXT[s.kind]} | {format_value(s.default)} | {s.unit} | "
                    f"{s.reason} | {s.acts_on} |"
                )
    lines += ["", "Next: [Models](README.md) · [Docs index](../README.md).", ""]
    return "\n".join(lines)


_KIND_HELP = {
    "setting": "meant to be changed for one project.",
    "tolerance": "a numerical tolerance or algorithm limit; changing it changes roundings, "
    "not engineering.",
    "limit": "a limit on the size of an input or a file, against hostile or absurd files.",
    "constant": "a physical constant or a definition.",
    "format": "how a result is written.",
    "creation": "a default or limit of the guided mode and the forms.",
    "internal": "a performance or bookkeeping value with no effect on a result.",
}
_GROUP_TITLE = {
    "environment": "Environment: orbit, passes, eclipses, scenarios",
    "power": "Power",
    "thermal": "Thermal",
    "mass": "Mass",
    "link": "RF link",
    "compare": "Comparison",
    "reports": "Reports and plots",
    "files": "Project files and tables",
    "units": "Units",
    "creation": "Creation: guided mode and forms",
    "internal": "Internal",
}


def _groups() -> list[str]:
    seen: list[str] = []
    for s in CATALOGUE:
        if s.group not in seen:
            seen.append(s.group)
    return seen


def _anchor(group: str) -> str:
    title = _GROUP_TITLE[group].lower()
    return "".join(c for c in title.replace(" ", "-") if c.isalnum() or c == "-")


def format_value(value: float) -> str:
    """The value as the page and the panel show it: whole numbers without a decimal point,
    others in the shortest exact form."""
    if float(value).is_integer() and abs(value) < 1e15:
        return f"{int(value):,}".replace(",", " ") if abs(value) >= 10_000 else str(int(value))
    return f"{value:.12g}"
