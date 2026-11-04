# Pointing and slew budget

How long a turn from one pointing attitude to another takes, how fast the spacecraft turns, how much angular momentum the actuators must store and how much electrical energy the slews use. Added in 2.2.0 (decision D-234).

## Pointing modes are not spacecraft modes

A [spacecraft mode](../glossary.md#spacecraft-mode) chooses the power mode of every unit. A **pointing mode** says what the spacecraft points at (`nadir`, `sun`, `inertial`, `target`, `other`), the accuracy required and the actuators that hold it. A project has both, and they are kept apart: the pointing file does not change a spacecraft mode. The pointing budget on this page reports the power to hold each pointing mode (`hold_power_w`) and of each slew (`slew_power_w`) by itself. To put them on the **power timeline**, place the pointing modes in a scenario (`pointing_default` and `pointing_rules`): the timeline then adds the holding power of the active mode and, where the mode changes, the slew between the two modes, as its own series ([the scenario](../user-manual/scenarios.md#pointing-and-manoeuvres-in-a-scenario), decision D-235). A scenario that places nothing leaves the power budget as it was.

## The slew

A slew is a rest-to-rest rotation of the angle θ about one body axis. With the actuators' maximum torque T as the only limit and the inertia I about the axis, the spacecraft accelerates at α = T / I for half the angle and decelerates for the other half (**bang-bang**):

```
t = 2 √(θ / α)         peak rate  ω = √(θ α)                (POINT-SLEW)
```

If the spacecraft may not turn faster than ω_max (a gyro, a star-tracker or a wheel speed limit), it holds that rate in between:

```
t = θ / ω_max + ω_max / α
```

The peak angular momentum the actuators must store is `h = I ω_peak` (POINT-MOMENTUM); the margin is the momentum capacity less `h`, and a negative margin is the finding `POINTING_MOMENTUM_EXCEEDED`. The electrical energy of a slew is the slew power times the slew time (POINT-ENERGY); the settling time is added to the time of the slew and not to its energy. A slew that is done several times a day (`per_day`) adds its time and energy up per day.

## The inertia

The inertia of a slew is the one you give (`inertia_kgm2`, with its source), or, if you leave it out, the diagonal entry of the mass budget's inertia about the centre of gravity for the slew's axis, in the mission phase named by `mass_phase` (the first phase by default). The report names which one it used. The mass budget's inertia counts only the items with a position (its coverage is shown in the mass report), so it is a lower bound of the true inertia and the slew it gives is faster than the real one: give the inertia from your own analysis when you have it.

## Inputs

| Input | Where | Notes |
|---|---|---|
| Actuators | `actuators.<id>`: `max_torque_nm`, `max_rate_deg_s`, `momentum_capacity_nms`, `slew_power_w` | torque is required, the rest optional |
| Pointing modes | `modes.<id>`: `reference`, `accuracy_deg`, `actuator`, `hold_power_w` | |
| Slews | `slews[]`: `from_mode`, `to_mode`, `angle_deg`, `axis`, `actuator`, `inertia_kgm2`, `settle_s`, `per_day` | |

Every number is a sourced value; a placeholder gives n/a, never zero.

## Simplifications

[DV-P2](../DEVIATIONS.md): a rigid body turning about a principal axis; the torque is constant and instantly reversed; no flexible modes, no coupling between axes, no gyroscopic torque, no actuator dynamics or saturation curve; one axis per slew (a slew about an arbitrary axis is not a combination of the three). The tool does not choose the actuators or size the wheels.

## Outputs

`budget run --budget pointing` (and `--budget all` when the file exists) writes `pointing.xlsx|pdf|docx|json` and `pointing_slews.csv`; the layout of the JSON is in [RESULT_FORMAT](../RESULT_FORMAT.md). In the window it is the **Pointing** page of the *Power* area, and the Reports page writes it. A pointing mode may also record how it is controlled (`control`: `three_axis`, `spin`, `bdot` or `sun_safe`); that changes no result, and its reference may be `bdot` or `spin` as well.
