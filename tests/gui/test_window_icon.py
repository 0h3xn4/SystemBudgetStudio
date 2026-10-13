"""The window and the application have the logo as their icon (D-148)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon, QImage
from PySide6.QtWidgets import QApplication

from budget_core.assets import icon_files
from budget_gui.app import create_app
from budget_gui.main_window import MainWindow
from budget_gui.theme import app_icon

SIZES = [16, 24, 32, 48, 64, 128, 256]


def test_the_icon_files_are_there_in_every_size_and_square() -> None:
    files = icon_files()
    assert [int(f.stem.split("-")[1]) for f in files] == SIZES
    for file in files:
        size = int(file.stem.split("-")[1])
        image = QImage(str(file))
        assert (image.width(), image.height()) == (size, size)
        assert image.hasAlphaChannel()


def test_the_corners_are_transparent_and_the_middle_is_the_logo() -> None:
    image = QImage(str(icon_files()[-1])).convertToFormat(QImage.Format.Format_ARGB32)
    assert image.pixelColor(0, 0).alpha() == 0  # the rounded corner shows what is behind
    centre = image.pixelColor(128, 150)
    assert centre.alpha() == 255 and centre.name() != "#ffffff"
    assert image.pixelColor(180, 150).name() == "#f4f4f4"  # the tallest bar


def test_the_application_icon_has_every_size(qtbot) -> None:  # type: ignore[no-untyped-def]
    icon = app_icon()
    assert not icon.isNull()
    available = {(s.width(), s.height()) for s in icon.availableSizes()}
    assert available == {(n, n) for n in SIZES}
    assert not icon.pixmap(QSize(32, 32)).isNull()


def test_create_app_sets_the_window_icon_of_the_application(qtbot) -> None:  # type: ignore[no-untyped-def]
    app = create_app(["x"])
    assert not app.windowIcon().isNull()
    assert not QApplication.windowIcon().isNull()


def test_the_main_window_shows_the_icon(qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    create_app(["x"])
    window = MainWindow()
    qtbot.addWidget(window)
    # a window takes the icon of the application unless it sets its own
    assert not window.windowIcon().isNull()
    assert window.windowIcon().pixmap(QSize(48, 48)).size().width() > 0


def test_missing_icon_files_leave_an_empty_icon_and_the_window_still_opens(
    monkeypatch: pytest.MonkeyPatch, qtbot
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr("budget_gui.theme.icon_files", lambda: [])
    assert app_icon().isNull()
    assert isinstance(app_icon(), QIcon)
    window = MainWindow()
    qtbot.addWidget(window)
