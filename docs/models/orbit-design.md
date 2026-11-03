# Orbit design helpers

**What it computes.** From what a mission analyst asks for to the numbers an orbit file takes: the local time of the ascending node and the right ascension that goes with it, the inclination (or the altitude) of a sun-synchronous orbit, and the orbit whose ground track repeats. In the window it is *Edit → Orbit helper…* (2.2.0), on the command line `budget orbit` ([command line](../user-manual/command-line.md)); how to use it is in [scenarios](../user-manual/scenarios.md#how-do-i-design-the-orbit-local-time-sun-synchronous-repeat-ground-track).

**What it is not.** It reads no project file and changes no result: it writes plain elements, which the scenario then propagates as before. Each number is a definition, a constant of the Earth model of the scenario or an input of the user.

## Equations

| Id | Name | Formula | Source |
|---|---|---|---|
| ORB-J2-RATES | Secular rates of a mean orbit under J2 | `k = 1.5 J2 (Re/p)² n`; node `Ω̇ = −k cos i`; perigee `ω̇ = k (2 − 2.5 sin² i)`; mean anomaly `Ṁ = n + k √(1−e²) (1 − 1.5 sin² i)`; `p = a (1−e²)`, `n = √(μ/a³)` | first-order secular J2 theory, a textbook relation; citation to be supplied (SOURCE_MISSING) |
| ORB-SSO | Sun-synchronous condition | `cos i = −ω_sun / (1.5 J2 (Re/p)² n)`; `ω_sun` the rate of the mean Sun (360° per tropical year) | same; `ω_sun` is the coefficient of the Sun model (ENV-SUN) |
| ORB-LTAN | Mean local solar time of the ascending node | `LTAN = UT + (Ω − GMST) / 15°/h` (mod 24 h), GMST from ENV-GMST | mean solar time is universal time plus longitude over 15° per hour; the equation of time is not applied |
| ORB-REPEAT | Repeat ground track | `(ω̇ + Ṁ) / (ω_earth − Ω̇) = N / D`, solved for `a` by bisection | textbook relation; citation to be supplied (SOURCE_MISSING) |

`Re`, `μ` and `J2` are those of the Earth model of the scenario, WGS-84 or WGS-72 ([model choices](choices.md)); `ω_earth` is the rate of the GMST polynomial the tool uses for the Earth rotation (7.2921158553e-5 rad/s), `ω_sun` that of the Sun model (0.9856474 °/day). Both are listed with the other constants in [settings](settings.md).

## Steps

1. **LTAN and RAAN.** The local time is `UT + (Ω − GMST)/15`, so the right ascension for a wanted local time at an epoch is `GMST + 15 (LTAN − UT)`. UTC is taken as UT1 (DV-E1, at most 0.9 s, 0.004° of node).
2. **Sun-synchronous inclination.** ORB-SSO gives the inclination of an altitude and eccentricity (always above 90°); above about 5,974 km (circular) the node cannot move fast enough and there is no solution. The altitude of an inclination is the same relation solved for `a`.
3. **Repeat ground track.** A nodal day is the time the Earth takes to turn once relative to the node, `2π / (ω_earth − Ω̇)`. An orbit repeats after N nodal periods in D nodal days when the angular rate from the node over that angular rate is N/D; the semi-major axis is found by bisection between a perigee 100 km above the surface and the highest orbit that fits (for a sun-synchronous orbit, the one with `cos i = −1`). The tracks of a repeat cycle are spaced `2π Re / N` apart at the equator. For a sun-synchronous orbit the nodal day is exactly 24 mean solar hours, so 15 revolutions per day is a nodal period of 96.000 min.

## How it was checked

Not against its own formulas. Against the SGP4 propagation the scenario uses, against the mean Sun of the Sun model, and against textbook values:

- the node of a sun-synchronous design drifts in SGP4 at the mean-Sun rate to 0.15 % (0.9841 against 0.9856 °/day), so its local time moves by 11 s in 30 days;
- the local time from sidereal time agrees with `12 h + (Ω − L)/15` from the mean longitude of the Sun to 0.02 h;
- the sun-synchronous inclinations at 600, 700 and 800 km are 97.79°, 98.19° and 98.60°;
- 14 revolutions a day (SSO) at 888 km: the ascending-node longitude after 14 revolutions in SGP4 differs by 0.21° from where it started, against tracks 25.7° apart.

## Accuracy and limits

First-order J2 only: SGP4 includes terms of higher order, so a designed orbit behaves in the tool as designed to a few parts in a thousand (DEVIATIONS DV-E6). The elements are *mean* elements, the way the scenario uses them (DV-E2): the node of the *osculating* orbit at the epoch is about two minutes of local time away from the mean node (0.03 h at 650 km, circular, argument of latitude 0), and that offset is constant. The local time is the mean solar one; the true local time differs by the equation of time (up to about ±16 minutes during the year). No drag, no third-body forces, no frozen-orbit design.
