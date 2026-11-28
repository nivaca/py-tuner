"""Estimación de la frecuencia fundamental de un sonido de cuerda, en dos pasos.

Primero, una estimación gruesa del período con el método de McLeod (la función
de diferencia cuadrada normalizada, NSDF, calculada con la FFT), que resiste
bien los errores de octava. Después, un refinamiento fino: la frecuencia de
cada armónico se busca como el máximo exacto de la transformada de Fourier en
tiempo discreto de la señal enventanada (Newton sobre |X(f)|², sin el sesgo de
la interpolación entre casillas de la FFT), y la fundamental sale de un ajuste
por mínimos cuadrados ponderados al modelo de una cuerda real,
f_n = n·f0·√(1 + B·n²), que tiene en cuenta su inarmonicidad B.

El módulo solo usa numpy y no sabe nada del audio ni de las notas: recibe
muestras y devuelve una frecuencia en Hz, con su claridad y su nivel.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

# Ventana de Blackman-Harris de cuatro términos: lóbulos laterales a -92 dB,
# de modo que un armónico vecino casi no desplaza el máximo de otro.
_BH = (0.35875, 0.48829, 0.14128, 0.01168)

# The smallest frame the fine stage uses, whatever the pitch.
MIN_FINE = 4096


def blackman_harris(n: int) -> np.ndarray:
    """Una ventana simétrica de Blackman-Harris de cuatro términos y N puntos."""
    k = np.arange(n) * (2 * np.pi / (n - 1))
    a0, a1, a2, a3 = _BH
    return a0 - a1 * np.cos(k) + a2 * np.cos(2 * k) - a3 * np.cos(3 * k)


@dataclass(frozen=True)
class Estimate:
    """What one analysis frame says.

    frequency: the first partial in Hz (0.0 when no pitch was found).
    clarity: the height of the chosen NSDF peak, 0..1 (1 = perfectly periodic).
    level: the RMS level of the frame in dBFS.
    inharmonicity: the fitted B coefficient (0.0 when it could not be fitted).
    harmonics: how many partials took part in the fit.
    """

    frequency: float
    clarity: float
    level: float
    inharmonicity: float = 0.0
    harmonics: int = 0
    partials: tuple[tuple[int, float, float], ...] = field(default=(), repr=False)

    @property
    def found(self) -> bool:
        return self.frequency > 0.0


def level_db(x: np.ndarray) -> float:
    """El nivel RMS de X en dBFS (-inf para el silencio)."""
    rms = float(np.sqrt(np.mean(np.square(x)))) if len(x) else 0.0
    return 20 * np.log10(rms) if rms > 0 else float("-inf")


def nsdf(x: np.ndarray, max_lag: int) -> np.ndarray:
    """McLeod's normalized square difference function of X for lags 0..MAX_LAG.

    n(τ) = 2·r(τ) / m(τ), with r the autocorrelation and
    m(τ) = Σ (x[j]² + x[j+τ]²) over the overlapping part.
    """
    w = len(x)
    size = 1 << int(np.ceil(np.log2(2 * w)))
    spec = np.fft.rfft(x, size)
    r = np.fft.irfft(spec * np.conj(spec), size)[: max_lag + 1]
    # m(τ) con sumas acumuladas: la energía de x[0:w-τ] más la de x[τ:w]
    sq = np.concatenate(([0.0], np.cumsum(x * x)))
    lags = np.arange(max_lag + 1)
    m = (sq[w - lags] - sq[0]) + (sq[w] - sq[lags])
    out = np.zeros(max_lag + 1)
    ok = m > 1e-12
    out[ok] = 2 * r[ok] / m[ok]
    return out


def coarse_period(x: np.ndarray, rate: float, fmin: float, fmax: float,
                  k: float = 0.9) -> tuple[float, float]:
    """The period of X in samples (fractional) and its clarity, by McLeod's method.

    Among the "key maxima" (the highest point between each pair of upward and
    downward zero crossings of the NSDF) inside [rate/fmax, rate/fmin], the
    first whose height reaches K times the highest one is taken: the first,
    and not the highest, so that twice the period is never chosen.
    Returns (0.0, 0.0) when there is none.
    """
    lo = max(2, int(np.floor(rate / fmax)))
    hi = int(np.ceil(rate / fmin))
    if hi + 2 >= len(x) // 2 + len(x) // 4:
        hi = len(x) // 2 + len(x) // 4 - 3
    if hi <= lo:
        return 0.0, 0.0
    n = nsdf(x, hi + 1)
    # Los máximos clave: el más alto de cada tramo positivo de la curva,
    # pasado el primer cruce por cero (antes está el pico trivial de τ = 0).
    pos = n > 0
    first_neg = np.argmax(~pos)
    if first_neg == 0 and pos[0]:
        return 0.0, 0.0
    peaks: list[int] = []
    i = int(first_neg)
    end = len(n) - 1
    while i < end:
        while i < end and not pos[i]:
            i += 1
        if i >= end:
            break
        j = i
        best = i
        while j < end and pos[j]:
            if n[j] > n[best]:
                best = j
            j += 1
        if j >= end and pos[j - 1]:
            # un tramo que no se cierra puede no tener aún su máximo
            if best < end - 1:
                peaks.append(best)
            break
        peaks.append(best)
        i = j
    peaks = [p for p in peaks if lo <= p <= hi and 0 < p < end]
    if not peaks:
        return 0.0, 0.0
    top = max(n[p] for p in peaks)
    if top <= 0:
        return 0.0, 0.0
    chosen = next(p for p in peaks if n[p] >= k * top)
    # Interpolación parabólica del pico, para un período fraccionario.
    a, b, c = n[chosen - 1], n[chosen], n[chosen + 1]
    den = a - 2 * b + c
    shift = 0.5 * (a - c) / den if den < 0 else 0.0
    clarity = b - 0.25 * (a - c) * shift
    return chosen + shift, float(min(1.0, clarity))


def _peak_frequencies(y: np.ndarray, rate: float, guesses: np.ndarray,
                      iterations: int = 4) -> tuple[np.ndarray, np.ndarray]:
    """The frequencies near GUESSES where |DTFT(Y)| is highest, and their amplitudes.

    Y is the already windowed frame. Newton's method on P(f) = |X(f)|², with
    the first and second derivatives of X computed in the same pass, so each
    iteration is three matrix products. Every harmonic is solved at once.
    """
    n = len(y)
    t = (np.arange(n) - (n - 1) / 2) / rate  # tiempo centrado: fases pequeñas, mejor condicionado
    ty = t * y
    tty = t * ty
    f = guesses.astype(float).copy()
    # Paso máximo: un cuarto del lóbulo principal (4 casillas de la FFT para Blackman-Harris).
    max_step = rate / n
    for _ in range(iterations):
        e = _phasors(f, n, rate)
        x0 = e @ y
        x1 = (-2j * np.pi) * (e @ ty)
        x2 = (-4 * np.pi ** 2) * (e @ tty)
        d1 = 2 * np.real(np.conj(x0) * x1)
        d2 = 2 * (np.abs(x1) ** 2 + np.real(np.conj(x0) * x2))
        step = np.where(d2 < 0, -d1 / np.where(d2 < 0, d2, -1.0), np.sign(d1) * max_step)
        f += np.clip(step, -max_step, max_step)
    return f, np.abs(_phasors(f, n, rate) @ y)


def _phasors(f: np.ndarray, n: int, rate: float, block: int = 128) -> np.ndarray:
    """exp(-2πi·f·t) for each frequency of F (rows) and the N centred times t (columns).

    Built as the product of a coarse grid (one value per BLOCK samples) and a
    fine one (BLOCK values): two small exponentials instead of one large one,
    about nine times faster, with the same precision (errors near 1e-13).
    """
    blocks = -(-n // block)
    start = -(n - 1) / 2 / rate
    coarse = np.exp(-2j * np.pi * np.outer(f, start + np.arange(blocks) * (block / rate)))
    fine = np.exp(-2j * np.pi * np.outer(f, np.arange(block) / rate))
    return (coarse[:, :, None] * fine[:, None, :]).reshape(len(f), -1)[:, :n]


def refine(x: np.ndarray, rate: float, f_guess: float, max_harmonics: int = 16,
           floor_db: float = -50.0) -> tuple[float, float, list[tuple[int, float, float]]]:
    """The first partial of X, refined from F_GUESS with the harmonics.

    Each harmonic up to MAX_HARMONICS (and below Nyquist·0.9) is located
    exactly; those weaker than FLOOR_DB below the strongest, or not clearly
    above the noise floor, are dropped. Then
    (f_n/n)² = f0²·(1 + B·n²) is fitted by weighted least squares (weights
    (n·A_n)², which is how the variance of each estimate falls), and the
    first partial is f0·√(1+B). Returns (frequency, B, [(n, f_n, A_n), ...]).
    """
    win = blackman_harris(len(x))
    y = (x - np.average(x, weights=win)) * win
    count = int(min(max_harmonics, (0.45 * rate) // f_guess))
    if count < 1:
        return 0.0, 0.0, []
    ns = np.arange(1, count + 1)
    floor = 10 ** (floor_db / 20)
    # El ruido de fondo, en las mismas unidades que |X(f)|: la mediana del
    # espectro, que los pocos armónicos casi no mueven. Un pico que no le saque
    # 12 dB es ruido, y con el peso n² de los armónicos altos dañaría el ajuste.
    noise = 4 * float(np.median(np.abs(np.fft.rfft(y))))
    # Primera pasada con los armónicos bajos, donde la inarmonicidad casi no
    # mueve nada; de ahí salen f0 y B para predecir dónde están los altos.
    low = ns[: min(count, 6)]
    guesses = low * f_guess
    freqs, amps = _peak_frequencies(y, rate, guesses)
    keep = _plausible(freqs, guesses, amps, f_guess, floor, noise)
    f0, b = _fit(low[keep], freqs[keep], amps[keep]) if keep.any() else (0.0, 0.0)
    if f0 > 0 and count > len(low):
        guesses = ns * f0 * np.sqrt(1 + b * ns ** 2)
        freqs, amps = _peak_frequencies(y, rate, guesses)
        keep = _plausible(freqs, guesses, amps, f_guess, floor, noise)
        ns = ns[keep]
        f0, b = _fit(ns, freqs[keep], amps[keep])
        freqs, amps = freqs[keep], amps[keep]
    else:
        ns, freqs, amps = low[keep], freqs[keep], amps[keep]
    partials = [(int(n), float(f), float(a)) for n, f, a in zip(ns, freqs, amps)]
    if f0 <= 0:
        return 0.0, 0.0, partials
    return float(f0 * np.sqrt(1 + b)), float(b), partials


def _plausible(freqs: np.ndarray, guesses: np.ndarray, amps: np.ndarray, f_guess: float,
               floor: float, noise: float) -> np.ndarray:
    """Which found peaks count as harmonics: strong enough (FLOOR times the
    strongest, and above NOISE) and still near where they were looked for (a
    peak that wandered a quarter of f0 away is something else)."""
    if not len(amps) or amps.max() <= 0:
        return np.zeros(len(amps), dtype=bool)
    return ((amps >= amps.max() * floor) & (amps > noise)
            & (np.abs(freqs - guesses) < 0.25 * f_guess))


def _fit(ns: np.ndarray, freqs: np.ndarray, amps: np.ndarray) -> tuple[float, float]:
    """f0 y B a partir de los parciales (n, f_n, A_n), con B ≥ 0; (0, 0) si no se puede."""
    if len(ns) == 0:
        return 0.0, 0.0
    y = freqs / ns
    w = (ns * amps) ** 2
    if len(ns) >= 3 and ns.max() >= 3:
        # Al cuadrado, el modelo es lineal sin aproximación alguna:
        # (f_n/n)² = f0² + f0²·B·n². Los pesos casi no cambian (y es casi constante).
        a_mat = np.stack([np.ones_like(y), ns.astype(float) ** 2], axis=1)
        sw = np.sqrt(w)
        (a, c), *_ = np.linalg.lstsq(a_mat * sw[:, None], y * y * sw, rcond=None)
        if a > 0 and c >= 0:
            b = c / a
            # Los valores reales de B en estas cuerdas no pasan de unas milésimas.
            if b < 0.02:
                return float(np.sqrt(a)), float(b)
    # Sin ajuste posible: la media ponderada de f_n/n, sin inarmonicidad.
    return float(np.sum(w * y) / np.sum(w)), 0.0


def highpass(x: np.ndarray, rate: float, corner: float, order: int = 2) -> np.ndarray:
    """X without what lies under CORNER Hz: a Butterworth high-pass of ORDER applied by its magnitude in the
    frequency domain, so without phase shift (the frequencies above keep their exact phase).

    Como en Strobie (Davorin Šego), que corta bajo A0: se lleva la continua y el retumbo bajo las notas, que
    inflan la correlación de los períodos largos.
    """
    n = len(x)
    size = 1 << int(np.ceil(np.log2(2 * n)))  # (con ceros detrás, para que el filtro no dé la vuelta)
    spec = np.fft.rfft(x, size)
    f = np.fft.rfftfreq(size, 1 / rate)
    with np.errstate(divide="ignore"):
        gain = 1 / np.sqrt(1 + (corner / np.maximum(f, 1e-9)) ** (2 * order))
    gain[0] = 0.0
    return np.fft.irfft(spec * gain, size)[:n]


def lowpass(x: np.ndarray, rate: float, corner: float, order: int = 4) -> np.ndarray:
    """X without what lies over CORNER Hz: a Butterworth low-pass of ORDER, applied as highpass() is (by its
    magnitude in the frequency domain, with zeros behind, without phase shift)."""
    n = len(x)
    # ceros detrás, tantos como dura la respuesta del filtro (unos 4/CORNER segundos), para que no dé la vuelta
    size = 1 << int(np.ceil(np.log2(n + int(np.ceil(4 * rate / corner)))))
    spec = np.fft.rfft(x, size)
    f = np.fft.rfftfreq(size, 1 / rate)
    # The gain of the filter is real, so no bin moves its phase.
    return np.fft.irfft(spec / np.sqrt(1 + (f / corner) ** (2 * order)), size)[:n]


# The low-pass of the second look at the clarity: this many times the pitch found, and never under this (Hz)
COARSE_HARMONICS = 12.0
COARSE_LOWPASS_MIN = 200.0
# El nivel se mide hasta tantas veces la nota más aguda del margen, y nunca por debajo de tantos Hz
LEVEL_BAND = 2.0
LEVEL_BAND_MIN = 500.0


def prominence(x: np.ndarray, rate: float, cap: float = 40.0) -> tuple[np.ndarray, float]:
    """How far each bin of X's spectrum stands over the sound around it, in dB (0..CAP), and the bin width in Hz.

    The background is the lower quartile of the bins within 40 Hz either side, worked out every few bins and
    joined by straight lines, as Strobie's harmonic stack does: a partial and its lobes take a small share of
    the bins around them, so the quartile falls between partials. A peak counts by how far it stands out, not by
    its level, so a loud low rumble and a soft clear partial weigh alike.
    """
    n = len(x)
    size = 1 << int(np.ceil(np.log2(2 * n)))
    mag = np.abs(np.fft.rfft((x - x.mean()) * np.hanning(n), size))
    db = 20 * np.log10(mag + 1e-12 * (mag.max() + 1e-30))
    df = rate / size
    half = max(4, int(40 / df))
    step = max(1, half // 4)
    padded = np.pad(db, half, mode="edge")
    windows = np.lib.stride_tricks.sliding_window_view(padded, 2 * half + 1)[::step]
    centres = np.arange(0, len(db), step)[: len(windows)]
    background = np.interp(np.arange(len(db)), centres, np.percentile(windows, 25, axis=1))
    return np.clip(db - background, 0.0, cap), df


# Lo que cuesta cada lugar de armónico en el que no hay nada (dB de prominencia): el ruido mismo sobresale unos
# 5 o 6 dB de su cuartil, una parcial de verdad mucho más
SLOT_COST_DB = 8.0
# A partial this far over its background is clear (it sets the ceiling of the harmonics compared)
CLEAR_DB = 12.0


def harmonic_score(prom: np.ndarray, df: float, f0: float, ceiling: float) -> float:
    """How well F0 explains the peaks of PROM up to CEILING Hz: for each of its harmonics, its prominence less
    SLOT_COST_DB (an empty place costs), and less the prominence at each half-harmonic, (n - ½)·F0.

    Las posiciones intermedias restan, como los picos negativos del núcleo del reconocedor de teclas de Entropy
    Piano Tuner (Hinrichsen y Wick), y la suma sobre los armónicos, como la pila de armónicos de Strobie (Davorin
    Šego): una altura una octava baja paga sus lugares vacíos, una octava (o una duodécima) alta cubre menos
    parciales y encuentra los impares verdaderos entre los suyos. Each harmonic is looked for within 1.2 % of
    n·F0, as a stiff string's partials run sharp.
    """
    count = int(ceiling // f0)
    if count < 1:
        return -np.inf

    def peak(f: float) -> float:
        lo, hi = int((f * 0.988) / df), int(np.ceil((f * 1.012) / df)) + 1
        return float(prom[max(lo, 0):min(hi, len(prom))].max()) if lo < len(prom) else 0.0

    ns = range(1, count + 1)
    return sum(peak(n * f0) - SLOT_COST_DB for n in ns) - sum(peak((n - 0.5) * f0) for n in ns)


# The ratios to the coarse pitch that are tried as the real one: the octave and twelfth either side, the usual
# errors of a period method (a sub-harmonic shared by two ringing partials, or the 2nd harmonic of a string
# whose fundamental is weak).
CANDIDATES = (1 / 3, 1 / 2, 1.0, 2.0, 3.0)
# How much better (dB of prominence) another candidate must score to replace the coarse pitch
SWITCH_DB = 6.0
# Lo que gana el candidato que sigue la nota que ya sonaba (a menos de 60 cents de ella): en la cola de una
# nota, cuando sus parciales se apagan, un múltiplo o un submúltiplo puede ganar por poco y por azar.
CONTINUITY_DB = 12.0


# An octave or a twelfth up is only taken if the sound also repeats at that shorter lag: its NSDF there at least
# this share of the NSDF at the period found
UP_PERIODICITY = 0.8


def choose_octave(x: np.ndarray, rate: float, guess: float, fmin: float, fmax: float, periods: float,
                  prefer: float | None = None, periodicity=None) -> float:
    """The candidate around GUESS that best explains the spectrum of X, GUESS itself unless another is clearly
    better. PREFER, the pitch of the note already sounding, gives the candidate near it an advantage (as Tuneo,
    by Braulio Ríos, narrows its search around the note while it decays). PERIODICITY(ratio), if given, is how
    periodic the sound is at the period divided by RATIO, relative to the period found: a candidate above GUESS
    needs it (a sound with a pitch of 3f repeats every third of the period of f)."""
    options = [guess * r for r in CANDIDATES if fmin <= guess * r <= fmax
               and (r <= 1 or periodicity is None or periodicity(r) >= UP_PERIODICITY)]
    if len(options) < 2:
        return guess
    # Un cuadro con bastantes períodos del candidato más grave, para que sus armónicos se separen.
    size = min(len(x), int(max(MIN_FINE, periods * rate / min(options))))
    prom, df = prominence(x[-size:], rate)
    # Los armónicos se comparan hasta poco más allá de la parcial clara más alta (y no más de doce del
    # candidato del período): por encima no hay nada que explicar, y un seno no premia a sus múltiplos.
    top = min(5000.0, 0.45 * rate, 12 * guess)
    clear = np.nonzero(prom[: int(top / df)] >= CLEAR_DB)[0]
    if not len(clear):
        return guess
    ceiling = min(top, 1.1 * clear[-1] * df)
    scores = {f: harmonic_score(prom, df, f, ceiling) for f in options}
    if prefer:
        for f in scores:
            if abs(1200 * np.log2(f / prefer)) < 60:
                scores[f] += CONTINUITY_DB
    best = max(scores, key=scores.get)
    return best if scores[best] > scores[guess] + SWITCH_DB else guess


@dataclass
class Detector:
    """The analysis settings, and the frame sizes they imply.

    rate: sample rate in Hz. fmin, fmax: the range of the fundamental.
    periods: how many periods of the found pitch the fine frame holds (more:
    steadier and slower). min_level: frames quieter than this (dBFS) are
    silence. min_clarity: frames less periodic than this have no pitch.
    """

    rate: float = 48000.0
    fmin: float = 27.5
    fmax: float = 1500.0
    periods: float = 16.0
    min_level: float = -60.0
    min_clarity: float = 0.75
    max_harmonics: int = 16

    @property
    def coarse_size(self) -> int:
        """Las muestras que pide el paso grueso: tres períodos de la nota más grave."""
        return int(np.ceil(3 * self.rate / self.fmin))

    def fine_size(self, frequency: float) -> int:
        """Las muestras que usa el paso fino para una altura de FREQUENCY."""
        return int(max(MIN_FINE, np.ceil(self.periods * self.rate / frequency)))

    @property
    def band_top(self) -> float:
        """The top of the band whose level is measured (Hz): a few times the highest note, so that the room's
        noise counts only where the notes are."""
        # (bajo el Nyquist, siempre: a 44,1 kHz el modo cromático llega a unos 3,5 kHz)
        return min(0.45 * self.rate, max(LEVEL_BAND * self.fmax, LEVEL_BAND_MIN))

    def band_level(self, x: np.ndarray, count: int) -> float:
        """The level (dBFS) of the last COUNT samples of the high-passed X, in the band of the notes.

        A low note through a phone's microphone has its sound in a few narrow partials: in the whole band its
        level falls into the room's noise long before its partials do. Measured in the band, the note and the
        learned noise floor are compared where the note is.
        """
        return level_db(lowpass(x[-count:], self.rate, self.band_top))

    @property
    def history(self) -> int:
        """Samples a caller should keep: enough for both stages at the lowest note."""
        return max(self.coarse_size, self.fine_size(self.fmin))

    def analyze(self, samples: np.ndarray, prefer: float | None = None) -> Estimate:
        """The pitch of the most recent samples (the end of SAMPLES); PREFER, the note already sounding, if any."""
        x = np.asarray(samples, dtype=np.float64)
        if len(x) == 0:
            return Estimate(0.0, 0.0, float("-inf"))
        # the newest samples, which the level is measured on
        last = min(len(x), MIN_FINE * 2)
        if len(x) < 4 * self.rate / self.fmax:
            # Too few samples for any period: only the level, as it comes.
            return Estimate(0.0, 0.0, level_db(x[-last:]))
        # sin lo que queda bajo el margen (a 0,7 de la nota más grave): la continua y el retumbo
        x = highpass(x - x.mean(), self.rate, 0.7 * self.fmin)
        # el nivel, medido solo donde están las notas (y el ruido que les toca)
        level = self.band_level(x, last)
        if level < self.min_level:
            return Estimate(0.0, 0.0, level)
        coarse = x[-min(len(x), self.coarse_size):]
        coarse = coarse - coarse.mean()
        period, clarity = coarse_period(coarse, self.rate, self.fmin, self.fmax)
        if period > 0:
            # La claridad, otra vez, sobre los parciales bajos de la altura hallada. Por un micrófono de teléfono
            # la fundamental de una cuerda grave llega débil y mandan los parciales altos, que suben por la
            # inarmonicidad y se hunden antes en el ruido: el cuadro deja de parecer periódico aunque la nota esté
            # clara. Como Strobie (Davorin Šego), que detecta bajo un pasabajos.
            corner = max(COARSE_LOWPASS_MIN, COARSE_HARMONICS * self.rate / period)
            # (una nota aguda no lo necesita: su corte quedaría sobre la banda entera)
            if corner < 0.4 * self.rate:
                # Only the clarity is taken from the filtered frame; the period stays the one of the whole band.
                _, low_clarity = coarse_period(lowpass(coarse, self.rate, corner), self.rate, self.fmin, self.fmax)
                clarity = max(clarity, low_clarity)
        if period <= 0 or clarity < self.min_clarity:
            return Estimate(0.0, clarity, level)
        # La periodicidad a una fracción del período, del mismo NSDF del paso grueso
        n = nsdf(coarse, int(np.ceil(period)) + 2)

        def periodicity(ratio: float) -> float:
            lag = period / ratio
            i = int(round(lag))
            return float(n[max(1, i - 1):i + 2].max() / max(n[int(round(period))], 1e-9)) if i >= 2 else 0.0

        guess = choose_octave(x, self.rate, self.rate / period, self.fmin, self.fmax, self.periods, prefer,
                              periodicity)
        size = self.fine_size(guess)
        if len(x) < size:
            # Sin un cuadro fino entero (al empezar a escuchar, o en una máquina lenta) la estimación sería
            # pobre: mejor ninguna, hasta que haya muestras.
            return Estimate(0.0, clarity, level)
        freq, b, partials = refine(x[-size:], self.rate, guess, self.max_harmonics)
        # El refinamiento no debe alejarse del período: si lo hace, algo lo engañó, y el cuadro no dice nada.
        if freq <= 0 or abs(1200 * np.log2(freq / guess)) > 60:
            return Estimate(0.0, clarity, level)
        return Estimate(freq, clarity, level, b, len(partials), tuple(partials))
