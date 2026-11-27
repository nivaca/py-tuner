"""El afinador completo: la nota o cuerda de referencia, los cents, y el hilo de análisis."""

from __future__ import annotations

import time

import numpy as np
import pytest
from conftest import RATE, string

from py_tuner import audio, notes
from py_tuner.settings import Settings
from py_tuner.tuner import LiveTuner, Tuner


def detuned(midi: int, c: float, a4: float = 440.0) -> float:
    return notes.frequency(midi, a4) * 2 ** (c / 1200)


def last(tuner: Tuner, x: np.ndarray):
    return tuner.analyze_all(x)[-1]


@pytest.mark.parametrize(("instrument", "note", "c"), [
    ("guitar", "E2", +3.0), ("guitar", "B3", -12.5), ("bass", "E1", -0.4), ("bass", "G2", +7.0),
    ("double-bass", "A1", +1.5), ("violin", "G3", -2.25), ("violin", "E5", +0.6),
])
def test_strings_and_cents(instrument, note, c):
    s = Settings(instrument=instrument, tuning="")
    tuner = Tuner(s, RATE)
    midi = notes.parse(note)
    r = last(tuner, string(detuned(midi, c), seconds=1.5))
    assert r.active
    assert r.target_midi == midi
    assert r.string == [notes.parse(x) for x in s.instrument_preset().tunings[0].strings].index(midi)
    assert r.cents == pytest.approx(c, abs=0.05)
    assert r.in_tune == (abs(c) <= s.tolerance)


def test_reference_a4():
    # El mismo sonido, medido contra La 440 y contra La 442.
    x = string(220.0, seconds=1.2)
    r440 = last(Tuner(Settings(instrument="chromatic"), RATE), x)
    r442 = last(Tuner(Settings(instrument="chromatic", a4=442.0), RATE), x)
    assert r440.cents == pytest.approx(0.0, abs=0.05)
    assert r442.cents == pytest.approx(1200 * np.log2(220 / 221), abs=0.05)
    assert r442.target_frequency == pytest.approx(221.0)


def test_chromatic_finds_any_note():
    tuner = Tuner(Settings(instrument="chromatic"), RATE)
    r = last(tuner, string(detuned(notes.parse("C#3"), -20), seconds=1.2))
    assert r.target_midi == notes.parse("C#3")
    assert r.string is None
    assert r.cents == pytest.approx(-20, abs=0.05)


def test_locked_string():
    # Con la sexta cuerda fija, un La 110 se mide contra el Mi 82: +500 cents.
    tuner = Tuner(Settings(instrument="guitar", string=0), RATE)
    r = last(tuner, string(110.0, seconds=1.2))
    assert r.string == 0
    assert r.cents == pytest.approx(500, abs=0.1)


def test_auto_string_picks_the_nearest():
    tuner = Tuner(Settings(instrument="guitar"), RATE)
    # un Re 3 muy bajo (70 cents) sigue siendo la cuarta cuerda
    r = last(tuner, string(detuned(notes.parse("D3"), -70), seconds=1.2))
    assert r.string == 2


def test_alternate_tuning():
    tuner = Tuner(Settings(instrument="guitar", tuning="Drop D"), RATE)
    r = last(tuner, string(detuned(notes.parse("D2"), 1.0), seconds=1.5))
    assert (r.target_midi, r.string) == (notes.parse("D2"), 0)


def test_silence_reading():
    tuner = Tuner(Settings(), RATE)
    r = last(tuner, np.zeros(RATE))
    assert not r.active
    assert r.level == float("-inf")


def test_reconfigure_keeps_history_unless_the_range_changes():
    tuner = Tuner(Settings(), RATE)
    tuner.analyze_all(string(110.0, seconds=0.6))
    assert tuner.stabilizer.reading() is not None
    tuner.configure(Settings(tolerance=3.0))
    assert tuner.stabilizer.reading() is not None
    tuner.configure(Settings(instrument="violin", tuning=""))
    assert tuner.stabilizer.reading() is None


class FakeSource(audio.Source):
    """A source fed by the test."""

    def __init__(self) -> None:
        self.rate = RATE
        self.buffer = audio.RingBuffer(4 * RATE)
        self.started = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.started = False


def test_live_tuner_thread():
    src = FakeSource()
    live = LiveTuner(Settings(instrument="bass"), src)
    live.start()
    try:
        assert src.started
        x = string(notes.frequency(notes.parse("A1")), seconds=1.5)
        for i in range(0, len(x), 1200):
            src.buffer.write(x[i:i + 1200])
            time.sleep(0.005)
        deadline = time.monotonic() + 3
        while not live.reading.active and time.monotonic() < deadline:
            time.sleep(0.02)
        r = live.reading
        assert r.active and r.target_midi == notes.parse("A1")
        assert abs(r.cents) < 0.1
        live.configure(Settings(instrument="bass", a4=441.0))
        assert live.settings.a4 == 441.0
    finally:
        live.stop()
    assert not src.started
    assert live.error is None
