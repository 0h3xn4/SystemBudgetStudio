#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""The pull request carries the ticked data box (protection programme, phase 7).

    PR_BODY="..." PR_AUTHOR="login" python packaging/pr_body_check.py

Fails (exit 1) unless the text of the pull request has the line of the template ticked:
"- [x] I have not included confidential, proprietary, export-controlled, personal or customer
data." The Dependabot service is exempt, because it writes its own text and makes only version
bumps. The text comes in through the environment, never through the command line, so nothing a
person typed is run by a shell. Standard library only.
"""

from __future__ import annotations

import os
import re
import sys

STATEMENT = (
    "I have not included confidential, proprietary, export-controlled, personal or customer data."
)
TICKED = re.compile(r"^\s*[-*]\s*\[[xX]\]\s*" + re.escape(STATEMENT) + r"\s*$", re.MULTILINE)
EXEMPT = frozenset({"dependabot[bot]"})


def passes(body: str, author: str) -> bool:
    return author in EXEMPT or TICKED.search(body or "") is not None


def main() -> int:
    body = os.environ.get("PR_BODY", "")
    author = os.environ.get("PR_AUTHOR", "")
    if passes(body, author):
        print("The data box is ticked.")
        return 0
    print("The pull request text must contain this line, ticked:")
    print(f"- [x] {STATEMENT}")
    print("Edit the pull request text (the template is .github/PULL_REQUEST_TEMPLATE.md).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
