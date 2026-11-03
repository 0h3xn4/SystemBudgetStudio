"""The orbit helper (2.2.0, D-228): a dialog that turns a local time of the node, a sun-synchronous
request or a repeat cycle into elements, and writes them to an orbit in one undo step, or hands
them to the Add scenario form."""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest

from budget_core.io.project_loader import load_project
from budget_core.orbit_design import raan_from_ltan_deg
from budget_gui.add_scenario_dialog import AddScenarioDialog
from budget_gui.main_window import MainWindow
from budget_gui.orbit_helper_dialog import OrbitHelperDialog

pytestmark = pytest.mark.gui

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
EPOCH = "2026-06-01T00:00:00Z"


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


def _sso(dialog: OrbitHelperDialog, altitude: str = "600", ltan: str = "10:30") -> None:
    dialog.mode_combo.setCurrentIndex(dialog.MODE_SSO)
    dialog.epoch_edit.setText(EPOCH)
    dialog.altitude_edit.setText(altitude)
    dialog.ltan_edit.setText(ltan)


# ---- the dialog -----------------------------------------------------------------------------


def test_a_sun_synchronous_request_gives_the_elements(qtbot) -> None:  # type: ignore[no-untyped-def]
    dialog = OrbitHelperDialog([])
    qtbot.addWidget(dialog)
    _sso(dialog)
    assert dialog.apply_button.isEnabled()
    values = dialog.values()
    assert values is not None
    assert values.inclination_deg == pytest.approx(97.79, abs=0.05)
    assert values.raan_deg == pytest.approx(
        raan_from_ltan_deg(10.5, datetime(2026, 6, 1, tzinfo=UTC)), abs=1e-6
    )
    assert values.altitude_km == pytest.approx(600.0) and values.eccentricity == 0.0
    assert "97.78" in dialog.result_label.text() and "10:30" in dialog.result_label.text()


def test_a_repeat_ground_track(qtbot) -> None:  # type: ignore[no-untyped-def]
    dialog = OrbitHelperDialog([])
    qtbot.addWidget(dialog)
    dialog.mode_combo.setCurrentIndex(dialog.MODE_REPEAT)
    dialog.epoch_edit.setText(EPOCH)
    dialog.revolutions_edit.setText("15")
    dialog.days_edit.setText("1")
    dialog.sso_check.setChecked(True)
    dialog.ltan_edit.setText("22:30")
    values = dialog.values()
    assert values is not None
    assert values.altitude_km == pytest.approx(561.0, abs=10.0)
    assert "15 revolutions in 1 day" in dialog.result_label.text()


def test_the_local_time_of_a_given_orbit(qtbot) -> None:  # type: ignore[no-untyped-def]
    dialog = OrbitHelperDialog([])
    qtbot.addWidget(dialog)
    dialog.mode_combo.setCurrentIndex(dialog.MODE_LTAN)
    dialog.epoch_edit.setText(EPOCH)
    dialog.altitude_edit.setText("500")
    dialog.inclination_edit.setText("51.6")
    dialog.ltan_edit.setText("09:00")
    values = dialog.values()
    assert values is not None and values.inclination_deg == 51.6
    assert 0.0 <= values.raan_deg < 360.0


def test_an_impossible_request_is_said_and_cannot_be_applied(qtbot) -> None:  # type: ignore[no-untyped-def]
    dialog = OrbitHelperDialog([])
    qtbot.addWidget(dialog)
    _sso(dialog, altitude="8000")
    assert not dialog.apply_button.isEnabled()
    assert "sun-synchronous" in dialog.error_label.text()
    assert dialog.values() is None


def test_nothing_is_said_before_the_user_types(qtbot) -> None:  # type: ignore[no-untyped-def]
    dialog = OrbitHelperDialog([])
    qtbot.addWidget(dialog)
    assert dialog.error_label.text() == "" and not dialog.apply_button.isEnabled()


def test_a_bad_epoch_and_a_bad_local_time_are_said(qtbot) -> None:  # type: ignore[no-untyped-def]
    dialog = OrbitHelperDialog([])
    qtbot.addWidget(dialog)
    _sso(dialog)
    dialog.epoch_edit.setText("yesterday")
    assert "epoch" in dialog.error_label.text().lower()
    dialog.epoch_edit.setText(EPOCH)
    dialog.ltan_edit.setText("25:00")
    assert "local time" in dialog.error_label.text().lower()


def test_with_orbits_the_button_writes_and_without_it_hands_over(qtbot) -> None:  # type: ignore[no-untyped-def]
    writing = OrbitHelperDialog(["leo"])
    handing = OrbitHelperDialog([])
    qtbot.addWidget(writing)
    qtbot.addWidget(handing)
    assert writing.apply_button.text() == "Write to orbit" and writing.orbit_combo.count() == 1
    assert handing.apply_button.text() == "Use these values" and not handing.orbit_combo.isVisible()


# ---- in the window --------------------------------------------------------------------------


def test_the_menu_entry_and_its_shortcut(window: MainWindow) -> None:
    assert window.orbit_helper_action.shortcut().toString() == "Ctrl+Shift+H"
    assert window.orbit_helper_action in window.model_edit_actions()


def test_the_helper_writes_the_elements_in_one_undo_step(window: MainWindow, project: Path) -> None:
    orbit_id = next(iter(load_project(project).project.orbits))  # type: ignore[union-attr]
    rel = f"orbits/{orbit_id}.yaml"
    before = window.document.data(rel)["elements"]["raan_deg"]
    steps = window.document.undo_stack.count()

    def ask(orbits: list[str]):  # type: ignore[no-untyped-def]
        dialog = OrbitHelperDialog(orbits)
        _sso(dialog, "650", "10:30")
        values = dialog.values()
        assert values is not None
        return orbit_id, values

    window._ask_orbit_helper = ask  # type: ignore[method-assign]
    assert window.orbit_helper()
    assert window.document.undo_stack.count() == steps + 1
    el = window.document.data(rel)["elements"]
    assert el["semi_major_axis_m"] == pytest.approx(6378137.0 + 650e3, rel=1e-9)
    assert el["inclination_deg"] == pytest.approx(97.9, abs=0.1) and el["raan_deg"] != before
    assert el["epoch_utc"] == EPOCH and el["eccentricity_ratio"] == 0.0
    assert "elements.raan_deg" in window.document.data(rel)["provenance"]
    assert window.save_model()
    result = load_project(project)
    assert result.project is not None
    assert not [p for p in result.problems if p.severity.value == "error"]
    assert not [p for p in result.problems if p.code == "PROVENANCE_PATH_UNKNOWN"]
    window.undo_action.trigger()
    assert window.document.data(rel)["elements"]["raan_deg"] == before


def test_a_tle_orbit_is_not_offered(window: MainWindow) -> None:
    asked: list[list[str]] = []

    def ask(orbits: list[str]):  # type: ignore[no-untyped-def]
        asked.append(orbits)
        return None

    window._ask_orbit_helper = ask  # type: ignore[method-assign]
    window.orbit_helper()
    assert asked and all(not o.startswith("tle") for o in asked[0])


# ---- the Add scenario form ------------------------------------------------------------------


def test_the_add_scenario_form_takes_the_values_of_the_helper(qtbot) -> None:  # type: ignore[no-untyped-def]
    dialog = AddScenarioDialog([], [], ["nominal"])
    qtbot.addWidget(dialog)
    helper = OrbitHelperDialog([])
    qtbot.addWidget(helper)
    _sso(helper, "600", "10:30")
    values = helper.values()
    assert values is not None
    dialog._ask_helper = lambda epoch: values  # type: ignore[method-assign]
    dialog.open_orbit_helper()
    assert float(dialog.altitude_edit.text()) == pytest.approx(600.0)
    assert float(dialog.inclination_edit.text()) == pytest.approx(97.79, abs=0.05)
    assert float(dialog.raan_edit.text()) == pytest.approx(values.raan_deg, abs=1e-3)
    assert dialog.start_edit.text() == EPOCH  # the epoch of the helper, when no start was typed
