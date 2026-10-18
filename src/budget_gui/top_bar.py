"""The top bar: project · revision · unsaved marker · scenario · BOL/EOL · Run · run status.

The scenario and the case (beginning or end of life) are chosen here once and apply to every tab
that has them; the tabs keep no selector of their own. *Run* is the one primary button of the
window (the accent colour is used for nothing else): it works out the scenario, the power
timeline and the link passes of the selected scenario. The chip says in a word, with an icon, where
the results stand.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from budget_gui import icons, theme
from budget_gui.run_controller import STATE_TEXT, RunState

CASES = ("BOL", "EOL")
CHIP_ICON = {
    RunState.NOT_RUN: "circle-minus",
    RunState.RUNNING: "refresh-cw",
    RunState.OK: "circle-check",
    RunState.STALE: "triangle-alert",
    RunState.FAILED: "circle-x",
}


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
        layout.setContentsMargins(8, 2, 10, 2)
        layout.setSpacing(4)
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
        self.setStyleSheet("")  # the rule of the theme applies; see `theme.stylesheet`
        self.style().unpolish(self)
        self.style().polish(self)


class TopBar(QWidget):
    scenario_chosen = Signal(str)
    case_chosen = Signal(str)
    run_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.name_label = QLabel("No project open")
        self.name_label.setProperty("role", "title")
        self.revision_label = QLabel("")
        self.revision_label.setProperty("role", "muted")
        self.revision_label.setFont(theme.mono_font())
        self.dirty_label = QLabel("")
        self.dirty_label.setToolTip("Some files or tables have changes that are not saved yet.")

        self.scenario_combo = QComboBox()
        self.scenario_combo.setMinimumContentsLength(10)
        self.scenario_combo.setToolTip(
            "The scenario every tab shows (Model > Scenario, Power > Timeline, Link > Passes)."
        )
        self.case_buttons: dict[str, QPushButton] = {}
        group = QButtonGroup(self)
        group.setExclusive(True)
        for case in CASES:
            button = QPushButton(case)
            button.setCheckable(True)
            button.setProperty("kind", "secondary")
            button.setToolTip(
                {
                    "BOL": "Beginning of life: the solar array and battery as new.",
                    "EOL": "End of life: with the degradation over the design life.",
                }[case]
            )
            group.addButton(button)
            self.case_buttons[case] = button
            button.clicked.connect(lambda _checked=False, c=case: self.case_chosen.emit(c))
        self.case_buttons["BOL"].setChecked(True)

        self.run_button = QPushButton("Run")
        self.run_button.setIcon(icons.icon("play", theme.tokens().text_on_accent))
        self.run_button.setToolTip(
            "Work out the scenario, the power timeline and the link passes of the selected "
            "scenario (Ctrl+R). The static budgets are always up to date."
        )
        self.run_button.setEnabled(False)
        self.chip = StatusChip()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(12)
        layout.addWidget(self.name_label)
        layout.addWidget(self.revision_label)
        layout.addWidget(self.dirty_label)
        layout.addStretch(1)
        layout.addWidget(QLabel("Scenario"))
        layout.addWidget(self.scenario_combo)
        case_row = QHBoxLayout()
        case_row.setSpacing(0)
        for button in self.case_buttons.values():
            case_row.addWidget(button)
        layout.addLayout(case_row)
        layout.addWidget(self.run_button)
        layout.addWidget(self.chip)
        self.scenario_combo.activated.connect(
            lambda _i: self.scenario_chosen.emit(self.scenario_combo.currentText())
        )
        self.run_button.clicked.connect(self.run_requested)
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

    def set_run_state(
        self, state: RunState, can_run: bool, detail: str = "", tip: str = ""
    ) -> None:
        self.chip.set_state(state, detail, tip)
        self.run_button.setEnabled(can_run)

    def _retint(self) -> None:
        self.run_button.setIcon(icons.icon("play", theme.tokens().text_on_accent))
