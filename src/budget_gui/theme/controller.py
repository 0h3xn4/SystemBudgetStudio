"""The theme in use: light, dark or whatever the operating system uses, the UI scale, and motion.

`ThemeManager` makes the palette and the style sheet from the tokens, applies them, follows the
operating system while the mode is `system` and tells the widgets that paint themselves (the plots,
the timeline strips) to draw again with `changed`. Switching is live: no restart.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QProxyStyle,
    QPushButton,
    QStyle,
    QStyleOption,
    QTabBar,
    QToolButton,
    QWidget,
)

from budget_core.assets import icon_files
from budget_gui.theme import scale
from budget_gui.theme.fonts import load_fonts, ui_font
from budget_gui.theme.qss import palette, stylesheet
from budget_gui.theme.tokens import DARK, LIGHT, Tokens


class Mode(StrEnum):
    """What the user chose: a fixed theme, or whatever the operating system uses."""

    LIGHT = "light"
    DARK = "dark"
    SYSTEM = "system"


def system_is_dark() -> bool:
    """True when the operating system (Qt 6.5 and later) says it uses a dark colour scheme."""
    hints = QGuiApplication.styleHints()
    return hints is not None and hints.colorScheme() == Qt.ColorScheme.Dark


class WindowStyle(QProxyStyle):
    """Fusion, with the icons of the standard message boxes drawn from the icon set of the window
    in the colour of their level (D-173): the boxes Qt makes for us look like the rest."""

    _LEVELS = {
        QStyle.StandardPixmap.SP_MessageBoxQuestion: ("circle-help", "standby"),
        QStyle.StandardPixmap.SP_MessageBoxInformation: ("info", "standby"),
        QStyle.StandardPixmap.SP_MessageBoxWarning: ("triangle-alert", "caution"),
        QStyle.StandardPixmap.SP_MessageBoxCritical: ("circle-x", "critical"),
    }

    def __init__(self) -> None:
        super().__init__("Fusion")

    def drawPrimitive(  # noqa: N802 (Qt naming)
        self,
        element: QStyle.PrimitiveElement,
        option: QStyleOption,
        painter: QPainter,
        widget: QWidget | None = None,
    ) -> None:
        """The focus rectangle of a check box, a radio button or a header is the focus ring of
        the window (2 px, the focus colour), not Fusion's dotted line. A ring painted over the
        control does not change its size, which a border of the style sheet would (D-181)."""
        if element == QStyle.PrimitiveElement.PE_FrameFocusRect:
            if isinstance(widget, QPushButton | QToolButton | QTabBar):
                return  # their style sheet draws the ring: a second one is a box in a box
            box: Any = option  # the stubs of QStyleOption lack rect
            ring = scale.px(scale.FOCUS_RING)
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(QPen(QColor(manager().tokens.focus), ring))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(
                box.rect.adjusted(ring // 2, ring // 2, -ring, -ring),
                scale.px(scale.RADIUS_CONTROL),
                scale.px(scale.RADIUS_CONTROL),
            )
            painter.restore()
            return
        super().drawPrimitive(element, option, painter, widget)

    def standardIcon(  # noqa: N802 (Qt naming)
        self,
        standard_icon: QStyle.StandardPixmap,
        option: object = None,
        widget: object = None,
    ) -> QIcon:
        found = self._LEVELS.get(standard_icon)
        if found is None:
            return super().standardIcon(standard_icon, option, widget)  # type: ignore[arg-type]
        from budget_gui import icons  # here: the icons need the theme, which imports this module

        name, level = found
        return icons.icon(name, getattr(manager().tokens, level).fg)


class ThemeManager(QObject):
    """The theme in use. Widgets that paint with `tokens()` connect to `changed` to draw again."""

    changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._mode = Mode.LIGHT
        self._tokens = LIGHT
        self._hooked = False
        self._reduce_motion = False
        self._style: WindowStyle | None = None

    @property
    def mode(self) -> Mode:
        return self._mode

    @property
    def tokens(self) -> Tokens:
        return self._tokens

    @property
    def scale_percent(self) -> int:
        return scale.scale_percent()

    @property
    def reduce_motion(self) -> bool:
        """True when animations are off: the user asked for it, or there is no screen (the tests
        run offscreen)."""
        return self._reduce_motion or QGuiApplication.platformName() == "offscreen"

    @property
    def reduce_motion_setting(self) -> bool:
        """What the user chose (*Reduce motion*), not counting the screenless platform."""
        return self._reduce_motion

    def motion_ms(self, index: int = 0) -> int:
        """The duration of an animation in ms (0 when motion is reduced); `index` 0 is the
        shorter, 1 the longer of the two durations of the design language."""
        return 0 if self.reduce_motion else scale.MOTION_MS[min(index, 1)]

    def set_reduce_motion(self, value: bool) -> None:
        self._reduce_motion = bool(value)
        self.changed.emit()

    def set_mode(self, mode: Mode | str, app: QApplication | None = None) -> None:
        self._mode = Mode(mode) if not isinstance(mode, Mode) else mode
        self.apply(app)

    def set_scale(self, percent: int, app: QApplication | None = None) -> None:
        scale.set_scale_percent(percent)
        self.apply(app)

    def _resolve(self) -> Tokens:
        if self._mode is Mode.LIGHT:
            return LIGHT
        if self._mode is Mode.DARK:
            return DARK
        return DARK if system_is_dark() else LIGHT

    def apply(self, app: QApplication | None = None) -> None:
        app = app or QApplication.instance()  # type: ignore[assignment]
        self._tokens = self._resolve()
        if isinstance(app, QApplication):
            if not self._hooked and app.styleHints() is not None:
                app.styleHints().colorSchemeChanged.connect(self._system_changed)
                self._hooked = True
            if self._style is None:  # one look on every platform, coloured by the palette
                self._style = WindowStyle()
                app.setStyle(self._style)
            app.setPalette(palette(self._tokens))
            app.setFont(ui_font())
            app.setStyleSheet(stylesheet(self._tokens))
        self.changed.emit()

    def _system_changed(self, *_args: object) -> None:
        if self._mode is Mode.SYSTEM:
            self.apply()


_MANAGER: ThemeManager | None = None


def manager() -> ThemeManager:
    global _MANAGER
    if _MANAGER is None:
        _MANAGER = ThemeManager()
    return _MANAGER


def tokens() -> Tokens:
    """The tokens of the theme in use."""
    return manager().tokens


def app_icon() -> QIcon:
    """The application icon (D-148): PNG files of 16 to 256 px, so no SVG plugin is needed. An
    empty icon when the files are missing; the window still opens."""
    icon = QIcon()
    for path in icon_files():
        icon.addFile(str(path))
    return icon


def apply_theme(app: QApplication, name: Mode | str = Mode.LIGHT) -> None:
    """Load the fonts and apply the theme (`light`, `dark` or `system`)."""
    load_fonts()
    manager().set_mode(name, app)


__all__ = ["Mode", "ThemeManager", "apply_theme", "app_icon", "manager", "system_is_dark", "tokens"]
