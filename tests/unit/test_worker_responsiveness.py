"""While a worker thread computes, the window thread must get the interpreter lock soon (D-183).

A week at 1 s is 604,800 samples; one SGP4 call or one conversion of a list of that many floats
held the lock for 50 to 450 ms, and the window, which needs it for every paint, stood still. The
test runs the two heaviest steps in a thread and times how long the main thread waits at most.
"""

from __future__ import annotations

import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest

from budget_core.environment.elements import ElementsPropagator
from budget_core.io.project_loader import load_project
from budget_core.power.battery import integrate_battery
from tests.perf_limits import HOLD_LIMIT_S

pytestmark = pytest.mark.perf

APP_SWITCH_INTERVAL_S = 0.0005  # what the GUI sets (budget_gui.app.SWITCH_INTERVAL_S)


@pytest.fixture(autouse=True)
def the_switch_interval_of_the_app() -> object:
    """The slices give the lock away between two calls; the interval says how soon a waiting
    thread asks for it. At the interpreter's default of 5 ms a burst of hand-overs still takes
    hundreds of milliseconds."""
    before = sys.getswitchinterval()
    sys.setswitchinterval(APP_SWITCH_INTERVAL_S)
    yield
    sys.setswitchinterval(before)


EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
WEEK_S = 604800


def longest_wait(work: object) -> float:
    done = threading.Event()

    def run() -> None:
        try:
            work()  # type: ignore[operator]
        finally:
            done.set()

    threading.Thread(target=run, daemon=True).start()
    worst, last = 0.0, time.perf_counter()
    while not done.is_set():
        time.sleep(0.001)
        now = time.perf_counter()
        worst, last = max(worst, now - last), now
    return worst


def test_a_week_of_orbit_positions_does_not_stall_another_thread() -> None:
    loaded = load_project(EXAMPLES / "microsat_250kg_eps").project
    assert loaded is not None
    propagator = ElementsPropagator(next(iter(loaded.orbits.values())))
    times = np.arange(WEEK_S + 1, dtype=float)
    start = datetime(2026, 6, 1, tzinfo=UTC)
    longest_wait(lambda: propagator._positions(start, times))  # imports and caches settle
    worst = longest_wait(lambda: propagator._positions(start, times))
    assert worst < HOLD_LIMIT_S, f"the main thread waited {worst * 1000:.0f} ms"


def test_a_week_of_battery_steps_does_not_stall_another_thread() -> None:
    n = WEEK_S
    steps = np.ones(n)
    generation = 40.0 + 30.0 * np.sin(np.arange(n) / 2000.0)
    demand = np.full(n, 45.0)
    worst = longest_wait(
        lambda: integrate_battery(steps, generation, demand, 100.0, 0.95, 0.97, 60.0)
    )
    assert worst < HOLD_LIMIT_S, f"the main thread waited {worst * 1000:.0f} ms"
