"""The layout file keeps only window geometry, dock state, column widths and the theme (D-150)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QByteArray

from budget_gui import layout_settings
from budget_gui.layout_settings import GROUPS, LayoutError, LayoutSettings


@pytest.fixture
def settings(tmp_path: Path) -> LayoutSettings:
    return LayoutSettings(tmp_path / "layout.ini")


def test_geometry_widths_and_a_theme_name_round_trip(
    settings: LayoutSettings, tmp_path: Path
) -> None:
    settings.set_bytes("window/geometry", QByteArray(b"\x01\x02\x03"))
    settings.set_int_list("columns/units", [120, 80, 64])
    settings.set_word("theme/mode", "dark", ("light", "dark", "system"))
    settings.sync()
    again = LayoutSettings(tmp_path / "layout.ini")
    assert bytes(again.bytes_value("window/geometry") or b"") == b"\x01\x02\x03"
    assert again.int_list("columns/units") == [120, 80, 64]
    assert again.word("theme/mode", ("light", "dark", "system"), "system") == "dark"


@pytest.mark.parametrize(
    "key",
    [
        "recent/project",
        "projects",
        "window",
        "window/",
        "../escape",
        "dialog/last_folder",
        "theme/a b",
    ],
)
def test_a_key_outside_the_four_groups_is_refused(settings: LayoutSettings, key: str) -> None:
    with pytest.raises(LayoutError):
        settings.set_word(key, "dark", ("dark",))
    with pytest.raises(LayoutError):
        settings.int_list(key)


def test_a_name_that_is_not_allowed_is_refused_and_a_stored_one_falls_back(
    settings: LayoutSettings,
) -> None:
    with pytest.raises(LayoutError):
        settings.set_word("theme/mode", "/home/me/secret project", ("light", "dark"))
    assert settings.word("theme/mode", ("light", "dark"), "light") == "light"


def test_the_file_holds_only_the_four_groups(settings: LayoutSettings, tmp_path: Path) -> None:
    settings.set_bytes("window/geometry", QByteArray(b"x"))
    settings.set_bytes("dock/state", QByteArray(b"y"))
    settings.set_int_list("columns/power", [1, 2])
    settings.set_word("theme/mode", "light", ("light",))
    settings.sync()
    sections = {
        line.strip("[]")
        for line in (tmp_path / "layout.ini").read_text().splitlines()
        if line.startswith("[")
    }
    assert sections <= set(GROUPS) | {"General"}


def test_a_damaged_value_gives_an_empty_answer(settings: LayoutSettings, tmp_path: Path) -> None:
    (tmp_path / "layout.ini").write_text("[columns]\nunits=abc,2\n", encoding="utf-8")
    assert LayoutSettings(tmp_path / "layout.ini").int_list("columns/units") == []


def test_without_a_path_nothing_is_read_or_written(tmp_path: Path) -> None:
    off = LayoutSettings(None)
    off.set_bytes("window/geometry", QByteArray(b"x"))
    off.set_word("theme/mode", "dark", ("dark",))
    assert off.bytes_value("window/geometry") is None
    assert off.word("theme/mode", ("dark",), "x") == "x"
    assert off.path is None and not list(tmp_path.iterdir())


def test_the_place_follows_the_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("BUDGET_NO_LAYOUT", raising=False)
    monkeypatch.setenv("BUDGET_CONFIG_DIR", str(tmp_path))
    assert layout_settings.default_path() == tmp_path / "layout.ini"
    monkeypatch.setenv("BUDGET_NO_LAYOUT", "1")
    assert layout_settings.default_path() is None
