"""Compare, Reports, the dialogs and the side panels after the overhaul (D-180)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QWizard

from budget_gui import theme
from budget_gui.components import Button, EmptyState
from budget_gui.grid_view import PastePreview
from budget_gui.guided import GuidedWizard
from budget_gui.legend import LegendDialog
from budget_gui.main_window import MainWindow
from tests.helpers import edit

pytestmark = pytest.mark.gui
EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


@pytest.fixture
def window(qtbot, tmp_path: Path) -> MainWindow:  # type: ignore[no-untyped-def]
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", tmp_path / "a")
    w = MainWindow()
    qtbot.addWidget(w, before_close_func=lambda win: win.editors.discard_all_changes())
    w.resize(1400, 860)
    w.show()
    w.open_project(tmp_path / "a")
    QApplication.processEvents()
    return w


# ---- Compare ---------------------------------------------------------------------------------
def test_compare_says_what_to_do_until_there_is_a_result(window: MainWindow) -> None:
    view = window.compare_view
    window.show_view(view)
    assert view.empty_state.isVisibleTo(view) and not view.table.isVisibleTo(view)
    assert isinstance(view.empty_state, EmptyState) and view.empty_state.button is None
    assert view.compare_button.kind == "primary"  # the one primary action of the page


def test_the_key_columns_never_push_the_values_out(
    window: MainWindow,
    qtbot,  # type: ignore[no-untyped-def]
    tmp_path: Path,
) -> None:
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", tmp_path / "b")
    edit(tmp_path / "b", "units/adcs.yaml", "avg_power_w: 7.0", "avg_power_w: 9.0")
    view = window.compare_view
    window.show_view(view)
    view.set_other_folder(tmp_path / "b")
    with qtbot.waitSignal(view.computed, timeout=120000):
        view.compare()
    QApplication.processEvents()
    assert view.table.isVisibleTo(view) and not view.empty_state.isVisibleTo(view)
    header = view.table.horizontalHeader()
    for column, cap in enumerate(theme.COMPARE_KEY_WIDTHS):
        assert header.sectionSize(column) <= theme.px(cap)
    # A, B and the change are in view without scrolling sideways
    last = header.sectionViewportPosition(6) + header.sectionSize(6)
    assert last <= view.table.viewport().width()
    first = view.table.item(0, 0)
    assert first is not None and first.toolTip() == first.text()  # the full name is in the tooltip


# ---- Reports ---------------------------------------------------------------------------------
def test_the_reports_page_says_the_provenance_in_a_line_and_keeps_the_rows_a_click_away(
    window: MainWindow,
) -> None:
    view = window.reports_view
    window.show_view(view)
    QApplication.processEvents()
    assert "System Budget Studio" in view.provenance_summary.text()
    assert "revision" in view.provenance_summary.text()
    assert view.provenance_table.isHidden() and view.provenance_table.rowCount() > 0
    view.provenance_toggle.click()
    assert not view.provenance_table.isHidden() and view.provenance_toggle.text() == "Hide details"
    view.provenance_toggle.click()
    assert view.provenance_table.isHidden()


def test_the_results_list_is_an_empty_state_until_files_are_written(window: MainWindow) -> None:
    view = window.reports_view
    window.show_view(view)
    assert view.results_empty.isVisibleTo(view) and not view.results.isVisibleTo(view)
    view.show_results([str(Path("/tmp") / "a.csv")])
    assert view.results.isVisibleTo(view) and not view.results_empty.isVisibleTo(view)
    view.set_busy(True)
    assert view.results_empty.isVisibleTo(view)
    view.set_busy(False)
    assert view.export_button.kind == "primary" and view.browse_button.kind == "secondary"


# ---- dialogs ---------------------------------------------------------------------------------
def test_the_paste_preview_has_one_primary_button_and_the_figures_in_mono(qtbot) -> None:  # type: ignore[no-untyped-def]
    dialog = PastePreview([("Unit / mass_kg", "1.2", "1.4")], 1, None)
    qtbot.addWidget(dialog)
    assert isinstance(dialog.apply_button, Button) and dialog.apply_button.kind == "primary"
    assert dialog.apply_button.isDefault()
    from PySide6.QtWidgets import QTableWidget

    grid = dialog.findChild(QTableWidget)
    assert grid is not None and grid.focusPolicy() == Qt.FocusPolicy.NoFocus
    assert grid.item(0, 1).font().family() == theme.mono_font().family()


def test_the_wizard_has_one_primary_button_per_page(qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    wizard = GuidedWizard(tmp_path)
    qtbot.addWidget(wizard)
    wizard.show()
    kinds = {
        which: wizard.button(which).property("kind")
        for which in (
            QWizard.WizardButton.NextButton,
            QWizard.WizardButton.FinishButton,
            QWizard.WizardButton.BackButton,
            QWizard.WizardButton.CancelButton,
        )
    }
    assert kinds[QWizard.WizardButton.NextButton] == "primary"
    assert kinds[QWizard.WizardButton.FinishButton] == "primary"
    assert kinds[QWizard.WizardButton.BackButton] == kinds[QWizard.WizardButton.CancelButton]
    assert kinds[QWizard.WizardButton.CancelButton] == "secondary"


def test_the_cell_style_legend_shows_every_row_without_scrolling(qtbot) -> None:  # type: ignore[no-untyped-def]
    dialog = LegendDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    QApplication.processEvents()
    legend = dialog.legend
    total = sum(legend.rowHeight(r) for r in range(legend.model().rowCount()))
    assert total <= legend.viewport().height()
    assert legend.focusPolicy() == Qt.FocusPolicy.NoFocus


# ---- the side panels -------------------------------------------------------------------------
def test_the_inspector_says_what_to_select_and_the_provenance_values_wrap(
    window: MainWindow,
) -> None:
    inspector = window.inspector
    assert isinstance(inspector.empty, EmptyState)
    panel = window.provenance_panel
    assert panel.table.textElideMode() == Qt.TextElideMode.ElideNone
    assert panel.table.wordWrap()
