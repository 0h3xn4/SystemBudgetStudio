#!/bin/sh
# Removes what install.sh created: the program folder, the command links, the menu entry, its
# icons, and the folders the installer created for them once they are empty. Your projects and
# reports are not touched, nor is a command of yours that install.sh did not create. The window's
# settings (layout.ini, and recent-projects.txt if you switched that list on) stay in your
# configuration folder; the script says where, and you delete that folder to remove them.
# Usage: uninstall.sh [--quiet]
set -eu

quiet=0
[ "${1:-}" = "--quiet" ] && quiet=1

self="$0"
if command -v readlink >/dev/null 2>&1 && resolved="$(readlink -f "$self" 2>/dev/null)"; then
    self="$resolved"
fi
prefix="$(cd "$(dirname "$self")" && pwd -P)"
manifest="$prefix/install-manifest.txt"
if [ ! -f "$manifest" ]; then
    echo "$prefix has no install-manifest.txt; it was not installed by install.sh." >&2
    exit 1
fi

# The folders the installer created, deepest first (read now: the manifest goes with the program).
created_dirs="$(sed -n 's/^dir //p' "$manifest" | LC_ALL=C sort -ru)"

while IFS=' ' read -r kind path; do
    if [ "$kind" = "link" ]; then
        # only remove a link that still points into this installation
        if [ -L "$path" ] && [ "$(readlink "$path")" = "$prefix/$(basename "$path")" ]; then
            rm -f "$path"
        fi
    elif [ "$kind" = "file" ]; then
        rm -f "$path"
    fi
done < "$manifest"

# The script is running from inside the folder it removes; that works because the shell has read it.
cd /
rm -rf "$prefix"
if [ -n "$created_dirs" ]; then
    printf '%s\n' "$created_dirs" | while IFS= read -r folder; do
        # rmdir removes a folder only when it is empty: one that holds other files stays.
        [ -n "$folder" ] && rmdir "$folder" 2>/dev/null || true
    done
fi
if [ "$quiet" = 0 ]; then
    echo "Removed $prefix"
    settings="${XDG_CONFIG_HOME:-$HOME/.config}/System Budget Studio"
    if [ -d "$settings" ]; then
        echo "Kept the window settings in $settings; delete that folder to remove them too."
    fi
fi
exit 0
