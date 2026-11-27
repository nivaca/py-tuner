#!/usr/bin/env python3
"""Hace una AppImage de py-tuner, para Linux:

    uv run python tools/bundle-appimage.py [-o CARPETA] [--python APPIMAGE]
                                          [--python-version 3.14] [--appimagetool APPIMAGE]

La AppImage es build/release/py-tuner-VERSIÓN-x86_64.AppImage (la versión de
pyproject.toml; --output da otra carpeta). Lleva un Python propio (uno
reubicable del proyecto python-appimage, https://github.com/niess/python-appimage),
con py-tuner y todo lo que necesita instalado dentro (NumPy, sounddevice,
PySide6), y el PortAudio que compila tools/build-libs.py; así corre en cualquier Linux reciente (glibc 2.34 o
posterior: Ubuntu 22.04, Debian 12, Fedora 35 y posteriores) sin instalar nada.

    py-tuner.AppImage                 la ventana
    py-tuner.AppImage tui | cli ...   la terminal o la línea de órdenes, con las opciones de siempre

Lo que necesita se descarga la primera vez y queda en la caché del usuario
(~/.cache/py-tuner-build): el Python y appimagetool
(https://github.com/AppImage/appimagetool). El wheel del programa lo hace
"uv build", y sus dependencias vienen de PyPI (por eso hace falta la red);
PortAudio la hace tools/build-libs.py (en build/libs) si todavía no está.
(Tomado de py-slowdown.)
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import tomllib
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "build" / "release"  # (not dist/, which keeps only the RPM)
APP_ID = "py-tuner"
ARCH = "x86_64"
VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]

# The Python put in the AppImage (python-appimage has one release per version,
# with an AppImage per manylinux; PySide6 needs glibc 2.34 anyway).
PYTHON = "3.14"
PYTHON_RELEASES = "https://api.github.com/repos/niess/python-appimage/releases/tags/python{version}"
MANYLINUX = ("manylinux_2_28", "manylinux2014")
APPIMAGETOOL = f"https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-{ARCH}.AppImage"

# Parts of PySide6/Qt the program doesn't use (QML/Quick, the designer and
# other tools, headers, type stubs), left out to make the AppImage smaller.
PRUNE = [
    "PySide6/Qt/qml", "PySide6/Qt/libexec", "PySide6/include", "PySide6/typesystems", "PySide6/glue",
    "PySide6/scripts", "PySide6/examples", "PySide6/doc",
    "PySide6/designer", "PySide6/assistant", "PySide6/linguist", "PySide6/lrelease", "PySide6/lupdate",
    "PySide6/qmlformat", "PySide6/qmllint", "PySide6/qmlls", "PySide6/qmlcachegen", "PySide6/qmlimportscanner",
    "PySide6/qmltyperegistrar", "PySide6/balsam", "PySide6/balsamui", "PySide6/svgtoqml", "PySide6/qsb",
    "PySide6/rcc", "PySide6/uic", "PySide6/Qt/plugins/designer", "PySide6/Qt/plugins/qmltooling",
    "PySide6/Qt/plugins/qmllint",
]
PRUNE_GLOBS = ["PySide6/*.pyi", "PySide6/Qt/lib/libQt6Designer*", "PySide6/Qt/lib/libQt6Qml*",
               "PySide6/Qt/lib/libQt6Quick*", "PySide6/Qt/lib/libQt6ShaderTools*", "PySide6/Qt/lib/libQt6Help*",
               "PySide6/QtQml*", "PySide6/QtQuick*", "PySide6/QtDesigner*", "PySide6/QtHelp*",
               "PySide6/Qt/translations/assistant_*", "PySide6/Qt/translations/designer_*",
               "PySide6/Qt/translations/linguist_*", "PySide6/Qt/translations/qtdeclarative_*",
               "PySide6/Qt/translations/qt_help_*"]

DESKTOP = (ROOT / "packaging" / f"{APP_ID}.desktop").read_text(encoding="utf-8")
LIBS = ("libportaudio.so.2",)  # (made by tools/build-libs.py)

# %(python)s: the interpreter, relative to the AppDir
APPRUN = r"""#!/bin/bash
#  Starts py-tuner in the AppImage (made by tools/bundle-appimage.py).
ROOT="$(dirname "$(readlink -f -- "$0")")"
export APPDIR="${APPDIR:-$ROOT}"
PYTHON="$APPDIR/%(python)s"
#  (the AppImage cannot be written to)
export PYTHONDONTWRITEBYTECODE=1
#  Only what is inside the AppImage: not the user's site-packages, nor
#  another Python's settings
export PYTHONNOUSERSITE=1
unset PYTHONPATH PYTHONHOME PYTHONSTARTUP VIRTUAL_ENV
exec "$PYTHON" -m py_tuner "$@"
"""


def say(text: str):
    print(text, file=sys.stderr, flush=True)


def name() -> str:
    return f"{APP_ID}-{VERSION}-{ARCH}.AppImage"


def cache_dir() -> Path:
    base = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    path = base / "py-tuner-build"
    path.mkdir(parents=True, exist_ok=True)
    return path


def download(url: str, path: Path) -> Path:
    """Download URL into PATH (unless it is there already)."""
    if not path.is_file():
        say(f"Downloading {url} ...")
        tmp = path.with_name(path.name + ".tmp")
        with urllib.request.urlopen(url, timeout=120) as r, open(tmp, "wb") as f:
            shutil.copyfileobj(r, f)
        os.replace(tmp, path)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def python_appimage(version: str) -> Path:
    """The Python AppImage of VERSION, for the newest manylinux there is one for."""
    url = PYTHON_RELEASES.format(version=version)
    request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(request, timeout=60) as r:
        assets = json.load(r)["assets"]
    tag = "cp" + version.replace(".", "")
    for manylinux in MANYLINUX:
        end = f"-{tag}-{tag}-{manylinux}_{ARCH}.AppImage"  # (not the free-threaded cp3XXt)
        found = [a["browser_download_url"] for a in assets if a["name"].endswith(end)]
        if found:
            return download(found[0], cache_dir() / found[0].rsplit("/", 1)[1])
    raise OSError(f"there is no Python {version} AppImage at {url}")


def wheel(folder: Path) -> Path:
    """The program's wheel, made with uv build."""
    if not shutil.which("uv"):
        raise OSError("uv is needed to make the wheel (https://docs.astral.sh/uv/)")
    subprocess.run(["uv", "build", "--wheel", "--out-dir", str(folder)], cwd=ROOT, check=True,
                   stdout=subprocess.DEVNULL)
    found = sorted(folder.glob(f"py_tuner-{VERSION}-*.whl"))
    if not found:
        raise OSError("uv build made no wheel")
    return found[0]


def make_appdir(appdir: Path, whl: Path, libs: Path):
    """Turn the AppDir of the Python into that of py-tuner."""
    pythons = [p for p in sorted(appdir.glob("opt/python3*/bin/python3.*")) if not p.name.endswith("-config")]
    if not pythons:
        raise OSError(f"there is no Python in {appdir}")
    python = pythons[0]
    say(f"Installing py-tuner and its dependencies into {python.relative_to(appdir)} ...")
    # Everything must go inside: pip must not see packages of the user's
    # site-packages (or another environment) as already installed.
    env = clean_env()
    subprocess.run([str(python), "-s", "-m", "pip", "install", "--isolated", "--no-cache-dir",
                    "--no-warn-script-location", "--disable-pip-version-check", "--quiet",
                    str(whl)], check=True, env=env)
    site = next(appdir.glob("opt/python3*/lib/python3.*/site-packages"))
    # PortAudio, la de tools/build-libs.py: audio.py la busca en lib/.
    lib = site / "py_tuner" / "lib"
    lib.mkdir(exist_ok=True)
    for name in LIBS:
        shutil.copy2(libs / name, lib / name)
    for rel in PRUNE:
        path = site / rel
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()
    for pattern in PRUNE_GLOBS:
        for path in site.glob(pattern):
            shutil.rmtree(path) if path.is_dir() else path.unlink()
    # Out with what makes it the Python's AppImage
    for pattern in ("AppRun", "*.desktop", "*.png", "*.svg", ".DirIcon", "usr/share/applications",
                    "usr/share/metainfo"):
        for path in appdir.glob(pattern):
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            else:
                path.unlink()
    apprun = appdir / "AppRun"
    apprun.write_text(APPRUN % {"python": python.relative_to(appdir)},
                      encoding="utf-8", newline="\n")
    apprun.chmod(0o755)
    (appdir / f"{APP_ID}.desktop").write_text(DESKTOP, encoding="utf-8", newline="\n")
    icons = ROOT / "src" / "py_tuner" / "icons" / "linux" / "hicolor"
    shutil.copy2(icons / "256x256" / "apps" / f"{APP_ID}.png", appdir / f"{APP_ID}.png")
    os.symlink(f"{APP_ID}.png", appdir / ".DirIcon")
    shutil.copytree(icons, appdir / "usr" / "share" / "icons" / "hicolor", dirs_exist_ok=True)


def clean_env(**extra) -> dict:
    """The environment without anything that would make a Python look outside its own folders."""
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("PYTHON", "PIP_", "VIRTUAL_ENV", "UV_", "CONDA"))}
    env.update(PYTHONNOUSERSITE="1", **extra)
    return env


def check_imports(appdir: Path):
    """Stop if the bundled Python can't do, on its own, what the program needs: find the pitch of a tone, draw
    the window, and find the bundled PortAudio (no sound card is needed for that)."""
    python = next(p for p in sorted(appdir.glob("opt/python3*/bin/python3.*")) if not p.name.endswith("-config"))
    code = ("import numpy, PySide6; from py_tuner import audio, pitch; from py_tuner.gui import window; "
            "t = numpy.arange(48000) / 48000; e = pitch.Detector().analyze(0.5 * numpy.sin(2 * numpy.pi * 110 * t)); "
            "assert abs(e.frequency - 110) < 0.01, e; "
            "sd = audio.sounddevice(); assert 'py_tuner' in sd._libname, sd._libname; "
            "print(numpy.__version__, PySide6.__version__, sd.get_portaudio_version()[1])")
    r = subprocess.run([str(python), "-s", "-c", code], check=False, capture_output=True, text=True,
                       env=clean_env(QT_QPA_PLATFORM="offscreen", APPDIR=str(appdir)))
    if r.returncode != 0:
        raise OSError(f"the bundled Python cannot run the program:\n{r.stderr.strip()}")
    say(f"Bundled NumPy, PySide6, PortAudio: {r.stdout.strip()} (a tone of 110 Hz found)")


def smoke_test(appimage: Path):
    """Run the AppImage as a user with nothing installed would: an empty home folder."""
    with tempfile.TemporaryDirectory() as home:
        env = clean_env(HOME=home, XDG_CONFIG_HOME=f"{home}/.config", XDG_CACHE_HOME=f"{home}/.cache",
                        XDG_DATA_HOME=f"{home}/.local/share", APPIMAGE_EXTRACT_AND_RUN="1")
        r = subprocess.run([str(appimage), "--version"], check=False, capture_output=True, text=True, env=env,
                           cwd=home)
        if r.returncode != 0 or VERSION not in r.stdout:
            raise OSError(f"the AppImage failed (--version):\n{(r.stderr or r.stdout).strip()}")
    say("The AppImage runs on its own (empty home folder): --version.")


def open_to_all(appdir: Path):
    """Let everyone read the AppDir: folders 0755, files 0644, or 0755 if they can be run."""
    for folder, dirs, names in os.walk(appdir):
        for d in dirs:
            p = Path(folder, d)
            if not p.is_symlink():
                p.chmod(0o755)
        for n in names:
            p = Path(folder, n)
            if not p.is_symlink():
                p.chmod(0o755 if p.stat().st_mode & stat.S_IXUSR else 0o644)
    appdir.chmod(0o755)


def libraries(folder: Path) -> Path:
    """The folder with the libraries of tools/build-libs.py, made now if they are not there."""
    if not all((folder / name).is_file() for name in LIBS):
        subprocess.run([sys.executable, str(ROOT / "tools" / "build-libs.py"), "-o", str(folder)], check=True)
    return folder


def bundle(output: Path, python: Path | None = None, appimagetool: Path | None = None,
           version: str = PYTHON, libs: Path = ROOT / "build" / "libs") -> Path:
    libs = libraries(libs)
    python = python or python_appimage(version)
    appimagetool = appimagetool or download(APPIMAGETOOL, cache_dir() / Path(APPIMAGETOOL).name)
    path = output / name()
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        subprocess.run([str(python.resolve()), "--appimage-extract"], cwd=tmp, check=True,
                       stdout=subprocess.DEVNULL)
        appdir = tmp / "squashfs-root"
        make_appdir(appdir, wheel(tmp / "wheel"), libs)
        check_imports(appdir)
        open_to_all(appdir)
        # (without FUSE, as in a container, the tool runs extracted)
        env = dict(os.environ, ARCH=ARCH, APPIMAGE_EXTRACT_AND_RUN="1")
        tmp_out = path.with_name(path.name + ".tmp")
        subprocess.run([str(appimagetool.resolve()), "--no-appstream", "--comp", "zstd", str(appdir),
                        str(tmp_out)], check=True, env=env, stdout=subprocess.DEVNULL)
    os.replace(tmp_out, path)
    smoke_test(path)
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(prog="tools/bundle-appimage.py",
                                     description=f"Make an AppImage of py-tuner: {name()}, with a Python of "
                                                 "its own.")
    parser.add_argument("-o", "--output", type=Path, default=None,
                        help="the folder to write it in (default: build/release/)")
    parser.add_argument("--python", type=Path, metavar="APPIMAGE",
                        help="the Python AppImage to use (default: one of python-appimage, downloaded)")
    parser.add_argument("--python-version", default=PYTHON, metavar="VERSION",
                        help=f"the version of Python to download (default: {PYTHON})")
    parser.add_argument("--appimagetool", type=Path, metavar="APPIMAGE",
                        help="the appimagetool to use (default: downloaded)")
    args = parser.parse_args(argv)
    if not sys.platform.startswith("linux"):
        sys.exit("bundle-appimage.py: AppImages are made on Linux")
    output = (args.output or DIST).resolve()  # (la prueba final corre la AppImage desde otra carpeta)
    output.mkdir(parents=True, exist_ok=True)
    try:
        path = bundle(output, args.python, args.appimagetool, args.python_version)
    except (OSError, subprocess.CalledProcessError, ValueError, KeyError, StopIteration) as e:
        sys.exit(f"bundle-appimage.py: {e}")
    print(f"Wrote {path} ({path.stat().st_size / 1e6:.1f} MB).")


if __name__ == "__main__":
    main()
