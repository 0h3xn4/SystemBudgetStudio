"""The in-place YAML patch the GUI editors save with (GUI-17, GUI-21): comments, key order,
untouched values, BOM, CRLF, links and permissions stay; a save without an edit writes nothing."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import pytest

from budget_core.io.project_loader import model_to_data
from budget_core.io.roundtrip import (
    file_stamp,
    has_comments,
    patch_yaml_text,
    plan_save,
    save_edited_data,
    split_text,
)
from budget_core.io.yamlio import load_yaml_text
from budget_core.model import Unit

UNIT = """\
# Camera payload. Sources: vendor datasheet rev C.
schema_version: 2
kind: unit
name: Camera payload   # as in the ICD
subsystem: Payload
mass_kg: 0.4
bus: main
maturity: class_b
modes:
  # standby draw measured on the bench
  - name: off
    avg_power_w: 0.0
    peak_power_w: 0.0
    duty_cycle_ratio: 1.0
    heat_dissipation_ratio: 1.0
  - name: imaging   # datasheet table 4
    avg_power_w: 2.4
    peak_power_w: 3.1
    duty_cycle_ratio: 1.0
    heat_dissipation_ratio: 0.9
  - name: idle
    avg_power_w: 0.3
    peak_power_w: 0.4
    duty_cycle_ratio: 1.0
"""


def data_of(text: str) -> dict[str, Any]:
    return model_to_data(Unit.model_validate(load_yaml_text(text).data))


def check(data: Any) -> dict[str, Any]:
    return model_to_data(Unit.model_validate(data))


def edited(text: str, change) -> tuple[str, dict[str, Any], dict[str, Any]]:  # type: ignore[no-untyped-def]
    old = data_of(text)
    new = data_of(text)
    change(new)
    return patch_yaml_text(text, old, new), old, new


def test_no_change_gives_the_same_text() -> None:
    assert patch_yaml_text(UNIT, data_of(UNIT), data_of(UNIT)) == UNIT


def test_a_changed_value_keeps_comments_order_and_the_other_values() -> None:
    def change(d: dict[str, Any]) -> None:
        d["modes"][1]["avg_power_w"] = 2.5

    text, _old, new = edited(UNIT, change)
    assert text == UNIT.replace("avg_power_w: 2.4", "avg_power_w: 2.5")
    assert data_of(text) == new


def test_a_removed_row_takes_its_comment_and_keeps_the_others() -> None:
    def change(d: dict[str, Any]) -> None:
        del d["modes"][0]

    text, _old, new = edited(UNIT, change)
    assert "# datasheet table 4" in text and "# Camera payload. Sources" in text
    assert "name: off" not in text and "heat_dissipation_ratio: 0.9" in text
    assert data_of(text) == new


def test_an_added_row_and_a_new_key_are_inserted_in_place() -> None:
    def change(d: dict[str, Any]) -> None:
        d["modes"].insert(
            2, {"name": "new", "avg_power_w": 1.0, "peak_power_w": 1.5, "duty_cycle_ratio": 1.0}
        )
        d["modes"][2]["min_duration_s"] = 5.0

    text, _old, new = edited(UNIT, change)
    assert text.index("name: imaging") < text.index("name: new") < text.index("name: idle")
    assert "# datasheet table 4" in text
    assert data_of(text) == new


def test_hidden_and_unknown_keys_that_are_not_edited_stay() -> None:
    text = UNIT.replace("bus: main", "bus: main\nfuture_key: 5")
    old = data_of(UNIT)
    new = data_of(UNIT)
    new["name"] = "Camera 2"
    patched = patch_yaml_text(text, old, new)
    assert "future_key: 5" in patched and "name: Camera 2" in patched
    assert "# as in the ICD" in patched


def test_a_file_that_uses_other_indentation_keeps_it() -> None:
    text = UNIT.replace("  - name", "- name").replace("    avg", "  avg")
    text = (
        text.replace("    peak", "  peak")
        .replace("    duty", "  duty")
        .replace("    heat", "  heat")
    )
    old = data_of(text)
    new = data_of(text)
    new["modes"][2]["avg_power_w"] = 0.35
    patched = patch_yaml_text(text, old, new)
    assert patched == text.replace("avg_power_w: 0.3\n", "avg_power_w: 0.35\n")


def test_save_without_an_edit_writes_nothing(tmp_path: Path) -> None:
    path = tmp_path / "u.yaml"
    path.write_bytes(UNIT.encode())
    before = path.stat().st_mtime_ns
    result = save_edited_data(path, data_of(UNIT), data_of(UNIT), check)
    assert not result.changed and not result.canonical
    assert path.read_bytes() == UNIT.encode() and path.stat().st_mtime_ns == before


def test_save_keeps_bom_and_crlf(tmp_path: Path) -> None:
    path = tmp_path / "u.yaml"
    path.write_bytes(b"\xef\xbb\xbf" + UNIT.replace("\n", "\r\n").encode())
    new = data_of(UNIT)
    new["mass_kg"] = 0.5
    result = save_edited_data(path, data_of(UNIT), new, check)
    assert result.changed and not result.canonical
    raw = path.read_bytes()
    assert (
        raw.startswith(b"\xef\xbb\xbf")
        and b"\r\n" in raw
        and b"\n" not in raw.replace(b"\r\n", b"")
    )
    text, bom, crlf = split_text(raw)
    assert bom and crlf and "mass_kg: 0.5" in text and "# as in the ICD" in text


def test_a_file_the_patch_cannot_follow_is_rewritten_whole_but_correctly(tmp_path: Path) -> None:
    path = tmp_path / "u.yaml"
    path.write_text("schema_version: 2\nkind: unit\n", encoding="utf-8")  # not what 'old' says
    new = data_of(UNIT)
    result = save_edited_data(path, data_of(UNIT), new, check)
    assert result.changed and result.canonical
    assert data_of(path.read_text(encoding="utf-8")) == new


def test_a_symbolic_link_stays_a_link_and_the_mode_is_kept(tmp_path: Path) -> None:
    real = tmp_path / "real.yaml"
    real.write_bytes(UNIT.encode())
    real.chmod(0o600)
    link = tmp_path / "u.yaml"
    try:
        link.symlink_to(real)
    except OSError:
        pytest.skip("no symbolic links here")
    new = data_of(UNIT)
    new["mass_kg"] = 0.9
    save_edited_data(link, data_of(UNIT), new, check)
    assert link.is_symlink() and "mass_kg: 0.9" in real.read_text(encoding="utf-8")
    if sys.platform != "win32":
        assert real.stat().st_mode & 0o777 == 0o600


def test_file_stamp_changes_with_the_bytes(tmp_path: Path) -> None:
    path = tmp_path / "x"
    assert file_stamp(path) is None
    path.write_bytes(b"a")
    first = file_stamp(path)
    path.write_bytes(b"b")
    assert first is not None and file_stamp(path) not in (None, first)
    assert os.path.exists(path)


def test_a_plan_says_an_edit_in_place_keeps_the_comments(tmp_path: Path) -> None:
    path = tmp_path / "u.yaml"
    path.write_bytes(UNIT.encode())
    new = data_of(UNIT)
    new["mass_kg"] = 0.5
    plan = plan_save(path, data_of(UNIT), new, check)
    assert plan.changed and not plan.canonical and not plan.drops_comments
    assert path.read_bytes() == UNIT.encode()  # planning writes nothing


def test_a_plan_warns_when_the_rewrite_would_drop_comments(tmp_path: Path) -> None:
    path = tmp_path / "u.yaml"
    text = "# the vendor says so\nschema_version: 2\nkind: unit\n"
    path.write_text(text, encoding="utf-8")  # not what 'old' says: the patch cannot follow
    new = data_of(UNIT)
    plan = plan_save(path, data_of(UNIT), new, check)
    assert plan.changed and plan.canonical and plan.drops_comments
    assert path.read_text(encoding="utf-8") == text
    result = save_edited_data(path, data_of(UNIT), new, check)
    assert result.canonical and result.dropped_comments
    assert "# the vendor says so" not in path.read_text(encoding="utf-8")


def test_a_rewrite_of_a_file_without_comments_loses_nothing(tmp_path: Path) -> None:
    path = tmp_path / "u.yaml"
    path.write_text("schema_version: 2\nkind: unit\n", encoding="utf-8")
    plan = plan_save(path, data_of(UNIT), data_of(UNIT), check)
    assert plan.canonical and not plan.drops_comments


def test_has_comments_reads_the_yaml_not_the_characters() -> None:
    assert has_comments("a: 1  # why\n")
    assert has_comments("# top\na: 1\n")
    assert has_comments("a:\n  - 1\n  # between\n  - 2\n")
    assert not has_comments('a: "Table #3 of the sheet"\n')
    assert not has_comments("a: 1\nb: [2, 3]\n")
    assert not has_comments("a: [unclosed\n")  # unreadable: nothing to keep
