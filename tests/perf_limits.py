"""Wall-clock limits for the tests that time something.

The spec target (10 s for the week-at-1-s stress case) holds on the reference machine; shared CI
runners are slower and noisy. A test fails only when the time is above `LIMIT_S`, three times the
target, which a real regression (a quadratic loop, a lost cache) exceeds by far. `REFUSE_S` is
for hostile inputs that must be refused quickly instead of hanging: the point is "not for minutes".
"""

TARGET_S = 10.0
LIMIT_S = 3 * TARGET_S
REFUSE_S = 10.0

# The longest time a worker thread may keep the window thread waiting for the interpreter lock (a
# long NumPy or SGP4 call). The aim for the whole window is 100 ms, and its own work comes on top.
HOLD_TARGET_S = 0.05
HOLD_LIMIT_S = 3 * HOLD_TARGET_S
