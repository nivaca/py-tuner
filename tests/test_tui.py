"""La interfaz de terminal: las letras grandes, la aguja y el estroboscopio de texto, y el programa
entero en una pseudoterminal."""

from __future__ import annotations

import os
import pty
import select
import subprocess
import sys
import time

import pytest
from conftest import string, write_wav

from py_tuner import display, notes, settings, tui


def test_big_font_has_every_note_name():
    for system in notes.NAME_SYSTEMS:
        for acc in notes.ACCIDENTALS:
            for midi in range(12, 108):
                label = notes.full_name(midi, system, acc)
                rows = tui.big(label)
                assert len(rows) == 5
                # cada carácter tiene su glifo: ninguno se pierde
                assert all(ch.upper() in tui._FONT for ch in label), label


def test_needle_row():
    scale, pos = tui.needle_row(0.0, 41)
    assert len(scale) == 41 and pos == 20 and scale[20] == "┼"
    assert tui.needle_row(50.0, 41)[1] == 40
    assert tui.needle_row(-80.0, 41)[1] == 0
    assert tui.needle_row(None, 41)[1] is None


def test_wrap_keys():
    halves = ["q quit   0 A4 = 440", "i instrument   l language"]
    assert tui.wrap_keys(halves, 200) == ["q quit   0 A4 = 440   i instrument   l language"]
    assert tui.wrap_keys(halves, 30) == ["q quit   0 A4 = 440", "i instrument   l language"]
    assert tui.wrap_keys(halves, 12) == ["q quit", "0 A4 = 440", "i instrument", "l language"]


def test_strobe_row_moves_with_phase():
    a = tui.strobe_row(0.0, 16)
    b = tui.strobe_row(0.25, 16)
    assert a != b and a.count("█") == b.count("█") == 8


def test_strobe_model():
    st = display.Strobe(period=8)
    assert st.advance(0.0, 1.0) == [0.0, 0.0, 0.0]
    p = st.advance(2.0, 1.0)
    assert p == pytest.approx([2 / 8, 4 / 8, 0.0])
    st.advance(None, 5.0)
    assert st.phases == pytest.approx([2 / 8, 4 / 8, 0.0])
    st.advance(-2.0, 1.0)
    assert st.phases == pytest.approx([0.0, 0.0, 0.0])


def read_for(fd: int, seconds: float) -> bytes:
    out = b""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        r, _, _ = select.select([fd], [], [], 0.05)
        if r:
            try:
                out += os.read(fd, 65536)
            except OSError:
                break
    return out


@pytest.mark.skipif(sys.platform == "win32", reason="needs a pseudo-terminal")
def test_tui_runs_in_a_terminal(tmp_path, config_home):
    write_wav(tmp_path / "a.wav", string(notes.frequency(notes.parse("D3")) * 2 ** (-3 / 1200), seconds=4.0,
                                         decay=0.1))
    master, slave = pty.openpty()
    env = {**os.environ, "TERM": "xterm-256color", "LINES": "40", "COLUMNS": "120"}
    proc = subprocess.Popen([sys.executable, "-m", "py_tuner", "tui", "--file", str(tmp_path / "a.wav"),
                             "-i", "guitar"], stdin=slave, stdout=slave, stderr=slave, env=env, close_fds=True)
    os.close(slave)
    try:
        out = read_for(master, 2.5)
        os.write(master, b"\x1bOC\x1bOC")  # dos veces la flecha derecha (modo keypad de xterm): La + 0,2 Hz
        out += read_for(master, 0.5)
        os.write(master, b"q")
        assert proc.wait(timeout=10) == 0
    finally:
        if proc.poll() is None:
            proc.kill()
        os.close(master)
    text = out.decode("utf-8", "replace")
    assert "Guitar" in text and "D3" in text
    assert "-3.0" in text or "-3.1" in text or "-2.9" in text
    # las flechas cambiaron el La, y quedó guardado
    assert settings.load().a4 == pytest.approx(440.2)


def test_trace_rows():
    rows = tui.trace_rows([0.0, 3.0, -30.0, None, 0.5], 8, 1.0)
    assert len(rows) == 5 and all(len(r) == 8 for r in rows)
    # columnas 3..7: afinada, alta, muy baja, sin nota, afinada
    assert rows[2][3] == "•" and rows[1][4] == "•" and rows[4][5] == "•"
    assert rows[2][6] == "·" and rows[2][7] == "•"
    assert rows[0].strip() == ""


def test_needle_row_fine_scale():
    lin, _ = tui.needle_row(None, 41, "linear")
    fine, pos = tui.needle_row(2.0, 41, "fine")
    assert lin != fine and pos > 20 + round(2 / 50 * 20)  # (dos cents se ven más lejos del centro)


def test_spectrum_rows():
    from py_tuner.settings import Settings
    from conftest import RATE

    x = string(110.0, seconds=0.5, snr_db=60)
    rows = tui.spectrum_rows(x[-16384:], RATE, 60, Settings())
    assert len(rows[0]) == 60 and set(rows[0]) - set(tui.BARS + " ") == set()
    assert "A2" in rows[1]
