# Past releases: what they lack, and options

Date: 2026-11-09. The 24 releases v1.0.0 to v2.11.1 were built before the notices, the inventory and the source archives existed. Only the latest release, v2.11.1, was downloaded and inspected (SHA-256 checked, files listed, nothing run: [evidence](evidence/2026-11-09/release-2.11.1-contents.txt)); the older ones were built by the same workflow and are expected to be alike, which is **not verified**. This page is a finding, not a legal conclusion (LQ-03, LQ-17, LQ-18).

## Gaps of v2.11.1 (Linux tarball, `.deb`, `.rpm`; Windows setup and zip)

| Gap | Where |
|---|---|
| No third-party notices file. `licences/` has the licence texts of the 21 Python packages only. | Both |
| 96 shared libraries on Linux (system libraries of the Rocky 9 build machine, and libraries inside the Pillow and NumPy wheels), 143 DLL and PYD files on Windows (Visual C++ runtime, OpenSSL, libffi, Mesa) have no notice of their own. | Both |
| No source code of Qt, PySide6 and shiboken6, and no written offer. | Both |
| SBOM lists the 21 Python packages only. | Both |
| Unused Qt parts bundled (12 libraries, 45 plugins, translations, Qt Svg, Qt Network). | Both |
| Pillow 12.3.0 with 39 advisories (F-78). | Both |
| Unsigned installer; no attestation. | Windows |

## Options (the owner decides: question Q18; changing a release needs the owner's OK)

| Option | Effect | Cost and risk |
|---|---|---|
| **A. Leave the releases as they are and say so.** Add a short notice to the README and the release page text of the latest release: older releases lack notices and source archives; use the next release. | Nothing changed in releases. The gap stays for those who downloaded them. | No effort. Does not close the gap. |
| **B. Add files to the latest release (v2.11.1) and mark older ones as superseded.** Attach `THIRD_PARTY_NOTICES` and the source archives of Qt and PySide6 6.10.3 (the versions v2.11.1 contains) as new assets; edit the release texts of the older ones to point to them. | The latest release becomes complete. Older releases point to it. Nothing existing is replaced. | Needs the owner's OK to edit releases. Notices for v2.11.1 would have to come from a build of its tag (not the current tree). |
| **C. Add files to all 24 releases.** | Every release complete. | The Qt and PySide6 versions differ per release (6.10.1 and later for 2.x, older for 1.x); each needs its own source archives and a build of its tag. Much work. |
| **D. Take the oldest releases down.** | Fewer incomplete files online. | Destructive and cannot be undone for users who linked them; not recommended without a lawyer. |

**Recommendation:** A now (it costs nothing and is true), B for v2.11.1 once Phase 4 is merged, and the new Apache-2.0 release as the first complete one. The owner's default for Q18 is "leave and record the gap" (D-259), which is option A.
