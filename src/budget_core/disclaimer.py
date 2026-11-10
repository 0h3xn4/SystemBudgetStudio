# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""The disclaimer: one text, kept here and nowhere else.

The README, the window (first screen and Help > About), the user guide, the provenance of every
report and export, and the website all show this text. `scripts/sync_disclaimer.py` writes it into
the files that hold a copy (the README and the user guide); a test
(`tests/unit/test_disclaimer.py`) fails when any copy differs from it. Change the words here.
"""

from __future__ import annotations

ITEMS = (
    "The results are engineering estimates.",
    "They depend entirely on the inputs and the sources you enter.",
    "The software comes with no warranty (see the Apache License 2.0, sections 7 and 8).",
    "It is not certified or qualified for any mission, flight or safety use.",
    "It does not replace independent verification and review.",
    "You are responsible for decisions based on it.",
)
DISCLAIMER = " ".join(ITEMS)

# The README holds the text between these two lines.
START_MARK = "<!-- disclaimer:start -->"
END_MARK = "<!-- disclaimer:end -->"


def readme_block() -> str:
    """What stands in the README, markers included."""
    return f"{START_MARK}\n{DISCLAIMER}\n{END_MARK}"
