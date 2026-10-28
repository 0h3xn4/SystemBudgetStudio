# Transparency audit (Phase 0)

Status: **Phase 0 only. No code, test, configuration or documentation file other than this one was changed.** Implementation waits for the product owner's review of this document (see [section 8](#8-decisions-needed-from-the-product-owner)).

**Progress after the review** (the owner adopted the recommendations of section 8, decision D-203): P0 (safety net, `docs/changes.md`, two defects fixed) is done; P1 (input digest, run parameters, `budget verify`) is in progress. Later phases follow the order of section 7. The sections below are the audit as it stood at 1.7.0 and are not rewritten as phases land; what changed is recorded in [`changes.md`](changes.md), the [changelog](../CHANGELOG.md) and the pages of [`models/`](models/README.md).

Tool version audited: 1.7.0 (`main` at the merge of PR #78). Date: 2026-10-28.

Task context: engineering teams find the tool a "black box" and too restrictive. The users are experienced spacecraft systems engineers who must verify, defend and adapt every number in a design review. The target principles are: glass box, nothing hidden or hard-coded, engineer stays in control, progressive disclosure. The task lists 14 requirements; section 3 scores the tool against each of them.

## Contents

1. [How this audit was made](#1-how-this-audit-was-made)
2. [Summary](#2-summary)
3. [The 14 requirements: where the tool stands](#3-the-14-requirements-where-the-tool-stands)
4. [Cross-cutting findings](#4-cross-cutting-findings)
5. [Candidate defects found on the way](#5-candidate-defects-found-on-the-way)
6. [Interface inventory](#6-interface-inventory-inputs-and-outputs)
7. [Prioritized implementation plan](#7-prioritized-implementation-plan)
8. [Decisions needed from the product owner](#8-decisions-needed-from-the-product-owner)
9. [Constraints that shape the plan](#9-constraints-that-shape-the-plan)
10. [Limits of this audit](#10-limits-of-this-audit)
11. Appendices A to H: the full findings of the eight area audits (about 975 rows with file and line)

## 1. How this audit was made

The code base is about 38,000 lines in `src/` (core 22,000, window 15,000, command line 800). Eight read-only audits ran in parallel, each over one area, each with the same brief: find every hard-coded constant, default, margin, threshold and rule (A); every hidden assumption (B); every output without a visible derivation (C); every forced single option (D); every input and output exchanged with files or other tools (E); and what already works. Each finding has an ID and a verified file and line. The areas, and where their full tables are:

| Appendix | Area | Files (src/budget_core unless noted) | ID prefix |
|---|---|---|---|
| A | Power, scenario, environment | `power/`, `scenario/`, `environment/`, `timeutil.py`, `slices.py`, `control.py`, `model/power_system.py`, `model/environment.py` | PWR- |
| B | Mass, thermal, units, equations | `mass/`, `thermal/`, `units/`, `equations.py`, `assumptions.py`, `model/` (mass, thermal, equipment, config, base, project, versions) | MAS-, THM-, UNT-, EQN- |
| C | RF link | `link/`, `model/link.py`, `new_link.py`, `new_ebn0.py`, `new_site.py` | LNK- |
| D | Loading, validation, Problems, schemas | `io/`, `problems.py`, `schemas.py` | IOV- |
| E | Project creation and compare | `blank.py`, `wizard.py`, `examples.py`, `new_*.py`, `compare*.py`, `selftest.py` | BLD- |
| F | Reports, plots, provenance, command line, guide generation | `reports/`, `plots/`, `provenance.py`, `guide/`, `budget_cli/` | RPT- |
| G | Window: shell, session, panels | `budget_gui/` (main window, session, model document, panels, dialogs) | GS- |
| H | Window: result views, grids, plots | `budget_gui/` (views, grids, plot widget) | GV- |

Counts of rows (a row is one finding; the same issue can appear in two areas, so these are not unique issues):

| Area | A constants, defaults, rules | B hidden assumptions | C outputs without derivation | D forced options | E interfaces |
|---|---|---|---|---|---|
| Power | 62 | 40 | 16 | 14 | 14 |
| Mass, thermal, units, equations | 63 | 30 | 14 | 12 | 12 |
| Link | 27 | 24 | 12 | 11 | 12 |
| Loading, validation, Problems | 120 | 27 | 11 | 12 | 14 |
| Creation and compare | 52 | 21 | 8 | 9 | 7 |
| Reports, provenance, CLI | 46 | 18 | 22 | 12 | 22 |
| Window shell | 34 | 22 | 14 | 9 | 17 |
| Window views | 41 | 24 | 22 | 17 | 12 |
| **Total** | **445** | **206** | **119** | **96** | **110** |

In addition: all **82 Problem codes** are tabulated against the four elements that requirement 12 asks for (Appendix D).

I (the author of this document) re-ran or re-read the claims that matter most for decisions; they are marked **verified** in section 5. Everything else is as reported by the area audits, who read the code; see section 10 for what was not checked.

## 2. Summary

### What the tool already does well (the plan builds on this)

- **Sourced numbers and placeholders.** Every standards-like number is a `Sourced` value with a mandatory `source`; `source: TBD` marks a placeholder; a result that needs a placeholder shows `n/a`, never `0`; the INCOMPLETE banner and Problems say which. This is the base for "every default visible".
- **"Configuration numbers used" tables** in every report (name, value, unit, source, status, and in JSON file and path).
- **An equation registry** (40 equations, with formulas) rendered into reports and the guide, with an honest `SOURCE_MISSING` marker instead of a made-up citation. A deviations file (DV-*) and a decisions file (D-*) record simplifications.
- **Provenance on every export** (tool, version, nine library versions, project, revision, scenario, UTC time, user), reproducible bytes (`SOURCE_DATE_EPOCH`, fixed zip times).
- **Problems carry code, file, path and line**, double-click jumps to the line.
- **Schema versions with migrations**, the project folder as the only place state lives, atomic writes, a stamp check that refuses to overwrite a file changed on disk.
- **A complete command line** with exit codes, `--strict`, `validate --format json`.

### The diagnosis in one paragraph

The tool is transparent about **configuration numbers** and about **whether** a result is complete. It is not transparent about **how** a number was derived or about the **choices that are not configuration numbers**. Three layers are opaque. (1) Plain-float inputs (unit mass and power, temperature limits, orbit elements, ground stations, positions) have no `source` field at all, so the placeholder mechanism cannot flag them. (2) About 445 constants, tolerances, defaults, limits and policies live as literals in code; a few are documented, almost none are visible in the window or in an export, none is editable. (3) The derivation chain equation → inputs → intermediate values → result is exposed nowhere: reports append the whole equation registry whether used or not, the window shows no equation, and the exports leave out the intermediates (link terms, per-step factors, the thermal network).

### The twelve largest gaps

1. **No Explain.** Nothing ties an equation id to the code that computes it or to an output cell. 37 of 40 equations are `SOURCE_MISSING`. Several computations are not registered at all (system margin application, the mass-limit check, the inertia checks, the thermal solver, unit conversion, the dB helpers and the Celsius display offset). (RPT-C04, MAS/EQN section of Appendix B, GV-C01 to C05)
2. **Unit-level inputs have no source.** Mass, power, duty, temperature limits, areas, positions, orbit elements and stations are plain floats. The thermal documentation claims every thermal number has a source; that is not true for areas and limits. (IOV, MAS, UNT)
3. **No override and no waiver.** A computed value cannot be overridden. All 42 plausibility ranges are hard errors, and any error discards the whole project (`project=None`). (Appendix D, G)
4. **No change history.** Only the in-memory undo stack. `revision` is a hand-edited string. Save, the text editor and the unit-table import are three separate write paths that record nothing. (GS)
5. **Provenance has no input fingerprint.** No project hash, file list, config hash or run parameters; the one existing cache hash uses file size and mtime. A colleague cannot reproduce or even verify a result from an export alone. (RPT-C02, C03)
6. **Problems do not explain themselves.** `Problem` has only message and hint. Of 82 codes, the rule is stated for 72, the reason for 16, a limit for about 8, the actual value for none, an override route for none; three hints are generic and wrong for many cases. (Appendix D, requirement-12 table)
7. **Hidden defaults written into projects.** The wizard and forms write eccentricity 0.001, argument of perigee 90°, mean anomaly 0, the epoch, a derived time step (10 s to 600 s), a shadow model and about 60 invented sample numbers whose "synthetic" source is not treated as a placeholder. (BLD)
8. **Fixed model choices with alternatives.** Two gravity conventions mixed without a choice (WGS-72 inside TLE propagation, WGS-84 for elements and geometry), spherical Earth for the link, nadir-only 1-D antenna pattern, free-space loss only, end-hold in attenuation and pattern lookups, one multiplicative margin per maturity class, Kirchhoff and one shared view ratio in the thermal model, "nominal" load basis as the default for verdicts. (PWR, LNK, MAS/THM)
9. **Units and rounding are implicit in outputs.** `Column.unit` exists but is never rendered; plot cursors carry no unit; Mbit/MByte conversions exist in three places; PDF and DOCX show rounded text, XLSX full doubles, CSVs three different precisions. `1 ton` parses as 907 kg (US short ton). (RPT, GV, UNT)
10. **No extension points and no documented Python API.** Registries are module-level dicts edited in source; `budget_core/__init__.py` exports only the version. (GS cross-cutting, RPT-E19)
11. **Workflow is hard-wired and invisible.** The pipeline exists in three places in code, is never shown as inputs → step → outputs, "up to date" is a reload counter rather than a content hash, and Run works on the saved project while the status tooltip says "from the inputs now on screen". (GS)
12. **Imported data leaves no trace.** The unit-table import records no file name, hash or time; antenna-pattern and imported-environment files are not hashed; nothing watches files for change. (GS, RPT-E14, E15, LNK)

## 3. The 14 requirements: where the tool stands

Scale: **None** (absent), **Minimal** (a hook exists), **Partial** (works for a part of the tool), **Good**.

| # | Requirement | Today | Main gap | Evidence |
|---|---|---|---|---|
| 1 | Calculation trace ("Explain") | **None** | No mapping from outputs to equation, inputs and intermediates; registry not linked to code; intermediates not computed for display or export | RPT-C04/C07/C09, GV-C01..C05, Appendix B EQN |
| 2 | Assumptions panel | **Partial** | An "Assumptions" tab exists in the four static budget views only. It lists sourced configuration numbers, not constants, plain inputs, model choices, run options or form-written defaults; not in timeline, passes, scenario or compare; not editable from there | RPT-B008, GV-B, GS-C |
| 3 | Externalized configuration | **Partial** | Margin policy, power system, thermal model and environment, mass limits, Eb/N0 and attenuation tables are config files. About 445 literals are not, including physical constants, solver tolerances, step policies, limits and form defaults. There is no template or sharing mechanism | A tables of every appendix |
| 4 | Selectable models | **Minimal** | Selectable today: shadow model (cylindrical or conical), load basis, case display, environment source. Missing: gravity and Earth model, Sun model, margin application, thermal simplifications, link loss models and antenna pointing, rate selection policy | PWR-D, LNK-D, MAS-D |
| 5 | Units everywhere | **Partial** | Units are in field names and grid headers. Not shown: plot cursor and tick values, `Column.unit` in exports, source units of typed text; conversions are implicit (canonical units; `ton`; three Mbit/MByte copies) | GV-B, RPT-C21, UNT |
| 6 | Workflow visibility | **Minimal** | "Start here" card and Run chip only. No consumes/produces view, no inspectable or editable intermediates, staleness by counter, Inspector and Provenance hidden by default (D-191) | GS cross-cutting (req 6) |
| 7 | Overrides | **None** | No override of computed or suggested values, no flag, no justification field; hard validation errors cannot be waived | Appendix D summary, GS (req 7) |
| 8 | Change history | **None** (undo only) | Nothing persisted; no who, when, old/new, reason | GS (req 8) |
| 9 | Provenance | **Partial** | Tool, version, libraries, time, user, project, revision, scenario are there. Missing: input hash and file list, configuration used (only `Sourced` numbers appear), run parameters, platform; user defaults to the OS login (personal data in every file) | RPT-C02, RPT-B018 |
| 10 | Open data (CSV/JSON of intermediates) | **Partial** | Final tables and series are exported. Missing: intermediates, equations, constants, an inputs snapshot, an output schema; precision differs by format | RPT-C section, C.1 matrix |
| 11 | Scriptable | **Partial** | The CLI covers runs, compare, units, guide; JSON only for `validate`. No documented Python API; the programmatic export path (`reports.run.*_output`, `load_project`) is undocumented and unpromised | RPT-E19/E20 |
| 12 | Explainable warnings | **Minimal** | Message and hint only; see the 82-code table. The "no project values in messages" rule conflicts with "actual value" (decision D1) | Appendix D |
| 13 | Extensibility | **None** | Module-level dicts and tuples; only `MigrationRegistry` is injectable; no entry points | GS (req 13) |
| 14 | Visible data links | **Minimal** | The unit-table import is the one tool-to-tool import; it records nothing; no change detection except at save and F5; pattern and imported-environment files not hashed; exports not shaped for consumers | GS (req 14), RPT-E, LNK-E |

## 4. Cross-cutting findings

These are the findings that recur across areas and decide the architecture of the plan.

**T1. Three kinds of numbers, only one is tracked.** `Sourced` numbers (config, links) have value, source, note and a placeholder state. Inputs in `units/`, `modes/`, `orbits/`, `ground_stations/`, `targets/`, `expendables/` do not. Constants and tolerances in code have a source string only for the physical constants (and those only appear in the guide). The plan needs one uniform notion of "a number with provenance" across all three.

**T2. Duplicated literals will drift.** Examples: the Earth radius exists twice (`environment/constants.py:23`, `link/constants.py:14`, the latter hard-coded) and again as `EARTH_RADIUS` used for altitude in `new_scenario.py` and `wizard.py`; the year range 1950 to 2100 in `timeutil.py:12` and `model/environment.py:18` and as "year 2101" in `new_scenario.py:203`; the 0 to 180 degree antenna rule in `model/link.py:36` and `link/evaluate.py:253`; the 1e-9 tolerance family in at least five places; the 200-row compare cap in three; Mbit/MByte conversions in `link_view.py`, `budget_cli/main.py` and `link_report.py`; GUI spin-box ranges that the core checks then refuse (0 to 100,000 km vs 160 to 2000 km; 1000 days vs 180). Externalizing must collapse duplicates first.

**T3. Hard errors with no way out.** Every plausibility range (42) and every pydantic bound is an error that makes the project unusable. Engineers legitimately need to model out-of-range cases (a deliberately odd design for a trade study). Requirement 7 needs a waiver with a reason, which means a load pipeline that can carry "accepted with justification" through to every output.

**T4. Rounding is policy, and it is scattered.** `GENERAL_DIGITS=10` in two places, per-column decimals in every report builder, compare reading "as displayed", CSV `repr` in one family and fixed 6, 3, 1 places in another, scenario JSON rounded to 3, 4 or 6 places. A user-visible precision policy (and full-precision in machine-readable output) is a prerequisite for "reproduce a colleague's result".

**T5. Privacy rule versus glass box.** CLAUDE.md: Problems and messages never contain values read from project files; no project content in logs, temp files, crash dumps. Requirement 12 asks for actual values in warnings. The audits found: limits were never covered (they are constants or configuration); values already appear in result tables and the unit-import preview; the rule exists so project content cannot leak through logs and crash dumps. A narrow carve-out (values may appear in widgets, reports and exports the user creates; never in logs, crash dumps or layout files) satisfies both. This is **decision D1**.

**T6. Byte-identical outputs and golden files.** Every report is deterministic and 88 golden files plus the committed schemas and examples fail on drift. Any new column, row, provenance field or model field changes them. The plan therefore (a) captures current outputs first, (b) adds new content in new places (new sections, new files) before touching existing ones, and (c) regenerates goldens only deliberately and one phase at a time.

**T7. One format revision, not many.** Each model-field change needs a schema version bump and a migration. The plan batches all file-format changes into a single, additive revision (new optional fields and new optional files; an old project loads unchanged and results do not move).

**T8. The window shows report tables verbatim.** The result views render `ReportDocument` tables, so a new report column reaches the window, the five export formats, compare and the goldens at once. Window-only data must use the existing window-only fields (`status_column`, `status_marks`, `bar`).

## 5. Candidate defects found on the way

The constraint says: do not change existing numerical results unless a bug is found, and document a bug with before and after values in `docs/changes.md`. None of the following is changed in Phase 0. They are listed so you can decide which are bugs and which are documented behaviour. **Verified** means I re-ran or re-read it myself; **reported** means an area audit found it by reading code and I did not independently check it.

| # | Finding | Status | Effect on numbers | Suggested handling |
|---|---|---|---|---|
| V1 | `1 ton` is accepted and parsed as **907.18 kg** (pint's default registry: US short ton). `1 t` is 1000 kg. A systems engineer reading "ton" will usually mean the metric tonne. | **Verified** (ran `parse_quantity("1 ton", "mass_kg")`) | Any project that wrote "ton" gets 9.3 % less mass than the metric reading | Decision D2: refuse "ton" with a message naming `t` and `lb`, or define it explicitly; record in `docs/changes.md` |
| V2 | TLE propagation uses the sgp4 default gravity constants **WGS-72** (radius 6378.135 km, mu 398600.8); element-based orbits use **WGS-84**; all geometry (altitude, eclipse, link) uses the WGS-84 radius. The user cannot choose and nothing says so. WGS-72 for TLEs is the conventional pairing, so this may be right, but it is undocumented. DV-E2 covers only the elements path. | **Verified** (`elements.py:47` passes no constant set; ran `Satrec.twoline2rv`: 6378.135 km) | None until a model choice is added; document first | Document in DEVIATIONS and in `docs/models/`; offer as a selectable model (phase 5) |
| V3 | If all 4 refinement rounds still add edges, the battery `traces` belong to the previous edge set while `prepared` was rebuilt on the finer one (`power/time_domain.py:482-496`), and no warning is raised for non-convergence. | **Verified by reading**; not reproduced (needs a case that does not converge in 4 rounds) | Unknown; possibly none in practice | Phase 1 characterization test with a forced low round count; add a "not converged" warning |
| V4 | The "Minimum allowed" depth-of-discharge line is drawn on the SOC plot only when a DoD violation exists (`plots/power.py:52-75`); a compliant design never shows its limit. | Reported | None | Always draw the limit (display change) |
| V5 | The Orbits tab colours an energy balance red below 0 (`timeline_view.py:699`) while the core flags it only below −1e-6 Wh (`time_domain.py:1022`). | Reported | None | Use one threshold, show it |
| V6 | Generic and wrong hints: `FIELD_INVALID` always says "Write a number in W…", also for "peak below average" and for ratios; `CONFIG_VALUE_INVALID` always says "ratios are written as fractions", also for dB, K and dBi; `YAML_SYNTAX` always says "check indentation", also for size and alias refusals. | Reported | None | Phase 6 |
| V7 | Documentation that is not true: thermal docs say every thermal number has a source (not areas, limits); FILE_FORMAT says anchors are unsupported but a lone anchor loads; FILE_FORMAT says the JSON schemas carry the limits (only the pydantic bounds); `reports-and-exports.md:56` describes CSV precision wrongly; `max_elevation_deg` is missing from `link-budget.md`; DV-M3 recommends a per-phase expendable position that the model cannot express. | Reported | None | Fix in the phase that touches each area |
| V8 | Wizard and forms write unseen values (eccentricity 0.001, argument of perigee 90°, mean anomaly 0, epoch = start, a derived step up to 600 s, `cylindrical` shadow in new scenarios vs `conical` in two samples). A coarse step samples an eclipse at about three points and can silently skip the orbit-balance check (D-196). | Reported | Depends on the project | Show on the Review page; make editable |
| V9 | **Run uses the saved project** while grid edits are unsaved, but the status tooltip says "Everything was worked out from the inputs now on screen" (`main_window.py:1447`). `run_controller.run()` has no unsaved-edits check. | Reported, consistent with a read of `run_controller.py` | None | Warn or save first; tie "up to date" to a content hash |
| V10 | `save_edited_data` can fall back to a whole-file rewrite that drops all comments (where users keep sources, per D-102) and returns `canonical=True`; its only caller ignores it (`model_document.py:421`). | Reported; the call site checked (return value unused) | None | Tell the user before it happens |
| V11 | The OS login name is written into every export, including document author properties. | Reported | None | Decision D4 (opt-in user) |
| V12 | Hash-less cache key for imported environments uses file size and mtime (`scenario/run.py:202`). A same-size edit within one mtime tick reuses a stale environment. | Reported | Possible stale environment | Content hash |
| V13 | The thermal check table omits the required margin, so a `margin` status cannot be reproduced from it. | Reported | None | Add column in the explain trace |

No defect found so far changes a number the tool prints for a correct input except V1 (a units ambiguity) and V3 (unproven). Everything else is missing visibility, not wrong arithmetic.

## 6. Interface inventory (inputs and outputs)

Full rows with file and line are in the "E" section of each appendix. Consolidated:

**Read**
- The project folder: `project.yaml`, `spacecraft.yaml`, `units/`, `modes/`, `config/` (margin policy, power system, thermal environment and model, mass limits, Eb/N0 table, attenuation table), `links/`, `orbits/`, `ground_stations/`, `targets/`, `scenarios/`, `expendables/`. The loader warns about ignored files and folders. **No output lists the files read or hashes them.**
- Optional side inputs: antenna pattern file (`pattern_file`, inside the project folder; not hashed), the imported-environment CSV folder (`spacemissionstudio` format; cache key from name, size and mtime), TLE lines inline in the orbit file, unit power-mode tables (CSV or XLSX; import source not recorded).
- Environment variables: `SOURCE_DATE_EPOCH`, `BUDGET_USER`, `BUDGET_NO_LAYOUT`, the OS account name (via `getpass`).
- Bundled assets read at run time: IBM Plex and Inter and JetBrains Mono font files, icons, the guide chapters; installed library metadata (nine libraries) for provenance.
- The clipboard (grid copy and paste); the operating system's file dialogs.

**Written**
- Next to the project or in `--out`: `<prefix>.xlsx`, `.pdf`, `.docx`, `.json` and CSV sets, `*_provenance.csv`, scenario files (`*_environment.json`, `*_eclipses.csv`, `*_passes.csv`, `*_timeline.csv`), `compare*` files and `compare_differences.csv`, `unit_power_modes.csv|xlsx`, the guide (`.html`, `.pdf`), JSON Schemas, example projects. Writes are atomic through temporary files `.name.pid.tmp` in the same folder.
- Project files on Save: only the changed files, patched in place so comments survive in the normal case; deleted files after a question; unit-table `--apply` writes `units/*.yaml` by a separate path.
- The only state outside the project: `layout.ini` (window layout, four fixed groups, UI words only; D-105, D-150).

**Invisible or implicit today**
- Which files a result came from (no manifest); which library builds produced it (versions only); the personal user name in file properties; the temporary files; the in-memory scenario cache; the end-hold and clipping behaviour of table lookups; the unit canonicalisation (typed "200 g" becomes `0.2` and the original text is lost on load).

## 7. Prioritized implementation plan

### Principles for every phase

- **Tests first.** Before a phase touches an area, characterization tests capture today's outputs for that area (all example projects and the synthetic cases). Where a golden file already exists it is kept.
- **Numbers do not move.** New settings default to today's values; a settings file that is absent means today's behaviour. A phase ends with the full suite green and the goldens unchanged except where the phase deliberately adds output (those goldens are regenerated once, reviewed, and listed in the PR).
- **New content goes into new places first** (new sections, new sidecar files, new JSON keys), so existing columns and rows stay put.
- **Additive file-format changes only, batched** into one revision (phase 3), with one migration.
- **Documentation per model, rule and assumption** goes into `docs/models/` in the same phase that makes it visible, in plain systems-engineering language, with the equation, the symbols and units, the source (or an honest "source to be supplied"), and the known limits. Bugs go to `docs/changes.md` with before and after values.
- **Working software after each step.** Each phase is a PR (or several), releasable on its own.

### Phases, in the recommended order

| Phase | Name | Requirements | What is delivered (user-visible) | Impact on numbers | File format | Size |
|---|---|---|---|---|---|---|
| **P0** | Safety net | all | Characterization tests for every solver and every export; test for V3 and V9; `docs/changes.md` created; `docs/models/` skeleton | none | none | M |
| **P1** | Provenance and reproducibility | 9, 10, 11 (part), 14 (part) | A content-based **input manifest** (every file read, with a hash) and a **configuration digest** in every export; run parameters (basis, case, phase, step, shadow model) in provenance; `budget verify <export> <project>` that says whether a project reproduces a result; per-format precision policy documented; output JSON gets a schema and version; user name opt-in | none | none (outputs only) | M |
| **P2** | The glass box core: calculation trace | 1, 5 | A **trace** for each output: equation id, formula, inputs with units, intermediates, result, source. Static power, mass, thermal and link first, then time-domain and pass summaries (aggregates and a chosen sample). A registry-to-code binding and a test that every computed quantity has an id. `budget explain`; trace in JSON and an "Explain" sheet or section. **Window: an Explain panel opened from any result cell** (one click, hidden by default) | none | none | XL |
| **P3** | One additive format revision | 2, 3, 7, 8 (foundation) | Optional `source` and `note` on plain inputs (units, orbit, stations, positions); a project `settings` file kind for model settings; `audit/overrides.yaml` and `audit/history.yaml` sidecar file kinds; migration; schemas and examples regenerated | none (absent = today's behaviour) | **one bump, one migration** | L |
| **P4** | Externalized configuration and assumptions panel | 2, 3, 4 (part) | Constants, tolerances, step policies, limits and defaults move into `config/model_settings.yaml` (units, comments, source), defaults identical; duplicates collapsed first (T2). **Assumptions panel** lists everything active (config numbers, constants, model choices, run options, defaults written by forms), each with its source and a link to where to edit it. Project **templates**: save a configuration as a named template, apply to a new project | none | uses P3 | XL |
| **P5** | Selectable models | 4 | A model registry with a visible active choice: gravity and Earth model, Sun model, shadow model, load basis, margin application, link loss terms and antenna pointing model, rate selection policy, thermal simplifications where a defensible alternative exists. Always displayed in reports and the Assumptions panel | none by default | uses P3, P4 | L to XL (per model) |
| **P6** | Explainable warnings | 12 | `Problem` gets rule id, rationale, actual, limit, unit and resolution/override route; every one of the 82 codes completed; wrong hints fixed; per-code documentation page; carve-out for privacy (D1) | none | none | L |
| **P7** | Overrides and change history | 7, 8 | Override any computed or suggested value with a **justification**; re-validation and a stated consequence; the value is marked **overridden** in every view and export; hard validation errors become waivable with a reason; an append-only **history** (who, when, old, new, reason) written by Save, the text editor and the unit-table import through one path | none unless the user overrides | uses P3 | XL |
| **P8** | Workflow visibility | 6 | A pipeline view (step, what it consumes, what it produces, status), intermediate results browsable and, where meaningful, editable between steps; staleness by content hash; Run warns about unsaved edits (V9); Inspector and Provenance reachable in one click (D5) | none | none | L |
| **P9** | Open data and visible data links | 10, 14 | All intermediates exportable (CSV and JSON); import records (path, hash, time, imported values) for the unit table, pattern files and imported environments; "source changed" detection at load and on demand; exports shaped for other tools (stable keys, units, provenance) | none | uses P3 | L |
| **P10** | Extensibility and API | 11, 13 | A documented, versioned Python API (`budget_core.api`), registries for models, rules, item types, equations and report kinds, discovery by entry point and by a user plug-in folder; worked examples; plug-in trust model (D6) | none | none | XL |

Sizes are relative effort: M a few days of work, L about a week or two, XL several weeks. They are estimates from the audit, not commitments.

### Why this order

1. **P0 and P1 are cheap, safe and valuable on their own.** They change no model and give the "reproduce a colleague's result" capability immediately.
2. **P2 (Explain) is the heart of the request** and does not need any file-format change, so it comes before the format revision. It also forces the registry-to-code binding that P4 to P6 need.
3. **P3 comes just before the features that need new file content**, so one migration serves P4, P5 and P7.
4. **P6 (warnings) comes before P7 (overrides)**, because a waiver needs the structured rule id.
5. **P8 to P10** build on the earlier structures and can be re-ordered by priority.

A release rhythm that fits the project: P0+P1 → 1.8.0; P2 → 1.9.0; P3+P4+P5 → 2.0.0 (the file-format revision); P6 → 2.1.0; P7+P8 → 2.2.0; P9+P10 → 2.3.0. This is a suggestion (decision D9).

### Smallest useful first step

If you want a first deliverable within a week: **P0 plus the input manifest and run parameters of P1**. It answers "can I reproduce this?" and "which files and settings produced this?" without touching any model.

## 8. Decisions needed from the product owner

I will not start P0 until you have reviewed this. These are the points where the code cannot decide for you.

| # | Question | My recommendation |
|---|---|---|
| D1 | **Privacy rule versus actual values.** Allow actual and limit values in warnings, shown in the Problems panel, reports and exports, while still never writing project values to logs, crash dumps, temporary files outside the project or `layout.ini`? | Yes. Limits are configuration; actual values already appear in result tables. Keep the ban for logs and crash dumps. |
| D2 | **"ton".** Refuse the word and require `t`, `tonne` or `lb`? Or define it as metric? | Refuse with a message that names the options (a silent 9 % difference is worse than an error). Treat as a documented behaviour change in `docs/changes.md`. |
| D3 | **What the input hash covers.** Raw file bytes (comments change it; comments carry sources per D-102) or the parsed canonical model (comments do not)? | Both: a manifest with raw-byte hashes per file, and one digest of the parsed model. Reproducibility uses the model digest; the manifest shows exactly what was read. |
| D4 | **Who is recorded.** The OS login is written into every file today. Keep, make opt-in, or let the project name an author? | Opt-in; default is "unknown" in exports and the history uses a name the user types once per project. |
| D5 | **Inspector and Provenance visibility.** They are hidden in the focused view by D-191. Keep that default and add a one-click "Explain" entry? | Keep the default; add Explain to the right-click menu, Ctrl+K and a shortcut (one click away, as the task asks). |
| D6 | **Plug-in trust.** Allow loading Python plug-ins from a folder the user controls (executes arbitrary code; the tool is offline and has no telemetry)? Or only declarative plug-ins (YAML models, rule files) first? | Start declarative and registry-based (no code loading) in P10a; add code plug-ins as an explicit, opt-in setting with a visible warning in P10b. |
| D7 | **Physical constants.** Speed of light, Boltzmann and the Earth radius were fixed in code by owner decisions D-054, D-078, D-141. Keep them fixed but visible, and make only *named sets* selectable (WGS-84, WGS-72)? Or make them freely editable? | Visible always, selectable among named sets, free editing only through an override with a reason. |
| D8 | **Synthetic sample numbers.** Introduce a distinct status ("illustrative") so sample projects show their invented numbers as not-for-use, without reusing `TBD`? | Yes; it needs one new status in the format revision (P3). |
| D9 | **Versioning and releases.** Treat the format revision as 2.0.0? Release each phase, or batches? | As in section 7: batches, 2.0.0 for P3 to P5. |
| D10 | **Scope and order.** All 14 requirements are a multi-release programme (roughly P0 to P10). Do you want the whole programme in this order, or a subset first (for example P0, P1, P2, P6)? | P0, P1, P2, P6 first: they need no format change and answer the three most common questions in a review (what produced this, how was it computed, why is this a problem). |

## 9. Constraints that shape the plan

- **Golden files and generated artefacts.** `tests/golden/` (88 files), `src/budget_core/schemas/` and `examples/` are generated and compared; any change in them is deliberate, regenerated with `UPDATE_GOLDEN=1`, `budget export-schemas` and `budget export-examples --force`, and reviewed line by line.
- **Byte-identical reports.** Deterministic output is a product promise (spec constraint 14). New provenance fields must be deterministic and appear in every format together: `Provenance.rows()`, the CSV sidecar, the PDF and DOCX footers, the JSON, the hand-built scenario JSON and `textsafe._provenance`.
- **Schema versions and migrations** for every model-field change (CLAUDE.md).
- **Core purity.** `budget_core` has no GUI or network imports; exposing tolerances means passing a settings object into plain functions (`time_domain_budget`, the propagator), not reading globals.
- **Cache keys.** The scenario environment cache key must include any new user-editable detection step, gravity or Sun model, otherwise stale environments are reused. The plot-layer cache key (`plot_widget.py:389-401`) and the result key (`timeline_view.py:289`) must include anything newly displayed or selectable.
- **UI rules.** No hex colours, fonts or pixel sizes outside `budget_gui/theme/` (a test fails); nothing longer than about 50 ms on the window thread; keyboard first, every action in Ctrl+K; the window opens in the focused view (D-191) and `test_focused_view.py` guards it. `SOURCE_ROLE` and `TOTAL_ROLE` both equal `UserRole+23` (`delegates.py:49-50`) and must be separated before cell sources are shown.
- **Compare.** `compare_run.py` pairs rows by key columns and compares displayed text, so new columns appear as "added columns" and per-column decimals change what compare reports.
- **Python 3.14 only.** All probes and tests need 3.14 (PEP 758 syntax in the sources).
- **Equation sources are owner-supplied** (D-061). P2 can show the equation, inputs, intermediates and the source *status*; it cannot invent citations. 37 of 40 equations need a reference from you or your team before the Explain view can cite them.
- **Docs to keep true** in each phase: `DEVIATIONS.md`, `DECISIONS.md`, `FILE_FORMAT.md`, `ENVIRONMENT_FORMAT.md`, the user-manual pages of the area, the in-app guide chapters, `CHANGELOG.md`, and the new `docs/models/`.

## 10. Limits of this audit

- The audit read code and documentation and ran small probes; it did **not** run the test suite, did not re-diff the committed JSON Schemas against the models, and did not read the icon and font loaders (the run-time asset reads GV-E12 are marked unverified there).
- Each area audit verified its own line numbers with `grep` or by reading; a few are approximate and are marked in the appendices. One range (`link_view.py:380-420`) was not verified.
- Two of the eight agents could not execute the command line on the machine's default Python 3.13 (the sources use 3.14 syntax) and used a 3.14 environment or read the code instead. The builders-and-compare audit could not run code at all.
- Findings are produced by reading and by language-model analysis. I re-checked the items marked **verified** in section 5, the equation counts (40 equations, 37 without source, by running the registry) and a sample of line references; the rest should be treated as strong leads that each phase confirms with a test before acting on them.
- Out of scope by design: pixel sizes and colours of the window, the packaging scripts and CI workflows, the tests themselves, and the licence tooling.
- UX and workflow judgements (for example "hidden by default") describe the current behaviour, not a recommendation to change it; D5 and the phase notes are the recommendations.

---

# Appendices: full findings of the area audits

Each appendix is the report of one area audit, unchanged except that headings are demoted one level. Row IDs are stable and are the references used above. "Source stated?" and "documented where?" refer to the user-facing documentation and the code comments.

## Appendix A — Power, scenario and environment

All paths are under `/home/user/systembudgetstudio/` and all line numbers were read in this session. "SRC" = `src/budget_core/`. "Doc" = `docs/`. Anything not run is marked "unverified (not executed)".

### Summary

Counts: A 62 rows, B 40 rows, C 16 rows, D 14 rows, E 14 rows.

The five most important gaps:
1. **No physical model parameter outside the Sourced electrical inputs can be changed.** Earth radius/mu/flattening, Sun radius, AU, the Sun ephemeris coefficients, the GMST polynomial, the solar-array irradiance law, the 20 s detection grid, the 1e-3 s edge tolerance, the 30-day TLE limit and all verdict tolerances are Python literals. Only the constants are listed (guide chapter "Constants shipped with the tool", `SRC/guide/build.py:100-133`). The rest is visible only through DEVIATIONS prose.
2. **Gravity/Earth model is inconsistent between orbit sources and not documented.** A TLE is built with `Satrec.twoline2rv(l1,l2)` (`SRC/environment/elements.py:47`). That defaults to WGS72 (radiusearthkm 6378.135, mu 398600.8; checked by running sgp4 2.27). Elements use WGS84 (`elements.py:54`), and all geometry (shadow, topocentric, nadir frame) uses the WGS84 radius from `SRC/environment/constants.py:23`. DV-E2 mentions only the elements path. The user cannot select the gravity model.
3. **Verdicts depend on silent policy choices.** The default load basis is `nominal` (unmargined) in the CLI (`src/budget_cli/main.py:190-192`), so DoD, depletion and peak verdicts are produced without margins unless the user flips a switch. The mission phase falls back silently to the only phase in the project (`SRC/power/time_domain.py:425-427`). BOL/EOL are the only two ages (`time_domain.py:37`). `BATTERY_DEPLETED`, `ORBIT_BALANCE_NEGATIVE` and `PEAK_POWER_EXCEEDED` have fixed rules and tolerances (`time_domain.py:47-52`).
4. **Outputs hide their derivation.** The report shows assumptions (the Sourced inputs) and equation text, but not the intermediate values:
   - the array factors (k_T, k_age, per-face cosines, E);
   - the sun-body vector;
   - the orbit-window boundaries;
   - the refined-edge count and tolerances;
   - the plotted series is a grid-step *mean* while the summary min/max come from the *refined* edges (`time_domain.py:1036` vs `1044-1059`);
   - none of the numerical constants of the environment (detection step, tolerances, orbit definition, TLE lines) is in the scenario exports.
   Every `TDP-*`, `ENV-SUN` and `ENV-SHADOW-*` equation has `source=None` and is flagged SOURCE_MISSING (`SRC/equations.py:30-118, 316-345`).
5. **Possible silent inconsistency in the refinement loop.** If all `MAX_REFINE_ROUNDS = 4` rounds still add edges, `prepared` is rebuilt on the finer edges but `traces` still belong to the previous edges (`time_domain.py:482-496`). No warning is raised for non-convergence. Unverified (not executed).

Other notable items:
- Imported (SpaceMissionStudio) data silently ignores `shadow_model`, takes the Sun from the tool's own low-precision model, and assumes the file's frame is TEME.
- The cache key for imports uses file size and mtime, not a content hash (`SRC/scenario/run.py:202`).
- Hard limits in code (`MAX_SAMPLES`, year range, semi-major-axis range, cell counts) are not in the project files.

### A. Constants, defaults, thresholds, rules

Columns: ID | file:line | value | purpose | visible to user? | editable w/o code? | source stated?

#### A1. Physical constants and models
| ID | file:line | value | purpose | visible? | editable? | source |
|---|---|---|---|---|---|---|
| PWR-001 | SRC/environment/constants.py:23-28 | Earth radius = `wgs84.radiusearthkm*1000` = 6 378 137 m (from sgp4 lib) | shadow, topocentric, nadir, geodetic, wizard altitude to a | Yes: guide chapter (guide/build.py:100-133); not in run reports | No | Yes: "WGS 84 (NIMA TR8350.2), value as used by sgp4" |
| PWR-002 | constants.py:29-34 | Earth mu = `wgs84.mu*1e9` | Kepler mean motion from a (elements.py:51) | same | No | Yes (same) |
| PWR-003 | constants.py:35-37 | flattening 1/298.257223563 | WGS-84 geodetic site position (geometry.py:78-87); NOT used by shadow (spherical Earth, geometry.py:116, 131, 147) | same | No | Yes |
| PWR-004 | constants.py:38-40 | Sun radius 695 700 000 m | conical shadow apparent radius (geometry.py:115) | same | No | Yes (IAU 2015 B3) |
| PWR-005 | constants.py:41 | AU 149 597 870 700 m | Sun distance (geometry.py:55-56) | same | No | Yes (IAU 2012 B2) |
| PWR-006 | SRC/environment/geometry.py:39-47 | Sun ephemeris coefficients 280.460, 0.9856474, 357.528, 0.9856003, 1.915, 0.020, 23.439, 4e-7 | low-precision Sun (about 0.01 deg) | Equation ENV-SUN in reports; coefficients only in code | No | Registry says "reproduced from memory ... Owner to verify", `source=None` (equations.py:316-326) |
| PWR-007 | geometry.py:55 | 1.00014, 0.01671, 0.00014 | Sun distance in AU | no | No | same, ENV-SUN |
| PWR-008 | geometry.py:61-64 | 67310.54841, 876600*3600+8640184.812866, 0.093104, 6.2e-6 | IAU-82 GMST | Equation shown | No | Yes (sgp4 gstime, Vallado) |
| PWR-009 | geometry.py:39,61 | 2451545.0 (J2000) | epoch for both models | no | No | none stated |
| PWR-010 | geometry.py:126-134, 143-165 | model ids "cylindrical"/"conical" | shadow geometry; conical = Montenbruck and Gill 3.4.2 (equations.py:340-345, "reproduced from memory") | Yes (scenario field, reports) | Yes: `shadow_model` in scenario | Equation `source=None` |
| PWR-011 | SRC/environment/elements.py:54-66 | `sgp4init(WGS84, "i", 1, epoch-2433281.5, bstar=0, ndot=0, nddot=0, ...)` | elements to SGP4. Satellite number 1; improved mode "i"; drag B*=0, ndot=nddot=0 | DV-E2 mentions B*=0; not "i", not WGS84 choice | No | DV-E2 |
| PWR-012 | elements.py:47 | `Satrec.twoline2rv(l1,l2)` -> sgp4 default WGS72 (6378.135 km, mu 398600.8) | TLE propagation | NOT mentioned anywhere (Doc DV-E1/E2, ENVIRONMENT_FORMAT) | No | none |
| PWR-013 | elements.py:120, 135 | x1000 (km to m) | unit conversion | n/a | n/a | n/a |
| PWR-014 | elements.py:51 | x60 rad/min | SGP4 unit | n/a | n/a | n/a |

#### A2. Environment thresholds, tolerances, grids
| ID | file:line | value | purpose | visible? | editable? | source |
|---|---|---|---|---|---|---|
| PWR-015 | SRC/model/environment.py:17 (used elements.py:29,243; model/environment.py:218) | `DETECTION_STEP_S = 20.0` | fixed grid for passes/eclipses regardless of `step_s`; also in the sample-count limit | Yes in docs (scenarios.md, ENVIRONMENT_FORMAT conventions, DV-E4); not in exports | No | Rationale in comment/D-057, D-146 |
| PWR-016 | elements.py:39 | `LIT = 1 - 1e-12` | sunlight ratio below this = eclipse (penumbra counts as eclipse) | No | No | none |
| PWR-017 | elements.py:40 | `UMBRA = 1e-12` | ratio at or below this = umbra | No | No | none |
| PWR-018 | elements.py:41 | `EDGE_TOLERANCE_S = 1e-3` | bisection tolerance of pass/eclipse edges ("about 1 ms" in docs) | Yes (docs only) | No | none |
| PWR-019 | SRC/environment/intervals.py:62 | `bisect_edge tol=1e-3` default | same (default is overridden by PWR-018) | no | No | none |
| PWR-020 | elements.py:367 | `1e-2` s golden-section stop | time/value of max elevation and max shadow margin | No | No | none |
| PWR-021 | elements.py:364 | golden ratio (sqrt5-1)/2 | search | n/a | n/a | n/a |
| PWR-022 | elements.py:71 (and 83, 88) | `MAX_TLE_AGE_DAYS = 30.0` | warning ORBIT_EPOCH_FAR | Yes (message and docs) | No | none stated |
| PWR-023 | elements.py:288-292, 343-347 | rate-bound heuristic (margin + max-slope*(2 intervals) >= 0) | decides whether a sub-grid pass/shadow is searched | No | No | DV-E4 describes the idea only |
| PWR-024 | elements.py:320 | `max(el_max, min_elevation)` | pass max elevation clipped up to the minimum elevation | No | No | none |
| PWR-025 | SRC/environment/data.py:31, 36 | `+1e-9` in floor; `np.minimum(times, duration)` | sample count and last sample clipped to the end | comment only | No | comment (0.7/0.1) |
| PWR-026 | SRC/power/signals.py:20, 22, 25 | `1e-9` | step edges, closing step | no | No | comment |
| PWR-027 | SRC/model/environment.py:15 | `MAX_SAMPLES = 1_000_000` | scenario size limit counted at min(step, 20 s) | Yes (docs) | No | comment ("about 11 days at 1 s") |
| PWR-028 | model/environment.py:16 | `MAX_RULES = 10_000` | rules and segments per scenario | no | No | none |
| PWR-029 | model/environment.py:18; SRC/timeutil.py:12-13 | years 1950-2100 (duplicated in two files) | accepted dates | Yes | No | D-120: Sun/Earth models and TLE convention meant for that range |
| PWR-030 | model/environment.py:19 | `SEMI_MAJOR_AXIS_RANGE_M = (6.4e6, 1.0e8)` | element sanity range | Yes (docs) | No | comment |
| PWR-031 | model/environment.py:53 (call), 63-77 | eccentricity [0,1), i [0,180], angles [0,360) | element validation | schema | No | none |
| PWR-032 | model/environment.py:124-126 | lat +/-90, lon +/-180, alt -1000..100000 m, min_el [0,90) | site validation | schema | No | none |
| PWR-033 | model/environment.py:58 | TLE two-digit-year pivot 57 | epoch decoding (2000+yy for yy<57) | no | No | standard convention, not cited |
| PWR-034 | model/environment.py:39, 95 | TLE 69 characters, checksum mod 10 | validation | message | No | TLE format |
| PWR-035 | model/environment.py:224, 228 | `1e-9` | segment overlap/outside tolerance | no | No | none |
| PWR-036 | model/environment.py:183 | default `shadow_model = "cylindrical"` | default shadow | Yes in file when written; default is hidden if omitted | Yes | none |
| PWR-037 | SRC/environment/spacemissionstudio.py:42-44 | 250 MB, 2 000 000 rows, 100 000 rows | importer limits | Yes (ENVIRONMENT_FORMAT) | No | none |
| PWR-038 | spacemissionstudio.py:180 | `1e-6` s coverage tolerance | import must cover [0,duration] | no | No | none |
| PWR-039 | spacemissionstudio.py:211, 250 | peak 0..90 deg; elevation -90..90 deg | import validation | docs | No | none |
| PWR-040 | spacemissionstudio.py:151, 161, 263 | umbra = eclipse = ratio 0 (inclusive interval ends); 1e-9 s pass window | imported shadow is sharp | note in code comment; docs "no penumbra information" | No | none |

#### A3. Power / battery / time-domain
| ID | file:line | value | purpose | visible? | editable? | source |
|---|---|---|---|---|---|---|
| PWR-041 | SRC/power/time_domain.py:37 | `CASES = ("bol","eol")` | only two cases | Yes (report fact line, timeline_report.py:50-53) | No | D-061..066 |
| PWR-042 | time_domain.py:47 | `RATIO_TOL = 1e-9` | DoD exceed test (`> limit + tol`, line 328); also SoC/DoD ratios | No | No | comment ("rounding noise") |
| PWR-043 | time_domain.py:48 | `POWER_TOL_W = 1e-9` | peak exceedance (851) and depletion threshold `1e-9 * max(1, max demand, max gen)` (1004-1005) | No | No | comment |
| PWR-044 | time_domain.py:49 | `ENERGY_TOL_WH = 1e-6` | negative orbit balance threshold (1022) | No | No | none |
| PWR-045 | time_domain.py:50 | `REFINE_TOL_S = 1e-6` | refined-edge merge | No | No | none |
| PWR-046 | time_domain.py:51 | `PENUMBRA_MIN_S = 0.01` | a ramp shorter than 10 ms is a sharp edge; knot matching tolerance (276) | No | No | none |
| PWR-047 | time_domain.py:52 | `MAX_REFINE_ROUNDS = 4` | battery saturation refinement rounds (no non-convergence warning) | No | No | comment |
| PWR-048 | time_domain.py:853 | `1e-9` | merge of adjacent peak violations | No | No | none |
| PWR-049 | time_domain.py:836-838 | `age_factor_ratio=1.0` in base generation; applied per case at 939 | design: BOL factor 1 | No | No | none |
| PWR-050 | time_domain.py:917 | EOL years = `design_life_yr` | only EOL age possible | Yes (report line) | via `design_life_yr` | none |
| PWR-051 | time_domain.py:425-427 | phase = argument or scenario or the single project phase | DoD limit selection (silent fallback) | Shown as "mission phase: X" in report | via scenario | none |
| PWR-052 | time_domain.py:1165 | `+1e-9` in `format_offset` | display | n/a | n/a | n/a |
| PWR-053 | SRC/power/orbits.py:22 | `MAX_STEP_RAD = pi/2` | step limit for orbit windows | Yes (message, docs "quarter period") | No | comment |
| PWR-054 | orbits.py:47 | `sin(10 deg)` | "moved enough" to define the orbit plane | No | No | none |
| PWR-055 | orbits.py:53, 55, 59, 63 | `1e-9` | angle tolerances | No | No | none |
| PWR-056 | SRC/scenario/timeline.py:234 | `EPS = 1e-9` s | snapping/merging of mode boundaries | No | No | comment ("no sliver gap") |
| PWR-057 | SRC/model/power_system.py:527-532 | `MAX_STRINGS=10000`, `MAX_CELLS_PER_STRING=10000`, `MAX_CELLS_IN_SERIES=1000`, `MAX_CELLS_IN_PARALLEL=10000`, `MAX_DIRECTION_COMPONENT=1e6`, `MIN_DIRECTION_LENGTH=1e-6` | input sanity | error text | No | comment ("far above any real spacecraft") |
| PWR-058 | SRC/power/static_budget.py:414 | efficiency in (0,1], loss in [0,1) | ValueError bounds | error | No | none |
| PWR-059 | SRC/power/battery.py:61, 63 | eff in (0,1]; initial energy <= capacity*(1+1e-12) | validation | error | No | none |
| PWR-060 | SRC/power/array.py:22 | `max(0, 1 + alpha*(T-Tref))` | temperature factor floored at 0 | Equation TDP-TEMP | No | `source=None` |
| PWR-061 | array.py:48 | `max(cos, 0)` | no back-side generation, no incidence-angle cell law | Equation TDP-COS | No | `source=None` |
| PWR-062 | SRC/scenario/export.py:352, 384, 439, 442, 461-465, 477 | 3 decimals (s), 4 decimals (deg), 6 decimals (fraction) | output rounding | Not stated in files | No | comment in export.py docstring ("fixed decimals") |

### B. Hidden assumptions

| ID | file:line | assumption / behaviour | documented where? |
|---|---|---|---|
| PWR-B01 | elements.py:47 | TLE is propagated with sgp4's default WGS72 constants, while shadow/topocentric/nadir frames use WGS84 radius (constants.py:23). Elements path uses WGS84 (line 54) | not documented (DV-E2 covers elements only) |
| PWR-B02 | elements.py:48-67 | Elements treated as SGP4 *Kozai mean* elements; no drag; epoch used as SGP4 epoch | Doc DV-E2 |
| PWR-B03 | geometry.py:36-56, 69 | Sun from low-precision formula in "mean equator and equinox of date, close to TEME"; the same unit vector is used with TEME positions without nutation/precession correction | partly: DV-E1 (0.01 deg); frame statement only in code docstring |
| PWR-B04 | geometry.py:68-73, 28-33 | UTC treated as UT1 (no leap seconds, no EOP), GMST rotation only, no polar motion, no nutation | Doc DV-E1 |
| PWR-B05 | geometry.py:116, 131, 147 | Earth is a sphere of equatorial radius for the shadow; no oblateness, no atmosphere; Sun is a uniform disk at the Sun-Earth distance (satellite offset used in conical, `to_sun = sun - r`) | Doc DV-P1 (oblateness and refraction); the 6378 km "equatorial" choice is not stated |
| PWR-B06 | geometry.py:94-106 | Elevation = geometric, geodetic up, no refraction, no horizon mask, no terrain | Doc DV-E1 (refraction); ENV-TOPO; mask not mentioned |
| PWR-B07 | elements.py:168-169 | Eclipse = any shadow (penumbra included); umbra = ratio <= 1e-12. The `in_eclipse` and `in_sunlight` rules use `env.eclipses` (penumbra counts as eclipse for mode switching) (timeline.py:308-316) | not stated in scenarios.md (unverified in GUI text) |
| PWR-B08 | elements.py:242-244, 281-300 | Detection on fixed 20 s grid; gap of sunlight shorter than 20 s between two shadows is not searched; unimodality assumed in golden-section | Doc DV-E4 (gap), unimodal assumption not stated |
| PWR-B09 | elements.py:288-292, 343-347 | Short pass/shadow candidate selection uses a linear rate bound: could miss an extremum if the function curves faster | Doc DV-E4 gives the idea, not the miss risk |
| PWR-B10 | spacemissionstudio.py:140-163 | Imported data: `shadow_model` ignored; umbras = eclipses; Sun from the tool's own formula; imported frame assumed to be the same inertial frame as the Sun formula and GMST rotation | Doc: "inertial frame used as given", "no penumbra information"; ignoring `shadow_model` not stated; report still prints shadow_model (timeline_report.py:48) |
| PWR-B11 | spacemissionstudio.py:120-129, 258-259 | Cubic Hermite for positions (uses file velocities); linear interpolation for elevation/range; azimuth interpolated on unwrapped radians; values outside passes set NaN | Doc: "cubic Hermite interpolation" only |
| PWR-B12 | spacemissionstudio.py:221, 267-273 | Time of max elevation of imported passes = best profile sample, else NaN; imported max elevation not cross-checked against profile | Doc (ENVIRONMENT_FORMAT) |
| PWR-B13 | power/attitude.py:17-29 | Nadir frame: x along track from `np.gradient` of grid positions (one-sided at the ends), z = -r/\|r\|, y = -h. Velocity precision depends on `step_s`. Exact velocity from SGP4 is not used | Doc: DV-P5 "body frame equals local orbital frame" (finite differences not mentioned) |
| PWR-B14 | time_domain.py:817-824, 794 | Sun direction in body frame is sampled at the *start* of each grid step; mode pointing taken per solve step; `sun` pointing = constant vector with no error | Doc DV-P5/DV-P6 |
| PWR-B15 | time_domain.py:828-839, array.py:68-78 | Array generation: constant irradiance E (no 1/R^2), single cell temperature, identical cell efficiency on all faces, cosine-only incidence law, no shadowing between faces, no albedo or Earth IR, no MPPT or topology | Doc DV-P2, DV-P5 |
| PWR-B16 | time_domain.py:245-302; Doc DV-P6 | Soft shadow: piecewise-linear ramp 1->0 (eclipse start to umbra start) and back; error about 0.1 s for an 8 s penumbra; penumbra-only eclipse ramps to the deepest sample, or 0.5 if none | Doc DV-P6 (quantified) |
| PWR-B17 | time_domain.py:379-393 | Battery solved on grid refined at eclipse edges, mode edges, orbit-window edges and saturation instants; reported series are step *means* (`_GridMap.mean`, 893-896), energies read at grid edges; summary extrema (min margin, min SoC, max DoD) and violations come from the refined solution | Doc: power-budget.md:64 says "do not depend on the time step"; the mean/extreme split is not documented |
| PWR-B18 | time_domain.py:482-496 | Up to 4 refinement rounds; no flag if the 4th round still changed the edges; traces then belong to the previous edge set (unverified, not executed) | not documented |
| PWR-B19 | battery.py:77-104 | Energy store: constant efficiencies; surplus charges until full, then is *curtailed*; deficit discharges until empty (E=0, DoD=100 % is physically reachable), unmet demand reported; no current/power limit, no voltage, no temperature, no self-discharge; DoD limit is a check only, not a control | Doc DV-P4 (limits); "DoD limit does not stop discharge" not stated |
| PWR-B20 | battery.py:33, time_domain.py:956 | Capacity = Ah x nominal V x series x parallel x (1-fade)^years; no usable-capacity or reserve factor; initial SoC applies to the *faded* capacity at EOL; battery state is not carried between cases | Equation TDP-CAP |
| PWR-B21 | array.py:25-29, battery.py:31-34 | Degradation compounding yearly: (1-r)^years for both array and battery; no beginning-of-life loss, no radiation model | Equations TDP-AGE, TDP-CAP |
| PWR-B22 | time_domain.py:395-411, 217-225 | Demand per mode is the *average* source power (avg x duty) of the mode; duty-cycle transients inside a mode are not seen by the battery; peak power is evaluated per mode segment only and not integrated | Doc partially (static budget); battery implication not stated |
| PWR-B23 | static_budget.py:403-405, 508-512 | Margins compound: unit margin on each unit, then system margin on the sum (multiplicative); peak is margined the same way; nominal basis uses neither | Equations PWR-MARGIN, PWR-SYSMARGIN; Doc |
| PWR-B24 | static_budget.py:564-571, 536-547 | Missing/placeholder margin, efficiency, loss: the dependent result is None (n/a), never zero; missing class margin -> unit margin None -> mode margined totals None | Doc (module docstring; power-budget.md read-the-result) |
| PWR-B25 | time_domain.py:402-406 | If any segment's mode has None flow, the whole demand series is None and all battery results are n/a (all-or-nothing) | not stated in manual |
| PWR-B26 | static_budget.py:555, 550-553 | Deterministic ordering: modes and units sorted by id; sums with `math.fsum` | not stated |
| PWR-B27 | orbits.py:44-70 | "Orbit" for the balance = one in-plane revolution from the starting angle of sample 0 (not perigee, node, or eclipse boundary); angle unwrapped from positions, partial last revolution ignored; plane found from first sample moved by >10 deg | Doc: "complete orbit" only; phase of window start not stated |
| PWR-B28 | time_domain.py:1093-1135 | Orbit balance = integral of (generation - demand) over each window by linear interpolation of cumulative sums at the window bounds; battery change likewise interpolated | Equation TDP-BALANCE |
| PWR-B29 | time_domain.py:323-340 | DoD exceedance start/end are *linearly interpolated* between refined edges; worst = max at edges | not stated |
| PWR-B30 | time_domain.py:842-880 | Peak check: per timeline segment, sum of unit peaks (all at once) at the source vs one limit; "nominal" basis compares unmargined peak; adjacent exceeding segments merged | Equation TDP-PEAK/PWR-PEAK |
| PWR-B31 | scenario/timeline.py:248-270, 295-319 | Layering: default -> rules in order -> manual segments; `during_pass` paints [aos-lead, los+lag]; clipped to [0,duration]; boundaries within 1e-9 s are snapped; same-mode neighbours merged | Doc: scenarios.md, ENVIRONMENT_FORMAT (D-056); snapping not stated |
| PWR-B32 | timeline.py:322-329; time_domain.py:410 | `step_mode` in outputs = mode at the *start* of each grid step; a step that contains a mode change shows only the first mode | not stated |
| PWR-B33 | data.py:89-100 | `eclipse_fraction` merges overlapping intervals and clips to [0, duration] | comment only |
| PWR-B34 | timeutil.py:15-23, 56-70 | Only extended ISO accepted; UTC only (offsets refused); fractional seconds truncated at 6 digits; year 1950-2100 | Doc: UTC only; years; truncation not stated |
| PWR-B35 | timeutil.py:73-82 | `format_utc` drops trailing zero microseconds | not stated |
| PWR-B36 | scenario/run.py:145-156 | OverflowError/ValueError during computation is reported as a date out-of-range problem, whatever the real cause | message |
| PWR-B37 | slices.py:16 | `SLICE = 2048`: slicing of NumPy/SGP4 calls; results bit-identical | Doc comment (D-182/183) |
| PWR-B38 | environment/elements.py:105-135 | Positions obtained in SGP4 batches of 2048 samples; an SGP4 error at any sample aborts the run (no partial result) | message only |
| PWR-B39 | environment/elements.py:96-103 | `check_orbit` only tests propagation at the epoch | not stated |
| PWR-B40 | control.py:1-46 | Cancel/progress is an observer only; results identical | Doc comment |

### C. Outputs without a visible derivation

| ID | where the user sees it | what is missing |
|---|---|---|
| PWR-C01 | Eclipse list/fraction, passes (CSV/JSON, scenario.py exports) | Orbit definition used (TLE lines or elements), gravity model, Sun model, shadow radius, detection step 20 s, edge tolerance 1 ms, tool code version. Export has only `grid`, `source`, `shadow_model`, `notes`, provenance (export.py:427-493) |
| PWR-C02 | Time-domain plot "generation" | k_T, k_age, E, cell counts, per-face cosines, sun-body vector, lit ratio per step are not reported. `lit_ratio` and the pointing are in the series CSV only as lit ratio (timeline_export.py:58-86). Intermediate array terms are missing |
| PWR-C03 | Summary: min SoC, max DoD, min margin | Computed from the refined solution (time_domain.py:1036, 1084-1086), while the plot and series show grid-step means (1044-1059, 893-896). The user cannot reconcile the plotted minimum with the reported one. Refined edges are not exported |
| PWR-C04 | Violations table (DoD, depletion, balance, peak) | The tolerance applied (1e-9 ratio, 1e-9 W x scale, 1e-6 Wh), the linear interpolation of start/end, and the merge rule are not displayed (time_domain.py:328-340, 1004-1005, 1022, 851-865) |
| PWR-C05 | "Not evaluated" lines | Reasons are text; when all-or-nothing None logic hides a single missing mode flow (time_domain.py:402-406), the missing item is not named in the line |
| PWR-C06 | Orbit balance table | Window boundaries (derived from positions), the choice of start (first sample angle) and the 10 deg plane test are not shown; eclipse seconds per window are shown, solar constant etc. not (time_domain.py:1093-1135) |
| PWR-C07 | "Demand" series | Which basis (nominal/margined) is stated in the report line; the per-mode `load_w / demand_w / peak_demand_w` appear in `modes` JSON, but the chain (unit margin -> system margin -> converter -> distribution) per mode is in the static table only, not tied to the time-domain run |
| PWR-C08 | Equations chapter | All `TDP-*`, `ENV-SUN`, `ENV-SHADOW-*`, `PWR-*` show SOURCE_MISSING (equations.py:30-118, 255-300, 316-345). Some say "reproduced from memory" in notes |
| PWR-C09 | Assumptions list (report) | Contains only Sourced inputs (design life, array, battery, DoD, peak limit, margins, loss, efficiency). Excludes: `attitude` content, irradiance law, constants of PWR-001..008, tolerances, and the TLE/element values |
| PWR-C10 | Pass table (max elevation) | Peak is clipped to the minimum elevation (elements.py:320); `time_of_max` resolution 10 ms (elements.py:367); imported peak is the user's number |
| PWR-C11 | Sun/eclipse of imported data | The ratio shown (0/1) and the Sun direction come from tool formulas, not the import; the report prints `shadow_model` that was not applied (timeline_report.py:48; spacemissionstudio.py:140-163) |
| PWR-C12 | Orbit age warning (ORBIT_EPOCH_FAR) | Shows only the 30 day limit; rationale (no drag/B*) is in the hint only (elements.py:85-93) |
| PWR-C13 | `step_mode` column | Shows the first mode only for steps spanning a mode change (time_domain.py:410) |
| PWR-C14 | Scenario JSON rounding | 3 decimals of seconds, 4 decimals of degrees; the rounding is not in the file (export.py:442, 461-465) |
| PWR-C15 | "Battery depleted" magnitude | `unmet_w` is an average over the step and refined step; the actual instant of depletion inside a step (saturation fraction) is used but not reported (battery.py:86-98) |
| PWR-C16 | Peak violation | Compared with `limits.peak_power_w` on the basis chosen; which units contribute and the margin used are not listed in the violation row |

### D. Forced options

| ID | file:line | fixed choice | plausible alternatives |
|---|---|---|---|
| PWR-D01 | elements.py:44-68 | SGP4 only (no numerical propagator, no J2-secular/Kepler option); elements -> SGP4 mean elements with B*=0 | Kepler/J2 secular propagator, high-fidelity numerical with drag/SRP, user B* or drag model, osculating-to-mean conversion |
| PWR-D02 | elements.py:47 vs 54 | WGS72 for TLE, WGS84 for elements | user-selected gravity model (WGS72/WGS84/EGM96), consistent with geometry |
| PWR-D03 | geometry.py:36-56 | Almanac low-precision Sun | JPL DE/VSOP87/SOFA ephemeris, user-given Sun vectors, fixed beta angle |
| PWR-D04 | geometry.py:59-73 | GMST only, UTC=UT1 | EOP/UT1-UTC, full IAU-2006 CIO |
| PWR-D05 | geometry.py:116, 131, 147 | Spherical Earth shadow with equatorial radius | oblate shadow, atmospheric shadow, mean radius, user radius |
| PWR-D06 | model/environment.py:183; elements.py:168 | Two shadow models only; eclipse = any ratio <1 | penumbra threshold (e.g. >10 % illumination), dual-cone, sunlight fraction cutoff for "eclipse" |
| PWR-D07 | elements.py:242-244 | Detection grid 20 s fixed | user detection step / tolerance |
| PWR-D08 | geometry.py:94-106 | Geometric elevation; single min-elevation threshold | refraction, horizon mask by azimuth, antenna keep-outs, terrain |
| PWR-D09 | model/power_system.py:523; attitude.py | Pointing modes: `sun` (fixed vector) and `nadir` only | sun-tracking SADA with gimbal limits/pointing error, yaw steering, inertial, LVLH offsets, user quaternion table |
| PWR-D10 | array.py:51-78 | One cell temperature, constant irradiance, cosine law, no albedo | temperature vs sun/eclipse, 1/R^2 irradiance, incidence-angle factor tables, albedo, I-V/MPPT, per-string shadowing |
| PWR-D11 | battery.py:47-113 | Energy-store model with fixed efficiencies | charge/discharge power limits, voltage/current model, temperature dependency, SoC reserve, EOL profile, charge taper |
| PWR-D12 | time_domain.py:37 | BOL and EOL only; EOL = design life | any mission year, mid-life, user list of ages |
| PWR-D13 | time_domain.py:36 | Two load bases: nominal, margined | per-unit choice, only system margin, only maturity margin, worst-case/peak-based demand, duty-cycle resolved timelines |
| PWR-D14 | orbits.py; time_domain.py:1093 | Balance per in-plane revolution from the start angle | balance per eclipse-sunlight cycle, per day, per orbit starting at perigee/node, rolling window |

### E. Interfaces

| ID | file:line | direction | what / format | user told? | provenance? |
|---|---|---|---|---|---|
| PWR-E01 | SRC/scenario/run.py (project loader) | in | `orbits/<id>.yaml`, `scenarios/<id>.yaml`, `ground_stations/`, `targets/`, `config/power_system.yaml`, margin policy, power config | Yes (docs) | Sourced values carry `source`; orbit TLE/elements carry none |
| PWR-E02 | spacemissionstudio.py:56-100, 165-276 | in | `<import_dir>/orbit.csv`, `eclipse.csv`, `passes_<site>.csv`, optional `profile_<site>.csv` (UTF-8 with optional BOM, comma, point decimal) | Yes (ENVIRONMENT_FORMAT, interim) | No hash/version of imported files in outputs; only note strings for missing profile (spacemissionstudio.py:237-240) |
| PWR-E03 | scenario/run.py:181-204 | internal/in | Cache fingerprint: JSON of source, times, step, shadow model, sites, orbit; for imports file name + size + mtime_ns (`stat`) | No | Not a content hash: an edit with the same size and mtime is missed |
| PWR-E04 | scenario/export.py:496-505 | out | `<id>_environment.json`, `_eclipses.csv`, `_passes.csv`, `_timeline.csv`, `_provenance.csv` (LF, fixed decimals) | Yes (docs, CLI) | Yes: tool, version, python, libraries (numpy, sgp4 ...), project name/revision, user (export.py:481-491; provenance.py:26-34, 127) |
| PWR-E05 | SRC/reports/timeline_export.py:58-86, 188-231 | out | power-timeline series CSV per case (`series_every` thinning), summary/violations/balances CSVs, JSON with `assumptions`, `not_evaluated`, `problems`, provenance | Yes (CLI `--series-every`) | Yes provenance; no tolerances, no refined-edge list, no orbit definition |
| PWR-E06 | SRC/reports/timeline_report.py:40-53, 245-275 | out | Report (PDF/DOCX/XLSX) with facts, assumptions, equations (`TDP-`, `PWR-`, `ENV-`), provenance, banner when incomplete | Yes | Yes |
| PWR-E07 | spacemissionstudio.py:287-332 | out | `export_spacemissionstudio` writes orbit/eclipse/passes/profile CSV (finite-difference velocities); no CLI call found in `src/` (unverified outside tests) | Docs mention (tests) | none |
| PWR-E08 | elements.py:15 (`sgp4`), geometry.py:15 | in (library) | `sgp4` lib supplies WGS constants, `jday`, `Satrec`, `gstime`-equivalent value; version recorded by provenance | Provenance lists version | Yes |
| PWR-E09 | constants.py:11, 23-34 | in (library) | Earth radius and mu read at import time from `sgp4.earth_gravity.wgs84`; a library change would silently change tool constants | Guide chapter prints values | No test pin visible here (unverified) |
| PWR-E10 | SRC/timeutil.py | in/out | UTC strings in all files, no offsets | Yes (error message) | n/a |
| PWR-E11 | SRC/control.py | in/out | `RunControl` callbacks, no files | n/a | n/a |
| PWR-E12 | SRC/slices.py | internal | no external interface | n/a | n/a |
| PWR-E13 | SRC/guide/build.py:100-133 | out | "Constants shipped with the tool" table in the user guide | Yes | Value + source |
| PWR-E14 | scenario/run.py:128-132 | out | Problem message refers to `docs/ENVIRONMENT_FORMAT.md` and `<import_dir>/<file>` and line number (no content echoed) | Yes | n/a |

### Already good

- `Sourced` model: every electrical input needs `source`; `TBD` or null is a placeholder and results become n/a, never 0 (`SRC/model/base.py:131-141`; `static_budget.py`; `time_domain.py:202-214`). RESULT_INCOMPLETE problems carry file and path jump links.
- `Assumption` records (value, unit, source, file, path, placeholder) are exported in report and JSON (`SRC/assumptions.py`; `timeline_export.py:221`).
- `NotEvaluated` list: a check that could not run is not reported as passed (`time_domain.py:82-89, 562-600`).
- Constants have names, units and sources in `SRC/environment/constants.py` and appear in the generated guide (`guide/build.py:100-133`).
- Equation registry with IDs (`TDP-*`, `PWR-*`, `ENV-*`) and a SOURCE_MISSING flag instead of pretending to cite (`SRC/equations.py`).
- DEVIATIONS.md lists the main simplifications (DV-P1, P2, P4, P5, P6, E1, E2, E4) with quantified errors in DV-P6/E1.
- Reports state load basis, phase, shadow model, source, BOL/EOL meaning (`timeline_report.py:40-53`).
- Provenance (tool/version/libraries/user/project revision) attached to JSON and CSV (`export.py:481-491`).
- Results independent of step size by design (exact overlaps, refined edges); documented in power-budget.md:64.
- Importer error messages name file and line, never content (no privacy leak).
- `control.py` and `slices.py` are observer-only/bit-identical; the design documents it.

### Notes for the plan

- **Byte-identical constraints.** Scenario and power outputs are deterministic (LF, fixed decimals, sorted keys), and examples/schemas are regenerated with `budget export-examples --force` and `budget export-schemas`; tests fail on drift (CLAUDE.md). Moving a literal to a config or project field must keep today's default so the examples and golden files stay identical. Hash the defaults into the Provenance rather than changing values.
- **Schema versioning.** Any new field in `scenario`, `orbit` or `power_system` needs a version bump and a migration (FILE_FORMAT.md). `Scenario.schema_version` is already 2 in the example; `CURRENT_VERSIONS` is in `SRC/model/versions.py`.
- **Core purity.** `budget_core` has no GUI/network imports; tolerances such as PWR-042..047 are used inside the solver, so exposing them means a settings object passed into `time_domain_budget`/`ElementsPropagator` (both are plain functions/classes today with keyword defaults).
- **Cache key.** `environment_key` (run.py:181-204) lists exactly which scenario fields are part of the environment. Adding a user-editable detection step, gravity model or Sun model requires adding it to the key, or stale environments are reused.
- **Interlocking limits.** `DETECTION_STEP_S` also sets the sample-count limit (model/environment.py:218) and the doc text in three places (scenarios.md:139, 167; ENVIRONMENT_FORMAT.md:13, 34). Year limits exist twice (`timeutil.py`, `model/environment.py`).
- **Imported data.** Frame, Sun source and shadow-model handling are all implicit; the format is "interim" (D-055). A change here will meet the future real export format.
- **Refinement-loop risk (PWR-B18).** Before relying on refined edges as an audit trail, confirm by test what happens when `MAX_REFINE_ROUNDS` is exhausted (not executed here).
- **Physical-constant duplication.** `SRC/link/constants.py:14` repeats the WGS84 radius 6 378 137.0 as a literal (outside this area); `new_scenario.py:220, 231` and `wizard.py:206` use `EARTH_RADIUS` for altitude to semi-major axis (spherical, equatorial radius). Alternative Earth models need all of them to follow.
- **Docs to keep true.** Per CLAUDE.md, code changes here require updates in DEVIATIONS.md, ENVIRONMENT_FORMAT.md, scenarios.md and power-budget.md. DEVIATIONS.md has a stray order (DV-E4 is listed before DV-E3, DV-P4 after DV-E3).

## Appendix B — Mass, thermal, units and equations

Scope: `src/budget_core/{mass,thermal,units}/`, `equations.py`, `assumptions.py`, `model/{mass,thermal,equipment,config,base,project,versions}.py`, plus the places they are consumed (`reports/{mass,thermal}_report.py`, `reports/export.py`, `io/validation.py`, `blank.py`, `examples.py`) and the docs named in the brief. Read-only. All paths are relative to `/home/user/systembudgetstudio/`; `sb/` = `src/budget_core/`. Line numbers verified with `cat -n`/`grep -n`. The `budget` CLI could not be run (installed Python is 3.13, the code needs 3.14 syntax `except A, B:`); parser behaviour was checked by importing `units/quantity.py` directly, solver and report behaviour by reading.

### Summary

- Counts: A = 63 rows (constants, defaults, thresholds, rules), B = 30, C = 14, D = 12, E = 12.
- Gap 1 (equations): 37 of 40 registered equations are `SOURCE_MISSING`, including every MASS-*, TH-* (except TH-SB), PWR-*, TDP-*, LNK-*. The registry is linked to the code only by docstring convention (no test ties equation ids to code). Several computed things have no registry entry (system-margin application, mass-limit check, thermal solver algorithm, inertia-physical check, unit conversion). The GUI never shows an equation (`grep -i equation src/budget_gui` is empty); equations appear only in report files and the generated guide.
- Gap 2 (thermal numerics hidden): the solver tolerances, damping, refinement thresholds and the "residual" threshold (sb/thermal/steady_state.py:59-60, 88, 97-99, 166; static_thermal.py:138; thermal_report.py:111) are literals, not in any file the user can edit, not printed in the report, not in DEVIATIONS. The report prints only "Largest node imbalance ... below 0.000001 W".
- Gap 3 (thermal physics fixed): Kirchhoff (IR absorptivity = emissivity), the same Earth view ratio for albedo and Earth IR, radiation area = absorbing area, sink at `space_temperature_k` for all surfaces, average unmargined power only (peak dissipation is computed but never used for a case). Only a few of these are in DEVIATIONS (DV-T1/T2/T3); Kirchhoff and the albedo/IR sharing are only in the registry formula text.
- Gap 4 (margin policy fixed in shape): one flat multiplicative margin per maturity class, then one flat multiplicative system margin, same for units and expendables, same for every phase; mass limits are checked only against the system-margined total (sb/mass/static_mass.py:126-132, 177-183, 241-247). Margin values are editable (config file) but the policy structure is not.
- Gap 5 (units): the unit catalogue is a fixed 25-suffix dict (sb/units/quantity.py:30-57); conversions are delegated to pint's default registry (unpinned definitions: `ton` is the US short ton, 907.18 kg; `year` = 365.25 d); values are rounded to 15 significant digits (quantity.py:212) and the original text ("200 g") is lost on save; the temperature-difference rule is a substring test on the field name (`"margin" in field`, quantity.py:146).
- Data model gap: Sourced (value + source + note) is used only for config numbers. Unit mass, surface area, power modes, temperature limits, positions, inertia, expendable masses are plain floats with no source and no uncertainty (model/equipment.py:53-59, 95; model/thermal.py:52; model/mass.py:96). The manual (thermal-budget.md:91) and THERMAL_SOURCES.md say every number has a source; this is not true for these. Assumption rows (`assumptions.py:11-19`) carry no `note`.

### A. Constants, defaults, thresholds, rules

Legend: visible = shown in UI/report/docs to the user; editable = changeable without editing code.

#### A1. Mass (MAS)

| ID | file:line | value | purpose | visible? | editable? | source stated? |
|---|---|---|---|---|---|---|
| MAS-A01 | sb/mass/static_mass.py:26 | `LIMIT_TOLERANCE_RATIO = 1e-9`; used at 243 (limit check: `abs(margin) <= 1e-9 * max(1.0, abs(limit))` sets margin to 0) and 329 (expendable masses "differ" test) | a limit met within rounding noise is met; expendables with equal masses get no inertia warning | manual mass-budget.md:53 says "rounding noise is ignored" without the number; not in report | no (constant) | "as in D-097" |
| MAS-A02 | sb/mass/static_mass.py:31, 182 | formula `m*(1+margin)` and `sum(m_m)*(1+system)`: multiplicative chain, class margin first, system margin on the sum | mass margin policy | formula in registry MASS-MARGIN/MASS-SYSMARGIN (equations.py:296-309), margin_ratio per item in report Items table | structure no; values yes (`config/margin_policy.yaml`) | "project convention D-040" (SOURCE_MISSING) |
| MAS-A03 | sb/mass/static_mass.py:177 | total nominal = `fsum` of all rows present in the phase; expendables of every phase included | mass total | yes | no | no |
| MAS-A04 | sb/mass/static_mass.py:213, 223, 286 | items with `mass_kg <= 0.0` are skipped by the CG, by the "excluded" list and by the MASS_PROPS_MISSING warning | zero-mass items silently left out of CG/inertia | not stated in docs | no | no |
| MAS-A05 | sb/mass/static_mass.py:225-226 | inertia about the origin `(0.0, 0.0, 0.0)` and about the computed CG | frame origin for the "about origin" tensor | report column "About origin"; origin is the user's body_frame text | origin fixed to frame origin | D-048 |
| MAS-A06 | sb/mass/static_mass.py:356, 362 | unit label of an assumption chosen by `"margin" in path` -> "ratio", else "kg" | label of rows in "Configuration numbers used" | yes (label only) | no | no |
| MAS-A07 | sb/mass/static_mass.py:267, 292, 309, 332 | severities fixed: MASS_LIMIT_EXCEEDED ERROR (267), MASS_PROPS_MISSING WARNING (292), MASS_INERTIA_POINT_MASS INFO (309), MASS_INERTIA_NOT_SCALED WARNING (332) | verdict severity | codes in manual | no | no |
| MAS-A08 | sb/model/mass.py:28-29, 38, 45 | `1e-300` floor and `tol = 1e-9 * scale` (minors use `tol*scale`, determinant `tol*scale*scale`) | tolerance of the "inertia is physical" check (C = tr(I)/2 E - I positive semidefinite) | error text only ("cannot belong to a rigid body"); tolerance not stated | no | no (the criterion is stated in the docstring, no citation) |
| MAS-A09 | sb/model/mass.py:49-51 | `ixx/iyy/izz >= 0`; products unconstrained except by A08 | schema limit | schema | no | no |
| MAS-A10 | sb/model/mass.py:78 | `position_m` exactly 3 floats, no bounds | position format | docs | no | D-048 |
| MAS-A11 | sb/model/mass.py:96-104 | `masses_kg` per phase, `>= 0`, keys sorted on load | expendable masses; sorted order | docs | file | no (no `source` field) |
| MAS-A12 | sb/model/equipment.py:95 | `Unit.mass_kg >= 0` plain float | unit mass | docs | file | NO source/uncertainty field |
| MAS-A13 | sb/model/project.py:201 | default phase name `"all"` when `mission_phases` is empty | phase list | describe-the-spacecraft.md says "None are assumed" but D-049 and project.py use `all` | file (`mission_phases`) | D-049 |
| MAS-A14 | sb/model/mass.py:113-130 | uniqueness rule: two limits with equal name and overlapping phase are refused | mass limits | error | no | no |
| MAS-A15 | sb/io/validation.py:299-302 | margin ratio plausible range `[0, 10]` (class and system margins; placeholders skipped) | rejects margins above 1000 % | error text with range | no | no |
| MAS-A16 | sb/io/validation.py:306-312 | mass limit range `(0, 1e9]` kg | plausibility | error text | no | no |
| MAS-A17 | sb/blank.py:32 | `MATURITY_CLASSES = ("class_a", "class_b", "class_c")` labels (values TBD) | new-project wizard default catalogue | wizard | yes (edit `margin_policy.yaml`; names are free dict keys, model/config.py:186) | "labels only" |
| MAS-A18 | sb/examples.py:160 | example margins `class_a 0.05, class_b 0.10, class_c 0.20`; `system_power_margin_ratio 0.10` (162-166); mass margins TBD | invented example data | yes (file in examples/) | yes | invented, labelled |

#### A2. Thermal (THM)

| ID | file:line | value | purpose | visible? | editable? | source stated? |
|---|---|---|---|---|---|---|
| THM-A01 | sb/thermal/steady_state.py:20-21 | `STEFAN_BOLTZMANN_WM2K4 = 5.670374419e-8` | sigma | registry TH-SB (equations.py:154-160), report equation table, THERMAL_SOURCES.md:19 | no (constant, one value) | yes: "CODATA 2018 / SI 2019"; D-072; a test recomputes it |
| THM-A02 | sb/thermal/steady_state.py:59 | `tolerance_k = 1e-10` Newton step tolerance (default arg; `solve_steady_state` called at static_thermal.py:480 without override) | convergence | no | no | no |
| THM-A03 | sb/thermal/steady_state.py:60 | `max_iterations = 200` | convergence budget; failure raises ThermalSolveError -> THERMAL_SOLVE_FAILED | message only | no | no |
| THM-A04 | sb/thermal/steady_state.py:69 | `np.allclose(g, g.T)` default rtol 1e-5, atol 1e-8 decides "symmetric" | input check | no | no | no |
| THM-A05 | sb/thermal/steady_state.py:80 | initial guess `(sum(Q)/sum(R) + T_space^4)^0.25` (one-node equilibrium) | Newton start | no | no | comment "a good first guess" |
| THM-A06 | sb/thermal/steady_state.py:87-88 | damping: step scaled so that no temperature changes by more than 50 % (`0.5/biggest`) | keeps T > 0 | no | no | no |
| THM-A07 | sb/thermal/steady_state.py:166 | balance test `abs(flow) <= 1e-9 * through + 64*eps*(coupling@t)` per node, `through = Q + R(T^4+Ts^4) + sum G\|dT\|` (164) | the "converged" criterion (relative 1e-9 of node's own heat flow, plus 64 machine-epsilon floor at 165) | report prints only the largest absolute residual | no | docstring rationale (150-163) |
| THM-A08 | sb/thermal/steady_state.py:97-99, 117, 121, 123, 126 | `ACCURACY_K = 1e-4`, `REFINE_ROUNDS = 8`, `REFINED_K = 1e-7`, `64 * eps` floor | accuracy gate: if the temperature uncertainty bound exceeds 1e-4 K, iterative refinement with exact rational residual (`fractions.Fraction`, 136-147), accepted if correction <= 1e-7 K, else error | manual thermal-budget.md:157 mentions "conductances near 1e14 W/K"; thresholds not stated | no | docstring |
| THM-A09 | sb/thermal/static_thermal.py:138 | `_clean`: flows `< 1e-9 W` shown as 0.0 (also removes -0.0); applied to radiated, conducted and the residual (516-517, 530) | display of "radiated/conducted" and residual | no | no | docstring |
| THM-A10 | sb/reports/thermal_report.py:111 | residual shown as "below 0.000001 W" when `< 1e-6`, else 6 decimals | report text | yes (text) | no | no |
| THM-A11 | sb/reports/thermal_report.py:12, 19-20 | `ABSOLUTE_ZERO_OFFSET_K = 273.15` (name misleading: it is the Celsius offset) | C column in report | yes | no | no |
| THM-A12 | sb/thermal/static_thermal.py:129-133 | TH-ABS: `A (a*f_sun*S + a*f_earth*albedo*S + eps*f_earth*E_IR)`; albedo uses the Earth view ratio; IR absorptivity = emissivity (Kirchhoff); no cos factor, no solar distance | absorbed heat | formula in registry TH-ABS; "constant view ratios, DV-T2" | structure no; inputs yes | `SOURCE_MISSING` |
| THM-A13 | sb/thermal/static_thermal.py:464 | `R_i += eps * sigma * area` – radiating area = absorbing area, whole area radiates to `T_space` (no view to Earth/other nodes) | radiation to space | TH-BAL formula, DV-T1/T3 | no | `SOURCE_MISSING` |
| THM-A14 | sb/thermal/static_thermal.py:299-300 | duplicate conductances between the same pair are summed (`+=`) | parallel links | not documented | file | no |
| THM-A15 | sb/thermal/static_thermal.py:114-116, 203-216 | dissipation = `effective_power_w * ratio`, where `effective_power_w = avg*duty` from the power budget (unmargined, no system margin); peak = `peak_power_w * ratio`; only the average enters the temperature solve (403-405, 478) | heat input | DV-T3 (DEVIATIONS.md:22) and report note (thermal_report.py:28-29); NOT in the manual | no | TH-DISS `SOURCE_MISSING` |
| THM-A16 | sb/thermal/static_thermal.py:109-111 | status vocabulary `ok, exceeded, margin, no limits, n/a, ok (margin not checked)` | verdicts | manual table thermal-budget.md:148-155 | no | no |
| THM-A17 | sb/thermal/static_thermal.py:571-590 | `exceeded` if headroom < 0; `margin` if headroom < `temperature_margin_k` on EITHER side (same margin for hot and cold); `THERMAL_MARGIN_INSUFFICIENT` has severity ERROR (591-594) | thermal verdict | registry TH-LIMIT; manual | margin value yes (`temperature_margin_k`); rule no | TH-LIMIT `SOURCE_MISSING` |
| THM-A18 | sb/thermal/static_thermal.py:178-180 | unit node = `unit.thermal_node or unit.subsystem` | mapping | manual, D-039 | file | D-039 |
| THM-A19 | sb/model/thermal.py:216 | `limit_set: Literal["operating","survival"]`, default `operating` | which limit band | manual | file (choice among 2) | D-074 |
| THM-A20 | sb/model/thermal.py:151 | `heat_capacity_jperk` accepted but unused ("reserved for transient work") | schema | file format docs | n/a | no |
| THM-A21 | sb/model/thermal.py:182 | `area_m2 > 0` plain float (no source) | surface area | docs | file | NO source |
| THM-A22 | sb/model/equipment.py:56-59, 74-86 | temperature limits `> 0` plain floats, no source; rule: min<max, survival band must enclose operating band | unit limits | error text | file | NO source field (THERMAL_SOURCES.md:12 implies one) |
| THM-A23 | sb/model/equipment.py:28 | `heat_dissipation_ratio` in [0,1], default None (n/a, never 1.0); no source field | dissipation | manual | file | D-037 |
| THM-A24 | sb/io/validation.py:515-535, 541-577 | plausibility ranges: space temperature `(0, 1e4]`, temperature margin `[0, 1e4]`, solar flux `[0, 1e5]`, albedo `[0,1]`, Earth IR `[0, 1e5]`, conductance `(0, 1e12]`, emissivity `(0,1]`, absorptivity `[0,1]`, view ratios `[0,1]` | reject nonsense | error text with range | no | no |
| THM-A25 | sb/examples.py:777-820 | example thermal values (emissivity 0.85, absorptivity 0.6, G 0.5 W/K, space 3.0 K, margin 5.0 K, hot 1400 W/m2 / albedo 0.3 / IR 240, cold 0 / 0 / 240; view ratios hot 0.5/0.3, cold 0/0.8) | invented example data | in examples/ | yes | "invented" |
| THM-A26 | sb/thermal/static_thermal.py:303-317 | case solved independently, in dict order sorted by name (model/thermal.py:225-228); node order sorted alphabetically (thermal.py:200-203) | determinism | no | no | no |

#### A3. Units (UNT)

| ID | file:line | value | purpose | visible? | editable? | source stated? |
|---|---|---|---|---|---|---|
| UNT-A01 | sb/units/quantity.py:30-57 | catalogue of 25 field-name suffixes (`w, wh, hz, kg, kgm2, m, s, k, perk, wk, jperk, m2, wm2, ah, yr, deg, v, a, bps, bit, ratio, db, dbi, dbw, dbm, dbk`) each mapped to canonical label + pint unit | what unit a field name implies; the suffix is taken after the LAST underscore (97-102) | manual describe-the-spacecraft.md:77-86 lists a few; labels in schema docs | no | no |
| UNT-A02 | sb/units/quantity.py:61-67 | log offsets: `dbw` accepts `dBm` with -30, `dbm` accepts `dBW` with +30; `dbk` accepts `dB/K` and `dBK`; `db`, `dbi` only their own token | dB cross-conversion | partly in manual (:84,:86) | no | no |
| UNT-A03 | sb/units/quantity.py:68 | `_ALL_LOG_TOKENS = {db, dbi, dbw, dbm, dbhz, dbk, db/k, dbc}` (refused in linear fields; `dBHz` and `dBc` are recognised but accepted in no field) | refusal list | error text | no | no |
| UNT-A04 | sb/units/quantity.py:72 | `MAX_MAGNITUDE = 1.0e20` (also base.py:104) | rejects "far outside any physical range" | error | no | rationale in comment |
| UNT-A05 | sb/units/quantity.py:76-80 | token whitelist: regex `^[A-Za-z0-9_°µμΩ%/ ^*.·\-]{1,32}$`, exponents `**`/`^` with at most 2 digits and no chaining (77-78, 83-87), `m2`/`m3` rewritten to `m^2`/`m^3` (80, 137) | blocks pint expression evaluation | error text "unit is not recognised" | no | comment explains the attack |
| UNT-A06 | sb/units/quantity.py:90-94 | number grammar: ASCII digits only, accepts `nan/inf` then refuses (135) | parse | error | no | comment |
| UNT-A07 | sb/units/quantity.py:119 | `pint.UnitRegistry(cache_folder=None)`: pint's built-in default definitions (pyproject pin `pint>=0.24,<0.27`; installed 0.26.1); so `1 ton` -> 907.18 kg (US short ton), `1 year` = 365.25 d (value 1.0 yr), `1 MB/s` -> 8e6 bit/s, `1 GB` -> 8e9 bit, `1 lb` -> 0.45359237 kg (all checked by running `parse_quantity`) | the actual conversion factors | not shown; no list of accepted units in docs | no (pint version only) | pint library |
| UNT-A08 | sb/units/quantity.py:212 | linear results rounded to 15 significant digits `float(f"{value:.15g}")` (log and ratio results are not rounded) | `-40 degC` -> 233.15 | comment only; docs mention the -40 degC example (describe-the-spacecraft.md:86) | no | comment |
| UNT-A09 | sb/units/quantity.py:143-144 | `ratio` accepts only no unit, `ratio`, or `%`; `percent`, `ppm` refused | ratio parsing | error text | no | no |
| UNT-A10 | sb/units/quantity.py:146, 233-239 | a field is a temperature DIFFERENCE iff `"margin" in field` (substring); then `degC/degF` refused, `K`/`delta_degC` accepted. All other `_k` fields treat `degC` as absolute | degC handling | manual (:86) names `temperature_margin_k` only | no | no |
| UNT-A11 | sb/units/quantity.py:219-245 | refuses units containing radian/steradian outside `_deg` fields (so `60 rpm` is refused), refuses delta units in absolute temperature, refuses `< -1e-9 K` after conversion; a plain `-1 K` is accepted by the parser (range checked later) | physical sanity | error text | no | comment |
| UNT-A12 | sb/units/db.py:299, 303, 307, 311 | constants `1000.0` (mW per W) and `30.0` (dBW-dBm offset); `10 log10` power ratio convention (db.py:1-4) | dB helpers | docstring | no | no |
| UNT-A13 | sb/units/quantity.py:153-155 | example strings per suffix (`2.5 W`, `2.2 GHz`, `1.5 kg`, `35 min`) | error hints | error text | no | no |
| UNT-A14 | sb/model/base.py:13-14 | `extra="forbid"`, `frozen=True`, `allow_inf_nan=False` | strict file reading | schema | no | no |
| UNT-A15 | sb/model/base.py:139-141 | placeholder rule: `value is None` or `source.strip().upper() == "TBD"`; any other non-empty string (even "x") counts as a sourced value | what counts as a source | manual placeholders-and-sources.md (not read) | no | spec constraint 15 |

#### A4. Equations, assumptions, versions (EQN)

| ID | file:line | value | purpose | visible? | editable? | source stated? |
|---|---|---|---|---|---|---|
| EQN-A01 | sb/equations.py:258-377 | 40 equations; `source=None` for 37 (all but ENV-GMST l.333, ENV-GEODETIC l.356, TH-SB l.158) | registry | reports (closing_sections, reports/common.py:80-91), guide chapter (guide/build.py:79-94) | no | 3 of 40 |
| EQN-A02 | sb/equations.py:28-33, 123-127, 173-177, 253-256 | per-domain "project convention, decision D-0xx, text not available to the tool, owner to confirm" notes (`_TD_NOTE` D-061, `_TH_NOTE` D-071, `_LNK_NOTE` D-077, `_CONVENTION` D-040) | explains SOURCE_MISSING | yes (Notes column in guide; the report table prints only `source_text`, reports/common.py:80-91) | no | n/a |
| EQN-A03 | sb/assumptions.py:30-35 | hint text "Replace the placeholder with a sourced value; results that need it show n/a." and severity WARNING for every RESULT_INCOMPLETE | incompleteness | yes | no | no |
| EQN-A04 | sb/model/versions.py:4-22 | schema versions (unit 2, margin_policy 2, scenario 2, rest 1) | file migration | FILE_FORMAT.md | no | no |

### B. Hidden assumptions

| ID | file:line | assumption / behaviour | documented where? |
|---|---|---|---|
| MAS-B01 | sb/mass/static_mass.py:212-226 (`_cog`), 213 | CG and inertia use NOMINAL masses only; margin mass has no position; items without position or with mass 0 are dropped (never zero-position) | manual mass-budget.md:55, DV-M1, D-050; zero-mass dropping not documented |
| MAS-B02 | sb/mass/static_mass.py:126-132, 177-183 | Margin compounding: (nominal x (1+class)) summed, then x (1+system), not additive; same for expendables (propellant gets the maturity-class margin of its `maturity` field, no residual/loading-error allowance) | manual mass-budget.md:13 says "then", formulas only in registry (SOURCE_MISSING); expendable treatment not documented |
| MAS-B03 | sb/mass/static_mass.py:139-140, 159 | unit with `phases` set is absent in other phases; expendable must give every phase (`exp.masses_kg[phase]` KeyError otherwise, guarded by validation io/validation.py:973-1003) | manual :17 |
| MAS-B04 | sb/mass/static_mass.py:319-342 | expendable own inertia identical in every phase (does not scale with fill) | DV-M4, warning MASS_INERTIA_NOT_SCALED |
| MAS-B05 | sb/mass/static_mass.py:157-166, model/mass.py:97 | an expendable has ONE position for all phases (tank CG shift not modelled); DEVIATIONS DV-M3 (line 14) says "use phases and an expendable position per phase", which the model cannot express (the only way is one expendable per phase, with zero masses elsewhere) | DEVIATIONS DV-M3 (text does not match the model) |
| MAS-B06 | sb/mass/mass_properties.py:1-6, 58-67 | inertia tensor convention: Ixy etc. are tensor elements (minus product of inertia), own inertia axes parallel to the body frame (no rotation of items), all sums by `math.fsum` | D-048, report note (mass_report.py:164-165), docstring |
| MAS-B07 | sb/mass/mass_properties.py:42-52 | CG = total / zero-mass returns None (no CG); no treatment of negative masses (schema forbids) | docstring |
| MAS-B08 | sb/mass/static_mass.py:241-247 | a limit is compared with the system-margined total only; a limit with `phase: null` applies to every phase; if any margin is placeholder the status is `n/a` (not "ok") | report title "checked against the system-margined total" (mass_report.py:64) |
| MAS-B09 | sb/mass/static_mass.py:29-31, 177-183 | placeholder margin => margined masses and totals `None` (n/a) for the whole phase (one unknown class makes the entire phase total n/a), nominal total still shown | manual :13 |
| MAS-B10 | sb/reports/mass_report.py:48, 109; sb/reports/document.py:84-85 | margin and coverage printed as percent with `decimals-2` places, i.e. 1 decimal of percent (12.34 % shows 12.3 %); kg to 3 decimals, m 4, inertia 5 (mass_report.py:14, 17, 160-161) | numfmt.py docstring (rounding rule); precision per column not documented to the user; xlsx keeps exact values (DV-R1) |
| THM-B01 | sb/thermal/static_thermal.py:498-531, steady_state.py:77-94 | each node is isothermal; unit temperature = node temperature (no unit-to-node gradient, no interface resistance unless the user adds a node) | DV-T1 |
| THM-B02 | sb/thermal/static_thermal.py:119-133 | Kirchhoff: Earth IR absorbed with `eps` (infrared emissivity) not a separate IR absorptivity; albedo and Earth IR share ONE `earth_view_ratio`; no cosine/illumination geometry; solar flux not scaled with distance | formula text in registry TH-ABS and D-074 only; not in the manual; DEVIATIONS DV-T2/T3 cover "constant view ratios" |
| THM-B03 | sb/thermal/static_thermal.py:464, steady_state.py:82 | the radiating area equals the absorbing area, radiates with the same `eps`, to a single sink at `space_temperature_k` (user value, not 0 K); view to Earth does not reduce the sink view | DV-T3 (partly) |
| THM-B04 | sb/thermal/static_thermal.py:203-216, 403-405 | thermal input uses average electrical power x duty x ratio, UNMARGINED (no maturity or system margin); peak dissipation is reported but never drives a thermal case; no "hot case at peak" option | DV-T3 (DEVIATIONS.md:22) and report note; not in manual |
| THM-B05 | sb/thermal/static_thermal.py:343-355, 478 | a unit contributes only if the case's spacecraft mode assigns it a power mode; mission `phases` of the unit are ignored in thermal | not documented |
| THM-B06 | sb/thermal/static_thermal.py:299-300, 285-302 | conductance matrix symmetric; links between the same pair add; `links_ok` logic (301-302 re-sets True when there are no links) | not documented |
| THM-B07 | sb/thermal/static_thermal.py:399-405, 454-456, 467-477 | any missing input in a case (placeholder flux, one surface exposure, one dissipation ratio) makes the WHOLE case incomplete: no temperatures at all, unit checks become `n/a` | manual :155 ("placeholder upstream"), report text "not computed (inputs missing, see Problems)" |
| THM-B08 | sb/thermal/steady_state.py:73-75 | a node group with no radiating surface raises ThermalSolveError; surfaces with `eps` x `area` sum <= 0 count as no path | manual :157 |
| THM-B09 | sb/thermal/steady_state.py:123-133 | when the accuracy bound is exceeded, the answer is refined with exact rational arithmetic; if corrections do not die out the case fails rather than returning a number | manual :157 (1e14 W/K hint), docstring |
| THM-B10 | sb/thermal/static_thermal.py:136-138, 516-517 | radiated and conducted flows < 1e-9 W displayed as 0 | docstring only |
| THM-B11 | sb/thermal/static_thermal.py:571-574 | headroom sign convention: lower = T - Tmin, upper = Tmax - T; `required_margin_k` is applied symmetrically; it is stored in the check object (`UnitLimitCheck.required_margin_k`, l.83) but the check table (thermal_report.py:128-145) has no column for it | table notes |
| UNT-B01 | sb/model/base.py:38-46, sb/units/quantity.py:122-149 | a value written with a unit ("200 g") is converted to the canonical unit at load and only the converted float is kept; the original text and the "converted" fact are not stored or reported; on save the file holds the canonical number | manual describe-the-spacecraft.md:80 ("saved as 0.2") |
| UNT-B02 | sb/units/quantity.py:97-102 | the unit of a number is inferred ONLY from the field-name suffix; a value without a unit in a suffixed field is taken as already canonical (YAML number); a string without a unit is refused in linear fields (182-185) | manual :77 |
| UNT-B03 | sb/units/quantity.py:119, 195 | pint default registry decides every unit meaning (ton, year, MB, nmi, lb...); no restriction to a "safe" list; US short ton for `ton`, `tonne` = 1000 kg | not documented |
| UNT-B04 | sb/model/base.py:30-46 | the unit parser applies to fields with a unit suffix and to list/dict-of-float annotations only (`_holds_numbers`); a nested `Sourced.value` field (named `value`) is numeric-checked (l.27) but its unit is NOT inferred from the parent field name (the canonical unit of `conductance_wk.value` is implicit) | not documented; manual shows plain numbers inside Sourced |
| UNT-B05 | sb/units/db.py:276-279, 287, 295 | `ratio_to_db`/`watt_to_dbw` raise ValueError for non-positive input; reverse conversions do not guard overflow | docstring |
| UNT-B06 | sb/model/base.py:127-128 | many dict fields are re-sorted by key on load (thermal nodes thermal.py:200-203, cases 225-228, maturity classes config.py:190-193, expendable masses mass.py:99-104, assignments equipment.py:129-132, converter efficiencies config.py:202-205) -> the file order is not the model order; saved files change order | not documented |
| EQN-B01 | sb/equations.py (whole), sb/assumptions.py:11-19 | the registry is descriptive text: nothing ties equation ids to code (ids appear in docstrings: mass_properties.py:43, 56; static_mass.py:30; static_thermal.py:115, 129; steady_state.py:1); a code change can drift from `formula` without a failing test | guide chapter note (guide/build.py:196) |
| EQN-B02 | sb/assumptions.py:11-19 | an `Assumption` holds name, value, unit, source, file, path, placeholder; the `note` of the Sourced item is dropped, and plain-float inputs never appear | report "Configuration numbers used" |
| EQN-B03 | sb/mass/static_mass.py:345-480, thermal/static_thermal.py:149-172 | assumption rows are deduplicated by (file, path) only in thermal (153, 158-160); mass rebuilds them per class; the list is generated during computation, so a number unused in a given run (e.g. a class no unit uses, static_mass.py:367-370) is not listed | no |

### C. Outputs without a visible derivation

| ID | where the user sees it | what is missing |
|---|---|---|
| MAS-C01 | Mass report Summary "With system margin", Totals table, Limits table (mass_report.py:21-77, 128-144) | no statement of the formula next to the number, no breakdown "nominal -> + class margins (per class sum) -> + system margin" (only item rows and subsystem rows); the system margin value used is only in the assumption table, not in the Summary/Totals; the report equation table lists MASS-MARGIN, MASS-SYSMARGIN, MASS-COG, MASS-PARALLEL all `SOURCE_MISSING` |
| MAS-C02 | Limit status "ok"/"exceeded" (mass_report.py:56-77) | tolerance 1e-9 and the reference (system-margined total) are not in the table; the "Margin" column is limit minus margined total in kg, no percentage |
| MAS-C03 | CG x/y/z and "CG coverage" (mass_report.py:25-35, 48) | the contributing items per phase (which are excluded/point masses) are only in Problems (MASS_PROPS_MISSING once per file, `_property_problems` lines 280-316), not in the CG table; `CogResult.excluded_ids`/`point_mass_ids` (static_mass.py:77-78) are not exported |
| MAS-C04 | Inertia tensor table (mass_report.py:147-166) | no per-item contribution (own inertia, parallel-axis term), no principal moments/axes; formula MASS-PARALLEL SOURCE_MISSING; no conversion to product-of-inertia sign convention beyond the note |
| MAS-C05 | CSV export of mass (reports/export.py:70-109) | only the item table (no inertia, own-inertia flag, totals, CG, limits, system margin) |
| THM-C01 | Node temperature table (thermal_report.py:73-105) | absorbed heat is a single number per node: no split into sun / albedo / Earth IR per surface, no surface list, areas, radiation coefficient R_i, conductance matrix; the solver, its tolerances, iteration count and the convergence criterion are not stated (only "largest node imbalance"); the reference equation TH-BAL is SOURCE_MISSING |
| THM-C02 | Unit limit check table (thermal_report.py:114-145) | `required_margin_k` is not shown (it is in `UnitLimitCheck`, static_thermal.py:83); a `margin` status cannot be reproduced from the table; which limit set (operating/survival) is in the title but not the source of the limit (no source exists in the model) |
| THM-C03 | Dissipation tables (thermal_report.py:33-61) | "Effective power" is margin-free `avg x duty` but the column does not say so, the note on the summary does; peak dissipation shown but unused for temperatures |
| THM-C04 | Thermal "Configuration numbers used" table (via closing_sections) | lists Sourced values only; surface area, unit temperature limits, unit mass and heat-dissipation ratios (plain floats) have no source row, so the reader cannot tell which inputs have no source |
| UNT-C01 | any value entered with a unit | no record that "200 g" became 0.2 kg; GUI/report show only the canonical number (no "entered as" trace) |
| EQN-C01 | GUI | no equation view in the window (budget_gui has no equation reference); equations reach the user only in exported reports and in the guide (`budget guide`) |
| EQN-C02 | report "Equations" table (reports/common.py:80-91) | selected by id prefix (`MASS-`, `TH-`); the table lists the equations in the family whether or not the run used them (e.g. TH-SB appears even for a model with no surfaces; TH-LIMIT is listed but the code has no id reference), and omits non-registered computations (see EQN-D below) |
| EQN-C03 | "Source" column | prints `SOURCE_MISSING` for 37/40; the explanatory note (D-xxx "owner to confirm") is in the guide but only a general footnote in reports (common.py:89-90) |
| EQN-C04 | provenance block (provenance.py:39-61) | tool version + library versions + user + time, but no hash of the input files, no registry/equation version, no solver tolerance set, no pint registry definition version beyond library version |

### D. Forced options

| ID | file:line | the fixed choice | plausible alternatives |
|---|---|---|---|
| MAS-D01 | static_mass.py:126-132, 177-183 | margin = one multiplicative ratio per maturity class, then one multiplicative system margin on the sum | additive margin; margin per subsystem or per phase; mass growth allowance by maturity (percentile-based, AIAA S-120 / ECSS-E-ST-10-02/-20 style), separate expendable (propellant residual/loading) policy; margin on CG/inertia |
| MAS-D02 | static_mass.py:241-247 | limits compared with the system-margined total | compare to nominal or unit-margined total; allocations per subsystem; CG envelope and inertia-ratio limits |
| MAS-D03 | static_mass.py:212-226 | CG/inertia from nominal masses, point-mass if no own inertia, constant expendable inertia | CG/inertia with margin mass at an assumed position; per-phase positions and inertia scaling (tank fill models); CG uncertainty bounds |
| MAS-D04 | model/mass.py:78 | one body frame, free-text definition, no frame transforms; items axes parallel to body | per-item orientation (rotation matrices), several frames |
| THM-D01 | thermal/steady_state.py (whole) | steady-state lumped network, Newton solver, radiation to one sink temperature | transient solution (heat capacity field exists, unused), orbit-averaged cases, view-factor matrices between nodes, temperature-dependent conductance/optical properties (BOL/EOL) |
| THM-D02 | static_thermal.py:119-133 | TH-ABS form with Kirchhoff and shared Earth view ratio | separate IR absorptivity, separate albedo view factor, cosine/incidence angle, orbit-dependent fluxes computed from the environment module |
| THM-D03 | static_thermal.py:203-216, 403-405 | average unmargined power as heat | margined power, peak power as hot case, per-mode time-weighted average |
| THM-D04 | static_thermal.py:571-590 | symmetric required margin applied to both bounds, one margin for all units, hot and cold | per-unit/per-case margins, uncertainty margin policy (e.g. different values for hot/cold/predicted) |
| THM-D05 | model/thermal.py:216 | `limit_set` is the closed pair operating/survival | additional limit sets (turn-on, storage, acceptance/qualification offsets) |
| THM-D06 | steady_state.py:59-60, 97-99 | one fixed numeric recipe (Newton + exact refinement) and tolerances | user-selectable tolerance, solver choice, report of iterations; fail vs warn on precision |
| UNT-D01 | quantity.py:30-57 | unit catalogue is a fixed 25-suffix dictionary, canonical unit per suffix is fixed (SI-based, Wh, Ah, yr, deg) | user-defined suffixes/units, project unit policy (display units), restricted-unit whitelist instead of the whole pint registry |
| EQN-D01 | equations.py | single registry, one formula per quantity, no alternative equations selectable | alternative standard formulas (e.g. ECSS vs NASA mass growth, different thermal models) selectable per project and recorded in the result |

### E. Interfaces

| ID | file:line | direction | what / format | user told? | provenance? |
|---|---|---|---|---|---|
| MAS-E01 | sb/io (via io/validation.py:959-1003, model/mass.py:88-97) | in | `expendables/<id>.yaml` (YAML, schema v1) | yes (manual) | schema_version only; no file hash recorded in results |
| MAS-E02 | model/mass.py:113-130; io/validation.py:306-312 | in | `config/mass_limits.yaml` | yes | schema_version; each limit has `source` |
| MAS-E03 | model/config.py:183-193 | in | `config/margin_policy.yaml` (v2; v1 migrated, io/migrations.py:110-137) | yes | each number has `source`; migration adds TBD placeholders |
| THM-E01 | model/thermal.py:193-203, 218-228 | in | `config/thermal_model.yaml`, `config/thermal_environment.yaml` (optional files, no missing-file warning other than RESULT_INCOMPLETE) | yes (manual) | `source` on every Sourced number; none on area/limits |
| THM-E02 | model/equipment.py:90-103 | in | `units/<id>.yaml` incl. `temperature_limits`, `thermal_node`, `mass_properties`, `catalogue_ref` (reserved, unused: equipment.py:98) | yes | no per-field source |
| MAS-E04 | reports/mass_report.py, reports/export.py:70-109 | out | mass budget report (PDF/DOCX/XLSX) and CSV per phase | yes | provenance block (tool, libs, project, revision, time, user); no input hashes |
| THM-E03 | reports/thermal_report.py, reports/export.py:126-175 | out | thermal report; CSV per mode (dissipation) and per case (node temperatures) | yes | same provenance block; no check/limit CSV |
| UNT-E01 | units/quantity.py:115-119 | in (library data) | pint built-in unit definitions; `cache_folder=None` (no cache file written) | no | pint version listed in provenance libraries (provenance.py:29) |
| EQN-E01 | equations.py -> guide/build.py:79-94, reports/common.py:80-91 | out | "Equations and sources" chapter in the generated guide and the Equations table in each report | yes | none (no registry version) |
| EQN-E02 | model/versions.py:4-22; src/budget_core/schemas | out | exported JSON schemas (`budget export-schemas`) | CLAUDE.md only | `schema_version` per file kind |
| UNT-E02 | model/base.py:38-46 | in/out | file values written with units are normalised on load; saving rewrites the canonical number | docs line 80 | none (original text lost) |
| THM-E04 | static_thermal/session (sb/../budget_gui/session.py:61-68) | internal | GUI runs the mass and thermal budgets on every run alongside the power budget, no separate switch | no | n/a |

### Already good

- `Sourced` + `TBD` placeholder mechanism with `RESULT_INCOMPLETE` and n/a propagation, never zero (model/base.py:131-141, assumptions.py:30-35, static_mass.py:20-23, static_thermal.py:136-172). It is the base for any "every default visible" rule.
- Margin policy, system margin, mass limits, thermal environment and thermal model values are all in editable, sourced config files; maturity classes are free-named (model/config.py:186).
- "Configuration numbers used" table (name, value, unit, source, status) in every mass and thermal report, with file and path in the Assumption object.
- Equation registry with id, formula, source or `SOURCE_MISSING`, notes; rendered in the guide and in reports; the three sourced entries show the intended pattern.
- DEVIATIONS.md (DV-M1..M4, DV-T1..T3) and DECISIONS.md numbering; report notes state the nominal-mass rule for CG (mass_report.py:51-52) and the dissipation rule (thermal_report.py:28-29).
- Thermal residual reported (balance_residual_w) and an accuracy gate that refuses a number instead of reporting a wrong one (steady_state.py:102-133).
- Unit parser: whitelist, explicit refusal of implicit dB/linear and degC/delta mistakes, error messages without the input value; documented in the manual (describe-the-spacecraft.md:84-86).
- Report rounding rule documented (numfmt.py:1-7, DV-R1).
- Mass / thermal problems carry file + path so the GUI can jump to the cause.
- Provenance block in every report (tool, library versions, project revision, time, user).

### Notes for the plan

- Golden files: `examples/` and `src/budget_core/schemas` are generated and tests fail on drift (CLAUDE.md). Adding fields to `Unit`, `Surface`, `TemperatureLimits`, `Expendable` (e.g. `source`, `note`) or new config files (solver settings, tolerance, margin application mode) needs a schema version bump + migration (model/versions.py, io/migrations.py) and regeneration of schemas and examples.
- Byte-identical outputs: the report numbers use exact decimal rounding (numfmt.py) and CSVs use `repr(float)` (export.py:104); adding columns/rows to mass or thermal reports or CSVs changes golden/compare outputs (compare_run.py keys rows by the first column, DV-C1).
- Numerical results must not change by exposing constants: THM-A02..A09 define the current answers to the last digits; moving them to config must keep defaults identical. The `64 eps` floor and 1e-9 balance test shape which cases fail with THERMAL_SOLVE_FAILED.
- Equation registry is not machine-linked to code: a registry-to-code binding (ids in the code paths that compute, a test that every computed quantity has an id) would be a precondition for any "show the equation behind this number" feature. Currently unregistered computations: system margin application (static_mass.py:178-183 has no id comment), mass-limit status (241-247), inertia about CG (`inertia_about`, mass_properties.py:70), inertia-physical test (model/mass.py:20-45), thermal solver algorithm (steady_state.py), node radiation coefficient R_i (static_thermal.py:464), unit conversions (quantity.py), dB helpers (db.py) and Celsius display offset (thermal_report.py:12). Registered but with no id reference in code: MASS-SYSMARGIN, PWR-SYSMARGIN, PWR-PEAK, TH-LIMIT, TH-SB.
- Sourced is attached to config numbers only; extending provenance to unit-level inputs (mass, power modes, limits, areas) touches the largest set of files (units/*.yaml, unit_table import/export, GUI grids, wizard dialogs).
- The `"margin" in field` temperature-difference heuristic and suffix-by-last-underscore inference are structural: any new field name must follow them; a metadata-driven unit declaration would be a model-wide change.
- `pint` definitions are an external behaviour dependency (version range `>=0.24,<0.27`); freezing the accepted list or recording the registry version in provenance affects `packaging/lock.sh` and the licence check.
- Python 3.14-only syntax (`except A, B:`) prevents running the CLI on 3.13; any verification run needs 3.14 (tests under `tests/`).
- Documentation to keep true when changing this area: DEVIATIONS.md (add Kirchhoff/shared view ratio, expendable margin, margin compounding, DV-M3 text vs model), mass-budget.md, thermal-budget.md (unmargined dissipation, numerics), THERMAL_SOURCES.md:12, thermal-budget.md:91 (claims every number has a source).

## Appendix C — RF link

Paths are under `/home/user/systembudgetstudio/src/budget_core/` unless stated. Line numbers verified by reading/grep.
"Engine" = `link/evaluate.py` (EV) and `link/budget.py` (BU).

### Summary
- Counts: A = 27, B = 24, C = 12, D = 11, E = 12 findings.
- The equation chain (EIRP, FSPL, G/T, C/N0, Eb/N0, margin) is plain, textbook and correctly documented as LNK-* in `equations.py:173-247`. The gaps are around the chain, not in it.
- Top gaps:
  1. LNK-001/LNK-020: the report and UI show only sums and results. The static table gives EIRP, G/T and "Other losses" as one sum, never their components (power, line loss, gain, pointing, polarisation, implementation). Attenuation is shown as one summed number. Nothing shows the nadir angle or the gain actually taken from the pattern at each sample. The series CSV has no nadir angle and no antenna gain column.
  2. LNK-005/LNK-006: attenuation lookup silently holds the end value outside the tabulated elevations (np.interp clamps), and a single entry is a constant at all elevations. Interpolation is linear in elevation of dB, with no warning when the elevation is outside the table. Optimistic if the lowest tabulated elevation is above the evaluated one.
  3. LNK-007/LNK-021: the antenna model is 1-D (angle from nadir only), the spacecraft boresight is always at nadir regardless of attitude, the Earth is a sphere (R = WGS-84 equatorial) for that angle, and a pattern is held flat beyond its last angle. The model choices are fixed, only documented, and not user-selectable. Two copies of the Earth radius exist.
  4. LNK-010/LNK-011/LNK-012: hard-coded engine policies that change results and are not editable: 5 s pass sampling, selection of the highest closing rate with no hysteresis, per-day = linear scaling of the total, 1 % frequency tolerance for attenuation entries, "larger loss wins" for duplicates, first-match for the Eb/N0 entry. `max_elevation_deg` is missing from the user manual.
  5. LNK-024/LNK-025: the Eb/N0 table is a bare number per (modulation, coding) text pair, with no BER/FER target, no reference, no bandwidth or code-rate fields. Rb is silently the information rate. `polarisation` strings and `attenuation_kind` are stored but never used in computation. The report's provenance has no input file hashes (pattern CSV, tables).

### A. Constants, defaults, thresholds, rules

| ID | file:line | value | purpose | visible to user? | editable w/o code? | source stated? |
|---|---|---|---|---|---|---|
| LNK-001 | link/constants.py:9-10 | c = 299 792 458 m/s | FSPL (BU:41-45) | In report Equations table, `equations.py:194` ("c = ..."). Not in "Configuration numbers used". | No | Yes, "SI 2019 exact"; owner confirmed D-078/D-141 |
| LNK-002 | link/constants.py:11-13 | k = 1.380649e-23 J/K, k_dB = 10log10(k) = -228.599 dBW/Hz/K | C/N0 (BU:57-61) | Report equation text `equations.py:208`; the dB value is not shown | No | Yes, SI 2019 |
| LNK-003 | link/constants.py:14-15 | R_earth = 6 378 137.0 m, hard-coded second copy | Spacecraft range from Earth centre and nadir angle (BU:84-98) | Only in code comment, DEVIATIONS DV-L2, and `LNK-NADIR` text (value not given). Not in the report | No; a spherical Earth is the only choice. Not tied to site altitude or ellipsoid | Yes (WGS 84 equatorial); duplicates `environment/constants.py:23` (not imported from it; a comment claims they are equal) |
| LNK-004 | link/evaluate.py:36 | LINK_SAMPLE_S = 5.0 s | Max length of a pass piece, each evaluated at its midpoint | User manual link-budget.md says "at most 5 s", DV-L3, D-130. Not in reports/JSON/assumptions | No | Rationale in comment (D-057, DV-L3); no value justification |
| LNK-005 | link/evaluate.py:37, 758, 820 | DAY_S = 86 400 s; per-day = total / (duration/DAY_S); threshold `duration >= DAY_S*(1-1e-9)` | Data per day = linear scaling of the scenario total | Report note "scaled to 86 400 s" (link_report.py:142), `LNK-VOLUME` | No. The per-day rule is not selectable | Rationale in D-130 |
| LNK-006 | link/evaluate.py:364 | 0.01 (1 %) | Which attenuation entries count as "for the link frequency" | D-134, FILE_FORMAT error code list. Not in link-budget.md. Not in the report; only a warning appears when none match | No | None |
| LNK-007 | link/evaluate.py:406 | `max(...)` of duplicates | Two attenuation entries of one name at the same elevation (reachable only via the fallback to "all entries") use the larger loss | Warning `LINK_ATTENUATION_DUPLICATE` | No | None |
| LNK-008 | link/evaluate.py:527 | `entries[0]` | First Eb/N0 entry matching the exact (case-sensitive) text pair | No. The loader makes the pair unique (config.py:60-67), so benign | No | n/a |
| LNK-009 | link/evaluate.py:735, 846, 858 | 1e-12 s | Sample "active" threshold; empty pass; empty piece | No | No | None |
| LNK-010 | link/evaluate.py:849 | `- 1e-9` in `ceil(dur/5 - 1e-9)` | Piece count | No | No | None |
| LNK-011 | link/evaluate.py:734-737 | `el <= max_elevation_deg` (inclusive) | Tracking-limit rule: samples above the limit are inactive and carry 0 rate and 0 volume | Field in FILE_FORMAT.md:164 and D-077. Not described in link-budget.md. The pass series CSV has an `active` column | Yes (`max_elevation_deg` in the link file, gt 0, le 90, model/link.py:135) | n/a (user input) |
| LNK-012 | link/evaluate.py:622, 752 | `m >= required_margin` (no tolerance) | "Closes" test; rate selection = highest listed rate that closes | Equation text `LNK-MARGIN`; D-077 | The listed rates and the margin are user inputs. The rule is not | n/a |
| LNK-013 | model/link.py:113-114 | elevation 0..90, range gt 0 | Static point limits; not checked against geometry | JSON schemas | No | None |
| LNK-014 | model/link.py:123, 135 | frequency gt 0; max_elevation (0,90] | Input bounds | Schemas | No | None |
| LNK-015 | model/link.py:168 | pattern angles in [0, 180] and strictly increasing | Pattern validity | Error message | No | None |
| LNK-016 | io/validation.py:588-627 (checks at 593-627) | power_w (0, 1e12]; line/pointing/pol/impl/required_margin/feed loss [0,100] dB; T_sys (0, 1e6] K; G/T [-100,100] dB/K; antenna gain [-50,100] dBi | Range checks (`CONFIG_VALUE_INVALID`). Negative losses or a negative required margin are refused | FILE_FORMAT.md:40 lists only gain, G/T, Eb/N0 and attenuation ranges. Power, loss, margin and T_sys ranges are not documented | No | None |
| LNK-017 | io/validation.py:630-649 | required_ebn0 [-20, 60] dB; attenuation loss [0,100] dB | Table range checks | FILE_FORMAT.md:40 | No | None |
| LNK-018 | model/config.py:72 | attenuation_kind in {rain, gas, cloud, scintillation, other} | Fixed catalogue. Used only as a label, never in a computation (grep: no other use) | Schema | No | n/a |
| LNK-019 | model/link.py:121 (`direction: Literal["downlink","uplink"]`) | 2 directions | Fixed catalogue. Decides which end is the spacecraft (EV:224, 561-572). No crosslink, no relay | Docs | No | n/a |
| LNK-020 | new_link.py:40 | FREQUENCY_RANGE_MHZ = (1.0, 1e6) | Sanity check in the wizard | Error text states it | No | Comment: "a sanity range, not a standard" |
| LNK-021 | new_site.py:39-41 | lat [-90,90], lon [-180,180], altitude [-1000, 100000] m | Wizard limits. Match the model, model/environment.py:121-125 | Error text | No | Comment: "as the model takes it" |
| LNK-022 | model/environment.py:125 | min_elevation_deg in [0, 90) | Site visibility threshold; no default (good). In the pass maths the mask is `elevation >= min_elevation` (environment/elements.py:310) | Wizard text | Yes (user input) | n/a |
| LNK-023 | model/environment.py:17 (DETECTION_STEP_S) | 20 s | Fixed grid on which passes are detected (edges bisected to 1e-3 s, elements.py:41). Sets which passes exist for the link pass series | DV-E4, D-130 | No | Rationale in D-130 |
| LNK-024 | environment/elements.py:320 | `max(el_max, min_elevation)` | The reported pass max elevation is clamped up to the site minimum | No | No | None |
| LNK-025 | new_unit.py:23-25 (used by new_link/new_site/new_ebn0) | MAX_ID = 60, MAX_TEXT = 120, id regex | Wizard limits | Messages | No | n/a |
| LNK-026 | reports/link_export.py:37-38, 69-71 and link_report.py (Column decimals) | CSV 6 decimals (elev/range 3, freq 1), report columns 1 to 3 decimals, rate in kbit/s, volume in Mbit and MByte (= bits/8e6, decimal) | Output rounding; half-up on the shortest decimal (numfmt.py:3-8) | Rounding rule only in the numfmt docstring. The report does not say "MByte = 10^6 bytes" | No | None |
| LNK-027 | plots/link.py:13-26 | RATE_COLORS (12 hex), y 0..90 deg for elevation (95) | Plot presentation (out of scope except the y clamp) | Plot | No | n/a |

### B. Hidden assumptions

| ID | file:line | assumption / behaviour | documented where? |
|---|---|---|---|
| LNK-B01 | EV:557, 560-572; BU:93-98 | Spacecraft antenna angle is measured from nadir only (axisymmetric, 1-D pattern, no azimuth). The boresight is always at nadir whatever the attitude, mode or pointing. A ground antenna is always at angle 0 (constant gain, perfect tracking). | DV-L2 (owner confirmed), FILE_FORMAT.md:169, link-budget.md "Antennas" (partly). Not in the report. `LNK-NADIR` equation text says so briefly |
| LNK-B02 | BU:84-98; EV:557 | Nadir angle: spherical Earth, R = 6 378 137 m, site at sea level (site altitude and ellipsoid ignored). The angle is derived from the elevation and range at the sample. Inconsistent static-point pairs (range impossible for the elevation) are silently clipped by `np.clip(ratio,-1,1)` (BU:98). | DV-L2 and `LNK-NADIR`. The clip is not documented; no warning for a static point whose elevation and range do not fit the orbit |
| LNK-B03 | BU:105 (`np.interp`) | Antenna pattern: linear interpolation of dBi vs angle (not in linear power), ends held flat beyond the first/last angle. A pattern ending at 60 deg gives the 60 deg gain at 120 deg. No warning when queried outside the table. | link-budget.md:"ends held", FILE_FORMAT.md:169. Not in the report |
| LNK-B04 | BU:108-132; EV:339-416 | Attenuation: each named series is interpolated linearly in elevation (dB vs deg, not cosec), ends held flat. One entry (or entries with elevation None) = a constant at every elevation. An entry with `elevation_deg` None is added to the interpolated part. Elevations below the lowest tabulated value use that value (can be optimistic). Multiple names are summed. No warning for out-of-range elevation. | `LNK-ATT` text "linear interpolation by elevation"; the end-hold is documented nowhere for attenuation. link-budget.md does not describe the attenuation table at all |
| LNK-B05 | EV:361-379 | Frequency match tolerance of attenuation entries is 1 % of the link frequency. With no match, all entries of that name are used (warning). With several in-tolerance entries (different freq_hz) they all enter the same elevation set and the "larger loss" rule applies. No interpolation in frequency. | D-134, FILE_FORMAT error codes. Not in the user manual |
| LNK-B06 | EV:414-416 | If any entry of any named attenuation is a placeholder, the whole atmospheric term is None, so C/N0 and everything downstream is n/a (not only that entry). | D-134 (summary), RESULT_INCOMPLETE problem. No per-entry n/a explanation in the output |
| LNK-B07 | EV:489-491 | `fixed_losses` = pointing + polarisation + implementation, summed and applied as a constant at every sample and static point. Pointing loss does not depend on the pattern or on geometry. If any one is a placeholder, all three vanish and C/N0 is n/a. | DV-L2; `LNK-CN0` equation. The components are not itemised in the static table or CSV (only the sum, `other_losses_db`) |
| LNK-B08 | EV:560-581 | Computation order is fixed: EIRP = P_dBW - L_line + G_tx(angle); G/T; atmospheric; C/N0 = EIRP - FSPL - (L_atm + L_fixed) + G/T - k_dB. All losses are in dB and added. | equations.py:173-247 |
| LNK-B09 | EV:566-572 | G/T: either given as a constant (no angle dependence, no weather-dependent sky noise, no antenna-pattern effect), or G_rx - feed_loss - 10log10(T_sys). Feed loss is subtracted from G, with no T_amb reference-plane treatment. The T_sys is a single input (no breakdown into sky/LNA/ground). | `LNK-GT` ("referenced to the antenna output as given") |
| LNK-B10 | EV:621-622, 750-754; BU:64-68 | Eb/N0 = C/N0 - 10log10(Rb), where `data_rates_bps` is the information bit rate. The coded/channel rate is not separate, and the required Eb/N0 is per (modulation, coding) text pair. The table has no BER/FER/target availability, no Es/N0, bandwidth, roll-off or symbol-rate check. | `LNK-EBN0`. The meaning of "data rate" (information vs channel) and of "required Eb/N0" (BER target) is not stated |
| LNK-B11 | EV:512-535 | Eb/N0 lookup is on exact, case-sensitive text equality of modulation and coding. | new_ebn0.py header; D-200 |
| LNK-B12 | EV:626-631, BU:76-81 | "Rate at required margin" is a continuous value C/N0 - Eb/N0_req - margin, independent of the listed rates; infinite = n/a. | Report column name only. Not in `LNK-*` equations |
| LNK-B13 | EV:750-757 | Rate selection per sample: highest listed rate that closes, else 0. No hysteresis, no ramp, no acquisition time, protocol overhead or coding overhead. Inactive samples have rate 0. | D-081, DV-L3, link-budget.md ("Not modelled") |
| LNK-B14 | EV:697-716, 717-723 | Pass sampling: with exact geometry (the propagator) each pass is split into pieces of at most 5 s, each evaluated at its midpoint. With imported SMS data, the pieces are the parts of the pass in each scenario step and elevation/range are linearly interpolated from the grid arrays (EV:721-722). The result then depends on the file and on `step_s`. | DV-L3, link-budget.md (the imported case is only in DV-L3) |
| LNK-B15 | EV:726-735 | `active_modes`: only the time of each piece that overlaps the listed mode segments counts. The elevation test for `max_elevation_deg` is made at the piece midpoint only, so the whole piece is dropped or kept. | D-098, link-budget.md (partly). The midpoint treatment of the tracking limit is not documented |
| LNK-B16 | EV:756-758, 777-781 | Volume = sum(selected_rate x in-pass seconds). Per-day = volume / (duration/86400), only if duration >= 1 day. The lowest margin shown is at the lowest listed rate over active samples only. `usable_s` = time where a rate closes. | link-budget.md, DV-L3, `LNK-VOLUME`. Fixed |
| LNK-B17 | EV:749-752 | Margins (K,R) are computed for inactive samples as well and appear in the series CSV and the plot; only `selected_rate`, volume and the minimum margin exclude them. | Not documented. The `active` column exists in the CSV |
| LNK-B18 | EV:707, environment/geometry.py:90-106 | Elevation is geometric (WGS-84 geodetic up, no refraction, UTC treated as UT1 for GMST). This is the geometry for pass edges and for the link's elevation. | DV-E1 (not linked from link-budget.md) |
| LNK-B19 | EV:556-558, 561 | `nadir`, `zero`: for a ground-side antenna the "angle" is a vector of zeros, so a gain function would be evaluated at 0 deg (a pattern on the ground end is refused at load, validation.py:720-731). | FILE_FORMAT.md:169 |
| LNK-B20 | EV:131-161 | The "Configuration numbers used" table lists each sourced number once per (file, path), so a number shared by two links appears once. Values of c, k, R_earth and LINK_SAMPLE_S are not rows of it. | Report section "Configuration numbers used" |
| LNK-B21 | EV:703-705 | A link with `peer` None is skipped silently in the pass series (static points only). The peer not being in the scenario `sites` is a warning (LINK_SITE_NOT_IN_SCENARIO). | DV-L2 (inter-satellite link = static only) |
| LNK-B22 | link/evaluate.py:243-256 | Pattern CSV: UTF-8 with or without BOM, comma separator only, header names case-insensitive, rows with empty first cell skipped, extra columns ignored, angle 0..180 strictly increasing. Fully re-read at every run. | Error hint; link-budget.md (partly: no BOM/semicolon rules) |
| LNK-B23 | EV:50-70 vs report | `required_margin_db` is the single "margin" definition: closes when Eb/N0 - Eb/N0_req >= required margin. No separate split of the margin into policy parts (for example link margin vs implementation vs weather). | `LNK-MARGIN` |
| LNK-B24 | EV:149-154, 175-179 | A `None` in an input blanks only what needs it (never zero), D-134. A placeholder power gives n/a EIRP, so n/a margins. n/a is an empty cell (CSV) and null (JSON). | docs/user-manual/placeholders-and-sources.md, link_export.py:3 |

### C. Outputs without a visible derivation

| ID | where the user sees it | what is missing |
|---|---|---|
| LNK-C01 | Static table "EIRP (dBW)", report/CSV/JSON (link_report.py:36, link_export.py:72) | Components P_tx (dBW), line loss and antenna gain at the chosen angle are not shown. The nadir angle used is not shown either. The pattern gain taken is hidden |
| LNK-C02 | "G/T (dB/K)" | When built from antenna + T_sys + feed loss: the receive gain at the angle, the feed loss and 10log10(T_sys) are not itemised |
| LNK-C03 | "Other losses" (link_report.py:42, 'other_losses_db' CSV) | Pointing, polarisation and implementation are summed. Only the sum is in the table and CSV. The JSON `static` rows have `other_losses_db` only. The assumptions list has the three values separately, but not next to the row |
| LNK-C04 | "Atmospheric" and `atmospheric_loss_db` | The sum of all named attenuation entries. Which entries (and which elevation breakpoints, interpolation weights, the 1 % frequency match, the end-hold) is not shown |
| LNK-C05 | "Path loss" | The FSPL inputs (range, frequency) are shown; c is not. Fine for a static table, but the pass series has no per-sample frequency or Doppler note |
| LNK-C06 | "C/N0", "Eb/N0", "Margin" | No term-by-term sum row (EIRP - FSPL - L_atm - L_other + G/T - k) is shown. k_dB (-228.6) is nowhere in the UI. The user cannot reproduce the sum from the table without knowing k |
| LNK-C07 | "Highest closing rate", "Rate at required margin" | Selection logic is not shown (only in a table note, link_report.py:68-71). No column says which constraint (required margin value) was applied at each row, except in the separate rate table |
| LNK-C08 | Series CSV (link_export.py:96-149) and plots | No column for the nadir angle, the antenna gain actually used, the `fixed losses` or the `mode` at the sample. The `active` flag does not say why it is inactive (mode, tracking limit, or outside) |
| LNK-C09 | "Usable (s)", "Lowest margin" (pass table) | `usable_s` counts piece lengths of the rate>0 samples only. "Lowest margin" is at the lowest listed rate over active samples. Both are named in notes only; the number of samples and the 5 s piece length are not shown |
| LNK-C10 | "Data volume per link", "Per day (Mbit/MByte)" | The report says "scaled to 86 400 s". The GUI table (link_view.py:416-417) and the CLI (budget_cli/main.py:587-596) give no such note. The GUI status line "x MByte in the scenario" uses 8e6, which is not stated |
| LNK-C11 | Problem `LINK_NOT_CLOSED` (EV:585-594) | The message does not give the best margin reached or the shortfall (by design, no values in problems). The user must find it in the table |
| LNK-C12 | Reports (docx/pdf/xlsx/json) | The report's "Equations" table lists LNK-* (the `LNK-` prefix, common.py:81-91) and cites "SOURCE_MISSING". The equation table has no constants and no model choices (R_earth, 5 s, 1 %). Provenance rows (provenance.py:50-61) have no input file hashes, no pattern file |

### D. Forced options

| ID | file:line | the fixed choice | plausible alternatives |
|---|---|---|---|
| LNK-D01 | BU:41-45 | Free-space loss only; no atmosphere model; no ionosphere, no depolarisation | ITU-R P.618/P.676/P.840/P.531 models (user tables only today, DV-L1, DV-P3); different tables |
| LNK-D02 | EV:339-416; model/config.py:70-76 | Attenuation: a single dB per elevation, no statistics (availability, exceedance %), no climate input, no station dependence | Table per availability %, per station; csc(el) scaling; frequency interpolation; separate rain/gas/cloud/scintillation roll-up (RSS vs sum) |
| LNK-D03 | BU:63-66; EV:557-572 | Spacecraft antenna: 1-D pattern, boresight at nadir | Offset boresight, 2-D (az/el) patterns, attitude-driven pointing, gimbal or steering, sun-pointing mode, an off-nadir angle from the scenario |
| LNK-D04 | EV:84-98, 557 | Spherical Earth, R = WGS-84 equatorial | WGS-84 ellipsoid, site altitude, a local radius |
| LNK-D05 | EV:489-491 | Pointing/polarisation/implementation losses are fixed constants | Pointing loss from pattern and mispointing; polarisation loss from axial ratio; implementation loss by modulation and rate; per-rate losses |
| LNK-D06 | EV:750-757 | Highest closing rate chosen per sample, no hysteresis | Adaptive coding and modulation (ACM) with several MODCODs, hysteresis, fixed rate per pass, margin-weighted choice, rate choice by data-volume goal |
| LNK-D07 | EV:512-535; config.py:48-67 | Required Eb/N0 is a single number per (modulation, coding) | Table per BER/FER target, versus rate, Eb/N0 from Es/N0 and spectral efficiency, bandwidth and noise-bandwidth checks, a link margin split into named contributions |
| LNK-D08 | EV:758 | Per-day volume is linear scaling and n/a below one day | Average over N days of a longer propagation; a worst-day figure; a per-orbit figure |
| LNK-D09 | EV:36, 849 | 5 s pass pieces, midpoint evaluation | A finer or user-chosen step, adaptive step, trapezoid or Simpson integration |
| LNK-D10 | model/link.py:121; EV:224 | Only downlink/uplink with a ground station; an ISL is static points only (no geometry) | Crosslink with a scenario target spacecraft, relay links, multiple stations in parallel sharing a link |
| LNK-D11 | EV:707-722 | Imported (SMS) geometry is interpolated linearly in elevation and range; the exact geometry uses SGP4 | Cubic or higher interpolation, a source flag in the output |

### E. Interfaces

| ID | file:line | direction | what / format | user told? | provenance? |
|---|---|---|---|---|---|
| LNK-E01 | io/project_loader.py (links/ directory); model/link.py | in | `links/<id>.yaml` (kind: link, schema v1) | Yes (FILE_FORMAT.md:137-172) | File names only. No hash of the file in the reports |
| LNK-E02 | io (config) | in | `config/ebn0_table.yaml`, `config/attenuation_table.yaml` (kind tables, entries with `{value, source, note}`) | Yes (link-budget.md mentions both; FILE_FORMAT.md:24-25) | Each used value with its source is listed in "Configuration numbers used" (value, unit, source, status). No hash of the file |
| LNK-E03 | EV:227-270 | in | Antenna pattern CSV (`angle_deg,gain_dbi`) at a project-relative path, resolved inside the project root (`resolve_inside`) | Yes (link-budget.md "How do I give an antenna gain?"; error hint) | `pattern_source` text only. No hash. The file's name and path are in the assumption row. Re-read at every run |
| LNK-E04 | io loader for `ground_stations/`, `targets/` | in | `ground_stations/<id>.yaml`, `targets/<id>.yaml` (lat, lon, altitude, min elevation) | Yes (FILE_FORMAT.md:12-13) | No `source` field on a site position or min elevation. They are plain numbers, not `Sourced` (model/environment.py:121-125) |
| LNK-E05 | scenario/run.py:50-85 | in | Scenario `sites` list ties stations to links. `scenarios/<id>.yaml` | Yes | Scenario id in provenance |
| LNK-E06 | environment/spacemissionstudio.py:36-44 | in | Imported `profile_<site>.csv`, `passes_<site>.csv` (elevation, azimuth, range) as the geometry for the pass series when `environment_source: spacemissionstudio` | Yes (ENVIRONMENT_FORMAT.md) | Not in link outputs (the link reports do not say the geometry came from an import) |
| LNK-E07 | reports/run.py:114-140; link_export.py | out | `link_static.*` / `link_passes_<scenario>.*` as CSV (static), per-link series CSV, passes CSV, JSON, DOCX, PDF, XLSX | Yes (reports-and-exports.md) | Provenance table (tool, Python, libraries, project, revision, scenario, time, user). No input hashes, no engine constants |
| LNK-E08 | reports/link_export.py:199-247 | out | JSON: static rows, assumptions (the sourced values), problems, provenance; with passes: scenario id/start/duration/step, per-link summary and passes. Series samples are not in the JSON (only in the series CSV) | Partly | Provenance dict |
| LNK-E09 | plots/link.py; reports/link_report.py:211-229 | out | Link plot PNG embedded in the report (margin per rate, selected rate, elevation) | Yes | None. Plot colours, y clamp 0..90 are fixed |
| LNK-E10 | budget_cli/main.py:143, 216, 487-510, 555-596 | in/out | CLI `budget run --budget link`, `budget link-passes`: console summary of volume in MByte (/8e6) | Yes (command-line.md) | None |
| LNK-E11 | new_link.py, new_ebn0.py, new_site.py, remove_item.py; GUI dialogs `add_link_dialog.py`, `add_ebn0_dialog.py`, `add_site_dialog.py`, `remove_item_dialog.py` | out (writes project files) | Create `links/<id>.yaml`, `config/ebn0_table.yaml` rows, `ground_stations/`, `targets/` files, with every number as a `source: TBD` placeholder (new_link.py:130-131, new_ebn0.py:223-230). Removal is blocked while a scenario or link names the file (remove_item.py:416-481) | Yes (dialog text; link-budget.md) | Standard Sourced note "Placeholder: supply the project's value." Site coordinates and min elevation are required with no default (good) |
| LNK-E12 | examples/*/links, config | in | The shipped examples carry every link number as TBD (no invented values). The only content is structure: frequencies, rates, pattern angles/gains of the X-band example with `source: TBD` | Yes (examples/README.md) | n/a |

### Already good
- Every link number from a data sheet or standard is a `Sourced` value with a mandatory `source`; `TBD` or null = placeholder. Placeholders yield n/a (never 0), term by term (D-134), and a RESULT_INCOMPLETE problem lists the exact file and path (EV:137-154).
- "Configuration numbers used" in each report/JSON lists each used value, unit, source, file and path, placeholder status (`Assumption`, assumptions.py:12-21; EV:131-154), including attenuation entries and Eb/N0 entries with their table paths.
- The LNK-* equations (`equations.py:173-247`) are shown in the report's Equations table, together with their source status (SOURCE_MISSING, to be confirmed). The units are in the field names. c and k are given in the equation text with the SI source.
- Constants have an attached source string (link/constants.py); the owner confirmed them (D-078, D-141).
- Deviations are published: DV-L1, DV-L2, DV-L3, DV-P3, DV-E1, DV-E3, DV-E4 (docs/DEVIATIONS.md:9-25).
- The series CSV has `in_pass_s` and `active`; the rows add up to the pass volume (link_export.py:117-119). Time in UTC and in seconds.
- The wizards ask no invented numbers (new_link.py, new_ebn0.py, new_site.py); a site has no default minimum elevation (model/environment.py:125).
- Result independence of `step_s` for propagated geometry (D-130); numerical text rounding rule is one place (reports/numfmt.py).
- `pattern_file` stays inside the project folder, with a size/shape check and a clear error (EV:227-270).
- Golden files for link reports exist (tests/golden/link_*), plus 19 hand-calculation regression cases (docs/demo/M5.md).

### Notes for the plan
- Byte-identical constraint: goldens in `tests/golden/link_*` (docx/json/pdf/xlsx text and CSV for microsat_150kg, microsat_250kg and a synthetic case). Any added column, row, note or equation text in the link report changes them. JSON schemas and examples are also regenerated and tested for drift (`budget export-schemas`, `export-examples`). A new field on `Link`, `Antenna` or the tables needs a schema version bump plus a migration (CLAUDE.md).
- Per-term itemisation (EIRP, G/T, losses, nadir angle, antenna gain) can be added to `Evaluation`/`StaticRow` (frozen dataclasses, EV:42-70, 541-551) and the CSV/JSON. These are mostly additive in the engine, but they change the CSV headers, the JSON keys and all link goldens.
- The nadir/pattern machinery (EV:557-572) is shared by the static and the pass paths. Evaluate is called with arrays (K samples) and with 1-element arrays for static points. Both have to stay consistent.
- Making constants editable: c, k and R_earth are "definitional" by D-054/D-078/D-141, and the owner has confirmed that they ship in code. Editing them is a policy change. The simplest transparent route is to list them (value, source) in the Assumptions table. LINK_SAMPLE_S, the 1 % tolerance, and the end-hold/extrapolation rule are engine policy with no owner confirmation and no config home. `config/` has no link policy file today; any new file needs a kind, schema, loader entry (project_loader.py), validation, `FILE_FORMAT.md`, and `DECISIONS.md` entries.
- Two Earth-radius copies (link/constants.py:14, environment/constants.py:23) can drift; the link one is hard-coded. Any model choice (ellipsoid, site altitude) would touch both and `DV-L2`.
- Attenuation: `attenuation_kind` and the `polarisation` strings are stored but unused, so they are free metadata hooks. Interpolation or extrapolation changes (flag out-of-range, csc scaling) change numerical results and all goldens that use non-placeholder attenuation (the examples ship placeholders, so shipped goldens are n/a there; synthetic goldens in tests/link_helpers.py are the real numeric tests).
- Imported-geometry path (EV:721-722) depends on the grid and `step_s`; changing the sampling policy needs both branches (`_pass_pieces` EV:836-860).
- Docs to change together with code: link-budget.md (no attenuation, Eb/N0-table, tracking-limit, polarisation sections), FILE_FORMAT.md:137-172, DEVIATIONS.md DV-L*, equations.py `LNK-*`, DECISIONS.md. User-visible GUI text must keep the professional terminology and the "no values in problems/messages" rule (CLAUDE.md).
- GUI: the Link budget tab renders `session.link_document` (the report document), so a change in `link_report.py` reaches the window, the DOCX/PDF/XLSX and the goldens at once. The pass tab (`budget_gui/link_view.py:380-420`) builds its own tables and its own MByte (8e6) arithmetic, separately from the report and the CLI (three copies of the Mbit/MByte conversions: link_view.py:327,416-417; budget_cli/main.py:592-596; link_report.py:125-127).

## Appendix D — Loading, validation, Problems and schemas

Area: `src/budget_core/io/*`, `problems.py`, `schemas.py`, `schemas/*.json`, `model/*.py` (bounds, defaults), `model/versions.py`, `units/quantity.py`, `timeutil.py`, plus every `Problem(` emitter in core/GUI (needed for requirement 12). Docs read: `docs/FILE_FORMAT.md`, `docs/user-manual/read-and-fix-problems.md`, `placeholders-and-sources.md`, guide chapter `11-troubleshooting.md`, DECISIONS D-102/D-120/D-133, DEVIATIONS.
Method: read all files; probed the loader on a copy of `examples/microsat_250kg_eps` (a py3.13-compatible copy of the source because the repo uses py3.14-only `except A, B:` syntax). Probe outputs are quoted as "probe". Nothing in the repository was changed.

### Summary

- Counts: A 120 rows (62 constants/defaults in A1, 42 range rows in A2 holding about 51 bounds, 16 pydantic-bound rows in A3), B 27, C 11, D 12, E 14; Problem codes enumerated: 82 (identical to the list in FILE_FORMAT.md, table below).
- No override or waiver mechanism exists anywhere (grep for waive/suppress/acknowledge/override/justif finds nothing relevant). The only controls are `--strict` (warnings fail, `budget_cli/main.py:137,355`) and replacing a number with a `TBD` placeholder. Every plausibility range and pydantic bound is a hard error that makes `LoadResult.project = None` (`project_loader.py:512`): the whole project is unusable and the user cannot "accept with justification".
- Requirement 12: of 82 codes, none carries the actual value (SCHEMA_TOO_NEW prints the schema-version integer read from the file, the one exception); a limit number appears for about 8 (pydantic bounds via FIELD_INVALID/IMPORT_VALUE_INVALID, `CONFIG_VALUE_INVALID` range, `ORBIT_EPOCH_FAR` 30 d, `LINK_ATTENUATION_FREQUENCY` 1 %, `ENV_PROPAGATION_FAILED` years, schema versions). "Why it matters" is stated (Y) for 16 and partly (P) for 20; the rule is stated for 72 (P 9, N 1). `Problem` is a flat dataclass (`problems.py:21-29`: severity, code, message, file, path, line, hint) with no structured fields for rule, rationale, actual, limit or override route; the actual/limit numbers for result findings exist in result tables (`LimitCheck`, `UnitLimitCheck`, `Violation.extreme`) but not in the Problem.
- Wrong or generic hints: `FIELD_INVALID` always gets the unit hint "Write a number in W, or a value with a unit (for example '2.5 W')" even when the rule violated is "peak must not be below average", "step must not exceed duration", or the field is a ratio ("Write a number in ratio ... '2.5 ratio'") (`errors.py:52-58,75`, probe). `CONFIG_VALUE_INVALID` always says "ratios are written as fractions (0.1 means 10 %)", also for Eb/N0 in dB, temperatures and gains (`validation.py:268`, probe).
- Unit and scenario numbers carry no source: `mass_kg`, `avg_power_w`, `peak_power_w`, `temperature_limits`, ground-station data, orbit elements are plain floats (`equipment.py:23-30,95`); only `config/*` and `links/*` use `Sourced`. D-102 states this openly. The `TBD` placeholder mechanism therefore cannot flag an unsourced unit mass or power.
- Silent save behaviour: `save_edited_data` falls back to rewriting the whole file canonically (all comments lost; comments are where users keep sources per `roundtrip.py:3-5`) and returns `SaveResult.canonical=True`, but the only caller ignores it (`model_document.py:421`). `write_project` and `dump_yaml` never keep comments (`yamlio.py:256`).

### A. Constants, defaults, thresholds, rules

"Visible" = shown to the user in UI/report/message; "Editable" = changeable without editing code. Unless noted: visible only in docs (FILE_FORMAT.md) or in the message text, not editable, no source stated.

#### A1. Loader and parser limits, catalogues, constants

| ID | file:line | value | purpose | visible? | editable? | source? |
|---|---|---|---|---|---|---|
| IOV-A001 | io/yamlio.py:66, project_loader.py:169-177 | MAX_YAML_BYTES = 1,000,000 | refuse bigger project file (FILE_INVALID / YAML_SYNTAX) | docs FILE_FORMAT.md:186; message omits number | no | rationale in comment (memory/time exhaustion) |
| IOV-A002 | yamlio.py:67 | MAX_YAML_LINES = 20,000 | same | docs only | no | comment |
| IOV-A003 | yamlio.py:68 | MAX_YAML_LINE_CHARS = 50,000 | same | docs only | no | comment |
| IOV-A004 | yamlio.py:69 | MAX_FLOW_DEPTH = 32 (nested `[`/`{`) | scanner is quadratic in flow depth | docs only | no | comment (65 s for 60,000 brackets) |
| IOV-A005 | yamlio.py:70 | MAX_FLOW_BRACKETS = 2,000 of each of `[ ] { }` | same | docs only | no | comment |
| IOV-A006 | yamlio.py:71 | MAX_FLOW_ITEMS = 30,000 commas | same | docs only | no | none |
| IOV-A007 | yamlio.py:72,130 | MAX_YAML_DEPTH = 64 | nesting | docs only | no | none |
| IOV-A008 | yamlio.py:73,132 | MAX_YAML_NODES = 60,000 | entry count (about 60 us/node) | docs only | no | comment |
| IOV-A009 | yamlio.py:169-204 | anchors/aliases, any tag, merge key `<<` refused | alias bomb, misreading. A lone anchor `&x` without alias is accepted (probe), contrary to docs "anchors ... not supported" (FILE_FORMAT.md:186) | message + docs | no | comment |
| IOV-A010 | quantity.py:72; base.py:91-106; quantity.py:147 | MAX_MAGNITUDE = 1e20 in canonical unit, every numeric field | refuse overflow-prone numbers | docs | no | comment |
| IOV-A011 | quantity.py:76-80 | token regex `{1,32}` chars, exponents max 2 digits | stop pint expression evaluation | no | no | comment |
| IOV-A012 | quantity.py:30-57 | fixed catalogue of 26 unit suffixes (w, wh, hz, kg, kgm2, m, s, k, perk, wk, jperk, m2, wm2, ah, yr, deg, v, a, bps, bit, ratio, db, dbi, dbw, dbm, dbk) | field-name suffix defines the unit | docs (D-025) | no | none |
| IOV-A013 | quantity.py:61-67 | log token offsets (dBW <-> dBm 30, dB/K = dBK) | log unit conversion | docs | no | none |
| IOV-A014 | quantity.py:212 | `float(f"{value:.15g}")` | rounds converted values to 15 significant digits (so 233.15 not 233.14999...) | no | no | comment |
| IOV-A015 | quantity.py:215-245 | rpm/rad refused, degC below 0 K refused, "margin" in field name = temperature difference (`difference="margin" in field`, :146) | unit sanity; the margin rule keys off a substring of the field name | docs (FILE_FORMAT.md:38) | no | comment |
| IOV-A016 | unit_table.py:52-55 | MAX_FILE_BYTES 5,000,000; MAX_UNPACKED_BYTES 50,000,000; MAX_ROWS 100,000; MAX_COLUMNS 50 | table import | D-102; message omits numbers | no | comment |
| IOV-A017 | unit_table.py:185-188 | CSV delimiter guessed from header line among `, ; \t` (most frequent; default `,`) | import | D-102 | no | none |
| IOV-A018 | unit_table.py:345 | `_same`: rel_tol 1e-12, abs_tol 1e-15 | a cell equal within this is "unchanged" in the import plan | no | no | none |
| IOV-A019 | unit_table.py:39-50 | KEY/INFO/NUMBER columns fixed (6 power-mode number columns) | template | docs | no | none |
| IOV-A020 | project_loader.py:58-67 | CONFIG_FILES: 8 fixed config kinds | which config files exist | docs | no | none |
| IOV-A021 | project_loader.py:70 | OPTIONAL_CONFIG = power_system, thermal_model, thermal_environment (others missing -> CONFIG_MISSING warning) | policy | docs | no | none |
| IOV-A022 | project_loader.py:260-269 | ENTITY_FOLDERS: units, modes, expendables, orbits, ground_stations, targets, scenarios, links | layout | docs | no | none |
| IOV-A023 | project_loader.py:270 | `_CLEAN_ID = [A-Za-z0-9][A-Za-z0-9_-]*` (otherwise ID_UNUSUAL warning) | id style | message/docs | no | D-120 |
| IOV-A024 | project_loader.py:224,247-257 | `kind` equality check, `schema_version` must be an int >= 1 (`migrations.py:35,52`) | file identity | message | no | none |
| IOV-A025 | model/base.py:141; model/link.py:42; io/validation.py:241; link/evaluate.py (pattern_source) | placeholder test: `value is None` or `source.strip().upper() == "TBD"`; the literal "TBD" is repeated in 4 places, not centralised | defines "placeholder" | docs (placeholders-and-sources.md) | no | spec constraint 15 |
| IOV-A026 | model/base.py:136; errors.py:98-101 | `source` only needs `min_length=1` and not spaces-only (`base.py:65-76`): "x" or "n/a" or "TBC" is accepted as a source; only the exact string TBD (any case) flags a placeholder | source quality | docs | no | none |
| IOV-A027 | validation.py:176,217 | CONFIG_PLACEHOLDER is severity WARNING (not ERROR); GUI maps it to class "Not checked" via `problem_class.py:23` `NOT_CHECKED_CODES = {CONFIG_PLACEHOLDER, RESULT_INCOMPLETE, THERMAL_NO_LIMITS}` | severity policy | docs | no | D-151 |
| IOV-A028 | validation.py:262; project_loader.py:512 | every range violation is ERROR; any ERROR => project None | severity policy | docs | no | none |
| IOV-A029 | versions.py:3-22 | CURRENT_VERSIONS (18 kinds; unit 2, scenario 2, margin_policy 2, rest 1) | schema versions | docs + JSON schema `const` | no | D-143 |
| IOV-A030 | migrations.py:162-169 | migration registry: margin_policy 1->2, scenario 1->2, unit 1->2 only | migration | docs FILE_FORMAT.md | no | D-051/D-062/D-071 |
| IOV-A031 | migrations.py:98-99,116-118,137 | v1->v2 margin policy inserts mass margin as placeholder `{value: null, source: TBD, note: "Added by migration ..."}` | migration default | FILE_MIGRATED info + CONFIG_PLACEHOLDER per field | by editing file | D-051 |
| IOV-A032 | timeutil.py:12-13 and model/environment.py:18 | MIN_YEAR 1950, MAX_YEAR 2100, defined twice | time range | message/docs | no | D-120, D-133; DUPLICATED constant |
| IOV-A033 | environment.py:15 | MAX_SAMPLES = 1,000,000 | scenario size (`duration_s/min(step_s,20)+1`) | message "too many time steps; increase step_s" (no numbers) | no | comment |
| IOV-A034 | environment.py:16,187-188 | MAX_RULES = 10,000 per scenario for rules and segments | size | pydantic message (limit shown) | no | none |
| IOV-A035 | environment.py:17,218 | DETECTION_STEP_S = 20.0 (pass/eclipse detection grid, independent of step_s) | accuracy/size | DV-E4 in DEVIATIONS | no | D-146 |
| IOV-A036 | environment.py:19,67 | SEMI_MAJOR_AXIS_RANGE_M = (6.4e6, 1.0e8) m (Earth only; no Moon/other bodies; perigee check is by SGP4, not by radius) | orbit bound | pydantic msg shows 6400000 | no | comment only |
| IOV-A037 | environment.py:68-72 | eccentricity [0,1), inclination [0,180], RAAN/argp/M [0,360) | angle ranges | pydantic msg | no | none |
| IOV-A038 | environment.py:122-125 | latitude [-90,90], longitude [-180,180], altitude [-1000, 100000] m, min_elevation [0,90) | site bounds | pydantic msg | no | none |
| IOV-A039 | environment.py:95,97 | TLE line length 69, first chars `1`/`2`, checksum mod 10 (:37-40), same satellite number (:101), epoch parse (:43-60: day 1..367, 2-digit year pivot `year < 57` => 20xx) | TLE validity | message | no | none cited (NORAD format) |
| IOV-A040 | environment.py:224,228 | 1e-9 s tolerance in segment overlap/outside checks | scenario | no | no | none |
| IOV-A041 | power_system.py:22-25 | MAX_STRINGS 10,000; MAX_CELLS_PER_STRING 10,000; MAX_CELLS_IN_SERIES 1,000; MAX_CELLS_IN_PARALLEL 10,000 | count bounds | pydantic msg, D-133 | no | comment "far above any real spacecraft" |
| IOV-A042 | power_system.py:26-27,31-42 | MAX_DIRECTION_COMPONENT 1e6; MIN_DIRECTION_LENGTH 1e-6 | direction vectors | message ("must not exceed {limit}") | no | none |
| IOV-A043 | link.py:36; link/evaluate.py:253 | antenna pattern angles must lie in [0, 180] deg, strictly increasing, >= 2 points (YAML pattern and CSV pattern; rule duplicated in two places) | pattern validity | message (CSV: hint) | no | none |
| IOV-A044 | mass.py:28-45 | inertia physicality test with tol = 1e-9 * scale, scale floor 1e-300 | rigid-body check | message "cannot belong to a rigid body" (no numbers) | no | docstring only |
| IOV-A045 | mass/static_mass.py:26,243,329 | LIMIT_TOLERANCE_RATIO = 1e-9: margin within 1e-9*max(1,limit) counts as 0 (met); same constant decides MASS_INERTIA_NOT_SCALED (mass spread > 1e-9 of max) | pass/fail tolerance | no (not in any report) | no | comment "as in D-097" |
| IOV-A046 | power/time_domain.py:47-52 | RATIO_TOL 1e-9, POWER_TOL_W 1e-9, ENERGY_TOL_WH 1e-6, REFINE_TOL_S 1e-6, PENUMBRA_MIN_S 0.01, MAX_REFINE_ROUNDS 4 | tolerances deciding violation detection (power agent owns detail) | no | no | comment |
| IOV-A047 | environment/elements.py:71,81 | MAX_TLE_AGE_DAYS = 30.0 -> ORBIT_EPOCH_FAR warning | TLE staleness | message states 30 days | no | comment "a TLE is a fit around its epoch" (no citation); D-133 |
| IOV-A048 | link/evaluate.py:364 | attenuation entry within 1 % of link frequency else LINK_ATTENUATION_FREQUENCY | matching | message states "1 %" | no | none |
| IOV-A049 | link/evaluate.py:36,37,758,820 | LINK_SAMPLE_S 5.0; DAY_S 86400; per-day volume only if duration >= DAY_S*(1-1e-9) | link sampling/per-day | DV-L3 | no | D-ref |
| IOV-A050 | power/time_domain.py:540-557 | orbit energy balance needs step <= quarter of the orbit period and >= 3 steps | ORBIT_BALANCE_NOT_EVALUATED | message states "quarter of the orbit period" | no | none |
| IOV-A051 | mass.py:52-54 (`ixy/ixz/iyz = 0.0`), mass.py:77-78 | off-diagonal inertia default 0.0 | silent default | docs | by file | none |
| IOV-A052 | equipment.py:25 | `duty_cycle_ratio` default 1.0 | silent default (a unit with no duty is on 100 %) | docs FILE_FORMAT.md:30 | by file | D-024 |
| IOV-A053 | equipment.py:28 | `heat_dissipation_ratio` default None => thermal n/a | n/a not 0 | docs | by file | D-037 |
| IOV-A054 | environment.py:150-151 | `lead_s`, `lag_s` default 0.0 | pass window padding | docs | by file | none |
| IOV-A055 | environment.py:177,183 | `environment_source` default "elements"; `shadow_model` default "cylindrical" | silent model choice | DV-P1 | by file | none |
| IOV-A056 | thermal.py:82 | `limit_set` default "operating" | which limits a case checks | docs | by file | none |
| IOV-A057 | project.py:58 | no `mission_phases` => single phase "all" | phase default | docs | by file | none |
| IOV-A058 | equipment.py:101 (`phases`), 102 (`thermal_node`) | `phases=None` => unit in all phases; `thermal_node=None` => node named like `subsystem` | defaults | docs | by file | D-039 |
| IOV-A059 | link.py:122,133-134 | `active_modes` empty => every mode; `peer=None` => static points only; `attenuation=[]` => no atmospheric loss | defaults | docs | by file | none |
| IOV-A060 | io/errors.py:82-91 | FIELD_UNKNOWN suggestion uses `difflib.get_close_matches(n=1)` default cutoff 0.6 | typo hint | no | no | none |
| IOV-A061 | yamlio.py:258-262 | canonical dump: indent mapping 2 / sequence 4 / offset 2, width 4096, no comments, `null` for None | write format | docs | no | D-ref |
| IOV-A062 | project_loader.py:89 | optional fields that are None or "" are omitted on canonical write | write format | no | no | none |

#### A2. Plausibility ranges that raise CONFIG_VALUE_INVALID (error) in `io/validation.py` `_value_ranges`

Skipped when the number is a placeholder or None (`validation.py:286-287`), so a missing/TBD number is never range-checked. Brackets: `(` open, `[` closed. Neither the actual value nor the unit of the range appears in the message; the hint is always the ratio hint (line 268). Not in the JSON schemas (the `Sourced.value` schema has no bounds, see `schemas/margin_policy.schema.json`); docs list only 5 of these ranges (FILE_FORMAT.md:40: gain_dbi, g_over_t, required_ebn0, loss_db, "ranges of earlier versions").

| ID | line | quantity (field) | allowed range |
|---|---|---|---|
| IOV-A101 | 300 | class power/mass margin ratio | [0, 10] |
| IOV-A102 | 302 | system power/mass margin ratio | [0, 10] |
| IOV-A103 | 306-314 | mass limit `limit_kg` | (0, 1e9] kg |
| IOV-A104 | 318-326 | `distribution_loss_ratio` | [0, 1) |
| IOV-A105 | 328-336 | `converter_efficiency_ratio` | (0, 1] |
| IOV-A106 | 343 | `design_life_yr` | (0, 1e3] |
| IOV-A107 | 345-352 | `solar_irradiance_wm2` | (0, 1e4] |
| IOV-A108 | 353-361 | `cell_area_m2` | (0, 1e12] |
| IOV-A109 | 362-370 | `cell_efficiency_ratio` | (0, 1] |
| IOV-A110 | 371-379 | `reference_temperature_k` | (0, 1e4] |
| IOV-A111 | 380-388 | `cell_temperature_k` | (0, 1e4] |
| IOV-A112 | 389-397 | `efficiency_temp_coeff_perk` | (-1, 1) |
| IOV-A113 | 398-406 | `packing_loss_ratio` | [0, 1) |
| IOV-A114 | 407-415 | `harness_loss_ratio` | [0, 1) |
| IOV-A115 | 416-424 | `annual_degradation_ratio` | [0, 1) |
| IOV-A116 | 425-433 | `cell_capacity_ah` | (0, 1e12] |
| IOV-A117 | 434-442 | `cell_nominal_voltage_v` | (0, 1e12] |
| IOV-A118 | 443-451 | `charge_efficiency_ratio` | (0, 1] |
| IOV-A119 | 452-460 | `discharge_efficiency_ratio` | (0, 1] |
| IOV-A120 | 461-469 | `annual_capacity_fade_ratio` | [0, 1) |
| IOV-A121 | 470-478 | `initial_soc_ratio` | [0, 1] |
| IOV-A122 | 479-487 | `limits.peak_power_w` | (0, 1e12] |
| IOV-A123 | 491-500 | `max_dod_ratio` per phase | (0, 1] |
| IOV-A124 | 513-521 | `space_temperature_k` | (0, 1e4] |
| IOV-A125 | 522-529 | `temperature_margin_k` | [0, 1e4] |
| IOV-A126 | 532 | `solar_flux_wm2` | [0, 1e5] |
| IOV-A127 | 533 | `albedo_ratio` | [0, 1] |
| IOV-A128 | 534-536 | `earth_ir_wm2` | [0, 1e5] |
| IOV-A129 | 540-548 | `conductance_wk` | (0, 1e12] |
| IOV-A130 | 551-559 | `emissivity_ratio` | (0, 1] |
| IOV-A131 | 560-567 | `absorptivity_ratio` | [0, 1] |
| IOV-A132 | 570-577 | `solar_view_ratio`, `earth_view_ratio` | [0, 1] |
| IOV-A133 | 593 | transmitter `power_w` | (0, 1e12] |
| IOV-A134 | 594 | `line_loss_db` | [0, 100] |
| IOV-A135 | 595-601 | `required_margin_db`, `pointing_loss_db`, `polarisation_loss_db`, `implementation_loss_db` | [0, 100] (negative required margin or negative loss refused) |
| IOV-A136 | 602-611 | `system_noise_temperature_k` | (0, 1e6] |
| IOV-A137 | 613 | `feed_loss_db` | [0, 100] |
| IOV-A138 | 615 | `g_over_t_dbk` | [-100, 100] |
| IOV-A139 | 616-625 | antenna `gain_dbi` | [-50, 100] |
| IOV-A140 | 633-640 | `required_ebn0_db` | [-20, 60] |
| IOV-A141 | 642-649 | attenuation `loss_db` | [0, 100] |
| IOV-A142 | 341, 511, 589 | `big = 1e12` local constant used as the "upper bound" of many of the above | |

#### A3. pydantic `Field` bounds (error text e.g. "Input should be greater than or equal to 0", limit shown, actual not; all in JSON schemas)

| ID | file:line | bounds |
|---|---|---|
| IOV-A201 | equipment.py:23-24 | `avg_power_w`, `peak_power_w` >= 0; peak >= avg (:33-41) |
| IOV-A202 | equipment.py:25 | `duty_cycle_ratio` [0,1], default 1.0 |
| IOV-A203 | equipment.py:28 | `heat_dissipation_ratio` [0,1] |
| IOV-A204 | equipment.py:29-30 | `min_duration_s`, `max_duration_s` > 0; min <= max (:41-48) |
| IOV-A205 | equipment.py:56-59 | temperature limits > 0 K; min < max; survival band encloses operating band (:62-87) |
| IOV-A206 | equipment.py:95 | unit `mass_kg` >= 0 (0 kg allowed, no upper bound except 1e20) |
| IOV-A207 | equipment.py:137 | bus `nominal_voltage_v` > 0 |
| IOV-A208 | environment.py:141-143,150-151,181-182 | segment `start_s` >= 0, `duration_s` > 0; `lead_s`,`lag_s` >= 0; scenario `duration_s` > 0, `step_s` > 0, step <= duration (:214) |
| IOV-A209 | link.py:113-114 | static point elevation [0,90], range > 0 |
| IOV-A210 | link.py:123,135 | `frequency_hz` > 0; `max_elevation_deg` (0, 90] |
| IOV-A211 | link.py:128 + validator :138-143 | `data_rates_bps` non-empty, all > 0, silently `sorted(set(...))` |
| IOV-A212 | config.py:73-74 | attenuation `freq_hz` > 0, `elevation_deg` [0,90] |
| IOV-A213 | mass.py:49-51 | inertia diagonal >= 0; `negative_mass` check on `masses_kg` (:101-104) |
| IOV-A214 | mass.py:78 | `position_m` exactly 3 entries |
| IOV-A215 | thermal.py:21,52 | `heat_capacity_jperk` > 0 (reserved, unused); surface `area_m2` > 0 |
| IOV-A216 | power_system.py:51-52,90-91 | string/cell counts: see IOV-A041 |

### B. Hidden assumptions

| ID | file:line | assumption/behaviour | documented where? |
|---|---|---|---|
| IOV-B001 | project_loader.py:512-513 | any ERROR (including range violations and result-independent file problems) sets `project=None`; nothing is computed, no partial results, even when the error is in an unused optional file | docs say "invalid input stops the budget" (read-and-fix-problems.md:17) |
| IOV-B002 | validation.py:286-287 | range checks are skipped for placeholder or missing values, so a `TBD` is never checked and a missing number gives n/a downstream | implicit |
| IOV-B003 | base.py:141, assumptions.py, power/time_domain.py:206-214, link/evaluate.py:146-153 | a Sourced number with a real value but `source: TBD` is DISCARDED (treated as missing, result n/a); the value is not used even provisionally | placeholders-and-sources.md says "n/a (never a silent zero)"; does not say a present value is ignored |
| IOV-B004 | base.py:15-45 | before validation every field named like a unit is parsed: strings with units converted to canonical, yes/no refused in numeric fields, text refused in numbers without suffix, blank text refused | FILE_FORMAT.md:38 |
| IOV-B005 | quantity.py:146 | a temperature field whose name contains "margin" is treated as a difference (K), others absolute; `degC` in a margin refused | FILE_FORMAT.md:38 |
| IOV-B006 | quantity.py:212 | linear unit conversions are rounded to 15 significant digits | comment only |
| IOV-B007 | yamlio.py:163-164 | unquoted ISO date/time in YAML loads as datetime and is silently re-serialised (`+00:00` -> `Z`, other offsets rejected later by `parse_utc`) | no |
| IOV-B008 | timeutil.py:65 | fractional seconds truncated to 6 digits (9 accepted); date-only means 00:00:00; no trailing Z means UTC | FILE_FORMAT.md:39 partly |
| IOV-B009 | environment.py:34 (`_utc` returns `format_utc`) | `start_utc` and `epoch_utc` are normalised on load, so the saved file differs from the typed text | no |
| IOV-B010 | many `_sorted` validators: config.py:30-33,42-45; equipment.py:129-132; mass.py:101-104; power_system.py:98-101,118-121; thermal.py:57-60,70-73,95-98; link.py:138-143 | dict keys are sorted alphabetically on load (classes, assignments, converter map, masses_kg, max_dod, by_mode, exposure, nodes, cases); `data_rates_bps` sorted and de-duplicated; so file order is not preserved in the model/canonical write | no |
| IOV-B011 | project_loader.py:89 | canonical write drops optional fields equal to None or "" | no |
| IOV-B012 | yamlio.py:256; project_loader.py:114 | `write_project` / `dump_yaml` write without comments | docstring only |
| IOV-B013 | roundtrip.py:244-250; model_document.py:421 | in-place save falls back silently to a whole-file canonical rewrite (comments lost) when the patch cannot be verified or the file is an older schema; `SaveResult.canonical` is never read by the GUI/CLI | docstring only |
| IOV-B014 | migrations.py:87-95; FILE_MIGRATED | migrated in memory; message gives versions but not which fields were renamed/added; for margin_policy the new mass margins become placeholders (visible only as separate CONFIG_PLACEHOLDER entries) | FILE_FORMAT.md "Margin policy schema 2" |
| IOV-B015 | schemas.py:3-6 | JSON schemas describe canonical numbers only, not "2.2 GHz" strings; they carry pydantic bounds but not the A2 ranges nor cross-field rules (peak >= avg, survival encloses operating, receiver/antenna exclusivity); `schema_version` pinned with `const` current version | schemas.py docstring; FILE_FORMAT.md:203 claims "exported JSON Schemas carry the limits" (true only for A3) |
| IOV-B016 | project_loader.py:279-283,366,383 | `os.listdir` of entity folders, `.yaml` only, sorted by name; `.yml`, upper-case, nested folders skipped with FILE_IGNORED (only inside project root and entity/config folders; other file types silent) | FILE_FORMAT.md:35 |
| IOV-B017 | project_loader.py:444-461 vs validation.py failure sets | a reference to a file that failed to load is not reported (no REF_UNKNOWN_*) | FILE_FORMAT.md:36 |
| IOV-B018 | validation.py:149-154 | cross-file checks run only when `project.yaml` and `spacecraft.yaml` loaded; `_value_ranges` etc. need a full project | no |
| IOV-B019 | validation.py:1049-1062 | orbit validity is tested by actually running SGP4 once at epoch (`check_orbit`); the error is an SGP4 return code, not a rule | no |
| IOV-B020 | validation.py:1064-1075 | ground stations and targets share one id namespace | FILE_FORMAT.md |
| IOV-B021 | link/evaluate.py:244-256 | pattern CSV: UTF-8 (BOM allowed), comma only; semicolon refused; unit tables accept `, ; \t` (inconsistent) | hint text |
| IOV-B022 | model_document.py:491 vs validation.py:1128-1140 | REF_UNKNOWN_SITE rule is implemented twice (editor live check and loader) with different hint wording | no |
| IOV-B023 | errors.py:104-112 | `value_error`/`assertion_error` messages are replaced by a generic "has a value that cannot be used" to avoid quoting the file value; the actual reason is lost | comment only |
| IOV-B024 | problems.py:55-60 | Problems are sorted by file, line, path, code; duplicates are only merged in some modules (`_unique`, `_seen` in link/power), so one cause can print once per location | no |
| IOV-B025 | roundtrip.py:34,58-70 | BOM and CRLF preserved on in-place save; canonical write is LF without BOM (FILE_FORMAT.md line 3 says "LF line endings") | docstring |
| IOV-B026 | project_loader.py:236-244 | arithmetic/recursion errors inside validators are reported as one generic FILE_INVALID "value that cannot be processed" without naming the field | no |
| IOV-B027 | migrations.py:60-86 | chain of migrations is applied step by step; a missing step is an error; there is no downgrade, and no `tool_version` is stored in project files (`ProjectMeta` has only name, revision, description: project.py:22-27), so the writer of a file cannot be identified | FILE_FORMAT.md:205 |

### C. Opaque outputs

| ID | where the user sees it | what is missing |
|---|---|---|
| IOV-C001 | `CONFIG_VALUE_INVALID` (validation.py:257-269) | actual value (by convention), the unit the range is in, why the bound exists (physical meaning or sanity limit), whether it is a hard physical limit or a plausibility guard, route to override; the hint is wrong for non-ratio quantities |
| IOV-C002 | `FIELD_INVALID` from pydantic bounds (errors.py:75) | field's unit of the bound ("greater than or equal to 0" has no unit), reason for the bound, hint addresses units not the rule |
| IOV-C003 | `MASS_LIMIT_EXCEEDED`, `THERMAL_LIMIT_EXCEEDED`, `THERMAL_MARGIN_INSUFFICIENT`, `LINK_NOT_CLOSED` (Problems panel/CLI/report problem table) | the computed value, the limit and the margin (they are in the result tables `LimitCheck`, `UnitLimitCheck`, link rows, but the Problem has only an index like `limits[2]` or "mission phase number 3"; the limit's name is not given) |
| IOV-C004 | `BATTERY_DOD_EXCEEDED`, `BATTERY_DEPLETED`, `ORBIT_BALANCE_NEGATIVE`, `PEAK_POWER_EXCEEDED` (time_domain.py:1138-1160) | worst value (`Violation.extreme`), limit, duration; the Problem shows count and first time only |
| IOV-C005 | `RESULT_INCOMPLETE` / `CONFIG_PLACEHOLDER` (assumptions.py:29-37) | which results become n/a because of this number (the hint says "results that need it show n/a" generically), and in which tables |
| IOV-C006 | `ORBIT_INVALID` (validation.py:1054) | the rule/limit failed (perigee below surface? decay?) — message is "SGP4 cannot propagate this orbit at its epoch (error N)" with the SGP4 internal code, no meaning of N |
| IOV-C007 | `ORBIT_BALANCE_NOT_EVALUATED` (time_domain.py:540-557) | step size, orbit period and the threshold actually used |
| IOV-C008 | `LINK_ATTENUATION_FREQUENCY` (evaluate.py:364-378) | link frequency, entry frequency, ratio vs 1 % |
| IOV-C009 | `YAML_SYNTAX` for limit refusals (yamlio.py:90-109,130-132) | which limit and its value; the hint "Check indentation, colons and quotes" is wrong for size/alias/tag/merge-key refusals |
| IOV-C010 | `FILE_MIGRATED` (migrations.py:89-95) | what changed in the data; for margin_policy the new placeholders |
| IOV-C011 | Silent normalisation on load (B007-B011, A014) | no report that a time, a unit-suffixed string, a key order, a duplicate data rate was altered |

### D. Forced options

| ID | file:line | fixed choice | plausible alternatives |
|---|---|---|---|
| IOV-D001 | validation.py:262 / project_loader.py:512 | plausibility ranges are errors that block the whole project | warning with justification; user-editable bounds in a config file; "accepted by" record |
| IOV-D002 | base.py:141 | placeholder = null value or `TBD` only; a present value with TBD is ignored | "provisional" status that uses the value but flags results; other tokens (TBC, assumed, estimated); source categories (standard, datasheet, test, analysis, assumption) |
| IOV-D003 | base.py:130-141 | single-value `Sourced` (value, source, note) | add date, document id, revision, uncertainty, page/section, owner, approval status |
| IOV-D004 | equipment.py (numbers without source) | unit mass/power/limits are plain floats | `Sourced` or per-unit provenance (D-102 admits the gap) |
| IOV-D005 | problems.py:21-29 | Problem = free text message + hint; severity 3 levels | structured: rule id, rationale, actual, limit, unit, override route, doc link; user-configurable severity |
| IOV-D006 | CLAUDE.md convention; problems.py:3-4; errors.py:3-4; quantity.py:7 | no values read from project files in any message | opt-in value display, redaction level, reference to value (file:line) instead |
| IOV-D007 | yamlio.py:169-204 | YAML only; aliases/anchors/tags/merge refused | allow aliases with expansion limit; other formats (JSON, TOML) |
| IOV-D008 | project_loader.py:114 / yamlio.py:255 | canonical dump without comments for new/whole-file write | comment-preserving always; sidecar notes |
| IOV-D009 | model_document.py:421 | silent canonical fallback | warn/refuse/ask before dropping comments |
| IOV-D010 | environment.py:18, timeutil.py:12 | years 1950-2100; UTC only; Earth-only semi-major axis range | other epochs; other time systems (TAI, UT1, TT); other central bodies |
| IOV-D011 | model Literal fields: config.py:72 (`attenuation_kind`: rain, gas, cloud, scintillation, other), link.py:121 (`direction`), power_system.py:18 (`Pointing`: sun, nadir only), thermal.py:82 (`limit_set`), environment.py:147,177,183 (rule kinds during_pass/in_eclipse/in_sunlight; sources elements/spacemissionstudio; shadow cylindrical/conical) | closed enumerations | inertial/velocity/target pointing; more rule kinds; other shadow models; other environment sources |
| IOV-D012 | versions.py / migrations.py | one linear schema version per kind, in-memory migration, no downgrade | per-file tool version stamp, migration report |

### E. Interfaces (in my area)

| ID | file:line | direction | what / format | user told? | provenance? |
|---|---|---|---|---|---|
| IOV-E001 | project_loader.py:442-470,474-489 | in | `project.yaml`, `spacecraft.yaml`, 8 entity folders `*.yaml`, 8 `config/*.yaml` (UTF-8 YAML, <=1 MB) | docs; FILE_IGNORED warns of skipped lookalikes | none (no hash, no file mtime recorded in results) |
| IOV-E002 | project_loader.py:366,383; :281 | in | directory listings (`os.listdir`, `os.scandir`) to find files, deterministic sort | no | no |
| IOV-E003 | validation.py:735; link/evaluate.py:226-262 | in | antenna `pattern_file` CSV (columns angle_deg, gain_dbi) inside project; `pattern_source` text | docs; hint on error | source string only; no hash |
| IOV-E004 | validation.py:1100; scenario/run.py:86-98 | in | `import_dir` (SpaceMissionStudio files) | docs/ENVIRONMENT_FORMAT.md | none here |
| IOV-E005 | unit_table.py:236-257 | in | unit table CSV (UTF-8-sig) / XLSX (first sheet only, `data_only`, formulas never evaluated) | D-102, "How to use" sheet | none; plan lists old/new values (Change) in the preview |
| IOV-E006 | unit_table.py:76-119 | out | unit table CSV/XLSX template; text defused against formula injection | D-102 | none |
| IOV-E007 | unit_table.py:578-604 | out | in-place edits of `units/*.yaml` through ruamel (comments kept), atomic temp files in the unit folder | confirmation dialog (GUI) | none |
| IOV-E008 | roundtrip.py:223-255; reports/files.py:70-131 | out | in-place save of project files; temp file in same folder then rename; BOM/CRLF/mode kept; symlink written through | partly (`canonical` ignored by GUI) | sha256 stamp used to detect external change (`roundtrip.py:45-55`, `model_document.py:398`), not stored |
| IOV-E009 | project_loader.py:114-137; wizard.py:183; examples.py:1210 | out | `write_project`: whole project in canonical form | yes (new project / examples) | none |
| IOV-E010 | schemas.py:77-83; schemas/*.json (18 files) | out | JSON Schemas per kind, committed in package; `budget export-schemas` | docs | schema_version const; no tool version/hash |
| IOV-E011 | units/quantity.py:115-119 | in | pint `UnitRegistry(cache_folder=None)`: unit definitions from the pint package (no disk cache); the pint version defines every non-log unit conversion | no | pint version not recorded in outputs |
| IOV-E012 | yamlio.py:114-117 | in | ruamel.yaml round-trip parser (YAML 1.2 semantics) | no | version not recorded |
| IOV-E013 | io/errors.py, problems.py:to_dict; reports/common.py:95-120 | out | problem list in reports (severity, code, location, path, message, hint) and JSON | yes | no tool/rule version |
| IOV-E014 | no env var, network or clipboard use in this area (grep) | n/a | | | |

### Requirement 12: enumeration of every Problem code

Legend: Y = stated; P = partly or generically; N = not stated. "actual+limit" = actual value AND limit both present in the message/hint (by convention the actual value is never present; the column notes the limit separately where it is). "resolve/override": hint says how to fix (R) / how to override (O). No code offers an override route (O = N for all; the nearest equivalents are "write TBD" and "change the limit and cite its source", noted).

| code | severity | rule stated? | why stated? | actual+limit values? | how to resolve / override? | where |
|---|---|---|---|---|---|---|
| FILE_INVALID | error | Y (outside project / not regular / too large / not UTF-8 / not a mapping) | P (only "links that lead out are not followed") | N (1,000,000 B limit not shown) | R: P (hint on 2 of 6 variants; none for outside folder, mapping, unprocessable value: generic); O: N | project_loader.py:154,163,172,181,210,239 |
| FILE_NOT_FOUND | error | P | N | N | R: Y; O: N | project_loader.py:186,431 |
| YAML_SYNTAX | error | Y (e.g. "too many lines", "nested too deeply", "anchors not supported") | P (aliases: "write the values out"; others none) | N (limit numbers never shown) | R: P, hint is always "Check indentation, colons and quotes" even for limit/alias errors; O: N | project_loader.py:198; yamlio.py:90-238 |
| KIND_MISMATCH | error | Y | P ("file location decides its kind") | P (expected kind named, actual not) | R: Y; O: N | project_loader.py:217 |
| SCHEMA_VERSION_MISSING | error | Y | N | P (expected version named in hint) | R: Y; O: N | migrations.py:38,55 |
| SCHEMA_TOO_NEW | error | Y | Y | Y (file version and supported version; an integer from the file, the only value-bearing message) | R: Y; O: N | migrations.py:46 |
| SCHEMA_MIGRATION_MISSING | error | Y | N | Y (version numbers) | R: P ("open with an older release"); O: N | migrations.py:67 |
| SCHEMA_MIGRATION_FAILED | error | P | N | P (version) | R: P ("check against documentation"); O: N | migrations.py:81 |
| FILE_MIGRATED | info | Y | P | Y (from/to version) | R: Y (save); O: n/a | migrations.py:91 |
| FIELD_MISSING | error | Y | N | N | R: Y (adds unit); O: N | errors.py:77-81 |
| FIELD_UNKNOWN | error | Y | N | N (allowed fields listed or "did you mean") | R: Y; O: N | errors.py:82-91 |
| FIELD_INVALID | error | Y for pydantic bounds and custom rules; message is pydantic text | N | limit Y for `ge/le/gt/lt` ("greater than or equal to 0"), custom text states rule without numbers; actual N | R: P wrong hint (unit hint, probe); O: N | errors.py:75,114 |
| UNIT_INVALID | error | Y | N | N (canonical unit in hint) | R: Y; O: N | errors.py:92-94 |
| DUPLICATE_NAME | error | Y | P (only in docstring: cannot be told apart in a report) | N | R: P ("Rename one of the entries", entry not named); O: N | errors.py:95-97 |
| SOURCE_MISSING | error | Y | P (hint: "cite the standard") | n/a | R: Y (cite or TBD); O: P (TBD) | errors.py:98-101 |
| ID_INVALID | error | Y | P | N | R: Y; O: N | project_loader.py:304,316 |
| ID_UNUSUAL | warning | Y | Y (hard to type/tell apart) | N | R: Y; O: n/a (loads) | project_loader.py:328 |
| ID_COLLISION | warning | Y | Y (file systems) | N | R: Y | project_loader.py:345 |
| FILE_IGNORED | warning | Y | P | N | R: Y | project_loader.py:361 |
| CONFIG_MISSING | warning | P | N (does not say which results go n/a) | N | R: P ("create it with every number sourced") | project_loader.py:482 |
| REF_UNKNOWN_BUS | error | Y | N | N | R: Y | validation.py:69,140 |
| REF_UNKNOWN_MATURITY | error | Y | N | N | R: Y | validation.py:81,965 |
| REF_UNKNOWN_UNIT | error | Y | N | N | R: Y | validation.py:100 |
| REF_UNKNOWN_UNIT_MODE | error | Y | N | N | R: Y | validation.py:112 |
| UNIT_NOT_MAPPED | error | Y | N | N | R: Y (exact line to add) | validation.py:124 |
| REF_UNKNOWN_PHASE | error | Y | N | N | R: Y | validation.py:883,910,950,997,1012 |
| REF_UNKNOWN_MODE | error | Y | N | N (hint lists defined modes) | R: Y | validation.py:682,860,897,1154 |
| REF_UNKNOWN_STATION | error | Y | N | N (lists defined) | R: Y | validation.py:669 |
| REF_UNKNOWN_ATTENUATION | error | Y | N | N | R: Y | validation.py:697 |
| REF_UNKNOWN_MODULATION | error | Y | N | N | R: Y | validation.py:712 |
| REF_UNKNOWN_CASE | error | Y | N | N | R: Y | validation.py:825 |
| REF_UNKNOWN_ORBIT | error | Y | N | N (lists defined) | R: Y | validation.py:1088 |
| REF_UNKNOWN_SITE | error | Y | N | N | R: Y | validation.py:1120,1133; model_document.py:491 |
| THERMAL_NODE_UNKNOWN | error | Y | N | N | R: Y | validation.py:798,811,843 |
| CONFIG_PLACEHOLDER | warning (UI: Not checked) | Y | P ("results that use it are not trustworthy") | N | R: Y; O: N (a TBD value cannot be used provisionally) | validation.py:175,216,231,246 |
| CONFIG_EMPTY_TABLE | warning | Y | N | N | R: Y | validation.py:189,201 |
| CONFIG_VALUE_INVALID | error | Y (quantity named) | N | limit Y (range, no unit); actual N | R: P (ratio hint for every quantity); O: N | validation.py:263 |
| PHASE_MASS_MISSING | error | Y | N | N | R: Y | validation.py:983 |
| MASS_FRAME_UNDEFINED | warning | Y | P | N | R: Y (example) | validation.py:1028 |
| ORBIT_INVALID | error | P (SGP4 reason text) | N | N (SGP4 internal code) | R: P | validation.py:1054 |
| DUPLICATE_ID | error | Y | N | N | R: Y | validation.py:1068 |
| IMPORT_DIR_MISSING | error | Y | N | N | R: P | validation.py:1106; scenario/run.py:90 |
| LINK_ANTENNA_PATTERN_GROUND | error | Y | P ("ground antenna tracks") | N | R: Y | validation.py:726 |
| LINK_PATTERN_FILE_MISSING | error | Y | N | N | R: P | validation.py:740 |
| SCENARIO_OPTION_IGNORED | warning | Y | Y (user probably expects it to matter) | N | R: Y | validation.py:768 |
| SCENARIO_PHASE_NO_DOD | warning | Y | Y (check not evaluated) | N | R: Y | validation.py:926 |
| IMPORT_FILE_UNREADABLE | error | Y | N | N | R: Y | unit_table.py:149,262 |
| IMPORT_FILE_TOO_LARGE | error | Y | N | N (5 MB, 100,000 rows, 50 columns, 50 MB unpacked not shown) | R: P | unit_table.py:165 |
| IMPORT_COLUMN_IGNORED | warning | Y | N | N | R: Y | unit_table.py:274 |
| IMPORT_COLUMN_MISSING | error | Y | N | N | R: Y | unit_table.py:357 |
| IMPORT_UNKNOWN_UNIT | error | Y | N | N | R: Y | unit_table.py:379 |
| IMPORT_FIELD_MISSING | error | Y | N | N | R: Y | unit_table.py:392,445 |
| IMPORT_DUPLICATE_ROW | error | Y | N | N | R: Y | unit_table.py:405 |
| IMPORT_VALUE_INVALID | error | Y (UnitError text or pydantic text) | N | limit Y when from pydantic; actual N | R: P (hint says "message says what the field requires") | unit_table.py:427,468 |
| RESULT_INCOMPLETE | warning (UI: Not checked) | P (names the number: "X is missing/a placeholder") | P ("results that need it show n/a", not which) | N | R: Y; O: N | assumptions.py:32 (callers: static_budget.py:268-272, static_mass.py:360-365, time_domain.py:206-212,687,782,798,807, static_thermal.py:164-171,252,259,349,430, link/evaluate.py:146-153,304,325,353,520) |
| MASS_LIMIT_EXCEEDED | error | P (a limit exceeded; which is only `limits[i]`) | N | N (values in mass table) | R: Y; "change the limit (cite its source)" is the nearest to an override | static_mass.py:268 |
| MASS_PROPS_MISSING | warning | Y | Y (excluded from CG and inertia, never counted as zero) | N | R: Y | static_mass.py:293 |
| MASS_INERTIA_POINT_MASS | info | Y | P | N | R: N (no hint) | static_mass.py:310 |
| MASS_INERTIA_NOT_SCALED | warning | Y | Y | N (threshold 1e-9 hidden) | R: Y ("remove or accept") | static_mass.py:333 |
| THERMAL_SOLVE_FAILED | error | Y | Y (no path to space) | N | R: Y | static_thermal.py:490 |
| THERMAL_NO_LIMITS | warning (UI: Not checked) | Y | P ("not checked") | N | R: Y | static_thermal.py:556 |
| THERMAL_LIMIT_EXCEEDED | error | Y | N | N (temperature, limit in the case table) | R: P (design or limit) | static_thermal.py:579 |
| THERMAL_MARGIN_INSUFFICIENT | error | Y | P | N | R: P ("margin set in thermal_environment.yaml") | static_thermal.py:594 |
| ORBIT_EPOCH_FAR | warning | Y | Y | limit Y (30 days), actual N | R: Y | elements.py:87 |
| SCENARIO_UNKNOWN | error | Y | N | N | R: Y (lists defined) | scenario/run.py:110 |
| ENV_INPUT_INVALID | error | P (exception text) | N | N | R: P (see docs) | scenario/run.py:127 |
| SCENARIO_TOO_LARGE | error | Y | Y | N | R: Y | scenario/run.py:138 |
| ENV_PROPAGATION_FAILED | error | P | P | limit Y in one variant ("years 1950 to 2100"), actual N | R: P | scenario/run.py:149,161 |
| ORBIT_BALANCE_NOT_EVALUATED | warning | Y | Y | rule Y ("quarter of the period"), values N | R: Y | time_domain.py:542,552 |
| BATTERY_DOD_EXCEEDED | error | Y | P | N (count and first time only; `extreme` in violations table) | R: P; O: N | time_domain.py:1149 |
| BATTERY_DEPLETED | error | Y | Y (demand not supplied) | N | R: P | time_domain.py:1149 |
| ORBIT_BALANCE_NEGATIVE | error | Y | P | N | R: P | time_domain.py:1149 |
| PEAK_POWER_EXCEEDED | error | Y | P | N | R: P | time_domain.py:1149 |
| LINK_INPUT_INVALID | error | Y | N | P (hint gives 0..180 rule, no values) | R: Y | evaluate.py:235,261 |
| LINK_ATTENUATION_FREQUENCY | warning | Y | N | limit Y (1 %), actual N | R: P | evaluate.py:372 |
| LINK_ATTENUATION_DUPLICATE | warning | Y | P (larger loss used) | N | R: Y | evaluate.py:398 |
| LINK_NOT_CLOSED | error | P | N | N (margin/required margin in link table) | R: Y | evaluate.py:588 |
| LINK_NO_STATIC_POINTS | info | Y | Y | N | R: Y | evaluate.py:661 |
| LINK_SITE_NOT_IN_SCENARIO | warning | Y | Y | N | R: Y | evaluate.py:697 |
| LINK_NEVER_ACTIVE | info | Y | Y | N | R: Y | evaluate.py:765 |
| LINK_PER_DAY_NOT_GIVEN | info | Y | Y | N | R: Y | evaluate.py:824 |
| INTERNAL_ERROR | error | N | N | N | R: P (run `budget validate`) | budget_gui/session.py:90 |

Totals (counted from the table): 82 codes. Rule stated: Y 72, P 9, N 1 (INTERNAL_ERROR). Why stated: Y 16, P 20, N 46. Limit number stated: about 8 codes. Actual value: 0 (SCHEMA_TOO_NEW prints the file's schema version integer, the single exception). Resolve hint present for all but MASS_INERTIA_POINT_MASS (and several FILE_INVALID variants); override route for 0.

#### Design question (recorded, not resolved)
CLAUDE.md convention "Problems/messages never contain values read from project files (field names, ids and units only)" (also `problems.py:3-4`, `errors.py:3-4`, `quantity.py:7`, `unit_table.py:12`, user guide chapter 11 line 3, read-and-fix-problems.md:11) conflicts with requirement 12 "actual and limit values". Facts relevant to the decision: (a) limits are constants or configuration, so they were never covered by the convention (already printed in pydantic messages, CONFIG_VALUE_INVALID, ORBIT_EPOCH_FAR); (b) actual values for result findings already appear in tables of the same reports and in the unit-table import preview (`Change.old/new`, unit_table.py:296-304); (c) ids (file names) are already allowed in messages; (d) the convention exists because the spec calls project data possibly sensitive (spec constraint 11, "no project content in logs, temp files, crash dumps"); (e) the loader catches pydantic `value_error` text because it may quote the offending value (`errors.py:104-107`), i.e. suppression is by code design, not by accident.

### Already good

- `Problem` carries file, YAML path and line (`LineMap.lookup` falls back to nearest ancestor), deterministic order, `to_dict` for JSON, and appears with hint in reports (`reports/common.py:95-120`).
- `Sourced` model makes `source` mandatory (SOURCE_MISSING); placeholders produce n/a, never silent 0; INCOMPLETE banner and "Configuration numbers used" table (placeholders-and-sources.md); `Assumption` records name/value/unit/source/file/path/placeholder (`assumptions.py:11-20`).
- Units explicit in field names; strict unit parsing; logarithmic vs linear never implicitly converted; unit label shown in hints.
- Strict model (`extra="forbid"`, `allow_inf_nan=False`) with "did you mean" suggestions.
- Schema versioning with migrations, `FILE_MIGRATED` info, `SCHEMA_TOO_NEW` with both versions; committed JSON schemas checked by test; `schema_version` pinned by `const`.
- Limits are documented (FILE_FORMAT.md:186, D-133) and checked before parsing; paths confined to the project folder (`paths.py`); atomic writes; round-trip edit keeps comments and key order in the normal case (`roundtrip.py`); sha256 stamp detects external edits.
- Unit table import: dry-run plan, "empty cell = unchanged", all-or-nothing apply (D-102).
- Result findings in the power timeline already group by code and case with count, first time and file/path (`violation_problems`), and violations tables hold `extreme`.
- Scenario/severity classes in GUI: "Not checked" separated from warnings (`problem_class.py`), with explanations.

### Notes for the plan

- Structural change needed for requirement 12: `Problem` (frozen dataclass, `problems.py:21`) has no fields for rule id, rationale, actual, limit, unit or override. `to_dict`, `format`, reports (`reports/common.py:95-120`), GUI panel (`problems_panel.py:377-384`), tooltips, CLI and JSON all consume message+hint; adding fields touches all of them. 14 files construct `Problem(` (grep count above) plus `_p`/`_range_problem`/`incomplete`/`_error` helpers: converging on one factory is feasible (validation.py has two).
- Tests and golden files: tests compare generated JSON schemas and examples (`budget export-schemas`, `budget export-examples --force`; "tests fail on drift", CLAUDE.md). Changing model bounds or adding fields (source on unit numbers, override records) requires regenerating schemas/examples, a schema version bump and a migration (CLAUDE.md "Schema changes need a version bump and a migration"; FILE_FORMAT.md). `CURRENT_VERSIONS` and each `model/*.py` default `schema_version` are linked.
- Moving A2 ranges into data (config) would make them visible/editable but they currently live in code and are not in the JSON schemas; moving them must keep the "no invented standards values" rule (`source` field) and the project-level convention that thresholds are not silently supplied by the tool.
- Override design touches the load pipeline: errors currently null the project (`project_loader.py:512`); an override record would have to be validated at load and reported at every output (Problems panel, report banner, provenance). The `Sourced` placeholder logic is duplicated (base.py:141, link.py:42, validation.py:241, evaluate.py pattern_source) so a "provisional/overridden" status must be added in all four, and in the solvers' `get` helpers (power/time_domain.py:195-215, link/evaluate.py:130-160, static_thermal.py:155-175, static_mass.py:355-370, static_budget.py:260-275).
- Byte-identical constraints: `write_project` output is documented as stable bytes ("stable bytes for an unchanged project", project_loader.py:115); `save_edited_data` returns the same bytes when unchanged. Example projects under `examples/` are generated and compared by tests.
- Two exception-clause syntax forms (`except A, B:`) are Python 3.14 only (PEP 758): the repo cannot be imported on 3.13 (the sandbox default python), so tests/probes need 3.14.
- Duplicated rules to unify in any rewrite: MIN/MAX_YEAR (timeutil.py:12, environment.py:18), antenna-pattern 0..180 (link.py:36, evaluate.py:253), REF_UNKNOWN_SITE (validation.py:1128, model_document.py:491), the "TBD" literal (4 places), the 1e-9 family of tolerances (IOV-A040, A044, A045, A046, plus `thermal/static_thermal.py:138` `abs(watts) < 1e-9`).
- Name collision: `SOURCE_MISSING` is both a Problem code (errors.py:99) and the equation-source marker (`equations.py:12`); user docs mention both.
- Docs drift found: FILE_FORMAT.md:186 says anchors are unsupported but a lone anchor loads (probe); FILE_FORMAT.md:203 says JSON schemas carry the limits, true only for the pydantic bounds (A3) and not A2.
- Not run: the pytest suite (py3.14 needed); schema drift between `schemas/*.json` and models not re-verified.

## Appendix E — Project creation and comparison

Paths are relative to `src/budget_core/` unless stated. Line numbers verified with grep/cat -n. Could not execute the code (Python 3.14 environment lacks sgp4 etc.), so statements about written files come from reading code plus the committed `examples/microsat_250kg_eps/` files.

### Summary
- Counts: A = 52 rows, B = 21, C = 8, D = 9, E = 7 (grouped where identical).
- Top gaps:
  1. The default guided sample (`microsat_250kg_eps`) writes ~60 invented numbers into a NEW user project (margins 5/10/20 %, system margin 10 %, converter 0.90, distribution loss 0.03, array/battery/thermal/link values, ground stations, links, scenario rules). They carry `source: "Synthetic example value; not from a data sheet or a standard."` (examples.py:77), which `Sourced.is_placeholder` (model/base.py:139) does NOT treat as a placeholder, so Problems and the INCOMPLETE banner do not flag them (only the TBD mass margin stays open). Nothing in `src` tests for the marker text outside examples.py. The description says "All numbers are invented placeholders" (wizard.py:229) but they are not placeholders in the validator's sense.
  2. Unit-level data in samples (mass_kg, avg/peak power, duty, `heat_dissipation_ratio` 1.0, geometry, inertia, propellant masses, array cell counts, battery series/parallel) are plain floats with NO source field at all (model has no source on Unit/PowerMode); only `Sourced` config numbers carry a (synthetic) source.
  3. "Near-circular" orbit inputs the user never typed: eccentricity 0.001, arg. perigee 90 deg, mean anomaly 0, epoch = scenario start, a = WGS-84 equatorial radius + altitude (wizard.py:34,206-211; new_scenario.py:221-253). Docs state e only partly; mean anomaly/arg perigee/frame are not shown in the forms, and RAAN/inclination do not follow altitude (default 97.6 deg is not recomputed as sun-synchronous when altitude changes).
  4. Time step policy: new scenarios get 10 s, or ceil(duration/8640) s up to a 600 s cap (wizard.py:35-36,133-138; new_scenario.py:35,263). The form/review pages never show the chosen step; a coarse step (600 s from 60 days) means eclipses (~2000 s) are sampled at ~3 points and the orbit energy balance may "silently stop being evaluated" (DECISIONS D-196).
  5. Compare reports only differences "as displayed" (rounded to each column's decimals, or 10 significant digits for general columns), has no tolerance/threshold control, compares report output only (not inputs), silently skips Problems/Provenance/Equations, and `n/a` vs NaN are the same. A real output change below display precision is invisible; the user cannot tell which input change caused an output change. The self-test has no numerical reference values: it only checks existence/format (hidden thresholds 6000 s, 30 s, `IBMPlexSans`, >= 8 chapters).

### A. Constants, defaults, thresholds, rules
| ID | file:line | value | purpose | visible to user? | editable w/o code? | source stated? |
|---|---|---|---|---|---|---|
| BLD-001 | blank.py:32 | `("class_a","class_b","class_c")` | the three maturity classes of a blank project (labels, margins TBD) | yes (create-a-project.md:38; margin_policy.yaml) | yes (rename/add in config file; wizard has no choice of count) | n/a (labels) |
| BLD-002 | blank.py:33,64-71 | bus voltage range 1..1000 V | rejects bus voltage outside range | message only on violation; docs say no default, not the range | no | none |
| BLD-003 | blank.py:34, new_unit.py:24, new_mode.py:108 (4x) | MAX_NAME 120 / MAX_TEXT 120 / description 480 chars | text length limits | message on violation | no | none |
| BLD-004 | blank.py:84,86 ; wizard.py:228 | `revision="1"`; spacecraft name = project name | defaults written | in project.yaml | yes | n/a |
| BLD-005 | blank.py:87,47 | bus name "main"; one bus only | blank project bus | wizard field, docs | yes | n/a |
| BLD-006 | blank.py:91-100 | margin_policy 3 classes x (power, mass) + system power/mass + distribution loss + one converter efficiency, all `Sourced(None,"TBD")` | placeholders (no invented number) | yes: Problems CONFIG_PLACEHOLDER, INCOMPLETE banner | yes | yes: "TBD" + note |
| BLD-007 | blank.py:101-103 | empty Ebn0/attenuation tables, `MassLimits(limits=[])` | no tables | yes CONFIG_EMPTY_TABLE | yes | n/a |
| BLD-008 | blank.py (absent) | `mission_phases` empty -> model treats as one phase "all" (model/equipment.py:145) | blank project has no phases | partly (docs: "no mission phases") | yes | none |
| WIZ-001 | wizard.py:27-31 | three sample ids | catalogue of samples (+ stress_200_units not offered) | yes | no (code) | n/a |
| WIZ-002 | wizard.py:58-63 | defaults: sample=`microsat_250kg_eps`, altitude 550 km, inclination 97.6 deg, RAAN 100 deg, 1 day, start 2026-06-01T00:00:00Z | pre-filled answers; GUI repeats them (budget_gui/guided.py:~120-124) | yes (editable fields) | yes (user types) | none; docs call 550 km "about"; 97.6 deg is not tied to altitude |
| WIZ-003 | wizard.py:37 | altitude 160..2000 km | accepted range (GUI spin allows 0..100000, guided.py:~121) | docs say 160 to 2000 | no | none |
| WIZ-004 | wizard.py:94,98 | inclination 0..180, RAAN 0 <= x < 360 (GUI spin max 359.9) | ranges | message | no | none |
| WIZ-005 | wizard.py:38,101 | MAX_DAYS 180 | max scenario length; "under a minute" (machine dependent, D-196) | yes (docs) | no | DECISIONS D-196 only; GUI spin allows 1000 days then refuses |
| WIZ-006 | wizard.py:35,133-138 | MAX_STEPS 8640 | step = max(sample step, ceil(duration/8640)) | docs scenarios.md:9 ; NOT shown on wizard Review page | yes in scenario file afterwards | D-196 |
| WIZ-007 | wizard.py:36 | MAX_STEP_S 600 s cap | cap of step coarsening | docs scenarios.md:9 | file | D-196 ("quarter period ~1300 s") |
| WIZ-008 | wizard.py:34 ; new_scenario.py:221 | eccentricity 0.001 | "near circular" | docs (scenarios.md:9,22) ; not on wizard pages | yes in orbit file | "as in the sample orbits" |
| WIZ-009 | wizard.py:210 ; new_scenario.py:222 | arg_perigee 90 deg | near-circular orbit start phase | scenarios.md:25 (example yaml only) | yes in orbit file | none |
| WIZ-010 | wizard.py:211 ; new_scenario.py:253 | mean_anomaly 0 deg | start at perigee (= arg. of latitude 90 deg, i.e. northernmost point, not the ascending node) | only implied ("scenario starts at perigee" for ellipse) | yes in file | none |
| WIZ-011 | wizard.py:205,206 ; new_scenario.py:220,231,235 | epoch = scenario start; a = EARTH_RADIUS(WGS-84 equatorial 6378137 m via sgp4 wgs84) + altitude | altitude converted to semi-major axis (so "altitude" = a - R_eq, not geodetic height; perigee altitude of a e=0.001 orbit is ~7 km lower than typed) | not stated | no | constants.py:23 cites WGS 84 |
| WIZ-012 | wizard.py:219,226-230 ; new_scenario (name from user) | scenario name "First scenario (guided mode)"; revision "1"; description text | metadata | yes | yes | n/a |
| WIZ-013 | wizard.py:39,141-150 ; 40-42 | MAX_SLUG 60; ASCII folding (non-ASCII letters dropped: "Ørsted" -> "rsted", CJK -> "project"); Windows device names prefixed | folder name | folder shown on Review | no | none |
| WIZ-014 | wizard.py:66-71 | start text: naive time = UTC, offset converted to UTC; `Z` accepted | UTC interpretation | message "such as ...Z" | no | none (new_scenario.py comment in D-189 says "offset refused" -- contradicts: wizard converts) |
| WIZ-015 | wizard.py:101,128 vs new_scenario.py:203 ; timeutil.py:12-13 | years 1950..2100; message in new_scenario hard-codes "year 2101" instead of MAX_YEAR+1 | date range | message | no | none |
| SMP-001 | examples.py:155 | margins `class_a 0.05, class_b 0.10, class_c 0.20`; `system_power_margin_ratio 0.10` (165) | power margin policy written into new projects from `microsat_250kg_eps` | yes (config + Assumptions) | yes | source = SYNTH_VALUE (not TBD, so not flagged) |
| SMP-002 | examples.py:169-170 | distribution_loss 0.03; converter efficiency 0.90 per bus | power config | yes | yes | SYNTH_VALUE |
| SMP-003 | examples.py:99-138 | design life 5 yr; irradiance 1360; cell area 0.003 m2; eta 0.29; T_ref 301 K; T_cell 318 K; temp coeff -0.0020 /K; packing 0.03; harness 0.02; degradation 0.03/yr; cell 3.0 Ah, 3.6 V; 8s4p (plain ints, no source); charge/discharge eff 0.95; fade 0.03; SOC0 0.9; DoD max 0.3 in every phase; sun direction [1,0,0]; peak limit 180 W (88) | power system | yes | yes | SYNTH_VALUE except cells_in_series/parallel, faces strings/cells (plain), sun_direction, attitude |
| SMP-004 | examples.py:133-137, 1015-1019 | attitude default `sun`; downlink/imaging/nominal `nadir` | pointing assumption | in power_system.yaml | yes | none |
| SMP-005 | examples.py:803-821, 781, 785, 793-794 | space 3.0 K; temperature margin 5.0 K; cold: S=0, albedo 0, IR 240; hot: S=1400, albedo 0.3, IR 240; conductance 0.5 W/K; emissivity 0.85; absorptivity 0.6; exposure (0.5,0.3)/(0.0,0.8); one node per subsystem in an alphabetical chain; one panel per node (area 0.5 m2 for 250 kg) | thermal model | yes | yes | SYNTH_VALUE; the chain topology and exposure fractions are design inputs with no source |
| SMP-006 | examples.py:861-870, 877-919, 929-949 | TX 5/10 W, line loss 0.5 dB, gain 3.0 dBi or 3-point pattern, G/T 10/20 dB/K, required margin 3.0 dB, pointing 1.0, polarisation loss 0.5, implementation 1.0 dB, RHCP hard-coded (861,863); freq 2.2/8.2 GHz; rates; QPSK rate 1/2 Eb/N0 4.0 dB, uncoded 10.0 dB; gas 0.2/0.5 dB; rain 3.0/1.0/0.4 dB at 5/20/90 deg | links + tables | yes | yes | SYNTH_VALUE (frequencies, rates, modulation, ranges of static points are plain) |
| SMP-007 | examples.py:213-226 | heat dissipation 0.7/0.7/0.5 for radios; 1.0 for all other modes (248); temp limits 233.15/343.15/218.15/358.15 K, radio upper 332.15 K | thermal inputs; comment claims "node reaches about 329 K" (223) - stale-risk narrative | in unit files | yes | none (plain floats) |
| SMP-008 | examples.py:273-703, 471-489, 707-726 | ~35 unit rows: mass, avg/peak W, duty, bus, maturity, geometry; sums "to 250 kg at launch with 5 kg propellant" | unit data | yes | yes | none; no source field exists |
| SMP-009 | examples.py:192-199 | uniform-box inertia, rounded to 6 dp | inertia of every unit with dims | no formula in UI; comment only | file | "textbook formula" comment |
| SMP-010 | examples.py:728, 731-767 | phases launch/bol/eol; orbit a=6928137 m e=0.001 i=97.6 RAAN 100; stations at 67N 20E and 45S 170E, min elev 5/10 deg; target 40N 100W min elev 45 deg | the wizard keeps stations/targets/phases from the sample | yes | yes | "invented round numbers" (comment) |
| SMP-011 | examples.py:960-966, 1035-1041, 1089 | propellant 9/8.5/0.8 kg or 5/4.8/0.6; scenario `mission_phase="eol"` (complete only) | expendable + battery DoD phase | yes | yes | none |
| SMP-012 | examples.py:993-1010, 1079-1098 | scenario rules (in_eclipse->nominal; during_pass imaging lead 30 s; downlink), default_mode, segment 0..1800 s safe, shadow model `conical` (150 kg, stress) vs model default `cylindrical` (250 kg) | scenario logic inherited by wizard projects (wizard.py:213-225 keeps all but orbit/start/duration/step) | yes in scenario file; wizard does not say which shadow model the user got | yes | none |
| NEW-001 | new_unit.py:25,23 | id regex `[A-Za-z0-9][A-Za-z0-9_-]*`, 60 chars; collision by NFC+casefold (reports/files.py:48) | id rules | message | no | "what the loader takes without a warning" |
| NEW-002 | new_unit.py:137-143 + model/equipment.py:25,28 | new PowerMode gets duty_cycle 1.0 (written), heat_dissipation_ratio None (omitted -> thermal n/a, D-037), min/max duration None | unit defaults | duty in file; none in the form | yes | D-024/D-037 |
| NEW-003 | new_unit.py:105-121 | mass >= 0, powers >= 0, peak >= avg; no upper bounds | validation | message | no | none |
| NEW-004 | budget_gui/model_pages.py:~147-149 | new unit is put into EVERY spacecraft mode in the power mode just typed (incl. `off`/`survival`/`safe`) | keeps loader valid (UNIT_NOT_MAPPED) | status line after add | yes (modes/ files) | D-187 |
| NEW-005 | new_mode.py:25,45-68 | new mode: copy of another mode, else each unit's mode named "off" (case-insensitive), else first power mode | mode defaults | caller told which units fell back | yes | none |
| NEW-006 | new_scenario.py:35-36,72 | MIN_STEP_S 10; APOGEE 160..40000 km; apogee >= perigee | ellipse limits | messages | no | comment "Molniya or GTO" |
| NEW-007 | new_scenario.py:229-236 | e = (ra-rp)/(2R+rp+ra) with R = WGS-84 equatorial; a = R + (rp+ra)/2; start at perigee | ellipse maths | description text | no | none |
| NEW-008 | new_scenario.py:257-263 | `environment_source="elements"`; shadow_model default **cylindrical** (model default, not stated); no sites/rules; segments none | scenario defaults | cylindrical not stated in form or description | yes (editor) | none |
| NEW-009 | new_site.py:39-41 | lat +-90, lon +-180, alt -1000..100000 m, min elevation 0 <= x < 90 | site ranges; no default for elevation | message | no | "as the model takes it" |
| NEW-010 | new_expendable.py:51-109 | every mission phase needs a mass >= 0; position optional (all three or none); absent position -> mass counted, not in CoM | rules | docstring | no | none |
| NEW-011 | remove_item.py:1-60 | removal blocked when referenced by scenario/link | rule | message names ids | no | D-201 |
| CMP-001 | compare.py:41 ; compare_run.py:110 ; budget_cli/main.py:260 | default max 200 listed differences per budget (duplicated literal) | display cap | yes (stated, CSV/JSON complete) | yes (`--max-rows`; GUI: no control found) | none |
| CMP-002 | compare.py:39-40 | skipped: sections "Problems","Provenance"; table "Equations" | what is not compared | docs compare.md:57 | no | none |
| CMP-003 | compare.py:147-148 | "changed" iff displayed text differs; display = per-column `decimals` (half-up decimal rounding, numfmt.py) or 10 significant digits for `decimals<0` (numfmt.py:17,76-81); percent columns use decimals-2 (document.py:85) | change threshold = display rounding; no absolute/relative tolerance option | docs compare.md:51 ; per-column decimals not shown | no | none |
| CMP-004 | compare.py:133-142 ; numfmt.py:32-37 | percent change to 1 decimal (hard-coded), blank when A == 0; percent-kind change in "pp" with 2 extra scale | change formatting | partly | no | none |
| CMP-005 | compare.py:105-107,182-183 | key columns = table.key_columns else column 0; if the two tables disagree on key header names, fall back to column 0; duplicate keys paired by order with " #n" | row pairing | docs compare.md:52 (fallback not documented) | no (declared in report builders) | none |
| CMP-006 | compare.py:122-130,160-172 | tables matched by (section title, table title); duplicate titles/headers suffixed " #n" | matching | docs | no | none |
| CMP-007 | compare_run.py:26-28,70-74 | static kinds (power, mass, thermal, link) compared only when projects differ (`same_project` False); scenario kinds (timeline, link-passes) only when both sides have a scenario | default kind set | docs compare.md:22,32 | `--budget` | none |
| CMP-008 | compare_run.py:94,99 | scenario reports built with `plots=False`; link/timeline `[]` empty problems list passed | what is compared | not stated | no | none |
| CMP-009 | compare_run.py:77-100 | when a side has no links / no scenario the kind is "not compared" with a note | missing data policy | note printed | no | none |
| SLF-001 | selftest.py:31 | `parse_quantity("2.2 GHz","freq_hz")` must equal 2.2e9 within 1.0 Hz | unit parsing check | no | no | none |
| SLF-002 | selftest.py:33,39-44 | orbit of `microsat_250kg`, grid 6000 s at 30 s, shadow "cylindrical", expects >= 1 eclipse | propagation check (existence only; 6000 s ~ 1 orbit at 550 km) | no | no | none |
| SLF-003 | selftest.py:54 | PDF must contain bytes `IBMPlexSans` | bundled-font check; couples to the exported-file font (CLAUDE.md: Plex only for exported files) | no | no | none |
| SLF-004 | selftest.py:93,126-136 | link rows >= 2 and `cn0_dbhz` not None, rates present; time-domain `energy_wh` not None; thermal cases complete; chapters >= 8; HTML contains "Equations and sources" | structure checks | no | no | none |
| SLF-005 | selftest.py:127-129 | one_day scenario overridden to duration 6000 s / step 30 s | time-domain check | no | no | none |

### B. Hidden assumptions
| ID | file:line | assumption/behaviour | documented where? |
|---|---|---|---|
| B-001 | examples.py:77 ; model/base.py:131-141 | A number whose source is any non-TBD text, even "Synthetic example value", is a normal sourced number: no Problems entry, no INCOMPLETE banner. A new user project from the default sample therefore looks complete in power/thermal/link. | wizard note guided.py:~55 and create-a-project.md:17 say "invented"; validator does not know |
| B-002 | wizard.py:213-225 | Wizard keeps everything of the sample except orbit, start, duration, step, name: stations, targets, links, rules, shadow model, mission_phase, segments (the 150 kg sample's 0-1800 s "safe" segment forces the minimum scenario length, wizard.py:73-80) | partly (error message when too short) |
| B-003 | wizard.py:66-71 | start text without zone is taken as UTC; with zone converted | message gives example only |
| B-004 | wizard.py:196-206 | altitude is measured from the WGS-84 equatorial radius, not mean/geodetic; mean elements fed to SGP4 without drag (model/environment.py:64 "DEVIATIONS DV-E2") | DEVIATIONS DV-E2 (not in the form) |
| B-005 | wizard.py:210-211 | near-circular orbits start at argument of latitude 90 deg (northernmost point); with RAAN and start epoch this fixes the initial eclipse/pass phase and local time of ascending node (LTAN), none of which the user states | scenarios.md:22-25 example yaml only |
| B-006 | wizard.py:133-138 ; new_scenario.py:263 | step silently coarsened for long scenarios; coarse steps degrade eclipse/pass resolution, and the orbit energy balance may stop being evaluated | DECISIONS D-196, scenarios.md:9 (not on the form/review page) |
| B-007 | model/environment.py:15-17,218 | scenario sample limit 1,000,000 counted at min(step, 20 s) detection grid; passes/eclipses detected on a 20 s grid regardless of step | scenarios.md:71 |
| B-008 | new_scenario.py:259-262 | new scenario uses the model default `cylindrical` shadow, the sample scenarios use `conical`: two creation paths, different physics, neither stated | scenarios.md:63 describes the field; not the creation default |
| B-009 | new_unit.py:137-143 | heat_dissipation_ratio left unset -> thermal results needing it are n/a; samples set 1.0 explicitly (examples.py:248) so sample thermal results exist where a user-added unit gives n/a | D-037 (model comment) |
| B-010 | model_pages.py:~147-149 | new unit joins every spacecraft mode in the typed power mode, so it draws power in `off`/`safe` until edited | message after add; D-187 |
| B-011 | new_mode.py:45-68 | "off" matched case-insensitively by name only; units without an `off` start in their first power mode | caller message lists them |
| B-012 | new_unit.py:75 ; new_*.py | id uniqueness by NFC + casefold (Windows-style) on every platform | message |
| B-013 | wizard.py:141-150 | folder name ASCII-folded, non-Latin names lose characters; fallback "project" | none |
| B-014 | wizard.py:164-190 | on write failure the folder is removed (`shutil.rmtree`); an existing folder is never touched; errors are generic ("check dates, length, orbit") and hide the real cause | docstring |
| B-015 | blank.py:98-100 | the converter efficiency table is keyed by the single bus name; extra buses must be added by hand; classes are exactly three | create-a-project.md:38 |
| B-016 | compare.py:147-157 | `None` and non-finite values both display as `n/a`, so n/a -> NaN is "no difference"; text cells compared as strings; bool cells fall through to string compare | none |
| B-017 | compare.py:101-102,154 | numeric change computed from exact values only if both cells are numbers; the percentage uses \|A\| and is blank when A = 0 | compare.md:53 partly |
| B-018 | compare.py:182-183 | if the two tables' key header sets differ, the pairing silently falls back to the first column (can produce spurious added/removed rows) | none |
| B-019 | compare.py:264-282 | `compared` counts only shared-column value cells in matched rows; added/removed rows, one-sided columns are not in the denominator | summary text compare.md:54 |
| B-020 | compare_run.py:118-123 | provenance of both sides built with the same user/generated_at; scenario kinds run the full scenario on both sides (cost ~ 2 runs) | none |
| B-021 | selftest.py:62-63 | any exception becomes `<ExceptionType> during the self-test` (no message, no location; by design "never file content") | getting-started.md:70 |

### C. Outputs without a visible derivation
| ID | where the user sees it | what is missing |
|---|---|---|
| C-001 | Compare report/window: status `changed` and the +/- change | the tolerance (display precision of the column), which input changed, the exact A/B values (only displayed text is shown in the report; exact values appear only through the change string), tool/hash of each side beyond name+revision+scenario |
| C-002 | Compare summary line "N value(s) differ out of M compared" | M excludes one-sided rows/columns; no per-section totals of unchanged vs. skipped tables (Problems/Provenance/Equations skipped silently except in docs) |
| C-003 | Compare never says whether the two sides were built with the same config (margin policy etc.) | no input-diff section (e.g. which Sourced values or sources changed); only derived tables |
| C-004 | Wizard Review page (guided.py:~325-345) | lists name, folder, sample text, orbit, scenario; omits eccentricity, arg. perigee, mean anomaly, step, shadow model, stations/links/margins that come with the sample, and the fact that the numbers have non-TBD "Synthetic" sources |
| C-005 | Add-scenario form/description | the near-circular description (new_scenario.py:223-226) states e but not arg. perigee 90, mean anomaly 0, cylindrical shadow, step choice |
| C-006 | New project opened in the window | Problems panel does not list the synthetic numbers (not placeholders) so the user cannot see which ~60 numbers are invented without reading Assumptions text |
| C-007 | Self-test "Self-test passed." | no list of checks run, no values, no reference comparison; a numerically wrong but renderable build passes |
| C-008 | "Starts at perigee" / altitude in orbit name `"550 km, 97.6 deg inclination"` (wizard.py:~203) | name uses typed altitude but a = R_eq + alt with e=0.001, so true perigee/apogee differ |

### D. Forced options
| ID | file:line | the fixed choice | plausible alternatives |
|---|---|---|---|
| D-001 | wizard.py:27-31 | only three sample spacecraft (250 kg/150 kg class) to start from; no choice of class count/margin set | start from user catalogue/template project, choose number and names of maturity classes (blank.py:32 fixed three) |
| D-002 | wizard.py:154,205-211 | circular-ish orbit: e 0.001, arg perigee 90, M0 0, mean elements | TLE, sun-synchronous helper (inclination from altitude), LTAN input, eccentricity/true anomaly input, J2/drag |
| D-003 | wizard.py:133-138 | step = max(10 s, ceil(duration/8640)), cap 600 s | user-chosen step; accuracy target (e.g. max eclipse timing error) |
| D-004 | wizard.py:101,38 | scenario up to 180 days | user limit with run-time estimate; > 230 d needs sample limit change |
| D-005 | new_scenario.py:259 | cylindrical shadow on creation | conical default, user choice at creation |
| D-006 | blank.py:98-100 | one converter efficiency per bus, scalar distribution loss | per-converter/curve efficiency, load-dependent |
| D-007 | compare.py:147 | "as displayed" equality; no numeric tolerance | absolute/relative tolerances per quantity, significance threshold, show unchanged, input diff |
| D-008 | compare_run.py:26-28 | fixed set of 6 compared report kinds | compare custom tables, mass-property, config-only diff |
| D-009 | new_unit.py:25 | id charset fixed ASCII | free names with slug mapping |

### E. Interfaces
| ID | file:line | direction | what/format | user told? | provenance? |
|---|---|---|---|---|---|
| E-001 | wizard.py:164-190 (write_new_project), 193-238 (`_build`) | out | new project folder of YAML files (via `write_project`) with `schema_version`/`kind` | yes (folder shown) | `project.yaml` description says guided sample; no generator version/timestamp/sample id field (sample id only in description text) |
| E-002 | blank.py:108-120 ; budget_cli/main.py:~728 | out | blank project folder | yes | description only |
| E-003 | examples.py:1191-1211 | out | `budget export-examples`: all four examples; `--force` overwrites example files | yes (refusal text) | none; committed copies in `examples/` must stay in sync (tests fail on drift - CLAUDE.md) |
| E-004 | new_unit/new_scenario/new_site/new_expendable `*_data` | out | plain dicts written by the window as `units/<id>.yaml`, `orbits/<id>.yaml`+`scenarios/<id>.yaml`, ... | yes | none; no "created by form" marker or time |
| E-005 | compare.py:294-346,472 | out | `compare_differences.csv` (columns CSV_HEADER), JSON (sorted keys), XLSX/PDF/DOCX | yes | provenance of side A project only (compare_run.py:131-132); side B provenance in each ComparisonResult, JSON `provenance` is one provenance (A) |
| E-006 | compare_run.py:77-100 | in | both projects loaded from folders (git worktree/old copy) | yes | revision label only; no file hash of side B shown in the report summary table (only name/revision/scenario rows, compare.py:434-438) |
| E-007 | selftest.py:156-198 | in/out | reads only bundled fonts/guide assets, writes nothing (in-memory) | yes (getting-started.md:70) | none |

### Already good
- `source: TBD` placeholder convention plus INCOMPLETE banner for blank projects; blank project invents no number and the bus voltage has no default (D-185, blank.py:1-8).
- All `new_*` forms refuse missing numbers instead of defaulting to 0, and messages never echo user values (new_unit.py:1-6).
- Samples label their numbers with an explicit synthetic source string (examples.py:77) and `Assumptions` tables list value + source + file + path.
- Compare never drops rows silently (truncation counted and stated; CSV/JSON complete), shows one-sided sections/tables/columns, pairs rows by declared key columns, computes change/percentage from exact decimal values, and states the "as displayed" rule in the report summary (compare.py:428) and docs.
- Decisions D-185..D-201 and docs/user-manual/scenarios.md document the step policy, 180-day limit, eccentricity/arg perigee and apogee limits.
- Wizard Review page and `DESCRIPTION` strings state that the project is a sample/blank.

### Notes for the plan
- Samples are generated by code (examples.py) and committed under `examples/`; tests fail on drift (`budget export-examples examples --force`). Any change to default sample numbers, sources or new fields (e.g. a stronger "synthetic" flag) changes golden files, docs figures (compare.md output counts 218/544 etc., create-a-project.md) and probably report goldens.
- `Sourced.is_placeholder` is shared by power/mass/thermal/link/validation (6+ modules): flagging "synthetic" sources would change INCOMPLETE banners and Problems for every example and test; needs a distinct status (e.g. "illustrative") rather than reusing TBD.
- Unit/PowerMode numbers have no source field; adding one needs a schema version bump and migration (CLAUDE.md), and affects the project file format, schemas export and all example files.
- `compare` works on rendered `ReportDocument` cells: any tolerance feature must live between `format_cell` and the report column definitions (`Column.decimals` set in each report builder); per-column decimals change compare results retroactively.
- Duplicated literals: 200 max rows (compare.py:41, compare_run.py:110, CLI), 180 days / 8640 / 600 / 0.001 shared via wizard.py imported by new_scenario.py (single source), but "year 2101" and GUI spin ranges (guided.py:~120-124) are separate literals.
- GUI-side defaults (guided.py) duplicate WizardAnswers defaults; the GUI package is out of this area's file list but is where the user actually sees the forms (pixel rules in `budget_gui/theme` only; text/ranges are not theme-restricted).
- Python 3.14 syntax (`except A, B:`) in sources means tooling here must run under 3.14 with deps; not a plan issue but affects automated checks.

## Appendix F — Reports, plots, provenance, command line and guide generation

Paths are relative to `src/` unless they start with `docs/` or `tests/`. Line numbers were verified with grep or sed by the auditing agent, who also ran `validate`, `run`, `power-timeline` and `link-passes` on `examples/microsat_150kg` with SOURCE_DATE_EPOCH=1767323045 and BUDGET_USER=audit and opened the resulting XLSX, JSON and CSV files. The example projects are all placeholders, so their outputs are mostly `n/a`.

### Summary

Counts: A 46, B 18, C 22 plus a format matrix, D 12, E 22.

Top gaps:

1. **The provenance block has no input fingerprint.**
   - It holds only: tool, tool version, Python, 9 library versions, project name, project revision, scenario id, UTC time, OS user (`provenance.py:38-61`).
   - It has no project hash, no per-file hash, no file list, no config hash, no git commit. `revision` is hand-maintained (`docs/user-manual/reports-and-exports.md:44`), and nothing warns if inputs change while it stays the same.
   - The only SHA-256 uses are `scenario/run.py:204` and `io/roundtrip.py:46`. They are an in-memory cache key and editor change detection, never exported.
   - The `scenario/run.py` key hashes imported CSVs by name, size and mtime (`:202`), not by content.
2. **A colleague cannot reproduce or verify a result from an export alone.**
   - Reports carry only `Sourced` numbers (config, link, mass limits, thermal, power system). They carry no orbit elements, station coordinates, scenario timeline or rules, mode definitions, or unit/mass/position inputs.
   - Unit, mass, orbit and station numbers have no `source` field in the model.
   - XLSX, PDF and DOCX drop each number's `file` and `path` (`reports/common.py:77`); only JSON has them. `Sourced.note` is dropped everywhere (`assumptions.py:11-20`).
3. **Equations are not tied to outputs, and 37 of 40 are SOURCE_MISSING.**
   - Every report appends all equations of its prefix, used or not (`reports/common.py:87`). No column, row or JSON key names an equation id. JSON and CSV carry no equations.
   - Only ENV-GMST, ENV-GEODETIC and TH-SB have sources.
   - Constants (c, k_B, Earth radius, mu, flattening, solar radius, AU) appear only in the guide's last chapter (`guide/build.py:107-135`). They appear in no report, JSON or CSV.
4. **Intermediate values are mostly absent.**
   - Link: EIRP is shown but not its parts. "Other losses" is a single sum.
   - Time-domain power: no per-step k_T, k_age, cos θ or per-face power.
   - Static power: no converter or distribution loss in W.
   - Thermal: the network and solver are not shown.
5. **Rounding and units are inconsistent across formats.**
   - XLSX stores full doubles with a display format. PDF and DOCX show rounded text only.
   - Static CSVs use full `repr`. Link and timeline CSVs use fixed 6 dp (3 for elevation and range, 1 for frequency).
   - The scenario JSON is rounded to 3, 4 or 6 dp (`scenario/export.py:110-138`).
   - `Column.unit` is never rendered (grep). Units exist only as header text.

Also:
- The OS login name is written into every file, including document author properties.
- There is no documented Python API. `budget_core/__init__.py` exports only `APP_NAME` and `__version__`.
- The CLI has no override mechanism.
- There is no standalone plot export. Plots exist only as PNG pictures embedded in XLSX, PDF and DOCX.

### A. Constants, defaults, thresholds, rules

Columns: ID | file:line | value | purpose | visible? | editable w/o code? | source stated?

| ID | file:line | value | purpose | visible? | editable? | source? |
|---|---|---|---|---|---|---|
| RPT-A001 | reports/numfmt.py:17 | `GENERAL_DIGITS=10` (guide uses `.10g` at guide/build.py:109,115,121,167) | Significant digits of "general" columns | Documented (reports-and-exports.md:55) | No | No |
| RPT-A002 | numfmt.py:16 | Decimal `prec=450`, `ROUND_HALF_UP` | Rounding rule for all formatted numbers | Documented (:54) | No | Rationale in docstring (matches spreadsheet display) |
| RPT-A003 | document.py:23 | `Column.decimals=3` default | Displayed precision | Output only | No | No |
| RPT-A003a | power_report.py:12,18,63,122; mass_report.py:192,196,227,289,321,339-341 | W 3 dp, duty 2 dp, margin % 1 dp, converter efficiency 3 dp; kg 3 dp, m 4 dp, CG coverage % 1 dp, inertia 5 dp | Per-table decimals | Output only | No | No |
| RPT-A003b | thermal_report.py:43,77,133; link_report.py:25-46,99,136,155 | Dissipation ratio 2 dp, temperatures 2 dp, dB 2 dp, elevation and range 1 dp, rates 3 dp, Mbit 2 dp | Same | Output only | No | No |
| RPT-A003c | timeline_report.py:97,111-115,140-144,187-189 | Case values 3 dp, times 1 dp, violation worst value and limit 4 dp | Same | Output only | No | No |
| RPT-A004 | document.py:85 | Percent column shows `decimals-2` places | Display | Output only | No | No |
| RPT-A005 | document.py:13 | `NA="n/a"` for None and non-finite values (never 0) | Missing-data marker | Documented (:54) | No | n/a |
| RPT-A006 | common.py:14-17 | `BANNER` text, a binary verdict. Triggers on any placeholder (power, mass, timeline) or any n/a result (thermal, link) | Only completeness verdict. Gives no list of affected results | Yes | No | No |
| RPT-A007 | common.py:21,28 | Sheet name max 31 characters; reserved "history" | XLSX sheet names | No | No | Excel limit |
| RPT-A008 | xlsx.py:30,31,32,33,34,97 | Font IBM Plex Sans, fill E0E0E0, figure 1100 px, row 20 px, cell cap 32000 characters, banner DA1E28 | Layout. Text over the cap is truncated with a note (:80-86) | Cap documented | No | Excel limit |
| RPT-A009 | pdf.py:50,51,241,247-248 | Cell cap 400 characters (60 on retry), A4 landscape, margin 12 mm | Layout. Truncation with note | Cap documented | No | No |
| RPT-A010 | docx.py:35,39,186 | A4 landscape, margin 12 mm, 8 pt, IBM Plex Sans | Layout | No | No | No |
| RPT-A011 | files.py:19,21 | `MAX_NAME=120` bytes; charset `[\w.\-]` | File name sanitising | Documented (:50) | No | No |
| RPT-A012 | files.py:108 | Temp file `.{name}.{pid}.tmp` in the output folder | Atomic write | Documented | No | n/a |
| RPT-A013 | run.py:48 | `REPORT_KINDS` = xlsx, pdf, docx, json, csv | Fixed format catalogue | Yes | No | n/a |
| RPT-A014 | export.py:19-31,60-72,93-100,121-132 | Fixed CSV column sets for power, mass, thermal | What is exported | In the files | No | No |
| RPT-A015 | export.py:109-110 | CSV floats via `repr` (full precision) | CSV precision | Partly (:56) | No | No |
| RPT-A016 | link_export.py:37,69-71,123,129; timeline_export.py:55 | 6 dp; elevation and range 3 dp; frequency 1 dp; values below 5e-7 written as 0 | CSV precision and clipping | 6 dp documented; 3 dp, 1 dp and the 5e-7 clip are not | No | No |
| RPT-A017 | scenario/export.py:22-24,110-138 | Times 3 dp, max elevation 4 dp, eclipse fraction 6 dp | Precision loss in scenario JSON and CSV | No | No | No |
| RPT-A018 | csvutil.py:14,20-25 | Leading apostrophe on formula-like text | CSV injection guard. Alters project strings | Documented (:60) | No | No |
| RPT-A019 | thermal_report.py:12 | `273.15` (misnamed `ABSOLUTE_ZERO_OFFSET_K`) | K to °C display | Output only | No | No |
| RPT-A020 | thermal_report.py:111 | Imbalance below 1e-6 W printed as "below 0.000001 W" | Solver residual display | In note | No | No |
| RPT-A021 | link_report.py:125,127,144 | bits/1e6 = Mbit, bits/8e6 = MByte (decimal), per day = total scaled to 86 400 s | Volume units. Linear scaling if the scenario is not 24 h | Note mentions 86 400 s | No | No |
| RPT-A022 | link_report.py:54,76 | ×1/1000 (m to km, bps to kbit/s) | Unit scaling | Header text | No | n/a |
| RPT-A023 | timeline_report.py:48 | Eclipse fraction `:.2f` % | Display | Yes | No | No |
| RPT-A024 | timeline_report.py:52 | BOL and EOL definition is fixed prose | Meaning of the two cases | Yes | No | No |
| RPT-A025 | provenance.py:25-35 | `LIBRARIES` (9) | The only environment fingerprint | Yes | No | A test keeps it in step with pyproject |
| RPT-A026 | provenance.py:118 | Default scenario "static (no scenario)" | Static budgets carry no scenario | Yes | No | n/a |
| RPT-A027 | provenance.py:68,113 | Missing library or user becomes "unknown" | Silent fallback | Yes | No | n/a |
| RPT-A028 | provenance.py:81,101 | Time truncated to whole seconds, UTC | Resolution | Yes | `--date` / SOURCE_DATE_EPOCH | n/a |
| RPT-A029 | timeutil.py:12-13 (used at cli/main.py:69, provenance.py:96) | Years 1950 to 2100 | `--date` and SOURCE_DATE_EPOCH range | Documented (command-line.md:34) | No | No |
| RPT-A030 | zipnorm.py:8,14,19-20 | Fixed zip time 1980-01-01, deflate level 9, mode 0644, sorted entries | Byte-identical XLSX and DOCX | Docstring | No | n/a |
| RPT-A031 | xlsx.py:134-140; docx.py:216-231; pdf.py:154,257-261 | Doc properties set to the provenance time and user. DOCX revision=1; comments, keywords and category are empty | Metadata | No | No | n/a |
| RPT-A032 | plots/render.py:32-36,104 | SCALE 2, WIDTH 1400, panel height 260, margins 96/24/56/64, gap 36, PNG compress 6, LANCZOS | Plot geometry | No | No | No |
| RPT-A033 | render.py:188,200; spec.py:131 | Buckets = max(width/2, 50); min/max decimation; line 1.6 px | Zoomed-out series are reduced to min and max per bucket | Docstring (spec.py:2-4) | No | No |
| RPT-A034 | spec.py:18-26; plots/link.py:13-26 | Fixed Carbon palette; band colours cycle after 5; rate colours cycle after 12 | Colours repeat | No | No | No |
| RPT-A035 | spec.py:73-81 | Time axis switches unit at 600 s, 3 h, 3 d | Axis | Axis label | No | No |
| RPT-A036 | spec.py:84,216; render.py:160,165 | Nice ticks, 5 y and 8 x target, pad 6 %, min span 1e-12 | Axis scaling | No | No | No |
| RPT-A037 | spec.py (`tick_labels`) | Exponent form at ≥1e6 or <1e-4 | Axis labels | No | No | No |
| RPT-A038 | plots/power.py:52,57-63,75 | Peak limit line drawn if `peak_limit_w` is set. The "Minimum allowed" (1-DoD) line is drawn only if a DoD violation exists (the limit is read from a violation). A "Zero" line is always drawn | The SOC panel shows no limit line when there is no violation | No | No | No |
| RPT-A039 | plots/envelope.py:32-33 | `BLOCK=64`, `BLOCKS_PER_BUCKET=2` (GUI plot only) | Fast envelope | No | No | n/a |
| RPT-A040 | guide/build.py:30-37 | `GROUPS` | Guide structure | Yes | No | n/a |
| RPT-A041 | guide/build.py:159-160 | `--project` lists `Sourced` numbers only from `project.config` and `project.links` | Units, orbits, stations, modes, expendables and scenarios are not listed | Not stated | No | n/a |
| RPT-A042 | budget_cli/main.py:262,207,187,191 | Defaults `--max-rows 200`, `--series-every 1`, `--case both`, `--load-basis nominal` | Options | `--help` | Flags | No |
| RPT-A043 | main.py:431 | `_COUNTED_ONLY` = CONFIG_PLACEHOLDER, RESULT_INCOMPLETE are only counted on the console | Console noise filter | Partly (command-line.md:52) | No | No |
| RPT-A044 | main.py:515,582,632,690; 371; 716 | Default out `<project>/results` (inside the project tree); units-export default; guide stem | Output location | Yes | `--out` | No |
| RPT-A045 | main.py:355,462 | Exit 1 on errors, or on warnings with `--strict`. Exit 0 even when all results are n/a with the banner | Pass/fail policy | Documented | `--strict` | No |
| RPT-A046 | equations.py | 40 equations: TDP 11, LNK 9, ENV 6, PWR 5, TH 5, MASS 4. 37 have no source | Citation status of the tool | Yes (every report) | No (Python registry) | 3 sourced: ENV-GMST, ENV-GEODETIC, TH-SB |

The physical constants live in `environment/constants.py:23-43` and `link/constants.py:9-15`. They are sourced and not selectable. They are shown only in the guide.

### B. Hidden assumptions

| ID | file:line | assumption or behaviour | documented where? |
|---|---|---|---|
| RPT-B001 | numfmt.py:1-8,41-50 | Half-up rounding on the shortest decimal repr. A small negative number is displayed unsigned as 0.00 | reports-and-exports.md:54 |
| RPT-B002 | xlsx.py:71-72 | XLSX holds the full double with a display format; PDF and DOCX hold only rounded text | Partly (:54) |
| RPT-B003 | xlsx.py (all) | XLSX has no formulas, so a reviewer cannot trace or recompute in Excel | No |
| RPT-B004 | xlsx.py:129-133 | Any cell typed as a formula by openpyxl is forced to a string | Code comment |
| RPT-B005 | textsafe.py:15-21 | Control characters in project text are silently removed in XLSX and DOCX, with no note. PDF shows "?" with a note (pdf.py:176-216). CSV adds an apostrophe | PDF and CSV documented; XLSX and DOCX not |
| RPT-B006 | pdf.py:50,189-200,241 | Cells over 400 characters are shortened in the PDF (60 on retry) | :59 |
| RPT-B007 | common.py:87 | The equation table lists all equations with the prefix, used or not | No |
| RPT-B008 | common.py:68-80; power/static_budget.py:250-307; mass/static_mass.py:345-398 | "Configuration numbers used" holds only `Sourced` numbers the budget read. Plain numbers (unit power, duty, mass, positions) are absent | No |
| RPT-B009 | timeline_report.py:251 | The "Static power" section re-runs `static_power_budget(project)` instead of embedding the result the timeline used | No |
| RPT-B010 | run.py:217-224 | CSV parts and `_provenance.csv` are written only when the output has CSV parts | Partly |
| RPT-B011 | main.py:507 | `run --budget all` silently skips the link budget if the project has no links. `--budget link` alone exits 1 | No |
| RPT-B012 | main.py:490 | `run` always labels the scenario "static (no scenario)". A static run cannot name a case or limit set | Implicit |
| RPT-B013 | main.py:473-478 | Several scenarios and no `--scenario`: exit 2. None: exit 1 | command-line.md:43 |
| RPT-B014 | main.py:699 | `compare` always returns 0 | No |
| RPT-B015 | compare.py:146-148,428 | Differences below display precision are hidden (the report says so). Change values use exact values | In the report |
| RPT-B016 | link_report.py:243-248 | The link INCOMPLETE banner also triggers on any n/a `cn0` or `margin` | Implicit |
| RPT-B017 | scenario/export.py:154-176 | Scenario outputs carry provenance but no INCOMPLETE flag | Implicit |
| RPT-B018 | provenance.py:104-113 | The user defaults to the OS login (BUDGET_USER, else getpass). Personal data goes into every file | Variable documented (command-line.md:61); privacy aspect not stated |

### C. Outputs without a visible derivation

#### C.1 Format matrix

| Format | Written | NOT written |
|---|---|---|
| **XLSX** (`reports/xlsx.py`) | One sheet per Section (Summary, per mode, phase or case, plots as PNG), then **Assumptions**, **Problems**, **Provenance**. Assumptions holds "Configuration numbers used" (Name, Value, Unit, Source, Status) and "Equations" (ID, Name, Formula, Source). Problems holds severity, code, file:line, path, message, hint. Full-double values with a display format. Banner on every sheet | Formulas. File and path of each number. `Sourced.note`. Orbit, station, scenario and mode inputs. Constants. Per-column equation links. Structured units. Input hashes |
| **PDF** (`pdf.py`) | Same tables, A4 landscape, embedded PNG plots. Footer: tool, version, project, revision, scenario, time, user. Banner headline on every page. Metadata: title, author=user, subject=project, creator=tool | As XLSX, plus full precision. Characters outside IBM Plex become "?". Cells over 400 characters are cut |
| **DOCX** (`docx.py`) | Same as PDF. Core properties: author=user, title, subject=project, created and modified | As PDF. No note for removed control characters |
| **CSV** (`export.py`, `link_export.py`, `timeline_export.py`) | One file per table or series, plus `<prefix>_provenance.csv` (8 provenance rows plus `Incomplete`) | Assumptions, equations, problems, banner text. Units appear only in column names |
| **JSON** (`export.py:45`, `link_export.py:199`, `timeline_export.py:438`) | Full result tree, `incomplete`, `problems` (load problems included), `provenance`, `assumptions` with file and path. Timeline JSON adds grid, environment source and shadow model, limits (`peak_power_w`, `dod_limit_ratio`), modes, per-case summaries and balances, `not_evaluated` | Equations. Constants. Input snapshot. Time series (CSV only). No output schema or version (`export-schemas` covers input files only) |
| **Plots** (`plots/`) | PNG 1400 px, embedded in XLSX, PDF, DOCX. Power: generation, demand, SOC, margin, eclipse and pass bands, peak limit. Link: margin per rate, selected rate, elevation | No standalone image export (CLI or GUI). No vector, no data labels. DoD line only on violation. No provenance in the image |
| **Scenario files** (`scenario/export.py`) | `*_environment.json` (grid, eclipses, umbras, passes, timeline, notes, provenance), `*_eclipses.csv`, `*_passes.csv`, `*_timeline.csv`, `*_provenance.csv` | Orbit elements, propagator, Earth and Sun model, station coordinates. Rounded to 3, 4 or 6 dp |

CSV sets:
- power: one per mode, 12 columns.
- mass: one per phase, 11 columns.
- thermal: one per mode (9 columns) and one per case (6 columns).
- link: `_table` (18 columns, one row per link, point and rate). With passes also `_summary` and one series file per link.
- timeline: series per case (14 columns), `violations` (12 columns), `orbits` (9 columns).

#### C.2 Findings

| ID | where the user sees it | what is missing |
|---|---|---|
| RPT-C01 | "Configuration numbers used" (XLSX, PDF, DOCX) | File and path (they exist in `Assumption` and in JSON). `note`. No link from a result cell to the number it used. Power lists only the used maturity classes, system margin, distribution loss and bus converters, not which unit used which |
| RPT-C02 | Provenance block | Input hash, file list, config hash, commit, OS or platform, BLAS or NumPy build, whether `--date` or `--user` were overrides, scenario file content. Load basis, case and phase appear only in the time-domain text, not in provenance |
| RPT-C03 | Timeline and link-passes reports | Orbit elements, epoch, propagator, shadow and Sun model parameters, station and target coordinates, mode timeline and rules. Only "Environment source; shadow model; start; duration; step" is printed (timeline_report.py:45-47; link_report.py:207-208) |
| RPT-C04 | Equations table | Not tied to any output column. All equations of the prefix are listed. 37 of 40 are SOURCE_MISSING. No symbol units. Absent from JSON and CSV |
| RPT-C05 | Static power report | Missing: converter and distribution loss as W per bus. Which margin policy produced `margin_ratio`. The peak-case policy appears only in a note |
| RPT-C06 | All reports | The constants (c, k_B, Earth radius 6378137 m, mu, flattening, solar radius, AU) appear in no report, JSON or CSV. They are in the guide only |
| RPT-C07 | Link table (link_report.py:29-72) | Missing per row: transmit power, line loss and antenna gain (only in Assumptions), frequency (CSV only), bandwidth or noise term, the attenuation row used. "Other losses" is one sum without the values of pointing, polarisation and implementation |
| RPT-C08 | Link "Highest closing rate" and "Rate at required margin" | Selection logic is described only in a note |
| RPT-C09 | Time-domain results | Per-step k_T, k_age, cos θ and per-face power are not exported. The CSV has `sunlight_ratio`, `generation_w`, `demand_w`, `margin_w`, `battery_power_w`, `curtailed_w`, `unmet_w`, `energy_wh`, `soc_ratio`, `dod_ratio` |
| RPT-C10 | Time-domain "Static power" section | Summary table only, not the per-unit rows |
| RPT-C11 | Thermal report | Node temperatures with absorbed, radiated and conducted W. Missing: the network layout, node-to-unit mapping, solver and tolerance, formula-level terms. The imbalance is a threshold sentence only |
| RPT-C12 | Violations table | Check logic and limit source are not shown. It shows code, worst value, limit and the config path |
| RPT-C13 | `not_evaluated` | In the timeline note and JSON only. No code in XLSX |
| RPT-C14 | Mass report | CG and inertia are shown with a short note. The inertia method (D-048) and the positions are not in the report |
| RPT-C15 | Plots | No numbers or markers. The legend drops entries as "+N more" (render.py:221-234) |
| RPT-C16 | Problems table | Messages never contain the offending value (CLAUDE.md privacy rule). A reviewer sees the field but not the value that triggered the problem |
| RPT-C17 | `validate --format json` (main.py:343-348) | Only `errors`, `warnings`, `problems[]` (severity, code, message, file, path, line, hint). No schema version, file list, hash, tool version or model counts |
| RPT-C18 | Compare report | No input hash per side. Rows beyond `--max-rows` 200 are counted but not listed (CSV and JSON list all) |
| RPT-C19 | Guide `--project` | `.10g` values. No units, orbits, stations or modes. Origin shown only as `config` or `links/<id>` plus the field path |
| RPT-C20 | Static JSON | Row values and assumptions with file and path. No field links to an equation id |
| RPT-C21 | Column units | `Column.unit` is set in builders but never rendered (grep: only textsafe.py:29). Units are free text in headers |
| RPT-C22 | PDF and DOCX numbers | Rounded display only. Full precision is available only via JSON, CSV or XLSX |

#### C.3 Reproducibility from an export alone (requirement 14)

No. The reasons:
- The export lacks the orbit, stations, scenario, units, modes, geometry and every non-`Sourced` number.
- It has no hash, so nobody can check that a given project folder produced it.
- You need the project folder at the same revision, the same tool version, and for byte identity the same Pillow, ReportLab and openpyxl.
- `reports-and-exports.md:36-44` says identical project, scenario, user and time give identical bytes. It does not mention library or BLAS versions, and it relies on the user raising `revision`.

### D. Forced options

| ID | file:line | fixed choice | plausible alternatives |
|---|---|---|---|
| RPT-D01 | numfmt.py:16 | Half-up rounding; per-column decimals fixed in code | User-set digits or decimals. Scientific notation. Half-even. Full precision in PDF and DOCX |
| RPT-D02 | run.py:48 | Five formats | HTML, Markdown, LaTeX, Parquet, XLSX with live formulas and named ranges, a reproducibility bundle (zip of inputs and results) |
| RPT-D03 | pdf.py:247; docx.py:39 | A4 landscape only | Letter, portrait, corporate template |
| RPT-D04 | pdf.py, xlsx.py, docx.py | IBM Plex Sans and a fixed style | Corporate fonts and templates |
| RPT-D05 | common.py:14-17 | One banner and a binary verdict | Per-result flags. A review-status banner (draft or reviewed) |
| RPT-D06 | provenance.py:104-113 | The user is the OS login unless overridden | Opt-in, anonymised or role-based author |
| RPT-D07 | provenance.py | Fixed provenance fields | Inputs hash, git commit, platform, reviewer or approver, free note |
| RPT-D08 | plots/ | PNG only, fixed size and palette | SVG or PDF vector. A CSV of plotted points. DoD line always drawn |
| RPT-D09 | zipnorm.py; xlsx.py:143-145 | Fixed 1980 zip times | Real wall-clock time alongside "generated" |
| RPT-D10 | main.py:143,188,191 | Only the listed switches | Value override with justification. Choice of thermal case or limit set and of shadow model. A JSON summary of `run` |
| RPT-D11 | main.py:337-355 | `validate` JSON is the problem list only | Schema version, file list, hashes, model summary |
| RPT-D12 | guide/ | HTML and PDF guide | Markdown. A per-project "calculation book" (inputs, equations, values, results) |

### E. Interfaces

| ID | file:line | dir | what and format | user told? | provenance? |
|---|---|---|---|---|---|
| RPT-E01 | run.py:179-225 | out | `<prefix>.xlsx`, `.pdf`, `.docx`, `.json` and CSV sets to `--out` or `<project>/results` | Yes (`Wrote` lines, docs) | Embedded in XLSX, PDF, DOCX, JSON. CSV via `_provenance.csv` |
| RPT-E02 | files.py:108 | out | Temp files `.name.pid.tmp` in the output folder, then replace | Yes (docs :50) | No |
| RPT-E03 | scenario/export.py:173-176 | out | `<id>_environment.json`, `_eclipses.csv`, `_passes.csv`, `_timeline.csv`, `_provenance.csv` | Yes | JSON embeds it. No incomplete flag |
| RPT-E04 | compare.py:419-474; compare_run.py | out | `compare.*` and `compare_differences.csv` | Yes | Provenance yes, no input hash |
| RPT-E05 | main.py:371-387 | out | `unit_power_modes.csv` (UTF-8 BOM) or `.xlsx` | Yes | None |
| RPT-E06 | main.py:394-426 | in/out | Reads a filled unit table (CSV or XLSX). `--apply` writes `units/*.yaml` | Yes (plan printed first) | The import source is not recorded in the unit files |
| RPT-E07 | main.py:702-727; guide/html.py:43-53 | out | `system-budget-studio-guide.html` (fonts inlined as base64) and `.pdf` | Yes | Tool version only. No date (good for byte identity) |
| RPT-E08 | main.py:781-787 | out | JSON Schemas; example projects | Yes | Schema version in files |
| RPT-E09 | assets.py:20-38; pdf.py:55; render.py:42 | in | Bundled IBM Plex fonts read at runtime. No network | Yes (offline test) | Font files not in provenance |
| RPT-E10 | provenance.py:84,107,111 | in | Env `SOURCE_DATE_EPOCH`, `BUDGET_USER`, OS account via `getpass` | Yes (command-line.md:57-63) | Result recorded, source not |
| RPT-E11 | pdf.py:44-45 | internal | ReportLab remote-URL loading disabled | Comment | n/a |
| RPT-E12 | provenance.py:63-68 | in | `importlib.metadata` versions of 9 libraries | Printed | Version strings only |
| RPT-E13 | io/project_loader.py | in | Project YAML tree: `project.yaml`, `spacecraft.yaml`, `units/`, `modes/`, `config/`, `links/`, `orbits/`, `ground_stations/`, `targets/`, `scenarios/`, `expendables/` | Docs | **No hash or file list in any output** |
| RPT-E14 | scenario/run.py:196-202 | in | Optional `spacemissionstudio` CSV import folder | FILE_FORMAT | Cache key uses name, size, mtime, never exported. No content hash |
| RPT-E15 | model/link.py (`pattern_file`) | in | Antenna pattern file | Docs | Only `pattern_source` in Assumptions. No content hash |
| RPT-E16 | main.py:330-334 | out | stdout for results and banner, stderr for errors | Yes (command-line.md:48-55) | n/a |
| RPT-E17 | main.py:343-355 | out | `validate --format json` to stdout | Yes | No version or hash |
| RPT-E18 | pyproject.toml:46-47 | out | Entry point `budget = budget_cli.main:main` | Yes | n/a |
| RPT-E19 | budget_core/__init__.py | API | Exports only `APP_NAME` and `__version__`. No package-level `__all__` (some modules have one: `new_*.py`, `model/__init__.py`, `remove_item.py`). `py.typed` ships | `ARCHITECTURE.md` says "the GUI only touches `budget_core` public API" but nothing defines it. The user manual never mentions importing `budget_core` | **No documented Python API or stability promise** |
| RPT-E20 | run.py (`BudgetOutput`, `*_output`, `write_outputs`) | API | The programmatic export path shared by CLI and GUI | Developer docs only | n/a |
| RPT-E21 | selftest.py:22 | internal | `budget self-test` | Yes | n/a |
| RPT-E22 | tests/golden (88 files) | test | Content dumps stable to 9 significant digits, values under 1e-6 set to 0.0 | Developer-only | n/a |

Exit codes (`budget_cli/main.py`; documented in command-line.md:37-46):
- 0: success.
- 1: errors, or warnings with `--strict` (`:355,:462`); a write failure; an internal error; no scenarios; no links with `--budget link`.
- 2: bad call (`:375`, `:662`, `:789` no command), several scenarios without `--scenario` (`:478`), unusable SOURCE_DATE_EPOCH (`:823`).
- 130: Ctrl+C (`:812`).

JSON output exists for `validate --format json` only. Every other command prints text; the report JSON files are separate. There is no machine-readable summary of `run`.

CLI versus GUI:
- The CLI can run all budgets, timeline, link passes and compare. It can export unit tables and apply imports, write the guide, create a blank project, and run schemas, examples and self-test.
- The CLI cannot edit or override values. It cannot add units, modes, links, scenarios or stations, though core builders `new_*.py` exist for the GUI wizards. It cannot choose a thermal case, a limit set or a shadow model, or remove items, view equations or plots, or export plots.

### Already good

- A uniform provenance block in all formats, also in the PDF and DOCX footers and document properties.
- Reproducible bytes: SOURCE_DATE_EPOCH, `--date`, `--user`, fixed zip times and order, ReportLab invariant mode. A bad SOURCE_DATE_EPOCH is an error, not a silent fallback (`provenance.py:75-101`).
- `closing_sections` (`reports/common.py:56`) already puts sourced config numbers with PLACEHOLDER status, the equation registry, Problems and Provenance into every report. It is the natural extension point.
- The INCOMPLETE banner on every sheet and page, and `incomplete` in JSON and in the CSV sidecar.
- Placeholders become n/a, never 0, under uniform rules.
- Atomic multi-file writes with sanitised names and a collision check.
- The `EQUATIONS` registry feeds both reports and the guide, with explicit SOURCE_MISSING.
- Constants are sourced and printed in the guide.
- Compare uses exact values and says that sub-display differences are hidden.
- `budget guide --project` lists every `Sourced` number of the config and links with status.
- `--strict`, `validate --format json`, offline operation, and a command reference with exit codes (`docs/user-manual/command-line.md`).
- Problems carry file, line and path.

### Notes for the plan

- **Byte-identical output is a hard constraint.**
  - A new provenance field must be deterministic and appear in every format. The golden files in `tests/golden` (88) would need regeneration.
  - Goldens compare content dumps, not bytes. Bytes are not guaranteed across library or BLAS builds.
  - Places to keep in step for a new field: `Provenance.rows()` (`provenance.py:50-61`), `provenance_csv`, the PDF footer (`pdf.py:229-231`) and DOCX footer (`docx.py:200-205`), JSON `asdict(provenance)`, the hand-built scenario JSON provenance (`scenario/export.py:158-168`), and the explicit field list in `textsafe._provenance` (`textsafe.py:49-58`).
- **An input hash must not use mtime.** The existing fingerprint (`scenario/run.py:181-204`) does, so it is not reproducible. Decide whether to hash raw YAML bytes (comments, where sources live per D-102, would change it) or the parsed model.
- **File list.** `LoadResult` has `lines` but no file list. Imported CSVs and antenna pattern files are read outside the main loader.
- **Rounding changes** break the goldens and `compare`, which hides sub-display differences. `GENERAL_DIGITS=10` is hard-coded separately in `numfmt.py` and the guide.
- **Privacy rule.** Problem messages never contain project values. Showing the offending value requires relaxing that rule.
- **Sources for plain numbers** (unit power, mass, orbit, stations) need a file-format change with a schema version bump and a migration (CLAUDE.md), not only report changes.
- **Equation links.** `Column` could carry an equation id (it has an unused `unit` field already). XLSX, PDF, DOCX and compare (`key_columns`) must all handle it.
- **Equation sources.** 37 of 40 SOURCE_MISSING means the table cannot serve as a citation list yet. The sources are owner-supplied (D-061).
- **API.** Defining one means choosing the surface (`reports.run.*_output`, `io.project_loader.load_project`, the budget functions), adding `__all__`, and writing docs.
- **CLI overrides** need a model-level override record with a justification before any flag exists. `budget_cli/main.py` is 838 lines with no override concept.
- **Python 3.14 only.** `budget_cli/main.py:67` uses the PEP 758 syntax; the system python 3.13 cannot import it.
- **Docs drift.** `docs/user-manual/reports-and-exports.md:56` says CSV and JSON hold "full precision (series files: six decimals…)". Static CSVs use full `repr`; link and timeline CSVs use fixed 6, 3 or 1 dp; the scenario JSON is rounded. Line 48 of the same page repeats one sentence about the Export buttons.

## Appendix G — Window: shell, session and panels

Scope read in full: main_window.py, session.py, model_document.py, layout_settings.py, privacy.py, app.py, command_palette.py, project_tree.py, problems_panel.py, problem_class.py, inspector.py, provenance_panel.py, status_bar.py, top_bar.py, settings_popover.py, start_here.py, welcome.py, help_view.py, run_controller.py, editor.py, worker.py, banner.py, edit_bar.py, unit_table.py (GUI), the five add_*_dialog.py, remove_item_dialog.py, guided.py (partly). Core files behind the dialogs and wizard (new_*.py, wizard.py, blank.py, remove_item.py, io/unit_table.py, provenance.py) were read because they hold the numbers the dialogs apply. Paths below are relative to /home/user/systembudgetstudio/src/. Nothing in the repo was modified.

### Summary
- Counts: A = 34 rows, B = 22, C = 14, D = 9, E = 17 (plus requirement 6/7/8/13/14 answers below, which are cross-cutting).
- Top 5 gaps:
  1. Requirement 7 (overrides): there is none. No computed value can be overridden anywhere in the window; the only editable things are input fields. grep for "override" in src finds only the layout.ini path text and the editor's overwrite-on-save. A `Sourced` input has value/source/note, but nothing flags "this replaces a computed value" and nothing demands a justification.
  2. Requirement 8 (change history): only the in-memory Qt undo stack (`model_document.py:176`), unbounded, cleared on load/discard/external change, never persisted, no who/when/why. `ProjectMeta.revision` (`budget_core/model/project.py:26`) is a free string the user bumps by hand; no date, author or reason. Nothing is written when a file is saved by the window or by the unit-table import.
  3. Requirement 6 (workflow visibility): the workflow is hard-wired in three places (Start here 4 steps `start_here.py:36`, load-time static chain `session.py:52`, Run chain `run_controller.py:54`) and never shown as inputs -> step -> outputs. The Inspector says it is a first version and shows only file/field/problems (`inspector.py:1-6`); the Provenance dock shows tool/versions/project/time/user, no input hashes, no per-result inputs.
  4. "Up to date" is not tied to the inputs: the chip tooltip says "worked out from the inputs now on screen" (`main_window.py:1447`) but Run (Ctrl+R) uses the SAVED project while grid edits are unsaved (`run_all` `main_window.py:1388` never checks `document.is_modified()`); static budgets only refresh after Save+reload. Stale detection is a reload counter (`timeline_view.py:289`, `scenario_view.py:354`), not a content hash, so any F5 makes every result "Out of date" even if nothing changed, and an external edit is not noticed until F5.
  5. Hidden number choices behind the dialogs and wizard: step = `first_run_step_s` (10 s base, 8640 steps, 600 s cap), eccentricity 0.001 and arg. of perigee 90 deg for "near-circular", spherical orbit from WGS-84 equatorial radius, 180-day / 160-2000 km limits, wizard defaults (550 km, 97.6 deg, 100 deg RAAN, 1 day, 2026-06-01). None is editable in the form or listed in the UI; only the resulting file values are visible afterwards.

### Answers to the cross-cutting requirements
- **Req 6, where am I / what does each step consume and produce:** Partial. Visible: Start here card with 4 steps and done/to-do icons (`start_here.py:36-75, 106-118`), Run chip with 5 states and stage text (`run_controller.py:26-32`, `top_bar.py:99-104`), status bar "Last run HH:MM:SS" (`status_bar.py:79`). Not visible: what each step reads/writes (no dependency view), which results derive from which files, which result is stale because of which edit. Intermediates: the Scenario/Timeline/Passes views (Part B) show some; the window offers no way to list or open "intermediate results" as such. The Start here card disappears once all four steps are done (`main_window.py:1508-1510`) and is hidden in focused view only by user choice; the Inspector and Provenance docks are HIDDEN by default (`main_window.py:123`, `1227-1234`, D-191).
- **Req 7, overrides:** None today. Inputs are edited in place in grids/YAML; derived numbers (margins, losses, link results) have no override field. A placeholder is the only "special" value state (`source: TBD`, `grid_models.py:598-605`).
- **Req 8, change history:** Undo stack only (`model_document.py:63-124, 176`); `Undo` tooltip shows the text of one step (`edit_bar.py:66-75`); no history panel; no persisted log; no author/time/reason; save writes no changelog. Revision label shows in top bar (`top_bar.py:190-192`) and Compare uses it, but bumping is manual.
- **Req 13, extensibility hooks:** No plugin/registry in the window. Closest: command palette is built by walking the menu bar (`main_window.py:1775-1795`), so any QAction becomes a command, but there is no public register call; `MigrationRegistry` is injectable into `load_project(root, registry)` (`budget_core/io/project_loader.py:423`, `migrations.py:162`); `CONFIG_FILES`, `REPORT_KINDS` (`reports/run.py:48`), `EXAMPLES`, `SAMPLES`, equation registry `EQUATIONS` are module-level dicts/tuples edited only in source. No entry points in pyproject (`[project.scripts]`/`gui-scripts` only).
- **Req 14, visible data links:** The only external file the window imports is the unit power table CSV/XLSX (`unit_table.py` GUI, `budget_core/io/unit_table.py`). TLEs live inline in the orbit YAML (`budget_core/model/environment.py:84`); there are no external TLE or antenna-pattern files; the add-scenario form offers elements only. After import the file name/hash/time is NOT recorded anywhere (name goes only into Problem messages, `unit_table.py:89`). No file watcher exists (no `QFileSystemWatcher` in budget_gui). Reload = F5/File>Reload (`main_window.py:336`) or automatic after Save; a file changed on disk is detected only (a) at save time by SHA-256 stamp (`model_document.py:398`, `editor.py:83-107`) and (b) when F5 reloads. No banner "files changed on disk".

### A. Constants, defaults, thresholds, rules
Visible = shown in UI/exports; Editable = changeable without editing code.

| ID | file:line | value | purpose | visible? | editable w/o code? | source stated? |
|---|---|---|---|---|---|---|
| SHL-A01 | gui/main_window.py:123 | `DEFAULT_VIEW="focused"` | window starts with Inspector + Provenance hidden, Problems = one line, optional grid columns hidden | View menu + tooltip (`main_window.py:496`) | yes: View>Focused view, saved in layout.ini `window/view` | D-191 |
| SHL-A02 | gui/main_window.py:124, 1166, 1178 | `LAYOUT_VERSION=2` | saved dock layout of another version is silently ignored | no | no | none |
| SHL-A03 | gui/main_window.py:605 | `Path.home()/"SystemBudgetStudio"` | default parent folder of the guided wizard | yes (wizard field) | yes (field) | none |
| SHL-A04 | gui/main_window.py:1816 | `rglob("*.yaml")[:400]` | palette lists at most 400 project files, only `.yaml` | no | no | none |
| SHL-A05 | gui/main_window.py:1826 | `message[:90]` | palette truncates problem text | no | no | none |
| SHL-A06 | gui/command_palette.py:30 | `MAX_SHOWN=60` | at most 60 palette hits, silently cut | no | no | none |
| SHL-A07 | gui/problem_class.py:22 | `NOT_CHECKED_CODES={"CONFIG_PLACEHOLDER","RESULT_INCOMPLETE","THERMAL_NO_LIMITS"}` | which warnings are shown as "Not checked" (neither pass nor fail) instead of warnings; decides counts in status bar, tree badges | class word in panel; the code list not shown | no | D-151 text |
| SHL-A08 | gui/problem_class.py:57-64 | ERROR->error; WARNING+code in set->not checked; WARNING->warning; else info | severity-to-class rule | tooltips (`problem_class.py:46-54`) | no | none |
| SHL-A09 | gui/top_bar.py:29, 145-150 | `CASES=("BOL","EOL")`, tooltips "solar array and battery as new" / "degradation over the design life" | the only two life cases the window offers | yes | no | none |
| SHL-A10 | gui/start_here.py:36-75, 106-118 | 4 fixed steps; done = file count > 0 (units, modes, scenarios) and, for step 4, `saved and ran` | defines what "a project is set up" means | yes | no | D-190 |
| SHL-A11 | gui/project_tree.py:55 | `GROUP_UNITS_ABOVE=8` | units grouped by subsystem above 8 (cosmetic) | no | no | none |
| SHL-A12 | gui/project_tree.py:78-80, 187-189 | `*.yaml` glob, top level only | tree/"Files" list only shows `*.yaml`; other files invisible (the loader does warn about `.yml`, `loader:396-410`) | partly | no | none |
| SHL-A13 | gui/status_bar.py:69 | project path cut to last 59 chars | display only | tooltip has full path | no | none |
| SHL-A14 | gui/session.py:30 | `BACKGROUND_LOADING=True` | async load; a result made while newer request exists is dropped | status line "Loading..." | no | none |
| SHL-A15 | gui/session.py:210 | `worker.wait(10000)` ms | wait for a finished loader thread | no | no | none |
| SHL-A16 | gui/app.py:37 | `SWITCH_INTERVAL_S=0.0005` | process-wide interpreter switch interval | no | no | D-183 |
| SHL-A17 | gui/layout_settings.py:22-29 | file `layout.ini`; groups window/dock/columns/theme; words {full,reduced},{open,folded},{shown,hidden},{focused,full},{double,single}; key regex `{1,64}` | what the settings file may hold | docs/user-manual/use-the-window.md:104 | delete file / Reset layout | D-105, D-150 |
| SHL-A18 | gui/layout_settings.py:34-39 | env `BUDGET_NO_LAYOUT`, `BUDGET_CONFIG_DIR`; default `QStandardPaths.AppConfigLocation` | where the settings file lives | user manual | yes (env) | D-150 |
| SHL-A19 | gui/theme/scale.py:97-98 | `SCALES=(90,100,110,125)`, `DEFAULT_SCALE=100` | UI scale choices (docs UI_OVERHAUL_PLAN.md:222 says 100/110/125/150: docs and code differ) | yes | choices fixed | none |
| SHL-A20 | gui/privacy.py:18 | `UNWRITABLE_SETTINGS_PATH=os.devnull+"/<settings disabled>"` | Qt settings redirected so Qt writes nothing | docs only | no | D-105 |
| SHL-A21 | gui/unit_table.py:28 | `PREVIEW_LINES=20` | import preview shows 20 changes then "... and N more" | yes | no | none |
| SHL-A22 | core io/unit_table.py:50-53 | `MAX_FILE_BYTES=5_000_000`, `MAX_UNPACKED_BYTES=50_000_000`, `MAX_ROWS=100_000`, `MAX_COLUMNS=50` | import size limits (refused with a message) | message | no | none |
| SHL-A23 | core io/unit_table.py:38-48 | only 6 numeric columns: avg_power_w, peak_power_w, duty_cycle_ratio, heat_dissipation_ratio, min_duration_s, max_duration_s | what an import can change; units fixed to SI by column name | file header | no | none |
| SHL-A24 | core io/unit_table.py:344-345 | `isclose(rel_tol=1e-12, abs_tol=1e-15)` | decides "unchanged" on import | no | no | none |
| SHL-A25 | core wizard.py:34 | `ECCENTRICITY_RATIO=0.001` | "near-circular" orbit of every form/wizard orbit | text of scenario `description` (`new_scenario.py:224-227`); dialog intro does not give the number | no | "as in the sample orbits" |
| SHL-A26 | core new_scenario.py:222; wizard.py:210; new_scenario.py:253; wizard.py:211 | arg. of perigee `90.0`, mean anomaly `0.0` | fixed elements for near-circular orbit / "starts at perigee" for elliptical | only in written orbit file | edit orbit YAML after | none |
| SHL-A27 | core wizard.py:37, new_scenario.py:162 | `ALTITUDE_RANGE_KM=(160,2000)` | allowed (perigee) altitude of the form | error text only | no | none |
| SHL-A28 | core new_scenario.py:36 | `APOGEE_RANGE_KM=(160,40000)` | "up to a Molniya or GTO" | error text | no | comment |
| SHL-A29 | core wizard.py:38; new_scenario.py:191; add_scenario_dialog intro | `MAX_DAYS=180` | scenario length cap in forms | dialog intro + error | no (scenario YAML can be hand-edited) | "a run of this length takes under a minute (D-196)" |
| SHL-A30 | core new_scenario.py:35; wizard.py:35-36,135-139 | `MIN_STEP_S=10`, `MAX_STEPS=8640`, `MAX_STEP_S=600` => `step_s` | time step chosen for a new scenario (180 d -> 600 s, so 25 920 steps) | step_s visible in scenario file/editor afterwards; rule not stated in the form | no | comments only; 600 s from "a quarter period" |
| SHL-A31 | core model/environment.py:18; timeutil.py:12-13,32 | years 1950..2100; "must end before 2101" | date limits for scenarios | error text | no | none |
| SHL-A32 | core new_site.py:39-41, 97-105 | lat -90..90, lon -180..180, alt -1000..100000 m, min elevation 0 .. <90 deg | site form ranges | placeholders/error | no | "as the model takes it" |
| SHL-A33 | core new_link.py:40; blank.py:33; new_unit.py:23-25 | `FREQUENCY_RANGE_MHZ=(1,1e6)`, `BUS_VOLTAGE_RANGE_V=(1,1000)`, `MAX_ID=60`, `MAX_TEXT=120` (descr 480), id regex | form limits | error text | no | none |
| SHL-A34 | core wizard.py:58-63; gui/guided.py:117-123 | wizard defaults: sample `microsat_250kg_eps`, 550 km, 97.6 deg, RAAN 100, 1 day, start `2026-06-01T00:00:00Z`; GUI spin limits 0..100000 km, 0.01..1000 days differ from the checks (160..2000 km, <=180 d) | prefilled orbit/scenario | yes (prefilled) | yes (fields) | "invented sample" note `guided.py:149`; blank: `MATURITY_CLASSES=("class_a","class_b","class_c")` labels (`blank.py:32`) |

### B. Hidden assumptions

| ID | file:line | assumption / behaviour | documented where? |
|---|---|---|---|
| SHL-B01 | gui/main_window.py:1388-1397, 1447 | Run uses the SAVED project; unsaved grid edits are not in the results, yet the chip says "Up to date ... from the inputs now on screen". Only the top-bar "Unsaved changes" marker differs. | not documented |
| SHL-B02 | gui/session.py:52-96; main_window.py:1700-1704 | Power/mass/thermal/link static budgets are recomputed only on load (open, F5, after Save); not on edit. Tooltip says "The static budgets are always up to date" (`top_bar.py:30-33`) which is true only for saved files. | tooltip only |
| SHL-B03 | gui/timeline_view.py:289-299; scenario_view.py:354; link_view.py:202 | Stale/valid = reload revision counter, not input content. Every reload (even identical files) marks results Out of date; unsaved edits never mark results stale. | not documented |
| SHL-B04 | gui/main_window.py:1720, 1562 | `_last_run` is set to `now()` at every project LOAD, so the status bar shows "Last run HH:MM:SS" before any Run; the chip "Up to date" detail uses the same time. | tooltip text implies computations |
| SHL-B05 | gui/session.py:85-96 | One catch-all: any exception in any static budget gives a single `INTERNAL_ERROR` problem with only the exception class name; nothing else of the project is shown. | message says run `budget validate` |
| SHL-B06 | gui/session.py:137-140, 229-248 | After a failed load the last good budgets stay on screen (banner "may not match the files"), but `outputs=[]` so export is blocked. Grids keep editing the last good document (`model_document.py:204`). | banner text |
| SHL-B07 | gui/app.py:19-26, 29-34; worker.py:36-43 | Exception text is deliberately dropped (privacy rule): users see only the class name; no way to see a traceback/log. | docstring |
| SHL-B08 | gui/model_document.py:276-297, 468-473 | Every edit is re-validated and replaced by `model_to_data(model_validate(data))`: "2500 mW" becomes 2.5; optional None/"" fields are removed; invalid data kept as typed. | module docstring |
| SHL-B09 | gui/model_document.py:421 (+ core io/roundtrip.py:223-255) | `save_edited_data` returns `SaveResult.canonical`; the window discards it. If the YAML cannot be patched it rewrites the whole file canonically (comments lost) with no message. Unverified: whether a file loaded through a migration is rewritten with the new schema version silently. | roundtrip docstring (D-103) |
| SHL-B10 | gui/model_document.py:438-457 | The document holds only spacecraft, units, modes, scenarios, links, ground stations, targets, expendables and 6 config files; `project.yaml` (name, revision) and `orbits/*.yaml` are NOT editable in the grids (text editor only). | none |
| SHL-B11 | gui/model_document.py:214-216 | If a file changes on disk and has no pending edits, the undo history is cleared silently on reload. | comment |
| SHL-B12 | gui/main_window.py:1127-1153; grid_models.py:51-52, 235-244 | Inspector "Value:" is the cell text rounded to a fixed number of decimals per column (e.g. mass 3, temperature 2, source value 6 via `:g` at grid_models.py:665); the exact value (`.12g`, `grid_models.py:60`) is only in the cell tooltip. | none |
| SHL-B13 | gui/main_window.py:1753-1757 | Problems from timeline/pass views are de-duplicated against project problems by (code, file, path, message). Identical messages from different sources collapse. | none |
| SHL-B14 | gui/problems_panel.py:305-308 | Filter is an AND of lowercase words over message/file/path/code/hint. | placeholder text |
| SHL-B15 | gui/project_tree.py:121-184 | Tree structure is fixed (Spacecraft, Units, Modes, Expendables, Solar array/Battery fields of `power_system.yaml`, Orbits, Stations, Targets, Scenarios, Links, Budget configuration, Files); a file kind not in this list appears only under "Files". | none |
| SHL-B16 | gui/unit_table.py:61-65; core io/unit_table.py:215 | Export writes CSV with BOM; import reads `.xlsx` with `data_only=True` (cached formula results only; formula without cached value reads as empty); numeric columns assumed SI by header name; no unit conversion. | none |
| SHL-B17 | gui/unit_table.py:110-115 | Import writes unit files directly (not an undo step, not in the Model document) and reloads; refused if any unsaved edit exists. | message |
| SHL-B18 | gui/model_document.py:476-501 | `_cross_checks` duplicates one loader rule (REF_UNKNOWN_SITE) in the window; other cross-file checks (station/peer, mode references) are only seen after Save+reload. | docstring |
| SHL-B19 | gui/main_window.py:1198-1206, 1280-1330 | Window width thresholds hide Inspector/Provenance/Project docks without telling the user. | docstring |
| SHL-B20 | core wizard.py:197-207; new_scenario.py:219-228, 241-246 | Altitude -> semi-major axis uses `EARTH_RADIUS` = WGS-84 equatorial radius (6 378 137 m) + altitude; elliptical e = (ra-rp)/(2R+rp+ra). Dialog says "altitude of the orbit". Spherical-Earth altitude convention not stated in the form. | constant source string only |
| SHL-B21 | core wizard.py:177-190 | The guided wizard copies a synthetic sample project built in code, then overwrites orbit/scenario; everything else (units, config numbers) is the sample's invented data. | wizard text + project description |
| SHL-B22 | gui/main_window.py:1670-1694 (editor.py:100-112) | Text editor tab saves atomically through a temp file in the project folder, preserves BOM/CRLF, asks before overwriting a file changed on disk; the text-editor path and the grid path are two separate save mechanisms (the editor does not go through the undo stack or the Document). | no |

### C. Outputs without a visible derivation

| ID | where the user sees it | what is missing |
|---|---|---|
| SHL-C01 | Run chip "Up to date" / "Out of date" / "Not run" (`top_bar.py`, `run_controller.py:153-169`) | Which inputs/files each result was computed from; why it is stale (no list of changed files/fields); stale logic is a counter. |
| SHL-C02 | Inspector for a cell (`inspector.py:124-156`) | Equation/formula that uses the field, "where used" (results that read it), source of a sourced value, allowed range, default vs explicit; shows rounded value only. Docstring admits these are deferred (`inspector.py:3-5`; D-154 "come with the editable model" never delivered). |
| SHL-C03 | Inspector for a tree node (`inspector.py:158-192`) | Only file/field and problems of the node; no content summary, no hash, no dependents. |
| SHL-C04 | Provenance dock (`provenance_panel.py:55-72`, `budget_core/provenance.py:40-49`) | Eight rows only: tool, Python, libraries, project, revision, scenario ("static (no scenario)" for the load-time budgets), generated time, user. No file list, no SHA-256 of any input file (the window already computes `file_stamp` for save conflicts, `roundtrip.py:49-55`), no config/standards versions, no list of constants used, no run parameters (step, case, shadow model). Panel is not refreshed after Run, so it never describes the timeline. "User" = BUDGET_USER or OS account (`provenance.py:104-112`). |
| SHL-C05 | Status bar "N not checked" (`status_bar.py:85-93`) | Count only; which inputs are missing is in the Problems panel, but not which results depend on each. |
| SHL-C06 | Problems panel (`problems_panel.py`) | Message + hint + file:line + code; no link from a problem to the equation or the margin value that triggered it, no values (by privacy rule: "field names, ids and units only" so the numbers behind a violation are not in the message). |
| SHL-C07 | Start here card state (`start_here.py:106-118`) | "Done" derived from counts of files only; no check that the units/modes are valid or complete. |
| SHL-C08 | Add-scenario result (`main_window.py:759-762`) | Status line does not list the derived values it wrote (step_s, eccentricity 0.001, arg. of perigee 90, mean anomaly 0, WGS-84 radius); they are visible only by opening the files. |
| SHL-C09 | Add link / Add Eb/N0 (`main_window.py:1039-1042`, `932-935`) | Says "placeholders", not which fields or what each placeholder blocks. |
| SHL-C10 | Unit-table import preview (`unit_table.py:35-44`) | Shows 20 old->new values with `:g`; no source-file name/hash/time kept afterwards; no reason field. |
| SHL-C11 | INTERNAL_ERROR / "An unexpected error occurred (TypeName)" / "The export failed (TypeName)" | No location, no log, no way for the user to get the cause. |
| SHL-C12 | Undo/Redo tooltip (`edit_bar.py:66-75`) | One step's name only; no list of past edits, old->new values, or time. |
| SHL-C13 | Banner "stale" (`main_window.py:1404-1409`) | Says results may not match the files; does not show what changed between last good and current. |
| SHL-C14 | User guide chapter "Equations and sources" (`budget_core/guide/build.py:157-186`, opened by Help>User guide with the project) | Lists equations/constants/sourced numbers, but no per-result link: cannot go from a result cell to its equation. |

### D. Forced options

| ID | file:line | the fixed choice | plausible alternatives |
|---|---|---|---|
| SHL-D01 | gui/run_controller.py:54-61 | Run = scenario -> power timeline -> link passes (links only if any) of ONE scenario | per-step Run; run all scenarios; choose which steps; parameter sweeps; mass/thermal timeline (none) |
| SHL-D02 | gui/top_bar.py:29 | life cases BOL/EOL only | mid-life, user-defined cases, per-case degradation |
| SHL-D03 | gui/model_document.py:398-404, session.py | Save = overwrite-in-place with SHA-256 conflict refusal; no versioned/branch save | save as new revision; auto-increment revision; keep a backup/change record |
| SHL-D04 | gui/main_window.py:1109-1111 | Change detection = manual F5 (or auto after Save); no watcher | file watcher with "files changed" banner; auto-reload; diff against loaded |
| SHL-D05 | gui/layout_settings.py, privacy.py | Single global per-user `layout.ini`, UI-only; no per-project settings, no engineering settings (precision, units system, default step, tolerances), no recent projects | per-project settings file in project folder; user-selectable numeric display precision; recent-files list |
| SHL-D06 | gui/session.py:52-96 | Fixed computation order at load: power, mass, thermal, provenance, outputs, link | user-visible pipeline, selective recompute |
| SHL-D07 | gui/start_here.py:36-75 | Fixed four-step onboarding, linear gating (`can_start`) | checklist for review/verification workflow; steps per discipline |
| SHL-D08 | gui/add_scenario_dialog.py, core new_scenario.py | New scenarios: elements-based orbit only, one spacecraft mode for the whole time, no TLE, no sites, no rules, step auto-chosen | TLE input, step choice, multi-segment/mode schedule, eccentricity input, other propagators |
| SHL-D09 | gui/remove_item_dialog.py, core remove_item.py:25 | Removable kinds: expendable, ground station, imaging target, link. Scenarios, orbits, config entries cannot be removed from the window (units/modes via grids) | remove scenario/orbit; archive instead of delete |

### E. Interfaces

| ID | file:line | direction | what / format | user told? | provenance / hash / version? |
|---|---|---|---|---|---|
| SHL-E01 | gui/layout_settings.py:22,34-39,52 | out/in | `layout.ini` (QSettings INI, binary `QByteArray` geometry and dock state) in `AppConfigLocation` or `$BUDGET_CONFIG_DIR`; written at close and on each setting change (`main_window.py:540-593, 1173-1185`) | docs + `use-the-window.md:104`; no in-app notice | `LAYOUT_VERSION` only for docks |
| SHL-E02 | gui/privacy.py:18-26; app.py:45; main_window.py:133 | out (suppressed) | Qt would write `~/.config/QtProject.conf`; redirected to unwritable path; file dialogs forget last folder | docs (`use-the-window.md:143`) | n/a |
| SHL-E03 | env `BUDGET_CONFIG_DIR`, `BUDGET_NO_LAYOUT` (layout_settings.py:34-36); `BUDGET_USER`, `SOURCE_DATE_EPOCH` (core provenance.py:5,104-112,70-86); `QT_QPA_PLATFORM` (Qt) | in | environment variables | CLI manual `command-line.md:61-62`; not shown in the window | the resulting user/time appear in Provenance rows |
| SHL-E04 | gui/session.py:55; core io/project_loader.py | in | project folder: `project.yaml`, `spacecraft.yaml`, `units, modes, scenarios, orbits, links, ground_stations, targets, expendables/*.yaml`, `config/*.yaml` (known names only; unknown ignored with warning `loader:396-410`) | Problems panel warnings | schema_version per file; no folder hash |
| SHL-E05 | gui/model_document.py:381-434; editor.py:100-112 | out | writes edited YAML in place (patched, comments kept, or whole-file rewrite silently), deletes files after a question (`main_window.py:1633-1644`), atomic temp file inside the project folder | status line "Saved N files" | SHA-256 stamp used only for conflict check, not recorded |
| SHL-E06 | gui/unit_table.py:47-69; core io/unit_table.py:76-135 | out | export unit power modes to CSV (UTF-8 BOM) or XLSX at a user-chosen path | file dialog | no provenance sheet/columns stated (unverified) |
| SHL-E07 | gui/unit_table.py:72-115; core io/unit_table.py:236-258, 578-604 | in -> project | import CSV/XLSX; patches `units/*.yaml` directly | preview dialog (20 lines) | file name only in problem text; no hash/time/author stored |
| SHL-E08 | gui/main_window.py:1080-1090, 1940-2031; gui/worker.py | out | report files (XLSX, PDF, DOCX, JSON, CSV) to a chosen folder via background thread | status line "Exported N file(s) to ..." | Provenance block in each (rows of C04) |
| SHL-E09 | gui/main_window.py:641-686 | out | scenario results (CSV/JSON), power timeline exports | message boxes/status | provenance as above |
| SHL-E10 | gui/help_view.py:24, 90-97 | out | guide HTML + PDF `system-budget-studio-guide.html/.pdf` to a chosen folder | status label | guide built with the open project's sourced numbers |
| SHL-E11 | gui/main_window.py:601-610; gui/guided.py:104; core wizard.py:160-184 | out | new project folder under `~/SystemBudgetStudio` (default) or chosen parent; half-written folder deleted on failure (`rmtree`, `wizard.py:178`) | wizard text | project description records the sample name |
| SHL-E12 | gui/theme/fonts.py:17-35; theme/qss.py:133; theme/controller.py:203; icons.py:41 | in | bundled fonts (Inter, JetBrains Mono TTF), PNG icon masks, app icon read from the package assets at start | no | no version recorded |
| SHL-E13 | gui/main_window.py:1857-1874 | in | drag-and-drop of one project folder opens it | welcome text | n/a |
| SHL-E14 | grid_view.py (Part B), noted here | in/out | clipboard text with tabs (copy/paste of cells) | tooltip | none |
| SHL-E15 | gui/app.py:62-80 | in/out | `--self-test`, `--smoke`, `argv[0]` project folder | `--help` unverified | n/a |
| SHL-E16 | gui/status_bar.py:34-36 | claim | "Offline" label: no network connections, no telemetry; consistent with `help_view.py` (`setOpenExternalLinks(False)`) and no network imports found in budget_gui | tooltip | n/a |
| SHL-E17 | gui/reports_view.py:383 (Part B) | out | `QDesktopServices.openUrl` file URL to open the export folder in the OS file manager | button label | n/a |

### Already good
- Source field on every standards-like number (`Sourced`: value/source/note, `budget_core/model/base.py:131-141`) and the placeholder state `source: TBD` rendered as dashed "TBD" cells plus the "Not checked" class and status-bar count (`problem_class.py`, `grid_models.py:598-683`, D-150).
- Inputs grid lists every sourced number with value, unit and source (`grid_models.py:608-700`), filter and "Placeholders only" (`model_pages.py:410-420`).
- Equation registry and constants with sources, rendered into the guide chapter "Equations and sources", including the open project's sourced numbers and PLACEHOLDER flags (`guide/build.py:60-186`, `equations.py`).
- Provenance block (tool, versions of 9 libraries, project, revision, scenario, UTC time, user) on every export, reproducible via `SOURCE_DATE_EPOCH`/`BUDGET_USER`; shown in the Provenance dock and on the Reports page.
- Save safety: SHA-256 stamp check refuses to overwrite a file changed on disk (`model_document.py:398-404`, `editor.py:83-107`); comment-preserving patch save (D-103); confirmation before deleting files; atomic writes.
- Last-good results kept on screen with a "stale" banner after a failed load (`session.py:137-248`, `main_window.py:1399-1427`).
- Undo/redo of every grid edit, add and remove as single steps with names (`model_document.py`), tooltips naming the step.
- Problems messages carry code, file, field path, line; double-click jumps to the YAML line (`problems_panel.py`, `main_window.py:1593-1595`); Problems classes have icon + word + tooltip explanation.
- Loader warns about ignored files/folders and unknown config names (`project_loader.py:396-410`).
- Strict privacy design: layout.ini limited to four groups, only UI words; no network; documented (D-105, D-150, `use-the-window.md:104,143`).
- Forms refuse invented numbers: orbit/site/expendable numbers start empty; sourced link numbers written as `TBD` placeholders (`new_link.py:134-160`, `add_*_dialog.py` docstrings).
- Remove-item blocks removals that would dangle references and names the users (`remove_item.py:78-106`).
- CLI exposes `--user` / `--date` for reproducible provenance (`docs/user-manual/command-line.md:33-34`).

### Notes for the plan
- Golden files / byte-identical outputs: provenance rows (`Provenance.rows()`, `provenance.py:40-49`) are embedded in every export; adding rows (input hashes, run parameters) changes goldens and `export-examples` (CLAUDE.md: tests fail on drift). Add behind a schema/version bump or regenerate goldens deliberately.
- Privacy constraints are tested: CLAUDE.md rules "Problems/messages never contain values read from project files" and "no project content in logs, temp files outside the project folder" conflict with a glass-box Inspector that wants to show values/derivations. Needs a deliberate carve-out (values shown in widgets are fine; messages/logs/layout.ini are not). `layout_settings.py:63-66` raises on any key outside four groups, so any per-project or engineering setting needs a new place (project folder file), not layout.ini.
- A change log needs an owner decision on location: the only persistable place is the project folder (rule: no state outside it). Save path is `ModelDocument.save` (`model_document.py:381`); the unit-table import (`io/unit_table.py:578`) and the text editor (`editor.py:100`) write files by two other paths, so a change record must hook all three, or the import should go through the Document.
- Overrides need a model change: `Sourced`-like wrapper with reason, and schema version bump plus a migration (CLAUDE.md "Schema changes need a version bump and a migration"); regenerate `schemas/` and examples.
- Stale/up-to-date semantics (B01-B03) are spread over `timeline_view.py`, `scenario_view.py`, `link_view.py` (Part B) and `run_controller.py`; changing to a content-hash key must touch all, and `ResultKey` (`timeline_view.py:289`) is the place to extend.
- Tests assert the window defaults (`tests/gui/conftest.py` starts in full view; `test_focused_view.py` tests the default); making Inspector/Provenance visible by default changes those tests (D-191 is an owner decision).
- Theme rule: a test fails on pixel sizes/hex colours outside `budget_gui/theme/`; any new panel must take sizes from the scales.
- Fixed form limits live in core (`wizard.py`, `new_*.py`) shared with the CLI/headless guided mode and the examples; making them project/config-driven affects `budget wizard`-like entry points and tests using `MAX_DAYS` (grep `MAX_DAYS` also used in `guided.py:31,166`).
- Part B overlap: grids (`grid_models.py`, `grid_view.py`, `delegates.py`), scenario editor `MAX_SECONDS=10_000_000` (`scenario_editor.py:45`), timeline/link views and reports page were not audited here beyond the lines cited.

## Appendix H — Window: result views, grids and plots

Scope: `src/budget_gui` result and editing views (power timeline, link passes, scenario view and editor, static budget views `widgets.py`, compare, reports page, grids/models/delegates, YAML editor, unit table, plot widget and plot preparation, cell legend, number formatting), plus the core code those views render verbatim (`budget_core/plots/*`, `reports/document.py`, `reports/numfmt.py`, `reports/*_report.py`, `compare.py`) because the window shows "exactly what the reports contain" (`widgets.py:72`). Line numbers verified by reading. Part A files (main_window, session, panels, settings, inspector) not audited, only referenced.

### Summary
- Counts: A = 41 items (GV-A01..A41), B = 24 (GV-B01..B24), C = 22 (GV-C01..C22), D = 17 (GV-D01..D17), E = 12 (GV-E01..E12).
- Top 5 gaps:
  1. No view shows an equation, inputs or intermediate values behind a number. The only equations/inputs list is the "Assumptions" tab of the 4 static budget views. The power timeline, link passes, scenario, compare and plots have no assumptions/equations at all. Nothing is clickable from a result cell to its inputs (GV-C01, C02, C03).
  2. Verdict thresholds and colours are fixed in code and not explained in the view. Examples: the GUI FAIL test `balance_wh < 0` (timeline_view.py:699) differs from the core tolerance `-ENERGY_TOL_WH`. `STATUS_WORDS` maps "margin" to NEAR with no value shown. The "Minimum allowed" DoD line appears only after a DoD violation (power.py:274) (GV-A09..A14, C07, C08).
  3. Run options and definitions are not shown in the window. The load basis (nominal/margined), mission phase, shadow model, step, BOL/EOL definition and orbit definition are written into the export (`timeline_report._facts`) but not shown in the timeline window. BOL/EOL are fixed names and always both solved (GV-B01, B02, D01, C09).
  4. Units: plot readout/tick labels carry no unit. Units in grids are implicit by field-name suffix (typed plain number = canonical unit). Mixed Mbit / MByte / "T+" bases. Unit-level mass and power inputs have no source field and are not in any Assumptions list (GV-C10..C14, B05, B06).
  5. Editing: no way to override a computed value, no justification or override flag, no change log beyond undo text. The scenario editor cannot edit start/duration/step/orbit/mission_phase (YAML only). Sourced-node shape is a closed set `{value, source, note}` (GV-D09..D12, C17).

### A. Constants, defaults, thresholds, rules
Visible = can the user see it in the window/reports. Editable = without editing code. "-" = none.

| ID | file:line | value | purpose | visible? | editable w/o code? | source stated? |
|---|---|---|---|---|---|---|
| GV-A01 | budget_gui/timeline_view.py:71-73 | `BASES=("nominal","margined")`, `CASE_NAMES=("bol","eol")`, `AXES` | fixed choice lists of the timeline view; default basis = first item "nominal" | combo items yes; meaning only in tooltip :155 | no (list) | no |
| GV-A02 | budget_core/power/time_domain.py:37 (used by timeline_view.py:122) | `CASES=("bol","eol")` | the only cases computed | name yes; definition only in export `timeline_report.py:50-51` | no | no |
| GV-A03 | budget_core/power/time_domain.py:46-51 | `RATIO_TOL=1e-9`, `POWER_TOL_W=1e-9`, `ENERGY_TOL_WH=1e-6`, `REFINE_TOL_S=1e-6`, `PENUMBRA_MIN_S=0.01`, `MAX_REFINE_ROUNDS=4` | pass/fail tolerances and grid refinement that decide what the Violations tab lists | no | no | comment only: "rounding noise" |
| GV-A04 | budget_core/power/time_domain.py:54-59 | 4 violation codes + `CODES_TEXT` | the only findings the Violations tab can show | text yes | no | no |
| GV-A05 | budget_gui/timeline_view.py:727 | `pad = max(0.5*duration, 300.0)` s | zoom window around a selected violation | no | no | no |
| GV-A06 | budget_gui/link_view.py:428 | `max(0.5*duration, 120.0)` s | zoom window around a selected pass | no | no | no |
| GV-A07 | budget_gui/plot_widget.py:61-66 `_number` | `>=1e6 or <0.01 -> .3g`; `>=1000 -> .0f`; else `.3f` stripped | number format of tick labels and cursor readout (3 significant digits at the extremes, no unit) | yes (implicitly) | no | no |
| GV-A08 | budget_gui/plot_widget.py:52-58, 334-338 | `_hms_full` rounds to 1 s; difference `:+.4g` (line 350) | cursor time and delta text, so sub-second data show the same time | yes | no | no |
| GV-A09 | budget_gui/timeline_view.py:633-640 | FAIL colour when `rows[r][9] != "0"` (string compare) and `unmet_wh > 0.0` | summary table verdict colouring; threshold 0.0 differs from core `POWER_TOL_W*scale` (time_domain.py:1005) | colour + icon | no | no |
| GV-A10 | budget_gui/timeline_view.py:698-700 | FAIL when `(balance_wh or 0) < 0` | Orbits tab colouring; core uses `balance_wh < -ENERGY_TOL_WH` (time_domain.py:1022), so a balance of -1e-7 Wh is red in the table but not a violation | colour + icon | no | no |
| GV-A11 | budget_gui/timeline_view.py:672 | every "Worst" cell FAIL | Violations table: the worst-value cell is always red | yes | no | no |
| GV-A12 | budget_gui/widgets.py:48-57 | `STATUS_WORDS` {ok, yes -> PASS; margin -> NEAR; exceeded, no -> FAIL; no limits, ok (margin not checked), n/a -> NOT_CHECKED} | maps the status words of the static tables to colours; unknown words get no state | yes (colour + tooltip generic) | no | no |
| GV-A13 | budget_core/thermal/static_thermal.py:109-111, 570-604 | status words `ok/exceeded/margin/no limits/n/a/ok (margin not checked)`; margin test `up < margin or down < margin` (strict) | thermal verdict; the required margin comes from config/thermal_environment.yaml (`temperature_margin_k`, line 278) | margin value NOT in the check table (`thermal_report.py:454-471` has no margin column) | margin value yes (config) | no |
| GV-A14 | budget_core/mass/static_mass.py:26, 243 | `LIMIT_TOLERANCE_RATIO=1e-9`; limit met within `1e-9*max(1,abs(limit))` counts as 0 margin / ok | mass limit verdict; no NEAR state for mass | no | no | comment "as in D-097" |
| GV-A15 | budget_gui/widgets.py:88-96 | bar share = value/limit; >1 = over | margin bar below the number (mass limits `bar=(3,2)` mass_report.py:201) | bar yes, rule no | no | no |
| GV-A16 | budget_gui/legend.py:273-301 | example shares 0.35 / 0.88 / 1.2; texts "Within / Near / Limit broken" | legend; "Near the limit" is "Inside the required margin" but no rule is stated | yes | no | no |
| GV-A17 | budget_gui/delegates.py:70-78 | generic tooltips "Within the limit." "Near the limit." "The limit is broken." | tooltips for status cells; no limit value, no rule | yes | no | no |
| GV-A18 | budget_gui/delegates.py:49-50 | `TOTAL_ROLE` and `SOURCE_ROLE` both `UserRole+23` | role collision; `SOURCE_ROLE` and `tooltip_for(status, source)` (delegates.py:251) are never fed a source (widgets.py:152-153 pass state only) | the source tooltip is dead code | - | - |
| GV-A19 | budget_core/reports/numfmt.py:16-17, 54-66 | half-up rounding on the shortest decimal repr; `GENERAL_DIGITS=10` | all displayed numbers in the budget views | partly (columns' decimals) | no | comment only |
| GV-A20 | budget_core/reports/power_report.py:108-112, 159, 161 | W 3 decimals; Duty 2 decimals; Margin `percent` with `decimals=3` -> `max(3-2,0)=1` decimal of percent (document.py:85) | display precision of the power budget; grid shows duty with 3 decimals (grid_models.py:382) | yes | no | no |
| GV-A21 | budget_core/reports/mass_report.py:139,143,173,234,267,285-286 | kg 3, m 4, CG coverage percent, inertia 5 decimals | mass budget precision | yes | no | no |
| GV-A22 | budget_core/reports/thermal_report.py:338, 369, 435-437, 459-463 | `ABSOLUTE_ZERO_OFFSET_K=273.15` (named so, is the Kelvin to Celsius offset); K 2 decimals; ratio 2; "below 0.000001 W" threshold literal 1e-6 | thermal precision and imbalance statement | yes | no | no |
| GV-A23 | budget_core/reports/link_report.py:25-46,99,135-159 | dB 2, elevation 1, range 1, kbit/s 3, Mbit 2 | link budget precision | yes | no | no |
| GV-A24 | budget_gui/grid_models.py:334,342,380-392,613,665 | decimals: mass 3, temperatures 2, powers/ratios 3, durations 1; sourced value shown `:g` (6 significant digits) | grid display rounding (tooltip has full value via `edit_text` `.12g`, line 60, and the unit, lines 259-262) | yes (tooltip) | no | no |
| GV-A25 | budget_gui/timeline_view.py:592-598, 605-615 | `num` 2 decimals (1 for Wh, 4 for Worst/Limit), `pct` 1 decimal, `*100` | timeline table precision | no | no | no |
| GV-A26 | budget_gui/scenario_view.py:411-435 | `.1f` seconds | eclipse/pass/timeline table precision | no | no | no |
| GV-A27 | budget_gui/link_view.py:399-403 | duration `.0f`, elevation `.1f`, usable `.0f`, margin/volume 2 decimals | link pass precision | no | no | no |
| GV-A28 | budget_gui/plot_widget.py:472 | `buckets = max(int(rect.width()), 50)` | plot decimation: one min/max pair per pixel column | no | no | comment D-147 |
| GV-A29 | budget_core/plots/envelope.py:32-33 | `BLOCK=64`, `BLOCKS_PER_BUCKET=2` | block summary size and the switch from samples to blocks | no | no | module text |
| GV-A30 | budget_core/plots/spec.py:72-81, 216 | time units switch at 600 s / 3 h / 3 d; y padding 0.06 of range; `nice_ticks(lo,hi,4)` (plot_widget.py:466,515) | axis scale choice and y range | no | no | no |
| GV-A31 | budget_core/plots/power.py:264-294 | panels Power (y_min 0), Battery (0..1, scale 100), Margin; series names; Peak limit, Minimum allowed (1-DoD limit), Zero lines | fixed plot layout | yes | no | no |
| GV-A32 | budget_core/plots/link.py:314-327, 393-396 | 12 `RATE_COLORS`; elevation panel fixed 0..90 deg; selected rate y_min 0 | link plot layout; colour cycles after 12 rates | yes | no | no |
| GV-A33 | budget_gui/time_axis.py:116-132, 227-230 | `UTC_STEPS_S` list, `MAX_TICKS=10`; orbit period = median of eclipse start spacing, needs >= 3 eclipses | axis ticks and orbit axis definition | tooltip :162 says "from the spacing of the eclipses" | no | no |
| GV-A34 | budget_gui/plot_widget.py:69, 252, 265, 620, 656 | `MARKER_MIN_WIDTH=3`, click gap 2.0 px, min view width 1.0 s, wheel factor 1.25, drag threshold 3 px | interaction constants (the 1.0 s minimum is data-relevant) | no | no | no |
| GV-A35 | budget_gui/timeline.py:28-48 | `TICK_STEPS`, `min_px=90` | scenario strip ticks | no | no | no |
| GV-A36 | budget_gui/scenario_editor.py:38-45, 84-92 | `RULE_KINDS` (3), `SHADOW_MODELS` (2), `MAX_SECONDS=10_000_000`, spin 1 decimal, seconds only | scenario editor choice lists and input limits | yes | no | no |
| GV-A37 | budget_gui/scenario_view.py:442 | `round(start,1)`, `round(end-start,1)` | a range dragged on the strip becomes a segment rounded to 0.1 s | no | no | no |
| GV-A38 | budget_core/compare.py:39-41 | `SKIP_SECTIONS={Problems, Provenance}`, `SKIP_TABLES={Equations}`, `DEFAULT_MAX_ROWS=200` | what the Compare tab leaves out/truncates | truncation stated in status (compare_view.py:291-292), the skips not | no | no |
| GV-A39 | budget_gui/grid_view.py:50-53 | `PREVIEW_ROWS=200`, `FIT_ROWS=80`, `MAX_COLUMN=300`, `SHOWN_PROBLEMS=3` | paste-preview cap, problems shown | partly | no | no |
| GV-A40 | budget_core/wizard.py:34-38, 133-138; new_scenario.py:35-36,220-222,263 | wizard defaults: eccentricity 0.001, arg. of perigee 90 deg, mean anomaly 0, `MAX_STEPS=8640`, `MAX_STEP_S=600`, `MIN_STEP_S=10`, `MAX_DAYS=180`, spherical `EARTH_RADIUS` (WGS-84 equatorial) for a=R+h | values written into a new orbit/scenario by the Add scenario dialog | written to the YAML (editable), the dialog does not list them | yes (YAML) | comments only |
| GV-A41 | budget_core/environment/constants.py:23-39 | WGS-84 radius/mu/flattening (via sgp4), IAU solar radius, AU | physical constants; each has a `source` | NOT shown in any view/Assumptions list; not selectable | no | yes (in code) |

### B. Hidden assumptions

| ID | file:line | assumption / behaviour | documented where? |
|---|---|---|---|
| GV-B01 | timeline_view.py:5-6, 157, 259 | BOL and EOL are always both solved; the case combo only changes what is shown (also violations list `v.case in (case,"",None)`, :545) | docstring only; the BOL/EOL definition ("no degradation" / "design life applied to both") only in the export (timeline_report.py:50-51) |
| GV-B02 | timeline_view.py:152-157, 290; power.py:249-253 | the demand basis (nominal/margined), mission phase (selects the DoD limit via `scenario.mission_phase`, model/environment.py:185) and shadow model are not shown anywhere in the timeline window or its plot title | export paragraph `_facts` (timeline_report.py:40-52), `note` at :129 |
| GV-B03 | power.py:274 | the "Minimum allowed" SoC line is taken from the violations, so it is absent from the plot while no DoD violation exists; limit visible only in failure | not documented |
| GV-B04 | power.py:269 | "Peak limit" line drawn only if `result.peak_limit_w is not None` | not documented |
| GV-B05 | grid_models.py:46-48, 261; entry.py:12-19; quantity.py:97-112 | unit convention = last `_suffix` of the field name; a plain number typed in a cell is in the canonical unit; a number with a unit ("800 mW") is converted by the model; the cell then shows the converted value, the typed unit is lost | header `[unit]` and tooltip; rule not stated in the UI (entry.py docstring only) |
| GV-B06 | grid_models.py:649-652 | the "unit" column of the Inputs grid is derived from the last string in the path, "" when there is no suffix | none |
| GV-B07 | grid_models.py:575-581 | a "sourced" node is recognised only when its keys are a subset of `{value, source, note}`; nodes with other keys are silently not listed in the Inputs grid | none |
| GV-B08 | grid_models.py:626 | the Inputs grid covers only `config/` and `links/`; not spacecraft.yaml, orbits, sites, units (mass, powers), scenarios | grid title only |
| GV-B09 | grid_models.py:158-159, 240-241 | missing optional value is drawn as "n/a" (not checked), a missing non-optional is "" (empty) | column tips (`absent_tip`), legend |
| GV-B10 | grid_models.py:64-72 | `parse_cell`: empty optional cell removes the field; an emptied required numeric becomes "" and is refused by the model | tooltip/message |
| GV-B11 | grid_view.py:340-341, 447 | paste writes the typed text through the same unit parser; a paste only lists cells whose text differs; pasted source of units is the clipboard (no provenance) | paste preview |
| GV-B12 | timeline_view.py:477-483 | hover readout: mode = last timeline segment that started at or before t; eclipse test inclusive `start<=t<=end`; UTC = start + `round(t)` s | none |
| GV-B13 | plot_widget.py:334-352; spec.py:184-197 | readout of a step series holds the value, a line series (SoC) is linearly interpolated between edges; value outside series is skipped | none |
| GV-B14 | envelope.py (module text), plot_widget.py:476-500 | zoomed-out plots are drawn from a min/max envelope (pairs of vertical lines), so the visual order of extremes inside a pixel is lost; readout uses full-resolution values | module docstring |
| GV-B15 | timeline_view.py:521-533 vs time_domain.py / power/orbits.py:1-12 | two different definitions of "orbit": the Orbits table uses windows from the angle in the orbit plane (revolutions from the start angle); the plot "Orbit" axis uses the median spacing of eclipse starts (time_axis.py:224-230), needing >= 3 eclipses | tooltip of the axis only |
| GV-B16 | scenario_editor.py:210, 214; scenario_view.py (editor) | rule order: later rule wins; manual segments applied last; segment order does not matter | row title/tooltip text (yes, shown) |
| GV-B17 | scenario_editor.py:345 | a missing `shadow_model` is shown as "cylindrical" (the model default) without saying it is a default | none |
| GV-B18 | model_document.py:381-436 | Save validates every changed file and refuses all saves if any is invalid; checks disk change by SHA-256 of bytes (roundtrip.py:45-46) | message text |
| GV-B19 | compare.py:5-11, 145-157 | only values that differ *as displayed* are changes (changes below the display precision are invisible); change and % computed from exact values; "now computed/now n/a" for None | module docstring; not in the window |
| GV-B20 | compare_run.py:70-74 | comparing two scenarios of the same project compares only the scenario results (timeline, link-passes); the static budgets are compared only against another project folder; the timeline of a compare uses default `load_basis` (compare_run.py:93) | status text when nothing to compare |
| GV-B21 | link_view.py:327, 410, 417; link_report.py:139 | data volume uses decimal prefixes: Mbit = bits/1e6, MByte = bits/8e6; the link pass "Lowest margin" is at the lowest listed rate over active samples (link_report.py:175 note) | note in export only |
| GV-B22 | widgets.py:157-211 | budget tables are created lazily when the sheet is first shown; widths from the first 60 rows; table height fixed (no scroll) | comment |
| GV-B23 | scenario_view.py:358-364 | the scenario summary line shows eclipse count and passes per site, plus run notes and problems messages | n/a |
| GV-B24 | reports_view.py:47, 196-198 | the Reports page shows 6 of the 8 provenance rows (Python and Libraries are filtered out) while it says "Every file carries the provenance below" | none |

### C. Outputs without a visible derivation
What each view offers today (equation / inputs with units / intermediates / source):

| ID | where the user sees it | what is shown today / what is missing |
|---|---|---|
| GV-C01 | Static budget views (widgets.py PowerView: power, mass, thermal, link) | Shown: report tables, the table `note` (e.g. "Average = sum of unit power x duty cycle", power_report.py:144), tab "Assumptions" with "Configuration numbers used" (name, value 10 sig. digits, unit, source, sourced/PLACEHOLDER) and an "Equations" table (id, name, formula, source text) - the best offer in the product. Missing: link from a result cell to the equation or to the inputs that produced it; the file/path of each assumption (the `Assumption` has `file`/`path`, assumptions.py:15-21, but common.py:68-79 drops them); per-cell tooltips (header text only, widgets.py:111-112). |
| GV-C02 | Power timeline view (timeline_view.py) | Tabs Summary/Violations/Orbits/Modes + plot. Missing: Assumptions/Equations/Facts tab (the export has them: closing_sections + `_facts`, timeline_report.py:40-52, 256-262; the window only counts placeholders, :431); no tooltips on any table cell (fill_table sets none, scenario_view.py:94-124); headers give units only. |
| GV-C03 | Link passes view, Scenario view tables, Compare tab | Link: pass and volume tables, no link budget line items, no elevation mask or Eb/N0 required shown, no assumptions. Scenario: eclipse/pass/timeline tables with start/end/duration only; no eclipse model parameters, no elevation mask, no step. Compare: values as strings, no derivation, no tooltip with exact values (compare_view.py:343-366). |
| GV-C04 | Plot series (all plots) | Series label + panel y-label only. No equation, no input list, no definition of "Generation"/"Demand at source"/"Margin" in the window. Cursor readout lists label + value (3 decimals) without unit (plot_widget.py:346). |
| GV-C05 | Plot hover readout | `value_at`: sample/hold or interpolated value at the cursor; step series hold. Missing: unit, which equation, which basis/case (the plot title has only the case: power.py:296). |
| GV-C06 | Status colours in budget tables (PASS/NEAR/FAIL/NOT_CHECKED) | Icon + colour + generic tooltip text (delegates.py:70-78). Missing: the limit, the margin, the rule (e.g. "margin" means closer than temperature_margin_k to a limit; the margin value is not displayed). |
| GV-C07 | Thermal "Unit temperature limits" table | Shows temperature, lower/upper limit, headrooms, status; missing: the required margin used, the limit set's source (header says only `limit_set`), the node temperature derivation (only the final solve residual "below 0.000001 W", thermal_report.py:437). |
| GV-C08 | Timeline Violations table | Shown: case, finding text, from/to, duration, worst, limit, unit, input file:path (good: link to the source); double-click opens the input. Missing: the equation behind "worst" (e.g. SoC or demand-minus-generation), the tolerance (`RATIO_TOL` etc.), and for "ORBIT_BALANCE_NEGATIVE" what an orbit is. |
| GV-C09 | Timeline Summary table | Capacity (Wh), avg generation/demand, generated/demanded Wh, lowest SoC %, deepest DoD %, unmet Wh, violation count per case. Missing: basis of demand, battery capacity BOL vs EOL derivation, array degradation, DoD limit and where it comes from, the not-evaluated checks list (only in the status tooltip, timeline_view.py:443). |
| GV-C10 | Timeline Orbits table | Eclipse (s), generated, demanded, balance, stored change (Wh). Missing: how an orbit window is defined (orbits.py), how energy is integrated (`dt` weighted sums, time_domain.py:1110-1114), refinement of edges. |
| GV-C11 | Timeline Modes table | `Share (%) = duration/total*100` (timeline_view.py:710), Load, Demand at source, Peak at source (W). Missing: equation of load (avg x duty), conversion to source side (converter efficiency of which bus), margin application when basis = margined. |
| GV-C12 | Grid cells (units, power modes, spacecraft modes, inputs) | Header `[unit]`, column tooltip, cell tooltip with exact value + unit; computed column "average x duty [W]" (grid_models.py:393, 423-439) with tooltip "Average power times duty cycle". Missing: source of mass_kg / powers / temperature limits (the unit file has no source field: model/equipment.py:15-30, 90-103); maturity -> margin % not shown next to the unit. |
| GV-C13 | Inputs grid (Inputs page) | Shows value, derived unit, source, note, placeholder state: a real source/provenance view for the config and link numbers. Missing: where each is used, equation using it, version/date of the source, valid range. |
| GV-C14 | Reports page | Lists items + status + formats + provenance summary line; details toggle shows 6 of 8 rows. Missing: list of the sheets/tables in a file, the load basis, the case, the numeric format rule, input file hashes (Provenance has none: provenance.py:38-48). |
| GV-C15 | Scenario view status line | Counts eclipses/passes + notes/problems (scenario_view.py:358-364). Missing: shadow model, step and propagation method used, epoch frame/time system, elevation mask. |
| GV-C16 | Scenario timeline strips (timeline.py) | Eclipse (penumbra) and umbra bars, passes per site, mode bar with colour by position in sorted mode list (timeline.py:60-63). Missing: legend for sunlight/eclipse/umbra, mode-colour key, how a mode segment was decided (which rule/segment won). |
| GV-C17 | Scenario "Mode timeline" table | Start/End/Duration/Mode only; the rule or segment that produced each interval is not shown (the "later rule wins" result is invisible). |
| GV-C18 | Link plot | margin per listed rate, required margin line, selected rate, elevation. Missing: link equation terms, which losses, pointing, atmosphere models, `required_margin_db` source. |
| GV-C19 | Compare table | "Change (%)" relative to \|A\| (numfmt.py:32-37), pp for percent columns (compare.py:136); only displayed-difference changes. Missing: statement of tolerance rule, the unlisted differences beyond 200 rows (stated in count only), why a value changed (which input differs). |
| GV-C20 | Placeholder/`n/a` cells | Tooltip "n/a: this result depends on an input that is a placeholder or missing" (delegates.py:73-74) but not *which* input; the Problems panel (part A) holds it. |
| GV-C21 | "Not evaluated" checks (timeline) | Count in status line, full text in status tooltip (timeline_view.py:437-443). Not in a table. |
| GV-C22 | Mass/inertia/CG tables | CG coverage %, inertia tensor with note on sign convention (mass_report.py:289-290). Missing: the parallel-axis/aggregation equations in the window (they are in the Equations table, `MASS-` prefix), inputs per item that lack a position. |

### D. Forced options

| ID | file:line | the fixed choice | plausible alternatives |
|---|---|---|---|
| GV-D01 | timeline_view.py:71-73, 157; time_domain.py:37 | cases BOL and EOL only, both always computed | user-defined cases (mid-life, specific degradation, temperature), selecting a subset to speed up |
| GV-D02 | timeline_view.py:71, 109 | demand basis `nominal` or `margined` (margin = unit+system); average-power based (duty-weighted) | peak-based demand, per-unit margin on/off, separate margins for sizing vs verification |
| GV-D03 | plot_widget.py:472; envelope.py:32-33 | decimation to min/max per pixel column; block 64 | show raw samples, user-set decimation, LTTB, export the plotted series |
| GV-D04 | spec.py:72-81 | time units switch at 600 s / 3 h / 3 d | fixed unit chosen by user |
| GV-D05 | power.py:264-294 | three fixed panels; SoC 0..100 % fixed | user-selectable series/panels, absolute Wh, log scale |
| GV-D06 | timeline_view.py:73, time_axis.py | 3 time axes (Elapsed, UTC, Orbit) | MET with day count, local solar time, per-orbit fraction |
| GV-D07 | scenario_editor.py:38, 40-44 | 3 rule kinds (during pass, eclipse, sunlight) | rules on elevation/occultation, time windows, mode transitions/duration limits (min/max_duration_s exist in the unit grid but not in rules) |
| GV-D08 | scenario_editor.py:39 | shadow model `cylindrical` or `conical` | with penumbra grading, refraction/oblateness, albedo |
| GV-D09 | scenario_editor.py (whole) | the editor edits only default_mode, shadow_model, sites, rules, segments | start/duration/step/orbit/mission_phase/environment_source editing in the GUI (YAML only today) |
| GV-D10 | grid_models.py:575-581 | sourced node = `{value, source, note}` only; source is free text, only `TBD` is special (is_placeholder, :598-605) | structured source (document id, revision, page), retrieval date, status (verified/estimated), justification for overrides |
| GV-D11 | grid_models.py:325-347, 374-394 | units grid: mass and temperature limits; power modes grid: avg/peak/duty/heat ratio/min/max duration | CoG/inertia (`mass_properties`), phases, thermal node, per-item margin override, uncertainty |
| GV-D12 | grid_view.py (whole), widgets.py | computed values are read-only everywhere (budget tables, "average x duty" column) | override with flag and justification |
| GV-D13 | compare.py:39-41,145-157 | compare by displayed precision, 200 rows, skipping Problems/Provenance/Equations | tolerance chosen by the user, full list, compare of assumptions/equations |
| GV-D14 | reports/run.py:48; reports_view.py:40-46 | five formats; one bundle per run | per-table selection, template, language/number format (decimal comma), units system |
| GV-D15 | reports/numfmt.py:16-17, 54-66 | one rounding rule (half up) and per-column decimals | show significant digits, user precision, scientific notation |
| GV-D16 | link_view.py:327, 410, 417 | decimal Mbit / MByte (1e6, 8e6) | Mibit / MiB, kbit, GB |
| GV-D17 | wizard.py:34-38; new_scenario.py:220 | wizard orbit defaults (e=0.001, w=90 deg, M=0) and spherical radius for altitude to a | choose Keplerian elements, TLE, Earth model |

### E. Interfaces

| ID | file:line | direction | what / format | user told? | provenance? |
|---|---|---|---|---|---|
| GV-E01 | editor.py:68-81, 100-112 | in/out | project YAML files read as bytes; saved atomically (`write_bytes_atomic`), BOM and CRLF kept | tab title `*` when modified; "changed on disk" check | SHA-256 stamp of bytes in memory (roundtrip.py:45), not stored |
| GV-E02 | model_document.py:381-436 | out | Save writes changed/added files, deletes removed ones (`unlink`), via `save_edited_data` (checked against the model) | yes (messages) | none (no changelog, undo text only) |
| GV-E03 | unit_table.py:71-93, 96-139 | out/in | export `unit_power_modes.csv` (UTF-8 BOM) or `.xlsx`; import of csv/xlsx with preview of old -> new (`:g`, 6 significant digits, line 56) and confirmation | yes (preview) | file name is passed to the plan (`path.name`); no hash |
| GV-E04 | grid_view.py:298-312, 359-380 | in/out | system clipboard: tab-separated text, copy uses the exact edit text (`.12g`), paste goes through the unit parser | message "Copied n cells / Pasted n cells" | none |
| GV-E05 | timeline_view.py:761-786; link_view.py:452-477; compare_view.py:389-412 | out | folder chosen in a dialog; files xlsx/pdf/docx/json/csv from `write_outputs` | list of files in the Reports page; toast/status | provenance table inside each file (tool, version, Python, libraries, project, revision, scenario, time, user: provenance.py:50-61); no input hash |
| GV-E06 | reports_view.py:295-334, 379-383 | out | Reports page: items x formats, folder; "Show the folder" opens the system file manager (`QDesktopServices.openUrl`) | yes | as E05 |
| GV-E07 | compare_view.py:61-80 | in | reads another project folder (`load_project`) | yes (path field) | its name+revision are shown (side B label, :334-339), not its content hash |
| GV-E08 | scenario_view.py:445-456 | out | `write_scenario_outputs` to a folder | yes | provenance object |
| GV-E09 | provenance.py:75-113 (used by every export) | in | environment variables `SOURCE_DATE_EPOCH`, `BUDGET_USER`, OS account name (`getpass`) shape the exported time and user | not shown in the window | it is the provenance |
| GV-E10 | help_view.py:76-81 | out | user guide written as HTML and PDF to a folder chosen by the user | yes | n/a |
| GV-E11 | privacy.py:14-26 | in/out | QSettings is redirected to an unwritable path so nothing is persisted by Qt | no (internal) | n/a |
| GV-E12 | icons.py, theme/fonts.py (not read in detail, unverified) | in | icon and font assets read at run time | no | no |

### Already good
- Static budget views have an "Assumptions" tab with name/value/unit/source/status and an Equations table (common.py:67-91; widgets.py shows every `Section`).
- The window shows the same tables the reports contain (DocTableModel, widgets.py:72), so GUI and export cannot disagree on numbers.
- Placeholder/`n/a` handling: a missing or `TBD` input never becomes 0; "n/a" has a distinct style and tooltip; INCOMPLETE banner (common.py:14-18; legend.py:290-299; delegates.py).
- Grid cells show header `[unit]`, exact value and unit in the tooltip (grid_models.py:259-263), the unit parser accepts typed units, decimal comma is explained (grid_models.py:217-218), Save refuses invalid data and disk-changed files.
- Violations table gives limit, worst value, unit and the input file:path, double-click jumps to it (timeline_view.py:644-673, 734-738); "not evaluated" checks are listed, so absence of a violation is not read as a pass (timeline_view.py:436-443).
- Stale-result protection: `ResultKey` + STALE text; exports disabled for stale results (validity.py).
- Inputs grid lists every sourced number with source and note, with a "Placeholders only" filter and a count (model_pages.py:409-457).
- Cell-state legend drawn by the same delegate as the tables (legend.py).
- Plot readout uses full-resolution values (not the decimated ones); a pinned cursor shows differences; a legend click hides/solos series.
- Cell edits are one undo step each with a named step; paste shows old/new before applying (grid_view.py:73-120).
- Compare lists added/removed/now n/a, states truncation, exports every difference to CSV/JSON (compare.py module text).
- The export `_facts` paragraphs (timeline_report.py:40-52) already contain basis, shadow model, step, BOL/EOL definition and eclipse fraction: reuse in the window.

### Notes for the plan
- The window renders `ReportDocument` tables verbatim; adding a column or table to `*_report.py` changes xlsx/pdf/docx/json/csv outputs (byte-identical regeneration with `SOURCE_DATE_EPOCH`, golden/drift tests) and the compare keys (compare.py matches by table title, row key columns and column header, so new columns appear as "added" columns). Window-only data can use the existing window-only fields (`status_column`, `status_marks`, `bar`, document.py:36-43).
- Constraint in CLAUDE.md: problems/messages never contain values read from project files. Derivation text with numbers should be a view (tooltip/side panel), not a Problem message.
- Schema changes need a version bump and a migration: adding `source` to unit mass/power, `justification`/`override` to sourced nodes, or widening `is_sourced` (grid_models.py:575) touches model/schema/examples (`export-schemas`, `export-examples --force`).
- GUI rules: no hex colours/fonts/pixel sizes outside `budget_gui/theme/`; nothing > ~50 ms on the GUI thread (tables of long timelines are filled in steps, timeline_view.py:410-445); work in workers (`plot_prepare.py`); the default "focused view" hides Inspector and Provenance (D-191), so derivation panels there need the reveal rule.
- `plot_widget` caches the painted layer by a key (plot_widget.py:389-401): any change in what is drawn (units in labels, extra lines) must be part of the key.
- Two definitions of "orbit" (GV-B15) and two sets of tolerances (GV-A09/A10 vs core) should be unified before explaining them to the user.
- The `Assumption` object already has `file` and `path`; exposing them is a report change (common.py:68-79). Physical constants (`constants.py:23-39`) are not in `Assumption`s, so adding them changes the assumptions tables of every report.
- Fixed collision `SOURCE_ROLE == TOTAL_ROLE` (delegates.py:49-50) must be resolved before using `SOURCE_ROLE` for cell sources.
- Behaviour-sensitive: the timeline `basis_combo` is part of `ResultKey` options (timeline_view.py:290); adding more options (cases, tolerances) means extending the key or results go stale silently.
