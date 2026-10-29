"""Run a scenario: compute its environment and mode timeline."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from budget_core.control import RunControl, checkpoint, stage
from budget_core.environment.data import (
    Environment,
    EnvironmentData,
    PropagationError,
    SiteDef,
    TimeGrid,
)
from budget_core.environment.elements import ElementsPropagator, orbit_age_problem
from budget_core.environment.spacemissionstudio import (
    EnvironmentInputError,
    SpaceMissionStudioImport,
)
from budget_core.io.paths import resolve_inside
from budget_core.io.project_loader import model_to_data
from budget_core.model import Project, Scenario
from budget_core.problems import Problem, Severity
from budget_core.scenario.timeline import TimelineSegment, build_timeline
from budget_core.timeutil import format_utc, parse_utc


class ScenarioRunError(Exception):
    """A scenario cannot be run; `problem` explains why in plain words."""

    def __init__(self, problem: Problem) -> None:
        super().__init__(problem.message)
        self.problem = problem


@dataclass(frozen=True, eq=False)
class ScenarioRun:
    scenario_id: str
    scenario: Scenario
    env: EnvironmentData
    timeline: tuple[TimelineSegment, ...]
    notes: tuple[str, ...]
    problems: tuple[Problem, ...] = ()  # findings of the run itself (an old TLE)


# what the report says of the Earth model the geometry was computed on (D-219)
EARTH_MODEL_TEXT = {
    "wgs84": "WGS-84",
    "wgs72": "WGS-72",
    "tle": "TLE: WGS-72 propagation, WGS-84 geometry",
    "imported": "not used (imported environment)",
}


def run_parameters(run: ScenarioRun) -> tuple[tuple[str, str], ...]:
    """The scenario options that change a number, for the provenance of a run's outputs."""
    env, sc = run.env, run.scenario
    return (
        ("Environment source", str(env.source)),
        ("Shadow model", str(env.shadow_model)),
        ("Earth model", EARTH_MODEL_TEXT.get(env.earth_model, env.earth_model)),
        ("Start (UTC)", format_utc(env.grid.start)),
        ("Duration", f"{sc.duration_s:.0f} s"),
        ("Step", f"{sc.step_s:g} s"),
    )


def grid_for(scenario: Scenario) -> TimeGrid:
    return TimeGrid(parse_utc(scenario.start_utc), scenario.duration_s, scenario.step_s)


def sites_for(project: Project, scenario: Scenario) -> list[SiteDef]:
    out: list[SiteDef] = []
    for site_id in scenario.sites:
        if site_id in project.ground_stations:
            g = project.ground_stations[site_id]
            out.append(
                SiteDef(
                    site_id,
                    "ground_station",
                    g.latitude_deg,
                    g.longitude_deg,
                    g.altitude_m,
                    g.min_elevation_deg,
                )
            )
        else:
            t = project.targets[site_id]
            out.append(
                SiteDef(
                    site_id,
                    "target",
                    t.latitude_deg,
                    t.longitude_deg,
                    t.altitude_m,
                    t.min_elevation_deg,
                )
            )
    return out


def environment_for(project: Project, scenario: Scenario) -> Environment:
    if scenario.environment_source == "spacemissionstudio":
        assert scenario.import_dir is not None
        folder = resolve_inside(project.root, scenario.import_dir)
        if folder is None:
            raise ScenarioRunError(
                Problem(
                    Severity.ERROR,
                    "IMPORT_DIR_MISSING",
                    "The import folder must be inside the project folder.",
                    hint="Use a relative path below the project folder.",
                )
            )
        return SpaceMissionStudioImport(folder)
    assert scenario.orbit is not None
    return ElementsPropagator(project.orbits[scenario.orbit], scenario.earth_model)


def run_scenario(
    project: Project, scenario_id: str, control: RunControl | None = None
) -> ScenarioRun:
    """Compute the environment and the mode timeline. The project must be valid. A `control`
    reports the stages and can stop it between them (the environment is one step)."""
    if scenario_id not in project.scenarios:
        known = ", ".join(sorted(project.scenarios)) or "none"
        raise ScenarioRunError(
            Problem(
                Severity.ERROR,
                "SCENARIO_UNKNOWN",
                f"Scenario '{scenario_id}' does not exist.",
                hint=f"Defined scenarios: {known}.",
            )
        )
    scenario = project.scenarios[scenario_id]
    adapter = environment_for(project, scenario)
    stage(control, "Orbit, eclipses and passes")
    try:
        env = adapter.compute(
            grid_for(scenario), sites_for(project, scenario), scenario.shadow_model
        )
    except EnvironmentInputError as exc:
        base = scenario.import_dir or ""
        raise ScenarioRunError(
            Problem(
                Severity.ERROR,
                "ENV_INPUT_INVALID",
                f"{exc}.",
                file=f"{base}/{exc.file}",
                line=exc.line,
                hint="See docs/ENVIRONMENT_FORMAT.md for the expected files.",
            )
        ) from None
    except MemoryError:
        raise ScenarioRunError(
            Problem(
                Severity.ERROR,
                "SCENARIO_TOO_LARGE",
                "The scenario needs more memory than is available.",
                file=f"scenarios/{scenario_id}.yaml",
                path="step_s",
                hint="Increase step_s or shorten duration_s.",
            )
        ) from None
    except OverflowError, ValueError:
        raise ScenarioRunError(
            Problem(
                Severity.ERROR,
                "ENV_PROPAGATION_FAILED",
                "The orbit cannot be computed for these dates (a value is out of range).",
                file=f"scenarios/{scenario_id}.yaml",
                path="start_utc",
                hint="Check the scenario start, the duration and the orbit; start times are "
                "limited to the years 1950 to 2100.",
            )
        ) from None
    except PropagationError as exc:
        raise ScenarioRunError(
            Problem(
                Severity.ERROR,
                "ENV_PROPAGATION_FAILED",
                f"{exc}.",
                file=f"orbits/{scenario.orbit}.yaml",
                hint="Check the orbit; very low or very eccentric orbits decay.",
            )
        ) from None
    checkpoint(control)
    notes = tuple(getattr(adapter, "notes", ()))
    problems: list[Problem] = []
    if scenario.environment_source == "elements" and scenario.orbit in project.orbits:
        age = orbit_age_problem(
            project.orbits[scenario.orbit], env.grid.start, scenario.orbit, scenario_id
        )
        if age is not None:
            problems.append(age)
    return ScenarioRun(
        scenario_id, scenario, env, build_timeline(scenario, env), notes, tuple(problems)
    )


FULL_HASH_BYTES = 16 * 1024 * 1024  # files up to this size are hashed whole
EDGE_HASH_BYTES = 1024 * 1024  # larger ones: their first and last megabyte, and the size


def import_fingerprint(path: Path) -> str:
    """What identifies the content of an imported file for the key. A file of up to 16 MiB is
    hashed whole, so an edit of any size is seen even when the size and the modification time
    stay the same (a coarse clock or a restored time); a larger file is identified by its size,
    its modification time and its first and last megabyte, since hashing hundreds of megabytes
    on every check would stall the window (D-212)."""
    info = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        if info.st_size <= FULL_HASH_BYTES:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
            return f"{info.st_size}:{digest.hexdigest()}"
        digest.update(handle.read(EDGE_HASH_BYTES))
        handle.seek(max(info.st_size - EDGE_HASH_BYTES, 0))
        digest.update(handle.read(EDGE_HASH_BYTES))
    return f"{info.st_size}:{info.st_mtime_ns}:{digest.hexdigest()}"


def environment_key(project: Project, scenario: Scenario) -> str:
    """Fingerprint of everything the environment depends on. Rules, segments, the default mode
    and the name only change the timeline, so they are not part of it. Equal keys allow reusing a
    computed environment."""
    parts: dict[str, object] = {
        "source": scenario.environment_source,
        "start_utc": scenario.start_utc,
        "duration_s": scenario.duration_s,
        "step_s": scenario.step_s,
        "shadow_model": scenario.shadow_model,
        "earth_model": scenario.earth_model,
        "sites": [
            [
                site_id,
                model_to_data(
                    (project.ground_stations | project.targets)[site_id], annotations=False
                ),
            ]
            for site_id in scenario.sites
            if site_id in project.ground_stations or site_id in project.targets
        ],
    }
    if scenario.environment_source == "elements" and scenario.orbit in project.orbits:
        parts["orbit"] = model_to_data(project.orbits[scenario.orbit], annotations=False)
    if scenario.environment_source == "spacemissionstudio" and scenario.import_dir:
        folder = resolve_inside(project.root, scenario.import_dir)
        files = sorted(folder.glob("*.csv")) if folder is not None and folder.is_dir() else []
        parts["import"] = [[p.name, import_fingerprint(p)] for p in files]
    text = json.dumps(parts, sort_keys=True, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def rebuild_timeline(run: ScenarioRun, scenario: Scenario) -> ScenarioRun:
    """The same environment with the timeline of an edited scenario (rules, segments, default)."""
    return ScenarioRun(
        run.scenario_id,
        scenario,
        run.env,
        build_timeline(scenario, run.env),
        run.notes,
        run.problems,
    )
