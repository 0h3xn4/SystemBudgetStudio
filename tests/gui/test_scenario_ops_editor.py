# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""The pointing and manoeuvres section of the scenario editor (2.3.0): the default pointing mode,
pointing rules and placed burns, each change one undo step, written to the scenario file."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from budget_core.io.project_loader import load_project
from budget_gui.main_window import MainWindow

pytestmark = pytest.mark.gui

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


@pytest.fixture
def window(qtbot, tmp_path: Path):  # type: ignore[no-untyped-def]
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", tmp_path / "p")
    w = MainWindow()
    qtbot.addWidget(w, before_close_func=lambda win: win.editors.discard_all_changes())
    w.open_project(tmp_path / "p")
    return w


def test_the_section_offers_the_pointing_modes_and_manoeuvres_of_the_project(window) -> None:  # type: ignore[no-untyped-def]
    ops = window.scenario_view.editor.ops
    assert ops.pointing_modes == ["nadir", "target"]
    assert ops.maneuver_names == ["Deorbit", "Orbit trim", "Station-keeping"]
    assert ops.default_combo.findText("nadir") >= 0
    assert ops.rule_count() == 0 and ops.maneuver_count() == 0


def test_setting_the_default_pointing_mode_is_one_undo_step(window) -> None:  # type: ignore[no-untyped-def]
    ops = window.scenario_view.editor.ops
    stack = window.document.undo_stack
    before = stack.index()
    assert ops.set_default("nadir")
    assert stack.index() == before + 1
    data = window.document.data("scenarios/one_day.yaml")
    assert data["pointing_default"] == "nadir"
    stack.undo()
    assert "pointing_default" not in window.document.data("scenarios/one_day.yaml")


def test_a_pointing_rule_is_added_changed_and_removed(window) -> None:  # type: ignore[no-untyped-def]
    ops = window.scenario_view.editor.ops
    assert ops.set_default("nadir")
    assert ops.add_rule()
    assert ops.rule_count() == 1
    assert ops.set_rule(0, kind="in_eclipse", mode="target")
    rule = window.document.data("scenarios/one_day.yaml")["pointing_rules"][0]
    assert rule["kind"] == "in_eclipse" and rule["mode"] == "target" and "site" not in rule
    assert ops.remove_rule(0)
    assert ops.rule_count() == 0


def test_a_burn_is_placed_moved_and_removed(window) -> None:  # type: ignore[no-untyped-def]
    ops = window.scenario_view.editor.ops
    assert ops.add_maneuver()
    assert ops.maneuver_count() == 1
    assert ops.set_maneuver(0, name="Deorbit", start_s=3600.0)
    placed = window.document.data("scenarios/one_day.yaml")["maneuvers"][0]
    assert placed == {"name": "Deorbit", "start_s": 3600.0}
    assert ops.remove_maneuver(0)
    assert (
        "maneuvers" not in window.document.data("scenarios/one_day.yaml")
        or not (window.document.data("scenarios/one_day.yaml")["maneuvers"])
    )


def test_what_is_written_loads_and_runs(window, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    ops = window.scenario_view.editor.ops
    ops.set_default("nadir")
    ops.add_rule()
    ops.set_rule(0, kind="in_eclipse", mode="target")
    ops.add_maneuver()
    ops.set_maneuver(0, name="Orbit trim", start_s=100.0)
    window._confirm_comment_loss = lambda *_a, **_k: True  # type: ignore[method-assign]
    assert window.save_model()
    loaded = load_project(tmp_path / "p")
    assert loaded.project is not None
    scenario = loaded.project.scenarios["one_day"]
    assert scenario.pointing_default == "nadir" and scenario.maneuvers[0].name == "Orbit trim"
    assert scenario.pointing_rules[0].mode == "target"


def test_a_project_without_pointing_has_nothing_to_choose(qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", tmp_path / "p")
    (tmp_path / "p" / "config" / "pointing.yaml").unlink()
    (tmp_path / "p" / "config" / "propulsion.yaml").unlink()
    w = MainWindow()
    qtbot.addWidget(w, before_close_func=lambda win: win.editors.discard_all_changes())
    w.open_project(tmp_path / "p")
    ops = w.scenario_view.editor.ops
    assert ops.pointing_modes == [] and ops.maneuver_names == []
    assert not ops.add_rule_button.isEnabled() and not ops.add_maneuver_button.isEnabled()
