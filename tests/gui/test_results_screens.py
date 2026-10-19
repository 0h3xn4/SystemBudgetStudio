"""The Results screens after the overhaul: the plot metrics at the UI scale, the labelled toolbar,
the table pane that folds, the one inline banner, wrapped paragraphs (D-178)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QLabel, QSplitter, QTableWidget, QWidget

from budget_gui import theme
from budget_gui.banner import Banner
from budget_gui.components import CollapseButton
from budget_gui.main_window import MainWindow
from budget_gui.plot_metrics import PLOT, STRIPS
from budget_gui.scenario_view import fill_table
from budget_gui.theme import Status

pytestmark = pytest.mark.gui
EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


@pytest.fixture
def window(qtbot, tmp_path: Path) -> MainWindow:  # type: ignore[no-untyped-def]
    shutil.copytree(EXAMPLES / "microsat_250kg", tmp_path / "p")  # placeholders: it is incomplete
    w = MainWindow()
    qtbot.addWidget(w, before_close_func=lambda win: win.editors.discard_all_changes())
    w.resize(1400, 860)
    w.show()
    w.open_project(tmp_path / "p")
    QApplication.processEvents()
    return w


def test_the_plot_sizes_follow_the_ui_scale() -> None:
    try:
        theme.manager().set_scale(125)
        assert PLOT.left == theme.px(theme.PLOT_MARGINS[0]) > theme.PLOT_MARGINS[0]
        assert STRIPS.row == theme.px(theme.STRIP_ROW) > theme.STRIP_ROW
        theme.manager().set_scale(100)
        assert PLOT.left == theme.PLOT_MARGINS[0] and STRIPS.left == theme.STRIP_MARGINS[0]
    finally:
        theme.manager().set_scale(100)


def test_the_toolbar_of_the_timeline_is_labelled_and_has_names(window: MainWindow) -> None:
    view = window.timeline_view
    for button, text in (
        (
            view.previous_violation,
            "",
        ),  # an icon with a tooltip and a name, after the word *Violation*
        (view.next_violation, ""),
        (view.compute_button, "Compute"),
        (view.export_button, "Export…"),
    ):
        assert button.text() == text and button.toolTip() and not button.icon().isNull()
    assert view.previous_violation.accessibleName() == "Previous violation"
    assert view.next_violation.accessibleName() == "Next violation"
    assert view.compute_button.kind == "secondary"  # Run is the one primary action


def test_the_table_pane_folds_away_and_comes_back(window: MainWindow) -> None:
    for view in (window.timeline_view, window.link_passes_view):
        window.show_view(view)
        QApplication.processEvents()
        splitter = view.body
        assert isinstance(splitter, QSplitter) and isinstance(view.fold_button, CollapseButton)
        assert not view.fold_button.is_folded() and "Hide" in view.fold_button.toolTip()
        before = splitter.sizes()
        assert before[1] > 0
        view.fold_button.click()
        assert view.fold_button.is_folded() and splitter.sizes()[1] == 0
        assert "Show" in view.fold_button.toolTip()
        view.fold_button.click()
        assert not view.fold_button.is_folded() and splitter.sizes()[1] > 0


def test_a_page_of_results_has_one_inline_banner_and_its_text_wraps(window: MainWindow) -> None:
    for view in (window.power_view, window.mass_view, window.thermal_view):
        window.show_view(view)
        QApplication.processEvents()
        assert isinstance(view.banner, Banner) and view.banner.kind == "incomplete"
        assert view.banner.isVisibleTo(window) and "INCOMPLETE" in view.banner.text()
    window.show_view(window.mass_view)
    page = window.mass_view.tabs.widget(0)
    page.ensure_built()
    labels = page.findChildren(QLabel)
    assert any(label.text().startswith("Body frame") and label.wordWrap() for label in labels)


def test_a_filled_table_shows_states_and_numbers_as_before(qtbot) -> None:  # type: ignore[no-untyped-def]
    table = QTableWidget()
    qtbot.addWidget(table)
    fill_table(
        table,
        ["name", "value", "state"],
        [["a", "1.5", "x"], ["b", "n/a", "y"], ["c", "2.5", "z"]],
        numeric={1},
        states={(2, 1): Status.FAIL},
    )
    from budget_gui.delegates import NUMERIC_ROLE, STATE_ROLE

    assert table.rowCount() == 3 and table.columnCount() == 3
    assert (
        table.item(0, 1).data(NUMERIC_ROLE) is True and table.item(0, 0).data(NUMERIC_ROLE) is None
    )
    assert table.item(1, 1).data(STATE_ROLE) == Status.NOT_CHECKED.value  # n/a is never zero
    assert table.item(2, 1).data(STATE_ROLE) == Status.FAIL.value
    assert not (table.item(0, 0).flags() & table.item(0, 0).flags().ItemIsEditable)
    assert isinstance(table, QWidget)
