"""`budget thermal-beta`: the node temperatures against the beta angle (2.7.0, D-250).

Solves the project's steady-state thermal model for a range of beta angles, taking the solar view of
every surface that gives its `normal_lvlh` from the angle (orbit average, the worst instant, or
both). The orbit is a circle at the altitude of the scenario's orbit, or the one given with
`--altitude-km`. Writes a CSV, a JSON and a plot next to the other results.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from budget_core.environment.constants import DEFAULT_EARTH_MODEL, EARTH_MODELS
from budget_core.provenance import make_provenance
from budget_core.reports.files import write_files
from budget_core.thermal.beta_sweep import (
    BetaSweep,
    BetaSweepError,
    Mode,
    beta_range,
    orbit_of_run,
    thermal_beta_sweep,
)

MODES: tuple[Mode, ...] = ("average", "peak")


def add_parser(sub: Any, *, folder: Any, iso_datetime: Any, float_type: Any = float) -> None:
    p = sub.add_parser(
        "thermal-beta",
        help="Node temperatures against the beta angle (orbit average and worst instant).",
    )
    p.add_argument("project", type=Path, help="Project folder (contains project.yaml).")
    p.add_argument("--case", help="Thermal case to solve (default: hot, or the only one).")
    p.add_argument(
        "--mode",
        choices=(*MODES, "both"),
        default="both",
        help="Orbit-average heat loads, the instant of the most absorbed sunlight, or both.",
    )
    p.add_argument("--beta-min", type=float_type, default=-90.0, help="Lowest beta angle, deg.")
    p.add_argument("--beta-max", type=float_type, default=90.0, help="Highest beta angle, deg.")
    p.add_argument("--beta-step", type=float_type, default=15.0, help="Beta angle step, deg.")
    p.add_argument(
        "--scenario", help="Scenario whose orbit gives the altitude (optional if only one)."
    )
    p.add_argument(
        "--altitude-km", type=float_type, help="Altitude of a circular orbit, km (no scenario)."
    )
    p.add_argument(
        "--earth-model",
        choices=sorted(EARTH_MODELS),
        default=DEFAULT_EARTH_MODEL,
        help="Earth radius with --altitude-km (a scenario brings its own). Default: wgs84.",
    )
    p.add_argument("--out", type=folder, help="Output folder (default: <project>/results).")
    p.add_argument("--no-plots", action="store_true", help="Do not write the plots.")
    p.add_argument("--user", help="User name for the provenance block.")
    p.add_argument("--date", type=iso_datetime, help="Generation time, ISO 8601.")
    p.add_argument("--strict", action="store_true", help="Treat warnings as failures.")


def _case_of(env_cases: list[str], requested: str | None) -> tuple[str | None, str]:
    if requested is not None:
        return requested, ""
    if "hot" in env_cases:
        return "hot", ""
    if len(env_cases) == 1:
        return env_cases[0], ""
    return None, "The thermal environment has several cases; choose one with --case."


def _summary(sweep: BetaSweep) -> list[str]:
    lines = [
        f"Case {sweep.case}, {'orbit average' if sweep.mode == 'average' else 'worst instant'}: "
        f"circular orbit {sweep.altitude_m / 1000.0:.0f} km, "
        f"{len(sweep.surfaces_from_beta)} surface(s) from the beta angle, "
        f"{len(sweep.surfaces_typed)} with typed view ratios."
    ]
    for p in sweep.points:
        if not p.case.complete:
            lines.append(f"  beta {p.beta_deg:+7.2f} deg: n/a (inputs missing, see the problems)")
            continue
        hot = max(p.case.nodes, key=lambda n: n.temperature_k)
        cold = min(p.case.nodes, key=lambda n: n.temperature_k)
        exceeded = sum(1 for c in p.case.checks if c.status == "exceeded")
        lines.append(
            f"  beta {p.beta_deg:+7.2f} deg  sunlit {p.sunlit_fraction * 100:5.1f} %  "
            f"hottest {hot.node} {hot.temperature_k:6.1f} K  coldest {cold.node} "
            f"{cold.temperature_k:6.1f} K  {exceeded} unit(s) beyond a limit"
        )
    return lines


def run(args: argparse.Namespace) -> int:
    from budget_cli.main import _choose_scenario, _fail, _finish, _load_or_fail
    from budget_core.reports.thermal_beta_export import beta_files
    from budget_core.scenario.run import ScenarioRunError, run_scenario

    loaded, code = _load_or_fail(args.project)
    if loaded is None or loaded.project is None:
        return code
    project = loaded.project
    env = project.config.thermal_environment
    if project.config.thermal_model is None or env is None:
        _fail("The project has no thermal model or thermal environment; nothing to compute.")
        return 1
    case, why = _case_of(sorted(env.cases), args.case)
    if case is None:
        _fail(why)
        return 2
    try:
        angles = beta_range(args.beta_min, args.beta_max, args.beta_step)
    except BetaSweepError as exc:
        _fail(str(exc))
        return 2

    scenario_label = "static (no scenario)"
    if args.altitude_km is not None:
        if args.altitude_km <= 0.0:
            _fail("The altitude is above 0 km.")
            return 2
        earth_radius = EARTH_MODELS[args.earth_model].radius_m
        orbit_radius = earth_radius + args.altitude_km * 1000.0
    else:
        scenario_id, code = _choose_scenario(project, args.scenario)
        if scenario_id is None:
            return code
        try:
            run = run_scenario(project, scenario_id)
        except ScenarioRunError as exc:
            _fail(exc.problem.format())
            return 1
        try:
            earth_radius, orbit_radius = orbit_of_run(run)
        except BetaSweepError as exc:
            _fail(f"{exc} Give --altitude-km.")
            return 1
        scenario_label = run.scenario_id

    provenance = make_provenance(
        project, scenario=scenario_label, user=args.user, generated_at=args.date
    )
    folder = args.out or (args.project / "results")
    problems = list(loaded.problems)
    files: list[tuple[str, bytes | str]] = []
    modes = MODES if args.mode == "both" else (args.mode,)
    for mode in modes:
        try:
            sweep = thermal_beta_sweep(
                project,
                case,
                angles,
                mode=mode,
                earth_radius_m=earth_radius,
                orbit_radius_m=orbit_radius,
            )
        except BetaSweepError as exc:
            _fail(str(exc))
            return 1
        problems.extend(sweep.problems)
        files.extend(beta_files(sweep, provenance, loaded.problems, plots=not args.no_plots))
        for line in _summary(sweep):
            print(line)
    for path in write_files(folder, files):
        print(f"Wrote {path}")
    return _finish(problems, [], args.strict)
