# Getting started

This page takes you from nothing to a first result: install the tool, run a budget on an example project, open the window, and fix a violation the tool finds.

**Contents:** [1. Prerequisites](#1-prerequisites) · [2. Install](#2-install) · [3. Check the install](#3-check-the-install) · [4. Your first budget](#4-your-first-budget) · [5. A first worked example: find and fix a power violation](#5-a-first-worked-example-find-and-fix-a-power-violation) · [6. Open the window](#6-open-the-window) · [Offline install](#offline-install) · [Installers](#installers)

## 1. Prerequisites

| You need | Check with | Notes |
|---|---|---|
| Python 3.11, 3.12 or 3.13 | `python3 --version` (Windows: `py -3 --version`) | 3.14 and newer are not supported yet. |
| git | `git --version` | Only to download the source. You can also download a ZIP from GitHub. |
| A terminal | | Windows: PowerShell. Linux/macOS: any shell. |

**Linux only: one system library for the window.** The Qt window needs `libxcb-cursor0`. Without it the window does not open and you see *"Could not load the Qt platform plugin xcb"* (see [troubleshooting](troubleshooting.md#the-window-does-not-open-on-linux)). The command-line tool does not need it.

```bash
sudo apt install libxcb-cursor0          # Ubuntu / Debian
```

On RHEL or Rocky the window needs the Qt libraries listed in the user guide chapter *Installing and uninstalling* ([source](../src/budget_core/guide/chapters/12-installation.md)), and `xcb-util-cursor`, which is not in their own repositories but in EPEL: `sudo dnf install epel-release` (on RHEL itself: the `epel-release` package from the Fedora project's EPEL page), then `sudo dnf install xcb-util-cursor`.

**macOS** is not tested. The tool should run from source (Python and Qt are cross-platform), but nobody has checked it.

## 2. Install

Use a virtual environment so the tool's libraries stay out of your system Python.

Linux and macOS:

```bash
git clone https://github.com/0h3xn4/systembudgetstudio.git
cd systembudgetstudio
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Windows (PowerShell):

```powershell
git clone https://github.com/0h3xn4/systembudgetstudio.git
cd systembudgetstudio
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
```

If PowerShell says *running scripts is disabled*, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned` once in that window and activate again.

`pip install -e .` installs the runtime libraries only (PySide6, pydantic, numpy, sgp4, ReportLab, openpyxl, python-docx, pint, Pillow, ruamel.yaml). It takes about a minute and needs no compiler. After it, two commands exist inside the environment:

- `budget`: the command-line tool;
- `system-budget-studio`: the window.

Every time you open a new terminal, activate the environment again (`source .venv/bin/activate`, or `.venv\Scripts\Activate.ps1`) from the repository folder.

## 3. Check the install

```bash
budget --version
budget self-test
```

You should see:

```text
System Budget Studio 1.0.0
Self-test passed.
```

`self-test` computes a small budget and renders it as XLSX, PDF and DOCX, and builds the user guide, using only the installed files. If it fails, it says what; see [troubleshooting](troubleshooting.md).

## 4. Your first budget

The tool ships four example projects with **invented data**. Copy them somewhere you can write:

```bash
budget export-examples demo
```

```text
microsat_150kg
microsat_250kg
microsat_250kg_eps
stress_200_units
```

Check one project. `validate` reads every file of the project folder and lists what is wrong or still open:

```bash
budget validate demo/microsat_250kg_eps
```

```text
config/margin_policy.yaml:9: warning CONFIG_PLACEHOLDER: This number is a placeholder (no value or source 'TBD'); results that use it are not trustworthy. (at classes.class_a.mass_margin_ratio)
    Replace it with a value from your margin policy, standard or data sheet and cite the source.
…
0 errors, 5 warnings.
```

Reading it: each problem is `file:line: severity CODE: message (at field)` and a hint on the next line. **Warnings** are open items, here the *[placeholders](glossary.md#placeholder)*: numbers the tool will not invent (the margin policy and the mass limit). **Errors** would stop a budget from being computed. Add `--strict` to treat warnings as failures too.

Compute the static power budget and write the reports:

```bash
budget run demo/microsat_250kg_eps --budget power --out out
```

```text
Wrote out/power_static.xlsx
Wrote out/power_static.pdf
Wrote out/power_static.docx
Wrote out/power_static.json
Wrote out/power_static_charging.csv
Wrote out/power_static_downlink.csv
…
Wrote out/power_static_provenance.csv
0 errors, 5 warnings.
```

Open `out/power_static.xlsx` (or the PDF). You see the average and peak power of each spacecraft mode, with and without margins; the last sheets list the configuration numbers used with their sources, the equations, the problems and the provenance. Entries that depend on a placeholder show **n/a** and the report starts with an **INCOMPLETE** banner: that is the tool refusing to present guesses as results. Leave out `--budget power` to compute power, mass, thermal and link budgets in one go.

## 5. A first worked example: find and fix a power violation

Question: *does the 250 kg example satellite's solar array and battery support its operating modes over one day?* This needs the time-domain budget, which steps through an orbit scenario.

**Step 1: run it.**

```bash
budget power-timeline demo/microsat_250kg_eps --out out
```

```text
Wrote out/power_time_one_day.xlsx
…
BOL: generated 2399.2 Wh, lowest state of charge 82.7 %, 16 violation(s).
EOL: generated 2060.3 Wh, lowest state of charge 79.7 %, 16 violation(s).
config/power_system.yaml: error PEAK_POWER_EXCEEDED: The peak power demand at the source exceeds the power limit. 16 interval(s), the first at T+00:02:06. (at limits.peak_power_w)
    Open the violations table for every interval; change the input named here or the scenario.
1 error, 5 warnings.
```

**What it says.** BOL and EOL are *[beginning* and *end of life](glossary.md#bol-eol)* (the array is new, or aged by its design life; see the [glossary](glossary.md)). The battery never gets below 79 % charge, so there is no battery problem. But the demand at the power source exceeds the **[peak power limit](glossary.md#peak-power)** during 16 intervals, the first starting 2 minutes 6 seconds into the scenario. The command ends with exit code 1 because it found an error; scripts can use that.

**Step 2: look at the details.** `out/power_time_one_day_violations.csv` has one row per interval, with start and end time, the worst value, the limit and the input to change:

```text
case,code,start_s,end_s,duration_s,…,worst_value,limit,unit,file,path
,PEAK_POWER_EXCEEDED,126.126,619.344,493.218,…,247.766323,180.000000,W,config/power_system.yaml,limits.peak_power_w
```

The worst demand is 247.8 W and the limit is 180 W, in `config/power_system.yaml` at `limits.peak_power_w`. The intervals are mostly the downlink passes: the radio transmits while the camera and the attitude control are on.

**Step 3: decide.** You can reduce the demand (change the scenario or the radio's modes) or change the limit **if you have a better, sourced value**. For this example we only want to see the effect, so raise the invented limit. Open `demo/microsat_250kg_eps/config/power_system.yaml` in a text editor and find:

```yaml
limits:
  peak_power_w:
    value: 180.0
    source: Synthetic example value; not from a data sheet or a standard.
```

Change `value: 180.0` to `value: 260.0`. In a real project you would also change the `source` to say where the new number comes from.

**Step 4: run again.**

```bash
budget power-timeline demo/microsat_250kg_eps --out out
```

```text
BOL: generated 2399.2 Wh, lowest state of charge 82.7 %, 0 violation(s).
EOL: generated 2060.3 Wh, lowest state of charge 79.7 %, 0 violation(s).
0 errors, 5 warnings.
```

Exit code 0: the violation is gone (the radio's thermal finding is a separate check; see the [examples](../examples/README.md)). You have now done the core loop of the tool: **describe, compute, read the findings, change an input, compute again**. To see exactly what a change did, [compare the two revisions](user-manual/compare.md).

## 6. Open the window

```bash
system-budget-studio demo/microsat_250kg_eps
```

You should see the window below: the **top bar** (project, revision, scenario, BOL and EOL, **Run** and the run status), the **project tree** on the left, seven **tabs** (Model, Power, Mass, Thermal, Link, Compare, Reports), and on the right the **Inspector**, **Problems** and **Provenance** panels.

![The Power budget tab of the 250 kg example satellite: a table of average and peak power for each spacecraft mode, with the project tree on the left and the Problems panel below](images/power-budget.png)

- **Power → Budget** is the table you saw in the XLSX file; **Mass**, **Thermal** and **Link → Budget** are the other static budgets. Cells with `n/a` have a marker and a tooltip that says which kind of input is missing.
- Press **Run** (Ctrl+R) to work out the scenario you ran above, the power timeline and the link passes in one go; the chip next to it says when they are up to date. In **Power → Timeline**, hover over a plot to read the values at that time; the wheel zooms, dragging pans, a double-click shows everything again, a click pins a second cursor (the readout then shows differences) and Escape unpins it. The shaded bands are eclipses and passes. Click a row of the **Violations** table to zoom to that interval.
- Double-click (or Enter on) a row of the **Problems** panel to jump to the file and line it names; **F8** goes to the next problem. Press Enter on a file in the tree to edit it; **Ctrl+S** saves, and the budgets update. If you make a mistake the tables keep the last results that worked, with a yellow banner that says so.
- **File → Export reports** (Ctrl+E), or the **Reports** tab, writes the same files as the command line.
- **File → New project (guided)** (Ctrl+N) builds a new project from a sample spacecraft in five short pages.

On Linux without a display (a server, a container) set `QT_QPA_PLATFORM=offscreen` to run the window without showing it. That is only useful for tests: `system-budget-studio --smoke` creates the window and exits.

## Offline install

The tool never needs the internet while running. To install it on a machine without internet access, first collect the wheels on a connected machine **of the same operating system and Python version**:

```bash
pip download -r requirements.lock -d wheelhouse     # the runtime libraries, pinned with hashes
pip download hatchling editables -d wheelhouse      # needed to build the package itself
```

Copy `wheelhouse/` and the source folder to the offline machine, create the virtual environment there, and run from the source folder:

```bash
pip install --no-index --find-links wheelhouse --require-hashes -r requirements.lock
pip install --no-index --find-links wheelhouse --no-deps -e .
budget --version
```

The lock file (`requirements.lock`) pins every runtime library with a hash, so what you install is exactly what was tested.

## Installers

The [Releases page](https://github.com/0h3xn4/systembudgetstudio/releases/latest) has a Windows installer (per user, no administrator rights), a Windows portable ZIP, a Linux tarball with `install.sh` (per user, no administrator rights), a `.deb` for Ubuntu and Debian and an `.rpm` for RHEL and Rocky (both for all users, installed with `sudo apt install ./file.deb` or `sudo dnf install ./file.rpm`, and they bring in the system libraries the window needs; on RHEL and Rocky enable EPEL first with `sudo dnf install epel-release`), with `SHA256SUMS-windows.txt` and `SHA256SUMS-linux.txt` to check the downloads; or install from source as above. The steps are in the user guide chapter *Installing and uninstalling* ([source](../src/budget_core/guide/chapters/12-installation.md)) and the [clean-machine checklist](INSTALL_CHECKLIST.md).

Next: the [user manual](user-manual/README.md) (task by task), the [examples](../examples/README.md), or [troubleshooting](troubleshooting.md) if something did not work.
