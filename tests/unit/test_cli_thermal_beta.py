"""`budget thermal-beta` (D-250): a sweep over beta angles written as CSV, JSON and a plot."""

from __future__ import annotations

import csv
import json
import re
import shutil
from pathlib import Path

import pytest

from budget_cli.main import main
from budget_core.result_format import RESULT_FORMAT_NAME

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


@pytest.fixture
def root(tmp_path: Path) -> Path:
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", tmp_path / "p")
    return tmp_path / "p"


def _rows(path: Path) -> list[list[str]]:
    return list(csv.reader(path.read_text(encoding="utf-8-sig").splitlines()))


def test_a_sweep_writes_the_csv_the_json_the_plot_and_the_provenance(
    root: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "out"
    code = main(["thermal-beta", str(root), "--beta-step", "45", "--out", str(out)])
    assert code == 0
    names = sorted(p.name for p in out.iterdir())
    for mode in ("average", "peak"):
        stem = f"thermal_beta_hot_{mode}"
        assert {f"{stem}.csv", f"{stem}.json", f"{stem}.png", f"{stem}_provenance.csv"} <= set(
            names
        )
    rows = _rows(out / "thermal_beta_hot_average.csv")
    assert rows[0][:4] == ["beta_deg", "sunlit_fraction", "orbit_angle_deg", "complete"]
    assert [float(r[0]) for r in rows[1:]] == [-90.0, -45.0, 0.0, 45.0, 90.0]
    assert all(r[3] == "yes" for r in rows[1:])
    assert rows[1][2] == ""  # the average has no orbit angle
    peak = _rows(out / "thermal_beta_hot_peak.csv")
    assert all(r[2] != "" for r in peak[1:])
    assert "sunlit" in capsys.readouterr().out
    payload = json.loads((out / "thermal_beta_hot_average.json").read_text(encoding="utf-8"))
    assert payload["result_format"]["name"] == RESULT_FORMAT_NAME
    assert payload["result_format"]["kind"] == "thermal_beta"
    assert payload["case"] == "hot" and payload["mode"] == "average"
    assert len(payload["points"]) == 5 and payload["surfaces_typed"] == []
    assert (out / "thermal_beta_hot_average.png").read_bytes()[:4] == b"\x89PNG"


def test_one_mode_and_no_plots(root: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    assert main(["thermal-beta", str(root), "--mode", "peak", "--no-plots", "--out", str(out)]) == 0
    assert sorted(p.name for p in out.iterdir()) == [
        "thermal_beta_hot_peak.csv",
        "thermal_beta_hot_peak.json",
        "thermal_beta_hot_peak_provenance.csv",
    ]


def test_the_same_input_gives_the_same_files(root: Path, tmp_path: Path) -> None:
    args = ["thermal-beta", str(root), "--beta-step", "30", "--date", "2026-01-01T00:00:00Z"]
    for name in ("a", "b"):
        assert main([*args, "--user", "tester", "--out", str(tmp_path / name)]) == 0
    for p in sorted((tmp_path / "a").iterdir()):
        assert p.read_bytes() == (tmp_path / "b" / p.name).read_bytes(), p.name


def test_an_altitude_replaces_the_scenario_and_a_higher_orbit_is_sunlit_longer(
    root: Path, tmp_path: Path
) -> None:
    out = tmp_path / "out"
    base = ["thermal-beta", str(root), "--mode", "average", "--beta-min", "0", "--beta-max", "0"]
    assert main([*base, "--altitude-km", "500", "--out", str(out / "low")]) == 0
    assert main([*base, "--altitude-km", "2000", "--out", str(out / "high")]) == 0
    low = _rows(out / "low" / "thermal_beta_hot_average.csv")[1]
    high = _rows(out / "high" / "thermal_beta_hot_average.csv")[1]
    assert float(high[1]) > float(low[1])  # sunlit fraction at beta 0


def test_what_cannot_run_is_refused_with_a_message_and_writes_nothing(
    root: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "out"
    assert main(["thermal-beta", str(root), "--case", "nope", "--out", str(out)]) == 1
    assert main(["thermal-beta", str(root), "--beta-step", "0", "--out", str(out)]) == 2
    assert main(["thermal-beta", str(root), "--altitude-km", "-5", "--out", str(out)]) == 2
    assert main(["thermal-beta", str(root), "--beta-min", "50", "--beta-max", "10"]) == 2
    err = capsys.readouterr().err
    assert "no such case" in err and "step" in err
    assert not out.exists()


def test_a_project_without_normals_says_so(
    root: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = root / "config" / "thermal_model.yaml"
    lines = path.read_text(encoding="utf-8").splitlines()
    kept: list[str] = []
    skip = False
    for line in lines:
        if line.strip().startswith("normal_lvlh:"):
            skip = True
            continue
        if skip and re.fullmatch(r"- -?\d+(\.\d+)?", line.strip()):
            continue
        skip = False
        kept.append(line)
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")
    assert main(["thermal-beta", str(root), "--out", str(tmp_path / "out")]) == 1
    assert "normal_lvlh" in capsys.readouterr().err  # not a load error: the project is valid
