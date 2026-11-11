<!--
SPDX-FileCopyrightText: 2026 0h3xn4

SPDX-License-Identifier: Apache-2.0
-->

# Security of the code, the build and the release

What the project does, where it is checked, and what the owner must set on GitHub. The threats are in [threat-model.md](threat-model.md); how to report a problem is in [SECURITY.md](../../SECURITY.md). Decision: D-263.

## Rules for code that reads or writes files

- Everything read from a file is data. Never `eval`, `exec`, `compile`, `__import__`, `importlib`, `pickle`, `marshal`, `subprocess`, `shell=True`, a network module, or PyYAML. `tests/unit/test_code_safety.py` reads every source file and fails on them. An exception needs a line in its `ALLOWED` table with a reason.
- YAML is read with `ruamel.yaml` in `typ="rt"` mode through `io/yamlio.py` (limits, no aliases, no tags). A new reader of YAML calls `load_yaml_text` first.
- XML is read with `defusedxml` (`idm/xmltree.py`). The standard library parsers are not imported (the same test).
- Every size is bounded while reading, not after (`read_limited`, `handle.read(limit + 1)`). A size written in a file header is not trusted.
- A path from a file goes through `resolve_inside`; a name from a file goes through `safe_name`.
- Text that goes into CSV uses `csv_writer` (`reports/csvutil.py`), which defuses spreadsheet formulas. A raw `csv.writer` is allowed only in `csvutil.py` and in the one export that writes numbers (`test_formula_injection.py`).
- A message or hint never contains text read from a file (CLAUDE.md). A new input format also needs: a limit test, a hostile-file test in `tests/unit/test_hostile_inputs.py`, and a row in the threat model.

## Dependencies

- Runtime and development libraries are installed from `requirements.lock` and `requirements-dev.lock` with `--require-hashes`. Make them with `packaging/lock.sh` (uv, universal, hashes). Install from source the same way: `pip install --require-hashes -r requirements.lock` and then `pip install --no-deps -e .` (see [getting started](../getting-started.md)). The build tool `hatchling` is the one thing that is fetched without a hash; it is not part of what is installed.
- `.github/workflows/audit.yml` runs `pip-audit` on both locks every Monday, on a change of a lock or of `pyproject.toml`, and on request. A finding fails the run.
- `.github/workflows/dependency-review.yml` fails a change that adds a package with a known vulnerability of high or critical severity. It needs the repository's Dependency graph (on since 2026-11-11) and runs on every pull request that changes `pyproject.toml`, a lock file or a workflow; `pip-audit` (above) also runs on every lock change.
- `.github/dependabot.yml` proposes updates of the actions (and of the ranges in `pyproject.toml`). Nothing merges by itself. After a change of `pyproject.toml` run `packaging/lock.sh` and commit the locks, because Dependabot does not make hashed locks. Dependabot commits cannot carry a `Signed-off-by` line; the DCO check lets exactly that bot address through (`packaging/dco_check.py`), and the person who merges the pull request takes the change over.
- A new runtime dependency needs: an entry in `[project.dependencies]`, new locks, a licence on the allow list (`packaging/bundle_policy.toml`, `docs/LICENCES.md`), a hidden import in the PyInstaller spec when it is loaded by name, and a reason in `docs/DECISIONS.md`.

## Workflows

`tests/unit/test_workflows.py` checks every file in `.github/workflows/`:

1. every `uses:` is a full commit id with a version comment (`# v1.2.3`); a tag is not accepted, because a tag can be moved;
2. a top-level `permissions:` that is read-only; a job asks for more only where it needs it;
3. a job that writes to releases or signs files (`contents`, `attestations`, `id-token` set to `write`) runs in the `release` environment;
4. no `pull_request_target`;
5. text from a pull request, an input or a branch name is never written into a shell script; it goes through `env:`.

When you update an action, take the commit that the tag points to. An annotated tag has two ids; `git ls-remote https://github.com/<owner>/<action>.git "refs/tags/<tag>^{}"` gives the commit.

| Workflow | What it does |
|---|---|
| `ci.yml` | Lint, types and the tests on Linux and Windows; REUSE; offline evidence |
| `dco.yml` | `Signed-off-by` on every commit |
| `pr-checklist.yml` | The pull request text has the data box ticked (no confidential, export-controlled, personal or customer data); Dependabot exempt |
| `audit.yml` | `pip-audit` of the locks |
| `dependency-review.yml` | Known vulnerabilities in a dependency change (pull requests that change a dependency or a workflow) |
| `codeql.yml` | CodeQL for Python and for the workflows; results in the Security tab |
| `secrets.yml` | gitleaks on commits |
| `scorecard.yml` | OpenSSF Scorecard (the result stays in this repository; `publish_results` is false) |
| `release.yml` | Builds and tests the installers; on a tag, the `publish` job attaches the files and records the attestations |
| `attach-release.yml` | Attaches the files of an earlier run to a release, by hand |

## Settings that only the owner can change

These are repository settings; the workflows cannot set them. Until they are set, the controls above are weaker than this page says.

1. **Environment `release`** (Settings, Environments, **New environment**). Add the owner as **required reviewer** (leave *Prevent self-review* off: the owner pushes the tag and approves the run) and limit it to tags `v*` (*Deployment branches and tags*, a tag rule). The workflows name the environment, but it is not listed until it exists: create it **by hand before the first tag**, otherwise the first run creates it without a reviewer and does not wait. A run then waits on its page in Actions until the owner presses *Review deployments* and approves.
2. **Private vulnerability reporting** (Settings, Code security).
3. **Secret scanning and push protection**, **Dependabot alerts**, **Dependency graph** and **code scanning default setup off** (CodeQL runs from `codeql.yml`).
4. **Branch protection or a ruleset for `main`**: pull request required, no force push, no deletion (done). Required checks were declined (D-271): the checks run on every pull request and the maintainer merges only on green. See [BRANCH_PROTECTION.md](../BRANCH_PROTECTION.md).
5. **Actions permissions**: the default token read-only, and "Allow GitHub Actions to create and approve pull requests" off. Approval needed for workflows from first-time contributors.
6. **Two-factor authentication** with a passkey on the owner account.

## Reproducible builds

The release files are **not** reproducible bit for bit. What is stable, and what is not:

| Part | Status |
|---|---|
| Python libraries | Fixed: the locks pin each file by hash. |
| Reports, results and exports | Deterministic: the golden tests compare them byte for byte. |
| The `.deb` and the PyInstaller bundle | Time stamps and file order can differ between two builds. The `.deb` honours `SOURCE_DATE_EPOCH`; the bundle does not set it. |
| System libraries in the Linux bundle | Taken from `rockylinux:9` at build time. The image is named by tag, not by digest, and its packages move with Rocky 9 updates. The SBOM and `COMPLIANCE-RECORD.md` list the versions that were used. |
| Qt and PySide6 | Fixed by the lock and `packaging/sources.toml` (version and SHA-256 of the sources). |
| The Windows installer | Built by Inno Setup, installed with Chocolatey at build time (version not pinned). |

What a user can check instead is **where** a file was built: `gh attestation verify` proves the file came from this repository's release workflow on a named commit. To get a closer-to-reproducible build, pin the Rocky image by digest, pin the Inno Setup version, and set `SOURCE_DATE_EPOCH` for the bundle; this is not done yet; it is risk R-31 in the [risk register](../legal/risk-register.md).

## Release checklist (security part)

Do these in addition to "Cut a release" in the [developer guide](README.md):

1. All checks of the release pull request are green, including CodeQL, the secret scan and the dependency audit. No open Code scanning alert of high severity.
2. The tag is on the merge commit of the release pull request.
3. When the `publish` job waits for the `release` environment, read the run: the commit, the files, the checks. Then approve.
4. Open the draft release. Read `COMPLIANCE-RECORD.md`: both checks say **passed**, and the hashes match `SHA256SUMS-*.txt`.
5. Run `gh attestation verify` on one file of each system (see [security-and-privacy.md](../security-and-privacy.md#check-a-download)).
6. Publish. Then keep the compliance record: it is part of the release.

## If something goes wrong

- **A secret was committed.** Revoke it at the source first. Then remove it from the files. Do not rewrite published history without the owner's decision.
- **A vulnerable release.** Fix on a branch, release a new version, and say in the release notes which versions are affected. Do not change the old release; mark it in the notes.
- **A release file that does not verify.** Delete the draft or the file only with the owner's decision, then find the cause (the run log, the `release` environment approvals).
- **A leaked token or a lost account.** Follow GitHub's account recovery, then rotate every secret and re-check the settings above.
