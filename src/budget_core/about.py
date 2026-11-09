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

from budget_core import APP_NAME, __version__

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
            THIRD_PARTY_STATEMENT.replace("`", ""),
        )
    )
