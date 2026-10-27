# Developer docs

This page is for people who change System Budget Studio: how the repository is laid out, how to test and lint, how generated files are kept in step, how to keep the documentation true, and how to cut a release. For the first set-up see [CONTRIBUTING](../../CONTRIBUTING.md).

**Contents:** [Layout](#layout) · [Test, lint, type-check](#test-lint-type-check) · [Generated files](#generated-files) · [Golden files](#golden-files) · [The offline test](#the-offline-test) · [Keep the documentation true](#keep-the-documentation-true) · [Build the installers](#build-the-installers) · [Cut a release](#cut-a-release) · [Upstream documents](#upstream-documents)

## Layout

```text
src/budget_core/   the headless core: model, units, environment, power, mass, thermal, link, reports, guide
src/budget_cli/    the `budget` command (depends only on the core)
src/budget_gui/    the PySide6 window (depends only on the core): theme/ (tokens, fonts, style sheet, the only place for colours and sizes), components/ (buttons, badges, cards ...), one module per view
tests/             unit, regression, golden, gui, offline
scripts/           measuring and screenshot tools for the window (ui_screenshots.py, ui_baseline.py, ui_access_audit.py, ui_scale_shots.py, ui_gallery.py)
docs/              this documentation; docs/demo = milestone notes; docs/ui = the plan and the screenshots of the UI overhaul
examples/          the four example projects (generated; invented data)
packaging/         PyInstaller spec, Linux and Windows installers, licence and bundle checks
assets/            bundled fonts, licence texts and the application icon (assets/icons)
```

The [architecture overview](../ARCHITECTURE.md) explains the design: pure solvers over NumPy arrays, `Problem` records instead of exceptions for user errors, configuration with sources, and the decision numbers ([DECISIONS.md](../DECISIONS.md)) behind each choice. The rule that matters most when you add code: **the core imports neither the GUI nor anything networked**, and the CLI and GUI call the same core functions, so they cannot disagree.

## Test, lint, type-check

```bash
pip install -e ".[dev]"
QT_QPA_PLATFORM=offscreen pytest                 # everything (about 30 minutes in one process: the core tests about 8, the window tests about 22)
QT_QPA_PLATFORM=offscreen pytest tests/unit      # one folder; the quick loop while you work
pytest tests/offline                             # the no-network test
ruff check . && ruff format --check . && mypy    # lint, format, strict types
```

Tests are in five groups: `unit`, `regression` (hand-calculated reference cases, with the working in comments), `golden` (stored expected reports), `gui` (pytest-qt, offscreen) and `offline`. Properties are checked with Hypothesis. Tests marked `perf` time the one-week stress case and how long a worker thread may keep the window thread waiting (D-183); they fail only above three times the target (`tests/perf_limits.py`).

CI ([`.github/workflows/ci.yml`](../../.github/workflows/ci.yml)) runs ruff, mypy and pytest on Ubuntu and Windows with Python 3.11 and 3.13, and checks that a runtime-only install (`pip install -e .`) gives a runnable `budget`. Actions are pinned to commit SHAs.

## Working on the window

The rules are in [DESIGN.md](../DESIGN.md) and [CLAUDE.md](../../CLAUDE.md). The ones that bite:

- **Colours, fonts and sizes live in `budget_gui/theme/` only.** Take sizes from `theme.gap()`, `theme.inset()` and `theme.px()`, fonts from `theme.ui_font()` and `theme.mono_font()`, colours from `theme.tokens()`. A test fails on a hex colour, a font family or a pixel size anywhere else.
- **Nothing longer than about 50 ms on the window thread.** Computations run in a `QThread` worker; a worker that makes the plot also prepares it (`plot_prepare.py`, D-182). A long NumPy or SGP4 call in the core goes in slices (`budget_core/slices.py`) so that the window can have the interpreter lock between them; `create_app` shortens the switch interval for the same reason (D-183). `tests/unit/test_worker_responsiveness.py` guards it.
- **A view that can be large uses model and view**, not `QTableWidget`. The small result tables of the scenario, the timeline and the link passes are `QTableWidget`s, filled in turns so that no turn is long.
- **The window opens in the focused view** (`DEFAULT_VIEW` in `main_window.py`, D-191): a new panel or column that matters must stay reachable in the full view and from the View menu. Most window tests look at the Inspector, the Problems list or the optional columns, so `tests/gui/conftest.py` starts every test in the full view; `tests/gui/test_focused_view.py` puts the default back and tests it. Anything that points at a problem must open the list (`MainWindow.reveal_problems`).
- **A form that adds a file** (*Add unit*, *mode*, *scenario*, *expendable*, *ground station*, *imaging target*, *link*, *Eb/N0 entry*; D-187 to D-200) has the same four parts. The core builder `budget_core/new_<thing>.py` holds an `…Answers` dataclass, `check_<thing>` (a list of `Issue(field, message)`; the messages name fields, never values read from a file) and `<thing>_data` (plain data through the model, the last check). The dialog `budget_gui/add_<thing>_dialog.py` starts empty, shows no error until the user has typed something and keeps its Add button off until the checks pass. `MainWindow.add_<thing>` collects the ids that exist (the loaded project plus those added and not saved yet), asks through a `_ask_<thing>` method that tests replace, and adds the file with `document.add_file`, which is one undo step; its `QAction` has a shortcut, an entry in `model_edit_actions()` and so appears in Ctrl+K. A number that comes from a standard or a data sheet is never asked for with a default: it is written as a placeholder (`source: TBD`). Write the tests first (`tests/unit/test_new_<thing>.py`, `tests/gui/test_add_<thing>.py`) and change the pages in the table below.
- **Every control that shows only an icon has a tooltip and an accessible name**; `scripts/ui_access_audit.py` lists what is missing and `tests/gui/test_accessibility.py` fails on it.
- **Measure before you tune.** `scripts/ui_baseline.py` measures start-up, tab switches and the heaviest interactions; for a stall, a heartbeat timer on the window thread plus `faulthandler.dump_traceback_later` on the worker shows who holds the interpreter lock (D-183).

## Generated files

Some files are produced by code and checked by tests, so they cannot drift:

| File | Regenerate with | After changing |
|---|---|---|
| `src/budget_core/schemas/*.schema.json` | `budget export-schemas src/budget_core/schemas` | the model |
| `examples/` | `budget export-examples examples --force` | the example builders |
| `docs/LICENCES.md` | `python packaging/licence_check.py --markdown docs/LICENCES.md` | the dependencies |
| `requirements.lock`, `requirements-dev.lock` | `packaging/lock.sh` (uses `uv`; needs a network) | `pyproject.toml` dependencies |
| `assets/icons/logo-*.png`, `assets/icons/logo.ico` | `python packaging/make_icons.py` (the same drawing as `docs/images/logo.svg`) | the logo |
| `tests/golden/*` | `UPDATE_GOLDEN=1 pytest tests/golden`, then **read the diff** | a deliberate change of a report |

## Golden files

A golden test builds a report, dumps its content as text (cell values, PDF text, DOCX paragraphs, JSON) and compares it with a stored copy. Compressed bytes are never compared (they differ between zlib builds). Numbers that depend on the platform's floating point are rounded in the dump (6 or 9 significant digits; values below 1e-6 count as zero in the thermal goldens). When a golden changes, review the diff and explain it in the pull request.

## The offline test

`tests/offline/test_offline.py` runs the CLI and the offscreen window in a fresh interpreter with sockets blocked, and fails if a networking module (`http.client`, `urllib.request`, `ssl`, `requests`, `PySide6.QtNetwork`, …) is imported. ReportLab's networking modules are imported lazily for this reason. Keep it green: it is the proof of the no-network promise.

## Keep the documentation true

When behaviour changes, change these in the same pull request:

| If you change… | Update |
|---|---|
| a CLI option or exit code | `--help` text, [command-line reference](../user-manual/command-line.md), [getting started](../getting-started.md) if shown there |
| the file format | [FILE_FORMAT.md](../FILE_FORMAT.md), the schema version and a migration, the matching [user manual](../user-manual/README.md) page and the **in-app guide chapter** ([`src/budget_core/guide/chapters/`](../../src/budget_core/guide/chapters/)) |
| a problem code | [FILE_FORMAT.md](../FILE_FORMAT.md) code list, guide chapter 11, [read and fix problems](../user-manual/read-and-fix-problems.md) |
| an example project | [examples/README.md](../../examples/README.md): its expected output |
| a menu, an area of the window or a shortcut | [use the window](../user-manual/use-the-window.md), the screenshots in [`docs/images/`](../images/), the in-app guide chapter *Quick start* |
| a colour, a font, a size or a component of the window | `budget_gui/theme/` and [DESIGN.md](../DESIGN.md) (its tables are checked by a test; a colour, a font family or a pixel size anywhere else in `budget_gui/` fails the build) |
| anything the window keeps or writes outside a project folder | [use the window](../user-manual/use-the-window.md#where-does-the-window-keep-its-layout), the in-app guide chapter *Installing and uninstalling*, the install checklist |
| any decision or simplification | [DECISIONS.md](../DECISIONS.md) / [DEVIATIONS.md](../DEVIATIONS.md) and the [CHANGELOG](../../CHANGELOG.md) |

A test holds part of this in place (`tests/unit/test_docs_match_program.py`): every `budget ...` command shown in a code block must be accepted by the real parser, every option must be in the command-line reference, every field of every JSON Schema must be named in a file-format page, and every page must be linked from another page. It runs with the unit tests, in a second.

The manual pages (task-oriented) and the in-app guide chapters (topic-oriented, shipped with the tool) overlap on purpose; change both. Check links before you push, with [lychee](https://github.com/lycheeverse/lychee):

```bash
lychee --offline --include-fragments --no-progress README.md CONTRIBUTING.md CHANGELOG.md 'docs/**/*.md' 'examples/**/*.md'
```

To regenerate the screenshots run the window offscreen (`QT_QPA_PLATFORM=offscreen`), open `examples/microsat_250kg_eps`, show the area, and save `window.grab()` to `docs/images/ui-overhaul/`. `scripts/ui_screenshots.py DIR` saves every page and dialog in both themes, and `scripts/ui_scale_shots.py DIR` every page at 90 to 125 %. Run every command in [getting started](../getting-started.md) in a fresh virtual environment now and then; the commands there are the documentation's tests.

## Build the installers

The installers are built by CI ([`release.yml`](../../.github/workflows/release.yml)); locally:

```bash
pip install -e ".[dev]"
packaging/build.sh                        # one-folder bundle in dist/, SBOM, licence report, bundle check
packaging/linux/build_in_container.sh     # the Linux release, inside rockylinux:8 (old glibc): tarball, .deb, .rpm
python packaging/linux/make_deb.py dist/system-budget-studio --out dist   # only the .deb, from a built bundle
packaging/linux/make_rpm.sh dist/system-budget-studio dist                # only the .rpm (needs rpmbuild)
sudo packaging/linux/test_package.sh deb dist/*.deb                       # install, check, remove (use a container)
```

`packaging/check_bundle.py` fails the build if development code is bundled, licence material is missing or the bundle holds no Python of its own (the installers need none on the machine; the Windows setup always adds its folder to the user PATH, D-184). `system-budget-studio --smoke` creates the window and exits; CI runs it on every platform. See the decisions D-088, D-089, D-095, D-096 and D-184.

## Cut a release

1. Decide the version `X.Y.Z` and set it everywhere it is written: `pyproject.toml` (`version`) and `src/budget_core/__init__.py` (`__version__`; a test checks that these two agree), the comment with the version in `packaging/linux/system-budget-studio.spec` and in `packaging/windows/system_budget_studio.iss`, and the sample output of `budget --version` and the status line in `README.md` and `docs/getting-started.md`. `git grep` for the old version finds them; leave the mentions in `CHANGELOG.md`, `DECISIONS.md` and the historical pages alone. Then regenerate the golden files with `UPDATE_GOLDEN=1 pytest tests/golden` and read the diff: only the version line (`System Budget Studio X.Y.Z | …`, `tool_version`) and the one hash that covers it may change.
2. If dependencies changed run `packaging/lock.sh` and `python packaging/licence_check.py --markdown docs/LICENCES.md`.
3. Update [CHANGELOG.md](../../CHANGELOG.md): move *Unreleased* under the new version with the date.
4. Merge to `main` through a pull request with CI green.
5. Tag **after** the pull request is merged, and tag the merge commit: `git fetch origin && git tag vX.Y.Z origin/main && git push origin vX.Y.Z` (or, with no local clone, **Releases > Draft a new release** on GitHub: *Choose a tag*, type `vX.Y.Z`, *Create new tag on publish*, target `main`, then publish; `main` is whatever it is at that moment, so merge nothing else first, or type the commit of the release pull request as the target, otherwise the tag lands on the newest commit and the release contains it). A tag on an earlier commit has the old version in `pyproject.toml`, and the workflow refuses it (the run fails at once, nothing is attached): delete the tag and the release, and tag again. The **Installers** workflow runs: it refuses a tag that differs from the `pyproject.toml` version, builds the Linux bundle on Rocky 8 and the Windows installer and portable zip, installs and uninstalls each as an ordinary user, makes the `.deb` and the `.rpm` of the Linux bundle and installs and removes them on clean Ubuntu 22.04 and 24.04, Debian 12 and Rocky 8 and 9 containers (`packaging/linux/test_package.sh`, with the window started on a virtual X server), and uploads the artefacts: the installers, the `.deb` and `.rpm`, `SHA256SUMS.txt`, `sbom.cdx.json` and `licences.md`. Its last job (`publish`, D-144) then checks every file against the checksum lists and attaches the files to the release of the tag with `packaging/attach_release.sh`; a release that does not exist yet is created as a **draft**, so nothing becomes public by itself.
6. Download the artefacts and carry out the manual steps of the [clean-machine checklist](../INSTALL_CHECKLIST.md) on a clean Windows and a clean Rocky 8 machine.
7. Publish: write the description of the release (a release made from a tag has an empty one; say what changed, the download table and the known limits) and press **Publish** (the files are attached already). If you made the release in the browser in step 5, it is public from that moment and the files are attached by the workflow 15 to 25 minutes later: mark it *pre-release* until they are there, then edit it and make it the latest release. To attach the files of an earlier run to a release, start **Actions > Attach release files** with the run id and the tag.

## Upstream documents

This repository is not a fork and was not derived from another project, so there is no upstream README to keep in step: `README.md` is the only README of the project.

Next: [Architecture](../ARCHITECTURE.md) · [Decisions](../DECISIONS.md) · [Docs index](../README.md).
