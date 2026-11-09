# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""Reading models of IDM-CIC (reads models from IDM-CIC, (c) CNES).

IDM-CIC is software of the French space agency CNES. This package only reads the model file that
the program writes (a ZIP archive with an XML model inside); it uses no CNES software, no library
and no data of CNES, and it does not suggest that CNES endorses or supports this tool. The file
format is described in this repository in our own words (docs/models/idm-import.md); the code uses
the element and attribute names of the format because it has to.

`read_idm` (reader.py) turns the archive into a typed, unit-normalised `IdmModel` (model.py). A
later layer maps that model onto a project; nothing here writes project files.
"""

from __future__ import annotations

# The version of the published XML model specification that this reader was written against.
# Files of a newer minor version are read with a warning (IDM_VERSION_NEWER).
SPEC_VERSION = "3.4.0.19"
SPEC_MAJOR_MINOR = (3, 4)
