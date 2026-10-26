# Troubleshooting

This page lists the errors you are most likely to meet when installing and starting the tool, with the exact text and the fix. Messages about your *project files* (problem codes such as `UNIT_INVALID`) are in [Read and fix problems](user-manual/read-and-fix-problems.md).

**Contents:** [Install](#install) · [Start the window](#start-the-window) · [Run a command](#run-a-command) · [Results](#results) · [Still stuck](#still-stuck)

## Install

### `pip install -e .` fails with "requires a different Python" or "No matching distribution"

The tool supports Python 3.11, 3.12 and 3.13 (not 3.14 or newer, not 3.10 or older). Check `python3 --version`, install a supported one, and create the virtual environment with it: `python3.13 -m venv .venv`.

### `pip` says "externally-managed-environment"

Your system Python refuses installs outside a virtual environment. Create one (`python3 -m venv .venv`, then activate it) as in [getting started](getting-started.md#2-install) and run `pip install -e .` inside it.

### `budget: command not found` (or `'budget' is not recognized`)

If you installed from source, the virtual environment is not active in this terminal. Activate it from the repository folder: `source .venv/bin/activate` (Windows: `.venv\Scripts\Activate.ps1`). Your prompt then starts with `(.venv)`.

If you used the **Windows setup** (1.3.1 or newer), it has put its folder on your user PATH, but a terminal that was already open does not see that: open a new one. If you used the portable zip, or a setup older than 1.3.1 where the PATH option was not ticked, run `budget.exe` by its full path, or add the folder to your PATH yourself.

If you used the **Linux tarball**, `install.sh` links `budget` into `~/.local/bin`; make sure that folder is on your `PATH`, and add it to your shell's start-up file if your distribution does not. The `.deb` and `.rpm` link it into `/usr/bin`.

### PowerShell: "running scripts is disabled on this system"

Run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned`, answer `Y`, then activate again. It only affects that window.

### `pip install` cannot reach the internet

On a machine without internet access, use a wheelhouse: [offline install](getting-started.md#offline-install).

## Start the window

### The window does not open on Linux

```text
qt.qpa.plugin: From 6.5.0, xcb-cursor0 or libxcb-cursor0 is needed to load the Qt xcb platform plugin.
qt.qpa.plugin: Could not load the Qt platform plugin "xcb" in "" even though it was found.
This application failed to start because no Qt platform plugin could be initialized.
```

A system library is missing. On Ubuntu or Debian: `sudo apt install libxcb-cursor0`. On RHEL or Rocky install the Qt libraries listed in the user guide chapter *Installing and uninstalling* ([source](../src/budget_core/guide/chapters/12-installation.md)) and `xcb-util-cursor`, which is in EPEL and not in their own repositories: `sudo dnf install epel-release`, then `sudo dnf install xcb-util-cursor`. The command-line `budget` does not need it. To see what else is missing: `QT_DEBUG_PLUGINS=1 system-budget-studio`.

### "This plugin does not support propagateSizeHints()"

A harmless Qt message, printed when the window starts on some Linux set-ups (and always under `QT_QPA_PLATFORM=offscreen`). Ignore it.

### No window appears, but there is no error (Linux over SSH or in a container)

There is no display. Use the command line, or run with a display (X forwarding, a desktop session). For tests set `QT_QPA_PLATFORM=offscreen`; `system-budget-studio --smoke` then creates the window and prints `Smoke test passed.`

## Run a command

### `<project>: error FILE_NOT_FOUND: The project folder does not exist.`

The path is wrong. A project folder contains `project.yaml`. Run `budget validate <folder>`; if you are in the wrong directory, give the path relative to where you are or an absolute path.

### `spacecraft.yaml: error FILE_NOT_FOUND: The file cannot be read.`

The folder exists but is not a project (for example an empty folder), or a file is missing. Compare with an example: `budget export-examples demo` and look at `demo/microsat_250kg`.

### `A file could not be written. Check that the output folder exists, is a folder and that you may write to it.`

`--out` points at a file, a folder you cannot write to, or a path that does not exist and cannot be created. Choose a folder you own. Without `--out` the tool writes to `<project>/results`, so the project folder itself must be writable.

### `Two outputs would be written to the same file name.`

Two units, links, phases or cases have names that become the same file name (file names keep only letters, digits, `.`, `-`, `_`). Rename one.

### `budget new`: `The folder 'x' already exists.` or `the following arguments are required: --bus-voltage-v`

`budget new` never touches an existing folder: give a folder that does not exist yet. The bus voltage has no default, because it is your design value: give it in volts (`--bus-voltage-v 28`; it must be between 1 and 1000). See [a blank project](user-manual/create-a-project.md#how-do-i-start-a-blank-project).

### `<project>: error SCENARIO_UNKNOWN: Scenario 'x' does not exist.`

The `--scenario` id is wrong. The message ends with the list of scenarios the project has (`Defined scenarios: one_day.`); the id is the file name in `scenarios/` without `.yaml`.

### `budget run: error: argument --budget: invalid choice`

You gave a value the option does not accept; the message lists the allowed ones. Exit code 2.

### `Give a second project folder, or two different scenarios (--scenario-a and --scenario-b) of the same project.`

`budget compare` needs two sides. Give two folders, or `--scenario-a` and `--scenario-b` that differ. See [compare](user-manual/compare.md).

### The command wrote all its files but exited with code 1

By design: an error-level *finding* (a limit exceeded) makes the exit code 1. Read the last lines of the output. The `microsat_250kg_eps` example does this on purpose ([examples](../examples/README.md#exit-codes-in-the-examples)).

### `A file or folder could not be read or written. Check the paths and that you may use them.`

A permission or path problem that is not one of the cases above (for example a read-only disk or a missing parent folder). Check the paths and your permissions.

### `Internal error (SomeError). Run 'budget validate <project folder>' to check the project and report the problem.`

A bug. The message names only the kind of error, never your data. Run `budget validate <project>` for details and report it with the error name.

## Results

### Results say `n/a` and the report starts with INCOMPLETE

A number the result needs is a placeholder. That is intended: see [placeholders and sources](user-manual/placeholders-and-sources.md).

### The output folder has only some of the files, or the tool says a file could not be written

The files of a run are written under temporary names first, so a failing write leaves the old files untouched. The message names the file; check that the folder exists, that you may write there and that the disk is not full. If the message lists files as "already replaced", the failure came while moving the files into place: run the command again.

### Two outputs would be written to the same file name

Two ids differ only in case or in characters a file name cannot hold (`hot` and `Hot`), or an id equals a name the tool generates (a mode called `provenance`, a link called `summary`). The message names the file. Rename one id.

### A `?` in the PDF where a name has non-Latin letters

The bundled PDF font has no glyphs for CJK or emoji. The PDF shows `?` and a note gives the count; the XLSX, DOCX and JSON files hold the original text.

### `BOL: n/a (inputs missing, see the problems below).`

The power timeline needs `config/power_system.yaml` with a complete array and battery, a scenario and a mission phase; the examples `microsat_250kg`, `microsat_150kg` and `stress_200_units` have templates only. Use `microsat_250kg_eps`, or fill in the numbers.

### Same inputs, different file bytes

Reports include the generation time and the user. Pass `--user` and `--date` to regenerate exactly: [reports and exports](user-manual/reports-and-exports.md#how-do-i-regenerate-a-report-exactly).

### The run is slow

A week at 1 s with 200 units takes about ten seconds; the orbit computation dominates. While exploring, use a larger `step_s` in the scenario, and with `power-timeline` or `link-passes` add `--no-plots`, `--report csv` or (power-timeline) `--series-every N`.

### The window does not close, or says "The window closes when it is done"

A computation or an export is still running in the background; stopping it half way could damage the output, so the window waits and closes by itself when the job has finished (a long timeline can take a minute). Quitting again does nothing harmful.

### Export is switched off, or says "out of date" / "changed since this result was computed"

The result on screen was computed from different inputs than the ones set now: the project was reloaded or saved, another scenario or demand basis is selected, or the other folder in **Compare** changed. The run status in the top bar says **Out of date**. Press **Run** (or **Compute** in the view, or **Compare**) again, then export.

### A yellow banner says the tables show the last results that worked

The project has an error since you last saved. The budget tables are kept from before it so you can see what your change did, and nothing can be exported from them. Press **Show the first error** in the banner, fix it, save; the banner goes when the project loads.

### A panel is missing or the window looks wrong

A new window starts in the **focused view**: the Problems panel is one line of counts (press **Show problems** for the list), the Inspector and Provenance panels are hidden and the grids hide their optional columns (the **Optional columns** button shows them). **View → Focused view** (Ctrl+Shift+F) turns it off and shows everything. If something else is missing, **View → Reset layout** restores the panels, their sizes and the Problems columns. The panels can also be switched on in the **View** menu. The window layout is kept in `layout.ini` (see [use the window](user-manual/use-the-window.md#where-does-the-window-keep-its-layout)); deleting that file does the same.

### Add unit says "The spacecraft has no bus", or the form will not accept the subsystem

A unit needs a bus, so add one in `spacecraft.yaml` first (a project made with `budget new` or the wizard has one). With a thermal model in the project, the **subsystem** must be the name of one of its nodes (the form suggests them), or add the node to `config/thermal_model.yaml` first. The mass and the powers have no default: the form refuses an empty one. See [add a unit](user-manual/describe-the-spacecraft.md#how-do-i-add-a-unit).

### A spacecraft mode: "The project has no unit yet", "has no power mode of that name", or "is used by the scenario(s)"

A spacecraft mode says what every unit is doing, so **Add spacecraft mode** needs at least one unit: add it first. In the *Spacecraft modes* grid a cell takes only a power mode the unit has (the message lists them); add the power mode to the unit in *Power modes* first. **Remove spacecraft mode** is refused while a scenario names the mode, as its default mode, in a rule or in a segment: change the scenario (*Model → Scenario*) and remove the mode afterwards. See [add a spacecraft mode](user-manual/describe-the-spacecraft.md#how-do-i-add-a-spacecraft-mode).

### Add scenario: "add a spacecraft mode first", or a number is refused

A scenario says which spacecraft mode is active, so **Add scenario** needs one: add it first (Edit → Add spacecraft mode). The form takes an altitude of 160 to 2000 km, an inclination of 0 to 180 degrees, a RAAN of 0 up to (not including) 360 degrees, a start in UTC with a trailing Z and no offset (`2026-06-01T00:00:00Z`) and a length above 0 and at most 180 days, and, for an elliptical orbit, an apogee altitude of at least the altitude and at most 40,000 km with an argument of perigee of 0 up to (not including) 360 degrees; the line under the form says which answer is wrong. See [add an orbit and a scenario](user-manual/scenarios.md#how-do-i-add-an-orbit-and-a-scenario-in-the-window).

### Add expendable: a phase mass is refused, or the id exists

An expendable needs a mass in **every** mission phase of the spacecraft (`PHASE_MASS_MISSING` otherwise): write 0 for a phase in which it is not on board. The form has one field per phase and refuses an empty one, a negative one and a position with fewer than three coordinates (all three or none). The id is the file name `expendables/<id>.yaml`; an id that differs from another only in capitals counts as the same. A bipropellant is two expendables, fuel and oxidizer, added one after the other. See [phases and propellant](user-manual/mass-budget.md#how-do-i-handle-mission-phases-and-propellant).

### Add ground station or Add imaging target: a number is refused, or the id exists

The latitude is between -90 and 90 degrees, the longitude between -180 and 180, the altitude between -1000 and 100000 m and the minimum elevation at least 0 and less than 90 degrees; none has a default and the line under the form says which answer is wrong. A scenario names a station or a target by id, so an id may not be used by both (nor differ only in capitals). Adding a site does not put it in a scenario: tick it under **Sites** in *Model → Scenario*. See [ground stations and targets](user-manual/scenarios.md#how-do-i-add-a-ground-station-or-an-imaging-target).

### Add link: "add a ground station first", or the modulation and coding are refused

A link joins the spacecraft and a ground station, so **Add link** needs one: add it first (Edit → Add ground station). The ground station is chosen from the list, the frequency is in **megahertz** (2200 for 2.2 GHz; a value in hertz is refused) and the data rates are in bit/s, separated by semicolons. The modulation and coding must be a pair of `config/ebn0_table.yaml` (the loader refuses any other, `REF_UNKNOWN_MODULATION`); while that table has no entry you type them. The transmit power, the antenna gain, the G/T, the required margin and the losses are written as placeholders, so the link shows *n/a* and the Problems panel lists them until you fill them in *Model → Inputs*. See [describe a link](user-manual/link-budget.md#how-do-i-describe-a-link).

### Save asks "Saving deletes 1 file from the project folder"

You removed a unit with **Remove unit**. Saving deletes its file (`units/<id>.yaml`) and takes it out of every spacecraft mode. Answer **No** to keep the file, then **Undo** (Ctrl+Z) the removal. A deleted file is not in the undo history any more.

### "The file ... changed on disk after it was opened in this tab"

Another program (or a git checkout) changed the file while you had it open with unsaved edits. Answer **No**, copy your edit elsewhere, press F5 to load the new file, and apply your edit again; answer **Yes** only if your version should win.

## Still stuck

1. Run `budget self-test`. It checks the installation and says what failed.
2. Run `budget validate <project>` and read the first error: later ones are often consequences.
3. Search the [FAQ](faq.md).
4. For a bug, collect the output of `budget --version`, the command you ran and the message. Do not attach project files if they may be sensitive; messages never contain your values.

Next: [FAQ](faq.md) · [Glossary](glossary.md).
