"""Progress and cancellation of a long computation (D-167).

A computation takes an optional `RunControl`. It reports a *stage* (a short plain phrase such as
"Power timeline") when it begins one, and it asks `checkpoint()` between steps; when the caller
has asked to stop, the checkpoint raises `Cancelled` and the computation ends without a result.
Nothing is written anywhere and nothing is half done: the caller keeps what it had.

Without a control (the command line, the tests of the equations) nothing is reported and nothing
can be cancelled, and the results are exactly the same: a control only observes and interrupts.
The stages carry no project content.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


class Cancelled(Exception):  # noqa: N818 (a signal, not an error)
    """The caller asked the computation to stop."""


@dataclass(frozen=True)
class RunControl:
    should_cancel: Callable[[], bool] | None = None
    on_stage: Callable[[str], None] | None = None

    def checkpoint(self) -> None:
        if self.should_cancel is not None and self.should_cancel():
            raise Cancelled

    def stage(self, text: str) -> None:
        """Say what is being worked on, and stop here if asked to."""
        if self.on_stage is not None:
            self.on_stage(text)
        self.checkpoint()


def checkpoint(control: RunControl | None) -> None:
    if control is not None:
        control.checkpoint()


def stage(control: RunControl | None, text: str) -> None:
    if control is not None:
        control.stage(text)
