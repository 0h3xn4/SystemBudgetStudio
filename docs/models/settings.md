# Settings, tolerances and constants

Generated from the catalogue in `budget_core/settings.py` (`budget settings --markdown`); a test fails when this page is out of date. Every number the tool applies that no project file shows is listed here with its value, unit, why it is what it is, and where it acts. Nothing on this page changes a result by being listed; the values are the ones the code uses.

**Kinds.** **Setting (per project)**: meant to be changed for one project. **Numerical tolerance**: a numerical tolerance or algorithm limit; changing it changes roundings, not engineering. **Input limit**: a limit on the size of an input or a file, against hostile or absurd files. **Constant**: a physical constant or a definition. **Output format**: how a result is written. **Creation default**: a default or limit of the guided mode and the forms. **Internal**: a performance or bookkeeping value with no effect on a result.

Today every setting is at its default: the project file that changes the settings meant to be changed (kind *Setting*) is a later step of the plan ([transparency_p4_design.md](../transparency_p4_design.md)).

**Contents:** [Environment: orbit, passes, eclipses, scenarios](#environment-orbit-passes-eclipses-scenarios) · [Power](#power) · [Thermal](#thermal) · [Mass](#mass) · [RF link](#rf-link) · [Comparison](#comparison) · [Reports and plots](#reports-and-plots) · [Project files and tables](#project-files-and-tables) · [Units](#units) · [Creation: guided mode and forms](#creation-guided-mode-and-forms) · [Internal](#internal)

## Environment: orbit, passes, eclipses, scenarios

| Id | Kind | Value | Unit | Why | Acts on |
|---|---|---|---|---|---|
| `environment.detection_step_s` | Setting (per project) | 20 | s | Fine enough to find every pass and eclipse of a low orbit, whatever the scenario step. | The grid on which passes and eclipses are found; also sets the largest scenario (max_samples). |
| `environment.tle_max_age_days` | Setting (per project) | 30 | d | A TLE is accurate for days to a few weeks; older ones give the warning ORBIT_EPOCH_FAR. | The warning ORBIT_EPOCH_FAR (a TLE epoch this far from the scenario start). |
| `environment.max_samples` | Setting (per project) | 1 000 000 | samples | About 11 days at 1 s; a week at 1 s (604,801) is the design case. | Refuses a scenario with more time steps (duration over the finer of the step and the detection grid). |
| `environment.sunlight_threshold_ratio` | Numerical tolerance | 0.999999999999 | ratio | Any shadow counts as eclipse, penumbra included (D-146, DEVIATIONS DV-E4). | The edges of eclipses and the umbra. |
| `environment.umbra_ratio` | Numerical tolerance | 1e-12 | ratio | Numerical zero of the sunlight ratio (D-146, DEVIATIONS DV-E4). | The umbra. |
| `environment.edge_tolerance_s` | Numerical tolerance | 0.001 | s | About 1 ms: far below any step and any time the results show. | Bisection of every pass and eclipse edge. |
| `environment.max_rules` | Input limit | 10 000 | count | Keeps the timeline of a scenario small enough to build and show. | Refuses a scenario with more rules or segments. |
| `environment.min_year` | Input limit | 1950 | year | The Sun and Earth models and the TLE epoch convention are meant for this range (D-120). | Dates of scenarios and element epochs. |
| `environment.max_year` | Input limit | 2100 | year | The Sun and Earth models and the TLE epoch convention are meant for this range (D-120). | Dates of scenarios and element epochs. |
| `environment.timeline_epsilon_s` | Numerical tolerance | 1e-09 | s | A gap or overlap this small between modes is rounding, not a sliver of time. | The mode timeline of a scenario. |
| `environment.imported_file_max_bytes` | Input limit | 250 000 000 | bytes | A file is read whole: a week at 1 s is 604,801 rows of about 120 bytes. | Import of SpaceMissionStudio files. |
| `environment.imported_max_rows` | Input limit | 2 000 000 | rows | A file is read whole, so it is bounded. | Import of orbit.csv and profile_<site>.csv. |
| `environment.imported_max_pass_rows` | Input limit | 100 000 | rows | A file is read whole, so it is bounded. | Import of eclipse.csv and passes_<site>.csv. |
| `environment.full_hash_bytes` | Internal | 16 777 216 | bytes | Up to this size the content is hashed whole (D-212); larger files by size, time and ends. | Whether a computed environment can be reused. |
| `environment.edge_hash_bytes` | Internal | 1 048 576 | bytes | A large file is identified by its size, time and its first and last megabyte (D-212). | Whether a computed environment can be reused. |

## Power

| Id | Kind | Value | Unit | Why | Acts on |
|---|---|---|---|---|---|
| `power.ratio_tolerance` | Numerical tolerance | 1e-09 | ratio | A limit that is met exactly must not be reported because of rounding noise. | The depth-of-discharge finding of the power timeline. |
| `power.power_tolerance_w` | Numerical tolerance | 1e-09 | W | A limit that is met exactly must not be reported because of rounding noise. | The peak-power finding and the test for an empty battery. |
| `power.energy_tolerance_wh` | Numerical tolerance | 1e-06 | Wh | A balance that is zero within rounding is not negative. | The negative orbit balance finding. |
| `power.refine_tolerance_s` | Numerical tolerance | 1e-06 | s | Instants closer than this to an existing edge are the same edge. | The refinement of the power timeline. |
| `power.penumbra_min_s` | Numerical tolerance | 0.01 | s | A ramp from sunlight to umbra shorter than this is a sharp edge. | How the array output changes at an eclipse edge. |
| `power.max_refine_rounds` | Numerical tolerance | 4 | rounds | The instants are found on a grid that already holds them; four rounds are enough in practice and POWER_REFINEMENT_INCOMPLETE says when they were not. | The refinement of the power timeline. |
| `power.max_strings` | Input limit | 10 000 | count | Input sanity: far beyond any array. | Validation of power_system.yaml. |
| `power.max_cells_per_string` | Input limit | 10 000 | count | Input sanity: far beyond any array. | Validation of power_system.yaml. |
| `power.max_cells_in_series` | Input limit | 1000 | count | Input sanity: far beyond any battery. | Validation of power_system.yaml. |
| `power.max_cells_in_parallel` | Input limit | 10 000 | count | Input sanity: far beyond any battery. | Validation of power_system.yaml. |
| `power.max_direction_component` | Input limit | 1 000 000 | ratio | Input sanity: a direction is normalised, so a huge component is a slip. | Validation of power_system.yaml. |
| `power.min_direction_length` | Input limit | 1e-06 | ratio | A direction of nearly zero length has no direction. | Validation of power_system.yaml. |

## Thermal

| Id | Kind | Value | Unit | Why | Acts on |
|---|---|---|---|---|---|
| `thermal.accuracy_k` | Numerical tolerance | 0.0001 | K | Far below the accuracy of any thermal input. | The steady-state solution of the thermal network. |
| `thermal.refine_rounds` | Numerical tolerance | 8 | rounds | The Newton solution is refined until a correction is rounding. | The steady-state solution of the thermal network. |
| `thermal.refined_k` | Numerical tolerance | 1e-07 | K | A correction below this is rounding: the temperatures are as good as they get. | The steady-state solution of the thermal network. |
| `thermal.stefan_boltzmann_wm2k4` | Constant | 5.670374419e-08 | W/(m2 K4) | Exact in the 2019 SI (defined from h, k and c). | Radiation of every surface (TH-RAD). |
| `thermal.celsius_offset_k` | Output format | 273.15 | K | Definition of the Celsius scale; used for display only, the model works in kelvin. | The Celsius columns of the thermal report. |

## Mass

| Id | Kind | Value | Unit | Why | Acts on |
|---|---|---|---|---|---|
| `mass.limit_tolerance_ratio` | Numerical tolerance | 1e-09 | ratio | A limit met to within rounding noise is met (as in D-097). | The status of a mass limit. |

## RF link

| Id | Kind | Value | Unit | Why | Acts on |
|---|---|---|---|---|---|
| `link.pass_sample_s` | Numerical tolerance | 5 | s | A pass is sampled at this step when the environment gives the exact geometry, so the results do not depend on the scenario step (D-057, DV-L3). | The margin and rate over a pass, and the data volume. |
| `link.day_s` | Constant | 86 400 | s | Definition; the data volume per day is scaled with it. | The data volume per day. |
| `link.speed_of_light_ms` | Constant | 299 792 458 | m/s | Exact by the definition of the metre (SI). | Free-space path loss and wavelength. |
| `link.boltzmann_jk` | Constant | 1.380649e-23 | J/K | Exact in the 2019 SI. | C/N0 (noise power density). |
| `link.earth_radius_m` | Constant | 6 378 137 | m | WGS-84 equatorial radius; the same value as the environment module. | Geometry of the link when it is not given by the environment. |

## Comparison

| Id | Kind | Value | Unit | Why | Acts on |
|---|---|---|---|---|---|
| `compare.max_rows` | Setting (per project) | 200 | rows | Keeps a report readable; the CSV and JSON files list every difference. | The comparison report and the Compare page (option --max-rows). |

## Reports and plots

| Id | Kind | Value | Unit | Why | Acts on |
|---|---|---|---|---|---|
| `reports.general_digits` | Output format | 10 | digits | Byte-identical reports need a fixed precision; ten digits show every input exactly. | Columns without a fixed number of decimals. |
| `reports.pdf_cell_limit` | Output format | 400 | characters | A longer text would make a row taller than a page. | PDF tables. |
| `reports.xlsx_cell_limit` | Output format | 32 000 | characters | A spreadsheet cell holds 32,767 characters. | XLSX tables. |
| `reports.xlsx_figure_width_px` | Output format | 1100 | px | Fits a normal screen. | Figures in XLSX reports. |
| `reports.xlsx_row_px` | Output format | 20 | px | The default row height of a spreadsheet. | Where tables start below a figure in XLSX reports. |
| `reports.docx_property_limit` | Output format | 255 | characters | The limit of a Word core property. | Title and other properties of DOCX reports. |
| `reports.plot_scale` | Output format | 2 | factor | Sharp plots on high-resolution screens and in print. | Plots in reports. |
| `reports.plot_width_px` | Output format | 1400 | px | A full page width at the plot scale. | Plots in reports. |
| `reports.plot_panel_height_px` | Output format | 260 | px | Several panels fit one page. | Plots in reports. |
| `reports.plot_block` | Internal | 64 | samples | Keeps zooming and panning fast (D-182). | How a long series is drawn; the numbers are not changed. |
| `reports.plot_blocks_per_bucket` | Internal | 2 | blocks | Keeps zooming and panning fast (D-182). | How a long series is drawn; the numbers are not changed. |
| `reports.result_file_max_bytes` | Input limit | 200 000 000 | bytes | A result file with long series; far beyond a normal export. | budget verify. |

## Project files and tables

| Id | Kind | Value | Unit | Why | Acts on |
|---|---|---|---|---|---|
| `files.max_yaml_bytes` | Input limit | 1 000 000 | bytes | A project file is a few kB; this stops memory and time exhaustion. | Loading every project file. |
| `files.max_yaml_lines` | Input limit | 20 000 | lines | Checked on the raw text before parsing, so a hostile file is refused quickly. | Loading every project file. |
| `files.max_yaml_line_chars` | Input limit | 50 000 | characters | Checked on the raw text before parsing. | Loading every project file. |
| `files.max_flow_depth` | Input limit | 32 | levels | The YAML scanner is quadratic in the depth of flow nesting. | Loading every project file. |
| `files.max_flow_brackets` | Input limit | 2000 | count | Checked on the raw text before parsing. | Loading every project file. |
| `files.max_flow_items` | Input limit | 30 000 | count | Checked on the raw text before parsing. | Loading every project file. |
| `files.max_yaml_depth` | Input limit | 64 | levels | No project file is nested this deep. | Loading every project file. |
| `files.max_yaml_nodes` | Input limit | 60 000 | count | Parsing costs about 60 microseconds per node. | Loading every project file. |
| `files.unit_table_max_bytes` | Input limit | 5 000 000 | bytes | A table of a few hundred units is far smaller. | budget units-import and the window's import. |
| `files.unit_table_max_unpacked_bytes` | Input limit | 50 000 000 | bytes | An .xlsx is a zip; one that unpacks to something huge is refused. | budget units-import and the window's import. |
| `files.unit_table_max_rows` | Input limit | 100 000 | rows | Far beyond any spacecraft. | budget units-import and the window's import. |
| `files.unit_table_max_columns` | Input limit | 50 | columns | Far beyond the columns the table has. | budget units-import and the window's import. |

## Units

| Id | Kind | Value | Unit | Why | Acts on |
|---|---|---|---|---|---|
| `units.max_magnitude` | Input limit | 1e+20 | canonical unit | Far beyond every physical quantity here, but small enough that squares stay finite. | Every field whose name carries a unit. |

## Creation: guided mode and forms

| Id | Kind | Value | Unit | Why | Acts on |
|---|---|---|---|---|---|
| `creation.wizard_eccentricity_ratio` | Creation default | 0.001 | ratio | Near circular, as in the sample orbits. | The orbit file the guided mode writes. |
| `creation.wizard_max_days` | Creation default | 180 | d | A run of this length takes under a minute (D-196). | The scenario the guided mode writes. |
| `creation.wizard_max_steps` | Creation default | 8640 | steps | A longer scenario gets a coarser step so the first run stays quick. | The step the guided mode writes. |
| `creation.wizard_max_step_s` | Creation default | 600 | s | Never so coarse that the orbits are missed (a quarter period). | The step the guided mode writes. |
| `creation.wizard_max_slug` | Creation default | 60 | characters | Fits every file system and keeps paths short. | The project folder the guided mode creates. |
| `creation.min_step_s` | Creation default | 10 | s | The first run stays quick; a longer scenario gets a coarser step. | The scenario the form writes. |
| `creation.max_id` | Creation default | 60 | characters | The id is a file name: short, typable, portable. | Add unit and the other forms that create a file. |
| `creation.max_text` | Creation default | 120 | characters | Names are labels, not documents. | The forms. |
| `creation.max_name` | Creation default | 120 | characters | Names are labels, not documents. | budget new and the guided mode. |
| `creation.max_file_name` | Creation default | 120 | characters | Fits every file system. | Names of report and result files. |

## Internal

| Id | Kind | Value | Unit | Why | Acts on |
|---|---|---|---|---|---|
| `internal.slice` | Internal | 2048 | elements | About a millisecond for a conversion or SGP4, so the window stays responsive (D-183). | How long computations are cut; the numbers are bit-identical. |

Next: [Models](README.md) · [Docs index](../README.md).
