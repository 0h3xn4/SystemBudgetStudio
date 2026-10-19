"""The Reports tab: what to write, in which formats, where, with the provenance first (D-165).

One page in place of three File-menu commands with a folder dialog each. The page lists what can
be exported (the static budgets, the power timeline, the scenario results) with the state of each
(ready, not worked out yet, out of date), the formats, the folder; it shows the provenance that
every file will carry before anything is written, a progress bar while the files are made, and the
list of the files written with a button that shows their folder. A refusal is a disabled button
with the reason in its tooltip, not a message box.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from budget_core.provenance import Provenance
from budget_core.reports.run import REPORT_KINDS
from budget_gui import icons, theme
from budget_gui.components import Button, EmptyState
from budget_gui.theme import Status

FORMAT_TIPS = {
    "xlsx": "A workbook with one sheet per table.",
    "pdf": "A printable report with the figures.",
    "docx": "An editable Word report.",
    "json": "Every number, for other programs.",
    "csv": "One file per table, for a spreadsheet or a script.",
}
PROVENANCE_ROWS = ("Tool", "Project", "Project revision", "Scenario", "Generated (UTC)", "User")
READY_TEXT = "Ready"


@dataclass(frozen=True)
class ReportItem:
    """One thing that can be exported and where it stands."""

    key: str  # "budgets", "timeline" or "scenario"
    title: str
    detail: str  # which files it writes
    status: Status
    status_text: str
    ready: bool
    formats: bool = True  # False: its files are fixed (the format choice does not apply)


class ReportsView(QWidget):
    export_requested = Signal(object, object, str)  # item keys, formats, folder

    def __init__(self) -> None:
        super().__init__()
        self._items: list[ReportItem] = []
        self._boxes: dict[str, QCheckBox] = {}
        self._state_icons: dict[str, tuple[QLabel, QLabel]] = {}
        self._busy = False
        self._wanted: dict[str, bool] = {}  # what the user ticked, kept while an item is not ready
        self._written: list[str] = []

        title = QLabel("Reports")
        title.setProperty("role", "heading")
        intro = QLabel(
            "Write the budgets of the open project to a folder. Every file carries the provenance "
            "below, so it can be traced to its run."
        )
        intro.setWordWrap(True)
        intro.setProperty("role", "muted")

        # The provenance is the one of the Provenance panel: a line says it, the rows are one
        # click away and are not repeated in a table that is always open (D-180).
        self.provenance_summary = QLabel("")
        self.provenance_summary.setWordWrap(True)
        self.provenance_summary.setFont(theme.mono_font(theme.TYPE_SMALL))
        self.provenance_summary.setProperty("role", "muted")
        self.provenance_toggle = Button("Show details", "ghost", compact=True)
        self.provenance_toggle.clicked.connect(self._toggle_provenance)
        self.provenance_table = QTableWidget(0, 2)
        self.provenance_table.setHorizontalHeaderLabels(["Item", "Value"])
        self.provenance_table.verticalHeader().setVisible(False)
        self.provenance_table.horizontalHeader().setStretchLastSection(True)
        self.provenance_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.provenance_table.setTabKeyNavigation(False)  # Tab leaves a read-only table
        self.provenance_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.provenance_table.hide()

        self.items_grid = QGridLayout()
        self.items_grid.setHorizontalSpacing(theme.gap(3))
        self.format_boxes: dict[str, QCheckBox] = {}
        formats = QHBoxLayout()
        for kind in REPORT_KINDS:
            box = QCheckBox(kind.upper())
            box.setChecked(True)
            box.setToolTip(FORMAT_TIPS[kind])
            box.toggled.connect(self._update_button)
            self.format_boxes[kind] = box
            formats.addWidget(box)
        formats.addStretch(1)

        self.folder_edit = QLineEdit()
        self.folder_edit.setPlaceholderText("Folder to write the files into")
        self.folder_edit.setAccessibleName("Folder to write the files into")
        self.folder_edit.textChanged.connect(self._update_button)
        self.browse_button = Button("Browse…", icon="folder-open")
        self.browse_button.clicked.connect(self._browse)
        self.export_button = Button("Export", "primary", icon="file-output")
        self.export_button.clicked.connect(self._export)
        folder_row = QHBoxLayout()
        folder_row.addWidget(self.folder_edit, 1)
        folder_row.addWidget(self.browse_button)
        folder_row.addWidget(self.export_button)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # busy: the time it takes is not known
        self.progress.setMaximumHeight(theme.px(theme.PROGRESS_HEIGHT))
        self.progress.setTextVisible(False)
        self.progress.hide()
        self.status = QLabel("")
        self.status.setWordWrap(True)

        self.results = QTableWidget(0, 2)
        self.results.setHorizontalHeaderLabels(["File written", "Folder"])
        self.results.verticalHeader().setVisible(False)
        self.results.horizontalHeader().setStretchLastSection(True)
        self.results.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.results.setTabKeyNavigation(False)
        self.reveal_button = Button("Show the folder", icon="folder-open")
        self.reveal_button.setEnabled(False)
        self.reveal_button.clicked.connect(self.reveal)
        self.results_empty = EmptyState(  # nothing written yet: a line, not an empty table
            "Nothing written yet. Choose what to export and a folder, then press Export.",
            icon="file-output",
        )
        self.results.hide()
        self.reveal_button.hide()

        page = QWidget()  # in a scroll area, so a low window can still show the whole page
        layout = QVBoxLayout(page)
        layout.setContentsMargins(*theme.inset(3))
        layout.setSpacing(theme.gap(2))
        layout.addWidget(title)
        layout.addWidget(intro)
        provenance_row = QHBoxLayout()
        provenance_row.addWidget(self._heading("Provenance (written into every file)"), 1)
        provenance_row.addWidget(self.provenance_toggle)
        layout.addLayout(provenance_row)
        layout.addWidget(self.provenance_summary)
        layout.addWidget(self.provenance_table)
        layout.addWidget(self._heading("What to export"))
        layout.addLayout(self.items_grid)
        layout.addWidget(self._heading("Formats"))
        layout.addLayout(formats)
        layout.addWidget(self._heading("Where"))
        layout.addLayout(folder_row)
        layout.addWidget(self.progress)
        layout.addWidget(self.status)
        layout.addWidget(self.results, 1)
        layout.addWidget(self.results_empty, 1)
        layout.addWidget(self.reveal_button, 0, Qt.AlignmentFlag.AlignLeft)
        self.results.setMinimumHeight(theme.px(theme.RESULTS_MIN_HEIGHT))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(page)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        theme.manager().changed.connect(self._theme_changed)
        self.set_items([])
        self.set_provenance(None)

    @staticmethod
    def _heading(text: str) -> QLabel:
        label = QLabel(text)
        label.setProperty("role", "section-title")
        return label

    # ---- what the page shows -----------------------------------------------------------------
    def set_provenance(self, provenance: Provenance | None) -> None:
        rows = [
            (n, v) for n, v in (provenance.rows() if provenance else []) if n in PROVENANCE_ROWS
        ]
        self.provenance_table.setRowCount(len(rows))
        for i, (name, value) in enumerate(rows):
            for column, text in enumerate((name, value)):
                item = QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if column == 1:
                    item.setFont(theme.mono_font())
                self.provenance_table.setItem(i, column, item)
        self.provenance_table.resizeRowsToContents()
        height = self.provenance_table.horizontalHeader().height() + 2 * theme.px(theme.BORDER)
        height += sum(self.provenance_table.rowHeight(r) for r in range(len(rows)))
        self.provenance_table.setFixedHeight(height)  # all rows, no scroll bar of its own
        values = dict(rows)
        revision = f"revision {values['Project revision']}" if "Project revision" in values else ""
        self.provenance_summary.setText(
            " · ".join(
                v
                for v in (
                    values.get("Tool"),
                    values.get("Project"),
                    revision,
                    values.get("Scenario"),
                )
                if v
            )
            or "Open a project to see the provenance every file will carry."
        )
        self.provenance_toggle.setEnabled(bool(rows))
        if not rows:
            self.provenance_table.hide()
            self.provenance_toggle.setText("Show details")

    def _toggle_provenance(self) -> None:
        show = self.provenance_table.isHidden()
        self.provenance_table.setVisible(show)
        self.provenance_toggle.setText("Hide details" if show else "Show details")

    def set_items(self, items: list[ReportItem]) -> None:
        """Show what can be exported. What the user ticked or unticked is remembered; an item that
        is not ready cannot be ticked."""
        self._items = list(items)
        while self.items_grid.count():
            widget = self.items_grid.takeAt(0).widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self._boxes, self._state_icons = {}, {}
        for row, item in enumerate(items):
            box = QCheckBox(item.title)
            box.setEnabled(item.ready and not self._busy)
            box.setChecked(item.ready and self._wanted.get(item.key, True))
            box.toggled.connect(lambda on, key=item.key: self._ticked(key, on))
            detail = QLabel(item.detail)
            detail.setProperty("role", "muted")
            mark, text = QLabel(), QLabel()
            holder = QWidget()
            holder_layout = QHBoxLayout(holder)
            holder_layout.setContentsMargins(0, 0, 0, 0)
            holder_layout.setSpacing(theme.gap(1))
            holder_layout.addWidget(mark)
            holder_layout.addWidget(text, 1)
            self._boxes[item.key] = box
            self._state_icons[item.key] = (mark, text)
            self.items_grid.addWidget(box, row, 0)
            self.items_grid.addWidget(detail, row, 1)
            self.items_grid.addWidget(holder, row, 2)
        self._paint_states()
        self._update_button()

    def _paint_states(self) -> None:
        tokens = theme.tokens()
        for item in self._items:
            labels = self._state_icons.get(item.key)
            if labels is None:
                continue
            mark, text = labels
            mark.setPixmap(icons.status_icon(item.status, tokens).pixmap(14, 14))
            text.setText(item.status_text)
            for label in labels:
                label.setToolTip(theme.STATUS_LABELS[item.status])

    def _theme_changed(self) -> None:
        self._paint_states()

    # ---- choosing ----------------------------------------------------------------------------
    def _ticked(self, key: str, on: bool) -> None:
        box = self._boxes.get(key)
        if box is not None and box.isEnabled():  # not the unticking of an item that is not ready
            self._wanted[key] = on
        self._update_button()

    def selected_items(self) -> set[str]:
        return {key for key, box in self._boxes.items() if box.isChecked() and box.isEnabled()}

    def selected_formats(self) -> set[str]:
        return {kind for kind, box in self.format_boxes.items() if box.isChecked()}

    def folder(self) -> str:
        return self.folder_edit.text().strip()

    def set_folder(self, folder: Path | str) -> None:
        self.folder_edit.setText(str(folder))

    def _browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose the folder for the reports")
        if folder:
            self.set_folder(folder)

    def refusal(self) -> str:
        """Why Export does nothing now, or "" when it will write."""
        if self._busy:
            return "The files are being written."
        if not any(item.ready for item in self._items):
            return "Nothing is ready to export. Fix the errors, then press Run."
        selected = self.selected_items()
        if not selected:
            return "Tick what to export."
        needs_formats = any(i.formats for i in self._items if i.key in selected)
        if needs_formats and not self.selected_formats():
            return "Tick at least one format."
        if not self.folder():
            return "Choose the folder to write into."
        return ""

    def _update_button(self) -> None:
        reason = self.refusal()
        self.export_button.setEnabled(not reason)
        self.export_button.setToolTip(reason or "Write the files into the folder.")

    def _export(self) -> None:
        if self.refusal():
            return
        self.export_requested.emit(self.selected_items(), self.selected_formats(), self.folder())

    # ---- while and after writing -------------------------------------------------------------
    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.progress.setVisible(busy)
        for item in self._items:
            box = self._boxes.get(item.key)
            if box is not None:
                box.setEnabled(item.ready and not busy)
        self.browse_button.setEnabled(not busy)
        if busy:
            self.status.setText("Writing the files…")
            self.results.setRowCount(0)
            self._written = []
            self.reveal_button.setEnabled(False)
            self._show_results_table(False)
        self._update_button()

    def show_results(self, paths: list[str]) -> None:
        self._written = list(paths)
        self.results.setRowCount(len(paths))
        for i, path in enumerate(paths):
            location = Path(path)
            for column, text in enumerate((location.name, str(location.parent))):
                item = QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if column == 0:
                    item.setFont(theme.mono_font())
                self.results.setItem(i, column, item)
        self.results.resizeColumnToContents(0)
        self.reveal_button.setEnabled(bool(paths))
        self._show_results_table(bool(paths))
        self.status.setText(
            f"Wrote {len(paths)} file{'s' if len(paths) != 1 else ''}." if paths else "No files."
        )

    def _show_results_table(self, shown: bool) -> None:
        self.results.setVisible(shown)
        self.reveal_button.setVisible(shown)
        self.results_empty.setVisible(not shown)

    def show_failure(self, message: str) -> None:
        self.status.setText(message)

    def reveal(self) -> None:
        """Show the folder of the files just written in the system's file manager."""
        if self._written:
            folder = Path(self._written[0]).parent
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
