"""Lo que las tres interfaces muestran igual: nombres, cifras y el movimiento del estroboscopio.

Así la ventana, la terminal y la línea de órdenes escriben las notas, los
cents y las frecuencias con las mismas reglas, y sus estroboscopios giran a
la misma velocidad.
"""

from __future__ import annotations

import math

from . import notes
from .interface import number, tr
from .settings import Settings
from .tuner import Reading

# The needle's scale, in cents either side.
NEEDLE_RANGE = 50.0
# Velocidad del estroboscopio: celdas (o franjas) por segundo por cada cent de
# desviación, en la primera banda; las siguientes van al doble y al cuádruple,
# como los armónicos 1, 2 y 4 de un estroboscopio mecánico.
STROBE_SPEED = 1.0
STROBE_BANDS = (1, 2, 4)


def note_name(midi: int, s: Settings, unicode: bool = True) -> str:
    """The name of MIDI as shown: transposed for a transposing instrument (only the name; the pitch is the same)."""
    return notes.name(midi + s.transpose, s.names, s.accidentals, unicode)


def note_full(midi: int, s: Settings, unicode: bool = True) -> str:
    return notes.full_name(midi + s.transpose, s.names, s.accidentals, unicode)


def string_labels(s: Settings, unicode: bool = True) -> list[str]:
    """Los nombres de las cuerdas de la afinación actual, de la más grave a la más aguda ([] en modo cromático)."""
    inst = s.instrument_preset()
    if not inst.tunings:
        return []
    return [note_full(m + s.capo, s, unicode) for m in inst.tuning(s.tuning).midis]


def cents_text(r: Reading) -> str:
    """La desviación con signo y un decimal, al estilo "+0.0", o "" si no hay nota."""
    if not r.active:
        return ""
    c = round(r.cents, 1)
    return number(f"{c:+.1f}" if c != 0 else "0.0")


def freq_text(hz: float) -> str:
    """A frequency with three decimals below 100 Hz and two above (a hundredth
    of a cent at 41 Hz is 0.0024 Hz: the digits shown should be ones that mean
    something, not noise)."""
    return number(f"{hz:.3f}" if hz < 100 else f"{hz:.2f}")


def summary(s: Settings) -> str:
    """"Guitar · Standard · A4 = 440.0 Hz" for headers and status lines."""
    inst = s.instrument_preset()
    parts = [tr(inst.name)]
    if inst.tunings:
        parts.append(tr(inst.tuning(s.tuning).name))
        if s.string is not None:
            labels = string_labels(s)
            if s.string < len(labels):
                parts.append(tr("string {name}", name=labels[s.string]))
    if inst.tunings and s.capo:
        parts.append(tr("capo {fret}", fret=s.capo))
    if s.transpose:
        parts.append(tr("transposed {semitones}", semitones=f"{s.transpose:+d}"))
    if s.offsets:
        parts.append(tr("offsets"))
    parts.append(f"A4 = {number(f'{s.a4:.1f}')} Hz")
    return " · ".join(parts)


class Strobe:
    """The phase of each strobe band, advanced by the deviation and the time.

    A band moves STROBE_SPEED·band cells per second per cent: right when sharp,
    left when flat, still when in tune. The phase is kept in [0, 1) of one
    pattern period of PERIOD cells.
    """

    def __init__(self, period: float = 8.0) -> None:
        self.period = period
        self.phases = [0.0 for _ in STROBE_BANDS]

    def advance(self, cents: float | None, dt: float) -> list[float]:
        if cents is not None:
            # (más allá de la escala de la aguja el dibujo ya no se sigue con el ojo)
            c = max(-NEEDLE_RANGE, min(NEEDLE_RANGE, cents))
            for i, band in enumerate(STROBE_BANDS):
                self.phases[i] = (self.phases[i] + c * STROBE_SPEED * band * dt / self.period) % 1.0
        return self.phases


class Follower:
    """The real strobe's bands (strobe.Band, from the readings) drawn smoothly between readings.

    Las lecturas llegan cada 25 ms y la ventana se dibuja cada 16: entre una y otra, cada banda sigue a la
    velocidad que traía (como mucho 60 ms, por si las lecturas se detienen).
    """

    LIMIT = 0.06

    def __init__(self) -> None:
        self._bands: tuple = ()
        self._time = 0.0
        self._speed: list[float] = []

    def update(self, bands: tuple, now: float) -> None:
        if not bands:
            self._bands, self._speed = (), []
            return
        if bands != self._bands:
            if self._bands and len(self._bands) == len(bands) and now > self._time:
                dt = now - self._time
                self._speed = [(b.position - a.position) / dt for a, b in zip(self._bands, bands)]
            else:
                self._speed = [0.0] * len(bands)
            self._bands, self._time = bands, now

    def phases(self, now: float) -> list[tuple[float, float]]:
        """[(phase in 0..1, alpha), ...] of each band at NOW."""
        ahead = min(max(0.0, now - self._time), self.LIMIT)
        return [((b.position + v * ahead) % 1.0, b.alpha) for b, v in zip(self._bands, self._speed)]


# The needle's scales: "linear" (a cent is a cent anywhere) and "fine" (an arctangent, as the gauge of Tuneo, by
# Braulio Ríos: the cents near the centre spread out, the far ones close up, ±50 still at the ends).
NEEDLE_SCALES = ("linear", "fine")
# La rodilla de la escala fina (cents): a ±FINE_KNEE queda la mitad de cada lado de la escala
FINE_KNEE = 5.0


def needle_fraction(cents: float, scale: str = "linear") -> float:
    """Where CENTS falls on the needle's scale, from -1 (-50 cents) to 1 (+50 cents)."""
    c = max(-NEEDLE_RANGE, min(NEEDLE_RANGE, cents))
    if scale == "fine":
        return math.atan(c / FINE_KNEE) / math.atan(NEEDLE_RANGE / FINE_KNEE)
    return c / NEEDLE_RANGE


def needle_ticks(scale: str = "linear") -> list[tuple[float, bool]]:
    """The marks of the scale: [(cents, major)], the majors labelled."""
    if scale == "fine":
        majors = (0, 1, 2, 5, 10, 20, 50)
        minors = (3, 4, 30, 40)
        marks = [(c, True) for c in majors] + [(c, False) for c in minors]
    else:
        marks = [(c, c % 10 == 0) for c in range(0, 51, 5)]
    out = sorted({(s * c, major) for c, major in marks for s in (1, -1)})
    return out


# El espectro que se muestra: de dónde a dónde (Hz, en escala logarítmica) y cuántas muestras recientes
SPECTRUM_LOW = 30.0
SPECTRUM_HIGH = 5000.0
SPECTRUM_SAMPLES = 16384
# A peak named on the spectrum stands this far over its background (dB)
PEAK_DB = 15.0


def spectrum(samples, rate: float, points: int = 400) -> tuple[list[float], list[float]]:
    """The spectrum of SAMPLES as POINTS (frequency, dBFS) pairs, log-spaced from SPECTRUM_LOW to SPECTRUM_HIGH:
    the loudest bin around each point, so a narrow partial never falls between two points."""
    import numpy as np

    x = np.asarray(samples, dtype=np.float64)
    if len(x) < 256:
        return [], []
    win = np.hanning(len(x))
    mag = np.abs(np.fft.rfft((x - x.mean()) * win)) * 2 / win.sum()
    db = 20 * np.log10(mag + 1e-12)
    df = rate / len(x)
    edges = np.geomspace(SPECTRUM_LOW, min(SPECTRUM_HIGH, 0.45 * rate), points + 1)
    out_f, out_db = [], []
    for lo, hi in zip(edges[:-1], edges[1:]):
        a, b = int(lo / df), max(int(lo / df) + 1, int(np.ceil(hi / df)))
        out_f.append(float(np.sqrt(lo * hi)))
        out_db.append(float(db[a:b].max()) if a < len(db) else -240.0)
    return out_f, out_db


def peaks(samples, rate: float, most: int = 5) -> list[tuple[float, float]]:
    """The clearest peaks of SAMPLES' spectrum, [(frequency, dBFS)] loudest first: those standing PEAK_DB over
    the sound around them (the prominence of pitch.py, as Strobie's spectrum names its loudest peaks)."""
    import numpy as np

    from .pitch import prominence

    x = np.asarray(samples, dtype=np.float64)
    if len(x) < 1024:
        return []
    prom, df = prominence(x, rate)
    size = int(round(rate / df))
    win = np.hanning(len(x))
    mag = np.abs(np.fft.rfft((x - x.mean()) * win, size)) * 2 / win.sum()
    db = 20 * np.log10(mag + 1e-12)
    lo, hi = int(SPECTRUM_LOW / df), min(len(db) - 2, int(SPECTRUM_HIGH / df))
    found = []
    for i in range(max(lo, 1), hi):
        if prom[i] >= PEAK_DB and db[i] >= db[i - 1] and db[i] > db[i + 1]:
            # el máximo entre casillas, por una parábola en dB
            a, b, c = db[i - 1], db[i], db[i + 1]
            shift = 0.5 * (a - c) / (a - 2 * b + c) if (a - 2 * b + c) < 0 else 0.0
            found.append(((i + shift) * df, float(b)))
    found.sort(key=lambda p: -p[1])
    # (sin dos picos del mismo lóbulo: a menos de un cuarto de tono, el más fuerte)
    kept: list[tuple[float, float]] = []
    for f, level in found:
        if all(abs(1200 * np.log2(f / g)) > 50 for g, _ in kept):
            kept.append((f, level))
        if len(kept) == most:
            break
    return kept


def peak_label(frequency: float, s: Settings) -> str:
    """A peak as the note nearest to it, with its cents: "E3 +2"."""
    midi = notes.nearest(frequency, s.a4)
    c = notes.cents(frequency, notes.frequency(midi, s.a4))
    return f"{note_full(midi, s)} {c:+.0f}"
