# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""The beta angle of a scenario (2.2.0, D-227): the angle between the Sun direction and the orbit
plane, over the grid; its minimum, mean and maximum; the critical angle above which the orbit has
no eclipse; the series written as `<id>_beta.csv`."""

from __future__ import annotations

import csv
import math
import shutil
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest

from budget_core.environment.beta import beta_angle_deg, beta_statistics, critical_beta_deg
from budget_core.environment.constants import EARTH_MODELS
from budget_core.io.project_loader import load_project, model_to_data
from budget_core.orbit_design import design_sun_synchronous
from budget_core.scenario.export import write_scenario_outputs
from budget_core.scenario.run import run_scenario
from budget_core.scenario.statistics import scenario_statistics

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
RE = EARTH_MODELS["wgs84"].radius_m


# ---- the angle ------------------------------------------------------------------------------


def test_the_sun_in_the_orbit_plane_is_beta_zero_and_on_the_normal_is_ninety() -> None:
    position = np.array([[7.0e6, 0.0, 0.0]])
    velocity = np.array([[0.0, 7.5e3, 0.0]])  # the normal is +z
    assert beta_angle_deg(position, velocity, np.array([[1.0, 0.0, 0.0]]))[0] == pytest.approx(0.0)
    assert beta_angle_deg(position, velocity, np.array([[0.0, 1.0, 0.0]]))[0] == pytest.approx(0.0)
    assert beta_angle_deg(position, velocity, np.array([[0.0, 0.0, 1.0]]))[0] == pytest.approx(90.0)
    assert beta_angle_deg(position, velocity, np.array([[0.0, 0.0, -1.0]]))[0] == pytest.approx(
        -90.0
    )


def test_the_sign_follows_the_orbit_normal() -> None:
    position = np.array([[7.0e6, 0.0, 0.0]])
    sun = np.array([[0.0, 0.0, 1.0]])
    prograde = beta_angle_deg(position, np.array([[0.0, 7.5e3, 0.0]]), sun)[0]
    retrograde = beta_angle_deg(position, np.array([[0.0, -7.5e3, 0.0]]), sun)[0]
    assert prograde == pytest.approx(90.0) and retrograde == pytest.approx(-90.0)


def test_a_known_angle() -> None:
    sun = np.array([[math.cos(math.radians(30.0)), 0.0, math.sin(math.radians(30.0))]])
    got = beta_angle_deg(np.array([[7.0e6, 0.0, 0.0]]), np.array([[0.0, 7.5e3, 0.0]]), sun)
    assert got[0] == pytest.approx(30.0)


def test_the_critical_angle_of_a_circular_orbit() -> None:
    assert critical_beta_deg(RE + 700e3, RE) == pytest.approx(
        math.degrees(math.asin(RE / (RE + 700e3))), abs=1e-9
    )
    assert critical_beta_deg(RE + 700e3, RE) == pytest.approx(64.3, abs=0.1)
    assert critical_beta_deg(RE + 35786e3, RE) == pytest.approx(8.7, abs=0.1)  # geostationary


# ---- against the closed form and the eclipses of the scenario -------------------------------


def _scenario(tmp_path: Path, ltan_h: float, epoch: str, days: float = 3.0) -> Path:
    """A copy of the 250 kg example whose orbit is a sun-synchronous design at a local time."""
    root = tmp_path / "p"
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", root)
    when = datetime.fromisoformat(epoch.replace("Z", "+00:00")).astimezone(UTC)
    design = design_sun_synchronous(altitude_m=700e3, ltan_h=ltan_h, epoch=when)
    orbit_file = next((root / "orbits").glob("*.yaml"))
    text = (
        "schema_version: 2\nkind: orbit\nname: Designed orbit\nelements:\n"
        f"  epoch_utc: '{epoch}'\n  semi_major_axis_m: {design.semi_major_axis_m}\n"
        f"  eccentricity_ratio: 0.0\n  inclination_deg: {design.inclination_deg}\n"
        f"  raan_deg: {design.raan_deg}\n  arg_perigee_deg: 0.0\n  mean_anomaly_deg: 0.0\n"
    )
    orbit_file.write_text(text, encoding="utf-8", newline="\n")
    scenario_file = next((root / "scenarios").glob("*.yaml"))
    lines = scenario_file.read_text(encoding="utf-8").splitlines()
    out = []
    for line in lines:
        if line.startswith("start_utc"):
            line = f"start_utc: '{epoch}'"
        elif line.startswith("duration_s"):
            line = f"duration_s: {days * 86400.0}"
        out.append(line)
    scenario_file.write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")
    return root


def _run(root: Path):  # type: ignore[no-untyped-def]
    loaded = load_project(root)
    assert loaded.project is not None
    scenario_id = next(iter(loaded.project.scenarios))
    return loaded.project, scenario_id, run_scenario(loaded.project, scenario_id)


def test_the_series_agrees_with_the_closed_form_of_the_elements(tmp_path: Path) -> None:
    """sin(beta) = Sun . h with h = (sin RAAN sin i, -cos RAAN sin i, cos i): the plane of the
    elements and the Sun direction, with no velocity in it."""
    root = _scenario(tmp_path, 10.5, "2026-06-01T00:00:00Z", days=1.0)
    project, scenario_id, run = _run(root)
    orbit = next(iter(project.orbits.values()))
    el = orbit.elements
    assert el is not None
    inc = math.radians(el.inclination_deg)
    # the node of a sun-synchronous orbit moves 0.9856 deg a day, which the plane has to follow
    node_rate = math.radians(0.9856474) / 86400.0
    raan = math.radians(el.raan_deg) + node_rate * run.env.grid.times_s
    normal = np.column_stack(
        [
            np.sin(raan) * math.sin(inc),
            -np.cos(raan) * math.sin(inc),
            np.full_like(raan, math.cos(inc)),
        ]
    )
    expected = np.degrees(np.arcsin(np.sum(run.env.sun_direction * normal, axis=1)))
    got = beta_angle_deg(run.env.position_m, run.env.velocity_m_s, run.env.sun_direction)
    # SGP4's osculating plane differs from the mean plane by short-period terms only
    assert np.max(np.abs(got - expected)) < 0.05


def test_a_dawn_dusk_orbit_has_no_eclipse_and_a_noon_orbit_has_many(tmp_path: Path) -> None:
    dawn_dusk = _run(_scenario(tmp_path / "a", 6.0, "2026-06-21T00:00:00Z", days=2.0))[2]
    noon = _run(_scenario(tmp_path / "b", 12.0, "2026-03-20T00:00:00Z", days=2.0))[2]
    s_dd, s_noon = scenario_statistics(dawn_dusk.env), scenario_statistics(noon.env)
    assert s_dd.beta is not None and s_noon.beta is not None
    # physical consistency: above the critical angle the orbit never enters the shadow
    assert min(abs(s_dd.beta.min_deg), abs(s_dd.beta.max_deg)) > s_dd.beta.critical_deg
    assert s_dd.eclipses.durations.count == 0
    assert max(abs(s_noon.beta.min_deg), abs(s_noon.beta.max_deg)) < s_noon.beta.critical_deg
    assert s_noon.eclipses.durations.count > 20


def test_the_statistics_of_a_series() -> None:
    beta = np.array([-10.0, 0.0, 20.0, 30.0])
    s = beta_statistics(beta, mean_radius_m=RE + 700e3, earth_radius_m=RE)
    assert (s.min_deg, s.max_deg) == (-10.0, 30.0) and s.mean_deg == pytest.approx(10.0)
    assert s.critical_deg == pytest.approx(64.3, abs=0.1)
    assert s.to_dict()["critical_deg"] == pytest.approx(64.3, abs=0.1)


def test_an_environment_without_a_velocity_gets_it_from_the_positions() -> None:
    """An imported environment has positions only; the plane is then that of the positions."""
    t = np.linspace(0.0, 6000.0, 61)
    w = 2.0 * math.pi / 5800.0
    position = 7.0e6 * np.column_stack([np.cos(w * t), np.sin(w * t), np.zeros_like(t)])
    sun = np.tile([0.0, 0.0, 1.0], (len(t), 1))
    got = beta_angle_deg(position, None, sun, times_s=t)
    assert np.allclose(got, 90.0, atol=1e-6)


# ---- the outputs ----------------------------------------------------------------------------


def test_the_series_is_written_as_a_csv_with_the_provenance(tmp_path: Path) -> None:
    root = _scenario(tmp_path, 10.5, "2026-06-01T00:00:00Z", days=1.0)
    project, scenario_id, run = _run(root)
    from budget_core.provenance import make_provenance

    files = write_scenario_outputs(
        run, make_provenance(project, scenario=scenario_id), tmp_path / "out"
    )
    beta_file = next(p for p in files if p.name.endswith("_beta.csv"))
    rows = list(csv.reader(beta_file.read_text(encoding="utf-8").splitlines()))
    assert rows[0] == ["time_s", "utc", "beta_deg"]
    data = rows[1:]
    # at most one sample every 10 minutes whatever the step, the end included
    assert 140 <= len(data) <= 146 and float(data[0][0]) == 0.0
    assert float(data[-1][0]) == pytest.approx(86400.0)
    assert all(-90.0 <= float(r[2]) <= 90.0 for r in data)
    assert any(p.name.endswith("_provenance.csv") for p in files)  # the provenance is its own file


def test_the_json_has_the_beta_statistics(tmp_path: Path) -> None:
    import json

    root = _scenario(tmp_path, 10.5, "2026-06-01T00:00:00Z", days=1.0)
    project, scenario_id, run = _run(root)
    from budget_core.provenance import make_provenance

    files = write_scenario_outputs(
        run, make_provenance(project, scenario=scenario_id), tmp_path / "out"
    )
    data = json.loads(next(p for p in files if p.name.endswith("_environment.json")).read_text())
    beta = data["statistics"]["beta"]
    assert set(beta) >= {"min_deg", "mean_deg", "max_deg", "critical_deg"}
    assert beta["min_deg"] <= beta["mean_deg"] <= beta["max_deg"]


def test_model_to_data_is_untouched_by_the_feature() -> None:
    # nothing of the beta angle is stored in a project: the orbit file has no new field
    loaded = load_project(EXAMPLES / "microsat_250kg_eps")
    assert loaded.project is not None
    orbit = next(iter(loaded.project.orbits.values()))
    assert "beta" not in str(model_to_data(orbit)).lower()


# ---- the plot -------------------------------------------------------------------------------


def test_the_plot_has_the_series_and_the_critical_angle(tmp_path: Path) -> None:
    from budget_core.plots.beta import beta_plot

    root = _scenario(tmp_path, 10.5, "2026-06-01T00:00:00Z", days=1.0)
    _, _, run = _run(root)
    spec = beta_plot(run.env)
    assert spec is not None and len(spec.panels) == 1
    panel = spec.panels[0]
    assert panel.y_label == "deg" and len(panel.series) == 1
    assert len(panel.series[0].x) == len(run.env.grid.times_s)
    critical = scenario_statistics(run.env).beta.critical_deg  # type: ignore[union-attr]
    assert sorted(line.y for line in panel.hlines) == pytest.approx([-critical, critical])
    assert (panel.y_min, panel.y_max) == (-90.0, 90.0)


def test_there_is_no_plot_without_an_orbit_plane() -> None:
    from budget_core.plots.beta import beta_plot

    class _Env:
        position_m = np.empty((0, 3))

    assert beta_plot(_Env()) is None  # type: ignore[arg-type]
