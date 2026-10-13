# Changelog

All notable changes to System Budget Studio, newest first. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); each line names the decision (`D-0xx` in [DECISIONS.md](docs/DECISIONS.md)) behind it. Version 1.0.0 is released ([how to cut a release](docs/developer/README.md#cut-a-release)).

## [Unreleased]

- **A banner and a logo.** `docs/images/banner.svg` (top of the README) and `docs/images/logo.svg`: four budget bars under a dashed limit line, in the style of the SpaceMissionStudio banner. They are plain SVG, drawn for this project; the window and the installers do not use them yet.
- **Errors go to standard error.** A command that cannot do its work (a refused load, a run that finds errors, a command called wrongly, an unwritable file, an internal error) says why on standard error; results, warnings and summaries stay on standard output, and so does the whole list of `budget validate`. Exit codes are unchanged. See [command line](docs/user-manual/command-line.md#standard-output-and-standard-error) (D-145; audit RC-15).
- **Eclipses and umbras shorter than 20 s are found.** The fixed 20 s detection grid could miss a shadow that begins and ends between two samples (an 11.6 s eclipse was missed when the scenario started 8 to 14 s after the epoch of the orbit). Such shadows are now found from the local maximum of how far inside the shadow the satellite is, as short passes are found from the elevation maximum (D-146; DV-E4; audit TL-6).
- **Documentation brought up to date after the release.** README, getting started and the changelog point to the installers on the Releases page; the records of the documentation audit, the audit report, the branch-protection page, D-017 and the deviations page no longer say that there is no release, no licence or an undecided visibility (D-140, D-143, D-144). The README now starts with an install section for the installers, has release and licence badges, and states the known limits.
- **The release workflow attaches the installers to the release.** After a tag is built, the files are checked against their checksums and uploaded to the GitHub Release (a missing release is created as a draft); *Actions > Attach release files* does the same for an earlier run (D-144).

## [1.0.0] - 2026-10-12


The first release. The version is 1.0.0 (D-143); the milestones M0 to M6 below were internal steps that were never released. Everything below is in the repository at this version.

### Licence
- **MIT licence** and a `LICENSE` file; the installers and bundles ship it (D-140). The eight earlier decisions marked "owner to confirm" are confirmed (D-141).
- The mission phase of a scenario without a depth-of-discharge entry is warned about (`SCENARIO_PHASE_NO_DOD`).

### Pre-release audit: window (GUI)
- **Opening and reloading a project no longer freezes the window.** The project loads in a background thread (open, F5, reload after a save); the status bar says "Loading the project…" and the window stays usable (the 200-unit project: longest freeze from about 3.6 s to about 0.5 s). Overlapping requests are answered by one reload. Showing the tables is cheaper too (D-142).
- **A scenario edit is saved into the project that is open now.** Opening a second project with a scenario of the same name and pressing *Save scenario* used to write into the first project's file (D-103).
- **Saving a unit no longer drops `heat_dissipation_ratio`** (or any field the table does not show), and the unit table and the scenario editor now edit the file in place: comments, key order and unchanged values stay, a save without a real change leaves the file byte-identical, and the write is atomic (D-103). The text tab keeps a byte-order mark and CRLF line ends, keeps cursor and undo after a save, and asks before overwriting a file that changed on disk.
- **Results belong to their inputs.** A scenario, timeline, link or comparison result is marked stale (and its export switched off) when the project, an orbit, ground station or target file, the scenario selected or the demand basis changed; a result for a scenario that is no longer selected is not shown; findings of a stale result leave the Problems panel; link-pass findings now reach it (D-104).
- **No silent loss of edits.** Switching the scenario asks before discarding edits, a project that stops loading keeps unsaved scenario edits, clean table editors follow a file that was saved in the text tab or imported from a table (D-104).
- **Closing the window while a computation or export runs** no longer freezes it for 10 s and aborts; it closes when the job has finished. A second export right after a first is no longer refused (D-104).
- **Save errors are plain** (a read-only folder used to give "unexpected error"). Exports from the File menu or a tab say which folder they wrote to, or why they did not.
- **Qt file dialogs no longer write `~/.config/QtProject.conf`** (or the Windows registry); the dialogs do not remember the last folder (D-105).
- Smaller: the project tree lists `links/`, keeps its selection on reload, and old tab pages are deleted (memory no longer grows with reloads); the Problems panel lists errors first and opens taller; the minimum window height fits a 1366 x 768 screen (the scenario editor scrolls); disabled buttons and focus are visible; the warning colour is readable; `1_0`, `nan` and a decimal comma in a cell give a clear message; Ctrl+S in the Scenario tab saves the scenario; double-clicking a missing file says it does not exist; the *File* menu has no duplicate mnemonic; the wizard expands `~`, refuses a blank or unwritable parent folder; a missing comparison folder is named as such; a flat plot no longer raises; jumping to a violation keeps its zoom; the Power timeline and Link passes exports are built in the background thread.

### Pre-release audit: loader, validation, command line, wizard, units
- **Loader.** A file is refused on counts of its raw text (size, lines, brackets, depth) before the YAML parser runs: 60 KB of `[` no longer takes a minute. Tags (`!!omap`), the `<<` key and odd directives are `YAML_SYNTAX` problems instead of internal errors. A pipe or folder named `*.yaml` no longer blocks the loader (D-122).
- **Stray files and ids.** `FILE_IGNORED` for `.yml`, `.YAML`, sub-folders and misspelt config files; `ID_UNUSUAL`, `ID_COLLISION`, `ID_INVALID` for odd file names; no `REF_UNKNOWN_*` cascade from a file that failed to load (D-120).
- **Problem text.** Messages and hints no longer contain names or values read from files (phase, class, node, case, surface, limit, attenuation names; TLE digits). They give the path, line or an index (D-121).
- **Validation.** Ranges for antenna gain, G/T, required Eb/N0 and atmospheric loss; duplicate Eb/N0, attenuation and mass-limit entries; whitespace-only text; survival band must enclose the operating band; `SCENARIO_OPTION_IGNORED`; yes/no values and numeric text are not numbers; migrations keep unknown keys (D-123).
- **Units and times.** `m2`, `kg m2`, `W/m2` read back; `-40 degC` is exactly 233.15 K; a temperature difference is refused for an absolute temperature; exact capitals for dB units; ASCII digits only. Years are four digits and limited to 1950 to 2100 (D-123, D-124).
- **Guided mode.** A duration below the sample's step or segments, a start outside 1950 to 2100, a 400-character name and Windows device names (`CON`) are handled; a half-written project is removed.
- **SpaceMissionStudio import.** Byte order mark accepted, size and row limits, files must lie inside `import_dir`, peak elevation checked, no invented time of the pass maximum (D-124).
- **Command line.** `link-passes` fails on a link that closes at no rate and counts load problems like `run` and `power-timeline`; unencodable characters no longer crash a finished run; a bad `SOURCE_DATE_EPOCH` or `--date` is a clear error; `export-examples` needs `--force` to replace existing folders; `--series-every` and `--max-rows` are range-checked; several or no scenarios without `--scenario`, a file given as the project, `run --budget link` without links, `units-export` with a wrong suffix and `budget` without a command are explained; options cannot be abbreviated; the INCOMPLETE banner is printed when a later budget is incomplete; guide, schema and project files are written atomically (D-125). The JSON schemas fix `schema_version`.

### Pre-release audit: solvers, environment, power, thermal, link, mass
- **Power:** beginning of life no longer needs the annual array degradation or the battery capacity fade (it was n/a with a placeholder in either; PWR-1). The battery's full and empty instants and the orbit boundaries are solver edges, so the start of a depletion, its worst unmet power and a depth-of-discharge crossing no longer depend on the step (PWR-2, D-131). The soft shadow comes from the eclipse and umbra intervals and is step-independent (PWR-5, DV-P6). Orbit windows are refused for a step longer than a quarter orbit (`ORBIT_BALANCE_NOT_EVALUATED`) and the last orbit is kept when the duration is not a multiple of the step (PWR-3, PWR-11). Checks that could not run are listed as "Not evaluated" in the report, the window and `budget power-timeline`, never as "No violations found", and the per-case violation count includes the case-independent findings (PWR-4, RC-7). No spurious depletion from rounding noise (PWR-9). Messages say "missing from <file>" when only a key is absent (PWR-10).
- **Mass:** a limit that is met exactly is not exceeded (24.255 kg against a 24.255 kg limit gave `MASS_LIMIT_EXCEEDED`; PWR-6). New warning `MASS_INERTIA_NOT_SCALED` for an expendable whose own inertia does not follow its changing mass (PWR-7, DV-M4).
- **Thermal:** every node must balance to its own heat; an isolated tiny node beside a large body was reported at 4.5 K / 5.985 K instead of the 3 K of space (TL-1). Stiff networks are refined with an exact residual before being refused (TL-17). Limit and margin findings name the case and are no longer merged (TL-14); an environment without cases is `RESULT_INCOMPLETE` (TL-13); messages no longer repeat surface and limit names (TL-15). D-132.
- **Link:** path loss, atmospheric loss, EIRP, G/T and C/N0 are computed from their own inputs; a placeholder required margin or Eb/N0 no longer blanks them (TL-4). Samples are evaluated in the middle of the part of the pass they stand for and only inside the pass; the data volume and the lowest margin no longer depend on `step_s` (TL-5; the link goldens changed, D-130). Per-day volume is n/a for a scenario shorter than a day; `LINK_NEVER_ACTIVE` note; attenuation entries are matched by frequency and duplicates warn; a BOM in a pattern CSV is read; infinite numbers are `null` in the JSON (TL-7, TL-8, TL-9, TL-11, TL-12).
- **Environment:** passes are found at any `step_s`, including passes of a few seconds (TL-6/MI-7, D-130). The time grid keeps the last sample of a decimal step (MI-6). Overlapping eclipses count once in the eclipse fraction (PWR-8). Limits: the cost limit covers the detection grid and running out of memory is a plain message (MI-5); start times and epochs in 1950 to 2100 (MI-8); semi-major axis 6.4e6 to 1e8 m, matching TLE satellite numbers, a valid TLE epoch and a warning for a TLE more than 30 days from the start (MI-9, D-133); bounded cell and string counts and direction vectors (MI-16).
- **Shown where the results are used.** `budget link-passes` says `n/a per day` for a scenario shorter than a day; `budget scenario` and the Scenario tab show the stale-orbit warning; the timeline JSON lists the checks that did not run (`not_evaluated`); the timeline tab counts case-independent violations and names the checks that did not run.

### Added since the milestones
- Unit power data as a table: `budget units-export` (CSV or XLSX), `budget units-import` (preview, then `--apply`), and *File → Export/Import unit table* in the window. Empty cell means unchanged; no unit is created or deleted; formulas are never evaluated; one problem stops the whole import; the unit files are edited in place so comments and key order stay (D-102).
- Documentation restructure: [README](README.md), [docs index](docs/README.md), [getting started](docs/getting-started.md), [user manual](docs/user-manual/README.md), [examples guide](examples/README.md), [FAQ](docs/faq.md), [troubleshooting](docs/troubleshooting.md), [glossary](docs/glossary.md), [tips](docs/tips.md), [CONTRIBUTING](CONTRIBUTING.md), [developer docs](docs/developer/README.md) and the [documentation audit](docs/DOCS_AUDIT.md).

### Pre-release audit: reports and output
- Every format rounds half up on the decimal value (0.125 is 0.13 in PDF, DOCX, CSV comparison and XLSX), never prints `-0.00`, and shows a number that is not finite as n/a; the *Configuration numbers used* table shows up to ten significant digits (D-110).
- Writing outputs: the set is staged and moved into place together, the failing file is named, replaced files keep their permissions, names are limited by bytes, reserved names include `con.tar.gz`, names that differ only by case are refused (D-111).
- The INCOMPLETE banner is on every sheet and page; JSON has `incomplete`, the provenance CSV a row `Incomplete`; link reports are incomplete when a pass result is n/a because a table entry is missing; equation lists include the PWR-* and ENV-* equations the results rely on (D-112).
- The Problems table has Path and Hint columns; JSON `problems` include the load-time problems (D-116).
- Comparison pairs link tables by link, point, rate and AOS time, so inserting a point does not shift the rows; changes come from exact values; one-sided columns, tables and repeated titles are listed; CSV and JSON hold every difference; the summary separates values from rows (D-113).
- Provenance lists numpy, Pillow, python-docx and sgp4 as well and the packaged build ships their metadata; PDF dates, DOCX application name and XLSX creator are consistent; scenario JSON carries Python and library versions; CSV defusing leaves plain words alone (D-114).
- PDF: very long cells are shortened with a note instead of failing the run, missing glyphs are `?`, header words are not split, the footer wraps; XLSX: valid unique sheet names, long cells shortened; DOCX properties are cut at 255 characters; plots: gaps, single samples, tick labels, legend overflow (D-115).
- Series CSV files: the mode id is quoted and defused; the link series has `in_pass_s`, the time each row stands for (D-116).

### Fixed since the milestones
- **File → Export scenario results** existed in the code but was not connected to any menu; it is now, and an unwritable folder gives a plain message. The "Compute a scenario first (Ctrl+R)" message named a shortcut that does not exist; it now says to press Compute in the Scenario tab.

### Changed since the milestones
- `docs/ARCHITECTURE.md`, `PLAN.md`, `BRANCH_PROTECTION.md`, `ENVIRONMENT_FORMAT.md`, `FILE_FORMAT.md` and the user guide chapters corrected where they described features that do not exist.

### Honesty round
- Unit import from CSV/XLSX and a separate expert mode are recorded as deferred; documents no longer claim them (D-099).
- A `<name>_provenance.csv` is written beside every set of CSV files (D-100).
- Thermal goldens are tolerant of the last digits; wall-clock tests have 3x headroom; tests for the remaining problem codes (D-101).

### Numerics round
- The power budget no longer depends on the time step: the battery is solved on the grid refined by every eclipse and mode-change edge (D-097).
- Overlapping eclipses from imported data count once; a limit met exactly is not a finding.
- Thermal solver accepts only balanced solutions and refuses networks it cannot resolve; `ok (margin not checked)` for a placeholder margin (D-098).
- Link passes weight `active_modes` by overlap; `usable_s` is n/a when not computable; new `LINK_NOT_CLOSED` finding.
- Angle units (`rpm`) are refused in non-angle fields; temperatures below absolute zero are refused.
- A mass-limit finding points at the right entry when names repeat.

### Packaging round
- Bundles exclude development code; the SBOM and licence report describe what is shipped; licence texts travel with the program (D-095).
- Safer `install.sh`/`uninstall.sh`; Windows installer sets `ChangesEnvironment`, removes exactly its PATH entry, cleans up on upgrade (D-096).
- CI smoke-tests that the window can be created on every platform, checks tag against version, writes `SHA256SUMS.txt`.

### Hardening round
- Unit tokens are checked before pint sees them; YAML aliases and oversized files are refused; limits on number magnitude, steps and rules (D-092).
- Project paths cannot leave the project folder; output names are sanitised and written atomically; spreadsheet formulas in CSV/XLSX are defused (D-093).
- GUI data safety: no concurrent export, confirm before discarding edits, stale results cannot be exported, no tracebacks (D-094).

### M6 Polish
- Comparison of two revisions or two scenarios (`budget compare`, Compare tab) (D-084, D-085).
- Guided new-project wizard (D-086); offline user guide in HTML and PDF with a generated *Equations and sources* chapter (`budget guide`) (D-087).
- Per-user installers for Windows and Linux built and tested in CI (D-088); licence review (D-089); performance pass (D-090); golden reports for every reference project (D-091).

### M5 Link budget
- Link files per direction, antennas (constant, table, pattern file), static table, pass time series with margin-constrained data rate and data volume per pass and per day (D-077 to D-083).

### M4b Thermal budget
- Heat dissipation by unit, subsystem, node and mode; steady-state node model with hot and cold cases; unit temperature limits (D-071 to D-076).

### M4 Time-domain power budget
- Solar array and battery model over a scenario for beginning and end of life; depth of discharge, orbit balance and peak power violations with time stamps; plots with cursors (D-061 to D-070).

### M3 Environment
- Eclipses and ground-station and target passes from orbital elements or a TLE (SGP4); an importer for an interim SpaceMissionStudio format; scenario mode timelines from rules and segments; `budget scenario` and the Scenario tab (D-053 to D-060).

### M2 Static budgets
- Static power budget with maturity and system margins and converter and distribution losses (M2a); static mass budget with centre of gravity, inertia and phases (M2b); XLSX, PDF, DOCX, CSV and JSON reports with provenance; Problems panel (D-040 to D-052).

### M1 Model and units
- Project model, unit-suffix convention with `pint` at the file boundary, schema versions with migrations, sourced configuration with placeholders, `budget validate`.

### M0 Foundation
- Repository, CI, an empty Carbon-styled window, packaging, the offline test.

Next: [Docs index](docs/README.md).
