<!--
SPDX-FileCopyrightText: 2026 0h3xn4

SPDX-License-Identifier: Apache-2.0
-->

# Threat model

Last reviewed: 2026-11-10 (protection programme, phase 6; D-263). Change this page in the same pull request as a change that adds an input format, an output format, a dependency or a workflow.

## What is protected

| Asset | Why it matters |
|---|---|
| The user's computer and files | The program must not run code from a file, and must not read or write outside the folders the user chose. |
| The user's project content (design data, which can be confidential or export-controlled) | It must not leave the computer through the program: no network, no logs, no temporary files, no crash dumps. |
| The user's decisions based on the numbers | A wrong number is a safety problem. The numbers have golden tests, and a file must not change them without the user seeing it. |
| The release files | A user must be able to tell that a file is the one the maintainer's workflow built. |
| The maintainer's accounts and the repository | An attacker who owns them can ship harmful releases. |

## Who the attacker can be

1. **A stranger who sends a file.** A colleague, a customer or a download site sends a project folder, a unit table, a model file (`.idm`), a CSV or an XLSX. The user opens it. This is the main case.
2. **A stranger who proposes a change.** A pull request or an issue with a harmful workflow change, a dependency, or a file.
3. **A stranger who controls a dependency or an action.** A library or a GitHub Action is changed or replaced after it was reviewed.
4. **A stranger who tampers with a download.** A mirror or a network between the release page and the user.
5. **Not in scope:** an attacker who already runs code as the user. A program on the user's computer cannot defend against that.

## Where untrusted data comes in

| Input | Reader | Controls | Tests |
|---|---|---|---|
| Project files (YAML) | `io/yamlio.py` (ruamel.yaml, round-trip mode) | 1 MB, 20,000 lines, 50,000 characters per line, depth 64, 60,000 nodes; aliases, tags, merge keys and duplicate keys are refused; no PyYAML | `test_audit_yaml.py`, `test_hostile_inputs.py`, `test_code_safety.py` |
| Paths inside project files | `io/paths.py` (`resolve_inside`) | A path must stay in the project folder, also through symbolic links | `test_hardening_paths.py` |
| IDM model (zip with XML) | `idm/archive.py`, `idm/xmltree.py` | Never extracted; only `model.xml` at the root is read; 200 MB archive, 100 MB XML, 20,000 entries; XML read by `defusedxml` (no document type, entities or external references), 200 levels, 5 million nodes | `test_idm_archive.py`, `test_hostile_inputs.py` |
| Unit tables (CSV, XLSX) | `io/unit_table.py`, `io/entry_tables.py` | 5 MB file, 50 MB unpacked, 100,000 rows, 50 columns; formulas are not evaluated (`data_only`); `openpyxl` reads XML through `defusedxml` | `test_unit_table.py`, `test_hostile_inputs.py` |
| Environment files (CSV, interim formats) | `environment/` | 250 MB per file, 2 million rows (100,000 for passes and eclipses); site names in file names go through `safe_name` | `test_spacemissionstudio.py`, `test_hostile_inputs.py` |

## Where data goes out

| Output | Risk | Control | Tests |
|---|---|---|---|
| CSV, XLSX and report text from project text | A spreadsheet runs `=...` as a formula | CSV: one apostrophe in front of text that starts with `= + - @` tab or CR (numbers and plain words are not changed); XLSX: cells forced to text | `test_formula_injection.py`, `test_hardening_output.py` |
| File names from project text | A name like `../x` writes outside the folder | `safe_name`; staged, atomic writes inside the output folder; a link is replaced, never followed | `test_hardening_output.py`, `test_hostile_inputs.py` |
| Network | Project content leaves the computer | The code has no network module; sockets are blocked in the test and the whole workflow runs under `strace` and under a Windows firewall rule | `tests/offline/`, `test_code_safety.py` |
| Logs, temp files, crash dumps | Project content is left behind | None are written; a canary test searches for project text | `tests/offline/test_privacy_canary.py` |

## Supply chain

| Threat | Control |
|---|---|
| A library is replaced or has a known vulnerability | Hashed lock files (`--require-hashes`); weekly `pip-audit` and on every lock change; dependency review (once the owner enables the Dependency graph); Dependabot for the version ranges; the list of libraries in the SBOM |
| An action is changed after review | Every action is pinned to a full commit id (a test checks it); Dependabot proposes the update |
| A workflow runs with too many rights | Read-only default token (a test checks it); writes only in jobs that use the `release` environment (a test checks it); no `pull_request_target` (a test checks it); no text from a pull request in a shell script (a test checks it) |
| A harmful pull request is merged | Review by the maintainer; required checks (owner setting) |
| A release is published without review | The `publish` job needs the approval of a required reviewer in the `release` environment (owner setting); a new release is a draft until the owner publishes it |
| A download is replaced | `SHA256SUMS`; signed build attestations (`gh attestation verify`); the compliance record lists the hashes. There is no code-signing certificate (see [signing options](../legal/signing-options.md)) |
| A secret is committed | gitleaks on every pull request and push; GitHub secret scanning and push protection (owner setting) |

## Not covered (known limits)

- **The computer is trusted.** Project files are plain text; there is no encryption.
- **Native libraries.** Qt, Pillow, NumPy and the others are C and C++ code. A flaw in them can be reached through a crafted image or font. The audit and the update policy are the controls; the tests do not cover it.
- **A large legitimate file.** The limits are set far above real files. A file just below a limit can still use time and memory (seconds, hundreds of megabytes).
- **The builds are not reproducible bit for bit.** See [security.md](security.md#reproducible-builds).
- **The Windows installer is unsigned.** SmartScreen warns on first run.
- **PDF and DOCX viewers.** The reports contain project text. A viewer's own flaws are not in scope.
