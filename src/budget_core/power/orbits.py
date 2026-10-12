"""Orbit windows: one window per completed revolution, found from the positions alone.

Works for every environment source (it needs no orbital elements) and for equatorial and polar
orbits. Window k runs from the k-th to the (k+1)-th passage of the starting angle in the orbit
plane; the first window starts at the first sample. A partial last revolution is not a window.

The angle is unwrapped from the samples, so the samples must not be further apart than a
quarter of a revolution (`MAX_STEP_RAD`): beyond that a step cannot be told from a step of a
different number of revolutions plus the same remainder, and the windows would be wrong. Then no
windows are returned and the reason is `coarse`.
"""

from __future__ import annotations

import math
from typing import Any, Literal

import numpy as np

NDArray = np.ndarray[Any, np.dtype[np.float64]]

MAX_STEP_RAD = math.pi / 2.0  # largest angle between two samples that still gives windows
WindowReason = Literal["coarse", "plane", "incomplete"]


def orbit_windows(
    times_s: NDArray, position_m: NDArray, end_s: float | None = None
) -> list[tuple[float, float]]:
    return orbit_windows_with_reason(times_s, position_m, end_s)[0]


def orbit_windows_with_reason(
    times_s: NDArray, position_m: NDArray, end_s: float | None = None
) -> tuple[list[tuple[float, float]], WindowReason | None]:
    """The windows and, when there are none, why: `coarse` (samples further apart than a quarter
    of a revolution), `plane` (the orbit plane cannot be found: fewer than three samples or no
    movement) or `incomplete` (less than one revolution). `end_s` is the scenario end: when it
    lies after the last sample (the duration is not a multiple of the step) the angle is
    extended linearly to it, so a revolution that completes in the last step is kept."""
    r = np.asarray(position_m, dtype=np.float64)
    t = np.asarray(times_s, dtype=np.float64)
    if len(r) < 3:
        return [], "plane"
    r0 = r[0] / np.linalg.norm(r[0])
    cross = np.cross(r0, r)
    sines = np.linalg.norm(cross, axis=1) / np.linalg.norm(r, axis=1)
    moved = np.nonzero(sines > math.sin(math.radians(10.0)))[0]
    if len(moved) == 0:
        return [], "plane"
    normal = cross[moved[0]] / np.linalg.norm(cross[moved[0]])
    ey = np.cross(normal, r0)
    angle = np.unwrap(np.arctan2(r @ ey, r @ r0))
    if np.any(np.abs(np.diff(angle)) > MAX_STEP_RAD + 1e-9):
        return [], "coarse"
    if end_s is not None and end_s > t[-1] + 1e-9:
        rate = (angle[-1] - angle[-2]) / (t[-1] - t[-2])
        t = np.append(t, end_s)
        angle = np.append(angle, angle[-1] + rate * (end_s - t[-2]))
    revolutions = int(math.floor(angle[-1] / (2.0 * math.pi) + 1e-9))
    marks = [float(t[0])]
    for k in range(1, revolutions + 1):
        target = 2.0 * math.pi * k
        j = int(np.searchsorted(angle, target - 1e-9, side="left"))
        if j <= 0 or j >= len(angle):
            break
        a0, a1 = angle[j - 1], angle[j]
        fraction = 1.0 if a1 == a0 else min(max((target - a0) / (a1 - a0), 0.0), 1.0)
        marks.append(float(t[j - 1] + fraction * (t[j] - t[j - 1])))
    windows = list(zip(marks[:-1], marks[1:], strict=True))
    return windows, (None if windows else "incomplete")
