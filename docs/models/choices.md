# Model choices

Generated from the registry in `budget_core/model_choices.py` (`budget choices --markdown`); a test fails when this page is out of date. A *model choice* is a place where a result depends on a modelling decision. A choice is **selectable** only when a defensible alternative with a citable source exists, it can be checked against an independent reference, it changes one thing and its default is the behaviour of every project that does not say ([transparency_p5_design.md](../transparency_p5_design.md), section 2). Every other model is listed as **fixed**, with the reason, so that none is hidden. Nothing on this page changes a result by being listed.

**Where a choice is made.** *Scenario file*: a field of the scenario, so two scenarios can use two models. *Run option*: an option of a run, recorded in the run parameters. *Fixed*: not selectable in this version.

**Contents:** [Environment: orbit, Earth, Sun, eclipses](#environment-orbit-earth-sun-eclipses) · [Power](#power) · [Thermal](#thermal) · [Mass](#mass) · [RF link](#rf-link)

## Environment: orbit, Earth, Sun, eclipses

| Id | Choice | Default | Alternatives | Made in | Acts on | Reference |
|---|---|---|---|---|---|---|
| `environment.source` | Source of the environment | Computed from the orbit file | `elements`; `spacemissionstudio` | scenarios/<id>.yaml field environment_source | Where the orbit, the eclipses and the passes come from. | DEVIATIONS DV-I1, docs/ENVIRONMENT_FORMAT.md |
| `environment.shadow_model` | Shadow geometry | Cylindrical shadow | `cylindrical`; `conical` | scenarios/<id>.yaml field shadow_model | Eclipse times, the sunlit fraction of the array and every result that follows from them. | DEVIATIONS DV-P1, DV-E4 |
| `environment.earth_model` | Earth constants | WGS-84 | `wgs84`; `wgs72` | scenarios/<id>.yaml field earth_model | The propagation of an orbit given as elements (mean motion and the SGP4 constants) and the Earth sphere of the shadow. The ground sites stay WGS-84 geodetic coordinates, a TLE stays on WGS-72, an imported environment is not computed here. | DEVIATIONS DV-E5 |
| `environment.propagation` | Orbit propagation | SGP4 on mean elements | (none: fixed) | Fixed | Every position of the spacecraft. | DEVIATIONS DV-E2: elements are used as mean elements, without drag (B* = 0). A numerical propagator is a different model with new inputs (forces, drag), not a switch. |
| `environment.gravity_tle` | Gravity model of a TLE | WGS-72 | (none: fixed) | Fixed | The propagation of a TLE. | DEVIATIONS DV-E5: the SGP4 library's default constants, the usual pairing for TLEs; SGP4 is defined on this set. |
| `environment.sun_position` | Sun position | Low-precision almanac formulae (about 0.01 degree) | (none: fixed) | Fixed | The Sun direction and distance, the shadow and the array incidence. | DEVIATIONS DV-E1; equation ENV-SUN. A high-precision ephemeris needs data or a dependency that is not offline and licence-clean today. |
| `environment.earth_rotation` | Earth rotation | GMST only, UTC treated as UT1 | (none: fixed) | Fixed | The ground track, the passes and the visibility of a site. | DEVIATIONS DV-E1: up to 0.9 s, about 400 m on the ground. |
| `environment.shadow_earth` | Earth in the shadow geometry | Sphere of the equatorial radius | (none: fixed) | Fixed | The edge of the shadow. | DEVIATIONS DV-P1: no oblateness, no atmosphere. |
| `environment.eclipse` | Eclipse | Any shadow, penumbra included | (none: fixed) | Fixed | Whether an interval counts as an eclipse. | DEVIATIONS DV-E4: the sunlight ratio is below 1 by more than 1e-12. |

## Power

| Id | Choice | Default | Alternatives | Made in | Acts on | Reference |
|---|---|---|---|---|---|---|
| `power.load_basis` | Load basis of the power timeline | Nominal loads | `nominal`; `margined` | Option --load-basis of budget power-timeline; the window runs the nominal basis | The demand of every mode, and so the energy balance and the battery. | docs/models/power-timeline.md |
| `power.cases` | Power cases | BOL and EOL (EOL at the design life) | (none: fixed) | Fixed | The age of the array and the battery in every result. | DEVIATIONS DV-P2; power_system.design_life_yr. |
| `power.array_irradiance` | Irradiance on the array | Constant solar_irradiance_wm2 | (none: fixed) | Fixed | The array output. | DEVIATIONS DV-P5: no Earth-Sun distance variation. A seasonal irradiance is planned for 2.0.0 (P5c). |

## Thermal

| Id | Choice | Default | Alternatives | Made in | Acts on | Reference |
|---|---|---|---|---|---|---|
| `thermal.model` | Thermal model | Steady state, isothermal nodes, radiation to one sink | (none: fixed) | Fixed | Every temperature. | DEVIATIONS DV-T1, DV-T3: a transient model or view factors are a different model with new inputs, not a switch. |

## Mass

| Id | Choice | Default | Alternatives | Made in | Acts on | Reference |
|---|---|---|---|---|---|---|
| `mass.margin_position` | Position of the margin mass | None: the margin is in the totals only | (none: fixed) | Fixed | The centre of gravity and the inertia use nominal masses. | DEVIATIONS DV-M1: giving the margin a position needs new inputs. |

## RF link

| Id | Choice | Default | Alternatives | Made in | Acts on | Reference |
|---|---|---|---|---|---|---|
| `link.rate_selection` | Data rate of a link | The highest listed rate that closes the margin | (none: fixed) | Fixed | The rate and the data volume of every pass. | docs/models/link-static.md; the rate at which the margin equals the required margin is computed and shown beside it. No other policy is offered (owner decision, D-219). |

## The alternatives of the selectable choices

### Source of the environment

`environment.source`, made in: scenarios/<id>.yaml field environment_source. Default: `elements`.

| Value | Title | Equations | Source or note |
|---|---|---|---|
| `elements` | Computed from the orbit file | `ENV-SUN`, `ENV-GMST`, `ENV-GEODETIC` | SGP4 on the orbit of the project, or on its TLE. ENV-SUN: SOURCE_MISSING; ENV-GMST: sgp4 library, sgp4.propagation.gstime (IAU-82 GMST, Vallado); ENV-GEODETIC: WGS 84 (NIMA TR8350.2) ellipsoid definition |
| `spacemissionstudio` | Read from a SpaceMissionStudio export | (none) | The positions, eclipses and passes are imported, not computed here. |

### Shadow geometry

`environment.shadow_model`, made in: scenarios/<id>.yaml field shadow_model. Default: `cylindrical`.

| Value | Title | Equations | Source or note |
|---|---|---|---|
| `cylindrical` | Cylindrical shadow | `ENV-SHADOW-CYL` | The Sun is a point at infinity: lit or dark, no penumbra. ENV-SHADOW-CYL: SOURCE_MISSING |
| `conical` | Conical shadow (umbra, penumbra, annular) | `ENV-SHADOW-CON` | The Sun and the Earth are discs: the lit fraction falls through the penumbra. ENV-SHADOW-CON: SOURCE_MISSING |

### Earth constants

`environment.earth_model`, made in: scenarios/<id>.yaml field earth_model. Default: `wgs84`.

| Value | Title | Equations | Source or note |
|---|---|---|---|
| `wgs84` | WGS-84 | (none) | The default. WGS 84 (NIMA TR8350.2), the set of the sgp4 library: equatorial radius 6378.137 km, mu 398600.5 km3/s2. |
| `wgs72` | WGS-72 | (none) | Also the set a TLE is defined on. WGS 72, the gravity constants of the SGP4 theory (Hoots and Roehrich, Spacetrack Report No. 3), the set of the sgp4 library: equatorial radius 6378.135 km, mu 398600.8 km3/s2. |

### Load basis of the power timeline

`power.load_basis`, made in: Option --load-basis of budget power-timeline; the window runs the nominal basis. Default: `nominal`.

| Value | Title | Equations | Source or note |
|---|---|---|---|
| `nominal` | Nominal loads | (none) | The average and peak power of each mode as given. |
| `margined` | Margined loads | (none) | The same with the system and source margins applied. |

Next: [Models](README.md) · [Docs index](../README.md).
