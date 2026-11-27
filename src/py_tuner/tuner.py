"""El afinador propiamente dicho: de las muestras a una lectura completa.

Junta el detector (pitch), el estabilizador y las notas: decide contra qué
nota o cuerda se compara el sonido y cuántos cents se aparta. Tuner trabaja
sobre muestras que se le dan (y así se prueba, o analiza un archivo);
LiveTuner lo hace solo, en un hilo aparte, sobre una fuente de sonido, y
deja la última lectura donde la ventana, la terminal o la línea de órdenes
la recogen.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

import numpy as np

from . import notes
from .audio import Source
from .pitch import Detector, Estimate
from .settings import Settings
from .stabilizer import Stabilizer

# Cada cuánto se analiza (segundos): 40 lecturas por segundo.
HOP = 0.025
# Semitones searched below the lowest string and above the highest, in an instrument's tuning
STRING_BELOW = 5
STRING_ABOVE = 7
# A pluck: the level of the newest HOP of sound this many times its envelope, which follows over ONSET_ENVELOPE_S
# (as Strobie, by Davorin Šego, finds its onsets: 1.5 over 0.3 s)
ONSET_RATIO = 1.5
ONSET_ENVELOPE_S = 0.3


@dataclass(frozen=True)
class Reading:
    """What the tuner shows at one moment.

    frequency: the steady frequency (Hz; 0.0 when there is no note).
    raw: the last frame's own estimate. target_midi, target_frequency: the note
    compared against. cents: how far frequency is from it. string: the index of
    the string compared against (None in chromatic mode). spread: the steadiness
    (cents). level: input level (dBFS). clarity: periodicity (0..1).
    in_tune: |cents| within the tolerance.
    """

    frequency: float = 0.0
    raw: float = 0.0
    target_midi: int | None = None
    target_frequency: float = 0.0
    cents: float = 0.0
    string: int | None = None
    spread: float = 0.0
    count: int = 0
    level: float = float("-inf")
    clarity: float = 0.0
    inharmonicity: float = 0.0
    harmonics: int = 0
    in_tune: bool = False
    time: float = 0.0

    @property
    def active(self) -> bool:
        return self.frequency > 0.0


class Tuner:
    """The analysis, without any sound card: feed it samples, get readings."""

    def __init__(self, settings: Settings, rate: int) -> None:
        self.rate = rate
        self.configure(settings)

    def configure(self, settings: Settings) -> None:
        """Toma la nueva configuración SETTINGS (conserva la historia si solo cambió la presentación)."""
        self.settings = settings.validated()
        s = self.settings
        self.instrument = s.instrument_preset()
        self.tuning = self.instrument.tuning(s.tuning) if self.instrument.tunings else None
        self.string_midis = self.tuning.midis if self.tuning else ()
        if self.string_midis:
            # Con cuerdas, se busca solo cerca de ellas: de una cuarta bajo la más grave (una cuerda muy floja) a
            # una quinta sobre la más aguda. Lo que queda fuera (el golpe de la pulsación, un submúltiplo de dos
            # cuerdas que resuenan) no puede pasar por una nota. Como el margen ceñido a la cuerda de pianito (Axel
            # Stevens) y de Tuneo (Braulio Ríos).
            fmin = notes.frequency(min(self.string_midis) - STRING_BELOW, s.a4)
            fmax = notes.frequency(max(self.string_midis) + STRING_ABOVE, s.a4)
        else:
            # Un poco más allá del margen del instrumento, para afinar desde una cuerda muy floja o muy tensa
            fmin = notes.frequency(self.instrument.lowest, s.a4) * 0.85
            fmax = notes.frequency(self.instrument.highest, s.a4) * 1.1
        fmax = min(fmax, 0.4 * self.rate)
        old = getattr(self, "detector", None)
        self.detector = Detector(rate=self.rate, fmin=fmin, fmax=fmax, periods=s.periods,
                                 min_level=s.min_level)
        if old is None or (old.fmin, old.fmax, old.periods) != (fmin, fmax, s.periods):
            self.stabilizer = Stabilizer(window=s.smoothing)
        self.stabilizer.window = s.smoothing

    @property
    def history(self) -> int:
        """Cuántas muestras pide analyze()."""
        return self.detector.history

    def target(self, freq: float) -> tuple[int, int | None]:
        """(nota MIDI, índice de la cuerda o None) contra la que se compara FREQ."""
        s = self.settings
        if not self.string_midis:
            return notes.nearest(freq, s.a4), None
        if s.string is not None and s.string < len(self.string_midis):
            return self.string_midis[s.string], s.string
        m = notes.midi_of(freq, s.a4)
        best = min(range(len(self.string_midis)), key=lambda i: abs(self.string_midis[i] - m))
        return self.string_midis[best], best

    def analyze(self, samples: np.ndarray, now: float) -> Reading:
        """The reading after the newest SAMPLES (their end is at time NOW, in seconds)."""
        onset = self._onset(samples, now)
        # La nota que suena orienta la elección de la octava, salvo justo después de pulsar.
        prefer = None if self.stabilizer.recent_onset(now) else self.stabilizer.centre_frequency()
        est: Estimate = self.detector.analyze(samples, prefer)
        smooth = self.stabilizer.push(now, est.frequency, onset)
        if smooth is None:
            return Reading(raw=est.frequency, level=est.level, clarity=est.clarity, time=now)
        midi, string = self.target(smooth.frequency)
        target = notes.frequency(midi, self.settings.a4)
        c = notes.cents(smooth.frequency, target)
        return Reading(frequency=smooth.frequency, raw=est.frequency, target_midi=midi,
                       target_frequency=target, cents=c, string=string, spread=smooth.spread, count=smooth.count,
                       level=est.level, clarity=est.clarity, inharmonicity=est.inharmonicity,
                       harmonics=est.harmonics, in_tune=abs(c) <= self.settings.tolerance, time=now)

    def _onset(self, samples: np.ndarray, now: float) -> bool:
        """Whether the newest samples are a pluck: their level jumps ONSET_RATIO over the envelope."""
        n = max(1, int(HOP * self.rate))
        newest = np.asarray(samples[-n:], dtype=np.float64)
        amp = float(np.sqrt(np.mean(newest * newest))) if len(newest) else 0.0
        last = getattr(self, "_env_time", None)
        env = getattr(self, "_envelope", 0.0)
        dt = HOP if last is None else max(0.0, now - last)
        onset = amp > ONSET_RATIO * env and 20 * np.log10(amp + 1e-12) > self.settings.min_level
        # la envolvente sigue al nivel, más despacio cuanto más largo ONSET_ENVELOPE_S
        k = 1 - np.exp(-dt / ONSET_ENVELOPE_S) if dt > 0 else 1.0
        self._envelope = env + (amp - env) * k
        self._env_time = now
        return bool(onset)

    def analyze_all(self, samples: np.ndarray, hop: float = HOP) -> list[Reading]:
        """Lecturas cada HOP segundos a lo largo de una grabación entera."""
        step = max(1, int(hop * self.rate))
        out = []
        for end in range(step, len(samples) + 1, step):
            start = max(0, end - self.history)
            out.append(self.analyze(samples[start:end], end / self.rate))
        return out


class LiveTuner:
    """A Tuner fed by a Source in a thread of its own; .reading is the latest result."""

    def __init__(self, settings: Settings, source: Source) -> None:
        self.source = source
        self.tuner = Tuner(settings, source.rate)
        self.reading = Reading()
        self.error: str | None = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def settings(self) -> Settings:
        return self.tuner.settings

    def configure(self, settings: Settings) -> None:
        with self._lock:
            self.tuner.configure(settings)

    def start(self) -> None:
        self.source.start()
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="py-tuner analysis", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
        self.source.stop()

    def _run(self) -> None:
        seen = 0
        while not self._stop.is_set():
            buf = self.source.buffer
            total = buf.total
            if total == seen:
                self._stop.wait(HOP / 2)
                continue
            seen = total
            try:
                with self._lock:
                    samples = buf.latest(self.tuner.history)
                    reading = self.tuner.analyze(samples, total / self.source.rate)
                self.reading = reading
            except Exception as exc:  # noqa: BLE001 (un fallo del análisis se muestra, no mata el hilo)
                self.error = f"{type(exc).__name__}: {exc}"
            # (se espera lo que falte para el próximo cuadro, contando lo que tardó éste)
            self._stop.wait(max(0.0, HOP - (time.monotonic() % HOP)))
