"""The form of *Remove from project* (D-201): which expendable, ground station, imaging target or
link to remove.

The kinds that have no item are not offered. An item that a scenario or a link still names is
listed with the reason (the window works it out), and *Remove* stays off for it, as the removal of
a spacecraft mode does for a mode that a scenario names. The file is deleted when the project is
saved, after the usual question; until then Undo brings it back.
"""

from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from budget_core.remove_item import KINDS, LABELS
from budget_gui import theme
from budget_gui.components import Button


class RemoveItemDialog(QDialog):
    """`items` maps a kind to its ids, each with the reason it cannot be removed ("" if none)."""

    def __init__(
        self, items: Mapping[str, Mapping[str, str]], parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Remove from project")
        self._items = {kind: dict(items[kind]) for kind in KINDS if items.get(kind)}

        self.kind_combo = QComboBox()
        self.kind_combo.setAccessibleName("Kind of item to remove")
        for kind in self._items:
            self.kind_combo.addItem(LABELS[kind], kind)
        self.id_combo = QComboBox()
        self.id_combo.setAccessibleName("Item to remove")

        form = QFormLayout()
        form.setHorizontalSpacing(theme.gap(2))
        form.setVerticalSpacing(theme.gap(1))
        form.addRow("Kind", self.kind_combo)
        form.addRow("Name", self.id_combo)

        intro = QLabel(
            "The file is deleted when you save the project, after a question; Undo (Ctrl+Z) "
            "brings it back until then. An item that a scenario or a link names cannot be "
            "removed: change those first."
        )
        intro.setWordWrap(True)
        intro.setProperty("role", "muted")
        self.note_label = QLabel("")
        self.note_label.setWordWrap(True)
        self.note_label.setProperty("role", "error")
        self.remove_button = Button("Remove", "danger")
        cancel = Button("Cancel")
        self.remove_button.clicked.connect(self.accept)
        cancel.setDefault(True)
        cancel.clicked.connect(self.reject)
        buttons = QHBoxLayout()
        buttons.setSpacing(theme.gap(1))
        buttons.addStretch(1)
        buttons.addWidget(cancel)
        buttons.addWidget(self.remove_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*theme.inset(3))
        layout.setSpacing(theme.gap(2))
        layout.addWidget(intro)
        layout.addLayout(form)
        layout.addWidget(self.note_label)
        layout.addLayout(buttons)

        self.kind_combo.currentIndexChanged.connect(self._kind_changed)
        self.id_combo.currentIndexChanged.connect(self._refresh)
        self.resize(*theme.scaled(theme.PALETTE_SIZE))
        self._kind_changed()

    def choice(self) -> tuple[str, str]:
        """The kind and the id that are chosen."""
        return str(self.kind_combo.currentData()), self.id_combo.currentText()

    def _kind_changed(self, *_args: object) -> None:
        self.id_combo.blockSignals(True)
        self.id_combo.clear()
        kind = self.kind_combo.currentData()
        if kind in self._items:
            self.id_combo.addItems(sorted(self._items[kind]))
        self.id_combo.blockSignals(False)
        self._refresh()

    def _refresh(self, *_args: object) -> None:
        kind, item_id = self.choice()
        reason = self._items.get(kind, {}).get(item_id, "")
        self.note_label.setText(reason)
        self.remove_button.setEnabled(bool(item_id) and not reason)
