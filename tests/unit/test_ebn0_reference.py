# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""The error-rate reference of an Eb/N0 entry (2.1.0): the bit error rate and the frame error rate
the required Eb/N0 refers to. It is recorded as given and shown with the number; the tool never
supplies one and no result depends on it."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError

from budget_core.explain import Explainer
from budget_core.io.migrations import DEFAULT_REGISTRY
from budget_core.io.project_loader import load_project, model_to_data
from budget_core.link.evaluate import link_static_budget
from budget_core.model import CURRENT_VERSIONS, Ebn0Entry, Ebn0Table, Sourced
from budget_core.new_ebn0 import Ebn0Answers, check_ebn0, ebn0_entry_data

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
TABLE = "config/ebn0_table.yaml"


def _entry(**extra: object) -> Ebn0Entry:
    return Ebn0Entry(
        modulation="QPSK",
        coding="rate 1/2",
        required_ebn0_db=Sourced(value=4.0, source="A data sheet"),
        **extra,  # type: ignore[arg-type]
    )


# ---- the model ------------------------------------------------------------------------------


def test_the_reference_is_optional_and_absent_by_default() -> None:
    entry = _entry()
    assert entry.target_ber is None and entry.target_fer is None
    assert "target_ber" not in model_to_data(Ebn0Table(entries=[entry]))["entries"][0]


def test_a_reference_is_kept_and_written() -> None:
    entry = _entry(target_ber=1e-5, target_fer=1e-7)
    written = model_to_data(Ebn0Table(entries=[entry]))["entries"][0]
    assert written["target_ber"] == 1e-5 and written["target_fer"] == 1e-7


@pytest.mark.parametrize("bad", [0.0, -1e-5, 1.0, 2.0])
def test_a_rate_must_be_between_zero_and_one(bad: float) -> None:
    with pytest.raises(ValidationError):
        _entry(target_ber=bad)
    with pytest.raises(ValidationError):
        _entry(target_fer=bad)


def test_the_text_names_what_is_recorded() -> None:
    assert _entry().reference_text() == ""
    assert _entry(target_ber=1e-5).reference_text() == "BER 1e-05"
    assert _entry(target_fer=1e-7).reference_text() == "FER 1e-07"
    assert _entry(target_ber=1e-5, target_fer=1e-7).reference_text() == "BER 1e-05, FER 1e-07"


# ---- the file format ------------------------------------------------------------------------


def test_the_schema_version_went_up_and_an_older_table_reads_unchanged() -> None:
    assert CURRENT_VERSIONS["ebn0_table"] == 3
    data = {"schema_version": 2, "kind": "ebn0_table", "entries": []}
    out, problem = DEFAULT_REGISTRY.migrate("ebn0_table", data)
    assert out["schema_version"] == 3 and out["entries"] == []
    assert problem is not None and problem.code == "FILE_MIGRATED"


def _project_with(tmp_path: Path, ber: str) -> Path:
    root = tmp_path / "p"
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", root)
    path = root / TABLE
    text = path.read_text(encoding="utf-8")
    text = text.replace("    coding: rate 1/2\n", f"    coding: rate 1/2\n{ber}", 1)
    path.write_text(text, encoding="utf-8", newline="\n")
    return root


def test_a_table_with_a_reference_loads_clean(tmp_path: Path) -> None:
    root = _project_with(tmp_path, "    target_ber: 1.0e-5\n    target_fer: 1.0e-7\n")
    result = load_project(root)
    assert result.project is not None
    entry = result.project.config.ebn0_table.entries[0]  # type: ignore[union-attr]
    assert entry.target_ber == 1e-5 and entry.target_fer == 1e-7
    assert not [p for p in result.problems if p.severity == "error"]


def test_a_rate_out_of_range_is_a_problem_not_a_crash(tmp_path: Path) -> None:
    result = load_project(_project_with(tmp_path, "    target_ber: 2\n"))
    assert any(p.file == TABLE for p in result.problems)


# ---- shown with the number ------------------------------------------------------------------


def test_the_budget_names_the_reference_next_to_the_required_ebn0(tmp_path: Path) -> None:
    root = _project_with(tmp_path, "    target_ber: 1.0e-5\n")
    project = load_project(root).project
    assert project is not None
    names = [a.name for a in link_static_budget(project).assumptions]
    assert "Required Eb/N0, QPSK rate 1/2 at BER 1e-05" in names


def test_the_budget_is_unchanged_without_a_reference() -> None:
    project = load_project(EXAMPLES / "microsat_250kg_eps").project
    assert project is not None
    names = [a.name for a in link_static_budget(project).assumptions]
    assert "Required Eb/N0, QPSK rate 1/2" in names


def test_explain_names_the_reference(tmp_path: Path) -> None:
    root = _project_with(tmp_path, "    target_ber: 1.0e-5\n    target_fer: 1.0e-7\n")
    project = load_project(root).project
    assert project is not None
    explainer = Explainer(project)
    table = explainer.table("link:static")
    key = tuple(str(table.rows[0][i]) for i in table.key_columns)
    explanation = explainer.explain("link:static", key, "Required Eb/N0 (dB)")
    text = "\n".join(
        f"{s.label} {s.logic}" + " ".join(q.name for q in s.inputs) for s in explanation.steps
    )
    assert "BER 1e-05, FER 1e-07" in text


def test_the_same_value_gives_the_same_result_with_or_without_it(tmp_path: Path) -> None:
    plain = load_project(_project_with(tmp_path / "a", "")).project
    with_ref = load_project(_project_with(tmp_path / "b", "    target_ber: 1.0e-5\n")).project
    assert plain is not None and with_ref is not None
    a, b = link_static_budget(plain), link_static_budget(with_ref)
    assert [r.required_ebn0_db for r in a.rows] == [r.required_ebn0_db for r in b.rows]


# ---- the form -------------------------------------------------------------------------------


def test_the_form_answers_can_carry_the_reference() -> None:
    answers = Ebn0Answers("QPSK", "rate 1/2", target_ber="1e-5", target_fer="1e-7")
    assert check_ebn0(answers, existing_pairs=[]) == []
    data = ebn0_entry_data(answers)
    assert data["target_ber"] == 1e-5 and data["target_fer"] == 1e-7
    assert data["required_ebn0_db"]["source"] == "TBD"  # the Eb/N0 itself is still a placeholder


def test_the_form_without_a_reference_writes_none() -> None:
    data = ebn0_entry_data(Ebn0Answers("QPSK", "none"))
    assert "target_ber" not in data and "target_fer" not in data


@pytest.mark.parametrize("text", ["abc", "0", "1", "-1e-5", "2", "1e-5 x"])
def test_the_form_refuses_a_rate_that_is_not_between_zero_and_one(text: str) -> None:
    issues = check_ebn0(Ebn0Answers("QPSK", "none", target_ber=text), existing_pairs=[])
    assert issues and issues[0].field == "target_ber"
    issues = check_ebn0(Ebn0Answers("QPSK", "none", target_fer=text), existing_pairs=[])
    assert issues and issues[0].field == "target_fer"
