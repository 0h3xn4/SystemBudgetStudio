# Legal record

This folder is the written record of the care taken to protect System Budget Studio, its owner, its users and the visitors of its website. It follows the brief `LEGAL_AND_WEBSITE_SystemBudgetStudio.md`. It is not legal advice. Nothing in it is a legal conclusion; open legal points are written as questions in [lawyer-questions.md](lawyer-questions.md).

Never put secrets or personal data in this folder.

| File | Content | First written |
|---|---|---|
| [inventory.md](inventory.md) | Files, assets, dependencies, bundled components, data, external references, versions and licence mentions | 2026-11-09 |
| [claims-register.md](claims-register.md) | Every public claim, where it appears, its evidence, and whether the evidence is enough | 2026-11-09 |
| [legal-audit.md](legal-audit.md) | Every finding with severity, proposed measure and status; the numbered questions for the owner | 2026-11-09 |
| [risk-register.md](risk-register.md) | One row per risk | 2026-11-09 |
| [owner-checklist.md](owner-checklist.md) | Steps only the owner can do | 2026-11-09 |
| [past-releases.md](past-releases.md) | What the published releases lack (notices, sources, SBOM) and the options | 2026-11-09 |
| [promise-wording.md](promise-wording.md) | Words that read as a promise and what replaced them | 2026-11-10 |
| [trademark-search.md](trademark-search.md) | First search for the name (not a clearance) | 2026-11-10 |
| [residual-risk-report.md](residual-risk-report.md) | The final report: what changed, what was verified and not, open decisions and steps, residual risks, questions for a lawyer, the proposed repository description | 2026-11-10 |
| [signing-options.md](signing-options.md) | Code signing: options, costs, who is named as publisher (nothing implemented) | 2026-11-10 |
| [lawyer-questions.md](lawyer-questions.md) | Questions for a lawyer | 2026-11-09 |
| `evidence/YYYY-MM-DD/` | Raw output of scans and checks | 2026-11-09 |
| `residual-risk-report.md` | Final report of Phase 9 | not yet written |

## Evidence folders

| Folder | Content |
|---|---|
| [evidence/2026-11-09/](evidence/2026-11-09/) | Phase 1: history scan, working-tree scan, image-metadata scan, external hosts, GitHub state |

## Log

| Date | Phase | Entry |
|---|---|---|
| 2026-11-09 | 1 | Orientation, inventory, claims register, audit, risk register, first owner checklist and lawyer questions, website plan (`docs/site/plan.md`). Read-only: no code, document, release or setting changed. |
| 2026-11-09 | 1 | Pull request #129 (D-258) merged into `main` during the work; the record was merged with it and updated (F-03, F-33, F-55, F-75, F-77, new F-78 Pillow advisories, claims C-31 to C-38, risk R-26). |
| 2026-11-09 | 2 | Ownership statement in the README; EXIF removed from `tree-before.jpg`; Phase 2 scans ([phase2-scan.txt](evidence/2026-11-09/phase2-scan.txt)); owner's defaults recorded as D-259; commit-identity steps in the owner checklist. |
| 2026-11-09 | 3 | Apache-2.0 (`LICENSE`, `NOTICE`, `LICENSES/`, `REUSE.toml`, SPDX headers), `reuse lint` evidence, DCO check, contribution rules, About dialog; owner's answers on Q2 (Germany), Q13 (login-gated sample model), Q15 (no list); D-260. |
| 2026-11-09 | 4 | Third-party compliance: inventory of everything the installers bundle, `THIRD_PARTY_NOTICES.txt`, the licence gate (`packaging/bundle_policy.toml`), Qt trimmed to what the program uses, source archives of Qt and PySide6 on every release, past-releases note; proven on the Rocky 9 and Windows builds; D-261. |
| 2026-11-10 | 5 | One disclaimer in code, README, guide, first screen, About and every report; no login name in reports; wording table; AI-authorship, support, non-commercial and privacy statements; offline test extended; first trademark search; D-262. |
| 2026-11-10 | 6 | `defusedxml` for IDM XML and `openpyxl`; hostile-file, formula-injection, source-scan and workflow tests; limits for antenna pattern files; Space Mission Studio file names; CodeQL, gitleaks, Scorecard, dependency review, Dependabot; `release` environment; compliance record per release; hashed source install; `SECURITY.md`, threat model, security guide; signing options (nothing implemented); Inno Setup licence checked; D-263. |
| 2026-11-10 | 7 | Issue forms and pull request template with the data box and a CI check; `CODE_OF_CONDUCT.md` (Contributor Covenant 3.0; reporting through GitHub's private form); `.github/CODEOWNERS`; export-control section in `examples/README.md` and a test that the examples are invented; owner checklist (tag ruleset, code owners, moderation, conduct contact); LQ-21; D-264. |
| 2026-11-10 | 8 | The owner discarded the website plan during phase 8 (D-265). The unfinished work was never committed or pushed and was set aside outside the repository. Nothing was published. |
| 2026-11-10 | 9 | Without a website: the audit (F-02, F-13, F-82, F-83, F-84), the risk register (R-04, R-10, R-11, R-13, R-17, R-18, R-24, R-25) and the owner checklist updated; the final report [residual-risk-report.md](residual-risk-report.md); the repository description and topics proposed (not applied). |
| 2026-11-10 | after 9 | The owner renamed the repository to `0h3xn4/system-budget-studio`; live references updated, history records unchanged (D-266). The proposed description in [residual-risk-report.md](residual-risk-report.md) is unchanged. |
| 2026-11-10 | after 9 | v2.11.2 was published from the MIT commit `41a330a` (risk R-28 happened). The last MIT release is 2.11.2; the statements and the MIT text file follow (D-267). The next release needs a new version number (owner). |
