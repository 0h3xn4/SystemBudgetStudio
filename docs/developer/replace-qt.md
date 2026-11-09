# Replace the Qt libraries of an installed copy

System Budget Studio uses Qt 6 and PySide6 under the GNU Lesser General Public License, version 3
(LGPL-3.0). The licence lets you replace these libraries with another version of your own, for
example one you built from the source code. The installers are made so that this works: the Qt and
PySide6 libraries are separate files in the program folder, not parts of one executable.

**Contents:** [What is in the folder](#what-is-in-the-folder) · [Replace the libraries](#replace-the-libraries) · [Where the source code is](#where-the-source-code-is) · [What the program needs](#what-the-program-needs)

## What is in the folder

The program folder has two programs (`system-budget-studio` and `budget`, with `.exe` on Windows) and a folder `_internal` with everything they load. The Qt part is:

| Linux (`_internal/`) | Windows (`_internal\PySide6\`) | What it is |
|---|---|---|
| `libQt6Core.so.6`, `libQt6Gui.so.6`, `libQt6Widgets.so.6`, `libQt6DBus.so.6`, `libQt6OpenGL.so.6`, `libQt6XcbQpa.so.6`, `libQt6WaylandClient.so.6` | `Qt6Core.dll`, `Qt6Gui.dll`, `Qt6Widgets.dll` | The Qt libraries the program uses |
| `PySide6/Qt/plugins/…` | `PySide6\plugins\…` | Qt plugins: the platform (xcb, wayland, windows, offscreen), the OpenGL integrations, input contexts, platform themes, the Windows style |
| `PySide6/QtCore.abi3.so`, `QtGui.abi3.so`, `QtWidgets.abi3.so`, `libpyside6.abi3.so.6.10`, `libshiboken6.abi3.so.6.10` | `PySide6\QtCore.pyd`, `QtGui.pyd`, `QtWidgets.pyd`, `pyside6.abi3.dll`, `shiboken6\shiboken6.abi3.dll` | The Python bindings (PySide6 and shiboken6) |

The exact list of files of your copy, with the licence of each component, is in `licences/COMPONENTS.json`; the licence texts are in `THIRD_PARTY_NOTICES.txt` (also under **Help → Third-party licences**).

## Replace the libraries

1. Get a version of **PySide6 that matches the version in `THIRD_PARTY_NOTICES.txt`** (for example 6.10.x). The Python bindings and the Qt libraries must come from the same release; a different minor version of Qt does not load.
2. Install it into a separate Python environment, or build it from the source code (next section), and copy the files named in the table above over the files of the program folder. Keep the file names. On Linux the Qt libraries must keep their `.so.6` names.
3. Start the program from a terminal: `system-budget-studio --diagnose` prints the versions of Qt and PySide6 that it loaded, the graphics plugin and the screens. If Qt cannot load a library or a plugin, it names the file.
4. To go back, install the program again (the installer replaces the folder) or copy the original files back.

A copy with replaced libraries is yours: the project cannot test it and gives no support for it.

## Where the source code is

The exact source code of the Qt and PySide6 versions in a release is **attached to that release** on GitHub, with `SOURCES.txt` (the file names, their SHA-256 and what each is for):

| Archive | Contains |
|---|---|
| `qtbase-everywhere-src-<version>.tar.xz` | QtCore, QtGui, QtWidgets, QtDBus, the xcb platform plugin and the platform themes |
| `qtwayland-everywhere-src-<version>.tar.xz` | The Wayland client library and plugins |
| `pyside-setup-everywhere-src-<version>.tar.xz` | PySide6 and shiboken6 |

They are the archives published by the Qt project (<https://download.qt.io>); the project checks their SHA-256 against the values the Qt project publishes (`packaging/sources.toml`). The build instructions are those of the Qt project: the file `README` of each archive.

## What the program needs

The program uses `QtCore`, `QtGui` and `QtWidgets` and, for the window system, the platform plugins named above. It does not use Qt Network, Qt Svg, Qt Quick, the image-format plugins, Qt Print Support or Qt Charts. The list of what the installers keep and leave out is in `packaging/bundle_policy.toml`; `packaging/check_bundle.py` fails a release build that contains a Qt library or plugin outside it, or a Qt module that is licensed under the GPL only.

Next: [Developer docs](README.md) · [Licences of the libraries](../LICENCES.md).
