# P4 design: model settings and the Assumptions panel

Status: **proposed, for review; nothing is implemented.** Decision record: D-217 in [DECISIONS.md](DECISIONS.md). Context: step P4 of the [transparency plan](transparency_audit.md#7-prioritized-implementation-plan); the file revision it relies on is [P3](transparency_p3_design.md) (built).

## 1. What it is for

The tool applies numbers and rules that no file shows: a detection grid of 20 s, a warning at 30 days of TLE age, a sunlight threshold of `1 - 1e-12`, four refinement rounds, 2 decimals here and 4 there, a wizard that starts at 550 km. Some of them a user may rightly want to change; most only need to be **visible**, with their value, their unit, why they are what they are and where they act. P4 does two things:

1. **A catalogue of every such setting** (one entry each: id, group, value, unit, bounds, source or reason, where it acts, whether the project may change it), and **a project file that can change the ones that are meant to be changed**.
2. **An Assumptions panel** (window, `budget assumptions`, and one table in every report) that lists everything active for a project, each with its source and where to edit it.

P4 changes no result: an absent settings file, and a file that repeats the defaults, give today's numbers byte for byte.

## 2. What exists today (from the audit)

About 150 literals are spread over the modules (appendices A to E of the audit). They fall into six kinds, and only the first deserves a switch:

| Kind | Examples | Proposal |
|---|---|---|
| **A. Model settings** a reviewer may legitimately set | detection grid (`DETECTION_STEP_S`, 20 s), TLE age that triggers `ORBIT_EPOCH_FAR` (30 d), the scenario size limit (`MAX_SAMPLES`), the comparison list cap (200) | **editable** in the project file |
| **B. Numerical tolerances and algorithm limits** | `LIT`, `UMBRA`, `EDGE_TOLERANCE_S`, `RATIO_TOL`, `POWER_TOL_W`, `ENERGY_TOL_WH`, `MAX_REFINE_ROUNDS`, the step limit `pi/2` | **shown, fixed**: changing them gives different roundings, not different engineering |
| **C. Input sanity limits** | number of strings and cells, text lengths, years 1950 to 2100, element ranges, file size and line caps | **shown, fixed**: they guard against hostile or absurd files |
| **D. Physical constants and named models** | Earth radius and `mu` (WGS-84 from the SGP4 library), the Sun model, the spherical shadow, TLE on WGS-72 | **shown now**; made **selectable among named sets in P5**, free editing only through an override with a reason (P7), as decided in D7 |
| **E. Output formats** | decimals per column, JSON key order, CSV precision | **shown, fixed** (the precision policy is part of byte-identical reports) |
| **F. Creation defaults** | the wizard's 550 km, 97.6 deg, 180 days, e = 0.001; new-unit duty cycle 1.0; scenario shadow model `cylindrical` when omitted | **shown** with where each is written; a user-level preference is not in this step (section 8) |

Cost of reading a setting: the solvers already take the `Project` (`time_domain_budget(project, run, ...)`, `static_power_budget(project)`, the environment from the scenario), so a settings object can travel on `project.config` without changing any signature.

## 3. The catalogue (one source of truth)

A new module `budget_core/settings.py` holds `CATALOGUE`, an ordered table of `SettingSpec`:

```
id            "environment.detection_step_s"
group         environment | power | thermal | link | compare | output | creation | limits
title         "Detection grid of passes and eclipses"
unit          "s"
default       20.0                       # the value the code has today
bounds        (1.0, 300.0)               # editable settings only
kind          setting | tolerance | limit | constant | format | creation
reason        why this default (decision, source, or "implementation choice")
acts_on       where it matters, in plain words (and the model page)
```

- The modules **import their defaults from the catalogue** instead of holding their own literal (so the code and the table cannot drift). A test checks that no catalogue default differs from the value the solver used before this step (pinned from the audit table), and that every module constant of kinds B to E is registered.
- Kinds B to F are in the catalogue for display only; the loader refuses a settings file that names them (`SETTING_FIXED`), with the reason, so nobody believes a value was applied.

## 4. The project file

`config/model_settings.yaml`, `kind: model_settings`, schema version 1. One entry per editable setting, same shape as the other configuration numbers (value, source, note):

```yaml
schema_version: 1
kind: model_settings
environment:
  detection_step_s:
    value: 10
    source: "Project decision, review 2026-11-03"
    note: "Finer grid for the short passes of the polar station"
  tle_max_age_days:
    value: 14
    source: "Mission operations rule 7"
```

- Absent file, absent group or absent setting: the default; no warning (this is not a placeholder). A **source is required** for a setting that differs from its default (`SETTING_SOURCE_MISSING`, warning), so that a changed assumption always says why.
- Values are validated against the bounds (`SETTING_OUT_OF_RANGE`, error) and the unit rules of the other files (suffix in the name or the catalogue unit).
- Creating the file writes `requires: [settings]` into `project.yaml` (D-213): a tool without settings refuses the project (`FEATURE_UNSUPPORTED`) instead of ignoring the file (`FILE_IGNORED` warning today).
- **Digest.** The file is part of the model digest like any configuration file (a changed grid changes the result). A file that repeats the defaults gives a different digest from no file; that is accepted and documented (the alternative, normalising to the effective settings, hides what the file said).
- **Cache key.** A setting that changes the environment (the detection grid) joins `environment_key`, otherwise a stale environment would be reused.
- Documentation: `docs/models/settings.md` (generated from the catalogue, like `PROBLEMS.md`, with a test for drift) lists every setting, its kind and its reason.

## 5. The Assumptions panel

One list, built from one function (`budget_core/assumptions_view.py`), used by the window, the command line and the reports:

| Section | Rows |
|---|---|
| Configuration numbers | every sourced number of `config/` and the links (already in the reports): value, unit, source, status |
| Model settings | every catalogue entry: active value, default, changed? (marked), source, kind |
| Model choices | shadow model, environment source, load basis, case, mission phase, pointing, detection grid, with where each is set |
| Run options | what the run used (the parameters of the provenance) |
| Defaults written by forms | the creation defaults of kind F and what was written into this project's files from them |

- **Window:** a page of the Model area (and Ctrl+K entry), a filter box, a column "where to edit" whose link opens the file at the line, or the settings page for a catalogue entry; a changed value has the same marker everywhere. Empty sections use `EmptyState`. Built from the model/view classes (can be large).
- **Command line:** `budget assumptions PROJECT [--format text|json] [--section NAME] [--changed]`; prints no project values beyond what the reports print (D-207 holds: the numeric rows follow the report rules).
- **Reports:** the existing table *Configuration numbers used* is unchanged; a new table **Model settings** lists the settings that differ from their defaults (an empty table says "all at defaults"), and the provenance table gets the row **Model settings** (`defaults` or `N changed`). Golden files change by those rows only.
- A settings change is **one undo step** in the window, the same path as any grid edit (`ModelDocument`); the settings page is a small form generated from the catalogue (editable entries only).

## 6. What does not change

Numbers, solvers, report layouts apart from the two additions of section 5, and the default behaviour of every command. Moving a literal into the catalogue must give the same value (a test per constant). The model digest of a project without the file is unchanged (the file is not in the digest when absent).

## 7. Order of work (each its own pull request)

1. **P4a, the catalogue and the file.** `settings.py` with every constant of the audit registered (kinds A to F), the importing of defaults by the modules, the file kind (model, version, loader, codes `SETTING_FIXED`, `SETTING_OUT_OF_RANGE`, `SETTING_SOURCE_MISSING`, `FEATURE_UNSUPPORTED` use), schema, `requires`, digest, `docs/models/settings.md`, tests (every default pinned; round trip; refusal of fixed settings).
2. **P4b, the editable settings act.** The detection grid, the TLE age warning, the sample limit and the comparison cap read the project's value; cache key; characterization tests (defaults identical, a changed value changes the result as documented).
3. **P4c, the Assumptions panel.** `assumptions_view.py`, the window page, `budget assumptions`, the report table and provenance row, goldens regenerated and reviewed, manual and model pages.
4. **P4d, project templates** (only if wanted, see question 5).

Nothing is released before P5 (2.0.0). Each step leaves the tool working.

## 8. Questions for the owner

1. **File name and place.** `config/model_settings.yaml` (my proposal, next to the other configuration files; the P3 text said `settings.yaml` loosely) or a root-level `settings.yaml`?
2. **Which settings are editable in 2.0.0?** My proposal is the four of kind A (detection grid, TLE age warning, scenario size limit, comparison cap). Everything else is shown but fixed until a real need appears. Is the list too short, too long, or the wrong four?
3. **Tolerances (kind B) editable?** I propose not: they are implementation choices, and a reviewer who changes `RATIO_TOL` gets noise. If you want them editable, they would sit behind an "expert" flag with the source required.
4. **Reports: list only changed settings (proposal) or all of them?** All of them is about 60 rows in every report; changed-only keeps reports short and the panel has the full list.
5. **Templates** (the audit's "save a configuration as a named template and apply it to a new project"). A template is a folder of configuration files plus settings that a new project starts from. It needs a place for templates outside any project (a user folder, which the privacy rule restricts to what the user saves on purpose). Now (P4d), later, or not at all?
6. **Creation defaults (kind F)** such as 550 km and 180 days: shown only (proposal), or a per-user preference file the wizard reads? The latter is a new kind of file outside the project and I would keep it for after 2.0.0.

## 9. Tests (outline)

- Every catalogue default equals the value pinned from the audit (and from the code before the change); a constant not in the catalogue fails a test that scans the modules for the named constants.
- A project with no settings file, and one with a file of defaults, give byte-identical results; a changed editable setting changes exactly what its model page says.
- The loader: a fixed setting, a value out of range and a missing source each give their code; the file in an old tool is refused through `requires`.
- The panel: every section is built for every example; the window page edits a setting in one undo step; the command prints no source text and no value that a report would not print.
- The generated pages (`settings.md`, `PROBLEMS.md`, the schemas, the examples) are checked for drift.
