"""Pre-release audit fixes in the link budget (TL-4 to TL-9, TL-11, TL-12, TL-15, MI-3)."""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest

from budget_core.environment.data import EnvironmentData, NDArray
from budget_core.io.project_loader import load_project
from budget_core.link.evaluate import link_pass_series, link_static_budget
from budget_core.model import Antenna, AttenuationEntry, AttenuationTable, ScenarioRule
from budget_core.provenance import make_provenance
from budget_core.reports.run import link_output
from budget_core.scenario.run import ScenarioRun, run_scenario
from tests.link_helpers import downlink, link_project, pass_run
from tests.power_helpers import sv

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
WHEN = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)


# ---- TL-4: the terms are computed independently --------------------------------------------------


def test_a_placeholder_required_margin_leaves_the_link_terms_and_blanks_the_margins() -> None:
    link = downlink(required_margin_db=sv(None))
    row = link_static_budget(link_project(links={"dl": link})).rows[0]
    assert row.path_loss_db is not None and row.eirp_dbw is not None
    assert row.g_over_t_dbk is not None and row.cn0_dbhz is not None
    assert row.atmospheric_loss_db is not None and row.required_ebn0_db is not None
    assert row.rates == () and row.max_rate_bps is None and row.max_rate_continuous_bps is None


def test_a_placeholder_attenuation_blanks_only_what_needs_it() -> None:
    project = link_project(links={"dl": downlink(attenuation=["gas"])})
    table = project.config.attenuation_table
    assert table is not None
    gas = table.entries[2].model_copy(update={"loss_db": sv(None)})
    table = AttenuationTable(entries=[*table.entries[:2], gas])
    project = replace(project, config=replace(project.config, attenuation_table=table))
    row = link_static_budget(project).rows[0]
    assert row.path_loss_db == pytest.approx(158.45, abs=0.05)  # 20 log10(4 pi 1e6 2e9 / c)
    assert row.eirp_dbw is not None and row.g_over_t_dbk is not None
    assert row.atmospheric_loss_db is None and row.cn0_dbhz is None and row.rates == ()


def test_the_pass_series_keeps_the_terms_when_the_required_ebn0_is_a_placeholder() -> None:
    result = link_pass_series(link_project(ebn0=None), pass_run())
    s = result.series[0]
    assert s.path_loss_db is not None and s.eirp_dbw is not None and s.cn0_dbhz is not None
    assert s.margin_db is None and s.selected_rate_bps is None and s.volume_bits is None


# ---- TL-5 / TL-6: samples are inside the pass, evaluated in the middle -------------------------


def ramp_run(step_s: float) -> ScenarioRun:
    """Elevation rising 0.05 degree per second (5 degrees at the start of the pass at 100 s)."""
    run = pass_run(step_s=step_s)
    vis = run.env.sites["gs"]
    t = run.env.grid.times_s
    vis = replace(vis, elevation_deg=0.05 * t, range_m=np.full(len(t), 1.0e6))
    env = replace(run.env, sites={"gs": vis})
    return ScenarioRun(run.scenario_id, run.scenario, env, run.timeline, run.notes)


@pytest.mark.parametrize("step", [10.0, 100.0, 300.0])
def test_no_sample_is_before_the_pass_or_below_the_minimum_elevation(step: float) -> None:
    s = link_pass_series(link_project(), ramp_run(step)).series[0]
    assert s.elevation_deg.min() >= 5.0 - 1e-9  # the station's minimum elevation
    assert s.times_s.min() >= 100.0 and s.times_s.max() <= 400.0
    # the first sample is the middle of the in-pass part of its step
    first_end = min(step * (np.floor(100.0 / step) + 1.0), 400.0)
    assert s.times_s[0] == pytest.approx(0.5 * (100.0 + first_end))
    assert s.passes[0].minimum_margin_db is not None


def exact_run(step_s: float, rules: list[ScenarioRule] | None = None) -> ScenarioRun:
    """One pass from 100 to 400 s whose elevation and range are known at any time, as with the
    orbit propagator: the range falls from 3000 km at the edges to 1000 km in the middle."""
    run = pass_run(step_s=step_s, rules=rules)

    def geometry(times: NDArray) -> tuple[NDArray, NDArray, NDArray]:
        x = ((np.asarray(times) - 250.0) / 150.0) ** 2
        return 5.0 + 35.0 * (1.0 - x), np.zeros(len(times)), 1.0e6 + 2.0e6 * x

    vis = replace(run.env.sites["gs"], geometry_at=geometry)
    env: EnvironmentData = replace(run.env, sites={"gs": vis})
    return ScenarioRun(run.scenario_id, run.scenario, env, run.timeline, run.notes)


@pytest.mark.parametrize("step", [1.0, 7.0, 10.0, 60.0, 300.0])
def test_volume_and_margin_do_not_depend_on_the_scenario_step(step: float) -> None:
    reference = link_pass_series(link_project(), exact_run(10.0)).series[0]
    s = link_pass_series(link_project(), exact_run(step)).series[0]
    assert s.volume_bits == pytest.approx(reference.volume_bits, rel=1e-12)
    assert s.passes[0].minimum_margin_db == pytest.approx(
        reference.passes[0].minimum_margin_db, abs=1e-9
    )
    assert s.passes[0].usable_s == pytest.approx(reference.passes[0].usable_s, abs=1e-9)
    # the rate changes inside the pass (10 kbit/s at the edges, 100 kbit/s in the middle)
    assert set(s.selected_rate_bps) == {10e3, 100e3}  # type: ignore[arg-type]
    assert 10e3 * 300.0 < s.volume_bits < 100e3 * 300.0  # type: ignore[operator]


def test_a_mode_change_inside_a_sample_counts_for_the_time_it_covers() -> None:
    rules = [ScenarioRule(kind="during_pass", site="gs", mode="b", lead_s=0.0, lag_s=0.0)]
    link = downlink(active_modes=["b"])
    whole = link_pass_series(link_project(links={"dl": link}), exact_run(60.0, rules)).series[0]
    assert whole.passes[0].usable_s == pytest.approx(300.0)
    assert whole.weight_s is not None and whole.weight_s.sum() == pytest.approx(300.0)


def test_real_orbit_volume_does_not_depend_on_the_scenario_step(tmp_path: Path) -> None:
    volumes: dict[float, float] = {}
    lowest: dict[float, float] = {}
    for step in (10.0, 60.0, 300.0):
        shutil.copytree(EXAMPLES / "microsat_150kg", tmp_path / f"p{int(step)}")
        folder = tmp_path / f"p{int(step)}"
        name = sorted(p.name for p in (folder / "scenarios").iterdir())[0]
        path = folder / "scenarios" / name
        path.write_text(
            "".join(
                f"step_s: {step}\n" if line.startswith("step_s:") else line
                for line in path.read_text().splitlines(keepends=True)
            )
        )
        project = load_project(folder).project
        assert project is not None
        run = run_scenario(project, path.stem)
        for s in link_pass_series(project, run).series:
            volumes[step] = volumes.get(step, 0.0) + (s.volume_bits or 0.0)
            station = project.ground_stations[s.site]
            assert s.elevation_deg.min() >= station.min_elevation_deg - 1e-6
            lows = [p.minimum_margin_db for p in s.passes if p.minimum_margin_db is not None]
            lowest[step] = min([lowest.get(step, 1e9), *lows])
    assert volumes[10.0] > 0.0
    assert volumes[60.0] == pytest.approx(volumes[10.0], rel=1e-9)
    assert volumes[300.0] == pytest.approx(volumes[10.0], rel=1e-9)
    assert lowest[300.0] == pytest.approx(lowest[10.0], abs=1e-9)


# ---- TL-7, TL-8 --------------------------------------------------------------------------------


def test_a_link_that_is_never_active_is_noted() -> None:
    link = downlink(active_modes=["b"])  # nothing in this scenario puts the spacecraft in mode b
    result = link_pass_series(link_project(links={"dl": link}), pass_run())
    (problem,) = [p for p in result.problems if p.code == "LINK_NEVER_ACTIVE"]
    assert problem.severity.value == "info" and problem.file == "links/dl.yaml"
    assert result.series[0].volume_bits == 0.0


def test_an_active_link_is_not_noted() -> None:
    result = link_pass_series(link_project(), pass_run())
    assert not [p for p in result.problems if p.code == "LINK_NEVER_ACTIVE"]


def test_per_day_volume_is_given_only_for_a_scenario_of_a_day_or_more() -> None:
    short = link_pass_series(link_project(), pass_run(duration_s=3000.0)).series[0]
    assert short.volume_bits and short.volume_per_day_bits is None
    note = [
        p
        for p in link_pass_series(link_project(), pass_run(duration_s=3000.0)).problems
        if p.code == "LINK_PER_DAY_NOT_GIVEN"
    ]
    assert len(note) == 1
    two_days = link_pass_series(link_project(), pass_run(duration_s=172800.0, step_s=100.0))
    s = two_days.series[0]
    assert s.volume_per_day_bits == pytest.approx(s.volume_bits / 2.0)  # type: ignore[operator]
    assert not [p for p in two_days.problems if p.code == "LINK_PER_DAY_NOT_GIVEN"]


# ---- TL-9, TL-15 -----------------------------------------------------------------------------


def with_entries(link_attenuation: list[str], entries: list[AttenuationEntry]):  # type: ignore[no-untyped-def]
    project = link_project(links={"dl": downlink(attenuation=link_attenuation)})
    table = AttenuationTable(entries=entries)
    return replace(project, config=replace(project.config, attenuation_table=table))


def entry(name: str, loss: float, freq: float = 2.0e9, elevation: float | None = None):  # type: ignore[no-untyped-def]
    return AttenuationEntry(
        name=name, attenuation_kind="gas", freq_hz=freq, elevation_deg=elevation, loss_db=sv(loss)
    )


def test_attenuation_entries_of_another_frequency_are_ignored_when_one_matches() -> None:
    project = with_entries(["gas"], [entry("gas", 0.4), entry("gas", 5.0, freq=8.0e9)])
    result = link_static_budget(project)
    assert result.rows[0].atmospheric_loss_db == pytest.approx(0.4)
    assert not [p for p in result.problems if p.code == "LINK_ATTENUATION_FREQUENCY"]


def test_attenuation_of_another_frequency_only_is_used_with_a_warning() -> None:
    project = with_entries(["gas"], [entry("gas", 5.0, freq=8.0e9)])
    result = link_static_budget(project)
    assert result.rows[0].atmospheric_loss_db == pytest.approx(5.0)
    assert [p.code for p in result.problems if p.code.startswith("LINK_ATT")] == [
        "LINK_ATTENUATION_FREQUENCY"
    ]


def test_duplicate_attenuation_entries_use_the_larger_loss_and_warn() -> None:
    project = with_entries(["gas"], [entry("gas", 0.4), entry("gas", 0.9)])
    result = link_static_budget(project)
    assert result.rows[0].atmospheric_loss_db == pytest.approx(0.9)
    assert [p.code for p in result.problems if p.code == "LINK_ATTENUATION_DUPLICATE"]
    elevation = with_entries(
        ["gas"], [entry("gas", 0.4, elevation=5.0), entry("gas", 0.9, elevation=5.0)]
    )
    assert [
        p for p in link_static_budget(elevation).problems if p.code == "LINK_ATTENUATION_DUPLICATE"
    ]


def test_attenuation_messages_do_not_repeat_the_name() -> None:
    project = with_entries(["secret name"], [entry("gas", 0.4, freq=8.0e9)])
    result = link_static_budget(project)
    assert result.problems
    assert not [p for p in result.problems if "secret" in p.message + p.hint]
    project = with_entries(["secret"], [entry("secret", 0.4, freq=8.0e9)])
    assert not [p for p in link_static_budget(project).problems if "secret" in p.message + p.hint]


# ---- TL-11, TL-12, MI-3 ----------------------------------------------------------------------


def test_an_absurd_gain_gives_null_in_the_json_not_infinity() -> None:
    tx = downlink().transmitter.model_copy(update={"antenna": Antenna(gain_dbi=sv(5000.0))})
    project = link_project(links={"dl": downlink(transmitter=tx)})
    static = link_static_budget(project)
    prov = make_provenance(project, scenario="s", user="u", generated_at=WHEN)
    text = link_output(project, static, prov).json_text

    def reject(constant: str) -> None:
        raise AssertionError(f"JSON holds {constant}")

    data = json.loads(text, parse_constant=reject)
    assert data["static"][0]["max_rate_continuous_bps"] is None


def test_a_pattern_file_with_a_byte_order_mark_is_read(tmp_path: Path) -> None:
    (tmp_path / "pattern.csv").write_bytes(b"\xef\xbb\xbfangle_deg,gain_dbi\r\n0,6\r\n60,0\r\n")
    tx = downlink().transmitter.model_copy(
        update={"antenna": Antenna(pattern_file="pattern.csv", pattern_source="test fixture")}
    )
    result = link_static_budget(link_project(root=tmp_path, links={"dl": downlink(transmitter=tx)}))
    assert result.rows[0].eirp_dbw is not None
    assert not [p for p in result.problems if p.code == "LINK_INPUT_INVALID"]


def test_a_semicolon_pattern_file_says_which_delimiter_is_read(tmp_path: Path) -> None:
    (tmp_path / "pattern.csv").write_text("angle_deg;gain_dbi\n0;6\n60;0\n", encoding="utf-8")
    tx = downlink().transmitter.model_copy(
        update={"antenna": Antenna(pattern_file="pattern.csv", pattern_source="test fixture")}
    )
    result = link_static_budget(link_project(root=tmp_path, links={"dl": downlink(transmitter=tx)}))
    (problem,) = [p for p in result.problems if p.code == "LINK_INPUT_INVALID"]
    assert "comma" in problem.hint and "semicolon" in problem.hint


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="needs named pipes")
def test_a_pattern_file_that_is_a_pipe_is_refused_without_blocking(tmp_path: Path) -> None:
    os.mkfifo(tmp_path / "pattern.csv")
    tx = downlink().transmitter.model_copy(
        update={"antenna": Antenna(pattern_file="pattern.csv", pattern_source="test fixture")}
    )
    result = link_static_budget(link_project(root=tmp_path, links={"dl": downlink(transmitter=tx)}))
    assert [p.code for p in result.problems if p.code == "LINK_INPUT_INVALID"]
