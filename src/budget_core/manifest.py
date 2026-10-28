"""What a result was computed from: the files read and a digest of the model they gave (D-204).

Two fingerprints answer two different questions. The **file manifest** lists every project file the
loader read, with its size and the SHA-256 of its raw bytes, so a reviewer can see exactly which
file differs (a comment edit changes it; the numbers do not). The **model digest** is the SHA-256
of the loaded model in a canonical form (every id, every field, sorted, comments and key order
gone), so two projects that give the same numbers have the same digest however they are written.
Reproducing a result needs the model digest to match; finding out why it does not needs the
manifest.

No timestamp, path outside the project or user name enters either value.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

DIGEST_PREFIX = "sha256:"


@dataclass(frozen=True, order=True)
class ManifestEntry:
    """One project file as it was read: its path inside the project, its size and its hash."""

    path: str
    size: int
    sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {"path": self.path, "size": self.size, "sha256": self.sha256}


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def entry_for(path: str, raw: bytes) -> ManifestEntry:
    return ManifestEntry(path, len(raw), sha256_hex(raw))


def files_digest(entries: tuple[ManifestEntry, ...]) -> str:
    """One digest over the whole manifest (path, size and hash of each file, sorted by path)."""
    lines = [f"{e.path}\t{e.size}\t{e.sha256}\n" for e in sorted(entries)]
    return DIGEST_PREFIX + sha256_hex("".join(lines).encode("utf-8"))


def canonical_json(data: Any) -> str:
    """Plain data as one deterministic line: sorted keys, no spaces, ASCII, no NaN or infinity."""
    return json.dumps(
        data, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    )


def data_digest(data: Any) -> str:
    return DIGEST_PREFIX + sha256_hex(canonical_json(data).encode("utf-8"))
