# Pre-release audit: findings list

Status: **Fixed.** The findings below are the report as approved on 2026-10-12. Every critical and high finding and nearly every medium and low finding is fixed, in four pull requests: [#17](https://github.com/0h3xn4/systembudgetstudio/pull/17) (window), [#18](https://github.com/0h3xn4/systembudgetstudio/pull/18) (loader, validation, command line, wizard, units), [#19](https://github.com/0h3xn4/systembudgetstudio/pull/19) (reports and output) and [#20](https://github.com/0h3xn4/systembudgetstudio/pull/20) (solvers and environment). Release preparation ([#21](https://github.com/0h3xn4/systembudgetstudio/pull/21): licence, the owner's confirmations, version 1.0.0), the window freeze on opening a project ([#22](https://github.com/0h3xn4/systembudgetstudio/pull/22), D-142) and the release workflow that attaches the installers ([#23](https://github.com/0h3xn4/systembudgetstudio/pull/23), [#24](https://github.com/0h3xn4/systembudgetstudio/pull/24), D-144) followed. **Version 1.0.0 was released on 2026-10-12**; the installers, the checksum lists, the SBOM and the licence report are attached to the [release](https://github.com/0h3xn4/systembudgetstudio/releases/tag/v1.0.0). The sections below keep the original wording of each finding; this section says what became of it.


## Resolution

Every fix has a regression test that fails on the old code (about 640 new tests; the suite went from 1151 to 1790+ tests).

| Findings | Status | Where |
|---|---|---|
| GUI-1, GUI-2 (critical) | Fixed | #17 |
| GUI-3 to GUI-7, GUI-9 to GUI-12 (high) | Fixed | #17 |
| GUI-8, GUI-13, GUI-15 to GUI-27, GUI-30 to GUI-34 | Fixed | #17 |
| GUI-14 | **Fixed.** Export output is built in the worker thread (#17); loading and reloading a project runs in a background thread and showing the tables is cheaper (D-142): the longest freeze on opening the 200-unit project went from about 3.6 s to about 0.5 s. | #17, then the load-in-background PR |
| GUI-28, mouse-only plot (GUI-29), GUI-35 (layout) | **Not done / partly.** Hover repaint speed of a 600,000-point plot, keyboard access to the plot, and three small layout items. | |
| PWR-1 (high) | Fixed | #20 |
| PWR-2 to PWR-12 | Fixed (PWR-10 in #20 for the wording and in the release-preparation PR for the validation warning `SCENARIO_PHASE_NO_DOD`) | #20 |
| RC-1, RC-3, RC-16, RC-22, RC-23, LD-1, LD-2 | Fixed | #18 |
| RC-15 | **Fixed.** A non-UTF-8 console no longer turns a finished run into "Internal error" (#18); error text now goes to standard error and results stay on standard output, with `budget validate` as the documented exception (D-145). | #18, then the standard-error PR |
| RC-2, RC-4 to RC-6, RC-8 to RC-14, RC-17 to RC-21, RC-24, RC-25 | Fixed | #19 |
| RC-7 | Fixed | #20 |
| TL-2, TL-3, TL-16 | Fixed | #19 |
| TL-1, TL-4 to TL-9, TL-11 to TL-14, TL-17 | Fixed | #20 |
| TL-10, TL-15 | Fixed | #18, #20 |
| MI-1 to MI-4 (high) | Fixed | #18 |
| MI-10 | Fixed | #17 |
| MI-11 to MI-15, MI-19, MI-20 | Fixed | #18 |
| MI-17 | **Partly.** Ranges, duplicate entries, whitespace names, survival-band and ignored-option warnings are done. Not done: `all` as a phase name, plausibility limits for power-model numbers. | #18 |
| MI-5 to MI-9, MI-16 | Fixed | #20 (MI-8 also #18) |
| MI-18 | **Deferred.** Frozen models are shallow (a list inside can be changed in code). No user path reaches it; nothing in the tool relies on it. | |
| PK-1 (package description) | Fixed | release preparation |
| Eclipses shorter than 20 s | **Fixed after the release** (D-146, DV-E4). Passes and, now, eclipses and umbras of any length are found; the regression test uses an orbit with an 11.6 s eclipse that the 20 s grid missed at some phases. | the short-eclipse PR |

### Your decisions of 2026-10-12

1. Step independence of passes and link samples: **fixed** (D-130). 2. Problem messages: **strict**, names are never in the text (D-121). 3. Rounding: **half up** in every format (D-110). 4. Qt dialog history: **suppressed** (D-105). 5. Partial link results: **independent terms** (D-134). 6. Ids: **warnings** for unusual ids, an error only for ids that cannot work (D-120). 7. TLE age: **30 days** (D-133). 8. Dates: **1950 to 2100** (D-124, D-133). 9. Licence: **MIT, public repository** (D-140); the eight "owner to confirm" decisions **confirmed** (D-141); tagging stays with you.


## How this was done

- Every module of `budget_core`, `budget_cli` and `budget_gui` was read by one of five area auditors (power/mass, GUI, thermal/link/compare, model/io/environment/scenario, reports/plots/CLI/guide). Each ran the code with normal, edge and deliberately bad inputs.
- I did the packaging, install scripts, dependency and wheel checks, the CLI and wizard fuzzing, and a mutation spot-check of the tests myself.
- The full suite (1151 tests) passes with warnings treated as errors. `ruff`, `ruff format --check` and `mypy` are clean (static hygiene scans found no `print` debugging, `TODO` hacks or dead imports).
- **Verified** means I re-ran the reproduction myself. **Agent-reproduced** means the area auditor ran it and quoted the result, and I have not re-run it. **By code reading** means no run.
- Limits of this audit: I ran as root, so read-only-directory failures are checked by reading code only. No Windows run, no Excel, no real display (GUI checks use the offscreen platform). The Windows installer and the Rocky 8 build are not exercised here (CI covers them).

## Verdict at the time of the report (superseded by Phase 5 below)

The numerical core is sound where checked by hand (link equations, orbit balance, battery integration, mass properties, thermal energy balance, pass bookkeeping, determinism). **I do not consider the tools releasable yet.** Two GUI bugs silently corrupt or misdirect saved project files (GUI-1, GUI-2), several GUI paths lose edits or export stale results, `link-passes` can hide a failed link, and the loader can hang or raise on hostile or odd YAML. All of those are small, local fixes. Details and counts are below.

| Severity | Count |
|---|---|
| Critical | 2 |
| High | 14 |
| Medium | about 50 |
| Low | about 70 |

## Decisions asked of you (answered, see the Resolution)

These fixes change results, message wording or accepted input, so I will not decide them silently:

1. **Step-independence of passes, link samples and eclipses** (TL-5, TL-6/MI-7). Fixing it changes reported link volumes and lowest margins (today: 21720 Mbit at 1 s vs 18928 at 120 s vs 22668 at 300 s). Goldens would change. Fix, or only document the limit and warn?
2. **Problem messages** (MI-4, TL-15). The rule says only field names, ids and units. Today messages also contain free-text names (phase, case, class, surface). Removing them is safe but makes some messages less specific. Strict rule or allow names that are map keys?
3. **Rounding** (RC-8). Making all formats round half-up changes displayed numbers in PDF, DOCX and CSV in a few cases (0.125 → 0.13), so some goldens change.
4. **Qt file-dialog history** (GUI-8). Qt writes the last-used folders to `~/.config/QtProject.conf` (Windows: registry). Is that acceptable, or do you want it suppressed? Suppressing means dialogs forget the last folder.
5. **Partial link results** (TL-4). Compute path loss, EIRP and G/T when only the required margin is a placeholder? This shows more numbers while the INCOMPLETE banner stays. Your rule is "only results that need the placeholder go n/a", so I read this as a bug, but it is a visible change.
6. **Ids from file names** (MI-12). Enforcing `[A-Za-z0-9][A-Za-z0-9_-]*` could reject existing projects that use spaces. Warn or error?
7. **TLE age warning threshold** (MI-9). What age is "stale" (30 days?).
8. **Dates** (MI-8). Allowed range for scenario start times (I suggest 1950 to 2100).
9. **Open owner items from before** (not audit findings): repository visibility and licence, real inputs and sources, open decisions D-043/D-048/D-054/D-072/D-078/D-059/D-064/DV-L2, tagging and who publishes `v0.1.0`.

Proposed fix order: critical, then high, then medium. I would do it in four PRs (GUI data loss and stale exports; loader and CLI robustness; reports and output correctness; solvers and validation), each with regression tests.

---

# CRITICAL

**GUI-1 · `budget_gui/scenario_view.py:224-229,397-403,509-512`** · **Verified**
- *What:* `ScenarioEditor._root` is set only in `load()`. `reload_if_clean` does not update it. Open project B with a scenario of the same id as project A, then press "Save scenario": B's edit is written into **A's** `scenarios/<id>.yaml`.
- *Why it matters:* an edit lands in the wrong project, silently. Both projects now differ from what the user believes.
- *Fix:* set `_root` from the current project whenever the project changes (or call `load()` when the root differs). Test: open A, open B with the same scenario id, save, assert A is untouched.

**GUI-2 · `budget_gui/unit_editor.py:33-40,163-179`** · **Verified**
- *What:* the unit editor has no `heat_dissipation_ratio` column, and `_data` rebuilds each mode from the six visible columns. Saving a unit **drops `heat_dissipation_ratio` from every mode**, even with no edit.
- *Why it matters:* after a no-op save, the thermal budget shows n/a for those modes. The user never touched thermal.
- *Fix:* keep hidden keys from the original model by row (or add the column). Test: a no-op save leaves the file byte-identical.

# HIGH

**GUI-3 · `budget_gui/editor.py:262-269`, `unit_editor.py:72,164,207`** · Verified (text edit)
- *What:* `reload_clean_files` refreshes only the YAML text editor. A clean unit editor keeps a stale `_original` after a text-tab save, a unit-table import or F5; its next Save reverts the newer file.
- *Fix:* reload clean unit/scenario editors too, or mark them stale. Test: save in the text tab, then save in the table tab, assert the text edit survives.

**GUI-4 · `budget_gui/scenario_view.py:530-533,189-194,652`** · Verified
- *What:* switching the scenario combo calls `load()`, replacing the editor contents with no prompt and leaving `_modified` True. `confirm_discard_pending_edit` is dead code.
- *Fix:* ask before discarding, or revert the combo.

**GUI-5 · `budget_gui/scenario_view.py:497-501`** · Verified
- *What:* a reload with no project calls `editor.clear()`, which sets `_modified` False; unsaved edits are lost without a prompt (contradicts D-060).

**GUI-6 · `budget_gui/main_window.py:352-358`; `scenario_view.py:580`, `timeline_view.py:247`, `link_view.py:226`, `compare_view.py:221`** · Verified
- *What:* closing the window during an export or long compute blocks the UI for exactly 10 s, then prints "QThread: Destroyed while thread is still running" and aborts (exit 134). Computes over 30 s do the same.
- *Fix:* ignore the close while a job runs (or cancel cooperatively and close from the worker's `finished` signal).

**GUI-7 · `budget_gui/main_window.py:258-275`, `editor.py:74`** · Verified
- *What:* `save_current` catches only `OSError`, but `write_file` raises `OutputError`; the user sees "unexpected error (OutputError)" and the friendly message is dead code.
- *Fix:* `except (OSError, OutputError)`.

**GUI-9 · `budget_gui/scenario_view.py:514-528`** · Verified
- *What:* the stale check compares `environment_key` only inside `elif run.scenario != scenario`. Editing an orbit, station or target file does not mark the Scenario tab stale; export writes the old eclipses and passes. No stale check at all on scenario export.

**GUI-10 · `budget_gui/timeline_view.py:100-104,150-154,196-200`** · Verified
- *What:* the Demand combo (nominal/margined) has no signal. Changing it leaves a stale result on screen and exportable; the report says "Demand basis: nominal".

**GUI-11 · `budget_gui/timeline_view.py:224-229`, `link_view.py:196-199`, `scenario_view.py:554-571`** · Verified
- *What:* `_done` never compares the result's scenario with the current selection. Compute `one_day`, select `two`: the `one_day` result is shown and exportable under "two".

**GUI-12 · `budget_gui/compare_view.py:142-156,195-212,261-273`** · Verified
- *What:* `set_project` only changes the status text. Export stays enabled and exports the old comparison after the project changes or reloads.

*(GUI-9 to GUI-12 share one root cause: results are not tied to the inputs they were computed from. One small "result is valid for (project revision, scenario, options)" check, used by every tab, fixes all four.)*

**PWR-1 · `power/time_domain.py:515-516,733-746`** · Verified
- *What:* the BOL case (age 0) requires `annual_degradation_ratio` and the battery `annual_capacity_fade_ratio`. A placeholder in either makes the whole BOL case n/a, although BOL does not use them. (A placeholder design life correctly leaves BOL alone.)
- *Fix:* age factor 1.0 and fade exponent 0 at 0 years without requiring the inputs; require them only for years > 0.

**RC-1 · `budget_cli/main.py:479-487`** · Verified
- *What:* `link-passes` filters only WARNING problems, prints a hard-coded `0 errors`, and returns 0. A link that closes at no data rate (`LINK_NOT_CLOSED`, error) passes silently; `run --budget link` on the same project prints the error and exits 1. The JSON file holds the errors.
- *Why it matters:* CI gates on exit codes.
- *Fix:* use the same error handling as `_run`.

**MI-1 · `io/yamlio.py:107-148`, `io/project_loader.py:153`** · Verified
- *What:* the depth (64) and node (200,000) caps run only after the full parse. `"x: " + "[" * N` takes 3.8 s at 2,000, 9.9 s at 8,000, 65 s at 60,000 (about 1.1 ms per bracket; a 2 MB file would take about 35 minutes). A flow list of 190k scalars takes 13.7 s.
- *Why it matters:* a small file from someone else hangs `validate`, the GUI load and `units-import`.
- *Fix:* a cheap pre-scan before parsing (maximum bracket depth, line length, approximate item count); lower the byte cap.

**MI-2 · `io/yamlio.py:82,89,140`** · Verified
- *What:* a tagged sequence (`name: !!omap [a: 1]`) raises `TypeError`; an inline merge key (`<<: {foo: 1}`) raises `KeyError`, or is silently accepted when the merged key is valid (the docs say `<<` is unsupported); `%YAML 1.3` raises `AssertionError`. The CLI prints "Internal error (TypeError). Run 'budget validate …'", which is circular when the failing command is `validate`. Python tags are not executed.
- *Fix:* catch broadly around parse and convert and return `YamlSyntaxError`; reject non-standard tags and `<<` explicitly; use `getattr` fallbacks for line numbers.

**MI-4 · `io/validation.py` (messages at 85, 97, 109, 125, 624, 740, 773, 795, 809, 822, 846, 887, 902, 1003, 1016; hints at 60, 72, 101, 129, 628, 643, 717, 744, 777, 813, 851, 865, 891); `model/environment.py:25-28`; also `thermal/static_thermal.py:402-444`, `link/evaluate.py:235-247`** · Agent-reproduced (12 of 24 problems leaked a planted secret)
- *What:* Problem messages and hints contain values read from project files (phase, mode, case and class names, surface names, user-written paths). A TLE with a superscript digit gives `invalid literal for int() with base 10: '²'`, echoing file content. This breaks the CLAUDE.md rule "only field names, ids and units".
- *Why it matters:* the tool is intended for controlled data; a pasted Problems list leaks names.
- *Fix:* name the path or index only; in the TLE check use `ch in "0123456789"` and raise a custom error; map `value_error` in `explain()` to a generic text. **Decision 2.**

# MEDIUM

## Power and mass

- **PWR-2 · `power/time_domain.py:251-268,781-795,300-302,894-909`** (agent-reproduced). When the battery empties or fills inside a refined step, the depletion start, worst case and DoD interval end depend on the step (true start 2440 s reported as 1500 s at step 1500). Contradicts D-097. *Fix:* add saturation instants as refined edges; exact slope for crossings.
- **PWR-3 · `power/orbits.py:26-41`** (agent-reproduced). Orbit windows are wrong or empty when the step exceeds about half the period, with no message. *Fix:* no windows beyond ~90° per step, and a "orbit balance not evaluated" problem.
- **PWR-4 · `reports/timeline_report.py:181`, `budget_cli/main.py:536`** (agent-reproduced). "No violations found." / "0 violation(s)" is printed when the DoD, depletion, peak or orbit checks were not evaluated (placeholders, no phase, no complete orbit). *Fix:* record `checks_not_evaluated` and print "Not evaluated: …".
- **PWR-5 · `power/time_domain.py:217-230`** (agent-reproduced). The soft (conical) shadow is not step-independent: step 300 gives +2.0 % lit time, step 1000 falls back to the sharp model. *Fix:* build the lit ratio from `env.eclipses`/`env.umbras`.
- **PWR-6 · `mass/static_mass.py:321-325`** · **Verified.** A mass limit met exactly is reported `MASS_LIMIT_EXCEEDED` (an error) because of float noise (24.255000000000003 vs 24.255). My mutation check (`>=` → `>`) is not caught by any test. *Fix:* `margin >= -1e-9 * max(1, abs(value))`; add a boundary test.
- **PWR-7 · `mass/static_mass.py:238-256,292-307`, `model/mass.py:297-306`** (agent-reproduced). An expendable's own inertia does not scale with its phase mass (a tank at 10 % mass keeps full inertia), without a warning. *Fix:* warn, and record in DEVIATIONS.

## GUI

- **GUI-8 · all `QFileDialog` calls** (`main_window.py:160,170,190,207`, `unit_table.py:52,85`, `help_view.py:63`, `compare_view.py:162`, `guided.py:149`) · Verified. Qt writes `~/.config/QtProject.conf` (FileDialog history; Windows registry). Violates "no state outside the project". **Decision 4.**
- **GUI-13 · `main_window.py:296-311`** (verified). `_update_problems` uses `timeline_view.problems()` even when stale; A's findings show in B's Problems panel.
- **GUI-14 · `session.py:62-107`, `timeline_view.py:417-427`** (verified). Load, reload and output building run on the GUI thread: `stress_200_units` opens in 6.96 s and reloads in 7.65 s (every Ctrl+S freezes); building the timeline output takes 4.67 s.
- **GUI-15 · `widgets.py:256-303`** (verified). `tabs.clear()` does not delete pages; table views grow 78 → 728 after ten reloads (memory leak).
- **GUI-16 · `editor.py:69-77`** (verified). The text tab overwrites a file changed on disk (no mtime/hash check).
- **GUI-17 · `unit_editor.py:203`, `scenario_view.py:403`** (verified; same as MI-10). `write_bytes(dump_model(...))` drops all YAML comments, reorders keys, and is not atomic (D-094 says temp file), while D-102 tells users to keep sources as comments. SPEC constraint 12 (clean Git diffs). *Fix:* route through `write_file` and a ruamel round-trip patch like `units-import` already uses.
- **GUI-18 · `widgets.py:197-206`** (verified). The project tree has no `links/` group; link files cannot be opened from the tree (the manual says they are listed).
- **GUI-19 · `main_window.py:184-192`** (verified). Export checks only that a result exists; after a project change, picking a folder does nothing, silently. No finished/failed signals for the timeline, link and compare exports; success says "Exported N file(s)" without the folder.
- **GUI-20 · `main_window.py:103,296-311`, `link_view.py:232`.** Link-pass problems are never merged into the Problems panel (effect unverified).
- **GUI-21 · `editor.py:56-77`** (verified). Save converts CRLF to LF and drops a BOM.
- **GUI-22 · `editor.py:262-269`** (verified). Every save reloads the just-saved editor: cursor to column 0, undo history lost.
- **GUI-23 · `timeline_view.py:400-408`** (verified with doctored data). Jumping to a violation zooms and then resets the view when the case combo changes.
- **GUI-24 · `scenario_view.py:137` + docks** (verified). Minimum window size 897×781, taller than a 1366×768 screen.
- **GUI-25 · `theme.py:53-54`** (verified). No `:disabled`/`:focus` style on buttons; a disabled Export looks like an enabled Compute.

## Reports, CLI, output

- **RC-2 · `reports/timeline_export.py:62,80`** · Verified by code reading. The series CSV writes the `mode` id with `"%s"`, bypassing `csv_writer`: commas/quotes add columns and a leading `=` is not defused. Ids need an unusual file name, so I rate it medium. *Fix:* build rows with `csv_writer`.
- **RC-3 · `main.py:479,538`.** `--strict` ignores load warnings in `link-passes` and `power-timeline` (`validate --strict` and `run --strict` exit 1, `link-passes --strict` exits 0); warnings are counted but not printed.
- **RC-4 · `reports/export.py:44`, `timeline_export.py:209`, `link_export.py:184`.** JSON `problems` omits load-time problems that XLSX, PDF and DOCX list (6 vs 88).
- **RC-5 · `provenance.py:20`, `packaging/system_budget_studio.spec`.** `LIBRARIES` omits python-docx, Pillow, numpy and sgp4 (spec constraint 19); the frozen build reports `unknown` for openpyxl and reportlab (no `copy_metadata`). *Fix:* extend the list and add `copy_metadata`.
- **RC-6 · `reports/files.py:55-62` (used by `io/unit_table.py:571`).** `units-import --apply` resets file permissions: mode 600 becomes 644 (SPEC constraint 11). *Fix:* copy the mode before `os.replace`.
- **RC-7 · `reports/timeline_report.py:75`, `main.py:536`.** The per-case "Violations" count omits case-independent (peak-power) violations: "0 violation(s)" is printed with "1 error".
- **RC-8 · `reports/document.py:58-66` vs `xlsx.py:25-26`.** PDF/DOCX/CSV round half-even on the binary value; XLSX is rounded by Excel half-up (0.125 → 0.13 vs 0.12); "-0.00" in PDF and DOCX. **Decision 3.**
- **RC-9 · `reports/common.py:44`.** The "Configuration numbers used" table shows 4 decimals: -0.00041234 → -0.0004; anything below 5e-5 → 0.0000.
- **RC-10 · `reports/docx.py:180-183`** · Verified. A project name or `--user` longer than 255 characters makes DOCX export fail with "Internal error (ValueError)"; nothing is written for that run. *Fix:* truncate core properties.
- **RC-11 · `reports/common.py:65-75`.** The Problems table drops `path` and `hint` (81 identical-looking rows).
- **RC-12 · `reports/run.py:181-184`, `files.py`.** A failing write leaves a partial output set with a generic message that names no file; stale files from earlier runs stay.
- **RC-13 · `xlsx.py:68`, `pdf.py:148`, `docx.py:161`.** The INCOMPLETE banner appears only on the first sheet/page; CSV and JSON carry no completeness flag.
- **RC-14 · `timeline_report.py`, `link_report.py`.** The equation lists name only `TDP-*` / `LNK-*`; `PWR-*`, `ENV-*` equations the results rely on are not listed (spec constraint 16).
- **RC-15 · `main.py:693-698`** (agent-reproduced; I could not re-run it here). With a non-UTF-8 stdout (redirected cp1252 on Windows) and a non-ASCII name in the output, the run writes its files, then prints "Internal error (UnicodeEncodeError)" and exits 1. *Fix:* `sys.stdout.reconfigure(errors="backslashreplace")`.
- **RC-16 · `provenance.py:59-65`** · Verified. A bad `SOURCE_DATE_EPOCH` (`abc`, `-5`, empty) is silently ignored (not reproducible, no message); `--date 9999-12-31T23:59:59-05:00` gives "Internal error (OverflowError)".
- **LD-1 · `budget_core/examples.py` (`export_examples`, `write_project`), CLI `export-examples`** · **Verified.** Writes over existing files in the target folder without asking. Running it on a folder with a project of the same name replaces the user's edits. *Fix:* refuse a non-empty target or existing project folders, unless `--force`.
- **LD-2 · `main.py:136,192`** · **Verified.** `--series-every` and `--max-rows` accept zero and negative values (`--max-rows -5` gives "420 value(s) differ" instead of 210). *Fix:* argparse type with a minimum.

## Thermal, link, compare

- **TL-1 · `thermal/steady_state.py:115-122`** · **Verified.** A node counts as converged against the whole body's heat flux, not its own. An isolated 1e-3 m² node reports 4.5 K (cold) and 5.985 K (hot); the true value is 3.0 K. The report states the imbalance is below 1e-6 W, which hides the error. *Fix:* per-node balance plus a small-step test; add an isolated-node test.
- **TL-2 · `compare.py:82-90`** · **Verified.** Link tables are matched on the first column (the link id, which repeats; repeats are numbered by position). Inserting one static point or data rate shifts every later row, so unchanged points are reported as changed. *Fix:* tables declare key columns.
- **TL-3 · `reports/link_report.py:226-228`** · **Verified.** No INCOMPLETE banner when pass results are n/a because an Eb/N0 or attenuation entry is missing (missing is not a placeholder) and there are no static points. *Fix:* set `incomplete` when any series margin is None.
- **TL-4 · `link/evaluate.py:216-229,536-537`.** All-or-nothing: a placeholder required margin, required Eb/N0 or attenuation entry blanks free-space loss, EIRP, G/T and C/N0, which are computable. **Decision 5.**
- **TL-5 · `link/evaluate.py:679-690,731-735`.** The geometry at the start of each step is used before AOS or below the minimum elevation; the lowest margin and sample elevations include it (minimum -10.96° at step 300). Volume is step-dependent: 21720 Mbit at 1 s, 18928 at 120 s, 22668 at 300 s. **Decision 1.**
- **TL-6 / MI-7 · `environment/elements.py:20,31,159-162`.** Passes shorter than about 20 s are missed depending on `step_s` (10 passes at 0.5 s, 9 at 60 s), with no warning. Conflicts with D-057 and with ENVIRONMENT_FORMAT.md. **Decision 1.**
- **TL-10 · `io/validation.py:571-597,646-660`.** No range checks on `gain_dbi`, `g_over_t_dbk`, `required_ebn0_db`, `loss_db` (a -10 dB atmospheric loss is accepted); duplicate Eb/N0 entries accepted, the first silently wins.
- **TL-14 · `thermal/static_thermal.py:567-591,314-322`.** `THERMAL_LIMIT_EXCEEDED` messages do not name the case, and the dedupe merges hot and cold into one problem.
- **TL-16 · `compare.py:104-118,143,154`, `reports/document.py:58-65`, `main.py:192,595`.** -0.0 vs 0.0 is a phantom change; change and percent are computed from rounded values (0.16 % shown as 0.8 %); one-sided columns and a second table with the same title are dropped silently; the CLI counts whole-row differences as values ("61 value(s) differ out of 32 compared").

## Model, io, environment

- **MI-3 · `io/project_loader.py:153-161`** · Verified. A FIFO named `*.yaml` blocks the loader (no `is_file()` check). Same pattern in `link/evaluate.py:249`.
- **MI-5 · `model/environment.py:14,180`, `environment/elements.py:159-162`** (agent-reproduced). Cost limits cover the output grid but not the 20 s detection grid. `step_s: 3600` over four years ran over 110 s with 1.2 GB; `duration_s: 1e12` gives "Internal error (MemoryError)".
- **MI-6 · `environment/data.py:26-27`** · **Verified.** `int(duration_s // step_s) + 1` drops the last sample for decimal steps (1.0/0.1 gives 10, not 11; 0.7/0.1 gives 7). *Fix:* `int(math.floor(d/s + 1e-9)) + 1`.
- **MI-8 · `timeutil.py:24`, `model/environment.py`, `wizard.py:_start`** · **Verified.** `%Y` is not zero-padded: `normalise_utc("0001-01-01T00:00:00Z")` returns `'1-01-01T00:00:00Z'`; the project loads, then `run_scenario` fails. Year 9999 gives OverflowError at output. **Decision 8.**
- **MI-9 · `environment/elements.py:check_orbit`, `model/environment.py`.** No TLE staleness warning (a 2008 ISS TLE in a 2026 scenario runs silently); semi-major axis up to 1e12 m and epoch 1900 are accepted; TLE satellite numbers on lines 1 and 2 may differ. **Decision 7.**
- **MI-10 · `unit_editor.py:203`, `scenario_view.py:403`, `project_loader.py:101-103`.** Same as GUI-17; also `write_project`/`export_examples` never remove stale files.
- **MI-11 · `project_loader.py:261-279`.** Stray files (`camera.yml`, `.YAML`, subfolders, a misspelled config file) are ignored silently; the only symptom is a misleading `REF_UNKNOWN_UNIT`. A unit that fails to parse cascades into `REF_UNKNOWN_UNIT`/`UNIT_NOT_MAPPED` for every mode. *Fix:* warn `FILE_IGNORED`, suppress derived errors.
- **MI-14 · `units/quantity.py:35,42,43,148,175-225`.** Canonical labels `kg m2`, `m2`, `W/m2` are rejected on re-read (the hint example "2.5 W/m2" fails); pint `AssertionError` escapes for some angle fields; -40 degC becomes 233.14999999999998; `delta_degC` is accepted for an absolute temperature; Arabic-Indic digits are accepted.
- **MI-19 · `wizard.py:61-66,91-95,132-142`** · **Verified.** `duration_days` below the step writes a project that does not load; the microsat sample with `duration_days < 0.0208` fails its own segment check; a year-1 start raises OverflowError/ValidationError; a 400-character name raises OSError before the try; `folder_name("CON")` returns the Windows device name `con`.

---

# LOW

(Grouped; each has file and line, and an agent-reproduced or verified reproduction unless marked.)

## Power and mass
- **PWR-8 · `environment/data.py:82-84`.** `eclipse_fraction` double-counts overlapping intervals (0.667 vs 0.333). Fix: merge and clip.
- **PWR-9 · `time_domain.py:47`, `power/signals.py:51-52`.** The 1e-9 W tolerance is below `step_means` noise over a week at 1 s: spurious `BATTERY_DEPLETED` of 1e-12 Wh when generation equals demand.
- **PWR-10 · `time_domain.py:173-179`, `static_budget.py:256-259`, `static_mass.py:399-406`.** "is missing (<file> not provided)" when only one key is absent although the file exists.
- **PWR-11 · `power/orbits.py`, `TimeGrid.times_s`.** The last orbit is dropped when the duration is not a multiple of the step; orbit balance for it is skipped silently.
- **PWR-12.** `_value` unused (`time_domain.py:164`); TDP-ARRAY note cites DV-P4 instead of DV-P5; `Violation.start_s` can be `numpy.float64`; any case name other than `eol` is treated as BOL.

## GUI
- **GUI-26 · `guided.py:165-166,218-225`.** Parent `~/Projects` creates a literal `./~/Projects` (no expanduser); blank parent means the cwd; no writability check.
- **GUI-27 · `plot_widget.py:223-231`.** `y_min == y_max` raises ZeroDivisionError in `paintEvent` (synthetic spec only).
- **GUI-28 · `plot_widget.py:362-375`.** Hover repaints the whole widget; 604,800 points take 0.27 s per paint.
- **GUI-29.** Ctrl+S on the Scenario tab does nothing silently; tree selection lost on reload; double-click on `CONFIG_MISSING` does nothing; duplicate mnemonic S; plot is mouse-only; unit cells accept `1_0` as 10 and `1,5` gives a generic message.
- **GUI-30.** Problems panel opens 1 to 2 rows tall and is sorted by file, not severity.
- **GUI-31 · `compare_view.py:57-70,175-183`.** A nonexistent or `~` folder gives the wrong message ("has errors").
- **GUI-32.** Warning colour `#b28600` on `#f4f4f4` is about 3:1 contrast; `assets_dir()` `FileNotFoundError` at startup unhandled (unverified).
- **GUI-33/34 (unverified).** Stale status text after a reload during compute; `finished_ok` emitted before the thread ends, so a second export may be refused; `write_file` turns a symlinked project file into a regular file on save.
- **GUI-35.** Layout: `during_pass` combo truncated; last tick label clipped; long site names cut.

## Thermal, link, compare
- **TL-7 · `link/evaluate.py:726`.** A link that is never active prints "0.00 MByte" with 0 warnings. Add a `LINK_NEVER_ACTIVE` note.
- **TL-8 · `evaluate.py:725`.** "Per day" is a plain scaling; a 400 s scenario gives 4.8e11 bit/day. Show n/a or label it as scaled.
- **TL-9 · `evaluate.py:349,375-390`.** Attenuation entries are merged by name only; duplicate (name, elevation) accepted, the larger loss wins.
- **TL-11 · `link/budget.py:80`, `link_export.py:209`.** `gain_dbi` 5000 produces `Infinity` in JSON (invalid JSON) and a numpy RuntimeWarning.
- **TL-12 · `evaluate.py:249`.** A pattern CSV with a UTF-8 BOM is rejected (Excel "CSV UTF-8"). Use `utf-8-sig`.
- **TL-13 · `thermal/static_thermal.py:294`.** An environment with `cases: {}` produces no temperatures, no banner and no problem.
- **TL-15.** Part of MI-4.
- **TL-17 · `steady_state.py:99-112`.** The precision guard (D-098) rejects a 5-node chain with G ≥ 1e6 W/K whose answer is accurate to 3e-14 K. Use the actual residual, or document the limit.
- **`reports/run.py:181-182`.** The duplicate-name check is case-sensitive: cases `hot` and `Hot` collide on Windows.

## Reports, plots, CLI
- **RC-17 · `compare.py:339`.** Truncation hint says "Narrow the comparison to a single budget"; `--max-rows` applies per budget. CSV/JSON hold the truncated list.
- **RC-18 · `files.py:32-45`, `run.py:181`.** `MAX_NAME` counts characters not bytes (90 CJK characters fail); case-sensitive duplicate check; `con.tar.gz` not reserved; trailing dot kept; link id `summary`/`table` or mode id `provenance` collide with generated names; `--out ""` writes into the cwd.
- **RC-19 · `pdf.py:91,168-172`.** A 10,000-character cell gives `LayoutError` (all formats for that run lost); a long footer overlaps the page number; the "Subsystem" header wraps as "Subsyste/m"; CJK and emoji are dropped silently in PDF and plots.
- **RC-20 · `plots/render.py:158-190`, `spec.py`.** NaN draws spikes; a one-sample non-step series draws nothing; `nice_ticks(0.01, 0.03)` labels are duplicated; more than 7 series overflow the legend.
- **RC-21.** Scenario JSON provenance lacks `python_version`/`libraries` (`scenario/export.py:150`); PDF dates are 2000-01-01 (`pdf.py:144`); DOCX `app.xml` says "Microsoft Macintosh Word"; `csvutil.defuse` rewrites provenance values (`+1-2@x` → `'+1-2@x`).
- **RC-22 · CLI.** No `--scenario` with zero or several scenarios gives "Scenario '' does not exist"; a file given as the project says "folder does not exist"; `run --budget link` with no links exits 0; `units-export` checks the suffix after loading; `budget` with no command exits 0; `allow_abbrev` is on; the banner print uses only the first output (an empty line when a later budget is incomplete: `run cubesat_3u_eps`); quick-start says every writing command accepts `--user`/`--date` (not `units-export`, `guide`, `export-schemas`, `export-examples`); `reports-and-exports.md` says "one sheet per table" (it is one per section).
- **RC-23 · `main.py:623,629`, `schemas.py:77`, `project_loader.py:103`.** Guide, schema and example exports use `write_text` (not atomic, follows symlinks); `write_file` has no fsync.
- **RC-24 · `link_export.series_csv`** (uncertain). Rows before AOS are flagged `active=true`; the partial-step weight is not recorded, so the row sum differs from the summary volume.
- **RC-25 (not verified in Excel).** `sheet_name` does not reject a trailing apostrophe; cells over 32,767 characters; NaN/inf written as an empty value.

## Model, io
- **MI-12 · `project_loader.py:261`.** File-stem ids are not validated (spaces, hidden names, Cyrillic look-alikes, NFC/NFD twins, non-UTF-8 names that become lone surrogates). **Decision 6.**
- **MI-13 · `io/migrations.py`.** The v1 margin_policy migration drops unknown keys (bypasses `extra="forbid"`); `schema_version: 0` message; no progress guard in the migration loop.
- **MI-15 · `model/base.py:21-37`.** Bool accepted in list/dict items and non-suffixed fields (`strings: true`, `strings: "3"`, `position_m: [True, False, 0.5]`).
- **MI-16 · `model/power_system.py:21-60`.** Unbounded integers (`strings: 10**400` gives OverflowError at run time); `normal_body: [1e300, 0, 0]` yields wrong generation (11.2 vs 99.7 Wh) with a numpy warning.
- **MI-17.** Validation holes: temperature-limit bands only ordered pairwise; duplicate Eb/N0, attenuation and mass-limit entries; whitespace-only names; `all` as a phase; `efficiency_temp_coeff_perk` +0.5 /K; system margin ratio 5; `import_dir`/`orbit`/`shadow_model` silently ignored in some combinations.
- **MI-18.** Frozen models are shallow (`unit.modes.append(...)` works; `model_copy(update=...)` bypasses validation, as `wizard.py:132` does).
- **MI-20 · `spacemissionstudio.py`, `link/evaluate.py:249`.** BOM CSV rejected; no size or row cap; a symlink inside `import_dir` pointing outside is read; pass `max_elevation_deg` not validated; `time_of_max_s` is the AOS/LOS midpoint (an invented value); semicolon CSV rejected.
- **Small:** GroundStation/Target files write `schema_version`/`kind` last; env CSV `start_utc` sub-second precision inconsistent; non-string keys give "a field appears twice"; JSON schemas have no `const` on `schema_version`; eclipse intervals have no partial flags; `unit_table` apply re-indents files not using 2/4/2.

## Packaging and release hygiene (my own checks)
- **PK-1 · `pyproject.toml` description** says "power budgets and RF link budgets"; the tool now also does mass and thermal. Update.
- **PK-2 · release workflow** (`.github/workflows/release.yml`) uploads artefacts only; it does not publish a GitHub Release. Fine, but someone must publish `v1.0.0` (owner item).
- **PK-3 · lock file** (`requirements.lock`) is generated for Python 3.11 universal; direct dependencies all fall within the `pyproject.toml` ranges. `pip check` is clean. `pip-audit` was not run (no network access to the advisory database from here); run it before tagging.
- **PK-4 (note).** Checked-in `dist/` and `build/` directories are ignored by git; the local `dist/` bundle is stale (RC-5 observed it). Not a repository problem.

---

# What was checked and found correct

- **Install and uninstall.** A clean venv from the hashed `requirements.lock` plus `pip install --no-deps .` gives a working `budget` (`--version`, `self-test`, `export-examples`, `validate`). The wheel contains all three packages, assets and schemas, no tests or `.pyc`. `install.sh`/`uninstall.sh` work with spaces and shell metacharacters in the home and prefix paths (including the desktop-entry quoting), install the self-test, and leave nothing behind.
- **Numerics.** Link formulas to full precision against hand calculation; uplink nadir angle; attenuation interpolation; pass-series bookkeeping; thermal dissipation, absorbed heat and energy balance; a 3000-network solver sweep; orbit balance and battery efficiencies; `integrate_battery` against a 2000-substep reference (4.9e-11 Wh); mass centre of gravity and parallel-axis theorem; pass AOS/LOS against brute force; conical shadow against disk-overlap brute force; Sun position at J2000; timeline fuzz of 3000 random rule sets (no gaps or overlaps).
- **Loader security.** Aliases and anchors rejected, duplicate keys rejected, tags not executed, size cap, depth cap, non-UTF-8, BOM and CRLF, symlink escapes, NaN/inf, path confinement for `import_dir` and `pattern_file`; unit-token whitelist fuzzed with 1.44 million tokens (no hang).
- **Outputs.** Report tables match the document model cell for cell on all six budgets for three example projects; XLSX formula injection is neutralised; sheet names; atomic writes; no project values in load errors; determinism across hash seed, time zone, locale, working directory and project path (63 files identical); guide HTML/PDF byte-identical, no broken links; every CLI option documented and in `--help`.
- **Tests.** 1151 pass with warnings as errors. Mutation spot-check: a wrong path-loss exponent, a wrong Eb/N0 offset, a battery boundary comparison and the power ratio tolerance are all caught; the mass-limit boundary is not (PWR-6).

# Phase 5: release checklist and verdict

Checked on 2026-10-12 on the tree of the release-preparation pull request (all four fix pull requests merged).

| Item | Result |
|---|---|
| All tests passing | **Yes.** 1810 tests pass with warnings treated as errors on Linux (Python 3.13; 1793 when the audit was closed, the rest came with the later fixes); `ruff check`, `ruff format --check` and `mypy` are clean. CI (Ubuntu and Windows, Python 3.11 and 3.13) was green on #17, #18, #19 and #20; the Installers workflow (Rocky 8 bundle, Windows installer, install, self-test, uninstall) was green on #19. |
| Help text and docs accurate | **Yes.** Every command and option in `--help` is documented and the reverse; the manual, FAQ, troubleshooting, guide chapters, file format and decisions were updated with each fix. All 538 documentation links and anchors resolve (checked with lychee, offline). Two broken anchors left over from the renumbering of decisions were fixed in the release-preparation PR. |
| Version and changelog | **Yes.** `pyproject.toml` and `budget_core.__version__` are both 1.0.0 (a test checks this); the changelog holds everything under `[1.0.0] - 2026-10-12`. Change the date if you tag on another day. |
| Dependencies pinned | **Yes.** `requirements.lock` and `requirements-dev.lock` pin every package with hashes; every direct dependency in `pyproject.toml` lies inside its range. `pip-audit` on the runtime lock file: **no known vulnerabilities** (2026-10-12). `pip check` is clean. |
| No debug output or TODO hacks | **Yes.** No `TODO`, `FIXME`, `XXX`, `HACK`, `breakpoint()` or `pdb` in `src`, `packaging` or `tests`; output of the tool is only what the commands document. |
| Clean install from scratch | **Yes, on Linux.** A new virtual environment from the hashed lock file plus the wheel of this tree: `pip check` clean, `budget self-test` passes, the window starts (`system-budget-studio --smoke`, offscreen), an example project runs. The wheel carries `LICENSE` and MIT metadata. The Windows installer is built, installed, self-tested and uninstalled by CI on every packaging change; a person has not run it on a clean Windows machine. |
| Licence | **MIT**, `LICENSE` in the repository, the wheel and every bundle (D-140). Third-party licences: all permissive or LGPL (`docs/LICENCES.md`). |
| Owner decisions | D-043, D-048, D-054, D-059, D-064, D-072, D-078 and DV-L2 confirmed (D-141). D-061, D-071 and D-077 (equations from textbooks, registered `SOURCE_MISSING`) still say "owner to confirm"; they do not affect any number. |

## Verdict

**I consider the tool releasable as the first release, numbered 1.0.0 by the owner's decision (D-143), with the limits below stated plainly.** The file formats are at `schema_version` 1 and migrate; the limits below are the reason to treat results as engineering estimates until real, sourced inputs are entered. Every critical and high finding of the audit is fixed and has a test that fails without the fix; the numerical core agrees with hand calculations; outputs are reproducible byte for byte; nothing needs the network.

What I am **not certain** about:

1. **Excel and Windows by hand.** I could not open the XLSX files in Excel (sheet-name and cell-length rules follow the documented limits), and nobody has done the [clean-machine checklist](docs/INSTALL_CHECKLIST.md) on a real Windows or Rocky 8 machine. CI builds, installs, self-tests and uninstalls both installers; it cannot look at the window.
2. **The window on a real display.** The window tests run offscreen. A plot of a week at 1 s resolution repaints slowly on hover (GUI-28); opening a project of 200 units loads in a background thread (GUI-14, D-142) but still pauses the window for up to about half a second while the tables are shown.
3. **Real data.** The example projects hold invented data and the tool ships no standards values, as the spec requires. The numerical results are only as good as the numbers and sources you enter; the equations are checked against hand calculations, not against a flight project.
4. ~~**Short eclipses** (under about 20 s) can still be missed (DV-E4)~~ Fixed after the release (D-146).
5. ~~**Error text on standard output** (RC-15)~~ Fixed after the release (D-145): errors go to standard error.

## Steps that stay with you

Done on 2026-10-12: the release-preparation pull request was merged, the owner tagged `v1.0.0` on GitHub (the assistant's session cannot push tags), the Installers workflow built the files, and the files were attached to the release (by hand the first time; since D-144 the workflow does it). What is still open:

1. Run the [clean-machine checklist](docs/INSTALL_CHECKLIST.md) on a real Windows and a real Rocky 8 machine, then delete or reword the placeholder line in the text of the release.
2. Decide on the open items of the list above (short eclipses, errors on standard output, slow hover repaint, D-061, D-071 and D-077).
