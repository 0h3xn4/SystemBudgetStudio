"""Contrast of two colours (WCAG 2.2) and the text colour that reads on a given background."""

from __future__ import annotations

from PySide6.QtGui import QColor

MIN_TEXT = 4.5  # WCAG 2.2 AA, text
MIN_GRAPHIC = 3.0  # WCAG 2.2 AA, icons, plot lines and the focus ring


def luminance(colour: str) -> float:
    c = QColor(colour)
    parts = []
    for channel in (c.redF(), c.greenF(), c.blueF()):
        parts.append(channel / 12.92 if channel <= 0.03928 else ((channel + 0.055) / 1.055) ** 2.4)
    return 0.2126 * parts[0] + 0.7152 * parts[1] + 0.0722 * parts[2]


def contrast_ratio(foreground: str, background: str) -> float:
    """WCAG contrast ratio of two #RRGGBB colours (4.5 is the minimum for text)."""
    a, b = luminance(foreground), luminance(background)
    lighter, darker = max(a, b), min(a, b)
    return (lighter + 0.05) / (darker + 0.05)


def readable_text(background: str) -> QColor:
    """Black or white, whichever reads better on `background` (the labels on coloured bars)."""
    light, dark = "#ffffff", "#0b0d10"
    return QColor(
        light if contrast_ratio(light, background) >= contrast_ratio(dark, background) else dark
    )
