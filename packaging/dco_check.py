#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""Developer Certificate of Origin check: every commit of a pull request is signed off.

    python packaging/dco_check.py <base> <head>

Lists the non-merge commits in `<base>..<head>` and fails (exit 1) when one has no
`Signed-off-by: Name <address>` line (`git commit -s` adds it). Commits made before the check
was introduced (`ENFORCED_FROM`) are not asked for it. The rules are in CONTRIBUTING.md.
Standard library only.
"""

from __future__ import annotations

import re
import subprocess
import sys
from datetime import datetime

# the check was introduced on this date; older commits have no sign-off and are not rewritten
ENFORCED_FROM = datetime.fromisoformat("2026-11-09T16:05:00+00:00")
SIGNED_OFF = re.compile(r"^Signed-off-by: \S.* <[^<>\s]+@[^<>\s]+>\s*$", re.MULTILINE)


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], check=True, capture_output=True, text=True, encoding="utf-8"
    ).stdout


def unsigned_commits(base: str, head: str) -> list[str]:
    """The short ids and subjects of the commits that need a sign-off and have none."""
    missing: list[str] = []
    for sha in git("rev-list", "--no-merges", f"{base}..{head}").split():
        when, _, message = git("show", "-s", "--format=%cI%n%B", sha).partition("\n")
        if datetime.fromisoformat(when.strip()) < ENFORCED_FROM:
            continue
        if not SIGNED_OFF.search(message):
            missing.append(
                f"{sha[:10]} {message.strip().splitlines()[0] if message.strip() else ''}"
            )
    return missing


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2
    missing = unsigned_commits(argv[1], argv[2])
    if not missing:
        print("Every commit is signed off.")
        return 0
    print("These commits have no 'Signed-off-by:' line (use `git commit -s`; see CONTRIBUTING.md):")
    for line in missing:
        print(f"  {line}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
