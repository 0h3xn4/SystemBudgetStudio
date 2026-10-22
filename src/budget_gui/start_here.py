"""The *Start here* panel: what to do next in a project that is not finished yet (D-190).

A blank project opens to empty pages and a person who has not read the manual does not know where
to begin. The panel lists the four steps that take it to a first result (a unit, a spacecraft mode,
an orbit with a scenario, save and run) and puts one button on each. A step is done when the files
say so; the first step that is not done is the one to do now and carries the one accent. The panel
is shown while a project has an open step, can be hidden (the choice is kept in `layout.ini`) and
comes back with *Help > Start here*. It holds no number and reads no project content.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass

from PySide6.QtCore import QSize, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy

from budget_gui import icons, theme
from budget_gui.components import Button, Card, icon_button

UNIT, MODE, SCENARIO, RUN = "unit", "mode", "scenario", "run"


@dataclass(frozen=True)
class StepText:
    key: str
    title: str
    chip: str  # the short name on the step's small button
    hint: str
    button: str
    shortcut: str
    needs: str  # what must be done first, in words (the tip of a button that cannot be pressed yet)


STEP_TEXTS: tuple[StepText, ...] = (
    StepText(
        UNIT,
        "Add a unit",
        "Unit",
        "A unit is one piece of hardware on the spacecraft, for example a transmitter or a "
        "battery.",
        "Add unit…",
        "Ctrl+Shift+N",
        "",
    ),
    StepText(
        MODE,
        "Add a spacecraft mode",
        "Spacecraft mode",
        "A spacecraft mode says what every unit is doing at a time, for example safe or science.",
        "Add mode…",
        "Ctrl+Shift+M",
        "Add a unit first.",
    ),
    StepText(
        SCENARIO,
        "Add an orbit and a scenario",
        "Orbit and scenario",
        "A scenario is a stretch of time on an orbit. It gives the eclipses and the power "
        "timeline.",
        "Add scenario…",
        "Ctrl+Shift+O",
        "Add a spacecraft mode first.",
    ),
    StepText(
        RUN,
        "Save and run",
        "Save and run",
        "Saving writes the files of the project. Run works out the budgets from them.",
        "Save and run",
        "Ctrl+R",
        "Add a scenario first.",
    ),
)


@dataclass(frozen=True)
class Progress:
    """Which steps are done: derived from the files of the project and the state of the run."""

    done: frozenset[str]

    @property
    def current(self) -> str | None:
        """The first step that is not done, or None when all four are."""
        for text in STEP_TEXTS:
            if text.key not in self.done:
                return text.key
        return None

    @property
    def finished(self) -> bool:
        return self.current is None

    def can_start(self, key: str) -> bool:
        """A step can be started when every step before it is done."""
        for text in STEP_TEXTS:
            if text.key == key:
                return True
            if text.key not in self.done:
                return False
        return False


def progress(*, units: int, modes: int, scenarios: int, saved: bool, ran: bool) -> Progress:
    """The steps done for a project with that many unit, spacecraft mode and scenario files (the
    ones on screen, edits included), no unsaved edit (`saved`) and a run that is up to date."""
    done: set[str] = set()
    if units > 0:
        done.add(UNIT)
    if modes > 0:
        done.add(MODE)
    if scenarios > 0:
        done.add(SCENARIO)
    if scenarios > 0 and saved and ran:
        done.add(RUN)
    return Progress(frozenset(done))


class StartHerePanel(Card):
    """The card above the work area. It only draws and says which button was pressed.

    Two lines: the four steps as small buttons with their state, and under them what the step to
    do now means, with its one primary button. It can be squeezed to nothing (a short window gives
    its room to the work area), so it never raises the minimum size of the window."""

    step_requested = Signal(str)
    hide_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setAccessibleName("Start here")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self.title = QLabel("Start here")
        self.title.setProperty("role", "title")
        self.hide_button = icon_button("x", "Hide this panel (Help > Start here shows it again)")
        self.hide_button.clicked.connect(self.hide_requested)
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(theme.gap(1))
        top.addWidget(self.title)
        top.addSpacing(theme.gap(1))
        self.buttons: dict[str, Button] = {}
        for number, text in enumerate(STEP_TEXTS, start=1):
            chip = Button(f"{number}  {text.chip}", "ghost", icon="circle-dashed")
            chip.clicked.connect(lambda _checked=False, key=text.key: self.step_requested.emit(key))
            top.addWidget(chip)
            self.buttons[text.key] = chip
        top.addStretch(1)
        top.addWidget(self.hide_button)
        self.body.addLayout(top)
        self.hint = QLabel()
        self.hint.setProperty("role", "muted")
        self.hint.setWordWrap(True)
        self.next_button = Button("", "primary")
        self.next_button.clicked.connect(self._next_clicked)
        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)
        bottom.setSpacing(theme.gap(2))
        bottom.addWidget(self.hint, 1)
        bottom.addWidget(self.next_button)
        self.body.addLayout(bottom)
        self._done: frozenset[str] = frozenset()
        self._current: str | None = UNIT
        theme.manager().changed.connect(self._retint)
        self.set_progress(Progress(frozenset()))

    def minimumSizeHint(self) -> QSize:  # noqa: N802 (Qt naming)
        return QSize(super().minimumSizeHint().width(), 0)

    def _next_clicked(self) -> None:
        if self._current is not None:
            self.step_requested.emit(self._current)

    def set_progress(self, state: Progress) -> None:
        self._done = state.done
        current = self._current = state.current
        self.title.setText("Start here" if current is not None else "Start here: all done")
        for text in STEP_TEXTS:
            key = text.key
            can = state.can_start(key)
            button = self.buttons[key]
            button.setEnabled(can)
            word = "done" if key in state.done else "to do"
            button.setAccessibleName(f"{text.title}, {word}")
            button.set_tip(text.hint if can else text.needs, text.shortcut if can else "")
        step = next((t for t in STEP_TEXTS if t.key == current), None)
        if step is None:
            self.hint.setText(
                "Everything is set up. Edit the model, press Run again, or hide this panel."
            )
            self.next_button.hide()
        else:
            self.hint.setText(f"{step.title}. {step.hint}")
            self.next_button.setText(step.button)
            self.next_button.setAccessibleName(f"{step.title}: {step.button}")
            self.next_button.set_tip("", step.shortcut)
            self.next_button.show()
        self._retint()

    def _retint(self) -> None:
        tokens = theme.tokens()
        for key, button in self.buttons.items():
            done = key in self._done
            name = "circle-check" if done else "circle-dashed"
            colour = tokens.status(theme.Status.PASS).fg if done else tokens.text_secondary
            button.setIcon(icons.icon(name, colour))

    def step_keys(self) -> tuple[str, ...]:
        return tuple(self.buttons)

    def done_keys(self) -> Collection[str]:
        return self._done
