# UI overhaul: SystemDesignStudio

> **How to use:** save this file as `docs/ui/UI_OVERHAUL.md` in the repository, start Claude Code in plan mode (Shift+Tab) and send: *"Read docs/ui/UI_OVERHAUL.md and follow it. Do Phase 1 only, then stop for my review."* After approving the plan, run one milestone per session: *"Implement milestone M1 from docs/ui/UI_OVERHAUL_PLAN.md. Stop when its acceptance criteria pass."*

> **Fill in before use:** replace the bracketed paragraph under "Role and goal" with two or three sentences on what SystemDesignStudio does and who uses it. If you leave it, Claude Code will derive it from the code and ask you to confirm.

## Role and goal

You are a senior UI engineer working in the SystemDesignStudio repository. [What the tool does, which data it holds, who uses it, and which other tools it exchanges files with.]

Before planning, read `README.md`, `CLAUDE.md`, everything in the docs folder (in particular any SPEC, ARCHITECTURE, PLAN and DECISIONS files), and the entire GUI code. In the plan, start with a short description of the tool's purpose, users and main workflows as you understand them from the code and docs, and ask me to confirm it.

The GUI is PySide6 and, like the other tools of the suite, follows IBM Carbon. Users find it outdated, sluggish, cluttered, convoluted, raw and unattractive. Your job is a complete, comprehensive overhaul of the GUI's look, structure and responsiveness that fixes all of these, following the design language below, without changing what the tool computes or generates.

## Hard rules for this overhaul

- **UI only.** Do not change computation, core or engine behaviour, project/scenario file formats, CLI commands and flags, or any generated output file. Every existing test, including golden-file tests, must pass unchanged. If a UI improvement seems to need a core change, stop and ask me.
- **Stay on PySide6.** No rewrite into a web frontend, no Electron/Tauri, no third-party Qt theme packages (qt-material, qdarkstyle etc.). Build the theme ourselves from tokens.
- **Offline by design.** Bundle every font, icon and JavaScript asset (including plotly.js) inside the package. No network access at runtime, no CDN, no font or icon downloads.
- **Dependencies.** Prefer none. Anything new must be permissively licensed, pinned, added only to the GUI extra, and recorded in `docs/DECISIONS.md` and the SBOM/licence report. Keep heavy tooling out of the main dependencies.
- **Remove Carbon completely:** the Carbon stylesheet and tokens, IBM Plex fonts (unless there is a documented reason to keep them), and Carbon references in docs. Record the change in `docs/DECISIONS.md`.
- **Workflow.** Plan first, then one milestone per session. Write or update tests first where practical. Add the design rules below to `CLAUDE.md` so every later session follows them. Where this prompt is silent, pick the simplest option, record it in `docs/DECISIONS.md` with a one-line rationale and continue; where a choice affects workflows users rely on, ask.

## Design language

SpaceMissionStudio, SystemDesignStudio and HarnessDesignStudio must look and behave like one product family. The token values below are identical across all three repositories. If another tool of the suite already contains a finished theme package from this overhaul, ask me for it and reuse its tokens verbatim rather than re-deriving them.

**Character:** calm, dense, precise. The reference points are listed under Design references below: quiet neutral surfaces, crisp type, very few lines, colour only where it means something. Not a consumer app, not classic enterprise.

### Design references

Four sources define the target. Take the ideas listed for each and nothing else: copy no code, assets, icons or text from any of them, and add none of them as a dependency. If you have network access during development you may look at them for orientation; the finished tool never refers to them at runtime.

- **shadcn/ui — visual style only.** shadcn/ui is a React component collection for the web, so it cannot be used in a PySide6 app; we rebuild its look in Qt. Borrow: the neutral gray palette with one accent colour, Inter, 6–8 px corner radii, 1 px low-contrast borders, restrained shadows only on floating elements, compact but generous-feeling control proportions, and its clean component anatomy (buttons, inputs, tabs, badges, popovers, dialogs, toasts, command menu). The token table below is already derived from this style.
- **Linear — interaction and feel.** Borrow: the calm, uncluttered layout; the command palette (Ctrl+K) as the fastest route to every action and object; keyboard-first workflows with shortcuts shown in tooltips and menus; fast, subtle motion; instant feedback with optimistic updates where safe; inline editing instead of dialogs; and a restrained, precise typographic hierarchy.
- **Foxglove (and Rerun) — technical data presentation.** Borrow: dense, resizable panel layouts that users can arrange and that are remembered; dark-theme handling of plots and data; time-series plots with a time cursor linked across panels; compact monospace display of values, IDs and logs; and the sense that a lot of data is on screen without it feeling busy.
- **Astro UXDS — status and alerts.** Borrow: the status taxonomy used in the tokens (critical, serious, caution, normal, standby, off); the rule that status is always shown with colour plus an icon or text; status rolling up from child items to their parent so the most severe state is visible at the top level; and alert handling that separates transient notifications (toasts) from persistent, acknowledgeable problems (the Problems panel), sorted by severity.

Where these references conflict with each other or with the rules in this file, the rules in this file win.

### Principles

1. **Colour means something.** The interface is neutral. The single accent colour is used only for the primary action, selection and focus. Status colours are used only for status (high-performance HMI / ISA-101 approach), so an abnormal value is the only coloured thing on screen and is spotted in under a second. Status is always paired with an icon or text, never colour alone.
2. **Separate with surfaces, not lines.** Distinguish areas by background elevation and spacing. Borders are 1 px and subtle, used only for inputs, table headers and splitters. No boxes inside boxes, no group-box frames.
3. **Density with order.** Engineers want a lot on screen. Get there with a strict 4 px grid, consistent row heights and alignment, not by randomly shrinking padding.
4. **Precision.** Every number shows its unit (in the field suffix or the column header). Numbers are right-aligned with tabular figures. Significant figures are consistent per quantity. Timestamps are ISO 8601 UTC with `Z`. Values, IDs and table selections are copyable.
5. **Keyboard first.** Command palette, shortcuts for every frequent action (shown in tooltips and menus), visible focus everywhere.
6. **Never freeze.** See the responsiveness rules.

### Tokens

One source of truth: a theme package inside the existing GUI package (for example `<gui>/theme/tokens.py`). The QSS, the Plotly template, chart palettes and any on-screen diagram styling are generated from it. No hex colour, font family or pixel size appears anywhere else in GUI code; a test enforces this.

| Token | Dark | Light |
|---|---|---|
| bg.canvas | #0B0D10 | #F7F7F8 |
| bg.surface | #111418 | #FFFFFF |
| bg.raised | #171B21 | #FFFFFF (+ shadow) |
| bg.hover | #1D222A | #F0F1F3 |
| bg.selected | accent at 16 % | accent at 10 % |
| border.subtle | #222832 | #E4E5E9 |
| border.strong | #2E3540 | #D0D3D9 |
| text.primary | #E7E9EC | #16181D |
| text.secondary | #A1A8B3 | #50565F |
| text.muted | #7A828E | #7C838D |
| accent | #4C8DFF | #2563EB |

Status, following the Astro UXDS taxonomy (tune lightness per theme until text and icons pass contrast): critical #FF4D4F, serious #FF8A3D, caution #F5B83D, normal #3DD68C, standby #56B4F5, off = text.muted. Diff tokens, derived as tinted backgrounds: diff.added (normal), diff.removed (critical), diff.changed (caution). These starting values are a proposal; adjust only to meet WCAG AA, and record any change.

**Typography.** Inter for the UI, JetBrains Mono for numbers in tables, IDs, part numbers, code and logs. Both SIL OFL: bundle the font files and licence texts, register them at startup with `QFontDatabase`, never depend on system fonts. Sizes: 11 caption, 12 small and table, 13 body (base), 15 section title, 18 page title, 22 display (rare). Weights 400, 500, 600 only. Enable Inter's tabular figures (`tnum`) where the Qt version supports font features (Qt 6.7+); otherwise use JetBrains Mono for numeric columns.

**Spacing and shape.** 4 px grid (4, 8, 12, 16, 24, 32). Control height 28 px compact / 32 px default; table rows 26 px. Radius 6 px for controls, 8 px for panels, popovers and dialogs. Focus ring 2 px accent. Shadows only on floating elements (menus, popovers, dialogs, toasts).

**Icons.** Lucide (ISC licence), bundled SVGs, 16 px in the UI and 20 px in the navigation rail, tinted at runtime from tokens. One icon set only; replace all others.

**Motion.** 120–180 ms ease-out for hover, panel open/close and toasts. Never animate data values or plots. Respect a "reduce motion" setting.

**Themes.** Dark and light, following the OS by default with an override in Settings, switchable live without restart.

### App shell

Adapt to the tool, but keep the same structure across the suite:

- **Left navigation rail** for the top-level areas: icon plus label, collapsible to icons only.
- **Top bar:** project name, save state and revision, breadcrumbs, and a global command palette (Ctrl+K) that searches commands, objects and settings.
- **Central workspace** with tabs and splitters; layout remembered per project.
- **Right inspector:** properties of the current selection, edited in place.
- **Bottom:** a status bar (background jobs with progress and cancel, last run, an offline indicator) and a collapsible **Problems panel** (severity, ID, object, message; click to jump to the source).
- Modal dialogs only for destructive confirmations and multi-step wizards. Everything else happens inline or in the inspector. Success feedback is a non-modal toast.
- Every list and table has an empty state: one line of explanation plus the primary action.

### Components

Standardise and reuse: buttons (primary, secondary, ghost, danger), text and number inputs with unit suffix and inline validation messages, segmented controls, tabs, status badges, toasts, determinate progress with cancel, split panes, empty and loading states, tree views, and **tables**: `QTableView` with a `QAbstractTableModel`, sortable and filterable, sticky header, right-aligned numeric columns with units in the header, copy selection as TSV (pastes cleanly into Excel), column-visibility menu, row hover, no zebra striping.

### Responsiveness

- Nothing longer than about 50 ms runs on the GUI thread. Simulations, generation, imports, file I/O and checks run in workers (`QThreadPool`/`QRunnable`, worker `QObject`s on a `QThread`, or `QProcess`), report progress, can be cancelled, and post results back through signals.
- Replace `QTableWidget`/`QTreeWidget` holding large data with model/view; batch model updates.
- Create heavy tabs and every `QWebEngineView` lazily; share one `QWebEngineProfile`; reuse views instead of recreating them; load the bundled plotly.js once.
- Debounce recomputation triggered by typing (about 250 ms).
- The GUI must remain fluid with WebEngine in software rendering (WSL2 with `QTWEBENGINE_CHROMIUM_FLAGS=--disable-gpu`): avoid WebGL by default where an SVG/canvas renderer suffices.
- Measure startup to first interactive window, tab switching and the heaviest interaction, before and after. Add an optional timing log in debug mode.

### Accessibility

WCAG 2.2 AA contrast for all text in both themes (automated test over token pairs), full keyboard navigation with visible focus, tooltips on every icon-only button, and support for OS scaling plus a UI-scale setting (90/100/110/125 %).

### Plots

A Plotly template generated from the tokens: Inter, transparent background over bg.surface, gridlines in border.subtle, axis text in text.secondary, axis titles always with units, and one 8-colour categorical palette that is colour-vision-deficiency safe and distinct from the status colours. Linked time cursors where several plots share a time axis.

## SystemDesignStudio specifics

Users are systems engineers. Apply the patterns below to whichever of these the tool actually contains; do not add features it does not have. Propose the navigation areas in the plan, typically Home, the main model or architecture, Budgets, Analyses or Trades, Baselines, Outputs and Settings.

**System breakdown / product tree.** Tree view with inline add, rename and reorder (drag and drop plus keyboard), the inspector for properties, search, and clear indication of where an element is used.

**Budgets** (for example mass, power, data, propellant, link, pointing). Dense tables with columns for basic value, margin, value with margin, allocation and status badge; roll-up totals pinned at the bottom; mode- or phase-dependent values as switchable columns. Margin policies and thresholds come from the project or config, never invented. Status colour appears only when an allocation or margin is violated.

**Diagrams** (block diagrams, N² matrices, architecture views). A canvas with zoom, pan, fit and click-to-select linked to the inspector, node and edge styling from the tokens on screen. Exported diagram files stay byte-identical unless I approve a change separately.

**Trade studies.** A comparison matrix with criteria, weights and scores, sorting, and the winning option highlighted with the accent, not a status colour.

**Interfaces to other tools** (for example HarnessDesignStudio or ICD Studio files). Imports through one consistent wizard (choose file, preview, validation, diff, accept), with the import source and date visible wherever imported data is shown.

**Baselines and versions.** History and a diff view using the diff tokens, with released baselines visibly locked.

**Suggested screen milestones:** M3 Home, M4 System breakdown, M5 Budgets, M6 Diagrams, M7 Trades and analyses, M8 Imports, Baselines and Outputs, M9 Settings. Adjust to the tool's real feature set in the plan.

**Version:** next minor release, with a CHANGELOG entry describing the new UI.

## Process

### Phase 1 — Audit and plan (no code)

1. Read the documents listed above and the whole GUI package.
2. Build a screenshot harness: a script that opens every window, tab and dialog with an example project and saves PNGs (offscreen, or under `xvfb-run` if WebEngine needs it) to `docs/ui/screenshots/before/`. Run it.
3. Inventory: every screen and dialog, every stylesheet and hardcoded colour, font and size, every place work runs on the GUI thread, every `QTableWidget` with potentially large data.
4. Measure the performance baseline described under Responsiveness.
5. Write `docs/ui/UI_OVERHAUL_PLAN.md` containing: findings per screen (what is cluttered, convoluted, sluggish or inconsistent, with screenshot references); the proposed information architecture (mapping every current tab, menu and dialog to its new place in the shell); the milestone plan with acceptance criteria per milestone; risks; and questions for me.
6. Stop and present the plan. Do not start implementing until I approve it.

### Milestones after approval

- **M1 Foundation:** theme package, tokens, generated QSS, bundled fonts and icons, live theme switching, Plotly template, the hardcoded-style test and the contrast test. Carbon removed.
- **M2 Shell:** navigation rail, top bar, command palette, inspector, status bar with job list, Problems panel, layout persistence, keyboard shortcuts.
- **M3 onward:** the screen milestones in the tool-specific section, one per session.
- **Final milestone:** performance pass against the baseline, accessibility pass, `docs/ui/screenshots/after/`, a short `docs/ui/BEFORE_AFTER.md` comparison, updated user guide screenshots, CHANGELOG entry and the version bump given above.

## Verification

- pytest-qt smoke test for every screen: opens with the example project in both themes, no exceptions, no warnings from Qt about stylesheets.
- Test that fails if a hex colour, font family name or pixel size appears in GUI code outside the theme package.
- Contrast test over all text/background token pairs in both themes.
- Screenshot harness rerun at the end of every milestone; mention noteworthy differences in the session summary.
- All existing tests green, golden files untouched, CLI behaviour unchanged.

## Definition of done

A user opening the tool sees a calm, modern, consistent interface in dark or light mode; finds every function through the navigation rail or Ctrl+K; never sees the window freeze; can tell the state of their work (saved, running, problems, released) at a glance; and gets byte-identical outputs to the previous release.
