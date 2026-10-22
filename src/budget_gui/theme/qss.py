"""The Qt palette and the style sheet, both made from the tokens (D-169).

No other module of the window sets a style sheet. A widget asks for a look with a dynamic property:
`kind` on a button (`primary`, `secondary` (the default), `ghost`, `danger`, `link`), `role` on a
label or a frame (`title`, `muted`, `chip`, ...), `size="compact"` for the 28 px height. The
sheet is generated at the UI scale in use, so it is made again when the scale changes.
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette

from budget_core.assets import assets_dir
from budget_gui.theme.scale import (
    BORDER,
    CONTROL_COMPACT,
    CONTROL_DEFAULT,
    FOCUS_RING,
    RADIUS_CONTROL,
    RADIUS_PANEL,
    SPACE,
    TYPE_BASE,
    TYPE_CAPTION,
    TYPE_DISPLAY,
    TYPE_HEADING,
    TYPE_SMALL,
    TYPE_TITLE,
    px,
)
from budget_gui.theme.tokens import Level, Tokens

CHIP_STATES = ("not_run", "running", "ok", "stale", "failed")
_ITEM_TEXT = "QTableView, QTreeView, QListView, QTableWidget, QListWidget"


def palette(t: Tokens) -> QPalette:
    pal = QPalette()
    roles = {
        QPalette.ColorRole.Window: t.canvas,
        QPalette.ColorRole.WindowText: t.text,
        QPalette.ColorRole.Base: t.surface,
        QPalette.ColorRole.AlternateBase: t.surface,
        QPalette.ColorRole.Text: t.text,
        QPalette.ColorRole.Button: t.surface,
        QPalette.ColorRole.ButtonText: t.text,
        QPalette.ColorRole.BrightText: t.text_on_accent,
        QPalette.ColorRole.ToolTipBase: t.raised,
        QPalette.ColorRole.ToolTipText: t.text,
        QPalette.ColorRole.PlaceholderText: t.text_muted,
        QPalette.ColorRole.Highlight: t.selected,
        QPalette.ColorRole.HighlightedText: t.text,
        QPalette.ColorRole.Link: t.accent_text,
        QPalette.ColorRole.LinkVisited: t.standby.fg,
        QPalette.ColorRole.Mid: t.border_subtle,
        QPalette.ColorRole.Midlight: t.hover,
        QPalette.ColorRole.Dark: t.border_strong,
        QPalette.ColorRole.Light: t.surface,
        QPalette.ColorRole.Shadow: t.border_strong,
    }
    for role, value in roles.items():
        pal.setColor(role, QColor(value))
    for role in (
        QPalette.ColorRole.Text,
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.ButtonText,
    ):
        pal.setColor(QPalette.ColorGroup.Disabled, role, QColor(t.text_muted))
    return pal


def chip_colours(t: Tokens, state: str) -> tuple[str, str]:
    """(text and icon colour, tint) of the run-status chip: the status palette, so a state looks
    the same wherever it appears. `running` is the one state that is not a verdict."""
    if state == "ok":
        style = t.normal
    elif state == "stale":
        style = t.caution
    elif state == "failed":
        style = t.critical
    elif state == "running":
        return (t.accent_text, t.selected)
    else:
        style = t.off
    return (style.fg, style.bg)


def banner_colours(t: Tokens, kind: str) -> tuple[str, str]:
    """(text and icon colour, tint) of a banner: `stale` and `incomplete` are cautions, `failed` is
    a failure."""
    style = t.critical if kind == "failed" else t.caution
    return (style.fg, style.bg)


def _chip_rules(t: Tokens) -> str:
    rules = []
    for state in CHIP_STATES:
        fg, bg = chip_colours(t, state)
        rules.append(
            f'QFrame[role="chip"][state="{state}"] {{ background: {bg}; }}\n'
            f'    QFrame[role="chip"][state="{state}"] QLabel {{ background: transparent; '
            f"color: {fg}; font-weight: 500; }}"
        )
    return "\n    ".join(rules)


def _banner_rules(t: Tokens) -> str:
    rules = []
    for kind in ("stale", "failed", "incomplete"):
        fg, bg = banner_colours(t, kind)
        rules.append(
            f'QFrame[role="banner-bar"][kind="{kind}"] {{ background: {bg}; }}\n'
            f'    QFrame[role="banner-bar"][kind="{kind}"] QLabel {{ background: transparent; '
            f"color: {fg}; }}\n"
            f'    QFrame[role="banner-bar"][kind="{kind}"] QPushButton[kind="link"] '
            f"{{ color: {fg}; font-weight: 500; }}"
        )
    return "\n    ".join(rules)


def _badge_rules(t: Tokens) -> str:
    """`QLabel[role="badge"][level="critical"]` ... : a status badge (icon and text beside it)."""
    return "\n    ".join(
        f'QLabel[role="badge"][level="{level.value}"] {{ background: {t.level(level).bg}; '
        f"color: {t.level(level).fg}; }}"
        for level in Level
    )


def _arrow_url(name: str, t: Tokens) -> str | None:
    """The file of an arrow in the colours of the theme (`packaging/make_theme_images.py`), as a
    style-sheet URL; None when the assets are missing (the arrow is then left out)."""
    try:
        path = assets_dir() / "icons" / "ui" / "theme" / f"{name}-{t.name}.png"
    except FileNotFoundError:
        return None
    return path.as_posix() if path.is_file() else None


def _tab_close_rules(t: Tokens) -> str:
    """The close mark of a tab (a file of the editor): a small x that gets a tint on hover; the
    style draws its own box without it."""
    mark = _arrow_url("x", t)
    rules = [
        "QTabBar::close-button { subcontrol-position: right; border: none;"
        f" background: transparent; border-radius: {px(RADIUS_CONTROL)}px;"
        f" margin: 0 {px(SPACE[0])}px;" + (f' image: url("{mark}");' if mark else "") + " }",
        f"QTabBar::close-button:hover {{ background: {t.hover}; }}",
    ]
    return "\n    ".join(rules)


def _drop_down_rules(t: Tokens) -> str:
    """The drop-down of a combo box and the buttons of a spin box: no frame of their own (the
    style draws a dark one), an arrow in the secondary text colour."""
    down, up = _arrow_url("chevron-down", t), _arrow_url("chevron-up", t)
    width, arrow = px(24), px(12)
    rules = [
        f"QComboBox::drop-down {{ subcontrol-origin: padding; subcontrol-position: center right;"
        f" width: {width}px; border: none; background: transparent; }}",
        "QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button,"
        " QDoubleSpinBox::down-button { border: none; background: transparent;"
        f" width: {px(20)}px; }}",
    ]
    if down:
        rules.append(
            f"QComboBox::down-arrow, QSpinBox::down-arrow, QDoubleSpinBox::down-arrow"
            f' {{ image: url("{down}"); width: {arrow}px; height: {arrow}px; }}'
        )
    if up:
        rules.append(
            f"QSpinBox::up-arrow, QDoubleSpinBox::up-arrow"
            f' {{ image: url("{up}"); width: {arrow}px; height: {arrow}px; }}'
        )
    return "\n    ".join(rules)


def document_css(t: Tokens) -> str:
    """The style of rich text shown in the window (the user guide): the page of the theme, not the
    white page of the exported file."""
    from budget_gui.theme.fonts import FONT_MONO, FONT_UI

    return f"""
    body {{ font-family: "{FONT_UI}"; color: {t.text}; background: {t.surface};
            font-size: {px(TYPE_BASE + 1)}px; line-height: 150%; }}
    h1, h2, h3 {{ font-weight: 600; color: {t.text}; }}
    h1 {{ font-size: {px(TYPE_DISPLAY)}px; margin-top: {px(SPACE[4])}px; }}
    h1.doc-title {{ margin-top: 0; }}
    h2 {{ font-size: {px(TYPE_HEADING)}px; margin-top: {px(SPACE[3])}px; }}
    h3 {{ font-size: {px(TYPE_TITLE)}px; margin-top: {px(SPACE[2])}px; }}
    a {{ color: {t.accent_text}; }}
    code, pre {{ font-family: "{FONT_MONO}"; font-size: {px(TYPE_SMALL)}px; }}
    code {{ background: {t.hover}; }}
    pre {{ background: {t.hover}; color: {t.text}; }}
    table {{ border-collapse: collapse; width: 100%; font-size: {px(TYPE_SMALL)}px; }}
    th {{ background: {t.hover}; text-align: left; color: {t.text_secondary}; }}
    th, td {{ border-bottom: {BORDER}px solid {t.border_subtle}; padding: {px(SPACE[0])}px; }}
    blockquote {{ background: {t.selected}; color: {t.text}; }}
    .meta {{ color: {t.text_secondary}; }}
    """


def stylesheet(t: Tokens) -> str:
    s0, s1, s2, s3 = SPACE[0], SPACE[1], SPACE[2], SPACE[3]
    h = px(CONTROL_DEFAULT - 2 * BORDER)  # content height: the border is added by the box model
    hc = px(CONTROL_COMPACT - 2 * BORDER)
    ring = FOCUS_RING
    rc, rp = px(RADIUS_CONTROL), px(RADIUS_PANEL)
    pad = px(s2)
    pad_ring = px(
        s2 - (ring - BORDER)
    )  # the ring is thicker than the border: padding gives it back
    return f"""
    QWidget {{ background: {t.surface}; color: {t.text}; font-size: {px(TYPE_BASE)}px; }}
    QMainWindow, QDialog {{ background: {t.canvas}; }}
    QMainWindow::separator {{ background: {t.canvas}; width: {px(s1)}px; height: {px(s1)}px; }}
    QStatusBar {{ background: {t.canvas}; color: {t.text_secondary};
                  font-size: {px(TYPE_SMALL)}px; }}
    QStatusBar::item {{ border: none; }}
    QStatusBar QLabel {{ background: transparent; }}
    QDockWidget {{ font-weight: 600; }}
    QDockWidget::title {{ background: {t.canvas}; color: {t.text_secondary};
                          padding: {px(s1)}px {px(s1)}px; font-size: {px(TYPE_SMALL)}px; }}
    QMenuBar {{ background: {t.canvas}; color: {t.text}; }}
    QMenuBar::item {{ background: transparent; padding: {px(s0)}px {px(s1)}px;
                      border-radius: {px(4)}px; }}
    QMenuBar::item:selected {{ background: {t.hover}; }}
    QMenu {{ background: {t.raised}; border: {BORDER}px solid {t.border_subtle};
             padding: {px(s0)}px; }}
    QMenu::item {{ padding: {px(s1 - 2)}px {px(s3)}px {px(s1 - 2)}px {px(s2)}px;
                   border-radius: {px(4)}px; }}
    QMenu::item:selected {{ background: {t.selected}; color: {t.text}; }}
    QMenu::item:disabled {{ color: {t.text_muted}; }}
    QMenu::separator {{ height: {BORDER}px; background: {t.border_subtle};
                        margin: {px(s0)}px {px(s1)}px; }}
    QToolTip {{ background: {t.raised}; color: {t.text}; border: {BORDER}px solid {t.border_subtle};
                padding: {px(s0)}px {px(s1)}px; }}

    QPushButton, QToolButton {{ background: {t.surface}; color: {t.text};
        border: {BORDER}px solid {t.border_strong}; border-radius: {rc}px;
        padding: 0 {pad}px; min-height: {h}px; }}
    QPushButton:hover, QToolButton:hover {{ background: {t.hover}; }}
    QPushButton:pressed, QToolButton:pressed {{ background: {t.selected}; }}
    QPushButton:checked, QToolButton:checked {{ background: {t.selected};
        border-color: {t.accent}; }}
    QPushButton:disabled, QToolButton:disabled {{ background: {t.canvas}; color: {t.text_muted};
        border-color: {t.border_subtle}; }}
    QPushButton[size="compact"], QToolButton[size="compact"] {{ min-height: {hc}px; }}
    QPushButton[kind="primary"] {{ background: {t.accent}; color: {t.text_on_accent};
        border-color: {t.accent}; }}
    QPushButton[kind="primary"]:hover {{ background: {t.accent_hover};
        border-color: {t.accent_hover}; }}
    QPushButton[kind="primary"]:pressed {{ background: {t.accent_hover}; }}
    QPushButton[kind="primary"]:disabled {{ background: {t.canvas}; color: {t.text_muted};
        border-color: {t.border_subtle}; }}
    QPushButton[kind="ghost"], QToolButton {{ background: transparent; color: {t.text_secondary};
        border-color: transparent; }}
    QPushButton[kind="ghost"]:hover, QToolButton:hover {{ background: {t.hover}; color: {t.text}; }}
    QPushButton[kind="ghost"]:checked, QToolButton:checked {{ background: {t.selected};
        color: {t.text}; }}
    QPushButton[kind="ghost"]:disabled, QToolButton:disabled {{ background: transparent;
        color: {t.text_muted}; }}
    QPushButton[kind="danger"] {{ background: {t.critical.fg}; color: {t.text_on_accent};
        border-color: {t.critical.fg}; }}
    QPushButton[kind="danger"]:hover {{ background: {t.critical.fg}; border-color: {t.text}; }}
    QPushButton[kind="link"] {{ background: transparent; color: {t.accent_text}; border: none;
        padding: 0 {px(s0)}px; min-height: 0; text-decoration: underline; }}
    QPushButton[kind="link"]:hover {{ background: transparent; color: {t.accent_hover}; }}
    QPushButton:focus, QToolButton:focus {{ border: {ring}px solid {t.focus};
        padding: 0 {pad_ring}px; min-height: {h - 2}px; }}
    QPushButton[size="compact"]:focus, QToolButton[size="compact"]:focus
        {{ min-height: {hc - 2}px; }}
    QPushButton[kind="primary"]:focus {{ border-color: {t.text}; }}
    QPushButton[kind="link"]:focus {{ border: {ring}px solid {t.focus}; min-height: 0;
        padding: 0 {px(s0)}px; }}

    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{ background: {t.surface}; color: {t.text};
        border: {BORDER}px solid {t.border_strong}; border-radius: {rc}px;
        padding: 0 {px(s1)}px; min-height: {h}px; selection-background-color: {t.selected};
        selection-color: {t.text}; }}
    QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover
        {{ border-color: {t.text_muted}; }}
    QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus
        {{ border: {ring}px solid {t.focus}; padding: 0 {px(s1 - (ring - BORDER))}px;
           min-height: {h - 2}px; }}
    QLineEdit:disabled, QComboBox:disabled {{ background: {t.canvas}; color: {t.text_muted};
        border-color: {t.border_subtle}; }}
    QLineEdit[size="compact"], QComboBox[size="compact"] {{ min-height: {hc}px; }}
    QComboBox QAbstractItemView {{ background: {t.raised};
        border: {BORDER}px solid {t.border_subtle};
        selection-background-color: {t.selected}; selection-color: {t.text}; outline: none; }}
    QPlainTextEdit, QTextEdit, QTextBrowser {{ background: {t.surface}; color: {t.text};
        border: {BORDER}px solid {t.border_subtle}; border-radius: {rc}px;
        selection-background-color: {t.selected}; selection-color: {t.text}; }}
    QPlainTextEdit:focus, QTextEdit:focus {{ border: {ring}px solid {t.focus}; }}
    QCheckBox, QRadioButton {{ background: transparent; spacing: {px(s1)}px; }}
    QCheckBox:focus, QRadioButton:focus {{ color: {t.text}; }}
    QGroupBox {{ border: none; margin: 0; padding: 0; font-weight: 600; }}

    {_ITEM_TEXT} {{ background: {t.surface}; color: {t.text}; border: none;
        gridline-color: {t.border_subtle}; alternate-background-color: {t.surface};
        selection-background-color: {t.selected}; selection-color: {t.text}; outline: none; }}
    QTableView::item, QTableWidget::item {{ padding: 0 {px(s1)}px; }}
    QTableView::item:hover, QTreeView::item:hover, QListView::item:hover
        {{ background: {t.hover}; }}
    QTableView::item:selected, QTreeView::item:selected, QListView::item:selected
        {{ background: {t.selected}; color: {t.text}; }}
    QTableView:focus, QTreeView:focus, QListView:focus, QTableWidget:focus, QListWidget:focus
        {{ border: {ring}px solid {t.focus}; }}
    QTableCornerButton::section {{ background: {t.surface}; border: none; }}
    QHeaderView::section {{ background: {t.surface}; color: {t.text_secondary}; border: none;
        border-bottom: {BORDER}px solid {t.border_subtle}; padding: {px(s0)}px {px(s1)}px;
        font-weight: 500; font-size: {px(TYPE_SMALL)}px; }}

    QTabWidget::pane {{ border: none; border-top: {BORDER}px solid {t.border_subtle}; }}
    QTabBar {{ background: transparent; }}
    QTabBar::tab {{ background: transparent; color: {t.text_secondary};
        padding: {px(s1)}px {px(s2)}px; border-bottom: {ring}px solid transparent;
        border-top-left-radius: {rc}px; border-top-right-radius: {rc}px; }}
    QTabBar::tab:hover {{ background: {t.hover}; color: {t.text}; }}
    QTabBar::tab:selected {{ color: {t.text}; border-bottom: {ring}px solid {t.accent}; }}
    QTabBar::tab:focus {{ border: {ring}px solid {t.focus}; }}
    QTabBar::tab:selected:focus {{ border: {ring}px solid {t.focus}; }}
    {_tab_close_rules(t)}

    QTabBar[role="segmented"]::tab {{ background: transparent; color: {t.text_secondary};
        padding: {px(s0 + 2)}px {px(s2)}px; margin-right: {px(2)}px; border: none;
        border-radius: {rc}px; }}
    QTabBar[role="segmented"]::tab:hover {{ background: {t.hover}; color: {t.text}; }}
    QTabBar[role="segmented"]::tab:selected {{ background: {t.selected}; color: {t.text};
        border: none; }}

    QToolBar {{ background: {t.canvas}; border: none; padding: 0; spacing: 0; }}
    QFrame[role="rail"] {{ background: {t.canvas}; }}
    QToolButton[role="rail-button"] {{ background: transparent; color: {t.text_secondary};
        border: {BORDER}px solid transparent; border-radius: {rc}px; padding: 0 {px(s1)}px;
        min-height: {h}px; font-weight: 500; text-align: left; }}
    QToolButton[role="rail-button"]:hover {{ background: {t.hover}; color: {t.text}; }}
    QToolButton[role="rail-button"]:checked {{ background: {t.selected}; color: {t.text}; }}
    QToolButton[role="rail-button"][toggle="true"]:checked {{ background: transparent; }}
    QToolButton[role="rail-button"]:disabled {{ background: transparent; color: {t.text_muted}; }}
    QToolButton[role="rail-button"]:focus {{ border: {ring}px solid {t.focus};
        padding: 0 {px(s1 - (ring - BORDER))}px; min-height: {h - 2}px; }}
    QWidget[role="panel-title"] {{ background: {t.canvas}; }}
    QWidget[role="panel-title"] QLabel {{ background: transparent; color: {t.text_secondary};
        font-weight: 600; font-size: {px(TYPE_SMALL)}px; }}

    QScrollBar:vertical {{ background: transparent; width: {px(10)}px; margin: 0; }}
    QScrollBar:horizontal {{ background: transparent; height: {px(10)}px; margin: 0; }}
    QScrollBar::handle {{ background: {t.border_strong}; border-radius: {px(3)}px;
        margin: {px(2)}px; }}
    QScrollBar::handle:vertical {{ min-height: {px(24)}px; }}
    QScrollBar::handle:horizontal {{ min-width: {px(24)}px; }}
    QScrollBar::handle:hover {{ background: {t.text_muted}; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
    QAbstractScrollArea {{ background: {t.surface}; }}
    QSplitter::handle {{ background: {t.canvas}; }}
    QProgressBar {{ background: {t.hover}; border: none; border-radius: {px(2)}px;
        max-height: {px(4)}px; text-align: center; color: transparent; }}
    QProgressBar::chunk {{ background: {t.accent}; border-radius: {px(2)}px; }}

    QFrame[role="card"] {{ background: {t.surface}; border: {BORDER}px solid {t.border_subtle};
        border-radius: {rp}px; }}
    QFrame[role="raised"], QDialog[role="raised"] {{ background: {t.raised};
        border: {BORDER}px solid {t.border_subtle}; border-radius: {rp}px; }}
    QFrame[role="empty"] {{ background: transparent; }}
    QFrame[role="segmented"] {{ background: {t.hover}; border: none; border-radius: {rc}px;
        padding: {px(2)}px; }}
    QFrame[role="segmented"] QPushButton {{ background: transparent;
        border: {ring}px solid transparent; border-radius: {rc - px(2)}px;
        padding: 0 {px(s1 - ring)}px; color: {t.text_secondary}; }}
    QFrame[role="segmented"] QPushButton:hover {{ color: {t.text}; }}
    QFrame[role="segmented"] QPushButton:checked {{ background: {t.surface}; color: {t.text}; }}
    QFrame[role="segmented"] QPushButton:focus {{ border: {ring}px solid {t.focus}; }}
    QLabel {{ background: transparent; }}
    QLabel[role="error"] {{ color: {t.critical.fg}; }}
    QLabel[role="section-title"] {{ font-weight: 600; font-size: {px(TYPE_TITLE)}px;
        padding-top: {px(s1 - 2)}px; }}
    QLabel[role="muted"] {{ color: {t.text_secondary}; }}
    QLabel[role="caption"] {{ font-size: {px(TYPE_CAPTION)}px; color: {t.text_muted}; }}
    QLabel[role="small"] {{ font-size: {px(TYPE_SMALL)}px; color: {t.text_secondary}; }}
    QLabel[role="title"] {{ font-size: {px(TYPE_TITLE)}px; font-weight: 600; }}
    QLabel[role="heading"] {{ font-size: {px(TYPE_HEADING)}px; font-weight: 600; }}
    QLabel[role="display"] {{ font-size: {px(TYPE_DISPLAY)}px; font-weight: 600; }}
    QLabel[role="dirty"] {{ color: {t.caution.fg}; font-weight: 500; }}
    QLabel[role="chip"] {{ padding: 1px {px(s1)}px; border-radius: {px(s3 // 2)}px;
        font-size: {px(TYPE_SMALL)}px; }}
    QFrame[role="chip"] {{ border-radius: {px(s3 // 2 + 2)}px; }}
    QLabel[role="badge"] {{ padding: 1px {px(s1)}px; border-radius: {rc}px;
        font-size: {px(TYPE_SMALL)}px; font-weight: 500; }}
    {_drop_down_rules(t)}
    {_badge_rules(t)}
    {_chip_rules(t)}
    {_banner_rules(t)}
    """
