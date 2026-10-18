#!/bin/sh
# Installs a built .deb or .rpm in a clean distribution container, checks it, and removes it again
# (run as root inside the container; D-149). The window is started for real on a virtual X server,
# so a system library missing from the package's requirements fails here.
#
#   test_package.sh deb|rpm <package file>
#
# Ubuntu and Debian containers use apt, Rocky and RHEL ones use dnf.
set -eu

[ $# -eq 2 ] || { echo "usage: $0 deb|rpm <package file>" >&2; exit 2; }
kind="$1"
package="$(cd "$(dirname "$2")" && pwd -P)/$(basename "$2")"

step() { printf '== %s\n' "$*"; }
fail() { printf 'FAILED: %s\n' "$*" >&2; exit 1; }
gone() { for path in "$@"; do [ ! -e "$path" ] && [ ! -L "$path" ] || fail "still there after removal: $path"; done; }
present() { for path in "$@"; do [ -e "$path" ] || fail "missing after installation: $path"; done; }

PROGRAM_PATHS="/opt/system-budget-studio /usr/bin/budget /usr/bin/system-budget-studio"
MENU_PATHS="/usr/share/applications/system-budget-studio.desktop"
ICON_PATHS="/usr/share/icons/hicolor/16x16/apps/system-budget-studio.png /usr/share/icons/hicolor/256x256/apps/system-budget-studio.png"

step "install $package"
case "$kind" in
    deb)
        export DEBIAN_FRONTEND=noninteractive
        apt-get update -q
        apt-get install -y -q "$package" xvfb xauth desktop-file-utils
        dpkg -s system-budget-studio | grep -q '^Status: install ok installed'
        ;;
    rpm)
        # xcb-util-cursor, which Qt's window needs, is in EPEL on RHEL and Rocky 8 and 9
        dnf -y install epel-release
        dnf -y install "$package" xorg-x11-server-Xvfb xauth desktop-file-utils
        rpm -q system-budget-studio
        ;;
    *) fail "unknown package kind: $kind" ;;
esac

step "files"
# shellcheck disable=SC2086
present $PROGRAM_PATHS $MENU_PATHS $ICON_PATHS
[ "$(readlink /usr/bin/budget)" = /opt/system-budget-studio/budget ] || fail "the link of budget"
desktop-file-validate /usr/share/applications/system-budget-studio.desktop
grep -q '^Icon=system-budget-studio$' /usr/share/applications/system-budget-studio.desktop
[ ! -e /opt/system-budget-studio/install.sh ] || fail "the per-user installer is in the package"
present /opt/system-budget-studio/LICENSE /opt/system-budget-studio/licences.md \
    /opt/system-budget-studio/sbom.cdx.json /opt/system-budget-studio/licences/INDEX.md
case "$kind" in
    deb) dpkg -V system-budget-studio ;;
    rpm) rpm -V system-budget-studio ;;
esac

step "the programs"
budget --version
budget self-test
system-budget-studio --self-test
work="$(mktemp -d)"
budget export-examples "$work/demo" >/dev/null
budget validate "$work/demo/microsat_250kg_eps"
budget run "$work/demo/microsat_250kg_eps" --budget power --report json --out "$work/out" || true
[ -s "$work/out/power_static.json" ] || fail "the power budget wrote no file"
QT_QPA_PLATFORM=offscreen system-budget-studio --smoke
step "the window on a virtual X server"
unset QT_QPA_PLATFORM
xvfb-run -a system-budget-studio --smoke

step "reinstall over the installed version"
case "$kind" in
    deb) apt-get install -y -q --reinstall "$package" ;;
    rpm) dnf -y reinstall "$package" ;;
esac
budget --version

step "remove"
case "$kind" in
    deb) apt-get remove -y -q system-budget-studio ;;
    rpm) dnf -y remove system-budget-studio ;;
esac
# shellcheck disable=SC2086
gone $PROGRAM_PATHS $MENU_PATHS $ICON_PATHS
echo "Package test passed: $kind"
