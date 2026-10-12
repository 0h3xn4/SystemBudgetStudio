"""Edit a YAML project file in place: change only what differs, keep comments and key order.

A GUI editor shows part of a file. Saving the whole model would drop comments (the place where
users keep sources, decision D-102), reorder keys and lose fields the editor does not show. Here
the file is parsed in ruamel's round-trip mode and the difference between the model as loaded
(`old`) and as edited (`new`) is applied to it: values that did not change are left exactly as
written, keys that were not edited stay. A save without an edit gives the same bytes.

Everything is plain data. Files are written through `write_file` (temporary file, then replace),
a symbolic link is written through to its target, the file mode is kept, and a byte-order mark and
CRLF line ends are kept.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq

from budget_core.io.yamlio import dump_yaml, load_yaml_text
from budget_core.reports.files import write_file

BOM = b"\xef\xbb\xbf"


@dataclass(frozen=True)
class SaveResult:
    path: Path
    changed: bool  # False: the file already held exactly these values and was not written
    canonical: bool  # True: the edit could not be applied in place; the file was rewritten whole


# ---- reading and writing bytes ----------------------------------------------------------------
def file_stamp(path: Path) -> str | None:
    """A fingerprint of the file's bytes, or None when it cannot be read (used to notice that a
    file changed on disk after an editor loaded it)."""
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return None


def split_text(raw: bytes) -> tuple[str, bool, bool]:
    """(text with LF line ends, had a BOM, uses CRLF). Raises UnicodeDecodeError."""
    bom = raw.startswith(BOM)
    text = raw[len(BOM) :].decode("utf-8") if bom else raw.decode("utf-8")
    crlf = text.count("\r\n") > text.count("\n") - text.count("\r\n")
    return text.replace("\r\n", "\n"), bom, crlf


def join_text(text: str, bom: bool, crlf: bool) -> bytes:
    """The inverse of `split_text`."""
    if crlf:
        text = text.replace("\r\n", "\n").replace("\n", "\r\n")
    return (BOM if bom else b"") + text.encode("utf-8")


def write_bytes_atomic(path: Path, data: bytes) -> Path:
    """Write `data` over the existing file `path` through a temporary file. A symbolic link is
    followed (the link stays a link) and the permission bits of the old file are kept. Raises
    `OutputError` when the folder cannot be written."""
    path = Path(path)
    target = Path(os.path.realpath(path)) if path.is_symlink() else path
    mode: int | None
    try:
        mode = target.stat().st_mode & 0o7777
    except OSError:
        mode = None
    written = write_file(target.parent, target.name, data, sanitise=False)
    if mode is not None:
        with contextlib.suppress(OSError):  # a file system without modes: nothing to keep
            os.chmod(written, mode)
    return written


# ---- the patch --------------------------------------------------------------------------------
def _equal(a: Any, b: Any) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_equal(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_equal(x, y) for x, y in zip(a, b, strict=True))
    return bool(a == b)


def _signature(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _commented(value: Any) -> Any:
    if isinstance(value, dict):
        mapping = CommentedMap()
        for key, item in value.items():
            mapping[key] = _commented(item)
        return mapping
    if isinstance(value, list):
        sequence = CommentedSeq()
        for item in value:
            sequence.append(_commented(item))
        return sequence
    return value


def _patch(node: Any, old: Any, new: Any) -> Any:
    """`node` (the parsed file) changed so that it holds `new` where `old` was; returns the node
    to keep in the parent (the same object when it was patched in place)."""
    if isinstance(node, CommentedMap) and isinstance(old, dict) and isinstance(new, dict):
        _patch_map(node, old, new)
        return node
    if (
        isinstance(node, CommentedSeq)
        and isinstance(old, list)
        and isinstance(new, list)
        and len(node) == len(old)
    ):
        _patch_seq(node, old, new)
        return node
    return _commented(new)


def _patch_map(node: CommentedMap, old: dict[str, Any], new: dict[str, Any]) -> None:
    for key in old:
        if key not in new and key in node:
            del node[key]
    keys = list(new)
    for index, key in enumerate(keys):
        value = new[key]
        if key in node:
            if key in old and _equal(old[key], value):
                continue
            child = _patch(node[key], old.get(key), value)
            if child is not node[key]:
                node[key] = child
            continue
        position = 0
        for previous in reversed(keys[:index]):
            if previous in node:
                position = list(node).index(previous) + 1
                break
        node.insert(position, key, _commented(value))


def _patch_seq(node: CommentedSeq, old: list[Any], new: list[Any]) -> None:
    matcher = SequenceMatcher(
        a=[_signature(x) for x in old], b=[_signature(x) for x in new], autojunk=False
    )
    for tag, i1, i2, j1, j2 in reversed(matcher.get_opcodes()):
        if tag == "equal":
            continue
        paired = min(i2 - i1, j2 - j1)
        for index in range(i2 - 1, i1 + paired - 1, -1):  # surplus old items
            del node[index]
        for offset, item in enumerate(new[j1 + paired : j2]):  # surplus new items
            node.insert(i1 + paired + offset, _commented(item))
        for offset in range(paired):
            child = _patch(node[i1 + offset], old[i1 + offset], new[j1 + offset])
            if child is not node[i1 + offset]:
                node[i1 + offset] = child


def _indent_of(text: str) -> tuple[int, int, int]:
    """(mapping indent, sequence indent, dash offset) as the file uses them; 2, 4, 2 by default."""
    mapping, sequence, offset = None, None, None
    previous_key_indent: int | None = None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        if previous_key_indent is not None and indent >= previous_key_indent:
            if stripped.startswith("- "):
                if sequence is None:
                    offset = indent - previous_key_indent
                    sequence = offset + len(stripped) - len(stripped[1:].lstrip(" "))
            elif mapping is None and indent > previous_key_indent:
                mapping = indent - previous_key_indent
        previous_key_indent = indent if re.search(r":\s*(#.*)?$", stripped) else None
        if mapping is not None and sequence is not None:
            break
    return mapping or 2, sequence or 4, offset if offset is not None else 2


def patch_yaml_text(text: str, old: Any, new: Any) -> str:
    """`text` with the difference between the plain data `old` and `new` applied; comments, key
    order and everything not changed stay as written. `old` is the data `text` was read as.
    Raises `YamlSyntaxError` for a file the project loader would refuse."""
    if _equal(old, new):
        return text
    load_yaml_text(text)  # the loader's size, alias and duplicate-key checks
    mapping, sequence, offset = _indent_of(text)
    yaml = YAML(typ="rt")
    yaml.preserve_quotes = True
    yaml.default_flow_style = False
    yaml.indent(mapping=mapping, sequence=sequence, offset=offset)
    yaml.width = 4096
    yaml.representer.add_representer(
        type(None), lambda rep, _data: rep.represent_scalar("tag:yaml.org,2002:null", "null")
    )
    document = yaml.load(text)
    document = _patch(document, old, new)
    buffer = io.StringIO()
    yaml.dump(document, buffer)
    return buffer.getvalue()


# ---- saving a model ---------------------------------------------------------------------------
def save_edited_data(
    path: Path,
    old: dict[str, Any],
    new: dict[str, Any],
    check: Callable[[Any], dict[str, Any]],
) -> SaveResult:
    """Write the edit `old` -> `new` into the existing file `path`.

    `check` turns data read from a file into the plain data of its model (validate, then
    `model_to_data`). The patched text is read back through it and must give exactly `new`; when
    it does not (a hand-written file the patch cannot follow, an older schema version) the file is
    written whole in canonical form instead, and `canonical` says so. A file that already holds
    the new values is not written at all. Raises `OutputError` (cannot write), `OSError` and
    `UnicodeDecodeError` (cannot read)."""
    path = Path(path)
    if not path.is_file():
        write_bytes_atomic(path, dump_yaml(new).encode("utf-8"))
        return SaveResult(path, True, False)
    raw = path.read_bytes()
    text, bom, crlf = split_text(raw)
    canonical = False
    try:
        patched = patch_yaml_text(text, old, new)
        if not _equal(check(load_yaml_text(patched).data), new):
            raise ValueError("the patched file does not hold the edited values")
    except Exception:  # any failure: keep the data right, give up the comments
        patched = dump_yaml(new)
        canonical = True
    data = join_text(patched, bom, crlf)
    if data == raw:
        return SaveResult(path, False, False)
    write_bytes_atomic(path, data)
    return SaveResult(path, True, canonical)
