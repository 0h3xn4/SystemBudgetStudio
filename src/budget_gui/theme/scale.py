"""The scales of the window: spacing, type, shape, control sizes, motion and the UI scale (D-169).

Every pixel size of the window comes from here (a test checks that no other module of the window
holds a font name, a colour or a pixel size of its own). The numbers are the ones of the design
language in `docs/ui/UI_OVERHAUL.md`: a 4 px grid, six type sizes, three weights, two radii.

`px(n)` applies the UI scale the user chose (90, 100, 110 or 125 %) to a size in pixels.
"""

from __future__ import annotations

SPACE = (4, 8, 12, 16, 24, 32)  # px: the only gaps and paddings (a 4 px grid)

# type sizes in px: caption, small and table, body (the base), section title, page title, display
TYPE_CAPTION, TYPE_SMALL, TYPE_BASE, TYPE_TITLE, TYPE_HEADING, TYPE_DISPLAY = 11, 12, 13, 15, 18, 22
TYPE_SIZES = (TYPE_CAPTION, TYPE_SMALL, TYPE_BASE, TYPE_TITLE, TYPE_HEADING, TYPE_DISPLAY)
WEIGHTS = (400, 500, 600)  # regular, medium, semibold: the only weights

RADIUS_CONTROL = 6  # px: buttons, inputs, tabs, chips
RADIUS_PANEL = 8  # px: panels, popovers, dialogs, toasts

CONTROL_COMPACT = 28  # px: the height of a control in a dense place (toolbars, table filters)
CONTROL_DEFAULT = 32  # px: the height of a control everywhere else
ROW_HEIGHT = 26  # px: a table row
FOCUS_RING = 2  # px: the focus ring, in the accent colour
BORDER = 1  # px: borders are always 1 px

ICON_UI = 16  # px: an icon in the window
ICON_RAIL = 20  # px: an icon in the navigation rail
MOTION_MS = (120, 180)  # ease-out for hover, panels opening and closing, toasts (never for data)

SCALES = (90, 100, 110, 125)  # % : what the UI-scale setting offers
DEFAULT_SCALE = 100

_scale = DEFAULT_SCALE


def scale_percent() -> int:
    """The UI scale in use, in per cent."""
    return _scale


def set_scale_percent(percent: int) -> int:
    """Use `percent` (one of `SCALES`; anything else is the nearest one) and return it."""
    global _scale
    _scale = min(SCALES, key=lambda s: abs(s - int(percent)))
    return _scale


def px(size: float) -> int:
    """`size` pixels at the UI scale in use, rounded to a whole pixel (never below 1 for a
    positive size)."""
    scaled = round(size * _scale / 100)
    return max(scaled, 1) if size > 0 else 0


def gap(index: int) -> int:
    """The `index`-th step of the spacing scale (0 to 5) in px at the UI scale."""
    return px(SPACE[index])


def inset(horizontal: int, vertical: int | None = None) -> tuple[int, int, int, int]:
    """Layout margins (left, top, right, bottom) from steps of the spacing scale."""
    v = horizontal if vertical is None else vertical
    return (gap(horizontal), gap(v), gap(horizontal), gap(v))


def scaled(size: tuple[int, int]) -> tuple[int, int]:
    """A (width, height) in pixels at the UI scale."""
    return (px(size[0]), px(size[1]))


# sizes of windows, panels and views that are not on a scale; (width, height) unless said
WINDOW_DEFAULT = (1400, 860)
DOCK_WIDTHS = (280, 420)  # the project panel and the Problems panel
PALETTE_SIZE = (560, 420)  # the command palette and the paste preview
GUIDE_SIZE = (980, 760)
LEGEND_MIN = (640, 340)
PLOT_MIN_HEIGHT = 220
TIMELINE_MIN_HEIGHT = 180
LIST_MIN_HEIGHT = 48  # the Problems list
COLUMN_MIN = 40  # a table column is never narrower
TABLE_MIN_HEIGHT = 60  # a table in a page that holds several
PROVENANCE_MAX_HEIGHT = 170
RESULTS_MIN_HEIGHT = 140
SITES_MAX_HEIGHT = 72
COMBO_MAX_WIDTH = 120
COMPACT_BUTTON_WIDTH = 36  # the arrows that step through violations
PROGRESS_HEIGHT = 4
