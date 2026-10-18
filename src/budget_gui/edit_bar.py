"""The row of buttons every editing page has: Undo, Redo, Save (and the cell-styles legend)."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from budget_gui import icons, theme
from budget_gui.model_document import ModelDocument


class EditBar(QWidget):
    """Undo and Redo of the shared document (their tooltips name the step), Save, and, when the
    page shows cells, the legend. Icons are made again when the theme changes."""

    save_requested = Signal()
    legend_requested = Signal()

    def __init__(self, document: ModelDocument, *, legend: bool = True) -> None:
        super().__init__()
        self.document = document
        self._icon_names: dict[QPushButton, str] = {}
        self.undo_button = self.make_button("Undo", "undo-2", "Undo the last edit (Ctrl+Z)")
        self.redo_button = self.make_button("Redo", "redo-2", "Redo (Ctrl+Shift+Z)")
        self.save_button = QPushButton(icons.icon("save"), "Save")
        self.save_button.setToolTip("Write the changed files (Ctrl+S)")
        self._icon_names[self.save_button] = "save"
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
        theme.manager().changed.connect(self._retint)
        self.refresh()

    def make_button(self, text: str, icon: str, tip: str) -> QPushButton:
        button = QPushButton(icons.icon(icon), text)
        button.setProperty("kind", "secondary")
        button.setToolTip(tip)
        self._icon_names[button] = icon
        return button

    def refresh(self, *_args: object) -> None:
        stack = self.document.undo_stack
        try:
            can_undo, can_redo = stack.canUndo(), stack.canRedo()
        except RuntimeError:  # the document is going away with the window
            return
        self.undo_button.setEnabled(can_undo)
        self.redo_button.setEnabled(can_redo)
        self.undo_button.setToolTip(
            f"Undo: {stack.undoText()} (Ctrl+Z)" if can_undo else "Nothing to undo"
        )
        self.redo_button.setToolTip(
            f"Redo: {stack.redoText()} (Ctrl+Shift+Z)" if can_redo else "Nothing to redo"
        )

    def _retint(self) -> None:
        """Icons are tinted when they are made: make them again for the theme now in use."""
        for button, name in self._icon_names.items():
            button.setIcon(icons.icon(name))
