Software de código abierto que usa py-tuner
===========================================

*(English: [THIRD-PARTY.md](THIRD-PARTY.md))*

py-tuner es software libre, bajo la Licencia Pública General de GNU,
versión 3 o posterior (GPL-3.0-or-later). Está hecho sobre el software de
código abierto que se lista aquí: las bibliotecas que usa y las
herramientas que lo construyen, lo prueban y lo empaquetan. Las versiones
son las de py-tuner 0.1.0 (como las resuelve `uv.lock`); `uv tree` muestra
las de cualquier versión posterior. Las licencias se dan como
identificadores SPDX, tal como las declara cada proyecto.

Todas estas licencias permiten usarlas en un programa bajo la GPL 3.
PySide6 y Qt se usan bajo la LGPL 3 de GNU, como bibliotecas que se cargan
al correr.


Las bibliotecas que necesita py-tuner
-------------------------------------

| Software | Versión | Licencia | Para qué la usa py-tuner |
|---|---|---|---|
| [NumPy](https://numpy.org) | 2.5 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | Todo el análisis: las transformadas de Fourier, el ajuste de los armónicos |
| [sounddevice](https://github.com/spatialaudio/python-sounddevice) | 0.5 | MIT | Toma el sonido de la tarjeta de sonido |
| [PortAudio](https://www.portaudio.com/) | 19.7 | MIT | La tarjeta de sonido, debajo de sounddevice |
| [PySide6](https://pyside.org) y Shiboken6 (con Qt 6) | 6.12 | LGPL-3.0-only (o GPL-2.0-only o GPL-3.0-only) | La ventana |

Lo que estas traen consigo:

| Software | Versión | Licencia |
|---|---|---|
| [cffi](https://github.com/python-cffi/cffi) | 2.1 | MIT-0 |
| [pycparser](https://github.com/eliben/pycparser) | 3.12 | BSD-3-Clause |

La interfaz de terminal usa el módulo curses de la biblioteca estándar de
Python, sobre [ncurses](https://invisible-island.net/ncurses/) (X11, una
licencia al estilo de la MIT); Python mismo está bajo la licencia PSF-2.0.

El RPM usa los paquetes de Fedora de NumPy, sounddevice, PortAudio y
PySide6. La AppImage lleva su propio Python
([python-appimage](https://github.com/niess/python-appimage), Python bajo
PSF-2.0) y una PortAudio compilada por `tools/build-libs.py` a partir de su
código.


Lo que aprendió de otros programas
----------------------------------

| Software | Licencia | Lo que py-tuner le debe |
|---|---|---|
| [FMIT](https://github.com/gillesdegottex/fmit) (Free Music Instrument Tuner), de Gilles Degottex | GPL-2.0-or-later (sus bibliotecas, LGPL-2.1-or-later) | La forma del análisis de un afinador: una estimación gruesa que no puede errar la octava y después una fina; y el estudio de dónde se pierde su precisión |

En py-tuner no hay código de FMIT: se leyó, no se copió. Los métodos que
usa py-tuner vienen de la bibliografía: la función de diferencia cuadrada
normalizada de McLeod y Wyvill ("A smarter way to find pitch", 2005) y la
inarmonicidad de las cuerdas rígidas, f_n = n·f0·√(1+B·n²) (Fletcher,
1964).


Las herramientas que lo construyen, lo prueban y lo empaquetan
--------------------------------------------------------------

| Software | Licencia | Para qué |
|---|---|---|
| [uv](https://github.com/astral-sh/uv) y uv_build | Apache-2.0 OR MIT | El entorno, el wheel y el paquete del código |
| [pytest](https://pytest.org) | MIT | Las pruebas |
| [zig](https://ziglang.org) (el paquete ziglang de PyPI) | MIT | Compila PortAudio para la AppImage |
| [appimagetool](https://github.com/AppImage/appimagetool) | MIT | Hace la AppImage |
| [rpm-build](https://rpm.org), rpm-sign, rpmdevtools | GPL-2.0-or-later | El RPM |
| [GnuPG](https://gnupg.org) | GPL-3.0-or-later | Firma los archivos, el RPM y la etiqueta |
| [Inkscape](https://inkscape.org) | GPL-2.0-or-later | Dibuja los íconos a partir de su SVG |
| [Pillow](https://python-pillow.org) | MIT-CMU | Los íconos para Windows y macOS (.ico, .icns) |
| [LuaLaTeX](https://www.luatex.org), [latexmk](https://ctan.org/pkg/latexmk), makeindex | GPL-2.0-or-later, GPL-2.0-only, MIT | Los manuales de usuario |
| [Junicode](https://github.com/psb1558/Junicode-font), [DejaVu](https://dejavu-fonts.github.io) | OFL-1.1, Bitstream-Vera | Las fuentes de los manuales |
| [AppStream](https://www.freedesktop.org/wiki/Distributions/AppStream/), desktop-file-utils | LGPL-2.1-or-later, GPL-2.0-or-later | Comprueban los metadatos y la entrada del menú |
