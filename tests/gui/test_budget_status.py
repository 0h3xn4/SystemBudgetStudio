"""Status cells and limit bars in the Mass, Thermal and Link tables (UX step 4, D-164)."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt

from budget_core.reports.document import Column, Table
from budget_gui.delegates import MARGIN_ROLE, STATE_ROLE
from budget_gui.theme import Status
from budget_gui.widgets import DocTableModel

TOOLTIP = Qt.ItemDataRole.ToolTipRole


def limits_table(*rows: tuple[object, ...]) -> Table:
    return Table(
        "Mass limits",
        (
            Column("Phase"),
            Column("Limit"),
            Column("Limit value (kg)", "number", 3),
            Column("Total (kg)", "number", 3),
            Column("Margin (kg)", "number", 3),
            Column("Status"),
        ),
        tuple(rows),  # type: ignore[arg-type]
        status_column=5,
        status_marks=(3, 4),
        bar=(3, 2),
    )


def state(model: DocTableModel, row: int, column: int) -> object:
    return model.index(row, column).data(STATE_ROLE)


def test_a_status_word_colours_its_cell_and_the_cells_marked_with_it() -> None:
    model = DocTableModel(
        limits_table(
            ("launch", "Launch mass", 300.0, 250.0, 50.0, "ok"),
            ("launch", "Launch mass", 300.0, 295.0, 5.0, "margin"),
            ("launch", "Launch mass", 300.0, 310.0, -10.0, "exceeded"),
            ("launch", "Launch mass", None, 250.0, None, "n/a"),
        )
    )
    assert [state(model, r, 5) for r in range(4)] == ["pass", "near", "fail", "not_checked"]
    assert [state(model, r, 3) for r in range(4)] == ["pass", "near", "fail", "not_checked"]
    assert state(model, 0, 4) == "pass"
    assert state(model, 0, 2) is None and state(model, 0, 0) is None  # the limit value and phase


def test_a_cell_that_is_n_a_is_not_checked_even_outside_the_status_columns() -> None:
    model = DocTableModel(limits_table(("launch", "x", None, 250.0, None, "n/a")))
    assert state(model, 0, 2) == Status.NOT_CHECKED.value


def test_the_bar_is_the_share_of_the_limit_and_only_on_the_value_column() -> None:
    model = DocTableModel(
        limits_table(
            ("p", "l", 300.0, 150.0, 150.0, "ok"),
            ("p", "l", 300.0, 330.0, -30.0, "exceeded"),
            ("p", "l", None, 330.0, None, "n/a"),
            ("p", "l", 0.0, 1.0, None, "n/a"),
        )
    )
    shares = [model.index(r, 3).data(MARGIN_ROLE) for r in range(4)]
    assert shares[0] == pytest.approx(0.5) and shares[1] == pytest.approx(1.1)
    assert shares[2] is None and shares[3] is None  # no limit, or a limit of nothing
    assert model.index(0, 2).data(MARGIN_ROLE) is None  # not the limit column


def test_a_table_without_a_status_column_has_no_states() -> None:
    table = Table("t", (Column("a"), Column("b", "number", 1)), (("ok", 1.0), ("no", 2.0)))
    model = DocTableModel(table)
    assert state(model, 0, 0) is None and model.index(0, 1).data(MARGIN_ROLE) is None


def test_the_tooltip_of_a_state_says_what_it_means() -> None:
    model = DocTableModel(limits_table(("p", "l", 300.0, 310.0, -10.0, "exceeded")))
    assert "limit" in str(model.index(0, 5).data(TOOLTIP)).lower()


def test_thermal_and_link_words_have_states() -> None:
    table = Table(
        "t",
        (Column("Unit"), Column("Temperature (K)", "number", 2), Column("Status")),
        (
            ("a", 250.0, "ok"),
            ("b", 330.0, "margin"),
            ("c", 360.0, "exceeded"),
            ("d", 250.0, "no limits"),
            ("e", 250.0, "ok (margin not checked)"),
            ("f", 250.0, "yes"),
            ("g", 250.0, "no"),
        ),
        status_column=2,
        status_marks=(1,),
    )
    model = DocTableModel(table)
    assert [state(model, r, 1) for r in range(7)] == [
        "pass",
        "near",
        "fail",
        "not_checked",
        "not_checked",
        "pass",
        "fail",
    ]


def test_the_declared_columns_of_the_real_reports_are_the_ones_that_mean_it(qtbot) -> None:  # type: ignore[no-untyped-def]
    import shutil
    from pathlib import Path

    from budget_gui.main_window import MainWindow

    examples = Path(__file__).resolve().parents[2] / "examples"
    window = MainWindow()
    qtbot.addWidget(window, before_close_func=lambda w: w.editors.discard_all_changes())
    import tempfile

    with tempfile.TemporaryDirectory() as folder:
        shutil.copytree(examples / "microsat_250kg_eps", Path(folder) / "p")
        window.open_project(Path(folder) / "p")
        session = window.session
        marked = 0
        for document in (session.mass_document, session.thermal_document, session.link_document):
            assert document is not None
            for section in document.sections:
                for table in section.tables:
                    if table.status_column is None:
                        continue
                    marked += 1
                    header = table.columns[table.status_column].header
                    assert header in ("Status", "Closes"), table.title
                    for column in table.status_marks:
                        assert table.columns[column].kind == "number", table.title
                    if table.bar:
                        assert all(table.columns[c].kind == "number" for c in table.bar)
        assert marked >= 4  # mass limits, two thermal cases, the rate table
