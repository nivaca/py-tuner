#!/usr/bin/env python3
"""Compila la biblioteca de sonido que lleva la AppImage:

    uv run python tools/build-libs.py [-o CARPETA]

En CARPETA (build/libs por omisión) deja libportaudio.so.2: PortAudio 19.7.0 (licencia MIT), solo con ALSA.

El RPM no la usa: Fedora tiene la suya. Pero la de Fedora pide una glibc muy nueva (la 2.38, y trae además JACK
y PipeWire), y la AppImage debe correr desde la 2.34. Así que se compila aquí, de su código (cuyo SHA-256 se
comprueba), con el compilador de C de zig (el paquete ziglang de PyPI, que uvx trae), para glibc 2.28: no
depende más que de la glibc. Solo con ALSA, que carga al correr (PA_ALSA_DYNAMIC): toda distribución la tiene,
y PipeWire y PulseAudio la atienden. Para compilarla hacen falta los encabezados de ALSA (alsa-lib-devel en
Fedora, libasound2-dev en Debian). (Tomado de py-slowdown, que compila además Rubber Band.)

Lo descargado queda en ~/.cache/py-tuner-build.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ZIG = ["uvx", "--from", "ziglang==0.17.1", "python", "-m", "ziglang"]
TARGET = "x86_64-linux-gnu.2.28"

PORTAUDIO = {
    "url": "https://files.portaudio.com/archives/pa_stable_v190700_20210406.tgz",
    "sha256": "47efbf42c77c19a05d22e627d42873e991ec0c1357219c0d74ce6a2948cb2def",
    "folder": "portaudio",
}
ALSA_HEADERS = Path("/usr/include/alsa/asoundlib.h")


def say(text: str):
    print(text, file=sys.stderr, flush=True)


def cache_dir() -> Path:
    base = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    path = base / "py-tuner-build"
    path.mkdir(parents=True, exist_ok=True)
    return path


def fetch(source: dict) -> Path:
    """The archive of SOURCE, downloaded once and checked by its SHA-256."""
    path = cache_dir() / source["url"].rsplit("/", 1)[1]
    if not path.is_file():
        say(f"Downloading {source['url']}")
        tmp = path.with_name(path.name + ".tmp")
        with urllib.request.urlopen(source["url"], timeout=120) as r, open(tmp, "wb") as f:
            shutil.copyfileobj(r, f)
        os.replace(tmp, path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != source["sha256"]:
        path.unlink()
        raise OSError(f"{path.name} is not the archive expected (SHA-256 {digest}); it was removed")
    return path


def unpack(archive: Path, into: Path, folder: str) -> Path:
    with tarfile.open(archive) as tar:
        tar.extractall(into, filter="data")
    return into / folder


def zig(*args: str, cwd: Path):
    subprocess.run([*ZIG, *args], cwd=cwd, check=True)


def build_portaudio(work: Path, out: Path) -> Path:
    if not ALSA_HEADERS.is_file():
        raise OSError("ALSA's headers are needed to build PortAudio (sudo dnf install alsa-lib-devel, or "
                      "sudo apt install libasound2-dev)")
    say("Compiling PortAudio (ALSA only)")
    source = unpack(fetch(PORTAUDIO), work, PORTAUDIO["folder"])
    # Solo los encabezados de ALSA del sistema, no toda /usr/include: los de C son los de zig, para glibc 2.28.
    headers = work / "alsa-headers"
    headers.mkdir()
    (headers / "alsa").symlink_to(ALSA_HEADERS.parent)
    files = sorted(str(p.relative_to(source)) for p in (source / "src/common").glob("*.c"))
    files += ["src/os/unix/pa_unix_hostapis.c", "src/os/unix/pa_unix_util.c", "src/hostapi/alsa/pa_linux_alsa.c"]
    target = out / "libportaudio.so.2"
    zig("cc", "-target", TARGET, "-shared", "-fPIC", "-O2", "-s", "-DNDEBUG", "-DPA_USE_ALSA=1",
        "-DPA_ALSA_DYNAMIC=1", "-DPA_LITTLE_ENDIAN", "-Iinclude", "-Isrc/common", "-Isrc/os/unix",
        f"-I{headers}", *files, "-Wl,-soname,libportaudio.so.2", "-o", str(target), "-lpthread", "-ldl", "-lm",
        cwd=source)
    return target


def check(lib: Path, symbol: str):
    """Stop unless LIB exports SYMBOL and (on Linux) needs no glibc newer than 2.28."""
    import ctypes
    import re

    if not hasattr(ctypes.CDLL(str(lib)), symbol):
        raise OSError(f"{lib.name} does not export {symbol}")
    if shutil.which("objdump") and lib.suffix != ".dylib":
        dump = subprocess.run(["objdump", "-T", str(lib)], capture_output=True, text=True, check=True).stdout
        versions = {tuple(map(int, v.split("."))) for v in re.findall(r"GLIBC_([0-9.]+)", dump)}
        if versions and max(versions) > (2, 28):
            raise OSError(f"{lib.name} needs glibc {'.'.join(map(str, max(versions)))}")


def build(out: Path) -> list[Path]:
    if not shutil.which("uvx"):
        raise OSError("uvx (of uv) is needed, to run zig's compiler (https://docs.astral.sh/uv/)")
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="py-tuner-libs-") as tmp:
        portaudio = build_portaudio(Path(tmp), out)
    check(portaudio, "Pa_Initialize")
    return [portaudio]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="tools/build-libs.py", description="Compile PortAudio for the AppImage.")
    parser.add_argument("-o", "--output", type=Path, default=ROOT / "build" / "libs",
                        help="the folder to write it in (default: build/libs)")
    args = parser.parse_args(argv)
    if not sys.platform.startswith("linux"):
        sys.exit("build-libs.py: the library of the AppImage is made on Linux")
    try:
        built = build(args.output)
    except (OSError, subprocess.CalledProcessError, tarfile.TarError) as error:
        sys.exit(f"build-libs.py: {error}")
    for path in built:
        print(f"Wrote {path} ({path.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
