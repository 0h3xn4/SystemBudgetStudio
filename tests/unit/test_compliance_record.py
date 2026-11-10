# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""The compliance record of a release (packaging/compliance_record.py)."""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "compliance_record", ROOT / "packaging/compliance_record.py"
)
assert spec is not None and spec.loader is not None
record = importlib.util.module_from_spec(spec)
sys.modules["compliance_record"] = record
spec.loader.exec_module(record)


def make(folder: Path) -> None:
    for name, data in {
        "system-budget-studio-1.0.0-setup.exe": b"exe",
        "system-budget-studio-1.0.0-linux-x86_64.tar.gz": b"tar",
        "sbom-linux.cdx.json": b"{}",
        "licences-linux.md": b"l",
        "THIRD_PARTY_NOTICES-linux.txt": b"n",
        "SHA256SUMS-linux.txt": b"s",
        "qtbase-everywhere-src-6.10.3.tar.xz": b"qt",
    }.items():
        (folder / name).write_bytes(data)


def test_every_file_is_listed_with_its_hash(tmp_path: Path) -> None:
    make(tmp_path)
    text = record.render(tmp_path, "v1.0.0", "abc", "42", "o/r")
    assert hashlib.sha256(b"exe").hexdigest() in text
    for name in tmp_path.iterdir():
        assert f"`{name.name}`" in text
    assert "gh attestation verify <file> --owner o" in text
    assert "### Source code of the LGPL parts" in text


def test_a_check_that_did_not_run_is_never_written_as_passed(tmp_path: Path) -> None:
    make(tmp_path)
    assert "REUSE (licence and copyright of every file): **not run**" in record.render(
        tmp_path, "v1.0.0"
    )
    checks = tmp_path / "checks"
    checks.mkdir()
    (checks / "reuse.exit").write_text("0\n")
    (checks / "pip-audit.exit").write_text("1\n")
    text = record.render(tmp_path, "v1.0.0", checks=checks)
    assert "REUSE (licence and copyright of every file): **passed**" in text
    assert "**FAILED (exit code 1)**" in text


def test_the_record_does_not_list_itself(tmp_path: Path) -> None:
    make(tmp_path)
    (tmp_path / "COMPLIANCE-RECORD.md").write_text("old")
    assert "`COMPLIANCE-RECORD.md`" not in record.render(tmp_path, "v1.0.0")


def test_the_command_line_writes_the_file(tmp_path: Path) -> None:
    make(tmp_path)
    out = tmp_path.parent / f"{tmp_path.name}-out.md"
    assert record.main(["x", str(tmp_path), "--tag", "v1.0.0", "--out", str(out)]) == 0
    assert out.read_text(encoding="utf-8").startswith("# Compliance record of v1.0.0")
