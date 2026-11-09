# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""LTAN as an orbit input (2.3.0, D-236): the elements may give the local time of the ascending node
(`ltan_h`, mean solar time) instead of the RAAN; the RAAN is then derived at the epoch. Exactly one
of the two is given. A change of epoch keeps the local time, so the RAAN moves with it."""

from __future__ import annotations

import math
from datetime import UTC, datetime

import numpy as np
import pytest
from pydantic import ValidationError

from budget_core.environment.elements import build_satrec, derived_raan_deg
from budget_core.io.migrations import DEFAULT_REGISTRY
from budget_core.model import Orbit
from budget_core.model.environment import Elements
from budget_core.orbit_design import mean_solar_time_of_node_h, raan_from_ltan_deg


def elements(**over: object) -> dict[str, object]:
    base: dict[str, object] = {
        "epoch_utc": "2026-06-01T00:00:00Z",
        "semi_major_axis_m": 6_378_137.0 + 650_000.0,
        "eccentricity_ratio": 0.0011,
        "inclination_deg": 97.9,
        "arg_perigee_deg": 90.0,
        "mean_anomaly_deg": 0.0,
    }
    base.update(over)
    return base


def orbit(**over: object) -> Orbit:
    return Orbit.model_validate({"name": "SSO", "elements": elements(**over)})


def test_exactly_one_of_raan_and_ltan_is_given() -> None:
    assert orbit(ltan_h=10.5).elements.ltan_h == 10.5  # type: ignore[union-attr]
    assert orbit(raan_deg=120.0).elements.raan_deg == 120.0  # type: ignore[union-attr]
    with pytest.raises(ValidationError):
        orbit(raan_deg=120.0, ltan_h=10.5)
    with pytest.raises(ValidationError):
        orbit()


def test_the_local_time_is_in_hours_below_24() -> None:
    for bad in (-0.1, 24.0, 30.0):
        with pytest.raises(ValidationError):
            orbit(ltan_h=bad)


def test_the_derived_raan_has_the_asked_local_time() -> None:
    el = orbit(ltan_h=10.5).elements
    assert el is not None
    raan = derived_raan_deg(el)
    epoch = datetime(2026, 6, 1, tzinfo=UTC)
    assert mean_solar_time_of_node_h(raan, epoch) == pytest.approx(10.5, abs=1e-9)
    assert raan == pytest.approx(raan_from_ltan_deg(10.5, epoch), abs=1e-12)


def test_an_explicit_raan_is_returned_as_it_is() -> None:
    el = orbit(raan_deg=123.4).elements
    assert el is not None and derived_raan_deg(el) == 123.4


def test_a_later_epoch_with_the_same_local_time_has_another_raan() -> None:
    a = orbit(ltan_h=10.5, epoch_utc="2026-03-01T00:00:00Z").elements
    b = orbit(ltan_h=10.5, epoch_utc="2026-09-01T00:00:00Z").elements
    assert a is not None and b is not None
    assert abs(derived_raan_deg(a) - derived_raan_deg(b)) > 1.0  # the Sun moved
    for el, month in ((a, 3), (b, 9)):
        epoch = datetime(2026, month, 1, tzinfo=UTC)
        assert mean_solar_time_of_node_h(derived_raan_deg(el), epoch) == pytest.approx(
            10.5, abs=1e-9
        )


def test_the_propagated_orbit_uses_the_derived_raan() -> None:
    by_time = build_satrec(orbit(ltan_h=10.5))
    el = orbit(ltan_h=10.5).elements
    assert el is not None
    by_raan = build_satrec(orbit(raan_deg=derived_raan_deg(el)))
    assert by_time.nodeo == pytest.approx(by_raan.nodeo, abs=1e-12)
    assert math.degrees(by_time.nodeo) == pytest.approx(derived_raan_deg(el), abs=1e-9)
    err, r1, v1 = by_time.sgp4(by_time.jdsatepoch, 0.1)
    err2, r2, v2 = by_raan.sgp4(by_raan.jdsatepoch, 0.1)
    assert err == err2 == 0 and np.allclose(r1, r2) and np.allclose(v1, v2)


def test_the_file_round_trips_and_older_orbits_migrate() -> None:
    again = Elements.model_validate(Elements.model_validate(elements(ltan_h=6.0)).model_dump())
    assert again.ltan_h == 6.0 and again.raan_deg is None
    data = {"schema_version": 3, "kind": "orbit", "name": "x"}
    out, problem = DEFAULT_REGISTRY.migrate("orbit", data)
    assert problem is not None and problem.code == "FILE_MIGRATED" and out["schema_version"] == 4


def test_a_scenario_on_a_local_time_runs_and_says_which_raan_it_derived() -> None:
    from dataclasses import replace
    from pathlib import Path

    from budget_core.io.project_loader import load_project
    from budget_core.scenario.run import run_scenario

    loaded = load_project(Path(__file__).resolve().parents[2] / "examples" / "microsat_250kg_eps")
    project = loaded.project
    assert project is not None
    base = project.orbits["leo"]
    assert base.elements is not None
    ltan = base.model_copy(
        update={
            "elements": Elements.model_validate(
                {**base.elements.model_dump(), "raan_deg": None, "ltan_h": 10.5}
            )
        }
    )
    short = project.scenarios["one_day"].model_copy(update={"duration_s": 7200.0})
    changed = replace(project, orbits={"leo": ltan}, scenarios={"one_day": short})
    run = run_scenario(changed, "one_day")
    assert any("derived from the local time" in n for n in run.notes)
    assert run.env.eclipses is not None
