#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""Write the disclaimer of `budget_core/disclaimer.py` into the files that hold a copy.

    python scripts/sync_disclaimer.py            # rewrite the README and the user guide chapter
    python scripts/sync_disclaimer.py --check    # only report a copy that differs (exit 1)

The README holds it between two marker lines; the user guide chapter holds it as the paragraph
after the heading "Limits and responsibility" (and the privacy statement of `budget_core/about.py`
after "What the program stores and sends"). The window, the About dialog and the provenance of the
reports read the modules directly; a test checks the other statements of `about.py` in the README.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from budget_core import about, disclaimer  # noqa: E402

README = ROOT / "README.md"
CHAPTER = ROOT / "src" / "budget_core" / "guide" / "chapters" / "01-introduction.md"
HEADING = "## Limits and responsibility"
PRIVACY_HEADING = "## What the program stores and sends"


def synced_readme(text: str) -> str:
    pattern = re.compile(
        re.escape(disclaimer.START_MARK) + r".*?" + re.escape(disclaimer.END_MARK), re.DOTALL
    )
    if not pattern.search(text):
        raise SystemExit("README.md has no disclaimer markers.")
    return pattern.sub(lambda _m: disclaimer.readme_block(), text, count=1)


def _paragraph_after(text: str, heading: str, body: str) -> str:
    pattern = re.compile(re.escape(heading) + r"\n\n(.*?)(?=\n\n|\Z)", re.DOTALL)
    if not pattern.search(text):
        raise SystemExit(f"{CHAPTER.name} has no heading {heading!r}.")
    return pattern.sub(lambda _m: f"{heading}\n\n{body}", text, count=1)


def synced_chapter(text: str) -> str:
    text = _paragraph_after(text, HEADING, disclaimer.DISCLAIMER)
    return _paragraph_after(text, PRIVACY_HEADING, about.PRIVACY_STATEMENT)


def main(argv: list[str]) -> int:
    check = "--check" in argv
    stale = []
    for path, fn in ((README, synced_readme), (CHAPTER, synced_chapter)):
        old = path.read_text(encoding="utf-8")
        new = fn(old)
        if new != old:
            stale.append(path.name)
            if not check:
                path.write_text(new, encoding="utf-8")
    if stale:
        print(("differs: " if check else "rewrote: ") + ", ".join(stale))
    return 1 if (stale and check) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
