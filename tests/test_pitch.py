"""La precisión del detector, medida con cuerdas sintéticas de frecuencia conocida."""

from __future__ import annotations

import numpy as np
import pytest
from conftest import RATE, cents, string

from py_tuner import pitch
from py_tuner.pitch import Detector

# (nombre, primer parcial en Hz, inarmonicidad B): las cuerdas al aire de los
# cuatro instrumentos, de la más grave del bajo de cinco a la más aguda del violín.
STRINGS = [
    ("B0 bass", 30.868, 8e-5), ("E1 bass", 41.203, 5e-5), ("A1 bass", 55.0, 5e-5),
    ("E2 guitar", 82.407, 1e-4), ("A2 guitar", 110.0, 1e-4), ("D3 guitar", 146.832, 1e-4),
    ("G3 violin", 195.998, 2e-5), ("B3 guitar", 246.942, 2e-4), ("E4 guitar", 329.628, 3e-4),
    ("A4 violin", 440.0, 5e-5), ("E5 violin", 659.255, 5e-5),
]


def errors(x: np.ndarray, f1: float, det: Detector, hop: int = 2400) -> np.ndarray:
    """The error (cents) of every frame through X; NaN where nothing was found."""
    out = []
    for end in range(det.history, len(x) + 1, hop):
        e = det.analyze(x[end - det.history:end])
        out.append(cents(e.frequency, f1) if e.found else np.nan)
    return np.array(out)


@pytest.mark.parametrize(("label", "f1", "b"), STRINGS, ids=[s[0] for s in STRINGS])
def test_open_strings_within_a_tenth_of_a_cent(label, f1, b):
    # A 40 dB de relación señal/ruido, cada cuadro por sí solo cae a menos de 0,1 cent.
    det = Detector(rate=RATE)
    err = errors(string(f1, seconds=1.2, b=b, seed=int(f1)), f1, det)
    assert not np.isnan(err).any()
    assert np.max(np.abs(err)) < 0.1, err


@pytest.mark.parametrize(("label", "f1", "b"), STRINGS[::2], ids=[s[0] for s in STRINGS[::2]])
def test_noisy_strings_are_unbiased(label, f1, b):
    # With noise only 20 dB down, single frames scatter, but their mean stays put.
    det = Detector(rate=RATE)
    err = errors(string(f1, seconds=3.0, b=b, snr_db=20, decay=0.2, seed=7), f1, det)
    assert not np.isnan(err).any()
    assert abs(np.mean(err)) < 0.1
    assert np.std(err) < 0.4


@pytest.mark.parametrize("f1", [41.203, 82.407, 196.0])
def test_weak_fundamental(f1):
    # Un micrófono pequeño apenas recoge la fundamental de una cuerda grave:
    # la frecuencia sale de los armónicos y del ajuste de la inarmonicidad.
    det = Detector(rate=RATE)
    err = errors(string(f1, seconds=1.2, fundamental=0.02), f1, det)
    assert np.max(np.abs(err)) < 0.1


def test_missing_fundamental():
    det = Detector(rate=RATE)
    f1 = 55.0
    err = errors(string(f1, seconds=1.2, fundamental=0.0, b=0.0), f1, det)
    assert not np.isnan(err).any()
    assert np.max(np.abs(err)) < 0.2


def test_inharmonicity_is_fitted_and_does_not_bias():
    # A strongly inharmonic string: the upper partials are many cents sharp of n·f1.
    det = Detector(rate=RATE)
    f1, b = 82.407, 5e-4
    x = string(f1, seconds=1.2, b=b)
    e = det.analyze(x[-det.history:])
    assert abs(cents(e.frequency, f1)) < 0.1
    assert e.inharmonicity == pytest.approx(b, rel=0.15)
    assert e.harmonics >= 8


def test_strong_second_harmonic_is_not_an_octave_error():
    t = np.arange(RATE) / RATE
    f1 = 110.0
    x = 0.2 * np.sin(2 * np.pi * f1 * t) + 0.8 * np.sin(2 * np.pi * 2 * f1 * t + 1.0) \
        + 0.3 * np.sin(2 * np.pi * 3 * f1 * t)
    det = Detector(rate=RATE)
    e = det.analyze(x)
    assert abs(cents(e.frequency, f1)) < 0.05


def test_pure_sine_is_exact():
    t = np.arange(RATE) / RATE
    for f in (31.0, 100.0, 440.0 * 2 ** (0.37 / 1200), 1000.0):
        e = Detector(rate=RATE, fmax=1500).analyze(0.5 * np.sin(2 * np.pi * f * t + 0.3))
        assert abs(cents(e.frequency, f)) < 0.01, f


def test_other_sample_rates():
    for rate in (44100, 96000):
        f1 = 110.0
        det = Detector(rate=rate)
        x = string(f1, seconds=1.0, rate=rate)
        e = det.analyze(x[-det.history:])
        assert abs(cents(e.frequency, f1)) < 0.1


def test_silence_and_quiet_sounds_have_no_pitch():
    det = Detector(rate=RATE)
    assert not det.analyze(np.zeros(det.history)).found
    assert det.analyze(np.zeros(det.history)).level == float("-inf")
    quiet = 1e-4 * string(110.0, snr_db=None)  # -86 dBFS
    assert not det.analyze(quiet[-det.history:]).found
    assert not det.analyze(np.array([])).found


def test_noise_has_no_pitch():
    rng = np.random.default_rng(5)
    det = Detector(rate=RATE)
    found = [det.analyze(0.1 * rng.normal(size=det.history)).found for _ in range(10)]
    assert sum(found) == 0


def test_out_of_range_is_not_found():
    # Un La 440 cuando el margen acaba en 300 Hz no debe verse como otra nota.
    det = Detector(rate=RATE, fmin=27.5, fmax=300.0)
    t = np.arange(RATE) / RATE
    e = det.analyze(0.5 * np.sin(2 * np.pi * 440 * t))
    assert not e.found or abs(cents(e.frequency, 220.0)) < 1  # at most the octave below, never something else


def test_phasors_match_exp():
    f = np.array([41.2, 523.3, 4000.0])
    n = 5000
    t = (np.arange(n) - (n - 1) / 2) / RATE
    assert np.max(np.abs(pitch._phasors(f, n, RATE) - np.exp(-2j * np.pi * np.outer(f, t)))) < 1e-11


def test_nsdf_of_sine_peaks_at_the_period():
    t = np.arange(4800) / RATE
    x = np.sin(2 * np.pi * 100 * t)
    n = pitch.nsdf(x, 600)
    assert n[0] == pytest.approx(1.0)
    assert int(np.argmax(n[100:])) + 100 == 480


def test_level_db():
    assert pitch.level_db(np.ones(100)) == pytest.approx(0.0)
    assert pitch.level_db(np.full(100, 0.1)) == pytest.approx(-20.0)
    assert pitch.level_db(np.zeros(10)) == float("-inf")


def test_frame_sizes():
    det = Detector(rate=48000, fmin=40, periods=16)
    assert det.fine_size(1000) == pitch.MIN_FINE
    assert det.fine_size(40) == 19200
    assert det.history >= det.coarse_size
