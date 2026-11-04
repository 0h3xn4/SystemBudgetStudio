# Design: the thermal model against the beta angle

Status: **proposed, for the owner's review; nothing is implemented.** Decision record: D-250 in [DECISIONS.md](DECISIONS.md). It answers the item that every release since 2.3.0 lists as *"no multi-node thermal model against the beta angle"*.

## 1. What is missing, exactly

The tool already has a **multi-node, steady-state** thermal model ([thermal-static.md](models/thermal-static.md)): nodes, conductances, surfaces, and *cases* (hot, cold, ...) with a solar flux, an albedo and an Earth infrared flux. What a case does **not** know is the orbit. Each surface carries one fixed `solar_view_ratio` and one `earth_view_ratio` per case, typed by the user. So:

- the hot case is "the Sun at its worst angle", whichever angle that is, and the user has to know it;
- nothing connects the result to the **beta angle** (the angle between the orbit plane and the direction of the Sun), although the tool computes the beta angle over a scenario ([D-227](DECISIONS.md)) and the beta angle is what decides how a spacecraft sees the Sun: the sunlit part of the orbit, which faces are lit, and for how long.

*A thermal result against the beta angle* means: for a range of beta angles (and in particular the extremes of a mission), the orbit-average heat each surface absorbs, and from it the node temperatures with the model that already exists.

## 2. What can be done without guessing

Only the **Sun** side is pure geometry and can be checked against an independent calculation. Proposed scope, in order:

1. **Sunlit fraction of the orbit and the solar exposure of a flat face, as functions of the beta angle**, for a circular orbit at the altitude of the scenario's orbit and a spacecraft pointing to nadir (the local-vertical frame: x along the velocity, y opposite to the orbit normal, z to nadir). The position of the Sun in that frame at orbit angle `u` is `s = (-cos b sin u, -sin b, -cos b cos u)`; a face with outward normal `n` is lit by `max(0, n . s)` while the spacecraft is outside the shadow, which is a cylinder of the Earth's radius (the shadow model the tool already has, ENV-SHADOW-CYL): in shadow when `cos b cos u < 0` and `1 - cos^2 b cos^2 u < (Re / r)^2`. The orbit average of that product is the **solar exposure ratio** of the face for that beta angle. It replaces the typed `solar_view_ratio` of the *orbit-average* case.
2. **A beta sweep**: the steady-state temperatures of the existing model with the orbit-average heat loads, for beta angles from a minimum to a maximum in steps, as a table and a plot (temperature of each node against beta, with the unit limits).

What stays as it is and is **not** derived: the **Earth view** and the **albedo** of a face. The exact relations (the view factor of a plate to a sphere, the albedo integral over the sunlit disc) are textbook but long, depend on the attitude and on the face's tilt, and a mistake in them would not show in any test I can write without a second implementation. They stay typed per case (`earth_view_ratio`), sourced like today, and the sweep says so on its first line. This is the DV the sweep would carry (section 6).

Beyond this scope and **not proposed**: a transient (thermal capacity) model, a spacecraft that does not point to nadir (inertial or sun pointing: needs the attitude of each pointing mode of [pointing.md](models/pointing.md), a larger design), eclipses of the Moon, and a ray-traced view factor between faces.

## 3. New inputs

The model needs the **orientation of each surface** in the local-vertical frame, which no file records today. Proposed: an optional, sourced field on a surface of `config/thermal_model.yaml`:

```yaml
surfaces:
  - name: ADCS panel
    node: ADCS
    area_m2: 0.5
    emissivity_ratio: {...}
    absorptivity_ratio: {...}
    normal_lvlh: [0.0, 0.0, -1.0]     # outward unit normal in x (velocity), y (-orbit normal), z (nadir); optional
```

A surface without `normal_lvlh` keeps its typed view ratios (nothing changes); a surface with one takes its solar exposure from the beta angle in the sweep. The vector must be of length 1 within 1e-6; a surface that is not flat (a tube, a cone) has no normal and keeps the typed ratios. A new schema version of the file (3, identity migration, as `ebn0_table` was moved in 2.1.0), the inputs digest of a project that sets the field changes, an existing project's does not.

The sweep itself is a command, not a file: `budget thermal-beta PROJECT --case hot --beta-min 0 --beta-max 90 --beta-step 10 [--altitude-km ...]`, with the altitude read from the scenario's orbit unless given (a circular orbit at the semi-major axis, noted). Results: a CSV and the JSON of the usual result format, a plot, and the window's Thermal area gets a *Beta sweep* page in a second step.

## 4. How it is checked

1. **Closed forms**: at beta = 90 degrees the Sun is along the orbit normal, the orbit is never eclipsed, and the face with normal `-y` gets exactly 1 while every other face gets 0 (computed: 1.000 and 0.000). At beta = 0 the sunlit fraction is `1 - asin(Re/r) / pi` (at 700 km: 0.643, so an eclipse of 35.7 % of the orbit, the textbook value); the exposure of a face and of its opposite are equal for the faces along `x` (computed: 0.228 each at 700 km).
2. **Independent propagation**: for 8 beta angles, an orbit propagated with SGP4 (a real RAAN chosen so that the tool's own beta computation gives the angle) and the tool's own eclipse finder: the sunlit fraction must agree with the analytic one to 1 %, and the orbit average of `max(0, n . s)` computed from the propagated Sun vector in the propagated local-vertical frame must agree to 1 %.
3. **Limiting case**: a model with one face with typed ratios gives, in a sweep with `normal_lvlh` set to the face's direction at the beta of the typed case, the same temperatures as the existing static case.

## 5. What it changes in a release

Nothing for an existing project (no result, no file, no digest). A new schema version of one file, one new command, one new results table. No existing equation changes; three new equations (the exposure of a face, the sunlit fraction, the orbit-average heat load), registered with `SOURCE_MISSING` like the others until a reference text is attached.

## 6. Deviations the feature would carry

- **DV-T4 (proposed):** orbit-average heat loads with a steady-state solution (no thermal capacity): the temperatures are the ones a spacecraft of large thermal inertia would have on average, not the extremes of a real orbit; the extremes of a small spacecraft can be tens of kelvin from them.
- **DV-T5 (proposed):** circular orbit, nadir pointing, flat faces, a cylindrical shadow; the Earth view and albedo are typed, not derived.

## 7. Questions for the owner

1. **Is the Sun-only scope enough**, with the Earth view and albedo typed per case? The alternative is to derive those too, with a second independent implementation to check against (a ray-traced numerical integration, test-only), which roughly doubles the work and adds a second place where an error can hide.
2. **Is `normal_lvlh` the right input?** Another way is a named face (`+x`, `-y`, ...) of a box-shaped spacecraft, which is simpler to type and less general.
3. **Orbit-average only**, or also the worst instant of the orbit (the hot case is usually the peak flux, not the average)? The peak is one more column and needs no new inputs.
4. **Window page in the same release**, or the command first?

Recommendation: **yes** to the Sun-only scope; **`normal_lvlh`** with the named faces as a convenience in the form; **both** the average and the peak; **the command first**, the window page in a second release.
