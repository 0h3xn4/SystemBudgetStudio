"""The command palette, Ctrl+K: type a few words, press Enter (D-166).

One list of everything the window can do or go to: the menu commands, the units, the files, the
scenarios and the problems of the open project. The words typed must all appear in a command, in
any order and case; the nearest to the start comes first. Up and Down move in the list while the
cursor stays in the field; Enter runs the command; Esc closes.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout

MAX_SHOWN = 60


@dataclass(frozen=True)
class Command:
    text: str  # what is searched and shown
    run: Callable[[], object]
    hint: str = ""  # a shortcut, or the kind of thing ("unit", "file")


def rank(query: str, commands: list[Command]) -> list[Command]:
    """The commands that contain every word of the query, the nearest to the start first (then
    the shortest). An empty query lists the commands in the order they were given."""
    words = query.lower().split()
    if not words:
        return list(commands)
    scored: list[tuple[int, int, int, Command]] = []
    for position, command in enumerate(commands):
        haystack = f"{command.text} {command.hint}".lower()
        spots = [haystack.find(word) for word in words]
        if min(spots) < 0:
            continue
        scored.append((sum(spots), len(command.text), position, command))
    scored.sort(key=lambda item: item[:3])
    return [item[3] for item in scored]


class CommandPalette(QDialog):
    def __init__(self, commands: list[Command], parent: object = None) -> None:
        super().__init__(parent)  # type: ignore[arg-type]
        self.setWindowTitle("Find a command")
        self.setModal(True)
        self.resize(560, 420)
        self._commands = list(commands)
        self._shown: list[Command] = []
        self.field = QLineEdit()
        self.field.setPlaceholderText("Type to find a command, a unit, a file or a problem")
        self.field.setClearButtonEnabled(True)
        self.listing = QListWidget()
        self.listing.setTabKeyNavigation(False)
        self.listing.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # the keys stay in the field
        self.empty = QLabel("Nothing matches.")
        self.empty.setProperty("role", "muted")
        layout = QVBoxLayout(self)
        layout.addWidget(self.field)
        layout.addWidget(self.listing, 1)
        layout.addWidget(self.empty)
        self.field.textChanged.connect(self._filter)
        self.listing.itemActivated.connect(lambda _item: self.run_current())
        self.listing.itemClicked.connect(lambda _item: self.run_current())
        self._filter("")

    def _filter(self, text: str) -> None:
        self._shown = rank(text, self._commands)[:MAX_SHOWN]
        self.listing.clear()
        for command in self._shown:
            label = f"{command.text}    [{command.hint}]" if command.hint else command.text
            self.listing.addItem(QListWidgetItem(label))
        if self._shown:
            self.listing.setCurrentRow(0)
        self.empty.setVisible(not self._shown)

    def shown(self) -> list[str]:
        return [c.text for c in self._shown]

    def run_current(self) -> None:
        row = self.listing.currentRow()
        if 0 <= row < len(self._shown):
            command = self._shown[row]
            self.accept()  # close first: the command may open a dialog of its own
            command.run()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 (Qt naming)
        key = event.key()
        if key in (Qt.Key.Key_Down, Qt.Key.Key_Up):
            step = 1 if key == Qt.Key.Key_Down else -1
            row = min(max(self.listing.currentRow() + step, 0), self.listing.count() - 1)
            self.listing.setCurrentRow(row)
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.run_current()
        else:
            super().keyPressEvent(event)
