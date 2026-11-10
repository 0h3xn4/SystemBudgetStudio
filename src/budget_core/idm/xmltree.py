# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""Parse the XML model into a tree, safely.

The model file has no use for a document type declaration or entities, so a file that has one is
refused. Two checks do this: a byte check before parsing, and `defusedxml`, which refuses a
document type, entities and external references in the parser itself (so a file the byte check
cannot see, for example one in another encoding, is refused too). The depth and the number of
nodes are bounded while parsing. A byte order mark (the program writes one although the format
description says there is none) is dropped.
"""

from __future__ import annotations

import io
import xml.etree.ElementTree as ET

from defusedxml import DefusedXmlException
from defusedxml.ElementTree import iterparse

from budget_core.idm.archive import IdmReadError

MAX_XML_DEPTH = 200  # nesting of elements; real models nest about 25 deep
MAX_XML_NODES = 5_000_000  # elements in the model; the biggest real model has about 100,000

_BOM = b"\xef\xbb\xbf"
_OTHER_BOMS = (b"\xff\xfe", b"\xfe\xff")  # UTF-16 and UTF-32 marks: the format is UTF-8


def parse_model(data: bytes) -> ET.Element:
    if data.startswith(_BOM):
        data = data[len(_BOM) :]
    if data.startswith(_OTHER_BOMS):
        raise IdmReadError("IDM_XML_INVALID", "The model is not well-formed XML in UTF-8.")
    if b"\x00" in data:  # XML text has no NUL byte; UTF-16 without a mark has many
        raise IdmReadError("IDM_XML_INVALID", "The model is not well-formed XML in UTF-8.")
    if b"<!DOCTYPE" in data or b"<!ENTITY" in data:
        raise IdmReadError(
            "IDM_XML_UNSAFE",
            "The model declares a document type or entities, which a model file does not need.",
            "The tool does not read such a file.",
        )
    root: ET.Element | None = None
    depth = 0
    nodes = 0
    try:
        for event, element in iterparse(
            io.BytesIO(data),
            events=("start", "end"),
            forbid_dtd=True,
            forbid_entities=True,
            forbid_external=True,
        ):
            if event == "start":
                depth += 1
                nodes += 1
                if depth > MAX_XML_DEPTH or nodes > MAX_XML_NODES:
                    raise IdmReadError(
                        "IDM_ARCHIVE_LIMIT",
                        "The XML model is more deeply nested or larger than the tool reads.",
                        "Real models are far smaller; check that this is the right file.",
                    )
                if root is None:
                    root = element
            else:
                depth -= 1
    except DefusedXmlException:
        raise IdmReadError(
            "IDM_XML_UNSAFE",
            "The model declares a document type or entities, which a model file does not need.",
            "The tool does not read such a file.",
        ) from None
    except ET.ParseError:
        raise IdmReadError(
            "IDM_XML_INVALID",
            "The model is not well-formed XML in UTF-8.",
            "The file may be damaged; save the model again in IDM-CIC.",
        ) from None
    if root is None:
        raise IdmReadError("IDM_XML_INVALID", "The model is empty.", "")
    return root
