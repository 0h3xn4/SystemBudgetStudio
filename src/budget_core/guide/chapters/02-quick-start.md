# Quick start

## Guided mode: from an orbit to a first budget

Choose **File > New project (guided)** (Ctrl+N). Five short pages ask for:

1. **Project**: a name and the parent folder. The project is stored in a new folder named after the project; an existing folder is never touched.
2. **Spacecraft**: a sample spacecraft to start from (a 250 kg minisatellite with complete example inputs, a 150 kg microsatellite with two links, a 250 kg minisatellite with placeholder inputs, or a **blank project** with no units and no invented number, which asks for the bus voltage and skips the orbit and the scenario).
3. **Orbit**: altitude, inclination and RAAN of a near-circular orbit.
4. **Scenario**: how long to simulate and when it starts (UTC).
5. **Review**: Finish creates the project, opens it, and computes the first power timeline.

With the defaults you only press **Next** four times and **Finish**. The first power timeline appears in well under a minute. Everything in the new project is *sample data with invented numbers*; the project description says so. Replace the numbers with your own sourced values, and the Problems panel and the INCOMPLETE banners show what is still open.

## From the command line

To start a spacecraft of your own: `budget new my_satellite --bus-voltage-v 28` writes a blank project (one bus, placeholder configuration, no units; the folder must not exist). In the window, a project that is not finished shows a **Start here** card with four steps (a unit, a spacecraft mode, an orbit and a scenario, save and run) and a button for the one to do now; **Help → Start here** shows it again. To look at examples:

```
budget export-examples demo
budget validate demo/microsat_250kg_eps
budget run demo/microsat_250kg_eps --out out
budget power-timeline demo/microsat_250kg_eps --out out
budget link-passes demo/microsat_150kg --out out
budget compare demo/microsat_250kg_eps demo/microsat_250kg --out out
budget guide --out guide
```

The commands that compute reports (`run`, `scenario`, `power-timeline`, `link-passes` and `compare`) accept `--user` and `--date` so that you can regenerate a report byte for byte. Without them the user is `BUDGET_USER` or the login name, and the date is `SOURCE_DATE_EPOCH` or the clock. `budget export-examples demo` refuses to touch example folders that already exist; add `--force` to replace their files.

## The window

- The **navigation rail** on the left chooses the area: **Model** (the Units, Power modes, Spacecraft modes and Inputs grids, the Scenario and the files you open; **Add unit** (Ctrl+Shift+N) and **Remove unit** (Ctrl+Shift+Delete) on the Units grid add and remove units; **Add spacecraft mode** (Ctrl+Shift+M) on the Spacecraft modes grid adds a mode; **Add scenario** (Ctrl+Shift+O) adds an orbit and a scenario; the Edit menu also has **Add expendable** (Ctrl+Shift+X), **Add ground station** (Ctrl+Shift+G), **Add imaging target** (Ctrl+Shift+T) and **Add link** (Ctrl+Shift+L)), **Power** (the budget and the timeline), **Mass**, **Thermal**, **Link** (the budget and the passes), **Compare** and **Reports**. Press Ctrl+1 to Ctrl+7, or Ctrl+K to find any command, unit or file by a few letters of its name.
- The **project panel** (Ctrl+B) lists spacecraft, units, modes, scenarios, links and configuration files. Double-click a file to edit it; double-click a unit to edit its power modes in a table (with **View > Open with a single click**, one click does it).
- **Run** (Ctrl+R) works out the scenario, the power timeline and the link passes; the chip beside it says whether the results are up to date. The static budgets are always up to date.
- The **Problems** panel along the bottom lists errors, warnings and open items. Double-click a row to jump to the file and line. The window opens in the **focused view** (**View > Focused view**, Ctrl+Shift+F): the problems are one line of counts with a **Show problems** button, the Inspector and Provenance panels are hidden and the grids show their main columns; turn it off to see everything.
- Select a value in a table and press **Ctrl+Shift+I** (**Explain**) to see how it was worked out; **View > Show the assumptions** (Ctrl+Shift+A) lists everything the tool applies next to your own numbers (the chapter *Tracing a number*).
- **File > Export reports** (Ctrl+E) writes the reports of all budgets to a folder you choose. Long computations run in a background thread, so the window stays responsive.
- **View > Theme**, **UI size** (90 to 125 %) and **Reduce motion** make the window easier to read.
