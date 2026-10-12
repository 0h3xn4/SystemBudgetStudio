"""Pre-release audit fixes in the thermal budget (TL-1, TL-13, TL-14, TL-15, TL-17).

Numbers are invented and worked out by hand (see `tests/thermal_helpers.py`).
"""

from __future__ import annotations

import numpy as np
import pytest

from budget_core.model import Surface, TemperatureLimits, ThermalEnvironment
from budget_core.thermal.static_thermal import static_thermal_budget
from budget_core.thermal.steady_state import (
    STEFAN_BOLTZMANN_WM2K4,
    ThermalSolveError,
    node_balance_w,
    solve_steady_state,
)
from tests.thermal_helpers import exposure, thermal_project

S = STEFAN_BOLTZMANN_WM2K4


# ---- TL-1: a node balances to its own heat, not to the body's -----------------------------------


@pytest.mark.parametrize("area", [1e-3, 1e-5])
@pytest.mark.parametrize("space", [3.0, 4.0, 200.0])
def test_an_isolated_tiny_node_beside_a_large_body_is_at_the_space_temperature(
    area: float, space: float
) -> None:
    # node 0: a body of 1 m2 with 100 W. Node 1: a tiny isolated node, no heat: it is at the
    # temperature of space, whatever the neighbour does
    g = np.zeros((2, 2))
    r = np.array([0.85 * S, 0.85 * S * area])
    t = solve_steady_state(g, r, np.array([100.0, 0.0]), space)
    assert t[1] == pytest.approx(space, abs=1e-6)
    assert t[0] == pytest.approx((100.0 / r[0] + space**4) ** 0.25, abs=1e-6)


def test_an_isolated_tiny_node_with_its_own_heat_follows_the_closed_form() -> None:
    # 1 mW into 0.85 * sigma * 1e-3 m2 against 3 K space: T^4 = Q / R + Ts^4
    g = np.zeros((2, 2))
    r = np.array([0.85 * S, 0.85 * S * 1e-3])
    q = np.array([100.0, 1e-3])
    t = solve_steady_state(g, r, q, 3.0)
    assert t[1] == pytest.approx((1e-3 / r[1] + 3.0**4) ** 0.25, abs=1e-6)


def test_every_node_balances_to_its_own_scale() -> None:
    g = np.zeros((2, 2))
    r = np.array([0.85 * S, 0.85 * S * 1e-3])
    q = np.array([100.0, 0.0])
    t = solve_steady_state(g, r, q, 3.0)
    residual = node_balance_w(g, r, q, 3.0, t)
    assert abs(residual[1]) < 1e-12  # the old test accepted 0.1 W on a node that radiates 0.5 W


# ---- TL-17: a stiff chain is solved when the answer is accurate ----------------------------------


def chain(g_wk: float, heat_w: float = 10.0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    n = 5
    g = np.zeros((n, n))
    for i in range(n - 1):
        g[i, i + 1] = g[i + 1, i] = g_wk
    r = np.zeros(n)
    r[0] = 0.8 * S * 0.4  # only node 0 radiates
    q = np.zeros(n)
    q[-1] = heat_w  # the heat enters at the far end and flows down the chain
    return g, r, q


@pytest.mark.parametrize("g_wk", [1e3, 1e6, 1e8, 1e10])
def test_a_stiff_five_node_chain_is_solved_to_the_closed_form(g_wk: float) -> None:
    # all the heat leaves from node 0: T0^4 = Q / R + Ts^4; each link carries Q, so node i is
    # i * Q / G warmer than node 0
    g, r, q = chain(g_wk)
    t = solve_steady_state(g, r, q, 3.0)
    t0 = (10.0 / r[0] + 3.0**4) ** 0.25
    assert t == pytest.approx(t0 + np.arange(5) * 10.0 / g_wk, abs=1e-9)


def test_unresolvable_stiffness_is_still_refused() -> None:
    g, r, q = chain(1e18)
    with pytest.raises(ThermalSolveError):
        solve_steady_state(g, r, q, 3.0)


# ---- TL-13, TL-14, TL-15 ---------------------------------------------------------------------


def test_a_thermal_environment_without_cases_is_incomplete() -> None:
    project = thermal_project()
    env = project.config.thermal_environment
    assert env is not None
    empty = ThermalEnvironment(
        space_temperature_k=env.space_temperature_k,
        temperature_margin_k=env.temperature_margin_k,
        cases={},
    )
    object.__setattr__(project.config, "thermal_environment", empty)
    result = static_thermal_budget(project)
    assert result.cases == ()
    (problem,) = [p for p in result.problems if p.path == "cases"]
    assert problem.code == "RESULT_INCOMPLETE" and problem.file == "config/thermal_environment.yaml"


def hot_and_cold_exceeded():  # type: ignore[no-untyped-def]
    # both cases put unit u1 (node A) outside a limit window it cannot meet
    limits = TemperatureLimits(operating_min_k=290.0, operating_max_k=295.0)
    return static_thermal_budget(thermal_project(limits_u1=limits))


def test_limit_findings_name_the_case_and_are_not_merged() -> None:
    result = hot_and_cold_exceeded()
    found = [p for p in result.problems if p.code == "THERMAL_LIMIT_EXCEEDED"]
    assert len(found) == 2
    # the case is a key the user typed: it is named in the path, not in the message
    assert {("hot" in p.path, "cold" in p.path) for p in found} == {(True, False), (False, True)}
    assert not [p for p in found if "hot" in p.message or "cold" in p.message]


def test_margin_findings_name_the_case() -> None:
    cold = next(c for c in static_thermal_budget(thermal_project()).cases if c.case == "cold")
    temp = next(n for n in cold.nodes if n.node == "B").temperature_k
    # a lower limit 2 K below the cold temperature of node B, against a required margin of 5 K
    limits = TemperatureLimits(operating_min_k=temp - 2.0, operating_max_k=400.0)
    result = static_thermal_budget(thermal_project(margin=5.0, limits_u2=limits))
    found = [p for p in result.problems if p.code == "THERMAL_MARGIN_INSUFFICIENT"]
    assert found and all("cold" in p.path and "cold" not in p.message for p in found)


def test_messages_do_not_repeat_surface_names() -> None:
    project = thermal_project(conductance=None)
    model = project.config.thermal_model
    assert model is not None
    secret = Surface(
        name="secret surface",
        node="A",
        area_m2=1.0,
        emissivity_ratio=model.surfaces[0].emissivity_ratio.model_copy(update={"value": None}),
        absorptivity_ratio=model.surfaces[0].absorptivity_ratio,
        exposure={"hot": exposure(0.5, 0.5)},  # no exposure for the case "cold"
    )
    object.__setattr__(model, "surfaces", [secret])
    result = static_thermal_budget(project)
    assert result.problems
    assert not [p for p in result.problems if "secret" in p.message + p.hint]
