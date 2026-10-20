"""Long NumPy and SGP4 calls in slices (D-183).

A call such as `ndarray.tolist()` or `np.array(list)` on the 600,000 samples of a week at 1 s
holds the interpreter lock for tens of milliseconds, and the window of the GUI, which needs the
lock for every paint, waits. Between two slices the interpreter can hand the lock to another thread.
The results are the same numbers, bit for bit: a slice only changes how many elements one call
converts.
"""

from __future__ import annotations

from typing import Any

import numpy as np

SLICE = 2048  # elements per call: about a millisecond for a conversion or for SGP4

NDArray = np.ndarray[Any, np.dtype[np.float64]]


def list_from(values: NDArray) -> list[float]:
    """`values.tolist()` of a one-dimensional array, in slices."""
    out: list[float] = []
    for start in range(0, len(values), SLICE):
        out.extend(values[start : start + SLICE].tolist())
    return out


def array_from(values: list[float], *, release_list: bool = False) -> NDArray:
    """`np.array(values)` of a list of floats, in slices. With `release_list` the list is given up
    on the way (emptied from its end, slice by slice): freeing 600,000 floats at once also holds
    the lock for tens of milliseconds."""
    out = np.empty(len(values), dtype=np.float64)
    for start in (
        reversed(range(0, len(values), SLICE)) if release_list else range(0, len(values), SLICE)
    ):
        out[start : start + SLICE] = values[start : start + SLICE]
        if release_list:
            del values[start:]
    return out


def release(values: list[float]) -> None:
    """Empty a long list in slices (see `array_from`)."""
    for start in reversed(range(0, len(values), SLICE)):
        del values[start:]
