"""D-207: every problem code has an entry, the entries are complete, and the page is current."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from budget_core.problem_catalogue import CATALOGUE, describe, render_markdown
from budget_core.problems import Problem, Severity

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
CODE = re.compile(r"^[A-Z][A-Z0-9]+(_[A-Z0-9]+)+$")

# Upper-case strings of the sources that are not problem codes (environment variables, names of
# model constants listed in an `__all__`, keys of forms). A new one of this shape is either a
# problem code (give it a catalogue entry) or belongs here.
NOT_CODES = frozenset(
    {
        "APOGEE_RANGE_KM",
        "BUDGET_CONFIG_DIR",
        "BUDGET_NO_LAYOUT",
        "BUDGET_USER",
        "CURRENT_VERSIONS",
        "FREQUENCY_RANGE_MHZ",
        "GROUND_STATION",
        "MIN_STEP_S",
        "OFF_MODE",
        "SOURCE_DATE_EPOCH",
    }
)


def _raised_candidates() -> set[str]:
    found: set[str] = set()
    for path in sorted(SRC.rglob("*.py")):
        if "theme" in path.parts:  # sizes, colours and fonts are named in capitals too
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and CODE.match(node.value)
            ):
                found.add(node.value)
    return found - NOT_CODES


def test_every_code_the_tool_can_raise_has_an_entry_and_no_entry_is_for_nothing() -> None:
    raised = _raised_candidates()
    assert raised - set(CATALOGUE) == set(), "codes without a catalogue entry"
    assert set(CATALOGUE) - raised == set(), "catalogue entries for codes that nothing raises"


def test_every_entry_is_complete_and_free_of_project_values() -> None:
    for code, entry in CATALOGUE.items():
        assert entry.code == code and CODE.match(code)
        for text in (entry.title, entry.rule, entry.why, entry.fix):
            assert text.strip() and "{" not in text and "}" not in text, code
        for text in (entry.rule, entry.why, entry.fix):
            assert text.rstrip().endswith("."), (code, text)
        assert entry.area


def test_describe_finds_an_entry_and_none_for_an_unknown_code() -> None:
    assert describe("MASS_LIMIT_EXCEEDED") is not None
    assert describe("NO_SUCH_CODE") is None


def test_the_page_of_codes_is_the_generated_one() -> None:
    page = (ROOT / "docs" / "PROBLEMS.md").read_text(encoding="utf-8")
    assert page == render_markdown(), "run: budget problems --markdown > docs/PROBLEMS.md"


def test_a_finding_with_numbers_says_so_and_a_plain_one_does_not() -> None:
    plain = Problem(Severity.ERROR, "X_Y", "m")
    assert plain.values_text() == "" and "actual" not in plain.to_dict()
    found = Problem(Severity.ERROR, "X_Y", "m", actual=12.5, limit=10.0, unit="kg")
    assert found.values_text() == "found 12.5 kg, limit 10 kg"
    assert found.to_dict()["actual"] == 12.5 and found.to_dict()["unit"] == "kg"
    assert "12.5" not in found.format()  # the command line text stays free of project values
