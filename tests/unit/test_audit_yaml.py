"""Audit fixes MI-1, MI-2, MI-3: bounded YAML parse time, odd YAML never raises, special files."""

from __future__ import annotations

import contextlib
import os
import time
from pathlib import Path

import pytest

from budget_core.io.project_loader import load_project
from budget_core.io.yamlio import YamlSyntaxError, load_yaml_text
from budget_core.problems import Severity
from tests.helpers import write_valid_project

FAST_S = 1.0


def _refused_quickly(text: str) -> YamlSyntaxError:
    started = time.perf_counter()
    with pytest.raises(YamlSyntaxError) as info:
        load_yaml_text(text)
    elapsed = time.perf_counter() - started
    assert elapsed < FAST_S, f"took {elapsed:.2f} s"
    return info.value


# ---- MI-1 ------------------------------------------------------------------------------------
@pytest.mark.parametrize("opener", ["[", "{", "[{", "[[{{"])
def test_deep_flow_nesting_is_refused_before_the_parse(opener: str) -> None:
    _refused_quickly("x: " + opener * (60_000 // len(opener)))


def test_60_kb_of_brackets_in_a_project_file_is_a_problem_quickly(tmp_path: Path) -> None:
    write_valid_project(tmp_path / "p")
    (tmp_path / "p" / "units" / "obc.yaml").write_text("x: " + "[" * 60_000, encoding="utf-8")
    started = time.perf_counter()
    result = load_project(tmp_path / "p")
    assert time.perf_counter() - started < FAST_S * 2
    problem = next(p for p in result.problems if p.file == "units/obc.yaml")
    assert problem.code == "YAML_SYNTAX"


def test_closers_hidden_in_quoted_strings_cannot_hide_the_depth() -> None:
    # every level is followed by a string full of closing brackets; the real depth keeps growing
    text = "x: " + ('[ "' + "]" * 40 + '", ') * 3000
    _refused_quickly(text)


def test_one_huge_flow_list_is_refused_quickly() -> None:
    _refused_quickly("x: [" + ",".join(["1"] * 190_000) + "]")


def test_a_very_long_line_is_refused_quickly() -> None:
    _refused_quickly("x: " + "a" * 200_000)


def test_too_many_lines_are_refused_quickly() -> None:
    _refused_quickly("".join(f"k{i}: 1\n" for i in range(60_000)))


def test_cr_only_line_endings_count_as_lines() -> None:
    _refused_quickly("".join(f"k{i}: 1\r" for i in range(60_000)))


def test_ordinary_flow_style_still_loads() -> None:
    text = "a: [1, 2, 3]\nb: {c: [1, {d: 2}], e: 'x [y] z'}\n# [ comment\nf: \"[\"\n"
    assert load_yaml_text(text).data["b"]["c"] == [1, {"d": 2}]


# ---- MI-2 ------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "text",
    [
        "name: !!omap [a: 1]\n",
        "name: !custom [1, 2]\n",
        "name: !!binary AAAA\n",
        "name: !!set {a, b}\n",
        "name: !!python/object:os.system x\n",
        "name: !!str 5\n",
    ],
)
def test_explicit_tags_are_a_syntax_error(text: str) -> None:
    with pytest.raises(YamlSyntaxError) as info:
        load_yaml_text(text)
    assert info.value.line == 1
    assert "tag" in str(info.value)


@pytest.mark.parametrize(
    "text",
    [
        "other:\n  <<: {foo: 1}\n  y: 2\n",
        "<<: {foo: 1}\n",
        "other: {<<: {foo: 1}}\n",
    ],
)
def test_inline_merge_key_is_a_syntax_error(text: str) -> None:
    with pytest.raises(YamlSyntaxError) as info:
        load_yaml_text(text)
    assert "<<" in str(info.value)


def test_quoted_merge_text_is_an_ordinary_string() -> None:
    assert load_yaml_text("a: '<<'\n'<<': 1\n").data == {"a": "<<", "<<": 1}


@pytest.mark.parametrize(
    "text", ["%YAML 1.3\n---\na: 1\n", "%YAML 9.9\n---\na: 1\n", "%FOO bar\n--- a\n"]
)
def test_directives_never_raise_other_than_syntax_error(text: str) -> None:
    with contextlib.suppress(YamlSyntaxError):
        load_yaml_text(text)


def test_any_parser_exception_becomes_a_syntax_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from budget_core.io import yamlio

    class Boom:
        allow_duplicate_keys = False

        def scan(self, text: str) -> list[object]:
            return []

        def load(self, text: str) -> object:
            raise AssertionError("internal")

    monkeypatch.setattr(yamlio, "_yaml", lambda: Boom())
    with pytest.raises(YamlSyntaxError):
        load_yaml_text("a: 1\n")


def test_tag_error_in_a_project_file_is_located(tmp_path: Path) -> None:
    write_valid_project(tmp_path / "p")
    path = tmp_path / "p" / "units" / "obc.yaml"
    path.write_text(path.read_text(encoding="utf-8") + "x: !!omap [a: 1]\n", encoding="utf-8")
    result = load_project(tmp_path / "p")
    problem = next(p for p in result.problems if p.file == "units/obc.yaml")
    assert problem.code == "YAML_SYNTAX" and problem.line is not None


# ---- MI-3 ------------------------------------------------------------------------------------
@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="needs POSIX named pipes")
def test_a_fifo_named_yaml_does_not_block_the_loader(tmp_path: Path) -> None:
    write_valid_project(tmp_path / "p")
    os.mkfifo(tmp_path / "p" / "units" / "pipe.yaml")
    started = time.perf_counter()
    result = load_project(tmp_path / "p")
    assert time.perf_counter() - started < 5.0
    problem = next(p for p in result.problems if p.file == "units/pipe.yaml")
    assert problem.severity is Severity.ERROR and problem.code == "FILE_INVALID"


def test_a_folder_named_yaml_is_a_problem(tmp_path: Path) -> None:
    write_valid_project(tmp_path / "p")
    (tmp_path / "p" / "units" / "dir.yaml").mkdir()
    result = load_project(tmp_path / "p")
    problem = next(p for p in result.problems if p.file == "units/dir.yaml")
    assert problem.code == "FILE_INVALID"


def test_reading_stops_one_byte_past_the_cap(tmp_path: Path) -> None:
    from budget_core.io.yamlio import read_limited

    path = tmp_path / "f.yaml"
    path.write_bytes(b"a" * 500)
    assert len(read_limited(path, 100)) == 101  # the caller sees "more than the cap"
    assert read_limited(path, 500) == b"a" * 500
