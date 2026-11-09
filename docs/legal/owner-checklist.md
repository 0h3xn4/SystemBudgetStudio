# Owner checklist

Date: 2026-11-09 (first version, Phase 1). These steps need you: they are account or repository settings, money, or personal choices. Claude does not do them (brief section 3.2). Tick a box when done, or write "declined" next to it. Later phases add steps; the final list is part of the Phase 9 report.

## Now (cheap, and it reduces risk today)

- [ ] **Change the repository description.** The current text says "Every equation sourced, every value with units, byte-identical reports" and "power and RF link budgets". README line 116 says 53 of 57 equations have no citation. *How:* GitHub, repository page, the gear icon next to **About**, edit **Description**. Proposed text (no promises, true today): "Offline desktop and command-line tool for small-satellite power, mass, thermal and link budgets, from one plain-text spacecraft model. Free and open source." Then press **Save changes**. (Findings F-50, F-83.)
- [ ] **Use the no-reply address for new commits.** *How:* GitHub, **Settings → Emails**: tick **Keep my email addresses private** and **Block command line pushes that expose my email**. Your no-reply address is shown on the same page (it ends in `@users.noreply.github.com`). On your computer: `git config --global user.email "<that address>"`. Past commits do not change. (F-10, F-18.)
- [ ] **Answer the questions** at the end of [legal-audit.md](legal-audit.md) (Q1 to Q19), in the chat.
- [ ] **Decide on pull request #129** (Q12) before Phase 5 and 6 start.

## Account security (before the website goes live)

- [ ] Two-factor login with a **passkey or a hardware security key**. *How:* **Settings → Password and authentication → Two-factor authentication**. Keep the recovery codes **offline** (printed, in a safe place), not in a cloud note.
- [ ] Check **Settings → Sessions** and **Settings → Applications → Authorized OAuth Apps and Installed GitHub Apps**; remove what you do not use.

## Repository settings (Phase 6 and 7 will say when each is needed)

- [ ] **Branch and tag rulesets** for `main` and for tags `v*`, as in [docs/BRANCH_PROTECTION.md](../BRANCH_PROTECTION.md): require pull requests, require the CI checks (including every new check added in Phase 3, 4 and 6), block force-pushes and deletion. *How:* **Settings → Rules → Rulesets → New ruleset**. The list of check names comes with the Phase 6 pull request.
- [ ] **Releases only by you.** Keep yourself as the only person with write access; create an environment named `release` with **required reviewers: you**. *How:* **Settings → Environments → New environment**.
- [ ] **Secret scanning and push protection.** *How:* **Settings → Code security** (or **Advanced Security**) → turn on **Secret scanning** and **Push protection**.
- [ ] **Private vulnerability reporting.** *How:* **Settings → Code security → Private vulnerability reporting → Enable**.
- [ ] **Dependabot alerts and security updates** (Phase 6 adds the version-update file). *How:* **Settings → Code security**.
- [ ] **Signed commits** (only if you want them). *How:* GitHub, **Settings → SSH and GPG keys**, add a signing key, then `git config --global commit.gpgsign true`. Then add "Require signed commits" to the ruleset.

## Personal

- [ ] **Ask your insurer** whether your personal liability insurance covers software you publish for free (R-22).
- [ ] **Give a lawyer in your country** [lawyer-questions.md](lawyer-questions.md) and [risk-register.md](risk-register.md). Ask first about LQ-01 to LQ-05.
- [ ] **Decide the contact** for the privacy page and the Code of Conduct (Q3). A dedicated project address is better than your personal one.

## Later (added in Phase 9)

- [ ] **Settings → Pages → Source: GitHub Actions**; **Enforce HTTPS**; protection rules for the `github-pages` environment.
- [ ] Apply the new repository description and topics (or confirm that Claude may).
- [ ] The site goes live only when you approve and merge the final pull request.
