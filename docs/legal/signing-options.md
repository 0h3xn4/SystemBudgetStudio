<!--
SPDX-FileCopyrightText: 2026 0h3xn4

SPDX-License-Identifier: Apache-2.0
-->

# Code signing: the options (decision for the owner)

Date: 2026-11-10. Status: **options only; nothing is implemented** (the owner's answer Q7 in D-259: present the options and costs, implement only what the owner chooses). No key, certificate or secret is stored in this repository.

Prices and rules below come from a web search on the date above and from the vendors' pages. They are approximate and change. Check each page before you decide. This page is not legal or tax advice.

## What is signed today

| Item | Status |
|---|---|
| Windows installer and portable zip | Not signed with a code-signing certificate. Windows SmartScreen shows "unknown publisher" on first run. |
| Linux tarball, `.deb`, `.rpm` | Not signed. |
| Build attestation (Sigstore, keyless, by GitHub) | **Yes**, from the first release made by the new `publish` job. It proves which workflow, on which commit, built each file. It does not give the Windows warning-free install. |
| `SHA256SUMS-*.txt` and `COMPLIANCE-RECORD.md` | Attached to the release; not signed themselves. |

## Windows options

| Option | Cost (approx.) | Who is named as publisher | Effort | Notes |
|---|---|---|---|---|
| **SignPath Foundation** (free signing for open-source projects) | Free | **SignPath Foundation**, not the owner | The owner applies; then a workflow step signs the build (needs the `release` environment, which now exists) | The conditions as published ([signpath.org](https://signpath.org/terms), [open-source page](https://about.signpath.io/product/open-source)): OSI-approved licence (Apache-2.0 qualifies), public repository, multi-factor authentication for every team member on SignPath and on GitHub, origin verification of the build, a code of conduct, the attribution text "Free code signing provided by SignPath.io, certificate by SignPath Foundation" in the documentation, and no liability of the Foundation. Read the current terms before applying. The owner's name and address are not published by this option. |
| **Azure Artifact Signing** (Microsoft; formerly Trusted Signing) | About USD 10 per month (Basic, 5,000 signatures) | The verified identity of the account (a person or an organisation) | Account in Azure, identity check, a workflow step | A third-party report says that individuals must be in the USA or Canada and that organisations can be in the USA, Canada, the EU or the UK. Not confirmed on Microsoft's pages here; check ([pricing](https://azure.microsoft.com/pricing/details/artifact-signing/)). Billing starts when the account is created. |
| **Commercial OV certificate** (for example Sectigo, DigiCert, SSL.com resellers) | About USD 200 to 450 per year | The name in the certificate, which is a verified person or company, and **is published in every signature** | Buy, identity check, hardware token or cloud key service (the vendors now generally require the key on hardware or in a cloud key service), key service in the workflow | Certificates are valid for at most about 460 days. Individual validation exists at some vendors. |
| **Commercial EV certificate** | About USD 300 to 500 per year or more | As above, a company | As above | Microsoft's own guidance says an EV certificate no longer removes the SmartScreen warning at once; reputation still has to build. EV is needed for kernel-mode drivers, which this program does not have. Not recommended. |
| **Do nothing** | Free | – | – | Users keep the warning. The checksum and the attestation stay available. |

Note on SmartScreen: for every option except the Foundation's, reputation builds with downloads. A signature does not make the warning go away on day one. ([Microsoft: code signing options](https://learn.microsoft.com/windows/apps/package-and-deploy/code-signing-options))

## Linux options

| Option | Cost | Effort | Notes |
|---|---|---|---|
| **Sigstore build attestation** (done) | Free | – | `gh attestation verify`. |
| **Signed checksum file with `cosign sign-blob` (keyless)** | Free | A step in `publish` (uses the same GitHub identity token) | Gives a second, tool-neutral way to check `SHA256SUMS`. |
| **GPG-signed `.deb` and `.rpm`** | Free | A key to create, store safely (not in the repository) and rotate; a public key to publish; a signing step | Needed only if the packages are served from a package repository. Direct downloads from the release page do not need it. |

## Recommendation

1. **Apply to SignPath Foundation after phase 7 is merged** (the code of conduct and the two-factor settings are conditions). It costs nothing, it does not publish the owner's name, and Apache-2.0 qualifies. Decide after reading the Foundation's current terms, especially the publisher name and what the project must promise.
2. Add `cosign sign-blob` for the checksum files if a user group asks for a signature that is not tied to GitHub's tooling.
3. Do not buy an EV certificate. Buy an OV certificate only if the owner wants the owner's or a company's own name as publisher and accepts that the name is published.

## What the owner must decide

- Sign with the Foundation, with Azure, with a bought certificate, or not at all.
- If a certificate with the owner's name is bought: the name that will be public (see D-259 Q1, Q3 and the privacy rules).
- Whether old releases are signed later. The default (D-259 Q8) is **no change to old releases**.

## What Claude will do after the decision

Add the signing step to `release.yml` (inside the `publish` job or a new job in the `release` environment), add a test to `tests/unit/test_workflows.py` for any new secret or permission, document the verification in `docs/security-and-privacy.md`, and record the decision in `docs/DECISIONS.md`. Secrets are set by the owner in the `release` environment; they are never written in a file.
