"""El tono de referencia: suena a la frecuencia pedida, sin chasquidos, sin pasarse del volumen."""

from __future__ import annotations

import numpy as np
import pytest

from py_tuner import tone
from py_tuner.pitch import Detector


def test_the_tone_has_the_pitch_asked():
    x = tone.pluck(82.407, seconds=1.5)
    assert x.dtype == np.float32 and len(x) == int(1.5 * tone.RATE)
    e = Detector(rate=tone.RATE).analyze(x[: tone.RATE])
    assert abs(1200 * np.log2(e.frequency / 82.407)) < 0.05


def test_the_tone_starts_and_ends_softly():
    x = tone.pluck(440.0, seconds=1.0, volume=0.3)
    assert np.max(np.abs(x)) == pytest.approx(0.3, rel=1e-3)
    assert abs(x[0]) < 1e-6 and abs(x[-1]) < 1e-6
