# Propulsion and delta-v budget

How much propellant the manoeuvres of a mission need, from the specific impulse of the thrusters and the dry mass; how long the burns last; what an electric system draws. Added in 2.2.0 (decision D-233).

## The model

The manoeuvres of `config/propulsion.yaml` are listed in mission order. The mass after the last one is the **dry mass**; going backwards, the rocket equation gives the mass before each burn:

```
m_before = m_after × exp(Δv / (Isp × g0))          (PROP-ROCKET)
propellant of the burn = m_before − m_after
```

The first manoeuvre therefore starts from the **initial mass** (dry mass plus all the propellant). `g0` is the standard gravity, 9.80665 m/s², a definition that turns a specific impulse in seconds into an exhaust velocity.

Per system:

- **Propellant** is the sum over its burns.
- **Burn time** at a constant thrust: `t = m_propellant × Isp × g0 / F` (PROP-BURN); the mass flow is `F / (Isp g0)`, so this is exact for a constant thrust.
- An **electric** system also gives the **power** it draws while thrusting (your input, `power_w`) and the **energy** `E = P × t / 3600` in Wh (PROP-ENERGY). The tool does not derive the power from the thrust and the specific impulse: it depends on the efficiency, which is not a number to guess.
- If the system names the expendable that holds its propellant (`propellant: <expendable id>`), the report compares the propellant needed with the **largest mass** that expendable has in the mass budget, and gives the margin (negative: not enough propellant loaded).

A **margin on delta-v** (`delta_v_margin_ratio`, 0.1 for 10 %) multiplies every manoeuvre's delta-v. It has no default: without it no margin is applied and the report says so.

A **manoeuvre** may repeat (`count`, for example six identical station-keeping burns); the delta-v of the line is `count × Δv × (1 + margin)`.

## Dry mass

Either given (`dry_mass_kg`, with its source) or taken from the mass budget: the nominal total of the first mission phase less the mass the propulsion systems' propellant expendables have in that phase. The report names which one it used. If the mass budget has no total (a placeholder somewhere), the dry mass is n/a and so is everything that needs it.

## Inputs

| Input | File and key | Notes |
|---|---|---|
| Specific impulse | `config/propulsion.yaml`, `systems.<id>.isp_s` | seconds; chemical or electric (`type`) |
| Thrust | `systems.<id>.thrust_n` | optional; needed for the burn time |
| Thrusting power | `systems.<id>.power_w` | electric systems only |
| Propellant expendable | `systems.<id>.propellant` | optional; an id in `expendables/` |
| Manoeuvres | `maneuvers[]`: `name`, `system`, `delta_v_m_s`, `count` | in mission order |
| Dry mass | `dry_mass_kg` | optional; else from the mass budget |
| Delta-v margin | `delta_v_margin_ratio` | optional; a ratio |

Every number is a sourced value (`{value, source}`); a placeholder (`source: TBD`) gives n/a, never zero, and the report carries the INCOMPLETE banner. A burn after an unknown one stays computable; a burn before it does not (its starting mass is unknown).

## Simplifications

See [DEVIATIONS](../DEVIATIONS.md) DV-P1: impulsive burns (no gravity, steering or pointing loss, no finite-burn loss); constant specific impulse and thrust (no throttling or blow-down curve); no residual or unusable propellant (add it to the dry mass); no propellant for attitude control unless you list it as a manoeuvre.

## What it is not

The tool does not compute the delta-v of a transfer, a plane change or a deorbit: you give the delta-v of each manoeuvre (from your analysis or a source). Nor does it size tanks or pick a thruster.

## Outputs

`budget run --budget propulsion` (and `--budget all` when the file exists) writes `propulsion.xlsx|pdf|docx|json` and `propulsion_maneuvers.csv`; the JSON layout is in [RESULT_FORMAT](../RESULT_FORMAT.md). The window computes it with the other budgets when the project is opened and includes it when you write the reports from the *Reports* page; the file is edited in the project tree under *Budget configuration*.
