# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""The words of Help > About: one source for the licence and the ownership statement.

The README, the window and the tests read these constants, so a copy that drifts fails a test
(`tests/unit/test_licence_statements.py`). The disclaimer, the statement on how the software is
made and the privacy statement are added to this module in a later step of the protection
programme; they will be generated from here in the same way.
"""

from __future__ import annotations

import sys
from pathlib import Path

from budget_core import APP_NAME, __version__
from budget_core.disclaimer import DISCLAIMER

COPYRIGHT_LINE = "Copyright 2026 0h3xn4"
PROJECT_LICENCE_SPDX = "Apache-2.0"
PROJECT_LICENCE_NAME = "Apache License, Version 2.0"
LAST_MIT_RELEASE = "2.11.2"

OWNERSHIP_STATEMENT = (
    "System Budget Studio is a personal project. It is not affiliated with, sponsored by or "
    "endorsed by any employer or organisation."
)
LICENCE_STATEMENT = (
    f"Licensed under the {PROJECT_LICENCE_NAME} (SPDX: {PROJECT_LICENCE_SPDX}). Releases up to and "
    f"including {LAST_MIT_RELEASE} were published under the MIT licence."
)
THIRD_PARTY_STATEMENT = (
    "The program folder contains the licence texts of the bundled libraries in `licences/` and "
    "the list `licences.md`."
)


def about_text() -> str:
    """The paragraphs of the About dialog, one per line."""
    return "\n\n".join(
        (
            f"{APP_NAME} {__version__}",
            COPYRIGHT_LINE,
            OWNERSHIP_STATEMENT,
            LICENCE_STATEMENT,
            DISCLAIMER,
            AI_AUTHORSHIP,
            SUPPORT_STATEMENT,
            NON_COMMERCIAL,
            PRIVACY_STATEMENT,
            THIRD_PARTY_STATEMENT.replace("`", ""),
        )
    )


AI_AUTHORSHIP = (
    "Most of the code and the documentation of System Budget Studio were written by Claude Code, "
    "an AI system made by Anthropic, under the direction of the owner. The owner set the "
    "requirements and the design decisions and reviewed the results. The equations are checked "
    "against hand calculations, not against a flight project. There has been no independent review."
)
SUPPORT_STATEMENT = (
    "System Budget Studio is maintained by one person in their free time. Maintenance status: "
    "active, best effort. There is no guaranteed support, maintenance, fixes or response time."
)
NON_COMMERCIAL = (
    "System Budget Studio is non-commercial: it has no sales, paid features, paid support, "
    "advertising, donations or sponsorship."
)
PRIVACY_STATEMENT = (
    "The program collects nothing and sends nothing; it never uses the network. It keeps one small "
    "file on your computer, the window layout (position, size, theme, and the name you may type "
    "for report files), and a list of your recent project folders only if you switch that list "
    "on in the settings (it is off by default). The files it exports name a user (never your "
    "account name: it is "
    '"unknown" unless you set a name), the tool and library versions, the project name and '
    "revision, the relative paths and hashes of the project files it read, and the time."
)

NOTICES_FILE = "THIRD_PARTY_NOTICES.txt"
NOT_INSTALLED_TEXT = (
    "This copy of the program was not started from an installer, so the file "
    f"{NOTICES_FILE} is not next to it. The installers carry it in the program folder. "
    "In the source repository the licences of the libraries are listed in docs/LICENCES.md, "
    "and the licences of the fonts and icons are in assets/fonts and assets/icons/ui."
)


def notices_path() -> Path | None:
    """The third-party notices file next to the program of an installed copy, if there is one."""
    if not getattr(sys, "frozen", False):
        return None
    path = Path(sys.executable).resolve().parent / NOTICES_FILE
    return path if path.is_file() else None


def third_party_text() -> str:
    """The text of Help > Third-party licences."""
    path = notices_path()
    if path is None:
        return NOT_INSTALLED_TEXT
    return path.read_text(encoding="utf-8", errors="replace")
