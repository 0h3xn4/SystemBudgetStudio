"""The theme of the window: tokens, scales, fonts, style sheet, plot colours, manager (D-169).

Everything that decides how the window looks lives in this package; no other module of the window
holds a colour, a font family or a pixel size of its own (a test checks it). The names below are
what the rest of the window imports.
"""

from budget_gui.theme.contrast import MIN_GRAPHIC, MIN_TEXT, contrast_ratio, readable_text
from budget_gui.theme.controller import (
    Mode,
    ThemeManager,
    app_icon,
    apply_theme,
    manager,
    system_is_dark,
    tokens,
)
from budget_gui.theme.fonts import FONT_MONO, FONT_UI, load_fonts, mono_font, ui_font
from budget_gui.theme.plots import CORE_ROLES, plot_colour, series_colour, severity_colour
from budget_gui.theme.qss import (
    CHIP_STATES,
    banner_colours,
    chip_colours,
    document_css,
    palette,
    stylesheet,
)
from budget_gui.theme.scale import *  # noqa: F403 (the names are listed in scale.__all__)
from budget_gui.theme.scale import __all__ as _scale_names
from budget_gui.theme.tokens import (
    DARK,
    LEVEL_ICONS,
    LIGHT,
    STATUS_ICONS,
    STATUS_LABELS,
    STATUS_LEVEL,
    THEMES,
    Level,
    Status,
    StatusStyle,
    Tokens,
    mix,
)

__all__ = [
    "CHIP_STATES",
    "CORE_ROLES",
    "DARK",
    "FONT_MONO",
    "FONT_UI",
    "LEVEL_ICONS",
    "LIGHT",
    "Level",
    "MIN_GRAPHIC",
    "MIN_TEXT",
    "Mode",
    "STATUS_ICONS",
    "STATUS_LABELS",
    "STATUS_LEVEL",
    "Status",
    "StatusStyle",
    "THEMES",
    "ThemeManager",
    "Tokens",
    "app_icon",
    "apply_theme",
    "banner_colours",
    "chip_colours",
    "contrast_ratio",
    "document_css",
    "load_fonts",
    "manager",
    "mix",
    "mono_font",
    "palette",
    "plot_colour",
    "readable_text",
    "series_colour",
    "severity_colour",
    "stylesheet",
    "system_is_dark",
    "tokens",
    "ui_font",
    *_scale_names,
]
