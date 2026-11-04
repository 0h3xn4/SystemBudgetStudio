"""`budget import idm`: a plan first, then --apply (decisions D-240 to D-243)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from budget_cli.main import main
from budget_core.io.project_loader import load_project
from budget_core.problems import Severity
from tests.idm.fixtures import write_idm


@pytest.fixture
def model(tmp_path: Path) -> Path:
    return write_idm(tmp_path / "synthetic.idm")


def test_without_apply_nothing_is_written(
    tmp_path: Path, model: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "p"
    assert main(["import", "idm", str(model), "--project", str(root), "--bus-voltage-v", "28"]) == 0
    out = capsys.readouterr().out
    assert "Units: 5 added." in out and "Nothing was written" in out
    assert "IDM-CIC model synthetic.idm" in out
    assert not root.exists()


def test_apply_creates_a_project_that_checks_out(
    tmp_path: Path, model: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "p"
    args = ["import", "idm", str(model), "--project", str(root), "--bus-voltage-v", "28"]
    assert main([*args, "--apply"]) == 0
    out = capsys.readouterr().out
    assert "Wrote" in out and "0 error(s)" in out
    loaded = load_project(root)
    assert [p for p in loaded.problems if p.severity is Severity.ERROR] == []
    assert main(["validate", str(root)]) == 0


def test_a_new_project_needs_a_bus_voltage(
    tmp_path: Path, model: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["import", "idm", str(model), "--project", str(tmp_path / "p")]) == 1
    err = capsys.readouterr().err
    assert "IDM_NEW_PROJECT_INCOMPLETE" in err and "nothing was written" in err.lower()


def test_a_second_import_changes_nothing(tmp_path: Path, model: Path) -> None:
    root = tmp_path / "p"
    args = ["import", "idm", str(model), "--project", str(root), "--bus-voltage-v", "28"]
    assert main([*args, "--apply"]) == 0
    before = {p: p.read_bytes() for p in root.rglob("*.yaml")}
    assert main([*args[:-2], "--apply"]) == 0
    assert {p: p.read_bytes() for p in root.rglob("*.yaml")} == before


def test_margins_applied(tmp_path: Path, model: Path) -> None:
    root = tmp_path / "p"
    args = ["import", "idm", str(model), "--project", str(root), "--bus-voltage-v", "28"]
    assert main([*args, "--margins", "applied", "--apply"]) == 0
    project = load_project(root).project
    assert project is not None
    assert {u.maturity for u in project.units.values()} == {"idm_applied"}


def test_json_output(tmp_path: Path, model: Path, capsys: pytest.CaptureFixture[str]) -> None:
    args = ["import", "idm", str(model), "--project", str(tmp_path / "p"), "--bus-voltage-v", "28"]
    assert main([*args, "--format", "json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["new_project"] is True and data["applied"] is False
    assert data["counts"]["unit"] == {"added": 5}
    assert any(f["path"] == "idm/import_state.yaml" for f in data["files"])
    assert {p["code"] for p in data["problems"]} >= {"IDM_MARGIN_NOT_APPLIED"}


def test_a_bad_file_is_refused_with_its_reason(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bad = tmp_path / "bad.idm"
    bad.write_bytes(b"not an archive")
    assert main(["import", "idm", str(bad), "--bus-voltage-v", "28"]) == 1
    err = capsys.readouterr().err
    assert "IDM_FILE_UNREADABLE" in err and "nothing was written" in err


def test_the_default_folder_is_named_after_the_file(
    tmp_path: Path, model: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["import", "idm", str(model), "--bus-voltage-v", "28", "--apply"]) == 0
    assert (tmp_path / "synthetic" / "project.yaml").is_file()


def test_the_option_choices(model: Path) -> None:
    with pytest.raises(SystemExit):
        main(["import", "idm", str(model), "--margins", "both"])
