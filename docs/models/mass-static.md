# Static mass budget

**What it computes.** For every mission phase: the mass of each unit and expendable with the margin of its maturity class; the totals by subsystem and for the spacecraft, with a system margin on top; the check against each mass limit; and the centre of gravity and inertia tensor of the items that have a position. It uses no orbit and no time. The mass of the spacecraft in each phase is the sum of what is aboard in that phase: a unit lists the phases it belongs to (all, when it lists none), an expendable has one mass per phase.

## Equations

| Id | Name | Formula | Source |
|---|---|---|---|
| MASS-MARGIN | Item mass with the maturity margin | `m_m = m × (1 + mass_margin_ratio(maturity))` | project convention (D-048 to D-050); citation to be supplied (SOURCE_MISSING) |
| MASS-SYSMARGIN | System margin on the margined total | `m_sys = (Σ m_m) × (1 + system_mass_margin_ratio)` | same |
| MASS-COG | Centre of gravity | `r_cg = Σ(m_i r_i) / Σ m_i`, nominal masses of the items with a position | classical mechanics (definition); no standards text cited |
| MASS-PARALLEL | Parallel-axis (Huygens–Steiner) theorem | `I = Σ(I_i + m_i(‖d_i‖² E − d_i d_iᵀ))`, `d_i = r_i − r_ref` | classical rigid-body mechanics; tensor-entry convention in D-048 |

The mass limit check has no registered equation: the margin is `limit − system-margined total`, and a margin within 1e-9 of the limit (relative) counts as zero because the sum of the masses carries rounding noise (a limit that is met exactly is not exceeded). The status is *ok* from a margin of zero up, *exceeded* below zero, *n/a* when the limit or the total is n/a.

## Inputs and where they come from

| Symbol | File and field | Notes |
|---|---|---|
| `m` (unit) | `units/<unit>.yaml`, `mass_kg` | a plain input, no source field |
| `m` (expendable) | `expendables/<id>.yaml`, `masses_kg.<phase>` | one mass per mission phase |
| `maturity` | `units/<unit>.yaml` or `expendables/<id>.yaml`, `maturity` | picks the margin |
| `mass_margin_ratio(maturity)` | `config/margin_policy.yaml`, `classes.<class>.mass_margin_ratio` | sourced; a placeholder gives n/a |
| `system_mass_margin_ratio` | `config/margin_policy.yaml`, `system_mass_margin_ratio` | sourced |
| `r_i` | `mass_properties.position_m` of the item, metres in the body frame | an item without a position is left out of the centre of gravity and the inertia (never counted at the origin) |
| `I_i` | `mass_properties.inertia` of the item (`ixx_kgm2` … `iyz_kgm2`) | an item without an own inertia is a point mass |
| mass limits | `config/mass_limits.yaml`, `limits[i].limit_kg`, optionally with a `phase` | sourced |

## Order of the computation

1. Each item: its mass in the phase, the margin of its class (a lookup), the margined mass (MASS-MARGIN).
2. The sums: nominal total, total with the unit margins, the subsystems (nominal and margined). A placeholder margin makes every margined sum that contains the item *n/a*.
3. The system margin on the margined total (MASS-SYSMARGIN), and the limit checks against that number.
4. The centre of gravity (MASS-COG) of the items that have a position and a mass; the coverage is the mass in the calculation divided by the nominal total.
5. The inertia tensor about the centre of gravity and about the origin of the body frame: each item's contribution by the parallel-axis theorem (MASS-PARALLEL), summed.

## Simplifications

- Margin mass has no position; the centre of gravity uses nominal masses only (DEVIATIONS DV-M1).
- An expendable's own inertia is one fixed tensor: it does not follow the mass in the phase, and the tool warns when an expendable has an inertia and more than one mass (DV-M4).
- Items without a position are left out of the centre of gravity and the inertia, and reported (the *CG coverage* column says how much of the mass is in).
- A placeholder anywhere in a chain makes every result that needs it *n/a*; it is never replaced by zero.

See any cell with [`budget explain`](explain.md) (table ids `mass:summary`, `mass:limits`, and per phase `mass:items:<phase>`, `mass:subsystems:<phase>`, `mass:totals:<phase>`, `mass:inertia:<phase>`) or *Explain this value* in the window. The user-level page: [mass budget](../user-manual/mass-budget.md).
