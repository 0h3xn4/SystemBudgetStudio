# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""One disclaimer, one source: every copy equals it (protection programme, phase 5, D-262)."""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

from budget_core import about, disclaimer
from budget_core.model import ProjectMeta  # noqa: F401  (the provenance needs a project)
from budget_core.provenance import Provenance

ROOT = Path(__file__).resolve().parents[2]
CHAPTER = ROOT / "src" / "budget_core" / "guide" / "chapters" / "01-introduction.md"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_the_disclaimer_says_what_the_brief_asks() -> None:
    text = disclaimer.DISCLAIMER.lower()
    for phrase in (
        "engineering estimates",
        "depend entirely on the inputs and the sources you enter",
        "no warranty",
        "not certified or qualified for any mission, flight or safety use",
        "does not replace independent verification and review",
        "you are responsible for decisions",
    ):
        assert phrase in text, phrase


def test_the_readme_holds_exactly_the_disclaimer() -> None:
    assert disclaimer.readme_block() in read(ROOT / "README.md")


def test_the_user_guide_holds_exactly_the_disclaimer_and_the_privacy_statement() -> None:
    text = read(CHAPTER)
    assert f"## Limits and responsibility\n\n{disclaimer.DISCLAIMER}\n" in text
    assert f"## What the program stores and sends\n\n{about.PRIVACY_STATEMENT}\n" in text


def test_the_sync_script_finds_every_copy_in_step() -> None:
    done = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "sync_disclaimer.py"), "--check"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stdout + done.stderr


def test_the_about_text_holds_the_statements() -> None:
    text = about.about_text()
    for statement in (
        disclaimer.DISCLAIMER,
        about.AI_AUTHORSHIP,
        about.SUPPORT_STATEMENT,
        about.NON_COMMERCIAL,
        about.PRIVACY_STATEMENT,
    ):
        assert statement in text


def test_the_readme_holds_the_statements_of_the_about_dialog() -> None:
    readme = " ".join(read(ROOT / "README.md").split())
    for statement in (
        about.AI_AUTHORSHIP,
        about.SUPPORT_STATEMENT,
        about.NON_COMMERCIAL,
        about.PRIVACY_STATEMENT,
    ):
        assert " ".join(statement.split()) in readme, statement[:60]


def test_the_ai_authorship_is_honest_and_claims_nothing_about_copyright() -> None:
    text = about.AI_AUTHORSHIP.lower()
    assert "claude code" in text and "anthropic" in text and "owner" in text
    assert "hand calculations" in text and "no independent review" in text
    assert "copyright" not in text and "protected" not in text


def test_every_provenance_carries_the_disclaimer() -> None:
    provenance = Provenance(
        tool="t",
        tool_version="1",
        python_version="3",
        libraries=(),
        project_name="p",
        project_revision="1",
        scenario="s",
        generated="2026-01-02T03:04:05Z",
        user="u",
    )
    assert ("Disclaimer", disclaimer.DISCLAIMER) in provenance.rows()
    assert asdict(provenance)["disclaimer"] == disclaimer.DISCLAIMER


# ---- words that read as a promise (phase 5, step 4) ------------------------------------------
PROMISE = re.compile(
    r"\b(guarantee[sd]?|defend|reliable|validated|proven|you can trust|can rely on|accurate)\b",
    re.IGNORECASE,
)
PAGES = [
    ROOT / "README.md",
    ROOT / "CONTRIBUTING.md",
    ROOT / "docs" / "getting-started.md",
    ROOT / "docs" / "faq.md",
    ROOT / "docs" / "tips.md",
    ROOT / "docs" / "security-and-privacy.md",
    *sorted((ROOT / "docs" / "user-manual").glob("*.md")),
    *sorted((ROOT / "src" / "budget_core" / "guide" / "chapters").glob("*.md")),
]


@pytest.mark.parametrize("page", PAGES, ids=lambda p: str(p.relative_to(ROOT)))
def test_no_promise_wording_in_the_public_pages(page: Path) -> None:
    text = read(page).replace(disclaimer.DISCLAIMER, "").replace(about.SUPPORT_STATEMENT, "")
    assert not PROMISE.findall(text), PROMISE.findall(text)


def test_the_window_texts_hold_no_promise_wording() -> None:
    for path in sorted((ROOT / "src" / "budget_gui").glob("*.py")):
        assert not PROMISE.findall(read(path)), (path.name, PROMISE.findall(read(path)))
