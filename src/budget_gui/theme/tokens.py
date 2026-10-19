"""The design tokens: every colour of the window, for the light and the dark theme (D-169).

The values are the token table of `docs/ui/UI_OVERHAUL.md`. Where WCAG 2.2 AA asked for a change,
the token differs from the table and says why (see `docs/DESIGN.md`): the muted text, the accent
text on the selected row and the status colours of the light theme are darker than the table's
values. Tints (selection, status backgrounds, the comparison colours) are mixed from a colour and
the surface, never typed in, so a changed token carries its tint with it.

Status follows the Astro UXDS taxonomy (critical, serious, caution, normal, standby, off) and is
always shown with an icon or text as well as colour. `Status` (pass, near, fail, not checked,
placeholder) is what the budget tables say; it maps onto the taxonomy.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from PySide6.QtGui import QColor


class Level(StrEnum):
    """The status taxonomy (Astro UXDS)."""

    CRITICAL = "critical"
    SERIOUS = "serious"
    CAUTION = "caution"
    NORMAL = "normal"
    STANDBY = "standby"
    OFF = "off"


class Status(StrEnum):
    """The state of a number or a limit. `NOT_CHECKED` is also what `n/a` means: a result that
    could not be computed or a limit that could not be checked because an input is a placeholder."""

    PASS = "pass"
    NEAR = "near"
    FAIL = "fail"
    NOT_CHECKED = "not_checked"
    PLACEHOLDER = "placeholder"


STATUS_LEVEL = {
    Status.PASS: Level.NORMAL,
    Status.NEAR: Level.CAUTION,
    Status.FAIL: Level.CRITICAL,
    Status.NOT_CHECKED: Level.OFF,
    Status.PLACEHOLDER: Level.STANDBY,
}

# text and icon of each status, for the legend, tooltips and the Problems panel
STATUS_LABELS = {
    Status.PASS: "Within the limit",
    Status.NEAR: "Near the limit",
    Status.FAIL: "Limit broken",
    Status.NOT_CHECKED: "Not checked (n/a)",
    Status.PLACEHOLDER: "Placeholder",
}
STATUS_ICONS = {
    Status.PASS: "circle-check",
    Status.NEAR: "triangle-alert",
    Status.FAIL: "circle-x",
    Status.NOT_CHECKED: "circle-minus",
    Status.PLACEHOLDER: "circle-dashed",
}
LEVEL_ICONS = {
    Level.CRITICAL: "circle-x",
    Level.SERIOUS: "octagon-alert",
    Level.CAUTION: "triangle-alert",
    Level.NORMAL: "circle-check",
    Level.STANDBY: "circle-dashed",
    Level.OFF: "circle-minus",
}


def mix(colour: str, over: str, amount: float) -> str:
    """`colour` at `amount` (0 to 1) over the opaque colour `over`, as #RRGGBB."""
    a, b = QColor(colour), QColor(over)
    parts = (
        round(a.red() * amount + b.red() * (1 - amount)),
        round(a.green() * amount + b.green() * (1 - amount)),
        round(a.blue() * amount + b.blue() * (1 - amount)),
    )
    return "#{:02x}{:02x}{:02x}".format(*parts)


@dataclass(frozen=True)
class StatusStyle:
    fg: str  # text and icon colour, 4.5 : 1 on every surface and on `bg`
    bg: str  # the tint behind a cell, a chip or a banner


@dataclass(frozen=True)
class Tokens:
    name: str
    dark: bool
    # surfaces: canvas (behind the panels) < surface (panels, tables) < raised (menus, popovers)
    canvas: str
    surface: str
    raised: str
    hover: str
    selected: str  # the accent at 10 % (light) or 16 % (dark) over the surface
    border_subtle: str
    border_strong: str
    shadow: str  # of floating elements only (#AARRGGBB)
    # text
    text: str
    text_secondary: str
    text_muted: str
    text_on_accent: str
    # the one accent: the primary action, selection and focus
    accent: str
    accent_hover: str
    accent_text: str  # links and accent text on the surfaces
    focus: str
    # status (Astro UXDS)
    critical: StatusStyle
    serious: StatusStyle
    caution: StatusStyle
    normal: StatusStyle
    standby: StatusStyle
    off: StatusStyle
    # plots: the series colours are a categorical palette made for colour-vision deficiency and
    # apart from the status colours (a test measures both)
    series: tuple[str, ...]
    plot_grid: str
    plot_ink: str
    plot_muted: str
    plot_readout_bg: str  # #AARRGGBB
    band_alpha: int
    # the scenario timeline strips
    strip_sunlit: str
    strip_eclipse: str
    strip_umbra: str
    strip_pass: str
    strip_track: str
    selection_overlay: tuple[int, int, int, int]
    # the comparison rows
    diff_added: str
    diff_removed: str
    diff_changed: str
    diff_now_computed: str
    diff_now_na: str
    # the file editor
    gutter_bg: str
    gutter_text: str
    line_highlight: str

    def color(self, value: str) -> QColor:
        return QColor(value)

    def level(self, level: Level) -> StatusStyle:
        return getattr(self, level.value)  # type: ignore[no-any-return]

    def status(self, status: Status) -> StatusStyle:
        return self.level(STATUS_LEVEL[status])

    @property
    def plot_bg(self) -> str:
        return self.surface

    @property
    def info(self) -> str:
        return self.standby.fg


def _style(fg: str, surface: str, amount: float) -> StatusStyle:
    return StatusStyle(fg, mix(fg, surface, amount))


def _build(
    *,
    name: str,
    dark: bool,
    canvas: str,
    surface: str,
    raised: str,
    hover: str,
    border_subtle: str,
    border_strong: str,
    text: str,
    text_secondary: str,
    text_muted: str,
    text_on_accent: str,
    accent: str,
    accent_hover: str,
    accent_text: str,
    status: dict[Level, str],
    series: tuple[str, ...],
    tint: float,
    shadow: str,
    band_alpha: int,
) -> Tokens:
    styles = {level: _style(colour, surface, tint) for level, colour in status.items()}
    accent_rgb = QColor(accent)
    return Tokens(
        name=name,
        dark=dark,
        canvas=canvas,
        surface=surface,
        raised=raised,
        hover=hover,
        selected=mix(accent, surface, 0.16 if dark else 0.10),
        border_subtle=border_subtle,
        border_strong=border_strong,
        shadow=shadow,
        text=text,
        text_secondary=text_secondary,
        text_muted=text_muted,
        text_on_accent=text_on_accent,
        accent=accent,
        accent_hover=accent_hover,
        accent_text=accent_text,
        focus=accent,
        critical=styles[Level.CRITICAL],
        serious=styles[Level.SERIOUS],
        caution=styles[Level.CAUTION],
        normal=styles[Level.NORMAL],
        standby=styles[Level.STANDBY],
        off=_style(text_muted, surface, tint),
        series=series,
        plot_grid=border_subtle,
        plot_ink=text,
        plot_muted=text_secondary,
        plot_readout_bg="#eb" + raised.lstrip("#"),
        band_alpha=band_alpha,
        strip_sunlit=mix(status[Level.CAUTION], surface, 0.22),
        strip_eclipse=mix(text_muted, surface, 0.55),
        strip_umbra=canvas if dark else mix(text, surface, 0.85),
        strip_pass=accent,
        strip_track=hover,
        selection_overlay=(accent_rgb.red(), accent_rgb.green(), accent_rgb.blue(), 60),
        diff_added=styles[Level.NORMAL].bg,
        diff_removed=styles[Level.CRITICAL].bg,
        diff_changed=styles[Level.CAUTION].bg,
        diff_now_computed=styles[Level.STANDBY].bg,
        diff_now_na=_style(text_muted, surface, tint).bg,
        gutter_bg=canvas,
        gutter_text=text_muted,
        line_highlight=styles[Level.CAUTION].bg,
    )


# Eight colours for series, chosen by search: at least 19 (light) and 20 (dark) CIELAB units apart
# for normal vision and for protanopia, deuteranopia and tritanopia, and at least 22 units from
# every status colour of their theme. `tests/gui/test_theme.py` measures both.
SERIES_LIGHT = (
    "#3232e2",
    "#50958a",
    "#b437cd",
    "#bb1b50",
    "#301386",
    "#b27ab8",
    "#703285",
    "#861356",
)
SERIES_DARK = (
    "#765cc1",
    "#8be6ee",
    "#eb70ad",
    "#d59658",
    "#b695e4",
    "#df2070",
    "#962de1",
    "#d6b594",
)

LIGHT = _build(
    name="light",
    dark=False,
    canvas="#f7f7f8",
    surface="#ffffff",
    raised="#ffffff",
    hover="#f0f1f3",
    border_subtle="#e4e5e9",
    border_strong="#d0d3d9",
    text="#16181d",
    text_secondary="#50565f",
    text_muted="#646b75",  # the table's #7c838d is 3.8 : 1 on white
    text_on_accent="#ffffff",
    accent="#2563eb",
    accent_hover="#1d4fd0",
    accent_text="#1d4fd0",  # the accent itself is 4.5 : 1 on the selected row, this is 5.9
    status={
        Level.CRITICAL: "#c62828",  # the table's #ff4d4f is 3.2 : 1 on white
        Level.SERIOUS: "#a8480a",
        Level.CAUTION: "#8a5a00",
        Level.NORMAL: "#14724a",
        Level.STANDBY: "#1e62b5",
    },
    series=SERIES_LIGHT,
    tint=0.12,
    shadow="#33101828",
    band_alpha=70,
)

DARK = _build(
    name="dark",
    dark=True,
    canvas="#0b0d10",
    surface="#111418",
    raised="#171b21",
    hover="#1d222a",
    border_subtle="#222832",
    border_strong="#2e3540",
    text="#e7e9ec",
    text_secondary="#a1a8b3",
    text_muted="#8a919c",  # the table's #7a828e is 4.1 : 1 on a hovered row
    text_on_accent="#0b0d10",  # white on #4c8dff is 3.0 : 1
    accent="#4c8dff",
    accent_hover="#6aa0ff",
    accent_text="#6aa0ff",
    status={
        Level.CRITICAL: "#ff6b6d",
        Level.SERIOUS: "#ff8a3d",
        Level.CAUTION: "#f5b83d",
        Level.NORMAL: "#3dd68c",
        Level.STANDBY: "#56b4f5",
    },
    series=SERIES_DARK,
    tint=0.16,
    shadow="#99000000",
    band_alpha=60,
)

THEMES = {"light": LIGHT, "dark": DARK}
