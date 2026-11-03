# Orbit design helpers

**What it computes.** From what a mission analyst asks for to the numbers an orbit file takes: the local time of the ascending node and the right ascension that goes with it, the inclination (or the altitude) of a sun-synchronous orbit, and the orbit whose ground track repeats. In the window it is *Edit → Orbit helper…* (2.2.0), on the command line `budget orbit` ([command line](../user-manual/command-line.md)); how to use it is in [scenarios](../user-manual/scenarios.md#how-do-i-design-the-orbit-local-time-sun-synchronous-repeat-ground-track).

**What it is not.** It reads no project file and changes no result: it writes plain elements, which the scenario then propagates as before. Each number is a definition, a constant of the Earth model of the scenario or an input of the user.

## Equations

| Id | Name | Formula | Source |
|---|---|---|---|
| ORB-J2-RATES | Secular rates of a mean orbit under J2 | `k = 1.5 J2 (Re/p)² n`; node `Ω̇ = −k cos i`; perigee `ω̇ = k (2 − 2.5 sin² i)`; mean anomaly `Ṁ = n + k √(1−e²) (1 − 1.5 sin² i)`; `p = a (1−e²)`, `n = √(μ/a³)` | first-order secular J2 theory, a textbook relation; citation to be supplied (SOURCE_MISSING) |
| ORB-SSO | Sun-synchronous condition | `cos i = −ω_sun / (1.5 J2 (Re/p)² n)`; `ω_sun` the rate of the mean Sun (360° per tropical year) | same; `ω_sun` is the coefficient of the Sun model (ENV-SUN) |
| ORB-LTAN | Mean local solar time of the ascending node | `LTAN = UT + (Ω − GMST) / 15°/h` (mod 24 h), GMST from ENV-GMST | mean solar time is universal time plus longitude over 15° per hour; the equation of time is not applied |
| ORB-FRAME | J2000 to TEME rotation | IAU-76 precession, ten terms of the IAU-1980 nutation, equation of the equinoxes | reproduced from memory; checked against astropy |
| ORB-STATE-FIT | Mean elements of a state vector | Newton's method for the elements whose SGP4 state at the epoch is the given one | a numerical fit to the tool's propagator |
| ORB-BETA | Beta angle | `β = asin((r × v)/|r × v| · s)`; critical angle `asin(Re / r)` | textbook definition; citation to be supplied (SOURCE_MISSING) |
| ORB-REPEAT | Repeat ground track | `(ω̇ + Ṁ) / (ω_earth − Ω̇) = N / D`, solved for `a` by bisection | textbook relation; citation to be supplied (SOURCE_MISSING) |

`Re`, `μ` and `J2` are those of the Earth model of the scenario, WGS-84 or WGS-72 ([model choices](choices.md)); `ω_earth` is the rate of the GMST polynomial the tool uses for the Earth rotation (7.2921158553e-5 rad/s), `ω_sun` that of the Sun model (0.9856474 °/day). Both are listed with the other constants in [settings](settings.md).

## Steps

1. **LTAN and RAAN.** The local time is `UT + (Ω − GMST)/15`, so the right ascension for a wanted local time at an epoch is `GMST + 15 (LTAN − UT)`. UTC is taken as UT1 (DV-E1, at most 0.9 s, 0.004° of node).
2. **Sun-synchronous inclination.** ORB-SSO gives the inclination of an altitude and eccentricity (always above 90°); above about 5,974 km (circular) the node cannot move fast enough and there is no solution. The altitude of an inclination is the same relation solved for `a`.
3. **Repeat ground track.** A nodal day is the time the Earth takes to turn once relative to the node, `2π / (ω_earth − Ω̇)`. An orbit repeats after N nodal periods in D nodal days when the angular rate from the node over that angular rate is N/D; the semi-major axis is found by bisection between a perigee 100 km above the surface and the highest orbit that fits (for a sun-synchronous orbit, the one with `cos i = −1`). The tracks of a repeat cycle are spaced `2π Re / N` apart at the equator. For a sun-synchronous orbit the nodal day is exactly 24 mean solar hours, so 15 revolutions per day is a nodal period of 96.000 min.

## State vectors

An orbit file may hold a position and velocity at an epoch (`state:`, [environment format](../ENVIRONMENT_FORMAT.md)). Two steps make it propagable:

1. **The frame (ORB-FRAME).** J2000 to TEME is the IAU-76 precession (`ζ`, `θ`, `z` polynomials), the ten largest terms of the IAU-1980 nutation (`Δψ`, `Δε`) and the equation of the equinoxes `Δψ cos ε` (TOD to TEME). A TEME state is used as it is. Against the full GCRS to TEME transformation of astropy at four dates (2000, 2010, 2026, 2040) the rotated position of a 7000 km vector differs by 0.7, 1.1, 1.8 and 2.4 m; the tests hold the same reference values.
2. **The elements (ORB-STATE-FIT).** The six mean elements are found for which SGP4's own state at the epoch equals the given one: Newton's method on the equinoctial elements (a, f, g, h, k, L), so that circular and equatorial orbits are not singular, with a finite-difference Jacobian and a halved step while the residual grows. A low orbit needs two iterations and about a millisecond; the state is reproduced to 3e-5 m and 1e-8 m/s. The fit uses the gravity set of the scenario's Earth model.

Checked by round trip (elements, then the SGP4 state, then the fit, in six orbits from circular to geostationary-like, prograde and retrograde, in TEME and in J2000: the elements come back to 1e-9 relative, and a day after the epoch the two orbits are 0.01 m apart) and by a scenario on a state: it gives the eclipses of the same orbit given as elements to 0.01 s. **Limits** ([DV-E7](../DEVIATIONS.md)): a retrograde equatorial orbit (inclination 180°) is not supported; mean and osculating elements differ (11.7 km in the semi-major axis at 600 km), so a state vector must not be typed as elements; after the epoch the orbit is SGP4's, without drag.

## Beta angle

The beta angle of a scenario is `asin((r × v)/|r × v| · s)` (ORB-BETA): the angle between the Sun direction `s` and the orbit plane, positive when the Sun is on the side the orbit normal points to, from −90° to +90°. `r` and `v` are the TEME state the propagator gives at every step, `s` the Sun model (ENV-SUN). It is shown as a plot and as minimum, mean and maximum on the Scenario page, and written as `<id>_beta.csv` (every ten minutes or every step if that is longer, [settings](settings.md)) and under `statistics.beta` in the environment JSON. The **critical angle** is `asin(Re / r)` at the mean radius: with the Earth as a cylinder of shadow, a circular orbit has no eclipse while |β| is above it (64° at 700 km). It is exact for a circular orbit; for an eccentric one the eclipse-free condition depends on where the Sun lies and the figure is an approximation at the mean radius. For an imported environment (no velocity) the plane is taken from the imported positions, `v = dr/dt`.

Checked against the closed form of the elements, `sin β = s · (sin Ω sin i, −cos Ω sin i, cos i)` (0.002° at the start, 0.05° over a day once the node's motion is included), and against the eclipses of the scenario: a dawn-dusk sun-synchronous orbit in June has |β| above the critical angle and no eclipse, a noon-midnight orbit at the equinox has |β| below it and an eclipse every orbit.

## How it was checked

Not against its own formulas. Against the SGP4 propagation the scenario uses, against the mean Sun of the Sun model, and against textbook values:

- the node of a sun-synchronous design drifts in SGP4 at the mean-Sun rate to 0.15 % (0.9841 against 0.9856 °/day), so its local time moves by 11 s in 30 days;
- the local time from sidereal time agrees with `12 h + (Ω − L)/15` from the mean longitude of the Sun to 0.02 h;
- the sun-synchronous inclinations at 600, 700 and 800 km are 97.79°, 98.19° and 98.60°;
- 14 revolutions a day (SSO) at 888 km: the ascending-node longitude after 14 revolutions in SGP4 differs by 0.21° from where it started, against tracks 25.7° apart.

## Accuracy and limits

First-order J2 only: SGP4 includes terms of higher order, so a designed orbit behaves in the tool as designed to a few parts in a thousand (DEVIATIONS DV-E6). The elements are *mean* elements, the way the scenario uses them (DV-E2): the node of the *osculating* orbit at the epoch is about two minutes of local time away from the mean node (0.03 h at 650 km, circular, argument of latitude 0), and that offset is constant. The local time is the mean solar one; the true local time differs by the equation of time (up to about ±16 minutes during the year). No drag, no third-body forces, no frozen-orbit design.
