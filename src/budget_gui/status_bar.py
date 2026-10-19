"""The status bar: what is open, when it last ran, which version, what could not be checked.

Messages about an action (`showMessage`) take the left side and go away. Four segments stay on
the right: the project folder, the time of the last run, the program version, and a link that
says how many findings are "not checked" (placeholders); it lists them in the Problems panel.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QPushButton, QStatusBar

from budget_core import __version__
from budget_gui import icons, theme


class AppStatusBar(QStatusBar):
    not_checked_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setSizeGripEnabled(False)
        self.not_checked = QPushButton("")
        self.not_checked.setProperty("kind", "link")
        self.not_checked.setFlat(True)
        self.not_checked.setVisible(False)
        self.not_checked.setCursor(Qt.CursorShape.PointingHandCursor)
        self.not_checked.clicked.connect(self.not_checked_requested)
        self.offline = QLabel(" Offline")
        self.offline.setProperty("role", "muted")
        self.offline.setToolTip(
            "This program makes no network connections: no cloud, no telemetry, no updates."
        )
        self._offline_icon = QLabel()
        theme.manager().changed.connect(self._retint)
        self._retint()
        self.path_label = QLabel("No project open")
        self.path_label.setFont(theme.mono_font())
        self.path_label.setProperty("role", "muted")
        self.last_run_label = QLabel("")
        self.last_run_label.setProperty("role", "muted")
        self.version_label = QLabel(f"Version {__version__}")
        self.version_label.setProperty("role", "muted")
        for widget in (
            self.not_checked,
            self._offline_icon,
            self.offline,
            self.path_label,
            self.last_run_label,
            self.version_label,
        ):
            self.addPermanentWidget(widget)

    def _retint(self) -> None:
        size = theme.px(theme.ICON_UI)
        icon = icons.icon("wifi-off", theme.tokens().text_secondary)
        self._offline_icon.setPixmap(icon.pixmap(size, size))
        self._offline_icon.setToolTip(self.offline.toolTip())

    def set_project_path(self, path: Path | None) -> None:
        if path is None:
            self.path_label.setText("No project open")
            self.path_label.setToolTip("")
            return
        text = str(path)
        if len(text) > 60:  # keep the end: the folder name matters most
            text = "…" + text[-59:]
        self.path_label.setText(text)
        self.path_label.setToolTip(str(path))

    def set_last_run(self, when: datetime | None) -> None:
        if when is None:
            self.last_run_label.setText("")
            self.last_run_label.setToolTip("")
            return
        self.last_run_label.setText(f"Last run {when:%H:%M:%S}")
        self.last_run_label.setToolTip(
            "When the budgets, the scenario, the power timeline or the link passes were last "
            f"worked out: {when:%Y-%m-%d %H:%M:%S}."
        )

    def set_not_checked(self, count: int) -> None:
        """'N not checked': findings that say a result could not be worked out (placeholders)."""
        self.not_checked.setVisible(count > 0)
        self.not_checked.setText(f"{count} not checked")
        self.not_checked.setToolTip(
            f"{count} finding{'s' if count != 1 else ''} say that a result could not be checked "
            "because an input is a placeholder or missing (the result shows n/a). "
            "Click to list them in the Problems panel."
        )
