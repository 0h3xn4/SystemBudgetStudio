"""User-interface icons: black PNG masks of Lucide icons, tinted with the colour of the theme.

One file per size serves every theme and every status colour, because the colour is applied when
the icon is made (D-150). The icon of a status is always drawn together with text or in a place
that has text, so colour is never the only carrier of its meaning.
"""

from __future__ import annotations

from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPixmap

from budget_core.assets import ui_icon_files
from budget_gui import theme
from budget_gui.theme import Status

_CACHE: dict[tuple[str, int], QIcon] = {}


def _tinted(path: str, colour: QColor) -> QPixmap:
    mask = QImage(path)
    if mask.isNull():
        return QPixmap()
    image = mask.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    painter = QPainter(image)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(image.rect(), colour)
    painter.end()
    return QPixmap.fromImage(image)


def icon(name: str, colour: str | QColor | None = None) -> QIcon:
    """The icon `name` in `colour` (default: the text colour of the theme in use). An empty icon
    when the files are missing; a missing icon never stops the window."""
    tint = QColor(colour) if colour is not None else QColor(theme.tokens().text)
    key = (name, tint.rgba())
    cached = _CACHE.get(key)
    if cached is not None:
        return cached
    result = QIcon()
    for path in ui_icon_files(name).values():
        tinted = _tinted(str(path), tint)
        if not tinted.isNull():
            result.addPixmap(tinted)
    _CACHE[key] = result
    return result


def toggle_icon(name: str, off: str | QColor, on: str | QColor) -> QIcon:
    """The icon `name` of a checkable button: in `off` when unchecked, in `on` when checked."""
    key = (f"{name}|toggle", QColor(off).rgba() ^ (QColor(on).rgba() << 1))
    cached = _CACHE.get(key)
    if cached is not None:
        return cached
    result = QIcon()
    for path in ui_icon_files(name).values():
        for colour, state in ((off, QIcon.State.Off), (on, QIcon.State.On)):
            tinted = _tinted(str(path), QColor(colour))
            if not tinted.isNull():
                result.addPixmap(tinted, QIcon.Mode.Normal, state)
                result.addPixmap(tinted, QIcon.Mode.Active, state)
    _CACHE[key] = result
    return result


def status_icon(status: Status, tokens: theme.Tokens | None = None) -> QIcon:
    """The icon of a status in the colour of that status."""
    t = tokens or theme.tokens()
    return icon(theme.STATUS_ICONS[status], t.status(status).fg)


def pixmap(name: str, size: int, colour: str | QColor | None = None) -> QPixmap:
    return icon(name, colour).pixmap(QSize(size, size))


def clear_cache() -> None:
    _CACHE.clear()
