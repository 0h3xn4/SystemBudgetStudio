"""What the views say while a computation runs, is stopped, or has been stopped (D-167)."""

from __future__ import annotations

COMPUTE_TEXT = "Compute"
CANCEL_TEXT = "Cancel"
CANCELLING_TEXT = "Cancelling… the current step finishes first."
CANCEL_TIP = "Stop this computation. The results shown now stay as they are."


def computing_text(stage: str) -> str:
    return f"Computing… {stage}" if stage else "Computing…"


def cancelled_text(has_results: bool) -> str:
    return "Cancelled. The results shown are from before." if has_results else "Cancelled."
