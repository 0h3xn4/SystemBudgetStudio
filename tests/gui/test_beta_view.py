"""The Beta sweep page of the Thermal area (D-250): a worker solves the thermal model for a range
of beta angles; the page shows the plot and the table and exports the files of the command."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest
from PySide6.QtWidgets import QFileDialog

from budget_gui.beta_view import (
    FROM_ALTITUDE,
    FROM_SCENARIO,
    NO_NORMALS_TEXT,
    NO_THERMAL_TEXT,
    BetaView,
)
from budget_gui.main_window import MainWindow
from budget_gui.validity import STALE_TEXT

pytestmark = pytest.mark.gui

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", tmp_path / "p")
    return tmp_path / "p"


@pytest.fixture
def window(qtbot, project: Path) -> MainWindow:  # type: ignore[no-untyped-def]
    w = MainWindow()
    qtbot.addWidget(w, before_close_func=lambda win: win.editors.discard_all_changes())
    w.open_project(project)
    return w


def compute(view: BetaView, qtbot) -> None:  # type: ignore[no-untyped-def]
    with qtbot.waitSignal(view.computed, timeout=120000):
        view.compute()


def test_the_thermal_area_has_a_budget_and_a_beta_sweep_page(window: MainWindow) -> None:
    pages = window.thermal_pages
    assert [pages.tabText(i) for i in range(pages.count())] == ["Budget", "Beta sweep"]
    assert window.workspace.show_view(window.beta_view)
    assert window.workspace.is_showing(window.beta_view)


def test_before_computing_it_says_so_and_cannot_export(window: MainWindow) -> None:
    view = window.beta_view
    assert "Not computed" in view.status.text()
    assert not view.export_button.isEnabled() and view.compute_button.isEnabled()
    assert view.case_combo.currentText() == "hot"
    assert view.orbit_combo.currentText() == FROM_SCENARIO
    assert not view.altitude.isVisibleTo(view)


def test_compute_fills_the_plot_and_the_table(window: MainWindow, qtbot) -> None:  # type: ignore[no-untyped-def]
    view = window.beta_view
    view.beta_step.setValue(30.0)
    compute(view, qtbot)
    sweep = view.result
    assert sweep is not None and len(sweep.points) == 7
    assert view.table.rowCount() == 7
    headers = [view.table.horizontalHeaderItem(c).text() for c in range(view.table.columnCount())]
    assert headers[:3] == ["Beta (deg)", "Sunlit (%)", "Orbit angle (deg)"]
    assert "EPS (K)" in headers and "Units beyond a limit" in headers[-2]
    assert view.table.item(0, 0).text() == "-90.0"
    assert view.table.item(0, 2).text() == ""  # the average has no orbit angle
    assert view.plot.spec() is not None  # type: ignore[attr-defined]
    assert view.plot.time_axis().name == "value"
    assert "Beta angle" in view.plot.axis_title()
    assert "Case hot, orbit average" in view.status.text()
    assert view.export_button.isEnabled() and view.is_valid()


def test_the_readout_of_the_plot_names_the_beta_angle(window: MainWindow, qtbot) -> None:  # type: ignore[no-untyped-def]
    view = window.beta_view
    view.beta_step.setValue(45.0)
    compute(view, qtbot)
    lines = view.plot.readout_lines(30.0)
    assert lines[0] == "Beta angle = 30.0 deg"
    view.plot.pin_cursor(0.0)
    assert "difference +30.0 deg" in view.plot.readout_lines(30.0)[1]


def test_the_worst_instant_gives_an_orbit_angle(window: MainWindow, qtbot) -> None:  # type: ignore[no-untyped-def]
    view = window.beta_view
    view.mode_combo.setCurrentIndex(1)
    view.beta_step.setValue(45.0)
    compute(view, qtbot)
    assert view.result is not None and view.result.mode == "peak"
    assert all(view.table.item(r, 2).text() != "" for r in range(view.table.rowCount()))


def test_a_changed_input_makes_the_result_stale_and_stops_the_export(
    window: MainWindow,
    qtbot,  # type: ignore[no-untyped-def]
) -> None:
    view = window.beta_view
    view.beta_step.setValue(45.0)
    compute(view, qtbot)
    assert view.problems() is not None
    view.mode_combo.setCurrentIndex(1)
    assert view.is_stale and view.status.text() == STALE_TEXT
    assert not view.export_button.isEnabled() and view.problems() == []
    errors: list[str] = []
    view.export_failed.connect(errors.append)
    view.export_to(Path("."))
    assert errors and "Press Compute again" in errors[0]
    view.mode_combo.setCurrentIndex(0)  # back to what was computed
    assert view.is_valid() and view.export_button.isEnabled()


def test_a_circular_orbit_at_an_altitude_replaces_the_scenario(
    window: MainWindow,
    qtbot,  # type: ignore[no-untyped-def]
) -> None:
    view = window.beta_view
    view.beta_min.setValue(0.0)
    view.beta_max.setValue(0.0)
    view.orbit_combo.setCurrentText(FROM_ALTITUDE)
    assert view.altitude.isVisibleTo(view) is True
    view.altitude.setValue(500.0)
    compute(view, qtbot)
    low = view.result.points[0].sunlit_fraction  # type: ignore[union-attr]
    view.altitude.setValue(2000.0)
    compute(view, qtbot)
    assert view.result.points[0].sunlit_fraction > low  # type: ignore[union-attr]
    assert "2000 km" in view.status.text()


def test_a_range_that_is_not_a_range_is_said_and_nothing_runs(window: MainWindow) -> None:
    view = window.beta_view
    view.beta_min.setValue(60.0)
    view.beta_max.setValue(10.0)
    view.compute()
    assert "lowest first" in view.status.text()
    assert view._worker is None  # noqa: SLF001


def test_export_writes_the_files_of_the_command(
    window: MainWindow,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    qtbot,  # type: ignore[no-untyped-def]
) -> None:
    view = window.beta_view
    view.beta_step.setValue(45.0)
    compute(view, qtbot)
    out = tmp_path / "out"
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *a, **k: str(out))
    with qtbot.waitSignal(view.export_finished, timeout=60000):
        view._choose_export()  # noqa: SLF001
    names = sorted(p.name for p in out.iterdir())
    assert names == [
        "thermal_beta_hot_average.csv",
        "thermal_beta_hot_average.json",
        "thermal_beta_hot_average.png",
        "thermal_beta_hot_average_provenance.csv",
    ]
    assert (out / "thermal_beta_hot_average.png").read_bytes()[:4] == b"\x89PNG"
    assert "Exported 4 file(s)" in view.status.text()


def test_the_page_says_what_a_project_without_directions_lacks(
    window: MainWindow, project: Path
) -> None:
    path = project / "config" / "thermal_model.yaml"
    lines = path.read_text(encoding="utf-8").splitlines()
    kept: list[str] = []
    skipping = False
    for line in lines:
        if line.strip().startswith("normal_lvlh:"):
            skipping = True
            continue
        if skipping and re.fullmatch(r"- -?\d+(\.\d+)?", line.strip()):
            continue
        skipping = False
        kept.append(line)
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")
    window.reload_project()
    view = window.beta_view
    assert view.empty.isVisibleTo(view) is True and not view.body.isVisibleTo(view)
    assert view.empty.message.text() == NO_NORMALS_TEXT
    assert not view.compute_button.isEnabled()


def test_a_project_without_a_thermal_model_has_an_empty_page(
    window: MainWindow, project: Path
) -> None:
    (project / "config" / "thermal_model.yaml").unlink()
    (project / "config" / "thermal_environment.yaml").unlink()
    window.reload_project()
    view = window.beta_view
    assert view.empty.message.text() == NO_THERMAL_TEXT
    assert not view.compute_button.isEnabled()


def test_a_running_sweep_can_be_cancelled(window: MainWindow, qtbot) -> None:  # type: ignore[no-untyped-def]
    view = window.beta_view
    view.mode_combo.setCurrentIndex(1)
    view.beta_step.setValue(0.5)  # 361 angles of the peak search: long enough to stop
    with qtbot.waitSignal(view.cancelled, timeout=60000):
        view.compute()
        assert view._worker is not None  # noqa: SLF001
        view.cancel()
    assert view.compute_button.text() == "Compute" and view.result is None
    assert "Cancelled" in view.status.text()
