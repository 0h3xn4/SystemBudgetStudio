"""The theme: one module that makes every colour, font and size of the window (D-150).

Colours live here and nowhere else (a test checks that no other module of the window holds a
colour literal). A theme is a set of `Tokens` (IBM Carbon *white* for the light theme, *g100* for
the dark one); from the tokens this module makes the `QPalette` and the style sheet, and the
`ThemeManager` applies them, follows the operating system when the mode is *system*, and tells
widgets that paint themselves (the plots) to draw again.

Status colours (pass, near the limit, fail, not checked, placeholder) are defined once, each with
a text colour, a background tint and an icon, so a status is never told by colour alone. Every
text colour reaches a contrast of 4.5 : 1 on the surface it is used on in both themes (a test
computes it).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontDatabase, QGuiApplication, QIcon, QPalette
from PySide6.QtWidgets import QApplication

from budget_core.assets import assets_dir, icon_files

# ---- scales ------------------------------------------------------------------------------------
SPACE = (4, 8, 12, 16, 24, 32)  # px: the only gaps and paddings
TYPE_SMALL, TYPE_BASE, TYPE_TITLE, TYPE_HEADING = 12, 13, 16, 20  # px
FONT_UI, FONT_MONO = "IBM Plex Sans", "IBM Plex Mono"


class Mode(StrEnum):
    """What the user chose: a fixed theme, or whatever the operating system uses."""

    LIGHT = "light"
    DARK = "dark"
    SYSTEM = "system"


class Status(StrEnum):
    """The state of a number or a limit. `NOT_CHECKED` is also what `n/a` means: a result that
    could not be computed or a limit that could not be checked because an input is a placeholder."""

    PASS = "pass"
    NEAR = "near"
    FAIL = "fail"
    NOT_CHECKED = "not_checked"
    PLACEHOLDER = "placeholder"


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


@dataclass(frozen=True)
class StatusStyle:
    fg: str  # text and icon colour, 4.5 : 1 on `background`, on `layer` and on `bg`
    bg: str  # tint behind a cell or a chip


@dataclass(frozen=True)
class Tokens:
    name: str
    dark: bool
    # surfaces and text
    background: str
    layer: str
    border: str
    border_strong: str
    text: str
    text_secondary: str
    text_disabled: str
    text_on_accent: str
    accent: str  # fill of the primary action
    accent_hover: str
    accent_text: str  # links and accent text on `background`
    focus: str
    selection_bg: str
    selection_text: str
    # status
    s_pass: StatusStyle
    s_near: StatusStyle
    s_fail: StatusStyle
    s_not_checked: StatusStyle
    s_placeholder: StatusStyle
    info: str
    # plots (series colours of the core are mapped, see `plot_colour`)
    plot_bg: str
    plot_grid: str
    plot_ink: str
    plot_muted: str
    plot_readout_bg: str
    band_alpha: int
    # the scenario timeline strips
    strip_sunlit: str
    strip_eclipse: str
    strip_umbra: str
    strip_pass: str
    strip_track: str
    categorical: tuple[str, ...]
    selection_overlay: tuple[int, int, int, int]
    # comparison rows and the file editor
    diff_changed: str
    diff_added: str
    diff_removed: str
    diff_now_computed: str
    diff_now_na: str
    gutter_bg: str
    gutter_text: str
    line_highlight: str

    def color(self, value: str) -> QColor:
        return QColor(value)

    def status(self, status: Status) -> StatusStyle:
        return {
            Status.PASS: self.s_pass,
            Status.NEAR: self.s_near,
            Status.FAIL: self.s_fail,
            Status.NOT_CHECKED: self.s_not_checked,
            Status.PLACEHOLDER: self.s_placeholder,
        }[status]


# Colours the core uses for plot series and bands (budget_core.plots.spec; they are chosen for a
# white page and are shared with the reports). The window draws them lighter on the dark theme.
_CORE_TO_DARK = {
    "#161616": "#f4f4f4",  # INK
    "#0f62fe": "#4589ff",  # BLUE
    "#da1e28": "#fa4d56",  # RED
    "#198038": "#42be65",  # GREEN
    "#8a3ffc": "#be95ff",  # PURPLE
    "#007d79": "#08bdba",  # TEAL
    "#8d8d8d": "#a8a8a8",  # GREY
    "#c6c6c6": "#525252",  # BAND_ECLIPSE
    "#a6c8ff": "#4589ff",  # BAND_COLORS
    "#9ef0f0": "#08bdba",
    "#d4bbff": "#a56eff",
    "#ffd6e8": "#ee5396",
    "#ffd9be": "#ff832b",
}

LIGHT = Tokens(
    name="light",
    dark=False,
    background="#ffffff",
    layer="#f4f4f4",
    border="#e0e0e0",
    border_strong="#8d8d8d",
    text="#161616",
    text_secondary="#525252",
    text_disabled="#6f6f6f",
    text_on_accent="#ffffff",
    accent="#0f62fe",
    accent_hover="#0050e6",
    accent_text="#0f62fe",
    focus="#0f62fe",
    selection_bg="#d0e2ff",
    selection_text="#161616",
    s_pass=StatusStyle("#0e6027", "#defbe6"),
    s_near=StatusStyle("#7a5d00", "#fcf4d6"),
    s_fail=StatusStyle("#a2191f", "#fff1f1"),
    s_not_checked=StatusStyle("#525252", "#e8e8e8"),
    s_placeholder=StatusStyle("#6929c4", "#f6f2ff"),
    info="#0043ce",
    plot_bg="#ffffff",
    plot_grid="#e0e0e0",
    plot_ink="#161616",
    plot_muted="#525252",
    plot_readout_bg="#ebffffff",  # Qt reads #AARRGGBB
    band_alpha=140,
    strip_sunlit="#fcf4d6",
    strip_eclipse="#525252",
    strip_umbra="#161616",
    strip_pass="#0f62fe",
    strip_track="#e0e0e0",
    categorical=(
        "#6929c4",
        "#1192e8",
        "#005d5d",
        "#9f1853",
        "#fa4d56",
        "#198038",
        "#002d9c",
        "#ee538b",
        "#b28600",
        "#009d9a",
        "#8a3800",
        "#a56eff",
        "#570408",
        "#012749",
    ),
    selection_overlay=(15, 98, 254, 60),
    diff_changed="#fcf4d6",
    diff_added="#defbe6",
    diff_removed="#fff1f1",
    diff_now_computed="#edf5ff",
    diff_now_na="#e8daff",
    gutter_bg="#f4f4f4",
    gutter_text="#6f6f6f",
    line_highlight="#fcf4d6",
)

DARK = Tokens(
    name="dark",
    dark=True,
    background="#161616",
    layer="#262626",
    border="#393939",
    border_strong="#6f6f6f",
    text="#f4f4f4",
    text_secondary="#c6c6c6",
    text_disabled="#8d8d8d",
    text_on_accent="#ffffff",
    accent="#0f62fe",
    accent_hover="#0353e9",
    accent_text="#78a9ff",
    focus="#ffffff",
    selection_bg="#0043ce",
    selection_text="#ffffff",
    s_pass=StatusStyle("#42be65", "#044317"),
    s_near=StatusStyle("#f1c21b", "#3d3200"),
    s_fail=StatusStyle("#ff8389", "#520408"),
    s_not_checked=StatusStyle("#a8a8a8", "#393939"),
    s_placeholder=StatusStyle("#be95ff", "#31135e"),
    info="#78a9ff",
    plot_bg="#161616",
    plot_grid="#393939",
    plot_ink="#f4f4f4",
    plot_muted="#c6c6c6",
    plot_readout_bg="#eb262626",
    band_alpha=110,
    strip_sunlit="#4d3f00",
    strip_eclipse="#6f6f6f",
    strip_umbra="#000000",
    strip_pass="#4589ff",
    strip_track="#393939",
    categorical=(
        "#a56eff",
        "#33b1ff",
        "#08bdba",
        "#ee5396",
        "#ff8389",
        "#42be65",
        "#78a9ff",
        "#ff7eb6",
        "#f1c21b",
        "#3ddbd9",
        "#ff832b",
        "#be95ff",
        "#ffb3b8",
        "#a6c8ff",
    ),
    selection_overlay=(120, 169, 255, 70),
    diff_changed="#3d3200",
    diff_added="#044317",
    diff_removed="#520408",
    diff_now_computed="#001d6c",
    diff_now_na="#31135e",
    gutter_bg="#262626",
    gutter_text="#8d8d8d",
    line_highlight="#3d3200",
)

# the names the first version of this module had
WHITE, G100 = LIGHT, DARK
THEMES = {"white": LIGHT, "g100": DARK, "light": LIGHT, "dark": DARK}


def plot_colour(tokens: Tokens, core_colour: str) -> QColor:
    """The colour to draw a plot series, limit line or band that the core gave in `core_colour`
    (made for a white page): the same on the light theme, a lighter one on the dark theme. A colour
    the core does not know is drawn as it is."""
    if tokens.dark:
        return QColor(_CORE_TO_DARK.get(core_colour.lower(), core_colour))
    return QColor(core_colour)


def severity_colour(tokens: Tokens, severity: str) -> str:
    """The text colour of a problem: errors `fail`, warnings `near`, information `info`."""
    if severity == "error":
        return tokens.s_fail.fg
    if severity == "warning":
        return tokens.s_near.fg
    return tokens.info


def contrast_ratio(foreground: str, background: str) -> float:
    """WCAG contrast ratio of two #RRGGBB colours (4.5 is the minimum for text)."""

    def luminance(colour: str) -> float:
        c = QColor(colour)
        parts = []
        for channel in (c.redF(), c.greenF(), c.blueF()):
            parts.append(
                channel / 12.92 if channel <= 0.03928 else ((channel + 0.055) / 1.055) ** 2.4
            )
        return 0.2126 * parts[0] + 0.7152 * parts[1] + 0.0722 * parts[2]

    a, b = luminance(foreground), luminance(background)
    lighter, darker = max(a, b), min(a, b)
    return (lighter + 0.05) / (darker + 0.05)


def readable_text(background: str) -> QColor:
    """Black or white, whichever reads better on `background` (the labels on coloured bars)."""
    light, dark = "#ffffff", "#161616"
    return QColor(
        light if contrast_ratio(light, background) >= contrast_ratio(dark, background) else dark
    )


# ---- fonts -------------------------------------------------------------------------------------
_FONT_FILES = (
    "IBMPlexSans-Light.ttf",
    "IBMPlexSans-Regular.ttf",
    "IBMPlexSans-SemiBold.ttf",
    "IBMPlexMono-Regular.ttf",
    "IBMPlexMono-SemiBold.ttf",
)


def load_fonts() -> list[str]:
    """Register the bundled IBM Plex fonts; return the family names that loaded."""
    families: list[str] = []
    try:
        fonts = assets_dir() / "fonts"
    except FileNotFoundError:  # no bundled fonts: the system font is used, the window still opens
        return families
    for name in _FONT_FILES:
        font_id = QFontDatabase.addApplicationFont(str(fonts / name))
        if font_id >= 0:
            families.extend(QFontDatabase.applicationFontFamilies(font_id))
    return sorted(set(families))


def ui_font(pixel_size: int = TYPE_BASE, *, bold: bool = False) -> QFont:
    font = QFont(FONT_UI)
    font.setPixelSize(pixel_size)
    font.setWeight(QFont.Weight.DemiBold if bold else QFont.Weight.Normal)
    return font


def mono_font(pixel_size: int = TYPE_BASE, *, bold: bool = False) -> QFont:
    """IBM Plex Mono, for numbers, identifiers and file paths: every digit has the same width."""
    font = QFont(FONT_MONO)
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.setPixelSize(pixel_size)
    font.setWeight(QFont.Weight.DemiBold if bold else QFont.Weight.Normal)
    return font


# ---- palette and style sheet -------------------------------------------------------------------
def palette(t: Tokens) -> QPalette:
    pal = QPalette()
    roles = {
        QPalette.ColorRole.Window: t.background,
        QPalette.ColorRole.WindowText: t.text,
        QPalette.ColorRole.Base: t.layer,
        QPalette.ColorRole.AlternateBase: t.background,
        QPalette.ColorRole.Text: t.text,
        QPalette.ColorRole.Button: t.accent,
        QPalette.ColorRole.ButtonText: t.text_on_accent,
        QPalette.ColorRole.BrightText: t.text_on_accent,
        QPalette.ColorRole.ToolTipBase: t.layer,
        QPalette.ColorRole.ToolTipText: t.text,
        QPalette.ColorRole.PlaceholderText: t.text_disabled,
        QPalette.ColorRole.Highlight: t.selection_bg,
        QPalette.ColorRole.HighlightedText: t.selection_text,
        QPalette.ColorRole.Link: t.accent_text,
        QPalette.ColorRole.LinkVisited: t.s_placeholder.fg,
        QPalette.ColorRole.Mid: t.border,
        QPalette.ColorRole.Midlight: t.layer,
        QPalette.ColorRole.Dark: t.border_strong,
        QPalette.ColorRole.Light: t.background,
        QPalette.ColorRole.Shadow: t.border_strong,
    }
    for role, value in roles.items():
        pal.setColor(role, QColor(value))
    for role in (
        QPalette.ColorRole.Text,
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.ButtonText,
    ):
        pal.setColor(QPalette.ColorGroup.Disabled, role, QColor(t.text_disabled))
    return pal


CHIP_STATES = ("not_run", "running", "ok", "stale", "failed")


def chip_colours(t: Tokens, state: str) -> tuple[str, str]:
    """(text and icon colour, tint) of the run-status chip: the status palette, so a state looks
    the same wherever it appears. `running` is the one state that is not a verdict."""
    if state == "ok":
        style = t.s_pass
    elif state == "stale":
        style = t.s_near
    elif state == "failed":
        style = t.s_fail
    elif state == "running":
        return (t.accent_text, t.layer)
    else:
        style = t.s_not_checked
    return (style.fg, style.bg)


def _chip_rules(t: Tokens) -> str:
    rules = []
    for state in CHIP_STATES:
        fg, bg = chip_colours(t, state)
        rules.append(
            f'QFrame[role="chip"][state="{state}"] {{ background: {bg}; }}\n'
            f'    QFrame[role="chip"][state="{state}"] QLabel {{ background: transparent; '
            f"color: {fg}; font-weight: 600; }}"
        )
    return "\n    ".join(rules)


def stylesheet(t: Tokens) -> str:
    s1, s2, s3 = SPACE[1], SPACE[2], SPACE[3]
    return f"""
    QWidget {{ background: {t.background}; color: {t.text}; font-size: {TYPE_BASE}px; }}
    QMainWindow, QDialog {{ background: {t.background}; }}
    QStatusBar, QDockWidget::title {{ background: {t.layer}; color: {t.text_secondary}; }}
    QPushButton {{ background: {t.accent}; color: {t.text_on_accent};
                   border: 2px solid {t.accent}; padding: {s1}px {s2}px; }}
    QPushButton:hover {{ background: {t.accent_hover}; border-color: {t.accent_hover}; }}
    QPushButton:disabled {{ background: {t.border}; color: {t.text_disabled};
                            border: 2px solid {t.border}; }}
    QPushButton:focus {{ border: 2px solid {t.focus}; }}
    QPushButton[kind="secondary"] {{ background: {t.background}; color: {t.accent_text};
                                     border: 1px solid {t.accent_text}; }}
    QPushButton[kind="secondary"]:hover {{ background: {t.layer}; }}
    QPushButton[kind="secondary"]:checked {{ background: {t.selection_bg};
                                             color: {t.selection_text}; }}
    QPushButton[kind="danger"] {{ background: {t.s_fail.fg}; border-color: {t.s_fail.fg};
                                  color: {t.background}; }}
    QPushButton[kind="link"] {{ background: transparent; color: {t.accent_text}; border: none;
                                padding: 0 {s1}px; text-decoration: underline; }}
    QPushButton[kind="link"]:hover {{ background: transparent; color: {t.accent_hover}; }}
    QPushButton[kind="link"]:focus {{ border: 2px solid {t.focus}; }}
    QStatusBar QLabel {{ background: transparent; }}
    QLineEdit:focus, QPlainTextEdit:focus, QTableView:focus, QTreeView:focus, QComboBox:focus,
    QListWidget:focus {{ border: 2px solid {t.focus}; }}
    QTableView, QTreeView, QLineEdit {{ background: {t.layer}; border: 1px solid {t.border}; }}
    QHeaderView::section {{ background: {t.layer}; border: none; color: {t.text_secondary};
                            border-bottom: 1px solid {t.border}; padding: {SPACE[0] + 2}px; }}
    QTabBar::tab {{ background: {t.layer}; color: {t.text_secondary}; padding: {s1}px {s3}px;
                    border-bottom: 2px solid transparent; }}
    QTabBar::tab:selected {{ background: {t.background}; color: {t.text};
                             border-bottom: 2px solid {t.accent_text}; }}
    QTabWidget::pane {{ border-top: 1px solid {t.border}; }}
    QDockWidget {{ font-weight: 600; }}
    QDockWidget::title {{ padding: {SPACE[1] - 2}px; }}
    QMenuBar, QMenu {{ background: {t.layer}; }}
    QMenu::item:selected {{ background: {t.selection_bg}; color: {t.selection_text}; }}
    QMenu::separator {{ height: 1px; background: {t.border}; margin: {SPACE[0]}px 0; }}
    QTableView, QTableWidget {{ gridline-color: {t.border}; alternate-background-color: {t.layer};
                                selection-background-color: {t.selection_bg};
                                selection-color: {t.selection_text}; }}
    QPlainTextEdit {{ background: {t.background}; border: 1px solid {t.border}; }}
    QToolTip {{ background: {t.layer}; color: {t.text}; border: 1px solid {t.border_strong};
                padding: {SPACE[0]}px; }}
    QLabel[role="error"] {{ color: {t.s_fail.fg}; }}
    QLabel[role="banner"] {{ color: {t.s_fail.fg}; font-weight: 600; padding: {SPACE[0]}px; }}
    QLabel[role="section-title"] {{ font-weight: 600; padding-top: {SPACE[1] - 2}px; }}
    QLabel[role="muted"] {{ color: {t.text_secondary}; }}
    QLabel[role="heading"] {{ font-size: {TYPE_HEADING}px; font-weight: 600; }}
    QLabel[role="title"] {{ font-size: {TYPE_TITLE}px; font-weight: 600; }}
    QLabel[role="small"] {{ font-size: {TYPE_SMALL}px; color: {t.text_secondary}; }}
    QLabel[role="chip"] {{ padding: 1px {s1}px; border-radius: {s3 // 2}px;
                           font-size: {TYPE_SMALL}px; }}
    QFrame[role="chip"] {{ border-radius: {s3 // 2 + 2}px; }}
    {_chip_rules(t)}
    QLabel[role="dirty"] {{ color: {t.s_near.fg}; font-weight: 600; }}
    """


# ---- the manager -------------------------------------------------------------------------------
def system_is_dark() -> bool:
    """True when the operating system (Qt 6.5 and later) says it uses a dark colour scheme."""
    hints = QGuiApplication.styleHints()
    return hints is not None and hints.colorScheme() == Qt.ColorScheme.Dark


class ThemeManager(QObject):
    """The theme in use. Widgets that paint with `tokens()` connect to `changed` to draw again."""

    changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._mode = Mode.LIGHT
        self._tokens = LIGHT
        self._hooked = False

    @property
    def mode(self) -> Mode:
        return self._mode

    @property
    def tokens(self) -> Tokens:
        return self._tokens

    def set_mode(self, mode: Mode | str, app: QApplication | None = None) -> None:
        self._mode = Mode(mode) if not isinstance(mode, Mode) else mode
        self.apply(app)

    def _resolve(self) -> Tokens:
        if self._mode is Mode.LIGHT:
            return LIGHT
        if self._mode is Mode.DARK:
            return DARK
        return DARK if system_is_dark() else LIGHT

    def apply(self, app: QApplication | None = None) -> None:
        app = app or QApplication.instance()  # type: ignore[assignment]
        self._tokens = self._resolve()
        if isinstance(app, QApplication):
            if not self._hooked and app.styleHints() is not None:
                app.styleHints().colorSchemeChanged.connect(self._system_changed)
                self._hooked = True
            app.setStyle("Fusion")  # one look on every platform, coloured by the palette
            app.setPalette(palette(self._tokens))
            app.setFont(ui_font())
            app.setStyleSheet(stylesheet(self._tokens))
        self.changed.emit()

    def _system_changed(self, *_args: object) -> None:
        if self._mode is Mode.SYSTEM:
            self.apply()


_MANAGER: ThemeManager | None = None


def manager() -> ThemeManager:
    global _MANAGER
    if _MANAGER is None:
        _MANAGER = ThemeManager()
    return _MANAGER


def tokens() -> Tokens:
    """The tokens of the theme in use."""
    return manager().tokens


def app_icon() -> QIcon:
    """The application icon (D-148): PNG files of 16 to 256 px, so no SVG plugin is needed. An
    empty icon when the files are missing; the window still opens."""
    icon = QIcon()
    for path in icon_files():
        icon.addFile(str(path))
    return icon


def apply_theme(app: QApplication, name: Mode | str = Mode.LIGHT) -> None:
    """Load the fonts and apply the theme (`light`, `dark` or `system`; the old names `white` and
    `g100` still work)."""
    load_fonts()
    mode = {"white": Mode.LIGHT, "g100": Mode.DARK}.get(str(getattr(name, "value", name)), name)
    manager().set_mode(mode, app)
