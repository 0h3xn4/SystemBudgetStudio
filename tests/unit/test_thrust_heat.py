# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""The heat of a burn in the thermal cases (2.3.0): a propulsion system that names a thermal node
and a thrusting heat puts that heat into the node in every thermal case whose spacecraft mode is the
mode a manoeuvre of the system holds during its burn."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from budget_core.io.project_loader import load_project
from budget_core.model import Project
from budget_core.model.propulsion import PropulsionConfig
from budget_core.thermal.static_thermal import static_thermal_budget

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


def sourced(value: float | None, source: str = "data sheet") -> dict[str, object]:
    return {"value": value, "source": source}


def propulsion(heat: dict[str, object] | None, mode: str | None = "safe") -> PropulsionConfig:
    system: dict[str, object] = {
        "name": "Ion",
        "type": "electric",
        "isp_s": sourced(1500.0),
        "thrust_n": sourced(0.5),
        "power_w": sourced(800.0),
    }
    if heat is not None:
        system |= {"thermal_node": "PL", "thrust_heat_w": heat}
    return PropulsionConfig.model_validate(
        {
            "systems": {"ion": system},
            "maneuvers": [
                {"name": "Raise", "system": "ion", "delta_v_m_s": sourced(4.0), "mode": mode}
            ],
            "dry_mass_kg": sourced(236.0),
        }
    )


@pytest.fixture(scope="module")
def base() -> Project:
    loaded = load_project(EXAMPLES / "microsat_250kg_eps")
    assert loaded.project is not None
    return loaded.project


def with_prop(base: Project, cfg: PropulsionConfig) -> Project:
    return replace(base, config=replace(base.config, propulsion=cfg))


def node_w(result, case: str, node: str) -> float:  # type: ignore[no-untyped-def]
    c = next(c for c in result.cases if c.case == case)
    return next(n.dissipation_w for n in c.nodes if n.node == node)


def test_the_heat_goes_into_the_node_of_the_cases_in_the_burn_mode(base: Project) -> None:
    quiet = static_thermal_budget(with_prop(base, propulsion(None)))
    hot = static_thermal_budget(with_prop(base, propulsion(sourced(120.0))))
    assert node_w(hot, "cold", "PL") == pytest.approx(node_w(quiet, "cold", "PL") + 120.0)
    assert node_w(hot, "hot", "PL") == pytest.approx(node_w(quiet, "hot", "PL"))  # another mode
    for node in ("ADCS", "EPS"):
        assert node_w(hot, "cold", node) == pytest.approx(node_w(quiet, "cold", node))
    cold_quiet = next(c for c in quiet.cases if c.case == "cold")
    cold_hot = next(c for c in hot.cases if c.case == "cold")
    t_quiet = next(n.temperature_k for n in cold_quiet.nodes if n.node == "PL")
    t_hot = next(n.temperature_k for n in cold_hot.nodes if n.node == "PL")
    assert t_hot > t_quiet


def test_a_manoeuvre_without_a_mode_adds_nothing(base: Project) -> None:
    quiet = static_thermal_budget(with_prop(base, propulsion(None, mode=None)))
    same = static_thermal_budget(with_prop(base, propulsion(sourced(120.0), mode=None)))
    assert node_w(same, "cold", "PL") == pytest.approx(node_w(quiet, "cold", "PL"))


def test_a_placeholder_heat_makes_the_case_incomplete(base: Project) -> None:
    result = static_thermal_budget(with_prop(base, propulsion(sourced(None, "TBD"))))
    cold = next(c for c in result.cases if c.case == "cold")
    assert not cold.complete
    assert any(p.code == "RESULT_INCOMPLETE" for p in result.problems)
    hot = next(c for c in result.cases if c.case == "hot")
    assert hot.complete


def test_a_heat_needs_its_node_and_the_node_must_exist() -> None:
    with pytest.raises(ValueError):
        PropulsionConfig.model_validate(
            {
                "systems": {
                    "ion": {
                        "name": "Ion",
                        "type": "electric",
                        "isp_s": sourced(1.0),
                        "thrust_heat_w": sourced(1.0),
                    }
                }
            }
        )
