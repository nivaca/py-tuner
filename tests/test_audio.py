"""La entrada de sonido: el búfer circular, los archivos WAV y su reproducción al ritmo del reloj."""

from __future__ import annotations

import threading
import time

import numpy as np
import pytest
from conftest import write_wav

from py_tuner import audio


def test_ring_buffer_wraps():
    rb = audio.RingBuffer(10)
    rb.write(np.arange(4))
    assert list(rb.latest(10)) == [0, 1, 2, 3]
    rb.write(np.arange(4, 13))
    assert list(rb.latest(10)) == list(range(3, 13))
    assert list(rb.latest(3)) == [10, 11, 12]
    rb.write(np.arange(100, 125))
    assert list(rb.latest(10)) == list(range(115, 125))
    assert rb.total == 38


def test_ring_buffer_threads():
    rb = audio.RingBuffer(1000)
    stop = threading.Event()

    def writer():
        k = 0
        while not stop.is_set():
            rb.write(np.arange(k, k + 37))
            k += 37

    t = threading.Thread(target=writer)
    t.start()
    try:
        for _ in range(200):
            x = rb.latest(500)
            # siempre una secuencia continua, nunca dos trozos mezclados
            assert len(x) == 0 or np.all(np.diff(x) == 1)
    finally:
        stop.set()
        t.join()


def test_to_mono():
    frames = np.array([[1.0, 3.0], [2.0, 4.0]])
    assert list(audio.to_mono(frames)) == [2.0, 3.0]
    assert list(audio.to_mono(frames, "2")) == [3.0, 4.0]
    assert list(audio.to_mono(frames, "9")) == [3.0, 4.0]
    assert list(audio.to_mono(np.array([1.0, 2.0]))) == [1.0, 2.0]


@pytest.mark.parametrize("width", [1, 2, 3, 4])
def test_read_wav_widths(tmp_path, width):
    x = 0.5 * np.sin(np.linspace(0, 20, 1000))
    write_wav(tmp_path / "a.wav", x, rate=44100, width=width, channels=2)
    rate, y = audio.read_wav(tmp_path / "a.wav")
    assert rate == 44100
    assert len(y) == 1000
    assert np.max(np.abs(y - x)) < (0.01 if width == 1 else 1e-4)


def test_file_source_plays_in_real_time(tmp_path):
    write_wav(tmp_path / "a.wav", np.zeros(48000), rate=48000)
    src = audio.FileSource(tmp_path / "a.wav", seconds=2)
    src.start()
    try:
        time.sleep(0.3)
    finally:
        src.stop()
    # unos 0,3 s de muestras, con holgura para una máquina cargada
    assert 0.15 * 48000 < src.buffer.total < 0.8 * 48000


def test_input_devices_never_raises():
    assert isinstance(audio.input_devices(), list)


def test_ring_buffer_window_by_absolute_position():
    rb = audio.RingBuffer(10)
    rb.write(np.arange(7))
    assert list(rb.window(5, 3)) == [2, 3, 4]
    rb.write(np.arange(7, 15))  # 15 escritas, quedan 5..14
    assert list(rb.window(12, 4)) == [8, 9, 10, 11]
    assert list(rb.window(15, 20)) == list(range(5, 15))
    assert list(rb.window(8, 5)) == [5, 6, 7]  # (lo más viejo ya se pisó)
    assert len(rb.window(15, 0)) == 0
