# Static RF link budget

**What it computes.** For every link and every static point (an elevation and a range): the effective isotropic radiated power (EIRP), the receiver figure of merit (G/T), the free-space path loss, the atmospheric loss, the other losses, the carrier to noise density (C/N0); then, for each listed data rate, the energy per bit to noise density (Eb/N0), the margin over the required Eb/N0 and whether the link closes; the highest listed rate that closes and the rate at which the margin equals the required margin. It has no orbit and no time. The same equations run over the passes of a scenario for the [link passes](../user-manual/link-budget.md) (margin over time, data volume): [link passes](link-passes.md).

## Equations

| Id | Name | Formula | Source |
|---|---|---|---|
| LNK-EIRP | Effective isotropic radiated power | `EIRP = P_tx − L_line + G_tx` (dBW) | textbook link budget; citation to be supplied (SOURCE_MISSING) |
| LNK-FSPL | Free-space path loss | `L_fs = 20 log10(4π d f / c)` (dB), `c = 299 792 458 m/s` | same; `c` is exact in the SI (D-078) |
| LNK-GT | Receiver figure of merit | `G/T = G_rx − L_feed − 10 log10(T_sys)` (dB/K), or given directly | same |
| LNK-CN0 | Carrier to noise density | `C/N0 = EIRP − L_fs − L_atm − L_point − L_pol − L_impl + G/T − 10 log10(k)` (dBHz), `k = 1.380649e-23 J/K` | same; `k` is exact in the SI (D-078) |
| LNK-EBN0 | Energy per bit to noise density | `Eb/N0 = C/N0 − 10 log10(R_b)` (dB) | same |
| LNK-MARGIN | Link margin | `margin = Eb/N0 − Eb/N0_required` (dB); the link closes when `margin ≥ required margin` | the required Eb/N0 is in `config/ebn0_table.yaml` with its source |
| LNK-ATT | Atmospheric attenuation | sum of the named table entries, linear interpolation by elevation | only from `config/attenuation_table.yaml`; the tool has no propagation model (DV-P3, DV-L1) |
| LNK-NADIR | Angle from nadir at the spacecraft | `sin η = R cos(el) / r`, `r² = R² + d² + 2 R d sin(el)` | spherical Earth, antenna boresight at nadir (DV-L2) |

The data volume equation (LNK-VOLUME) belongs to the passes: [link passes](link-passes.md).

## Inputs and where they come from

| Symbol | File and field | Notes |
|---|---|---|
| `P_tx`, `L_line` | `links/<link>.yaml`, `transmitter.power_w`, `transmitter.line_loss_db` | sourced; the power is converted to dBW |
| `G_tx`, `G_rx` | `links/<link>.yaml`, `transmitter.antenna` / `receiver.antenna`: `gain_dbi`, an in-file `pattern` or a `pattern_file` | a pattern is interpolated at the angle from nadir (spacecraft side) or from boresight (ground side, 0°) |
| `G/T` | `receiver.g_over_t_dbk`, or `receiver.system_noise_temperature_k` with `receiver.feed_loss_db` and the receiver gain | sourced |
| `d`, `el` | `static_points[i].range_m`, `.elevation_deg` | plain inputs |
| `f` | `frequency_hz` | plain input |
| `L_atm` | `attenuation` (names) with `config/attenuation_table.yaml`, `entries[k].loss_db` | entries for the link frequency (within 1 %); sourced |
| `L_point`, `L_pol`, `L_impl` | `pointing_loss_db`, `polarisation_loss_db`, `implementation_loss_db` | sourced |
| `R_b` | `data_rates_bps[i]` | plain inputs |
| `Eb/N0_required` | `config/ebn0_table.yaml`, `entries[i].required_ebn0_db` for the link's modulation and coding | sourced |
| required margin | `required_margin_db` | sourced |

## Order of the computation

1. The geometry of the point; the angle from nadir (LNK-NADIR) when an antenna has a pattern.
2. EIRP (LNK-EIRP), G/T (LNK-GT or given), path loss (LNK-FSPL), atmospheric loss (LNK-ATT) and the other losses.
3. C/N0 (LNK-CN0). A placeholder in any term makes C/N0 and everything after it *n/a*; it is never replaced by zero.
4. For each listed rate: Eb/N0 (LNK-EBN0), margin (LNK-MARGIN), closes or not. The highest closing rate, and the rate at which the margin equals the required margin: `10^((C/N0 − Eb/N0_required − required margin)/10)`.

## Simplifications

See DEVIATIONS DV-L1 to DV-L3: attenuation from user tables only (no built-in propagation model), spherical Earth, antenna boresight at nadir, ground antenna tracking perfectly; no interference, no Doppler, no link availability statistics.

See any cell with [`budget explain`](explain.md) (table ids `link:static`, with the link and the point as the row, and `link:rates`, with the link, the point and the data rate in kbit/s) or *Explain this value* in the window. The user-level page: [link budget](../user-manual/link-budget.md).
