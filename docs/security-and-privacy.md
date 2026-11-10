# Security and privacy

This page says what System Budget Studio does with your data, what it does not do, and how you can check each statement yourself, on your own computer, without trusting this page. It is written for the engineer who has to answer *"does this tool send anything out?"* before it is allowed on a work machine.

**Contents:** [What the program is built to do](#what-the-program-is-built-to-do) · [What it writes and where](#what-it-writes-and-where) · [Check it yourself](#check-it-yourself) · [What the project checks on every change](#what-the-project-checks-on-every-change) · [Check a download](#check-a-download) · [What is not covered](#what-is-not-covered) · [Report a problem](#report-a-problem)

## What the program is built to do

1. **No network use while running.** The program never opens a connection to any address, local or remote. It has no account, no licence check, no update check, no online help, no crash upload and no usage statistics.
2. **No project content outside your folders.** Names, values, paths and results of a project are written only to the project folder and to the output folder you choose. They are not in logs, in temporary files, in crash files or in the program's own settings.
3. **The only file the window keeps for itself is a layout file** (`layout.ini`): window size and position, the theme, which panels are open, and the name you may type under **Settings → Name in report files** (empty by default). It holds no project name and no path. `BUDGET_NO_LAYOUT=1` makes the window keep nothing; `BUDGET_CONFIG_DIR=<folder>` puts that file in a folder you choose.
4. **The two support aids are off unless you use them and contain no project.** `--diagnose` reports versions, screens and whether fonts and icons were found. `--fault-log` writes the Python stack of each thread if the process dies of a native fault. Both write to a file you name; neither sends anything.
5. **The installers and the program are built from the source in this repository**, by a workflow that anyone can read (`.github/workflows/`), from locked and hashed dependencies.

These are statements that a test or a command below can show to be false. If you find a counter-example, that is a defect: see [Report a problem](#report-a-problem).

## What it writes and where

| What | Where | Holds project content? |
|---|---|---|
| Your project | the project folder you create or open | yes, it is the project |
| Results, reports, exports, the user guide | the output folder you give (`--out`) or choose in the window | yes, they describe the project |
| Window layout (and the name for report files, if you typed one) | `layout.ini` in the program's settings folder under your user profile (`system-budget-studio --diagnose` prints the exact path; on Linux it is under `~/.config`), or `BUDGET_CONFIG_DIR`, or nowhere with `BUDGET_NO_LAYOUT=1` | no |
| Fault log, diagnose report | the file you name, only when you ask for it | no |
| Installation | the install folder, a Start-menu shortcut and, on Windows, the uninstall entry and one per-user `PATH` entry so that `budget` works in a terminal (all removed on uninstall) | no |

### What an exported file says about you

Every report and export carries a provenance block (a sheet, a table or a JSON object, and the properties of the XLSX, PDF and DOCX file):

| Item | Value |
|---|---|
| User | `--user`, else `BUDGET_USER`, else the name you typed under **Settings → Name in report files**, else `unknown`. **The program never reads your login name**, and it reads no host name. |
| Tool, Python and library versions | those of the program that wrote the file |
| Project name, revision, scenario | from the project |
| Input files | the **relative** paths, sizes and SHA-256 hashes of the project files it read (never absolute paths, never their content) |
| Generated (UTC) | the clock, `--date` or `SOURCE_DATE_EPOCH` |
| Disclaimer | the one disclaimer text of the program |

A file that you share therefore does not name you unless you chose to. The project name and the numbers in it are yours: check them before you send a file (see [what is not covered](#what-is-not-covered)).

The installer writes to the registry only the uninstall entry and the per-user `PATH` entry (`HKCU\Environment`); it needs no administrator rights. The portable zip writes no registry entry.

## Check it yourself

You do not need to read the source. Pick the level of effort you need.

### 1. Look at what the program is made of (a few minutes)

- `sbom.cdx.json` and `licences.md`, attached to every release, list every library in the bundle with its version and licence. There is no networking library in it: no `requests`, `urllib3`, `httpx`, `aiohttp`, and the Qt networking module (`QtNetwork`) is excluded from the bundle. (ReportLab, the PDF library, imports the standard `ssl`, `http.client` and `urllib.request` modules because it can fetch pictures from a web address; the tool restricts it to local files, D-043, and the test below proves no connection is made.)
- From source: `pip list` after `pip install .` shows the same runtime libraries, and `pyproject.toml` lists them under `[project.dependencies]`.

### 2. Run the whole workflow with the network cut (about 15 minutes)

Disconnect the computer from the network (or work in a machine with no route out), install, and run:

```
budget --version
budget self-test
system-budget-studio                # open the 250 kg example, run all budgets, close
```

Everything works the same. A program that needs a server to start, or to compute, fails here. For an air-gapped install see [offline install](getting-started.md#offline-install).

### 3. Watch every connection attempt (30 minutes, Linux)

With `strace` (needs no administrator rights for your own process):

```
strace -f -qq -e trace=network -o trace.txt budget run examples/microsat_250kg_eps --budget all --out out
grep -E 'AF_INET6?' trace.txt          # no output: no internet address was touched
```

`scripts/verify_offline.py` does this for the whole workflow (validate, run all budgets, scenario, power timeline, link passes, thermal, explain, compare, spreadsheet export and import, the guide) and, with `--gui`, for a start of the window. It first connects to `127.0.0.1:9` on purpose to show that its detector really sees a connection, then fails on any `connect`, `sendto`, `sendmsg`, `sendmmsg` or `bind` to an internet address:

```
python scripts/verify_offline.py                                  # command line
python scripts/verify_offline.py --gui "$(which system-budget-studio)"   # and the window
```

### 4. Block the program in the firewall (30 minutes, Windows)

In an elevated PowerShell, block outbound traffic for the program, then use it:

```
New-NetFirewallRule -DisplayName "block SBS" -Direction Outbound -Program "C:\Path\To\system-budget-studio.exe" -Action Block -Profile Any
New-NetFirewallRule -DisplayName "block budget" -Direction Outbound -Program "C:\Path\To\budget.exe"            -Action Block -Profile Any
```

Everything still works. To see attempts instead of blocking them, turn on *Windows Firewall with Advanced Security → Properties → Logging → Log dropped packets* and read `pfirewall.log` after the session, or use Resource Monitor → Network → TCP connections while the program runs. Remove the rules afterwards with `Remove-NetFirewallRule -DisplayName "block SBS","block budget"`.

### 5. Look for your data outside your folders (30 minutes)

Create a project whose name is a word you can search for (for example `CanaryZq7`). Run the budgets, close the window. Then search the user profile, the temporary folder and the install folder for that word, in plain text and in UTF-16:

```
grep -rIl CanaryZq7 ~ /tmp 2>/dev/null                     # Linux: only your project and output folders
Get-ChildItem -Recurse $env:USERPROFILE,$env:TEMP -ErrorAction SilentlyContinue | Select-String -Pattern CanaryZq7 -List   # Windows
```

The project folder and the output folder will be found; nothing else should be.

### 6. Capture the traffic of the whole machine (an hour, with your network team)

Run Wireshark (or the network team's tap) on the computer while the program runs the workflow above. Filter on the program's process (Wireshark with an Event Tracing capture on Windows, or `ss -tup` on Linux) and look for any packet it sent. This is the level to use for a formal sign-off; levels 3 and 4 give the same answer with less effort.

## What the project checks on every change

Each of these runs in the project's continuous integration; a change that fails any of them is not merged.

| Check | What it proves | Where |
|---|---|---|
| No networking module is imported by the core, the command line, the file formats or the window's start (PDF excepted, see D-043); sockets are blocked and any attempt fails the test | The code has no network path in the normal run | `tests/offline/test_offline.py` |
| The whole workflow runs under `strace` on Linux and fails on any connection, `sendto` or `bind` to an internet address; a deliberate connection proves the detector works | The program does not touch the network while doing real work | `scripts/verify_offline.py`, job *Offline evidence (Linux, strace)* |
| The same workflow runs on Windows with the outbound traffic of the Python programs blocked in the firewall; a control connection must fail first, so a firewall rule that does nothing cannot pass | The program does not need or use the network on Windows | job *Offline evidence (Windows, outbound firewall block)* |
| A project whose name, unit name, source text and folder carry a unique marker is run through the command line and the window in an empty sandbox; no file outside the project and output folders may contain the marker (UTF-8 or UTF-16), and the only file kept is the layout file | No project content leaks into logs, temporary files, caches or settings | `tests/offline/test_privacy_canary.py` |
| `pip-audit` checks the locked dependencies against the public vulnerability database every week and when a lock changes | The libraries in the program have no known vulnerability, or the failure is visible | `.github/workflows/audit.yml` |
| Dependencies are installed from lock files with hashes (`--require-hashes`) | The libraries are the ones that were reviewed | `requirements.lock`, `requirements-dev.lock`, `packaging/lock.sh` |
| Files from strangers are tested: bombs, external entities, path tricks, spreadsheet formulas; the source is scanned for code that could run file content, start a program or use the network; XML is read with `defusedxml` | A crafted file is refused and cannot run code, read other files or use the network | `tests/unit/test_hostile_inputs.py`, `test_formula_injection.py`, `test_code_safety.py` |
| The workflows are checked: actions pinned to a commit, a read-only token, no `pull_request_target`, writes only in the `release` environment; CodeQL, a secret scan, a dependency review and the OpenSSF Scorecard run in CI | The build and the release cannot be changed by a stranger without a trace | `tests/unit/test_workflows.py`, `.github/workflows/` |
| Licences are checked: permissive or LGPL only | No library with a licence that forbids the use | `docs/LICENCES.md` |

The first three are statements about this tool, not about its libraries; the evidence for the libraries is the list of libraries (`sbom.cdx.json`) and the audit.

## Check a download

Every file attached to a release has three independent checks, and the release has a record of them:

1. **Checksum.** `SHA256SUMS-windows.txt` and `SHA256SUMS-linux.txt` list the SHA-256 of each file. On Windows: `Get-FileHash <file> -Algorithm SHA256`; on Linux: `sha256sum -c SHA256SUMS-linux.txt`. This detects a damaged or replaced download, if the list itself came from the release page.
2. **Build attestation (from 2.11.2 on).** The release workflow records, with a signature from GitHub (Sigstore, no key to manage), which workflow run, on which commit, built each file. With the GitHub CLI:

   ```
   gh attestation verify system-budget-studio-<version>-linux-x86_64.tar.gz --repo 0h3xn4/SystemBudgetStudio
   ```

   A file that was not built by that repository's release workflow, or that was changed afterwards, fails. This is stronger than a checksum, because a checksum and a file can be replaced together.
3. **The source.** The tag `v<version>` names the commit; the workflows that built the files are in `.github/workflows/` at that commit, and `packaging/` holds the build scripts.

The release also carries `COMPLIANCE-RECORD.md`: every file with its size and SHA-256, the software bill of materials, the licence lists and notices, the source code of the LGPL parts, and the result of the REUSE and `pip-audit` checks that ran before the release (a check that did not run says *not run*). The builds are not reproducible bit for bit; the [developer guide](developer/security.md#reproducible-builds) says what is and what is not.

**The Windows installer is not code-signed.** Windows SmartScreen and some virus scanners therefore warn about it ("unknown publisher"). Signing needs a code-signing certificate from a certificate authority, and the project does not use one. Use the checksum and the attestation above instead, and let your security team scan the file. The options for signing are in [docs/legal/signing-options.md](legal/signing-options.md). If your organisation requires a signed installer, it can sign the downloaded file with its own certificate, or build from source (`pyinstaller packaging/system_budget_studio.spec`).

## What is not covered

Be clear about the limits when you answer the question.

- **The computer is trusted.** The tool does not encrypt project files; it relies on the operating system's access rights and disk encryption. A project folder is plain text on purpose.
- **Dependencies can still have vulnerabilities that are not yet known** or that the database does not list. The audit lowers the risk; it does not remove it.
- **A tested statement is true for the tested workflow.** The checks above run the commands and the window start and a run of all budgets; they do not click through every menu. A defect in a rarely used path is possible; the manual levels 3 and 4 let you test your own path.
- **Files you exchange are yours.** An exported report, a spreadsheet or a project zip carries the project's content to whoever you send it to. Check the content before you share it.
- **There is no plug-in or macro mechanism**, so no third-party code is loaded at run time apart from the libraries in the bundle (Qt loads its own graphics and image plug-ins from the bundle's folder).

## Report a problem

For a security problem (a file that makes the program do harm, a vulnerable library, a release file that does not verify) use the private report described in [SECURITY.md](../SECURITY.md): the **Security** tab of the repository, then **Report a vulnerability**. For anything else, for example a connection you did not expect or a file with project content outside the folders above, open an issue. A public issue is visible to everyone: describe what you ran and on which version (`budget --version`), and quote only the lines of the trace or the file names that show the problem, after checking that they contain no project name, path or value. Never attach a project, a report or a whole log.

Next: [FAQ](faq.md) · [Troubleshooting](troubleshooting.md) · [Docs index](README.md).
