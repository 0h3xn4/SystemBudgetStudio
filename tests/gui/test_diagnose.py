# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""The support aids of D-257: the diagnostics report and the opt-in fault log."""

from __future__ import annotations

import faulthandler
import sys
from pathlib import Path

import pytest

from budget_core import diagnostics
from budget_gui import app as gui_app
from budget_gui.app import create_app, split_options
from budget_gui.diagnostics import report

pytestmark = pytest.mark.gui


def test_the_options_are_taken_out_of_the_arguments() -> None:
    rest, fault, diagnose, file = split_options(
        ["--fault-log", "crash.txt", "--diagnose", "diag.txt", "project"]
    )
    assert (rest, fault, diagnose, file) == (["project"], Path("crash.txt"), True, Path("diag.txt"))
    assert split_options(["--diagnose"]) == ([], None, True, None)
    assert split_options(["--smoke"]) == (["--smoke"], None, False, None)
    # an option without its value is left to the old rules, it does not swallow a project
    assert split_options(["--fault-log"]) == (["--fault-log"], None, False, None)


def test_the_report_names_what_decides_a_start_up_problem(qtbot) -> None:  # type: ignore[no-untyped-def]
    app = create_app([])
    text = report(app)
    for needle in (
        "System Budget Studio",
        "Python ",
        "Assets folder:",
        "Bundled fonts found:",
        "platform plugin",
        "Screen 1:",
        "Bundled font families registered:",
        "Icon loads: yes",
        "Layout file:",
    ):
        assert needle in text, needle


def test_diagnose_writes_the_report_to_the_file_it_is_given(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "diag.txt"
    monkeypatch.setattr(sys, "argv", ["system-budget-studio", "--diagnose", str(out)])
    assert gui_app.main() == 0
    assert "Assets folder:" in out.read_text(encoding="utf-8")


def test_the_fault_log_is_on_only_when_asked_for(tmp_path: Path) -> None:
    was_enabled = faulthandler.is_enabled()
    log = tmp_path / "crash.txt"
    try:
        diagnostics.enable_fault_log(log)
        assert faulthandler.is_enabled()
        assert log.is_file() and log.read_text(encoding="utf-8") == ""  # nothing went wrong
    finally:
        diagnostics.disable_fault_log()
        if was_enabled:
            faulthandler.enable()
    assert faulthandler.is_enabled() == was_enabled


def test_the_environment_lines_have_no_project_content() -> None:
    text = "\n".join(diagnostics.environment_lines())
    assert "project" not in text.lower().replace("system budget studio", "")
