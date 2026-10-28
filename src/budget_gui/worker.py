"""Background export so the window stays responsive (spec: GUI responsive during runs)."""

from __future__ import annotations

from collections.abc import Callable, Collection, Sequence
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from budget_core.explain import Explainer, ExplainError
from budget_core.reports.files import OutputError
from budget_core.reports.run import BudgetOutput, write_outputs


class ExportWorker(QThread):
    """Writes report files in a thread. `outputs` may be a function that builds them, so the
    building (seconds for a week-long timeline) runs in the thread too."""

    finished_ok = Signal(list)
    failed = Signal(str)

    def __init__(
        self,
        outputs: Sequence[BudgetOutput] | Callable[[], Sequence[BudgetOutput]],
        folder: Path,
        kinds: Collection[str],
    ) -> None:
        super().__init__()
        self._args = (outputs if callable(outputs) else list(outputs), folder, set(kinds))

    def run(self) -> None:
        outputs, folder, kinds = self._args
        try:
            built = outputs() if callable(outputs) else outputs
            written = write_outputs(built, folder, kinds)
        except OutputError as exc:  # plain language by construction (no project content)
            self.failed.emit(str(exc))
            return
        except OSError:
            self.failed.emit(
                "The reports could not be written. Check that the folder exists, is a folder "
                "and that you may write to it."
            )
            return
        except Exception as exc:  # plain message only, no traceback or project content
            self.failed.emit(f"The export failed ({type(exc).__name__}).")
            return
        self.finished_ok.emit([str(p) for p in written])


class ExplainWorker(QThread):
    """Solves the power timeline again with the solver's detail (Explain needs the series the
    result only keeps as means), off the window thread."""

    finished_ok = Signal()
    failed = Signal(str)

    def __init__(self, explainer: Explainer) -> None:
        super().__init__()
        self._explainer = explainer

    def run(self) -> None:
        try:
            self._explainer.timeline_result()
        except ExplainError as exc:  # plain language by construction
            self.failed.emit(str(exc))
            return
        except Exception as exc:  # plain message only, no traceback or project content
            self.failed.emit(f"The explanation could not be prepared ({type(exc).__name__}).")
            return
        self.finished_ok.emit()
