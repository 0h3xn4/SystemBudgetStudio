# Owner checklist

Date: 2026-11-09 (first version, Phase 1); updated 2026-11-11 after the releases 2.12.0 and 2.12.1. These steps need you: they are account or repository settings, money, or personal choices. Claude does not do them (brief section 3.2). Tick a box when done, or write "declined" next to it. Later phases add steps; the final list is part of the Phase 9 report.

**Done or decided so far:** 2.12.0 and 2.12.1 are published by the release workflow, with `COMPLIANCE-RECORD.md` and attestations; the `release` environment has you as required reviewer (the 2.12.1 run waited for your approval); pull request #129 is merged. On 2026-11-10 you declined, for now, a security contact for `SECURITY.md` (the private report form stays the only way) and a decision on a code-signing certificate.

## Now (cheap, and it reduces risk today)

- [x] **Change the repository description** (Q19). *Done 2026-11-11 with the proposed text.* The current text says "Every equation sourced, every value with units, byte-identical reports" and "power and RF link budgets", which the README contradicts (53 of 57 equations have no citation yet). *How:* GitHub, repository page, the gear icon next to **About**, edit **Description**. Proposed text (no promises, true today): "Offline desktop and command-line tool for small-satellite power, mass, thermal and link budgets from one plain-text spacecraft model. Free and open source. Engineering estimates; no warranty." Then press **Save changes**. (Findings F-50, F-83.)
- [ ] **Use the no-reply address for new commits** (Phase 2, decision D-259). Your commits so far show a private address in 128 commit headers; they stay as they are. *How:* GitHub, **Settings → Emails**: tick **Keep my email addresses private** and **Block command line pushes that expose my email**. The no-reply address is shown on that page. It has the form `<id>+0h3xn4@users.noreply.github.com`; the id `291340596` appears in the public Debian package metadata, so the address is most likely:

  ```bash
  git config --global user.name "0h3xn4"
  git config --global user.email "291340596+0h3xn4@users.noreply.github.com"
  ```

  Check the address against the one GitHub shows before you run it. In an existing clone, run the same two lines without `--global` if you want the setting for this repository only. Verify with `git log -1 --format='%an <%ae>'` after your next commit. (F-10, F-18.)
- [x] **Answer the open questions** in [legal-audit.md](legal-audit.md): Q2 (country), Q13 (origin of the "CIC-SAT V6" and "real model" samples), Q15 (private list of names to search for), Q19 (repository description). The other questions are answered by the defaults, as you asked on 2026-11-09 (D-259); change any of them in the chat. *Done 2026-11-09 for Q2, Q13 and Q15; Q19 is the description item above.*
- [x] **Decide on pull request #129** (Q12) before Phase 5 and 6 start. *Done: merged on 2026-11-09.*

## Account security

- [ ] Two-factor login with a **passkey or a hardware security key**. *How:* **Settings → Password and authentication → Two-factor authentication**. Keep the recovery codes **offline** (printed, in a safe place), not in a cloud note.
- [ ] Check **Settings → Sessions** and **Settings → Applications → Authorized OAuth Apps and Installed GitHub Apps**; remove what you do not use.

## Repository settings (Phase 6 and 7 will say when each is needed)

- [ ] **Branch and tag rulesets** for `main` and for tags `v*`, as in [docs/BRANCH_PROTECTION.md](../BRANCH_PROTECTION.md): require pull requests, require the CI checks (including every new check added in Phase 3, 4 and 6), block force-pushes and deletion. *How:* **Settings → Rules → Rulesets → New ruleset**. The list of check names comes with the Phase 6 pull request.
- [x] **Dependency graph** (Phase 6): switch it on (**Settings → Code security → Dependency graph**). *Done 2026-11-11; the dependency-review workflow runs on pull requests again.*
- [ ] **More required checks** (Phase 6 and 7): after each new workflow has run once on a pull request, add `CodeQL (python)`, `CodeQL (actions)`, `gitleaks` and `Data box ticked (no confidential data)` to the required checks (list in [BRANCH_PROTECTION.md](../BRANCH_PROTECTION.md)). Leave "code scanning default setup" **off** (CodeQL runs from `codeql.yml`).
- [ ] **Environment `release`** (Phase 6): the workflows `publish` and `attach-release` name it. *Required reviewer: done* (the 2.12.1 run waited for your approval). Still to check: under **Deployment branches and tags**, allow only tags `v*`. *How:* **Settings → Environments → release**.
- [ ] **Actions settings** (Phase 6): default token read-only; switch off "Allow GitHub Actions to create and approve pull requests"; require approval for workflows of first-time contributors. *How:* **Settings → Actions → General**.
- [x] **Decide about code signing** (Phase 6, Q7): read [signing-options.md](signing-options.md). *Declined for now (2026-11-10): no certificate; the release notes say the installer is not signed.* The recommendation stays: SignPath Foundation, if you change your mind. Nothing is implemented until you decide.
- [ ] **First Scorecard result**: after `scorecard.yml` has run on `main`, look in **Security → Code scanning** and send me the score if you want it recorded; open alerts of CodeQL are to be looked at once.
- [ ] **Required checks** (Phase 3): in the ruleset for `main` add `REUSE (licence and copyright of every file)` and `Signed-off-by on every commit` to the required checks, next to the existing test jobs.
- [x] **Tag and publish 2.12.0, the first Apache-2.0 release** (F-27, D-267, D-268). *Done: 2.12.0 published on 2026-11-10 from `91acfbc`, 2.12.1 on 2026-11-11 from `9f33a97`; both with `COMPLIANCE-RECORD.md` (REUSE and `pip-audit` passed) and attestations.*
- [ ] **For every later release** (the steps in [Cut a release](../developer/README.md#cut-a-release)): tag the merge commit of the release pull request (on github.com: **Releases → Draft a new release**, new tag `vX.Y.Z`, target `main`, nothing merged in between), approve the `publish` job (**Actions → Installers → Review deployments**), read `COMPLIANCE-RECORD.md`, run `gh attestation verify <file> --owner 0h3xn4` on one file per system when you have the GitHub CLI, then publish.
- [ ] **Replace the description of the 2.11.1 release.** It is still GitHub's generated list of pull requests; Claude wrote a release note for it (ask for it again in the chat). *How:* the release page, the pencil icon, paste, **Update release**.
- [ ] **Check the trimmed Qt on real machines** (Phase 4, D-261): on a clean Windows 10/11 machine and on a Linux desktop with X11 and one with Wayland, install the next release and start the window; check that the light/dark theme follows the system (**View > Theme > Same as the system**), that the window has its decorations and that the keyboard works. The steps are in [docs/INSTALL_CHECKLIST.md](../INSTALL_CHECKLIST.md). If something is missing, tell me which plugin; it goes back into `packaging/bundle_policy.toml`.
- [ ] **Decide about the past releases** (Q18, [past-releases.md](past-releases.md)): option A (leave and say so) is the default; B adds notices and the 6.10.3 source archives to v2.11.1.
- [ ] **ScanCode:** allow `scancode -cl src scripts packaging tests docs` in a session, or run it yourself and send me the JSON (F-48).
- [ ] **Search the official trademark registers** (Phase 5, [trademark-search.md](trademark-search.md)): EUIPO eSearch plus, WIPO Global Brand Database, USPTO and DPMA, for "System Budget Studio" and "Budget Studio" in classes 9 and 42; write the date and result into that page.
- [ ] **Maintenance status:** the README says "Maintenance status: active, best effort". Change `SUPPORT_STATEMENT` in `src/budget_core/about.py` and run `python scripts/sync_disclaimer.py` if that stops being true.
- [x] **Releases only by you.** Keep yourself as the only person with write access; create an environment named `release` with **required reviewers: you**. *Done (the reviewer is set).* Check **Settings → Collaborators** once that only you have write access.
- [x] **Secret scanning and push protection.** *On (checked 2026-11-11).* *How:* **Settings → Code security** (or **Advanced Security**) → turn on **Secret scanning** and **Push protection**.
- [x] **Private vulnerability reporting.** *On since 2026-11-11.* *How:* **Settings → Code security → Private vulnerability reporting → Enable**.
- [x] **Dependabot alerts and security updates** *(on since 2026-11-11)* (Phase 6 adds the version-update file). *How:* **Settings → Code security**.
- [ ] **Signed commits** (only if you want them). *How:* GitHub, **Settings → SSH and GPG keys**, add a signing key, then `git config --global commit.gpgsign true`. Then add "Require signed commits" to the ruleset.

- [ ] **Tag ruleset and who can publish** (Phase 7): a ruleset for tags `v*` that only you can create and nobody can delete or move; check **Settings → Collaborators** shows only you with write access. *How:* **Settings → Rules → Rulesets → New tag ruleset**.
- [ ] **Code owners** (Phase 7): `.github/CODEOWNERS` names you. Do **not** switch on "Require review from Code Owners" while you are the only account (GitHub does not let you approve your own pull request, and the assistant's pull requests appear under your name). Switch it on only when a second person can approve.
- [ ] **Discussions off, moderation known** (Phase 7): **Settings → General → Features**, untick Discussions. Know where **Reported content** is. The Code of Conduct and the issue forms say you may edit or delete content that breaks the rules.
- [ ] **Code of Conduct contact** (Phase 7, Q3; *a dedicated address declined for now on 2026-11-10*): the Code of Conduct names GitHub's private report form (Security tab, *Report a vulnerability*, title starting `Conduct:`) as the way to report, so it works only after you switch on private vulnerability reporting (above). If you later choose a project address, change the reporting sentence in `CODE_OF_CONDUCT.md` (section *Reporting an Issue*) and in `SECURITY.md`. Tell me which address and I do it.

## Personal

- [ ] **Ask your insurer** whether your personal liability insurance covers software you publish for free (R-22).
- [ ] **Give a lawyer in your country** [lawyer-questions.md](lawyer-questions.md) and [risk-register.md](risk-register.md). Ask first about LQ-01 to LQ-05.
- [x] **Decide the contact** for the privacy page and the Code of Conduct (Q3). *Decided for now (2026-11-10): no dedicated address; GitHub's private report form is the only way.* If you add one later, a dedicated project address is better than your personal one. Whether the repository page needs an imprint, and which contact it must show, stays a question for the lawyer (LQ-04, the item above).
- [ ] **Read the terms of the CIC-IDM website** (the account you made to download the sample model) and tell me whether they limit publishing facts about the file or naming the tool (Q13, LQ-05).
- [ ] **Decide how the AI-written commits are signed off** (F-25, LQ-15): leave the sign-off "Claude", or sign off yourself when you merge.

## At the end (phase 9, without a website)

The website plan was discarded (D-265), so the Pages settings and the deploy steps are gone. What is left is in [residual-risk-report.md](residual-risk-report.md): every decision still open, every open step of this list in one table, and the proposed repository description and topics.

- [ ] **Apply the repository topics** from the report (or tell me different words); the description is done (2026-11-11). Claude cannot change repository settings.
- [ ] **Read the residual-risk report** and hand it, with [lawyer-questions.md](lawyer-questions.md) and [risk-register.md](risk-register.md), to a lawyer in Germany.
