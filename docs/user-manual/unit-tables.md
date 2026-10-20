# Unit power data in a spreadsheet

This page shows how to export the power modes of your units as a table, let a supplier or a colleague fill it in a spreadsheet, and import the values back into the project, checked and without losing anything.

**Contents:** [Export](#how-do-i-export-the-table) · [Fill it in](#how-do-i-fill-it-in) · [Preview and apply](#how-do-i-import-it) · [Rules](#the-rules-of-an-import) · [In the window](#how-do-i-do-this-in-the-window) · [Problems](#what-if-the-import-reports-a-problem)

## How do I export the table?

```bash
budget units-export my_satellite --out units.csv        # or units.xlsx
```

```text
Wrote units.csv
```

You get one row per **power mode** of every unit:

```text
unit_id,unit_name,subsystem,power_mode,avg_power_w,peak_power_w,duty_cycle_ratio,heat_dissipation_ratio,min_duration_s,max_duration_s
adapter,Separation adapter,STRUCT,off,0.0,0.0,1.0,1.0,,
adcs,Attitude control electronics,ADCS,off,0.0,0.0,1.0,1.0,,
adcs,Attitude control electronics,ADCS,safe,4.0,6.0,1.0,1.0,,
```

Without `--out` the file is `<project>/results/unit_power_modes.csv`. A `.xlsx` file has one sheet of values (**Unit power modes**) and a second sheet with instructions. The CSV starts with a byte order mark so that Excel reads the characters correctly. Open it in a spreadsheet program.

## How do I fill it in?

- Change a value, or fill an empty cell. Save as CSV (comma or semicolon separated, UTF-8) or as XLSX.
- A cell may carry a unit: `800 mW`, `2.5 W`, `40 %`. A plain number is in the unit named by the column (`avg_power_w` is watts).
- To **add a power mode** to a unit, add a row with the unit's `unit_id` and a new `power_mode` name, and fill at least `avg_power_w` and `peak_power_w`.
- `unit_name` and `subsystem` are only there for reading; changing them has no effect. Other columns you add are ignored (with a warning).
- Leave a cell **empty** to keep the current value. An empty cell never means zero.

## How do I import it?

First look at what would change. This writes nothing:

```bash
budget units-import my_satellite units_filled.csv
```

```text
camera / imaging: duty_cycle_ratio 0.6 -> 0.8 (row 9)
radio / downlink: avg_power_w 1.8 -> 2 (row 29)
radio / downlink: peak_power_w 4 -> 4.5 (row 29)
radio / burst: avg_power_w (new) -> 3 (row 31)
radio / burst: peak_power_w (new) -> 5 (row 31)
radio / burst: heat_dissipation_ratio (new) -> 0.6 (row 31)
6 values in 3 power modes would change; 27 already as in the table.
Nothing was written. Add --apply to write the changes.
```

Each line gives the unit, the power mode, the field, the old and the new value, and the row of your table. If it is what you intended, write it:

```bash
budget units-import my_satellite units_filled.csv --apply
```

```text
…
6 values in 3 power modes changed; 27 already as in the table.
Wrote units/camera.yaml
Wrote units/radio.yaml
```

The unit files are edited **in place**: your comments and the order of the keys stay, and only the changed lines differ, so `git diff` shows exactly what the import did. Check the result with `budget validate` and compare the budgets before and after with [compare](compare.md).

## The rules of an import

- **Empty means unchanged**, never zero.
- Only power modes of units that **already exist** are touched. An import creates no units (a unit also needs a mass, a bus and a maturity class: use the [unit file](describe-the-spacecraft.md#how-do-i-add-a-unit)) and deletes nothing: a mode or a unit missing from the table stays as it is.
- Every value is checked with the same rules as in the YAML files (peak power not below average power, a ratio between 0 and 1, a matching unit). A dBW value in a watt column is refused.
- **One problem stops everything**: if any row is wrong, nothing is written, so a half-imported table cannot happen.
- A spreadsheet **formula is never calculated**. If a cell holds a formula and the file has no stored result, the cell counts as empty; type the value instead.
- The power-mode numbers have no `source` field, so none is imported. Keep the supplier's document next to the table (or as a comment in the unit file) and raise the project `revision`.
- Limits: 5 MB, 100,000 rows, 50 columns.

## How do I do this in the window?

**File → Export unit table…** writes the table (choose `.csv` or `.xlsx`). **File → Import unit table…** reads a filled-in table and shows a **preview** of every changed value, old and new; choose **Yes** to write them. The window refuses to import while files have unsaved edits (save or discard them first), and reloads the project after a successful import.

## What if the import reports a problem?

```text
units_bad.csv:29: error IMPORT_VALUE_INVALID: Field 'peak_power_w': peak power must not be below average power. (at peak_power_w)
units_bad.csv:32: error IMPORT_UNKNOWN_UNIT: This row names a unit that the project does not have. (at unit_id)
2 errors; nothing was written.
```

The number after the file name is the **row** of your table; `(at …)` is the column. Messages never repeat what you typed. Common ones:

| Code | Meaning and fix |
|---|---|
| `IMPORT_FILE_UNREADABLE` | Not a `.csv` (UTF-8) or `.xlsx` file, damaged, or not found: start from the exported template |
| `IMPORT_FILE_TOO_LARGE` | Over the limits above; check that it is the right file |
| `IMPORT_COLUMN_MISSING` | The `unit_id` or `power_mode` column is missing |
| `IMPORT_UNKNOWN_UNIT` | The row names a unit the project does not have: use the ids of the template |
| `IMPORT_DUPLICATE_ROW` | Two rows for the same unit and power mode: keep one |
| `IMPORT_FIELD_MISSING` | A new power mode has no average or peak power |
| `IMPORT_VALUE_INVALID` | A cell is not a number (comma decimals such as `1,5` are not read), has a wrong unit, or breaks a rule |
| `IMPORT_COLUMN_IGNORED` | (warning) a column that is not part of the template is skipped |

The full list of codes is in [Read and fix problems](read-and-fix-problems.md). Decision: [D-102](../DECISIONS.md).

Next: [Placeholders and sources](placeholders-and-sources.md) · [Power budget](power-budget.md).
