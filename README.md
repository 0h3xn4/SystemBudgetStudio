# System Budget Studio

An offline desktop and command-line tool that computes **power, mass, thermal and radio-link budgets** for a small satellite from one spacecraft model kept in plain text files.

[![CI](https://github.com/0h3xn4/systembudgetstudio/actions/workflows/ci.yml/badge.svg)](https://github.com/0h3xn4/systembudgetstudio/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/0h3xn4/systembudgetstudio)](https://github.com/0h3xn4/systembudgetstudio/releases/latest)
![Python 3.11 to 3.13](https://img.shields.io/badge/python-3.11%20to%203.13-blue)
[![Licence: MIT](https://img.shields.io/badge/licence-MIT-green)](LICENSE)

![System Budget Studio showing the power timeline of the example CubeSat: generation, demand and state of charge over one orbit, with eclipse shading and a list of problems](docs/images/power-timeline.png)

## What is this?

Satellite teams keep power modes, eclipse cycles, battery depth of discharge, masses, temperatures and link margins in spreadsheets that drift apart. System Budget Studio replaces them with one model: you describe the spacecraft (units and their power modes, solar array, battery, radios, antennas), an orbit and some ground stations, and the tool computes the budgets, shows where a limit is broken, and writes reports.

It runs entirely on your own computer. There is no cloud service, no telemetry and no update check. Every number you enter carries its **source**, every number you have not yet sourced is marked as a **placeholder** (and the results that depend on it say *n/a* instead of guessing), and the same input always gives the same output files.

If you know a little Python and nothing about this tool, start with the [getting-started guide](docs/getting-started.md).

## Install

Download the installer for your system from the [Releases page](https://github.com/0h3xn4/systembudgetstudio/releases/latest). No Python is needed; nothing needs administrator rights.

| System | File | What to do |
|---|---|---|
| Windows 10/11 | `system-budget-studio-<version>-windows-x64-setup.exe` | Run it. A portable `…-portable.zip` also exists: extract it and start `system-budget-studio.exe`. |
| Linux (RHEL/Rocky 8 or newer, Ubuntu LTS) | `system-budget-studio-<version>-linux-x86_64.tar.gz` | `tar xzf` it, `cd system-budget-studio`, run `./install.sh`. |

Check the download against `SHA256SUMS-windows.txt` or `SHA256SUMS-linux.txt` from the same page. The installers are unsigned, so Windows may show a warning on first run. Details, uninstalling and the Linux libraries the window needs are in [getting started](docs/getting-started.md#installers). To work on the code or run from source, use the quick start below.

## Quick start (from source)

You need Python 3.11, 3.12 or 3.13 and git. On Linux also read the [prerequisites](docs/getting-started.md#1-prerequisites) (the window needs one system library).

```bash
git clone https://github.com/0h3xn4/systembudgetstudio.git
cd systembudgetstudio
python3 -m venv .venv && source .venv/bin/activate     # Windows: py -3 -m venv .venv ; .venv\Scripts\Activate.ps1
pip install -e .
budget --version                                       # System Budget Studio 1.0.0
budget export-examples demo                            # four example projects with invented data
budget validate demo/cubesat_3u_eps                    # check the project: 0 errors, a few warnings
budget run demo/cubesat_3u_eps --budget power --out out   # power budget as XLSX, PDF, DOCX, JSON and CSV
system-budget-studio demo/cubesat_3u_eps               # open the window
```

The reports in `out/` are the first result. [Getting started](docs/getting-started.md) shows what you should see at each step and walks through a first worked example.

## Where to go next

| I want to… | Read |
|---|---|
| Install the tool and get a first result | [Getting started](docs/getting-started.md) |
| See every guide on one page | [Documentation index](docs/README.md) |
| Do a specific task (build a project, run a budget, compare two revisions…) | [User manual](docs/user-manual/README.md) |
| Look at the example projects and what they show | [Examples](examples/README.md) |
| Fix an error message | [Troubleshooting](docs/troubleshooting.md) and the [FAQ](docs/faq.md) |
| Look up a word (BOL, EIRP, Eb/N0, placeholder…) | [Glossary](docs/glossary.md) |
| Work faster | [Tips and shortcuts](docs/tips.md) |
| See the file format of a project | [Project file format](docs/FILE_FORMAT.md) |
| Understand how the tool is built, or contribute | [Contributing](CONTRIBUTING.md) and [developer docs](docs/developer/README.md) |
| See what changed | [Changelog](CHANGELOG.md) |

## Features

- **Power budget**: average and peak power per spacecraft mode with maturity and system margins; a time-domain budget over an orbit scenario (solar array, battery, state of charge, depth of discharge, energy balance per orbit) for beginning and end of life, with every violation time-stamped.
- **Mass budget**: roll-up with margins, centre of gravity and inertia, mission phases and mass limits.
- **Thermal budget**: heat dissipation per unit, subsystem and mode, and a steady-state node model with hot and cold cases checked against unit temperature limits.
- **Link budget**: EIRP, path loss, G/T, C/N0, Eb/N0 and margin at chosen elevations, and over every ground-station pass with the data rate that closes and the data volume per pass and per day; uplink and downlink; several links per project.
- **Scenarios**: eclipses and passes from a two-line element set (TLE) or orbital elements, a mode timeline built from rules (for example "downlink during every pass") and segments; orbits can also be imported from [SpaceMissionStudio](docs/ENVIRONMENT_FORMAT.md).
- **Reports**: XLSX, PDF and DOCX in classic review layouts, CSV for every table and series, JSON for other tools. Every output carries provenance (tool and library versions, project revision, scenario, time, user) and is reproducible byte for byte.
- **Comparison**: two project revisions, or two scenarios, side by side with the differences listed.
- **Guided mode**: a wizard from an orbit to a first budget with a sample spacecraft; an offline user guide (HTML and PDF) with a generated *Equations and sources* chapter.
- **Plain-language problems**: every message names the file and field, says what is wrong and what to change; a double-click jumps to it.

Unit power modes can be exported to a CSV or XLSX table, filled in a spreadsheet and imported back with a preview ([unit tables](docs/user-manual/unit-tables.md)).

Not in version 1: data-storage budgets, transient thermal simulation, interference analysis, a separate expert mode. See [decision D-099](docs/DECISIONS.md).

## Requirements

- Python 3.11, 3.12 or 3.13 (checked in CI on Windows and Ubuntu with 3.11 and 3.13).
- Windows 10/11 or Linux (RHEL/Rocky 8 or newer, Ubuntu LTS). macOS is not tested.
- No administrator rights and no internet access are needed after the install. For an air-gapped machine see [offline install](docs/getting-started.md#offline-install).
- The installers above are self-contained; Python is needed only to install from source.

## Licence and status

Released under the [MIT licence](LICENSE) (decision D-140). Third-party licences are listed in [docs/LICENCES.md](docs/LICENCES.md) (the program uses PySide6 under the LGPL-3.0, and IBM Plex fonts under the SIL Open Font License, see [assets/fonts](assets/fonts/OFL-IBM-Plex.txt)).

Status: version 1.0.0, all planned milestones (M0 to M6) are done and tested ([plan and history](docs/PLAN.md)), and the tool went through a full pre-release audit ([AUDIT.md](AUDIT.md)). The example projects contain **invented data only**; the tool ships no standards values, so every real number, with its source, is yours to enter.

Known limits, stated plainly:

- The results are engineering estimates, only as good as the numbers and sources you enter; the equations are checked against hand calculations, not against a flight project.
- The installers are built and tested by CI (install, self-test, uninstall) but have not yet been run by hand on clean Windows and Rocky 8 machines ([checklist](docs/INSTALL_CHECKLIST.md)).
- An eclipse shorter than about 20 s can be missed ([DV-E4](docs/DEVIATIONS.md)); error messages go to standard output; hovering over a plot of a week at 1 s resolution repaints slowly.
- The XLSX files were not opened in Excel.

## Related tools

System Budget Studio belongs to a family of offline engineering tools: SpaceMissionStudio (orbit, eclipse and pass data; the only tool this one reads from today), Harness Design Studio, Requirements Studio, AIT Logbook and ICD Studio. [Tips](docs/tips.md#working-with-the-other-tools) says exactly what can be exchanged with each.

Next: [Getting started](docs/getting-started.md).
