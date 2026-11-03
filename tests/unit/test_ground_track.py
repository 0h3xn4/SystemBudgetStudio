"""The ground track of a scenario (2.2.0, D-232): the sub-satellite point (geodetic latitude,
longitude, height above the WGS-84 ellipsoid) over the grid; the latitude range, the ascending
equator crossings and the shift between them; the series written as `<id>_groundtrack.csv`."""

from __future__ import annotations

import csv
import math
from pathlib import Path

import numpy as np
import pytest

from budget_core.environment import geometry as geo
from budget_core.environment.ground_track import (
    ecef_to_geodetic,
    equator_crossings,
    ground_track,
    ground_track_statistics,
)
from budget_core.io.project_loader import load_project
from budget_core.scenario.export import ground_track_csv, write_scenario_outputs
from budget_core.scenario.run import run_scenario
from budget_core.scenario.statistics import scenario_statistics

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


# ---- the inverse of the geodetic conversion ------------------------------------------------


@pytest.mark.parametrize(
    "lat,lon,alt",
    [
        (0.0, 0.0, 0.0),
        (45.0, 10.0, 550e3),
        (-62.5, -150.0, 800e3),
        (89.9, 179.0, 400e3),
        (-0.01, -179.9, 35e6),
    ],
)
def test_the_inverse_of_geodetic_to_ecef(lat: float, lon: float, alt: float) -> None:
    ecef = geo.geodetic_to_ecef(lat, lon, alt)[None, :]
    got_lat, got_lon, got_alt = ecef_to_geodetic(ecef)
    assert got_lat[0] == pytest.approx(lat, abs=1e-9)
    assert got_lon[0] == pytest.approx(lon, abs=1e-9)
    assert got_alt[0] == pytest.approx(alt, abs=1e-5)


def test_the_poles_and_the_origin_of_longitude_are_defined() -> None:
    lat, lon, alt = ecef_to_geodetic(np.array([[0.0, 0.0, 6_356_752.314245 + 100.0]]))
    assert lat[0] == pytest.approx(90.0) and alt[0] == pytest.approx(100.0, abs=1e-4)
    assert math.isfinite(lon[0])
    lat, _, alt = ecef_to_geodetic(np.array([[0.0, 0.0, -(6_356_752.314245 + 100.0)]]))
    assert lat[0] == pytest.approx(-90.0) and alt[0] == pytest.approx(100.0, abs=1e-4)


def test_longitude_is_east_positive_in_minus_180_to_180() -> None:
    _, lon, _ = ecef_to_geodetic(
        np.array([[0.0, 7e6, 0.0], [0.0, -7e6, 0.0], [-7e6, 1.0, 0.0], [-7e6, -1.0, 0.0]])
    )
    assert lon[0] == pytest.approx(90.0) and lon[1] == pytest.approx(-90.0)
    assert lon[2] == pytest.approx(180.0, abs=1e-4) and lon[3] == pytest.approx(-180.0, abs=1e-4)


# ---- a computed scenario --------------------------------------------------------------------


@pytest.fixture(scope="module")
def run():  # type: ignore[no-untyped-def]
    loaded = load_project(EXAMPLES / "microsat_250kg_eps")
    assert loaded.project is not None
    scenario_id = sorted(loaded.project.scenarios)[0]
    return run_scenario(loaded.project, scenario_id)


def test_the_track_has_one_point_per_grid_time_and_the_orbit_height(run) -> None:  # type: ignore[no-untyped-def]
    track = ground_track(run.env)
    assert track is not None
    n = len(run.env.grid.times_s)
    assert len(track.latitude_deg) == len(track.longitude_deg) == len(track.altitude_m) == n
    r = np.linalg.norm(run.env.position_m, axis=1)
    # the height above the ellipsoid is within the Earth's flattening of radius minus Re
    assert np.all(np.abs(track.altitude_m - (r - 6_378_137.0)) < 25e3)
    assert np.all(np.abs(track.latitude_deg) <= 90.0)
    assert np.all(np.abs(track.longitude_deg) <= 180.0)


def test_the_latitude_reaches_the_inclination(run) -> None:  # type: ignore[no-untyped-def]
    track = ground_track(run.env)
    assert track is not None
    pos, vel = run.env.position_m, run.env.velocity_m_s
    h = np.cross(pos[0], vel[0])
    inclination = math.degrees(math.acos(h[2] / np.linalg.norm(h)))
    expected_max = inclination if inclination <= 90.0 else 180.0 - inclination
    # geodetic latitude of a point at geocentric latitude i on the ellipsoid:
    # tan(phi) = tan(i) / (1 - e2)
    e2 = 0.00669437999014
    geodetic = math.degrees(math.atan(math.tan(math.radians(expected_max)) / (1.0 - e2)))
    assert track.latitude_deg.max() == pytest.approx(geodetic, abs=0.25)


def test_a_point_on_the_greenwich_axis_at_gmst_zero_has_longitude_zero() -> None:
    # TEME x axis and the Earth-fixed x axis coincide when GMST is zero
    ecef = geo.eci_to_ecef(np.array([[7e6, 0.0, 0.0]]), np.array([0.0]))
    _, lon, _ = ecef_to_geodetic(ecef)
    assert lon[0] == pytest.approx(0.0, abs=1e-9)
    # a quarter turn of the Earth later the same inertial point is 90 degrees west
    ecef = geo.eci_to_ecef(np.array([[7e6, 0.0, 0.0]]), np.array([math.pi / 2]))
    _, lon, _ = ecef_to_geodetic(ecef)
    assert lon[0] == pytest.approx(-90.0, abs=1e-9)


# ---- equator crossings and the shift ---------------------------------------------------------


def test_equator_crossings_are_interpolated() -> None:
    t = np.array([0.0, 10.0, 20.0, 30.0, 40.0])
    lat = np.array([-2.0, 2.0, 4.0, -4.0, 4.0])
    lon = np.array([10.0, 12.0, 14.0, 16.0, 18.0])
    nodes = equator_crossings(t, lat, lon)
    assert [n.ascending for n in nodes] == [True, False, True]
    assert nodes[0].time_s == pytest.approx(5.0) and nodes[0].longitude_deg == pytest.approx(11.0)
    assert nodes[1].time_s == pytest.approx(22.5 + 0.0, abs=2.6)  # between 20 and 30
    assert nodes[2].time_s == pytest.approx(35.0)


def test_the_longitude_of_a_crossing_is_interpolated_across_the_date_line() -> None:
    t = np.array([0.0, 10.0])
    lat = np.array([-1.0, 1.0])
    lon = np.array([179.0, -179.0])
    (node,) = equator_crossings(t, lat, lon)
    assert abs(abs(node.longitude_deg) - 180.0) < 1e-9


def test_the_shift_between_ascending_nodes_follows_the_earth_rotation(run) -> None:  # type: ignore[no-untyped-def]
    track = ground_track(run.env)
    assert track is not None
    stats = ground_track_statistics(run.env.grid.times_s, track)
    assert stats.ascending_nodes >= 2 and stats.mean_node_shift_deg is not None
    # the node moves west by (earth rotation - node drift) x one revolution; the shift is
    # negative (west) and within a few degrees of -360 * T / 86164 for the nodal period T
    shift = stats.mean_node_shift_deg
    assert -30.0 < shift < -15.0, shift  # a low orbit: about 24 degrees per revolution
    period_s = stats.mean_node_spacing_s
    assert period_s is not None
    omega = 360.0 / 86164.0905  # deg/s
    assert shift == pytest.approx(-omega * period_s, abs=0.3)


def test_statistics_carry_the_latitude_range(run) -> None:  # type: ignore[no-untyped-def]
    stats = scenario_statistics(run.env)
    gt = stats.ground_track
    assert gt is not None
    data = stats.to_dict()["ground_track"]
    assert data["max_latitude_deg"] == pytest.approx(gt.max_latitude_deg, abs=1e-3)
    assert data["min_latitude_deg"] < 0.0 < data["max_latitude_deg"]


# ---- the file --------------------------------------------------------------------------------


def test_the_ground_track_file_has_the_columns_and_valid_values(run) -> None:  # type: ignore[no-untyped-def]
    text = ground_track_csv(run)
    assert text is not None
    rows = list(csv.reader(text.splitlines()))
    assert rows[0] == ["time_s", "utc", "latitude_deg", "longitude_deg", "altitude_m"]
    assert len(rows) > 10
    assert all(-90.0 <= float(r[2]) <= 90.0 and -180.0 <= float(r[3]) <= 180.0 for r in rows[1:])
    # one row every GROUND_TRACK_CSV_SAMPLE_S or every step if that is longer; the last time too
    assert float(rows[-1][0]) == pytest.approx(run.env.grid.times_s[-1], abs=1e-3)


def test_the_outputs_list_the_file_and_the_json_has_the_statistics(tmp_path: Path) -> None:
    import json

    from budget_core.provenance import make_provenance

    loaded = load_project(EXAMPLES / "microsat_250kg_eps")
    assert loaded.project is not None
    scenario_id = sorted(loaded.project.scenarios)[0]
    run = run_scenario(loaded.project, scenario_id)
    files = write_scenario_outputs(
        run, make_provenance(loaded.project, scenario=scenario_id), tmp_path
    )
    assert any(p.name.endswith("_groundtrack.csv") for p in files)
    data = json.loads(next(p for p in files if p.name.endswith("_environment.json")).read_text())
    assert set(data["statistics"]["ground_track"]) >= {
        "min_latitude_deg",
        "max_latitude_deg",
        "ascending_nodes",
    }
