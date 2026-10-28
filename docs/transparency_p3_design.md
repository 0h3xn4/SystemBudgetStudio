# P3 design: the file-format revision for provenance

Status: **proposed, for review; nothing is implemented.** Decision record: D-213 in [DECISIONS.md](DECISIONS.md). Context: step P3 of the [transparency plan](transparency_audit.md#7-prioritized-implementation-plan).

## 1. What it is for

Today a number from a data sheet can say where it came from (the `source` field of the numbers in `config/*.yaml`); a plain input (a unit's power, a mass, an orbit element, a station position) cannot. The programme asks that any input can carry its source, that invented sample numbers say so, and that a project file tells a tool which features it needs. P3 adds exactly that, once, so that P4 to P8 do not each need their own migration.

P3 changes no result. A project without the new content gives the same numbers, the same reports (apart from the rows below) and the same model digest as today.

## 2. Decisions taken (owner, from the review of the first proposal)

| | Decision |
|---|---|
| Provenance of a plain input | A **side mapping** `provenance:` in the file, keyed by field path; no value changes shape |
| Sample numbers | A status **`illustrative`**; every invented number of `examples/` carries it |
| Release | The format revision ships with P4 and P5 as **2.0.0** |

Three further choices are mine and are open to veto in this review: the path syntax (4.1), the file-level default (4.2) and the `requires` list (4.4). One scope change from the first proposal is explained in section 3.

## 3. Scope, and one change from the first proposal

**In P3:** `provenance:` on the entity files; a `status` on the sourced numbers of the configuration files; `requires:` in `project.yaml`; the one version step for every file kind; the migration; the loader rules and problem codes; the digest rules; Explain, Inspector, reports and a command that show or set a source; the examples marked `illustrative`.

**Not in P3 (changed from the first proposal):** the files `settings.yaml`, `audit/overrides.yaml` and `audit/history.yaml`. A new *file* needs no migration of the existing kinds (an older tool never reads it), so nothing is gained by defining it before the feature that gives it meaning, and a file that is read but does nothing yet is the hidden behaviour this programme exists to remove (an override a user writes must never be silently ignored). `settings.yaml` arrives with P4, the override and history files with P7. What P3 does provide for them is the `requires` list (4.4), so a project that uses one of them cannot be opened by a tool that would ignore it.

## 4. The format

### 4.1 `provenance:` on a file of an entity (unit, spacecraft mode, expendable, orbit, ground station, target, scenario, link, and `spacecraft.yaml`)

```yaml
provenance:
  mass_kg:
    source: "Data sheet XYZ rev C, table 3"
    note: "Flight model, measured"
    status: sourced
  modes[imaging].avg_power_w:
    source: "Thermal-vacuum test report TR-12, section 5"
    status: estimate
```

- **Key:** the path of a number in the file, written as in the Problems panel and in Explain (`modes[1].avg_power_w`), with one addition: in a list whose items have a `name` (the power modes of a unit), `[imaging]` selects the item by name, so inserting or removing a mode does not move the entry. A numeric index is still accepted.
- **Entry:** `source` (text, required), `note` (text, optional), `status` (optional, default `sourced`).
- **Status:** `sourced` (comes from the source named), `estimate` (an engineering estimate; the source says whose), `illustrative` (an invented sample value, not for use), `tbd` (a placeholder; the number is not to be used). A plain input with no entry has no recorded source; that is shown as such and is not an error.
- The keys must be paths that exist in the file; an entry for a path that does not is the warning `PROVENANCE_PATH_UNKNOWN` (a renamed or removed field), never an error.

### 4.2 A file-level default

```yaml
provenance:
  "*":
    source: "Invented example value"
    status: illustrative
```

`"*"` applies to every plain number of the file that has no entry of its own. The example projects use only this line per file, which is also the smallest way to mark a whole file as invented.

### 4.3 `status` on a sourced number (the files of `config/`)

The numbers of `config/*.yaml` already have `source` and `note`; they gain the same optional `status` (`sourced` by default, `estimate`, `illustrative`). The existing placeholder rule is unchanged: `source: TBD` or a null value is a placeholder whatever the status.

### 4.4 `requires:` in `project.yaml`

```yaml
requires: []        # features the project uses that an older tool would ignore
```

A list of feature names. This version knows none yet (P4 adds `settings`, P7 adds `overrides`). A name this version does not know is the error `FEATURE_UNSUPPORTED` ("this project needs a feature this version does not have; upgrade"). A tool without this field refuses the file because `requires` is an unknown key, so the guard works for old and new tools alike. The tool writes a feature into the list when the user creates the file that needs it; nothing else does.

## 5. Versions and migration

One step for every kind, because every kind either gains `provenance` or `status` (or, for `project`, `requires`):

| Kind | Now | After |
|---|---|---|
| project | 1 | 2 |
| spacecraft, expendable, orbit, ground_station, target, link, spacecraft_mode | 1 | 2 |
| unit, scenario | 2 | 3 |
| margin_policy | 2 | 3 |
| power_config, power_system, thermal_model, thermal_environment, mass_limits, ebn0_table, attenuation_table | 1 | 2 |

The migration of each is the identity plus the version number: no key moves. Files are migrated in memory as today (`FILE_MIGRATED`, info) and written in the new version on Save. A tool of an earlier release reads a new file as `SCHEMA_TOO_NEW` with the message to upgrade, which is the honest message (without the step it would say `FIELD_UNKNOWN` about `provenance`). The exported JSON Schemas and the example projects are regenerated, and the tests that fail on drift are updated in the same step.

## 6. What does not change

- **Numbers, solvers, report layouts:** none. The new fields are read and carried, not used by any equation.
- **The model digest** ([provenance.md](models/provenance.md)): `provenance` and `status` are left out of it, as comments are, so a project marked `illustrative` has the digest it had before; `model_to_data` omits the new fields when they are at their default. A test pins the digest of every example before and after.
- **The file manifest:** unchanged; a file edited to add a source changes its hash, as any edit does.
- **Problem messages and hints** stay free of project values; the new codes are in the catalogue.

## 7. Where it shows (the payoff)

- **Explain:** the `source` of a plain input, empty today, is filled from its entry (and its status, when it is not `sourced`).
- **Inspector:** the source, note and status of the selected cell.
- **Reports and exports:** the provenance table gains the row **Illustrative inputs** (a count; zero when none) and the assumptions table gains the status of the sourced numbers. A report built from an example therefore says it contains invented numbers. The golden files change by those rows only.
- **Command line:** `budget source PROJECT FILE PATH --source "..." [--note "..."] [--status ...]` sets an entry (through the same comment-preserving writer as the grids); `budget source PROJECT` lists the inputs by status. The window gets a **Source** field in the Inspector with the same effect, one undo step.
- **Not in P3:** a source column in every grid, and a hard rule that an input without a source is an error (that would be a policy, not a format).

## 8. Examples

`budget export-examples` writes `provenance: {"*": {source: "Invented example value", status: illustrative}}` into every entity file and `status: illustrative` on the sourced numbers of the examples. The examples remain invented data only.

## 9. Tests

- **Migration:** every kind, from its old version, loads and is written in the new one; a file from the new version is refused as `SCHEMA_TOO_NEW` by the old reader (simulated by the previous registry).
- **Digest:** the digest and every result file of every example are unchanged by marking the example (apart from the new rows).
- **Round trip:** an edit in the grids keeps `provenance` and its comments; the patch writer treats it as any mapping.
- **Loader:** the entries validate (status vocabulary, required `source`), a path that does not exist warns, `"*"` applies only to files without an entry of their own, name selectors survive inserting a mode, `requires` with an unknown feature is an error.
- **Explain:** an input with an entry shows its source and status; an input without one shows none.
- **Schemas, catalogue, docs:** the generated files match; the two new problem codes (`PROVENANCE_PATH_UNKNOWN`, `FEATURE_UNSUPPORTED`) are in the catalogue and in `PROBLEMS.md`.

## 10. Order of work

1. **P3a, the format:** models, versions and migration, loader rules and codes, digest rule, schemas, FILE_FORMAT.md, tests of sections 5, 6 and 9.
2. **P3b, the display:** Explain, Inspector, report rows, `budget source`, tests and manual.
3. **P3c, the examples:** regenerate them marked `illustrative`, regenerate the goldens, review the diff.

Each step is its own pull request and leaves the tool working. Nothing is released before P4 and P5 (2.0.0); until then `main` reads files of the new version while the released 1.9.0 does not, so a fix needed for 1.9.x would be cut from the `v1.9.0` tag on a maintenance branch.

## 11. What I ask the reviewer to check

The path syntax with name selectors (4.1); the `"*"` default (4.2); the `requires` list and that the sidecar files wait for P4 and P7 (3, 4.4); the four statuses (4.1); that the digest ignores them (6).
