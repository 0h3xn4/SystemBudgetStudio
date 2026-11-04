"""IDM-CIC and CNES material never enters the repository (decision D-237).

The programme and its documentation are CNES's, and this repository is public. These tests keep
the rules that were set for that: no model file outside the folder for synthetic fixtures, no
document of CNES, a credit that does not suggest an endorsement, and nothing in the importer that
calls CNES software.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = "tests/fixtures/idm/"


def tracked_files() -> list[str]:
    git = shutil.which("git")
    if git is None or not (ROOT / ".git").exists():
        pytest.skip("not a git checkout")
    out = subprocess.run(
        [git, "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True
    ).stdout.decode()
    return [name for name in out.split("\0") if name]


def test_no_model_file_is_tracked_outside_the_fixture_folder() -> None:
    bad = [f for f in tracked_files() if f.lower().endswith(".idm") and not f.startswith(FIXTURES)]
    assert bad == []


def test_gitignore_refuses_model_files_except_the_fixture_folder() -> None:
    lines = (ROOT / ".gitignore").read_text().splitlines()
    assert "*.idm" in lines
    assert "!tests/fixtures/idm/*.idm" in lines


def test_no_tracked_file_is_a_cnes_document_or_program() -> None:
    forbidden_suffixes = (".idm", ".dll", ".msi", ".nupkg")
    names = [
        f
        for f in tracked_files()
        if f.lower().endswith(forbidden_suffixes) and not f.startswith(FIXTURES)
    ]
    assert names == []
    for name in tracked_files():
        lowered = name.lower()
        assert not (lowered.endswith(".pdf") and ("idm" in lowered or "cnes" in lowered)), name


def test_the_importer_uses_no_cnes_software() -> None:
    forbidden = ("clr", "pythonnet", "System.Reflection", "IdmApi", "idm_api", "Idm.dll")
    for path in (ROOT / "src" / "budget_core" / "idm").glob("*.py"):
        text = path.read_text()
        for word in forbidden:
            assert word not in text, f"{path.name} mentions {word}"


def test_the_documentation_credits_cnes_and_claims_no_endorsement() -> None:
    page = (ROOT / "docs" / "models" / "idm-import.md").read_text()
    assert "© CNES" in page
    assert "does not endorse" in page
    assert "uses no CNES software" in page
    package = (ROOT / "src" / "budget_core" / "idm" / "__init__.py").read_text()
    assert "(c) CNES" in package
    assert "endorses" in package  # "does not suggest that CNES endorses ..."
