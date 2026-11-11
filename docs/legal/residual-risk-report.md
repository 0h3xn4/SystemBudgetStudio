<!--
SPDX-FileCopyrightText: 2026 0h3xn4

SPDX-License-Identifier: Apache-2.0
-->

# Residual-risk report

Date: 2026-11-10. This is the final report of the protection programme (brief phases 1 to 7 and the end of phase 9). It is written for the owner and for a lawyer. It is not legal advice. It holds no secret and no personal data beyond the handle `0h3xn4`.

**The website was not built.** On 2026-11-10 the owner discarded the website plan during phase 8 (D-265). Nothing was published, no deploy workflow exists, and the website parts of phases 8 and 9 (the site, its legal pages, the Pages settings) are void. The plan stays in [../site/plan.md](../site/plan.md).

Contents: [What was changed](#what-was-changed) · [What was verified and how](#what-was-verified-and-how) · [What could not be verified](#what-could-not-be-verified) · [Decisions still open](#decisions-still-open) · [Open steps for the owner](#open-steps-for-the-owner) · [Residual risks](#residual-risks) · [Questions for a lawyer](#questions-for-a-lawyer) · [Repository description and topics](#repository-description-and-topics-for-you-to-apply) · [Definition of done](#definition-of-done)

## What was changed

All changes went through pull requests that were merged after green CI (#130, #132, #133, #134, #135, #136, #139; #129 was the owner's). No budget number, equation or default was changed. Exports changed in two places that the owner approved (a disclaimer line and the neutral user name; golden files regenerated, see [../changes.md](../changes.md)).

| Phase | What | Decision | Where |
|---|---|---|---|
| 1 Orientation | Inventory, claims register, audit (F-01 to F-87), risk register, owner checklist, lawyer questions | – | this folder |
| 2 Personal data | Ownership statement, EXIF removed from one image, scans of tree and history (128 commits keep a private address by decision) | D-259 | `evidence/2026-11-09/` |
| 3 Licence | Apache-2.0 for new releases (`LICENSE`, `NOTICE`, `LICENSES/`, SPDX in every file, REUSE in CI), MIT text for releases up to 2.11.1, DCO check, contribution rules, About dialog | D-260 | root, `CONTRIBUTING.md` |
| 4 Third parties | Inventory of everything the installers bundle, notices, a licence gate in the build, Qt trimmed to what is used, Qt and PySide6 sources on every release | D-261 | `packaging/`, `docs/LICENCES.md` |
| 5 Liability, wording, privacy | One disclaimer everywhere and in every report, no account name in reports, promise words removed, AI-authorship, support and non-commercial statements, first trademark search | D-262 | `budget_core/disclaimer.py`, `about.py` |
| 6 Security | `defusedxml`, hostile-file, formula and source-scan tests, CodeQL, gitleaks, Scorecard, Dependabot, dependency review (by hand), `release` environment, compliance record per release, hashed source install, `SECURITY.md`, threat model, signing options (nothing implemented) | D-263 | `.github/`, `docs/developer/` |
| 7 Governance | Issue forms and PR template with the data box (and a CI check), Code of Conduct, `CODEOWNERS`, export-control note for the examples | D-264 | `.github/`, root |
| 8, 9 Website | Discarded by the owner | D-265 | – |

## What was verified and how

| Check | Result | Evidence |
|---|---|---|
| Unit, regression and offline tests | 3378 passed, 2 skipped (no `rpmbuild`; one example has no incomplete link) | `evidence/2026-11-10/test-run-phase-7.txt` |
| GUI and golden tests | 985 passed (phase 6; no program code changed since) | `evidence/2026-11-10/test-run-phase-6.txt` |
| Lint, format, types | `ruff`, `mypy` clean | same files |
| REUSE | Every file has a licence and a copyright line | `reuse lint` in CI (job `REUSE`) |
| DCO | Every commit since 2026-11-09 has `Signed-off-by` | CI job `DCO` |
| Licence gate | Rocky 9 and Windows installer builds pass the gate | CI jobs `Linux (built on Rocky 9 …)` and `Windows (per-user installer)` |
| Offline claim | No network in the code (source scan), blocked sockets in a test, `strace` on Linux, firewall block on Windows | `tests/offline/`, CI offline jobs |
| Hostile files | Bombs, external entities, path tricks, formulas, code-in-file tests | `tests/unit/test_hostile_inputs.py`, `test_formula_injection.py`, `test_code_safety.py` |
| Workflows | Pinned actions, read-only token, no `pull_request_target`, writers in the `release` environment | `tests/unit/test_workflows.py` |
| Vulnerable dependencies | `pip-audit` of both lock files, weekly and on every lock change | CI job `pip-audit of the lock files` |
| Static analysis, secrets | CodeQL (Python and workflows) and gitleaks green on the pull requests of phases 6 and 7 | CI |
| Claims | Every claim of the README and docs is in the claims register with its evidence (C-01 to C-45) | [claims-register.md](claims-register.md) |

## What could not be verified

- **Real machines.** The installers were built and tested by CI, not by hand on a clean Windows 10/11 or Rocky 9 machine; the trimmed Qt was not checked on real desktops (X11, Wayland); the XLSX files were never opened in Excel ([../INSTALL_CHECKLIST.md](../INSTALL_CHECKLIST.md)).
- **The release path.** ~~The compliance record, the attestations and the `release` environment have not run on a real tag yet (claim C-44).~~ **Update 2026-11-11:** proven by 2.12.0 and 2.12.1: both releases carry `COMPLIANCE-RECORD.md` (REUSE and `pip-audit` passed) and attestations, and the 2.12.1 `publish` job waited for the owner's approval in the `release` environment. `gh attestation verify` has not been run by hand yet.
- **Scanners.** gitleaks ran on the commit ranges of pull requests, not on the whole history; ScanCode was never run (the session may not run it); `exiftool` was not available. The company and customer name scan could not be done because the owner gave no list (Q15).
- **GitHub settings.** The session cannot read or change settings. Whether two-factor login, rulesets, required checks, secret scanning, push protection, private vulnerability reporting, the Dependency graph and the `release` reviewer are on is **not known**. **Update 2026-11-11:** the `release` reviewer is on (seen in the 2.12.1 run); the rest is still not known.
- **Law.** Whether the licence change is valid, whether AI-written code is protected, whether the LGPL conditions are met for old releases, whether the disclaimer works, whether the name is free, whether publishing needs an export licence, and whether the repository page needs an imprint are questions for a lawyer. Nothing here answers them.
- **The official trademark registers** (EUIPO, WIPO, USPTO, DPMA) were not searched; only a first web search was made ([trademark-search.md](trademark-search.md)).
- **Old releases.** The 24 releases up to 2.11.1 are unchanged, by decision (Q8, Q18). Their notices and source availability are a known gap ([past-releases.md](past-releases.md)).

## Decisions still open

| # | Decision | Recommendation | Where |
|---|---|---|---|
| 1 | The version of the first Apache-2.0 release. **Update 2026-11-10:** v2.11.2 was published from the MIT commit `41a330a`, so 2.11.2 is the last MIT release (D-267) and its number is taken. **Decided:** 2.12.0, published on 2026-11-10; 2.12.1 followed on 2026-11-11 | – | owner checklist |
| 2 | Past releases: leave them (option A) or add notices and the 6.10.3 sources to v2.11.1 (option B) (Q18) | A, with the gap recorded | [past-releases.md](past-releases.md) |
| 3 | Code signing for the Windows installer (Q7). **Declined for now on 2026-11-10** | SignPath Foundation, if the owner changes their mind; nothing is implemented | [signing-options.md](signing-options.md) |
| 4 | A project contact (Q3): a dedicated address, or GitHub's private report form only. **Decided for now on 2026-11-10:** the private report form only | A dedicated address if you want one later | owner checklist |
| 5 | Apply the repository description and topics (Q19) | See below | this report |
| 6 | Sign off AI-written commits yourself, or leave the sign-off "Claude" (F-25, LQ-15) | Ask the lawyer; until then leave it | audit F-25 |
| 7 | Reword "CIC-SAT V6 (sample of the owner)" in the history records (F-15) after reading the CIC-IDM site terms | Reword; do not add new statements about that model | audit F-15 |
| 8 | A full-history gitleaks run and a ScanCode run (F-04, F-48) | Run both once; send the results | owner checklist |
| 9 | Whether to cap the number of files in a project folder (R-32) | Not needed now; a Problems-panel message if it ever matters | risk register |
| 10 | Whether a website is wanted later (D-265) | Not now | `docs/site/plan.md` |

## Open steps for the owner

The full list is [owner-checklist.md](owner-checklist.md). It is repeated here in short form so that nothing is missed. Tick them there, or write "declined".

1. **Account:** passkey or hardware key, recovery codes offline, check sessions and authorised apps.
2. **Settings → Code security:** private vulnerability reporting (the Code of Conduct and `SECURITY.md` rely on it), secret scanning with push protection, Dependabot alerts, **Dependency graph** (then tell Claude to restore the dependency-review trigger).
3. **Rulesets** (**update 2026-11-11:** `main` done without required checks, D-271; tags `v*` still open): `main` (pull request, required checks: tests, `REUSE (licence and copyright of every file)`, `Signed-off-by on every commit`, `CodeQL (python)`, `CodeQL (actions)`, `gitleaks`, `Data box ticked (no confidential data)`) and tags `v*` (only you may create, nobody may delete or move). Do not require code-owner review while you are the only account.
4. **Environment `release`:** you as required reviewer (done), limited to tags `v*` (done). **Settings → Actions** (done 2026-11-11): read-only default token, no pull requests created by Actions, approval for first-time contributors.
5. **Repository:** Discussions off; know where reported content is; apply the description and topics below.
6. **Release:** 2.12.0 and 2.12.1 are published (decision 1); do the manual steps of [../INSTALL_CHECKLIST.md](../INSTALL_CHECKLIST.md) on a clean Windows and Rocky 9 machine, including the trimmed Qt on X11 and Wayland; run `gh attestation verify` on one file per system and read `COMPLIANCE-RECORD.md`.
7. **Commits:** the no-reply address (`Keep my email addresses private`, `Block command line pushes that expose my email`).
8. **Personal:** ask your insurer (R-22); give a lawyer in Germany this report, [lawyer-questions.md](lawyer-questions.md) and [risk-register.md](risk-register.md); search the official trademark registers; read the CIC-IDM site terms.

## Residual risks

Likelihood (L) and impact (I): L = low, M = medium, H = high. *Now* is the level after what was done, before any lawyer review. *Who*: C = Claude (code, docs), O = the owner, L = a lawyer. The full wording of every risk and its measures is in [risk-register.md](risk-register.md).

| ID | Risk (short) | L | I | Status | Now | What would reduce it further | Who |
|---|---|---|---|---|---|---|---|
| R-01 | A reader takes a claim as a promise and relies on a result for a flight or safety decision | M | H | Done except the repository description | M | Apply the new description; a lawyer reads the disclaimer (LQ-10, LQ-20); independent review of the equations | C, O, L |
| R-02 | LGPL (Qt, PySide6, system libraries) shipped without source or notice | L | H | Done for new builds; open for the 24 old releases | L new, M old | Option B of Q18; a lawyer on LQ-03, LQ-18 | C, O, L |
| R-03 | A GPL-only Qt module reaches a bundle | L | H | Done (the gate fails the build) | L | – | C |
| R-04 | The licence change is invalid or unclear | L | M | Done (merged, #133) | L | A lawyer on LQ-01, LQ-02 | L |
| R-05 | Copyright in AI-written code is uncertain | M | M | Open | M | Cannot be removed by wording; LQ-02 | L |
| R-06 | A private address is in 128 public commits | H | L–M | Decided: history left | M | A history rewrite (needs the owner's explicit OK and has costs for forks); a lawyer on LQ-12 | O, L |
| R-07 | Employer, customer or non-public data in the repository or history | L | H | Open | L | Owner's own check; the company-name scan needs a list (Q15 answered "no list") | O |
| R-08 | Read as affiliated with an employer or an agency | L | M | Done (README, About) | L | – | C |
| R-09 | Exports reveal the account name | H | L–M | Done (D-262) | L | – | C |
| R-10 | A hostile project, XLSX or IDM file attacks the user | L | M–H | Mitigated (phase 6) | L | A cap on files per folder; fuzzing; update Qt/Pillow promptly | C |
| R-11 | Supply-chain compromise (dependency, action, release file) | L | H | Done in the repository; owner settings open | M | The `release` reviewer, required checks, signing, pinned image digest (R-31) | C, O |
| R-12 | Owner account takeover | L | H | Open (owner) | L after steps 1 and 4 | Passkey, offline recovery codes, only you with write access | O |
| R-13 | A font, icon or image used outside its licence | L | M | Done | L | LQ-06 | C, L |
| R-14 | Real orbital data (ISS TLEs) in tests | L | L | Open | L | Replace with invented elements | C |
| R-15 | "IDM-CIC" and "CNES" named; reading their file format | L | M | Open | L–M | CIC-IDM site terms; LQ-05 | O, L |
| R-16 | The name conflicts with a registered mark | L | M | Open | unknown | Register search; LQ-08 | O, L |
| R-17 | A website mishandles visitors' data | – | – | Closed (no website) | – | – | – |
| R-18 | No imprint or privacy notice where German law requires one for the repository page | L | M | Open (LQ-04) | L–M | A lawyer's answer | O, L |
| R-19 | Posters put confidential or personal data in issues or PRs | M | M | Mitigated (phase 7) | L | You watch and delete | O |
| R-20 | The project becomes commercial without advice | L | M | Open | L | LQ-13 before any change | O |
| R-21 | Export control for publishing engineering software | L | M | Open | unknown | LQ-09 | L |
| R-22 | Personal liability not covered by insurance | L | M | Open | unknown | Ask the insurer; LQ-14, LQ-16 | O, L |
| R-24 | A scanner finding missed | M | M | Partly closed | L–M | Full-history gitleaks and ScanCode runs | C, O |
| R-26 | The published releases bundle Pillow with known vulnerabilities (F-78) | L | M | **Done:** 2.11.2 and later ship Pillow 13 (update 2026-11-11) | L | – | O |
| R-27 | The DCO sign-off carries an AI identity | M | L | Open | L | You sign off yourself; LQ-15 | O, L |
| R-28 | The next tag lands on the MIT commit | M | M | **Occurred** (v2.11.2); record corrected (D-267); closed: the first Apache-2.0 release is 2.12.0 | L | – | O |
| R-29 | The trimmed Qt loses a function on a real desktop | L | M | Open (owner check) | L | The real-machine checks | O |
| R-30 | A bundled component has no licence text, or a known gap is a real infringement (VC++ runtime, Mesa, Python's C libraries) | M | M | Open | M | LQ-17 to LQ-19; replace the Mesa DLL | C, L |
| R-31 | Release files are not reproducible bit for bit | M | L | Open | L | Pin the Rocky image by digest and Inno Setup by version; `SOURCE_DATE_EPOCH` for the bundle | C |
| R-32 | A huge project folder makes the program slow | L | L | Open | L | A cap with a message | C |

R-23 and R-25 are closed and not repeated. **The risks that matter most now** are R-01 and R-02 for the old releases (the gaps that cannot be closed by code), R-05 and R-12 (owner) and R-30 (R-28 is closed since 2.12.0, update 2026-11-11).

## Questions for a lawyer

All are in [lawyer-questions.md](lawyer-questions.md) with the facts for each, LQ-01 to LQ-21. Ask first about:

1. **LQ-01, LQ-02:** the licence change and the copyright of AI-written code, in German law.
2. **LQ-03, LQ-17 to LQ-19:** the LGPL conditions for Qt and PySide6 on old and new releases, the Visual C++ runtime, the Linux system libraries and the C libraries in Python.
3. **LQ-04:** an imprint or privacy notice for the repository page of a private person in Germany, and how to avoid a home address.
4. **LQ-10, LQ-14, LQ-16, LQ-20:** the disclaimer and liability for a free tool whose results might be used in a design review.
5. **LQ-05, LQ-08, LQ-09:** IDM-CIC and CNES names, the product name, an export licence for publishing as open source.
6. **LQ-12, LQ-15, LQ-21:** the private address in history, the AI sign-off, the CC BY-SA Code of Conduct.

## Repository description and topics for you to apply

Claude cannot change repository settings and did not. Where: GitHub, repository page, the gear icon next to **About**.

**Description** (the old text says "power and RF link budgets", "every equation sourced" and "byte-identical reports", which the README and the evidence do not support):

> Offline desktop and command-line tool for small-satellite power, mass, thermal and link budgets from one plain-text spacecraft model. Free and open source. Engineering estimates; no warranty.

**Topics** (GitHub topics are lower case, with hyphens): `satellite`, `spacecraft`, `small-satellites`, `systems-engineering`, `power-budget`, `link-budget`, `mass-budget`, `thermal-analysis`, `offline`, `python`, `pyside6`, `aerospace`.

**Leave empty:** the website field (there is no website).

## Definition of done

| Item of the brief | Status |
|---|---|
| Legal record complete and dated, evidence for every check | Done; this folder and `evidence/` |
| Every question in `legal-audit.md` has an answer | Answered (Q2, Q13, Q15 explicitly; the others by the defaults you approved on 2026-11-09, D-259); **Q19 is answered by the proposal above once you apply it** |
| Ownership statement in the README, the About dialog and on the website | README and About dialog done; **no website** |
| No personal or company data in the working tree, metadata, screenshots, example outputs; every history finding decided | Working tree scanned (phase 2); history decided (D-259, R-06); **Q15 gave no name list, so the company-name scan was not done; F-15 wording is yours** |
| The target licence is named everywhere; `NOTICE` exists; old releases marked MIT; `reuse lint` in CI | Done |
| DCO check, licence gate, Qt module check, `pip-audit`, CodeQL, gitleaks, the no-network test and Scorecard run in CI | Done (Scorecard runs on `main` and weekly; its first result is yours to read) |
| Every release build produces an SBOM, notices, Qt and PySide6 sources, attestations, SHA256 sums and a compliance record | Done; proven by the releases 2.12.0 and 2.12.1 (C-44) |
| The disclaimer is one text, the same everywhere, and tested | Done |
| No promise wording remains; every public claim has evidence | Done, except the repository description (yours to apply) |
| The AI-authorship section is in the README, the About dialog and on the website | README and About dialog done; **no website** |
| Hostile-file tests pass; formula injection handled as decided | Done (D-263) |
| The website: zero foreign requests, CSP, tests, legal pages, `site/reference.html` deleted | **Discarded (D-265).** `site/reference.html` never existed |
| Every item of `owner-checklist.md` is done by you or declined | **Open: those are your steps** (see above) |
| `lawyer-questions.md` and this report are ready to hand to a lawyer | Ready |
