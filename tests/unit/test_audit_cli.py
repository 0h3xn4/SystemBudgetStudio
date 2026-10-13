"""Audit RC-1, RC-3, RC-15, RC-16, RC-22, RC-23, LD-1, LD-2: command line behaviour."""

from __future__ import annotations

import io
import os
import re
import shutil
import sys
from pathlib import Path

import pytest

import budget_cli.main as cli
from budget_cli.main import build_parser, main
from tests.helpers import edit, write_valid_project

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
FIXED = ["--user", "Test User", "--date", "2026-01-02T03:04:05Z"]


@pytest.fixture
def eps(tmp_path: Path) -> Path:
    shutil.copytree(EXAMPLES / "cubesat_3u_eps", tmp_path / "eps")
    return tmp_path / "eps"


@pytest.fixture
def plain(tmp_path: Path) -> Path:
    write_valid_project(tmp_path / "plain")
    return tmp_path / "plain"


# ---- RC-1 -------------------------------------------------------------------------------------
def dead_link(root: Path) -> None:
    edit(root, "links/uhf_down.yaml", "value: 1.0", "value: 1.0e-12")


def test_link_passes_fails_when_a_link_closes_at_no_rate(
    eps: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dead_link(eps)
    code = main(["link-passes", str(eps), "--report", "json", *FIXED])
    captured = capsys.readouterr()
    out = captured.out + captured.err
    assert code == 1
    assert "LINK_NOT_CLOSED" in captured.err
    assert not re.search(r"(?<![1-9])0 errors", out) and re.search(r"[1-9]\d* errors?, ", out)


def test_link_passes_and_run_agree_on_a_dead_link(
    eps: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dead_link(eps)
    a = main(["link-passes", str(eps), "--report", "json", "--out", str(eps / "a"), *FIXED])
    b = main(
        ["run", str(eps), "--budget", "link", "--report", "json", "--out", str(eps / "b"), *FIXED]
    )
    capsys.readouterr()
    assert a == 1 and b == 1


def test_a_healthy_link_still_exits_zero(eps: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["link-passes", str(eps), "--report", "json", *FIXED]) == 0
    assert "0 errors" in capsys.readouterr().out


# ---- RC-3 -------------------------------------------------------------------------------------
def stray(root: Path) -> None:
    (root / "units" / "camera.yml").write_text("name: x\n", encoding="utf-8")


def warning_count(text: str) -> int:
    match = re.search(r"(\d+) warnings?\.", text)
    assert match, text
    return int(match.group(1))


@pytest.mark.parametrize("command", [["link-passes"], ["power-timeline"], ["run"]])
def test_load_warnings_are_printed_and_counted_by_every_command(
    eps: Path, command: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    base = [*command, str(eps), "--report", "json", *FIXED]
    main(base)
    before = capsys.readouterr().out
    stray(eps)
    main(base)
    after = capsys.readouterr().out
    assert "FILE_IGNORED" not in before and "FILE_IGNORED" in after
    assert warning_count(after) == warning_count(before) + 1


@pytest.mark.parametrize("command", [["link-passes"], ["power-timeline"], ["run"], ["validate"]])
def test_strict_agrees_everywhere(
    eps: Path, command: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    stray(eps)
    extra = [] if command == ["validate"] else ["--report", "json", *FIXED]
    assert main([*command, str(eps), "--strict", *extra]) == 1
    capsys.readouterr()


# ---- RC-15 ------------------------------------------------------------------------------------
def test_output_that_the_terminal_cannot_encode_does_not_crash(
    plain: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shutil.copy(plain / "units" / "obc.yaml", plain / "units" / "obcé中.yaml")
    raw = io.BytesIO()
    fake = io.TextIOWrapper(raw, encoding="cp1252", errors="strict", write_through=True)
    monkeypatch.setattr(sys, "stdout", fake)
    code = main(["validate", str(plain)])
    fake.flush()
    text = raw.getvalue().decode("cp1252")
    assert code == 1  # the extra unit is not assigned in any mode
    assert "\\u4e2d" in text and "Internal error" not in text


# ---- RC-16 ------------------------------------------------------------------------------------
@pytest.mark.parametrize("value", ["abc", "-5", "", "99999999999999999999", "1.5", "0x10"])
def test_a_bad_source_date_epoch_is_a_clear_error(
    plain: Path,
    value: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", value)
    code = main(["run", str(plain), "--budget", "mass", "--report", "json", "--user", "u"])
    out = capsys.readouterr().err
    assert code == 2
    assert "SOURCE_DATE_EPOCH" in out and "Internal error" not in out
    assert not (plain / "results").exists()


def test_a_good_source_date_epoch_still_makes_the_output_reproducible(
    plain: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1767323045")
    assert main(["run", str(plain), "--budget", "mass", "--report", "json", "--user", "u"]) == 0
    text = (plain / "results" / "mass_static.json").read_text(encoding="utf-8")
    assert "2026-01-02T03:04:05Z" in text


@pytest.mark.parametrize(
    "date", ["9999-12-31T23:59:59-05:00", "0001-01-01T00:00:00+05:00", "0001-01-01T00:00:00Z"]
)
def test_dates_that_cannot_be_converted_are_an_argument_error(
    plain: Path, date: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as info:
        main(["run", str(plain), "--date", date])
    assert info.value.code == 2
    assert "Internal error" not in capsys.readouterr().out


# ---- LD-1 -------------------------------------------------------------------------------------
def test_export_examples_does_not_replace_existing_projects(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "demo"
    assert main(["export-examples", str(target)]) == 0
    mine = target / "cubesat_3u" / "project.yaml"
    mine.write_text("# my own edit\n", encoding="utf-8")
    capsys.readouterr()
    assert main(["export-examples", str(target)]) == 1
    out = capsys.readouterr().err
    assert "--force" in out and "cubesat_3u" in out
    assert mine.read_text(encoding="utf-8") == "# my own edit\n"


def test_export_examples_force_replaces(tmp_path: Path) -> None:
    target = tmp_path / "demo"
    assert main(["export-examples", str(target)]) == 0
    mine = target / "cubesat_3u" / "project.yaml"
    original = mine.read_text(encoding="utf-8")
    mine.write_text("# my own edit\n", encoding="utf-8")
    assert main(["export-examples", str(target), "--force"]) == 0
    assert mine.read_text(encoding="utf-8") == original


def test_export_examples_into_a_folder_with_other_things_is_fine(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("keep", encoding="utf-8")
    (tmp_path / "mine").mkdir()
    assert main(["export-examples", str(tmp_path)]) == 0
    assert (tmp_path / "notes.txt").read_text(encoding="utf-8") == "keep"


# ---- LD-2 -------------------------------------------------------------------------------------
@pytest.mark.parametrize("value", ["0", "-1", "x", "1.5"])
def test_series_every_must_be_at_least_one(value: str) -> None:
    with pytest.raises(SystemExit) as info:
        build_parser().parse_args(["power-timeline", "p", "--series-every", value])
    assert info.value.code == 2


@pytest.mark.parametrize("value", ["-1", "-5", "x"])
def test_max_rows_must_not_be_negative(value: str) -> None:
    with pytest.raises(SystemExit) as info:
        build_parser().parse_args(["compare", "p", "--max-rows", value])
    assert info.value.code == 2


def test_the_limits_themselves_are_allowed() -> None:
    assert (
        build_parser().parse_args(["power-timeline", "p", "--series-every", "1"]).series_every == 1
    )
    assert build_parser().parse_args(["compare", "p", "--max-rows", "0"]).max_rows == 0


# ---- RC-22 ------------------------------------------------------------------------------------
@pytest.mark.parametrize("command", ["scenario", "power-timeline", "link-passes"])
def test_several_scenarios_without_a_choice_name_the_choices(
    eps: Path, command: str, capsys: pytest.CaptureFixture[str]
) -> None:
    shutil.copy(eps / "scenarios" / "one_day.yaml", eps / "scenarios" / "two_day.yaml")
    code = main([command, str(eps), "--out", str(eps / "o")])
    out = capsys.readouterr().err
    assert code == 2
    assert "--scenario" in out and "one_day" in out and "two_day" in out
    assert "does not exist" not in out


@pytest.mark.parametrize("command", ["scenario", "power-timeline", "link-passes"])
def test_no_scenario_in_the_project_is_said_plainly(
    eps: Path, command: str, capsys: pytest.CaptureFixture[str]
) -> None:
    for path in (eps / "scenarios").glob("*.yaml"):
        path.unlink()
    code = main([command, str(eps), "--out", str(eps / "o")])
    out = capsys.readouterr().err
    assert code in (1, 2)
    assert "no scenario" in out.lower() and "does not exist" not in out


def test_a_file_given_as_the_project_is_named_as_such(
    plain: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["validate", str(plain / "project.yaml")]) == 1
    out = capsys.readouterr().out
    assert "file" in out and "folder" in out and "does not exist" not in out


def test_run_budget_link_without_links_fails(
    plain: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["run", str(plain), "--budget", "link", *FIXED])
    out = capsys.readouterr().out
    assert code == 1 and "no links" in out
    assert not (plain / "results").exists()


def test_run_all_without_links_is_still_fine(plain: Path) -> None:
    assert main(["run", str(plain), "--budget", "mass", "--report", "json", *FIXED]) == 0
    assert main(["run", str(plain), "--report", "json", *FIXED]) == 0


def test_units_export_checks_the_file_type_before_loading(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(
        ["units-export", str(tmp_path / "no_such_project"), "--out", str(tmp_path / "x.txt")]
    )
    out = capsys.readouterr().err
    assert code == 2 and ".csv or .xlsx" in out and "does not exist" not in out


def test_no_command_prints_help_and_fails(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 2
    captured = capsys.readouterr()
    assert (
        "usage: budget" in captured.err + captured.out and "validate" in captured.err + captured.out
    )


def test_options_cannot_be_abbreviated(plain: Path) -> None:
    with pytest.raises(SystemExit) as info:
        main(["validate", str(plain), "--str"])
    assert info.value.code == 2
    with pytest.raises(SystemExit):
        main(["run", str(plain), "--bud", "mass"])


def test_the_incomplete_banner_is_printed_when_a_later_budget_is_incomplete(
    eps: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # in this example the power output (the first) is complete and a later one is not
    main(["run", str(eps), "--report", "json", "--out", str(eps / "o"), *FIXED])
    out = capsys.readouterr().out
    assert "INCOMPLETE" in out
    assert "\n\n" not in out  # no empty line where the banner should be


# ---- RC-23 ------------------------------------------------------------------------------------
@pytest.mark.skipif(sys.platform == "win32", reason="symbolic links need privileges on Windows")
def test_guide_schema_and_example_writes_replace_a_link_instead_of_following_it(
    tmp_path: Path,
) -> None:
    victim = tmp_path / "victim.txt"
    victim.write_text("precious", encoding="utf-8")
    out = tmp_path / "out"
    out.mkdir()
    os.symlink(victim, out / "system-budget-studio-guide.html")
    os.symlink(victim, out / "unit.schema.json")
    assert main(["guide", "--out", str(out), "--format", "html"]) == 0
    assert main(["export-schemas", str(out)]) == 0
    assert victim.read_text(encoding="utf-8") == "precious"
    assert not (out / "unit.schema.json").is_symlink()
    assert not (out / "system-budget-studio-guide.html").is_symlink()
    demo = tmp_path / "demo"
    os.makedirs(demo / "cubesat_3u")
    os.symlink(victim, demo / "cubesat_3u" / "project.yaml")
    assert main(["export-examples", str(demo), "--force"]) == 0
    assert victim.read_text(encoding="utf-8") == "precious"


def test_cli_module_exposes_the_help_helpers() -> None:
    assert callable(cli.build_parser)
