"""`budget orbit`: the orbit design calculator on the command line (2.2.0, D-226)."""

from __future__ import annotations

import json

import pytest

from budget_cli.main import main

EPOCH = "2026-06-01T00:00:00Z"


def _run(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, str, str]:
    code = main(["orbit", *argv])
    out = capsys.readouterr()
    return code, out.out, out.err


def test_sso_from_an_altitude(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = _run(capsys, "sso", "--altitude-km", "600", "--format", "json")
    data = json.loads(out)
    assert code == 0
    assert data["inclination_deg"] == pytest.approx(97.79, abs=0.05)
    assert data["altitude_km"] == pytest.approx(600.0)
    assert "raan_deg" not in data  # no local time asked


def test_sso_with_a_local_time_gives_the_node(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = _run(
        capsys,
        "sso",
        "--altitude-km",
        "600",
        "--ltan",
        "10:30",
        "--epoch",
        EPOCH,
        "--format",
        "json",
    )
    data = json.loads(out)
    assert code == 0 and 0.0 <= data["raan_deg"] < 360.0
    assert data["ltan_h"] == pytest.approx(10.5) and data["ltdn_h"] == pytest.approx(22.5)


def test_sso_from_an_inclination(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = _run(capsys, "sso", "--inclination-deg", "98.6", "--format", "json")
    assert code == 0 and json.loads(out)["altitude_km"] == pytest.approx(800.0, abs=15.0)


def test_sso_needs_an_altitude_or_an_inclination(capsys: pytest.CaptureFixture[str]) -> None:
    code, _, err = _run(capsys, "sso")
    assert code != 0 and "altitude" in err.lower()


def test_ltan_needs_the_epoch_and_converts_both_ways(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = _run(capsys, "ltan", "--epoch", EPOCH, "--ltan", "10:30", "--format", "json")
    raan = json.loads(out)["raan_deg"]
    assert code == 0
    code, out, _ = _run(capsys, "ltan", "--epoch", EPOCH, "--raan", str(raan), "--format", "json")
    assert code == 0 and json.loads(out)["ltan_h"] == pytest.approx(10.5, abs=1e-6)


def test_the_local_time_may_be_decimal_hours(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = _run(capsys, "ltan", "--epoch", EPOCH, "--ltan", "10.5", "--format", "json")
    assert code == 0 and json.loads(out)["ltan_h"] == pytest.approx(10.5)


@pytest.mark.parametrize("bad", ["25:00", "10:75", "abc", "-1"])
def test_a_bad_local_time_is_refused(capsys: pytest.CaptureFixture[str], bad: str) -> None:
    code, _, err = _run(capsys, "ltan", "--epoch", EPOCH, "--ltan", bad)
    assert code != 0 and "local time" in err.lower()


def test_a_bad_epoch_is_refused(capsys: pytest.CaptureFixture[str]) -> None:
    code, _, err = _run(capsys, "ltan", "--epoch", "yesterday", "--ltan", "10:30")
    assert code != 0 and "epoch" in err.lower()


def test_repeat(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = _run(
        capsys, "repeat", "--revolutions", "15", "--days", "1", "--sso", "--format", "json"
    )
    data = json.loads(out)
    assert code == 0
    assert data["altitude_km"] == pytest.approx(561.0, abs=10.0)
    assert data["track_spacing_km"] == pytest.approx(2671.0, abs=5.0)


def test_repeat_without_a_solution_says_so(capsys: pytest.CaptureFixture[str]) -> None:
    code, _, err = _run(capsys, "repeat", "--revolutions", "60", "--days", "1", "--sso")
    assert code != 0 and "no orbit" in err


def test_repeats_lists_the_cycles_of_a_window(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = _run(
        capsys,
        "repeats",
        "--altitude-min-km",
        "500",
        "--altitude-max-km",
        "800",
        "--max-days",
        "5",
        "--sso",
        "--format",
        "json",
    )
    data = json.loads(out)
    assert code == 0 and data and all(500.0 <= row["altitude_km"] <= 800.0 for row in data)
    assert [r["altitude_km"] for r in data] == sorted(r["altitude_km"] for r in data)


def test_text_output_names_each_value_with_its_unit(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = _run(capsys, "sso", "--altitude-km", "700")
    assert code == 0
    assert "Inclination" in out and " deg" in out and "Nodal period" in out and " min" in out


def test_the_earth_model_can_be_chosen(capsys: pytest.CaptureFixture[str]) -> None:
    _, a, _ = _run(capsys, "sso", "--altitude-km", "600", "--format", "json")
    _, b, _ = _run(
        capsys, "sso", "--altitude-km", "600", "--earth-model", "wgs72", "--format", "json"
    )
    assert json.loads(a)["inclination_deg"] != json.loads(b)["inclination_deg"]


# ---- from a state vector --------------------------------------------------------------------

STATE = (
    "--epoch",
    EPOCH,
    "--frame",
    "teme",
    "--position-m",
    "6978137",
    "0",
    "0",
    "--velocity-m-s",
    "0",
    "7500",
    "0",
)


def test_from_state_gives_the_mean_elements(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = _run(capsys, "from-state", *STATE, "--format", "json")
    data = json.loads(out)
    assert code == 0
    assert data["frame"] == "teme" and data["epoch"] == EPOCH
    assert 6.8e3 < data["semi_major_axis_km"] < 7.1e3 and 0.0 <= data["eccentricity"] < 0.1
    assert data["position_residual_m"] < 1e-3
    assert "osculating_semi_major_axis_km" in data and data["iterations"] >= 1


def test_from_state_text_names_the_values(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = _run(capsys, "from-state", *STATE)
    assert code == 0 and "Semi-major axis" in out and "RAAN" in out and " deg" in out


def test_from_state_needs_the_frame(capsys: pytest.CaptureFixture[str]) -> None:
    args = [a for a in STATE if a not in ("--frame", "teme")]
    code, _, err = _run(capsys, "from-state", *args)
    assert code != 0 and "frame" in err.lower()


def test_from_state_refuses_an_unbound_state(capsys: pytest.CaptureFixture[str]) -> None:
    args = list(STATE)
    args[args.index("7500")] = "12000"
    code, _, err = _run(capsys, "from-state", *args)
    assert code != 0 and "bound" in err


def test_from_state_in_j2000_differs_from_teme(capsys: pytest.CaptureFixture[str]) -> None:
    _, teme, _ = _run(capsys, "from-state", *STATE, "--format", "json")
    args = list(STATE)
    args[args.index("teme")] = "j2000"
    _, j2000, _ = _run(capsys, "from-state", *args, "--format", "json")
    assert json.loads(teme)["raan_deg"] != json.loads(j2000)["raan_deg"]
