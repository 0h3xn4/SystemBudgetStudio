# UX audit of the current window

Status: **approved; being implemented.** The owner approved the eight decisions and the five conventions ("as recommended"). Step 0 (foundation, D-150) and step 1 (the shell, D-151 to D-156) are done; [the status of each finding](#status-of-the-findings) is at the end. This page is kept as it was written; the table at the end says what changed.

**Contents:** [How this was done](#how-this-was-done) · [Verdict](#verdict) · [What to keep](#what-to-keep) · [Findings](#findings) · [Screenshots](#screenshots) · [Measurements](#measurements) · [Standard against the window](#the-standard-against-the-window) · [Conflicts with project rules](#where-the-standard-meets-the-project-rules-decisions-needed) · [Questions about conventions](#questions-about-conventions) · [Plan](#plan) · [Status of the findings](#status-of-the-findings)

## How this was done

The demo `examples/cubesat_3u_eps` was walked through the real `MainWindow` offscreen (Qt `offscreen` platform, 1400 × 860, device pixel ratio 1, Linux, PySide6 6.8): open → look at every tab → compute the scenario, the power timeline and the link passes → select a violation → open a unit in the table editor → open its YAML and break it (`bus: main` → `bus: nope`) → save → see what the window does → compare → the guided wizard. The same window was also looked at in the dark tokens, at 1280 × 720 and at 3840 × 2160. The code of all 21 modules in `src/budget_gui/` (5,142 lines) was read, and performance was measured on `stress_200_units` and on a week at 1 s.

All screenshots are in [`images/ux-audit/`](images/ux-audit/) and are linked from the findings (`S01` = `01-…png`).

**Not checked, and why:** a real display and real HiDPI (offscreen has a pixel ratio of 1, so 4K shows layout only, not text size); a screen reader; a colour-blindness simulator (the colours were read from the code); how the window looks under Windows. A person has to look at those once the redesign exists.

**Severity:** **S1** breaks a non-negotiable principle of the standard in the screen that matters most (the product's promise is not visible); **S2** a real obstacle for a systems engineer; **S3** rough; **S4** polish.

## Verdict

The window is **a correct viewer of the report tables with a competent plot**, not yet a review tool. Everything it shows is right (the numbers are the report numbers), and several pieces are better than they look (see [What to keep](#what-to-keep)). What is missing is the layer the standard asks for:

1. **The promise of the tool is invisible in the window.** Sources and placeholder status are not shown anywhere except as `n/a` in grey text and 6 `CONFIG_PLACEHOLDER` rows in the Problems list (UX-14, UX-21, UX-22). The unit editor has no source column at all.
2. **Margins are not the point of any screen.** A link margin of −0.32 dB, a mass limit, a battery depth of discharge: all are plain cells, same weight as everything else (UX-20, UX-28, UX-29).
3. **There is no shell.** No top bar, no Run, no revision, no scenario or BOL/EOL control shared by the tabs, no inspector, no badges on the tree. Each of four tabs has its own scenario combo and its own *Compute* button (UX-01 to UX-09).
4. **One error empties the whole window.** After one wrong bus name every budget and plot disappears and the tree forgets its unit names (UX-10, S12/S13).
5. **The keyboard is half-supported.** Enter does not open a tree item (verified), there is no command palette, no shortcut for a tab or for compute (UX-41).
6. **Visual system.** One light theme, 59 hard-coded colours, colour-only severity, and a dark token set that exists but cannot be chosen and leaves the plot white (UX-36 to UX-39, S15).
7. **Speed is mostly fine, with two exceptions:** zooming or panning a week at 1 s takes 184 to 373 ms per redraw (target: below 50 ms), and a week-long compute takes 8.6 s with no progress and no Cancel (UX-26, UX-43).

## What to keep

These work and the redesign must not lose them.

- **Every result is tied to its inputs** (`ResultKey`): results go stale when the project, scenario or a setting changes, and an out-of-date export is refused. The redesign should show this more loudly, not change it.
- **The timeline plot's interaction model**: hover cursor with a readout of every series and the spacecraft mode, a click pins a second cursor and the readout shows differences, wheel zoom around the pointer, drag to pan, double-click to reset, eclipse and pass shading. Hover now repaints in about 2 ms (D-147).
- **Double-click (or Enter) in Problems jumps to the file and line**, including list indices (`limits[0].limit_kg`).
- **Background loading and computing** in threads: the window never freezes (D-142); nothing is lost on close.
- **No unsaved-edit loss**: confirmations on close and on reload; files that changed on disk are detected.
- **YAML round-trip**: the table editors write only what was edited and keep comments and key order. Whatever replaces the editors must keep this byte-stability.
- **IBM Plex fonts and the Carbon tokens** are already shipped and used.
- **The wizard** produces a working first project; keep it for first use as the standard says.

## Findings

Columns: **ID** · what is wrong · **sev.** · principle of the standard (P1 numbers, P2 margins, P3 state, P4 nothing silent/undo, P5 keyboard, P6 density, P7 fast) · fix · screenshot.

### Shell, tree, panels

| ID | Finding | Sev. | Pr. | Fix | Shot |
|---|---|---|---|---|---|
| UX-01 | **No top bar.** Project name, revision, dirty marker, scenario, BOL/EOL, Run and a run-status chip do not exist. The window title carries the project name only. Four tabs each have their own *Scenario* combo (Scenario, Power timeline, Link passes, Compare) that must be kept in step by hand. | S2 | P3 | A top bar with one scenario selector and BOL/EOL (where relevant) shared by the tabs; project name · revision · dirty marker · Run · status chip. | S01, S07, S08 |
| UX-02 | **No *Run*.** Static budgets appear on load, but the scenario, the power timeline and the link passes each need their own *Compute* press, in an order the user must know (Scenario first). Four *Compute* buttons, four status texts. | S2 | P4, P7 | One primary **Run** (all, or the current budget) with a status chip; per-tab compute stays as a secondary action. | S06, S07, S08 |
| UX-03 | **The revision is shown nowhere** (`revision` in `project.yaml` labels comparisons and every report). | S2 | P3 | Show it in the top bar and on the Compare sides. | S01 |
| UX-04 | **Dirty state is a `*` after the tab title** of a file or unit editor, and nowhere else: not in the window title, the top bar or the tree. | S3 | P3 | One dirty marker model: top bar, tab, tree node, window title. | S11 |
| UX-05 | **The tree is a file tree, not a model tree.** It lists files and folders (`Configuration (8)`, `project.yaml`), unit ids, `Spacecraft modes (5)`; there are no nodes for solar array, battery, radios or antennas (they live inside `config/` and `spacecraft.yaml`). No problem or placeholder badges. Unit names are shown only when the project loads. | S2 | P1, P6 | Spacecraft (Units › modes, Solar array, Battery, Radios, Antennas), Orbit & Ground stations, Scenarios, Links; severity and placeholder badges with counts; names always shown. | S01, S12 |
| UX-06 | **Enter does not open a tree item** (verified by a scripted key press: the tree only listens to double-click, while the Problems table listens to activation). Arrow keys select, nothing opens. | S2 | P5 | Open on activation (Enter, double-click); `F2`/context menu for the rest. | S01 |
| UX-07 | **No inspector.** Nothing shows a field's help, unit, source, placeholder status, allowed range or where the value is used. The only way to see a source is to open the YAML. | S1 | P1 | Dockable Inspector fed by the model schemas (`budget_core/schemas`) and the file line map. "Where used" needs a read-only usage index from the core (see decisions). | — |
| UX-08 | **Only the Problems dock exists.** No Provenance panel (provenance is a tab inside each budget), no View menu, no *Reset layout*, no saved layout (the dock sizes are lost at every start). | S3 | P6 | Right dock *Inspector · Problems · Provenance*; `View > Reset layout`; layout saved (see decision on settings). | S01 |
| UX-09 | **Status bar** shows the Problems summary or a passing message ("Loading…", "Exported…"). Path, last run time, tool version and "n/a: 3 results blocked by placeholders" are missing; the version appears once at start-up. | S3 | P3, P4 | Persistent segments: path · last run · version · blocked-results link that filters Problems. | S01 |
| UX-10 | **One error blanks every view.** After `bus: nope` all four budget tabs say "No budget to show", Scenario/Power timeline/Link passes say "No scenario to show. Open a project that has scenarios." (it has one), the tree forgets unit names and the Compare sides read `(none)`. The last good results are thrown away, so the engineer cannot see what the fix changed. | S2 | P3 | Keep the last good results marked *stale: from before the error* with a banner and a link to the problem; the empty states say what is wrong. | S12, S13 |
| UX-11 | **Tab strip.** Eight fixed tabs plus one tab per open file or unit editor share one strip; at 1280 px it scrolls and the file tabs push budgets out of view (arrows at the right). The standard's *Model · Power · Mass · Thermal · Link · Compare · Reports* has 7. | S2 | P6 | The seven tabs; files, unit editors and the scenario live inside *Model*. | S09, S16 |
| UX-12 | **First screen is empty.** No recent projects, no drag-and-drop of a folder, no "New project" button; one grey status line. | S3 | P4 | An empty state with *Open*, *New (guided)*, recent projects. | S00 |

### Model editing

| ID | Finding | Sev. | Pr. | Fix | Shot |
|---|---|---|---|---|---|
| UX-13 | **One tab per unit; modes in a table inside it.** The form (name, subsystem, mass, bus, maturity) is vertical and the power modes are a grid; there is no grid across units, so comparing the radio with the OBC means two tabs. Headers are raw field names (`avg_power_w [W]`, `duty_cycle_ratio [ratio]`). | S2 | P6 | One data grid: rows = units, columns = mode powers (W), mass (kg), dissipation (W), limits (°C), maturity, source; readable headers with units. | S09 |
| UX-14 | **No source column and no placeholder styling in any editor.** The `source` of every number is in the YAML only; a placeholder (`value: null`, `source: TBD`) looks like an empty cell (S09: `min_duration_s`). The central promise of the tool, "every number carries its source", is not visible where numbers are typed. | S1 | P1 | Source column (collapsible); placeholder cells italic with a dashed border and a hollow marker; tooltip *Placeholder — no source. Results depending on it show n/a.*; *Mark as sourced…*; a legend button. | S09 |
| UX-15 | **Precision is whatever was typed** (`0.0`, `0.2`, `1.8`, `1.0`) and not fixed per column. | S3 | P1 | A number delegate with fixed precision per column; tabular figures. | S09 |
| UX-16 | **Every button is a large blue primary button** (*Add mode*, *Remove selected mode*, *Save*, *Browse…*, *Compute*, *Export…*). No hierarchy, and the destructive one looks like the safe ones. | S3 | P6 | One accent for the primary action; secondary and destructive styles; icon plus text. | S09, S06 |
| UX-17 | **Validation is a red label at the bottom, or a modal box.** There are 21 `QMessageBox` calls (information, warning, question, critical) for refusals such as "Compute the power timeline first", "The scenario results are out of date", "Fix the errors in the Problems panel first". | S2 | P4 | Messages beside the field and in Problems; refusals become disabled buttons with a reason in the tooltip; confirmations only for destructive actions, naming the object. | — |
| UX-18 | **No undo.** There is no `QUndoStack`; only the YAML text editor has Qt's own text undo. Adding or removing a mode, a rule or a segment cannot be undone. | S2 | P4 | Undo/redo across the grid, forms and scenario editor (see decision on the save model). | S09 |
| UX-19 | **The YAML editor is plain text.** Line numbers in a gutter, no highlighting, no inline problem marker, no search. The jump from Problems works. | S3 | P6 | Problem markers in the gutter; keep it as the expert fallback. | S10, S11 |
| UX-20 | **Unit tables via menu and file dialogs only.** *Export/Import unit table…* exist and have a preview; there is no paste of a spreadsheet range, no fill-down, no `Ctrl+C` of cells. | S3 | P6 | TSV paste with the existing preview; fill-down; copy. | — |
| UX-21 | **Scenario rules are rows of combo boxes**, not sentences; segments are a table; the small timeline strip exists but sits below the fold (S06: the editor is squeezed into the lowest 100 px of an 860 px window). | S2 | P6 | Rules as readable sentences ("Downlink during every pass over gs_north") with a sentence builder; segments on a strip. | S06 |

### Power

| ID | Finding | Sev. | Pr. | Fix | Shot |
|---|---|---|---|---|---|
| UX-22 | **The static power table is the report table.** Eight sub-tabs (*Summary, Mode charging … Assumptions, Provenance*); columns run past the right edge ("Pe…" cut off); no totals row; margin columns have the weight of all the others. | S2 | P2, P6 | Per-mode table with totals row; margin-vs-limit bar per row; columns sized to the window or frozen first column. | S01, S02 |
| UX-23 | **Broken limits are not visible in the tables.** `PEAK_POWER_EXCEEDED` (12 intervals) is in the Problems list and as a red dashed line in the plot, not in any cell. | S1 | P2 | Margin and limit cells coloured by state with an icon: pass, near, fail, **not checked**. | S07 |
| UX-24 | **`n/a` is grey right-aligned text.** It reads like a small number, differs from an empty cell only by colour, and does not say which placeholder blocks it. | S2 | P1, P2 | A distinct cell style with an icon; tooltip naming the blocking input; a click opens it in the Inspector. | S03 |
| UX-25 | **Timeline plot (keep the base):** gaps against the standard: BOL/EOL only by a combo (no overlay), no hide/solo by clicking the legend, the axis is elapsed time only (no UTC or orbit number), violations are not marked on the plot (a dashed limit line and a table), no *next/previous violation* buttons. (The three panels already share one time axis.) | S3 | P6 | Add them; keep the cursor model. | S07, S07b |
| UX-26 | **Plot is slow to zoom and pan on long runs** (see [measurements](#measurements)): 184 ms per pan step with 4 series of 604,801 points zoomed ×8; 373 ms for a full redraw; the decimation runs in a Python loop and the polylines are drawn antialiased. | S2 | P7 | Decimate with NumPy over a precomputed min/max pyramid; draw the plot once and shift the picture while dragging; target < 50 ms. A plotting library is not needed (see decisions). | — |
| UX-27 | **The plot has its own colours, not the theme's.** White background and ink colours are hard-coded; in the dark tokens the plot stays blinding white. | S2 | — | Plot colours from the theme module. | S15 |
| UX-28 | **The tables under the plot are squeezed.** At 1400 × 860 the *Summary* table shows one row and a horizontal scroll bar; the plot takes the space. | S2 | P6 | Splitter default that keeps the violations list and the summary readable; remember the user's split. | S07, S08 |
| UX-29 | **Margins in the timeline** (the third panel *Generation − demand*) is a good panel, but BOL/EOL, demand basis and scenario are three combos in a row with no indication of what is shown once the combos scroll out of the tab. | S3 | P3 | The top bar states scenario · case · basis while a result is on screen. | S07 |

### Mass, thermal, link

| ID | Finding | Sev. | Pr. | Fix | Shot |
|---|---|---|---|---|---|
| UX-30 | **Mass is flat report tables**, not a tree (subsystem › unit). A red banner says INCOMPLETE; three of the numbers (*With unit margins*, *With system margin*, the limit) are `n/a` with no way to see which input is missing. No margin bar, no phase selector (phases are sub-tabs). | S2 | P1, P2 | Tree-table with collapsible groups, bold totals with a top border, phase selector, limit row with a margin bar and a *not checked* state. | S03 |
| UX-31 | **Thermal shows only dissipation per mode on the first tab.** Hot and cold cases are separate sub-tabs, not side by side; no temperature is coloured against its unit's limit; no *near limit* state. | S2 | P2 | Node table with cold and hot side by side, each cell coloured within / near / exceeded / not checked (near = inside the required temperature margin the project already holds, see questions). | S04 |
| UX-32 | **The static link table is 11 columns wide** (cut off at "Re…"), uplink and downlink are not side by side, there is no elevation selector, and *Closes* is plain text. A **negative margin of −0.32 dB (76.8 kbit/s at 5° elevation) is not emphasised** at all. | S1 | P2 | A classic ladder (parameter · value · unit · source/derived) per link, uplink and downlink side by side, an elevation selector, the margin row highlighted by state. | S05 |
| UX-33 | **Link passes: the pass table shows one row** at default size under three tall plots; day totals are in a second sub-tab. Selecting a pass zooms the plot to it and pins the cursor (keep that); the pass is not marked on the Scenario tab's mode timeline. | S2 | P6 | Pass table first-class (station, start, duration, max elevation, closing rate, volume) with day totals; click highlights in the timeline. | S08 |

### Problems, compare, reports, wizard

| ID | Finding | Sev. | Pr. | Fix | Shot |
|---|---|---|---|---|---|
| UX-34 | **Problems panel.** Columns *Severity · Code · Location · Message*; the code column is wide, messages are cut with "…"; no filter, no grouping; two rows are visible at the default dock height; severity is told by text colour alone (red / olive); there is **no "not checked (placeholder)" class**: unsourced numbers are six ordinary warnings (`CONFIG_PLACEHOLDER`). | S2 | P2, P4 | Icon + colour + text per class (error / warning / not-checked); group by severity or file; filter box; counts in tree and status bar; message wraps. | S01 |
| UX-35 | **Compare is a bare table** (*Budget · Section · Row · Quantity · A · B · Change · Change (%) · Status*): no input diff, no signed colours, no overlay plots; when the project has an error side A is `(none)`. Side B is a text field plus *Browse…*. | S3 | P6 | Two panes: diff of inputs (old → new) and results Δ with sign colours; overlays with stable series colours. "Changed because of…" needs a dependency index in the core (decisions). | S13 |
| UX-36 | **No Reports page.** Exports are three File-menu commands (reports, power timeline, scenario results), each with a folder dialog and modal refusals; no format choice, no progress, no result list, no *Reveal in folder*, and provenance is not shown before export. | S2 | P4 | One *Reports* tab: budgets × formats, output folder, open after export, progress, the result list with paths, the provenance block first. | — |
| UX-37 | **Wizard** is a 500 × 360 modal with Back/Next/Cancel: fine for first use. Missing: a step list with ticks, a summary step, *Open in full editor*. | S3 | P6 | As the standard says. | S14 |

### Visual system, keyboard, feedback

| ID | Finding | Sev. | Pr. | Fix | Shot |
|---|---|---|---|---|---|
| UX-38 | **One theme, applied once.** `theme.py` defines white and g100 tokens but only white is ever applied; no OS default, no switch. Colours are hard-coded in 7 files (59 literals: `timeline.py` 25, `theme.py` 14, `plot_widget.py` 7, `compare_view.py` 6, `widgets.py` 4, `editor.py` 3), and five widgets call `setStyleSheet` with a colour. | S3 | — | One theme module producing `QPalette` + QSS from tokens; light, dark, OS default; no literals elsewhere. | S15 |
| UX-39 | **Status colours are not a system.** Red `#da1e28`, olive `#8a6a00` and blue exist for severity only; nothing for pass / near / fail / not-checked / placeholder; no icons, so colour carries the meaning. | S2 | P2 | One status palette, colour-blind safe, always with an icon or text. | S01 |
| UX-40 | **No type or spacing scale.** `font-size: 14px` for everything, paddings 4/6/8/14/16 chosen per widget; numbers are in Plex Sans, not Plex Mono; no tabular-figure setting. | S4 | P1 | Scale 12/13/16/20 and 4/8/12/16/24/32; Plex Mono for numbers, ids and paths. | — |
| UX-41 | **Keyboard.** Shortcuts: `Ctrl+N/O/S`, `F5`, `Ctrl+M`, `Ctrl+E`, `Ctrl+Shift+E`, `F1`. Missing: tab switching, Run/Compute, next/previous problem or violation, `Ctrl+K`. A scripted walk of 14 `Tab` presses from the tree never left the Problems table (Qt's default: `Tab` moves from cell to cell), so reaching a toolbar control from there is long. No defined focus order. | S2 | P5 | Command palette; shortcuts shown in menus; a defined focus order; `Esc` and `Tab` rules for tables. | — |
| UX-42 | **Few tooltips.** Two `setToolTip` calls in the whole GUI, none on column headers, buttons or the plot. | S3 | P4 | Tooltips on every control and header (unit, meaning, source of the equation). | — |
| UX-43 | **Long operations show a label, not progress.** A compute shows "Computing…" in a status label; a week at 1 s takes 8.6 s; there is no progress bar and no *Cancel*. | S2 | P7 | Non-modal progress bar and Cancel (see decision: cancelling needs support in the core loops or a separate process). | S06b |
| UX-44 | **Stale results are a line of small text** ("The project or a setting changed since the last computation. Press Compute.") and a disabled *Export…*. The plot and tables keep looking current. | S2 | P3 | A persistent banner with a *Recompute* button; the stale result dimmed. | — |
| UX-45 | **Nothing confirms success.** Messages appear in the status bar and are replaced by the next one; no toasts; failed runs have no persistent banner. | S3 | P4 | Non-blocking toasts for success; banners for stale results and failed runs. | — |
| UX-46 | **Empty states do not say what to add.** "No scenario to show. Open a project that has scenarios." (even when one exists, UX-10); "No budget to show. Open a project without errors." | S3 | P4 | "No ground stations — add one to compute passes", with the action. | S12 |
| UX-47 | **4K / HiDPI not verified.** Offscreen has a device pixel ratio of 1: S17 shows only that the layout stretches (the plot grows, the controls stay small). Fixed pixel paddings in the plot widget and 14 px type will need a check on a real HiDPI display. | S3 | — | Test on a real 4K / 200 % display after the shell exists. | S17 |

## Screenshots

Offscreen renders of the real window with the demo project, 1400 × 860 unless noted. `S11` and later were taken after the deliberate error described under [How this was done](#how-this-was-done) unless the caption says otherwise.

| | Screen | | Screen |
|---|---|---|---|
| [S00](images/ux-audit/00-empty.png) | Empty window at start | [S09](images/ux-audit/09-unit-editor.png) | Unit table editor (radio) |
| [S01](images/ux-audit/01-shell-power-summary.png) | Shell, Power budget summary | [S10](images/ux-audit/10-yaml-editor.png) | YAML editor |
| [S02](images/ux-audit/02-power-mode-tab.png) | Power budget, a mode tab | [S11](images/ux-audit/11-yaml-edited-unsaved.png) | YAML edited, unsaved |
| [S03](images/ux-audit/03-mass.png) | Mass budget | [S12](images/ux-audit/12-problem-after-save.png) | After saving the error: Power budget |
| [S04](images/ux-audit/04-thermal.png) | Thermal budget | [S13](images/ux-audit/13-compare.png) | After the error: Compare |
| [S05](images/ux-audit/05-link.png) | Link budget | [S14](images/ux-audit/14-wizard-step1.png) | Guided wizard, first page |
| [S06](images/ux-audit/06-scenario.png) | Scenario, before computing | [S15](images/ux-audit/15-dark-g100-timeline.png) | Dark tokens, Power timeline (good project) |
| [S06b](images/ux-audit/06b-scenario-computed.png) | Scenario, computed | [S16](images/ux-audit/16-1280x720-timeline.png) | 1280 × 720 (good project) |
| [S07](images/ux-audit/07-power-timeline.png) | Power timeline | [S17](images/ux-audit/17-4k-timeline.png) | 3840 × 2160 (good project) |
| [S07b](images/ux-audit/07b-violation-selected.png) | A violation selected | [S08](images/ux-audit/08-link-passes.png) | Link passes |

## Measurements

| What | Result | Target (standard) |
|---|---|---|
| Open `examples/cubesat_3u_eps` (synchronous load) | 1.0 s; in the window the load runs in a thread | window stays usable |
| Open `stress_200_units` (synchronous load) | 3.6 s; showing the Power / Mass / Thermal tab afterwards 79 / 19 / 13 ms; the tree (220 items) paints in 3 ms | < 100 ms UI response |
| Week at 1 s (`duration_s: 604800`, `step_s: 1`): power timeline compute and show | 8.6 s in a worker thread, label "Computing…", no progress, no Cancel | progress + Cancel |
| Same, plot of 4 series × 604,801 points: **hover** repaint | 1.7 ms (was 1.7 s with 20 series before D-147) | < 100 ms |
| Same, **pan** one step, zoomed ×8 | 184 ms | < 50 ms |
| Same, full-view redraw | 373 ms | < 50 ms |
| Profile of a 20-series redraw | `decimate` (a Python loop over buckets) ≈ 55 ms per series; antialiased `drawPolyline` ≈ 39 ms per series | — |

Not measured: the 200-unit project on a real display; startup time of the packaged app.

## The standard against the window

| Standard asks for | State today |
|---|---|
| Top bar (project · revision · dirty · scenario · BOL/EOL · Run · status chip) | missing (UX-01 to UX-04) |
| Left tree with Spacecraft › Units › modes, Solar array, Battery, Radios, Antennas, Orbit & Ground stations, Scenarios, Links, with badges | a file tree without array/battery/radio/antenna nodes and without badges (UX-05) |
| Tabs *Model · Power · Mass · Thermal · Link · Compare · Reports* | 8 fixed tabs + file tabs; no *Model* or *Reports* (UX-11, UX-36) |
| Right dock *Inspector · Problems · Provenance* | Problems only, at the bottom (UX-07, UX-08) |
| Status bar with path, last run, version, blocked-results link | message line only (UX-09) |
| Dock layout saved, *View > Reset layout* | not saved, no View menu (UX-08) |
| Unit data grid with inline editing, fill-down, TSV paste | one tab per unit, no paste (UX-13, UX-20) |
| Placeholder cells, *Mark as sourced…*, source column, legend | none (UX-14) |
| Scenario rules as sentences | rows of combo boxes (UX-21) |
| Power: per-mode table with margin bars; timeline with violation markers, linked axes, legend hide/solo, UTC/orbit axis, next/previous violation | table without bars; timeline has cursor, shading, readout, violations list (UX-22, UX-25) |
| Mass tree-table; Thermal hot/cold side by side with limit colours; Link ladder with uplink/downlink | flat report tables (UX-30 to UX-33) |
| Problems: icons, grouping, filter, *not checked* class | text colour only, no filter, no class (UX-34) |
| Compare: input diff + results Δ + overlays | one table (UX-35) |
| Reports page | three menu commands (UX-36) |
| `QUndoStack`, no `QMessageBox` for validation, toasts | none, 21 message boxes, none (UX-17, UX-18, UX-45) |
| `Ctrl+K`, shortcuts in menus | none for most actions (UX-41) |
| One theme module, light/dark/OS, status palette, Plex Sans + Mono, type and spacing scales, SVG icons | one light theme applied, 59 colour literals, no status palette, no icons (UX-38 to UX-40) |
| Worker + progress + Cancel | worker, no progress, no Cancel (UX-43) |

## Where the standard meets the project rules: decisions needed

Nothing here changes an equation, a file format or a report. These are points where the standard and an existing project rule (or a sensible limit) pull apart. My recommendation is first.

1. **Saving the layout and column widths (`QSettings`) against D-105.** The window disables every Qt settings file on purpose (`privacy.py`, D-105): Qt's file dialogs would otherwise write the folders you open, which is project content, to `~/.config`. Dock layout and column widths contain no project content. *Recommend:* write them to one small file of our own in the per-user config folder (`layout.ini`), holding only geometry, dock state and column widths keyed by view name; keep the dialog history suppressed; document it in `docs/DESIGN.md` and the privacy notes. The alternative is not saving the layout.
2. **Undo and saving.** Today an edit changes a table and *Save* writes the YAML in place, keeping comments and order. *Recommend:* keep explicit *Save* (files stay byte-stable and reviewable in git), put every edit of the grid, forms and scenario editor on one `QUndoStack` per project, show the dirty marker everywhere, and make *Save* the only thing that writes. Autosave would change the files behind the user's back, which this tool avoids.
3. **Plot library.** The standard suggests pyqtgraph or downsampling. *Recommend downsampling, no new dependency:* the slowness is a Python loop in `decimate` and antialiased polylines, not Qt. A NumPy min/max pyramid built once per series plus drawing the plot into a picture and shifting it while dragging reaches the < 50 ms target without a dependency. pyqtgraph is MIT-licensed and works, but it adds a runtime dependency (lock file with hashes, SBOM, licence page, bundle size, the offline test) and its own look to restyle. Say if you prefer it anyway.
4. **Icons.** Lucide (ISC) or Tabler (MIT) are SVG. Showing SVG in Qt needs the `QtSvg` module and its plugins in both bundles (I used PNG for the logo on purpose, D-148). *Recommend:* convert the 30 or so icons we need to PNG at build time with a script like `make_icons.py` (several sizes, light and dark variants), commit them, test them. The alternative is to bundle `QtSvg` and test it in the Rocky 8 and Ubuntu containers.
5. **Run and cancel.** *Run* is easy (it calls the existing per-tab computations in order). *Cancel* is not: the solvers run in a thread (`QThread`) and cannot be stopped safely. *Recommend:* add a cooperative cancel check to the long loops in the core (a flag read between steps; no change to any result), tested with a cancelled run leaving nothing behind. The alternative is to run budgets in a child process and kill it, which is heavier.
6. **New read-only core features** the standard implies: *where this value is used* (Inspector) and *changed because of…* (Compare) need an index from each input to the results that read it. This does not change an equation but is new core code. *Recommend:* leave both out of the first passes and decide after the Power view; the Inspector can show unit, source, range and help first.
7. **Forms from the schemas.** The model already has JSON schemas (`src/budget_core/schemas`) with fields and ranges. *Recommend:* build the *Model* forms and the Inspector's help and ranges from them instead of hand-writing a form per node, so the 18 file kinds are covered by one mechanism. The text of the help comes from the field descriptions (and where there is none, I add one to the model and regenerate the schemas, which does need the schema bump rule: description text only, no change to the format).
8. **Theme.** Light, dark and OS default (`QStyleHints.colorScheme`, Qt 6.5+). The plot, tables and Problems will take their colours from the same module. *Recommend* a setting in `View > Theme` (Light, Dark, System).

## Questions about conventions

The standard says to ask when a budgeting convention is unclear. I have not changed any, but the redesign needs these written down:

1. **Sign of a margin:** I propose *positive margin = within the limit, negative = broken* in every table, bar and colour, with the margin always limit minus value (or value minus requirement for link margin). Today the tables already follow this; please confirm it is the rule to show.
2. **"Near limit":** thermal already has a *required temperature margin* in the project configuration, so *near* = inside that margin and *exceeded* = beyond the limit. For power, mass and link there is no such number. *Do you want a configurable "near" band per budget (with a source, never invented), or show only pass / fail / not checked there?* I recommend the second until a project supplies a value.
3. **Depth of discharge and state of charge:** DoD is shown as a positive percentage of capacity used (as in the table today: 10.7 %), SoC as the remaining percentage. Confirm.
4. **BOL and EOL overlay:** the standard allows overlay or toggle. I propose a toggle by default with an overlay switch, BOL drawn solid and EOL dashed, the same colours per series.
5. **What *Run all* includes:** static power, mass, thermal and link (instant) plus, for the selected scenario, the scenario, the power timeline and the link passes. Confirm that is what *all* means.

## Plan

Each step is one pull request, with before and after screenshots (offscreen), one line per decision, and a question before the next. All existing GUI tests (206) stay green or are updated with the change they cover; the CLI and every output file are untouched.

| Step | What | Size |
|---|---|---|
| 0 | **Foundation**: the theme module (tokens, `QPalette`, QSS, status colours, scales), the number / placeholder / margin delegates, the icon set, the layout settings, `docs/DESIGN.md`. Nothing visible changes except that the dark theme works. | M |
| 1 | **App shell**: top bar, model tree with badges, Problems panel with classes, filter and grouping, Inspector skeleton, status bar, dock layout and *View > Reset layout*, Enter opens tree items, the seven tabs. Keep-last-good-results with a banner (UX-10). | L |
| 2 | **Model grid and placeholder styling**: the units grid, the source column, placeholder cells, undo, TSV paste, scenario rules as sentences. | L |
| 3 | **Power view**: per-mode table with bars and totals, timeline additions, the plot performance work (UX-26), progress and Cancel. | L |
| 4 | **Mass, Thermal, Link** tables (three small steps, one per view). | M each |
| 5 | **Compare and Reports.** | M |
| 6 | **Theme polish** and the HiDPI / keyboard acceptance pass, `Ctrl+K`. | M |

Acceptance per view (from the standard): keyboard only · light and dark · a placeholder-heavy project · 200 units · a week at 1 s · an empty project · 1280 × 720 and 4K · tests green · no hard-coded colours.

**What I need from you before step 0:** the answers to the eight decisions and five questions above (a one-word "as recommended" is enough), and whether the standard should be committed as `docs/UX_STANDARD.md` (I did so for traceability).

## Status of the findings

After step 1 (the shell). *Done* means the finding no longer applies in the window; *partly* names what is left; *open* is untouched. Later steps are in [the plan](#plan).

| Finding | Status | Where |
|---|---|---|
| UX-01 top bar | done | project, revision, unsaved marker, one scenario selector, BOL/EOL, Run, status (D-153) |
| UX-02 no Run | done | Run (Ctrl+R); the views keep an outline Compute |
| UX-03 revision shown nowhere | done | top bar |
| UX-04 dirty marker | partly | top bar and window title; the tab star stays. Not on the tree nodes yet |
| UX-05 file tree, no badges | done | model tree with badges (D-152); no radio or antenna nodes: the model has none |
| UX-06 Enter does not open | done | Enter opens a tree row and a problem |
| UX-07 no inspector | partly | Inspector skeleton (file, field, problems); the unit and source of a field are in the grid columns and tooltips; the Inspector does not follow a grid cell yet |
| UX-08 only the Problems dock | done | Inspector, Problems, Provenance; View menu; Reset layout; the layout is kept (D-154) |
| UX-09 status bar | done | folder, last run, version, not-checked link |
| UX-10 one error blanks everything | done | the last good tables stay, with a banner (D-155); the time-domain views are empty with a sentence |
| UX-11 tab strip | done | seven tabs; files open inside Model |
| UX-12 empty first screen | open | recent projects and a New button: step 6 |
| UX-13 one tab per unit | done | the Units and Power modes grids across all units (D-159) |
| UX-14 no source column, no placeholder styling | partly | placeholders, source and unit in the Inputs grid (every sourced number of the configuration and the links); unit values have no source in the file format |
| UX-15 precision | done | fixed decimals per column; the exact value in the tooltip and the editor |
| UX-16 every button primary | partly | Save is the primary button of a grid, the others are secondary; the other views follow in their steps |
| UX-17 validation by message box | partly | the grids have none (a cell, a tooltip and a line under the grid); the other views follow |
| UX-18 no undo | done | one undo stack for the grids and the scenario editor (D-159, D-160); the YAML text editor keeps Qt's own undo |
| UX-20 no paste, fill-down, copy | done | Ctrl+C, Ctrl+V with a preview, Ctrl+D, Delete in every grid |
| UX-21 rules as combo boxes | done | rules and segments as sentences with their controls, Up/Down, and more room for the editor (D-160) |
| UX-34 Problems panel | done | four classes, icons, filter, grouping, wrapped message (D-151) |
| UX-38 to UX-40 visual system | done in step 0 (D-150) | |
| UX-41 keyboard | partly | Ctrl+1 to Ctrl+7, Ctrl+R, F8; Tab no longer trapped in tables; `Ctrl+K` in step 6 |
| UX-43 progress and Cancel | open | step 3 |
| UX-44 stale banner | partly | the *out of date* run status; a banner for the failed run and for old results after an error |
| UX-45 toasts | partly | failed-run banner; toasts for success: later |
| UX-46 empty states | done | each empty view says why or what to add |
| all others | open | steps 2 to 6 |
