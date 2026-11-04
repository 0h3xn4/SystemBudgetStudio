# Propulsion and delta-v budget

This page shows how to get the propellant a mission needs from its manoeuvres, how long the burns last and what an electric thruster draws. The model is on [its own page](../models/propulsion.md).

**Contents:** [Describe the system](#how-do-i-describe-the-propulsion) · [Get the budget](#how-do-i-get-the-budget) · [Read the result](#how-do-i-read-the-result)

## How do I describe the propulsion?

Write `config/propulsion.yaml` (in the window: *Budget configuration* in the project tree opens it in the editor). Cut down to the shape, the numbers are placeholders for yours, each with a source:

```yaml
schema_version: 1
kind: propulsion
systems:
  thruster:
    name: Monopropellant thrusters
    type: chemical                  # or electric
    isp_s: {value: 220, source: "data sheet ..."}
    thrust_n: {value: 4, source: "data sheet ..."}   # for the burn time
    propellant: propellant          # an expendable (expendables/propellant.yaml)
  ion:
    name: Ion thruster
    type: electric
    isp_s: {value: 1500, source: "..."}
    thrust_n: {value: 0.05, source: "..."}
    power_w: {value: 800, source: "..."}   # drawn while thrusting
maneuvers:                          # in mission order
  - {name: Orbit trim, system: thruster, delta_v_m_s: {value: 12, source: "..."}}
  - {name: Station-keeping, system: ion, delta_v_m_s: {value: 1.5, source: "..."}, count: 6}
dry_mass_kg: {value: 236, source: "..."}          # leave out to take it from the mass budget
delta_v_margin_ratio: {value: 0.10, source: "..."} # 0.10 is 10 %
```

The delta-v of a manoeuvre is yours to give; the tool does not compute orbit transfers. Where a value is not known yet, write `value: null` and `source: TBD`: the result shows n/a and the report carries the INCOMPLETE banner. An unknown system in a manoeuvre is `REF_UNKNOWN_PROPULSION_SYSTEM`, an unknown propellant expendable `REF_UNKNOWN_EXPENDABLE`.

## How do I get the budget?

```bash
budget run my_satellite --budget propulsion --out out
```

`--budget all` includes it when the file exists. In the window it is the **Propulsion** page of the *Mass* area, and the **Reports** page writes it. To put a burn on the power timeline, place it in a scenario ([how](scenarios.md#pointing-and-manoeuvres-in-a-scenario)). The [example project](../../examples/README.md) `microsat_250kg_eps` has a small file with invented values.

## How do I read the result?

- **Summary:** the dry mass, the initial mass (dry mass and propellant), the margin, the total delta-v and the total propellant.
- **By system:** the propellant, what the mass budget loads in the expendable, the margin between them (negative: not enough propellant), the burn time and, for an electric system, the power and the energy for the thrust-time.
- **Manoeuvres:** each burn with the mass before and after and the propellant it uses. The last burn is the lightest: it starts from the dry mass, and every earlier one carries the propellant of the later ones.

The assumptions table lists every number used with its source and status; the equations are PROP-ROCKET, PROP-BURN and PROP-ENERGY. The simplifications (impulsive burns, constant Isp and thrust, no residuals) are [DV-P1](../DEVIATIONS.md).

Next: [Mass budget](mass-budget.md) (the propellant expendable) · [Power budget](power-budget.md).
