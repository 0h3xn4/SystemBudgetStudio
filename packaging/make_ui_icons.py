#!/usr/bin/env python3
"""Render the user-interface icons (Lucide SVG files) to black PNG masks.

    python packaging/make_ui_icons.py

Reads assets/icons/ui/src/<name>.svg and writes assets/icons/ui/<name>-<size>.png for the sizes
below. The window tints the masks with the colour of the theme (budget_gui/icons.py), so one file
serves the light and the dark theme and every status colour. The PNG files are committed; run
this only when an icon is added or changed. It needs PySide6 (QtSvg), which a developer has.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

SIZES = (16, 24, 32, 48)
FOLDER = Path(__file__).resolve().parent.parent / "assets" / "icons" / "ui"


def render(svg: bytes, size: int) -> QImage:
    """The icon in black on a transparent square; `currentColor` is black."""
    text = svg.decode("utf-8").replace("currentColor", "#000000")
    renderer = QSvgRenderer(QByteArray(text.encode("utf-8")))
    if not renderer.isValid():
        raise ValueError("not a valid SVG")
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter)
    painter.end()
    return image


def names() -> list[str]:
    return sorted(path.stem for path in (FOLDER / "src").glob("*.svg"))


def main() -> int:
    _app = QGuiApplication.instance() or QGuiApplication([])
    for name in names():
        svg = (FOLDER / "src" / f"{name}.svg").read_bytes()
        for size in SIZES:
            target = FOLDER / f"{name}-{size}.png"
            if not render(svg, size).save(str(target), "PNG"):
                print(f"cannot write {target}", file=sys.stderr)
                return 1
    print(f"{len(names())} icons, sizes {SIZES}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
