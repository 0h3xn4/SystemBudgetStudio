"""The fonts of the window: Inter for text, JetBrains Mono for numbers, identifiers and code.

Both are bundled (`assets/fonts`, SIL OFL) and registered at start-up; the window never depends on a
font of the system. Weights are 400, 500 and 600 only. Inter's tabular figures (`tnum`) are on, so
digits in a column line up even where the font is not the monospaced one.
"""

from __future__ import annotations

from PySide6.QtGui import QFont, QFontDatabase

from budget_core.assets import assets_dir
from budget_gui.theme.scale import TYPE_BASE, px

FONT_UI, FONT_MONO = "Inter", "JetBrains Mono"
FONT_FILES = (
    "Inter-Regular.ttf",
    "Inter-Medium.ttf",
    "Inter-SemiBold.ttf",
    "JetBrainsMono-Regular.ttf",
    "JetBrainsMono-Medium.ttf",
)
REGULAR, MEDIUM, SEMIBOLD = QFont.Weight.Normal, QFont.Weight.Medium, QFont.Weight.DemiBold
# JetBrains Mono is bundled in 400 and 500: its emphasis is the medium weight


def load_fonts() -> list[str]:
    """Register the bundled fonts; return the family names that loaded."""
    families: list[str] = []
    try:
        fonts = assets_dir() / "fonts"
    except FileNotFoundError:  # no bundled fonts: the system font is used, the window still opens
        return families
    for name in FONT_FILES:
        font_id = QFontDatabase.addApplicationFont(str(fonts / name))
        if font_id >= 0:
            families.extend(QFontDatabase.applicationFontFamilies(font_id))
    return sorted(set(families))


def ui_font(
    pixel_size: int = TYPE_BASE, *, bold: bool = False, weight: QFont.Weight = REGULAR
) -> QFont:
    """The text font at `pixel_size` (a size of the type scale) times the UI scale."""
    font = QFont(FONT_UI)
    font.setPixelSize(px(pixel_size))
    font.setWeight(SEMIBOLD if bold else weight)
    font.setFeature(QFont.Tag("tnum"), 1)
    return font


def mono_font(
    pixel_size: int = TYPE_BASE, *, bold: bool = False, weight: QFont.Weight = REGULAR
) -> QFont:
    """The font of numbers, identifiers, file paths and code: every character has the same width."""
    font = QFont(FONT_MONO)
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.setPixelSize(px(pixel_size))
    font.setWeight(MEDIUM if bold else weight)
    return font
