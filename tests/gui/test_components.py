"""The component library: every component in both themes (D-169)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from PySide6.QtCore import QtMsgType, qInstallMessageHandler
from PySide6.QtWidgets import QApplication, QDialog, QWidget

from budget_gui import theme
from budget_gui.components import (
    Button,
    Card,
    EmptyState,
    KeyValueList,
    MessageDialog,
    SectionHeader,
    SegmentedControl,
    StatusBadge,
    Toast,
    icon_button,
)
from budget_gui.theme import Level, Mode

pytestmark = pytest.mark.gui
BOTH = pytest.mark.parametrize("mode", [Mode.LIGHT, Mode.DARK], ids=["light", "dark"])


@pytest.fixture
def messages():  # type: ignore[no-untyped-def]
    """The messages Qt prints (a style sheet it cannot parse, an unknown property) while a test
    runs; a test asserts there are none."""
    seen: list[str] = []

    def handler(kind: QtMsgType, _context: object, text: str) -> None:
        if kind != QtMsgType.QtDebugMsg:
            seen.append(text)

    previous = qInstallMessageHandler(handler)
    yield seen
    qInstallMessageHandler(previous)


def _gallery_module():  # type: ignore[no-untyped-def]
    script = Path(__file__).resolve().parents[2] / "scripts" / "ui_gallery.py"
    spec = importlib.util.spec_from_file_location("ui_gallery", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@BOTH
def test_the_gallery_builds_in_both_themes_and_qt_has_no_complaint(  # type: ignore[no-untyped-def]
    qtbot, mode: Mode, messages: list[str]
) -> None:
    app = QApplication.instance()
    assert isinstance(app, QApplication)
    theme.manager().set_mode(mode, app)
    page = _gallery_module().build_gallery()
    qtbot.addWidget(page)
    page.resize(900, 1400)
    page.show()
    assert not page.grab().isNull()
    assert [m for m in messages if "tylesheet" in m or "property" in m or "parse" in m] == []


@BOTH
def test_a_button_has_a_kind_and_its_icon_follows_the_theme(qtbot, mode: Mode) -> None:  # type: ignore[no-untyped-def]
    theme.manager().set_mode(mode)
    primary = Button("Run", "primary", icon="play", tip="Run all", shortcut="Ctrl+R")
    qtbot.addWidget(primary)
    assert primary.kind == "primary" and primary.toolTip() == "Run all (Ctrl+R)"
    before = primary.icon().cacheKey()
    theme.manager().set_mode(Mode.DARK if mode is Mode.LIGHT else Mode.LIGHT)
    assert primary.icon().cacheKey() != before  # tinted again for the other theme
    primary.set_kind("secondary")
    assert primary.kind == "secondary"
    with pytest.raises(ValueError):
        Button("x", "huge")


def test_an_icon_button_has_a_name_for_screen_readers(qtbot) -> None:  # type: ignore[no-untyped-def]
    button = icon_button("search", "Find a command", shortcut="Ctrl+K")
    qtbot.addWidget(button)
    assert button.accessibleName() == "Find a command"
    assert "Ctrl+K" in button.toolTip() and button.text() == ""


@BOTH
def test_a_badge_has_text_and_an_icon_for_every_level(qtbot, mode: Mode) -> None:  # type: ignore[no-untyped-def]
    theme.manager().set_mode(mode)
    for level in Level:
        badge = StatusBadge(level, level.value)
        qtbot.addWidget(badge)
        assert badge.text() == level.value and badge.level is level
        assert badge.accessibleName() == f"{level.value}: {level.value}"
        assert not badge._icon.pixmap().isNull()
    badge.set_level(Level.CRITICAL, "Limit broken")
    assert badge.text() == "Limit broken" and badge.level is Level.CRITICAL


def test_the_segmented_control_chooses_one(qtbot) -> None:  # type: ignore[no-untyped-def]
    control = SegmentedControl([("bol", "BOL"), ("eol", "EOL")], current="eol")
    qtbot.addWidget(control)
    assert control.current() == "eol"
    with qtbot.waitSignal(control.changed) as blocker:
        control.button("bol").click()
    assert blocker.args == ["bol"] and control.current() == "bol"
    control.set_current("eol")
    assert control.current() == "eol" and not control.button("bol").isChecked()


def test_key_values_and_section_header(qtbot) -> None:  # type: ignore[no-untyped-def]
    pairs = KeyValueList()
    qtbot.addWidget(pairs)
    pairs.set_items([("Tool", "System Budget Studio"), ("Scenario", "one_day")])
    assert pairs.values() == {"Tool": "System Budget Studio", "Scenario": "one_day"}
    pairs.set_items([("Only", "one")])
    assert pairs.values() == {"Only": "one"}
    header = SectionHeader("Provenance")
    qtbot.addWidget(header)
    header.add_action(Button("Copy", "ghost"))
    assert header.title.text() == "Provenance"
    assert Card().property("role") == "card"


def test_an_empty_state_offers_the_primary_action(qtbot) -> None:  # type: ignore[no-untyped-def]
    state = EmptyState("No violations.", "Compute", icon="circle-check")
    qtbot.addWidget(state)
    assert state.button is not None and state.button.kind == "primary"
    with qtbot.waitSignal(state.action_requested):
        state.button.click()
    assert EmptyState("Nothing here.").button is None


def test_a_toast_shows_then_goes_by_itself(qtbot) -> None:  # type: ignore[no-untyped-def]
    host = QWidget()
    qtbot.addWidget(host)
    host.resize(600, 400)
    host.show()
    toast = Toast(host)
    toast.show_message("Saved", ms=50)
    assert toast.isVisible() and toast.text() == "Saved"
    assert toast.x() + toast.width() <= host.width() and toast.y() + toast.height() <= host.height()
    qtbot.waitUntil(lambda: not toast.isVisible(), timeout=2000)
    toast.show_message("Exported 3 files")  # a new one replaces the text, no stacking
    assert toast.text() == "Exported 3 files"


def test_a_destructive_question_never_defaults_to_the_destructive_answer(qtbot) -> None:  # type: ignore[no-untyped-def]
    dialog = MessageDialog(
        "Discard changes?",
        "This file has unsaved changes.",
        primary="Discard",
        secondary="Keep editing",
        destructive=True,
        level=Level.CAUTION,
    )
    qtbot.addWidget(dialog)
    assert dialog.primary_button.kind == "danger"
    assert dialog.secondary_button is not None and dialog.secondary_button.isDefault()
    assert not dialog.primary_button.isDefault()
    dialog.show()
    dialog.primary_button.click()
    assert dialog.result() == QDialog.DialogCode.Accepted
    other = MessageDialog("Saved", "Nothing else to do.", detail="Written to disk.")
    qtbot.addWidget(other)
    assert other.primary_button.isDefault() and other.secondary_button is None
    assert other.detail_label.text() == "Written to disk."


@BOTH
def test_every_component_paints_in_both_themes(qtbot, mode: Mode) -> None:  # type: ignore[no-untyped-def]
    theme.manager().set_mode(mode)
    page = QWidget()
    qtbot.addWidget(page)
    for widget in (
        Button("Primary", "primary"),
        Button("Danger", "danger"),
        StatusBadge(Level.NORMAL, "Normal"),
        SegmentedControl([("a", "A"), ("b", "B")]),
        EmptyState("Empty", "Go"),
        Card(),
    ):
        widget.setParent(page)
        widget.show()
        assert not widget.grab().isNull()


def test_the_guide_is_shown_in_the_colours_and_fonts_of_the_theme(qtbot) -> None:  # type: ignore[no-untyped-def]
    from budget_gui.help_view import GuideDialog

    theme.manager().set_mode(Mode.LIGHT)
    dialog = GuideDialog(None)
    qtbot.addWidget(dialog)
    html = dialog.browser.toHtml()
    assert "IBM Plex" not in html and theme.FONT_UI in html
    theme.manager().set_mode(Mode.DARK)  # the page follows the theme without a restart
    assert theme.DARK.surface.lstrip("#") in dialog.browser.toHtml().lower().replace("#", "")
    theme.manager().set_mode(Mode.LIGHT)
