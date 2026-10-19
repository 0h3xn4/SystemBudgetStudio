"""The navigation rail: the seven areas of the window as icons with labels, down the left side.

It replaces the row of tabs (D-173). The rail shows one area at a time, offers the command
palette, the project panel, the settings and the help at the bottom, and folds to icons only.
It knows nothing about the pages: it says which destination was chosen and the window shows it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from budget_gui import icons, theme


@dataclass(frozen=True)
class Destination:
    title: str
    icon: str
    tip: str  # what is there, for the tooltip
    shortcut: str = ""


DESTINATIONS = (
    Destination(
        "Model", "boxes", "Units, power modes, inputs, the scenario and the files", "Ctrl+1"
    ),
    Destination("Power", "zap", "The power budget and the power timeline", "Ctrl+2"),
    Destination("Mass", "weight", "The mass budget and the centre of gravity", "Ctrl+3"),
    Destination("Thermal", "thermometer", "The thermal budget", "Ctrl+4"),
    Destination("Link", "radio-tower", "The link budget and the passes", "Ctrl+5"),
    Destination("Compare", "git-compare", "Compare two revisions or two scenarios", "Ctrl+6"),
    Destination("Reports", "file-output", "Write the budgets to files", "Ctrl+7"),
)


class RailButton(QToolButton):
    """An icon and a label; the label goes when the rail is folded (the tooltip keeps it)."""

    def __init__(self, title: str, icon: str, tip: str, shortcut: str = "", *, checkable: bool):
        super().__init__()
        self.title = title
        self.icon_name = icon
        self.setText(title)
        self.setCheckable(checkable)
        self.setProperty("role", "rail-button")
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setIconSize(QSize(theme.px(theme.ICON_RAIL), theme.px(theme.ICON_RAIL)))
        label = f"{title} ({shortcut})" if shortcut else title
        self.setToolTip(f"{label}: {tip}" if tip else label)
        self.setAccessibleName(title)
        self.retint()

    def retint(self) -> None:
        t = theme.tokens()
        self.setIcon(icons.toggle_icon(self.icon_name, t.text_secondary, t.accent_text))

    def set_folded(self, folded: bool) -> None:
        style = (
            Qt.ToolButtonStyle.ToolButtonIconOnly
            if folded
            else Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        self.setToolButtonStyle(style)


class NavRail(QFrame):
    destination_chosen = Signal(int)
    find_requested = Signal()
    project_toggled = Signal(bool)
    settings_requested = Signal()
    help_requested = Signal()
    folded_changed = Signal(bool)

    def __init__(self, destinations: Sequence[Destination] = DESTINATIONS) -> None:
        super().__init__()
        self.setProperty("role", "rail")
        self._folded = False
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self.buttons: list[RailButton] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(theme.gap(1), theme.gap(1), theme.gap(1), theme.gap(1))
        layout.setSpacing(theme.gap(0))
        self.project_button = RailButton(
            "Project", "panel-left", "Show or hide the project panel", "Ctrl+B", checkable=True
        )
        self.project_button.setProperty("toggle", True)  # on or off, not a place
        self.project_button.setChecked(True)
        self.project_button.toggled.connect(self.project_toggled)
        layout.addWidget(self.project_button)
        layout.addSpacing(theme.gap(1))
        for index, destination in enumerate(destinations):
            button = RailButton(
                destination.title,
                destination.icon,
                destination.tip,
                destination.shortcut,
                checkable=True,
            )
            self._group.addButton(button, index)
            self.buttons.append(button)
            layout.addWidget(button)
        layout.addStretch(1)
        self.find_button = RailButton(
            "Find",
            "search",
            "Find a command, a unit, a file or a problem",
            "Ctrl+K",
            checkable=False,
        )
        self.settings_button = RailButton(
            "Settings", "settings", "Theme, UI size and motion", checkable=False
        )
        self.help_button = RailButton(
            "Help", "circle-help", "The user guide", "F1", checkable=False
        )
        self.fold_button = RailButton(
            "Fold", "chevrons-left", "Show only the icons", checkable=False
        )
        for button in (self.find_button, self.settings_button, self.help_button, self.fold_button):
            layout.addWidget(button)
        self.find_button.clicked.connect(self.find_requested)
        self.settings_button.clicked.connect(self.settings_requested)
        self.help_button.clicked.connect(self.help_requested)
        self.fold_button.clicked.connect(self.toggle_folded)
        self._group.idClicked.connect(self.destination_chosen)
        self.buttons[0].setChecked(True)
        theme.manager().changed.connect(self._retint)
        self._apply_width()

    # ---- state -------------------------------------------------------------------------------
    @property
    def folded(self) -> bool:
        return self._folded

    def current(self) -> int:
        return self._group.checkedId()

    def set_current(self, index: int) -> None:
        """Show `index` as the chosen destination (no signal: the window already shows it)."""
        if 0 <= index < len(self.buttons):
            self.buttons[index].setChecked(True)

    def set_enabled_destinations(self, enabled: bool) -> None:
        """The destinations wait for a project; the find, settings and help buttons never do."""
        for button in self.buttons:
            button.setEnabled(enabled)
        self.project_button.setEnabled(enabled)

    def set_project_checked(self, checked: bool) -> None:
        """Follow the project panel when it is shown or hidden elsewhere (no signal)."""
        self.project_button.blockSignals(True)
        self.project_button.setChecked(checked)
        self.project_button.blockSignals(False)

    def toggle_folded(self) -> None:
        self.set_folded(not self._folded)

    def set_folded(self, folded: bool) -> None:
        if folded == self._folded:
            return
        self._folded = folded
        self._apply_width()
        self.folded_changed.emit(folded)

    def _apply_width(self) -> None:
        every = [*self.buttons, self.project_button, self.find_button, self.settings_button]
        every += [self.help_button, self.fold_button]
        for button in every:
            button.set_folded(self._folded)
        self.fold_button.setToolTip("Show the labels" if self._folded else "Show only the icons")
        self.fold_button.icon_name = "chevrons-right" if self._folded else "chevrons-left"
        self.fold_button.setText("" if self._folded else "Fold")
        self.fold_button.retint()
        self.setFixedWidth(theme.px(theme.RAIL_COLLAPSED if self._folded else theme.RAIL_WIDTH))

    def _retint(self) -> None:
        every = [*self.buttons, self.project_button, self.find_button, self.settings_button]
        for button in [*every, self.help_button, self.fold_button]:
            button.retint()

    def rail_widget(self) -> QWidget:
        return self
