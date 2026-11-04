# Start a project from an IDM-CIC model

Reads models from IDM-CIC (© CNES). IDM-CIC is software of the French space agency CNES for the early design of satellites. System Budget Studio is independent of it: it reads the model file with its own code, needs no CNES software, and CNES does not endorse or support this tool.

**Contents:** [What it does](#what-does-the-import-do) · [First import](#how-do-i-start-a-project-from-a-model) · [Margins](#how-are-margins-handled) · [System modes](#how-do-system-modes-become-spacecraft-modes) · [Import again](#what-happens-when-i-import-the-model-again) · [Not imported](#what-is-not-imported) · [Problems](#what-do-the-messages-mean)

## What does the import do?

An IDM-CIC model holds the structure of a satellite with its equipment, masses, power modes and thermal modules. It does not compute an orbit power balance, a thermal network, a link budget or a reproducible report; this tool does. The import turns the model into the units, spacecraft modes, margin classes, thermal nodes and propellant of a project, with the source of every value recorded, so that you can run the budgets on it. It reads the model only: it never writes to the model file.

## In the window

**File → Import IDM-CIC model…** (also in the Ctrl+K palette) asks for the model file. With a project open you choose between updating it and creating a new project; for a new project you pick the folder in which the project folder is made and give the nominal voltage of the bus (a number, not a default: the model has none). Then you choose the margins option (see below). The model is read and the plan worked out in the background, and the window shows the summary, with the details one click away. Nothing is written until you answer **Yes**; the project is then opened, or reloaded. The window refuses to update a project that has unsaved edits (save or discard them first).

## How do I start a project from a model?

```bash
budget import idm satellite.idm --project my_satellite --bus-voltage-v 28
```

Without `--apply` this only shows the plan:

```text
IDM-CIC model satellite.idm (revision 78b4c9905d16), format 3.4.0.19.
Project: my_satellite (new).
Units: 123 added.
Spacecraft modes: 4 added.
Expendables: 2 added.
info IDM_MARGIN_NOT_APPLIED x2: A margin or target of an element is not applied
    el.1
    el.2
warning IDM_MASS_UNRESOLVED x1: An equipment occurrence is not imported because its mass is not known
    el.1_ss.STR_assi.1-1_eqi.2-1
Files: 139 to create, 0 to update.
Nothing was written. Add --apply to write 139 file(s).
```

Add `--apply` to write the project. A new project needs `--bus-voltage-v`: the model does not give the nominal voltage of the power bus, and the tool does not invent one. The bus is called `main` unless you give `--bus`. The one power bus is a simplification of the model: change a unit's bus in its file if you need more.

What you get:

- one **unit** for every physical copy of an equipment (an equipment placed twice is two units; the equipment inside a placed assembly counts once for each placed copy). The unit id is made from the object's identifier in the model, the name from the element, the assembly and the equipment;
- the **mass** of the equipment, its **power modes** (power as average and as peak, with the peak marked as an estimate because the model gives one number; the heat share is dissipation divided by power), its **temperature limits** (degrees Celsius in the model, kelvin in the project) and its **thermal node**;
- one **spacecraft mode** for every system mode, with the power mode of every unit;
- **maturity classes** `idm_…` in `config/margin_policy.yaml`, **thermal nodes** in `config/thermal_model.yaml`, a **mission phase** for every configuration of the model (and `reference`, the defaults), and an **expendable** for every tank;
- `idm/mode_map.yaml` and `idm/import_state.yaml`, see below.

Every imported value has a source: the model file name, its revision (a short hash of the content) and the object's identifier. Look at it with the Inspector, `budget source` or `budget explain`.

What is left to you, as in any new project: the power configuration (distribution loss, converter efficiency), the Eb/N0 and attenuation tables, an orbit, a scenario and links. They are placeholders, and the results that need them show *n/a*.

## How are margins handled?

An equipment in the model has a mass margin (its maturity level) and a power margin. Two ways, chosen with `--margins`:

| Option | Mass and power in the units | Margin classes | Use |
|---|---|---|---|
| `raw` (default) | as in the model, without margin | `idm_m10_p5`: the margins of the equipment | the project applies its margin policy, so you can change the margins in one place |
| `applied` | the model's margins already applied | `idm_applied`: no margin | the totals you see are those of the model; the project adds nothing |

The margins are never applied twice. The margins of an element (mass, power) and a subsystem's forced mass have no counterpart in the project; they are listed as not applied, and the project's totals can differ from the model's by them ([DV-IDM4](../DEVIATIONS.md)). The new project writes the system margins as 0 marked *estimate*, because the model has none.

## How do system modes become spacecraft modes?

`idm/mode_map.yaml` says what each system mode of the model becomes. It is drafted at the first import:

```yaml
schema_version: 1
kind: idm_mode_map
system_modes:
  ACQ:
    mode: acq
    name: Acquisition
```

`mode` is the file name in `modes/`; change it to rename the spacecraft mode, or write `null` to skip that system mode. Later imports only add entries for system modes that are new. A unit follows the element mode that the system mode names for its element; a custom power on a unit becomes a power mode `custom <mode>` of that unit. A unit with no mapping in a system mode is left unassigned, and the project check reports it (`UNIT_NOT_MAPPED`); nothing is guessed. The *duty cycle* of a system mode has no counterpart (a scenario gives the time shares) and is listed.

## What happens when I import the model again?

Import the new version of the model into the same project:

```bash
budget import idm satellite_v2.idm --project my_satellite
```

The import compares, for every value, what it wrote last time, what the model says now and what the file holds now (`idm/import_state.yaml` records what it wrote):

- the model changed the value and the file still holds what was imported: the value is **updated**;
- you changed the value and the model did not: your value **stays**;
- both changed: your value stays and `IDM_KEPT_USER_VALUE` tells you;
- a unit, mode, assignment or key that you added is **never touched**; comments in the files are kept;
- an object that the model no longer has is **flagged** (`IDM_REMOVED_IN_MODEL` once; `removed` in the state file) and its file is kept, never deleted;
- a file you deleted stays deleted; a file of yours with the name of an imported object is left alone;
- importing the same model twice changes nothing.

The sources record the revision of the model, so a new revision rewrites the sources of the values; only a value that really differs is reported as changed. The project folder is meant to be under version control: the change between two imports is an ordinary diff, and `budget compare` shows what it did to the results.

## What is not imported?

Not in this version: the centre of gravity and the inertia of the equipment (they need the placement of every equipment in the satellite; the mass properties stay empty and the budget lists them as missing, `MASS_PROPS_MISSING`); masses that the model computes from the area or volume of a shape; the system-mode duty cycles; element margins and mass targets; forced masses; additional properties; scenarios, trajectories and attitude files; solar array, battery, radios, antennas, ground stations and orbit (the model has none of them; they stay as they are in the project, or placeholders).

## What do the messages mean?

Every code has a page entry in [the problem list](../PROBLEMS.md#idm-cic-models-import). The usual ones: `IDM_MASS_UNRESOLVED` (the equipment's mass needs geometry or is not in the model, so the unit is not written), `IDM_POWER_UNRESOLVED` (a power mode or mapping could not be taken over), `IDM_TEMPERATURE_IGNORED` (a band was not given, or the survival band does not enclose the operating band), `IDM_NEVER_ENABLED` (an optional unit is off in every configuration).

The format that is read, and what it means, is described in [models/idm-import.md](../models/idm-import.md).

Next: [Create a project](create-a-project.md) · [Describe the spacecraft](describe-the-spacecraft.md) · [Command line](command-line.md).
