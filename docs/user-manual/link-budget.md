# Link budget

This page shows how to get the margin of a radio link at a chosen range and elevation, and the data volume you can send over every ground-station pass.

**Contents:** [Describe a link](#how-do-i-describe-a-link) · [Tables from a spreadsheet](#how-do-i-fill-the-ebn0-and-attenuation-tables-from-a-spreadsheet) · [Static table](#how-do-i-get-the-margin-at-a-chosen-range) · [Passes](#how-do-i-get-the-data-volume-over-the-passes) · [Antennas](#how-do-i-give-an-antenna-gain) · [Findings](#what-does-link_not_closed-mean)

## How do I describe a link?

**In the window:** press **Ctrl+Shift+L** (**Edit → Add link**, or *Add link* in Ctrl+K). The project needs a ground station first (**Ctrl+Shift+G**). A form asks for the name, the id (suggested from the name; it becomes the file name `links/<id>.yaml`), the **direction**, the **ground station** at the other end, the **frequency in MHz** (2200 for 2.2 GHz), the **modulation and coding** and the **data rates** in bit/s, separated by semicolons. The modulation and coding are chosen from the pairs of `config/ebn0_table.yaml`, because a link whose pair the table does not list is refused when the project loads; while the table has no entry (a blank project) you type them; add a pair to the table first with **Ctrl+Shift+B** (**Edit → Add Eb/N0 entry**: a modulation and a coding, with the Eb/N0 it requires as a placeholder for **Model → Inputs**). None of the numbers has a default. The transmit power, the line loss, the antenna gain, the G/T, the required margin and the pointing, polarisation and implementation losses are **not asked for**: they are written as placeholders (`source: TBD`) and appear in **Model → Inputs**, where you enter each value with its source. Until then the Problems panel lists each placeholder and the link shows *n/a*. The file is added in one undo step and **Save** (Ctrl+S) writes it. For an antenna pattern, attenuation, active modes or static points, edit the file as below. To remove a link, press **Ctrl+Shift+R** (**Edit → Remove from project**), choose *Link* and the name; **Save** deletes `links/<id>.yaml` after a question, and **Ctrl+Z** brings it back until then.

**By hand,** one file per direction of one link: `links/<id>.yaml`. Cut down to the shape (the numbers are placeholders for yours, each with a source):

```yaml
schema_version: 1
kind: link
name: S-band telemetry downlink
direction: downlink              # or uplink
peer: gs_north                   # ground station id; leave out for static points only
frequency_hz: 2.2 GHz
transmitter:
  power_w: {value: 2.0, source: "…"}        # RF output power
  line_loss_db: {value: 1.0, source: "…"}
  antenna:
    gain_dbi: {value: 5.0, source: "…"}
  polarisation: RHCP
receiver:
  g_over_t_dbk: {value: 18.0, source: "…"}  # or: antenna + system_noise_temperature_k + feed_loss_db
modulation: QPSK                 # with coding: an entry of config/ebn0_table.yaml
coding: rate 1/2
data_rates_bps: [32000, 128000, 512000]
required_margin_db: {value: 3.0, source: "…"}
pointing_loss_db: {value: 0.5, source: "…"}
polarisation_loss_db: {value: 0.3, source: "…"}
implementation_loss_db: {value: 1.0, source: "…"}
attenuation: [gas_s]             # names in config/attenuation_table.yaml
active_modes: [downlink]         # spacecraft modes in which the link is used (empty: always)
static_points:
  - {name: 5 deg elevation, elevation_deg: 5, range_m: 2200000}
```

The required [Eb/N0](../glossary.md#ebn0) comes from `config/ebn0_table.yaml` (an entry with the same modulation and coding). An entry may also say which error rate its Eb/N0 is for: `target_ber` (bit error rate) and `target_fer` (frame error rate), each a number above 0 and below 1, for example `target_ber: 1.0e-5`. You give them from the standard or data sheet the Eb/N0 comes from; the tool never fills them in, and no result depends on them. The Explain panel and the configuration table of the link report show them next to the number. The *Add Eb/N0 entry* form asks for them as optional fields; losses by name from `config/attenuation_table.yaml`. A project can hold several links (telemetry, payload data, inter-satellite), uplink and downlink. Every field is in the [file format](../FILE_FORMAT.md#links-decisions-d-077-to-d-083).

## How do I fill the Eb/N0 and attenuation tables from a spreadsheet?

A standard or a data sheet gives dozens of required Eb/N0 values (a modulation and coding each) or attenuation figures (by frequency and elevation). Typing them one by one in the form is slow; fill a table instead, the way [unit tables](unit-tables.md) work:

```bash
budget tables-export my_satellite ebn0 --out ebn0.xlsx          # or .csv; "attenuation" for the losses
# fill in the rows in a spreadsheet: value, source, status, note ...
budget tables-import my_satellite ebn0 ebn0.xlsx                # shows every change, writes nothing
budget tables-import my_satellite ebn0 ebn0.xlsx --apply        # writes config/ebn0_table.yaml
```

The columns are the fields of the entry: for the Eb/N0 table `modulation`, `coding`, `required_ebn0_db`, `source`, `status`, `note`, `target_ber`, `target_fer`; for the attenuation table `name`, `attenuation_kind`, `freq_hz`, `elevation_deg`, `loss_db`, `source`, `status`, `note`. The rules are the ones of the unit tables:

- A row is found by its key (modulation and coding; name, kind, frequency and elevation). A known key changes that entry; a new key **adds** an entry; the import never deletes one. A row that has only its key adds a placeholder (`source: TBD`) for you to fill in later.
- An **empty cell means unchanged**, never zero.
- **A number needs its source.** A value that is new or changed without a `source` in the same row is refused (`IMPORT_SOURCE_MISSING`): the tool never attributes a number to the source of another one, and it never fills in a standard's value itself (the project rule: no standards values are shipped). The `status` is `sourced`, `estimate` or `illustrative`.
- A value may carry a unit (`26.5 GHz` in `freq_hz`); a spreadsheet formula is never evaluated; a cell that is wrong is named by its row and column, never by its value.
- Without `--apply` nothing is written; with it the file is edited in place and keeps its comments, or is created if the project has no table yet. The project must be valid before an import starts.

**In the window** (2.8.0): **File → Export tables** and **File → Import tables** each have the three tables (*Eb/N0 table*, *Attenuation table*, *Margin policy*). Export asks for a file name (`.csv` or `.xlsx`). Import reads the filled-in file, checks it, and shows every change (old and new value) before anything is written; it stops, with the rows and columns that are wrong named, if a value has no source or is not valid, and while files of the project have unsaved edits. **Yes** writes the table file, keeping its comments, and reloads the project; the entries are also in the Ctrl+K palette.

The **margin policy** works the same way (`budget tables-export my_satellite margins`, 2.6.0): one row for each margin, with the columns `item`, `quantity`, `margin_ratio`, `source`, `status`, `note`. The `item` is a maturity class or `system`; the `quantity` is `power_margin_ratio` or `mass_margin_ratio`; a ratio is between 0 and 10. A row with a new class adds the class with its other margin as a placeholder; an import never deletes a class. The margins are a project decision, so the tool never supplies a value: every new or changed ratio needs its source in the same row.

## How do I get the margin at a chosen range?

```bash
budget run my_satellite --budget link --out out
```

For each **static point** (an [elevation](../glossary.md#elevation) and slant range you choose) and each listed data rate the table shows [EIRP](../glossary.md#eirp), [path loss](../glossary.md#path-loss), [G/T](../glossary.md#gt), other losses, [C/N0](../glossary.md#cn0), Eb/N0 and the [**margin**](../glossary.md#link-margin) over the required Eb/N0, and the highest rate that closes with the required margin. In the window: the **Link budget** tab. To see how any number of the table was obtained, with the equation of every step, the inputs and the files they come from, use `budget explain` or *View → Explain this value* in the window ([how](../models/explain.md); the model: [static link](../models/link-static.md)).

## How do I get the data volume over the passes?

```bash
budget link-passes my_satellite --out out
```

This needs a [scenario](scenarios.md) that lists the link's ground station under `sites`. For every pass the tool evaluates the link in pieces of at most 5 s, each at the elevation and range of its middle, and only inside the pass (the spacecraft antenna angle follows from the geometry, measured from nadir); the results do not depend on the scenario's `step_s` ([decision D-130](../DECISIONS.md)). It selects the **highest listed rate whose margin meets the required margin**. That gives the margin, the time with a usable rate and the data volume per pass, per scenario and, for a scenario of at least one day, per day (shorter scenarios show n/a per day):

```text
sband_down: 11 pass(es) over gs_north, 4438.17 MByte in the scenario (4438.17 MByte per day).
```

A sample counts for the part of its step that lies inside the pass and, if you set `active_modes`, for the time its part of the pass overlaps those spacecraft modes. The series CSV of a link has the column `in_pass_s` (seconds of the pass each row stands for); `selected_rate_bps` x `in_pass_s` summed over the rows gives the pass volume. A report whose pass results are n/a because a table entry (Eb/N0, attenuation) is missing carries the INCOMPLETE banner, as one with placeholders does. Not modelled: hysteresis, protocol overhead, acquisition time. In the window: the **Link passes** tab (select a pass to zoom the plot to it). To see how a number of the pass tables was obtained (a volume, a usable time, the lowest margin of a pass with the whole link budget at its sample), use `budget explain my_satellite linkpass:passes:sband_down --row 1 --column "Lowest margin (dB)"` or select it on the Passes sub-tab and choose *View → Explain this value* ([the model](../models/link-passes.md)).

## How do I give an antenna gain?

Use exactly one of: a constant `gain_dbi`; a `pattern` table (angles from nadir and gains, linearly interpolated, ends held); or a `pattern_file` CSV with columns `angle_deg,gain_dbi` and a `pattern_source`. The file must lie inside the project folder. A ground antenna must have a constant gain (it tracks).

## What does LINK_NOT_CLOSED mean?

No listed data rate meets the required margin at any static point, or at any active sample of the passes. Lower the data rates, raise the transmit power or gain, or check the losses and the required margin. `n/a` instead of numbers means an input (power, gain, Eb/N0 entry…) is still a [placeholder](placeholders-and-sources.md).

Next: [Scenarios](scenarios.md).
