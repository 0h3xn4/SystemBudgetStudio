# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""`budget tables-export` and `budget tables-import`: a template, a dry run, then --apply."""

from __future__ import annotations

import csv
import shutil
from pathlib import Path

import pytest

from budget_cli.main import main
from budget_core.io.project_loader import load_project

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


@pytest.fixture
def root(tmp_path: Path) -> Path:
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", tmp_path / "p")
    return tmp_path / "p"


def _rows(path: Path) -> list[list[str]]:
    return list(csv.reader(path.read_text(encoding="utf-8-sig").splitlines()))


def _filled(root: Path, tmp_path: Path, table: str, *, source: str = "Data sheet 7") -> Path:
    assert main(["tables-export", str(root), table, "--out", str(tmp_path / "t.csv")]) == 0
    rows = _rows(tmp_path / "t.csv")
    header = rows[0]
    value = "required_ebn0_db" if table == "ebn0" else "loss_db"
    rows[1][header.index(value)] = "9.25"
    rows[1][header.index("source")] = source
    with (tmp_path / "t.csv").open("w", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerows(rows)
    return tmp_path / "t.csv"


@pytest.mark.parametrize("table", ["ebn0", "attenuation"])
def test_export_writes_a_csv_next_to_the_results_by_default(root: Path, table: str) -> None:
    assert main(["tables-export", str(root), table]) == 0
    rows = _rows(root / "results" / f"{table}_table.csv")
    assert rows[0][0] in ("modulation", "name") and len(rows) >= 1


def test_export_can_write_an_xlsx_workbook(root: Path, tmp_path: Path) -> None:
    out = tmp_path / "e.xlsx"
    assert main(["tables-export", str(root), "ebn0", "--out", str(out)]) == 0
    assert out.read_bytes()[:2] == b"PK"


def test_export_refuses_a_file_type_it_does_not_write(
    root: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["tables-export", str(root), "ebn0", "--out", str(tmp_path / "e.txt")]) == 2
    assert ".csv or .xlsx" in capsys.readouterr().err


def test_an_unknown_table_name_is_refused(root: Path) -> None:
    with pytest.raises(SystemExit):
        main(["tables-export", str(root), "units"])


@pytest.mark.parametrize("table", ["ebn0", "attenuation"])
def test_import_shows_the_changes_and_writes_nothing_without_apply(
    root: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str], table: str
) -> None:
    before = (root / "config" / f"{table}_table.yaml").read_bytes()
    table_file = _filled(root, tmp_path, table)
    assert main(["tables-import", str(root), table, str(table_file)]) == 0
    out = capsys.readouterr().out
    assert "would change" in out and "Nothing was written" in out
    assert (root / "config" / f"{table}_table.yaml").read_bytes() == before


@pytest.mark.parametrize("table", ["ebn0", "attenuation"])
def test_apply_writes_the_table_and_the_project_still_loads(
    root: Path, tmp_path: Path, table: str
) -> None:
    table_file = _filled(root, tmp_path, table)
    assert main(["tables-import", str(root), table, str(table_file), "--apply"]) == 0
    text = (root / "config" / f"{table}_table.yaml").read_text(encoding="utf-8")
    assert "Data sheet 7" in text and "9.25" in text
    assert load_project(root).project is not None
    # a second import of the same file changes nothing
    assert main(["tables-import", str(root), table, str(table_file), "--apply"]) == 0


def test_a_value_without_a_source_is_refused_and_nothing_is_written(
    root: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    before = (root / "config" / "ebn0_table.yaml").read_bytes()
    table_file = _filled(root, tmp_path, "ebn0", source="")
    assert main(["tables-import", str(root), "ebn0", str(table_file), "--apply"]) == 1
    err = capsys.readouterr().err
    assert "IMPORT_SOURCE_MISSING" in err and "9.25" not in err
    assert (root / "config" / "ebn0_table.yaml").read_bytes() == before


def test_links_are_exported_changed_in_a_dry_run_and_written_with_apply(
    root: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    table = tmp_path / "links.csv"
    assert main(["tables-export", str(root), "links", "--out", str(table)]) == 0
    rows = _rows(table)
    header = rows[0]
    target = next(r for r in rows[1:] if r[header.index("field")] == "transmitter.power_w")
    target[header.index("value")] = "9.5"
    target[header.index("source")] = "Data sheet 7"
    with table.open("w", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerows(rows)
    link_id = target[header.index("link")]
    before = (root / "links" / f"{link_id}.yaml").read_text(encoding="utf-8")
    capsys.readouterr()

    assert main(["tables-import", str(root), "links", str(table)]) == 0
    assert "Nothing was written" in capsys.readouterr().out
    assert (root / "links" / f"{link_id}.yaml").read_text(encoding="utf-8") == before

    assert main(["tables-import", str(root), "links", str(table), "--apply"]) == 0
    assert f"Wrote {link_id}.yaml" in capsys.readouterr().out
    loaded = load_project(root)
    assert loaded.project is not None
    assert loaded.project.links[link_id].transmitter.power_w.value == 9.5
