<!--
SPDX-FileCopyrightText: 2026 0h3xn4

SPDX-License-Identifier: Apache-2.0
-->

# Security policy

System Budget Studio is a program that runs on your computer. It reads project files, unit tables and model files, and it writes reports. It has no network code. If you find a way to make it do something harmful with a file, or a weakness in how it is built or released, please tell me in private first.

## Report a vulnerability

Use GitHub's private report: open the **Security** tab of the repository, choose **Report a vulnerability**, and describe what you found. Only the maintainer sees the report.

- Say which version (`budget --version`) and which system you used.
- Describe the steps. A small file that shows the problem helps. Make the file yourself with invented data; never send a real project, a report or a log from real work.
- Do not publish the problem before we agree on a date. I will tell you when I have read the report and when a fix is released.

If the **Report a vulnerability** button is not shown (the maintainer has not enabled it yet), open a normal issue that says only "I have a security report and need a private way to send it". Do not put details in the issue. The maintainer will then give you a private way.

There is no bug bounty. This is a project that one person maintains in their free time, so replies can take some days. Credit in the release notes is given if you want it.

## What counts

In scope:

- a file (project folder, unit table, model file, zip, XML, YAML, CSV, XLSX) that makes the program run code, read or write a file outside the folders you chose, use the network, use unbounded memory or time, or show text that was not in the file;
- an exported file (CSV, XLSX, report) that runs a formula or a macro when it is opened in a spreadsheet;
- a weakness in the release files, the installers, the build or the workflows (for example a file that does not match its checksum or attestation, or an action that can be changed by a stranger);
- a library in the installers with a known vulnerability that the program uses.

Out of scope: results that are wrong because an input value is wrong (use a normal issue), the program's statements about itself that are not about security (also a normal issue), attacks that need an attacker who already controls your account or computer, and findings in the libraries that the program does not use.

## Supported versions

Only the latest release gets security fixes. Older releases stay available for the record, but they are not fixed. See the [releases](https://github.com/0h3xn4/system-budget-studio/releases).

## What the project does about security

- The threat model and the controls are in [docs/developer/threat-model.md](docs/developer/threat-model.md) and [docs/developer/security.md](docs/developer/security.md).
- Hostile-file tests, a source scan for dangerous code, a test of the workflows, CodeQL, a secret scan, a weekly dependency audit (`pip-audit`) and dependency pins with hashes run on every change.
- Releases come with checksums, a software bill of materials, a compliance record and signed build attestations. How to check them: [docs/security-and-privacy.md](docs/security-and-privacy.md#check-a-download).
- The Windows installer is not signed with a code-signing certificate. The options are described in [docs/legal/signing-options.md](docs/legal/signing-options.md).
