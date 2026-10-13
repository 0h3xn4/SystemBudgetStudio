# UX/UI Standard — System Budget Studio

You are redesigning the UX/UI of **System Budget Studio**, an offline PySide6 desktop app
(plus CLI) that computes power, mass, thermal and link budgets for a small satellite from one
plain-text spacecraft model. The current UI is clunky, unintuitive and visually poor. Make it
feel like the review tool a systems engineer reaches for instead of a spreadsheet, without
changing any equation, file format or output file (outputs are byte-reproducible; keep that).

## The tool, as it exists
- Model: units with power modes, solar array, battery, radios, antennas; orbit (TLE or
  elements) and ground stations; scenarios with mode timelines built from rules and segments.
- Budgets: **Power** (per-mode averages/peaks with maturity + system margins; time-domain
  generation/demand/SoC/DoD over an orbit, BOL and EOL, violations time-stamped), **Mass**
  (roll-up, CoG, inertia, phases, limits), **Thermal** (dissipation per unit/subsystem/mode;
  steady-state nodes, hot/cold cases vs limits), **Link** (EIRP, path loss, G/T, C/N0, Eb/N0,
  margin at elevations and per pass; data rate that closes; volume per pass/day).
- Every number carries a **source**; unsourced numbers are **placeholders** and dependent
  results show **n/a**. Problems name file and field; double-click jumps to them.
- Also: comparison of two revisions or scenarios, guided wizard, unit-table CSV/XLSX
  round-trip with import preview, reports (XLSX/PDF/DOCX/CSV/JSON) with provenance.
- Known issue: panning a week at 1 s with many series is slow.
- Stack: PySide6, IBM Plex fonts already shipped.

## Non-negotiable principles
1. **Numbers are sacred.** Unit in every column header; fixed precision per column; tabular
   figures; the source and placeholder status of every input visible at a glance and in detail
   on hover/inspector. `n/a` is rendered distinctly from `0` and from empty.
2. **Margins are the point.** Margin and limit columns are visually primary; a broken limit is
   impossible to miss; a limit that *could not be checked* (placeholder upstream) looks
   different from pass and from fail.
3. **State is always visible.** Unsaved edits, results stale relative to the model, which
   revision/scenario is shown, BOL vs EOL, hot vs cold.
4. **Nothing silent.** Specific feedback for every action; undo for every edit
   (`QUndoStack`); destructive actions confirmed with a sentence naming the object.
5. **Keyboard-first.** Everything reachable by keyboard; shortcuts in menus; `Ctrl+K`
   command palette (open unit, run budget, jump to problem, export…).
6. **Density with hierarchy.** Review layouts, not wizards, for experts; the wizard stays
   for first use only.
7. **Fast.** <100 ms UI response; budgets run in a worker with progress and cancel.

## Target layout (app shell)
- **Top bar:** project name · revision · dirty marker · scenario selector · BOL/EOL toggle
  where relevant · **Run** (primary; runs all budgets or the current one) · run status chip.
- **Left panel:** project tree — Spacecraft (Units › modes, Solar array, Battery, Radios,
  Antennas), Orbit & Ground stations, Scenarios, Links. Problem badges (count, severity) on
  nodes; placeholder badge (count) on nodes with unsourced values.
- **Main area:** tabs *Model* (form for selected node) · *Power* · *Mass* · *Thermal* ·
  *Link* · *Compare* · *Reports*.
- **Right panel (dockable):** *Inspector* (field help, unit, source, placeholder toggle,
  allowed range, where this value is used) · *Problems* · *Provenance* of the shown result.
- **Status bar:** project path · last run time · tool version · "n/a: 3 results blocked by
  placeholders" link that filters the Problems panel.
- Dock layout saved in `QSettings`; View > Reset layout.

## Screen-by-screen

### Model editing (unit tables and forms)
- Units and their power modes edited in a **data grid**, not one dialog per unit: rows =
  units, columns = mode powers (W) with unit in header, mass (kg), dissipation (W), limits
  (°C), maturity, source. Inline editing, `Tab`/`Enter` navigation, `Esc` cancels, fill-down,
  paste from spreadsheet (TSV) with a preview, same as the existing import preview.
- **Placeholder cells:** italic + dashed border + hollow marker; tooltip "Placeholder — no
  source. Results depending on it show n/a." Right-click → *Mark as sourced…* opens the
  source field. A legend button explains the cell styles.
- **Source** column always present but collapsible; editing source is one click.
- Scenario timeline rules shown as readable sentences ("Downlink during every pass over
  Svalbard") with an add/edit sentence builder; segments shown on a small timeline strip.
- Validation on edit; message beside the field and in Problems; never a `QMessageBox`.

### Power
- Per-mode table (average, peak, margins, system margin) with a totals row and a
  margin-vs-limit bar inline per row.
- **Timeline plot** (generation, demand, SoC, DoD) with eclipse shading, pass markers,
  violation markers; shared cursor with a readout panel (every series at that time, with
  units); BOL/EOL as overlay or toggle; linked x-axes across sub-plots; legend click
  hides/solos; time axis in UTC, orbit number or elapsed time.
- Violations list under the plot: time-stamped rows; click → cursor jumps and the row is
  highlighted; "next/previous violation" buttons.
- Fix the slow panning: render with **pyqtgraph** (or downsample to display resolution,
  min/max per pixel bucket) so a week at 1 s with many series pans in <50 ms.

### Mass
- Tree-table (subsystem › unit) with mass, maturity margin, total with margin, CoG xyz and
  inertia; phase selector; limit row at the bottom with a margin bar. Group rows collapsible;
  totals visibly distinct (bold, top border).

### Thermal
- Dissipation table per unit × mode; node model table with hot and cold case side by side,
  each temperature coloured against the unit's limits (within / near / exceeded / not checked).
  A small node diagram is optional; the table must stand on its own.

### Link
- Classic link-budget ladder table per link (parameter, value, unit, source/derived), uplink
  and downlink side by side; elevation selector; margin row highlighted.
- Per-pass table (station, start, duration, max elevation, closing data rate, volume) with
  day totals; click a pass → highlight in the scenario timeline.

### Problems panel
- Columns: severity · message · file · field; group by severity or by file; filter box;
  double-click jumps and focuses the field; counts in the tree and status bar.
- Distinguish **error / warning / not-checked (placeholder)** by icon and colour.

### Compare
- Two revisions or scenarios side by side; a diff table (input changes old → new) and a
  results delta table (Δ column, sign-coloured, with "changed because of…" link to the input
  diff when derivable). Plots overlaid with distinct, stable series colours.

### Reports
- One page: choose budgets × formats, output folder, open after export; progress; the
  result list with paths and "Reveal in folder". Provenance block displayed before export.

### Guided mode (wizard)
- Keep it, but: a left-hand step list with completion ticks, back/next, a summary step, and
  "Open in full editor" at every step. Never the default for an existing project.

## Shared components and Qt rules
- Tables: `QTableView` + `QAbstractTableModel` with delegates for numbers, placeholders and
  margin bars; sticky headers; sort/filter via proxy model; `Ctrl+C` TSV; `Ctrl+A`; export CSV
  from the context menu; column widths saved.
- Forms: `QFormLayout`; label above or left-aligned consistently; unit suffix; help text.
- Long operations in a worker thread with a non-modal progress bar and Cancel.
- Empty states tell the user what to add ("No ground stations — add one to compute passes").
- Toasts for success (non-blocking); persistent banners for stale results and failed runs.

## Visual system
- One theme module generating `QPalette` + QSS; no scattered `setStyleSheet`, no hard-coded
  colours. Light and dark themes, OS default.
- IBM Plex Sans (UI) and IBM Plex Mono (numbers, IDs, file paths); tabular figures.
- Type scale 12/13/16/20 px; spacing 4/8/12/16/24/32 px.
- Status colours (pass / near-limit / fail / not-checked / placeholder) defined once,
  colour-blind safe, always paired with an icon or text. One accent for the primary action.
- SVG icon set (Lucide/Tabler), tooltips on every icon button.

## Anti-patterns to remove
- One dialog per unit / mode; modal editing; nested dialogs.
- Placeholders that look like real numbers; `n/a` that looks like empty.
- Margins buried in a column with the same weight as everything else.
- Plots with default matplotlib styling, no cursor readout, no eclipse/pass context.
- Results that can be stale without a banner.
- `QMessageBox` for validation or routine info; icon-only buttons; inconsistent sizes.
- Frozen UI while a budget runs.

## How to work
1. **Audit first.** Walk the demo `cubesat_3u_eps` through: open → edit a unit → run power →
   fix a problem → compare → export. Write `docs/ux-audit.md` (issue · severity · fix ·
   screenshot). Stop and wait for approval.
2. **Order:** app shell & tree & Problems panel → model grid & placeholder styling → Power
   view (incl. performance) → Mass/Thermal/Link tables → Compare/Reports → theme polish.
3. **One view per iteration**, before/after screenshots (offscreen render), one line per
   decision, then ask.
4. **Never change** equations, project file format, report layouts or reproducibility.
   The CLI must keep working unchanged.
5. **Acceptance per view:** keyboard-only · light/dark · placeholder-heavy project ·
   project with 200 units · week at 1 s · empty project · 1280×720 and 4K · tests green ·
   no hard-coded colours.
6. Maintain `docs/DESIGN.md` (tokens, cell styles legend, status colours, shortcuts).
7. If a budgeting convention is unclear (margin definitions, sign of DoD, EOL assumptions), ask.
