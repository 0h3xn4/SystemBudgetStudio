"""Audit (small item): applying a unit-table import must not re-indent a file that is not 2/4/2."""

from __future__ import annotations

import pytest

from budget_core.io.unit_table import _detect_indent, _edited_text

BODY = "      avg_power_w: 1.0\n      peak_power_w: 2.0\n"
STYLES = {
    "canonical": (
        "schema_version: 2\nkind: unit\nname: X\nmodes:\n  - name: a\n    avg_power_w: 1.0\n"
        "    peak_power_w: 2.0\n  - name: b\n    avg_power_w: 1.0\n    peak_power_w: 2.0\n",
        (2, 4, 2),
    ),
    "dash_at_the_key": (
        "name: X\nmodes:\n- name: a\n  avg_power_w: 1.0\n  peak_power_w: 2.0\n",
        (2, 2, 0),
    ),
    "four_spaces": (
        "name: X\nmodes:\n    - name: a\n      avg_power_w: 1.0\n      peak_power_w: 2.0\n"
        "    - name: b\n      avg_power_w: 1.0\n      peak_power_w: 2.0\n",
        (2, 6, 4),  # no nested mapping: the mapping indent is not visible
    ),
    "comments_kept": (
        "# unit file\nname: X  # name\nmodes:\n  # first mode\n  - name: a\n    avg_power_w: 1.0\n"
        "    peak_power_w: 2.0\n",
        (2, 4, 2),
    ),
}


@pytest.mark.parametrize("style", sorted(STYLES))
def test_the_indent_is_detected_and_an_edit_free_round_trip_is_identical(style: str) -> None:
    text, expected = STYLES[style]
    assert _detect_indent(text) == expected
    assert _edited_text(text, []) == text


def test_an_ordinary_edit_changes_only_the_edited_line() -> None:
    from budget_core.io.unit_table import _Edit

    text, _ = STYLES["four_spaces"]
    new = _edited_text(text, [_Edit("x", "a", {"avg_power_w": 1.5}, False)])
    assert new == text.replace("avg_power_w: 1.0", "avg_power_w: 1.5", 1)
