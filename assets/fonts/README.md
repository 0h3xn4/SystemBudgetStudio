# Bundled fonts

All fonts are licensed under the SIL Open Font License 1.1; the licence texts sit next to the files.

| Files | Used for | Source | Release archive (SHA-256) |
|---|---|---|---|
| `Inter-Regular.ttf`, `Inter-Medium.ttf`, `Inter-SemiBold.ttf`, `OFL-Inter.txt` | The window (text, 400/500/600) | Inter 4.0, <https://github.com/rsms/inter/releases/tag/v4.0> | `ff970a5d4561a04f102a7cb781adbd6ac4e9b6c460914c7a101f15acb7f7d1a4` |
| `JetBrainsMono-Regular.ttf`, `JetBrainsMono-Medium.ttf`, `OFL-JetBrains-Mono.txt` | The window (numbers, identifiers, paths, code) | JetBrains Mono 2.304, <https://github.com/JetBrains/JetBrainsMono/releases/tag/v2.304> | `6f6376c6ed2960ea8a963cd7387ec9d76e3f629125bc33d1fdcd7eb7012f7bbf` |
| `IBMPlex*.ttf`, `OFL-IBM-Plex.txt` | **Exported files only** (PDF, DOCX, XLSX, plot PNGs, the user guide); not used by the window (D-168) | IBM Plex | – |

The files are the unmodified `Inter-*.ttf` of the archive's `extras/ttf` folder and the unmodified static
`JetBrainsMono-*.ttf` of its `fonts/ttf` folder. They are not downloaded at run time.
