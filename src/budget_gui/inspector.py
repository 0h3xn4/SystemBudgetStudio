"""The Inspector: what is known about the selected node of the project tree.

This first version shows where the node lives (file and field), the problems that belong to it by
class, and buttons to open it. The field-level help, unit, placeholder switch, allowed
range and "where used" are built from the model schemas in the step that makes the model editable.

For a number in an entity file the Inspector also shows where it came from and lets the user
record it (D-213): the source, a note and a status, for this input or for the whole file. The
Inspector only gathers the text; the window writes it as one undo step.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from budget_core.model.annotations import DEFAULT_KEY, INPUT_STATUSES, ProvenanceEntry
from budget_core.problems import Problem
from budget_gui import icons, theme
from budget_gui import problem_class as pc
from budget_gui.components import Button, EmptyState, SegmentedControl
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


STATUS_TEXT = {
    "sourced": "Sourced",
    "estimate": "Estimate",
    "illustrative": "Illustrative (invented)",
    "tbd": "To be determined",
}
SCOPE_INPUT, SCOPE_FILE = "input", "file"


@dataclass(frozen=True)
class SourceInfo:
    """What the file records about the source of the number under the cursor: the entry written
    for exactly this input (its key and entry) and the entry for the whole file."""

    path: str  # the input, written to survive edits (modes[imaging].avg_power_w)
    own: tuple[str, ProvenanceEntry] | None = None
    default: ProvenanceEntry | None = None


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
    source: SourceInfo | None = None  # the source of the number, when its file can record one


class InspectorPanel(QWidget):
    open_requested = Signal()  # open the node (file or field) in an editor
    open_file_requested = Signal(str)  # open the file of the cell that has the cursor
    modes_requested = Signal(str)  # open the power-mode table of a unit
    jump_requested = Signal(str, int)  # a problem: file and line
    source_requested = Signal(str, str, object)  # file, key, entry (None: remove the entry)

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
        self.empty = EmptyState(
            "Select a node of the project tree, or a cell of a grid, to see where it lives and "
            "what is wrong with it.",
            icon="info",
        )
        self.source_title = QLabel("Source")
        self.source_title.setProperty("role", "section-title")
        self.source_summary = QLabel("")
        self.source_summary.setProperty("role", "muted")
        self.source_summary.setWordWrap(True)
        self.source_scope = SegmentedControl(
            [(SCOPE_INPUT, "This input"), (SCOPE_FILE, "Whole file")], current=SCOPE_INPUT
        )
        self.source_scope.setToolTip(
            "An entry for this input, or the default for every number of the file that has none"
        )
        self.source_edit = QLineEdit()
        self.source_edit.setPlaceholderText("Where the number comes from")
        self.source_edit.setAccessibleName("Source")
        self.note_edit = QLineEdit()
        self.note_edit.setPlaceholderText("Note (optional)")
        self.note_edit.setAccessibleName("Note on the source")
        self.status_combo = QComboBox()
        self.status_combo.setAccessibleName("Status of the number")
        for status in INPUT_STATUSES:
            self.status_combo.addItem(STATUS_TEXT[status], status)
        self.source_set = Button("Set source", compact=True, tip="Record this source")
        self.source_remove = Button(
            "Remove", "ghost", compact=True, tip="Remove the recorded source"
        )
        self.source_box = QWidget()
        source_layout = QVBoxLayout(self.source_box)
        source_layout.setContentsMargins(0, 0, 0, 0)
        source_layout.setSpacing(theme.gap(1))
        source_buttons = QHBoxLayout()
        source_buttons.setSpacing(theme.gap(1))
        source_buttons.addWidget(self.source_set)
        source_buttons.addWidget(self.source_remove)
        source_buttons.addStretch(1)
        source_widgets: tuple[QWidget, ...] = (
            self.source_title,
            self.source_summary,
            self.source_scope,
            self.source_edit,
            self.note_edit,
            self.status_combo,
        )
        for source_widget in source_widgets:
            source_layout.addWidget(source_widget)
        source_layout.addLayout(source_buttons)
        self.open_button = Button("Open", compact=True)
        self.modes_button = Button("Edit power modes…", compact=True)

        buttons = QHBoxLayout()
        buttons.setSpacing(theme.gap(1))
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
            self.source_box,
            self.problems_title,
        ):
            details.addWidget(widget)
        details.addWidget(self.problems, 3)
        details.addStretch(1)  # what is shown stays at the top when there is no list of problems
        details.addLayout(buttons)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*theme.inset(2, 1))
        layout.addWidget(self.empty)
        layout.addWidget(self.details, 1)

        self._unit_id = ""
        self._cell_rel = ""
        self._source: SourceInfo | None = None
        self.source_scope.changed.connect(lambda _key: self._fill_source())
        self.source_set.clicked.connect(self._set_source)
        self.source_remove.clicked.connect(self._remove_source)
        self.source_edit.returnPressed.connect(self._set_source)
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
        self._show_source(cell.source)

    def show_node(self, node: Node | None, problems: list[Problem]) -> None:
        self._cell_rel = ""
        self._show_source(None)
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

    # ---- the source of the number under the cursor ---------------------------------------------
    def _show_source(self, info: SourceInfo | None) -> None:
        self._source = info
        self.source_box.setVisible(info is not None)
        if info is None:
            return
        own_scope = info.own is not None or info.default is None
        self.source_scope.blockSignals(True)
        self.source_scope.set_current(SCOPE_INPUT if own_scope else SCOPE_FILE)
        self.source_scope.blockSignals(False)
        self._fill_source()

    def _scope_entry(self) -> tuple[str, ProvenanceEntry | None]:
        """The key and the entry of the scope that is chosen."""
        info = self._source
        assert info is not None
        if self.source_scope.current() == SCOPE_FILE:
            return DEFAULT_KEY, info.default
        if info.own is not None:
            return info.own[0], info.own[1]
        return info.path, None

    def _fill_source(self) -> None:
        info = self._source
        if info is None:
            return
        key, entry = self._scope_entry()
        self.source_edit.setText(entry.source if entry else "")
        self.note_edit.setText(entry.note if entry else "")
        self.status_combo.setCurrentIndex(
            self.status_combo.findData(entry.status if entry else "sourced")
        )
        self.source_remove.setEnabled(entry is not None)
        if entry is not None:
            where = "the whole file" if key == DEFAULT_KEY else "this input"
            self.source_summary.setText(f"Recorded for {where}.")
        elif info.own is None and info.default is not None:
            self.source_summary.setText("This input follows the entry for the whole file.")
        else:
            self.source_summary.setText("No source is recorded for this input.")

    def _set_source(self) -> None:
        if self._source is None:
            return
        text = self.source_edit.text().strip()
        if not text:
            self.source_summary.setText("Write where the number comes from, or use Remove.")
            return
        key, _entry = self._scope_entry()
        entry = ProvenanceEntry(
            source=text,
            note=self.note_edit.text().strip(),
            status=self.status_combo.currentData(),
        )
        self.source_requested.emit(self._cell_rel, key, entry)

    def _remove_source(self) -> None:
        if self._source is None:
            return
        key, entry = self._scope_entry()
        if entry is not None:
            self.source_requested.emit(self._cell_rel, key, None)

    def _problem_activated(self, item: QListWidgetItem) -> None:
        file, line = item.data(PROBLEM_ROLE)
        if file:
            self.jump_requested.emit(file, int(line))
