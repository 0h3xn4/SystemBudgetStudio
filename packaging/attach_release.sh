#!/usr/bin/env bash
# Attach the files of one "Installers" run to the GitHub Release of a tag.
#
#   packaging/attach_release.sh <run-id> <tag>
#
# Needs the GitHub CLI (`gh`) with GH_TOKEN set (contents: write, actions: read). It downloads the
# two artefacts of the run, checks every file against the checksum lists the run made, gives the
# two checksum lists distinct names, and uploads the result to the release of the tag. A release
# that does not exist yet is created as a DRAFT, so nothing becomes public by itself. Files
# already attached are replaced (--clobber), so the script can be run again.
set -euo pipefail

if [ $# -ne 2 ]; then
    echo "Usage: $0 <run-id> <tag>" >&2
    exit 2
fi
run_id="$1"
tag="$2"
case "$tag" in v[0-9]*) ;; *) echo "The tag must look like v1.2.3 (got '$tag')." >&2; exit 2 ;; esac

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
gh run download "$run_id" --dir "$work"
win="$work/system-budget-studio-Windows"
lin="$work/system-budget-studio-Linux"
for folder in "$win" "$lin"; do
    [ -d "$folder" ] || { echo "The run $run_id has no artefact $(basename "$folder")." >&2; exit 1; }
done

stage="$work/upload"
mkdir "$stage"
cp "$win"/*-setup.exe "$win"/*-portable.zip "$lin"/*.tar.gz "$stage"/
cp "$win/SHA256SUMS.txt" "$stage/SHA256SUMS-windows.txt"
cp "$lin/SHA256SUMS.txt" "$stage/SHA256SUMS-linux.txt"
cp "$lin/sbom.cdx.json" "$lin/licences.md" "$stage"/

# Every file must match its checksum before it is published.
(cd "$stage" && sha256sum -c SHA256SUMS-windows.txt && sha256sum -c SHA256SUMS-linux.txt)

if ! gh release view "$tag" >/dev/null 2>&1; then
    gh release create "$tag" --draft --title "System Budget Studio ${tag#v}" \
        --notes "Files of the Installers run $run_id. Add the description, then publish."
fi
gh release upload "$tag" "$stage"/* --clobber
echo "Attached $(ls "$stage" | wc -l) files to the release $tag."
