"""Long NumPy and SGP4 calls run in slices, so the window thread gets the interpreter lock between
them (D-183). The results must not change by a single bit."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest

from budget_core import slices
from budget_core.environment import geometry as geo
from budget_core.environment.elements import ElementsPropagator
from budget_core.io.project_loader import load_project
from budget_core.power.battery import integrate_battery
from budget_core.slices import SLICE, array_from, list_from, release

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


def test_the_slice_is_small_enough_to_hold_the_lock_for_a_few_milliseconds() -> None:
    assert 512 <= SLICE <= 4096


@pytest.mark.parametrize("n", [0, 1, SLICE - 1, SLICE, SLICE + 1, 3 * SLICE + 5])
def test_a_list_is_the_array_it_came_from_in_any_number_of_slices(n: int) -> None:
    rng = np.random.default_rng(n)
    values = rng.normal(size=n)
    assert list_from(values) == values.tolist()
    back = array_from(values.tolist())
    assert back.dtype == np.float64 and back.shape == (n,)
    assert back.tobytes() == values.tobytes()


@pytest.mark.parametrize("n", [0, 1, SLICE, 2 * SLICE + 3])
def test_a_list_is_emptied_in_slices_when_it_is_released(n: int) -> None:
    values = [float(i) for i in range(n)]
    release(values)
    assert values == []


@pytest.mark.parametrize("n", [0, 1, SLICE, 2 * SLICE + 3])
def test_a_list_turned_into_an_array_can_be_given_up_on_the_way(n: int) -> None:
    values = np.random.default_rng(n).normal(size=n)
    as_list = values.tolist()
    back = array_from(as_list, release_list=True)
    assert back.tobytes() == values.tobytes()
    assert as_list == []


def test_nan_and_negative_zero_survive_the_slices() -> None:
    values = np.array([math.nan, -0.0, math.inf, -math.inf, 1e-320] * (SLICE // 2))
    assert array_from(list_from(values)).tobytes() == values.tobytes()


def test_the_lock_is_given_up_between_slices(monkeypatch: pytest.MonkeyPatch) -> None:
    """Python code runs between two slices; a counter stands for the interpreter's chance to hand
    the lock to another thread."""
    seen: list[int] = []
    real_range = range

    def spy_range(*args: int) -> range:
        out = real_range(*args)
        if len(args) == 3 and args[2] == SLICE:
            seen.append(len(out))
        return out

    monkeypatch.setattr(slices, "range", spy_range, raising=False)
    array_from([0.0] * (4 * SLICE))
    list_from(np.zeros(4 * SLICE))
    assert seen == [4, 4]


def test_the_battery_is_the_same_as_the_plain_loop_over_a_long_run() -> None:
    n = 5 * SLICE + 17
    rng = np.random.default_rng(7)
    dt = np.full(n, 1.0)
    generation = 40.0 + 30.0 * np.sin(np.arange(n) / 500.0) + rng.normal(size=n)
    demand = np.full(n, 45.0)
    trace = integrate_battery(dt, generation, demand, 100.0, 0.95, 0.97, 60.0)
    # reference: the loop of the model on whole lists, as it was before the slices
    energy = [60.0]
    e = 60.0
    for i in range(n):
        p = float((generation - demand)[i])
        hours = 1.0 / 3600.0
        if p >= 0.0:
            offered = p * hours
            room = (100.0 - e) / 0.95
            accepted = min(offered, room)
            accepted = max(accepted, 0.0)
            e = min(e + 0.95 * accepted, 100.0)
        else:
            needed = -p * hours
            available = e * 0.97
            supplied = min(needed, available)
            e = max(e - supplied / 0.97, 0.0)
        energy.append(e)
    assert trace.energy_wh.tobytes() == np.array(energy).tobytes()
    assert len(trace.battery_power_w) == n == len(trace.saturation_fraction)


def test_the_positions_of_an_orbit_are_the_same_in_slices_as_in_one_call() -> None:
    from sgp4.api import SatrecArray

    loaded = load_project(EXAMPLES / "microsat_250kg_eps").project
    assert loaded is not None
    orbit = next(iter(loaded.orbits.values()))
    propagator = ElementsPropagator(orbit)
    start = datetime(2026, 6, 1, tzinfo=UTC)
    times = np.arange(3 * SLICE + 11, dtype=float) * 10.0
    whole, fraction = geo.julian_date_parts(start)
    fractions = fraction + times / 86400.0
    error, pos, _ = SatrecArray([propagator.sat]).sgp4(np.full(len(times), whole), fractions)
    assert not np.any(error)
    sliced, jd = propagator._positions(start, times)
    assert sliced.tobytes() == (np.asarray(pos[0]) * 1000.0).tobytes()
    assert jd.tobytes() == (whole + fractions).tobytes()


def test_an_orbit_that_cannot_be_propagated_is_still_an_error_in_slices(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SGP4 reports an error in the second slice only: the whole propagation is refused."""
    from budget_core.environment import elements
    from budget_core.environment.elements import PropagationError

    class Failing:
        calls = 0

        def __init__(self, _satellites: list[object]) -> None:
            pass

        def sgp4(self, jd: np.ndarray, fr: np.ndarray) -> tuple[np.ndarray, np.ndarray, None]:
            Failing.calls += 1
            error = np.zeros((1, len(fr)), dtype=int)
            if Failing.calls == 2:
                error[0, 3] = 1
            return error, np.zeros((1, len(fr), 3)), None

    loaded = load_project(EXAMPLES / "microsat_250kg_eps").project
    assert loaded is not None
    propagator = ElementsPropagator(next(iter(loaded.orbits.values())))
    monkeypatch.setattr(elements, "SatrecArray", Failing)
    with pytest.raises(PropagationError):
        propagator._positions(datetime(2026, 6, 1, tzinfo=UTC), np.arange(3 * SLICE, dtype=float))
    assert Failing.calls == 2  # it stopped at the slice that failed
