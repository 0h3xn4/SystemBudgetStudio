# Inventory

Date: 2026-11-09. Repository state: branch `main` at `49417f6` (release 2.11.1). Read-only; nothing was changed to make this list. Facts only; judgments are in [legal-audit.md](legal-audit.md).

## 1. Repository facts that differ from the brief

| Brief says | Repository says |
|---|---|
| Version 1.3.0 | **2.11.1** (published; `main` is prepared as **2.11.2** by #131, not tagged: legal-audit F-27) (`pyproject.toml`, `src/budget_core/__init__.py`). 24 releases are published, `v1.0.0` (2026-10-12) to `v2.11.1` (2026-11-09), all under MIT. |
| `site/reference.html` exists | There is no `site/` directory on `main` or on any local or remote branch. |
| An About dialog exists | There is none. The Help menu has two entries, "Start here" and "User guide" (`src/budget_gui/main_window.py:426-436`). |
| Provenance holds user name and host name | It holds the user name only (`src/budget_core/provenance.py`). No host name is read. |
| Windows installer has a licence page | `packaging/windows/system_budget_studio.iss` sets only `AppPublisher`; it shows no licence page. |
| No other work in flight | Pull request #129 (decision D-258) was open when Phase 1 started and was **merged into `main` on 2026-11-09 (`9bf971d`)** while this work was under way. It added: `docs/security-and-privacy.md`, `scripts/verify_offline.py`, `tests/offline/test_privacy_canary.py`, the workflow `audit.yml` (`pip-audit`, weekly), the CI jobs "Offline evidence" (Linux `strace`, Windows firewall block), build-provenance attestations in `release.yml` (first used by the release after 2.11.1), and Pillow 12.3.0 to 13.0.0. This record was merged with it and updated. |

## 2. Directories

| Path | Tracked files | Kinds |
|---|---|---|
| `src/budget_core` | 199 | Python core, YAML/JSON schemas, guide chapters (Markdown) |
| `src/budget_cli` | 6 | Python command line |
| `src/budget_gui` | 84 | Python window (PySide6), theme tokens |
| `tests/` | about 340 | Python tests; `tests/golden` (88 reference files: txt, csv, json); GUI tests |
| `examples/` | 5 projects (microsat_150kg, microsat_250kg, microsat_250kg_clean, microsat_250kg_eps, stress_200_units) | YAML project files with invented data |
| `docs/` | about 560 | Markdown; `docs/images` and `docs/ui/screenshots` (PNG, one JPG, SVG) |
| `assets/fonts` | 12 | TTF fonts, OFL texts |
| `assets/icons` | 277 | Logo PNG and ICO; Lucide SVG sources (`ui/src`, 51) and rendered PNG masks |
| `assets/licences` | 3 | GPL-3.0 and LGPL-3.0 texts, README |
| `packaging/` | 20 | PyInstaller spec, Inno Setup script, Linux install, `.deb`/`.rpm` scripts, licence check, bundle check |
| `scripts/` | 6 | Screenshot and audit scripts for the window |
| `.github/workflows` | 3 | `ci.yml`, `release.yml`, `attach-release.yml` |
| root | | `LICENSE` (MIT), `README.md`, `CONTRIBUTING.md`, `CLAUDE.md`, `AUDIT.md`, `CHANGELOG.md`, lock files, `pyproject.toml` |

1937 tracked files in total: 714 PNG, 531 py, 389 yaml, 99 md, 83 txt, 53 svg, 20 json, 11 csv, 8 ttf, 1 jpg, 1 ico.
Missing: `SECURITY.md`, `CODEOWNERS`, `NOTICE`, `THIRD_PARTY_NOTICES.txt`, `LICENSES/`, `REUSE.toml`, `.github/ISSUE_TEMPLATE`, pull request template, Code of Conduct, Dependabot configuration, `.github/dependabot.yml`, `SECURITY.md`.

## 3. Non-code assets

| Asset | Path | Origin | Licence |
|---|---|---|---|
| Inter 4.0 (Regular, Medium, SemiBold) | `assets/fonts/Inter-*.ttf` | rsms/inter release v4.0, unmodified; SHA-256 of the archive recorded | OFL-1.1, "The Inter Project Authors"; no Reserved Font Name in the copyright line |
| JetBrains Mono 2.304 (Regular, Medium) | `assets/fonts/JetBrainsMono-*.ttf` | JetBrains release v2.304, unmodified; SHA-256 recorded | OFL-1.1, "The JetBrains Mono Project Authors"; no Reserved Font Name in the copyright line |
| IBM Plex (Mono Regular, Sans Regular, Sans SemiBold) | `assets/fonts/IBMPlex*.ttf` | IBM Plex; **no version and no hash recorded** | OFL-1.1, "IBM Corp." **with Reserved Font Name "Plex"** |
| Lucide icons 0.468.0 | `assets/icons/ui/src/*.svg` (51) and rendered PNG masks | lucide-icons/lucide tag 0.468.0, copied unchanged | ISC; portions MIT (Feather, Cole Bemis); text in `LICENSE-Lucide.txt` |
| Logo, banner | `docs/images/logo.svg`, `docs/images/banner.svg`, `assets/icons/logo-*.png`, `logo.ico` | Made for the project (`packaging/make_icons.py`); colours equal IBM Carbon palette values | Project licence. No origin note in the files. |
| Window screenshots | `docs/images/ui-overhaul` (10, light), `docs/ui/screenshots/m1..m6, before` (438), `docs/images/ux-audit`, `ux-redesign` | Made with `scripts/ui_*.py` from example projects | Project licence |
| `tree-before.jpg` | `docs/images/ux-redesign/tree-before.jpg` | A phone screenshot (Android EXIF, 2026-10-18); not referenced by any document | Project licence; metadata to remove |
| GPL-3.0 and LGPL-3.0 texts | `assets/licences/` | Licence texts for the Qt bindings | n/a |
| Example projects | `examples/` | Invented (338 sources "Invented example value", 276 "Synthetic example value", 322 "TBD") | Project licence |
| Test fixtures | `tests/golden`, `tests/idm`; hand-written synthetic IDM fixtures are built in code | Generated or invented | Project licence |

No third-party logo, photograph or stock image was found. Image metadata: [evidence/2026-11-09/image-metadata-scan.txt](evidence/2026-11-09/image-metadata-scan.txt): of 716 image files, one carries EXIF (`tree-before.jpg`); none carries PNG text chunks.

## 4. Dependencies

Runtime (from `requirements.lock`, hashed, 21 packages; licence column from `docs/LICENCES.md`, generated by `packaging/licence_check.py`):

| Package | Version | Licence |
|---|---|---|
| annotated-types | 0.8.0 | MIT |
| charset-normalizer | 3.5.2 | MIT |
| et-xmlfile | 2.0.0 | MIT |
| flexcache | 0.3 | BSD |
| flexparser | 0.4 | BSD-3-Clause |
| lxml | 6.1.3 | BSD-3-Clause |
| numpy | 2.5.3 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 |
| openpyxl | 3.1.5 | MIT |
| pillow | 13.0.0 (was 12.3.0 up to release 2.11.1) | MIT-CMU |
| pint | 0.26.1 | BSD |
| platformdirs | 4.12.4 | MIT |
| pydantic | 2.14.0 | MIT |
| pydantic-core | 2.50.0 | MIT |
| **pyside6-essentials** | 6.10.3 | **LGPL-3.0-only** |
| python-docx | 1.2.0 | MIT |
| reportlab | 4.5.1 | BSD |
| ruamel-yaml | 0.19.1 | MIT |
| sgp4 | 2.27 | MIT |
| **shiboken6** | 6.10.3 | **LGPL-3.0-only** |
| typing-extensions | 4.16.0 | PSF-2.0 |
| typing-inspection | 0.4.4 | MIT |

Direct dependencies in `pyproject.toml`: PySide6-Essentials, pydantic, ruamel.yaml, pint, openpyxl, reportlab, python-docx, pillow, numpy, sgp4. `defusedxml` is **not** a dependency. Build and development tools (dev extra, 95 packages in `requirements-dev.lock`): pytest, pytest-qt, hypothesis, pypdf, jsonschema, mypy, ruff, pyinstaller, cyclonedx-bom, pip-licenses, pip-audit, pip-tools. The licences of the 95 development packages were not individually reviewed in Phase 1 (they are not shipped).

## 5. What the installers bundle

Determined from `packaging/system_budget_studio.spec`, `packaging/build.sh`, `packaging/check_bundle.py` and the workflows. **No installer was built in this session** (the session has Python 3.13 and no PySide6; the project needs 3.14), so the exact Qt module and plugin list is still to be measured (Phase 4).

| Component | How it gets in | Notes |
|---|---|---|
| Python 3.14 runtime | PyInstaller one-folder build | PSF licence |
| PySide6-Essentials 6.10.3, shiboken6 | PyInstaller (shared libraries kept separate) | LGPL-3.0-only; no `PySide6-Addons`, so Qt Charts, Data Visualization and Virtual Keyboard are not expected; to be confirmed from a build |
| Qt 6 libraries and plugins | From the PySide6 wheel, as PyInstaller's hooks collect them | `PySide6.QtNetwork` is excluded; the rest not yet listed |
| The 21 Python packages above | PyInstaller | |
| PyInstaller bootloader | PyInstaller | GPL-2.0 with the bootloader exception; the exception text is not known to be shipped |
| Inter, JetBrains Mono, IBM Plex, OFL texts | `assets/` | |
| Lucide PNG masks | `assets/icons/ui` | |
| `LICENSE`, `licences.md`, `licences/<package>/…`, `licences/INDEX.md`, `sbom.cdx.json` | `packaging/build.sh` | `check_bundle.py` fails a build that lacks them |
| Inno Setup runtime parts (Windows installer) | Inno Setup 6 (`choco install innosetup`) | Inno Setup licence not recorded |
| `.deb`, `.rpm` wrappers | `packaging/linux/make_deb.py`, `make_rpm.sh` | `License: MIT` in both |

The CycloneDX SBOM (`sbom.cdx.json`) is made with `cyclonedx-py environment` from a runtime-only environment installed from `requirements.lock`. It lists the Python packages. It does not list the Python runtime, the Qt libraries as bundled, the bootloader, the fonts, the icons or the installer runtime.

## 6. Real-world data and constants

| Item | Where | Source cited | Real or invented |
|---|---|---|---|
| WGS-84 radius, mu, flattening | `src/budget_core/environment/constants.py:23-42` (read from `sgp4`) | WGS 84 (NIMA TR8350.2) | Published constants |
| WGS-72 radius, mu, J2 | `constants.py:59-76` (from `sgp4`) | Hoots and Roehrich, Spacetrack Report No. 3 | Published constants |
| Solar radius, astronomical unit | `constants.py:41-42` | IAU 2015 B3, IAU 2012 B2 | Published constants |
| Sun mean-longitude rate, low-precision Sun series | `constants.py:82-95`, `environment/geometry.py:36-65` | Astronomical Almanac | Published coefficients; marked "reproduced from memory", `SOURCE_MISSING` |
| GMST polynomial (IAU-82) | `geometry.py:59-65` | Vallado | Published coefficients |
| Conical shadow formulas | `equations.py:340-346, 446-450` | Montenbruck and Gill 3.4.2 | "Reproduced from memory", `SOURCE_MISSING` |
| ORB-FRAME terms (IAU-76 precession, IAU-1980 nutation) | `equations.py` (~412) | | "Reproduced from memory; checked against astropy" |
| Standard gravity 9.80665 | `constants.py:98-104` | 3rd CGPM, ISO 80000-3 | Defined constant |
| Speed of light, Boltzmann constant | `link/constants.py:8-14` | SI 2019 | Defined constants |
| Stefan-Boltzmann constant | `thermal/steady_state.py:22-23` | CODATA 2018 | Published constant |
| ISS two-line elements (NORAD 25544, epochs 19343 and 20194) | `tests/unit/test_earth_model.py:31`, `test_environment_models.py:15-18`, `test_audit_no_leak.py:174`, `tests/regression/test_audit_environment.py:182-183` | Comment: "from the sgp4 library documentation (public)" | **Real orbital data in tests**; terms of use not recorded. Not shipped in the installers. |
| Example orbit, ground stations, targets | `examples/*/orbits/leo.yaml`; `ground_stations/gs_north.yaml` (67, 20), `gs_south.yaml` (-45, 170); `targets/tgt_plains.yaml` | "Invented example value" | Invented. Some values sit near real ones (1360 W/m², 1400 W/m², albedo 0.3, S-band 2.2 GHz, X-band 8.2 GHz, QPSK Eb/N0 4 and 10 dB). |
| ITU-R, ECSS, CCSDS, NASA | `equations.py:125, 197-198, 276`; `docs/THERMAL_SOURCES.md`; `docs/SPEC.md:78` | Named as candidate references only | No values shipped (D-231, DEVIATIONS DV-P3, DV-L1) |
| IDM-CIC model files (CNES) | `src/budget_core/idm/` reads them; `.gitignore` excludes `*.idm` | CNES published description, version 3.4.0.19 | Third-party format. "CIC-SAT V6" and "an owner's real model" are named in `docs/DECISIONS.md` (D-246, D-253), `CHANGELOG.md` and `docs/changes.md` as test models. Origin to confirm (question Q13). |

Text and tables copied from standards, books or papers: **none found** in `docs/` (standards are named, not quoted). `docs/ui/UI_OVERHAUL.md` is "the brief, verbatim" and refers to IBM Carbon, Astro UXDS and shadcn/ui as inspiration; status colour names follow the Astro UXDS taxonomy (`src/budget_gui/theme/tokens.py:9,23,117`).

## 7. External URLs

Hosts that appear in tracked text ([evidence/2026-11-09/external-hosts.txt](evidence/2026-11-09/external-hosts.txt)): `github.com` (own repository, releases, upstream sources of fonts and icons), `www.w3.org` and `json-schema.org` (XML and schema namespace identifiers, not fetched), `scripts.sil.org` (OFL text), `www.gnu.org` and `fsf.org` (licence texts), `www.qt.io` and `code.qt.io` (Qt), `lucide.dev`, `example.invalid` (placeholder). The program does not fetch any of them (see the offline test, [claims-register.md](claims-register.md) C-03).

## 8. Where the version appears

`pyproject.toml:7`, `src/budget_core/__init__.py:4`, `README.md:55,112`, `docs/getting-started.md:66`, `docs/INSTALL_CHECKLIST.md:64`, `packaging/linux/system-budget-studio.spec:3`, `packaging/windows/system_budget_studio.iss:2`, `CHANGELOG.md`, and every file under `tests/golden/` that carries provenance (the version is written into reports, so a version bump changes the reference files). The release workflow checks that the tag equals the version in `pyproject.toml`.

## 9. Where a licence is named

| Place | Says |
|---|---|
| `LICENSE` | MIT, "Copyright (c) 2026 0h3xn4" |
| `pyproject.toml` | `license = { file = "LICENSE" }`, classifier "License :: OSI Approved :: MIT License"; no `license-files` |
| `README.md:12` | MIT badge; `README.md:108-110` "Released under the MIT licence (decision D-140)" |
| `docs/faq.md:21-23` | MIT |
| `docs/LICENCES.md` | Generated review of dependency licences; says nothing about the project licence |
| `packaging/linux/system-budget-studio.spec` | `License: MIT` |
| `packaging/linux/make_deb.py:125-130` | "Released under the MIT licence" in the Debian copyright text; maintainer is the GitHub no-reply address |
| `tests/unit/test_packages.py` | Asserts package metadata |
| `packaging/windows/system_budget_studio.iss` | No licence page |
| `CHANGELOG.md`, `docs/DECISIONS.md` (D-140) | History of the MIT decision |
| About dialog | none exists |
| Source files | No SPDX identifier and no copyright line in any source file |

## 10. Git history

The session's clone was shallow (50 commits). It was completed with `git fetch --unshallow`, and every history scan was run on the full history. 440 commits on all branches and tags, 2026-10-09 to 2026-11-09.

| Identity | Commits as author | Commits as committer |
|---|---|---|
| `ohexna <ohexna@mailbox.org>` | 128 | 0 (GitHub merged them: `GitHub <noreply@github.com>`, 128) |
| `Claude <noreply@anthropic.com>` | 312 | 312 |

Co-author trailers name Claude only (Opus 5.5 once, Sonnet 5.5, and an unversioned "Claude"). No bot, no other person. No blob over 2 MB. One secret-pattern hit: a test canary string (`tests/unit/test_audit_no_leak.py`). One personal-data hit in the tree: the GitHub no-reply address in `packaging/linux/make_deb.py`. The author address `ohexna@mailbox.org` sits in the metadata of 128 commits. Deleted files in history are invented examples (`cubesat_3u`), old fonts and screenshots. See [evidence/2026-11-09/history-scan.txt](evidence/2026-11-09/history-scan.txt).
