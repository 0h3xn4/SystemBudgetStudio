# Settings for the repository owner to apply

These are GitHub settings that only the repository owner can change; the assistant that builds the tool has no `gh` CLI and works through pull requests only. Status as checked on 2026-10-10 (item 2 updated on 2026-10-12) (from the GitHub API and the workflow files); tick them off when done.

1. **Default branch:** `main`. *Done* (the API reports `main`).
2. **Visibility:** the repository is **public** by the owner's decision of 2026-10-12 (D-140: MIT licence, invented example data only). The earlier request to make it private is withdrawn. *Done.*
3. **Branch protection for `main`** (Settings → Branches → Add rule). *Open* (not verifiable from here):
   - Require a pull request before merging.
   - Require status checks to pass: all `CI / ubuntu-latest / py3.14` and `CI / windows-latest / py3.14` jobs, `REUSE (licence and copyright of every file)`, `Signed-off-by on every commit`, `CodeQL (python)`, `CodeQL (actions)` and `gitleaks`. (A check appears in the list only after it has run once.)
   - Require branches to be up to date; block force pushes and deletions.
4. **Actions → General:** allow only actions pinned by SHA (optional hardening; the workflows already pin every action to a commit SHA and a test keeps it so). Set the default token to read-only, and switch off "Allow GitHub Actions to create and approve pull requests". Require approval for workflows from first-time contributors.
5. **Environments → `release`:** add yourself as **required reviewer** and limit the environment to the tags `v*`. The `publish` job of `release.yml` and `attach-release.yml` run in it, so no file is attached to a release before you approve. (GitHub creates the environment, without a reviewer, the first time a workflow names it.) *Open.*
6. **Code security:** switch on private vulnerability reporting (SECURITY.md relies on it), secret scanning and push protection, Dependabot alerts and the dependency graph. Leave "code scanning default setup" off: CodeQL runs from `codeql.yml`. *Open.*
7. **Account:** two-factor authentication with a passkey or a hardware key. *Open.*

The reasons and the other controls are in [developer/security.md](developer/security.md).

Next: [Docs index](README.md) · [Developer docs](developer/README.md).
