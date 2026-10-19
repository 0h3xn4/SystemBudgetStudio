#!/usr/bin/env python3
"""Render the arrows that the style sheet needs (combo boxes and spin boxes) in the theme colours.

    python packaging/make_theme_images.py

A style sheet can only use an image file, not a tinted mask, so the arrows (Lucide chevrons, see
assets/icons/ui/README.md) are made once per theme in the secondary text colour of that theme and
committed: assets/icons/ui/theme/<name>-<theme>.png and <name>-<theme>@2x.png (Qt picks the @2x
file on a high-DPI screen). Run this when a token or an arrow changes; a test checks that the
committed files are what this script makes.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

from budget_gui.theme.tokens import THEMES

ICONS = Path(__file__).resolve().parent.parent / "assets" / "icons" / "ui"
ARROWS = ("chevron-down", "chevron-up")
SIZE = 12  # px at 1x


def render(name: str, colour: str, size: int) -> QImage:
    svg = (ICONS / "src" / f"{name}.svg").read_text(encoding="utf-8")
    renderer = QSvgRenderer(QByteArray(svg.replace("currentColor", colour).encode("utf-8")))
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter)
    painter.end()
    return image


def main() -> int:
    _app = QGuiApplication.instance() or QGuiApplication([])
    target = ICONS / "theme"
    target.mkdir(exist_ok=True)
    for theme_name, tokens in THEMES.items():
        for name in ARROWS:
            for suffix, size in (("", SIZE), ("@2x", SIZE * 2)):
                file = target / f"{name}-{theme_name}{suffix}.png"
                if not render(name, tokens.text_secondary, size).save(str(file), "PNG"):
                    print(f"cannot write {file}", file=sys.stderr)
                    return 1
    print(f"{len(ARROWS) * len(THEMES) * 2} images in {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
