"""A new Eb/N0 table entry from a few answers (D-200): the checks and the data. Only the pair
(modulation, coding) is asked for; the required Eb/N0 is a number from a standard or a data sheet,
so it is written as a placeholder (`source: TBD`) for the inputs grid, never invented."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from budget_core.io.project_loader import load_project
from budget_core.io.yamlio import dump_yaml
from budget_core.new_ebn0 import Ebn0Answers, check_ebn0, ebn0_entry_data, ebn0_table_data

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "microsat_250kg_eps"
PAIRS = [("QPSK", "rate 1/2"), ("QPSK", "none")]


def fields(a: Ebn0Answers, pairs: list[tuple[str, str]] | None = None) -> list[str]:
    return [i.field for i in check_ebn0(a, existing_pairs=PAIRS if pairs is None else pairs)]


def test_a_new_pair_passes() -> None:
    assert fields(Ebn0Answers("BPSK", "rate 1/2")) == []
    assert fields(Ebn0Answers("8PSK", "none"), pairs=[]) == []


@pytest.mark.parametrize(
    ("answers", "field"),
    [
        (Ebn0Answers("", "none"), "modulation"),
        (Ebn0Answers("  ", "none"), "modulation"),
        (Ebn0Answers("BPSK", ""), "coding"),
        (Ebn0Answers("x" * 500, "none"), "modulation"),
        (Ebn0Answers("BPSK", "x" * 500), "coding"),
    ],
)
def test_wrong_answers_are_named_by_field(answers: Ebn0Answers, field: str) -> None:
    assert field in fields(answers)


def test_a_pair_that_is_in_the_table_is_refused_also_in_other_capitals() -> None:
    assert "modulation" in fields(Ebn0Answers("QPSK", "none"))
    assert "modulation" in fields(Ebn0Answers("qpsk", "None"))
    assert "modulation" in fields(Ebn0Answers(" QPSK ", "none"))  # spaces around do not count
    assert fields(Ebn0Answers("QPSK", "rate 3/4")) == []  # the same modulation, another coding


def test_the_entry_has_the_pair_and_a_placeholder_for_the_required_value() -> None:
    entry = ebn0_entry_data(Ebn0Answers(" BPSK ", " rate 1/2 "))
    assert entry["modulation"] == "BPSK" and entry["coding"] == "rate 1/2"
    required = entry["required_ebn0_db"]
    assert required["value"] is None and required["source"] == "TBD"


def test_a_new_table_has_the_one_entry() -> None:
    table = ebn0_table_data(Ebn0Answers("BPSK", "none"))
    assert table["kind"] == "ebn0_table" and len(table["entries"]) == 1


def test_an_entry_added_to_the_table_of_a_project_loads_as_a_placeholder(tmp_path: Path) -> None:
    folder = tmp_path / "p"
    shutil.copytree(EXAMPLE, folder)
    path = folder / "config" / "ebn0_table.yaml"
    loaded = load_project(folder).project
    assert loaded is not None and loaded.config.ebn0_table is not None
    data = loaded.config.ebn0_table.model_dump(mode="json")
    data["entries"].append(ebn0_entry_data(Ebn0Answers("BPSK", "rate 1/2")))
    path.write_text(dump_yaml(data), encoding="utf-8")
    result = load_project(folder)
    assert result.project is not None
    assert not [p for p in result.problems if p.severity.name == "ERROR"]
    table = result.project.config.ebn0_table
    assert table is not None
    added = [e for e in table.entries if (e.modulation, e.coding) == ("BPSK", "rate 1/2")]
    assert len(added) == 1 and added[0].required_ebn0_db.is_placeholder
