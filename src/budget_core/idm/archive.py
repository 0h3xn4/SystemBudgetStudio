"""Open a model archive and read its XML model, and nothing else.

The archive is never extracted: only the entry named `model.xml` at its root is read, with its
size bounded while it is read (a size written in the archive header is not trusted). Every other
entry (pictures, 3D files, data of other programs) is ignored. Failures are `IdmReadError`s whose
text is fixed and never contains anything read from the file.
"""

from __future__ import annotations

import hashlib
import zipfile
import zlib
from dataclasses import dataclass
from pathlib import Path

from budget_core.problems import Problem, Severity

MODEL_ENTRY = "model.xml"
MAX_IDM_FILE_BYTES = 200_000_000  # the archive on disk; real models are a few megabytes
MAX_MODEL_XML_BYTES = 100_000_000  # the XML model once unpacked; real ones are about 2 MB
MAX_ZIP_ENTRIES = 20_000  # entries in the archive (pictures, files of other programs)


class IdmReadError(Exception):
    """The archive or its XML cannot be used. `problem` says why, without file content."""

    def __init__(self, code: str, message: str, hint: str = "") -> None:
        super().__init__(message)
        self.problem = Problem(Severity.ERROR, code, message, hint=hint)


@dataclass(frozen=True)
class ModelBytes:
    data: bytes  # the content of model.xml as stored
    sha256: str  # its SHA-256, the revision of the model (same bytes, same revision)


def _unreadable(
    hint: str = "Check that this is a model file saved by IDM-CIC (.idm).",
) -> IdmReadError:
    return IdmReadError(
        "IDM_FILE_UNREADABLE", "The file cannot be read as an IDM-CIC archive.", hint
    )


def _too_large() -> IdmReadError:
    return IdmReadError(
        "IDM_ARCHIVE_LIMIT",
        "The archive is larger than the tool reads.",
        "Real models are a few megabytes; check that this is the right file.",
    )


def read_model_bytes(path: Path) -> ModelBytes:
    try:
        if path.stat().st_size > MAX_IDM_FILE_BYTES:
            raise _too_large()
        archive = zipfile.ZipFile(path)
    except IdmReadError:
        raise
    except OSError, zipfile.BadZipFile:
        raise _unreadable() from None
    with archive:
        infos = archive.infolist()
        if len(infos) > MAX_ZIP_ENTRIES:
            raise _too_large()
        found = [info for info in infos if info.filename == MODEL_ENTRY]
        if not found:
            raise IdmReadError(
                "IDM_MODEL_MISSING",
                "The archive has no model.xml entry at its root.",
                "An IDM-CIC model file holds its model in an entry named model.xml.",
            )
        if len(found) > 1:
            raise _unreadable("The archive names model.xml twice, so it is ambiguous.")
        info = found[0]
        if info.file_size > MAX_MODEL_XML_BYTES:
            raise _too_large()
        try:
            with archive.open(info) as handle:
                data = handle.read(MAX_MODEL_XML_BYTES + 1)
        except OSError, EOFError, zlib.error, RuntimeError, NotImplementedError, zipfile.BadZipFile:
            raise _unreadable("The model entry is damaged or encrypted.") from None
    if len(data) > MAX_MODEL_XML_BYTES:
        raise _too_large()
    return ModelBytes(data, hashlib.sha256(data).hexdigest())
