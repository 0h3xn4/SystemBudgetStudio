# Legal audit

Date: 2026-11-09. This is a technical and organisational audit, not legal advice. A finding is a fact plus a proposed measure. Where a legal judgment is needed, the finding points to a question in [lawyer-questions.md](lawyer-questions.md) (LQ-nn).

Severity: **High** can harm the owner, users or visitors if left; **Medium** should be fixed before the website goes live; **Low** is hygiene. Status: Open, Proposed (needs the owner's answer), Done.

Phase 1 changed nothing except adding `docs/legal/` and `docs/site/plan.md`.

## A. Findings that affect the plan itself

| ID | Sev | Finding | Proposed measure | Status |
|---|---|---|---|---|
| F-01 | High | The brief names version 1.3.0 and says "releases up to and including 1.3.0 remain MIT". The repository is at **2.11.1** with 24 published releases (1.0.0 to 2.11.1), all MIT. The licence boundary and every sentence that names it depend on this. | Use "every release up to and including the last one published before the change" and name the version at Phase 3. Needs answer **Q10**. | Proposed |
| F-02 | Medium | `site/reference.html` is not in the repository (no `site/` on any branch). The brief's draft, its guessed assets and its headline "Spacecraft budgets you can defend." are not available. | Write the page from the design system (plan in `docs/site/plan.md`). Ask the owner to supply the draft if it is wanted (**Q11**). Never use that headline. | Proposed |
| F-03 | Medium | Open pull request #129 (D-258) covers offline and privacy statements, `pip-audit`, build attestations, a security page and a canary test. It overlaps Phases 5 and 6, touches `ci.yml`, `release.yml`, `README.md`, `docs/DECISIONS.md`, the lock files, and takes decision number D-258. | Do not merge or edit it (rule 3.2). Ask whether to wait for it, rebase on it, or drop it (**Q12**). My Phase 3 and later decisions then start at D-259 or at the next free number after it merges. | Proposed |
| F-04 | Medium | Scanning tools could not be installed in this session: `gitleaks`, `reuse`, `scancode`, `exiftool`. The automatic permission check refused the download of an external binary. Phase 1 used pattern scans and Pillow-based metadata checks instead. They are weaker than the real tools. | Owner decides whether the session may install them (**Q14**). Otherwise the scans run in CI (Phase 6) and the first CI result goes into the record. | Proposed |
| F-05 | Low | The session's clone was shallow (50 of 440 commits). Fixed with `git fetch --unshallow`; all history scans use the full history. | none | Done |

## B. Phase 2: personal data, ownership, history

| ID | Sev | Finding | Proposed measure | Status |
|---|---|---|---|---|
| F-10 | Medium | The author address `ohexna@mailbox.org` is in the metadata of **128 of 440 commits** (the other 312 are authored by Claude). The repository is public, so the address and the name "ohexna" are public in the history. The public handle is `0h3xn4`, so the two names also link two identities. Not in the working tree. | Options in Q9: leave it; rewrite history (changes every commit hash, breaks all 24 tags and releases, needs force-push and a new release set; not recommended); or stop the spread now by using the no-reply address for new commits. **Recommendation: leave the history, set the no-reply address for new commits, tell GitHub to block pushes that expose the private address.** | Proposed |
| F-11 | Low | `LICENSE` names the copyright holder as the handle "0h3xn4". The `.deb` maintainer uses `0h3xn4 <291340596+0h3xn4@users.noreply.github.com>` (a public GitHub no-reply address with the numeric id). | Name per **Q1**. | Proposed |
| F-12 | Low | `docs/images/ux-redesign/tree-before.jpg` carries EXIF (Android build string, date 2026-10-18). It is not referenced by any document. The picture shows invented example data only. | Delete the file, or strip the EXIF and keep the picture. No history rewrite is proposed. | Proposed |
| F-13 | Low | The screenshots show the status bar path `/tmp/sbs-docshots-<random>/example`, a temporary folder, not a home directory. The window's user name does not appear in the pictures I opened (one of 438; the rest were not opened). | Regenerate the website screenshots with a fixed neutral path (Phase 8). Review every picture before use. | Open |
| F-14 | Low | `docs/transparency_audit.md` contains the path `/home/user/systembudgetstudio/` (a build-session path) and `docs/DECISIONS.md` mentions "a senior engineer", "the engineer's feedback" and "an owner's real model". No names. | Keep; confirm in **Q13** that no employer data is behind "the owner's real model" and "CIC-SAT V6 (sample of the owner)". | Proposed |
| F-15 | Medium | **"CIC-SAT V6 (sample of the owner)" and "an owner's real model"** are named in `docs/DECISIONS.md` (D-246, D-253), `CHANGELOG.md` and `docs/changes.md`, with counts taken from it ("104 of 124 equipment placed"). If a model came from an employer or customer, even the counts could be confidential. The `.idm` files themselves are excluded from the repository by `.gitignore` and by a test. | Owner confirms the origin (**Q13**). If it is a public sample, add the source; if not, remove the counts and review the history (**Q9**). | Proposed |
| F-16 | Low | Working-tree scan found no e-mail address (apart from the no-reply address), no home path of a person, no IP address of a host, no token or key (`evidence/2026-11-09/working-tree-scan.txt`). The scan cannot find **company or customer names**, because I do not know them. | Owner gives a private list of words to search for (not to be committed). See **Q15**. | Proposed |
| F-17 | Low | No ownership statement ("personal project, not affiliated with any employer") exists in README, docs or the window. | Phase 2 text, same wording everywhere. | Open |
| F-18 | Low | The commits made by the owner on GitHub show as `GitHub <noreply@github.com>` as committer. Local `git config` in this session uses `Claude <noreply@anthropic.com>`. There is no `.mailmap`. | Tell the owner how to set the no-reply address (owner checklist). | Open |
| F-19 | Low | `--diagnose` (D-257) writes environment variable values (`QT_*`, `BUDGET_*`), the assets folder path and the layout file path. These can show a home directory when the user posts the output in an issue. | Say so in the privacy statement and the template for bug reports. Phase 5. | Open |

## C. Phase 3: licence, REUSE, contributions

| ID | Sev | Finding | Proposed measure | Status |
|---|---|---|---|---|
| F-20 | Low | Authorship check: every commit is by the owner (128, merged by GitHub) or by Claude (312). No other person, no bot. One open pull request, by the owner. | The change to Apache-2.0 can go ahead without third-party consent. Whether the owner alone may relicense AI-assisted work is **LQ-02**. | Done / Proposed |
| F-21 | Medium | Licence references to change (inventory section 9): `LICENSE`, `pyproject.toml` (also `license-files`, classifier), README text and badge, FAQ, `.rpm` spec, `.deb` text, `tests/unit/test_packages.py`, CHANGELOG, DECISIONS (D-140). The Windows installer has **no** licence page; the window has **no** About dialog. | Phase 3 adds them. The brief's "About dialog" and "Help → Third-party licences" need to be built (**Q16**). | Open |
| F-22 | Medium | No source file has an SPDX identifier or a copyright line. 1937 tracked files. REUSE compliance needs `REUSE.toml` plus headers for Python files. | `REUSE.toml` for data and images; SPDX headers for the 531 Python files by script; `reuse lint` in CI. Changing 531 files is a large diff, reviewed as one commit per kind. | Open |
| F-23 | Low | No DCO, no contribution rules about origin, AI use, data, non-commercial scope. | Phase 3. | Open |
| F-24 | Low | A relicence to Apache-2.0 adds a patent grant and a "NOTICE" duty for others, and ends compatibility with GPL-2.0-only code (none is bundled). | Name the effects in the CHANGELOG without legal conclusions. | Open |

## D. Phase 4: third-party compliance

| ID | Sev | Finding | Proposed measure | Status |
|---|---|---|---|---|
| F-30 | High | **Qt and PySide6 (LGPL-3.0-only) are shipped in 24 releases without source archives and, as far as Phase 1 can see, without a written offer.** `check_bundle.py` checks for the licence texts, not for source or an offer. Whether that meets the licence is **LQ-03**. | Attach the exact source archives (or the owner's chosen alternative, **Q17**) to each new release and, if the owner agrees (Q18), to the old ones. | Proposed |
| F-31 | Medium | The SBOM covers the 21 Python packages only. It lacks the Python runtime, bundled Qt libraries and plugins, the PyInstaller bootloader, fonts, icons and the installer runtime. | Phase 4: generate an SBOM from the built bundle. | Open |
| F-32 | Medium | No `THIRD_PARTY_NOTICES.txt`. The bundle has `licences.md` (from `pip-licenses`) and `licences/<package>/` folders. Fonts' OFL texts and Lucide's licence are in `assets/`; their presence in the Windows installer page, the About dialog and the website is not guaranteed. | Phase 4. | Open |
| F-33 | Medium | `packaging/licence_check.py` is a gate for Python packages (permissive or LGPL). It does not run in CI (`ci.yml` does not call it), has no deny list file, and cannot see Qt modules, fonts or icons. | One allow/deny file under `packaging/`; run in CI and in release. | Open |
| F-34 | Medium | The list of bundled Qt modules and plugins is not recorded. `PySide6-Essentials` does not include the GPL-only add-on modules, but the bundle contents were not measured. | Build in CI, list the files, remove unused, add a CI check. Not measurable here without PySide6 6.10.3 on Python 3.14 (being installed for tests; if it works, Phase 4 measures it locally). | Open |
| F-35 | Low | The PyInstaller bootloader exception text is not known to ship in the bundle. | Check and add. | Open |
| F-36 | Low | IBM Plex carries the Reserved Font Name "Plex". The files are unmodified and have no recorded version or hash. | Record version and hash. Never rename or modify the fonts (the website uses the upstream WOFF2 for Inter and JetBrains Mono only). Embedding in PDF and DOCX exports: the OFL allows it (to be recorded as a finding with the licence text at Phase 4; this is not a legal conclusion, see LQ-06). | Open |
| F-37 | Low | Real data: two ISS two-line element sets in `tests/` ("from the sgp4 library documentation (public)"). Not shipped. Terms of use not recorded. | Replace with an invented orbit, or record the source and terms. | Proposed |
| F-38 | Low | Equations "reproduced from memory" from Montenbruck and Gill and Vallado (coefficients, formulas). No text copied. | Keep the citations; add the editions. | Open |
| F-39 | Low | The logo and banner use IBM Carbon palette colours; the status taxonomy follows Astro UXDS; `UI_OVERHAUL.md` records a brief that names Carbon, shadcn/ui and Astro UXDS. No code or image was copied. | Say in `docs/DESIGN.md` what is borrowed. Colour values and a naming scheme are plain facts, but ask in LQ-07. | Open |
| F-40 | Medium | **IDM-CIC (CNES).** The tool reads IDM-CIC model files and names IDM-CIC and CNES in README, window, guide and docs. Conventions for the centre of gravity were inferred (D-245) and not checked against the original. | Keep "independent of CNES" and the "not checked" statements; ask the lawyer (LQ-05). | Proposed |
| F-41 | Medium | Past releases (1.0.0 to 2.11.1): notices and source availability were not checked on the published files (Phase 4 step 10 needs the downloads; this session has not opened any release asset). | List the gaps at Phase 4 from the downloaded assets; the owner decides (Q18). Never change a release without the OK. | Open |
| F-42 | Low | `docs/user-manual` has no page that explains how a user replaces Qt libraries with another compatible version. | Phase 4. | Open |

## E. Phase 5: liability, wording, privacy of the program

| ID | Sev | Finding | Proposed measure | Status |
|---|---|---|---|---|
| F-50 | High | **The repository description says "Every equation sourced, every value with units, byte-identical reports"** (claims C-01, C-02, C-04). The README says 53 of 57 equations have no citation. | Change the description now; owner action (checklist). Do not copy these words anywhere. | Proposed |
| F-51 | High | There is no single disclaimer. The README lists known limits but says nothing about warranty, certification, flight or safety use, independent verification or user responsibility, except through the licence. | Phase 5: one text in code, generated copies, a test. | Open |
| F-52 | Medium | Exported reports carry no disclaimer line. | Needs the owner's answer to **Q4**. | Proposed |
| F-53 | Medium | **Every export embeds the operating-system account name** (`getpass.getuser()`): XLSX `creator`, PDF `author`, DOCX `author` and footer, scenario JSON, provenance CSV. The window has no control and always embeds it. No host name is read. `--user` and `BUDGET_USER` override it on the command line. | Brief question 5 premise differs (no host). Needs the owner's answer to **Q5**. Reports differ between users (affects claim C-04). | Proposed |
| F-54 | Medium | There is no About dialog, no privacy statement of the program and no text in the window about what is stored (`layout.ini` in the Qt config folder or `$BUDGET_CONFIG_DIR`; geometry, column widths and theme, no project names or paths). `privacy.py` redirects QSettings so file dialogs remember nothing. | Phase 5: About dialog with disclaimer, licence, third-party licences, AI authorship, privacy. | Open |
| F-55 | Medium | The offline test does not cover GUI actions after start, imports, UDP or `gethostbyname`, or the packaged build (claim C-03). `reportlab` imports `urllib`, `http` and `ssl`; the code blocks remote images and sets `trustedHosts` to an invalid name. | Extend the test; consider PR #129's work first. | Open |
| F-56 | Low | No support and maintenance statement in README. | Phase 5. | Open |
| F-57 | Low | Promise words: accurate 1, correct 3, verified 1, safe 6, trust 1 in the documents counted (claims register). | Table of replacements for the owner's OK. | Open |
| F-58 | Low | No non-commercial statement in README or CONTRIBUTING. | Phase 5. | Open |
| F-59 | Medium | AI authorship is not stated anywhere in README, docs or the window; the commit trailers do state it. 312 commits have Claude as author. Whether AI-written code is protected by copyright is not for the record to state (**LQ-02**). | Phase 5 wording; owner approves before commit. | Open |
| F-60 | Low | Trademarks: third-party names appear as plain text only (Windows, Linux, Ubuntu, Debian, RHEL, Rocky, Excel, Word, GitHub, Qt, PySide6, CNES, IDM-CIC, Inter, JetBrains, IBM Plex, Lucide, ReportLab, Astro UXDS). No third-party logo. The register search for "System Budget Studio" is not done yet. | Phase 5: search EUIPO, WIPO, USPTO classes 9 and 42; record; LQ-08. | Open |

## F. Phase 6: software, supply chain, release

| ID | Sev | Finding | Proposed measure | Status |
|---|---|---|---|---|
| F-70 | Low | **Parsing is already careful.** YAML: `ruamel.yaml` round-trip loader with a pre-check (1 MB, 20,000 lines, depth 32, no aliases, tags or merge keys, 60,000 nodes). IDM zip: never extracted, only `model.xml`, sizes capped. Imports: paths go through `resolve_inside`. Exports: names pass `safe_name`, writes are staged and replaced. | Add hostile-file tests that prove each (Phase 6). | Done / Open |
| F-71 | Medium | IDM XML uses the standard library `xml.etree` with a byte check for `<!DOCTYPE` and `<!ENTITY`, not `defusedxml`. A file in UTF-16 without a byte-order mark may hide the strings from the byte check (the code refuses UTF-16 with a mark). Up to 5,000,000 elements are allowed. `openpyxl` parses XLSX and `defusedxml` is not a dependency. Not verified by a test. | Use `defusedxml` for IDM; add it to the lock; lower the limits if the sample models allow; hostile tests. | Open |
| F-72 | Low | Zip limits for the IDM import cap the read at 100 MB but check no compression ratio; the XLSX import caps the declared size at 50 MB. | Add a ratio check; test. | Open |
| F-73 | Low | Unchecked: `model_document.py:443` (`unlink(root / rel)`), the SpaceMissionStudio export path (`spacemissionstudio.py:282`), a limit on the number of project files, `link/evaluate.py:256` and `verify.py:74` CSV limits. | Check and test. | Open |
| F-74 | Low | **Formula injection is already handled**: CSV text starting with `=`, `+`, `-`, `@`, TAB or CR gets a leading `'` (numbers and unit-suffixed numbers exempt); XLSX report cells are forced to strings; XLSX table exports use the same prefix (visible apostrophe). `spacemissionstudio.py:284` uses a raw `csv.writer`. | **Q6** asks only whether to keep this. The change would alter exports only for the SpaceMissionStudio file (to check). | Proposed |
| F-75 | Medium | CI: Actions are pinned to full SHAs with version comments (good); default permissions are read-only (good); no `pull_request_target`. Missing: `pip-audit` (in the dev extra only), CodeQL, `gitleaks`, Dependabot, OpenSSF Scorecard, build attestations, a `release` environment with approval; the `publish` job has `contents: write` without an approval gate. Source install in the docs (`pip install -e .`) does not use hashes. | Phase 6; coordinate with PR #129. | Open |
| F-76 | Medium | No `SECURITY.md`, no threat model, no private vulnerability reporting (setting, owner), no secret-scanning push protection (setting, owner). | Phase 6 / owner checklist. | Open |
| F-77 | Medium | The Windows installer is unsigned; no signatures or attestations exist for the 24 releases. | Present options at Phase 6 (Q7, Q8). | Proposed |

## G. Phase 7 to 9

| ID | Sev | Finding | Proposed measure | Status |
|---|---|---|---|---|
| F-80 | Medium | No issue or pull-request templates, no CODEOWNERS, no Code of Conduct, no data warning for posters. | Phase 7. The Code of Conduct needs a contact address (**Q3**). | Open |
| F-81 | Low | `examples/README.md` says the data is invented. Export control: nothing real found in examples; the ISS TLEs are public data. | Phase 7; LQ-09. | Open |
| F-82 | Medium | Privacy page and imprint: depend on the owner's country (**Q2**) and contact (**Q3**). Nothing is written until answered. | Phase 9. | Blocked on Q2, Q3 |
| F-83 | Low | The repository "About" box says "power and RF link budgets"; the tool also does mass, thermal, propulsion and pointing. | Proposed text and topics in Phase 9. | Open |
| F-84 | Low | Website tooling: the window screenshots need Python 3.14 and PySide6 (installed for the tests in this session); official WOFF2 files must be downloaded from the upstream releases. | Phase 8. | Open |

## Questions for the owner

Please answer each in one line. "Default" is what I will do if you say "use your defaults".

| # | Question | Default |
|---|---|---|
| Q1 | Which name goes in the copyright line: your real name or your handle (`0h3xn4`)? | Handle |
| Q2 | Which country do you live in? (Decides the privacy page and any imprint.) | none; pages blocked |
| Q3 | Which contact may be published? Do you want a project e-mail address? (A dedicated address is recommended, not your personal one. The Code of Conduct and the privacy page need it.) | GitHub private vulnerability reporting only; no e-mail |
| Q4 | Should exported reports carry a one-line disclaimer? (Changes XLSX, PDF, DOCX; golden files change.) | Yes in PDF and DOCX footer text and a provenance row in XLSX, CSV and JSON; you approve the text |
| Q5 | Provenance: should the user name be left out by default, or kept? (There is no host name today. Changes outputs.) | Write the neutral value `unknown` (the value the tool already uses when it finds no name), with a setting to include a name you type |
| Q6 | Formula injection: keep today's handling (apostrophe prefix in CSV and XLSX tables, string cells in XLSX reports) and only add tests and the SpaceMissionStudio file? | Keep |
| Q7 | Windows code signing: SignPath Foundation (free for open source, needs a verified identity and an approval process), a paid certificate, or none? | Ask me again at Phase 6 with a costs table |
| Q8 | Add signatures or attestations to existing release files afterwards? (Changes releases.) | No change to old releases; notices and source archives only if you say yes in Q18 |
| Q9 | Git history: the author address `ohexna@mailbox.org` is in 128 commits. Leave it, or rewrite? | Leave; use no-reply from now |
| Q10 | The brief says 1.3.0; the repository is at 2.11.1 with 24 MIT releases. Is "up to and including the last release before the change" right? Which version number will carry Apache-2.0 (suggest 2.12.0)? | Last release before the change; 2.12.0 |
| Q11 | `site/reference.html` is not in the repository. Do you have the draft? Should I write the page from scratch? | Write from scratch |
| Q12 | Pull request #129 (D-258) overlaps Phases 5 and 6. Merge it first, rebase my work on it, or close it? | You merge it first if you want it; I rebase |
| Q13 | Where did the model "CIC-SAT V6" and "the owner's real model" (DECISIONS D-246, D-253) come from? Is any of it employer, customer or non-public data? | none; stop on any doubt |
| Q14 | May this session install `gitleaks`, `reuse`, ScanCode and `exiftool` (downloads of external tools into a scratch folder)? If not, the scans run in CI only. | No download; CI only |
| Q15 | Please give me, in this chat only, a private list of company, customer, programme or person names to search for. I will not write them into the repository. | none |
| Q16 | The window has no About dialog and the Windows installer no licence page. May I add both (Phase 3 and 5)? | Yes |
| Q17 | LGPL source: attach the exact source archives of PySide6, shiboken6 and Qt to every release (recommended), or a link with a written offer? | Attach |
| Q18 | For the 24 existing releases: add notices and source archives (changes releases), or leave them as they are and record the gap? | Leave; record the gap |
| Q19 | The repository description says "Every equation sourced…byte-identical reports". May I give you a new text, and will you apply it? | Yes; text in Phase 9, earlier on request |
