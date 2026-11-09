# Licence texts of components that bring none

Verbatim copies of licence texts that the shipped components do not carry in a form the build can
copy by itself (the Python runtime of the Windows installer loads `libffi-8.dll` and has no file
for it). `packaging/bundle_inventory.py` copies them into the bundle. Never edit them.

| File | Component | Source |
|---|---|---|
| `libffi-LICENSE.txt` | libffi (MIT) | `LICENSE` of libffi v3.4.6, <https://github.com/libffi/libffi/blob/v3.4.6/LICENSE> |
| `icu-73-LICENSE.txt` | ICU 73 (`libicudata`, `libicuuc`, `libicui18n` inside the PySide6 wheel) | `icu4c/LICENSE` of ICU release-73-2, <https://github.com/unicode-org/icu/blob/release-73-2/icu4c/LICENSE> |
