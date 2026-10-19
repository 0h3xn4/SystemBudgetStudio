"""Measure what the user waits for: start to first window, tab switches, the heaviest actions.

    QT_QPA_PLATFORM=offscreen python scripts/ui_baseline.py

Prints milliseconds (median of several runs where a run is cheap). Offscreen, device pixel ratio
1: the numbers compare before with after on one machine; they are not absolute. Used for the UI
overhaul (docs/ui/UI_OVERHAUL.md); results go to docs/ui/UI_OVERHAUL_PLAN.md.
"""

from __future__ import annotations

import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["BUDGET_NO_LAYOUT"] = "1"
ROOT = Path(__file__).resolve().parent.parent

START = """
import time
t0 = time.perf_counter()
from budget_gui.app import create_app
from budget_gui.main_window import MainWindow
t1 = time.perf_counter()
app = create_app([])
w = MainWindow(); w.show(); app.processEvents()
t2 = time.perf_counter()
print(f"{(t1-t0)*1000:.0f} {(t2-t1)*1000:.0f}")
"""


def start_up() -> None:
    runs = []
    for _ in range(5):
        out = subprocess.run(
            [sys.executable, "-c", START], capture_output=True, text=True, check=True
        ).stdout.split()
        runs.append((float(out[0]), float(out[1])))
    imports = statistics.median(r[0] for r in runs)
    window = statistics.median(r[1] for r in runs)
    print(
        f"start-up: imports {imports:.0f} ms + app and first window {window:.0f} ms "
        f"= {imports + window:.0f} ms (median of 5 fresh processes, after the interpreter)"
    )


def main() -> None:
    start_up()
    from PySide6.QtCore import QEventLoop, QPoint, QPointF, Qt, QTimer
    from PySide6.QtGui import QWheelEvent
    from PySide6.QtWidgets import QApplication

    from budget_gui.app import create_app
    from budget_gui.main_window import MainWindow

    app = create_app([])

    def wait(ms: int) -> None:
        loop = QEventLoop()
        QTimer.singleShot(ms, loop.quit)
        loop.exec()

    def wait_for(cond, timeout=300.0) -> None:  # noqa: ANN001
        end = time.monotonic() + timeout
        while not cond() and time.monotonic() < end:
            wait(20)

    def timed(fn) -> float:  # noqa: ANN001
        t = time.perf_counter()
        fn()
        app.processEvents()
        return (time.perf_counter() - t) * 1000

    def tab_switches(window) -> str:  # noqa: ANN001
        times: dict[str, list[float]] = {}
        for _ in range(3):
            for i in range(window.workspace.count()):
                name = window.workspace.tabText(i)
                times.setdefault(name, []).append(
                    timed(lambda i=i: window.workspace.setCurrentIndex(i))
                )
        return ", ".join(f"{k} {statistics.median(v):.0f}" for k, v in times.items())

    work = Path(tempfile.mkdtemp(prefix="sbs-base-"))
    try:
        small = work / "small"
        shutil.copytree(ROOT / "examples" / "microsat_250kg_eps", small)
        big = work / "stress"
        shutil.copytree(ROOT / "examples" / "stress_200_units", big)
        week = work / "week"
        shutil.copytree(small, week)
        f = week / "scenarios/one_day.yaml"
        f.write_text(
            re.sub(
                r"step_s: \d+(\.\d+)?",
                "step_s: 1",
                re.sub(r"duration_s: \d+(\.\d+)?", "duration_s: 604800", f.read_text()),
            )
        )

        window = MainWindow()
        window.resize(1400, 860)
        window.show()
        app.processEvents()

        t = time.perf_counter()
        window.open_project(small)
        wait_for(lambda: window.session.project is not None)
        print(f"open microsat_250kg_eps: {(time.perf_counter() - t) * 1000:.0f} ms")
        t = time.perf_counter()
        window.run_all()
        wait(100)
        wait_for(lambda: not window.run_controller.is_running())
        print(
            "Run (a day, environment + timeline + link passes): "
            f"{(time.perf_counter() - t) * 1000:.0f} ms"
        )
        print("tab switch (ms, median of 3): " + tab_switches(window))

        window.editors.discard_all_changes()
        t = time.perf_counter()
        window.open_project(big)
        wait_for(lambda: window.session.path == big)
        wait(200)
        print(f"open stress_200_units: {(time.perf_counter() - t) * 1000:.0f} ms")
        print("tab switch, 200 units (ms, median of 3): " + tab_switches(window))
        window.workspace.setCurrentIndex(0)
        window.editors.setCurrentIndex(0)
        grid = window.units_page.table
        view = getattr(grid, "view", None)
        if view is not None:
            bar = view.verticalScrollBar()
            t = time.perf_counter()
            for v in range(0, bar.maximum(), max(1, bar.maximum() // 40)):
                bar.setValue(v)
                app.processEvents()
            print(f"scroll the 200-unit grid, 40 steps: {(time.perf_counter() - t) * 1000:.0f} ms")

        window.editors.discard_all_changes()
        window.open_project(week)
        wait_for(lambda: window.session.path == week)
        window.show_view(window.timeline_view)
        t = time.perf_counter()
        window.run_all()
        wait(200)
        peak_gap = 0.0
        last = time.perf_counter()
        while window.run_controller.is_running():
            wait(10)
            now = time.perf_counter()
            peak_gap = max(peak_gap, now - last)
            last = now
        print(
            f"Run, a week at 1 s: {time.perf_counter() - t:.1f} s; longest stretch the window "
            f"thread did not return to the event loop: {peak_gap * 1000:.0f} ms"
        )
        plot = window.timeline_view.plot
        plot.resize(1000, 600)
        app.processEvents()
        full = timed(plot.repaint)
        zoom = []
        for _ in range(8):
            pos = QPointF(500, 200)
            event = QWheelEvent(
                pos,
                plot.mapToGlobal(pos),
                QPoint(),
                QPoint(0, 120),
                Qt.MouseButton.NoButton,
                Qt.KeyboardModifier.NoModifier,
                Qt.ScrollPhase.NoScrollPhase,
                False,
            )
            zoom.append(timed(lambda event=event: QApplication.sendEvent(plot, event)))
        print(
            f"timeline plot, week at 1 s: full repaint {full:.0f} ms; wheel zoom step median "
            f"{statistics.median(zoom):.0f} ms, worst {max(zoom):.0f} ms"
        )
        window.editors.discard_all_changes()
        window.close()
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
