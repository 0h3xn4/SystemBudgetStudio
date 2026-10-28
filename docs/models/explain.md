# Explain: how a number was obtained

**What it is for.** Any number in a budget table can be traced to its equation, its inputs with units and where each input comes from, and every intermediate result. You can say in a design review where a number comes from without saying "the tool computed it".

## Using it

```bash
budget explain my_satellite                                   # the tables that can be explained
budget explain my_satellite power:units:nominal               # its columns and rows
budget explain my_satellite power:units:nominal --row eps --column "With margin (W)"
budget explain my_satellite power:units:nominal --row eps --column "With margin (W)" --format json
```

A cell is named by the **table id**, the **value of the row's first column** (repeat `--row` when a table has several key columns) and the **column header exactly as the table shows it**. The ids are printed by the first command: `power:summary`, and for every spacecraft mode `power:units:<mode>`, `power:subsystems:<mode>`, `power:buses:<mode>` and `power:totals:<mode>`; for the mass budget `mass:summary`, `mass:limits` (two key columns: the phase and the limit name, so give `--row` twice) and, for every mission phase, `mass:items:<phase>`, `mass:subsystems:<phase>`, `mass:totals:<phase>` and `mass:inertia:<phase>`; for the thermal budget `thermal:summary`, per spacecraft mode `thermal:units:<mode>`, `thermal:subsystems:<mode>` and `thermal:nodes:<mode>`, and per thermal case `thermal:temperatures:<case>` and `thermal:limits:<case>`.

What you get, for example for the power with margin of the unit `eps` in mode *Nominal*:

```
Units in mode Nominal / eps / With margin (W)
= 12.6 W

Step 1: Effective power of the unit  [PWR-EFF]
  average power of eps = 12 W  (units/eps.yaml modes[1].avg_power_w)
  duty cycle of eps = 1 ratio  (units/eps.yaml modes[1].duty_cycle_ratio)
  -> effective power of eps = 12 W

Step 2: Margin of the unit's maturity class
  margin of maturity class class_a = 0.05 ratio  (config/margin_policy.yaml classes.class_a.power_margin_ratio)  source: "..."
  -> margin of eps = 0.05 ratio

Step 3: Power with the maturity margin  [PWR-MARGIN]
  effective power of eps = 12 W  (result of step 1)
  margin of eps = 0.05 ratio  (result of step 2)
  -> power of eps with margin = 12.6 W
```

- **Equation.** The id in brackets is an entry of the equation registry (the same table that ends every report and the guide chapter *Equations and sources*), with its formula and its source. Most sources are still **SOURCE_MISSING** (the formula is a textbook relation or a project convention; the owner supplies the citation). The explanation says so; it never invents a source.
- **Inputs.** Each input shows its value, its unit, the file and the path in the file it was read from, and, for a number that has one, the source text. A plain input (a unit's power, a mass) has no source field yet, so none is shown.
- **n/a.** When an input is a placeholder (`source: TBD`) the result is *n/a* and the step that needed it shows which input was missing, with the source `TBD`.
- **The number is the table's number.** The explanation is computed again with the same functions the solver uses, and a test compares every cell of every explainable table with its explanation.

The value is shown with up to ten significant digits, not rounded to the display precision of the report.

## What is covered

| Budget | Tables | State |
|---|---|---|
| Static power | summary, units, subsystems, buses, totals (every spacecraft mode) | **available** (command line and window) |
| Static mass | summary, limits, and per mission phase items, subsystems, totals and centre of gravity, inertia | **available** (command line and window) |
| Static thermal | summary, units, subsystems, nodes (dissipation), node temperatures and unit limits per case | **available** (command line and window); a temperature is shown as the terms of its heat balance around the solver's result |
| Link, power timeline, orbit and eclipse | | planned, in this order |

The equation registry also records which code applies each equation; the equations that no code claims yet are listed in `tests/unit/test_equation_binding.py` and the list only gets shorter.

## In the window

On a Power, Mass or Thermal sheet, select a value and choose **View → Explain this value** (Ctrl+Shift+I, also in Ctrl+K), or right-click the value. The **Explain** panel opens on the right, in the same group as the Inspector and Provenance panels, and shows the title of the value, the value, and the same text `budget explain` prints. The panel is hidden until you ask for it, also in the focused view; closing it is final until the next request. When nothing is selected, or the value is not one that can be explained, the panel says so. The explanation is cleared when the project is loaded again, since the numbers may have changed. The tables of the link budget and the timelines do not offer it yet.

Decision: [D-206](../DECISIONS.md). The model behind the first tables: [static power](power-static.md).
