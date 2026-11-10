# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""The Developer Certificate of Origin check (packaging/dco_check.py)."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("dco_check", ROOT / "packaging/dco_check.py")
assert spec is not None and spec.loader is not None
dco = importlib.util.module_from_spec(spec)
sys.modules["dco_check"] = dco
spec.loader.exec_module(dco)


def run(repo: Path, *args: str, date: str = "2026-11-10T09:00:00+00:00") -> str:
    env = {
        "GIT_AUTHOR_NAME": "A", "GIT_AUTHOR_EMAIL": "a@example.org",
        "GIT_COMMITTER_NAME": "A", "GIT_COMMITTER_EMAIL": "a@example.org",
        "GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date,
        "PATH": "/usr/bin:/bin:/usr/local/bin",
    }  # fmt: skip
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True, env=env
    ).stdout.strip()


def commit(repo: Path, name: str, message: str, date: str = "2026-11-10T09:00:00+00:00") -> str:
    (repo / name).write_text(name)
    run(repo, "add", name)
    run(repo, "commit", "-q", "-m", message, date=date)
    return run(repo, "rev-parse", "HEAD")


def test_unsigned_commits_are_reported_and_signed_ones_pass(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    run(tmp_path, "init", "-q")
    base = commit(tmp_path, "a", "base")
    commit(tmp_path, "b", "signed\n\nSigned-off-by: A <a@example.org>")
    bad = commit(tmp_path, "c", "unsigned")
    commit(tmp_path, "d", "wrong form\n\nSigned-off-by: nobody")
    monkeypatch.chdir(tmp_path)
    missing = dco.unsigned_commits(base, "HEAD")
    assert len(missing) == 2 and missing[1].startswith(bad[:10])
    assert dco.unsigned_commits(base, bad) == [missing[1]]


def test_commits_before_the_check_was_introduced_are_not_asked(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    run(tmp_path, "init", "-q")
    base = commit(tmp_path, "a", "base", date="2026-11-01T09:00:00+00:00")
    commit(tmp_path, "b", "old unsigned", date="2026-11-02T09:00:00+00:00")
    monkeypatch.chdir(tmp_path)
    assert dco.unsigned_commits(base, "HEAD") == []


def test_merge_commits_are_not_asked(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    run(tmp_path, "init", "-q", "-b", "main")
    base = commit(tmp_path, "a", "base")
    run(tmp_path, "checkout", "-q", "-b", "side")
    commit(tmp_path, "b", "side\n\nSigned-off-by: A <a@example.org>")
    run(tmp_path, "checkout", "-q", "main")
    commit(tmp_path, "c", "main\n\nSigned-off-by: A <a@example.org>")
    run(tmp_path, "merge", "-q", "--no-ff", "side", "-m", "Merge side")
    monkeypatch.chdir(tmp_path)
    assert dco.unsigned_commits(base, "HEAD") == []


def test_only_the_dependabot_address_is_exempt(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    run(tmp_path, "init", "-q")
    base = commit(tmp_path, "a", "base")
    (tmp_path / "b").write_text("b")
    run(tmp_path, "add", "b")
    run(
        tmp_path,
        "commit",
        "-q",
        "-m",
        "Bump a from 1 to 2",
        "--author",
        "dependabot[bot] <49699333+dependabot[bot]@users.noreply.github.com>",
    )
    monkeypatch.chdir(tmp_path)
    assert dco.unsigned_commits(base, "HEAD") == []
    (tmp_path / "c").write_text("c")
    run(tmp_path, "add", "c")
    run(
        tmp_path,
        "commit",
        "-q",
        "-m",
        "Pretends to be a bot",
        "--author",
        "dependabot[bot] <someone@example.org>",
    )
    assert len(dco.unsigned_commits(base, "HEAD")) == 1
