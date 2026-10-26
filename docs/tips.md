# Tips

Shortcuts, working habits and ways to connect System Budget Studio to your other tools, for when you have done the [getting-started](getting-started.md) example.

**Contents:** [Faster work](#faster-work) · [Keep projects healthy](#keep-projects-healthy) · [Scripts and CI](#scripts-and-ci) · [Editor help](#get-completion-in-your-editor) · [Working with the other tools](#working-with-the-other-tools)

## Faster work

- **One click instead of a double-click**: turn on *View → Open with a single click* and a click opens an item of the project tree and edits a selected cell of a grid.
- **Shortcuts in the window**: Ctrl+N new project, Ctrl+O open, Ctrl+S save, F5 reload, Ctrl+M edit a unit's power modes, Ctrl+E export reports, Ctrl+Shift+E export the power timeline, Ctrl+Shift+N / Ctrl+Shift+M / Ctrl+Shift+O add a unit / a spacecraft mode / a scenario, Ctrl+Shift+X / Ctrl+Shift+G / Ctrl+Shift+T / Ctrl+Shift+L add an expendable / a ground station / an imaging target / a link, Ctrl+Shift+F focused view on or off, F1 guide ([all of them](user-manual/use-the-window.md#shortcuts)).
- **Switch the focused view off for the whole picture**: the window opens with the problems as one line, no Inspector or Provenance panel and only the main columns of the grids. *View → Focused view* (Ctrl+Shift+F) shows everything; the choice is remembered.
- **Pin a second cursor** on a plot with a click to read the difference between two times; Escape removes it.
- **Give a plot the whole page**: on *Power → Timeline* and *Link → Passes* the **Table** button folds the table under the plots away.
- **Make the window easier to read**: *View → UI size* (90 to 125 %), *View → Theme*, *View → Reduce motion*; a small laptop screen (1366 x 768) fits every size up to 110 %.
- **Explore with a coarse time step.** While you are trying ideas, set `step_s: 60` in the scenario; the results do not depend on the step in a way that hides a violation, so the numbers stay honest. Set it back for the final run.
- **Get supplier data in without typing**: export the unit power modes with `budget units-export`, let the supplier fill the table, and import it with `budget units-import` (a preview first; `--apply` writes) ([unit tables](user-manual/unit-tables.md)).
- **Run only what you need**: `--budget power`, `--report csv`, `--no-plots` make a run much faster.
- **Start from an example or a blank project**, not from an empty folder: copy the closest one from [`examples/`](../examples/README.md) and replace the numbers, or `budget new` and add your units.
- **Use the guided wizard** (Ctrl+N) to get a working orbit and scenario in a minute, then replace its sample spacecraft with yours, or pick *Blank project* (or run `budget new`) to start with no sample at all.
- **Jump from a problem to the cause** by double-clicking it in the Problems panel (the window starts in the focused view: **Show problems** opens the list, and **F8** does it too), or with **F8** and **Shift+F8**. Ctrl+1 to Ctrl+7 go to the areas of the window, Ctrl+K finds any command, unit or file by a few letters, Ctrl+B shows or hides the project panel, and Ctrl+R runs the scenario, the timeline and the passes.

## Keep projects healthy

- **Put the project folder in git.** Files are plain text with stable formatting: diffs show exactly which number changed. Commit after every sourced number you add; tag the revisions you review.
- **Raise `revision` in `project.yaml`** when you change numbers behind a report; it appears on every output and labels the sides of a [comparison](user-manual/compare.md).
- **Compare before you review**: `budget compare old new` lists what changed between two revisions, so reviewers read the differences, not two whole reports.
- **Keep sources as comments in the unit and scenario files.** The grids, the scenario editor and the unit-table import all edit in place, so a comment such as `# datasheet rev C, table 4` survives every save and `git diff` shows only the lines you changed.
- **Fill in the `source` honestly.** `TBD` is a fine value, and a report that says INCOMPLETE is better than one that looks complete and is not.
- **Look at `budget validate --strict`** before sending a report out: it fails on any placeholder still open.
- **Keep one project per spacecraft design**, with scenarios for the operating cases (commissioning, nominal, safe mode) in the same folder.

## Scripts and CI

```bash
budget validate project --strict --format json > problems.json   # machine-readable problems
budget run project --report csv --report json --out out           # data for other tools
budget power-timeline project --out out || echo "power violations" # exit code 1 on a finding
```

- Exit code 0/1/2 is documented in the [command-line reference](user-manual/command-line.md#exit-codes).
- Pass `--user` and `--date` (or `BUDGET_USER` and `SOURCE_DATE_EPOCH`) so generated reports are reproducible and diff-able.
- The tool writes only into the folder given by `--out`, and needs no network, so it runs in a locked-down build agent.
- A minimal CI job for your project repository: install the tool, `budget validate --strict`, `budget power-timeline`, upload `out/` as an artefact.

## Get completion in your editor

`budget export-schemas schemas` writes one JSON Schema per file kind (`unit.schema.json`, `link.schema.json`, `scenario.schema.json`, …). Editors with YAML support (for example VS Code with a YAML extension) can use them for completion and error squiggles: map each schema to the matching folder in your editor's YAML-schema setting. The schemas are also committed in [`src/budget_core/schemas/`](../src/budget_core/schemas/).

## Working with the other tools

System Budget Studio belongs to a family of offline engineering tools. This is **exactly what exists today**; nothing here is promised that the code does not do.

| Tool | What it is | What exchanges with System Budget Studio today |
|---|---|---|
| **SpaceMissionStudio** | Orbit, eclipse and pass computation | **Import**: a scenario with `environment_source: spacemissionstudio` and an `import_dir` reads orbit, eclipse and pass CSV files in an *interim* format (decision D-055), because no real export was available when it was built. The format is in [ENVIRONMENT_FORMAT.md](ENVIRONMENT_FORMAT.md). When real exports exist, the importer is to be adapted to them. **Export**: nothing is exported to it by a command (a Python helper writes the same files for tests). |
| **Harness Design Studio** | Cable harness design | None. Typical manual use: take unit lists and masses from your harness design, and cite the harness document in each `source`. |
| **Requirements Studio** | Requirements | None. Typical manual use: put the requirement ids in the `source` of the limits they set (`limits.peak_power_w`, a mass limit, a required margin), so a report shows which requirement a limit comes from. |
| **AIT Logbook** | Assembly, integration and test records | None. Typical manual use: attach the XLSX/PDF report (it carries tool version, project revision, time and user) to the log entry for the review it supported. |
| **ICD Studio** | Interface control documents | None. Typical manual use: take bus voltages and link parameters from the ICD, and cite its id and revision as the `source`. |

What *any* of these tools can read today is the tool's own output: **CSV** (one file per table or series), **JSON** (the full result with provenance) and **XLSX**. If you want a direct import or export with one of the tools, say which data should travel in which direction; it would be added as a decision in [DECISIONS.md](DECISIONS.md) and tested like the rest.

Next: [FAQ](faq.md) · [Glossary](glossary.md) · [User manual](user-manual/README.md).
