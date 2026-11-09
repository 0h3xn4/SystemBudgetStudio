# Owner checklist

Date: 2026-11-09 (first version, Phase 1). These steps need you: they are account or repository settings, money, or personal choices. Claude does not do them (brief section 3.2). Tick a box when done, or write "declined" next to it. Later phases add steps; the final list is part of the Phase 9 report.

## Now (cheap, and it reduces risk today)

- [ ] **Change the repository description.** The current text says "Every equation sourced, every value with units, byte-identical reports" and "power and RF link budgets". README line 116 says 53 of 57 equations have no citation. *How:* GitHub, repository page, the gear icon next to **About**, edit **Description**. Proposed text (no promises, true today): "Offline desktop and command-line tool for small-satellite power, mass, thermal and link budgets, from one plain-text spacecraft model. Free and open source." Then press **Save changes**. (Findings F-50, F-83.)
- [ ] **Use the no-reply address for new commits** (Phase 2, decision D-259). Your commits so far show a private address in 128 commit headers; they stay as they are. *How:* GitHub, **Settings → Emails**: tick **Keep my email addresses private** and **Block command line pushes that expose my email**. The no-reply address is shown on that page. It has the form `<id>+0h3xn4@users.noreply.github.com`; the id `291340596` appears in the public Debian package metadata, so the address is most likely:

  ```bash
  git config --global user.name "0h3xn4"
  git config --global user.email "291340596+0h3xn4@users.noreply.github.com"
  ```

  Check the address against the one GitHub shows before you run it. In an existing clone, run the same two lines without `--global` if you want the setting for this repository only. Verify with `git log -1 --format='%an <%ae>'` after your next commit. (F-10, F-18.)
- [ ] **Answer the open questions** in [legal-audit.md](legal-audit.md): Q2 (country), Q13 (origin of the "CIC-SAT V6" and "real model" samples), Q15 (private list of names to search for), Q19 (repository description). The other questions are answered by the defaults, as you asked on 2026-11-09 (D-259); change any of them in the chat.
- [ ] **Decide on pull request #129** (Q12) before Phase 5 and 6 start.

## Account security (before the website goes live)

- [ ] Two-factor login with a **passkey or a hardware security key**. *How:* **Settings → Password and authentication → Two-factor authentication**. Keep the recovery codes **offline** (printed, in a safe place), not in a cloud note.
- [ ] Check **Settings → Sessions** and **Settings → Applications → Authorized OAuth Apps and Installed GitHub Apps**; remove what you do not use.

## Repository settings (Phase 6 and 7 will say when each is needed)

- [ ] **Branch and tag rulesets** for `main` and for tags `v*`, as in [docs/BRANCH_PROTECTION.md](../BRANCH_PROTECTION.md): require pull requests, require the CI checks (including every new check added in Phase 3, 4 and 6), block force-pushes and deletion. *How:* **Settings → Rules → Rulesets → New ruleset**. The list of check names comes with the Phase 6 pull request.
- [ ] **Required checks** (Phase 3): in the ruleset for `main` add `REUSE (licence and copyright of every file)` and `Signed-off-by on every commit` to the required checks, next to the existing test jobs.
- [ ] **Release the Apache-2.0 version after the Phase 3 pull request is merged** (F-27, Q10: the MIT boundary is 2.11.1). The release commit `41a330a` of the prepared 2.11.2 has MIT sources: do **not** tag it. Tag the version (2.11.2 or 2.12.0, your choice) on the merge commit of #133 or later, and move the licence entries of `CHANGELOG.md` `[Unreleased]` into that version's section. Check that the version number in `pyproject.toml` and the tag agree (the release workflow requires it).
- [ ] **Releases only by you.** Keep yourself as the only person with write access; create an environment named `release` with **required reviewers: you**. *How:* **Settings → Environments → New environment**.
- [ ] **Secret scanning and push protection.** *How:* **Settings → Code security** (or **Advanced Security**) → turn on **Secret scanning** and **Push protection**.
- [ ] **Private vulnerability reporting.** *How:* **Settings → Code security → Private vulnerability reporting → Enable**.
- [ ] **Dependabot alerts and security updates** (Phase 6 adds the version-update file). *How:* **Settings → Code security**.
- [ ] **Signed commits** (only if you want them). *How:* GitHub, **Settings → SSH and GPG keys**, add a signing key, then `git config --global commit.gpgsign true`. Then add "Require signed commits" to the ruleset.

## Personal

- [ ] **Ask your insurer** whether your personal liability insurance covers software you publish for free (R-22).
- [ ] **Give a lawyer in your country** [lawyer-questions.md](lawyer-questions.md) and [risk-register.md](risk-register.md). Ask first about LQ-01 to LQ-05.
- [ ] **Decide the contact** for the privacy page and the Code of Conduct (Q3). A dedicated project address is better than your personal one. You live in Germany (Q2): ask the lawyer whether an imprint is needed and which contact it must show (LQ-04).
- [ ] **Read the terms of the CIC-IDM website** (the account you made to download the sample model) and tell me whether they limit publishing facts about the file or naming the tool (Q13, LQ-05).
- [ ] **Decide how the AI-written commits are signed off** (F-25, LQ-15): leave the sign-off "Claude", or sign off yourself when you merge.

## Later (added in Phase 9)

- [ ] **Settings → Pages → Source: GitHub Actions**; **Enforce HTTPS**; protection rules for the `github-pages` environment.
- [ ] Apply the new repository description and topics (or confirm that Claude may).
- [ ] The site goes live only when you approve and merge the final pull request.
