Open-source software used by py-tuner
=====================================

*(Español: [TERCEROS_es.md](TERCEROS_es.md))*

py-tuner is free software, under the GNU General Public License, version 3
or later (GPL-3.0-or-later). It is built on the open-source software listed
here: the libraries it uses, and the tools that build, test and package it.
The versions are those of py-tuner 0.1.0 (as `uv.lock` resolves them); `uv
tree` shows those of any later version. Licences are given as SPDX
identifiers, as each project declares them.

All of these licences allow their use in a program under the GPL 3. PySide6
and Qt are used under the GNU LGPL 3, as libraries loaded at run time.


The libraries py-tuner needs
----------------------------

| Software | Version | Licence | What py-tuner does with it |
|---|---|---|---|
| [NumPy](https://numpy.org) | 2.5 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | The whole analysis: the Fourier transforms, the fit of the harmonics |
| [sounddevice](https://github.com/spatialaudio/python-sounddevice) | 0.5 | MIT | Takes the sound from the sound card |
| [PortAudio](https://www.portaudio.com/) | 19.7 | MIT | The sound card, under sounddevice |
| [PySide6](https://pyside.org) and Shiboken6 (with Qt 6) | 6.12 | LGPL-3.0-only (or GPL-2.0-only or GPL-3.0-only) | The window |

What these bring with them:

| Software | Version | Licence |
|---|---|---|
| [cffi](https://github.com/python-cffi/cffi) | 2.1 | MIT-0 |
| [pycparser](https://github.com/eliben/pycparser) | 3.12 | BSD-3-Clause |

The terminal interface uses the curses module of Python's standard library,
over [ncurses](https://invisible-island.net/ncurses/) (X11, an MIT-style
licence); Python itself is under the PSF-2.0 licence.

The RPM uses Fedora's packages of NumPy, sounddevice, PortAudio and
PySide6. The AppImage carries its own Python
([python-appimage](https://github.com/niess/python-appimage), Python under
PSF-2.0), and a PortAudio compiled by `tools/build-libs.py` from its
source.


What it learnt from other programs
----------------------------------

| Software | Licence | What py-tuner owes it |
|---|---|---|
| [FMIT](https://github.com/gillesdegottex/fmit) (Free Music Instrument Tuner), by Gilles Degottex | GPL-2.0-or-later (its libraries LGPL-2.1-or-later) | The shape of a tuner's analysis: a coarse estimate that cannot be wrong by an octave, then a fine one; and the study of where its precision is lost |
| [Strobie](https://github.com/dsego/strobe-tuner) (strobe-tuner), by Davorin Šego | GPL-3.0 | The strobe driven by the phase of each partial, its rate scaled to cents and its stripes fading with the noise, and its vernier and harmonic modes; the prominence of a partial over its local background (its harmonic stack); the high-pass under the range; onsets as a level 1.5 times its envelope; a new note that is a harmonic or an undertone of the one sounding waits longer; the note held until 10 cents past halfway; note offsets; the trace of the deviation; and measuring with recordings shifted by known cents |
| [Entropy Piano Tuner](https://gitlab.com/tp3/Entropy-Piano-Tuner), by Haye Hinrichsen and Christoph Wick | GPL-3.0 | Its stroboscope, which demodulates the sound at each target partial with a decaying average; the negative weights of its key recognizer's kernel, where the partials of a wrong octave would fall |
| [Tuneo](https://github.com/DonBraulio/tuneo), by Braulio Ríos | "MIT No-Competition" (MIT with a restriction on commercial app stores) | Following the note that is sounding while it decays, and a full search again after a pluck; the scrolling history of the deviation. Its recordings of guitar strings were used to measure py-tuner (`tools/evaluate.py`), on this computer only |
| [pianito](https://github.com/4esv/pianito), by Axel Stevens | MIT | A search clamped near the strings when they are known; synthetic test tones with an attack, decaying partials and a weak fundamental; the command that plays a reference tone |

No code of these programs is in py-tuner: their sources were read, and the
ideas written again in Python. Tuneo's licence adds a restriction that the
GPL does not allow, so nothing of it (neither code nor recordings) is in
py-tuner or its releases. The methods
py-tuner uses come from the literature: McLeod and Wyvill's normalized
square difference function ("A smarter way to find pitch", 2005), and the
inharmonicity of stiff strings, f_n = n·f0·√(1+B·n²) (Fletcher, 1964).


Tools that build, test and package it
-------------------------------------

| Software | Licence | What for |
|---|---|---|
| [uv](https://github.com/astral-sh/uv) and uv_build | Apache-2.0 OR MIT | The environment, the wheel and the source package |
| [pytest](https://pytest.org) | MIT | The tests |
| [pyte](https://github.com/selectel/pyte) | LGPL-3.0 | Reads the terminal interface's screen for its pictures (`tools/terminal_images.py`) |
| [zig](https://ziglang.org) (the ziglang package of PyPI) | MIT | Compiles PortAudio for the AppImage |
| [appimagetool](https://github.com/AppImage/appimagetool) | MIT | Makes the AppImage |
| [rpm-build](https://rpm.org), rpm-sign, rpmdevtools | GPL-2.0-or-later | The RPM |
| [GnuPG](https://gnupg.org) | GPL-3.0-or-later | Signs the files, the RPM and the tag |
| [Inkscape](https://inkscape.org) | GPL-2.0-or-later | Draws the icons from their SVG |
| [Pillow](https://python-pillow.org) | MIT-CMU | The icons for Windows and macOS (.ico, .icns) |
| [LuaLaTeX](https://www.luatex.org), [latexmk](https://ctan.org/pkg/latexmk), makeindex | GPL-2.0-or-later, GPL-2.0-only, MIT | The user manuals |
| [Junicode](https://github.com/psb1558/Junicode-font), [DejaVu](https://dejavu-fonts.github.io) | OFL-1.1, Bitstream-Vera | The fonts of the manuals |
| [AppStream](https://www.freedesktop.org/wiki/Distributions/AppStream/), desktop-file-utils | LGPL-2.1-or-later, GPL-2.0-or-later | Check the metadata and the menu entry |
