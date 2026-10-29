"""The model choices of a scenario in the scenario editor (D-219, P5d): one drop-down each from
the registry, a tooltip with the source, one undo step, and the feature declared in project.yaml
when a non-default model is chosen."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from budget_core import model_choices as mc
from budget_core.io.project_loader import load_project
from budget_gui.main_window import MainWindow
from budget_gui.scenario_editor import ScenarioEditor

pytestmark = pytest.mark.gui

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
REL = "scenarios/one_day.yaml"
FIELDS = ("shadow_model", "earth_model", "irradiance_model")


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


def _combo(editor: ScenarioEditor, field: str):  # type: ignore[no-untyped-def]
    return getattr(editor, field)


def test_each_scenario_choice_of_the_registry_has_a_drop_down_with_its_values(
    editor: ScenarioEditor,
) -> None:
    entries = {m.field: m for m in mc.of_scope("scenario") if m.field in FIELDS}
    assert set(entries) == set(FIELDS)
    for field, entry in entries.items():
        combo = _combo(editor, field)
        assert [combo.itemText(i) for i in range(combo.count())] == [c.id for c in entry.choices]
        assert combo.currentText() == entry.default
        assert entry.title in combo.accessibleName()


def test_the_tooltip_of_a_value_names_its_source_or_its_note(editor: ScenarioEditor) -> None:
    combo = editor.earth_model
    wgs72 = [combo.itemText(i) for i in range(combo.count())].index("wgs72")
    tip = combo.itemData(wgs72, role=3)  # Qt.ToolTipRole
    assert "Hoots" in tip or "Spacetrack" in tip
    assert "Earth constants" in editor.earth_model.toolTip()


def test_a_choice_is_one_undo_step_and_declares_the_feature(
    editor: ScenarioEditor, window: MainWindow
) -> None:
    assert "model_choices" not in window.document.data("project.yaml").get("requires", [])
    before = window.document.undo_stack.count()
    editor.earth_model.setCurrentText("wgs72")
    assert window.document.undo_stack.count() == before + 1
    assert window.document.data(REL)["earth_model"] == "wgs72"
    assert "model_choices" in window.document.data("project.yaml")["requires"]
    window.undo_action.trigger()
    assert "earth_model" not in window.document.data(REL)
    assert "model_choices" not in window.document.data("project.yaml").get("requires", [])
    assert editor.earth_model.currentText() == "wgs84"


def test_going_back_to_the_default_removes_the_key(
    editor: ScenarioEditor, window: MainWindow
) -> None:
    editor.irradiance_model.setCurrentText("seasonal")
    assert window.document.data(REL)["irradiance_model"] == "seasonal"
    editor.irradiance_model.setCurrentText("constant")
    assert "irradiance_model" not in window.document.data(REL)


def test_the_feature_is_declared_once(editor: ScenarioEditor, window: MainWindow) -> None:
    editor.earth_model.setCurrentText("wgs72")
    editor.irradiance_model.setCurrentText("seasonal")
    assert window.document.data("project.yaml")["requires"].count("model_choices") == 1


def test_save_writes_the_choice_and_the_declaration_and_the_project_loads_clean(
    editor: ScenarioEditor, window: MainWindow, project: Path
) -> None:
    editor.earth_model.setCurrentText("wgs72")
    editor.irradiance_model.setCurrentText("seasonal")
    assert window.save_model()
    loaded = load_project(project)
    assert loaded.project is not None
    scenario = loaded.project.scenarios["one_day"]
    assert scenario.earth_model == "wgs72" and scenario.irradiance_model == "seasonal"
    assert "model_choices" in loaded.project.meta.requires
    codes = {p.code for p in loaded.problems}
    assert "FEATURE_NOT_DECLARED" not in codes and "FEATURE_UNSUPPORTED" not in codes


def test_the_assumptions_page_follows_the_choice(
    editor: ScenarioEditor, window: MainWindow
) -> None:
    editor.earth_model.setCurrentText("wgs72")
    assert window.save_model()
    rows = window.assumptions_page.visible_rows()
    earth = [r for r in rows if r.name.endswith("earth model") and "one_day" in r.name]
    assert earth and earth[0].value == "wgs72" and earth[0].status == "set"
