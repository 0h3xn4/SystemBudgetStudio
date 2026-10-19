# Design: the visual system of the window

This page is the reference for how the window looks and why. The numbers in it are checked by tests against `src/budget_gui/theme/` (a colour changed in the code and not here fails the build), so it stays true. The brief it follows is [ui/UI_OVERHAUL.md](ui/UI_OVERHAUL.md) (the plan is [ui/UI_OVERHAUL_PLAN.md](ui/UI_OVERHAUL_PLAN.md)); the standard before it is [UX_STANDARD.md](UX_STANDARD.md); what was wrong with the first window is in [ux-audit.md](ux-audit.md); the decisions are D-150 to D-156 and D-168 to D-172 in [DECISIONS.md](DECISIONS.md).

**Contents:** [Rules](#rules) · [Theme](#theme) · [Status colours](#status-colours) · [Plot and series colours](#plot-and-series-colours) · [Cell styles](#cell-styles) · [Type, spacing and shape](#type-spacing-and-shape) · [Components](#components) · [Icons](#icons) · [The shell](#the-shell) · [The layout file](#the-layout-file) · [Shortcuts](#shortcuts) · [Acceptance per view](#acceptance-per-view)

## Rules

1. **Colours, fonts and sizes live in `budget_gui/theme/` and nowhere else.** No other module of the window holds a colour literal, a font family or a pixel size, or calls `setStyleSheet` (tests enforce it; custom painting uses named constants of its module until its view is redone). A widget that paints itself asks `theme.tokens()` and connects to `theme.manager().changed` to draw again.
2. **Colour means something.** The interface is neutral. The accent is for the primary action, selection and the focus ring; status colours are for status. An abnormal value is the only coloured thing on a screen.
3. **A status is never told by colour alone.** Every status has an icon and text as well as a colour.
4. **Text reaches a contrast of 4.5 : 1** on every surface it is used on, in both themes; icons, plot lines and the focus ring 3 : 1 (a test computes both over every token pair).
5. **Numbers are JetBrains Mono** (identifiers, paths and code too), right-aligned, with a fixed number of decimals per column and the unit in the column header or the field.
6. **Separate with surfaces, not lines.** Areas differ by their background; borders are 1 px and subtle, used for inputs, table headers and splitters. No box in a box.
7. **One accent for one primary action** per view; every other button is secondary, ghost or danger.
8. **Sizes come from the scales** below; no other gaps, paddings or font sizes.

## Theme

Light and dark. `View > Theme` chooses *Light*, *Dark* or *Same as the system* (the default; it follows the operating system while the window is open and switches live). The choice is kept in the [layout file](#the-layout-file).

The tokens are the table of the design language, with the changes that WCAG 2.2 AA asked for (the muted text, the accent text on a selected row, the status colours of the light theme and the text on the accent of the dark theme are darker or lighter than the first values; the decision is D-169).

| Token | Light | Dark | Used for |
|---|---|---|---|
| `canvas` | `#f7f7f8` | `#0b0d10` | Behind the panels: window background, splitters, the status bar |
| `surface` | `#ffffff` | `#111418` | Panels, tables, inputs |
| `raised` | `#ffffff` | `#171b21` | Menus, popovers, dialogs, toasts (with a shadow) |
| `hover` | `#f0f1f3` | `#1d222a` | Row, button and menu item under the pointer; the track of a segmented control |
| `selected` | `#e9effd` | `#1a273d` | Selected rows and menu items: the accent at 10 % (light) or 16 % (dark) over the surface |
| `border_subtle` | `#e4e5e9` | `#222832` | 1 px lines: table headers, panel borders |
| `border_strong` | `#d0d3d9` | `#2e3540` | Input borders, the plot frame |
| `text` | `#16181d` | `#e7e9ec` | Primary text |
| `text_secondary` | `#50565f` | `#a1a8b3` | Table headers, captions, labels |
| `text_muted` | `#646b75` | `#8a919c` | Placeholders, disabled text, the *off* status |
| `text_on_accent` | `#ffffff` | `#0b0d10` | Text on the accent and on a danger button |
| `accent` | `#2563eb` | `#4c8dff` | The primary action, selection outline and the focus ring |
| `accent_hover` | `#1d4fd0` | `#6aa0ff` | The primary action under the pointer |
| `accent_text` | `#1d4fd0` | `#6aa0ff` | Links and accent-coloured text |

Not in the table (they follow the same two themes and are made from the tokens above): `focus` (the accent), the plot colours (`plot_*`, `band_alpha`), the scenario timeline strips (`strip_*`), the comparison tints (`diff_*`, the status tints) and the file editor (`gutter_*`, `line_highlight`). `shadow` is for floating elements only.

## Status colours

Status follows the Astro UXDS taxonomy (critical, serious, caution, normal, standby, off). What the budget tables say is a `Status` (pass, near, fail, not checked, placeholder); it maps onto the taxonomy. The icons differ so that colour is never alone.

| Level | Status | Icon | Text and icon, light | Tint, light | Text and icon, dark | Tint, dark | Contrast on its tint (light / dark) |
|---|---|---|---|---|---|---|---|
| **Critical** | `fail` | `circle-x` | `#c62828` | `#f8e5e5` | `#ff6b6d` | `#372226` | 4.6 / 5.3 |
| **Serious** | | `octagon-alert` | `#a8480a` | `#f5e9e2` | `#ff8a3d` | `#37271e` | 4.9 / 6.1 |
| **Caution** | `near` | `triangle-alert` | `#8a5a00` | `#f1ebe0` | `#f5b83d` | `#352e1e` | 5.0 / 7.6 |
| **Normal** | `pass` | `circle-check` | `#14724a` | `#e3eee9` | `#3dd68c` | `#18332b` | 5.0 / 7.2 |
| **Standby** | `placeholder` | `circle-dashed` | `#1e62b5` | `#e4ecf6` | `#56b4f5` | `#1c2e3b` | 5.1 / 6.1 |
| **Off** | `not_checked` | `circle-minus` | `#646b75` | `#ecedee` | `#8a919c` | `#24282d` | 4.6 / 4.7 |

*Not checked* is also what `n/a` means: a result that could not be computed, or a limit that could not be checked, because an input is a placeholder or missing. It is deliberately different from a pass, from a fail and from an empty cell. In Problems, errors are *critical*, warnings *caution* and information *standby*. *Serious* has no budget meaning yet; it is reserved (for example for a result that is not trustworthy).

## Plot and series colours

The plots of the window (`QPainter`) and the timeline strips draw with the theme. Each colour the core gives a series (`budget_core.plots.spec`, made for a white page and fixed by the exported files) stands for a role, and the window draws the role: ink, a series, the limit (*critical*), a band. The exported files do not change (D-168).

Eight series colours per theme, found by search so that every pair stays at least 15 CIELAB units apart for normal vision and for protanopia, deuteranopia and tritanopia (a test measures it, with the Machado matrices) and at least 20 units from every status colour:

| Theme | Series colours |
|---|---|
| Light | `#3232e2`, `#50958a`, `#b437cd`, `#bb1b50`, `#301386`, `#b27ab8`, `#703285`, `#861356` |
| Dark | `#765cc1`, `#8be6ee`, `#eb70ad`, `#d59658`, `#b695e4`, `#df2070`, `#962de1`, `#d6b594` |

More than eight categories (the modes of a scenario) go round again with a lighter mix of the same colours; a label on a bar is black or white, whichever reads at 4.5 : 1.

## Cell styles

One delegate (`budget_gui/delegates.py`) paints every table cell, so the same state always looks the same. `View > Cell styles…` shows them all (the same delegate draws the legend).

| Style | Look | Meaning |
|---|---|---|
| Number | right-aligned, JetBrains Mono | A value. Fixed decimals per column; the unit is in the header. |
| Within the limit | green tint, check icon, optional bar | The margin is positive. The bar below the number shows the share of the limit used. |
| Near the limit | amber tint, triangle icon | Inside the required margin, not broken. |
| Limit broken | red tint, cross icon, bold | The limit is broken. |
| Not checked (`n/a`) | grey tint, minus icon | Not computed or not checked because of a placeholder upstream. Tooltip says so. |
| Placeholder | purple tint, dashed border, italic, hollow-circle icon | An input without a source (`source: TBD`). Tooltip: *Results that depend on it show n/a.* |
| Empty | nothing | No value is needed. |

A model gives a cell its state through item data roles (`STATE_ROLE`, `NUMERIC_ROLE`, `MARGIN_ROLE`, `SOURCE_ROLE`); a cell without a state is plain text.

## Type, spacing and shape

| Scale | Values | Use |
|---|---|---|
| Type (px) | 11, 12, 13, 15, 18, 22 | 11 caption · 12 small, table and chips · 13 body (the base) · 15 section title · 18 page title · 22 display (rare) |
| Weights | 400, 500, 600 | regular · medium (table headers, chips) · semibold (titles) |
| Spacing (px) | 4, 8, 12, 16, 24, 32 | Every gap, padding and margin (`theme.gap(i)`, `theme.inset(h, v)`) |
| Radius (px) | 6, 8 | 6 controls (buttons, inputs, tabs, chips) · 8 panels, popovers, dialogs, toasts |
| Control height (px) | 28, 32 | 28 compact (`size="compact"`) · 32 everywhere else; a table row is 26 |
| Focus ring | 2 px, the accent | every control that takes the keyboard |
| Motion | 120 to 180 ms, ease-out | hover, a toast rising; never data or plots; off with *Reduce motion* and when there is no screen |
| UI scale | 90, 100, 110, 125 % | `View > UI size`; the font sizes, the style sheet and every `theme.px()` size follow |

Fonts: **Inter** for the interface (tabular figures on) and **JetBrains Mono** for numbers, identifiers, paths and code (`theme.ui_font()`, `theme.mono_font()`). Both ship with the program (SIL Open Font License, `assets/fonts/`); the window never relies on a font of the system (D-170).

Labels take their style from a `role` property (`error`, `banner`, `section-title`, `muted`, `caption`, `small`, `title`, `heading`, `display`, `chip`, `badge`), frames from `role` too (`card`, `raised`, `segmented`, `empty`), and buttons from `kind`: `primary` (the accent; one per view), `secondary` (the default), `ghost`, `danger`, `link`.

## Components

`budget_gui/components/` holds the parts views are made of; `scripts/ui_gallery.py` shows all of them in both themes.

| Component | What it is |
|---|---|
| `Button`, `icon_button` | A button of a kind, an icon that follows the theme, a tooltip that names the shortcut; an icon-only button always has a name for screen readers |
| `StatusBadge` | An icon and a word in the colour of a level |
| `SegmentedControl` | A few choices side by side, one chosen |
| `Card`, `SectionHeader`, `KeyValueList` | A panel, a title with actions, names and values (values in the mono font, selectable) |
| `EmptyState` | One line of explanation and the primary action, for every empty list or table |
| `Toast` | A non-modal confirmation that goes away by itself; a problem is never a toast, it is in the Problems panel |
| `MessageDialog`, `ask`, `inform` | Confirmation of something that cannot be undone, and refusals that need an answer; a destructive primary is red and never the default |

## Icons

Icons are [Lucide](https://lucide.dev) 0.468.0 (ISC licence). The SVG files in `assets/icons/ui/src/` are rendered once by `python packaging/make_ui_icons.py` into black PNG masks of 16, 24, 32 and 48 px, which `budget_gui/icons.py` tints with the colour asked for (`icons.icon(name, colour)`, `icons.status_icon(status)`). PNG files need no Qt SVG module in the installers. The arrows of combo boxes and spin boxes are the one exception: a style sheet can only use an image file, so `python packaging/make_theme_images.py` renders the two chevrons once per theme in the secondary text colour (`assets/icons/ui/theme/`, 1x and @2x) and a test checks the committed files against the tokens. Every icon button gets a tooltip. To add an icon, see `assets/icons/ui/README.md`.

## The shell

```text
┌ top bar: project · rev · unsaved · Scenario [ ▾ ] · [BOL][EOL] · [ Run ] · (run status) ┐
├ banners (only when needed): stale results · failed run ─────────────────────────────────┤
│ Project   │ Model │ Power │ Mass │ Thermal │ Link │ Compare │ Reports │ Inspector     │
│ tree with │  Power: Budget | Timeline       Link: Budget | Passes     │ Problems      │
│ badges    │  Model: Units, Power modes, Inputs, Scenario, files       │ Provenance    │
├ status bar: N not checked · project folder · last run · version ──────────────────────┤
```

- **Top bar.** The project name (it ends in an ellipsis before it widens the window; the tooltip has all of it), `rev`, a *● Unsaved changes* marker, the scenario selector, the BOL/EOL switch, **Run** and the run status. The scenario and the case are chosen here once; the tabs keep no selector of their own. **Run** is the one filled accent button of the window; **Compute** and **Export…** in the views are secondary.
- **Run status chip** (icon, word, tint from the status palette): *Not run* (not checked), *Running…* (accent text on the selected tint), *Up to date · time* (pass), *Out of date* (near), *Run failed* (fail).
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
- **Progress and Cancel** (D-167). While a run is in progress the Run button is *Cancel* (secondary style, then *Cancelling…* disabled), a 4 px busy bar sits under the top bar and the status chip names the step; each view's Compute button turns into Cancel and its status line names the step. `budget_gui/cancel_support.py` holds the texts.
- **Panels.** The project tree on the left; Inspector, Problems and Provenance as tabs of the right dock. Each has an object name, which is the key of the saved arrangement.
- **Status bar.** Action messages on the left (they go away); on the right the not-checked link, the project folder, the last run time and the version.
- **Plot speed** (D-161). A series is summarised once in blocks of 64 samples; the plot window is drawn from the blocks (zoomed out) or from a one-step reduction of the visible samples (zoomed in), a reduced series as one short line per pixel, bands on whole pixels. A week at 1 s pans and zooms in about 20 ms.
- **Speed.** Updating the window after a load or reload takes about 0.1 s for a project of 200 units: the cells of a budget table are measured from the font, a sheet is built the first time it is shown, and replacing a budget does not build the sheets it uncovers.

## The layout file

The window keeps no Qt settings file (D-105): Qt's dialogs would write the folders you open, which is project content. The **layout** is kept in one file of our own, `layout.ini`, in the per-user application configuration folder (on Linux `~/.config/System Budget Studio/`, on Windows `%APPDATA%\System Budget Studio\`). Only four groups of keys can be written to it (a test refuses anything else): `window` (geometry), `dock` (dock state), `columns` (the widths of the Problems columns; 0 is a hidden column) and `theme` (the mode, the UI scale and *Reduce motion*). **View → Reset layout** forgets `window`, `dock` and `columns` and restores the first arrangement. It never holds a project name, a path or a value. Delete the file to reset the layout; `BUDGET_CONFIG_DIR` moves it and `BUDGET_NO_LAYOUT=1` keeps nothing.

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
| `Ctrl+K` | Command palette | in the window |
| `Ctrl+Z` / `Ctrl+Shift+Z` | Undo / redo the edits of the grids | in the window |
| `Ctrl+C` / `Ctrl+V` | In a grid: copy the cells as text with tabs / paste a block, with a preview for more than one cell | in the window |
| `Ctrl+D` / `Delete` | In a grid: fill down / empty the optional cells | in the window |
| `Enter` / `Tab` / `Esc` | In a grid: accept and move down / accept and move right (leaves the grid after the last cell) / cancel | in the window |

## Acceptance per view

Every redesigned view is checked for: keyboard only · light and dark · a placeholder-heavy project · 200 units · a week at 1 s · an empty project · 1280 × 720 and 4K · tests green · no hard-coded colours.
