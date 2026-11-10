# Contributing

This page tells you how to set up a development copy of System Budget Studio, what the rules of the project are, and how to get a change merged. The details are in the [developer docs](docs/developer/README.md).

## Set up

```bash
git clone https://github.com/0h3xn4/SystemBudgetStudio.git
cd SystemBudgetStudio
python3 -m venv .venv && source .venv/bin/activate     # Windows: py -3 -m venv .venv ; .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
QT_QPA_PLATFORM=offscreen pytest                       # about 23 minutes; quick loop: pytest tests/unit or pytest -m "not slow". Windows PowerShell: $env:QT_QPA_PLATFORM="offscreen"; pytest
ruff check . && ruff format --check . && mypy
```

If the tests pass and the three checks print nothing worrying, you are ready. On Linux the window tests need the libraries listed in the [troubleshooting page](docs/troubleshooting.md#start-the-window).

## The rules of the project

These are enforced by tests and review (the full list is in [CLAUDE.md](CLAUDE.md) and the [specification](docs/SPEC.md)):

- **Tests first.** Write the failing test, then the code. Solvers need hand-calculated reference cases.
- **No warnings on `main`**: ruff, ruff format and mypy (strict) are clean.
- **Offline.** The core imports no GUI and no networking module; a test checks it.
- **Never invent standards values.** Numbers live in config files with a `source`; unknown is `source: TBD`.
- **Units are in the field names** (`power_w`, `freq_hz`, `gain_dbi`).
- **No project content in logs, temp files, crash dumps or messages**: messages name fields, ids and units only.
- **Example projects contain invented data only.**
- **The window follows [DESIGN.md](docs/DESIGN.md)**: colours, fonts and sizes live in `budget_gui/theme/` only (a test fails otherwise), a status always has an icon or text as well as a colour, and nothing runs for longer than about 50 ms on the window thread.
- **Runtime dependencies only in `[project.dependencies]`**; all tooling in the `dev` extra.
- **Record decisions** in [DECISIONS.md](docs/DECISIONS.md) and physics simplifications in [DEVIATIONS.md](docs/DEVIATIONS.md). A change to the file format needs a schema version bump and a migration ([FILE_FORMAT.md](docs/FILE_FORMAT.md)).

## Licence of contributions, origin and sign-off

System Budget Studio is a personal project of its owner. It is not affiliated with, sponsored by or endorsed by any employer or organisation. The source code is licensed under the [Apache License 2.0](LICENSE) (see [NOTICE](NOTICE)); a contribution is accepted under the same licence, as section 5 of that licence says.

- **Developer Certificate of Origin.** Every commit of a pull request must carry a `Signed-off-by: Your Name <you@example.org>` line (`git commit -s` adds it). By signing off you confirm the [Developer Certificate of Origin 1.1](https://developercertificate.org/): you wrote the change or have the right to submit it under this licence, and you know it is public and kept for good. A CI check (`DCO`, `packaging/dco_check.py`) fails a pull request with an unsigned commit.
- **You must have the right to submit what you submit.** Do not submit work that belongs to your employer, a customer or anyone else unless they allowed it in writing.
- **No copied code or text.** Do not paste code, text, tables or images from elsewhere unless its licence is compatible with the Apache License 2.0 and you keep its copyright and licence notice and add it to [docs/LICENCES.md](docs/LICENCES.md) or the file's header. Quotes from standards and papers stay short and carry their source.
- **Say it when an AI tool wrote it.** If an AI tool wrote part of your change, say so in the pull request. You are responsible for the change: read it, run the tests and sign it off yourself.
- **Never post confidential, proprietary, export-controlled, personal or customer data**: not in code, examples, test files, screenshots, issues or pull requests. Example data is invented. Files of IDM-CIC or other third-party tools are never committed (a test enforces it for `.idm` files).
- **The project is non-commercial.** It has no sales, paid features, paid support, advertising, donations or sponsorship, and proposals to change that are out of scope.
- **Every file carries its licence.** A new Python file starts with the two SPDX lines (`reuse annotate --copyright "<holder>" --year <year> --license Apache-2.0 <file>`); other files are covered by `REUSE.toml`. `reuse lint` must pass (CI job `REUSE`).
- **The owner may refuse any contribution of unclear origin**, and may edit or delete issues, comments and pull requests that break these rules.

## Make a change

1. Work on a branch; never push to `main`.
2. Make the change with tests. If you change the model or an example, regenerate the generated files (`budget export-schemas src/budget_core/schemas`, `budget export-examples examples --force`): the tests fail when they drift.
3. Update the documentation that describes the behaviour ([which pages](docs/developer/README.md#keep-the-documentation-true)) and add an entry to [CHANGELOG.md](CHANGELOG.md).
4. Sign off every commit (`git commit -s`) and open a pull request into `main`. CI must pass on Windows and Linux with Python 3.14. A change that touches `packaging/` also runs the installer workflow.

## Reporting a problem

Say what you ran (`budget --version`, the command), what you expected and the message you got. Messages never contain project values, so you can paste them; do not attach project files that may be sensitive.

Next: [Developer docs](docs/developer/README.md) · [Architecture](docs/ARCHITECTURE.md).
