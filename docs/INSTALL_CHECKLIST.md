# Clean-machine install checklist

Run this on a machine (or a fresh user account) that has never had System Budget Studio, with no administrator rights and, ideally, no network. Tick each line; the sign-off at the end is the M6 acceptance for installation.

`CI` marks steps that the **Installers** workflow (`.github/workflows/release.yml`) already runs on every change to `packaging/` and on every tag; a person still has to do the steps that need a screen.

## Windows 10 or 11 (standard user)

- [ ] Run `system-budget-studio-<version>-windows-x64-setup.exe` as a standard user: no elevation prompt appears; it installs to `%LOCALAPPDATA%\Programs\System Budget Studio`; it asks no question except the folder, and needs no Python. (CI: silent install with `/CURRENTUSER`.)
- [ ] The Start menu has *System Budget Studio*; it starts and shows the window in the Inter font (text) and JetBrains Mono (numbers). (Manual.)
- [ ] `budget --version` and `budget self-test` pass in a new terminal (the setup has added its folder to your PATH; no question is asked). (CI.)
- [ ] File > New project (guided): finish with the defaults; the first power timeline appears. (Manual; the automated wizard test covers the logic.)
- [ ] File > Export reports writes XLSX, PDF and DOCX that open in Excel, a PDF reader and Word. (Manual.)
- [ ] With the network cable out or Wi-Fi off, everything above still works. (Manual; the offline test covers the code.)
- [ ] Uninstall from *Apps and features*: the program folder, the Start menu entry and the PATH entry are gone (check *Environment Variables* for your user), your project folder is untouched. (CI: silent uninstall and the PATH entry.)
- [ ] The portable zip starts from a USB stick or a folder, installs nothing and makes no registry entry; the only file the window writes outside it is `layout.ini` in `%APPDATA%\System Budget Studio\`, and nothing at all with `BUDGET_NO_LAYOUT=1`. (Manual.)

## RHEL or Rocky Linux 8 (ordinary user)

- [ ] `tar xzf` the bundle and run `./install.sh` without sudo: it installs to `~/.local/opt/system-budget-studio` and prints *Self-test passed.* (CI: in a rockylinux:8 container as an unprivileged user.)
- [ ] The window starts on a graphical session (X11 or Wayland with XWayland) and shows the window in the system's colour scheme (light or dark; *View > Theme* switches it live). (Manual: needs the desktop libraries listed in the guide.)
- [ ] `budget run`, `budget power-timeline` and `budget compare` on the example projects write their files. (Manual; the CI runs `budget self-test`.)
- [ ] `~/.local/opt/system-budget-studio/uninstall.sh` removes the program, the links and the menu entry. (CI.)

## Ubuntu LTS (ordinary user)

- [ ] The same bundle installs and passes the self-test. (CI: ubuntu-latest, no sudo for the install.)
- [ ] The window starts and the guided wizard completes. (Manual.)

## Ubuntu or Debian, with the .deb (administrator)

- [ ] `sudo apt install ./system-budget-studio_<version>-1_amd64.deb` installs the package and the libraries it needs; `budget --version` and `budget self-test` pass. (CI: Ubuntu 22.04 and 24.04 and Debian 12 containers, as root.)
- [ ] The menu entry *System Budget Studio* is there with the logo as its icon; the window starts from it and shows the logo in the title bar and the task bar. (Manual; CI starts the window on a virtual X server.)
- [ ] `sudo apt remove system-budget-studio` takes away `/opt/system-budget-studio`, the two links in `/usr/bin`, the menu entry and the icons; your project folders are untouched. (CI.)

## RHEL or Rocky 8 or 9, with the .rpm (administrator)

- [ ] `sudo dnf install epel-release`, then `sudo dnf install ./system-budget-studio-<version>-1.x86_64.rpm` installs the package and the libraries it needs (`xcb-util-cursor` comes from EPEL); `budget --version` and `budget self-test` pass. (CI: rockylinux:8 and :9 containers, as root.)
- [ ] The menu entry is there with the logo, and the window starts from it. (Manual; CI starts the window on a virtual X server.)
- [ ] `sudo dnf remove system-budget-studio` takes away everything the package installed. (CI.)

## The window, on a real screen (new in 1.1.0, redone for 1.2.0; Windows, Rocky 8 and Ubuntu)

The window (redesigned in 1.1.0 and 1.2.0) was built and tested on a virtual (offscreen) display, which has a pixel ratio of 1. These steps need a person at a real screen; at least one of them on a 4K or 200 % display.

- [ ] With no project open the **welcome page** shows *Open a project folder…* and *New project (guided)…*; dropping the example folder on the window opens it. (Manual.)
- [ ] Open the complete 250 kg example. The project tree is quiet (one row per unit, badges only for errors and warnings). The text in the tree, the grids, the Problems panel (one line of counts in the focused view the window starts in; **Show problems** opens the list) and the top bar is sharp and not too small at 200 %; nothing is cut off or overlaps at 1280 x 720. (Manual; UX-47.)
- [ ] **Model > Power modes**: change a number, Ctrl+Z undoes it, a wrong value is explained under the grid, **Save** writes the file and keeps its comments. (Manual.)
- [ ] **A blank project** (1.4.0): **File > New project (guided)**, pick *Blank project*, give a bus voltage, **Finish**: the project opens on **Model > Units** with no unit, and the Problems panel lists the placeholders (**Show problems** in the focused view). **Add unit** (button, **Ctrl+Shift+N** or Ctrl+K) opens a form (Tab walks through every field, nothing is cut off at 200 %): the new unit is in the grid, **Save** writes its file, **Remove unit** then **Save** asks before it deletes the file, and **Undo** brings a removed unit back. **Add spacecraft mode** (**Ctrl+Shift+M**) opens a form, the new mode is in **Model > Spacecraft modes** with a row per unit, a typed power mode the unit does not have is refused with a message, and **Remove spacecraft mode** is refused while a scenario names the mode. **Add scenario** (**Ctrl+Shift+O**, or the button on the empty *Model > Scenario* page) opens a form that takes no default number; after **Save** and **Run** the first timeline shows eclipses. (Manual; the automated tests cover the logic.)
- [ ] **Start here and the focused view** (1.5.0, first-run pass 1.5.1): a new project shows the **Start here** card under the top bar with four steps (*Unit*, *Spacecraft mode*, *Orbit and scenario*, *Save and run*); its blue button does the step to do now, a step that needs an earlier one is greyed with a tooltip that says which, the card goes when all four are done, the **×** hides it for good (restart and check) and **Help > Start here** brings it back. A first start (no saved layout, or **View > Reset layout**) is the **focused view**: the Problems panel is one line of counts with a *Show problems* button, the Inspector and Provenance panels are hidden and a grid with optional columns has an *Optional columns* button. **View > Focused view** (**Ctrl+Shift+F**) turns it off for the full window and back; the *not checked* link in the status bar and **F8** open the list. **Edit > Add expendable** (Ctrl+Shift+X): the form has one mass field per mission phase of the project, refuses an empty one and a position with fewer than three coordinates, and the second expendable appears in the project tree and in the Mass area after **Save** and **Run**. **Edit > Add scenario**: a length of 180 days is accepted (181 is refused), the *Apogee altitude* field is empty for a near-circular orbit and, once filled, enables *Argument of perigee* and the first run shows eclipses that fit an elliptical orbit. With **View > Open with a single click** on (and in the Settings card), a click on a node of the project tree opens it and a click on a selected grid cell edits it; off, only a double-click or Enter opens and a double-click, F2 or typing edits; restart: the choice is kept. In **Model > Spacecraft modes**, double-click (or F2 on) a *power mode* cell: a list of that unit's power modes opens, one click chooses it and the file shows the change after **Save**. A blank project opens on the **Model** area (Units grid) with the rail naming *Model*; a project with units opens on **Power** with the rail naming *Power*. **Save and run** of the card ends on **Power → Timeline** with a toast. A focused tab (click *Model*, then look at *Units*) shows one ring, not a ring and a second outline over the label. The **BOL / EOL** control in the top bar is one pill with one ring when it has the keyboard, at 100 % and at 125 %. Nothing is cut off on a short screen (a laptop at 1366 x 768). (Manual.)
- [ ] **Run** (Ctrl+R): the bar and the step name appear; **Cancel** keeps the earlier results; a second **Run** completes. While the week at 1 s (below) is computed, the window keeps answering: menus open, the pointer over the plot still shows its readout, and nothing freezes for more than a blink (about 0.1 s; 1.3.0). **Power > Timeline**: click a legend entry, step through the violations, change the axis to UTC. Zooming and panning stay smooth on a week at 1 s (copy the example and set the duration to 604800 and the step to 1). (Manual.)
- [ ] **Reports**: choose a folder, export XLSX, PDF and DOCX; the list shows the files and *Show the folder* opens it. (Manual.)
- [ ] **Ctrl+K** finds a unit and a command; the Inspector follows the cell with the cursor (turn **View > Focused view** off to see the Inspector). (Manual.)
- [ ] **View > Theme > Dark** and back: no unreadable text or white patches in the plots, grids or dialogs. (Manual.)
- [ ] **View > UI size > 125 %** and back to 100 %: the text, the buttons and the tables grow and shrink together and nothing is cut off. (Manual.)
- [ ] Tab from the project panel reaches the navigation rail, the top bar, the page and the Problems panel and comes round again; the control that has the keyboard always shows a 2 px ring (check a check box, a tab and the plot too). (Manual; a test covers the walk offscreen.)
- [ ] On a **4K or 200 % display** (and, if you have one, a laptop at 150 %): the rail, the grids, the plots and the dialogs are sharp, the plot's axis title does not touch its tick labels, and *View > UI size* at 90 % and 125 % (after a restart) changes the size of everything together. At 125 % the smallest window is 1093 x 793: it needs a screen at least 800 px high. (Manual; the screenshots of every size are in `docs/ui/screenshots/m6/`.)
- [ ] With a screen reader (Narrator on Windows, Orca on Linux): the rail buttons, the *Previous* and *Next* violation arrows, the grids and the plots are read by name, not as *button* or *unknown*. (Manual; a test checks that the names exist.)

## Licences and integrity (all platforms)

- [ ] The program folder contains `licences/`, `licences.md` and `sbom.cdx.json`; the SBOM lists only the tool's runtime packages (about 21), no test or build tools. (CI: `packaging/check_bundle.py`.)
- [ ] The checksum of each download matches the list in `SHA256SUMS-windows.txt` (Windows files) or `SHA256SUMS-linux.txt` (the tarball, the `.deb` and the `.rpm`) on the Releases page. (Manual.)
- [ ] `system-budget-studio --smoke` exits with success on a machine with a display and, with `QT_QPA_PLATFORM=offscreen`, without one. (CI: all three platforms.)

## Sign-off

| Machine | OS version | Date | Tester | Result |
|---|---|---|---|---|
| | | | | |

Next: [Developer docs: cut a release](developer/README.md#cut-a-release) · [Docs index](README.md).
