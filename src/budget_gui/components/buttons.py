"""Buttons in the four kinds of the design language: primary, secondary, ghost, danger (D-169).

One accent for one primary action per view. The look comes from the style sheet (`kind` and `size`
properties); this only makes a button and keeps its icon in the colour of the theme.
"""

from __future__ import annotations

from PySide6.QtCore import QObject
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QAbstractButton, QPushButton, QWidget

from budget_gui import icons, theme

KINDS = ("primary", "secondary", "ghost", "danger")


class Button(QPushButton):
    """A push button of a kind, with an optional icon and shortcut hint in its tooltip."""

    def __init__(
        self,
        text: str = "",
        kind: str = "secondary",
        *,
        icon: str | None = None,
        compact: bool = False,
        tip: str = "",
        shortcut: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        if kind not in KINDS:
            raise ValueError(f"A button is one of {', '.join(KINDS)}.")
        self._icon_name = icon
        self.setProperty("kind", kind)
        if compact:
            self.setProperty("size", "compact")
        self.set_tip(tip, shortcut)
        self._retint()
        theme.manager().changed.connect(self._retint)

    @property
    def kind(self) -> str:
        return str(self.property("kind"))

    def set_kind(self, kind: str) -> None:
        self.setProperty("kind", kind)
        self.style().unpolish(self)
        self.style().polish(self)
        self._retint()

    def set_tip(self, tip: str, shortcut: str = "") -> None:
        """The tooltip names the shortcut: keyboard first (principle 5)."""
        self.setToolTip(f"{tip} ({shortcut})" if tip and shortcut else tip or shortcut)

    def _retint(self) -> None:
        """Icons are tinted when they are made: make the icon again for the theme in use."""
        if self._icon_name is None:
            return
        t = theme.tokens()
        on_accent = self.kind in ("primary", "danger")
        colour = t.text_on_accent if on_accent else t.text_secondary
        self.setIcon(icons.icon(self._icon_name, colour))


def icon_button(
    icon: str, tip: str, *, shortcut: str = "", parent: QWidget | None = None
) -> Button:
    """A button with an icon and no text: it always has a tooltip (accessibility rule)."""
    button = Button("", "ghost", icon=icon, compact=True, tip=tip, shortcut=shortcut, parent=parent)
    button.setAccessibleName(tip)
    return button


def tinted(button: QAbstractButton, name: str, colour: str | None = None) -> QIcon:
    """The icon `name` for a button that is not a `Button`, in the colour of the theme."""
    icon = icons.icon(name, colour)
    button.setIcon(icon)
    return icon


def is_primary(widget: QObject) -> bool:
    return bool(widget.property("kind") == "primary")
