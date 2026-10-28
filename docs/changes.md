# Changes to results and behaviour

Every change that moves a number the tool prints, or that refuses an input it used to accept, is recorded here with the values before and after. Changes that add information without moving a number (new columns, new sections, new files) are in the [changelog](../CHANGELOG.md) only.

The rule for the transparency work ([plan](transparency_audit.md)): no existing numerical result changes unless a defect is found; a defect is recorded here, with a test, before it is fixed.

Newest first.

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
