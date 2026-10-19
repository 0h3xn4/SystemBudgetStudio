"""The Inspector: what is known about the selected node of the project tree.

This first version shows where the node lives (file and field), the problems that belong to it by
class, and buttons to open it. The field-level help, unit, source, placeholder switch, allowed
range and "where used" are built from the model schemas in the step that makes the model editable.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from budget_core.problems import Problem
from budget_gui import icons, theme
from budget_gui import problem_class as pc
from budget_gui.project_tree import Node

KIND_TEXT = {
    "project": "Project",
    "file": "File",
    "raw_file": "File",
    "field": "Field",
    "unit": "Unit",
    "group": "Group",
}
PROBLEM_ROLE = int(Qt.ItemDataRole.UserRole) + 20


@dataclass(frozen=True)
class CellInfo:
    """What is known about the cell of a grid that has the cursor (UX-07)."""

    title: str  # the row: a unit or an input
    column: str  # the field with its unit, as the column header says
    rel: str  # the file the value lives in
    path: str  # the field inside the file
    value: str  # as shown in the cell
    state: str  # the words of its state ("Not checked (n/a)", "Limit broken"), or ""
    message: str  # why the model refuses the value, or ""
    help: str  # what the column means (its tooltip)


class InspectorPanel(QWidget):
    open_requested = Signal()  # open the node (file or field) in an editor
    open_file_requested = Signal(str)  # open the file of the cell that has the cursor
    modes_requested = Signal(str)  # open the power-mode table of a unit
    jump_requested = Signal(str, int)  # a problem: file and line

    def __init__(self) -> None:
        super().__init__()
        self.title = QLabel("")
        self.title.setProperty("role", "title")
        self.title.setWordWrap(True)
        self.kind_label = QLabel("")
        self.kind_label.setProperty("role", "muted")
        self.file_label = QLabel("")
        self.file_label.setFont(theme.mono_font())
        self.file_label.setWordWrap(True)
        self.file_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.field_label = QLabel("")
        self.field_label.setFont(theme.mono_font())
        self.field_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.counts_label = QLabel("")
        self.problems_title = QLabel("Problems on this node")
        self.problems_title.setProperty("role", "section-title")
        self.problems = QListWidget()
        self.problems.setWordWrap(True)
        self.problems.setAlternatingRowColors(True)
        self.empty = QLabel(
            "Select a node in the project tree to see where it lives and what is wrong with it."
        )
        self.empty.setWordWrap(True)
        self.empty.setProperty("role", "muted")
        self.open_button = QPushButton("Open")
        self.open_button.setProperty("kind", "secondary")
        self.modes_button = QPushButton("Edit power modes…")
        self.modes_button.setProperty("kind", "secondary")

        buttons = QHBoxLayout()
        buttons.addWidget(self.open_button)
        buttons.addWidget(self.modes_button)
        buttons.addStretch(1)
        self.details = QWidget()
        details = QVBoxLayout(self.details)
        details.setContentsMargins(0, 0, 0, 0)
        for widget in (
            self.title,
            self.kind_label,
            self.file_label,
            self.field_label,
            self.counts_label,
            self.problems_title,
        ):
            details.addWidget(widget)
        details.addWidget(self.problems, 3)
        details.addStretch(1)  # what is shown stays at the top when there is no list of problems
        details.addLayout(buttons)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.addWidget(self.empty)
        layout.addWidget(self.details, 1)

        self._unit_id = ""
        self._cell_rel = ""
        self.open_button.clicked.connect(self._open_clicked)
        self.modes_button.clicked.connect(lambda: self.modes_requested.emit(self._unit_id))
        self.problems.itemActivated.connect(self._problem_activated)
        self.show_node(None, [])

    def _open_clicked(self) -> None:
        if self._cell_rel:
            self.open_file_requested.emit(self._cell_rel)
        else:
            self.open_requested.emit()

    def show_cell(self, cell: CellInfo) -> None:
        """Show the cell that has the cursor in a grid: where its value lives, what it is, its
        state and, when the model refuses it, why."""
        self.empty.setVisible(False)
        self.details.setVisible(True)
        self._unit_id, self._cell_rel = "", cell.rel
        self.title.setText(cell.title)
        self.kind_label.setText(f"Cell: {cell.column}")
        self.file_label.setText(f"File: {cell.rel}")
        self.file_label.setVisible(True)
        self.field_label.setText(f"Field: {cell.path}")
        self.field_label.setVisible(bool(cell.path))
        lines = [f"Value: {cell.value}"]
        if cell.state:
            lines.append(cell.state)
        if cell.help:
            lines.append(cell.help)
        self.counts_label.setText("\n".join(lines))
        self.counts_label.setWordWrap(True)
        self.problems.clear()
        if cell.message:
            item = QListWidgetItem(
                icons.icon(pc.ICONS[pc.ProblemClass.ERROR], pc.colour(pc.ProblemClass.ERROR)),
                cell.message,
            )
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.problems.addItem(item)
        self.problems_title.setText("Why this value is refused")
        self.problems_title.setVisible(bool(cell.message))
        self.problems.setVisible(bool(cell.message))
        self.open_button.setText("Open the file")
        self.open_button.setVisible(True)
        self.modes_button.setVisible(False)

    def show_node(self, node: Node | None, problems: list[Problem]) -> None:
        self._cell_rel = ""
        self.problems_title.setText("Problems on this node")
        self.open_button.setText("Open")
        shown = node is not None
        self.empty.setVisible(not shown)
        self.details.setVisible(shown)
        if node is None:
            return
        self._unit_id = node.unit_id
        self.title.setText(f"{node.label}  ·  {node.ident}" if node.ident else node.label)
        self.kind_label.setText(KIND_TEXT.get(node.kind, "Group"))
        self.file_label.setText(f"File: {node.rel}" if node.rel else "")
        self.file_label.setVisible(bool(node.rel))
        self.field_label.setText(f"Field: {node.path}" if node.path else "")
        self.field_label.setVisible(bool(node.path))
        counts = pc.counts(problems)
        self.counts_label.setText(pc.summary(counts) if problems else "No problems on this node.")
        self.problems.clear()
        for problem in problems:
            cls = pc.classify(problem)
            where = problem.file or "<project>"
            if problem.line is not None:
                where += f":{problem.line}"
            item = QListWidgetItem(
                icons.icon(pc.ICONS[cls], pc.colour(cls)),
                f"{pc.LABELS[cls]}: {problem.message}\n{where}",
            )
            item.setData(PROBLEM_ROLE, (problem.file or "", problem.line or 1))
            item.setToolTip(problem.format())
            self.problems.addItem(item)
        self.problems_title.setVisible(bool(problems))
        self.problems.setVisible(bool(problems))
        self.open_button.setVisible(bool(node.rel))
        self.modes_button.setVisible(bool(self._unit_id))

    def _problem_activated(self, item: QListWidgetItem) -> None:
        file, line = item.data(PROBLEM_ROLE)
        if file:
            self.jump_requested.emit(file, int(line))
