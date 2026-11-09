# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""Opening the archive and parsing its XML are bounded and safe (D-237)."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from budget_core.idm import archive, xmltree
from budget_core.idm.reader import read_idm
from tests.idm.fixtures import model_xml, write_idm


def codes(path: Path) -> list[str]:
    return [p.code for p in read_idm(path).problems]


def test_a_missing_file(tmp_path: Path) -> None:
    assert codes(tmp_path / "none.idm") == ["IDM_FILE_UNREADABLE"]


def test_not_a_zip(tmp_path: Path) -> None:
    path = tmp_path / "x.idm"
    path.write_bytes(b"this is not an archive")
    assert codes(path) == ["IDM_FILE_UNREADABLE"]


def test_no_model_entry(tmp_path: Path) -> None:
    path = write_idm(tmp_path / "x.idm", model_name=None, extra={"notes.txt": b"hello"})
    assert codes(path) == ["IDM_MODEL_MISSING"]


def test_the_model_must_be_at_the_root(tmp_path: Path) -> None:
    path = write_idm(tmp_path / "x.idm", model_name="folder/model.xml")
    assert codes(path) == ["IDM_MODEL_MISSING"]


def test_two_model_entries_are_ambiguous(tmp_path: Path) -> None:
    path = tmp_path / "x.idm"
    with zipfile.ZipFile(path, "w") as z, pytest.warns(UserWarning):  # zipfile warns, too
        z.writestr("model.xml", b"<IDM />")
        z.writestr("model.xml", b"<IDM />")
    assert codes(path) == ["IDM_FILE_UNREADABLE"]


def test_other_entries_are_ignored_even_with_odd_names(tmp_path: Path) -> None:
    extra = {
        "../outside.txt": b"x",
        "managedData\\data.xml": b"<broken",
        "idmFiles/": b"",
        "idmFiles/picture.jpg": b"\xff\xd8",
    }
    read = read_idm(write_idm(tmp_path / "x.idm", extra=extra))
    assert read.ok
    assert not list(tmp_path.glob("**/outside.txt"))
    assert [p.name for p in tmp_path.iterdir()] == ["x.idm"]  # nothing was extracted


def test_a_byte_order_mark_and_crlf_are_fine(tmp_path: Path) -> None:
    assert read_idm(write_idm(tmp_path / "a.idm", bom=True)).ok
    assert read_idm(write_idm(tmp_path / "b.idm", bom=False)).ok


def test_the_file_size_is_bounded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = write_idm(tmp_path / "x.idm")
    monkeypatch.setattr(archive, "MAX_IDM_FILE_BYTES", 100)
    assert codes(path) == ["IDM_ARCHIVE_LIMIT"]


def test_the_unpacked_model_is_bounded_by_what_is_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = write_idm(tmp_path / "x.idm")
    monkeypatch.setattr(archive, "MAX_MODEL_XML_BYTES", 500)
    assert codes(path) == ["IDM_ARCHIVE_LIMIT"]


def test_too_many_entries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = write_idm(tmp_path / "x.idm", extra={f"idmFiles/{i}.txt": b"x" for i in range(5)})
    monkeypatch.setattr(archive, "MAX_ZIP_ENTRIES", 3)
    assert codes(path) == ["IDM_ARCHIVE_LIMIT"]


@pytest.mark.parametrize(
    "xml",
    [
        b"<IDM><IdmData",
        b"",
        b"not xml at all",
        b"\xff\xfe<\x00I\x00D\x00M\x00/\x00>\x00",
    ],
)
def test_malformed_xml(tmp_path: Path, xml: bytes) -> None:
    assert codes(write_idm(tmp_path / "x.idm", xml, bom=False)) == ["IDM_XML_INVALID"]


@pytest.mark.parametrize(
    "xml",
    [
        b'<!DOCTYPE IDM [<!ENTITY a "x">]><IDM />',
        b'<!DOCTYPE IDM SYSTEM "file:///etc/passwd"><IDM />',
        b'<IDM>&a;<!ENTITY a "x"></IDM>',
    ],
)
def test_document_types_and_entities_are_refused(tmp_path: Path, xml: bytes) -> None:
    assert codes(write_idm(tmp_path / "x.idm", xml, bom=False)) == ["IDM_XML_UNSAFE"]


def test_nesting_and_size_of_the_xml_are_bounded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    deep = b"<IDM>" + b"<a>" * 50 + b"</a>" * 50 + b"</IDM>"
    path = write_idm(tmp_path / "x.idm", deep, bom=False)
    monkeypatch.setattr(xmltree, "MAX_XML_DEPTH", 20)
    assert codes(path) == ["IDM_ARCHIVE_LIMIT"]
    monkeypatch.setattr(xmltree, "MAX_XML_DEPTH", 200)
    monkeypatch.setattr(xmltree, "MAX_XML_NODES", 10)
    assert codes(path) == ["IDM_ARCHIVE_LIMIT"]


def test_other_xml_is_not_a_model(tmp_path: Path) -> None:
    assert codes(write_idm(tmp_path / "x.idm", b"<other />", bom=False)) == [
        "IDM_STRUCTURE_INVALID"
    ]
    assert codes(write_idm(tmp_path / "y.idm", b"<IDM><IdmData /></IDM>", bom=False)) == [
        "IDM_STRUCTURE_INVALID"
    ]


def test_a_newer_minor_version_is_read_with_a_warning(tmp_path: Path) -> None:
    read = read_idm(write_idm(tmp_path / "x.idm", model_xml(version="3.5.0.32")))
    assert read.ok
    assert [p.code for p in read.problems] == ["IDM_VERSION_NEWER"]
    assert [
        p.code
        for p in read_idm(write_idm(tmp_path / "y.idm", model_xml(version="3.4.9.1"))).problems
    ] == []


def test_the_same_input_gives_the_same_model_and_revision(tmp_path: Path) -> None:
    a = read_idm(write_idm(tmp_path / "a.idm"))
    b = read_idm(write_idm(tmp_path / "b.idm"))
    assert a.model is not None and b.model is not None
    assert a.model.sha256 == b.model.sha256
    assert (tmp_path / "a.idm").read_bytes() == (tmp_path / "b.idm").read_bytes()
    assert a.model.occurrences == b.model.occurrences
    assert a.model.equipment == b.model.equipment
    changed = read_idm(write_idm(tmp_path / "c.idm", model_xml(margin_text="0,6")))
    assert changed.model is not None and changed.model.sha256 != a.model.sha256
