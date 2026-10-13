"""IBM Carbon theme (white and g100) with bundled IBM Plex fonts. No web resources."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QFont, QFontDatabase, QIcon
from PySide6.QtWidgets import QApplication

from budget_core.assets import assets_dir, icon_files


@dataclass(frozen=True)
class CarbonTokens:
    background: str
    layer: str
    border: str
    text: str
    text_secondary: str
    interactive: str
    interactive_text: str


WHITE = CarbonTokens("#ffffff", "#f4f4f4", "#e0e0e0", "#161616", "#525252", "#0f62fe", "#ffffff")
G100 = CarbonTokens("#161616", "#262626", "#393939", "#f4f4f4", "#c6c6c6", "#4589ff", "#ffffff")
THEMES = {"white": WHITE, "g100": G100}

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


def stylesheet(t: CarbonTokens) -> str:
    return f"""
    QWidget {{ background: {t.background}; color: {t.text}; font-size: 14px; }}
    QMainWindow, QDialog {{ background: {t.background}; }}
    QStatusBar, QDockWidget::title {{ background: {t.layer}; color: {t.text_secondary}; }}
    QPushButton {{ background: {t.interactive}; color: {t.interactive_text};
                   border: 2px solid {t.interactive}; padding: 8px 14px; }}
    QPushButton:disabled {{ background: {t.border}; color: {t.text_secondary};
                            border: 2px solid {t.border}; }}
    QPushButton:focus {{ border: 2px solid {t.text}; }}
    QLineEdit:focus, QPlainTextEdit:focus, QTableView:focus, QTreeView:focus, QComboBox:focus,
    QListWidget:focus {{ border: 2px solid {t.interactive}; }}
    QTableView, QTreeView, QLineEdit {{ background: {t.layer}; border: 1px solid {t.border}; }}
    QHeaderView::section {{ background: {t.layer}; border: none;
                            border-bottom: 1px solid {t.border}; padding: 6px; }}
    QTabBar::tab {{ background: {t.layer}; color: {t.text_secondary}; padding: 8px 16px;
                    border-bottom: 2px solid transparent; }}
    QTabBar::tab:selected {{ background: {t.background}; color: {t.text};
                             border-bottom: 2px solid {t.interactive}; }}
    QTabWidget::pane {{ border-top: 1px solid {t.border}; }}
    QDockWidget {{ font-weight: 600; }}
    QDockWidget::title {{ padding: 6px; }}
    QMenuBar, QMenu {{ background: {t.layer}; }}
    QMenu::item:selected {{ background: {t.border}; }}
    QTableView, QTableWidget {{ gridline-color: {t.border};
                                alternate-background-color: {t.layer}; }}
    QPlainTextEdit {{ background: {t.background}; border: 1px solid {t.border}; }}
    """


def app_icon() -> QIcon:
    """The application icon (D-148): PNG files of 16 to 256 px, so no SVG plugin is needed. An
    empty icon when the files are missing; the window still opens."""
    icon = QIcon()
    for path in icon_files():
        icon.addFile(str(path))
    return icon


def apply_theme(app: QApplication, name: str = "white") -> None:
    load_fonts()
    app.setFont(QFont("IBM Plex Sans", 10))
    app.setStyleSheet(stylesheet(THEMES[name]))
