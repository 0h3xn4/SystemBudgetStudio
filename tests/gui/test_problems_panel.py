"""The Problems panel: classes, order, filter, grouping, jumping (UX step 1, D-151)."""

from __future__ import annotations

import pytest

from budget_core.problems import Problem, Severity
from budget_gui import problem_class as pc
from budget_gui.problem_class import ProblemClass
from budget_gui.problems_panel import Grouping, ProblemsPanel


def make(
    severity: Severity, code: str, message: str, file: str | None = None, path: str = ""
) -> Problem:
    return Problem(severity, code, message, file=file, path=path)


SAMPLE = [
    make(Severity.INFO, "MASS_INERTIA_POINT_MASS", "Treated as a point mass.", "units/a.yaml"),
    make(
        Severity.WARNING,
        "CONFIG_PLACEHOLDER",
        "This number is a placeholder.",
        "config/m.yaml",
        "x",
    ),
    make(Severity.WARNING, "CONFIG_EMPTY_TABLE", "The table has no entries.", "config/t.yaml"),
    make(Severity.ERROR, "REF_UNKNOWN_BUS", "Unknown bus.", "units/b.yaml", "bus"),
    make(Severity.WARNING, "RESULT_INCOMPLETE", "A result is incomplete.", "config/m.yaml", "y"),
    make(
        Severity.WARNING,
        "THERMAL_NO_LIMITS",
        "Unit has no limits; it is not checked.",
        "units/a.yaml",
    ),
]


@pytest.fixture
def panel(qtbot) -> ProblemsPanel:  # type: ignore[no-untyped-def]
    widget = ProblemsPanel()
    qtbot.addWidget(widget)
    widget.set_problems(SAMPLE)
    return widget


def test_a_placeholder_is_not_checked_not_a_plain_warning() -> None:
    by_code = {p.code: pc.classify(p) for p in SAMPLE}
    assert by_code["CONFIG_PLACEHOLDER"] is ProblemClass.NOT_CHECKED
    assert by_code["RESULT_INCOMPLETE"] is ProblemClass.NOT_CHECKED
    assert by_code["THERMAL_NO_LIMITS"] is ProblemClass.NOT_CHECKED
    assert by_code["CONFIG_EMPTY_TABLE"] is ProblemClass.WARNING
    assert by_code["REF_UNKNOWN_BUS"] is ProblemClass.ERROR
    assert by_code["MASS_INERTIA_POINT_MASS"] is ProblemClass.INFO


def test_an_error_stays_an_error_even_with_a_not_checked_code() -> None:
    problem = make(Severity.ERROR, "CONFIG_PLACEHOLDER", "x")
    assert pc.classify(problem) is ProblemClass.ERROR


def test_every_class_has_an_icon_a_word_and_a_colour() -> None:
    for cls in ProblemClass:
        assert pc.LABELS[cls] and pc.ICONS[cls] and pc.colour(cls).startswith("#")
    assert len({pc.ICONS[cls] for cls in ProblemClass}) == 4  # never colour alone


def test_the_order_is_error_warning_not_checked_info(panel: ProblemsPanel) -> None:
    classes = [pc.classify(p) for p in panel.visible_problems]
    assert classes == sorted(classes, key=lambda c: pc.RANK[c])
    assert panel.codes()[0] == "REF_UNKNOWN_BUS"
    assert panel.codes()[-1] == "MASS_INERTIA_POINT_MASS"


def test_the_summary_counts_each_class(panel: ProblemsPanel) -> None:
    assert panel.summary.text() == "1 error, 1 warning, 3 not checked, 1 info"
    panel.set_problems([])
    assert panel.summary.text() == "0 errors, 0 warnings"


def test_the_filter_text_matches_message_file_field_and_code(panel: ProblemsPanel) -> None:
    panel.set_filter_text("config/m.yaml")
    assert set(panel.codes()) == {"CONFIG_PLACEHOLDER", "RESULT_INCOMPLETE"}
    panel.set_filter_text("bus")
    assert panel.codes() == ["REF_UNKNOWN_BUS"]
    panel.set_filter_text("no_such_thing")
    assert panel.codes() == [] and "No problem matches" in panel.empty.text()
    assert "showing 0 of 6" in panel.summary.text()
    panel.set_filter_text("")
    assert len(panel.codes()) == 6


def test_the_class_filter_shows_one_class(panel: ProblemsPanel) -> None:
    panel.set_class_filter(ProblemClass.NOT_CHECKED)
    assert len(panel.codes()) == 3 and panel.class_filter() is ProblemClass.NOT_CHECKED
    panel.set_class_filter(None)
    assert len(panel.codes()) == 6


def test_grouping_by_class_and_by_file(panel: ProblemsPanel) -> None:
    panel.set_grouping(Grouping.CLASS)
    titles = [panel.list_model.item(r, 0).text() for r in range(panel.list_model.rowCount())]
    assert titles == ["Error (1)", "Warning (1)", "Not checked (3)", "Info (1)"]
    panel.set_grouping(Grouping.FILE)
    titles = [panel.list_model.item(r, 0).text() for r in range(panel.list_model.rowCount())]
    assert titles[0] == "config/m.yaml (2)" and "units/a.yaml (2)" in titles
    assert len(panel.codes()) == 6  # the groups hold every problem once
    panel.set_grouping(Grouping.NONE)
    assert panel.list_model.rowCount() == 6


def test_jumping_uses_the_shown_order(panel: ProblemsPanel) -> None:
    jumps: list[tuple[str, int]] = []
    panel.jump_requested.connect(lambda f, line: jumps.append((f, line)))
    panel.activate_row(0)
    assert jumps == [("units/b.yaml", 1)]
    panel.set_class_filter(ProblemClass.NOT_CHECKED)
    panel.activate_row(0)
    assert jumps[-1][0] in {"config/m.yaml", "units/a.yaml"}


def test_next_and_previous_move_through_the_list_and_wrap(panel: ProblemsPanel) -> None:
    first = panel.select_next(1)
    assert first is not None and first.code == "REF_UNKNOWN_BUS"
    second = panel.select_next(1)
    assert second is not None and second is panel.visible_problems[1]
    assert panel.select_next(-1) is panel.visible_problems[0]
    assert panel.select_next(-1) is panel.visible_problems[-1]  # wraps to the end
    assert panel.current_problem() is panel.visible_problems[-1]


def test_the_selection_survives_a_new_list(panel: ProblemsPanel) -> None:
    panel.select_row(2)
    chosen = panel.current_problem()
    assert chosen is not None
    panel.set_problems(list(reversed(SAMPLE)))
    assert panel.current_problem() == chosen


def test_empty_states_say_what_is_going_on(qtbot) -> None:  # type: ignore[no-untyped-def]
    panel = ProblemsPanel()
    qtbot.addWidget(panel)
    panel.set_problems([], project_open=False)
    assert panel.summary.text() == "No project open" and "Open a project" in panel.empty.text()
    panel.set_problems([])
    assert "No problems" in panel.empty.text()


def test_a_placeholder_heavy_project_is_listed_quickly(qtbot) -> None:  # type: ignore[no-untyped-def]
    import time

    panel = ProblemsPanel()
    qtbot.addWidget(panel)
    many = [
        make(
            Severity.WARNING,
            "CONFIG_PLACEHOLDER",
            f"Placeholder {i}.",
            f"units/u{i % 40}.yaml",
            "p",
        )
        for i in range(400)
    ]
    start = time.perf_counter()
    panel.set_problems(many)
    assert time.perf_counter() - start < 1.0  # generous: ~0.1 s in practice
    assert len(panel.codes()) == 400
