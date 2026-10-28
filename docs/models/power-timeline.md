# Power timeline (time-domain power budget)

**What it computes.** For one scenario and two cases, beginning of life (BOL) and end of life (EOL): the power the solar array delivers, the demand at the source, the margin between them, the battery's stored energy, state of charge and depth of discharge, the energy balance of every complete orbit, and the findings (battery too deep, battery empty, negative orbit balance, peak power over the limit). It uses the orbit and the eclipses of the scenario and the mode timeline. The static budget of every mode (the demand) is [its own page](power-static.md).

## Equations

| Id | Name | Formula |
|---|---|---|
| TDP-TEMP | Cell efficiency at the operating temperature | `k_T = max(0, 1 + α (T_cell − T_ref))` |
| TDP-AGE | Array degradation over life | `k_age = (1 − annual_degradation_ratio) ^ years` |
| TDP-COS | Sun incidence on a face | `cos θ = n_face · s_body`, zero on the back side |
| TDP-LIT | Sunlit share of a step | `1 − eclipse time inside the step / step` (a soft shadow is a ramp) |
| TDP-ARRAY | Array output power per step | `P = E Σ_faces(N_cells max(0, cos θ)) A_cell η_ref k_T (1 − l_pack)(1 − l_harness) k_age f_lit` |
| TDP-DEMAND | Demand per step | the demand at the source of the mode the step lies in (static budget, PWR-SOURCE) |
| TDP-CAP | Battery capacity | `E_cap = C_cell V_cell N_series N_parallel (1 − annual_capacity_fade_ratio) ^ years` |
| TDP-SOC | Battery state of charge | surplus: `E += η_c min(P dt, (E_cap − E)/η_c)`; deficit: `E −= min(P dt, E η_d)/η_d` (`P` = generation − demand) |
| TDP-DOD | Depth of discharge | `DoD = 1 − E / E_cap`; a finding when above the allowed value of the mission phase |
| TDP-BALANCE | Orbit energy balance | `∫ (P_gen − P_dem) dt` over one revolution; negative is a finding |
| TDP-PEAK | Peak power at the source | the peak demand of a mode against the power limit |

The sources are **SOURCE_MISSING** (textbook relations and project conventions; the owner supplies the citation).

## Inputs and where they come from

Everything electrical is in `config/power_system.yaml` (`solar_array.*`, `battery.*`, `design_life_yr`, `attitude.*`, `limits.peak_power_w`), each a sourced number: a placeholder gives *n/a* in every result that needs it. The mode timeline, the orbit, the eclipses and the mission phase come from the scenario (`scenarios/<id>.yaml`), the demand of each mode from the static budget.

## The solver grid

The reported series are means over the scenario grid (`step_s`). The solver integrates on a finer grid: the scenario grid plus every eclipse edge, every mode-segment edge, every orbit-window edge and the instants at which the battery becomes full or empty, so a coarse step cannot average a discharge away (up to four refinement rounds; if the instants are still moving, `POWER_REFINEMENT_INCOMPLETE`). Every summary number (energy, extremes, balance, findings) comes from this finer grid.

An orbit window is one revolution of the angle in the orbit plane, counted from the start of the scenario; only complete revolutions have a balance.

## Simplifications

[DV-P4](../DEVIATIONS.md) (the battery is an energy store with constant efficiencies), DV-P5 (constant irradiance, no albedo, perfect pointing), DV-P6 (the Sun direction is sampled at the start of a step).

## Explain

`budget explain PROJECT timeline:cases --row "Lowest state of charge" --column EOL` shows how a number of the timeline tables was obtained ([how Explain works](explain.md)). Tables: `timeline:cases` (results by case: row = the quantity, column = BOL or EOL), `timeline:modes` (row = the mode), `timeline:balance:<case>` (row = the orbit number) and `timeline:violations` (rows are named by the case, the finding, and when it starts and ends). `--scenario`, `--load-basis` and `--phase` choose what is solved, as for `budget power-timeline`.

Because the battery state has no closed form, the explanation of a state of charge shows the step that ends at the instant asked about, with the stored energy before it and the efficiencies, and says that the stored energy before follows from integrating from the initial charge over all the steps before; a sum over the whole scenario (energy generated, demanded) is shown as the equation, the number of solver steps, the duration and the largest step, with the inputs of the array and the age factor. The energy demanded carries a cross-check against the mode table (demand × time of each mode). The solver's own series are available to anyone who needs every step: `budget power-timeline --series-every 1` writes them.

The explanation is the solver's own computation, kept on request (`time_domain_budget(..., keep_detail=True)`); in the window the scenario is solved again with it the first time a timeline value is explained (in a background thread, the same inputs give the same numbers) and kept until the timeline is worked out again. A test compares every cell of every timeline table with its explanation, for both demand bases, for a project that has every kind of finding and for a project with placeholders.
