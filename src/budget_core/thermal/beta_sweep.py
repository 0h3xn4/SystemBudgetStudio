"""Node temperatures against the beta angle (2.7.0, D-250).

The steady-state multi-node model of the project (`static_thermal`) is solved for a range of beta
angles. For every surface that gives its `normal_lvlh`, the solar view ratio of the chosen case is
taken from the beta angle instead of being typed: the orbit-average solar exposure of the face
(`mode="average"`, orbit-average heat loads) or its exposure at the orbit angle of the largest total
absorbed sunlight (`mode="peak"`, one instant, steady state at that instant). Everything else is
the project's own: the other surfaces keep their typed solar view, every surface keeps its typed
Earth view and albedo, and the case chooses the dissipation, the fluxes and the limits.

Circular orbit, nadir pointing, flat faces, no thermal capacity (DEVIATIONS DV-T4, DV-T5). Nothing
is invented: a surface with a normal but no `earth_view_ratio` for the case is reported as a
placeholder by the solver, like any other missing input.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Any, Literal

from budget_core.control import RunControl, checkpoint
from budget_core.environment.constants import DEFAULT_EARTH_MODEL, EARTH_MODELS
from budget_core.model import Project, Sourced
from budget_core.model.thermal import Exposure, Surface
from budget_core.problems import Problem
from budget_core.thermal.beta import face_exposure, peak_instant, sunlit_fraction
from budget_core.thermal.static_thermal import (
    CaseThermal,
    NodeTemperature,
    static_thermal_budget,
)

Mode = Literal["average", "peak"]

# a unit beyond a limit is a result at one beta angle (the table counts them), not a finding of
# the sweep: the solver's findings for the first angle would be read as the finding of all
BETA_DEPENDENT_FINDINGS = frozenset({"THERMAL_LIMIT_EXCEEDED", "THERMAL_MARGIN_INSUFFICIENT"})

SOURCE = "Computed from the beta angle, the orbit and the surface normal (TH-BETA-SUN)"


class BetaSweepError(ValueError):
    """The request cannot be run; the message says why in words (no values from files)."""


@dataclass(frozen=True)
class BetaPoint:
    beta_deg: float
    sunlit_fraction: float
    u_deg: float | None  # the orbit angle from noon of the peak instant (None: orbit average)
    case: CaseThermal  # the solver's result at this beta angle
    solar_view: dict[str, float]  # the solar view ratio used for each surface with a normal


@dataclass(frozen=True)
class BetaSweep:
    case: str
    mode: Mode
    earth_radius_m: float
    orbit_radius_m: float
    surfaces_from_beta: tuple[str, ...]
    surfaces_typed: tuple[str, ...]
    points: tuple[BetaPoint, ...]
    problems: tuple[Problem, ...]

    @property
    def altitude_m(self) -> float:
        return self.orbit_radius_m - self.earth_radius_m


def _typed(item: Sourced | None) -> float | None:
    return None if item is None or item.is_placeholder else item.value


def beta_range(beta_min: float, beta_max: float, step: float) -> list[float]:
    """The angles from `beta_min` to `beta_max` in steps of `step`, the last one included."""
    if step <= 0.0:
        raise BetaSweepError("The beta step is above 0.")
    if not -90.0 <= beta_min <= beta_max <= 90.0:
        raise BetaSweepError("The beta angles are between -90 and 90 degrees, lowest first.")
    count = int(math.floor((beta_max - beta_min) / step + 1e-9))
    values = [beta_min + i * step for i in range(count + 1)]
    if values[-1] < beta_max - 1e-9:
        values.append(beta_max)
    return values


def thermal_beta_sweep(
    project: Project,
    case: str,
    betas: Sequence[float],
    *,
    mode: Mode,
    earth_radius_m: float,
    orbit_radius_m: float,
    control: RunControl | None = None,
) -> BetaSweep:
    """The node temperatures of `case` at each beta angle. The project must be valid. With a
    `control` the window can stop it between two angles (nothing is returned then)."""
    model = project.config.thermal_model
    env = project.config.thermal_environment
    if model is None or env is None:
        raise BetaSweepError("The project has no thermal model or no thermal environment.")
    if case not in env.cases:
        raise BetaSweepError("The thermal environment has no such case.")
    if not betas:
        raise BetaSweepError("Give at least one beta angle.")
    if orbit_radius_m <= earth_radius_m:
        raise BetaSweepError("The orbit is not above the surface of the Earth.")
    with_normal = [s for s in model.surfaces if s.normal_lvlh is not None]
    if not with_normal:
        raise BetaSweepError(
            "No surface gives its normal_lvlh in config/thermal_model.yaml, so the beta angle "
            "has nothing to act on."
        )
    names = tuple(s.name for s in with_normal)
    typed = tuple(s.name for s in model.surfaces if s.normal_lvlh is None)

    one_case = env.model_copy(update={"cases": {case: env.cases[case]}})
    points: list[BetaPoint] = []
    problems: list[Problem] = []
    for beta in betas:
        checkpoint(control)
        views, u_deg = _solar_views(
            with_normal, beta, mode, earth_radius_m, orbit_radius_m, problems
        )
        surfaces = [_with_view(s, case, views.get(id(s))) for s in model.surfaces]
        trial = replace(
            project,
            config=replace(
                project.config,
                thermal_model=model.model_copy(update={"surfaces": surfaces}),
                thermal_environment=one_case,
            ),
        )
        result = static_thermal_budget(trial)
        if not points:
            problems.extend(p for p in result.problems if p.code not in BETA_DEPENDENT_FINDINGS)
        points.append(
            BetaPoint(
                beta,
                sunlit_fraction(beta, earth_radius_m, orbit_radius_m),
                u_deg,
                result.cases[0],
                {s.name: views[id(s)] for s in with_normal if id(s) in views},
            )
        )
    return BetaSweep(
        case,
        mode,
        earth_radius_m,
        orbit_radius_m,
        names,
        typed,
        tuple(points),
        tuple(_unique(problems)),
    )


def _solar_views(
    surfaces: list[Surface],
    beta: float,
    mode: Mode,
    earth_radius_m: float,
    orbit_radius_m: float,
    problems: list[Problem],
) -> tuple[dict[int, float], float | None]:
    """The solar view ratio of each surface with a normal, keyed by `id(surface)`."""
    if mode == "average":
        return (
            {
                id(s): face_exposure(
                    s.normal_lvlh or (0, 0, 0), beta, earth_radius_m, orbit_radius_m
                ).average
                for s in surfaces
            },
            None,
        )
    weights: list[float] = []
    for s in surfaces:
        alpha = _typed(s.absorptivity_ratio)
        if alpha is None:
            raise BetaSweepError(
                "The peak needs the absorptivity of every surface that gives its normal_lvlh; "
                "one is a placeholder."
            )
        weights.append(alpha * s.area_m2)
    peak = peak_instant(
        [s.normal_lvlh or (0, 0, 0) for s in surfaces],
        weights,
        beta,
        earth_radius_m,
        orbit_radius_m,
    )
    return (
        {id(s): e for s, e in zip(surfaces, peak.exposures, strict=True)},
        math.degrees(peak.u_rad),
    )


def _with_view(surface: Surface, case: str, solar_view: float | None) -> Surface:
    """The surface with the solar view of `case` taken from the beta angle (when it has a
    normal); the Earth view stays the typed one, a placeholder when the surface has none."""
    if solar_view is None:
        return surface
    typed = surface.exposure.get(case)
    earth = typed.earth_view_ratio if typed is not None else Sourced(value=None, source="TBD")
    exposure = Exposure(
        solar_view_ratio=Sourced(value=solar_view, source=SOURCE, status="estimate"),
        earth_view_ratio=earth,
    )
    return surface.model_copy(update={"exposure": {**surface.exposure, case: exposure}})


def _unique(items: list[Problem]) -> list[Problem]:
    seen: set[tuple[str, str | None, str, str]] = set()
    out: list[Problem] = []
    for p in items:
        key = (p.code, p.file, p.path, p.message)
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def orbit_of_run(run: Any) -> tuple[float, float]:
    """(Earth radius, orbit radius) in metres of a scenario run: the Earth model of the run and
    the mean radius of its propagated positions (the orbit is taken as a circle of that radius)."""
    import numpy as np

    positions = np.asarray(run.env.position_m)
    if len(positions) == 0:
        raise BetaSweepError("The scenario has no orbit positions.")
    model_id = run.env.earth_model if run.env.earth_model in EARTH_MODELS else DEFAULT_EARTH_MODEL
    return EARTH_MODELS[model_id].radius_m, float(np.mean(np.linalg.norm(positions, axis=1)))


def node_temperatures(point: BetaPoint) -> dict[str, float]:
    return {n.node: n.temperature_k for n in point.case.nodes}


__all__ = [
    "BetaPoint",
    "BetaSweep",
    "BetaSweepError",
    "NodeTemperature",
    "beta_range",
    "node_temperatures",
    "orbit_of_run",
    "thermal_beta_sweep",
]
