"""Run: the scenario, the power timeline and the link passes of the selected scenario, in order.

The static budgets (power, mass, thermal, link) are worked out when a project loads, so *Run* only
adds what needs a scenario. Each step is the computation of the view that shows it, so a result is
the same whether it is made by Run or by that view's own Compute button; the later steps reuse the
environment of the first (an orbit is not worked out twice). The controller also says in one word
where the results stand: not run, running, up to date, out of date, or failed.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from PySide6.QtCore import QObject, Signal


class RunState(StrEnum):
    NOT_RUN = "not_run"
    RUNNING = "running"
    OK = "ok"
    STALE = "stale"
    FAILED = "failed"


STATE_TEXT = {
    RunState.NOT_RUN: "Not run",
    RunState.RUNNING: "Running…",
    RunState.OK: "Up to date",
    RunState.STALE: "Out of date",
    RunState.FAILED: "Run failed",
}


class RunController(QObject):
    changed = Signal()

    def __init__(self, scenario: Any, timeline: Any, passes: Any) -> None:
        super().__init__()
        self.scenario, self.timeline, self.passes = scenario, timeline, passes
        self._queue: list[Any] = []
        self._current: Any = None
        self._failed: str | None = None
        for view in (scenario, timeline, passes):
            view.computed.connect(lambda _result, v=view: self._step_done(v))
            view.compute_failed.connect(lambda message, v=view: self._step_failed(v, message))

    # ---- what can run ------------------------------------------------------------------------
    def _steps(self) -> list[Any]:
        project = self.scenario.project
        if project is None or not self.scenario.selected_id():
            return []
        steps = [self.scenario, self.timeline]
        if project.links:
            steps.append(self.passes)
        return steps

    def can_run(self) -> bool:
        return bool(self._steps()) and not self.is_running()

    def is_running(self) -> bool:
        return self._current is not None or any(
            v.is_busy() for v in (self.scenario, self.timeline, self.passes)
        )

    # ---- running -----------------------------------------------------------------------------
    def run(self) -> bool:
        """Start a run of every step; False when there is nothing to run or one is running."""
        if not self.can_run():
            return False
        self._failed = None
        self._queue = self._steps()
        self._advance()
        return True

    def _advance(self) -> None:
        while self._queue:
            view = self._queue.pop(0)
            view.compute()
            if view.is_busy():
                self._current = view
                self.changed.emit()
                return
        self._current = None
        self.changed.emit()

    def _step_done(self, view: Any) -> None:
        if view is self._current:
            self._current = None
            self._advance()
        else:
            self.changed.emit()

    def _step_failed(self, view: Any, message: str) -> None:
        if view is self._current or self._queue:
            self._failed = message
            self._queue = []
            self._current = None
        self.changed.emit()

    def reset_failure(self) -> None:
        """A new project or a reload: an old failure says nothing about it."""
        if self._failed is not None:
            self._failed = None
            self.changed.emit()

    # ---- where the results stand -------------------------------------------------------------
    @property
    def failure(self) -> str | None:
        return self._failed

    def state(self) -> RunState:
        if self.is_running():
            return RunState.RUNNING
        if self._failed is not None:
            return RunState.FAILED
        steps = self._steps()
        if not steps:
            return RunState.NOT_RUN
        done = self.scenario.last_run is not None and self.timeline.result is not None
        if self.passes in steps:
            done = done and self.passes.result is not None
        if not done:
            return RunState.NOT_RUN
        stale = self.scenario.is_stale or self.timeline.is_stale
        if self.passes in steps:
            stale = stale or self.passes.is_stale
        return RunState.STALE if stale else RunState.OK
