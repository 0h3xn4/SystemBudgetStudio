# Installing and uninstalling

System Budget Studio installs for one user and needs no administrator rights. The installers work offline and add no background service.

## Windows 10 and 11

Run `system-budget-studio-<version>-windows-x64-setup.exe`. It installs to `%LOCALAPPDATA%\Programs\System Budget Studio` and adds a Start menu entry. Tick *Add the command-line tool budget to my PATH* if you want `budget` in every terminal.

For a silent install: `setup.exe /VERYSILENT /CURRENTUSER /DIR="C:\Tools\SBS"`.

A portable alternative is `system-budget-studio-<version>-windows-x64-portable.zip`: extract it anywhere and start `system-budget-studio.exe`. Nothing is installed and no registry entry is made. The window still keeps its layout file (see *Your files* below); set the environment variable `BUDGET_NO_LAYOUT=1` before you start it to keep nothing, or `BUDGET_CONFIG_DIR` to a folder of your choice to keep the file there.

To uninstall use *Apps and features*, or run `unins000.exe` in the install folder.

## Linux (RHEL and Rocky 8 or newer, Ubuntu LTS)

```
tar xzf system-budget-studio-<version>-linux-x86_64.tar.gz
cd system-budget-studio
./install.sh
```

The script copies the program to `~/.local/opt/system-budget-studio`, links `system-budget-studio` and `budget` into `~/.local/bin`, adds an application-menu entry with the program icon, and runs the self-test. Options: `--prefix DIR` for another folder, `--no-links`, `--no-desktop`, `--force`. Installing again from the downloaded folder replaces the previous version completely. A command of yours that is already called `budget` or `system-budget-studio` is not replaced unless you pass `--force`, and an existing folder that was not created by the installer is never overwritten. Run `install.sh` from the downloaded folder, not from the installed copy.

The window needs the usual desktop libraries (EGL, OpenGL, xkbcommon, fontconfig). On a minimal RHEL or Rocky 8 or 9 install them with `sudo dnf install mesa-libEGL mesa-libGL libxkbcommon libxkbcommon-x11 fontconfig xcb-util-wm xcb-util-image xcb-util-keysyms xcb-util-renderutil`, and `xcb-util-cursor` from EPEL (`sudo dnf install epel-release` first; RHEL itself gets `epel-release` from the Fedora project's EPEL page). Without `xcb-util-cursor` the window does not open. The command-line tool and the self-test work without a display.

To uninstall run `~/.local/opt/system-budget-studio/uninstall.sh`. It removes the program, the links, the menu entry and its icons that the installer created and nothing else.

## Linux packages (.deb and .rpm)

For a machine that several people use, or that an administrator sets up, the release also has a Debian package and an RPM package. They install for all users and need administrator rights (`sudo`); the tarball above does not.

```
sudo apt install ./system-budget-studio_<version>-1_amd64.deb      # Ubuntu 22.04 or newer, Debian 12
sudo dnf install ./system-budget-studio-<version>-1.x86_64.rpm     # RHEL or Rocky 8 or 9
```

The package manager also installs the system libraries the window needs. On RHEL and Rocky one of them, `xcb-util-cursor`, is in EPEL: run `sudo dnf install epel-release` once before installing the `.rpm` (without it `dnf` says that nothing provides `xcb-util-cursor`). The program goes to `/opt/system-budget-studio`; `system-budget-studio` and `budget` are linked into `/usr/bin`; the menu entry and the icons are installed system-wide. To remove it use `sudo apt remove system-budget-studio` or `sudo dnf remove system-budget-studio`. A newer package of the same name replaces the old one. The packages are not signed: check the download against `SHA256SUMS-linux.txt` first. Do not install a package and the tarball in the same account: they are two separate copies.

## Your files

Projects, reports and exports live in folders you choose. Neither installing, upgrading nor uninstalling touches them. The only thing the tool keeps outside them is the window's layout file, `layout.ini`, in your user configuration folder (on Linux `~/.config/System Budget Studio/`, on Windows `%APPDATA%\System Budget Studio\`): the window size and position, the panels, the theme and the UI size. It never holds a project name, a path or a value, and the command-line tool does not write it. The installers and uninstallers do not touch it; delete it by hand to forget the layout. There are no other settings, caches, logs or crash dumps.

## Licences and checksums

The program folder contains `licences/` (the licence text of every bundled package), `licences.md` and `sbom.cdx.json` (a CycloneDX list of what is shipped). Each release also lists a SHA-256 checksum for every download in `SHA256SUMS-windows.txt` (the Windows files) and `SHA256SUMS-linux.txt` (the Linux file).

## Checking an installation

```
budget --version
budget self-test
```

The self-test computes and renders a small budget in every report format and builds this guide, using only the installed files. `system-budget-studio --smoke` also creates the main window and exits, which checks that the graphics libraries are present (set `QT_QPA_PLATFORM=offscreen` on a machine without a display).

## Air-gapped machines

The installers contain every dependency. To install from source on a machine without internet access, use a mirrored wheel set: `pip install --no-index --find-links wheelhouse --require-hashes -r requirements.lock`.
