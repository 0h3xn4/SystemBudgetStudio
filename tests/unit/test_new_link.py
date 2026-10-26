"""A new link from a few answers (D-199): the checks and the data of the file. Only the structure
is asked for (direction, peer, frequency, modulation, coding, data rates); every sourced number
is written as a placeholder (`source: TBD`) to be filled in the inputs grid, never invented."""

from __future__ import annotations

import math
import shutil
from pathlib import Path

import pytest

from budget_core.io.project_loader import load_project
from budget_core.io.yamlio import dump_yaml
from budget_core.new_link import LinkAnswers, check_link, link_data

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "microsat_250kg_eps"
STATIONS = ["gs_north", "gs_south"]


def answers(**kw: object) -> LinkAnswers:
    base: dict[str, object] = {
        "link_id": "uhf_down",
        "name": "UHF telemetry downlink",
        "direction": "downlink",
        "peer": "gs_north",
        "frequency_mhz": 437.0,
        "modulation": "QPSK",
        "coding": "rate 1/2",
        "data_rates_bps": (9600.0, 19200.0),
    }
    return LinkAnswers(**{**base, **kw})  # type: ignore[arg-type]


PAIRS = [("QPSK", "rate 1/2"), ("QPSK", "none")]


def issues(
    a: LinkAnswers,
    existing: list[str] | None = None,
    pairs: list[tuple[str, str]] | None = None,
) -> list[str]:
    return [
        i.field
        for i in check_link(
            a,
            existing_ids=existing or [],
            ground_station_ids=STATIONS,
            ebn0_pairs=PAIRS if pairs is None else pairs,
        )
    ]


def test_good_answers_pass_for_both_directions() -> None:
    assert issues(answers()) == []
    assert issues(answers(direction="uplink")) == []


@pytest.mark.parametrize(
    ("change", "field"),
    [
        ({"link_id": ""}, "link_id"),
        ({"link_id": "a b"}, "link_id"),
        ({"link_id": "x" * 100}, "link_id"),
        ({"name": "  "}, "name"),
        ({"direction": "sideways"}, "direction"),
        ({"peer": ""}, "peer"),
        ({"peer": "gs_nowhere"}, "peer"),
        ({"frequency_mhz": None}, "frequency_mhz"),
        ({"frequency_mhz": math.nan}, "frequency_mhz"),
        ({"frequency_mhz": 0.0}, "frequency_mhz"),
        ({"frequency_mhz": -1.0}, "frequency_mhz"),
        ({"frequency_mhz": 2.2e9}, "frequency_mhz"),  # Hz typed in a MHz field
        ({"modulation": ""}, "modulation"),
        ({"coding": " "}, "coding"),
        ({"data_rates_bps": ()}, "data_rates_bps"),
        ({"data_rates_bps": (0.0,)}, "data_rates_bps"),
        ({"data_rates_bps": (9600.0, -1.0)}, "data_rates_bps"),
        ({"data_rates_bps": (9600.0, math.nan)}, "data_rates_bps"),
    ],
)
def test_wrong_answers_are_named_by_field(change: dict[str, object], field: str) -> None:
    assert field in issues(answers(**change))


def test_a_pair_that_the_table_does_not_list_is_refused_unless_the_table_is_empty() -> None:
    other = answers(modulation="BPSK", coding="rate 1/2")
    assert "modulation" in issues(other)
    assert "modulation" in issues(answers(coding="Rate 1/2"))  # the loader compares exactly
    assert issues(other, pairs=[]) == []  # a blank project has no table entries yet


def test_an_id_of_another_link_is_refused_also_in_other_capitals() -> None:
    assert "link_id" in issues(answers(), ["uhf_down"])
    assert "link_id" in issues(answers(), ["UHF_Down"])
    assert issues(answers(), ["sband_down"]) == []


def test_the_data_has_the_structure_and_only_placeholders_for_the_sourced_numbers() -> None:
    data = link_data(answers())
    assert data["kind"] == "link" and data["direction"] == "downlink"
    assert data["peer"] == "gs_north" and data["frequency_hz"] == 437.0e6
    assert data["modulation"] == "QPSK" and data["coding"] == "rate 1/2"
    assert data["data_rates_bps"] == [9600.0, 19200.0]
    sourced = [
        data["transmitter"]["power_w"],
        data["transmitter"]["line_loss_db"],
        data["transmitter"]["antenna"]["gain_dbi"],
        data["receiver"]["g_over_t_dbk"],
        data["required_margin_db"],
        data["pointing_loss_db"],
        data["polarisation_loss_db"],
        data["implementation_loss_db"],
    ]
    assert all(s["value"] is None and s["source"] == "TBD" for s in sourced)


def test_the_data_rates_are_sorted_and_without_doubles() -> None:
    assert link_data(answers(data_rates_bps=(19200.0, 9600.0, 9600.0)))["data_rates_bps"] == [
        9600.0,
        19200.0,
    ]


def test_a_new_link_makes_a_project_that_loads_with_the_placeholders_reported(
    tmp_path: Path,
) -> None:
    folder = tmp_path / "p"
    shutil.copytree(EXAMPLE, folder)
    (folder / "links" / "uhf_down.yaml").write_text(
        dump_yaml(link_data(answers())), encoding="utf-8"
    )
    loaded = load_project(folder)
    assert loaded.project is not None
    link = loaded.project.links["uhf_down"]
    assert link.peer == "gs_north" and link.transmitter.power_w.is_placeholder
    assert not [p for p in loaded.problems if p.severity.name == "ERROR"]
