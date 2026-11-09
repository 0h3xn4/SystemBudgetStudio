#!/usr/bin/env bash
# Build the portable one-folder bundle, its CycloneDX SBOM, its licence report and its notices.
# Needs the dev extra (pyinstaller, cyclonedx-bom, pip-licenses). The SBOM and the licence report
# describe what is shipped, so they are made from a runtime-only environment installed from the
# hashed lock file, never from the development environment.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-python}"
BUNDLE=dist/system-budget-studio

"$PY" -m PyInstaller --noconfirm --distpath dist --workpath build packaging/system_budget_studio.spec

RT="$(mktemp -d)"
trap 'rm -rf "$RT"' EXIT
"$PY" -m venv --without-pip "$RT/venv"
if [ -x "$RT/venv/Scripts/python.exe" ]; then RTPY="$RT/venv/Scripts/python.exe"; else RTPY="$RT/venv/bin/python"; fi
"$PY" -m pip --python "$RTPY" install --quiet --require-hashes -r requirements.lock
cyclonedx-py environment --of JSON --pyproject pyproject.toml -o dist/sbom.cdx.json "$RTPY"
pip-licenses --python "$RTPY" --format=markdown --output-file dist/licences.md

# The licence material travels with the program: texts, the licence report and the SBOM.
"$PY" packaging/licence_check.py --collect "$BUNDLE/licences"

# Source code of the LGPL components (attached to the release) and the third-party notices of Qt.
# A development build without network sets SBS_SKIP_SOURCES=1 and SBS_ALLOW_UNRESOLVED=1.
QT_NOTICES=()
if [ "${SBS_SKIP_SOURCES:-0}" != "1" ]; then
    "$PY" packaging/fetch_sources.py --out dist/sources --notices-out dist/qt-notices
    QT_NOTICES=(--qt-notices dist/qt-notices)
fi
# What else is in the bundle (Qt, system libraries, Python, the bootloader, fonts, icons): its
# licences and their texts, then THIRD_PARTY_NOTICES.txt and the SBOM of the whole bundle
"$PY" packaging/bundle_inventory.py collect "$BUNDLE" "${QT_NOTICES[@]}"
"$PY" packaging/bundle_inventory.py notices "$BUNDLE"
"$PY" packaging/bundle_inventory.py sbom "$BUNDLE" dist/sbom.cdx.json
cp "$BUNDLE/THIRD_PARTY_NOTICES.txt" dist/THIRD_PARTY_NOTICES.txt
cp LICENSE NOTICE dist/licences.md dist/sbom.cdx.json "$BUNDLE/"
"$PY" packaging/check_bundle.py "$BUNDLE"
