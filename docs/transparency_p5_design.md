# P5 design: selectable models

Status: **proposed, for review; nothing is implemented.** Decision record: D-219 in [DECISIONS.md](DECISIONS.md). Context: step P5 of the [transparency plan](transparency_audit.md#7-prioritized-implementation-plan); it builds on the file revision of [P3](transparency_p3_design.md) (built) and the catalogue and Assumptions page of [P4](transparency_p4_design.md) (built).

## 1. What it is for

Some results depend on a **modelling choice** that a reviewer may reasonably want to make differently: which shadow geometry decides an eclipse, which Earth constants the geometry uses, whether the array sees a constant or a seasonal irradiance. Today two of these exist as hidden or half-visible options (the `shadow_model` of a scenario; the `--load-basis` of a run) and the rest are fixed in code and described only in [DEVIATIONS.md](DEVIATIONS.md).

P5 gives a choice that is a real alternative **a name, a place in the project, a source, a test and a line in every report**, and keeps everything else fixed and visible (P4). It changes no result: an omitted choice is the default, which is what the code does today, byte for byte.

## 2. What counts as a selectable model

A choice is offered only when **all** of these hold. Otherwise it stays a documented simplification.

1. **A defensible alternative exists** with a citable source (not "the user's own formula": that is an override, P7).
2. **It can be checked** against an independent reference value in a test (a number from the source, or a limiting case that must agree with the default).
3. **It changes one thing**: a choice that needs new inputs is a new feature, not a switch.
4. **Its default is today's behaviour**, so no existing project changes.

This is the rule that keeps the list short. A model that fails it is recorded in the registry as *fixed*, with the reason, so the Assumptions page still shows it.

## 3. The candidates, and what I propose for 2.0.0

| Choice | Today | Alternative | Meets the rule? | Proposal |
|---|---|---|---|---|
| **Shadow geometry** | `cylindrical` default, `conical` available (scenario field `shadow_model`; ENV-SHADOW-CYL, ENV-SHADOW-CON) | already there | yes | **register** (no change of files or numbers) |
| **Earth constants** (radius, mu, flattening) of the elements path and of the geometry | WGS-84 (DV-E5); a TLE is on WGS-72 | WGS-72 for elements | yes: both are sets of the SGP4 library, the difference is a known size (radius 6378.135 vs 6378.137 km) | **new**, per scenario: `earth_model: wgs84 | wgs72`; a TLE stays on WGS-72 (SGP4 requires it) and says so |
| **Irradiance on the array** | constant `solar_irradiance_wm2` (DV-P5) | scaled by `(1 AU / R)^2` with the Earth-Sun distance the Sun model already computes; no new number | yes: the factor is exact geometry, the check is the perihelion and aphelion ratio | **new**, per scenario: `irradiance_model: constant | seasonal` |
| **Load basis** (nominal or margined) | run option, `nominal` default | already there | yes | **register**; the run option stays, the value in the run parameters is shown in the panel |
| **Rate selection** of a link (highest rate that closes) | fixed policy | e.g. fixed rate, or the rate at the required margin | needs a decision on what is defensible | **not in 2.0.0**: question 4 |
| **Margin application** of the mass budget (DV-M1) | margin mass has no position | giving it one | no: it needs new inputs | **fixed**, with the reason |
| **Thermal simplifications** (DV-T1, DV-T3) | lumped steady state, one sink | transient, view factors | no: a different model with new inputs, not a switch | **fixed**, with the reason |
| **Sun position** (DV-E1) | low-precision formulae, about 0.01 degree | a high-precision ephemeris | no: it needs data or a dependency that is not offline and licence-clean today | **fixed**, with the reason |
| **Orbit propagation** (DV-E2) | SGP4 on mean elements | a numerical propagator | no: new model, new inputs (drag, forces) | **fixed**, with the reason |

So 2.0.0 would have **four selectable choices** (two of them new) and a registry that lists the fixed ones with the reasons they are fixed. If you want more, they have to pass section 2 first.

## 4. The registry

A new module `budget_core/model_choices.py` holds `REGISTRY`, an ordered tuple of `ModelChoice`:

```
id            "environment.earth_model"
area          environment | power | link | run
title         "Earth constants"
scope         scenario | run | fixed
default       "wgs84"
choices       (Choice(id, title, equations, source, note), ...)
acts_on       what it changes, in plain words, with the DV id
```

- Each `Choice` names the equation ids it uses (`ENV-SHADOW-CON`), a **source**, and a one-line note. A fixed model has one choice and the reason it is fixed.
- The solvers read the value from the scenario and branch on it in **one place per model** (a function in the model's own module), never by a scattered `if`. A test checks that every `Choice.equations` id exists in the equation registry and that every branch of the code is reached by some choice.
- The registry replaces the hand-written `FIXED_CHOICES` of `assumptions_view.py`: the *Model choices* section of the Assumptions page, `budget assumptions` and the report table are built from it, so a choice cannot be in the code and missing from the page.

## 5. In the project file

The three scenario-scoped choices are optional fields of the scenario file, next to `shadow_model`:

```yaml
environment_source: elements
shadow_model: conical
earth_model: wgs84          # new; omitted = wgs84
irradiance_model: constant  # new; omitted = constant
```

- **No new file kind.** The scenario already holds the environment, so the choices that change the environment live there and join the environment cache key (`environment_key`), otherwise a stale environment would be reused.
- **Schema.** The scenario kind goes up one version with an identity migration (the P3 pattern); a project that sets a new field gets `requires: [model_choices]`, so an older tool refuses it (`FEATURE_UNSUPPORTED`) instead of failing on an unknown field.
- **Loader.** An unknown value is an error, `MODEL_CHOICE_UNKNOWN`, whose hint lists the valid ones (ids only, no project values). A choice the scenario cannot use (`earth_model` for a `spacemissionstudio` environment, whose geometry is imported) is a warning, `MODEL_CHOICE_IGNORED`, and the Assumptions page marks it *not used*.
- **Digest.** The fields are model inputs, so they are in the model digest like any other. A scenario that spells out the default has a different digest from one that omits it (the same rule as for settings in P4, and documented the same way).

## 6. Where it shows

- **Assumptions page and `budget assumptions`**: the *Model choices* section lists every registry entry with its active value, whether it is the default, the alternatives, the source and the file to edit; fixed models show their reason. A non-default value has the same marker everywhere.
- **Reports**: the provenance table gets the row **Model choices** (`defaults` or the changed ones, as `earth_model=wgs72`); a comparison shows both sides' row, so two revisions that differ in a model say so. The golden files change by that row only.
- **Explain**: the equation list of an explanation already follows the shadow model; it follows the other two the same way, and a step names the model it used.
- **Window**: the scenario editor gets a *Model choices* group of drop-downs (one per scenario-scoped choice, each with the source in its tooltip). A change is **one undo step** through `ModelDocument`, and an unsaved change makes the run chip *Out of date* as any edit does (D-211). Nothing is added to the default views: the group is in the scenario editor, and the Assumptions page is where all of them are listed.

## 7. What does not change

The default behaviour of every command, every number of a project that omits the fields, the report layouts apart from the one row, and the existing `--load-basis` option. Choosing a non-default model changes exactly what its model page says, and nothing else (a test per choice compares against the reference value of section 2).

## 8. Order of work (each its own pull request)

1. **P5a, the registry and the visibility.** `model_choices.py` with every row of the table (selectable and fixed), the Assumptions page, `budget assumptions` and the provenance row built from it, the reasons for the fixed models, `docs/models/choices.md` generated from the registry (a drift test, as for settings and problems). No file change, no number change.
2. **P5b, the Earth model.** The scenario field, loader codes, schema, `requires`, the geometry and elements path reading the chosen set (including the duplicate Earth radius of the link module, which must follow it), the environment key, the model page and the deviation entry DV-E5 updated, tests against the SGP4 constants.
3. **P5c, the seasonal irradiance.** The scenario field, the factor in the array generation, the equation and its source, the check against perihelion and aphelion, the Explain step, the model page and DV-P5.
4. **P5d, the window.** The *Model choices* group of the scenario editor, undo, tooltips, palette entry, tests.
5. **Release 2.0.0** (a separate step, as for every release): version, goldens, changelog, install checklist; you tag and publish.

Each step leaves the tool working, and the format revision ships once, with the last step that needs it.

## 9. Questions for the owner

1. **Where do the choices live?** In the scenario file (my proposal: the choice changes the environment, a scenario already names its shadow model, and two scenarios can compare two models) or in one project-wide file, which is simpler to read but makes a per-scenario comparison impossible?
2. **Which choices in 2.0.0?** My proposal is the four of section 3 (shadow geometry and load basis registered; Earth constants and seasonal irradiance new). Too many, too few, or the wrong two new ones?
3. **A TLE and `earth_model`.** SGP4 is defined on WGS-72 for a TLE, so the field would not apply to it. I propose to leave it fixed and say so on the page (`MODEL_CHOICE_IGNORED` when set on a scenario that uses a TLE). Agreed, or should a TLE on WGS-84 be allowed with a warning?
4. **Link rate selection.** The policy is "the highest listed rate that closes the margin". Is there an alternative you want as a model (a fixed rate; the continuous rate at the required margin, which is already computed and shown)? If not, it stays fixed.
5. **Seasonal irradiance needs a date.** The factor comes from the scenario start and the Sun model, so it needs no new number, but the result then depends on the date of the scenario. I propose to show the factor in the report. Is that enough, or do you want the aphelion and perihelion cases as named runs?
6. **Constants.** As decided in D7, only **named sets** are selectable; a free value for a constant waits for the override mechanism (P7). Still your decision?

## 10. Tests (outline)

- Every registry default equals the behaviour before the step (golden files byte-identical for a project that omits the fields).
- Each non-default choice is checked against its reference: WGS-72 radius and mu against the SGP4 library; the irradiance factor against the perihelion and aphelion distances (1.0167 and 0.9833 AU, ratio about 1.069); the conical shadow against the cylindrical limiting case at zero Sun radius.
- Every `Choice.equations` id exists; every branch of a model function is reached; the generated `choices.md` and the schemas do not drift.
- The loader: an unknown value, a choice that does not apply, and a project that uses the field in an older tool (`requires`).
- The Assumptions page and the report row are built for every example; a comparison of two scenarios that differ in a model shows it; the editor changes a choice in one undo step.
- **Working software after each step.** Each phase is a PR, and none changes a number until a user chooses a non-default model.
