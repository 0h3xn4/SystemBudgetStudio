"""Which text goes to which stream (D-145): what a command produced goes to standard output;
why it could not do its work goes to standard error. `validate` is the exception: its listing
of problems is its output."""

import json
import shutil
from pathlib import Path

import pytest

from budget_cli import main as cli
from budget_cli.main import main
from tests.helpers import edit, write_valid_project

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
FIXED = ["--user", "tester", "--date", "2026-01-01T00:00:00Z"]


@pytest.fixture
def root(tmp_path: Path) -> Path:
    write_valid_project(tmp_path)
    return tmp_path


def test_a_refused_run_speaks_on_standard_error_only(
    root: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    edit(root, "units/obc.yaml", "bus: main", "bus: nope")
    assert main(["run", str(root), "--out", str(tmp_path / "o"), *FIXED]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "REF_UNKNOWN_BUS" in captured.err and "nothing was written" in captured.err


def test_a_good_run_writes_nothing_to_standard_error(
    root: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["run", str(root), "--budget", "mass", "--out", str(tmp_path / "o"), *FIXED]) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert "Wrote" in captured.out and "0 errors" in captured.out


def test_findings_that_fail_a_run_go_to_standard_error_and_the_summary_to_standard_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    shutil.copytree(EXAMPLES / "cubesat_3u_eps", tmp_path / "p")
    code = main(
        ["run", str(tmp_path / "p"), "--budget", "thermal", "--out", str(tmp_path / "o"), *FIXED]
    )
    captured = capsys.readouterr()
    assert code == 1
    assert "THERMAL_MARGIN_INSUFFICIENT" in captured.err
    assert "THERMAL_MARGIN_INSUFFICIENT" not in captured.out
    assert "Wrote" in captured.out and "error" in captured.out


def test_validate_lists_its_problems_on_standard_output(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    edit(root, "units/obc.yaml", "bus: main", "bus: nope")
    assert main(["validate", str(root)]) == 1
    captured = capsys.readouterr()
    assert "REF_UNKNOWN_BUS" in captured.out
    assert captured.err == ""


def test_validate_json_is_clean_on_standard_output(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    edit(root, "units/obc.yaml", "bus: main", "bus: nope")
    main(["validate", str(root), "--format", "json"])
    captured = capsys.readouterr()
    assert json.loads(captured.out)["errors"] == 1
    assert captured.err == ""


def test_a_usage_error_and_an_unexpected_error_use_standard_error(
    monkeypatch: pytest.MonkeyPatch, root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["compare", str(root)]) == 2
    captured = capsys.readouterr()
    assert captured.out == "" and "second project" in captured.err

    def boom(_args: object) -> int:
        raise ValueError("SECRETVALUE")

    monkeypatch.setattr(cli, "_validate", boom)
    assert main(["validate", str(root)]) == 1
    captured = capsys.readouterr()
    assert captured.out == "" and "Internal error (ValueError)" in captured.err
    assert "SECRETVALUE" not in captured.err


def test_a_units_import_warning_stays_on_standard_output_when_the_import_works(
    root: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["units-export", str(root), "--out", str(tmp_path / "t.csv")]) == 0
    capsys.readouterr()
    assert main(["units-import", str(root), str(tmp_path / "t.csv")]) == 0
    assert capsys.readouterr().err == ""
