# UI overhaul: audit and plan (Phase 1)

Status: **Phase 1 (this audit and plan) was approved with "use the defaults" for all 12 questions of
[section 10](#10-questions-for-you); see [section 11](#11-progress) for where the milestones stand.**
The audit text below is the state of the window *before* the overhaul and is kept as written (the
"before" screenshots are in `docs/ui/screenshots/before/`). The brief is [`UI_OVERHAUL.md`](UI_OVERHAUL.md).

What Phase 1 added to the repository (documents and two measuring scripts, no code of the window):

| File | What it is |
|---|---|
| `docs/ui/UI_OVERHAUL.md` | The brief, verbatim. |
| `docs/ui/UI_OVERHAUL_PLAN.md` | This page. |
| `scripts/ui_screenshots.py` | Opens the example project and saves a PNG of every tab, sub-tab, dock, menu and dialog in both themes. |
| `scripts/ui_baseline.py` | Measures start-up, tab switches and the heaviest interactions. |
| `docs/ui/screenshots/before/` | The 56 screenshots (the welcome page and 27 views per theme) the harness made from `examples/microsat_250kg_eps` at 1400 × 860. |

Re-run: `QT_QPA_PLATFORM=offscreen python scripts/ui_screenshots.py docs/ui/screenshots/before` and
`QT_QPA_PLATFORM=offscreen python scripts/ui_baseline.py`.

## 1. Read this first: what is different from the brief

The brief was written for "SystemDesignStudio". This repository is **System Budget Studio** (power, mass,
thermal and link budgets of one spacecraft). I applied the brief to this application, because it is the
one in this repository. Where the brief names things this application does not have, the plan says so:

| The brief says | Here |
|---|---|
| Plotly template, bundled JS, WebEngine | Not applicable. The app has no web engine; plots are drawn with `QPainter` (`plot_widget.py`, `timeline.py`). The "Plotly template" becomes the plot styling in the theme. |
| Diagram canvas, trade tables, baselines, requirements | Not in this application. Their nearest equivalents are the budget tables, the Compare page and the scenario timeline strips. |
| "Remove Carbon completely (stylesheet, tokens, IBM Plex, docs references)" | The window's theme **is** IBM Carbon (white and g100 tokens, IBM Plex), and the 1.1.0 redesign built on it. But IBM Plex and the Carbon blue are also used by the **exported files** (PDF, DOCX, XLSX, PNG plots, the user guide), and the brief forbids changing outputs. See question 2. |
| "All existing tests, incl. goldens, pass unchanged" | True for the core, CLI and goldens. About six GUI tests pin the current look (IBM Plex families, Carbon hex values in the timeline strips, the DESIGN page quoting the tokens). See question 3. |
| Per-project layout (if the brief implies it) | The privacy rule D-150 allows one `layout.ini` with four fixed groups and no project names. See question 5. |

## 2. Purpose, users and workflows (please confirm or correct)

This is what the code, the SPEC and the 1.1.0 UX audit say. I will design for it unless you correct it.

**Purpose.** A systems engineer of a 100–500 kg spacecraft keeps one model of the spacecraft in plain
files and gets the power, mass, thermal and RF-link budgets from it, with every number traceable to a
source and every missing source visible (`n/a`, "not checked"), fully offline.

**Users.**
1. *The systems engineer* (primary): builds and edits the model, runs the budgets, reads the margins, fixes problems, exports reports for a review. Works for hours, mostly with tables, mostly on one or two monitors, mostly with a keyboard.
2. *The reviewer / customer engineer*: opens a finished project, reads the budgets and the provenance, compares two revisions or scenarios, exports. Does not edit.
3. *The first-time user*: needs a project to exist; uses the guided wizard and the welcome page.

**Core workflows (in the order the window should favour them).**
1. **Open or create a project** → see at once whether it is valid and whether it is "complete" (no placeholders).
2. **Edit the model** (units, power modes, sourced inputs, scenario rules) in grids, with undo, explicit save, and the Problems list next to the cell.
3. **Run** (all budgets for one scenario, BOL/EOL) → read the **margins and violations** per budget; jump from a violation to the input that causes it.
4. **Inspect the power timeline** (a day to a week at 1 s): zoom, pan, cursor readout, violation stepping.
5. **Compare** two revisions or two scenarios → what changed, by how much.
6. **Export reports** with provenance (XLSX, PDF, DOCX, JSON, CSV).
7. **Fix a problem**: Problems → file and line, or the grid cell.

What I will *not* add: accounts, cloud, telemetry, a recent-projects list (D-150: a path is project content), network anything.

## 3. Baseline measurements

Linux container, `offscreen` Qt, device pixel ratio 1, 1400 × 860, PySide6 6.8.3, Python 3.13. Numbers compare
before and after on this machine; they are not absolute. Script: `scripts/ui_baseline.py`.

| What | Before |
|---|---|
| Start-up, imports (`budget_gui`, PySide6) | 688 ms |
| Start-up, QApplication + fonts + theme + `MainWindow` shown and painted | 475 ms |
| **Start to first interactive window (after the interpreter)** | **1,163 ms** (median of 5 fresh processes) |
| Open `microsat_250kg_eps` | 611 ms |
| Run (a day: environment, timeline, link passes) | 533 ms |
| Tab switch, 7 tabs, project of 18 units (median of 3) | Model 46, Power 26, Mass 26, Thermal 17, Link 61, Compare 14, Reports 21 ms |
| Open `stress_200_units` | 3,315 ms (wall time including the background load) |
| Tab switch, 200 units | Model 59, Power 33, Mass 41, Thermal 22, Link 13, Compare 14, Reports 17 ms |
| Scroll the 200-unit grid, 40 steps | **2,241 ms (56 ms a step)**: the slowest everyday interaction |
| Run, a week at 1 s | 10.6 s; the longest stretch the window did not answer events: **350 ms** |
| Timeline plot, week at 1 s | full repaint 3 ms (cached layer); wheel-zoom step median **45 ms**, worst 63 ms |

Reading: everything but three items is already inside 100 ms. The three to watch are the grid scroll
(56 ms/step is ~18 fps), the 3.3 s open of a 200-unit project, and the 350 ms stall when a week's results
are delivered to the tables. The overhaul must not make any of these worse, and should bring the grid scroll
below 33 ms a step (milestone M3).

**Acceptance for performance, used in every milestone:** start-up ≤ 1.2 s; tab switch ≤ 100 ms (target ≤ 50);
plot zoom/pan step ≤ 50 ms median; grid scroll ≤ 33 ms a step; no stall of the window thread over 100 ms
while a job runs (350 ms today, fixed in M4); no regression over 10 % elsewhere.

## 4. Inventory

### 4.1 Windows, tabs, panels (what exists today)

`MainWindow` (`main_window.py`, 1,159 lines) with a menu bar, a **top bar** (project name and revision, scenario,
BOL/EOL, Run/Cancel with progress, status chip), two **banners** (stale, failed), a **7-tab workspace** and
four **docks** (Project left; Inspector, Problems, Provenance tabified on the right), a status bar.

| Tab | Sub-tabs / content | Module |
|---|---|---|
| Model | Units, Power modes, Inputs (grids); Scenario (timeline strips + rules form + Eclipses, Passes, Mode timeline tables); one closable tab per open YAML file | `grid_view.py`, `model_pages.py`, `scenario_view.py`, `scenario_editor.py`, `editor.py` |
| Power | Budget (report tables) · Timeline (3 stacked plots + Summary, Violations, Orbits, Modes tables) | `widgets.py`, `timeline_view.py`, `plot_widget.py` |
| Mass | Summary, Phase launch/bol/eol, Assumptions, Provenance | `widgets.py` |
| Thermal | same pattern | `widgets.py` |
| Link | Budget (tables) · Passes (plots + tables, volume) | `widgets.py`, `link_view.py` |
| Compare | two sides, filter, difference table | `compare_view.py` |
| Reports | provenance, items × formats, folder, results | `reports_view.py` |
| (no project) | Welcome page | `welcome.py` |

**Dialogs and floating windows (9 kinds):** command palette (`command_palette.py`), cell-style legend
(`legend.py`), user guide (`help_view.py`), paste preview (`grid_view.py`), guided wizard (`guided.py`, 4+ pages),
message boxes (19 `QMessageBox` calls: information, warning, question, critical), 7 folder pickers
(`QFileDialog`, native), the crash dialog (`app.py`), menus.

**Menus:** File (guided new, open, save, reload, edit power modes, three exports, unit table import/export,
quit), Edit (undo, redo), Run (run all), View (palette, Go to 1–7, theme, dock toggles, reset layout, cell styles),
Help (user guide).

### 4.2 The style system today

- One module, `theme.py` (598 lines): `Tokens` (43 colour and metric fields), `LIGHT` (Carbon white) and `DARK` (Carbon g100), the
  `QPalette`, **one 4.8 KB style sheet**, `ThemeManager` (light, dark, system, live switch, plots repaint).
- Scales: spacing 4/8/12/16/24/32 px; type 12/13/16/20 px; fonts IBM Plex Sans and Mono, bundled and loaded with
  `QFontDatabase`.
- Icons: 36 Lucide icons as black PNG masks (3 sizes), tinted at creation; re-tinted on theme change.
- Enforced by tests today: no colour literal and no `setStyleSheet(` outside `theme.py`; contrast 4.5 : 1 of every
  text colour on its surfaces in both themes; sizes only from the scales for margins.

### 4.3 What is hard-coded outside the theme

| Kind | Count | Where |
|---|---|---|
| Hex colour literals | **0** (test-enforced) | – |
| `setStyleSheet(` | **0** outside `theme.py` | – |
| Font literals | 1 | `editor.py:61` `QFont("IBM Plex Mono", 10)` (points, not pixels) |
| `ui_font/mono_font` and derived fonts | 14 references | `delegates.py`, `problems_panel.py`, tables |
| Pixel sizes (`setFixed*`, `setMinimum*`, `setMaximum*`, margins, spacing, icon sizes, column widths) | 50 lines; 27 are margins/spacing | `top_bar.py` 7, `reports_view.py` 5, `plot_widget.py`, `timeline.py` (painter constants `TOP`, `BOTTOM`, `ROW`, `GAP`), `legend.py`, `scenario_editor.py` |
| Hex colours in the **core** that the window re-maps | 13 | `budget_core/plots/spec.py` → `_CORE_TO_DARK` in `theme.py` |

So the existing theme module is already the single place for colour. What is missing relative to the brief:
a theme **package**, the Inter/JetBrains Mono fonts and the 11/12/13/15/18/22 scale, the 28/32 px control heights
and 6/8 px radii (Carbon is square), the motion rules, the UI-scale setting, and a test that also catches
**fonts and pixel sizes** outside the theme.

### 4.4 Work on the window thread, and big tables

- Background `QThread`s already exist for load (`session._LoadWorker`), the power timeline, the scenario, the link
  passes, compare and export. Cancel exists since 1.1.0 (`RunControl`, D-167).
- Work that still runs on the window thread: delivering results into `QTableWidget`s (the 350 ms stall above),
  building the project tree, building the grids (`GridModel`, 200 units ≈ the part of the 3.3 s after the load),
  `session.py:227` and `main_window.py:1148` call `processEvents()` in loops (load wait, close wait).
- `QTableWidget` (item-based) is used in **17 places**: timeline (4 tables), scenario (3), link (2), compare (1,
  up to ~1,000 rows in the screenshot), reports (2), provenance, paste preview, plus `QListWidget` in the palette,
  Inspector and scenario sites. Model/view is used for the grids (`GridModel`, `GridProxy`) and the budget
  report tables (`DocTableModel`). None of the item-based tables holds more than about 1,000 rows today; migrate
  the compare table only if measured slow (M5).

## 5. Findings by screen

Screenshots are in `docs/ui/screenshots/before/` as `NN-name-light.png` / `NN-name-dark.png` (the dark set
starts at 30). Severity: **A** blocks reading or hides data; **B** noticeable roughness; **C** polish.

### Shell (all screens, e.g. 09, 10, 14)

| # | Finding | Sev | Shot |
|---|---|---|---|
| S1 | **Three levels of tabs** on the Power and Link pages (workspace tab → sub-tab → result tabs: Power > Timeline > Summary/Violations/Orbits/Modes) and two on the others. The three bars look different (boxed, underlined, document-mode). | B | 09, 10 |
| S2 | **The right dock is 290 px wide and the Problems list wraps every message into 4–5 lines**: two problems are visible at a time; "Class" header and "Filter" box are cut ("Fil…"). The place where the most important information lives is the hardest to read. | A | 09, 17 |
| S3 | The central area gets ~700 of 1400 px when both docks are open, so wide tables scroll sideways (see Compare). | A | 14 |
| S4 | The project tree and Problems docks are visible but empty on the welcome page. | C | 01 |
| S5 | The top bar truncates the project name ("Example 250 kg minisatellite, com…") and mixes button styles (BOL/EOL segmented, Run filled, others outlined). | B | 09 |
| S6 | The tree shows a thick blue focus frame; focus rings are unequal between widgets (tree vs combos). | C | 09 |
| S7 | No navigation rail; navigation is tabs + Ctrl+1…7 + palette. Menus carry the actions. | – | all |

### Welcome (01, 02)
Centred title, two buttons, a hint line. Good content, large empty areas and the two empty docks (S4).

### Model > Units / Power modes / Inputs (03–05, 30–32)
Real grids with undo/redo/save. Findings: (M1) many columns, horizontal scroll with the identifier column not frozen; header carries units in brackets ("mass_kg [kg]") in the same weight as names; (M2) **Undo/Redo/Cell styles/Save are at the bottom, far from the table**, below the fold on small windows; (M3) the filter box is a line of grey text with no icon; (M4) 56 ms per scroll step on 200 units (section 3); (M5) problem markers only in the tree and the Problems dock, not in the cell row.

### Model > Scenario (06, 33)
Timeline strips on top, rules as sentences below. Findings: the saturated categorical mode colours (purple, magenta, teal) are the loudest thing in the window and unrelated to the rest of the palette; the time axis' last label is cut ("1…"); rule rows use text buttons "Up / Down / Remove" ×N (noise; icon buttons would do).

### Model > YAML editor (07, 34)
Plain monospace editor with line gutter. No search, no problem markers. Works; restyle only (font, gutter, selection).

### Power > Budget, Timeline (08, 09, 35, 36)
The timeline is strong (legend, markers, axis switch, violation stepping). Findings: three stacked plots take the whole height so the **Summary table below shows one row** ("BOL") and clips its columns; the toolbar mixes outlined and filled buttons and unlabelled ◀ ▶; plot grid, strips and bands are drawn in the hard Carbon palette (readable in both themes, 140-alpha bands in dark look muddy). Plots: axis labels and legends are 12 px; hit areas of legend entries are small.

### Mass, Thermal (10, 11, 37, 38)
Report tables with status cells and limit bars. Findings: the **INCOMPLETE banner is a bold red paragraph across the whole width**; the "Body frame: …" paragraph is one unwrapped line that runs out of the viewport; sub-tabs "Phase launch / bol / eol" are tabs where a segmented control would be enough; tables are left-aligned islands with a lot of empty space on the right.

### Link > Budget, Passes (12, 13)
Same table pattern; Passes has three tall plots and a one-row table at default size (same shape as Power > Timeline).

### Compare (14, 42)
Good: A/B labels, filter, tints. Findings: **the "Row" and "Quantity" columns take most of the width and push the A and B value columns out of the viewport**, so at 1400 px you must scroll sideways to see the numbers the page exists for (A); change column is also off-screen; the status message wraps into a 2-line sentence beside the buttons; the row tints (pink, yellow, lilac) are strong and unrelated to the status palette.

### Reports (15, 16, 43)
Clear structure. Findings: the provenance table repeats what the Provenance dock shows; the results table is empty but takes a third of the page; "Browse…" and the folder field are not aligned with the checkbox column.

### Docks: Inspector, Problems, Provenance (16–18, 44–46)
Inspector is a white column with a heading and a boxed list — mostly empty. Provenance values are truncated ("System Budget Stud…") in a 2-column table that cannot be widened without resizing the dock. All three share one narrow column (S2).

### Menus and dialogs (19–29, 47–56)
Menus are themed but plain; the palette is a plain list of "Menu > Item  [shortcut]" strings ("[menu]" where there is no shortcut), without icons or section headers; the message box (28) uses a blue "?" icon and two filled blue buttons with no hierarchy; the guide dialog (26) is an unstyled text browser with one small button under it; the wizard (29) is a 500 × 350 `QWizard` in Qt's modern style (header line, thin rule, three different button styles); the paste preview and cell legend use plain tables.

### Cross-cutting
- Two focus conventions (blue frame on the tree and the palette field, blue underline on tabs) and no consistent **focus ring**.
- Interactive controls are 24–30 px high in different places (combos, buttons, line edits): the brief asks for 28/32.
- Light and dark both pass the contrast test today; the dark plot bands and the compare row tints are the first things to review visually.
- UI scale: the window follows the OS DPI scale only; there is no 100/110/125/150 % setting.

## 6. Design language to implement (from the brief, mapped to this repository)

| Item | Brief | Today | Change |
|---|---|---|---|
| Fonts | Inter (UI), JetBrains Mono (numbers, code); bundled, `QFontDatabase` | IBM Plex Sans/Mono | New files in `assets/fonts/` (static Regular, Medium, SemiBold; Mono Regular, Medium; all SIL OFL); `LICENCES.md`, SBOM, `licence_check.py`. IBM Plex stays **only** for exported documents (question 2). |
| Type scale | 11/12/13/15/18/22 px | 12/13/16/20 | New scale in the theme package. |
| Grid, heights | 4 px grid; controls 28/32; rows 26 | spacing scale 4…32; controls 24–30; rows ~26 | Centralise `CONTROL_H`, `ROW_H`. |
| Radii | 6/8 | 0 (Carbon) | New radii in the style sheet; custom-painted widgets use the tokens. |
| Colour | tokens table, dark and light | Carbon tokens | New token set (neutral grey-blue surfaces, one accent, status set kept as semantic names: pass/near/fail/not checked/placeholder). Status stays icon + text + colour. |
| Icons | Lucide | Lucide (36 as masks) | Keep; add what the shell needs (rail icons). |
| Motion | 120–180 ms | none | Only for panel show/hide, hover/press, toast; **off** under `QT_QPA_PLATFORM=offscreen` and a "reduce motion" setting. |
| Theme | follow OS, live switch | exists | Keep; the rail's settings popover is the second entry point. |
| UI scale | setting | none | `theme/scale` (100, 110, 125, 150 %) in `layout.ini` (the `theme` group is allowed). Fonts and metrics scale; icons use the existing 3 mask sizes plus a larger one if needed. |
| Contrast | WCAG 2.2 AA test | 4.5 : 1 test exists | Extend: 3 : 1 for UI components and focus ring, all tokens × all surfaces, both themes. |
| Enforcement | test fails on hex/font/px outside theme | colour and `setStyleSheet` only | Add font family/size literals and pixel-size literals (allow-list for painting code with a comment). |

New code layout (M1): `budget_gui/theme/` (`tokens.py`, `scale.py`, `fonts.py`, `qss.py`, `manager.py`, `plots.py`),
`budget_gui/components/` (button variants, chip, card, empty state, toast, message dialog, segmented control,
section header, key-value list), and a developer-only "gallery" window script (`scripts/ui_gallery.py`) that
shows every component in both themes, used for screenshots and smoke tests.

## 7. Proposed information architecture

```
┌ menu bar (kept: File Edit Run View Help; every item also in the palette) ───────────────────────┐
├ top bar ─ project · revision · scenario ▾ · BOL|EOL · [Run / Cancel + progress] · chip · ⌘K  ────┤
│ rail │ side panel   │ workspace (one page at a time)                     │ inspector (right)     │
│ 56px │ (Project     │  page header: title · segmented sub-pages · actions │ Inspector | Provenance│
│      │  tree, toggle│                                                     │ (collapsible, 320 px) │
│      │  Ctrl+B)     │                                                     │                       │
├──────┴──────────────┴─────────────────────────────────────────────────────┴───────────────────────┤
│ Problems panel (bottom, resizable, collapsed = the one-line summary) │ status bar: path · run · v  │
└────────────────────────────────────────────────────────────────────────────────────────────────┘
```

Mapping of every current element:

| Today | New place | Notes |
|---|---|---|
| Tabs Model, Power, Mass, Thermal, Link, Compare, Reports | **Left rail**, 7 icons with labels in tooltips and optional text, Ctrl+1…7 unchanged | One level of navigation instead of tabs. |
| Sub-tabs Power: Budget · Timeline; Link: Budget · Passes; Model: Units · Power modes · Inputs · Scenario | **Segmented control in the page header** | Max one sub-level. |
| Mass/Thermal sub-tabs: Summary, Phase *, Assumptions, Provenance | Page header segmented control (Summary · Phases ▾ · Assumptions); **Provenance moves to the right inspector** (it already is a dock) | Removes the third tab bar (S1). |
| Result tabs of the timeline (Summary, Violations, Orbits, Modes) | Resizable bottom pane of the page with a segmented control; **collapsible** so the plots can have the page | Fixes the one-row summary. |
| Project tree dock (left) | Side panel next to the rail, toggled by the rail's top button and Ctrl+B; open by default on Model | Keeps unit selection and badges. |
| Inspector, Provenance docks (right) | One right panel with two pages; toggle in the top bar | Selection-driven, as now (`show_cell`). |
| Problems dock (right) | **Bottom panel** (full width, one line per problem), filter + grouping kept, jump to file/line kept; the status bar's "10 not checked" link opens it filtered | Fixes S2. |
| Top bar | Same contents; project name gets the space it needs; ⌘K field replaces the unlabeled shortcut | Run/Cancel unchanged (D-167). |
| Banners (stale, failed) | Inline banner component under the top bar, same texts | |
| Status bar | Same segments (path, last run, version, project state) | |
| Welcome page | The workspace with no project: same content, no empty panels | |
| Command palette (Ctrl+K) | Overlay card centred in the window; sections (Navigate, Run, File, View, Units, Problems); icons; shortcut chips | Command list unchanged. |
| Cell-style legend dialog | Popover from a "Cell styles" help button in the grid header | Dialog kept as fallback. |
| User guide dialog | Dialog, restyled (HTML is the guide's own CSS and is not changed, it is an output) | Question 2. |
| Paste preview | Themed dialog | |
| Guided wizard (`QWizard`) | Themed dialog with a step indicator; same pages, same answers object | Logic untouched. |
| 19 `QMessageBox` calls | One themed message dialog component (title, text, one primary and one secondary button, destructive style) | `QFileDialog` stays **native** (privacy: D-150). |
| Menus | Kept; every item has a palette entry and an icon where it has one on screen | |
| Theme menu | Menu **and** a rail-footer popover (theme, UI scale, reduce motion) | |

Responsiveness rules (from the brief, with the numbers): window minimum stays ≤ 1200 × 650 (test exists, UX GUI-24 for
1366 × 768); below 1280 px the right panel becomes an overlay; below 1100 px the side panel too and the rail shows icons only;
tables keep the key columns (identifier, quantity, A, B) frozen/prioritised so the data columns are never the ones pushed out
(Compare finding).

## 8. Milestones and acceptance criteria

Each milestone is one PR (or two small ones), all existing tests green except the ones listed under question 3,
docs and CHANGELOG updated, before/after screenshots added under `docs/ui/screenshots/`, performance numbers re-measured
with `scripts/ui_baseline.py`. I do not merge, tag or publish.

**M1 Foundation**
- `theme/` package with tokens (dark, light), type/space/radius/control-height/motion scales, fonts (Inter, JetBrains Mono bundled and loaded; added to licence report and SBOM), QSS generator, `ThemeManager` (OS-follow, live switch), UI-scale setting in `layout.ini`.
- Carbon removed from the window: tokens, style sheet, comments, `DESIGN.md`, `ux-audit` references updated (history kept where it is a record), D-entry for the removal; IBM Plex remains only where exported files need it (pending question 2).
- Component library (`components/`) with the gallery script; plots take their colours from the theme (QPainter).
- Tests: contrast test (all tokens on all surfaces, 4.5 : 1 text, 3 : 1 UI parts and focus ring, both themes); hygiene test (no hex, no font family/size literal, no pixel literal outside `theme/` and a short, commented allow-list for painting constants); smoke test of every component in both themes.
- Acceptance: the old window still runs unchanged in behaviour with the new tokens applied (visual change only); full test suite green; no change to core/CLI/golden files; start-up ≤ 1.2 s.

**M2 Shell**
- Rail, page header with segmented sub-pages, side panel (tree), right inspector, bottom Problems panel, status bar, top bar, banners, welcome as "no project" state, palette overlay, themed message dialog, settings popover; layout persisted in the allowed `layout.ini` groups only.
- Every item of the mapping in section 7 present; Ctrl+1…7, Ctrl+K, Ctrl+B, F1, F5, Ctrl+R still work (the keyboard-walk test passes).
- Acceptance: each tab/sub-tab/dialog of section 4.1 reachable and screenshot-tested (both themes); minimum window test; no sideways scroll at 1366 × 768 on any page except tables that are meant to scroll; tab switch ≤ 100 ms.

**M3 Model screens** — Units, Power modes, Inputs grids; scenario editor and strips; YAML editor; tree and badges.
- Toolbar above the grid (Undo, Redo, Filter, Cell styles, Save), frozen identifier column, row height 26, problem marker in the row, grid scroll ≤ 33 ms a step on 200 units (measured).
- Scenario: icon buttons, mode colours from the categorical token set, axis labels not cut.
- Acceptance: all grid/undo/paste/fill-down tests unchanged and green; keyboard walk unchanged.

**M4 Results screens** — Power budget and Timeline, Mass, Thermal, Link, Passes.
- Plots restyled (grid, strips, bands, legend, hover, axes) from the tokens in both themes; summary pane collapsible; status cells and limit bars on the new tokens; INCOMPLETE banner becomes the inline banner once per page; long text wraps.
- Delivering a week's results no longer stalls the window thread over 100 ms (build tables in chunks or models).
- Acceptance: plot interaction tests unchanged; zoom/pan ≤ 50 ms; the 350 ms stall below 100 ms.

**M5 Compare, Reports, dialogs** — Compare, Reports, Problems panel details, Inspector/Provenance, guide, wizard, paste preview, legend.
- Compare: key columns always visible; tints from the status/diff tokens; Reports: no duplicate provenance table; empty states.
- Acceptance: compare/reports/wizard tests unchanged and green; the timed wizard test stays.

**M6 Final**
- Accessibility pass (focus order, focus ring, names for screen readers on custom widgets, reduce motion), UI scale 100–150 % screenshots, HiDPI check list added to `INSTALL_CHECKLIST.md` (manual, yours), docs: `DESIGN.md` rewritten, user-manual screenshots replaced, `CLAUDE.md` gets the design rules, `DECISIONS.md` entries, `CHANGELOG.md`.
- Version **1.2.0** (next minor; goldens carry the tool version, so the 76 golden files change in their version line only, as in 1.1.0), release PR in the same way as 1.1.0.
- Acceptance: all tests green on Windows and Linux CI; before/after screenshot set complete; baseline table re-measured and no item worse than section 3.

## 9. Risks

| Risk | Plan |
|---|---|
| about 500 GUI tests, many assert behaviour and some assert the current look. Large visual change → churn. | Change look in M1 behind the tokens first; list every test that must change (question 3); no behaviour change in the same PR as a restyle. |
| The brief and "no output changes" meet in IBM Plex and the Carbon blue of exported files. | Question 2; default: GUI only, outputs untouched. |
| Custom-painted plots and strips do not follow QSS. | They already read tokens; they move to the new tokens in M1/M4; a repaint on theme change exists and is tested. |
| QSS with radii/heights is slow or inconsistent across platforms (Windows, Rocky 8 offscreen). | Keep the style sheet small (4.8 KB today); measure start-up each milestone; check Windows in CI (offscreen) and your manual list (real screen). |
| Fonts: Inter/JetBrains Mono metrics differ from Plex; column fits and tests with fixed widths may shift. | Table fit tests exist (`test_budget_table_fit.py`); re-run, adjust expectations by intent. |
| Left rail + bottom Problems panel changes the geometry the minimum-window test relies on. | The test stays; responsiveness rules above. |
| 1.1.0 manual checks are still pending on real machines, a 1.1.1 may be needed while the overhaul is open. | Overhaul on its own branch from `main`; hotfixes for 1.1.1 are small PRs from `main` and merged into the overhaul branch. |
| Animations in tests / offscreen. | Disabled when `QT_QPA_PLATFORM=offscreen` and with reduce motion. |
| Real-screen and HiDPI behaviour cannot be verified here. | Added to the install checklist in M6, as in 1.1.0. |
| Qt non-native dialogs would write folder names to `~/.config`. | Keep `QFileDialog` native; D-150 test stays. |
| New fonts add size (≈ 1 MB) to the installers. | Static weights only, subsetting not needed; recorded in the SBOM and checked in the licence report. |

## 10. Questions for you

Answer by number. Where I wrote a default, I will take it if you reply "use the defaults".

1. **Which project is this for?** The brief names SystemDesignStudio; I applied it to **System Budget Studio** (this repository). *Default: yes, this repository.*
2. **"Remove Carbon completely" vs "no output changes".** The GUI theme is Carbon. IBM Plex and the Carbon colours are *also* in the PDF, DOCX, XLSX, PNG plots and the user-guide HTML/PDF, and the goldens fix their bytes. *Default: remove Carbon from the whole window, its code, comments and docs; keep IBM Plex and the plot colours in exported files unchanged (they are an output format, not the UI), record that in DECISIONS, and keep the Plex font files and licence for that purpose.* The alternative (also restyle the outputs) breaks the "outputs unchanged" rule, regenerates goldens, and needs your explicit OK.
3. **Tests that pin the look.** About six GUI tests assert the old look (IBM Plex families in `test_window.py`, Carbon hex in `test_timeline_widget.py`, the DESIGN page quoting the tokens, the scale test in `test_theme.py`). *Default: update those, keeping their intent (the font that is loaded, the colour of the strips comes from the tokens, the design page matches the code), and list them in the M1 PR; every other test stays unchanged.*
4. **Purpose, users, workflows (section 2).** Correct as written? Anything missing, e.g. more reviewer-only use?
5. **Layout persistence.** Remember rail/panel state, theme and UI scale in the existing global `layout.ini` only (it may not name projects, D-150). *Default: global only, no per-project layout.*
6. **Problems panel at the bottom** (full width, one line per problem) instead of a right-hand tab. *Default: yes.* It is the largest single reading improvement and changes where people look for problems.
7. **Project tree as a side panel next to the rail** (toggle Ctrl+B) rather than hidden in the rail. *Default: yes.*
8. **Native menu bar kept.** The brief does not mention removing it. *Default: keep.*
9. **Dialogs.** Message boxes become themed in-app dialogs; folder pickers stay native. *Default: yes.*
10. **Version and goldens.** Next minor is 1.2.0; its release PR regenerates the version line in the golden files, as 1.1.0 did (content unchanged). *Default: yes.* Say so if "goldens unchanged" must include that line.
11. **Order and stopping points.** *Default: M1 → M2 → … in order, one PR each, you review the screenshots after M1, M2 and M5; I stop after each PR and wait for you to merge.*
12. **Timing against the pending 1.1.0 checks.** Start M1 now on a new branch from `main` while your real-machine checks are pending? *Default: yes; a defect from your checks goes into 1.1.1 first.*

## 11. Progress

All 12 questions were answered "use the defaults". One deviation from the plan's wording: the UI-scale
steps are the brief's 90, 100, 110 and 125 % (the plan said 100 to 150 %).

| Milestone | State | Notes |
|---|---|---|
| Phase 1: audit and plan | done | PR #39 |
| M1 Foundation | done (PR #39) | D-168 to D-172; fonts, `theme/` package, tokens, style sheet, UI scale, reduced motion, `components/`, gallery, tests; Carbon removed from the window |
| M2 Shell | done (merged in PR #39) | D-173 to D-175; rail, bottom Problems panel, narrow-window rules, settings card, palette overlay, offline segment; one change to the plan: the message boxes stay Qt's, themed through the style (D-174) |
| M3 Model screens | done (merged in PR #40) | D-176, D-177; toolbar above the grids, frozen identifier column, problem marker in the row, cheaper cell painting (a grid scroll step about 30 ms), scenario icon buttons, tab close mark, tree rows of 26 px |
| M4 Results screens | implemented, awaiting your review | D-178; one inline banner, labelled toolbar, foldable table pane, plot sizes in the theme and at the UI scale, cheaper table fill; the stall is 229 ms, not under 100 |
| M5 Compare, Reports, dialogs | not started | |
| M6 Final | not started | |

**M1 as built, against its acceptance criteria**

- Theme package with tokens (dark and light), type, space, radius, control-height and motion scales, bundled Inter and JetBrains Mono, the style sheet generated at the UI scale, live theme switching: done (`src/budget_gui/theme/`).
- Carbon removed from the window: done; IBM Plex remains for exported files only (D-168).
- Components with a gallery: done (`src/budget_gui/components/`, `scripts/ui_gallery.py`, screenshots in `docs/ui/screenshots/m1/`).
- Tests: contrast over every token pair, colour-vision distance, no colour, font family or pixel size outside the theme package, smoke test of every screen and dialog in four theme and scale combinations: done. The four old tests that pinned the look (question 3) were rewritten with the same intent.
- No change to core, CLI, file formats or goldens: yes; nothing under `src/budget_core`, `src/budget_cli`, `tests/golden` or `tests/regression` changed; the only test outside `tests/gui` that changed is the bundle-check test, which now expects the new fonts and arrow images.
- Performance (`docs/ui/screenshots/m1/baseline.txt`): **start-up is 12 % slower** (1.11 s to 1.25 s, measured interleaved against the commit before; the plan's limit was 10 % and 1.2 s, so this misses it). The cost is the larger style sheet (building the main window takes 55 ms longer) and 50 ms more imports; the fonts load in 9 ms. Tab switches (14 to 97 ms), opening 200 units (3.4 s), the week at 1 s (10.0 s, 290 ms longest stall) and plot zoom (48 ms median) are within noise of the baseline. The start-up cost is carried into M2, where the tab bars the style sheet styles are replaced by the rail.
- Known limit: the pixel constants inside custom painters (plot margins, timeline rows, cell bars) are named module constants, not yet theme constants; they are redone with their views in M3 and M4 (D-169).

**M2 as built, against its acceptance criteria**

- Every item of the mapping in section 7 is in place except two, both recorded: the breadcrumb (the rail and the segmented control already say where you are, and the name of the project needs the room) and the in-app message dialog for the 19 `QMessageBox` calls (D-174: the same boxes, drawn in the look of the window, so no behaviour and no test changes).
- `Ctrl+1` to `Ctrl+7`, `Ctrl+K`, `Ctrl+B`, `F1`, `F5` and `Ctrl+R` work; the keyboard-walk test now also visits the rail and comes back.
- Every area, page and dialog of section 4.1 is reachable and screenshot-tested in both themes; new screenshots in `docs/ui/screenshots/m2/` include the shell at 1600, 1200 and 1000 px, the folded rail and the settings card.
- Minimum window: the existing test (1200 × 650 for every area) passes after two minimum heights were lowered (a plot panel 110 to 88 px, the Problems list 48 to 32 px).
- No sideways scroll of a page at 1366 × 768 apart from tables that are meant to scroll: not measured one page at a time; the screenshot at 1200 px shows none. This is the one criterion I could not close with a number.
- Tab switch 16 to 62 ms (limit 100); plot zoom 23 ms median; grid scroll 1.6 s for 40 steps (it was 2.2 s); start-up +8 % against the commit before the overhaul (1.29 s to 1.40 s interleaved, limit 10 %); `docs/ui/screenshots/m2/baseline.txt`.
- Tests: all 561 GUI tests pass (19 new in `tests/gui/test_shell.py`; the full suite was run before the last two test edits, which were run on their own), 1715 core tests unchanged. Tests changed in intent-preserving ways: the dock arrangement and layout keys (`test_docks.py`), the keyboard walk, and a plot test that now waits for the narrow window to settle.

**M3 as built, against its acceptance criteria**

- Toolbar above the grid (filter, the page's tools, Undo, Redo, Cell styles, Save as the one primary button), row height 26, frozen identifier column, problem marker in the row: done (D-176). The frozen column is a second read-only view of the same model and selection over the left edge; the keyboard stays with the main view.
- Grid scroll at most 33 ms a step on 200 units: **30 ms** (was 40; 20 % less, measured interleaved against the commit before, on a loaded machine; 29 ms on a quiet one). Cost found by profiling: a repaint draws about 155 cells and each asked the model for 4 to 7 roles through the proxy model; one `CELL_ROLE` call, cached fonts, cut texts and colours, and a column 0 that paints nothing under the frozen column (D-177). The test that guards it allows 100 ms so that a slow CI machine does not fail it.
- Scenario editor: icon buttons with tooltips and accessible names, rules as cards, the label at the right edge of the strips no longer cut (it is left out). Mode colours were already the categorical set (M1). YAML editor: gaps from the spacing scale (its font, gutter and selection colours were done in M1). Project tree: rows of 26 px, badge sizes from the scales. A file tab's close mark is the themed *x* (the style drew an orange box).
- All grid, undo, paste, fill-down, cell-style and keyboard-walk tests pass unchanged; 12 new tests in `tests/gui/test_model_screens.py`. All 573 GUI tests pass (26 min), core tests: see the PR.
- No change to core, CLI, file formats or goldens.
- Baseline (`docs/ui/screenshots/m3/baseline.txt`): the machine was slower than for M2 (start-up 2.0 s against 1.3 s), so only the interleaved comparison above is meaningful; the other items are within noise of M2 (tab switch 16 to 68 ms, plot zoom 35 ms median, the week at 1 s 10.8 s with a 257 ms longest stall).
- Seen, not fixed: in the dark screenshots of the harness the project panel is squeezed to about 80 px (also in M2's). It looks like a dock width lost after a theme switch in the harness, not the default layout; I will check it on the way into M4 and say if it is real.

**M4 as built, against its acceptance criteria**

- Plots restyled from the tokens: the colours were done in M1; M4 moves the painted sizes (margins, gaps, marker bars, strip rows) into the theme at the UI scale (`plot_metrics.py`), sets the labels in the small type size and the numbers in the mono font. The summary pane is collapsible (*Hide table*, `CollapseButton`) and gets 3/8 of the height by default instead of 1/4. Violation navigation is two labelled buttons.
- INCOMPLETE banner: the inline banner once per page (Power, Mass, Thermal, Link budget); the long *Body frame* line wraps. The sub-pages (*Phase launch / bol / eol*) were already a segmented control since M2.
- Zoom and pan at most 50 ms: 27 ms median, 32 ms worst (`docs/ui/screenshots/m4/baseline.txt`). A full repaint is 2 ms.
- **Not met: the stall of a week's results under 100 ms.** Measured the same way as in M1 to M3, the longest stretch is **229 ms** (257 ms in M3, 290 ms in M1). The work was measured by handler: the scenario view's `_done` is 117 ms before and 53 ms after, the timeline's `_done` 113 ms before and 40 ms after (its tables come in the next turn of the event loop), `fill_table` takes half the time. What remains is several handlers and the first paint of the week's plot arriving back to back in one turn of the event loop (about 160 ms in one iteration), each under about 60 ms. Splitting it further means giving the scenario tables, the Problems panel and the plot's first paint a turn each; I stopped here because it changes the order in which the window updates (a result is no longer complete when the signal that carries it arrives for the tables of the timeline) and the aim was a number, not a behaviour. Say if you want it done.
- Tests: all existing plot, timeline, thermal, link, cancel, last-good and audit tests pass unchanged; one test that pinned the look (the style sheet names the roles, which listed the old red banner label) now names the three banners; new tests in `tests/gui/test_results_screens.py`. Full GUI and core runs: see the PR.
- Screenshots in both themes in `docs/ui/screenshots/m4/`. No change to core, CLI, file formats or goldens.
- The squeezed project panel in the dark screenshots (seen in M2 and M3) was a real defect of M2, not of the harness: a narrow window squeezes the side panels and they stayed so when the window grew. Fixed (D-179) with a test; at the 1200 px minimum the project panel is still a sliver, which I did not change (see D-179). The screenshots of M4 were taken before the fix, so the dark ones still show it.
