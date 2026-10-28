# Link passes (margin over time, data volume)

**What it computes.** For every link whose peer is a ground station of the scenario: the margin over each pass of that station, the data rate the link would use at each moment (the highest listed rate that closes with the required margin), and the data volume that follows: per pass, for the scenario and per day. It runs the equations of the [static link budget](link-static.md) at the elevation and range of every sample of a pass.

## How a pass is sampled

A pass is cut into equal pieces of at most `LINK_SAMPLE_S` when the orbit geometry can be computed at any time (an elements orbit), else into the part of the pass in each grid step (imported data). Each piece is evaluated at its middle (elevation and range). A piece **stands for** the seconds of itself in which the link is *active*: a mode listed in `active_modes` of the link (none listed: every mode) and an elevation not above `max_elevation_deg` (the tracking limit; not set: no limit). The rest of the piece counts as zero.

## Equations

| Id | Formula |
|---|---|
| LNK-FSPL, LNK-CN0, LNK-EBN0, LNK-MARGIN, … | as in the [static link budget](link-static.md), at the sample |
| LNK-VOLUME | `V = Σ R_selected × t_sample`, summed over the samples; `R_selected` is the highest listed rate whose margin is at least the required margin while the link is active, zero otherwise |

Per pass: usable time (the seconds of the samples at which some listed rate closes), the lowest margin (at the **first** listed rate, taken as the lowest, over the active samples), the volume. Per day: the scenario total divided by `duration / 86 400 s`; not given (n/a) for a scenario shorter than a day, since scaling would repeat its passes.

## Explain

`budget explain PROJECT linkpass:volume --row LINK` (a row per link: stations, passes, scenario total, per day) and `budget explain PROJECT linkpass:passes:LINK --row 1 --column "Lowest margin (dB)"` (a row per pass number). `--scenario` chooses the scenario ([how Explain works](explain.md)).

- **Lowest margin** of a pass is explained as the whole link budget at the sample where the margin is lowest: EIRP, G/T, path loss, atmospheric loss, other losses, C/N0, Eb/N0 and margin, each with its equation and inputs; the sample's elevation and range come from the pass series (time shown). 
- **Volume** (per pass, scenario total, per day) is shown as the seconds the link is active, the highest rate chosen, and the sum; the rate each sample chooses is the margin of that sample against the required margin.
- **AOS, loss of signal and the highest elevation** of a pass are read from the environment of the scenario (the orbit and the station); they are not computed again here.
- A cell is *n/a* when an input of the link budget is a placeholder, with the step that needed it.

A test compares every cell of every pass table with its explanation, for the example projects, for a placeholder, and for a scenario shorter than a day. Decision [D-209](../DECISIONS.md).
