"""The pointing and slew budget (2.2.0, D-234): pointing modes (an attitude reference, an accuracy
and the power to hold it) kept apart from the spacecraft modes, and slews between them with a
bang-bang time from the inertia and the torque, the peak rate and momentum, the energy and the
margin against the momentum the actuators can store."""

from __future__ import annotations

import math
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from budget_core.io.project_loader import dump_model, load_project
from budget_core.io.yamlio import load_yaml_text
from budget_core.model import Project
from budget_core.model.pointing import PointingConfig
from budget_core.pointing.budget import pointing_budget

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


def sourced(value: float | None, source: str = "data sheet") -> dict[str, object]:
    return {"value": value, "source": source}


def config(**over: object) -> PointingConfig:
    data: dict[str, object] = {
        "actuators": {
            "wheels": {
                "name": "Reaction wheels",
                "max_torque_nm": sourced(0.1),
                "max_rate_deg_s": sourced(2.0),
                "momentum_capacity_nms": sourced(8.0),
                "slew_power_w": sourced(60.0),
            }
        },
        "modes": {
            "nadir": {
                "name": "Nadir",
                "reference": "nadir",
                "accuracy_deg": sourced(0.5),
                "actuator": "wheels",
                "hold_power_w": sourced(12.0),
            },
            "target": {
                "name": "Target",
                "reference": "target",
                "accuracy_deg": sourced(0.1),
                "actuator": "wheels",
                "hold_power_w": sourced(20.0),
            },
        },
        "slews": [
            {
                "name": "To target",
                "from_mode": "nadir",
                "to_mode": "target",
                "angle_deg": sourced(90.0),
                "axis": "x",
                "actuator": "wheels",
                "inertia_kgm2": sourced(100.0),
            },
        ],
    }
    data.update(over)
    return PointingConfig.model_validate(data)


def with_config(project: Project, cfg: PointingConfig) -> Project:
    return replace(project, config=replace(project.config, pointing=cfg))


@pytest.fixture(scope="module")
def project() -> Project:
    loaded = load_project(EXAMPLES / "microsat_250kg_eps")
    assert loaded.project is not None
    return loaded.project


def slew(over: dict[str, object] | None = None, **cfg: object) -> dict[str, object]:
    base = {
        "name": "s",
        "from_mode": "nadir",
        "to_mode": "target",
        "angle_deg": sourced(90.0),
        "axis": "x",
        "actuator": "wheels",
        "inertia_kgm2": sourced(100.0),
    }
    base.update(over or {})
    return base


# ---- the slew --------------------------------------------------------------------------------


def test_a_triangular_profile_when_the_rate_limit_is_not_reached(project: Project) -> None:
    # 90 degrees, I = 100, T = 0.1: alpha = 1e-3 rad/s2; t = 2 sqrt(theta / alpha); peak rate
    # sqrt(theta alpha) = 0.0396 rad/s = 2.27 deg/s -- raise the limit above it
    cfg = config(
        actuators={
            "wheels": {"name": "w", "max_torque_nm": sourced(0.1), "max_rate_deg_s": sourced(5.0)}
        }
    )
    s = pointing_budget(with_config(project, cfg)).slews[0]
    theta, alpha = math.radians(90.0), 0.1 / 100.0
    assert s.slew_time_s == pytest.approx(2.0 * math.sqrt(theta / alpha), rel=1e-12)
    assert s.peak_rate_deg_s == pytest.approx(math.degrees(math.sqrt(theta * alpha)), rel=1e-12)
    assert s.peak_momentum_nms == pytest.approx(100.0 * math.sqrt(theta * alpha), rel=1e-12)
    assert not s.rate_limited


def test_a_trapezoid_when_the_rate_limit_is_reached(project: Project) -> None:
    s = pointing_budget(with_config(project, config())).slews[0]  # limit 2 deg/s < 2.27 deg/s
    theta, alpha, wmax = math.radians(90.0), 1e-3, math.radians(2.0)
    assert s.rate_limited
    assert s.slew_time_s == pytest.approx(theta / wmax + wmax / alpha, rel=1e-12)
    assert s.peak_rate_deg_s == pytest.approx(2.0)
    assert s.peak_momentum_nms == pytest.approx(100.0 * wmax, rel=1e-12)


def test_the_two_profiles_agree_at_the_limit(project: Project) -> None:
    theta, alpha = math.radians(90.0), 1e-3
    wmax_deg = math.degrees(math.sqrt(theta * alpha))
    cfg = config(
        actuators={
            "wheels": {
                "name": "w",
                "max_torque_nm": sourced(0.1),
                "max_rate_deg_s": sourced(wmax_deg),
            }
        }
    )
    s = pointing_budget(with_config(project, cfg)).slews[0]
    assert s.slew_time_s == pytest.approx(2.0 * math.sqrt(theta / alpha), rel=1e-9)


def test_a_bigger_inertia_or_a_smaller_torque_makes_a_longer_slew(project: Project) -> None:
    base = pointing_budget(
        with_config(
            project, config(actuators={"wheels": {"name": "w", "max_torque_nm": sourced(0.1)}})
        )
    ).slews[0]
    heavy = pointing_budget(
        with_config(
            project,
            config(
                actuators={"wheels": {"name": "w", "max_torque_nm": sourced(0.1)}},
                slews=[slew({"inertia_kgm2": sourced(400.0)})],
            ),
        )
    ).slews[0]
    assert heavy.slew_time_s == pytest.approx(2.0 * base.slew_time_s, rel=1e-12)  # sqrt(4)


def test_the_settling_time_adds_and_the_energy_follows_the_total(project: Project) -> None:
    cfg = config(slews=[slew({"settle_s": sourced(30.0), "per_day": 4})])
    s = pointing_budget(with_config(project, cfg)).slews[0]
    assert s.total_time_s == pytest.approx(s.slew_time_s + 30.0)
    assert s.energy_wh == pytest.approx(60.0 * s.slew_time_s / 3600.0)  # powered while slewing
    assert s.energy_per_day_wh == pytest.approx(4 * s.energy_wh)


def test_the_momentum_margin_is_capacity_minus_peak(project: Project) -> None:
    s = pointing_budget(with_config(project, config())).slews[0]
    assert s.momentum_margin_nms == pytest.approx(8.0 - s.peak_momentum_nms)


def test_a_slew_that_stores_more_than_the_capacity_is_a_finding(project: Project) -> None:
    cfg = config(
        actuators={
            "wheels": {
                "name": "w",
                "max_torque_nm": sourced(0.1),
                "momentum_capacity_nms": sourced(1.0),
            }
        }
    )
    result = pointing_budget(with_config(project, cfg))
    assert result.slews[0].momentum_margin_nms < 0.0
    assert any(p.code == "POINTING_MOMENTUM_EXCEEDED" for p in result.problems)


# ---- inertia, modes, placeholders ------------------------------------------------------------


def test_the_inertia_comes_from_the_mass_budget_when_not_given(project: Project) -> None:
    cfg = config(
        slews=[
            {
                "name": "s",
                "from_mode": "nadir",
                "to_mode": "target",
                "angle_deg": sourced(30.0),
                "axis": "z",
                "actuator": "wheels",
            }
        ]
    )
    result = pointing_budget(with_config(project, cfg))
    s = result.slews[0]
    assert s.inertia_kgm2 is not None and s.inertia_kgm2 > 0.0
    assert "mass budget" in s.inertia_source


def test_the_pointing_modes_table_has_the_hold_power(project: Project) -> None:
    result = pointing_budget(with_config(project, config()))
    nadir = next(m for m in result.modes if m.mode_id == "nadir")
    assert nadir.hold_power_w == 12.0 and nadir.accuracy_deg == 0.5 and nadir.reference == "nadir"


def test_a_placeholder_torque_gives_na_and_a_warning(project: Project) -> None:
    cfg = config(actuators={"wheels": {"name": "w", "max_torque_nm": sourced(None, "TBD")}})
    result = pointing_budget(with_config(project, cfg))
    assert result.slews[0].slew_time_s is None and result.slews[0].energy_wh is None
    assert any(p.code == "RESULT_INCOMPLETE" for p in result.problems)


def test_no_pointing_file_is_an_empty_result(project: Project) -> None:
    bare = replace(project, config=replace(project.config, pointing=None))
    assert pointing_budget(bare) is None


# ---- the file --------------------------------------------------------------------------------


def test_the_file_round_trips() -> None:
    cfg = config()
    assert PointingConfig.model_validate(load_yaml_text(dump_model(cfg)).data) == cfg


def test_validation_rejects_bad_inputs() -> None:
    with pytest.raises(ValueError):
        config(slews=[slew({"axis": "w"})])
    with pytest.raises(ValueError):
        config(slews=[slew({"per_day": 0})])
    with pytest.raises(ValueError):
        config(modes={"a": {"name": "a", "reference": "moon", "actuator": "wheels"}})


def test_unknown_references_are_refused(tmp_path: Path) -> None:
    root = tmp_path / "p"
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", root)
    base = (
        "schema_version: 1\nkind: pointing\n"
        "actuators:\n  wheels:\n    name: W\n    max_torque_nm: {value: 0.1, source: x}\n"
        "modes:\n  a: {name: A, reference: nadir, actuator: wheels}\n"
        "  b: {name: B, reference: sun, actuator: wheels}\n"
        "slews:\n  - {name: s, from_mode: a, to_mode: %s, axis: x, actuator: %s,\n"
        "      angle_deg: {value: 10, source: x}, inertia_kgm2: {value: 10, source: x}}\n"
    )
    target = root / "config" / "pointing.yaml"
    target.write_text(base % ("nope", "wheels"), encoding="utf-8")
    assert any(p.code == "REF_UNKNOWN_POINTING_MODE" for p in load_project(root).problems)
    target.write_text(base % ("b", "nope"), encoding="utf-8")
    assert any(p.code == "REF_UNKNOWN_ACTUATOR" for p in load_project(root).problems)
    target.write_text(base % ("b", "wheels"), encoding="utf-8")
    loaded = load_project(root)
    assert loaded.project is not None and loaded.project.config.pointing is not None


# ---- the command -----------------------------------------------------------------------------


def test_run_writes_the_pointing_report(tmp_path: Path) -> None:
    import json

    from budget_cli.main import main

    out = tmp_path / "out"
    code = main(
        ["run", str(EXAMPLES / "microsat_250kg_eps"), "--budget", "pointing", "--out", str(out)]
    )
    assert code == 0
    data = json.loads((out / "pointing.json").read_text(encoding="utf-8"))
    assert data["result_format"]["kind"] == "pointing" and data["slews"]
    assert (out / "pointing_slews.csv").is_file() and (out / "pointing.xlsx").is_file()
