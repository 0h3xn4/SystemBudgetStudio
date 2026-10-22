"""The top bar: project · revision · unsaved marker · scenario · BOL/EOL · Run · run status.

The scenario and the case (beginning or end of life) are chosen here once and apply to every tab
that has them; the tabs keep no selector of their own. *Run* is the one primary button of the
window (the accent colour is used for nothing else): it works out the scenario, the power
timeline and the link passes of the selected scenario. The chip says in a word, with an icon, where
the results stand.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QPainter, QPaintEvent, QPalette
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from budget_gui import icons, theme
from budget_gui.components import SegmentedControl
from budget_gui.run_controller import STATE_TEXT, RunState

CASES = ("BOL", "EOL")
RUN_TIP = (
    "Work out the scenario, the power timeline and the link passes of the selected "
    "scenario (Ctrl+R). The static budgets are always up to date."
)
CHIP_ICON = {
    RunState.NOT_RUN: "circle-minus",
    RunState.RUNNING: "refresh-cw",
    RunState.OK: "circle-check",
    RunState.STALE: "triangle-alert",
    RunState.FAILED: "circle-x",
}


class ElidedLabel(QLabel):
    """A label that gives up width before anything else does: a long project name ends in an
    ellipsis (the whole name is the tooltip) instead of forcing the window wide."""

    def __init__(self) -> None:
        super().__init__()
        self._full = ""

    def setText(self, text: str) -> None:  # noqa: N802 (Qt naming)
        self._full = text
        super().setText(text)
        self.setToolTip(text)

    def minimumSizeHint(self) -> QSize:  # noqa: N802 (Qt naming)
        return QSize(48, super().minimumSizeHint().height())

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 (Qt naming)
        painter = QPainter(self)
        painter.setFont(self.font())
        painter.setPen(self.palette().color(QPalette.ColorRole.WindowText))
        elided = self.fontMetrics().elidedText(
            self._full, Qt.TextElideMode.ElideRight, self.width()
        )
        painter.drawText(
            self.rect(), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), elided
        )


class StatusChip(QFrame):
    """An icon and a word on the tint of the status: never colour alone."""

    ICON = 16

    def __init__(self) -> None:
        super().__init__()
        self.setProperty("role", "chip")
        self._icon = QLabel()
        self._icon.setFixedSize(QSize(self.ICON, self.ICON))
        self._text = QLabel()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(theme.gap(1), theme.gap(0), theme.gap(2), theme.gap(0))
        layout.setSpacing(theme.gap(0))
        layout.addWidget(self._icon)
        layout.addWidget(self._text)
        self._state = RunState.NOT_RUN
        self._detail = ""
        self.set_state(RunState.NOT_RUN)
        theme.manager().changed.connect(self._retint)

    @property
    def state(self) -> RunState:
        return self._state

    def text(self) -> str:
        return self._text.text()

    def set_state(self, state: RunState, detail: str = "", tooltip: str = "") -> None:
        self._state, self._detail = state, detail
        self.setProperty("state", state.value)
        self._text.setText(STATE_TEXT[state] + (f" · {detail}" if detail else ""))
        self.setToolTip(tooltip)
        self._retint()

    def _retint(self) -> None:
        colour, _tint = theme.chip_colours(theme.tokens(), self._state.value)
        self._icon.setPixmap(
            icons.icon(CHIP_ICON[self._state], colour).pixmap(self.ICON, self.ICON)
        )
        self.style().unpolish(self)
        self.style().polish(self)


class TopBar(QWidget):
    scenario_chosen = Signal(str)
    case_chosen = Signal(str)
    run_requested = Signal()
    cancel_requested = Signal()  # Run was pressed while a run is in progress

    def __init__(self) -> None:
        super().__init__()
        self.name_label = ElidedLabel()
        self.name_label.setText("No project open")
        self.name_label.setProperty("role", "title")
        self.revision_label = QLabel("")
        self.revision_label.setProperty("role", "muted")
        self.revision_label.setFont(theme.mono_font())
        self.dirty_label = QLabel("")
        self.dirty_label.setToolTip("Some files or tables have changes that are not saved yet.")

        self.scenario_combo = QComboBox()
        self.scenario_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.scenario_combo.setMinimumContentsLength(12)
        self.scenario_combo.setToolTip(
            "The scenario every tab shows (Model > Scenario, Power > Timeline, Link > Passes)."
        )
        # one pill with the chosen case raised in it (the shared component)
        self.case_control = SegmentedControl([(case, case) for case in CASES], current="BOL")
        self.case_buttons: dict[str, QPushButton] = {}
        for case in CASES:
            button = self.case_control.button(case)
            button.setToolTip(
                {
                    "BOL": "Beginning of life: the solar array and battery as new.",
                    "EOL": "End of life: with the degradation over the design life.",
                }[case]
            )
            self.case_buttons[case] = button
            button.clicked.connect(lambda _checked=False, c=case: self.case_chosen.emit(c))

        self.run_button = QPushButton("Run")
        self.run_button.setProperty("kind", "primary")
        self.run_button.setIcon(icons.icon("play", theme.tokens().text_on_accent))
        self.run_button.setToolTip(RUN_TIP)
        self.run_button.setEnabled(False)
        self.chip = StatusChip()

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # busy: how long it takes is not known
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(theme.px(theme.PROGRESS_HEIGHT))
        self.progress.hide()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        layout = QHBoxLayout()
        layout.setContentsMargins(*theme.inset(2, 1))
        layout.setSpacing(theme.gap(1))
        outer.addLayout(layout)
        outer.addWidget(self.progress)
        layout.addWidget(self.name_label)
        layout.addWidget(self.revision_label)
        layout.addWidget(self.dirty_label)
        layout.addStretch(1)
        layout.addWidget(QLabel("Scenario"))
        layout.addWidget(self.scenario_combo)
        layout.addWidget(self.case_control)
        layout.addWidget(self.run_button)
        layout.addWidget(self.chip)
        self.scenario_combo.activated.connect(
            lambda _i: self.scenario_chosen.emit(self.scenario_combo.currentText())
        )
        self.run_button.clicked.connect(self._run_clicked)
        theme.manager().changed.connect(self._retint)

    # ---- state -------------------------------------------------------------------------------
    def set_project(self, name: str, revision: str) -> None:
        self.name_label.setText(name or "No project open")
        self.revision_label.setText(f"rev {revision}" if revision else "")

    def set_dirty(self, dirty: bool) -> None:
        if dirty:
            self.dirty_label.setText("● Unsaved changes")
            self.dirty_label.setProperty("role", "dirty")
        else:
            self.dirty_label.setText("")
        self.dirty_label.style().unpolish(self.dirty_label)
        self.dirty_label.style().polish(self.dirty_label)

    def set_scenarios(self, ids: list[str], selected: str) -> None:
        self.scenario_combo.blockSignals(True)
        self.scenario_combo.clear()
        self.scenario_combo.addItems(ids)
        if selected in ids:
            self.scenario_combo.setCurrentText(selected)
        self.scenario_combo.blockSignals(False)
        self.scenario_combo.setEnabled(bool(ids))

    def set_scenario(self, scenario_id: str) -> None:
        self.scenario_combo.blockSignals(True)
        self.scenario_combo.setCurrentText(scenario_id)
        self.scenario_combo.blockSignals(False)

    def set_case(self, case: str) -> None:
        button = self.case_buttons.get(case.upper())
        if button is not None:
            button.setChecked(True)

    def case(self) -> str:
        return next(c for c, b in self.case_buttons.items() if b.isChecked())

    def _run_clicked(self) -> None:
        if self.chip.state is RunState.RUNNING:
            self.cancel_requested.emit()
        else:
            self.run_requested.emit()

    def set_run_state(
        self,
        state: RunState,
        can_run: bool,
        detail: str = "",
        tip: str = "",
        cancelling: bool = False,
    ) -> None:
        """While a run is in progress the Run button is Cancel (and a thin bar runs under the top
        bar); it waits, disabled, once the cancel has been asked for."""
        self.chip.set_state(state, detail, tip)
        running = state is RunState.RUNNING
        self.progress.setVisible(running)
        self.run_button.setProperty("kind", "secondary" if running else "primary")
        self.run_button.setText(("Cancelling…" if cancelling else "Cancel") if running else "Run")
        self.run_button.setToolTip(
            "Stop the run. The results shown now stay as they are (Ctrl+R)." if running else RUN_TIP
        )
        self.run_button.setEnabled(not cancelling if running else can_run)
        self._retint()
        self.run_button.style().unpolish(self.run_button)
        self.run_button.style().polish(self.run_button)

    def _retint(self) -> None:
        if self.chip.state is RunState.RUNNING:
            self.run_button.setIcon(icons.icon("circle-x", theme.tokens().text))
            return
        self.run_button.setIcon(icons.icon("play", theme.tokens().text_on_accent))
