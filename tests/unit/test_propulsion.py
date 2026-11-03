"""The propulsion and delta-v budget (2.2.0, D-233): systems (chemical or electric) with a
specific impulse, manoeuvres in mission order with a delta-v, the propellant each needs by the
rocket equation (worked backwards from the dry mass), the burn time, the electric power and
energy, and the comparison with the propellant loaded in the mass budget."""

from __future__ import annotations

import math
import shutil
from pathlib import Path

import pytest

from budget_core.environment.constants import STANDARD_GRAVITY
from budget_core.io.project_loader import dump_model, load_project
from budget_core.model import Project
from budget_core.model.propulsion import Maneuver, PropulsionConfig, PropulsionSystem
from budget_core.propulsion.budget import propulsion_budget

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
G0 = STANDARD_GRAVITY.value


def sourced(value: float | None, source: str = "data sheet") -> dict[str, object]:
    return {"value": value, "source": source}


def config(**over: object) -> PropulsionConfig:
    data: dict[str, object] = {
        "systems": {
            "main": {
                "name": "Main engine",
                "type": "chemical",
                "isp_s": sourced(300.0),
                "thrust_n": sourced(100.0),
            },
            "ion": {
                "name": "Ion thruster",
                "type": "electric",
                "isp_s": sourced(1500.0),
                "thrust_n": sourced(0.05),
                "power_w": sourced(800.0),
            },
        },
        "maneuvers": [
            {"name": "Raise", "system": "main", "delta_v_m_s": sourced(200.0)},
            {"name": "Keep", "system": "ion", "delta_v_m_s": sourced(10.0), "count": 5},
        ],
        "dry_mass_kg": sourced(500.0),
    }
    data.update(over)
    return PropulsionConfig.model_validate(data)


def with_config(project: Project, cfg: PropulsionConfig) -> Project:
    from dataclasses import replace

    return replace(project, config=replace(project.config, propulsion=cfg))


@pytest.fixture(scope="module")
def project() -> Project:
    loaded = load_project(EXAMPLES / "microsat_250kg_eps")
    assert loaded.project is not None
    return loaded.project


# ---- the rocket equation ---------------------------------------------------------------------


def test_one_burn_matches_the_rocket_equation(project: Project) -> None:
    cfg = config(
        maneuvers=[{"name": "Raise", "system": "main", "delta_v_m_s": sourced(200.0)}],
        systems={"main": {"name": "m", "type": "chemical", "isp_s": sourced(300.0)}},
    )
    result = propulsion_budget(with_config(project, cfg))
    expected = 500.0 * (math.exp(200.0 / (300.0 * G0)) - 1.0)
    assert result.total_propellant_kg == pytest.approx(expected, rel=1e-12)
    assert result.initial_mass_kg == pytest.approx(500.0 + expected, rel=1e-12)


def test_the_manoeuvres_are_worked_backwards_so_the_last_burn_is_lightest(project: Project) -> None:
    result = propulsion_budget(with_config(project, config()))
    raise_, keep = result.maneuvers
    # the last burn starts from the dry mass, the first from dry mass plus the later propellant
    m_after_keep = 500.0
    m_before_keep = m_after_keep * math.exp(5 * 10.0 / (1500.0 * G0))
    assert keep.propellant_kg == pytest.approx(m_before_keep - m_after_keep, rel=1e-12)
    m_before_raise = m_before_keep * math.exp(200.0 / (300.0 * G0))
    assert raise_.propellant_kg == pytest.approx(m_before_raise - m_before_keep, rel=1e-12)
    assert raise_.mass_before_kg == pytest.approx(m_before_raise, rel=1e-12)
    assert raise_.mass_after_kg == pytest.approx(keep.mass_before_kg, rel=1e-12)


def test_the_total_delta_v_is_the_sum_and_the_propellant_adds_up(project: Project) -> None:
    result = propulsion_budget(with_config(project, config()))
    assert result.total_delta_v_m_s == pytest.approx(200.0 + 5 * 10.0)
    assert result.total_propellant_kg == pytest.approx(
        sum(m.propellant_kg for m in result.maneuvers)
    )
    assert result.initial_mass_kg == pytest.approx(500.0 + result.total_propellant_kg)
    assert sum(s.propellant_kg for s in result.systems) == pytest.approx(result.total_propellant_kg)


def test_an_electric_system_with_less_thrust_burns_longer_and_needs_power(project: Project) -> None:
    result = propulsion_budget(with_config(project, config()))
    ion = next(s for s in result.systems if s.system_id == "ion")
    main = next(s for s in result.systems if s.system_id == "main")
    # burn time = propellant * Isp * g0 / thrust (constant mass flow F / (Isp g0))
    assert ion.burn_time_s == pytest.approx(ion.propellant_kg * 1500.0 * G0 / 0.05, rel=1e-12)
    assert main.burn_time_s == pytest.approx(main.propellant_kg * 300.0 * G0 / 100.0, rel=1e-12)
    assert ion.energy_wh == pytest.approx(800.0 * ion.burn_time_s / 3600.0, rel=1e-12)
    assert ion.power_w == 800.0
    assert main.energy_wh is None and main.power_w is None  # a chemical system has no EP power


def test_a_margin_on_delta_v_scales_every_burn(project: Project) -> None:
    plain = propulsion_budget(with_config(project, config()))
    margined = propulsion_budget(with_config(project, config(delta_v_margin_ratio=sourced(0.10))))
    assert margined.total_delta_v_m_s == pytest.approx(1.1 * plain.total_delta_v_m_s)
    assert margined.total_propellant_kg > plain.total_propellant_kg
    keep = margined.maneuvers[1]
    expected = 500.0 * (math.exp(1.1 * 50.0 / (1500.0 * G0)) - 1.0)
    assert keep.propellant_kg == pytest.approx(expected, rel=1e-12)


def test_efficient_exhaust_needs_less_propellant(project: Project) -> None:
    low = propulsion_budget(
        with_config(
            project,
            config(
                systems={"main": {"name": "m", "type": "chemical", "isp_s": sourced(220.0)}},
                maneuvers=[{"name": "b", "system": "main", "delta_v_m_s": sourced(300.0)}],
            ),
        )
    )
    high = propulsion_budget(
        with_config(
            project,
            config(
                systems={"main": {"name": "m", "type": "chemical", "isp_s": sourced(320.0)}},
                maneuvers=[{"name": "b", "system": "main", "delta_v_m_s": sourced(300.0)}],
            ),
        )
    )
    assert high.total_propellant_kg < low.total_propellant_kg


# ---- placeholders and missing inputs -----------------------------------------------------------


def test_a_placeholder_isp_gives_na_not_zero_and_an_incomplete_warning(project: Project) -> None:
    cfg = config(
        systems={"main": {"name": "m", "type": "chemical", "isp_s": sourced(None, "TBD")}},
        maneuvers=[{"name": "b", "system": "main", "delta_v_m_s": sourced(100.0)}],
    )
    result = propulsion_budget(with_config(project, cfg))
    assert result.total_propellant_kg is None and result.maneuvers[0].propellant_kg is None
    assert any(p.code == "RESULT_INCOMPLETE" for p in result.problems)
    assert any(a.placeholder for a in result.assumptions)


def test_a_missing_thrust_gives_no_burn_time_only(project: Project) -> None:
    cfg = config(
        systems={"main": {"name": "m", "type": "chemical", "isp_s": sourced(300.0)}},
        maneuvers=[{"name": "b", "system": "main", "delta_v_m_s": sourced(100.0)}],
    )
    result = propulsion_budget(with_config(project, cfg))
    assert result.total_propellant_kg is not None
    assert result.systems[0].burn_time_s is None


def test_without_a_dry_mass_it_comes_from_the_mass_budget(project: Project) -> None:
    cfg = config(dry_mass_kg=None)
    result = propulsion_budget(with_config(project, cfg))
    assert result.dry_mass_kg is not None and result.dry_mass_kg > 0.0
    assert any(
        "mass budget" in a.source.lower() or "mass budget" in a.name.lower()
        for a in result.assumptions
    )


def test_no_propulsion_file_is_an_empty_result(project: Project) -> None:
    from dataclasses import replace

    bare = replace(project, config=replace(project.config, propulsion=None))
    assert propulsion_budget(bare) is None


# ---- the propellant in the mass budget ----------------------------------------------------------


def test_the_loaded_propellant_is_compared_with_the_need(project: Project) -> None:
    expendable_id = next(iter(project.expendables))
    expendable = project.expendables[expendable_id]
    loaded = max(expendable.masses_kg.values())
    cfg = config(
        systems={
            "main": {
                "name": "m",
                "type": "chemical",
                "isp_s": sourced(300.0),
                "propellant": expendable_id,
            }
        },
        maneuvers=[{"name": "b", "system": "main", "delta_v_m_s": sourced(100.0)}],
    )
    result = propulsion_budget(with_config(project, cfg))
    row = result.systems[0]
    assert row.loaded_kg == pytest.approx(loaded)
    assert row.margin_kg == pytest.approx(loaded - row.propellant_kg)
    # the dry mass then excludes the loaded propellant
    assert result.dry_mass_kg is not None


# ---- the file ------------------------------------------------------------------------------------


def test_the_file_round_trips(tmp_path: Path) -> None:
    cfg = config()
    from budget_core.io.yamlio import load_yaml_text

    again = PropulsionConfig.model_validate(load_yaml_text(dump_model(cfg)).data)
    assert again == cfg


def test_validation_rejects_bad_inputs() -> None:
    with pytest.raises(ValueError):
        PropulsionSystem.model_validate({"name": "x", "type": "nuclear", "isp_s": sourced(1.0)})
    with pytest.raises(ValueError):
        Maneuver.model_validate(
            {"name": "b", "system": "main", "delta_v_m_s": sourced(1.0), "count": 0}
        )
    with pytest.raises(ValueError):  # an electric system names its power
        config(
            systems={
                "ion": {
                    "name": "i",
                    "type": "chemical",
                    "isp_s": sourced(1.0),
                    "power_w": sourced(1.0),
                }
            }
        )


def test_a_project_with_the_file_loads_and_an_unknown_system_is_refused(tmp_path: Path) -> None:
    root = tmp_path / "p"
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", root)
    (root / "config" / "propulsion.yaml").write_text(
        "schema_version: 1\nkind: propulsion\n"
        "systems:\n  main:\n    name: Main\n    type: chemical\n"
        "    isp_s: {value: 300, source: x}\n"
        "maneuvers:\n  - name: b\n    system: nope\n    delta_v_m_s: {value: 10, source: x}\n",
        encoding="utf-8",
    )
    loaded = load_project(root)
    assert any(p.code == "REF_UNKNOWN_PROPULSION_SYSTEM" for p in loaded.problems)
    (root / "config" / "propulsion.yaml").write_text(
        "schema_version: 1\nkind: propulsion\n"
        "systems:\n  main:\n    name: Main\n    type: chemical\n"
        "    isp_s: {value: 300, source: x}\n"
        "maneuvers:\n  - name: b\n    system: main\n    delta_v_m_s: {value: 10, source: x}\n",
        encoding="utf-8",
    )
    loaded = load_project(root)
    assert loaded.project is not None and loaded.project.config.propulsion is not None


# ---- the command and the report ------------------------------------------------------------------


def test_run_writes_the_propulsion_report_and_files(tmp_path: Path) -> None:
    import csv
    import json

    from budget_cli.main import main

    out = tmp_path / "out"
    code = main(
        ["run", str(EXAMPLES / "microsat_250kg_eps"), "--budget", "propulsion", "--out", str(out)]
    )
    assert code == 0
    assert (out / "propulsion.xlsx").is_file() and (out / "propulsion.pdf").is_file()
    data = json.loads((out / "propulsion.json").read_text(encoding="utf-8"))
    assert data["result_format"]["kind"] == "propulsion"
    # 12 + 6 x 1.5 + 8 = 29 m/s plus the 10 % margin
    assert data["total_delta_v_m_s"] == pytest.approx(29.0 * 1.1)
    rows = list(csv.reader((out / "propulsion_maneuvers.csv").read_text().splitlines()))
    assert [r[0] for r in rows[1:]] == ["Orbit trim", "Station-keeping", "Deorbit"]
    expected = 236.0 * (math.exp(29.0 * 1.1 / (220.0 * G0)) - 1.0)
    assert data["total_propellant_kg"] == pytest.approx(expected, rel=1e-9)


def test_a_project_without_the_file_is_told_so(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from budget_cli.main import main

    root = tmp_path / "p"
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", root)
    (root / "config" / "propulsion.yaml").unlink()
    assert main(["run", str(root), "--budget", "propulsion", "--out", str(tmp_path / "o")]) == 1
    assert "no config/propulsion.yaml" in capsys.readouterr().err


def test_the_placeholder_example_shows_na_and_the_banner(tmp_path: Path) -> None:
    import json

    from budget_cli.main import main

    out = tmp_path / "out"
    main(["run", str(EXAMPLES / "microsat_250kg"), "--budget", "propulsion", "--out", str(out)])
    data = json.loads((out / "propulsion.json").read_text(encoding="utf-8"))
    assert data["incomplete"] is True and data["total_propellant_kg"] is None
