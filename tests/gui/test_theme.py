"""The theme: contrast, colour-vision safety, no style literals outside it, light, dark, system and
the UI scale (D-150, D-169)."""

from __future__ import annotations

import ast
import itertools
import math
import re
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication

from budget_core.plots import spec as core_spec
from budget_core.plots.spec import Panel, PlotSpec, Series
from budget_gui import icons, theme
from budget_gui.plot_widget import PlotWidget
from budget_gui.theme import DARK, LIGHT, Level, Mode, Status, contrast_ratio
from budget_gui.theme import controller as theme_manager

GUI = Path(__file__).resolve().parents[2] / "src" / "budget_gui"
BOTH = pytest.mark.parametrize("tokens", [LIGHT, DARK], ids=["light", "dark"])
MIN_TEXT = theme.MIN_TEXT  # WCAG 2.2 AA for text
MIN_GRAPHIC = theme.MIN_GRAPHIC  # WCAG 2.2 AA for icons, plot lines and the focus ring


def surfaces(tokens: theme.Tokens) -> list[str]:
    """Every surface text can sit on."""
    return [tokens.canvas, tokens.surface, tokens.raised, tokens.hover, tokens.selected]


# ---- contrast ----------------------------------------------------------------------------------
@BOTH
def test_text_reaches_4_5_to_1_on_every_surface_it_is_used_on(tokens: theme.Tokens) -> None:
    for name in ("text", "text_secondary", "text_muted", "accent_text"):
        for surface in surfaces(tokens):
            assert contrast_ratio(getattr(tokens, name), surface) >= MIN_TEXT, (name, surface)
    assert contrast_ratio(tokens.text_on_accent, tokens.accent) >= MIN_TEXT
    assert contrast_ratio(tokens.text_on_accent, tokens.accent_hover) >= MIN_TEXT
    assert contrast_ratio(tokens.text_on_accent, tokens.critical.fg) >= MIN_TEXT  # danger button
    assert contrast_ratio(tokens.gutter_text, tokens.gutter_bg) >= MIN_TEXT
    assert contrast_ratio(tokens.plot_muted, tokens.plot_bg) >= MIN_TEXT
    assert contrast_ratio(tokens.plot_ink, tokens.plot_bg) >= MIN_TEXT


@BOTH
def test_the_focus_ring_and_the_accent_are_seen_on_every_surface(tokens: theme.Tokens) -> None:
    for surface in surfaces(tokens):
        assert contrast_ratio(tokens.focus, surface) >= MIN_GRAPHIC, surface
    assert contrast_ratio(tokens.accent, tokens.surface) >= MIN_GRAPHIC


@BOTH
def test_every_level_is_readable_on_the_surfaces_and_on_its_own_tint(tokens: theme.Tokens) -> None:
    for level in Level:
        style = tokens.level(level)
        for surface in [*surfaces(tokens), style.bg]:
            assert contrast_ratio(style.fg, surface) >= MIN_TEXT, (level, surface)
    for status in Status:
        assert tokens.status(status) is tokens.level(theme.STATUS_LEVEL[status])


@BOTH
def test_text_on_the_comparison_tints_and_the_highlight(tokens: theme.Tokens) -> None:
    for name in (
        "diff_added",
        "diff_removed",
        "diff_changed",
        "diff_now_computed",
        "diff_now_na",
        "line_highlight",
    ):
        assert contrast_ratio(tokens.text, getattr(tokens, name)) >= MIN_TEXT, name


@BOTH
def test_the_label_on_every_mode_bar_is_readable(tokens: theme.Tokens) -> None:
    for index in range(3 * len(tokens.series)):  # three cycles of the palette
        colour = theme.series_colour(tokens, index).name()
        label = theme.readable_text(colour).name()
        assert contrast_ratio(label, colour) >= MIN_TEXT, (index, colour)


@BOTH
def test_a_series_is_seen_on_the_plot_background(tokens: theme.Tokens) -> None:
    for colour in tokens.series:
        assert contrast_ratio(colour, tokens.plot_bg) >= MIN_GRAPHIC, colour


# ---- colour-vision deficiency ------------------------------------------------------------------
_MACHADO = {  # severity 1.0 (Machado, Oliveira and Fernandes 2009), on linear RGB
    "protanopia": (
        (0.152286, 1.052583, -0.204868),
        (0.114503, 0.786281, 0.099216),
        (-0.003882, -0.048116, 1.051998),
    ),
    "deuteranopia": (
        (0.367322, 0.860646, -0.227968),
        (0.280085, 0.672501, 0.047413),
        (-0.011820, 0.042940, 0.968881),
    ),
    "tritanopia": (
        (1.255528, -0.076749, -0.178779),
        (-0.078411, 0.930809, 0.147602),
        (0.004733, 0.691367, 0.303900),
    ),
}


def _lab(colour: str, deficiency: str | None) -> tuple[float, float, float]:
    c = QColor(colour)
    lin = [
        v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
        for v in (c.redF(), c.greenF(), c.blueF())
    ]
    if deficiency:
        m = _MACHADO[deficiency]
        lin = [max(0.0, min(1.0, sum(m[i][j] * lin[j] for j in range(3)))) for i in range(3)]
    r, g, b = lin
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116

    return (116 * f(y) - 16, 500 * (f(x) - f(y)), 200 * (f(y) - f(z)))


def _delta_e(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return math.dist(a, b)


@BOTH
def test_the_series_colours_stay_apart_for_every_kind_of_colour_vision(
    tokens: theme.Tokens,
) -> None:
    assert len(tokens.series) == 8
    for deficiency in (None, *_MACHADO):
        for a, b in itertools.combinations(tokens.series, 2):
            assert _delta_e(_lab(a, deficiency), _lab(b, deficiency)) >= 15.0, (deficiency, a, b)


@BOTH
def test_the_series_colours_are_apart_from_the_status_colours(tokens: theme.Tokens) -> None:
    for colour in tokens.series:
        for level in Level:
            fg = tokens.level(level).fg
            assert _delta_e(_lab(colour, None), _lab(fg, None)) >= 20.0, (colour, level)


# ---- status ------------------------------------------------------------------------------------
def test_every_status_has_a_distinct_icon_so_colour_is_never_alone() -> None:
    names = [theme.STATUS_ICONS[s] for s in Status]
    assert len(set(names)) == len(Status)
    for status in Status:
        assert theme.STATUS_LABELS[status]
    assert len(set(theme.LEVEL_ICONS.values())) == len(Level)


def test_status_colours_differ_from_each_other_in_both_themes() -> None:
    for tokens in (LIGHT, DARK):
        foregrounds = [tokens.level(level).fg for level in Level]
        assert len(set(foregrounds)) == len(Level)


# ---- the colours the core gives a plot ---------------------------------------------------------
def test_every_colour_the_core_gives_a_plot_has_a_role_in_the_theme() -> None:
    core = {
        getattr(core_spec, name).lower()
        for name in ("INK", "BLUE", "RED", "GREEN", "PURPLE", "TEAL", "GREY", "BAND_ECLIPSE")
    } | {c.lower() for c in core_spec.BAND_COLORS}
    for colour in core:
        assert colour in theme.CORE_ROLES, colour
        for tokens in (LIGHT, DARK):
            drawn = theme.plot_colour(tokens, colour)
            if not theme.CORE_ROLES[colour].startswith(("band", "eclipse")):
                # a line on the plot: 3 : 1 is what a graphic needs
                assert contrast_ratio(drawn.name(), tokens.plot_bg) >= MIN_GRAPHIC, colour
    # the window never draws a core colour as it is
    assert theme.plot_colour(LIGHT, core_spec.BLUE) != QColor(core_spec.BLUE)
    assert theme.plot_colour(DARK, "#123456") == QColor("#123456")  # unknown: as it is


# ---- nothing outside the theme package sets a colour, a font or a size ------------------------
def _gui_modules() -> list[Path]:
    return [p for p in sorted(GUI.glob("*.py"))]  # the files of the package `theme/` are exempt


def test_no_module_of_the_window_but_the_theme_holds_a_colour() -> None:
    literal = re.compile(r"#[0-9a-fA-F]{6,8}\b|QColor\(\s*\d|QColor\(\s*Qt\.GlobalColor")
    offenders = []
    for path in _gui_modules():
        text = path.read_text(encoding="utf-8")
        if literal.search(text) or "setStyleSheet(" in text:
            offenders.append(path.name)
    assert offenders == []


SIZE_CALLS = {
    "setFixedWidth",
    "setFixedHeight",
    "setFixedSize",
    "setMinimumWidth",
    "setMinimumHeight",
    "setMinimumSize",
    "setMaximumWidth",
    "setMaximumHeight",
    "setMaximumSize",
    "setContentsMargins",
    "setSpacing",
    "setColumnWidth",
    "setRowHeight",
    "setDefaultSectionSize",
    "setMinimumSectionSize",
    "setIconSize",
    "setPixelSize",
    "setPointSize",
    "setPointSizeF",
    "resize",
    "setHandleWidth",
    "resizeDocks",
    "setIndentation",
    "setLineWidth",
    "setMidLineWidth",
}


SCALE_CALLS = {"gap", "inset", "px", "scaled"}  # these turn a step of a scale into pixels


def _numeric_literals(node: ast.AST) -> bool:
    """True when a size call is given a bare number other than 0 (also inside `QSize(...)`), a
    number that is not a step of the scale (`theme.gap(1)`, `theme.px(theme.ROW_HEIGHT)`)."""
    if isinstance(node, ast.Call) and getattr(node.func, "attr", getattr(node.func, "id", "")) in (
        SCALE_CALLS
    ):
        return False
    if (
        isinstance(node, ast.Constant)
        and isinstance(node.value, int | float)
        and not isinstance(node.value, bool)
        and node.value not in (0, -1)
    ):
        return True
    return any(_numeric_literals(child) for child in ast.iter_child_nodes(node))


def test_no_module_of_the_window_but_the_theme_holds_a_font_family() -> None:
    offenders = []
    for path in _gui_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = getattr(node.func, "attr", getattr(node.func, "id", ""))
                if name in {"QFont", "setFamily", "setFamilies"} and any(
                    isinstance(a, ast.Constant) and isinstance(a.value, str) for a in node.args
                ):
                    offenders.append(f"{path.name}:{node.lineno}")
    assert offenders == []


def test_no_module_of_the_window_but_the_theme_holds_a_pixel_size() -> None:
    offenders = []
    px_text = re.compile(r"\b\d+(\.\d+)?\s*px\b|font-size|border-radius")
    for path in _gui_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = getattr(node.func, "attr", getattr(node.func, "id", ""))
                if name in SIZE_CALLS and _numeric_literals(node):
                    offenders.append(f"{path.name}:{node.lineno} {name}")
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                if px_text.search(node.value) and len(node.value) < 200:
                    offenders.append(f"{path.name}:{node.lineno} text")
    assert offenders == [], offenders


def test_no_old_design_system_is_named_in_the_window_or_its_assets() -> None:
    """Carbon is gone from the window (D-168): its fonts, its tokens and its name."""
    carbon = re.compile(r"carbon|IBM Plex|IBMPlex|g100", re.IGNORECASE)
    offenders = [
        p.name for p in sorted(GUI.rglob("*.py")) if carbon.search(p.read_text(encoding="utf-8"))
    ]
    assert offenders == []


# ---- the style sheet and the scales ------------------------------------------------------------
def test_the_style_sheet_has_no_unresolved_field_and_names_the_roles() -> None:
    for tokens in (LIGHT, DARK):
        sheet = theme.stylesheet(tokens)
        assert "{t." not in sheet and "{s" not in sheet and "{TYPE" not in sheet
        assert "{px(" not in sheet and "{h" not in sheet and "{r" not in sheet
        for role in ("error", "banner", "section-title", "muted", "heading", "title", "caption"):
            assert f'QLabel[role="{role}"]' in sheet
        for kind in ("primary", "secondary", "ghost", "danger", "link"):
            assert f'kind="{kind}"' in sheet or kind == "secondary"
        assert tokens.surface in sheet and tokens.accent in sheet and tokens.canvas in sheet


def test_only_the_scales_are_used_for_sizes() -> None:
    assert theme.SPACE == (4, 8, 12, 16, 24, 32)
    assert theme.TYPE_SIZES == (11, 12, 13, 15, 18, 22)
    assert theme.WEIGHTS == (400, 500, 600)
    assert (theme.RADIUS_CONTROL, theme.RADIUS_PANEL) == (6, 8)
    assert (theme.CONTROL_COMPACT, theme.CONTROL_DEFAULT, theme.ROW_HEIGHT) == (28, 32, 26)
    assert theme.FOCUS_RING == 2 and theme.BORDER == 1
    assert theme.SCALES == (90, 100, 110, 125)


def test_the_package_exports_the_function_not_the_module() -> None:
    assert callable(theme.tokens) and callable(theme.manager)  # `tokens.py` is a module, too


def test_the_ui_scale_scales_sizes_and_the_style_sheet(qtbot) -> None:  # type: ignore[no-untyped-def]
    app = QApplication.instance()
    assert isinstance(app, QApplication)
    try:
        assert theme.px(32) == 32
        theme.manager().set_scale(125, app)
        assert theme.scale_percent() == 125 and theme.px(32) == 40 and theme.px(1) == 1
        assert "font-size: 16px" in app.styleSheet()  # 13 px at 125 %
        assert theme.ui_font().pixelSize() == 16
        theme.manager().set_scale(90, app)
        assert theme.px(32) == 29 and "font-size: 12px" in app.styleSheet()
        assert theme.set_scale_percent(113) == 110  # the nearest offered scale
    finally:
        theme.manager().set_scale(100, app)
    assert theme.px(32) == 32


# ---- fonts -------------------------------------------------------------------------------------
def test_the_bundled_fonts_are_used_for_text_and_for_numbers(qtbot) -> None:  # type: ignore[no-untyped-def]
    families = theme.load_fonts()
    assert "Inter" in families and "JetBrains Mono" in families
    assert theme.ui_font().family() == "Inter" == theme.FONT_UI
    assert theme.mono_font().family() == "JetBrains Mono" == theme.FONT_MONO
    assert "Inter" in QFontDatabase.families()
    assert theme.ui_font().pixelSize() == theme.TYPE_BASE
    assert [f.weight() for f in (theme.ui_font(), theme.ui_font(bold=True))] == [400, 600]


# ---- light, dark, system -----------------------------------------------------------------------
def test_the_dark_theme_colours_the_application(qtbot) -> None:  # type: ignore[no-untyped-def]
    app = QApplication.instance()
    assert isinstance(app, QApplication)
    changed: list[int] = []
    theme.manager().changed.connect(lambda: changed.append(1))
    theme.apply_theme(app, Mode.DARK)
    assert theme.tokens() is DARK and changed
    assert app.palette().color(QPalette.ColorRole.Window) == QColor(DARK.canvas)
    assert app.palette().color(QPalette.ColorRole.Base) == QColor(DARK.surface)
    assert DARK.surface in app.styleSheet()
    theme.apply_theme(app, "light")
    assert theme.tokens() is LIGHT
    assert app.palette().color(QPalette.ColorRole.Window) == QColor(LIGHT.canvas)


def test_the_system_mode_follows_the_colour_scheme(  # type: ignore[no-untyped-def]
    qtbot, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = QApplication.instance()
    assert isinstance(app, QApplication)
    dark = [True]
    monkeypatch.setattr(theme_manager, "system_is_dark", lambda: dark[0])
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


def test_motion_is_off_without_a_screen_and_when_reduced(qtbot) -> None:  # type: ignore[no-untyped-def]
    assert theme.manager().motion_ms() == 0  # the tests run offscreen
    assert theme.MOTION_MS == (120, 180)


# ---- icons -------------------------------------------------------------------------------------
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
    for level in Level:
        assert not icons.icon(theme.LEVEL_ICONS[level]).isNull()
    assert icons.icon("no-such-icon").isNull()


def test_the_arrows_of_the_style_sheet_are_what_the_script_makes(qtbot) -> None:  # type: ignore[no-untyped-def]
    """The arrow images are committed (a style sheet cannot tint a mask): they must be made from
    the current tokens by `packaging/make_theme_images.py`."""
    import importlib.util

    script = Path(__file__).resolve().parents[2] / "packaging" / "make_theme_images.py"
    spec = importlib.util.spec_from_file_location("make_theme_images", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    from PySide6.QtGui import QImage

    for name, tokens in itertools.product(module.ARROWS, theme.THEMES.values()):
        for suffix, size in (("", module.SIZE), ("@2x", module.SIZE * 2)):
            committed = QImage(str(module.ICONS / "theme" / f"{name}-{tokens.name}{suffix}.png"))
            assert committed == module.render(name, tokens.text_secondary, size), (
                name,
                tokens.name,
            )
    sheet = theme.stylesheet(LIGHT)
    assert "chevron-down-light.png" in sheet and "chevron-up-light.png" in sheet


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


def test_the_design_page_states_the_tokens_of_the_code() -> None:
    page = (Path(__file__).resolve().parents[2] / "docs" / "DESIGN.md").read_text(encoding="utf-8")
    for tokens in (LIGHT, DARK):
        for name in (
            "canvas",
            "surface",
            "raised",
            "hover",
            "selected",
            "border_subtle",
            "border_strong",
            "text",
            "text_secondary",
            "text_muted",
            "text_on_accent",
            "accent",
            "accent_hover",
            "accent_text",
        ):
            assert getattr(tokens, name) in page, (tokens.name, name)
        for level in Level:
            style = tokens.level(level)
            assert style.fg in page and style.bg in page, (tokens.name, level)
        for colour in tokens.series:
            assert colour in page, (tokens.name, colour)
    for level in Level:
        assert theme.LEVEL_ICONS[level] in page
    for status in Status:
        assert theme.STATUS_ICONS[status] in page
    for scale in ("11, 12, 13, 15, 18, 22", "4, 8, 12, 16, 24, 32", "90, 100, 110, 125"):
        assert scale in page
