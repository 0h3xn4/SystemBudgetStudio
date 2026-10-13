# Design: the visual system of the window

This page is the reference for how the window looks and why. The numbers in it are checked by tests against `src/budget_gui/theme.py` (a colour changed in the code and not here fails the build), so it stays true. The standard it follows is [UX_STANDARD.md](UX_STANDARD.md); what is wrong with the old window is in [ux-audit.md](ux-audit.md); the decisions are D-150 in [DECISIONS.md](DECISIONS.md).

**Contents:** [Rules](#rules) · [Theme](#theme) · [Status colours](#status-colours) · [Cell styles](#cell-styles) · [Type and spacing](#type-and-spacing) · [Icons](#icons) · [The layout file](#the-layout-file) · [Shortcuts](#shortcuts) · [Acceptance per view](#acceptance-per-view)

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

## The layout file

The window keeps no Qt settings file (D-105): Qt's dialogs would write the folders you open, which is project content. The **layout** is kept in one file of our own, `layout.ini`, in the per-user application configuration folder (on Linux `~/.config/System Budget Studio/`, on Windows `%APPDATA%\System Budget Studio\`). Only four groups of keys can be written to it (a test refuses anything else): `window` (geometry), `dock` (dock state), `columns` (table column widths) and `theme` (the mode). It never holds a project name, a path or a value. Delete the file to reset the layout; `BUDGET_CONFIG_DIR` moves it and `BUDGET_NO_LAYOUT=1` keeps nothing.

## Shortcuts

| Shortcut | Action | State |
|---|---|---|
| `Ctrl+N` / `Ctrl+O` / `Ctrl+S` | New (guided), open, save | in the window |
| `F5` | Reload the project | in the window |
| `Ctrl+M` | Edit the power modes of the selected unit | in the window |
| `Ctrl+E` / `Ctrl+Shift+E` | Export reports / export the power timeline | in the window |
| `F1` | User guide | in the window |
| `Ctrl+K` | Command palette | planned (step 6) |
| `Ctrl+Z` / `Ctrl+Shift+Z` | Undo / redo across edits | planned (step 2) |

## Acceptance per view

Every redesigned view is checked for: keyboard only · light and dark · a placeholder-heavy project · 200 units · a week at 1 s · an empty project · 1280 × 720 and 4K · tests green · no hard-coded colours.
