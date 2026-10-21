"""The blank project in the guided wizard (D-185): no orbit and no scenario are asked for, the bus
voltage is, and the window opens on the empty Units page instead of computing a timeline."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QWizard

from budget_core.io.project_loader import load_project
from budget_gui.guided import BLANK, GuidedWizard
from budget_gui.main_window import MainWindow

pytestmark = pytest.mark.gui


@pytest.fixture
def window(qtbot) -> MainWindow:  # type: ignore[no-untyped-def]
    w = MainWindow()
    qtbot.addWidget(w, before_close_func=lambda win: win.editors.discard_all_changes())
    return w


def choose_blank(wizard: GuidedWizard) -> None:
    wizard.sample_combo.setCurrentIndex(wizard.sample_combo.findData(BLANK))


def test_blank_is_the_last_choice_and_not_the_default(qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    wizard = GuidedWizard(tmp_path)
    qtbot.addWidget(wizard)
    assert wizard.sample_combo.itemData(wizard.sample_combo.count() - 1) == BLANK
    assert not wizard.is_blank()  # the existing four-clicks path is unchanged


def test_the_bus_fields_show_only_for_a_blank_project(qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    wizard = GuidedWizard(tmp_path)
    qtbot.addWidget(wizard)
    wizard.show()
    wizard.next()  # the spacecraft page
    page = wizard.currentPage()
    assert not wizard.bus_voltage.isVisibleTo(page)
    choose_blank(wizard)
    assert wizard.bus_voltage.isVisibleTo(page) and wizard.bus_name_edit.isVisibleTo(page)
    wizard.sample_combo.setCurrentIndex(0)
    assert not wizard.bus_voltage.isVisibleTo(page)


def test_the_voltage_has_no_default_and_blocks_next_until_given(qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    wizard = GuidedWizard(tmp_path)
    qtbot.addWidget(wizard)
    wizard.next()
    choose_blank(wizard)
    assert wizard.bus_voltage.value() == 0.0 and wizard.bus_voltage.specialValueText() == "not set"
    assert not wizard.currentPage().isComplete()
    assert "voltage" in wizard.error_label.text().lower()
    wizard.bus_voltage.setValue(28.0)
    assert wizard.currentPage().isComplete()
    assert wizard.error_label.text() == ""
    wizard.bus_name_edit.setText("  ")
    assert not wizard.currentPage().isComplete()
    assert "bus" in wizard.error_label.text().lower()


def test_orbit_and_scenario_are_skipped(qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    wizard = GuidedWizard(tmp_path)
    qtbot.addWidget(wizard)
    wizard.next()
    choose_blank(wizard)
    wizard.bus_voltage.setValue(28.0)
    wizard.next()
    assert wizard.currentPage().title() == "Review"
    assert wizard.button(QWizard.WizardButton.FinishButton).isEnabled()
    text = wizard.review.text()
    assert "blank project" in text and "28 V" in text
    assert "Orbit" not in text and "Scenario:" not in text
    assert "computes" not in wizard.currentPage().subTitle()
    wizard.back()
    assert wizard.currentPage().title() == "Spacecraft"  # Back does not go through the orbit


def test_a_sample_still_goes_through_all_five_pages(qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    wizard = GuidedWizard(tmp_path)
    qtbot.addWidget(wizard)
    choose_blank(wizard)
    wizard.sample_combo.setCurrentIndex(0)  # changed his mind
    visited = [wizard.currentPage().title()]
    for _ in range(4):
        wizard.next()
        visited.append(wizard.currentPage().title())
    assert visited == ["Project", "Spacecraft", "Orbit", "Scenario", "Review"]
    assert "computes the first power timeline" in wizard.currentPage().subTitle()


def test_a_wrong_project_name_blocks_the_first_page(qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    wizard = GuidedWizard(tmp_path)
    qtbot.addWidget(wizard)
    choose_blank(wizard)
    wizard.name_edit.setText("   ")
    assert not wizard.currentPage().isComplete()
    assert "name" in wizard.error_label.text().lower()


def test_finish_writes_the_blank_project_and_nothing_else(qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    wizard = GuidedWizard(tmp_path)
    qtbot.addWidget(wizard)
    wizard.name_edit.setText("Blank one")
    wizard.next()
    choose_blank(wizard)
    wizard.bus_voltage.setValue(12.0)
    wizard.bus_name_edit.setText("power")
    wizard.next()
    with qtbot.waitSignal(wizard.created) as made:
        wizard.accept()
    folder = made.args[0]
    assert folder == tmp_path / "blank-one"
    project = load_project(folder).project
    assert project is not None
    assert [(b.name, b.nominal_voltage_v) for b in project.spacecraft.buses] == [("power", 12.0)]
    assert not (project.units or project.scenarios or project.orbits)


def test_the_window_opens_a_blank_project_on_the_units_page_without_computing(
    window: MainWindow,
    tmp_path: Path,
    qtbot,  # type: ignore[no-untyped-def]
) -> None:
    wizard = window.open_guided_wizard(tmp_path)
    qtbot.addWidget(wizard)
    wizard.name_edit.setText("Window blank")
    wizard.next()
    choose_blank(wizard)
    wizard.bus_voltage.setValue(28.0)
    wizard.next()
    wizard.accept()
    qtbot.waitUntil(lambda: window.session.project is not None, timeout=20000)
    assert window.session.project is not None
    assert window.session.project.meta.name == "Window blank"
    assert window.timeline_view.result is None  # nothing was computed
    assert window.workspace.is_showing(window.units_page)
    assert "blank project is open" in window.statusBar().currentMessage()
