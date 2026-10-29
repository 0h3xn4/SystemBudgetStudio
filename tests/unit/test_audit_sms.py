"""Audit MI-20: the interim SpaceMissionStudio importer is bounded, confined and honest."""

from __future__ import annotations

import math
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from budget_core.environment.data import SiteDef, TimeGrid
from budget_core.environment.spacemissionstudio import (
    EnvironmentInputError,
    SpaceMissionStudioImport,
)

START = datetime(2026, 3, 20, 14, 46, tzinfo=UTC)
SITE = SiteDef("gs", "ground_station", 55.0, 10.0, 100.0, 5.0)
GRID = TimeGrid(START, 600.0, 60.0)
ORBIT = (
    "time_utc,x_m,y_m,z_m,vx_mps,vy_mps,vz_mps\n"
    "2026-03-20T14:46:00Z,7000000,0,0,0,7500,0\n"
    "2026-03-20T14:56:00Z,6000000,4000000,0,-3000,5000,0\n"
)
ECLIPSE = "start_utc,end_utc\n"
PASSES = "aos_utc,los_utc,max_elevation_deg\n2026-03-20T14:48:00Z,2026-03-20T14:54:00Z,40.5\n"
PROFILE = (
    "time_utc,elevation_deg,azimuth_deg,range_m\n"
    "2026-03-20T14:48:00Z,5,100,2000000\n"
    "2026-03-20T14:50:00Z,30,110,1500000\n"
    "2026-03-20T14:51:00Z,40.5,120,1200000\n"
    "2026-03-20T14:52:00Z,35,130,1300000\n"
    "2026-03-20T14:54:00Z,5,140,2000000\n"
)


def write(folder: Path, **files: str | bytes) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        data = content if isinstance(content, bytes) else content.encode("utf-8")
        (folder / name.replace("__", ".").replace("_csv", ".csv")).write_bytes(data)
    return folder


def folder_with(tmp_path: Path, profile: str | None = PROFILE, **overrides: str | bytes) -> Path:
    files: dict[str, str | bytes] = {
        "orbit_csv": ORBIT,
        "eclipse_csv": ECLIPSE,
        "passes_gs_csv": PASSES,
    }
    if profile is not None:
        files["profile_gs_csv"] = profile
    files.update(overrides)
    return write(tmp_path / "imp", **files)


def compute(folder: Path):  # type: ignore[no-untyped-def]
    return SpaceMissionStudioImport(folder).compute(GRID, [SITE], "cylindrical")


def test_the_reference_folder_loads(tmp_path: Path) -> None:
    env = compute(folder_with(tmp_path))
    assert len(env.sites["gs"].passes) == 1


def test_a_utf8_bom_from_excel_is_accepted(tmp_path: Path) -> None:
    bom = b"\xef\xbb\xbf"
    folder = folder_with(
        tmp_path,
        orbit_csv=bom + ORBIT.encode(),
        eclipse_csv=bom + ECLIPSE.encode(),
        passes_gs_csv=bom + PASSES.encode(),
        profile_gs_csv=bom + PROFILE.encode(),
    )
    assert len(compute(folder).sites["gs"].passes) == 1


@pytest.mark.parametrize("peak", ["95", "-1", "180", "nan"])
def test_a_maximum_elevation_outside_0_to_90_is_refused(tmp_path: Path, peak: str) -> None:
    passes = PASSES.replace("40.5", peak)
    with pytest.raises(EnvironmentInputError) as info:
        compute(folder_with(tmp_path, passes_gs_csv=passes))
    assert info.value.file == "passes_gs.csv" and info.value.line == 2


def test_the_time_of_maximum_is_never_invented(tmp_path: Path) -> None:
    # without a profile there is no way to know it
    (only,) = compute(folder_with(tmp_path, profile=None)).sites["gs"].passes
    assert math.isnan(only.time_of_max_s)


def test_the_time_of_maximum_comes_from_the_profile_when_there_is_one(tmp_path: Path) -> None:
    (only,) = compute(folder_with(tmp_path)).sites["gs"].passes
    assert only.time_of_max_s == pytest.approx(5 * 60.0)  # the 40.5 degree sample, 14:51:00


def test_a_semicolon_file_gets_a_message_about_the_separator(tmp_path: Path) -> None:
    with pytest.raises(EnvironmentInputError) as info:
        compute(folder_with(tmp_path, passes_gs_csv=PASSES.replace(",", ";")))
    assert "separator" in str(info.value) or "comma" in str(info.value)
    assert info.value.file == "passes_gs.csv"


@pytest.mark.skipif(sys.platform == "win32", reason="symbolic links need privileges on Windows")
def test_a_link_that_leads_out_of_the_folder_is_not_followed(tmp_path: Path) -> None:
    outside = tmp_path / "outside.csv"
    outside.write_text(PASSES, encoding="utf-8")
    folder = folder_with(tmp_path)
    (folder / "passes_gs.csv").unlink()
    os.symlink(outside, folder / "passes_gs.csv")
    with pytest.raises(EnvironmentInputError) as info:
        compute(folder)
    assert info.value.file == "passes_gs.csv" and "inside" in str(info.value)


def test_a_file_over_the_size_cap_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from budget_core.environment import spacemissionstudio as sms

    monkeypatch.setattr(sms, "MAX_FILE_BYTES", 100)
    with pytest.raises(EnvironmentInputError) as info:
        compute(folder_with(tmp_path))
    assert "too large" in str(info.value)


def test_a_file_with_too_many_rows_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from budget_core.environment import spacemissionstudio as sms

    monkeypatch.setattr(sms, "MAX_PASS_ROWS", 0)
    with pytest.raises(EnvironmentInputError) as info:
        compute(folder_with(tmp_path))
    assert "too many rows" in str(info.value)


def test_an_unknown_time_of_maximum_is_empty_in_csv_and_null_in_json(tmp_path: Path) -> None:
    import json
    from types import SimpleNamespace

    from budget_core.scenario import export

    env = compute(folder_with(tmp_path, profile=None))
    scenario = SimpleNamespace(irradiance_model="constant")
    run = SimpleNamespace(env=env, scenario_id="s", scenario=scenario, timeline=[], notes=[])
    text = export.passes_csv(run)  # type: ignore[arg-type]
    header, first = text.splitlines()[0].split(","), text.splitlines()[1].split(",")
    assert first[header.index("time_of_max_s")] == ""
    assert "nan" not in text.lower()
    provenance = SimpleNamespace(
        tool="t",
        tool_version="1",
        python_version="3.13.0",
        libraries=(("numpy", "2.0"),),
        project_name="p",
        project_revision="1",
        generated="2026-01-01T00:00:00Z",
        user="u",
        inputs_digest="",
        input_files=(),
        parameters=(),
        illustrative_inputs=None,
    )
    data = json.loads(export.environment_json(run, provenance))  # type: ignore[arg-type]
    assert data["sites"]["gs"]["passes"][0]["time_of_max_s"] is None


def test_the_documented_row_caps_are_generous_but_finite() -> None:
    from budget_core.environment import spacemissionstudio as sms

    assert 604_801 < sms.MAX_ROWS <= 5_000_000  # a week at 1 s is the design case
    assert 1_000 <= sms.MAX_PASS_ROWS <= 1_000_000
