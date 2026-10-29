# Reports and exports

This page lists the files the tool writes, shows how to choose them, and explains how to regenerate a report exactly.

**Contents:** [Which files](#which-files-do-i-get) · [Choose what is written](#how-do-i-choose-what-is-written) · [Regenerate exactly](#how-do-i-regenerate-a-report-exactly) · [From the window](#how-do-i-export-from-the-window) · [User guide](#how-do-i-get-the-user-guide)

## Which files do I get?

| Kind | Content |
|---|---|
| XLSX | One sheet per section (a section can hold several tables) in the classic review layout, plots as pictures, the configuration numbers used with their sources, the equations, the problems and the provenance |
| PDF | The same tables and plots on A4 landscape pages, with a provenance footer |
| DOCX | The same content for editing in a word processor |
| CSV | Every table and every time series, one file each; empty cells where a value is n/a. Each set also has `<name>_provenance.csv` |
| JSON | The full result for other tools, with the provenance, the load-time problems and an `incomplete` flag (`true` when the report carries the INCOMPLETE banner) |

Commands and what they write (prefix is the file name start):

| Command | Files start with |
|---|---|
| `budget run --budget power` | `power_static` (and one CSV per spacecraft mode) |
| `budget run --budget mass` | `mass_static` (one CSV per phase) |
| `budget run --budget thermal` | `thermal_static`, `thermal_case_<case>` |
| `budget run --budget link` | `link_static` |
| `budget power-timeline` | `power_time_<scenario>` (series per case, orbits, violations) |
| `budget link-passes` | `link_passes_<scenario>` |
| `budget scenario` | `<scenario>_environment.json`, `_eclipses.csv`, `_passes.csv`, `_timeline.csv` |
| `budget compare` | `compare` and `compare_differences.csv` |

All of them write to `<project>/results` unless you give `--out`.

## How do I choose what is written?

`--report xlsx --report csv` (repeat the option; the default is all kinds). `--budget` chooses the budget for `run`. `--no-plots` leaves the plots out of the reports (faster). `--series-every N` thins the time-series CSV of `power-timeline`.

## How do I regenerate a report exactly?

The same project, scenario, user name and generation time give the same file contents, byte for byte. A report carries the time and the user in its provenance block, so to reproduce an earlier report give both:

```bash
budget run my_satellite --user "A. Engineer" --date 2026-01-02T00:00:00Z --out out
```

Without them the user is the `BUDGET_USER` environment variable or your login name, and the date is `SOURCE_DATE_EPOCH` or the clock. Every report records the tool version, the library versions, the project revision, the scenario, the time and the user; because of that, remember to raise `revision` in `project.yaml` when you change numbers ([revisions](create-a-project.md#how-do-i-keep-revisions)).

## How do I know which inputs a result came from?

Every report also records **what it was computed from**, so that a colleague can check it without trusting the revision label:

| Provenance row | What it is |
|---|---|
| **Inputs digest (model)** | A SHA-256 of the project as the tool loaded it: every unit, mode, orbit, station, scenario, link and configuration number, in a fixed order. Comments, key order and spacing do not change it; any number does. |
| **Input files** | How many project files were read and one SHA-256 over their names, sizes and byte hashes. A comment edit changes this one but not the digest above. |
| **Run parameters** | The options that change a number: for a scenario the environment source, the shadow model, the Earth model, start, duration and step; for a power timeline also the demand basis, the cases and the mission phase. |

The JSON files carry the full list (`provenance.input_files`: path, size and hash of every file) and the run parameters as pairs. The CSV sets carry the three rows in `<name>_provenance.csv`.

To find out whether a project is the one a result came from, give the export and the project folder to `verify`:

```bash
budget verify results/power_static.json my_satellite
```

It prints **MATCH** (exit code 0) when the project gives the digest recorded in the export, and says which files differ as text only (a comment, say). It prints **DIFFERENT** (exit code 1) when it does not, and names the files that changed, appeared or disappeared, so you can see what was edited since the export. A `<name>_provenance.csv` works in place of the JSON file but cannot name the files. An export made by an older version records no digest and is reported as such. `verify` says whether the *inputs* agree, not whether the numbers are right; if the tool version differs it says so, because a new version can compute a different number from the same inputs ([changes](../changes.md)).

Files that are read outside the project's own YAML files (an antenna pattern file, imported environment files) are not in the list yet.

## How do I export from the window?

The **Reports** area (Ctrl+7) is the place to write files. It shows the provenance every file will carry, then what can be exported with where it stands (the static budgets, the power timeline and the scenario results; the last two are *not worked out* until you press **Run**, and *out of date* when the project changed since), the formats (XLSX, PDF, DOCX, JSON, CSV; the scenario files are always CSV and JSON), and a folder. **Export** writes the ticked parts one after the other in the background, with a progress bar, and lists the files written; **Show the folder** opens it. When Export is greyed out, its tooltip says why. **File → Export reports** (Ctrl+E) still writes the reports of all static budgets to a folder you choose and **File → Export power timeline** (Ctrl+Shift+E) the power timeline. *Power → Timeline*, *Link → Passes* and *Compare* also have an **Export…** button. The folder is not remembered between sessions, because the tool keeps no path of your projects.  *Power → Timeline*, *Link → Passes* and *Compare* also have an **Export…** button. While the project has an error nothing can be exported: the tables on screen are the old results from before the error. Long exports run in the background and the window stays usable; a second export cannot start while one runs.

An export never overwrites a file by writing half of it. The whole set is first written under temporary names in the output folder and only then moved into place, so a failing write (a full disk, a locked file) leaves the folder as it was; if a move itself fails, the message names the file that failed, the files already replaced and the files not written. A file that is replaced keeps its permissions. File names are reduced to letters, digits, `.`, `-` and `_`, at most 120 bytes, with no trailing dot and never a Windows device name (`con`, `nul`, `com1` ..., also as `con.tar.gz`). Two outputs whose names are the same once case is ignored (`hot` and `Hot` cases, or a mode called `provenance`) are refused with a message that names the file, because some file systems (Windows among them) would write them to one file. Files from earlier runs that this run does not write stay where they are.

## What do the numbers in a report mean?

- **Rounding.** Every format shows a number rounded half up on its decimal value, as a spreadsheet does: 0.125 with two decimals is `0.13` in the PDF, the DOCX, the comparison and the XLSX alike. A value that rounds to zero is written `0.00`, never `-0.00` (the XLSX cell keeps the exact value and its number format, so Excel may still show `-0.00` for a tiny negative number). A number that is not finite is `n/a`.
- **Configuration numbers used** are shown with up to ten significant digits (`-0.00041234`, `3e-09`), not rounded to the table precision.
- **CSV and JSON** hold the values at full precision (series files: six decimals, no `-0.000000`).
- **INCOMPLETE.** A report with placeholders or missing inputs carries the banner on every XLSX sheet, in the header of every PDF page and DOCX page, as `incomplete: true` in the JSON file and as the row `Incomplete,yes` in `<name>_provenance.csv`.
- **Problems table.** Severity, code, file and line, the path of the field, the message and the hint, for the problems found while loading the project as well as while computing. The JSON `problems` list is the same list.
- **Limits of a format.** A PDF shows a character its font lacks (for example CJK or emoji) as `?` and says how many; a table cell longer than 400 characters is shortened in the PDF, and a cell longer than 32,000 characters in the XLSX, each with a note saying that the DOCX and JSON files hold the full text. A very long footer wraps to two lines and then ends in an ellipsis.
- **Text that looks like a formula.** In CSV files, text that starts with `=` or `@`, or with `+` or `-` followed by anything but a number or plain words, gets one leading apostrophe (`'=SUM(1,2)`) so a spreadsheet shows it as text. Nothing else is changed: the provenance values the tool writes itself never start with such a character, and a name such as `-Müller` is left alone.
- **Series CSV of the link passes.** Each row is one piece of a pass (at most 5 s long) with the geometry of its middle. `in_pass_s` is the time that piece stands for (only the time spent in the link's `active_modes`, if you set them). The data of a row is `selected_rate_bps` x `in_pass_s`, so the rows add up to the pass volume of the summary. `active` says the link is used in that piece.

## How do I get the user guide?

Inside the window: **Help → User guide** (F1). As files:

```bash
budget guide --out guide                       # system-budget-studio-guide.html and .pdf
budget guide --out guide --project my_satellite   # also list your project's numbers and their sources
```

The HTML is a single self-contained file (fonts inlined, no scripts, no external resource). Its last chapter, *Equations and sources*, lists every equation the tool uses with its source (or `SOURCE_MISSING`), the constants shipped in code, and with `--project` every sourced number of your configuration and whether it is still a placeholder.

Next: [Compare](compare.md).
