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


def test_sustained_jump_is_a_new_note():
    st = Stabilizer(confirm=2)
    r = feed(st, [220.0] * 10 + [246.94] * 2)
    assert r.frequency == pytest.approx(246.94)
    assert r.count == 2


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
