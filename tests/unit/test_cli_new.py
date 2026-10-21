"""`budget new`: a blank project from the command line (D-185)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from budget_cli.main import main


def test_it_creates_a_project_that_validates(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    folder = tmp_path / "my-sat"
    assert main(["new", str(folder), "--bus-voltage-v", "28"]) == 0
    out = capsys.readouterr()
    assert "Created the blank project" in out.out and out.err == ""
    assert main(["validate", str(folder)]) == 0
    assert "0 errors" in capsys.readouterr().out


def test_the_name_defaults_to_the_folder_and_can_be_given(tmp_path: Path) -> None:
    assert main(["new", str(tmp_path / "alpha"), "--bus-voltage-v", "12"]) == 0
    given = [
        "new",
        str(tmp_path / "beta"),
        "--bus-voltage-v",
        "12.5",
        "--name",
        "Beta sat",
        "--bus-name",
        "power",
        "--spacecraft-name",
        "Beta FM",
    ]
    assert main(given) == 0
    alpha = yaml.safe_load((tmp_path / "alpha" / "project.yaml").read_text(encoding="utf-8"))
    beta = yaml.safe_load((tmp_path / "beta" / "project.yaml").read_text(encoding="utf-8"))
    craft = yaml.safe_load((tmp_path / "beta" / "spacecraft.yaml").read_text(encoding="utf-8"))
    assert alpha["name"] == "alpha" and beta["name"] == "Beta sat"
    assert craft["name"] == "Beta FM"
    assert craft["buses"] == [{"name": "power", "nominal_voltage_v": 12.5}]


def test_the_voltage_is_required(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as stop:
        main(["new", str(tmp_path / "x")])
    assert stop.value.code == 2
    assert "--bus-voltage-v" in capsys.readouterr().err
    assert not (tmp_path / "x").exists()


@pytest.mark.parametrize("voltage", ["0", "-5", "nan", "inf", "5000"])
def test_a_wrong_voltage_is_refused_and_nothing_is_written(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], voltage: str
) -> None:
    assert main(["new", str(tmp_path / "x"), "--bus-voltage-v", voltage]) == 1
    assert "voltage" in capsys.readouterr().err
    assert not (tmp_path / "x").exists()


def test_an_existing_folder_is_never_touched(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    folder = tmp_path / "taken"
    folder.mkdir()
    (folder / "mine.txt").write_text("keep", encoding="utf-8")
    assert main(["new", str(folder), "--bus-voltage-v", "28"]) == 1
    assert "already exists" in capsys.readouterr().err
    assert [p.name for p in folder.iterdir()] == ["mine.txt"]


def test_an_empty_folder_argument_is_refused(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as stop:
        main(["new", " ", "--bus-voltage-v", "28"])
    assert stop.value.code == 2
    capsys.readouterr()


def test_a_refusal_does_not_repeat_the_name_the_user_typed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    given = ["new", str(tmp_path / "x"), "--bus-voltage-v", "0", "--name", "SECRETNAME"]
    assert main(given) == 1
    assert "SECRETNAME" not in capsys.readouterr().err
