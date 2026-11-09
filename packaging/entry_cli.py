# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""Entry point of the command-line executable `budget` (PyInstaller)."""

import sys

from budget_cli.main import main

if __name__ == "__main__":
    sys.exit(main())
