"""Lo común de las pruebas: cuerdas sintéticas de frecuencia conocida, archivos WAV
y una carpeta de configuración propia para no tocar la del usuario."""

from __future__ import annotations

import os
import wave

import numpy as np
import pytest

# Las ventanas de las pruebas se dibujan fuera de la pantalla, y la interfaz está en inglés, sea cual sea el
# idioma del sistema (también en los procesos que las pruebas lanzan).
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LANGUAGE"] = "en"

RATE = 48000


def string(f1: float, seconds: float = 1.0, rate: int = RATE, b: float = 1e-4, harmonics: int = 20,
           fundamental: float = 1.0, snr_db: float | None = 40.0, decay: float = 0.5, seed: int = 0,
           attack: bool = False) -> np.ndarray:
    """A plucked-string tone whose FIRST PARTIAL is exactly F1 Hz.

    Partials at n·f0·√(1+B·n²) with amplitude 1/n (the first scaled by
    FUNDAMENTAL), each decaying a little faster than the one below, random
    phases, and white noise SNR_DB below the signal (None: no noise).
    """
    rng = np.random.default_rng(seed)
    t = np.arange(int(seconds * rate)) / rate
    f0 = f1 / np.sqrt(1 + b)
    x = np.zeros_like(t)
    for n in range(1, harmonics + 1):
        fn = n * f0 * np.sqrt(1 + b * n * n)
        if fn > 0.45 * rate:
            break
        a = (fundamental if n == 1 else 1.0) / n
        x += a * np.exp(-decay * np.sqrt(n) * t) * np.sin(2 * np.pi * fn * t + rng.uniform(0, 2 * np.pi))
    if attack:
        x *= np.minimum(1.0, t * 200)
    x *= 0.5 / np.max(np.abs(x))
    if snr_db is not None:
        power = np.mean(x * x) / 10 ** (snr_db / 10)
        x += rng.normal(0, np.sqrt(power), len(x))
    return x


def cents(f: float, ref: float) -> float:
    return 1200 * np.log2(f / ref)


def write_wav(path, samples: np.ndarray, rate: int = RATE, width: int = 2, channels: int = 1) -> None:
    """SAMPLES (-1..1) as a PCM WAV of WIDTH bytes per sample, copied to CHANNELS channels."""
    x = np.clip(np.asarray(samples, dtype=np.float64), -1, 1 - 1e-9)
    frames = np.repeat(x[:, None], channels, axis=1).reshape(-1)
    if width == 1:
        raw = (frames * 128 + 128).astype(np.uint8).tobytes()
    elif width == 2:
        raw = (frames * 32768).astype("<i2").tobytes()
    elif width == 3:
        v = (frames * (1 << 23)).astype(np.int32)
        b = v.astype("<i4").view(np.uint8).reshape(-1, 4)[:, :3]
        raw = b.tobytes()
    else:
        raw = (frames * 2147483648.0).astype("<i4").tobytes()
    with wave.open(str(path), "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(width)
        w.setframerate(rate)
        w.writeframes(raw)


@pytest.fixture(autouse=True)
def config_home(tmp_path, monkeypatch):
    """Every test gets its own empty configuration folder."""
    home = tmp_path / "config"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home))
    return home
