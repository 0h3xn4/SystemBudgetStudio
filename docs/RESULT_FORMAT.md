# Result file format (JSON)

Every `.json` file the tool writes next to a report has the same envelope, so another tool can recognise it, check the version of the layout and find out what produced it. This page lists the layouts. The *project* files (YAML) are described in [FILE_FORMAT.md](FILE_FORMAT.md).

Numbers are written at full precision (shortest exact form), in the SI-based units named by the key (`..._w` watts, `..._kg` kilograms, `..._k` kelvin, `..._s` seconds, `..._db` decibels, `..._ratio` fractions, `..._bps` bit/s). A value that could not be computed because an input is a placeholder is `null` (the reports show it as *n/a*); it is never `0`. Keys are sorted, the file is UTF-8, lines end with LF.

## The envelope

Every file has these keys at the top level:

| Key | Meaning |
|---|---|
| `result_format` | `{"name": "system-budget-studio-result", "kind": <kind>, "version": 1}`. Check `name` and `version` first. `version` changes only when a key is renamed, removed or changes meaning; adding a key does not change it. |
| `provenance` | What produced the file: `tool`, `tool_version`, `python_version`, `libraries` (name and version pairs), `project_name`, `project_revision`, `scenario`, `generated` (UTC), `user`, `inputs_digest`, `input_files`, `parameters`. |
| `incomplete` | `true` when the report carries the INCOMPLETE banner (a result needs a placeholder). Not in `scenario_environment` and `comparison`. |
| `problems` | Load and result problems: `severity`, `code`, `message`, `file`, `path`, `line`, `hint`, and for a finding that compares a number with a limit also `actual`, `limit` and `unit` (the number found, the limit and the unit; absent for the others). The rule behind each `code` is in [PROBLEMS.md](PROBLEMS.md). Not in `scenario_environment` and `comparison`. |
| `assumptions` | The configuration numbers the result used: `name`, `value`, `unit`, `source`, `file`, `path`, `placeholder`. Not in `scenario_environment` and `comparison`. |

`provenance.inputs_digest` is the SHA-256 of the loaded model (see [provenance](models/provenance.md)); `provenance.input_files` lists every project file read as `{path, size, sha256}`; `provenance.parameters` is a list of `[name, value]` pairs with the options that change a number (for a comparison: the digests of both sides). `budget verify` checks a project against these.

## Kinds

| `result_format.kind` | Written by | Other top-level keys |
|---|---|---|
| `power_static` | `budget run --budget power` | `modes`: one entry per spacecraft mode with `mode_id`, `mode_name`, `rows` (one per unit: `unit_id`, `unit_name`, `subsystem`, `bus`, `maturity`, `power_mode`, `avg_power_w`, `duty_cycle_ratio`, `effective_power_w`, `peak_power_w`, `margin_ratio`, `margined_power_w`, `margined_peak_w`), `subsystems`, `buses` (each with `converter_efficiency_ratio` and the `average` and `peak` flows) and the spacecraft `average` and `peak` flows. A flow has `load_w`, `unit_margined_w`, `system_margined_w`, `source_w`, `source_margined_w`. |
| `mass_static` | `budget run --budget mass` | `phases`: one entry per mission phase with `phase`, `rows` (`item_id`, `kind`, `name`, `subsystem`, `maturity`, `mass_kg`, `margin_ratio`, `margined_mass_kg`, `position_m`, `own_inertia`), `subsystems`, `total_kg`, `unit_margined_kg`, `system_margined_kg`, `limits` (`name`, `limit_kg`, `total_kg`, `margin_kg`, `status`) and `cog` (centre of mass and inertia). |
| `thermal_static` | `budget run --budget thermal` | `modes` (dissipation per node: `mode_id`, `mode_name`, `nodes`, `rows`, `subsystems`, `total_w`, `peak_total_w`) and `cases` (`case`, `description`, `mode_id`, `limit_set`, `nodes` with `temperature_k`, `absorbed_w`, `radiated_w`, `conducted_out_w`, `dissipation_w`; `checks` with the limits and headroom per unit; `balance_residual_w`; `complete`). |
| `link` | `budget run --budget link`, `budget link-passes` | `static`: one entry per link, point and rate (`link_id`, `link_name`, `direction`, `point`, `elevation_deg`, `range_m`, `frequency_hz`, `eirp_dbw`, `g_over_t_dbk`, `path_loss_db`, `atmospheric_loss_db`, `other_losses_db`, `cn0_dbhz`, `required_ebn0_db`, `required_margin_db`, `rates`, `max_rate_bps`, `max_rate_continuous_bps`). With a scenario also `scenario` (`id`, `start_utc`, `duration_s`, `step_s`) and `links` (`link`, `direction`, `station`, `rates_bps`, `required_margin_db`, `passes` with `aos_s`, `los_s`, `max_elevation_deg`, `minimum_margin_db`, `usable_s`, `volume_bits`; `volume_bits`, `volume_per_day_bits`). |
| `power_timeline` | `budget power-timeline` | `scenario`, `grid` (`start_utc`, `duration_s`, `step_s`, `steps`), `environment` (`source`, `shadow_model`, `eclipse_fraction`, `orbits`), `load_basis`, `mission_phase`, `limits` (`peak_power_w`, `dod_limit_ratio`), `modes` (`mode_id`, `mode_name`, `duration_s`, `load_w`, `demand_w`, `peak_demand_w`), `cases` keyed by case name (`bol`, `eol`: `age_years`, `capacity_wh`, `summary`, `balances`, `violations`), `violations` (`case`, `code`, `start_s`, `end_s`, `extreme`, `limit`, `unit`, `file`, `path`) and `not_evaluated` (the checks that could not run). The time series are in the CSV files, not here. |
| `scenario_environment` | `budget scenario` | `scenario`, `source`, `shadow_model`, `grid`, `eclipse_fraction`, `eclipses` and `umbras` (`start_s`, `end_s`, `duration_s`), `sites` keyed by id (`kind`, `passes`), `timeline` (`start_s`, `end_s`, `mode`) and `notes`. Times are seconds from the scenario start, rounded to 0.001 s. |
| `comparison` | `budget compare` | `label_a`, `label_b`, the counts `compared`, `unchanged`, `values_differ`, `rows_one_sided`, `truncated`, and `differences` and `unmatched` (one entry per row). A difference is "as displayed": a change below the displayed precision is not listed. The provenance describes side A; the digests of both sides are in `provenance.parameters`. |

## Reading these files safely

- Ignore keys you do not know; new keys are added without a version change.
- A `null` is "not available", never zero. `incomplete: true` means at least one number is missing or provisional.
- Compare `inputs_digest` values to know whether two files came from the same model.
- The text of `problems[].message` is for people; use `code` to decide.

Decision: [D-205](DECISIONS.md).
