"""What a computed result belongs to, so a tab never shows or exports numbers for other inputs.

Every result tab remembers the `ResultKey` it computed for (project revision, scenario, options
such as the demand basis) and compares it with the key of the inputs it holds now. When they
differ the result is stale: the tab says so and its export is off (decision D-104).
"""

from __future__ import annotations

from dataclasses import dataclass

STALE_TEXT = "The project or a setting changed since the last computation. Press Compute."
NOT_COMPUTED_TEXT = "Not computed yet. Press Compute."
CHANGED_WHILE_RUNNING_TEXT = "The project or a setting changed while this ran. Press Compute again."


@dataclass(frozen=True)
class ResultKey:
    revision: int  # counts project (re)loads; a new load is a new revision
    scenario: str
    options: tuple[str, ...] = ()
