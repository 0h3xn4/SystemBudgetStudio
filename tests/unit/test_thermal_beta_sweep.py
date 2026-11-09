# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""D-250: the node temperatures against the beta angle, with the existing steady-state model."""

from __future__ import annotations

from pathlib import Path

import pytest

from budget_core.environment.constants import EARTH_MODELS
from budget_core.io.project_loader import load_project
from budget_core.model import Project, Sourced
from budget_core.model.thermal import Exposure
from budget_core.thermal.beta import face_exposure, peak_instant
from budget_core.thermal.beta_sweep import (
    BetaSweepError,
    beta_range,
    node_temperatures,
    thermal_beta_sweep,
)
from budget_core.thermal.static_thermal import static_thermal_budget

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
RE = EARTH_MODELS["wgs84"].radius_m
R550 = RE + 550e3


@pytest.fixture(scope="module")
def project() -> Project:
    loaded = load_project(EXAMPLES / "microsat_250kg_eps")
    assert loaded.project is not None
    return loaded.project


def _sweep(project: Project, betas: list[float], mode: str = "average"):  # type: ignore[no-untyped-def]
    return thermal_beta_sweep(
        project,
        "hot",
        betas,
        mode=mode,
        earth_radius_m=RE,
        orbit_radius_m=R550,  # type: ignore[arg-type]
    )


def test_the_range_includes_both_ends_and_refuses_nonsense() -> None:
    assert beta_range(0.0, 90.0, 30.0) == [0.0, 30.0, 60.0, 90.0]
    assert beta_range(-10.0, 25.0, 10.0) == [-10.0, 0.0, 10.0, 20.0, 25.0]
    for bad in ((0.0, 90.0, 0.0), (50.0, 10.0, 5.0), (-100.0, 10.0, 5.0)):
        with pytest.raises(BetaSweepError):
            beta_range(*bad)


def test_a_beta_that_gives_the_typed_ratio_gives_the_typed_temperatures(project: Project) -> None:
    """The limiting case: type, for every surface, the solar view the geometry gives at 40
    degrees; the sweep at 40 degrees must equal the existing static budget exactly."""
    model = project.config.thermal_model
    assert model is not None
    surfaces = []
    for s in model.surfaces:
        assert s.normal_lvlh is not None
        f = face_exposure(s.normal_lvlh, 40.0, RE, R550).average
        typed = s.exposure["hot"]
        exposure = {
            **s.exposure,
            "hot": Exposure(
                solar_view_ratio=Sourced(value=f, source="typed for the test"),
                earth_view_ratio=typed.earth_view_ratio,
            ),
        }
        surfaces.append(s.model_copy(update={"exposure": exposure}))
    from dataclasses import replace

    typed_project = replace(
        project,
        config=replace(
            project.config, thermal_model=model.model_copy(update={"surfaces": surfaces})
        ),
    )
    static = next(c for c in static_thermal_budget(typed_project).cases if c.case == "hot")
    sweep = _sweep(project, [40.0])
    assert sweep.points[0].case.complete
    got, want = node_temperatures(sweep.points[0]), {n.node: n.temperature_k for n in static.nodes}
    assert got.keys() == want.keys()
    for node, kelvin in want.items():
        assert got[node] == pytest.approx(kelvin, abs=1e-9)


def test_a_surface_without_a_normal_keeps_its_typed_ratio(project: Project) -> None:
    model = project.config.thermal_model
    assert model is not None
    surfaces = list(model.surfaces)
    surfaces[0] = surfaces[0].model_copy(update={"normal_lvlh": None})
    from dataclasses import replace

    changed = replace(
        project,
        config=replace(
            project.config, thermal_model=model.model_copy(update={"surfaces": surfaces})
        ),
    )
    sweep = _sweep(changed, [0.0, 60.0])
    assert sweep.surfaces_typed == (surfaces[0].name,)
    assert surfaces[0].name not in sweep.points[0].solar_view
    assert surfaces[1].name in sweep.points[0].solar_view


def test_the_average_has_the_solar_view_of_the_orbit_average(project: Project) -> None:
    model = project.config.thermal_model
    assert model is not None
    point = _sweep(project, [30.0]).points[0]
    for s in model.surfaces:
        assert s.normal_lvlh is not None
        assert point.solar_view[s.name] == pytest.approx(
            face_exposure(s.normal_lvlh, 30.0, RE, R550).average
        )
    assert point.u_deg is None


def test_the_peak_is_hotter_than_the_average_and_uses_the_best_instant(project: Project) -> None:
    model = project.config.thermal_model
    assert model is not None
    average = _sweep(project, [0.0, 30.0], "average").points
    peak = _sweep(project, [0.0, 30.0], "peak").points
    for a, p in zip(average, peak, strict=True):
        assert p.u_deg is not None
        # the instant is the one of the most sunlight absorbed in total (a single node can be
        # cooler there than on average: its face may look away at that instant)
        assert sum(n.absorbed_w for n in p.case.nodes) >= sum(n.absorbed_w for n in a.case.nodes)
        for s in model.surfaces:
            assert p.solar_view[s.name] >= 0.0
    normals = [s.normal_lvlh for s in model.surfaces]
    weights = [s.absorptivity_ratio.value * s.area_m2 for s in model.surfaces]  # type: ignore[operator]
    best = peak_instant(normals, weights, 0.0, RE, R550)  # type: ignore[arg-type]
    assert peak[0].solar_view[model.surfaces[0].name] == pytest.approx(best.exposures[0])


def test_with_the_sun_on_the_orbit_normal_the_average_and_the_peak_agree(project: Project) -> None:
    a, p = _sweep(project, [90.0], "average").points[0], _sweep(project, [90.0], "peak").points[0]
    for node, kelvin in node_temperatures(a).items():
        assert node_temperatures(p)[node] == pytest.approx(kelvin, abs=1e-9)


def test_requests_that_cannot_run_are_refused(project: Project) -> None:
    with pytest.raises(BetaSweepError):
        thermal_beta_sweep(
            project, "nope", [0.0], mode="average", earth_radius_m=RE, orbit_radius_m=R550
        )
    with pytest.raises(BetaSweepError):
        thermal_beta_sweep(
            project, "hot", [], mode="average", earth_radius_m=RE, orbit_radius_m=R550
        )
    with pytest.raises(BetaSweepError):
        thermal_beta_sweep(
            project, "hot", [0.0], mode="average", earth_radius_m=RE, orbit_radius_m=RE
        )
    model = project.config.thermal_model
    assert model is not None
    from dataclasses import replace

    none = replace(
        project,
        config=replace(
            project.config,
            thermal_model=model.model_copy(
                update={
                    "surfaces": [s.model_copy(update={"normal_lvlh": None}) for s in model.surfaces]
                }
            ),
        ),
    )
    with pytest.raises(BetaSweepError, match="normal_lvlh"):
        thermal_beta_sweep(
            none, "hot", [0.0], mode="average", earth_radius_m=RE, orbit_radius_m=R550
        )


def test_a_missing_earth_view_is_a_placeholder_the_solver_reports(project: Project) -> None:
    model = project.config.thermal_model
    assert model is not None
    surfaces = [s.model_copy(update={"exposure": {}}) for s in model.surfaces]
    from dataclasses import replace

    changed = replace(
        project,
        config=replace(
            project.config, thermal_model=model.model_copy(update={"surfaces": surfaces})
        ),
    )
    sweep = _sweep(changed, [30.0])
    assert not sweep.points[0].case.complete  # nothing is invented
    assert any(p.code == "RESULT_INCOMPLETE" for p in sweep.problems)
