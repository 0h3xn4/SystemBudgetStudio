# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""Project text must never run as a formula when a spreadsheet opens an exported file (D-263).

Decision (D-259, Q6): the tool keeps its present handling. CSV text that starts with `=`, `+`, `-`,
`@`, a tab or a carriage return gets one leading apostrophe, except numbers and plain words. XLSX
cells that hold project text are forced to the string type. These tests cover every starting
character in every place where project text reaches a CSV or an XLSX file.
"""

from __future__ import annotations

import ast
import csv
import io
import zipfile
from pathlib import Path

import pytest

from budget_core.provenance import Provenance
from budget_core.reports.csvutil import DANGEROUS_START, csv_field, csv_writer, defuse
from budget_core.reports.document import Column, ReportDocument, Section, Table
from budget_core.reports.xlsx import render_xlsx

PROV = Provenance("t", "0", "3", (), "P", "1", "s", "2026-01-01T00:00:00Z", "u")

HOSTILE = [
    '=HYPERLINK("http://example.invalid","click")',
    "=cmd|' /C calc'!A0",
    "+1+1",
    "+cmd|' /C calc'!A0",
    "-2+3",
    "-1+cmd|x",
    "@SUM(1+1)",
    "\t=1+1",
    "\r=1+1",
]


@pytest.mark.parametrize("text", HOSTILE)
def test_every_dangerous_start_is_defused(text: str) -> None:
    assert text.startswith(DANGEROUS_START)
    assert defuse(text) == "'" + text
    assert csv_field(text).lstrip('"').startswith("'")


@pytest.mark.parametrize("text", HOSTILE)
def test_csv_round_trip_keeps_one_apostrophe_and_the_rest(text: str) -> None:
    buffer = io.StringIO()
    csv_writer(buffer).writerow([text, "ok"])
    row = next(csv.reader(io.StringIO(buffer.getvalue())))
    assert row == ["'" + text, "ok"]


def _document(text: str) -> ReportDocument:
    table = Table(text, (Column(text),), ((text,),))
    section = Section(text, "S", paragraphs=(text,), tables=(table,))
    return ReportDocument(text, PROV, (section,))


@pytest.mark.parametrize("text", HOSTILE)
def test_xlsx_never_stores_project_text_as_a_formula(text: str) -> None:
    data = render_xlsx(_document(text))
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for name in archive.namelist():
            if name.startswith("xl/worksheets/"):
                xml = archive.read(name).decode("utf-8")
                assert "<f>" not in xml and "<f " not in xml, name
                assert 't="f"' not in xml


def test_no_module_writes_csv_without_the_defusing_writer() -> None:
    """Only `csvutil` may call `csv.writer`, plus the one export that writes numbers only."""
    allowed = {
        "src/budget_core/reports/csvutil.py",
        "src/budget_core/environment/spacemissionstudio.py",
    }
    root = Path(__file__).resolve().parents[2]
    offenders = []
    for path in (root / "src").rglob("*.py"):
        rel = path.relative_to(root).as_posix()
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Attribute)
                and node.attr in {"writer", "DictWriter"}
                and isinstance(node.value, ast.Name)
                and node.value.id == "csv"
                and rel not in allowed
            ):
                offenders.append(rel)
    assert offenders == []


def test_the_space_mission_studio_export_holds_numbers_and_times_only(tmp_path: Path) -> None:
    """The one raw `csv.writer` writes no project text: the check keeps it that way."""
    from budget_core.environment.spacemissionstudio import export_spacemissionstudio
    from tests.unit.test_spacemissionstudio import reference

    env, _grid = reference()
    export_spacemissionstudio(env, tmp_path)
    for file in tmp_path.glob("*.csv"):
        rows = list(csv.reader(file.read_text(encoding="utf-8").splitlines()))
        for row in rows[1:]:
            for value in row:
                assert not value.startswith(DANGEROUS_START[0]), file.name
                assert value[:1] in "0123456789-", (file.name, value[:1])
