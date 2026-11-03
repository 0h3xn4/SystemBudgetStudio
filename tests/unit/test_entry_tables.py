"""The Eb/N0 and attenuation tables as spreadsheets (2.2.0, D-231): export, fill in with the values
and sources of a standard or data sheet, import with a preview. An empty cell means unchanged; a
number needs its source; nothing is invented, and no message carries a value from a file."""

from __future__ import annotations

import csv
import io
import shutil
from pathlib import Path

import pytest

from budget_core.io.entry_tables import (
    TABLES,
    apply_entry_plan,
    plan_entry_import,
    read_entry_table,
    table_csv,
    table_xlsx,
)
from budget_core.io.project_loader import load_project

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


@pytest.fixture
def root(tmp_path: Path) -> Path:
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", tmp_path / "p")
    return tmp_path / "p"


def _project(root: Path):  # type: ignore[no-untyped-def]
    loaded = load_project(root)
    assert loaded.project is not None
    return loaded.project


def _write(path: Path, rows: list[list[str]]) -> Path:
    buffer = io.StringIO()
    csv.writer(buffer, lineterminator="\n").writerows(rows)
    path.write_text(buffer.getvalue(), encoding="utf-8", newline="\n")
    return path


def _plan(root: Path, name: str, rows: list[list[str]], tmp: Path):  # type: ignore[no-untyped-def]
    table = read_entry_table(_write(tmp / "t.csv", rows), name)
    return plan_entry_import(_project(root), name, table, "t.csv")


EBN0_HEADER = [
    "modulation",
    "coding",
    "required_ebn0_db",
    "source",
    "status",
    "note",
    "target_ber",
    "target_fer",
]


# ---- export ---------------------------------------------------------------------------------


def test_the_tables_are_named() -> None:
    assert set(TABLES) == {"ebn0", "attenuation"}


def test_the_ebn0_export_has_the_columns_and_the_entries(root: Path) -> None:
    rows = list(csv.reader(io.StringIO(table_csv(_project(root), "ebn0"))))
    assert rows[0] == EBN0_HEADER
    assert len(rows) == 3 and rows[1][:2] == ["QPSK", "rate 1/2"] and rows[1][2] == "4.0"


def test_a_project_without_a_table_exports_the_header_only(root: Path) -> None:
    (root / "config" / "ebn0_table.yaml").unlink()
    text = table_csv(_project(root), "ebn0")
    assert text.strip().splitlines() == [",".join(EBN0_HEADER)]


def test_the_xlsx_export_reads_back_as_no_change(root: Path, tmp_path: Path) -> None:
    path = tmp_path / "t.xlsx"
    path.write_bytes(table_xlsx(_project(root), "ebn0"))
    plan = plan_entry_import(_project(root), "ebn0", read_entry_table(path, "ebn0"), "t.xlsx")
    assert plan.ok and not plan.changes and plan.unchanged == 2


def test_text_that_a_spreadsheet_would_run_is_defused(root: Path) -> None:
    path = root / "config" / "ebn0_table.yaml"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "Synthetic example value; not from a data sheet or a standard.", "=1+1", 1
        ),
        encoding="utf-8",
    )
    assert "'=1+1" in table_csv(_project(root), "ebn0")


# ---- changing and adding --------------------------------------------------------------------


def test_a_changed_value_is_a_change_and_an_equal_one_is_not(root: Path, tmp_path: Path) -> None:
    plan = _plan(
        root,
        "ebn0",
        [
            EBN0_HEADER,
            ["QPSK", "rate 1/2", "4.5", "Data sheet X, table 3", "", "", "", ""],
            ["QPSK", "none", "10", "", "", "", "", ""],
        ],
        tmp_path,
    )
    assert plan.ok
    fields = {(c.key, c.field): c for c in plan.changes}
    assert ("QPSK / rate 1/2", "required_ebn0_db") in fields and (
        "QPSK / rate 1/2",
        "source",
    ) in fields
    assert fields[("QPSK / rate 1/2", "required_ebn0_db")].kind == "changed"
    assert plan.unchanged == 1  # QPSK, none: the value is what it was and the rest is empty


def test_an_empty_cell_leaves_the_value_alone(root: Path, tmp_path: Path) -> None:
    plan = _plan(
        root, "ebn0", [EBN0_HEADER, ["QPSK", "rate 1/2", "", "", "estimate", "", "", ""]], tmp_path
    )
    assert plan.ok and [(c.field, c.new) for c in plan.changes] == [("status", "estimate")]


def test_a_new_row_with_a_value_and_a_source_is_added(root: Path, tmp_path: Path) -> None:
    plan = _plan(
        root,
        "ebn0",
        [
            EBN0_HEADER,
            ["8PSK", "rate 2/3", "6.6", "A standard, table 7", "sourced", "", "1e-5", ""],
        ],
        tmp_path,
    )
    assert plan.ok and any(
        c.kind == "added" and c.field == "required_ebn0_db" for c in plan.changes
    )
    written = apply_entry_plan(root, "ebn0", plan)
    assert [p.name for p in written] == ["ebn0_table.yaml"]
    entries = _project(root).config.ebn0_table.entries  # type: ignore[union-attr]
    new = next(e for e in entries if e.modulation == "8PSK")
    assert new.required_ebn0_db.value == 6.6 and new.target_ber == 1e-5
    assert new.required_ebn0_db.source == "A standard, table 7"


def test_a_new_row_with_only_the_key_is_a_placeholder(root: Path, tmp_path: Path) -> None:
    plan = _plan(
        root, "ebn0", [EBN0_HEADER, ["16APSK", "rate 3/4", "", "", "", "", "", ""]], tmp_path
    )
    assert plan.ok
    apply_entry_plan(root, "ebn0", plan)
    entry = next(e for e in _project(root).config.ebn0_table.entries if e.modulation == "16APSK")  # type: ignore[union-attr]
    assert entry.required_ebn0_db.value is None and entry.required_ebn0_db.source == "TBD"


def test_the_comments_of_the_file_survive(root: Path, tmp_path: Path) -> None:
    path = root / "config" / "ebn0_table.yaml"
    path.write_text(
        "# the table of the radio team\n" + path.read_text(encoding="utf-8"), encoding="utf-8"
    )
    plan = _plan(
        root, "ebn0", [EBN0_HEADER, ["BPSK", "none", "9.6", "Data sheet", "", "", "", ""]], tmp_path
    )
    apply_entry_plan(root, "ebn0", plan)
    assert path.read_text(encoding="utf-8").startswith("# the table of the radio team\n")


def test_a_missing_table_file_is_created(root: Path, tmp_path: Path) -> None:
    (root / "config" / "ebn0_table.yaml").unlink()
    plan = _plan(
        root,
        "ebn0",
        [EBN0_HEADER, ["QPSK", "rate 1/2", "4.1", "Data sheet", "", "", "", ""]],
        tmp_path,
    )
    apply_entry_plan(root, "ebn0", plan)
    table = _project(root).config.ebn0_table
    assert table is not None and len(table.entries) == 1


# ---- what is refused ------------------------------------------------------------------------


def test_a_value_without_a_source_is_refused(root: Path, tmp_path: Path) -> None:
    plan = _plan(
        root, "ebn0", [EBN0_HEADER, ["8PSK", "rate 2/3", "6.6", "", "", "", "", ""]], tmp_path
    )
    assert not plan.ok
    assert any(p.code == "IMPORT_SOURCE_MISSING" and p.line == 2 for p in plan.problems)
    assert apply_entry_plan(root, "ebn0", plan) == []


def test_a_bad_number_names_the_row_and_the_column_not_the_value(
    root: Path, tmp_path: Path
) -> None:
    plan = _plan(
        root, "ebn0", [EBN0_HEADER, ["QPSK", "rate 1/2", "7.77x", "S", "", "", "", ""]], tmp_path
    )
    assert not plan.ok
    problem = next(p for p in plan.problems if p.severity.value == "error")
    assert (
        problem.line == 2
        and "required_ebn0_db" in problem.message
        and "7.77" not in problem.message
    )


@pytest.mark.parametrize(
    "column,value", [("status", "great"), ("target_ber", "2"), ("target_ber", "0")]
)
def test_a_value_outside_its_range_is_refused(
    root: Path, tmp_path: Path, column: str, value: str
) -> None:
    row = ["QPSK", "rate 1/2", "", "", "", "", "", ""]
    row[EBN0_HEADER.index(column)] = value
    plan = _plan(root, "ebn0", [EBN0_HEADER, row], tmp_path)
    assert not plan.ok and any(column in p.message for p in plan.problems)


def test_a_row_without_its_key_is_refused(root: Path, tmp_path: Path) -> None:
    plan = _plan(root, "ebn0", [EBN0_HEADER, ["", "rate 1/2", "4", "S", "", "", "", ""]], tmp_path)
    assert not plan.ok and any("modulation" in p.message for p in plan.problems)


def test_the_same_key_twice_is_refused(root: Path, tmp_path: Path) -> None:
    rows = [
        EBN0_HEADER,
        ["QPSK", "rate 1/2", "4", "S", "", "", "", ""],
        ["QPSK", "rate 1/2", "5", "S", "", "", "", ""],
    ]
    plan = _plan(root, "ebn0", rows, tmp_path)
    assert not plan.ok and any(p.code == "IMPORT_DUPLICATE_ROW" for p in plan.problems)


def test_an_unknown_column_is_a_warning(root: Path, tmp_path: Path) -> None:
    plan = _plan(
        root,
        "ebn0",
        [[*EBN0_HEADER, "remarks"], ["QPSK", "rate 1/2", "", "", "", "", "", "", "x"]],
        tmp_path,
    )
    assert plan.ok and any(p.code == "IMPORT_COLUMN_IGNORED" for p in plan.problems)


# ---- the attenuation table ------------------------------------------------------------------

ATT_HEADER = [
    "name",
    "attenuation_kind",
    "freq_hz",
    "elevation_deg",
    "loss_db",
    "source",
    "status",
    "note",
]


def test_an_attenuation_entry_is_added(root: Path, tmp_path: Path) -> None:
    plan = _plan(
        root,
        "attenuation",
        [
            ATT_HEADER,
            ["rain_ka", "rain", "26.5e9", "10", "2.4", "A study, table 2", "estimate", ""],
        ],
        tmp_path,
    )
    assert plan.ok
    apply_entry_plan(root, "attenuation", plan)
    table = _project(root).config.attenuation_table
    assert table is not None
    entry = next(e for e in table.entries if e.name == "rain_ka")
    assert entry.freq_hz == 26.5e9 and entry.elevation_deg == 10.0 and entry.loss_db.value == 2.4
    assert entry.loss_db.status == "estimate"


def test_an_attenuation_kind_that_is_not_known_is_refused(root: Path, tmp_path: Path) -> None:
    plan = _plan(
        root, "attenuation", [ATT_HEADER, ["x", "fog", "1e9", "", "", "", "", ""]], tmp_path
    )
    assert not plan.ok and any("attenuation_kind" in p.message for p in plan.problems)


def test_the_attenuation_export_round_trips(root: Path, tmp_path: Path) -> None:
    text = table_csv(_project(root), "attenuation")
    path = tmp_path / "a.csv"
    path.write_text(text, encoding="utf-8", newline="\n")
    plan = plan_entry_import(
        _project(root), "attenuation", read_entry_table(path, "attenuation"), "a.csv"
    )
    assert plan.ok and not plan.changes


def test_a_table_that_is_not_one_of_ours_is_refused(root: Path, tmp_path: Path) -> None:
    with pytest.raises(KeyError):
        table_csv(_project(root), "links")
