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

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QWidget

from budget_gui import icons, theme
from budget_gui.components import Button, Card, icon_button

UNIT, MODE, SCENARIO, RUN = "unit", "mode", "scenario", "run"


@dataclass(frozen=True)
class StepText:
    key: str
    title: str
    hint: str
    button: str
    shortcut: str
    needs: str  # what must be done first, in words (the tip of a button that cannot be pressed yet)


STEP_TEXTS: tuple[StepText, ...] = (
    StepText(
        UNIT,
        "Add a unit",
        "A unit is one piece of hardware on the spacecraft, for example a transmitter or a "
        "battery.",
        "Add unit…",
        "Ctrl+Shift+N",
        "",
    ),
    StepText(
        MODE,
        "Add a spacecraft mode",
        "A spacecraft mode says what every unit is doing at a time, for example safe or science.",
        "Add mode…",
        "Ctrl+Shift+M",
        "Add a unit first.",
    ),
    StepText(
        SCENARIO,
        "Add an orbit and a scenario",
        "A scenario is a stretch of time on an orbit. It gives the eclipses and the power "
        "timeline.",
        "Add scenario…",
        "Ctrl+Shift+O",
        "Add a spacecraft mode first.",
    ),
    StepText(
        RUN,
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
    """The card above the work area. It only draws and says which button was pressed."""

    step_requested = Signal(str)
    hide_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setAccessibleName("Start here")
        self.title = QLabel("Start here")
        self.title.setProperty("role", "title")
        self.lead = QLabel("Four steps take a new project to its first result.")
        self.lead.setProperty("role", "muted")
        self.hide_button = icon_button("x", "Hide this panel (Help > Start here shows it again)")
        self.hide_button.clicked.connect(self.hide_requested)
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(theme.gap(1))
        top.addWidget(self.title)
        top.addWidget(self.lead, 1)
        top.addWidget(self.hide_button)
        self.body.addLayout(top)
        self._icons: dict[str, QLabel] = {}
        self._labels: dict[str, QLabel] = {}
        self._hints: dict[str, QLabel] = {}
        self.buttons: dict[str, Button] = {}
        steps = QWidget()
        grid = QGridLayout(steps)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(theme.gap(2))
        grid.setVerticalSpacing(theme.gap(1))
        grid.setColumnStretch(2, 1)  # the hint takes the room; icon, title and button align
        for row, text in enumerate(STEP_TEXTS):
            icon = QLabel()
            label = QLabel(f"{row + 1}. {text.title}")
            hint = QLabel(text.hint)
            hint.setProperty("role", "muted")
            hint.setWordWrap(True)
            button = Button(text.button, "secondary", shortcut=text.shortcut)
            button.setAccessibleName(f"{text.title}: {text.button}")
            button.clicked.connect(
                lambda _checked=False, key=text.key: self.step_requested.emit(key)
            )
            grid.addWidget(icon, row, 0)
            grid.addWidget(label, row, 1)
            grid.addWidget(hint, row, 2)
            grid.addWidget(button, row, 3)
            self._icons[text.key] = icon
            self._labels[text.key] = label
            self._hints[text.key] = hint
            self.buttons[text.key] = button
        self.body.addWidget(steps)
        self._done: frozenset[str] = frozenset()
        theme.manager().changed.connect(self._retint)
        self.set_progress(Progress(frozenset()))

    def set_progress(self, state: Progress) -> None:
        self._done = state.done
        current = state.current
        self.title.setText("Start here" if current is not None else "Start here: all done")
        self.lead.setText(
            "Four steps take a new project to its first result."
            if current is not None
            else "Everything is set up. Edit the model, press Run again, or hide this panel."
        )
        for text in STEP_TEXTS:
            key = text.key
            done = key in state.done
            # only the step to do now explains itself: the others are one line
            self._hints[key].setVisible(key == current)
            button = self.buttons[key]
            button.setVisible(not done or key == RUN and current is None)
            can = state.can_start(key)
            button.setEnabled(can)
            button.set_kind("primary" if key == current else "secondary")
            button.set_tip(text.needs if not can else "", "" if not can else text.shortcut)
            word = "done" if done else "to do"
            self._icons[key].setAccessibleName(word)
            self._labels[key].setAccessibleName(f"{text.title}, {word}")
        self._retint()

    def _retint(self) -> None:
        tokens = theme.tokens()
        size = theme.px(theme.ICON_UI)
        for key, label in self._icons.items():
            done = key in self._done
            name = "circle-check" if done else "circle-dashed"
            colour = tokens.status(theme.Status.PASS).fg if done else tokens.text_muted
            label.setPixmap(icons.icon(name, colour).pixmap(size, size))
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def step_keys(self) -> tuple[str, ...]:
        return tuple(self._icons)

    def done_keys(self) -> Collection[str]:
        return self._done
