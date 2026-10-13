"""The theme: contrast, no colour literals outside it, light, dark and system (D-150)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from budget_core.plots import spec as core_spec
from budget_core.plots.spec import Panel, PlotSpec, Series
from budget_gui import icons, theme
from budget_gui.plot_widget import PlotWidget
from budget_gui.theme import DARK, LIGHT, Mode, Status, contrast_ratio

GUI = Path(__file__).resolve().parents[2] / "src" / "budget_gui"
BOTH = pytest.mark.parametrize("tokens", [LIGHT, DARK], ids=["light", "dark"])
MIN_TEXT = 4.5  # WCAG AA for text


@BOTH
def test_text_reaches_4_5_to_1_on_the_surfaces_it_is_used_on(tokens: theme.Tokens) -> None:
    for name in ("text", "text_secondary", "text_disabled", "accent_text", "info"):
        for surface in (tokens.background, tokens.layer):
            assert contrast_ratio(getattr(tokens, name), surface) >= MIN_TEXT, (name, surface)
    assert contrast_ratio(tokens.text_on_accent, tokens.accent) >= MIN_TEXT
    assert contrast_ratio(tokens.text_on_accent, tokens.accent_hover) >= MIN_TEXT
    assert contrast_ratio(tokens.selection_text, tokens.selection_bg) >= MIN_TEXT
    assert contrast_ratio(tokens.gutter_text, tokens.gutter_bg) >= MIN_TEXT
    assert contrast_ratio(tokens.plot_muted, tokens.plot_bg) >= MIN_TEXT
    assert contrast_ratio(tokens.plot_ink, tokens.plot_bg) >= MIN_TEXT


@BOTH
def test_every_status_is_readable_on_the_surfaces_and_on_its_own_tint(tokens: theme.Tokens) -> None:
    for status in Status:
        style = tokens.status(status)
        for surface in (tokens.background, tokens.layer, style.bg):
            assert contrast_ratio(style.fg, surface) >= MIN_TEXT, (status, surface)


@BOTH
def test_text_on_the_comparison_tints_and_the_highlight(tokens: theme.Tokens) -> None:
    for name in (
        "diff_changed",
        "diff_added",
        "diff_removed",
        "diff_now_computed",
        "diff_now_na",
        "line_highlight",
    ):
        assert contrast_ratio(tokens.text, getattr(tokens, name)) >= MIN_TEXT, name


@BOTH
def test_the_label_on_every_mode_bar_is_readable(tokens: theme.Tokens) -> None:
    assert len(tokens.categorical) >= 14
    for colour in tokens.categorical:
        label = theme.readable_text(colour).name()
        assert contrast_ratio(label, colour) >= MIN_TEXT, colour


def test_every_status_has_a_distinct_icon_so_colour_is_never_alone() -> None:
    names = [theme.STATUS_ICONS[s] for s in Status]
    assert len(set(names)) == len(Status)
    for status in Status:
        assert theme.STATUS_LABELS[status]


def test_status_colours_differ_from_each_other_in_both_themes() -> None:
    for tokens in (LIGHT, DARK):
        foregrounds = [tokens.status(s).fg for s in Status]
        assert len(set(foregrounds)) == len(Status)


def test_every_colour_the_core_gives_a_plot_is_known_to_the_dark_theme() -> None:
    core = {
        getattr(core_spec, name).lower()
        for name in ("INK", "BLUE", "RED", "GREEN", "PURPLE", "TEAL", "GREY", "BAND_ECLIPSE")
    } | {c.lower() for c in core_spec.BAND_COLORS}
    for colour in core:
        assert colour in theme._CORE_TO_DARK, colour
        mapped = theme._CORE_TO_DARK[colour]
        if colour not in {c.lower() for c in core_spec.BAND_COLORS} | {"#c6c6c6"}:
            # a line on the dark plot: 3 : 1 is what a graphic needs
            assert contrast_ratio(mapped, DARK.plot_bg) >= 3.0, (colour, mapped)
        assert theme.plot_colour(LIGHT, colour) == QColor(colour)
    assert theme.plot_colour(DARK, "#123456") == QColor("#123456")  # unknown: as it is


def test_no_module_of_the_window_but_the_theme_holds_a_colour() -> None:
    literal = re.compile(r"#[0-9a-fA-F]{6,8}\b|QColor\(\s*\d|QColor\(\s*Qt\.GlobalColor")
    offenders = []
    for path in sorted(GUI.glob("*.py")):
        if path.name == "theme.py":
            continue
        text = path.read_text(encoding="utf-8")
        if literal.search(text) or "setStyleSheet(" in text:
            offenders.append(path.name)
    assert offenders == []


def test_the_style_sheet_has_no_unresolved_field_and_names_the_roles() -> None:
    for tokens in (LIGHT, DARK):
        sheet = theme.stylesheet(tokens)
        assert "{t." not in sheet and "{s" not in sheet and "{TYPE" not in sheet
        for role in ("error", "banner", "section-title", "muted", "heading", "title"):
            assert f'QLabel[role="{role}"]' in sheet
        assert tokens.background in sheet and tokens.accent in sheet


def test_only_the_scales_are_used_for_sizes() -> None:
    assert theme.SPACE == (4, 8, 12, 16, 24, 32)
    assert (theme.TYPE_SMALL, theme.TYPE_BASE, theme.TYPE_TITLE, theme.TYPE_HEADING) == (
        12,
        13,
        16,
        20,
    )


def test_the_dark_theme_colours_the_application(qtbot) -> None:  # type: ignore[no-untyped-def]
    app = QApplication.instance()
    assert isinstance(app, QApplication)
    changed: list[int] = []
    theme.manager().changed.connect(lambda: changed.append(1))
    theme.apply_theme(app, Mode.DARK)
    assert theme.tokens() is DARK and changed
    assert app.palette().color(QPalette.ColorRole.Window) == QColor(DARK.background)
    assert DARK.background in app.styleSheet()
    theme.apply_theme(app, "white")  # the old names still work
    assert theme.tokens() is LIGHT
    assert app.palette().color(QPalette.ColorRole.Window) == QColor(LIGHT.background)


def test_the_system_mode_follows_the_colour_scheme(  # type: ignore[no-untyped-def]
    qtbot, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = QApplication.instance()
    assert isinstance(app, QApplication)
    dark = [True]
    monkeypatch.setattr(theme, "system_is_dark", lambda: dark[0])
    theme.manager().set_mode(Mode.SYSTEM, app)
    assert theme.tokens() is DARK
    dark[0] = False
    theme.manager()._system_changed(Qt.ColorScheme.Light)  # what Qt's signal calls
    assert theme.tokens() is LIGHT
    theme.manager().set_mode(Mode.DARK, app)  # a fixed theme ignores the system
    dark[0] = False
    theme.manager()._system_changed(Qt.ColorScheme.Light)
    assert theme.tokens() is DARK


def test_the_plot_is_drawn_again_in_the_colours_of_the_new_theme(qtbot) -> None:  # type: ignore[no-untyped-def]
    widget = PlotWidget()
    qtbot.addWidget(widget)
    widget.resize(500, 300)
    widget.show()
    widget.set_spec(PlotSpec("t", (Panel("p", "W", (Series("s", *_line()),)),), x_max_s=10.0))
    light = widget.grab().toImage()
    assert light.pixelColor(2, 2) == QColor(LIGHT.plot_bg)
    theme.manager().set_mode(Mode.DARK)
    dark = widget.grab().toImage()
    assert dark.pixelColor(2, 2) == QColor(DARK.plot_bg)
    assert light != dark


def _line():  # type: ignore[no-untyped-def]
    import numpy as np

    x = np.linspace(0.0, 10.0, 50)
    return x, np.sin(x) + 2.0


def test_icons_are_tinted_with_the_colour_asked_for(qtbot) -> None:  # type: ignore[no-untyped-def]
    icon = icons.icon("circle-check", "#ff0000")
    image = icon.pixmap(48, 48).toImage()
    opaque = [
        image.pixelColor(x, y)
        for x in range(image.width())
        for y in range(image.height())
        if image.pixelColor(x, y).alpha() == 255
    ]
    assert opaque and all(c.red() == 255 and c.green() == 0 and c.blue() == 0 for c in opaque)
    assert icons.icon("circle-check", "#0000ff").cacheKey() != icon.cacheKey()


def test_every_status_icon_exists_and_a_missing_icon_is_empty_not_an_error(qtbot) -> None:  # type: ignore[no-untyped-def]
    for status in Status:
        assert not icons.status_icon(status).isNull()
    assert icons.icon("no-such-icon").isNull()


def test_the_design_page_states_the_colours_of_the_code() -> None:
    page = (Path(__file__).resolve().parents[2] / "docs" / "DESIGN.md").read_text(encoding="utf-8")
    for tokens in (LIGHT, DARK):
        for name in (
            "background",
            "layer",
            "border",
            "border_strong",
            "text",
            "text_secondary",
            "text_disabled",
            "accent",
            "accent_hover",
            "text_on_accent",
            "accent_text",
            "focus",
            "selection_bg",
            "selection_text",
            "info",
        ):
            assert getattr(tokens, name) in page, (tokens.name, name)
        for status in Status:
            style = tokens.status(status)
            assert style.fg in page and style.bg in page, (tokens.name, status)
    for status in Status:
        assert theme.STATUS_ICONS[status] in page
    for scale in ("12, 13, 16, 20", "4, 8, 12, 16, 24, 32"):
        assert scale in page


def test_a_closed_view_does_not_answer_a_theme_change(qtbot: object) -> None:
    """The theme manager outlives every window: a view that is gone must not be called when the
    theme changes (it raised "already deleted" in the next test)."""
    from PySide6.QtCore import QCoreApplication, QEvent

    from budget_gui.compare_view import CompareView

    view = CompareView()
    view.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    theme.manager().set_mode(Mode.DARK)
    theme.manager().set_mode(Mode.LIGHT)  # raises in the event loop if the view still listens
    QApplication.processEvents()
