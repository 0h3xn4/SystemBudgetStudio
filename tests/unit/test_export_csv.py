"""Series CSV files: quoting and defusing of ids (RC-2), no negative zero, the weight column that
makes row sums match the summary (RC-24)."""

from __future__ import annotations

import csv
import io
from dataclasses import replace

import numpy as np
import pytest

from budget_core.link.evaluate import link_pass_series
from budget_core.power.time_domain import time_domain_budget
from budget_core.reports import link_export, timeline_export
from budget_core.reports.link_export import series_csv as link_series_csv
from budget_core.reports.timeline_export import series_csv
from tests.link_helpers import link_project, pass_run
from tests.power_helpers import synthetic_env, synthetic_run, td_project


def timeline_result():  # type: ignore[no-untyped-def]
    project = td_project()
    return time_domain_budget(project, synthetic_run(synthetic_env(600.0, 60.0), default_mode="b"))


def test_series_csv_quotes_and_defuses_mode_ids() -> None:
    result = timeline_result()
    nasty = ('=SUM(1,2) "q"', "b")
    changed = replace(result, mode_ids=nasty)
    text = series_csv(changed, "bol")
    rows = list(csv.reader(io.StringIO(text)))
    assert {len(r) for r in rows} == {len(rows[0])}  # commas and quotes add no columns
    mode = rows[1][2]
    assert mode == "'" + nasty[0] or mode == nasty[1]
    assert not any(r[2].startswith("=") for r in rows)


def test_series_csv_has_no_negative_zero() -> None:
    result = timeline_result()
    n = result.steps
    margin = np.full(n, -1e-9)
    margin[0] = -0.0
    case = replace(result.cases[0], margin_w=margin)
    text = series_csv(replace(result, cases=(case, *result.cases[1:])), case.case)
    assert "-0.000000" not in text and "-0.0," not in text


def test_opt_has_no_negative_zero() -> None:
    assert link_export._opt(-1e-9) == "0.000000"
    assert timeline_export._opt(-0.0) == "0.000000"
    assert link_export._opt(-0.5) == "-0.500000"


def test_link_series_rows_sum_to_the_summary_volume() -> None:
    project = link_project()
    run = pass_run(aos_s=105.0, los_s=395.0, duration_s=1000.0, step_s=10.0)
    passes = link_pass_series(project, run)
    series = passes.series[0]
    rows = list(csv.DictReader(io.StringIO(link_series_csv(passes, series))))
    total = sum(float(r["selected_rate_bps"]) * float(r["in_pass_s"]) for r in rows)
    assert total == pytest.approx(series.volume_bits)
    first, last = rows[0], rows[-1]
    assert first["before_aos"] == "true" and float(first["in_pass_s"]) == pytest.approx(5.0)
    assert last["before_aos"] == "false" and float(last["in_pass_s"]) == pytest.approx(5.0)
    assert all(r["before_aos"] == "false" for r in rows[1:])
