"""Comparison pairs rows by declared key columns, computes changes from raw values and reports
what it cannot pair (audit TL-2, TL-16, RC-17)."""

from __future__ import annotations

import csv
import io
import json
from datetime import UTC, datetime

from budget_core.compare import ComparisonResult, compare_documents, comparison_output
from budget_core.link.evaluate import link_pass_series, link_static_budget
from budget_core.model import StaticPoint
from budget_core.provenance import Provenance, make_provenance
from budget_core.reports.document import Column, ReportDocument, Section, Table
from budget_core.reports.link_report import build_link_report
from tests.link_helpers import downlink, link_project, pass_run

PROV = Provenance("t", "0", "3", (), "P", "1", "s", "2026-01-02T03:04:05Z", "u")
WHEN = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)


def link_doc(points: list[StaticPoint], run=None):  # type: ignore[no-untyped-def]
    project = link_project(links={"dl": downlink(static_points=points)})
    prov = make_provenance(project, user="u", generated_at=WHEN)
    passes = link_pass_series(project, run) if run is not None else None
    return build_link_report(project, link_static_budget(project), prov, [], passes, plots=False)


def compare(a: ReportDocument, b: ReportDocument, **kw: object) -> ComparisonResult:
    return compare_documents("Link", a, b, "A", "B", **kw)  # type: ignore[arg-type]


A = StaticPoint(name="low", elevation_deg=10.0, range_m=1.0e6)
B = StaticPoint(name="high", elevation_deg=60.0, range_m=5.0e5)
INSERTED = StaticPoint(name="mid", elevation_deg=30.0, range_m=7.0e5)


def test_inserting_a_static_point_does_not_shift_the_pairing() -> None:
    result = compare(link_doc([A, B]), link_doc([INSERTED, A, B]))
    assert [d.status for d in result.differences if d.quantity != "(whole row)"] == []
    added = [d for d in result.differences if d.status == "added"]
    assert {d.table for d in added} == {"Link budget at the static points", "Margin by data rate"}
    assert result.rows_one_sided == len(added) == 1 + 3  # the point, and its three rates


def test_inserting_a_data_rate_does_not_shift_the_rate_table() -> None:
    base = link_project(links={"dl": downlink(static_points=[A, B])})
    more = link_project(
        links={"dl": downlink(static_points=[A, B], data_rates_bps=[5e3, 10e3, 100e3, 1e6])}
    )
    prov = make_provenance(base, user="u", generated_at=WHEN)
    docs = [
        build_link_report(p, link_static_budget(p), prov, [], None, plots=False)
        for p in (base, more)
    ]
    result = compare(*docs)
    values = [d for d in result.differences if d.status == "changed"]
    assert values == []


def test_pass_tables_are_keyed_by_aos_time() -> None:
    run = pass_run(aos_s=100.0, los_s=400.0)
    doc = link_doc([A], run)
    passes = next(t for s in doc.sections for t in s.tables if t.title.startswith("Passes of"))
    key = [passes.columns[i].header for i in passes.key_columns]
    assert key == ["AOS (UTC)"]


def test_a_generic_table_can_declare_its_key_columns() -> None:
    columns = (Column("Pass"), Column("AOS"), Column("Margin", "number", 2))

    def doc(rows: list[tuple[object, ...]]) -> ReportDocument:
        table = Table("Passes", columns, tuple(rows), key_columns=(1,))  # type: ignore[arg-type]
        return ReportDocument("R", PROV, (Section("S", "S", tables=(table,)),))

    a = doc([("1", "10:00", 3.0), ("2", "12:00", 4.0)])
    b = doc([("1", "08:00", 9.0), ("2", "10:00", 3.0), ("3", "12:00", 4.0)])
    result = compare(a, b)
    # the margins pair up by AOS; only the renumbering and the inserted pass show
    assert [(d.row, d.quantity) for d in result.differences if d.status == "changed"] == [
        ("10:00", "Pass"),
        ("12:00", "Pass"),
    ]
    assert [d.row for d in result.differences if d.status == "added"] == ["08:00"]


def test_negative_zero_is_not_a_change() -> None:
    cols = (Column("Item"), Column("Value", "number", 2))

    def doc(value: float) -> ReportDocument:
        return ReportDocument(
            "R", PROV, (Section("S", "S", tables=(Table("T", cols, (("a", value),)),)),)
        )

    assert compare(doc(-0.0), doc(0.0)).differences == ()
    assert compare(doc(-0.001), doc(0.0)).differences == ()  # both show 0.00


def test_change_and_percent_come_from_the_raw_values() -> None:
    cols = (Column("Item"), Column("Value", "number", 3))

    def doc(value: float) -> ReportDocument:
        return ReportDocument(
            "R", PROV, (Section("S", "S", tables=(Table("T", cols, (("a", value),)),)),)
        )

    (difference,) = compare(doc(0.1244), doc(0.1255)).differences
    assert (difference.value_a, difference.value_b) == ("0.124", "0.126")
    assert difference.change == "+0.001" and difference.change_percent == "+0.9 %"


def test_columns_on_one_side_only_are_reported() -> None:
    def doc(columns: tuple[Column, ...], row: tuple[object, ...]) -> ReportDocument:
        table = Table("T", columns, (row,))  # type: ignore[arg-type]
        return ReportDocument("R", PROV, (Section("S", "S", tables=(table,)),))

    a = doc((Column("Item"), Column("Old"), Column("Both")), ("x", "1", "2"))
    b = doc((Column("Item"), Column("New"), Column("Both")), ("x", "1", "2"))
    result = compare(a, b)
    reported = {(u.column, u.status) for u in result.unmatched}
    assert reported == {("Old", "removed"), ("New", "added")}
    output = comparison_output([result], "A", "B", PROV, "Compare")
    paragraphs = " ".join(p for s in output.document.sections for p in s.paragraphs)
    assert "Old" in paragraphs and "New" in paragraphs


def test_tables_with_the_same_title_are_both_compared() -> None:
    cols = (Column("Item"), Column("Value", "number", 1))

    def doc(first: float, second: float) -> ReportDocument:
        tables = (Table("T", cols, (("a", first),)), Table("T", cols, (("a", second),)))
        return ReportDocument("R", PROV, (Section("S", "S", tables=tables),))

    result = compare(doc(1.0, 2.0), doc(1.0, 3.0))
    assert [(d.table, d.value_a, d.value_b) for d in result.differences] == [("T #2", "2.0", "3.0")]


def test_value_and_row_counts_are_separate_and_agree_with_the_summary_line() -> None:
    cols = (Column("Item"), Column("Value", "number", 1), Column("Other", "number", 1))

    def doc(rows: list[tuple[object, ...]]) -> ReportDocument:
        table = Table("T", cols, tuple(rows))  # type: ignore[arg-type]
        return ReportDocument("R", PROV, (Section("S", "S", tables=(table,)),))

    a = doc([("a", 1.0, 1.0), ("b", 2.0, 2.0), ("c", 3.0, 3.0)])
    b = doc([("a", 9.0, 9.0), ("b", 2.0, 2.0), ("d", 4.0, 4.0)])
    result = compare(a, b)
    assert result.values_differ == 2 and result.rows_one_sided == 2 and result.compared == 4
    assert result.summary_line == (
        "2 value(s) differ out of 4 compared, and 2 row(s) exist on one side only."
    )
    output = comparison_output([result], "A", "B", PROV, "Compare")
    assert result.summary_line.rstrip(".") in " ".join(output.document.sections[0].paragraphs)


def test_csv_and_json_hold_every_difference_when_the_report_is_truncated() -> None:
    cols = (Column("Item"), Column("Value", "number", 1))
    rows_a = tuple((f"r{i}", float(i)) for i in range(10))
    rows_b = tuple((f"r{i}", float(i) + 1.0) for i in range(10))

    def doc(rows: tuple[tuple[object, ...], ...]) -> ReportDocument:
        return ReportDocument("R", PROV, (Section("S", "S", tables=(Table("T", cols, rows),)),))

    result = compare(doc(rows_a), doc(rows_b), max_rows=3)  # type: ignore[arg-type]
    assert len(result.differences) == 3 and result.truncated == 7
    output = comparison_output([result], "A", "B", PROV, "Compare")
    assert len(list(csv.reader(io.StringIO(output.csv_files[0][1])))) == 1 + 10
    data = json.loads(output.json_text)  # type: ignore[arg-type]
    assert len(data["differences"]) == 10 and data["truncated"] == 7
    text = " ".join(p for s in output.document.sections for p in s.paragraphs)
    assert "per budget" in text and "Narrow the comparison" not in text
