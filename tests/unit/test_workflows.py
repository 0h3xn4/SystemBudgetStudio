# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""Rules for the CI workflows (D-263). A workflow that breaks one fails here, before it runs.

1. Every action is pinned to a full 40-character commit id, with the version in a comment.
2. Every workflow sets `permissions:` at the top, and the top-level permission is read-only.
3. A job that can write to the repository's releases or sign files (`contents: write`,
   `attestations: write`, `id-token: write`) runs in the `release` environment, where the owner
   sets a required reviewer. The one exception is the job of `tag-release.yml`, which only
   creates a tag (`contents: write`, nothing that signs) and runs in the `tagging` environment
   (D-272): a tag is what anyone with write access may push, and publishing stays in `release`.
4. No `pull_request_target` (it runs code of a pull request with the rights of the repository).
5. No text that a pull request or a person controls (`github.event.*`, `inputs.*`, `head_ref`) is
   written straight into a shell script (script injection); it goes through `env:`.
6. Dependabot is set up for the actions.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml import YAML

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
PIN = re.compile(r"^[\w.-]+/[\w.-]+(?:/[\w./-]+)?@[0-9a-f]{40}$")
UNTRUSTED = re.compile(
    r"\$\{\{\s*(?:github\.event\.|github\.head_ref|inputs\.|github\.actor|github\.ref_name)"
)
WRITES = ("contents", "attestations", "id-token")


def load(path: Path) -> dict[str, Any]:
    return YAML(typ="safe").load(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def steps_of(workflow: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    return [
        (job_id, step) for job_id, job in workflow["jobs"].items() for step in job.get("steps", [])
    ]


def test_the_workflows_are_found() -> None:
    names = {p.name for p in WORKFLOWS}
    assert {"ci.yml", "release.yml", "audit.yml", "dco.yml", "codeql.yml"} <= names


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_actions_are_pinned_to_a_commit_with_the_version_in_a_comment(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    for number, line in enumerate(lines, start=1):
        match = re.match(r"^\s*-?\s*uses:\s*(\S+)(.*)$", line)
        if not match:
            continue
        action, rest = match.groups()
        if action.startswith("./"):
            continue
        assert PIN.match(action), f"{path.name}:{number} {action} is not pinned to a commit id"
        assert re.search(r"#\s*v\d", rest), f"{path.name}:{number} has no version comment"


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_the_top_level_permissions_are_read_only(path: Path) -> None:
    permissions = load(path).get("permissions")
    assert isinstance(permissions, dict), f"{path.name} has no top-level permissions"
    assert set(permissions.values()) <= {"read", "none"}, permissions


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_jobs_that_write_to_releases_use_the_release_environment(path: Path) -> None:
    for job_id, job in load(path)["jobs"].items():
        permissions = job.get("permissions") or {}
        if any(permissions.get(name) == "write" for name in WRITES):
            if path.name == "tag-release.yml":
                signs = {permissions.get("attestations"), permissions.get("id-token")}
                assert "write" not in signs, f"{path.name}:{job_id} may only create a tag"
                assert job.get("environment") == "tagging", f"{path.name}:{job_id}"
                continue
            assert job.get("environment") == "release", f"{path.name}:{job_id}"


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_no_pull_request_target(path: Path) -> None:
    triggers = load(path).get("on") or load(path).get(True)
    assert "pull_request_target" not in triggers


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_no_untrusted_text_in_a_shell_script(path: Path) -> None:
    for job_id, step in steps_of(load(path)):
        script = step.get("run")
        if isinstance(script, str):
            assert not UNTRUSTED.search(script), f"{path.name}:{job_id} writes it into `run:`"


def test_dependabot_watches_the_actions() -> None:
    config = load(ROOT / ".github" / "dependabot.yml")
    ecosystems = {u["package-ecosystem"] for u in config["updates"]}
    assert {"github-actions", "pip"} <= ecosystems


# ---- the tag workflow (D-272) ----------------------------------------------------------------
TAG = ROOT / ".github" / "workflows" / "tag-release.yml"


def test_the_tag_workflow_runs_only_by_hand_and_only_on_main() -> None:
    workflow = load(TAG)
    triggers = workflow.get("on") or workflow.get(True)
    assert set(triggers) == {"workflow_dispatch"}
    assert triggers["workflow_dispatch"]["inputs"]["version"]["required"] is True
    (job,) = workflow["jobs"].values()
    assert job["if"] == "github.ref == 'refs/heads/main'"
    assert job["permissions"] == {"contents": "write", "actions": "write"}


def test_the_tag_workflow_checks_the_version_before_it_tags() -> None:
    (job,) = load(TAG)["jobs"].values()
    check, create = (step for step in job["steps"] if "run" in step)
    for needed in ("pyproject.toml", "CHANGELOG.md", "git ls-remote --exit-code --tags"):
        assert needed in check["run"]
    assert check["env"]["VERSION"] == "${{ inputs.version }}"  # through env:, never inline
    assert "git/refs" in create["run"] and "gh workflow run release.yml" in create["run"]
    assert '--ref "v$VERSION"' in create["run"]  # the Installers run sees the tag as its ref


def test_the_installers_workflow_can_be_started_on_a_tag() -> None:
    release = load(ROOT / ".github" / "workflows" / "release.yml")
    triggers = release.get("on") or release.get(True)
    assert "workflow_dispatch" in triggers  # what the tag workflow starts
    assert release["jobs"]["publish"]["environment"] == "release"
    assert "refs/tags/" in release["jobs"]["publish"]["if"]  # on the tag, as for a pushed one
