# Provenance, input digest and `verify`

**What it is for.** A result is only as good as your ability to say what produced it. Every report, JSON file and CSV set carries a provenance block. Since 1.8 the block includes a fingerprint of the inputs, so that you, or a colleague, can check that a project is the one a result came from.

## What is recorded

| Item | Meaning | Changes when |
|---|---|---|
| Tool, Python, Libraries | The versions that computed the result | the installation changes |
| Project, Project revision | The name and the revision label from `project.yaml` | you edit them (the label is yours to raise) |
| Scenario | The scenario id, or "static (no scenario)" | |
| Run parameters | Options that change a number: environment source, shadow model, start, duration and step of the scenario; for a power timeline also the demand basis, the cases and the mission phase | you choose other options |
| Inputs digest (model) | SHA-256 of the project as loaded: every unit, mode, orbit, station, scenario, link and configuration number | a **number or a name** in any input file changes |
| Input files | The count and one SHA-256 over every file's name, size and byte hash | **any** change to a file, including a comment or spacing |
| Generated (UTC), User | When and by whom | every run (set `SOURCE_DATE_EPOCH` and `BUDGET_USER` to reproduce) |

The JSON files also list every input file with its size and hash (`provenance.input_files`) and the run parameters as name and value pairs.

## How the model digest is made

1. The loaded project is turned into plain data: every kind (units, modes, expendables, orbits, ground stations, targets, scenarios, links, configuration tables), every id, every field. Optional fields that are empty are left out.
2. The data is written as one line of JSON with sorted keys, no spaces and ASCII only; numbers are written in their shortest exact form.
3. The SHA-256 of that line is the digest.

Comments, key order, spacing, file names other than the ids, and the folder the project lives in do not enter. Because the digest is taken from what the tool *loaded*, two projects written differently but meaning the same give the same digest, and a typo in a comment does not break reproducibility.

## Checking a result: `budget verify`

```bash
budget verify results/power_static.json my_satellite
```

- **MATCH** (exit 0): the project gives the digest in the export. If some files differ as text only, they are named.
- **DIFFERENT** (exit 1): the project changed since the export. The changed, new and missing files are named (from the JSON export; a `_provenance.csv` has the digest only).
- **Not checkable** (exit 1): the export records no digest (made by 1.7 or older), or the project does not load.
- A file that is not an export of this tool gives exit 2.

If the tool version of the export differs from yours, `verify` says so. The same inputs can give a different number when an equation or a default changed between versions; every such change is recorded in [changes](../changes.md).

## Limits

- It proves the **inputs** agree, not that the numbers are right.
- Files read outside the project's YAML files (an antenna pattern file, imported environment files) are not in the manifest yet.
- Reproducing the exact bytes of a report additionally needs the same library builds (see the Libraries row) and the same `--user` and `--date`.

Decisions: [D-204](../DECISIONS.md), [D-205](../DECISIONS.md). The layout of the JSON files is in [RESULT_FORMAT.md](../RESULT_FORMAT.md).
