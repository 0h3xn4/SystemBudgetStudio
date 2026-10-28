# RPM package of System Budget Studio, made from the bundle folder (D-149). Build it with
# packaging/linux/make_rpm.sh, which passes the two macros below:
#   sbs_version  the version of the tool (1.8.0)
#   sbs_bundle   the bundle folder (dist/system-budget-studio)
# The package installs the bundle into /opt/system-budget-studio, links the two programs into
# /usr/bin, and adds the menu entry and the icons. It is not signed.
Name:           system-budget-studio
Version:        %{sbs_version}
Release:        1
Summary:        Power, mass, thermal and link budgets for small satellites
License:        MIT
URL:            https://github.com/0h3xn4/SystemBudgetStudio
ExclusiveArch:  x86_64

# The bundle brings Python, Qt and every library; what rpm would find in it is not what the
# system provides, so nothing is generated and the window's system libraries are listed instead.
AutoReqProv:    no
Requires:       glibc >= 2.34
Requires:       mesa-libEGL
Requires:       mesa-libGL
Requires:       libxkbcommon
Requires:       libxkbcommon-x11
Requires:       fontconfig
Requires:       dbus-libs
Requires:       xcb-util-wm
Requires:       xcb-util-image
Requires:       xcb-util-keysyms
Requires:       xcb-util-renderutil
# in EPEL on RHEL and Rocky 9 (not in their own repositories): enable EPEL first
Requires:       xcb-util-cursor

%global debug_package %{nil}
%global __os_install_post %{nil}
%global _build_id_links none
%define _binary_payload w6.xzdio
%define sbs_dir /opt/system-budget-studio

%description
Offline desktop and command-line tool that computes power, mass, thermal and radio-link budgets
for a small satellite from one spacecraft model kept in plain text files. Every number carries
its source, results that depend on an unsourced number say n/a, and the same input always gives
the same output files. No network access is needed. The package holds a self-contained build
(Python, Qt and every library are included).

%prep
# nothing to unpack: the bundle is built before the package

%build
# nothing to build

%install
mkdir -p %{buildroot}/opt
cp -a %{sbs_bundle} %{buildroot}%{sbs_dir}
rm -f %{buildroot}%{sbs_dir}/install.sh %{buildroot}%{sbs_dir}/uninstall.sh
mkdir -p %{buildroot}%{_bindir}
ln -s %{sbs_dir}/system-budget-studio %{buildroot}%{_bindir}/system-budget-studio
ln -s %{sbs_dir}/budget %{buildroot}%{_bindir}/budget
install -D -m 0644 %{sbs_desktop} %{buildroot}%{_datadir}/applications/system-budget-studio.desktop
for icon in %{sbs_bundle}/_internal/budget_core/assets/icons/logo-*.png; do
    size=$(basename "$icon" .png)
    size=${size#logo-}
    install -D -m 0644 "$icon" \
        "%{buildroot}%{_datadir}/icons/hicolor/${size}x${size}/apps/system-budget-studio.png"
done

%post
# refresh the menu and icon caches when the tools exist; never fail the installation over them
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q %{_datadir}/applications || :
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1 && [ -f %{_datadir}/icons/hicolor/index.theme ]; then
    gtk-update-icon-cache -q -t -f %{_datadir}/icons/hicolor || :
fi

%postun
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q %{_datadir}/applications || :
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1 && [ -f %{_datadir}/icons/hicolor/index.theme ]; then
    gtk-update-icon-cache -q -t -f %{_datadir}/icons/hicolor || :
fi

%files
%defattr(-,root,root,-)
%{sbs_dir}
%{_bindir}/system-budget-studio
%{_bindir}/budget
%{_datadir}/applications/system-budget-studio.desktop
%{_datadir}/icons/hicolor/*/apps/system-budget-studio.png
