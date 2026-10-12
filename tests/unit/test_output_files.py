"""Writing the output set: file modes, names, collisions and all-or-nothing staging (audit RC-6,
RC-12, RC-18)."""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import pytest

from budget_core.provenance import Provenance
from budget_core.reports import files as files_module
from budget_core.reports.document import ReportDocument
from budget_core.reports.files import MAX_NAME, OutputError, safe_name, write_file
from budget_core.reports.run import BudgetOutput, write_outputs

PROV = Provenance("t", "0", "3", (), "P", "1", "s", "2026-01-01T00:00:00Z", "u")


def output(prefix: str, csvs: tuple[tuple[str, str], ...]) -> BudgetOutput:
    return BudgetOutput(prefix, ReportDocument("R", PROV, ()), None, PROV, csvs, "{}\n")


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX modes")
def test_write_file_keeps_the_mode_of_an_existing_file(tmp_path: Path) -> None:
    target = tmp_path / "unit.yaml"
    target.write_text("old", encoding="utf-8")
    target.chmod(0o600)
    write_file(tmp_path, "unit.yaml", "new", sanitise=False)
    assert target.read_text(encoding="utf-8") == "new"
    assert stat.S_IMODE(target.stat().st_mode) == 0o600


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX modes")
def test_write_file_keeps_an_executable_mode(tmp_path: Path) -> None:
    target = tmp_path / "run.sh"
    target.write_text("x", encoding="utf-8")
    target.chmod(0o755)
    write_file(tmp_path, "run.sh", "y", sanitise=False)
    assert stat.S_IMODE(target.stat().st_mode) == 0o755


# ---- names ----------------------------------------------------------------------------------
def test_name_limit_counts_bytes_not_characters() -> None:
    name = safe_name("日" * 90 + ".csv")
    assert len(name.encode("utf-8")) <= MAX_NAME and name.endswith(".csv")
    assert name.startswith("日")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("con.tar.gz", "_con.tar.gz"),
        ("COM1.txt.bak", "_COM1.txt.bak"),
        ("lpt¹.csv", "_lpt¹.csv"),
        ("name.", "name"),
        ("name.csv.", "name.csv"),
        ("...", "_"),
    ],
)
def test_reserved_stems_and_trailing_dots(raw: str, expected: str) -> None:
    assert safe_name(raw) == expected


def test_case_insensitive_duplicates_are_refused(tmp_path: Path) -> None:
    one = output("p", (("case_hot.csv", "1"), ("case_Hot.csv", "2")))
    with pytest.raises(OutputError) as info:
        write_outputs([one], tmp_path / "o", {"csv"})
    assert "same file name" in str(info.value) and "case_" in str(info.value)
    assert not (tmp_path / "o").exists() or not list((tmp_path / "o").iterdir())


def test_collision_with_a_generated_name_names_the_file(tmp_path: Path) -> None:
    one = output("power_static", (("power_static_provenance.csv", "x"),))
    with pytest.raises(OutputError) as info:
        write_outputs([one], tmp_path / "o", {"csv"})
    assert "power_static_provenance.csv" in str(info.value)


# ---- all or nothing -------------------------------------------------------------------------
def test_a_failing_file_leaves_no_partial_set_and_is_named(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "o"
    out.mkdir()
    (out / "p.json").write_text("old json", encoding="utf-8")
    real = Path.write_bytes

    def flaky(self: Path, data: bytes) -> int:
        if self.name.startswith(".p_b.csv"):
            raise OSError("disk full")
        return real(self, data)

    monkeypatch.setattr(Path, "write_bytes", flaky)
    one = output("p", (("p_a.csv", "a"), ("p_b.csv", "b")))
    with pytest.raises(OutputError) as info:
        write_outputs([one], out, {"csv", "json"})
    assert "p_b.csv" in str(info.value)
    assert sorted(p.name for p in out.iterdir()) == ["p.json"]  # nothing new, nothing half-old
    assert (out / "p.json").read_text(encoding="utf-8") == "old json"


def test_failure_while_moving_reports_written_and_failed_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "o"
    real = os.replace

    def flaky(src: object, dst: object) -> None:
        if Path(str(dst)).name == "p_b.csv":
            raise OSError("boom")
        real(src, dst)  # type: ignore[arg-type]

    monkeypatch.setattr(files_module.os, "replace", flaky)
    one = output("p", (("p_a.csv", "a"), ("p_b.csv", "b"), ("p_c.csv", "c")))
    with pytest.raises(OutputError) as info:
        write_outputs([one], out, {"csv"})
    message = str(info.value)
    assert "p_b.csv" in message and "p_a.csv" in message  # failed file and what was written
    assert not [p for p in out.iterdir() if p.name.startswith(".")]  # no temporary files left
