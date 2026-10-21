"""Writing output files safely.

File names are often built from project text (mission phases, thermal case names, link ids), so
every name is reduced to a plain file name before it is joined to the output folder. A file is
written to a temporary name in the same folder and moved into place, so a failure never leaves a
half-written file, and a symlink at the target is replaced rather than followed.
"""

from __future__ import annotations

import contextlib
import os
import re
import stat
import unicodedata
from collections.abc import Sequence
from pathlib import Path

MAX_NAME = 120  # bytes (UTF-8); a file system allows 255, and a temporary name is longer
_RESERVED = re.compile(r"^(?:con|prn|aux|nul|(?:com|lpt)[1-9\u00b9\u00b2\u00b3])$", re.IGNORECASE)
_BAD = re.compile(r"[^\w.\-]+", re.UNICODE)


class OutputError(Exception):
    """The outputs cannot be written; the message is plain language without project content."""


def _fit(text: str, limit: int) -> str:
    """`text` cut to at most `limit` UTF-8 bytes, on a character boundary."""
    return text.encode("utf-8")[: max(limit, 1)].decode("utf-8", errors="ignore")


def safe_name(name: str) -> str:
    """A plain file name: letters, digits, '.', '-' and '_' only, no leading dot, no trailing dot,
    never a Windows device name (also with extensions: `con.tar.gz`), at most MAX_NAME bytes (the
    extension is kept)."""
    base = _BAD.sub("_", name).lstrip(".").rstrip(".") or "_"  # separators become '_'
    if _RESERVED.match(base.split(".", 1)[0]):
        base = "_" + base
    if len(base.encode("utf-8")) > MAX_NAME:
        stem, dot, ext = base.rpartition(".")
        if not dot or not stem or len(ext.encode("utf-8")) > MAX_NAME // 4:
            return _fit(base, MAX_NAME).rstrip(".") or "_"
        base = _fit(stem, MAX_NAME - len((dot + ext).encode())) + dot + ext
    return base


def same_name_key(name: str) -> str:
    """What a case-insensitive, normalising file system (Windows among them) treats as one name."""
    return unicodedata.normalize("NFC", name).casefold()


def _discard(path: Path) -> None:
    with contextlib.suppress(OSError):
        path.unlink(missing_ok=True)


def _message(failed: str, written: Sequence[str], pending: Sequence[str]) -> str:
    text = (
        f"The file {failed} could not be written. Check that the output folder exists, is a "
        "folder and that you may write to it."
    )
    if written:
        text += " Already replaced in the output folder: " + ", ".join(written) + "."
    if pending:
        text += " Not written: " + ", ".join(pending) + "."
    return text


def write_files(
    folder: Path, items: Sequence[tuple[str, bytes | str]], *, sanitise: bool = True
) -> list[Path]:
    """Write several files into `folder` and return their paths.

    Every file is first written to a temporary name in the folder; only when all of them are on
    disk are they moved into place. A failure while writing therefore leaves the folder as it was.
    A failure while moving (rare: permissions changing, the disk disappearing) removes the
    remaining temporary files and the message names the file that failed, the files already
    replaced and the files not written. A file that exists keeps its permission bits. Two names
    that a case-insensitive file system treats as one are refused."""
    folder = Path(folder)
    staged: list[tuple[Path, Path]] = []  # (temporary, target)
    seen: dict[str, str] = {}
    for name, data in items:
        if not isinstance(data, bytes | str):
            raise TypeError("data must be text or bytes")
        target = folder / (safe_name(name) if sanitise else Path(name).name)
        key = same_name_key(target.name)
        if key in seen:
            raise OutputError(
                f"Two outputs would be written to the same file name ({target.name}). Rename "
                "the units, links, phases or cases whose names are almost identical, or that "
                "equal a name the tool generates."
            )
        seen[key] = target.name
    pid = os.getpid()
    try:
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise OutputError(
                "The files could not be written: the output folder could not be created. Check "
                "that the path is valid and that you may write there."
            ) from exc
        for name, data in items:
            target = folder / (safe_name(name) if sanitise else Path(name).name)
            payload = data if isinstance(data, bytes) else data.encode("utf-8")
            temporary = folder / f".{target.name}.{pid}.tmp"
            staged.append((temporary, target))
            try:
                temporary.write_bytes(payload)
            except OSError as exc:
                raise OutputError(_message(target.name, [], [])) from exc
        done: list[str] = []
        for i, (temporary, target) in enumerate(staged):
            try:
                with contextlib.suppress(OSError):  # keep the mode of a file that is replaced
                    existing = os.lstat(target)
                    if stat.S_ISREG(existing.st_mode):
                        os.chmod(temporary, stat.S_IMODE(existing.st_mode))
                os.replace(temporary, target)
            except OSError as exc:
                raise OutputError(
                    _message(target.name, done, [t.name for _, t in staged[i + 1 :]])
                ) from exc
            done.append(target.name)
    except BaseException:
        for temporary, _ in staged:
            _discard(temporary)
        raise
    return [target for _, target in staged]


def write_file(folder: Path, name: str, data: bytes | str, *, sanitise: bool = True) -> Path:
    """Write `data` as `folder/<safe name>` atomically and return the path. `sanitise=False` keeps
    `name` as it is (for an existing file the user chose, which must keep its own name)."""
    return write_files(folder, [(name, data)], sanitise=sanitise)[0]
