"""The row of buttons every editing page has: Undo, Redo, Save (and the cell-styles legend)."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QWidget

from budget_gui import theme
from budget_gui.components import Button
from budget_gui.model_document import ModelDocument


class EditBar(QWidget):
    """Undo and Redo of the shared document (their tooltips name the step), the legend of the cell
    styles when the page shows cells, and Save, the one primary action of the page (D-176). It
    sits in the toolbar above the content."""

    save_requested = Signal()
    legend_requested = Signal()

    def __init__(self, document: ModelDocument, *, legend: bool = True) -> None:
        super().__init__()
        self.document = document
        self.undo_button = self.make_button("Undo", "undo-2", "Undo the last edit", "Ctrl+Z")
        self.redo_button = self.make_button("Redo", "redo-2", "Redo", "Ctrl+Shift+Z")
        self.save_button = Button(
            "Save",
            "primary",
            icon="save",
            compact=True,
            tip="Write the changed files",
            shortcut="Ctrl+S",
        )
        self.legend_button = self.make_button(
            "Cell styles", "circle-help", "What the cell styles mean"
        )
        self.legend_button.setVisible(legend)
        self.undo_button.clicked.connect(document.undo_stack.undo)
        self.redo_button.clicked.connect(document.undo_stack.redo)
        self.save_button.clicked.connect(self.save_requested)
        self.legend_button.clicked.connect(self.legend_requested)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(theme.gap(0))
        for button in (self.undo_button, self.redo_button, self.legend_button, self.save_button):
            row.addWidget(button)
        stack = document.undo_stack
        for signal in (
            stack.canUndoChanged,
            stack.canRedoChanged,
            stack.undoTextChanged,
            stack.redoTextChanged,
        ):
            signal.connect(self.refresh)
        self.refresh()

    @staticmethod
    def make_button(text: str, icon: str, tip: str, shortcut: str = "") -> Button:
        """A compact secondary button of the toolbar; its icon follows the theme."""
        return Button(text, "secondary", icon=icon, compact=True, tip=tip, shortcut=shortcut)

    def refresh(self, *_args: object) -> None:
        stack = self.document.undo_stack
        try:
            can_undo, can_redo = stack.canUndo(), stack.canRedo()
        except RuntimeError:  # the document is going away with the window
            return
        self.undo_button.setEnabled(can_undo)
        self.redo_button.setEnabled(can_redo)
        self.undo_button.set_tip(
            f"Undo: {stack.undoText()}" if can_undo else "Nothing to undo", "Ctrl+Z"
        )
        self.redo_button.set_tip(
            f"Redo: {stack.redoText()}" if can_redo else "Nothing to redo", "Ctrl+Shift+Z"
        )
