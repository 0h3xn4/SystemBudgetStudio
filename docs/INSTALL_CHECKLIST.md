# Clean-machine install checklist

Run this on a machine (or a fresh user account) that has never had System Budget Studio, with no administrator rights and, ideally, no network. Tick each line; the sign-off at the end is the M6 acceptance for installation.

`CI` marks steps that the **Installers** workflow (`.github/workflows/release.yml`) already runs on every change to `packaging/` and on every tag; a person still has to do the steps that need a screen.

## Windows 10 or 11 (standard user)

- [ ] Run `system-budget-studio-<version>-windows-x64-setup.exe` as a standard user: no elevation prompt appears; it installs to `%LOCALAPPDATA%\Programs\System Budget Studio`. (CI: silent install with `/CURRENTUSER`.)
- [ ] The Start menu has *System Budget Studio*; it starts and shows the window with the IBM Plex font. (Manual.)
- [ ] `budget --version` and `budget self-test` pass in a new terminal (after ticking the PATH task, or with the full path). (CI.)
- [ ] File > New project (guided): finish with the defaults; the first power timeline appears. (Manual; the automated wizard test covers the logic.)
- [ ] File > Export reports writes XLSX, PDF and DOCX that open in Excel, a PDF reader and Word. (Manual.)
- [ ] With the network cable out or Wi-Fi off, everything above still works. (Manual; the offline test covers the code.)
- [ ] Uninstall from *Apps and features*: the program folder and the Start menu entry are gone, your project folder is untouched. (CI: silent uninstall.)
- [ ] The portable zip starts from a USB stick or a folder and writes nothing outside it. (Manual.)

## RHEL or Rocky Linux 8 (ordinary user)

- [ ] `tar xzf` the bundle and run `./install.sh` without sudo: it installs to `~/.local/opt/system-budget-studio` and prints *Self-test passed.* (CI: in a rockylinux:8 container as an unprivileged user.)
- [ ] The window starts on a graphical session (X11 or Wayland with XWayland) and shows the Carbon theme. (Manual: needs the desktop libraries listed in the guide.)
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

## Licences and integrity (all platforms)

- [ ] The program folder contains `licences/`, `licences.md` and `sbom.cdx.json`; the SBOM lists only the tool's runtime packages (about 21), no test or build tools. (CI: `packaging/check_bundle.py`.)
- [ ] The checksum of each download matches the list in `SHA256SUMS-windows.txt` (Windows files) or `SHA256SUMS-linux.txt` (the tarball, the `.deb` and the `.rpm`) on the Releases page. (Manual.)
- [ ] `system-budget-studio --smoke` exits with success on a machine with a display and, with `QT_QPA_PLATFORM=offscreen`, without one. (CI: all three platforms.)

## Sign-off

| Machine | OS version | Date | Tester | Result |
|---|---|---|---|---|
| | | | | |

Next: [Developer docs: cut a release](developer/README.md#cut-a-release) · [Docs index](README.md).
