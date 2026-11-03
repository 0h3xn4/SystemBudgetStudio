# Scenarios and environment

A scenario places the spacecraft in an orbit for a time span and decides which spacecraft mode is active when.

## Orbit and sites

An orbit is given as a two-line element set (TLE) or as mean orbital elements. Ground stations and imaging targets have a latitude, longitude, altitude and minimum elevation. The tool computes eclipses (cylindrical or conical shadow) and the passes over every site listed in the scenario. In the window, **Edit > Add scenario** (Ctrl+Shift+O) writes an orbit and a scenario of up to 180 days (an optional apogee altitude and argument of perigee make the orbit elliptical), and **Edit > Add ground station** (Ctrl+Shift+G) and **Add imaging target** (Ctrl+Shift+T) write the sites; a site is used once the scenario lists it under **Sites**.

## Models

Three choices of a scenario change the environment and the array output, each with a default that is what earlier versions did: `shadow_model` (cylindrical or conical), `earth_model` (WGS-84, or WGS-72 for the gravity constants of an orbit given as elements and the Earth sphere of the shadow; a TLE is always on WGS-72) and `irradiance_model` (constant, or seasonal). They are drop-downs in **Model > Scenario**; every report names the models it used. See the chapter *Tracing a number*.

## Mode timeline

`default_mode` is active unless a rule or a segment says otherwise. Rules switch modes automatically (`in_eclipse`, `during_pass` of a site, with a lead and lag time); segments set a mode for a fixed interval. The **Scenario** page shows the resulting timeline and lets you edit rules and segments as sentences: a rule reads *Downlink during every pass over gs_north*, or *Imaging throughout every eclipse* (the mode lasts the whole eclipse; use a manual segment to limit it).

## Time grid

`start_utc`, `duration_s` and `step_s` define the grid on which the time-domain budgets are evaluated. Eclipses and mode segments are overlapped exactly with each step, not sampled. In the window the three are fields at the top of the scenario editor (each change is one undo step). A week at 1 s resolution with 200 units is computed in about 10 seconds.

## Statistics

After **Compute**, the **Statistics** tab gives the number, shortest, mean and longest eclipse, the share of the scenario in eclipse and the longest stretch of sunlight, and for every ground station and imaging target the number of passes, the time in contact, the shortest, mean and longest pass, the largest gap without a pass and the lowest, mean and highest peak elevation. The **Passes** tab can show one station or all. The **Beta angle** tab plots the angle between the Sun and the orbit plane over the scenario, and the Statistics tab gives its minimum, mean and maximum and the critical angle above which a circular orbit has no eclipse. The same figures are in `<id>_environment.json` under `statistics`, and the series in `<id>_beta.csv`.

The **Ground track** tab draws the sub-satellite point on a 30-degree graticule with the stations and targets marked (the tool carries no coastline data), and the Statistics tab gives the latitude range and the longitude shift between two ascending equator crossings. `<id>_groundtrack.csv` has the series.

## Imported environments

Instead of the built-in propagator a scenario can read orbit, eclipse and pass files exported by SpaceMissionStudio (`environment_source: spacemissionstudio`). The format is described in `docs/ENVIRONMENT_FORMAT.md` in the source repository.
