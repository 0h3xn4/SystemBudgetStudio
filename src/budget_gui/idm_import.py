# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""File menu action: start or update a project from an IDM-CIC model (decisions D-240 to D-244).

Reads models from IDM-CIC (c) CNES. The window asks for the model file, the target (the open
project or a new folder), the margin option and, for a new project, the voltage of the power bus.
The model is read and the plan worked out in a worker (a model of a few hundred pieces of
equipment takes seconds), the plan is shown, and nothing is written until the user says yes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication, QFileDialog, QInputDialog, QMessageBox

from budget_core.idm.importer import ImportPlan, apply_plan, plan_import
from budget_core.idm.mapping import ImportOptions, slug
from budget_core.idm.reader import read_idm
from budget_core.idm.summary import plan_summary
from budget_core.problems import Problem, Severity

if TYPE_CHECKING:
    from budget_gui.main_window import MainWindow

TITLE = "System Budget Studio"
MARGIN_CHOICES = (
    "raw: values as in the model, margins by the maturity classes of the project",
    "applied: the model's margins are applied to the values, the classes carry none",
)
BUS_VOLTAGE_RANGE_V = (1.0, 1000.0)
_NUMBER = re.compile(r"[+-]?\d+(?:[.,]\d+)?")


@dataclass(frozen=True)
class IdmRequest:
    file: Path
    root: Path
    options: ImportOptions
    bus_voltage_v: float | None


@dataclass(frozen=True)
class IdmResult:
    plan: ImportPlan | None
    notes: tuple[Problem, ...]
    source: str
    sha256: str
    errors: tuple[Problem, ...]


def work(request: IdmRequest) -> IdmResult:
    """Read the model and work out the plan (no GUI; run in a worker)."""
    read = read_idm(request.file)
    errors = tuple(p for p in read.problems if p.severity is Severity.ERROR)
    if errors or read.model is None:
        return IdmResult(None, (), "", "", errors)
    plan = plan_import(
        read.model, request.root, request.options, bus_voltage_v=request.bus_voltage_v
    )
    plan_errors = tuple(p for p in plan.problems if p.severity is Severity.ERROR)
    notes = (*read.problems, *plan.problems)
    return IdmResult(plan, notes, read.model.source_name, read.model.sha256, plan_errors)


class IdmWorker(QThread):
    finished_ok = Signal(object)

    def __init__(self, request: IdmRequest) -> None:
        super().__init__()
        self._request = request

    def run(self) -> None:
        self.finished_ok.emit(work(self._request))


def _bus_voltage(window: MainWindow) -> float | None:
    low, high = BUS_VOLTAGE_RANGE_V
    text, ok = QInputDialog.getText(
        window,
        TITLE,
        f"Nominal voltage of the power bus, in volts ({low:g} to {high:g}).\n"
        "The model does not give one and the tool does not invent it.",
    )
    if not ok:
        return None
    if not _NUMBER.fullmatch(text.strip()):
        QMessageBox.warning(window, TITLE, "Give the voltage as a number, for example 28.")
        return None
    value = float(text.strip().replace(",", "."))
    if not low <= value <= high:
        QMessageBox.warning(window, TITLE, f"The voltage must be between {low:g} and {high:g} V.")
        return None
    return value


def import_idm_model(window: MainWindow) -> None:
    name, _ = QFileDialog.getOpenFileName(
        window, "Import an IDM-CIC model", "", "IDM-CIC models (*.idm)"
    )
    if not name:
        return
    path = Path(name)
    open_root = window.session.path if window.session.project is not None else None
    into_open = False
    if open_root is not None:
        box = QMessageBox(window)
        box.setWindowTitle(TITLE)
        box.setText("Import the model into the open project, or create a new project from it?")
        update = box.addButton("Update the open project", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Create a new project", QMessageBox.ButtonRole.DestructiveRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.exec()
        clicked = box.clickedButton()
        if clicked is None or box.standardButton(clicked) == QMessageBox.StandardButton.Cancel:
            return
        into_open = clicked is update
    if into_open:
        assert open_root is not None
        if window.editors.has_unsaved_changes():
            QMessageBox.information(
                window,
                TITLE,
                "Some files have unsaved changes. Save or discard them first, then import.",
            )
            return
        root, voltage = open_root, None
        buses = [b.name for b in window.session.project.spacecraft.buses]  # type: ignore[union-attr]
        bus = buses[0]
        if len(buses) > 1:
            bus, ok = QInputDialog.getItem(window, TITLE, "Power bus of the units", buses, 0, False)
            if not ok:
                return
    else:
        parent = QFileDialog.getExistingDirectory(window, "Folder for the new project")
        if not parent:
            return
        root = Path(parent) / slug(path.stem)
        if root.exists():
            QMessageBox.warning(
                window, TITLE, f"The folder '{root.name}' already exists. Choose another folder."
            )
            return
        voltage = _bus_voltage(window)
        if voltage is None:
            return
        bus = "main"
    choice, ok = QInputDialog.getItem(window, TITLE, "Margins", list(MARGIN_CHOICES), 0, False)
    if not ok:
        return
    options = ImportOptions(margins=choice.split(":", 1)[0], bus=bus)
    run_import(window, IdmRequest(path, root, options, voltage), into_open)


def run_import(window: MainWindow, request: IdmRequest, into_open: bool) -> None:
    worker = IdmWorker(request)
    window._idm_worker = worker  # type: ignore[attr-defined]  # keep it alive until it finishes
    QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
    worker.finished_ok.connect(lambda result: _planned(window, request, result, into_open))
    worker.start()


def _planned(window: MainWindow, request: IdmRequest, result: IdmResult, into_open: bool) -> None:
    QApplication.restoreOverrideCursor()
    if result.plan is None or result.errors:
        text = "\n".join(p.format() for p in result.errors)
        QMessageBox.warning(
            window, TITLE, f"The model cannot be imported; nothing was written.\n\n{text}"
        )
        return
    summary = plan_summary(result.plan, list(result.notes), result.source, result.sha256)
    box = QMessageBox(window)
    box.setWindowTitle(TITLE)
    box.setText("Write these files?" if result.plan.files else "Nothing to write: no change.")
    box.setDetailedText(summary)
    box.setInformativeText(summary.splitlines()[2] if len(summary.splitlines()) > 2 else "")
    if result.plan.files:
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.setDefaultButton(QMessageBox.StandardButton.No)
    box.exec()
    if not result.plan.files or box.result() != int(QMessageBox.StandardButton.Yes):
        return
    try:
        apply_plan(result.plan)
    except (OSError, ValueError) as exc:
        QMessageBox.warning(window, TITLE, f"The files could not be written.\n\n{exc}")
        return
    if into_open:
        window.reload_project()
    else:
        window.open_project(request.root)
