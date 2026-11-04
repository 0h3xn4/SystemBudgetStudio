# Link budget

A link file describes one direction of one radio link: frequency, transmitter, receiver, modulation and coding, the data rates, the required margin, losses and the atmospheric attenuation entries it uses. A project can hold several links (telemetry, payload data, inter-satellite).

In the window, **Edit > Add link** (Ctrl+Shift+L) writes the link file from a form: the direction, the ground station at the other end, the frequency in MHz, the modulation and coding (a pair of the Eb/N0 table) and the data rates. The numbers that come from a data sheet or a standard (transmit power, antenna gain, G/T, the required margin and the losses) are written as placeholders (`source: TBD`) and filled in under **Model > Inputs**; until then the link shows **n/a**. Add the ground station first (**Edit > Add ground station**, Ctrl+Shift+G), and a pair to the Eb/N0 table if it has none (**Edit > Add Eb/N0 entry**, Ctrl+Shift+B; the Eb/N0 it requires is a placeholder for **Model > Inputs**).

## Static table

For every *static point* (a chosen elevation and slant range) and every listed data rate the table shows EIRP, path loss, G/T, other losses, C/N0, Eb/N0 and the margin over the required Eb/N0 from `config/ebn0_table.yaml`, and the highest rate that closes with the required margin. An entry of that table may record the bit and frame error rate its Eb/N0 is quoted for (`target_ber`, `target_fer`); you supply them, they are shown next to the number in Explain and in the report, and no result depends on them.

## Pass series

**Link passes > Compute** evaluates the link over every pass of the scenario for the link's ground station. The spacecraft antenna angle follows from the geometry (angle from nadir). Each pass is sampled in pieces of at most 5 s, evaluated in their middle and inside the pass only, so the result does not depend on the scenario step. For each sample the highest listed rate whose margin is at least the required margin is selected, which gives the data volume per pass and, for a scenario of at least a day, per day. A pass-by-pass table and a plot of the margin and the selected rate are shown; selecting a pass zooms the plot to it.

## Antennas

Use a constant `gain_dbi`, a `pattern` table (angle from nadir to gain, linear interpolation) or a `pattern_file` CSV with its `pattern_source`. A ground antenna must have a constant gain.

## Tables from a spreadsheet

The Eb/N0 table and the attenuation table can be written as a CSV or XLSX and read back: `budget tables-export PROJECT ebn0` (or `attenuation`, or `margins` for the margin policy), fill in the values with their sources, `budget tables-import PROJECT ebn0 FILE` (it shows every change and writes nothing; `--apply` writes). A value that is new or changed needs its source in the same row. The tool ships no standards values; this is how you load the ones you may use.

## What stays open

Transmit powers, gains, G/T, losses, required Eb/N0 and attenuation are your numbers; the examples contain invented values.
