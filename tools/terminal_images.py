#!/usr/bin/env python3
"""Hace las imágenes de la interfaz de terminal y de la línea de órdenes, en inglés y en español:

    uv run python tools/terminal_images.py

(tools/manual_images.py la llama también.) Escribe docs/img/tui_IDIOMA.png y docs/img/cli_IDIOMA.png, que usan los
README y los manuales. Las dos corren de verdad, sobre una grabación sintética de seis cuerdas de guitarra
desafinadas en cantidades conocidas: la interfaz de terminal en una pseudoterminal de 80 × 26, cuya pantalla lee pyte
(un emulador de terminal, de las dependencias de desarrollo), y la línea de órdenes como un proceso más, del que se
toma lo que escribe. Luego Qt pinta cada celda con su color, como lo haría una terminal oscura. La configuración del
usuario no se lee ni se escribe (XDG_CONFIG_HOME apunta a una carpeta temporal).
"""

from __future__ import annotations

import fcntl
import os
import pty
import select
import struct
import subprocess
import sys
import tempfile
import termios
import time
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "img"
RATE = 48000
COLS, ROWS = 80, 26

# The colours of a dark terminal (the eight of ANSI, as most themes draw them)
BACKGROUND = "#1e2228"
FOREGROUND = "#d8dee9"
COLOURS = {"default": FOREGROUND, "black": "#3b4252", "red": "#e06c75", "green": "#98c379", "yellow": "#e5c07b",
           "blue": "#61afef", "magenta": "#c678dd", "cyan": "#56b6c2", "white": "#e5e9f0"}
PROMPT = "#61afef"


def strings_wav(path: Path) -> None:
    """Six plucked guitar strings, each detuned by a known amount (+3, -7.5, 0, +0.4, -1.2 and +12 cents)."""
    rng = np.random.default_rng(3)
    parts = []
    for f, c in ((82.407, 3.0), (110.0, -7.5), (146.832, 0.0), (195.998, 0.4), (246.942, -1.2), (329.628, 12.0)):
        f1 = f * 2 ** (c / 1200)
        t = np.arange(int(1.5 * RATE)) / RATE
        b = 1e-4
        f0 = f1 / np.sqrt(1 + b)
        x = np.zeros_like(t)
        for n in range(1, 25):
            fn = n * f0 * np.sqrt(1 + b * n * n)
            if fn > 20000:
                break
            x += (1 / n) * np.exp(-(0.3 + 0.1 * n) * t) * np.sin(2 * np.pi * fn * t + rng.uniform(0, 6))
        parts += [x * np.minimum(1, t * 200), np.zeros(RATE // 4)]
    x = np.concatenate(parts)
    x = 0.5 * x / np.abs(x).max() + rng.normal(0, 0.002, len(x))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())


def tui_screen(wav: Path, lang: str, env: dict, seconds: float):
    """The screen of py-tuner tui, playing WAV, after SECONDS: a pyte.Screen."""
    import pyte

    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", ROWS, COLS, 0, 0))
    proc = subprocess.Popen([sys.executable, "-m", "py_tuner", "tui", "--file", str(wav), "-i", "guitar",
                             "--language", lang], stdin=slave, stdout=slave, stderr=slave,
                            env={**env, "TERM": "xterm-256color"})
    os.close(slave)
    screen = pyte.Screen(COLS, ROWS)
    stream = pyte.ByteStream(screen)
    end = time.monotonic() + seconds
    try:
        while time.monotonic() < end:
            ready, _, _ = select.select([master], [], [], 0.05)
            if ready:
                stream.feed(os.read(master, 65536))
        os.write(master, b"q")
        proc.wait(timeout=10)
    finally:
        if proc.poll() is None:
            proc.kill()
        os.close(master)
    return screen


def cells_of_screen(screen) -> list[list[tuple[str, str, bool]]]:
    """[[(character, colour, bold), ...] per row] of a pyte screen (reverse video as a light cell)."""
    rows = []
    for y in range(screen.lines):
        row = []
        line = screen.buffer[y]
        for x in range(screen.columns):
            ch = line[x]
            colour = COLOURS.get(ch.fg, FOREGROUND)
            if ch.reverse:
                # (la cuerda de comparación: invertida, como la muestra la terminal)
                row.append((ch.data, "reverse", ch.bold))
            else:
                row.append((ch.data, colour, ch.bold))
        rows.append(row)
    return rows


def cells_of_text(lines: list[tuple[str, str]]) -> list[list[tuple[str, str, bool]]]:
    """The cells of plain LINES, each (text, colour)."""
    return [[(ch, colour, False) for ch in text] for text, colour in lines]


def paint(rows: list[list[tuple[str, str, bool]]], path: Path, columns: int) -> None:
    """ROWS drawn as a terminal window would show them, into PATH."""
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QColor, QFont, QFontMetricsF, QImage, QPainter, QPainterPath

    font = QFont("DejaVu Sans Mono")
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.setPixelSize(17)
    bold = QFont(font)
    bold.setBold(True)
    metrics = QFontMetricsF(font)
    cw, ch = metrics.horizontalAdvance("M"), metrics.lineSpacing()
    pad, bar = 18.0, 30.0
    width, height = int(2 * pad + columns * cw), int(bar + 2 * pad + len(rows) * ch)
    img = QImage(width, height, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    frame = QPainterPath()
    frame.addRoundedRect(QRectF(0, 0, width, height), 10, 10)
    p.fillPath(frame, QColor(BACKGROUND))
    # la barra de la ventana, con sus tres botones
    p.fillRect(QRectF(0, 10, width, bar - 10), QColor("#2b3038"))
    top = QPainterPath()
    top.addRoundedRect(QRectF(0, 0, width, bar), 10, 10)
    p.fillPath(top, QColor("#2b3038"))
    for i, colour in enumerate(("#e06c75", "#e5c07b", "#98c379")):
        p.setBrush(QColor(colour))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(18 + 20 * i, bar / 2), 6, 6)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, False)

    def cell(x: int, y: int) -> QRectF:
        # (bordes en píxeles enteros: dos celdas vecinas se tocan sin rendija)
        left, right = round(pad + x * cw), round(pad + (x + 1) * cw)
        top_, bottom = round(bar + pad + y * ch), round(bar + pad + (y + 1) * ch)
        return QRectF(left, top_, right - left, bottom - top_)

    for y, row in enumerate(rows):
        base = bar + pad + y * ch
        for x, (text, colour, strong) in enumerate(row):
            if not text.strip() and colour != "reverse":
                continue
            left = pad + x * cw
            if colour == "reverse":
                p.fillRect(cell(x, y), QColor(FOREGROUND))
                colour = BACKGROUND
            if text == "█":
                # (los bloques llenos, como celdas pintadas)
                p.fillRect(cell(x, y), QColor(colour))
                continue
            p.setFont(bold if strong else font)
            p.setPen(QColor(colour))
            p.drawText(QPointF(left, base + metrics.ascent()), text)
    p.end()
    img.save(str(path))
    print(f"Wrote {path.relative_to(ROOT)}")


def cli_lines(wav: Path, lang: str, env: dict) -> list[tuple[str, str]]:
    """Two runs of the command line, as typed and as answered: a recording analysed note by note, and the first
    steady reading of the recording played as if it came from the sound card. (In a terminal, that reading is one
    line that rewrites itself: only its last state is shown, after the header.)"""
    lines: list[tuple[str, str]] = []
    runs = [["cli", "--file", wav.name, "-i", "guitar"],
            ["cli", "--file", wav.name, "-i", "guitar", "--realtime", "--once"]]
    for args in runs:
        done = subprocess.run([sys.executable, "-m", "py_tuner", *args, "--language", lang], cwd=wav.parent,
                              env=env, capture_output=True, text=True, timeout=60)
        lines.append(("$ py-tuner " + " ".join(args), PROMPT))
        out = done.stdout.rstrip("\n").splitlines()
        if "--once" in args:
            out = [out[0], out[-1]]
        for text in out:
            colour = COLOURS["green"] if text.rstrip().endswith(" OK") or " OK  " in text else FOREGROUND
            lines.append((text.split("\r")[-1], colour))
        lines.append(("", FOREGROUND))
    return lines[:-1]


def main() -> int:
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])  # noqa: F841 (Qt pinta con una aplicación)
    with tempfile.TemporaryDirectory(prefix="py-tuner-terminal-") as tmp:
        wav = Path(tmp) / "strings.wav"
        strings_wav(wav)
        env = {k: v for k, v in os.environ.items() if not k.startswith(("LANG", "LC_"))}
        env.update(XDG_CONFIG_HOME=str(Path(tmp) / "config"), PYTHONPATH=str(ROOT / "src"))
        for lang in ("en", "es"):
            # (a los 6,2 s suena la cuarta cuerda, el Sol, casi afinada: la terminal la muestra en verde)
            screen = tui_screen(wav, lang, {**env, "LANGUAGE": lang}, 6.2)
            paint(cells_of_screen(screen), OUT / f"tui_{lang}.png", COLS)
            lines = cli_lines(wav, lang, {**env, "LANGUAGE": lang})
            paint(cells_of_text(lines), OUT / f"cli_{lang}.png", max(len(t) for t, _ in lines) + 1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
