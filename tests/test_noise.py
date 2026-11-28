"""El ruido del cuarto aprendido: se aprende sin nota, no aprende una nota, y deja pasar solo lo que lo supera."""

from __future__ import annotations

import numpy as np
from conftest import RATE, string

from py_tuner import noise
from py_tuner.noise import NoiseFloor
from py_tuner.settings import Settings
from py_tuner.tuner import Tuner


def feed(floor: NoiseFloor, level: float, pitch: bool, start: float, seconds: float, step: float = 0.025):
    t = start
    while t < start + seconds:
        floor.update(level, pitch, t)
        t += step
    return t


def test_learns_the_background_and_gates_over_it():
    f = NoiseFloor()
    assert f.gate() is None
    feed(f, -50.0, False, 0.0, 0.3)
    assert f.gate() is None  # (aún no lo conoce)
    feed(f, -50.0, False, 0.3, 1.0)
    assert f.gate() == __import__("pytest").approx(-50.0 + noise.GATE_DB, abs=0.5)


def test_a_note_is_never_learned():
    f = NoiseFloor()
    t = feed(f, -50.0, False, 0.0, 2.0)
    feed(f, -20.0, True, t, 5.0)  # una nota larga y fuerte
    assert f.floor < -49.0


def test_a_louder_room_is_caught_up_slowly():
    f = NoiseFloor()
    t = feed(f, -50.0, False, 0.0, 2.0)
    t = feed(f, -40.0, False, t, 2.0)  # 10 dB más: algo suena, el piso apenas sube
    assert f.floor < -48.0
    feed(f, -40.0, False, t, 60.0)
    assert f.floor > -41.0


def test_quiet_tones_in_a_noisy_room():
    # Un cuarto con ruido a -40 dBFS: un tono 5 dB sobre el ruido de la banda de las notas (la que mide el
    # nivel) no es nota; uno 25 dB sobre él, sí.
    rng = np.random.default_rng(0)
    room = 0.01 * rng.normal(size=2 * RATE)
    band = np.sqrt(Tuner(Settings(), RATE).detector.band_top / (RATE / 2))
    for over, heard in ((5, False), (25, True)):
        tuner = Tuner(Settings(), RATE)
        tone = string(220.0, seconds=1.5, snr_db=None, decay=0.0)
        tone *= 0.01 * band * 10 ** (over / 20) / np.sqrt(np.mean(tone ** 2))
        x = np.concatenate([room, tone + 0.01 * rng.normal(size=len(tone))])
        r = tuner.analyze_all(x)
        assert any(x.active for x in r) is heard, over
        assert r[-1].gate > -55
    # Sin aprender el ruido, el tono débil pasa (solo cuenta el nivel fijo, -60 dBFS).
    tuner = Tuner(Settings(learn_noise=False), RATE)
    tone = string(220.0, seconds=1.5, snr_db=None, decay=0.0)
    tone *= 0.01 * 10 ** (5 / 20) / np.sqrt(np.mean(tone ** 2))
    x = np.concatenate([room, tone + 0.01 * rng.normal(size=len(tone))])
    assert any(r.active for r in tuner.analyze_all(x))
