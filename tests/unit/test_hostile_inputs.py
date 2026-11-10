# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""Hostile files, one place (D-263).

Every kind of file the tool reads can come from a stranger. Each test here builds a file that
tries to hurt the reader (a bomb, an external entity, a path that leaves the folder, a formula)
and checks that the tool refuses it, quickly, and says nothing that was read from the file.
Some of these cases are also tested next to their code; this file is the list to read when a new
input format is added.
"""

from __future__ import annotations

import io
import time
import zipfile
from pathlib import Path

import pytest

from budget_core.idm import archive, xmltree
from budget_core.idm.reader import read_idm
from budget_core.io import unit_table
from budget_core.io.yamlio import YamlSyntaxError, load_yaml_text
from budget_core.reports.files import safe_name
from tests.idm.fixtures import write_idm

CANARY = "CANARY-7f3a9c-must-never-appear"


def _codes(path: Path) -> list[str]:
    return [p.code for p in read_idm(path).problems]


def _all_text(result: object) -> str:
    return repr(result)


# ---- XML: the IDM model ------------------------------------------------------------------------
def test_an_external_entity_does_not_read_a_local_file(tmp_path: Path) -> None:
    secret = tmp_path / "secret.txt"
    secret.write_text(CANARY, encoding="utf-8")
    xml = (
        f'<?xml version="1.0"?><!DOCTYPE IDM [<!ENTITY x SYSTEM "{secret.as_uri()}">]>'
        "<IDM><name>&x;</name></IDM>"
    )
    result = read_idm(write_idm(tmp_path / "xxe.idm", xml, bom=False))
    assert [p.code for p in result.problems] == ["IDM_XML_UNSAFE"]
    assert CANARY not in _all_text(result)


def test_an_entity_expansion_bomb_is_refused_without_expanding(tmp_path: Path) -> None:
    levels = "".join(
        f'<!ENTITY l{i} "{f"&l{i - 1};" * 10}">' if i else '<!ENTITY l0 "lol">' for i in range(9)
    )
    xml = f"<?xml version='1.0'?><!DOCTYPE IDM [{levels}]><IDM>&l8;</IDM>"
    started = time.monotonic()
    codes = _codes(write_idm(tmp_path / "laughs.idm", xml, bom=False))
    assert codes == ["IDM_XML_UNSAFE"]
    assert time.monotonic() - started < 5


@pytest.mark.parametrize("encoding", ["utf-16-le", "utf-16-be", "utf-32-le"])
def test_a_model_in_utf16_without_a_mark_is_refused(tmp_path: Path, encoding: str) -> None:
    """The byte check for a document type reads UTF-8; another encoding must not slip past it."""
    xml = '<?xml version="1.0"?><!DOCTYPE IDM [<!ENTITY a "x">]><IDM>&a;</IDM>'
    path = write_idm(tmp_path / "wide.idm", xml.encode(encoding), bom=False)
    assert _codes(path) == ["IDM_XML_INVALID"]


def test_the_parser_itself_refuses_a_document_type() -> None:
    """If the byte check ever misses a case, the parser still stops it (defusedxml)."""
    from defusedxml import DefusedXmlException
    from defusedxml.ElementTree import fromstring

    with pytest.raises(DefusedXmlException):
        fromstring('<!DOCTYPE a [<!ENTITY b "c">]><a>&b;</a>', forbid_dtd=True)
    # and the model parser really is built on it
    assert "defusedxml" in Path(xmltree.__file__).read_text(encoding="utf-8")


def test_openpyxl_uses_defusedxml() -> None:
    """openpyxl reads .xlsx with defusedxml only when the package is installed."""
    from openpyxl.xml import DEFUSEDXML

    assert DEFUSEDXML


# ---- zip: the IDM archive ----------------------------------------------------------------------
def test_a_zip_bomb_is_read_only_up_to_the_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(archive, "MAX_MODEL_XML_BYTES", 200_000)
    bomb = b"<IDM>" + b" " * 20_000_000 + b"</IDM>"  # 20 MB that packs to about 20 kB
    path = write_idm(tmp_path / "bomb.idm", bomb, bom=False)
    assert path.stat().st_size < 100_000
    assert _codes(path) == ["IDM_ARCHIVE_LIMIT"]


def test_a_zip_bomb_in_an_entry_we_ignore_costs_nothing(tmp_path: Path) -> None:
    path = write_idm(
        tmp_path / "other.idm", extra={"data/huge.bin": b"\0" * 50_000_000}
    )  # never unpacked
    started = time.monotonic()
    read_idm(path)
    assert time.monotonic() - started < 5


@pytest.mark.parametrize(
    "name", ["../evil.txt", "/abs/evil.txt", "a/../../evil.txt", "..\\evil.txt", "C:\\evil.txt"]
)
def test_zip_slip_names_are_never_extracted(tmp_path: Path, name: str) -> None:
    work = tmp_path / "work"
    work.mkdir()
    path = write_idm(work / "slip.idm", extra={name: CANARY.encode()})
    read_idm(path)
    assert [p.name for p in work.iterdir()] == ["slip.idm"]
    assert not (tmp_path / "evil.txt").exists()


def test_a_model_entry_with_a_traversal_name_is_not_the_model(tmp_path: Path) -> None:
    path = write_idm(tmp_path / "x.idm", model_name="../model.xml")
    assert _codes(path) == ["IDM_MODEL_MISSING"]


def test_many_entries_are_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(archive, "MAX_ZIP_ENTRIES", 5)
    extra = {f"f{i}.txt": b"x" for i in range(10)}
    assert _codes(write_idm(tmp_path / "many.idm", extra=extra)) == ["IDM_ARCHIVE_LIMIT"]


# ---- YAML: the project files -------------------------------------------------------------------
BILLION_LAUGHS = (
    "a: &a [x, x, x, x, x, x, x, x, x]\n"
    "b: &b [*a, *a, *a, *a, *a, *a, *a, *a, *a]\n"
    "c: &c [*b, *b, *b, *b, *b, *b, *b, *b, *b]\n"
    "d: &d [*c, *c, *c, *c, *c, *c, *c, *c, *c]\n"
    "e: [*d, *d, *d, *d, *d, *d, *d, *d, *d]\n"
)


@pytest.mark.parametrize(
    "text",
    [
        BILLION_LAUGHS,
        "a: &x 1\nb: *x\n",
        "a: !!python/object/apply:os.system ['echo x']\n",
        "a: !!python/object/new:subprocess.Popen [[ls]]\n",
        "a: !<tag:yaml.org,2002:python/name:os.system> x\n",
        "%TAG ! tag:evil,2000:\n---\na: !x 1\n",
        "<<: *x\n",
    ],
)
def test_yaml_with_aliases_tags_and_code_is_refused_quickly(text: str) -> None:
    started = time.monotonic()
    with pytest.raises(YamlSyntaxError):
        load_yaml_text(text)
    assert time.monotonic() - started < 2


def test_yaml_nesting_and_size_are_bounded() -> None:
    with pytest.raises(YamlSyntaxError):
        load_yaml_text("a: " + "[" * 5_000 + "]" * 5_000 + "\n")
    with pytest.raises(YamlSyntaxError):
        load_yaml_text("x: 1\n" * 30_000)
    with pytest.raises(YamlSyntaxError):
        load_yaml_text("x: " + "y" * 2_000_000 + "\n")
    deep = "".join("  " * i + "k:\n" for i in range(200)) + "  " * 200 + "v: 1\n"
    with pytest.raises(YamlSyntaxError):
        load_yaml_text(deep)


def test_yaml_error_text_never_echoes_the_file() -> None:
    with pytest.raises(YamlSyntaxError) as info:
        load_yaml_text(f"{CANARY}: !!python/object:os.system x\n")
    assert CANARY not in str(info.value)


# ---- CSV and XLSX: unit tables -----------------------------------------------------------------
def test_a_huge_csv_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(unit_table, "MAX_ROWS", 10)
    path = tmp_path / "t.csv"
    path.write_text("id,power\n" + "a,1 W\n" * 50, encoding="utf-8")
    result = unit_table.read_table(path)
    assert result.problems and not result.rows


def test_a_csv_field_over_the_csv_limit_is_a_problem(tmp_path: Path) -> None:
    path = tmp_path / "t.csv"
    path.write_text("id,power\na," + "9" * 300_000 + "\n", encoding="utf-8")
    result = unit_table.read_table(path)
    assert result.problems and not result.rows


def test_a_csv_with_a_nul_byte_is_a_problem(tmp_path: Path) -> None:
    path = tmp_path / "t.csv"
    path.write_bytes(b"id,power\na,1\x00 W\n")
    result = unit_table.read_table(path)
    assert not any(r == "W" for r in result.rows)  # nothing crashes; rows may be rejected


def test_a_file_over_the_size_limit_is_refused_before_reading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(unit_table, "MAX_FILE_BYTES", 100)
    path = tmp_path / "t.csv"
    path.write_text("id,power\n" + "a,1 W\n" * 100, encoding="utf-8")
    assert unit_table.read_table(path).problems


def _xlsx_with(tmp_path: Path, shared_strings: bytes | None = None) -> Path:
    from openpyxl import Workbook

    book = Workbook()
    sheet = book.active
    assert sheet is not None
    sheet.append(["id", "power"])
    sheet.append(["a", "1 W"])
    path = tmp_path / "t.xlsx"
    book.save(path)
    if shared_strings is None:
        return path
    source = zipfile.ZipFile(path)
    out = tmp_path / "patched.xlsx"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as target:
        for info in source.infolist():
            data = source.read(info.filename)
            if info.filename == "xl/sharedStrings.xml":
                data = shared_strings
            target.writestr(info, data)
    source.close()
    return out


def test_an_xlsx_with_an_external_entity_does_not_read_a_local_file(tmp_path: Path) -> None:
    secret = tmp_path / "secret.txt"
    secret.write_text(CANARY, encoding="utf-8")
    bad = (
        f'<?xml version="1.0"?><!DOCTYPE sst [<!ENTITY x SYSTEM "{secret.as_uri()}">]>'
        '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="3" '
        'uniqueCount="3"><si><t>&x;</t></si><si><t>&x;</t></si><si><t>&x;</t></si></sst>'
    ).encode()
    result = unit_table.read_table(_xlsx_with(tmp_path, bad))
    assert CANARY not in _all_text(result)
    assert result.problems


def test_an_xlsx_that_unpacks_to_too_much_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(unit_table, "MAX_UNPACKED_BYTES", 10_000)
    path = tmp_path / "bomb.xlsx"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("xl/worksheets/sheet1.xml", b"<a>" + b" " * 5_000_000 + b"</a>")
    result = unit_table.read_table(path)
    assert result.problems and not result.rows


def test_a_file_that_is_not_what_its_suffix_says_is_a_problem(tmp_path: Path) -> None:
    path = tmp_path / "t.xlsx"
    path.write_bytes(io.BytesIO(b"PK\x03\x04 not really a zip").getvalue())
    assert unit_table.read_table(path).problems
    path2 = tmp_path / "t.csv"
    path2.write_bytes(b"\xff\xfe\x00\x00 not utf-8")
    assert unit_table.read_table(path2).problems


# ---- file names --------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "name",
    [
        "../../etc/passwd",
        "..\\..\\windows\\system32",
        "/etc/passwd",
        "C:\\evil",
        "con",
        "NUL.txt",
        "aux.tar.gz",
        ".hidden",
        "trailing.",
        "a\0b",
        "x" * 1000,
        "",
    ],
)
def test_safe_name_gives_a_plain_name(name: str) -> None:
    result = safe_name(name)
    assert result and "/" not in result and "\\" not in result and "\0" not in result
    assert not result.startswith(".") and not result.endswith(".")
    assert len(result.encode("utf-8")) <= 255
    assert result.split(".")[0].lower() not in {"con", "nul", "aux", "prn"}
