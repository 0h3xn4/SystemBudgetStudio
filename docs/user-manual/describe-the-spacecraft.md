# Describe the spacecraft

This page shows how to put the spacecraft into the project: its buses and phases, its units with their power modes, and the spacecraft modes that say what every unit is doing.

**Contents:** [Buses, phases, body frame](#how-do-i-set-the-buses-mission-phases-and-body-frame) · [A unit](#how-do-i-add-a-unit) · [Units in numbers](#how-do-i-write-units) · [A spacecraft mode](#how-do-i-add-a-spacecraft-mode) · [The table editor](#how-do-i-edit-power-modes-in-a-table)

## How do I set the buses, mission phases and body frame?

These live in `spacecraft.yaml`:

```yaml
schema_version: 1
kind: spacecraft
name: Minisat 250
buses:
  - name: main
    nominal_voltage_v: 28.0
  - name: payload
    nominal_voltage_v: 12.0
mission_phases:
  - launch
  - bol
  - eol
body_frame: 'Right-handed body frame. Origin: centre of the launch-vehicle interface plane. +Z: along the launch axis, away from the interface. X and Y: in the interface plane. Positions are item centres of mass in metres.'
```

- A [**bus**](../glossary.md#bus) is a power supply line; each unit names the bus it draws from.
- [**Mission phases**](../glossary.md#mission-phase) are names you choose (for example `launch`, `bol`, `eol`). None are assumed. They select the mass in [the mass budget](mass-budget.md) and the allowed depth of discharge in [the power budget](power-budget.md).
- The **body frame** is described in words, once: positions in the project mean the same axes and origin everywhere.

## How do I add a unit?

A *unit* is one piece of equipment (the on-board computer, a radio, a camera).

**In the window:** press **Ctrl+Shift+N** (**Edit → Add unit**, or *Add unit* in Ctrl+K), or open **Model → Units** and press **Add unit** (or right-click a row → *Add a unit…*). A form asks for the name, the id (suggested from the name; it becomes the file name `units/<id>.yaml`), the subsystem, the bus, the maturity class, the **mass** and the **first power mode** (its name and its average and peak power). None of the numbers has a default: the form does not accept an empty one, so a unit never gets a made-up mass or power. Then:

- the unit is in the grid at once, and **Save** (Ctrl+S) writes its file; **Undo** takes it back before that;
- **it is put in every spacecraft mode** with the power mode you just gave, because every spacecraft mode has to say what every unit does (without that the project would have errors). Change the assignment where it is wrong: `modes/<name>.yaml` (open it from the project tree), for example set a camera to `off` in the safe mode;
- with a thermal model in the project, the **subsystem must be the name of one of its nodes** (the form suggests them; a unit's thermal node is its subsystem unless it says otherwise), or add the node to `config/thermal_model.yaml` first;
- more power modes, limits and the rest are edited in the grids afterwards (**Power modes → Add mode**).

**Remove unit** (**Ctrl+Shift+Delete**, **Edit → Remove unit**, or the button) takes the selected unit out of the grid and out of every spacecraft mode in one undo step; **Save** then asks before it deletes the file. A unit that is the only one of a spacecraft mode is not removed (a mode needs at least one unit).

**By file:** create `units/<id>.yaml`; the file name (without `.yaml`) is the unit's id, used everywhere else:

```yaml
schema_version: 2
kind: unit
name: UHF/VHF radio
subsystem: TTC
mass_kg: 0.09
bus: main
maturity: class_b
modes:
  - name: off
    avg_power_w: 0.0
    peak_power_w: 0.0
  - name: downlink
    avg_power_w: 1.8
    peak_power_w: 4.0
    duty_cycle_ratio: 0.5
    heat_dissipation_ratio: 0.7
```

| Field | Meaning |
|---|---|
| `subsystem` | A label you choose; the budgets roll up by it. |
| `mass_kg` | Mass of the unit. |
| `bus` | A bus from `spacecraft.yaml`. |
| `maturity` | A [**maturity class**](../glossary.md#maturity-class) from the margin policy (`class_a`, …). It selects the margin added to this unit's power and mass. |
| `modes` | The unit's [**power modes**](../glossary.md#power-mode). Each has an average power, a peak power (not below the average), an optional [duty cycle](../glossary.md#duty-cycle) (0 to 1, default 1) and, for the thermal budget, the share of the power that becomes heat. |

Effective average power is `avg_power_w × duty_cycle_ratio`. Optional extras: `mass_properties` (position and inertia, for the [mass budget](mass-budget.md)), `temperature_limits` and `thermal_node` (for the [thermal budget](thermal-budget.md)). Everything is listed in the [file format](../FILE_FORMAT.md).

## How do I write units?

The unit is part of the field name: `avg_power_w` is in watts, `freq_hz` in hertz, `gain_dbi` in dBi. You can write the value with a unit and the tool converts it:

```yaml
mass_kg: 200 g          # saved as 0.2
frequency_hz: 2.2 GHz
```

The tool never converts a logarithmic unit to a linear one for you: `3 dBW` in a field that is in watts is an error (`UNIT_INVALID`), because that is the classic spreadsheet mistake this tool exists to prevent.

Capitals matter in units, as everywhere (`mW` is not `MW`): write logarithmic units as `dB`, `dBi`, `dBW`, `dBm` and `dB/K`. Squares can be written `m2` or `m^2`, so the label shown for a field (`W/m2`, `kg m2`) can be typed back. A temperature in `degC` is converted (`-40 degC` is 233.15 K); a *difference* such as `temperature_margin_k` takes `K` or `delta_degC`, never `degC`. A yes/no value (`true`) or a number in quotes is not a number in a field without a unit.

## How do I add a spacecraft mode?

A [**spacecraft mode**](../glossary.md#spacecraft-mode) (safe, nominal, imaging, downlink, charging) says which power mode each unit is in.

**In the window:** press **Ctrl+Shift+M** (**Edit → Add spacecraft mode**, or *Add spacecraft mode* in Ctrl+K), or open **Model → Spacecraft modes** and press **Add mode**. The project needs at least one unit first. A form asks for the name, the id (suggested from the name; it becomes the file name `modes/<id>.yaml`), an optional description and **where the assignments start from**: *every unit off* (a unit with no power mode called `off` starts in its first one, and the message says how many did) or *a copy of* another mode. Then set the power mode of each unit in the grid, one row per unit: choose one of that unit's power modes from the drop-down of the cell, or paste a column from a spreadsheet; a pasted name the unit does not have is refused with the list of the ones it has. **Save** (Ctrl+S) writes the file; adding is one undo step.

**Remove spacecraft mode** (**Ctrl+Shift+Backspace**, **Edit → Remove spacecraft mode**, or the button) removes the mode of the row with the cursor. It is refused while a scenario names the mode (as its default mode, in a rule or in a segment): change the scenario first. Save asks before it deletes the file.

**By file:** create `modes/<id>.yaml`:

```yaml
schema_version: 1
kind: spacecraft_mode
name: Downlink
description: Radio transmitting.
assignments:
  adcs: downlink
  camera: off
  obc: downlink
  radio: downlink
```

Keys are unit ids, values are power-mode names of that unit. Every unit must appear in every spacecraft mode, otherwise you get `UNIT_NOT_MAPPED` naming the unit (adding a unit in the window puts it in every mode for you). A scenario then says [which spacecraft mode is active when](scenarios.md).

## How do I get supplier data in from a spreadsheet?

Export the power modes as a table, let the supplier fill it in, and import it with a preview: [Unit power data in a spreadsheet](unit-tables.md).

## How do I edit power modes in a table?

In the window, select a unit in the project tree and press Enter (or choose **File → Edit unit power modes**, Ctrl+M): the **Power modes** grid of the **Model** tab shows its rows. Every unit is in the grid, so you can compare the radio with the OBC without switching tabs; typing a value with a unit works, you can paste a range from a spreadsheet, and **Ctrl+Z** undoes. **Ctrl+S** saves. [How to edit in the grids](use-the-window.md#how-do-i-edit-in-the-grids).

Next: [Placeholders and sources](placeholders-and-sources.md), then the [power budget](power-budget.md).
