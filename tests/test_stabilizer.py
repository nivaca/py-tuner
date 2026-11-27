"""El paso de estimaciones sueltas a una lectura estable."""

from __future__ import annotations

import numpy as np
import pytest

from py_tuner.stabilizer import Stabilizer


def feed(st: Stabilizer, freqs, start: float = 0.0, step: float = 0.025):
    out = None
    for i, f in enumerate(freqs):
        out = st.push(start + i * step, f)
    return out


def test_averages_noise_down():
    rng = np.random.default_rng(1)
    f = 110.0
    noisy = f * 2 ** (rng.normal(0, 0.3, 40) / 1200)  # 0.3 cents de dispersión por cuadro
    r = feed(Stabilizer(window=0.5), noisy)
    assert abs(1200 * np.log2(r.frequency / f)) < 0.1
    assert r.count in (20, 21)  # 0,5 s de cuadros cada 25 ms, según el redondeo del borde


def test_isolated_outlier_is_ignored():
    st = Stabilizer()
    freqs = [220.0] * 10 + [440.0] + [220.0] * 5
    r = feed(st, freqs)
    assert r.frequency == pytest.approx(220.0)


def test_a_new_note_after_a_pluck_needs_two_estimates():
    st = Stabilizer(confirm=2)
    feed(st, [220.0] * 10)
    st.push(0.25, 246.94, onset=True)
    r = st.push(0.275, 246.94)
    assert r.frequency == pytest.approx(246.94)
    assert r.count == 2


def test_a_new_note_without_a_pluck_must_hold():
    # Sin ataque, otra nota tiene que durar 0,3 s (un segundo afinándose, sin pulsar de nuevo).
    st = Stabilizer(confirm=2)
    feed(st, [220.0] * 10)
    r = feed(st, [246.94] * 5, start=0.25)  # 0.1 s
    assert r.frequency == pytest.approx(220.0)
    r = feed(st, [246.94] * 12, start=0.375)  # 0.4 s in all
    assert r.frequency == pytest.approx(246.94)


def test_an_octave_without_a_pluck_waits_longer():
    st = Stabilizer(confirm=2, hold=1.0)
    feed(st, [220.0] * 10)
    r = feed(st, [110.0] * 16, start=0.25)  # 0.375 s: past the 0.3 of a note, short of the 0.6 of an octave
    assert r.frequency == pytest.approx(220.0)
    r = feed(st, [110.0] * 12, start=0.65)
    assert r.frequency == pytest.approx(110.0)


def test_a_gap_restarts_the_wait():
    st = Stabilizer(confirm=2, hold=2.0)
    feed(st, [220.0] * 10)
    t = 0.25
    for _ in range(6):  # runs of 0.1 s of another note, broken by frames without pitch
        feed(st, [246.94] * 4, start=t)
        st.push(t + 0.1, 0.0)
        t += 0.125
    assert st.centre_frequency() == pytest.approx(220.0)


def test_undertone_of_a_note_just_ended_is_suspect():
    # La cola de una nota leída una octava abajo, ya sin la nota: espera como un salto.
    st = Stabilizer(confirm=2, hold=0.2)
    feed(st, [220.0] * 10)  # hasta 0.225
    assert st.push(0.5, 0.0) is None  # la nota se apagó
    r = feed(st, [110.0] * 6, start=0.55)
    assert r is None
    # A new note from silence, after a pluck, lights at once.
    st.push(1.0, 0.0, onset=True)
    assert st.push(1.025, 329.63) is not None


def test_related():
    assert Stabilizer.related(1200) and Stabilizer.related(-1902) and Stabilizer.related(702)
    assert not Stabilizer.related(200) and not Stabilizer.related(1000)


def test_alternating_jumps_are_not_confirmed():
    st = Stabilizer(confirm=2)
    r = feed(st, [220.0] * 10 + [300.0, 400.0, 300.0 * 1.5])
    assert r.frequency == pytest.approx(220.0)


def test_hold_then_silence():
    st = Stabilizer(window=0.5, hold=0.4)
    feed(st, [110.0] * 10)  # hasta t = 0.225
    assert st.push(0.4, 0.0) is not None  # dentro de la espera: la nota sigue
    assert st.push(0.7, 0.0) is None  # pasada la espera: se apaga


def test_spread():
    st = Stabilizer(window=10)
    r = feed(st, [440.0 * 2 ** (c / 1200) for c in (-2, -1, 0, 1, 2, -1, 0, 1)])
    assert 0 < r.spread <= 1.01


def test_reset():
    st = Stabilizer()
    feed(st, [110.0] * 5)
    st.reset()
    assert st.reading() is None
