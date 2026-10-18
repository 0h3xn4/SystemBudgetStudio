"""Places that show results of the solver audit fixes: the per-day figure, the stale-orbit warning
of a scenario run, the not-evaluated checks in the JSON, and the violation count of the window."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from budget_cli.main import main
from tests.helpers import edit
from tests.regression.test_audit_environment import tle_orbit

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
FIXED = ["--user", "Test User", "--date", "2026-01-02T03:04:05Z"]


@pytest.fixture
def root(tmp_path: Path) -> Path:
    dest = tmp_path / "p"
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", dest)
    return dest


def test_a_scenario_shorter_than_a_day_says_n_a_per_day(
    root: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    edit(root, "scenarios/one_day.yaml", "duration_s: 86400.0", "duration_s: 6000.0")
    main(["link-passes", str(root), "--out", str(tmp_path / "o"), "--report", "csv", *FIXED])
    out = capsys.readouterr().out
    assert "n/a per day" in out and "0.00 MByte per day" not in out


def test_the_scenario_command_prints_the_stale_orbit_warning(
    root: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    orbit = tle_orbit()
    assert orbit.tle is not None
    (root / "orbits" / "leo.yaml").write_text(
        "schema_version: 1\nkind: orbit\nname: ISS\ntle:\n"
        + "".join(f"  - '{line}'\n" for line in orbit.tle),
        encoding="utf-8",
    )
    assert main(["scenario", str(root), "--out", str(tmp_path / "o"), *FIXED]) == 0
    assert "ORBIT_EPOCH_FAR" in capsys.readouterr().out


def test_the_timeline_json_lists_the_checks_that_did_not_run(root: Path, tmp_path: Path) -> None:
    out = tmp_path / "o"
    main(["power-timeline", str(root), "--out", str(out), "--report", "json", *FIXED])
    data = json.loads((out / "power_time_one_day.json").read_text(encoding="utf-8"))
    assert isinstance(data["not_evaluated"], list)
