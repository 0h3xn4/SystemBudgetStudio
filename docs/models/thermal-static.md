# Static thermal budget

**What it computes.** For every spacecraft mode: the heat each unit dissipates, summed by subsystem, by thermal node and for the spacecraft. For every thermal case (for example *hot* and *cold*): the steady-state temperature of each thermal node, from the heat dissipated in it, the heat its surfaces absorb from the Sun, the Earth's albedo and the Earth's infrared, the heat it radiates to space and the heat it conducts to the other nodes; and a check of every unit's temperature against its limits. It has no orbit and no time: a case is one orbital condition, with constant view ratios.

## Equations

| Id | Name | Formula | Source |
|---|---|---|---|
| TH-DISS | Heat dissipated by a unit | `Q = P_eff × heat_dissipation_ratio` (peak: `P_peak × ratio`) | project convention (D-037); citation to be supplied (SOURCE_MISSING) |
| TH-ABS | Heat absorbed by a surface | `Q = A (α f_sun S + α f_earth a S + ε f_earth E_IR)` | same; constant view ratios per case, no view factors (DV-T2) |
| TH-SB | Radiation of a surface to space | `R = ε σ A` (W/K⁴), `σ = 5.670374419e-8 W m⁻² K⁻⁴` | CODATA 2018 / SI 2019 (exact from h, k, c) |
| TH-BAL | Steady-state node heat balance | `Σⱼ Gᵢⱼ (Tⱼ − Tᵢ) + Rᵢ (T_space⁴ − Tᵢ⁴) + Qᵢ = 0`, `Qᵢ` = dissipated + absorbed | same; isothermal nodes, linear conduction, radiation to space only (DV-T1) |
| TH-LIMIT | Unit temperature limit check | exceeded when `T < T_min` or `T > T_max`; *margin* when within the limits but closer than `temperature_margin_k` | operating or survival limits of the unit, chosen by the case (D-074) |

## Inputs and where they come from

| Symbol | File and field | Notes |
|---|---|---|
| `P_eff`, `P_peak` | from the static power budget (`budget explain … power:units:<mode>`) | the power mode the spacecraft mode assigns to the unit |
| `heat_dissipation_ratio` | `units/<unit>.yaml`, `modes[i].heat_dissipation_ratio` | per power mode; **never assumed**: a unit without it gives n/a |
| node of a unit | `units/<unit>.yaml`, `thermal_node` (the subsystem when it names none) | |
| `A`, `ε`, `α` | `config/thermal_model.yaml`, `surfaces[i].area_m2`, `.emissivity_ratio`, `.absorptivity_ratio` | `ε` and `α` are sourced |
| `f_sun`, `f_earth` | `config/thermal_model.yaml`, `surfaces[i].exposure.<case>.solar_view_ratio`, `.earth_view_ratio` | sourced, per case |
| `S`, `a`, `E_IR` | `config/thermal_environment.yaml`, `cases.<case>.solar_flux_wm2`, `.albedo_ratio`, `.earth_ir_wm2` | sourced |
| `T_space` | `config/thermal_environment.yaml`, `space_temperature_k` | sourced |
| `Gᵢⱼ` | `config/thermal_model.yaml`, `conductances[i].conductance_wk` | sourced; parallel conductances add |
| `T_min`, `T_max` | `units/<unit>.yaml`, `temperature_limits.operating_min_k` … or `survival_*` | the case chooses the set |
| required margin | `config/thermal_environment.yaml`, `temperature_margin_k` | sourced |

## Order of the computation

1. Each unit: the heat it dissipates (TH-DISS), then the sums by subsystem, by node and for the spacecraft mode.
2. Each case: the node inputs: heat dissipated in the node (the units on it, in the case's spacecraft mode), heat absorbed (TH-ABS summed over its surfaces) and the radiation coefficient (TH-SB summed over its surfaces).
3. The temperatures of **all nodes together** (TH-BAL): a damped Newton iteration (tolerance 1e-10 K) finds the temperatures at which every node's balance is zero. Every group of connected nodes needs a surface that radiates to space, otherwise there is no equilibrium and the case reports an error. The largest remaining node imbalance is printed under the temperature table.
4. The heat radiated and conducted by each node at those temperatures, and the check of each unit's temperature against its limits (TH-LIMIT).

## What *Explain* shows for a temperature

No formula gives one node's temperature from its own inputs: it depends on all the others. The explanation therefore shows every term of the node's heat balance, each computed again from the inputs with the solver's own functions (dissipated, absorbed per surface, radiation coefficient), takes the temperature from the solver, and then checks that the balance closes at it: heat in minus heat radiated minus heat conducted out is zero to rounding. The neighbours' temperatures are shown as the solver's results.

## Simplifications

See DEVIATIONS DV-T1 to DV-T3: isothermal nodes, constant view ratios per case, linear conduction, radiation to space only, no transient; dissipation uses average power times duty cycle, unmargined.

See any cell with [`budget explain`](explain.md) (table ids `thermal:summary`, per spacecraft mode `thermal:units:<mode>`, `thermal:subsystems:<mode>`, `thermal:nodes:<mode>`, per case `thermal:temperatures:<case>`, `thermal:limits:<case>`) or *Explain this value* in the window. The user-level page: [thermal budget](../user-manual/thermal-budget.md).
