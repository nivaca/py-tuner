"""El tono de referencia: una nota que suena por la salida de sonido, para afinar de oído.

Como la orden que da un tono de pianito (Axel Stevens). El tono no es un seno puro sino una cuerda pulsada
sintética, unos pocos armónicos que se apagan, que se compara mejor de oído con un instrumento de cuerda. Suena
a la frecuencia exacta del objetivo: el La de referencia, la desviación propia de la nota y, con cejilla, la
cuerda pisada.
"""

from __future__ import annotations

import numpy as np

RATE = 48000
# La subida y la bajada del principio y el final (segundos), para que no chasquee
FADE = 0.005


def pluck(frequency: float, seconds: float = 3.0, rate: int = RATE, volume: float = 0.3) -> np.ndarray:
    """A plucked-string tone of FREQUENCY Hz, SECONDS long, at most VOLUME (0..1), as float32 samples."""
    t = np.arange(int(seconds * rate)) / rate
    x = np.zeros_like(t)
    for n in range(1, 9):
        fn = n * frequency
        if fn > 0.45 * rate:
            break
        # los armónicos altos, más débiles y más breves
        x += (1 / n) * np.exp(-(0.6 + 0.4 * n) * t) * np.sin(2 * np.pi * fn * t)
    edge = int(FADE * rate)
    if edge and len(x) > 2 * edge:
        ramp = np.linspace(0.0, 1.0, edge)
        x[:edge] *= ramp
        x[-edge:] *= ramp[::-1]
    peak = np.max(np.abs(x))
    return (volume * x / peak if peak > 0 else x).astype(np.float32)


def play(frequency: float, seconds: float = 3.0, wait: bool = False) -> None:
    """Plays the tone through the default output (sounddevice, with the package's PortAudio if it has one); WAIT
    for it to end, or return at once. Raises the error of sounddevice if there is no output."""
    from .audio import sounddevice

    sd = sounddevice()
    sd.play(pluck(frequency, seconds), RATE)
    if wait:
        sd.wait()


def stop() -> None:
    """Stops a tone that is playing."""
    from .audio import sounddevice

    try:
        sounddevice().stop()
    except Exception:  # noqa: BLE001 (sin salida, no hay nada que parar)
        pass
