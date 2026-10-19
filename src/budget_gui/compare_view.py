"""Compare tab: the open project against another project folder (a revision), or two scenarios.

Differences are listed budget by budget with the status coloured (changed, added, removed,
now computed, now n/a). The comparison runs in a worker thread; the report files come from the
same code as `budget compare`.
"""

from __future__ import annotations

from collections.abc import Collection
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from budget_core.compare_run import Side, compare_sides, default_kinds
from budget_core.io.project_loader import load_project
from budget_core.model import Project
from budget_core.problems import Severity
from budget_core.reports.run import REPORT_KINDS, BudgetOutput
from budget_core.scenario.run import ScenarioRunError
from budget_gui import theme
from budget_gui.validity import CHANGED_WHILE_RUNNING_TEXT, STALE_TEXT, ResultKey
from budget_gui.worker import ExportWorker

NO_SCENARIO = "(none)"
ALL = "All differences"
HEADERS = ["Budget", "Section", "Row", "Quantity", "A", "B", "Change", "Change (%)", "Status"]
TINTS = {  # the status of a row -> the token of its background
    "changed": "diff_changed",
    "added": "diff_added",
    "removed": "diff_removed",
    "now computed": "diff_now_computed",
    "now n/a": "diff_now_na",
}


class CompareWorker(QThread):
    finished_ok = Signal(object, list)
    failed = Signal(str)

    def __init__(
        self, project: Project, scenario_a: str | None, other: Path | None, scenario_b: str | None
    ) -> None:
        super().__init__()
        self._args = (project, scenario_a, other, scenario_b)

    def run(self) -> None:
        project, scenario_a, other, scenario_b = self._args
        try:
            other_project = project
            if other is not None:
                if not other.is_dir():
                    self.failed.emit(
                        "The other project folder does not exist or is not a folder. "
                        "Check the path."
                    )
                    return
                loaded = load_project(other)
                errors = sum(1 for p in loaded.problems if p.severity is Severity.ERROR)
                if loaded.project is None or errors:
                    self.failed.emit(
                        "The other project cannot be compared: it has errors. "
                        "Open it and fix the problems listed there first."
                    )
                    return
                other_project = loaded.project
            a, b = Side(project, scenario_a), Side(other_project, scenario_b)
            kinds = default_kinds(a, b, same_project=other is None)
            if not kinds:
                self.failed.emit(
                    "Choose another project folder, or two different scenarios, to compare."
                )
                return
            output, notes = compare_sides(a, b, kinds)
        except ScenarioRunError as exc:
            self.failed.emit(exc.problem.format())
            return
        except Exception as exc:  # plain message only, never a traceback or project content
            self.failed.emit(f"The comparison failed ({type(exc).__name__}).")
            return
        self.finished_ok.emit(output, notes)


class CompareView(QWidget):
    computed = Signal(object)
    compute_failed = Signal(str)
    export_finished = Signal(list)
    export_failed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.project: Project | None = None
        self.output: BudgetOutput | None = None
        self._revision = 0  # counts project (re)loads
        self._output_key: ResultKey | None = None  # what `output` was compared from
        self._comparing_key: ResultKey | None = None
        self._worker: CompareWorker | None = None
        self._export_worker: ExportWorker | None = None

        self.scenario_a = QComboBox()
        self.other_edit = QLineEdit()
        self.other_edit.setPlaceholderText(
            "Other project folder (leave empty to compare scenarios)"
        )
        self.browse_button = QPushButton("Browse…")
        self.scenario_b = QComboBox()
        self.compare_button = QPushButton("Compare")
        self.export_button = QPushButton("Export…")
        self.export_button.setEnabled(False)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.side_a_label = QLabel("")
        self.side_a_label.setProperty("role", "muted")
        self.side_b_label = QLabel("")
        self.side_b_label.setProperty("role", "muted")
        self.filter_combo = QComboBox()
        self.filter_combo.addItems([ALL, *TINTS])
        self.filter_combo.setToolTip("Show only the differences of one kind.")
        self.filter_combo.setEnabled(False)
        self._shown: BudgetOutput | None = None
        theme.manager().changed.connect(self._theme_changed)
        self.table = QTableWidget(0, len(HEADERS))
        self.table.setHorizontalHeaderLabels(HEADERS)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setTabKeyNavigation(False)  # Tab leaves a read-only table
        self.table.verticalHeader().setVisible(False)

        row_a = QHBoxLayout()
        row_a.addWidget(QLabel("A: this project, scenario"))
        row_a.addWidget(self.scenario_a)
        row_a.addWidget(self.side_a_label, 1)
        row_b = QHBoxLayout()
        row_b.addWidget(QLabel("B:"))
        row_b.addWidget(self.other_edit, 1)
        row_b.addWidget(self.browse_button)
        row_b.addWidget(QLabel("scenario"))
        row_b.addWidget(self.scenario_b)
        row_b.addWidget(self.side_b_label)
        row_c = QHBoxLayout()
        row_c.addWidget(self.compare_button)
        row_c.addWidget(self.export_button)
        row_c.addWidget(QLabel("Show"))
        row_c.addWidget(self.filter_combo)
        row_c.addWidget(self.status, 1)
        layout = QVBoxLayout(self)
        for row in (row_a, row_b, row_c):
            layout.addLayout(row)
        layout.addWidget(self.table, 1)

        self.scenario_a.currentTextChanged.connect(lambda _t: self._update_validity())
        self.scenario_a.currentTextChanged.connect(lambda _t: self._update_side_a())
        self.filter_combo.currentTextChanged.connect(lambda _t: self._show(self._shown))
        self.scenario_b.currentTextChanged.connect(lambda _t: self._update_validity())
        self.other_edit.textChanged.connect(lambda _t: self._update_validity())
        self.browse_button.clicked.connect(lambda: self._browse())
        self.compare_button.clicked.connect(lambda: self.compare())
        self.export_button.clicked.connect(lambda: self._choose_export())
        self.set_project(None)

    # ---- project -----------------------------------------------------------------------------
    def current_key(self) -> ResultKey:
        """What a comparison started now would compare."""
        return ResultKey(
            self._revision,
            f"{self.scenario_a.currentText()}|{self.scenario_b.currentText()}",
            (self.other_edit.text().strip(),),
        )

    def is_valid(self) -> bool:
        """True when the comparison on screen was made from the inputs that are set now."""
        return self.output is not None and self._output_key == self.current_key()

    @property
    def is_stale(self) -> bool:
        return self.output is not None and not self.is_valid()

    def _update_validity(self) -> None:
        if self.output is None:
            return
        self.export_button.setEnabled(self.is_valid())
        if self.is_stale:
            self.status.setText(STALE_TEXT.replace("Compute", "Compare"))

    def set_project(self, project: Project | None) -> None:
        self.project = project
        self._revision += 1
        ids = [NO_SCENARIO, *sorted(project.scenarios)] if project else [NO_SCENARIO]
        for combo in (self.scenario_a, self.scenario_b):
            previous = combo.currentText()
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(ids)
            if previous in ids:
                combo.setCurrentText(previous)
            combo.blockSignals(False)
        self.compare_button.setEnabled(project is not None and self._worker is None)
        self._update_side_a()
        if project is None:
            self._show(None)
            self.status.setText("Open a project to compare it with another revision.")
        elif self.output is not None:
            self._update_validity()

    def _update_side_a(self) -> None:
        """Say which project, revision and scenario side A is (it is the open project)."""
        project = self.project
        if project is None:
            self.side_a_label.setText("")
            return
        scenario = self._scenario(self.scenario_a)
        text = f"{project.meta.name}, revision {project.meta.revision}"
        self.side_a_label.setText(text + (f", scenario {scenario}" if scenario else ""))

    def set_other_folder(self, folder: Path) -> None:
        self.other_edit.setText(str(folder))

    def _browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose the project folder to compare")
        if folder:
            self.set_other_folder(Path(folder))

    @staticmethod
    def _scenario(combo: QComboBox) -> str | None:
        text = combo.currentText()
        return None if text in ("", NO_SCENARIO) else text

    # ---- compare -----------------------------------------------------------------------------
    def compare(self) -> None:
        if self.project is None or self._worker is not None:
            return
        text = self.other_edit.text().strip()
        self.compare_button.setEnabled(False)
        self.status.setText("Comparing…")
        self._comparing_key = self.current_key()
        worker = CompareWorker(
            self.project,
            self._scenario(self.scenario_a),
            Path(text).expanduser() if text else None,
            self._scenario(self.scenario_b),
        )
        worker.finished_ok.connect(self._done)
        worker.failed.connect(self._failed)
        self._worker = worker
        worker.start()

    def _finish_worker(self) -> None:
        if self._worker is not None:
            self._worker.wait(30000)
            self._worker = None
        self.compare_button.setEnabled(self.project is not None)

    def _done(self, output: BudgetOutput, notes: list[str]) -> None:
        self._finish_worker()
        self.output = output
        self._output_key = self._comparing_key
        self._show(output)
        results = output.result
        total = sum(r.values_differ for r in results)
        text = (
            f"{total} value(s) differ across {len(results)} budget(s)."
            if total
            else "No differences."
        )
        if any(r.truncated for r in results):
            text += " Some differences are not listed; the export holds the first ones only."
        if notes:
            text += " " + " ".join(notes)
        self.status.setText(text)
        self.export_button.setEnabled(self.is_valid())
        if self.is_stale:
            self.status.setText(CHANGED_WHILE_RUNNING_TEXT.replace("Compute", "Compare"))
        self.computed.emit(output)

    def _failed(self, message: str) -> None:
        self._finish_worker()
        self.output = None
        self._show(None)
        self.status.setText(message)
        self.compute_failed.emit(message)

    def wait_for_worker(self) -> None:
        for worker in (self._worker, self._export_worker):
            if worker is not None:
                worker.wait(30000)

    # ---- display -----------------------------------------------------------------------------
    def _theme_changed(self) -> None:
        """Colour the table again (a bound method, so the connection ends with the widget)."""
        self._show(self._shown)

    def _show(self, output: BudgetOutput | None) -> None:
        self._shown = output
        results = output.result if output else ()
        wanted = self.filter_combo.currentText()
        rows = [(r.name, d) for r in results for d in r.differences if wanted in (ALL, d.status)]
        label_a = results[0].label_a if results else "A"
        label_b = results[0].label_b if results else "B"
        headers = [
            (f"A: {label_a}" if h == "A" else f"B: {label_b}" if h == "B" else h) for h in HEADERS
        ]
        self.table.setHorizontalHeaderLabels(headers)
        self.filter_combo.setEnabled(output is not None)
        self.side_b_label.setText(
            f"B: {results[0].provenance_b.project_name}, revision "
            f"{results[0].provenance_b.project_revision}"
            if results
            else ""
        )
        mono = theme.mono_font()
        self.table.setRowCount(len(rows))
        for i, (name, d) in enumerate(rows):
            texts = [
                name,
                d.section,
                d.row,
                d.quantity,
                d.value_a,
                d.value_b,
                d.change,
                d.change_percent,
                d.status,
            ]
            for column, text in enumerate(texts):
                item = QTableWidgetItem(text)
                tokens = theme.tokens()
                item.setBackground(QBrush(QColor(getattr(tokens, TINTS[d.status]))))
                item.setForeground(QBrush(QColor(tokens.text)))
                if column in (4, 5, 6, 7):
                    item.setFont(mono)
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                self.table.setItem(i, column, item)
        self.table.resizeColumnsToContents()
        if output is None:
            self.export_button.setEnabled(False)

    # ---- export ------------------------------------------------------------------------------
    def _choose_export(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Export the comparison to folder")
        if folder:
            self.export_to(Path(folder), set(REPORT_KINDS))

    def export_to(self, folder: Path, kinds: Collection[str]) -> None:
        if self._export_worker is not None:
            self.export_failed.emit("An export is already running; wait for it to finish.")
            return
        if self.output is None:
            self.export_failed.emit("Run a comparison first.")
            return
        if not self.is_valid():
            self.export_failed.emit(
                "The project or a setting changed since this comparison was made. "
                "Press Compare again."
            )
            return
        worker = ExportWorker([self.output], folder, kinds)
        worker.finished_ok.connect(self._export_done)
        worker.failed.connect(self._export_failed)
        self._export_worker = worker
        self.status.setText("Exporting…")
        worker.start()

    def _end_export(self) -> None:
        if self._export_worker is not None:
            self._export_worker.wait()  # the signal arrives just before the thread ends
            self._export_worker = None

    def _export_done(self, paths: list[str]) -> None:
        self._end_export()
        self.status.setText(f"Exported {len(paths)} file(s).")
        self.export_finished.emit(paths)

    def _export_failed(self, message: str) -> None:
        self._end_export()
        self.status.setText(message)
        self.export_failed.emit(message)

    def is_busy(self) -> bool:
        """A comparison or an export is running."""
        return self._worker is not None or self._export_worker is not None
