# Examples

This folder holds five complete example projects with **invented data**: none of the numbers describes a real spacecraft, and none comes from a standard or a data sheet. Every number in them is marked `illustrative` (a `provenance:` entry `*` in each file, `status: illustrative` on the sourced numbers), so a report made from an example says in its provenance table how many invented inputs it used; placeholders (`source: TBD`) stay placeholders. Use them to learn the tool and as templates for your own project: when you replace a number with a real one, record its source ([how](../docs/user-manual/placeholders-and-sources.md#how-do-i-record-where-a-plain-input-came-from)).

**Contents:** [Getting a copy](#getting-a-copy) · [Which example for what](#which-example-for-what) · [microsat_250kg](#microsat_250kg-placeholders-everywhere) · [microsat_250kg_eps](#microsat_250kg_eps-complete-power-and-thermal-inputs) · [microsat_250kg_clean](#microsat_250kg_clean-no-warnings-and-no-errors) · [microsat_150kg](#microsat_150kg-two-links-and-phases) · [stress_200_units](#stress_200_units-a-week-at-one-second) · [Exit codes](#exit-codes-in-the-examples)

## Getting a copy

You can run the examples straight from this folder (`budget run examples/microsat_250kg_eps …`), but the tool writes its reports into `<project>/results` by default, so give `--out` or work on a copy:

```bash
budget export-examples demo      # writes demo/microsat_150kg, demo/microsat_250kg, demo/microsat_250kg_eps, demo/microsat_250kg_clean, demo/stress_200_units
```

The copy is identical to this folder. (A test fails if the two ever differ, so the examples cannot go out of date silently.) All commands below assume the copy in `demo/` and an output folder `out`; run them from the folder that contains `demo/`. Install first: [getting started](../docs/getting-started.md).

## Which example for what

| Example | Shows | Complete inputs for | Takes |
|---|---|---|---|
| [`microsat_250kg`](microsat_250kg) | A 250 kg satellite with 18 units, two links and two ground stations; what a project with **placeholders** looks like: results that cannot be computed say *n/a* and the report is marked [INCOMPLETE](../docs/glossary.md#incomplete) | static power, mass; scenario | seconds |
| [`microsat_250kg_eps`](microsat_250kg_eps) | The same satellite with a complete (invented) solar array, battery and thermal model: the time-domain power budget, thermal budget and **findings** | power timeline, thermal, link passes | seconds |
| [`microsat_250kg_clean`](microsat_250kg_clean) | The same satellite with **every input filled in** (invented values) and every limit met: validating and running it report **no warning and no error**. What a finished project looks like | everything | seconds |
| [`microsat_150kg`](microsat_150kg) | A 150 kg satellite with 17 units, propellant ([mass phases](../docs/glossary.md#mission-phase)) and **two links** (S-band and X-band downlinks), two ground stations and an imaging target | link budget, link passes, mass | seconds |
| [`stress_200_units`](stress_200_units) | 200 units and a **one-week scenario at 1 s** (604,801 steps): a performance and scale check | scenario, static budgets | about 10 s per run |

`microsat_250kg` and `microsat_250kg_eps` also carry a small `config/propulsion.yaml` (a monopropellant system and three manoeuvres) and `config/pointing.yaml` (two pointing modes and a slew) with invented values, so that `budget run --budget propulsion` and `--budget pointing` have something to show (in the first they are placeholders: n/a). They place nothing in the scenario; see [pointing and manoeuvres in a scenario](../docs/user-manual/scenarios.md#pointing-and-manoeuvres-in-a-scenario) to try it on a copy.

Every example except `microsat_250kg_clean` leaves some numbers as [placeholders](../docs/glossary.md#placeholder) on purpose (the margin policy, the [Eb/N0](../docs/glossary.md#ebn0) table, mass limits and so on): the tool will not invent standards values, so each result that needs one shows *n/a* until you supply it with a source. Reports say so in an INCOMPLETE banner.

## microsat_250kg: placeholders everywhere

What to look at: how the tool behaves when inputs are missing.

```bash
budget validate demo/microsat_250kg
budget run demo/microsat_250kg --budget mass --out out
budget scenario demo/microsat_250kg --out out
```

Expected: `validate` ends with `0 errors, 128 warnings` (all of them placeholders: the margin policy, the Eb/N0 table, mass limits, thermal, power and link numbers); `run` writes `out/mass_static.xlsx` and friends and prints

```text
INCOMPLETE: some inputs are placeholders (source TBD or missing). Entries marked n/a depend on them and are not computed. Do not use this report as evidence until the placeholders are replaced with sourced values.
```

`scenario` prints `Scenario one_day (elements): 15 eclipse(s); passes: gs_north 11, gs_south 4, tgt_plains 1; 62 timeline segment(s).` and writes the eclipses, passes and mode timeline of one day as CSV and JSON. `budget power-timeline demo/microsat_250kg` prints `BOL: n/a (inputs missing, see the problems below).` because this project has no complete array and battery: use `microsat_250kg_eps` for that.

Try: open `demo/microsat_250kg/config/margin_policy.yaml`, replace one `TBD` with a number and a source, and run again; the *n/a* cells that depended on it fill in.

## microsat_250kg_eps: complete power and thermal inputs

What to look at: the time-domain power budget, the thermal budget, and how a **finding** looks. This is the example used in [getting started](../docs/getting-started.md#5-a-first-worked-example-find-and-fix-a-power-violation).

```bash
budget power-timeline demo/microsat_250kg_eps --out out
budget run demo/microsat_250kg_eps --budget thermal --out out
```

Expected from the first command (exit code 1, by design):

```text
BOL: generated 2399.2 Wh, lowest state of charge 82.7 %, 16 violation(s).
EOL: generated 2060.3 Wh, lowest state of charge 79.7 %, 16 violation(s).
config/power_system.yaml: error PEAK_POWER_EXCEEDED: The peak power demand at the source exceeds the power limit. 16 interval(s), the first at T+00:02:06. (at limits.peak_power_w)
```

Expected from the second (also exit code 1, by design):

```text
units/radio.yaml: error THERMAL_MARGIN_INSUFFICIENT: Unit 'radio' is within its operating limits in a thermal case but closer than the required temperature margin. (at temperature_limits (case hot))
```

The radio is inside its temperature limits but closer to one than the required margin. Raise `limits.peak_power_w` in `config/power_system.yaml` (or lower the radio's power) and the first finding goes; change the radio's `temperature_limits` or `temperature_margin_k` and the second goes. In the window, open the **Power timeline** and **Thermal budget** tabs.

## microsat_250kg_clean: no warnings and no errors

What to look at: what a project looks like when there is nothing left to fix. Every input has an invented value (marked `illustrative`, like the other examples) and every limit is met: the peak power stays under the source limit, the launch mass with margins stays under its limit, every unit is inside its temperature limits with the required margin. Use it as a reference for "all green", or to try a change of your own and see which finding it causes.

```bash
budget validate demo/microsat_250kg_clean
budget run demo/microsat_250kg_clean --budget all --out out
budget power-timeline demo/microsat_250kg_clean --out out
budget link-passes demo/microsat_250kg_clean --out out
```

Expected: `validate` prints `No problems found.`; `run`, `power-timeline` and `link-passes` end with `0 errors, 0 warnings.` and exit code 0 (also with `--strict`), and `power-timeline` prints `0 violation(s)` for BOL and EOL. The mass result carries one information note, not a warning: the propellant is a point mass, because per-phase inertia of an expendable is not modelled.

Try: in `config/power_system.yaml` lower `limits.peak_power_w` to 150 and run `power-timeline` again; a `PEAK_POWER_EXCEEDED` error appears, as in `microsat_250kg_eps`. The numbers differ from `microsat_250kg_eps` in four places only: the margin policy and mass limit are filled in, the radio's upper temperature limit is the same as the other units', and the source's peak power limit is 400 W instead of 180 W.

## microsat_150kg: two links and phases

What to look at: link budgets, and a mass budget with three mission phases (launch, beginning of life, end of life) in which the propellant mass falls from 9.0 kg to 0.8 kg.

```bash
budget run demo/microsat_150kg --budget link --out out
budget link-passes demo/microsat_150kg --out out
budget run demo/microsat_150kg --budget mass --out out
```

Expected from `link-passes` (a Link passes report per scenario, XLSX/PDF/DOCX/JSON and CSV):

```text
sband_down: 11 pass(es) over gs_north, 4438.17 MByte in the scenario (4438.17 MByte per day).
xband_down: 4 pass(es) over gs_south, 2714.57 MByte in the scenario (2714.57 MByte per day).
0 errors, 95 warnings.
```

For each pass the report gives the lowest margin, the time with a rate that closes and the data volume, from the highest listed data rate whose margin meets the required margin at each step. `budget run … --budget link` writes the static table: EIRP, path loss, G/T, C/N0, Eb/N0 and margin per listed data rate at chosen elevations. In the window use the **Link budget** and **Link passes** tabs.

`budget power-timeline demo/microsat_150kg` prints `n/a` for BOL and EOL: this example's power system is a template. Use it to see how the mass budget handles phases (open `expendables/propellant.yaml`: an expendable gives its mass for **every** phase, writing `0.0` where it is gone).

## stress_200_units: a week at one second

What to look at: scale. 200 units, three sites, a seven-day scenario at 1 s.

```bash
budget scenario demo/stress_200_units --out out
```

Expected: `Scenario stress_week (elements): 106 eclipse(s); passes: gs_north 71, gs_south 28, tgt_plains 10; 240 timeline segment(s).` after roughly seven seconds. The environment (orbit, eclipses and passes over 604,801 steps) is the expensive part. With complete power inputs a week at 1 s with 200 units, including the power budget, is computed in about ten seconds on an ordinary laptop. This project's power system is a template, so `power-timeline` reports `n/a`; the timing is checked by the performance tests, not by this example.

## Exit codes in the examples

A command that finds an **error-level** problem exits with **1**, so scripts and CI notice. `microsat_250kg_eps` is built to show two such findings, so two commands above exit 1 even though they wrote all their files. `--strict` makes warnings count as failures too. Exit **0** means no errors; **2** means a command was called wrongly. See the [command-line reference](../docs/user-manual/command-line.md#exit-codes).

Next: the [user manual](../docs/user-manual/README.md) to build your own project, or the [glossary](../docs/glossary.md) for the terms used here.
