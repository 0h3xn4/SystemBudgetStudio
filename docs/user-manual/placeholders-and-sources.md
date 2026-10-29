# Placeholders and sources

This page explains why some results say *n/a*, why a report may start with an INCOMPLETE banner, and how to enter a number the way the tool wants it.

**Contents:** [The rule](#the-rule-the-tool-never-invents-a-number) · [Enter a sourced number](#how-do-i-enter-a-sourced-number) · [Find what is open](#how-do-i-find-what-is-still-open) · [See everything that is active](#where-do-i-see-everything-that-is-active) · [Record where a plain input came from](#how-do-i-record-where-a-plain-input-came-from) · [Where the numbers live](#which-numbers-need-a-source)

## The rule: the tool never invents a number

Margins, efficiencies, degradation factors, flux values, required Eb/N0 and similar numbers decide whether a budget passes, so a plausible-looking default would be dangerous. The tool ships **none**. Instead every such number lives in a file under `config/` (or in a link, or a thermal file) written with a [`source`](../glossary.md#source). A number whose source is `TBD`, or that has no value, is a **[placeholder](../glossary.md#placeholder)**.

What a placeholder does:

- the project still loads, with the warning `CONFIG_PLACEHOLDER` (and `RESULT_INCOMPLETE` where a result needs it);
- every result that depends on it shows **n/a** (never a silent zero);
- the report starts with the [**INCOMPLETE**](../glossary.md#incomplete) banner: *"some inputs are placeholders (source TBD or missing) … Do not use this report as evidence until the placeholders are replaced with sourced values."*

## How do I enter a sourced number?

Write the number, and where it comes from:

```yaml
power_margin_ratio:
  value: 0.15
  source: "Programme margin policy, section 4"
  note: "optional free text"
```

- `value` is in the unit of the field name (`_ratio` is a plain number: 0.15 means 15 %; `50 %` is also accepted).
- `source` is free text: a document, a data sheet and page, a test report. It is printed next to the number in every report. Write something someone else could look up.
- To mark a number as not yet known, write `value: null` and `source: TBD`.

Do not copy a number from a standard unless you have the text and can cite it. The example projects use `Synthetic example value; not from a data sheet or a standard.` as their source, which is the honest description of invented numbers.

## Where do I see everything that is active?

Some numbers are not in any of your files: the grid on which passes and eclipses are found, the age of a TLE that is warned about, the tolerances of the solvers, the gravity model, the Sun model. The **Assumptions** page (Model area, **View → Show the assumptions**, Ctrl+Shift+A, or Ctrl+K) lists all of them next to your own, with four kinds of rows:

- **Numbers**: every sourced number of `config/` and of the links, with its unit, its source, its status (`sourced`, `estimate`, `illustrative` or `placeholder`) and the file and field to edit;
- **Settings**: the settings, tolerances, limits and constants the tool applies, with their value, why they are what they are and where they act; they are fixed in this version ([the full list](../models/settings.md));
- **Choices**: the environment and the shadow model of each scenario, the load basis of a run, and the models the tool fixes for every project (SGP4, a TLE on WGS-72 and elements on WGS-84, the low-precision Sun, BOL and EOL cases), each with the reason it is fixed ([the full list](../models/choices.md));
- **Forms**: the defaults the guided mode and the forms write into a new project.

The buttons above the list keep one kind; the filter keeps the rows that contain every word you type, in any order. Double-click a row that names a file to open it at the field. The page shows the project as it was last loaded or saved. On the command line: `budget assumptions my_satellite` (`--section`, `--format json`), `budget settings` and `budget choices`.

## How do I record where a plain input came from?

A mass, a power or an orbit element is a plain number in its file, and it can say where it came from too. Add a `provenance:` block at the end of the file, or let the tool write it:

```
budget source my_satellite units/obc.yaml mass_kg --source "Data sheet XYZ rev C, table 3" --status estimate
budget source my_satellite units/obc.yaml "modes[imaging].avg_power_w" --source "Thermal-vacuum test report TR-12" --note "measured at 28 V"
budget source my_satellite units/obc.yaml "*" --source "Invented example value" --status illustrative
```

- The path is the one **Explain** and the Problems panel use; `[imaging]` selects a power mode by its name, so adding or removing a mode does not move the entry. `*` is the default for every number of the file that has no entry of its own.
- The status is `sourced` (the default), `estimate` (an engineering estimate; the source says whose), `illustrative` (an invented sample value, not for use) or `tbd` (a placeholder). The sourced numbers of `config/` can carry `status: estimate` or `status: illustrative` too; `budget source my_satellite config/margin_policy.yaml system_power_margin_ratio --source "…"` sets one.
- In the window, select a number in the **Units** or **Power modes** grid: the **Inspector** shows its **Source** (choose *This input* or *Whole file*, write the source and a note, pick the status, press *Set source*). Each change is one undo step (Ctrl+Z) and is saved with the file like any other edit. The Inputs grid shows the source of a sourced number in its own columns.
- `--clear` removes an entry. The command writes the file in place and keeps its comments; if the file cannot be edited in place and has comments, it stops and says so (`--rewrite` writes the file whole).
- `budget source my_satellite` counts the inputs by status, and `--list illustrative` (or `sourced`, `estimate`, `tbd`, `none`) names them, with their file and path.

Where it shows: **Explain** prints the source of each input (and its status when it is not `sourced`), and every report has the row **Illustrative inputs** in its provenance table, so a report built from invented numbers says so. In the grid of sourced inputs, typing a new value or a new source over a number that has a status (an example's `illustrative` number, say) removes the status: the number is then yours, and you can set a new one with `budget source`. A source changes no number, and the model digest ignores it ([provenance](../models/provenance.md)). A project with no entries works as before; an input with no entry simply has no recorded source, which is not an error. Format: [FILE_FORMAT.md](../FILE_FORMAT.md#sources-statuses-and-required-features-schema-revision-d-213).

## How do I find what is still open?

- `budget validate <project>` lists every placeholder (`CONFIG_PLACEHOLDER`) and empty table (`CONFIG_EMPTY_TABLE`).
- Every report ends with a **Configuration numbers used** table: each number with its value, source and status (`sourced` or `PLACEHOLDER`).
- In the window, the **Problems** panel lists them (**Show problems** opens the list in the focused view, or click the *not checked* link in the status bar); double-click to jump to the field.
- When no placeholder is left that a result needs, the INCOMPLETE banner disappears.

## Which numbers need a source?

| File | Numbers |
|---|---|
| `config/margin_policy.yaml` | power and mass margin per maturity class; system power and mass margin |
| `config/power_config.yaml` | converter efficiency per bus; distribution loss |
| `config/power_system.yaml` | solar array (irradiance, cell area and efficiency, temperatures, losses, degradation), battery (capacity, voltage, efficiencies, fade, initial charge, allowed depth of discharge per phase), peak power limit, design life |
| `config/mass_limits.yaml` | mass limits per phase |
| `config/thermal_model.yaml`, `config/thermal_environment.yaml` | conductances, emissivity and absorptivity, view ratios, solar flux, albedo, Earth infrared, required temperature margin |
| `config/ebn0_table.yaml`, `config/attenuation_table.yaml` | required Eb/N0 per modulation and coding; atmospheric and rain losses |
| `links/<id>.yaml` | RF power, line loss, antenna gain, G/T, required margin and other losses |

The user guide chapter *Equations and sources* lists every equation the tool uses and its source, or `SOURCE_MISSING` where the reference text is still to be attached ([how to build the guide](reports-and-exports.md#how-do-i-get-the-user-guide)). Treat results that rest on such an equation as engineering estimates until your team has confirmed it.

Next: [Power budget](power-budget.md).
