# Thermal model against the beta angle

Added in 2.7.0 (decision D-250, deviations DV-T4 and DV-T5). It builds on the [static thermal budget](thermal-static.md): the same nodes, conductances, surfaces and cases, solved for a range of beta angles with the solar exposure of the surfaces taken from the geometry.

## What it computes

For each beta angle in a range and for one thermal case: the steady-state temperature of every node, the check of every unit against its limits, and the sunlit part of the orbit. Command: `budget thermal-beta`, and the **Beta sweep** page of the Thermal area in the window (2.8.0), which asks the same code ([manual](../user-manual/thermal-budget.md#how-do-the-temperatures-change-with-the-beta-angle)).

## Equations

| Id | Name | Formula |
|---|---|---|
| TH-BETA-LIT | Sunlit part of a circular orbit | eclipse half-angle `phi = acos(sqrt(1 - (Re/r)^2) / cos b)` when `\|sin b\| < Re/r`, else none; sunlit fraction `1 - phi/pi` |
| TH-BETA-SUN | Solar exposure of a flat face | `f = (1/2pi) integral over the sunlit orbit of max(0, n . s) du`, `s = (-cos b sin u, -sin b, -cos b cos u)` |

`b` is the beta angle, `u` the angle along the orbit from noon (the point nearest the Sun), `Re` the Earth radius of the Earth model and `r` the orbit radius. `s` is the unit vector to the Sun in the local-vertical frame of a nadir-pointing spacecraft (x along the velocity, y opposite to the orbit normal, z to nadir) and `n` the outward unit normal of the face in that frame. The shadow is the cylinder of the Earth (the tool's cylindrical shadow model).

On the sunlit arc `n . s = R cos(u - d) + c` with `c = -n_y sin b`, so the integral and the largest value are closed forms: the code splits the arc at the zero crossings and integrates each piece, with no sampling. The **average** mode uses `f` as the solar view ratio of the surface in `TH-ABS`. The **peak** mode finds the orbit angle that maximises the sum over the surfaces of `alpha A max(0, n . s)` (the sunlight absorbed per unit of solar flux, found on a fine grid and refined by golden-section search) and uses `max(0, n . s)` of every surface at that angle.

## Inputs

| Symbol | File and field | Notes |
|---|---|---|
| `n` | `config/thermal_model.yaml`, `surfaces[i].normal_lvlh` | a unit vector (length 1 within 1e-6) or a face name; a design input, not a sourced number; a surface without it keeps its typed view ratios |
| orbit radius | the scenario's orbit (the mean radius of the propagated positions) or `--altitude-km` | a circular orbit |
| `Re` | the Earth model of the scenario, or `--earth-model` | WGS-84 or WGS-72 constants of the SGP4 library |
| Earth view, albedo, fluxes, dissipation, limits | as the static thermal budget | typed per case, sourced; a surface with a normal but no Earth view for the case is a placeholder and that beta angle is n/a |

## How it is checked

- **Closed forms** (tests): with the Sun along the orbit normal (beta 90) the orbit is never eclipsed, the face with normal `-y` has exposure 1 and every other face 0; at beta 0 the sunlit part is `1 - asin(Re/r)/pi` (0.643 at 700 km); the eclipse ends at `asin(Re/r)` (64.3 degrees at 700 km); faces along x get the same; the sign of the beta angle swaps `+y` and `-y`.
- **The same integral by sampling**: 400 000 samples for 10 beta angles and 7 normals, agreement within 2e-5.
- **The orbit the tool propagates**: for four right ascensions of the example orbit (beta angles of 25, 60, -32 and -76 degrees) the exposure of each of the six faces, computed from the propagated positions and velocities, the Sun of the tool's own Sun model and the eclipses of the tool's own eclipse finder in the local-vertical frame, agrees with the closed form within 0.004 (the orbit is not exactly circular), and the sunlit part within 0.01.
- **Limiting case**: type, for every surface, the solar view the geometry gives at 40 degrees; the sweep at 40 degrees equals the static thermal budget to 1e-9 K.

## What it does not do (DV-T4, DV-T5)

- **No thermal capacity.** The temperatures are those of steady state at orbit-average heat loads (a spacecraft of large thermal inertia), or at one instant (the peak): not the swing of a real orbit. The extremes of a small spacecraft can be tens of kelvin from them. In the peak mode the instant is the one of the most sunlight absorbed; a node whose faces look away at that instant can be cooler than on average.
- **A circular orbit, nadir pointing, flat faces, a cylindrical shadow.** A spacecraft that points elsewhere (inertial, sun-pointing) and a surface that is not flat have no `normal_lvlh` and keep their typed ratios; an eccentric orbit uses its mean radius.
- **The Earth view and the albedo are typed**, not derived: the view factor of a plate to a sphere and the albedo integral are textbook but cannot be checked here without a second implementation. The sweep takes them from the case as they are, so they do not change with the beta angle.
- **The dissipation of the case does not change** with eclipse (the case names one spacecraft mode).

Next: [Models](README.md) · [Static thermal budget](thermal-static.md).
