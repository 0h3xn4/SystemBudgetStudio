# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""`microsat_250kg_clean`: the example whose validation and runs report no warning and no error.

The other examples leave numbers as placeholders and break a limit on purpose, to show the
Problems list. This one has an invented value for every input and meets every limit, so a new user
sees what a project with nothing to fix looks like. These tests run each command with `--strict`,
which turns any warning into a failure, so the example cannot start to report one without a test
failing."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from budget_cli.main import main
from budget_core.examples import EXAMPLES

EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "examples"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    shutil.copytree(EXAMPLES_DIR / "microsat_250kg_clean", tmp_path / "p")
    return tmp_path / "p"


def test_the_example_is_registered_and_its_folder_matches_the_builder() -> None:
    assert "microsat_250kg_clean" in EXAMPLES
    assert (EXAMPLES_DIR / "microsat_250kg_clean" / "project.yaml").is_file()


def test_validate_finds_nothing(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["validate", str(project), "--strict"]) == 0
    assert "No problems found." in capsys.readouterr().out


@pytest.mark.parametrize("budget", ["power", "mass", "thermal", "propulsion", "pointing", "link"])
def test_every_budget_runs_without_a_warning_or_an_error(
    project: Path, tmp_path: Path, budget: str, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "out"
    assert main(["run", str(project), "--budget", budget, "--out", str(out), "--strict"]) == 0
    captured = capsys.readouterr()
    assert "0 errors, 0 warnings." in captured.out
    assert "INCOMPLETE" not in captured.out + captured.err
    for path in out.glob("*.json"):
        problems = json.loads(path.read_text(encoding="utf-8")).get("problems", [])
        assert [p for p in problems if p["severity"] in ("error", "warning")] == []


@pytest.mark.parametrize("command", ["scenario", "power-timeline", "link-passes"])
def test_the_scenario_commands_report_nothing(
    project: Path, tmp_path: Path, command: str, capsys: pytest.CaptureFixture[str]
) -> None:
    strict = [] if command == "scenario" else ["--strict"]  # the scenario has no findings to count
    code = main([command, str(project), "--out", str(tmp_path / "out"), *strict])
    out = capsys.readouterr()
    assert code == 0
    assert "error" not in out.err.lower()
    assert "warning" not in out.err.lower()


def test_the_power_timeline_has_no_violation(
    project: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["power-timeline", str(project), "--out", str(tmp_path / "o")]) == 0
    text = capsys.readouterr().out
    assert "0 violation(s)" in text
    assert "n/a" not in text
