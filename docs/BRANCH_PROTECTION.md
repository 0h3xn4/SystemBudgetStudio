# Settings for the repository owner to apply

These are GitHub settings that only the repository owner can change; the assistant that builds the tool has no `gh` CLI and works through pull requests only. Status as checked on 2026-10-10 (item 2 updated on 2026-10-12) (from the GitHub API and the workflow files); tick them off when done.

1. **Default branch:** `main`. *Done* (the API reports `main`).
2. **Visibility:** the repository is **public** by the owner's decision of 2026-10-12 (D-140: MIT licence, invented example data only). The earlier request to make it private is withdrawn. *Done.*
3. **Branch protection for `main`** (Settings → Branches → Add rule). *Open* (not verifiable from here):
   - Require a pull request before merging.
   - Require status checks to pass: all `CI / ubuntu-latest / py3.14` and `CI / windows-latest / py3.14` jobs.
   - Require branches to be up to date; block force pushes and deletions.
4. **Actions → General:** allow only actions pinned by SHA (optional hardening). The workflows already pin every action to a commit SHA.

Next: [Docs index](README.md) · [Developer docs](developer/README.md).
