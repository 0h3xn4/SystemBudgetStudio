#!/bin/sh
# Builds the RPM package from the bundle folder (needs rpmbuild; D-149).
# Usage: make_rpm.sh <bundle folder> <output folder> [version]
# The version defaults to the one of the tool. Inside the rockylinux:8 container of
# build_in_container.sh the package is built with rpm 4.14 and installs on RHEL/Rocky 8 and 9.
set -eu

[ $# -ge 2 ] || { echo "usage: $0 <bundle folder> <output folder> [version]" >&2; exit 2; }
here="$(cd "$(dirname "$0")" && pwd -P)"
root="$(cd "$here/../.." && pwd -P)"
bundle="$(cd "$1" && pwd -P)"
mkdir -p "$2"
out="$(cd "$2" && pwd -P)"
version="${3:-$(sed -n 's/^__version__ = "\(.*\)"/\1/p' "$root/src/budget_core/__init__.py")}"
[ -n "$version" ] || { echo "cannot read the version" >&2; exit 1; }
[ -x "$bundle/system-budget-studio" ] && [ -x "$bundle/budget" ] \
    || { echo "$bundle is not a bundle folder" >&2; exit 1; }

top="$(mktemp -d)"
trap 'rm -rf "$top"' EXIT
mkdir -p "$top/BUILD" "$top/RPMS" "$top/SPECS" "$top/BUILDROOT"
rpmbuild -bb "$here/system-budget-studio.spec" \
    --define "_topdir $top" \
    --define "sbs_version $version" \
    --define "sbs_bundle $bundle" \
    --define "sbs_desktop $here/system-budget-studio.desktop"
cp "$top"/RPMS/*/*.rpm "$out/"
ls -1 "$out"/system-budget-studio-"$version"-1.*.rpm
