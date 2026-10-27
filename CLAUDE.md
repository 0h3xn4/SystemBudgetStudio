# System Budget Studio — working notes

Docs index: `docs/README.md` (change the docs with the code: `docs/developer/README.md#keep-the-documentation-true`). Spec: `docs/SPEC.md` (authoritative). Plan: `docs/PLAN.md`. Architecture: `docs/ARCHITECTURE.md`. Record decisions in `docs/DECISIONS.md`, physics simplifications in `docs/DEVIATIONS.md`.

## Commands
- Install: `pip install -e ".[dev]"`
- Test: `QT_QPA_PLATFORM=offscreen pytest` (offline test: `pytest tests/offline`)
- Lint/type: `ruff check . && ruff format --check . && mypy`
- Lock: `packaging/lock.sh` (uv, hashes)
- Regenerate generated files after model changes: `budget export-schemas src/budget_core/schemas` and `budget export-examples examples --force` (tests fail on drift)
- Package: `pyinstaller packaging/system_budget_studio.spec` (Linux release: `packaging/linux/build_in_container.sh` in `rockylinux:9`)
- Licences: `python packaging/licence_check.py --markdown docs/LICENCES.md` (permissive or LGPL only); user guide: `budget guide --out guide`

## Conventions
- Core (`budget_core`) has no GUI or networking imports; GUI and CLI depend only on the core.
- Units explicit in field names (`power_w`, `freq_hz`, `gain_dbi`).
- Never invent standards values: numbers live in config files with a `source` field; unknown = `source: TBD`.
- No project content in logs, temp files outside the project folder, or crash dumps.
- Tests first; no warnings on main. Work on a branch and open a PR; never push to `main`.
- Runtime deps only in `[project.dependencies]`; all tooling in the `dev` extra.
- Example projects: invented data only.
- Problems/messages never contain values read from project files (field names, ids and units only).
- File format: `docs/FILE_FORMAT.md`. Schema changes need a version bump and a migration.

## UI design rules (the window; full text in `docs/DESIGN.md`, brief in `docs/ui/UI_OVERHAUL.md`)
- Colours, fonts and pixel sizes live in `budget_gui/theme/` only (a test fails on a hex colour, a font family, a pixel size in a Qt size call or `setStyleSheet` anywhere else). Take sizes from the scales (`theme.gap(i)`, `theme.inset(h, v)`, `theme.px(theme.CONSTANT)`), fonts from `theme.ui_font()` / `theme.mono_font()`, colours from `theme.tokens()`; widgets that paint themselves connect to `theme.manager().changed`.
- Inter for text, JetBrains Mono for numbers, identifiers, paths and code. Type 11/12/13/15/18/22 px, weights 400/500/600, spacing 4/8/12/16/24/32 px, radii 6 (controls) and 8 (panels), controls 28/32 px, table rows 26 px, focus ring 2 px, motion 120 to 180 ms (never on data or plots, off with *Reduce motion*).
- Colour means something: neutral surfaces, one accent for the one primary action per view (`kind="primary"`), status colours only for status; a status always has an icon or text too; text 4.5 : 1 and icons/focus 3 : 1 in both themes (tests compute it). Separate areas with surfaces, not lines; no box in a box.
- Build views from `budget_gui/components/` (`Button`, `StatusBadge`, `SegmentedControl`, `Card`, `EmptyState`, `Toast`, `MessageDialog`...); every empty list has an `EmptyState`; success is a toast, a problem is in the Problems panel, a modal dialog only confirms something destructive or runs a wizard; an icon-only button has a tooltip and an accessible name.
- Keyboard first: every frequent action has a shortcut shown in its tooltip and menu entry, and an entry in the Ctrl+K palette; focus is always visible.
- Nothing longer than about 50 ms on the GUI thread; use model/view (not `QTableWidget`) for anything that can be large. Long NumPy/SGP4 calls in a worker run in slices (`budget_core/slices.py`) and the worker prepares the plot (`plot_prepare.py`) so the window keeps the interpreter lock available (D-182, D-183).
- The window opens in the focused view (D-191): problems as one line, no Inspector or Provenance, only the main grid columns. Anything that points at a problem calls `MainWindow.reveal_problems`; window tests start in the full view (`tests/gui/conftest.py`) and `test_focused_view.py` tests the default. The words stay professional: no plain-language rewrite of the terminology.
- Carbon and IBM Plex are gone from the window (D-168); IBM Plex stays only for exported files.
