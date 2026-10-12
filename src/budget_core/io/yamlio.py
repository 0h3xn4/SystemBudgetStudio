"""YAML reading with line tracking, and canonical (deterministic) writing.

Reading uses ruamel.yaml round-trip mode only to learn line numbers; the result is converted to
plain Python. Errors never include file content (spec constraint 11).
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path as FsPath
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.constructor import DuplicateKeyError
from ruamel.yaml.error import YAMLError

Path = tuple[str | int, ...]


class YamlSyntaxError(Exception):
    """The file is not valid YAML. `line` is 1-based when known; the message holds no content."""

    def __init__(self, message: str, line: int | None) -> None:
        super().__init__(message)
        self.line = line


@dataclass
class LineMap:
    """1-based line numbers for every mapping key and sequence item."""

    _lines: dict[Path, int] = field(default_factory=dict)

    def lookup(self, path: Path) -> int | None:
        """Line of `path`, or of its nearest existing ancestor."""
        for end in range(len(path), -1, -1):
            line = self._lines.get(path[:end])
            if line is not None:
                return line
        return None


@dataclass
class LoadedYaml:
    data: Any
    lines: LineMap


def format_path(path: Path) -> str:
    out = ""
    for part in path:
        if isinstance(part, int):
            out += f"[{part}]"
        else:
            out += f".{part}" if out else str(part)
    return out


# Limits. ruamel needs about 60 microseconds per node, and its scanner is quadratic in the depth of
# flow nesting ("x: [[[[..." takes 65 s for 60,000 brackets), so everything that could make the
# parse slow is checked on the raw text first (`_precheck`), with cheap counts only.
MAX_YAML_BYTES = 1_000_000  # a project file is a few kB; this stops memory and time exhaustion
MAX_YAML_LINES = 20_000
MAX_YAML_LINE_CHARS = 50_000
MAX_FLOW_DEPTH = 32  # nested [ and { on the raw text
MAX_FLOW_BRACKETS = 2_000  # of each of [ ] { } in one file
MAX_FLOW_ITEMS = 30_000  # commas
MAX_YAML_DEPTH = 64
MAX_YAML_NODES = 60_000

_BRACKETS = re.compile(r"[\[\]{}]")


def read_limited(path: FsPath, limit: int) -> bytes:
    """At most `limit` + 1 bytes of a file: a caller compares the length with `limit` and never
    reads a file that grew (or lies about its size) without bound."""
    with open(path, "rb") as handle:
        return handle.read(limit + 1)


def _precheck(text: str) -> None:
    """Refuse text that would make the parser slow, before the parser sees it. Counts only; quoting
    and comments are not interpreted, so the checks can only be stricter than the parser, never
    looser (a closing bracket inside a string does not lower the count of the opening ones)."""
    if len(text) > MAX_YAML_BYTES:
        raise YamlSyntaxError("the file is too large", None)
    lines = text.splitlines()
    if len(lines) > MAX_YAML_LINES:
        raise YamlSyntaxError("the file has too many lines", None)
    for number, text_line in enumerate(lines, start=1):
        if len(text_line) > MAX_YAML_LINE_CHARS:
            raise YamlSyntaxError("a line of the file is too long", number)
    if text.count(",") > MAX_FLOW_ITEMS:
        raise YamlSyntaxError("the file has too many list entries", None)
    if any(text.count(ch) > MAX_FLOW_BRACKETS for ch in "[]{}"):
        raise YamlSyntaxError("the file has too many brackets", None)
    if "[" not in text and "{" not in text:
        return
    depth = 0
    for match in _BRACKETS.finditer(text):
        if match.group() in "[{":
            depth += 1
            if depth > MAX_FLOW_DEPTH:
                line = text.count("\n", 0, match.start()) + 1
                raise YamlSyntaxError("the file is nested too deeply", line)
        elif depth:
            depth -= 1


def _yaml() -> YAML:
    yaml = YAML(typ="rt")
    yaml.allow_duplicate_keys = False
    return yaml


def _line_of(container: Any, key: Any, is_map: bool) -> int | None:
    """1-based line of a mapping key or sequence item; None when the parser did not record it."""
    try:
        position = container.lc.key(key) if is_map else container.lc.item(key)
        return int(position[0]) + 1
    except Exception:  # an object without line data: the location is simply unknown
        return None


def _convert(node: Any, path: Path, lines: dict[Path, int]) -> Any:
    if len(path) > MAX_YAML_DEPTH:
        raise YamlSyntaxError("the file is nested too deeply", None)
    if len(lines) > MAX_YAML_NODES:
        raise YamlSyntaxError("the file has too many entries", None)
    if isinstance(node, CommentedMap):
        start = getattr(getattr(node, "lc", None), "line", None)
        if isinstance(start, int):
            lines[path] = start + 1
        out: dict[Any, Any] = {}
        for key in node:
            child = path + (key,)
            line = _line_of(node, key, True)
            if line is not None:
                lines[child] = line
            out[key] = _convert(node[key], child, lines)
        return out
    if isinstance(node, CommentedSeq):
        seq: list[Any] = []
        for index, item in enumerate(node):
            child = path + (index,)
            line = _line_of(node, index, False)
            if line is not None:
                lines[child] = line
            seq.append(_convert(item, child, lines))
        return seq
    if isinstance(node, bool) or node is None:
        return node
    if isinstance(node, int):
        return int(node)
    if isinstance(node, float):
        return float(node)
    if isinstance(node, str):
        return str(node)
    if isinstance(node, datetime | date):
        return node.isoformat().replace("+00:00", "Z")  # unquoted ISO times load as datetimes
    # anything else (a tagged value, a set, bytes) is not plain YAML data
    raise YamlSyntaxError("the file contains a value that is not plain text, number or list", None)


def _scan_tokens(text: str) -> None:
    """Refuse what a project file never needs and what the loader would misread: aliases (a few
    hundred bytes can expand to gigabytes), explicit tags (`!!omap`, `!!binary`, `!custom`) and
    the merge key `<<`."""
    from ruamel.yaml.tokens import AliasToken, ScalarToken, TagToken, ValueToken

    previous: Any = None
    try:
        for token in _yaml().scan(text):
            start = getattr(token, "start_mark", None)
            line = start.line + 1 if start is not None else None
            if isinstance(token, AliasToken):
                raise YamlSyntaxError(
                    "anchors and aliases (&name, *name) are not supported; write the values out",
                    line,
                )
            if isinstance(token, TagToken):
                raise YamlSyntaxError(
                    "tags (!!type, !name) are not supported; write plain values", line
                )
            if (
                isinstance(token, ValueToken)
                and isinstance(previous, ScalarToken)
                and previous.value == "<<"
                and getattr(previous, "style", None) is None
            ):
                pstart = getattr(previous, "start_mark", None)
                raise YamlSyntaxError(
                    "the merge key '<<' is not supported; write the values out",
                    pstart.line + 1 if pstart is not None else line,
                )
            previous = token
    except YamlSyntaxError:
        raise
    except Exception:  # a scanner error: the loader below reports it with its own message
        return


def load_yaml_text(text: str) -> LoadedYaml:
    _precheck(text)
    _scan_tokens(text)
    try:
        raw = _yaml().load(text)
    except DuplicateKeyError as exc:
        mark = getattr(exc, "problem_mark", None)
        raise YamlSyntaxError(
            "a field appears twice in the same mapping",
            mark.line + 1 if mark is not None else None,
        ) from None
    except YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        raise YamlSyntaxError(
            "the file is not valid YAML", mark.line + 1 if mark is not None else None
        ) from None
    except RecursionError:
        raise YamlSyntaxError("the file is nested too deeply", None) from None
    except Exception:
        # an impossible date, an integer with thousands of digits, an internal assertion of the
        # parser on an odd directive, ...: always a located-as-far-as-possible syntax error
        raise YamlSyntaxError("the file cannot be read as YAML", None) from None
    lines: dict[Path, int] = {}
    try:
        data = _convert(raw, (), lines)
    except YamlSyntaxError:
        raise
    except RecursionError:
        raise YamlSyntaxError("the file is nested too deeply", None) from None
    except Exception:
        raise YamlSyntaxError("the file cannot be read as YAML", None) from None
    return LoadedYaml(data, LineMap(lines))


def _to_commented(value: Any) -> Any:
    if isinstance(value, dict):
        cm = CommentedMap()
        for key, item in value.items():
            cm[key] = _to_commented(item)
        return cm
    if isinstance(value, list):
        cs = CommentedSeq()
        for item in value:
            cs.append(_to_commented(item))
        return cs
    return value


def dump_yaml(data: Any) -> str:
    """Canonical YAML: insertion-ordered keys, 2-space maps, indented sequences, LF, no comments."""
    yaml = YAML(typ="rt")
    yaml.default_flow_style = False
    yaml.indent(mapping=2, sequence=4, offset=2)
    yaml.width = 4096
    yaml.preserve_quotes = False
    yaml.representer.add_representer(
        type(None), lambda rep, _data: rep.represent_scalar("tag:yaml.org,2002:null", "null")
    )
    buffer = io.StringIO()
    yaml.dump(_to_commented(data), buffer)
    return buffer.getvalue()
