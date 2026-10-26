"""A new ground station or imaging target from a few answers (D-198): the checks and the data of
the file. Both are a point on the ground with a minimum elevation, and a scenario names either one
in its `sites`, so an id may not be used by both."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from budget_core.io.project_loader import load_project
from budget_core.io.yamlio import dump_yaml
from budget_core.new_site import SiteAnswers, check_site, site_data

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "microsat_250kg_eps"


def answers(**kw: object) -> SiteAnswers:
    base: dict[str, object] = {
        "kind": "ground_station",
        "site_id": "gs_east",
        "name": "Example station east",
        "latitude_deg": 52.5,
        "longitude_deg": 13.4,
        "altitude_m": 40.0,
        "min_elevation_deg": 8.0,
    }
    return SiteAnswers(**{**base, **kw})  # type: ignore[arg-type]


def issues(a: SiteAnswers, *, existing=()):  # type: ignore[no-untyped-def]
    return check_site(a, existing_ids=list(existing))


def test_good_answers_have_no_issue() -> None:
    assert issues(answers()) == []
    assert issues(answers(kind="target")) == []


@pytest.mark.parametrize(
    ("kw", "field"),
    [
        ({"kind": "antenna"}, "kind"),
        ({"site_id": ""}, "site_id"),
        ({"site_id": "a b"}, "site_id"),
        ({"name": " "}, "name"),
        ({"latitude_deg": None}, "latitude_deg"),
        ({"latitude_deg": 91.0}, "latitude_deg"),
        ({"longitude_deg": None}, "longitude_deg"),
        ({"longitude_deg": -181.0}, "longitude_deg"),
        ({"altitude_m": None}, "altitude_m"),
        ({"altitude_m": 200000.0}, "altitude_m"),
        ({"altitude_m": -2000.0}, "altitude_m"),
        ({"min_elevation_deg": None}, "min_elevation_deg"),
        ({"min_elevation_deg": 90.0}, "min_elevation_deg"),
        ({"min_elevation_deg": -1.0}, "min_elevation_deg"),
        ({"latitude_deg": float("nan")}, "latitude_deg"),
    ],
)
def test_each_wrong_answer_names_its_field(kw: dict[str, object], field: str) -> None:
    found = issues(answers(**kw))
    assert found and found[0].field == field


def test_an_id_used_by_a_station_or_a_target_is_refused_also_in_other_capitals() -> None:
    assert issues(answers(), existing=["GS_East"])[0].field == "site_id"
    assert issues(answers(kind="target"), existing=["gs_east"])[0].field == "site_id"


def test_the_data_of_each_kind() -> None:
    station = site_data(answers())
    assert station["kind"] == "ground_station" and station["name"] == "Example station east"
    assert station["latitude_deg"] == 52.5 and station["min_elevation_deg"] == 8.0
    target = site_data(answers(kind="target", name="Plains"))
    assert target["kind"] == "target" and target["name"] == "Plains"


def test_a_new_station_and_a_new_target_make_a_project_that_loads(tmp_path: Path) -> None:
    folder = tmp_path / "p"
    shutil.copytree(EXAMPLE, folder)
    (folder / "ground_stations" / "gs_east.yaml").write_text(
        dump_yaml(site_data(answers())), encoding="utf-8"
    )
    (folder / "targets" / "tgt_hills.yaml").write_text(
        dump_yaml(site_data(answers(kind="target", site_id="tgt_hills", name="Hills"))),
        encoding="utf-8",
    )
    project = load_project(folder).project
    assert project is not None
    assert {"gs_north", "gs_south", "gs_east"} <= set(project.ground_stations)
    assert "tgt_hills" in project.targets
