"""Un estroboscopio de verdad: cada banda sigue la fase de una parcial del sonido.

Un estroboscopio mecánico gira a la frecuencia de la nota buscada y lo ilumina el sonido: si la nota está
afinada, el dibujo se queda quieto; si no, gira tanto más rápido cuanto más se aparta. Aquí cada banda hace lo
mismo con números, como el estroboscopio de Entropy Piano Tuner (Haye Hinrichsen y Christoph Wick): multiplica
el sonido por un fasor que gira a la frecuencia de su parcial (la demodulación), y guarda un promedio que se
olvida poco a poco; la fase de ese promedio es la posición del dibujo.

Como en Strobie (Davorin Šego), la velocidad se escala para que un cent sea una franja por segundo en cualquier
nota, y una banda se apaga cuando su parcial no sobresale del ruido que hay entre las parciales. Dos modos: en
"vernier", las tres bandas siguen la parcial más clara, a una, dos y cuatro veces la velocidad (la de abajo
muestra décimas de cent); en "harmonics", cada banda muestra su parcial (la 1, la 2 y la 3). Las parciales se
buscan donde las pone la inarmonicidad medida de la cuerda, así que en una cuerda afinada todas se quedan
quietas.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

MODES = ("vernier", "harmonics")
# Las parciales que se siguen, y las velocidades de cada banda, por modo
VERNIER_PARTIALS = (1, 2, 3, 4)
VERNIER_SPEEDS = (1, 2, 4)
HARMONIC_PARTIALS = (1, 2, 3)
# How fast each of the two averages forgets (seconds): longer is steadier and slower to follow a turn of the peg.
# Dos promedios en cascada dejan pasar las parciales vecinas (a f0 de distancia) y la imagen del sonido unos
# 60 dB por debajo, donde uno solo las dejaba a 35 dB y la fase temblaba un grado.
TIME_CONSTANT = 0.05
# A band shows fully when its partial stands this far over the noise between partials (dB), and not at all
# below FADE_FROM_DB
FADE_FROM_DB = 3.0
FADE_FULL_DB = 18.0
# Vernier: another partial is followed only when it stands this many dB clearer than the one followed
SWITCH_DB = 6.0
# Stripes per second for each cent of deviation, before a band's own speed
STRIPES_PER_CENT = 1.0


@dataclass(frozen=True)
class Band:
    """One band of the strobe as it is to be drawn: its position (in stripes) and how visible it is (0..1)."""

    position: float
    alpha: float


class Strobe:
    """The lock-ins of the strobe, fed with the sound as it comes and pointed at a target note."""

    def __init__(self, rate: float, mode: str = "vernier") -> None:
        self.rate = float(rate)
        self.mode = mode if mode in MODES else "vernier"
        self.target = 0.0
        self.inharmonicity = 0.0
        self._clock = 0  # muestras desde el principio: la fase de cada fasor sale de aquí, sin acumular error
        self.reset()

    @property
    def partials(self) -> tuple[int, ...]:
        return VERNIER_PARTIALS if self.mode == "vernier" else HARMONIC_PARTIALS

    def reset(self) -> None:
        n = len(self.partials)
        self._z1 = np.zeros(n, dtype=complex)  # el primer promedio
        self._z = np.zeros(n, dtype=complex)  # el segundo, el que se dibuja
        self._n1 = np.zeros(n, dtype=complex)
        self._noise = np.zeros(n, dtype=complex)
        self._last_angle = np.full(n, np.nan)
        self._position = np.zeros(n)  # franjas por parcial, sin dar la vuelta
        self._vernier = 0.0  # franjas del vernier: lo que avanza la parcial elegida en cada momento
        self._best = 0

    def set_target(self, frequency: float, inharmonicity: float = 0.0) -> None:
        """Point the bands at FREQUENCY (0: none). A new note (more than a quarter of a semitone away) starts the
        averages over; the same note, a few cents moved by an offset or a smoothed B, keeps them."""
        frequency = float(frequency or 0.0)
        far = (self.target <= 0 or frequency <= 0
               or abs(1200 * math.log2(frequency / self.target)) > 25)
        self.target = frequency
        self.inharmonicity = max(0.0, float(inharmonicity))
        if far:
            self.reset()

    def frequencies(self) -> np.ndarray:
        """Where each partial is looked for: n·f0·√(1+B·n²), with f0 such that the first partial is the target."""
        n = np.array(self.partials, dtype=float)
        b = self.inharmonicity
        f0 = self.target / math.sqrt(1 + b)
        return n * f0 * np.sqrt(1 + b * n * n)

    def feed(self, samples: np.ndarray) -> None:
        """Takes the newest SAMPLES (only those not fed before)."""
        x = np.asarray(samples, dtype=np.float64)
        count = len(x)
        if count == 0:
            return
        start = self._clock
        self._clock += count
        if self.target <= 0:
            return
        f = self.frequencies()
        ok = f < 0.45 * self.rate
        t = (start + np.arange(count)) / self.rate
        # Dos promedios que se olvidan, en cascada (z1[n] = d·z1[n-1] + u[n], z2[n] = d·z2[n-1] + z1[n]), de un
        # bloque de L muestras a la vez: z1 ← d^L·z1 + Σ d^(L-k)·u_k, z2 ← d^L·z2 + L·d^L·z1 + Σ (L-k+1)·d^(L-k)·u_k.
        decay = math.exp(-1 / (TIME_CONSTANT * self.rate))
        age = np.arange(count - 1, -1, -1)
        w1 = decay ** age
        w2 = (age + 1) * w1
        old = decay ** count
        # Entre una parcial y la siguiente (a media f0 de distancia) no hay más que ruido: su nivel compara.
        between = f + self.target / 2
        for i in np.nonzero(ok)[0]:
            for freq, z1, z2 in ((f[i], self._z1, self._z), (between[i], self._n1, self._noise)):
                u = x * np.exp(-2j * np.pi * freq * t)
                z2[i] = old * z2[i] + count * old * z1[i] + np.sum(w2 * u)
                z1[i] = old * z1[i] + np.sum(w1 * u)
        # La fase de cada banda avanza tanto como giró su promedio, escalada a franjas por cent.
        angle = np.angle(self._z)
        step = np.where(np.isnan(self._last_angle), 0.0,
                        (angle - self._last_angle + np.pi) % (2 * np.pi) - np.pi)
        self._last_angle = angle
        # un ciclo de diferencia a f Hz son 1200/(f·ln 2) cents por segundo
        cents_per_cycle = 1200 / (np.maximum(f, 1e-9) * math.log(2))
        moved = step / (2 * np.pi) * cents_per_cycle * STRIPES_PER_CENT
        self._position += moved
        self._ok = ok
        # El vernier suma lo que avanza la parcial más clara; cambia de parcial solo si otra es mucho más clara
        # (tomar la posición de otra, que anduvo distinto, sería un salto).
        snr = np.where(ok, self.snr(), -np.inf)
        if snr[int(np.argmax(snr))] > snr[self._best] + SWITCH_DB:
            self._best = int(np.argmax(snr))
        self._vernier += moved[self._best]

    def snr(self) -> np.ndarray:
        """How far each partial stands over the noise between partials, in dB."""
        with np.errstate(divide="ignore"):
            return 20 * np.log10((np.abs(self._z) + 1e-12) / (np.abs(self._noise) + 1e-12))

    def bands(self) -> list[Band]:
        """The three bands to draw (positions in stripes, as many cents as a stripe per second)."""
        if self.target <= 0:
            return [Band(0.0, 0.0) for _ in range(3)]
        snr = self.snr()
        alpha = np.clip((snr - FADE_FROM_DB) / (FADE_FULL_DB - FADE_FROM_DB), 0.0, 1.0)
        alpha = np.where(getattr(self, "_ok", np.ones(len(alpha), bool)), alpha, 0.0)
        if self.mode == "vernier":
            # la parcial más clara, a una, dos y cuatro veces su velocidad
            return [Band(float(self._vernier * s), float(alpha[self._best])) for s in VERNIER_SPEEDS]
        return [Band(float(p), float(a)) for p, a in zip(self._position, alpha)]
