"""The settings popover of the rail: theme, UI size, motion and single click, in one small card
(D-173, D-195).

It changes nothing itself: it says what was chosen and the window applies it and keeps it (the
same code as the View menu), so the two always agree.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import QCheckBox, QFrame, QLabel, QVBoxLayout, QWidget

from budget_gui import theme
from budget_gui.components import SegmentedControl


class SettingsPopover(QFrame):
    theme_chosen = Signal(str)  # a `theme.Mode` value
    scale_chosen = Signal(int)  # per cent
    motion_reduced = Signal(bool)
    single_click_chosen = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.Popup)
        self.setProperty("role", "raised")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*theme.inset(2))
        layout.setSpacing(theme.gap(1))
        title = QLabel("Settings")
        title.setProperty("role", "title")
        layout.addWidget(title)
        layout.addWidget(self._caption("Theme"))
        self.theme_control = SegmentedControl(
            [("light", "Light"), ("dark", "Dark"), ("system", "System")]
        )
        layout.addWidget(self.theme_control)
        layout.addWidget(self._caption("UI size"))
        self.scale_control = SegmentedControl([(str(p), f"{p} %") for p in theme.SCALES])
        layout.addWidget(self.scale_control)
        self.motion_box = QCheckBox("Reduce motion")
        layout.addWidget(self.motion_box)
        self.single_click_box = QCheckBox("Open and edit with a single click")
        self.single_click_box.setToolTip(
            "A click on a node of the project tree opens it, and a click on a selected cell of a "
            "grid edits it. Off: a double-click, Enter or F2."
        )
        layout.addWidget(self.single_click_box)
        self.theme_control.changed.connect(self.theme_chosen)
        self.scale_control.changed.connect(lambda key: self.scale_chosen.emit(int(key)))
        self.motion_box.toggled.connect(self.motion_reduced)
        self.single_click_box.toggled.connect(self.single_click_chosen)

    @staticmethod
    def _caption(text: str) -> QLabel:
        label = QLabel(text)
        label.setProperty("role", "small")
        return label

    def show_current(
        self, mode: theme.Mode, percent: int, reduced: bool, single_click: bool = False
    ) -> None:
        """Show what is in force now (the menu may have changed it) without sending a signal."""
        for control, key in ((self.theme_control, mode.value), (self.scale_control, str(percent))):
            control.blockSignals(True)
            control.set_current(key)
            control.blockSignals(False)
        self.motion_box.blockSignals(True)
        self.motion_box.setChecked(reduced)
        self.motion_box.blockSignals(False)
        self.single_click_box.blockSignals(True)
        self.single_click_box.setChecked(single_click)
        self.single_click_box.blockSignals(False)

    def open_beside(self, anchor: QWidget) -> None:
        """Open it to the right of `anchor`, its bottom edge level with the anchor's."""
        self.adjustSize()
        corner = anchor.mapToGlobal(QPoint(anchor.width(), anchor.height()))
        self.move(corner.x() + theme.gap(0), corner.y() - self.height())
        self.show()
