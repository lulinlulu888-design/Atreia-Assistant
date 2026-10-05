# The .rpm. Tauri builds the program and lays out its files (its own .rpm,
# unpacked into %{payload} by the workflow); this spec repackages them so the
# binary carries its packet-capture permission in the package itself (%caps)
# rather than from a setcap in a %post script.
#
# Why: rpm-ostree (Bazzite, Silverblue, Kinoite and the other image-based
# Fedoras) runs package scripts with most capabilities dropped, so a setcap
# there fails and the meter installs unable to capture. rpm, dnf, zypper and
# rpm-ostree all apply %caps themselves. See .github/workflows/arch-package.yml.
#
# Built with: rpmbuild -bb --define "pkgversion <v>" --define "payload <dir>"
#                      --define "filelist <file>"

%global debug_package %{nil}
# Ship the binary exactly as Tauri built it: no stripping or re-compressing.
%global __os_install_post %{nil}
%global _build_id_links none

Name:           a2-tools-dps-meter
Version:        %{pkgversion}
Release:        1
Summary:        A2Tools DPS Meter - AION 2 real-time DPS overlay
License:        GPL-3.0-only
URL:            https://github.com/taengu/A2Tools-DPS-Meter
ExclusiveArch:  x86_64

# libpcap is loaded at runtime, so rpmbuild cannot find it among the binary's
# libraries; the rest (WebKitGTK, GTK) it adds by itself.
Requires:       libpcap.so.1()(64bit)

%description
Real-time DPS overlay for AION 2, running natively on Linux while the game
runs under Proton.

%install
cp -a "%{payload}/." "%{buildroot}/"

%files -f %{filelist}
