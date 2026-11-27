"""El estroboscopio de verdad: sus bandas se mueven tantas franjas por segundo como cents se aparta el sonido."""

from __future__ import annotations

import numpy as np
import pytest
from conftest import RATE, string

from py_tuner.strobe import Strobe


def run(strobe: Strobe, x: np.ndarray, chunk: int = 1200) -> list[list]:
    """Feeds X in chunks, as the analysis does, and returns the bands after each one."""
    out = []
    for i in range(0, len(x), chunk):
        strobe.feed(x[i:i + chunk])
        out.append(strobe.bands())
    return out


def speed(history: list[list], band: int, seconds: float) -> float:
    """Stripes per second of BAND over the second half of HISTORY."""
    half = len(history) // 2
    return (history[-1][band].position - history[half][band].position) / (seconds / 2)


@pytest.mark.parametrize("cents", [1.0, -3.0, 0.3])
def test_vernier_bands_move_one_two_four_stripes_per_cent(cents):
    f = 110.0
    st = Strobe(RATE, "vernier")
    st.set_target(f)
    x = string(f * 2 ** (cents / 1200), seconds=3.0, b=0.0, decay=0.1)
    h = run(st, x)
    for band, mult in enumerate((1, 2, 4)):
        assert speed(h, band, 3.0) == pytest.approx(cents * mult, rel=0.05, abs=0.02)
    assert all(b.alpha > 0.9 for b in h[-1])


def test_in_tune_stands_still():
    st = Strobe(RATE, "vernier")
    st.set_target(196.0)
    h = run(st, string(196.0, seconds=2.0, b=0.0, decay=0.1))
    assert abs(speed(h, 2, 2.0)) < 0.02


def test_harmonic_bands_follow_a_stiff_string():
    # Una cuerda rígida afinada: con su inarmonicidad, las tres parciales se quedan quietas; sin ella, la 3
    # corre (sus cents de más, por segundo).
    f, b = 82.41, 4e-4
    x = string(f, seconds=3.0, b=b, decay=0.1)
    st = Strobe(RATE, "harmonics")
    st.set_target(f, b)
    h = run(st, x)
    assert all(abs(speed(h, i, 3.0)) < 0.05 for i in range(3))
    naive = Strobe(RATE, "harmonics")
    naive.set_target(f, 0.0)
    h = run(naive, x)
    sharp = 1200 * np.log2(np.sqrt(1 + 9 * b) / np.sqrt(1 + b))
    assert speed(h, 2, 3.0) == pytest.approx(sharp, rel=0.1)


def test_noise_fades_the_bands():
    rng = np.random.default_rng(0)
    st = Strobe(RATE, "vernier")
    st.set_target(220.0)
    h = run(st, 0.1 * rng.normal(size=RATE))
    assert all(b.alpha < 0.3 for b in h[-1])


def test_a_new_note_starts_over_and_none_draws_nothing():
    st = Strobe(RATE)
    st.set_target(110.0)
    run(st, string(110.0 * 2 ** (5 / 1200), seconds=1.0, b=0.0))
    assert st.bands()[0].position != 0
    st.set_target(110.0 * 2 ** (10 / 1200))  # (unos cents: la misma nota, el promedio sigue)
    assert st.bands()[0].position != 0
    st.set_target(146.8)
    assert st.bands()[0].position == 0
    st.set_target(0)
    assert all(b.alpha == 0 for b in st.bands())


def test_follower_extrapolates_between_readings():
    from py_tuner.display import Follower
    from py_tuner.strobe import Band

    f = Follower()
    f.update((Band(0.0, 1.0),), 10.0)
    f.update((Band(0.1, 1.0),), 10.025)  # 4 stripes per second
    assert f.phases(10.035)[0][0] == pytest.approx(0.14)
    assert f.phases(11.0)[0][0] == pytest.approx(0.1 + 4 * Follower.LIMIT)
    f.update((), 11.0)
    assert f.phases(11.0) == []
