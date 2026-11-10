# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""The landing page: what the window shows while no project is open (D-166, D-269).

The program always starts here, also when it was started with a folder (a pinned taskbar icon or a
double-clicked project keeps that folder in its command): the folder is offered, not opened. From
here the engineer opens a project folder, starts a new one with the guided steps, opens a copy of
an example, imports an IDM-CIC model, opens the user guide, or picks one of the recent projects
when that list is switched on (it is off by default: the tool keeps no path of the user's projects
unless asked, D-150, `recent_projects.py`).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMenu, QVBoxLayout, QWidget

from budget_core import APP_NAME
from budget_core.disclaimer import DISCLAIMER
from budget_gui import theme
from budget_gui.components import Button, Card

# the examples offered on the landing page, in this order, with what each one shows
EXAMPLE_TITLES: dict[str, str] = {
    "microsat_250kg_eps": "250 kg satellite with complete power and thermal inputs",
    "microsat_250kg_clean": "250 kg satellite with every input filled in (no warnings)",
    "microsat_250kg": "250 kg satellite with placeholders (what an early project looks like)",
    "microsat_150kg": "150 kg satellite with two links and mission phases",
    "stress_200_units": "200 units and a one-week scenario (performance check)",
}


def _muted(text: str, *, centred: bool = True) -> QLabel:
    label = QLabel(text)
    label.setProperty("role", "muted")
    label.setWordWrap(True)
    if centred:
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return label


def _row(*widgets: QWidget) -> QHBoxLayout:
    row = QHBoxLayout()
    row.setSpacing(theme.gap(1))
    row.addStretch(1)
    for widget in widgets:
        row.addWidget(widget)
    row.addStretch(1)
    return row


class WelcomePage(QWidget):
    open_requested = Signal()
    new_requested = Signal()
    example_requested = Signal(str)  # a key of EXAMPLE_TITLES
    import_requested = Signal()
    guide_requested = Signal()
    folder_requested = Signal(Path)  # the launch folder or a recent project
    clear_recent_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._launch_folder: Path | None = None
        title = QLabel(APP_NAME)
        title.setProperty("role", "heading")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lead = _muted(
            "Power, mass, thermal and link budgets of one spacecraft model. "
            "Everything stays on this computer."
        )

        # the folder the program was started with: offered, never opened by itself
        self.launch_card = Card()
        self.launch_label = QLabel()
        self.launch_label.setWordWrap(True)
        self.launch_button = Button("Open this folder", "secondary")
        self.launch_button.setAccessibleName("Open the folder the program was started with")
        self.launch_button.clicked.connect(self._open_launch_folder)
        launch_row = QHBoxLayout()
        launch_row.addWidget(self.launch_label, 1)
        launch_row.addWidget(self.launch_button)
        self.launch_card.body.addLayout(launch_row)
        self.launch_card.hide()

        self.open_button = Button(
            "Open a project folder…", "primary", tip="Open a project folder", shortcut="Ctrl+O"
        )
        self.new_button = Button(
            "New project (guided)…",
            "secondary",
            tip="Start a project with the guided steps",
            shortcut="Ctrl+N",
        )
        self.example_button = Button(
            "Open an example…",
            "secondary",
            tip="Write a copy of an example project (invented data) to a folder and open it",
        )
        self.import_button = Button(
            "Import IDM-CIC model…", "secondary", tip="Start or update a project from an IDM model"
        )
        self.guide_button = Button(
            "User guide", "ghost", tip="Open the user guide (it works offline)", shortcut="F1"
        )
        self.open_button.clicked.connect(self.open_requested)
        self.new_button.clicked.connect(self.new_requested)
        self.import_button.clicked.connect(self.import_requested)
        self.guide_button.clicked.connect(self.guide_requested)
        self.example_menu = QMenu(self)
        for key, text in EXAMPLE_TITLES.items():
            action = self.example_menu.addAction(text)
            action.setData(key)
            action.triggered.connect(lambda _checked=False, k=key: self.example_requested.emit(k))
        self.example_button.setMenu(self.example_menu)

        # recent projects: only when the user switched the list on (Settings)
        self.recent_card = Card()
        recent_layout = self.recent_card.body
        heading = QHBoxLayout()
        recent_title = QLabel("Recent projects")
        recent_title.setProperty("role", "title")
        self.clear_recent_button = Button(
            "Clear", "ghost", compact=True, tip="Forget the list of recent projects"
        )
        self.clear_recent_button.clicked.connect(self.clear_recent_requested)
        heading.addWidget(recent_title, 1)
        heading.addWidget(self.clear_recent_button)
        recent_layout.addLayout(heading)
        self.recent_list = QVBoxLayout()
        self.recent_list.setSpacing(theme.gap(0))
        recent_layout.addLayout(self.recent_list)
        self.recent_buttons: list[Button] = []
        self.recent_card.hide()

        hint = _muted("or drop a project folder on this window")
        self.disclaimer = _muted(DISCLAIMER)
        self.disclaimer.setAccessibleName("Disclaimer")
        keys = _muted("Ctrl+O open · Ctrl+N new · Ctrl+K find a command · F1 user guide")

        column = QVBoxLayout()
        column.setSpacing(theme.gap(2))
        column.addWidget(title)
        column.addWidget(lead)
        column.addWidget(self.launch_card)
        column.addLayout(_row(self.open_button, self.new_button))
        column.addLayout(_row(self.example_button, self.import_button, self.guide_button))
        column.addWidget(hint)
        column.addWidget(self.recent_card)
        centre = QHBoxLayout()
        centre.addStretch(1)
        centre.addLayout(column, 4)
        centre.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*theme.inset(5))
        layout.setSpacing(theme.gap(2))
        layout.addStretch(2)
        layout.addLayout(centre)
        layout.addStretch(3)
        layout.addWidget(self.disclaimer)
        layout.addWidget(keys)

    # ---- the folder the program was started with --------------------------------------------
    @property
    def launch_folder(self) -> Path | None:
        return self._launch_folder

    def set_launch_folder(self, folder: Path | None) -> None:
        """Offer the folder the program was started with (None: no offer)."""
        self._launch_folder = folder
        if folder is None:
            self.launch_card.hide()
            return
        self.launch_label.setText(f"The program was started with the folder {folder.name}.")
        self.launch_label.setToolTip(str(folder))
        self.launch_card.show()

    def _open_launch_folder(self) -> None:
        if self._launch_folder is not None:
            self.folder_requested.emit(self._launch_folder)

    # ---- recent projects ---------------------------------------------------------------------
    def set_recent(self, folders: list[Path]) -> None:
        """Show these folders (newest first); an empty list hides the card."""
        for button in self.recent_buttons:
            self.recent_list.removeWidget(button)
            button.hide()  # deleteLater waits for the event loop; until then it must not show
            button.deleteLater()
        self.recent_buttons = []
        for folder in folders:
            button = Button(folder.name or str(folder), "ghost", tip=str(folder))
            button.setAccessibleName(f"Open recent project {folder.name}")
            button.clicked.connect(lambda _checked=False, f=folder: self.folder_requested.emit(f))
            self.recent_list.addWidget(button, 0, Qt.AlignmentFlag.AlignLeft)
            self.recent_buttons.append(button)
        self.recent_card.setVisible(bool(folders))
