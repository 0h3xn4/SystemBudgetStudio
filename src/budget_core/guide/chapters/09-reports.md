# Reports and exports

`budget run`, `budget power-timeline`, `budget link-passes` and `budget compare` write their results next to each other:

| Kind | Content |
|---|---|
| XLSX | One sheet per section (a section can hold several tables) in the classic review layout, plots as pictures, assumptions and provenance |
| PDF | The same tables and plots on A4 landscape pages, with a provenance footer |
| DOCX | The same content for editing in a word processor |
| CSV | Every table and every time series, one file each, empty cells for values that are n/a |
| JSON | The full result for other tools |

Choose kinds with `--report xlsx --report csv` (default: all). In the window use **File > Export reports**.

## Assumptions and equations

Each report ends with the configuration numbers used (value, source, placeholder or sourced), the equations with their sources, the problems and the provenance. Entries that depend on placeholders show **n/a**, and the report starts with the INCOMPLETE banner.

## Reproducible files

The same project, scenario, user name and generation time give the same file contents. Use `--user` and `--date` (or `BUDGET_USER` and `SOURCE_DATE_EPOCH`) to regenerate an earlier report.

Every set of CSV files comes with a `<name>_provenance.csv` (tool and library versions, project, revision, scenario, time, user), because a CSV has no room for a header block. Plots exist only inside the reports, which carry the same provenance block; no plot is written as a loose image.

## Entering power data

Unit power data is typed in the unit editor or written in the unit's YAML file (`units/<id>.yaml`). It can also be filled in a spreadsheet: `budget units-export project --out units.csv` (or `.xlsx`) writes one row per power mode, you fill in or change the values, and `budget units-import project units.csv` shows what would change. Add `--apply` to write the changes into the unit files. In the window use *File > Export unit table* and *File > Import unit table*.

- An **empty cell means unchanged**, never zero.
- Only power modes of units that exist are changed; a row with a new power mode name adds that mode (average and peak power are required). Nothing is deleted.
- Values may carry a unit (`800 mW`, `40 %`); a plain number is in the unit named by the column.
- A spreadsheet formula is never calculated; type the value.
- One problem in the table stops the whole import and nothing is written.
- The unit files are edited in place, so comments and the order of keys stay and only the changed lines differ.
