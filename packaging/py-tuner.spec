# py-tuner, an accurate tuner for guitar, bass, double bass and violin.
# Copyright (C) 2026 Nicolas Vaughan <nicolasvaughan@proton.me>
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your
# option) any later version. This program is distributed WITHOUT ANY
# WARRANTY; see the LICENSE file, or <https://www.gnu.org/licenses/>.
#
# Build with packaging/build-rpm.sh, which makes the source tarball.

Name:           py-tuner
Version:        0.5.0
Release:        1%{?dist}
Summary:        An accurate tuner for guitar, bass, double bass and violin

License:        GPL-3.0-or-later
URL:            https://github.com/nivaca/py-tuner
Source0:        %{name}-%{version}.tar.gz

BuildArch:      noarch

BuildRequires:  python3-devel
BuildRequires:  desktop-file-utils
BuildRequires:  /usr/bin/appstreamcli
# For %%check: the tests run the window (headless) and the terminal interface
# (in a pseudo-terminal).
BuildRequires:  python3-pytest
BuildRequires:  python3-pyside6

# numpy and sounddevice (with PortAudio) come from the package's metadata (pyproject.toml).
# The window: Fedora's PySide6 (pyproject.toml names the PyPI wheel, pyside6-essentials).
Requires:       python3-pyside6
Requires:       hicolor-icon-theme

%description
py-tuner is a tuner for guitar, bass, double bass and violin, with a
chromatic mode for any other instrument. It listens to the sound card,
recognizes the note played, compares it with the nearest string of the
chosen tuning (or with one the user locks) and shows how many cents it is
off, with a needle and a strobe. The reference A can be set from 380 to
480 Hz, in tenths of a hertz.

On a steady string it is within a few hundredths of a cent: the pitch is
found from all the harmonics of the string, with their inharmonicity. It
runs in a window, in a full-screen terminal or on the command line, which
can also measure a WAV recording note by note, in English or Spanish.

%prep
%autosetup -n %{name}-%{version}
# (Fedora's PySide6 is python3-pyside6, which doesn't provide pyside6-essentials)
sed -i -e '/"pyside6-essentials/d' pyproject.toml

%generate_buildrequires
%pyproject_buildrequires

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files -l py_tuner
desktop-file-install --dir=%{buildroot}%{_datadir}/applications packaging/py-tuner.desktop
install -d %{buildroot}%{_datadir}/icons
cp -pr src/py_tuner/icons/linux/hicolor %{buildroot}%{_datadir}/icons/
install -Dpm 0644 packaging/io.github.nivaca.py-tuner.metainfo.xml \
    %{buildroot}%{_metainfodir}/io.github.nivaca.py-tuner.metainfo.xml
install -Dpm 0644 packaging/man/py-tuner.1 %{buildroot}%{_mandir}/man1/py-tuner.1
install -Dpm 0644 packaging/man/es/py-tuner.1 %{buildroot}%{_mandir}/es/man1/py-tuner.1

%check
desktop-file-validate %{buildroot}%{_datadir}/applications/py-tuner.desktop
appstreamcli validate --no-net %{buildroot}%{_metainfodir}/io.github.nivaca.py-tuner.metainfo.xml
export QT_QPA_PLATFORM=offscreen
%pyproject_check_import
# The whole test suite, on the installed package, with no settings of the
# builder's and the window drawn offscreen: each test file in a pytest of its
# own, as many at once as the build may use (tools/test.py).
export HOME="$PWD/check-home"
%{py3_test_envvars} %{python3} tools/test.py -j %{_smp_build_ncpus}
%{py3_test_envvars} %{buildroot}%{_bindir}/py-tuner --version | grep -q '%{version}'

%files -f %{pyproject_files}
%doc README.md README_es.md docs/DESCRIPTION.md docs/DESCRIPCIÓN_es.md docs/MANUAL_en.pdf docs/MANUAL_es.pdf
%{_bindir}/py-tuner
%{_datadir}/applications/py-tuner.desktop
%{_datadir}/icons/hicolor/*/apps/py-tuner.*
%{_metainfodir}/io.github.nivaca.py-tuner.metainfo.xml
%{_mandir}/man1/py-tuner.1*
%lang(es) %{_mandir}/es/man1/py-tuner.1*

%changelog
* Sat Nov 28 2026 Nicolas Vaughan <nicolasvaughan@proton.me> - 0.5.0-1
- Low notes through a weak microphone: the clarity judged again on the lower
  partials of the pitch found, the gate's level measured in the band of the notes

* Fri Nov 27 2026 Nicolas Vaughan <nicolasvaughan@proton.me> - 0.4.0-1
- A steady response for the double bass: the attack of each pluck left out,
  a longer average, the faint tail still read, a slower needle

* Fri Nov 27 2026 Nicolas Vaughan <nicolasvaughan@proton.me> - 0.3.0-1
- The noise of the room learned and ignored; the spectrum with its peaks named;
  a fine scale for the needle; the window no longer crashes as it closes

* Fri Nov 27 2026 Nicolas Vaughan <nicolasvaughan@proton.me> - 0.2.0-1
- Fewer wrong notes on real strings (an octave decision, note changes gated by
  plucks, a range tied to the strings); a real strobe that follows the phase of
  each partial, in vernier or harmonics mode; the history of the deviation; note
  offsets, transposition, a capo and a reference tone

* Fri Nov 27 2026 Nicolas Vaughan <nicolasvaughan@proton.me> - 0.1.0-1
- First package: the window, the terminal interface and the command line,
  in English or Spanish
