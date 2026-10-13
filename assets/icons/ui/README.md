# User-interface icons

The `src/*.svg` files are icons of [Lucide](https://lucide.dev), version **0.468.0** (tag `0.468.0` of
<https://github.com/lucide-icons/lucide>), under the ISC licence ([LICENSE-Lucide.txt](LICENSE-Lucide.txt)),
copied unchanged.

The window does not read the SVG files. `packaging/make_ui_icons.py` renders each one into black
PNG masks (`<name>-16.png` to `<name>-48.png`), which the window tints with the colour of the
theme at run time (`budget_gui/icons.py`). PNG files need no Qt SVG plugin in the installers
(D-148, D-150).

To add an icon: copy its SVG from the Lucide repository into `src/`, add the name to `NAMES` in
`packaging/make_ui_icons.py`, run the script, commit the PNG files, and name the icon in
`budget_gui/icons.py` where it is used.
