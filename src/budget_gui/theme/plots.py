"""How the plots of the window take their colours from the theme.

The core draws its plots (and the exported PNG, PDF and DOCX files) in its own colours, made for a
white page and fixed by the golden files. The window never draws those colours: each colour the
core can name stands for a role (ink, a series, the limit, a band), and the window draws the role in
the colour of the theme in use.
"""

from __future__ import annotations

from PySide6.QtGui import QColor

from budget_core.plots import spec as core
from budget_gui.theme.contrast import MIN_TEXT, contrast_ratio, readable_text
from budget_gui.theme.tokens import Tokens, mix

# core colour -> role: "ink", "muted", "limit", "eclipse", "series<N>" or "band<N>"
CORE_ROLES: dict[str, str] = {
    core.INK.lower(): "ink",
    core.BLUE.lower(): "series0",
    core.GREEN.lower(): "series1",
    core.PURPLE.lower(): "series2",
    core.TEAL.lower(): "series3",
    core.RED.lower(): "limit",
    core.GREY.lower(): "muted",
    core.BAND_ECLIPSE.lower(): "eclipse",
    **{colour.lower(): f"band{i}" for i, colour in enumerate(core.BAND_COLORS)},
}


def series_colour(tokens: Tokens, index: int) -> QColor:
    """The colour of the `index`-th series, mode or category. Past the eighth the palette starts
    again with a lighter mix, so neighbours of one cycle stay apart."""
    cycle, place = divmod(index, len(tokens.series))
    colour = tokens.series[place]
    if cycle:
        amount = max(0.35, 1.0 - 0.3 * cycle)
        colour = mix(colour, tokens.surface, amount)
        # a label on the bar must stay readable: take the mix back until it is
        while amount < 1.0 and contrast_ratio(readable_text(colour).name(), colour) < MIN_TEXT:
            amount = min(1.0, amount + 0.05)
            colour = mix(tokens.series[place], tokens.surface, amount)
    return QColor(colour)


def plot_colour(tokens: Tokens, core_colour: str) -> QColor:
    """The colour to draw a plot series, limit line or band that the core gave in `core_colour`. A
    colour the core does not know is drawn as it is."""
    role = CORE_ROLES.get(core_colour.lower())
    if role is None:
        return QColor(core_colour)
    if role == "ink":
        return QColor(tokens.plot_ink)
    if role == "muted":
        return QColor(tokens.text_muted)
    if role == "limit":
        return QColor(tokens.critical.fg)
    if role == "eclipse":
        return QColor(tokens.strip_eclipse)
    if role.startswith("series"):
        return QColor(tokens.series[int(role[6:]) % len(tokens.series)])
    return QColor(tokens.series[int(role[4:]) % len(tokens.series)])


def severity_colour(tokens: Tokens, severity: str) -> str:
    """The text colour of a problem: errors are critical, warnings caution, information standby."""
    if severity == "error":
        return tokens.critical.fg
    if severity == "warning":
        return tokens.caution.fg
    return tokens.standby.fg
