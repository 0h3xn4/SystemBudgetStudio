# Changes to results and behaviour

Every change that moves a number the tool prints, or that refuses an input it used to accept, is recorded here with the values before and after. Changes that add information without moving a number (new columns, new sections, new files) are in the [changelog](../CHANGELOG.md) only.

The rule for the transparency work ([plan](transparency_audit.md)): no existing numerical result changes unless a defect is found; a defect is recorded here, with a test, before it is fixed.

Newest first.

## 2026-11-05: the thermal model against the beta angle (2.7.0)

**What changed.** A new command, `budget thermal-beta`, and a new optional field `normal_lvlh` on a surface of `config/thermal_model.yaml` (schema version 3, identity migration; [D-250](DECISIONS.md)). No existing number moved: the static thermal budget, the power timeline and every other result are computed as before.

| Case | Before | After |
|---|---|---|
| Any project that does not set `normal_lvlh` | the numbers of 2.6.0 | the same numbers, the same inputs digest |
| A project that sets `normal_lvlh` | not possible | the same budgets; its inputs digest is a new value (the file changed) |
| The 250 kg, 150 kg and stress examples | no directions on surfaces | invented directions; thermal results unchanged, inputs digest and golden files updated |

**Effect.** None on any result. `budget verify` of an export made with 2.6.0 against an example of 2.7.0 reports DIFFERENT for the digest, since the example file gained the directions.

## 2026-11-04: the explanation of the demand with pointing and burns, and the margin policy as a spreadsheet (2.6.0)

**What changed.** (1) The explanation (`budget explain`, *Explain this value*) of *Average demand at source*, *Energy demanded* and of a peak-power finding of the power timeline now includes the pointing holds, slews and burns a scenario places; before, it described only the modes' demand, and for such a scenario its cross-check line and the worst peak did not agree with the table. (2) `budget tables-export` and `tables-import` take `margins` ([D-249](DECISIONS.md)). No number of any budget, no file format and no inputs digest changed.

| Case | Before | After |
|---|---|---|
| Any result of any project | the numbers of 2.5.0 | the same numbers |
| Explain of the demand, a scenario with no pointing and no burn | steps as before | the same steps |
| Explain of the demand, a scenario with pointing or burns | one step that left the load out; a cross-check that did not close | a step listing every event; a cross-check that closes |

**Effect.** None on any result. Only the text of an explanation changes, and only for scenarios that place pointing or burns.

## 2026-11-04: more shapes for the centre of gravity of an imported model (2.5.0)

**What changed.** The import now works out the centre of gravity and inertia of equipment whose shapes are whole cones, hollow cylinders, hollow cones with equal radii and tanks, as well as the shapes of 2.4.0 ([D-247](DECISIONS.md), deviation DV-IDM5). They are estimates, like the rest. Nothing else moved.

| Case | Before | After |
|---|---|---|
| Any existing project | the numbers of 2.4.0 | the same numbers, the same files, the same inputs digest |
| A model import of equipment with such a shape | no centre of gravity or inertia for that unit, a finding `IDM_GEOMETRY_SHAPE` | the unit has them, marked as an estimate; the mass budget no longer lists the unit as missing |
| CIC-SAT V6 (sample of the owner) | 104 of 124 equipment placed | 118 of 123 units placed |

**Effect.** None on existing projects. An import into a project made with 2.4.0 adds the new values to the units that had none (a value you changed is kept), so the centre of gravity of the whole satellite moves toward its real position.

## 2026-11-04: importing IDM-CIC models (2.4.0)

**What changed.** The command `budget import idm` and *File > Import IDM-CIC model...* build or update a project from a model file ([D-237 to D-244](DECISIONS.md)). No file format of the project changed (no schema version moved), no budget changed and no existing result moved: the golden files differ only by the tool version.

| Case | Before | After |
|---|---|---|
| Any existing project | the numbers of 2.3.0 | the same numbers, the same files, the same inputs digest |
| A project started from an IDM-CIC model | not possible | units, spacecraft modes, margin classes, thermal nodes, phases and expendables with their sources |

**Effect.** None on existing projects. A project made by the import has a folder `idm/` with two small files that the project loader ignores ([file format](FILE_FORMAT.md#files-of-the-idm-cic-import-240)).

## 2026-11-04: pointing and burns on the power timeline (scenario 5, orbit 4, pointing 2, propulsion 2)

**What changed.** A scenario may now place pointing modes and manoeuvres ([D-235](DECISIONS.md)), the elements of an orbit may give the local time of the node instead of the RAAN ([D-236](DECISIONS.md)). The scenario, orbit, pointing and propulsion files went up one schema version each (older files read unchanged), and the schema versions are part of the model digest, so the inputs digest of every project is a new value.

| Case | Before | After |
|---|---|---|
| A scenario that places no pointing and no manoeuvre | the power timeline of 2.2.0 | the same numbers, the same files |
| A scenario that places them | not possible | the load is added to the demand as its own series |
| Inputs digest of a project | value of 2.2.0 | a new value, the same for the old file and the new one |

**Effect.** `budget verify` of an export made by an earlier release reports DIFFERENT for the digest although the inputs are the same; the file hashes tell which. The series CSV gains a last column, `pointing_propulsion_w`, only for a scenario that places something.

## 2026-11-03: the inputs digest changes once more (the propulsion and pointing files)

**What changed.** A project may now hold `config/propulsion.yaml` and `config/pointing.yaml` ([D-233](DECISIONS.md), [D-234](DECISIONS.md)), two new file kinds at schema version 1. The model digest lists the schema version of every kind, so the digest of every project is a new value, and the example projects `microsat_250kg` and `microsat_250kg_eps` gain the file (their file hashes and digests change). No existing number changes: a project without the file gives the same budgets.

**Effect.** `budget verify` of an export made by an earlier release reports DIFFERENT for the digest although the inputs are the same; the file hashes tell which. The golden files of the examples change by the digest and file-hash lines and, for the two examples, by the new propulsion file.

## 2026-11-03: the inputs digest changes once more (orbit version 3)

**What changed.** The orbit file went up to schema version 3 for the new optional `state` block ([D-229](DECISIONS.md)), and the schema version is part of the model digest, so the digest of every project with an orbit is a new value. No result changed: an orbit given as a TLE or as elements is read and propagated exactly as before.

| Case | Before | After |
|---|---|---|
| Inputs digest of a project | value of 2.1.0 | a new value, the same for the old file and the new one |
| An orbit given as a TLE or as elements | propagated | propagated, the same numbers |
| An orbit given as a position and velocity | not possible | converted to mean elements ([DV-E7](DEVIATIONS.md)) |

**Effect.** `budget verify` of an export made by an earlier release reports DIFFERENT for the digest although the inputs are the same; the file hashes tell which. The golden files change by the digest and file-hash lines.

## 2026-11-03: the inputs digest changes once more (Eb/N0 table version 3)

**What changed.** The Eb/N0 table went up to schema version 3 for the new optional fields `target_ber` and `target_fer` ([D-225](DECISIONS.md)), and the schema version is part of the model digest, so the digest of every project that has an Eb/N0 table is a new value. No result changed: the fields are not used by any equation. A required Eb/N0 that carries a reference is named with it in the configuration table of the link report ("Required Eb/N0, QPSK rate 1/2 at BER 1e-05").

| Case | Before | After |
|---|---|---|
| Inputs digest of a project | value of 2.0.0 | a new value, the same for the old file and the new one |
| An entry without `target_ber` or `target_fer` | not possible to add | unchanged results and unchanged names |
| An entry with a reference | field refused as unknown | recorded and shown; no result changes |

**Effect.** `budget verify` of an export made by an earlier release reports DIFFERENT for the digest although the inputs are the same; the file hashes tell which. The golden files change by the digest and file-hash lines.

## 2026-10-29: the inputs digest changes again, and reports name the Earth model (model choice)

**What changed.** The scenario file went up to schema version 4 for the new optional field `earth_model` ([D-221](DECISIONS.md)), and the schema version is part of the model digest, so the digest of every project differs from the 1.9.0 value. (The format revision for provenance already changed it once; both changes are released together in 2.0.0, so a user sees one new value.) The provenance table of every report that has a scenario gains the row *Earth model* (`WGS-84` for every existing project), and the JSON environment blocks the key `earth_model`. No result changed: a scenario without the field, or with `earth_model: wgs84`, is computed on the same constants as before.

| Case | Before | After |
|---|---|---|
| A scenario without `earth_model`, or with `wgs84` | WGS-84 set | the same set, the same numbers |
| `earth_model: wgs72` on elements | not possible | WGS-72 gravity set and radius; positions differ by metres to a few kilometres over an orbit |
| `earth_model` on a TLE | not possible | no effect (TLE on WGS-72), warning `MODEL_CHOICE_IGNORED` |

**Effect.** `budget verify` of an export made before this change reports DIFFERENT for the digest although the inputs are the same. The golden files change by their digest and file-hash lines and by the *Earth model* row. Test: `tests/unit/test_earth_model.py`.

## 2026-10-29: the inputs digest changes once (file format revision)

**What changed.** The model digest of [provenance.md](models/provenance.md) is taken from what the tool loaded, and that includes the `schema_version` of each file. The format revision for provenance ([D-213](DECISIONS.md)) moved every file kind up one version, so the digest of every project is a different value than before. No input and no result changed.

| Case | Before | After |
|---|---|---|
| Inputs digest of a project | value of the release before the revision | a new value, the same for the old file and the new one (a file of the old version is migrated in memory to the new version) |
| Marking inputs with `provenance:` or `status:` | not possible | does not change the digest |

**Effect.** `budget verify` of an export made by an earlier release reports DIFFERENT for the digest although the inputs are the same; the file hashes tell which. The golden files change by their digest lines only. Test: `tests/unit/test_provenance_format.py` (marking changes neither the digest nor the environment key; a real change still does).

## 2026-10-28: a comparison pairs mass limits by phase and limit name

**What was wrong.** The mass limits table (phase, limit, value, total, margin, status) named only its first column, the phase, as its key. A comparison paired the rows of two revisions by the phase and, for a phase with several limits, by their order (`phase`, `phase #2`), so reordering or inserting a limit paired a limit with another one, and a renamed limit showed as a changed text cell.

| Case | Before | After |
|---|---|---|
| Mass limits table in a comparison | rows keyed by phase (+ order); the limit name was a compared cell | rows keyed by phase and limit name; the name is the key, not a compared cell |
| Comparison of the two revisions of `microsat_250kg_eps` | 3609 cells compared, 74 differ, 3535 unchanged | 3608 compared, 74 differ, 3534 unchanged (the limit name column is the key now) |

**Effect.** Only the count of compared cells in a comparison of mass budgets, and the pairing when limits are reordered or renamed. No budget number changed. It follows from naming the cell for `budget explain` (a limit is addressed by phase and name). Test: the golden comparison files, regenerated.

## 2026-10-28: "ton" is refused (units)

**What was wrong.** A value written with the unit `ton` (for example `5 ton` in a mass field) was read by the unit library as the US short ton, 907.18474 kg, while an engineer writing "ton" usually means the metric tonne, 1000 kg. The tool did not say so.

| Input | Before | After |
|---|---|---|
| `1 ton` in a `*_kg` field | 907.18474 kg | refused: "'ton' is ambiguous (US short ton 907 kg, metric tonne 1000 kg); write 't' for the metric tonne or 'lb' for pounds" |
| `1 tons` | 907.18474 kg | refused, same message |
| `1 t`, `1 tonne` | 1000 kg | 1000 kg (unchanged) |
| `1 lb` | 0.45359237 kg | 0.45359237 kg (unchanged) |

**Effect.** A project that used `ton` now shows an error on that field instead of a mass that was 9.3 % lower than the metric reading. The example projects do not use it. Decision: the product owner's recommendation D2 of the [transparency audit](transparency_audit.md#8-decisions-needed-from-the-product-owner). Test: `tests/unit/test_audit_units.py`.

## 2026-10-28: the power timeline no longer fails when the refinement rounds are used up

**What was wrong.** The battery full and empty instants are found by up to four refinement rounds (`MAX_REFINE_ROUNDS`). If the last round still added edges, the battery traces belonged to the previous, coarser edges while the rest of the run used the finer ones, and the orbit balance stopped with `ValueError: fp and xp are not of the same length` (shown as an internal error). No example or test case needs more than the four rounds, so no result in the repository changed.

| Case | Before | After |
|---|---|---|
| Synthetic two-orbit case run with the limit set to one round | internal error (`ValueError`) | result computed on the final edges; same minimum state of charge as the full run to 1e-6; warning `POWER_REFINEMENT_INCOMPLETE` |
| Any case that converges within the rounds | unchanged | unchanged, bit for bit (the golden files did not change) |

**Effect.** A case that needs more rounds now finishes, with a warning that the full and empty instants are accurate to the last edge found. Test: `tests/regression/test_audit_power.py`.
