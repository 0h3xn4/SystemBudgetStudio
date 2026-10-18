"""The scenario editor: rules as sentences, one undo stack, one Save (UX step 2c, D-160)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from budget_core.io.project_loader import load_project
from budget_gui.main_window import MainWindow
from budget_gui.scenario_editor import ScenarioEditor, rule_sentence, segment_sentence

pytestmark = pytest.mark.gui

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
REL = "scenarios/one_day.yaml"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", tmp_path / "p")
    return tmp_path / "p"


@pytest.fixture
def window(qtbot, project: Path):  # type: ignore[no-untyped-def]
    w = MainWindow()
    qtbot.addWidget(w, before_close_func=lambda win: win.editors.discard_all_changes())
    w.open_project(project)
    return w


@pytest.fixture
def editor(window: MainWindow) -> ScenarioEditor:
    return window.scenario_view.editor


def test_a_rule_reads_as_a_sentence() -> None:
    assert rule_sentence({"kind": "in_eclipse", "mode": "nominal"}) == "Nominal while in eclipse"
    assert (
        rule_sentence({"kind": "during_pass", "mode": "downlink", "site": "gs_north"})
        == "Downlink during every pass over gs_north"
    )
    assert (
        rule_sentence(
            {"kind": "during_pass", "mode": "imaging", "site": "tgt", "lead_s": 30.0, "lag_s": 5.5}
        )
        == "Imaging during every pass over tgt, from 30 s before to 5.5 s after"
    )
    assert (
        rule_sentence({"kind": "in_sunlight", "mode": "charging"}) == "Charging while in sunlight"
    )
    assert (
        segment_sentence({"mode": "imaging", "start_s": 100.0, "duration_s": 300.0})
        == "Imaging from T+100 s for 300 s"
    )


def test_the_rules_of_the_example_are_shown_as_sentences(editor: ScenarioEditor) -> None:
    assert [editor.rule_text(i) for i in range(editor.rule_count())] == [
        "Nominal while in eclipse",
        "Imaging during every pass over tgt_plains, from 30 s before to 0 s after",
        "Downlink during every pass over gs_north",
        "Downlink during every pass over gs_south",
    ]
    assert editor.rule_rows[1].accessibleName().startswith("Imaging during every pass over")


def test_the_controls_show_the_rule_and_hide_what_does_not_apply(editor: ScenarioEditor) -> None:
    eclipse, imaging = editor.rule_rows[0], editor.rule_rows[1]
    assert eclipse.mode.currentText() == "nominal" and eclipse.when.currentIndex() == 1
    assert eclipse.site.isHidden() and eclipse.timing.isHidden()  # no site, no lead or lag
    assert not imaging.site.isHidden() and imaging.site.currentText() == "tgt_plains"
    assert imaging.lead.value() == 30.0 and imaging.lag.value() == 0.0
    assert not eclipse.up.isEnabled() and eclipse.down.isEnabled()
    assert editor.rule_rows[-1].up.isEnabled() and not editor.rule_rows[-1].down.isEnabled()


def test_changing_a_control_is_one_named_undo_step(
    editor: ScenarioEditor, window: MainWindow
) -> None:
    editor.rule_rows[2].mode.setCurrentText("safe")
    assert window.document.value(REL, ("rules", 2, "mode")) == "safe"
    assert editor.rule_text(2) == "Safe during every pass over gs_north"
    assert window.document.undo_stack.undoText().startswith("Edit scenario one_day")
    assert editor.is_modified()
    window.undo_action.trigger()
    assert editor.rule_rows[2].mode.currentText() == "downlink" and not editor.is_modified()


def test_a_lead_typed_into_the_sentence_is_kept(editor: ScenarioEditor, window: MainWindow) -> None:
    row = editor.rule_rows[2]
    row.lead.setValue(45.0)
    row.lead.editingFinished.emit()
    assert window.document.value(REL, ("rules", 2, "lead_s")) == 45.0
    assert "from 45 s before" in editor.rule_text(2)


def test_changing_the_kind_keeps_the_rule_valid(editor: ScenarioEditor, window: MainWindow) -> None:
    editor.set_rule(1, kind="in_sunlight")  # was a pass rule with a site and a lead
    rule = window.document.value(REL, ("rules", 1))
    assert rule == {"kind": "in_sunlight", "mode": "imaging"} or "site" not in rule
    assert not window.document.problems(REL)
    editor.set_rule(1, kind="during_pass")  # a pass rule needs a site: the first listed one
    assert window.document.value(REL, ("rules", 1, "site")) == "gs_north"
    assert not window.document.problems(REL)


def test_add_remove_and_move_rules(editor: ScenarioEditor, window: MainWindow) -> None:
    before = editor.rule_count()
    assert editor.add_rule() and editor.rule_count() == before + 1
    assert editor.rule_text(before) == "Charging during every pass over gs_north"
    assert editor.move_rule(before, -1) and editor.rule_text(before - 1).startswith("Charging")
    assert not editor.move_rule(0, -1)  # already first
    assert editor.remove_rule(before - 1) and editor.rule_count() == before
    for _ in range(3):
        window.undo_action.trigger()
    assert editor.rule_count() == before and not editor.is_modified()


def test_a_rule_button_moves_the_rule(editor: ScenarioEditor) -> None:
    first = editor.rule_text(0)
    editor.rule_rows[0].down.click()
    assert editor.rule_text(1) == first


def test_the_default_mode_the_shadow_model_and_the_sites_are_edits_too(
    editor: ScenarioEditor, window: MainWindow
) -> None:
    editor.default_mode.setCurrentText("safe")
    editor.shadow_model.setCurrentText("conical")
    box = editor.sites_list
    item = next(box.item(i) for i in range(box.count()) if box.item(i).text() == "gs_south")
    from PySide6.QtCore import Qt

    item.setCheckState(Qt.CheckState.Unchecked)
    data = window.document.data(REL)
    assert data["default_mode"] == "safe" and data["shadow_model"] == "conical"
    assert "gs_south" not in data["sites"]
    assert [p.code for p in window.document.problems(REL)] == ["REF_UNKNOWN_SITE"]
    assert (
        "does not list" in editor.error_label.text()
        and "rules[3].site" in editor.error_label.text()
    )
    window.undo_action.trigger()
    assert not window.document.problems(REL)


def test_segments_are_sentences_with_controls(editor: ScenarioEditor, window: MainWindow) -> None:
    assert editor.add_segment(100.0, 300.0)
    assert editor.segment_count() == 1 and editor.segment(0) == (100.0, 300.0, "charging")
    row = editor.segment_rows[0]
    row.mode.setCurrentText("imaging")
    row.duration.setValue(120.0)
    row.duration.editingFinished.emit()
    assert editor.segment(0) == (100.0, 120.0, "imaging")
    assert row.accessibleName() == "Imaging from T+100 s for 120 s"
    assert editor.add_segment(500.0, 10.0)
    assert editor.move_segment(1, -1) and editor.segment(0)[0] == 500.0
    assert editor.remove_segment(0) and editor.segment_count() == 1


def test_overlapping_segments_are_explained_and_not_saved(
    editor: ScenarioEditor, project: Path
) -> None:
    before = (project / REL).read_bytes()
    editor.add_segment(0.0, 500.0)
    editor.add_segment(100.0, 500.0)
    assert "overlap" in editor.error_label.text().lower() and not editor.error_label.isHidden()
    assert editor.save() is False and "need correcting" in editor.note_label.text()
    assert (project / REL).read_bytes() == before


def test_save_writes_the_scenario_in_place_and_reloads(
    editor: ScenarioEditor, window: MainWindow, project: Path
) -> None:
    path = project / REL
    path.write_text("# Reviewed 2026\n" + path.read_text(encoding="utf-8"), encoding="utf-8")
    window.reload_project()
    editor.rule_rows[2].mode.setCurrentText("safe")
    assert editor.save() is True
    text = path.read_text(encoding="utf-8")
    assert text.startswith("# Reviewed 2026") and text.count("mode: safe") == 1
    assert not editor.is_modified()
    assert load_project(project).project.scenarios["one_day"].rules[2].mode == "safe"  # type: ignore[union-attr]
    assert editor.rule_text(2) == "Safe during every pass over gs_north"  # still shown after reload


def test_the_save_button_of_the_editor_saves_the_model(
    editor: ScenarioEditor, window: MainWindow, project: Path
) -> None:
    editor.default_mode.setCurrentText("safe")
    editor.bar.save_button.click()
    assert "default_mode: safe" in (project / REL).read_text(encoding="utf-8")


def test_a_grid_edit_and_a_scenario_edit_are_saved_together(
    editor: ScenarioEditor, window: MainWindow, project: Path
) -> None:
    from tests.gui_helpers import set_unit_value

    set_unit_value(window, "radio", "mass_kg", "5.5")
    editor.default_mode.setCurrentText("safe")
    assert sorted(window.document.modified_files()) == [REL, "units/radio.yaml"]
    assert window.save_model() is True
    assert load_project(project).project.units["radio"].mass_kg == 5.5  # type: ignore[union-attr]


def test_the_editor_follows_a_reload_from_disk(
    editor: ScenarioEditor, window: MainWindow, project: Path
) -> None:
    path = project / REL
    path.write_text(
        path.read_text(encoding="utf-8").replace("default_mode: charging", "default_mode: safe")
    )
    window.reload_project()
    assert editor.default_mode.currentText() == "safe" and not editor.is_modified()


def test_the_editor_is_empty_without_a_scenario(window: MainWindow, project: Path) -> None:
    for path in (project / "scenarios").glob("*.yaml"):
        path.unlink()
    window.reload_project()
    assert window.scenario_view.editor.rule_count() == 0
    assert window.scenario_view.editor.scenario_id == ""
