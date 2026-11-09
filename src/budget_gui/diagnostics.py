# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""What Qt knows about the machine, for `system-budget-studio --diagnose` (D-257).

No project is opened and nothing is read from a project: the report names the Qt and PySide6
versions, the platform plugin, the screens, whether the bundled fonts and icons loaded and which
layout file would be read. It is a support aid for a window that does not look or behave right
on somebody else's computer.
"""

from __future__ import annotations

from pathlib import Path

from PySide6 import __version__ as pyside_version
from PySide6.QtCore import qVersion
from PySide6.QtGui import QAccessible, QFontInfo, QImage, QImageReader
from PySide6.QtWidgets import QApplication

from budget_core.assets import ui_icon_files
from budget_core.diagnostics import environment_lines
from budget_gui import theme
from budget_gui.icons import icon, toggle_icon
from budget_gui.layout_settings import default_path
from budget_gui.theme.fonts import FONT_MONO, FONT_UI, load_fonts


def qt_lines(app: QApplication) -> list[str]:
    lines = [
        f"Qt {qVersion()}, PySide6 {pyside_version}, platform plugin '{app.platformName()}', "
        f"style '{app.style().objectName()}'",
        f"Colour scheme: {app.styleHints().colorScheme().name}; UI scale {theme.scale_percent()} %",
    ]
    for number, screen in enumerate(app.screens(), start=1):
        size = screen.size()
        lines.append(
            f"Screen {number}: {size.width()} x {size.height()}, pixel ratio "
            f"{screen.devicePixelRatio():g}, {screen.logicalDotsPerInch():.0f} dpi"
        )
    families = load_fonts()
    lines.append(f"Bundled font families registered: {', '.join(families) or 'NONE'}")
    lines.append(
        f"Text font in use: {QFontInfo(theme.ui_font()).family()} (wanted {FONT_UI}); "
        f"number font: {QFontInfo(theme.mono_font()).family()} (wanted {FONT_MONO})"
    )
    formats = sorted(str(f.toStdString()) for f in QImageReader.supportedImageFormats())
    lines.append(f"Image formats Qt reads: {', '.join(formats) or 'NONE'}")
    unreadable = [
        path.name for path in ui_icon_files("book-open").values() if QImage(str(path)).isNull()
    ]
    lines.append(
        f"Icon file readable: {'yes' if not unreadable else 'NO (' + ', '.join(unreadable) + ')'}"
    )
    lines.append(f"Icon loads: {'yes' if not icon('book-open').isNull() else 'NO'}")
    text = theme.tokens().text
    rail = toggle_icon("book-open", text, text)
    lines.append(f"Rail-style icon loads: {'yes' if not rail.isNull() else 'NO'}")
    lines.append(f"Accessibility active: {'yes' if QAccessible.isActive() else 'no'}")
    path: Path | None = default_path()
    if path is None:
        lines.append("Layout file: switched off")
    else:
        size_text = f"{path.stat().st_size} bytes" if path.is_file() else "none yet"
        lines.append(f"Layout file: {path} ({size_text})")
    return lines


def report(app: QApplication) -> str:
    return "\n".join([*environment_lines(), *qt_lines(app)]) + "\n"
