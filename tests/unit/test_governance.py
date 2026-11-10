# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""Repository governance files (protection programme, phase 7; D-264)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml import YAML

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("pr_body_check", ROOT / "packaging/pr_body_check.py")
assert spec is not None and spec.loader is not None
check = importlib.util.module_from_spec(spec)
sys.modules["pr_body_check"] = check
spec.loader.exec_module(check)

STATEMENT = (
    "I have not included confidential, proprietary, export-controlled, personal or customer data."
)


def _load(path: Path) -> Any:
    return YAML(typ="safe").load(path.read_text(encoding="utf-8"))


# ---- the data box ------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "body",
    [f"- [x] {STATEMENT}", f"text\n\n- [X] {STATEMENT}\n- [ ] other", f"  * [x]   {STATEMENT}  "],
)
def test_a_ticked_box_passes(body: str) -> None:
    assert check.passes(body, "someone")


@pytest.mark.parametrize(
    "body",
    ["", f"- [ ] {STATEMENT}", STATEMENT, "- [x] I checked it", f"- [x] {STATEMENT} (maybe)"],
)
def test_a_missing_or_unticked_box_fails(body: str) -> None:
    assert not check.passes(body, "someone")


def test_only_dependabot_is_exempt() -> None:
    assert check.passes("", "dependabot[bot]")
    assert not check.passes("", "dependabot")
    assert not check.passes("", "someone-else[bot]")


def test_the_pull_request_template_has_the_box_unticked() -> None:
    template = (ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md").read_text(encoding="utf-8")
    assert f"- [ ] {STATEMENT}" in template
    assert not check.passes(template, "someone")


def test_the_workflow_runs_on_edits_and_passes_text_through_the_environment() -> None:
    workflow = _load(ROOT / ".github" / "workflows" / "pr-checklist.yml")
    triggers = workflow.get("on") or workflow.get(True)
    assert "edited" in triggers["pull_request"]["types"]
    step = next(s for s in workflow["jobs"]["data-box"]["steps"] if "run" in s)
    assert "github.event" not in step["run"] and step["env"]["PR_BODY"]


# ---- issue forms -------------------------------------------------------------------------------
FORMS = sorted((ROOT / ".github" / "ISSUE_TEMPLATE").glob("*.yml"))


def test_issue_forms_exist_and_blank_issues_are_off() -> None:
    names = {p.name for p in FORMS}
    assert {"bug_report.yml", "feature_request.yml", "config.yml"} <= names
    assert (
        _load(ROOT / ".github" / "ISSUE_TEMPLATE" / "config.yml")["blank_issues_enabled"] is False
    )


@pytest.mark.parametrize("path", [p for p in FORMS if p.name != "config.yml"], ids=lambda p: p.name)
def test_every_issue_form_has_the_required_data_box(path: Path) -> None:
    form = _load(path)
    boxes = [b for b in form["body"] if b.get("id") == "no-confidential-data"]
    assert len(boxes) == 1
    option = boxes[0]["attributes"]["options"][0]
    assert option["label"] == STATEMENT and option["required"] is True


# ---- people files ------------------------------------------------------------------------------
def test_code_owners_name_the_owner_for_everything() -> None:
    lines = [
        line
        for line in (ROOT / ".github" / "CODEOWNERS").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    assert lines == ["* @0h3xn4"]


def test_the_code_of_conduct_is_filled_in_and_names_no_private_address() -> None:
    text = (ROOT / "CODE_OF_CONDUCT.md").read_text(encoding="utf-8")
    assert "Contributor Covenant 3.0" in text and "CC-BY-SA-4.0" in text
    assert "[NOTE" not in text  # no placeholder of the template is left
    assert "Report a vulnerability" in text
    assert "@" not in text.replace("@0h3xn4", "")  # no e-mail address
    assert (ROOT / "LICENSES" / "CC-BY-SA-4.0.txt").is_file()


def test_the_readme_and_contributing_ask_for_no_confidential_data() -> None:
    for name in ("README.md", "CONTRIBUTING.md"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert "export-controlled" in text and "edit or delete" in text, name
    assert "CODE_OF_CONDUCT.md" in (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")


# ---- the examples are invented -----------------------------------------------------------------
def test_example_orbits_and_stations_are_marked_invented_and_have_no_tle() -> None:
    files = sorted((ROOT / "examples").rglob("*.yaml"))
    assert len(files) > 50
    for path in files:
        data = _load(path)
        if not isinstance(data, dict):
            continue
        assert "tle" not in data, f"{path}: a TLE in an example"
        if data.get("kind") in {"orbit", "ground_station", "target"}:
            star = (data.get("provenance") or {}).get("*") or {}
            assert star.get("status") == "illustrative", path
            assert "nvented" in str(star.get("source")), path


def test_the_examples_readme_says_the_data_is_invented_and_not_export_controlled() -> None:
    text = (ROOT / "examples" / "README.md").read_text(encoding="utf-8")
    assert "export control" in text.lower() and "Invented data" in text
