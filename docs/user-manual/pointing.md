# Pointing and slew budget

This page shows how to get the time, rate, angular momentum and energy of the slews between pointing modes. The model is on [its own page](../models/pointing.md).

**Contents:** [Describe the pointing](#how-do-i-describe-the-pointing) · [Get the budget](#how-do-i-get-the-budget) · [Read the result](#how-do-i-read-the-result)

## How do I describe the pointing?

Write `config/pointing.yaml` (in the window: *Budget configuration* in the project tree opens it in the editor). Cut down to the shape, the numbers are placeholders for yours, each with a source:

```yaml
schema_version: 1
kind: pointing
actuators:
  wheels:
    name: Reaction wheels
    max_torque_nm: {value: 0.05, source: "data sheet ..."}
    max_rate_deg_s: {value: 1.5, source: "..."}          # optional rate limit
    momentum_capacity_nms: {value: 12, source: "..."}    # optional
    slew_power_w: {value: 45, source: "..."}             # optional
modes:
  nadir: {name: Nadir pointing, reference: nadir, actuator: wheels,
          accuracy_deg: {value: 0.5, source: "..."}, hold_power_w: {value: 15, source: "..."}}
  target: {name: Target tracking, reference: target, actuator: wheels}
slews:
  - name: Nadir to target
    from_mode: nadir
    to_mode: target
    angle_deg: {value: 60, source: "..."}
    axis: y
    actuator: wheels
    inertia_kgm2: {value: 95, source: "..."}   # leave out to take it from the mass budget
    settle_s: {value: 20, source: "..."}
    per_day: 6
```

A mode or a slew that names an actuator or a pointing mode that is not defined is `REF_UNKNOWN_ACTUATOR` or `REF_UNKNOWN_POINTING_MODE`.

## How do I get the budget?

```bash
budget run my_satellite --budget pointing --out out
```

`--budget all` includes it when the file exists. In the window the budget is computed with the others and written from the **Reports** page. The example `microsat_250kg_eps` has a small file with invented values.

## How do I read the result?

- **Pointing modes:** the reference, the accuracy requirement, the actuators and the holding power.
- **Slews:** the time of each slew and with settling, the peak rate (and whether the rate limit was reached), the inertia, the peak momentum against the capacity, the energy of one slew and per day.
- The summary gives the slew time and energy per day.

The holding and slewing power are *reported*, not added to the power budget: a pointing mode is not a spacecraft mode. Give the power to the units that draw it in their power modes.

Next: [Propulsion](propulsion.md) · [Mass budget](mass-budget.md) (the inertia).
