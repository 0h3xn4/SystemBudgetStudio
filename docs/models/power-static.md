# Static power budget

**What it computes.** For every spacecraft mode: the power each unit draws, with the margin of its maturity class; the totals by subsystem and by supply bus; and the power the solar array and battery system must supply at the source after the converter and distribution losses. It uses no orbit and no time: it answers "how much power does the spacecraft need in this mode?". The time-dependent budget (array, battery, eclipses) is the [power timeline](../user-manual/power-budget.md).

## Equations

| Id | Name | Formula | Source |
|---|---|---|---|
| PWR-EFF | Effective unit power | `P_eff = P_avg × duty_cycle_ratio` | project convention (D-040); citation to be supplied (SOURCE_MISSING) |
| PWR-MARGIN | Unit power with the maturity margin | `P_m = P_eff × (1 + margin_ratio(maturity))` | same |
| PWR-SYSMARGIN | System margin on the sum of the margined loads | `P_sys = (Σ P_m) × (1 + system_margin_ratio)` | same |
| PWR-SOURCE | Power at the source through the converter and the distribution | `P_source = P_load / (η_converter(bus) × (1 − distribution_loss_ratio))` | same |
| PWR-PEAK | Peak power | `P_peak = Σ peak_power_w of the units` (every unit at its peak at once, conservative) | same |

The margin policy of ECSS-E-ST-20C is the usual reference; the text is not available to the tool, so the equations carry **SOURCE_MISSING** until you supply the citation.

## Inputs and where they come from

| Symbol | File and field | Notes |
|---|---|---|
| `P_avg`, `duty_cycle_ratio`, `peak_power_w` | `units/<unit>.yaml`, `modes[i].avg_power_w`, `.duty_cycle_ratio`, `.peak_power_w` | the power mode the spacecraft mode assigns to the unit; a plain input, no source field |
| `maturity` | `units/<unit>.yaml`, `maturity` | picks the margin |
| `margin_ratio(maturity)` | `config/margin_policy.yaml`, `classes.<class>.power_margin_ratio` | sourced; a placeholder gives n/a |
| `system_margin_ratio` | `config/margin_policy.yaml`, `system_power_margin_ratio` | sourced |
| `η_converter(bus)` | `config/power_config.yaml`, `converter_efficiency_ratio.<bus>` | sourced, one per supply bus |
| `distribution_loss_ratio` | `config/power_config.yaml`, `distribution_loss_ratio` | sourced |

## Order of the computation

1. Each unit: effective power (PWR-EFF), then with its class margin (PWR-MARGIN). The peak power gets the same margin.
2. Subsystems: the sums of the unit values (peak by PWR-PEAK).
3. Each supply bus: the sum of its units' effective power (the *load*); the sum of the margined values; the system margin on the margined sum (PWR-SYSMARGIN); the source power of the load and of the system-margined load (PWR-SOURCE). The same chain for the peak.
4. The spacecraft: the sum over the buses.

## Simplifications

- All units at their peak at the same time (conservative).
- The margin is multiplicative and applied once per unit and once for the system; it is not applied per phase or per mode.
- The converter efficiency is one number per bus, independent of load.
- A placeholder anywhere in a chain makes every result that needs it *n/a*; it is never replaced by zero.

See any cell with [`budget explain`](explain.md). The decision behind the conventions: [D-040](../DECISIONS.md). The configuration numbers the budget used are the first table after the results in every report.
