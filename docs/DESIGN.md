# Design: the visual system of the window

This page is the reference for how the window looks and why. The numbers in it are checked by tests against `src/budget_gui/theme.py` (a colour changed in the code and not here fails the build), so it stays true. The standard it follows is [UX_STANDARD.md](UX_STANDARD.md); what is wrong with the old window is in [ux-audit.md](ux-audit.md); the decisions are D-150 to D-156 in [DECISIONS.md](DECISIONS.md).

**Contents:** [Rules](#rules) · [Theme](#theme) · [Status colours](#status-colours) · [Cell styles](#cell-styles) · [Type and spacing](#type-and-spacing) · [Icons](#icons) · [The shell](#the-shell) · [The layout file](#the-layout-file) · [Shortcuts](#shortcuts) · [Acceptance per view](#acceptance-per-view)

## Rules

1. **Colours live in `theme.py` and nowhere else.** No other module of the window holds a colour literal or calls `setStyleSheet` (a test enforces it). A widget that paints itself asks `theme.tokens()` and connects to `theme.manager().changed` to draw again.
2. **A status is never told by colour alone.** Every status has an icon and text as well as a colour.
3. **Text reaches a contrast of 4.5 : 1** on the surface it is used on, in both themes (a test computes it).
4. **Numbers are IBM Plex Mono**, right-aligned, with a fixed number of decimals per column and the unit in the column header.
5. **One accent colour for one primary action** per view.
6. **Sizes come from the scales** below; no other gaps, paddings or font sizes.

## Theme

Light is IBM Carbon *white*, dark is Carbon *g100*. `View > Theme` chooses *Light*, *Dark* or *Same as the system* (the default; it follows the operating system while the window is open). The choice is kept in the [layout file](#the-layout-file).

| Token | Light | Dark | Used for |
|---|---|---|---|
| `background` | `#ffffff` | `#161616` | Window and view background |
| `layer` | `#f4f4f4` | `#262626` | Table, tree and dock backgrounds, headers, the status bar |
| `border` | `#e0e0e0` | `#393939` | Hairlines, grid lines |
| `border_strong` | `#8d8d8d` | `#6f6f6f` | Outlines that must be seen (readout box, dividers in plots) |
| `text` | `#161616` | `#f4f4f4` | Body text |
| `text_secondary` | `#525252` | `#c6c6c6` | Captions, table headers, muted text |
| `text_disabled` | `#6f6f6f` | `#8d8d8d` | Disabled controls, empty-state text |
| `accent` | `#0f62fe` | `#0f62fe` | Fill of the one primary action |
| `accent_hover` | `#0050e6` | `#0353e9` | The primary action under the pointer |
| `text_on_accent` | `#ffffff` | `#ffffff` | Text on the accent |
| `accent_text` | `#0f62fe` | `#78a9ff` | Links and accent-coloured text |
| `focus` | `#0f62fe` | `#ffffff` | Focus ring |
| `selection_bg` | `#d0e2ff` | `#0043ce` | Selected rows and menu items |
| `selection_text` | `#161616` | `#ffffff` | Text on a selection |
| `info` | `#0043ce` | `#78a9ff` | Information messages |

Not in the table (they follow the same two themes): the plot colours (`plot_*`, `band_alpha`), the scenario timeline strips (`strip_*`, 14 `categorical` mode colours), the comparison tints (`diff_*`), and the file editor (`gutter_*`, `line_highlight`). The colours the core gives a plot (made for a white page, shared with the reports) are drawn lighter on the dark theme (`plot_colour`); the reports are not affected.

## Status colours

| Status | Icon | Text and icon, light | Tint, light | Text and icon, dark | Tint, dark | Contrast on its tint (light / dark) |
|---|---|---|---|---|---|---|
| **Within the limit** (`pass`) | `circle-check` | `#0e6027` | `#defbe6` | `#42be65` | `#044317` | 7.0 / 4.8 |
| **Near the limit** (`near`) | `triangle-alert` | `#7a5d00` | `#fcf4d6` | `#f1c21b` | `#3d3200` | 5.6 / 7.5 |
| **Limit broken** (`fail`) | `circle-x` | `#a2191f` | `#fff1f1` | `#ff8389` | `#520408` | 7.1 / 6.4 |
| **Not checked (n/a)** (`not_checked`) | `circle-minus` | `#525252` | `#e8e8e8` | `#a8a8a8` | `#393939` | 6.4 / 4.9 |
| **Placeholder** (`placeholder`) | `circle-dashed` | `#6929c4` | `#f6f2ff` | `#be95ff` | `#31135e` | 7.0 / 6.4 |

*Not checked* is also what `n/a` means: a result that could not be computed, or a limit that could not be checked, because an input is a placeholder or missing. It is deliberately different from a pass, from a fail and from an empty cell. In Problems, errors use *Limit broken*, warnings *Near the limit* and information the *info* colour.

## Cell styles

One delegate (`budget_gui/delegates.py`) paints every table cell, so the same state always looks the same. `View > Cell styles…` shows them all (the same delegate draws the legend).

| Style | Look | Meaning |
|---|---|---|
| Number | right-aligned, Plex Mono | A value. Fixed decimals per column; the unit is in the header. |
| Within the limit | green tint, check icon, optional bar | The margin is positive. The bar below the number shows the share of the limit used. |
| Near the limit | amber tint, triangle icon | Inside the required margin, not broken. |
| Limit broken | red tint, cross icon, bold | The limit is broken. |
| Not checked (`n/a`) | grey tint, minus icon | Not computed or not checked because of a placeholder upstream. Tooltip says so. |
| Placeholder | purple tint, dashed border, italic, hollow-circle icon | An input without a source (`source: TBD`). Tooltip: *Results that depend on it show n/a.* |
| Empty | nothing | No value is needed. |

A model gives a cell its state through item data roles (`STATE_ROLE`, `NUMERIC_ROLE`, `MARGIN_ROLE`, `SOURCE_ROLE`); a cell without a state is plain text.

## Type and spacing

| Scale | Values (px) | Use |
|---|---|---|
| Type | 12, 13, 16, 20 | 12 captions and chips · 13 the interface and tables · 16 section titles · 20 view headings |
| Spacing | 4, 8, 12, 16, 24, 32 | Every gap, padding and margin |

Fonts: **IBM Plex Sans** for the interface, **IBM Plex Mono** for numbers, identifiers and file paths (`theme.ui_font()`, `theme.mono_font()`). Both ship with the program (SIL Open Font License).

Labels take their style from a `role` property (`error`, `banner`, `section-title`, `muted`, `heading`, `title`, `small`, `chip`) and buttons from `kind` (`secondary`, `danger`; no `kind` is the primary action).

## Icons

Icons are [Lucide](https://lucide.dev) 0.468.0 (ISC licence). The SVG files in `assets/icons/ui/src/` are rendered once by `python packaging/make_ui_icons.py` into black PNG masks of 16, 24, 32 and 48 px, which `budget_gui/icons.py` tints with the colour asked for (`icons.icon(name, colour)`, `icons.status_icon(status)`). PNG files need no Qt SVG module in the installers. Every icon button gets a tooltip. To add an icon, see `assets/icons/ui/README.md`.

## The shell

```text
┌ top bar: project · rev · unsaved · Scenario [ ▾ ] · [BOL][EOL] · [ Run ] · (run status) ┐
├ banners (only when needed): stale results · failed run ─────────────────────────────────┤
│ Project   │ Model │ Power │ Mass │ Thermal │ Link │ Compare │ Reports │ Inspector     │
│ tree with │  Power: Budget | Timeline       Link: Budget | Passes     │ Problems      │
│ badges    │  Model: Units, Power modes, Inputs, Scenario, files       │ Provenance    │
├ status bar: N not checked · project folder · last run · version ──────────────────────┤
```

- **Top bar.** The project name (it ends in an ellipsis before it widens the window; the tooltip has all of it), `rev`, a *● Unsaved changes* marker, the scenario selector, the BOL/EOL switch, **Run** and the run status. The scenario and the case are chosen here once; the tabs keep no selector of their own. **Run** is the one filled accent button of the window; **Compute** and **Export…** in the views are outlined.
- **Run status chip** (icon, word, tint from the status palette): *Not run* (not checked), *Running…* (accent text on the layer), *Up to date · time* (pass), *Out of date* (near), *Run failed* (fail).
- **Banners** (icon, sentence, one action; tint from the status palette): *stale* (near) when the tables show the last results that worked, from before an error, with **Show the first error**; *failed* (fail) when a run did not finish, with **Run again**.
- **Problems classes.** Error (`circle-x`, fail colour), warning (`triangle-alert`, near), **not checked** (`circle-minus`, not-checked grey; a placeholder, an incomplete result or a unit without limits) and info (`info`). The class is chosen from the problem code only; an error stays an error. The tree shows the same icons with counts as badges; a node counts its own problems and those of its children, the project node counts all.
- **Tabs.** Model · Power · Mass · Thermal · Link · Compare · Reports, fixed; the grids (Units, Power modes, Inputs), the scenario and the files open inside *Model*; *Power* and *Link* have two pages (budget, and timeline or passes). `Ctrl+1` to `Ctrl+7`.
- **Project tree.** Rows by name, ids in the tooltip; units grouped by subsystem above eight units; a badge only for errors and warnings, rolled up on a folded group and never repeated on an open one; the raw file list adds nothing to its group (D-158).
- **Grids** (D-159). A grid is a `QTableView` over a model of the editable document, painted by the one cell delegate: numbers with fixed decimals in the mono font, the unit in the header, *not given* (a missing limit or heat ratio) as *not checked* with `n/a`, a **placeholder** (italic, dashed border, hollow marker) for a sourced number without a value or with the source `TBD`, a wrong cell as *fail* with its reason in the tooltip. The filter is above, the line of what is wrong, the line of feedback and the buttons (Undo, Redo, Cell styles, Save) below; no message box.
- **Scenario editor** (D-160). Rules and segments are sentences made of their controls (mode, *during every pass over / while in eclipse / while in sunlight*, site, lead and lag); Up and Down order the rules (a later rule wins); the editor edits the shared document, so it has the same undo, Save and dirty marker as the grids. The editor and the tables get more of the page than the timeline strip.
- **Timeline plot** (D-162). Legend entries are buttons (click hides, Shift-click solos; a hidden entry is struck through); violations are bars in the *fail* colour along the top of every panel with the selected one shaded; the time axis is an object (elapsed, UTC, orbit number) that the plot asks for ticks and a title.
- **Budget tables** (D-163). A header longer than 14 characters breaks into two lines; the totals row (`emphasise_last_row` of the report table) is semibold with a line above; the timeline tables use the cell delegate with `fill_table(numeric=…, states=…)`.
- **Limits in budget tables** (D-164). `Table.status_column`, `status_marks` and `bar` (window only) give a row its state and a (value, limit) pair its bar; the words of the status column map to pass, near, fail or not checked.
- **Reports page and Compare** (D-165). The Reports page reads what can be exported from the views (`ReportItem`: key, state, ready) and hands the choice (parts, formats, folder) to the window, which writes the parts one after the other with the existing export code; Compare names its columns from the comparison result.
- **First screen, palette, Inspector** (D-166). `WelcomePage` stands in for the tabs while `session.path` is None; `CommandPalette` ranks `Command(text, run, hint)` entries gathered by `MainWindow.palette_commands()`; `InspectorPanel.show_cell(CellInfo)` is fed by the grids' `selection_changed`.
- **Progress and Cancel** (D-167). While a run is in progress the Run button is *Cancel* (secondary style, then *Cancelling…* disabled), a 3 px busy bar sits under the top bar and the status chip names the step; each view's Compute button turns into Cancel and its status line names the step. `budget_gui/cancel_support.py` holds the texts.
- **Panels.** The project tree on the left; Inspector, Problems and Provenance as tabs of the right dock. Each has an object name, which is the key of the saved arrangement.
- **Status bar.** Action messages on the left (they go away); on the right the not-checked link, the project folder, the last run time and the version.
- **Plot speed** (D-161). A series is summarised once in blocks of 64 samples; the plot window is drawn from the blocks (zoomed out) or from a one-step reduction of the visible samples (zoomed in), a reduced series as one short line per pixel, bands on whole pixels. A week at 1 s pans and zooms in about 20 ms.
- **Speed.** Updating the window after a load or reload takes about 0.1 s for a project of 200 units: the cells of a budget table are measured from the font, a sheet is built the first time it is shown, and replacing a budget does not build the sheets it uncovers.

## The layout file

The window keeps no Qt settings file (D-105): Qt's dialogs would write the folders you open, which is project content. The **layout** is kept in one file of our own, `layout.ini`, in the per-user application configuration folder (on Linux `~/.config/System Budget Studio/`, on Windows `%APPDATA%\System Budget Studio\`). Only four groups of keys can be written to it (a test refuses anything else): `window` (geometry), `dock` (dock state), `columns` (the widths of the Problems columns; 0 is a hidden column) and `theme` (the mode). **View → Reset layout** forgets `window`, `dock` and `columns` and restores the first arrangement. It never holds a project name, a path or a value. Delete the file to reset the layout; `BUDGET_CONFIG_DIR` moves it and `BUDGET_NO_LAYOUT=1` keeps nothing.

## Shortcuts

| Shortcut | Action | State |
|---|---|---|
| `Ctrl+N` / `Ctrl+O` / `Ctrl+S` | New (guided), open, save | in the window |
| `F5` | Reload the project | in the window |
| `Ctrl+R` | Run: scenario, power timeline and link passes of the selected scenario | in the window |
| `Ctrl+1` … `Ctrl+7` | Go to the tab Model, Power, Mass, Thermal, Link, Compare, Reports | in the window |
| `Enter` | Open the selected row of the project tree or the Problems panel | in the window |
| `F8` / `Shift+F8` | Next / previous problem | in the window |
| `Ctrl+M` | Show the power modes of the selected unit in the grid | in the window |
| `Ctrl+E` / `Ctrl+Shift+E` | Export reports / export the power timeline | in the window |
| `F1` | User guide | in the window |
| `Ctrl+K` | Command palette | planned (step 6) |
| `Ctrl+Z` / `Ctrl+Shift+Z` | Undo / redo the edits of the grids | in the window |
| `Ctrl+C` / `Ctrl+V` | In a grid: copy the cells as text with tabs / paste a block, with a preview for more than one cell | in the window |
| `Ctrl+D` / `Delete` | In a grid: fill down / empty the optional cells | in the window |
| `Enter` / `Tab` / `Esc` | In a grid: accept and move down / accept and move right (leaves the grid after the last cell) / cancel | in the window |

## Acceptance per view

Every redesigned view is checked for: keyboard only · light and dark · a placeholder-heavy project · 200 units · a week at 1 s · an empty project · 1280 × 720 and 4K · tests green · no hard-coded colours.
