"""El paso de las estimaciones sueltas a una lectura estable.

Cada cuadro de análisis da una frecuencia con su ruido; el afinador muestra la
media recortada (la mitad central) de las de los últimos instantes, medidas en
cents, que resiste un valor aislado y aun así afina por debajo de lo que da
un cuadro solo. Un salto grande y sostenido es una nota nueva y vacía la
historia; un salto aislado se descarta. Tras un rato sin tono, la nota se
apaga.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass

# Un salto de más de un tercio de semitono no es la misma nota.
JUMP_CENTS = 35.0


@dataclass(frozen=True)
class Smoothed:
    """The steady reading: frequency in Hz, its spread (cents, the half-width of
    the central half of the recent values) and how many values it is made of."""

    frequency: float
    spread: float
    count: int


class Stabilizer:
    """Smooths a stream of (time, frequency) estimates, 0.0 meaning no pitch.

    window: seconds of history the reading averages. hold: seconds without a
    pitch before the note ends. confirm: how many consecutive estimates a jump
    needs to be taken as a new note.
    """

    def __init__(self, window: float = 0.5, hold: float = 0.4, confirm: int = 2) -> None:
        self.window = window
        self.hold = hold
        self.confirm = confirm
        self._values: deque[tuple[float, float]] = deque()  # (tiempo, cents absolutos)
        self._pending: list[tuple[float, float]] = []
        self._last_seen = -math.inf

    def reset(self) -> None:
        self._values.clear()
        self._pending.clear()
        self._last_seen = -math.inf

    def push(self, time: float, freq: float) -> Smoothed | None:
        """Toma una estimación y devuelve la lectura actual (None: no hay nota)."""
        if freq > 0:
            c = 1200 * math.log2(freq / 440.0)
            centre = self._centre()
            if centre is None or abs(c - centre) <= JUMP_CENTS:
                self._values.append((time, c))
                self._pending.clear()
            else:
                # Un salto: si los saltos seguidos coinciden entre sí, es otra nota.
                if self._pending and abs(c - self._pending[-1][1]) > JUMP_CENTS:
                    self._pending.clear()
                self._pending.append((time, c))
                if len(self._pending) >= self.confirm:
                    self._values = deque(self._pending)
                    self._pending = []
            self._last_seen = time
        elif time - self._last_seen > self.hold:
            self._values.clear()
            self._pending.clear()
        # La ventana se mide desde el último valor, no desde ahora: en una pausa
        # breve (dentro de HOLD) la lectura sigue en pantalla, sin encogerse.
        if self._values:
            latest = self._values[-1][0]
            while self._values[0][0] < latest - self.window:
                self._values.popleft()
        return self.reading()

    def _centre(self) -> float | None:
        if not self._values:
            return None
        cs = sorted(c for _, c in self._values)
        return cs[len(cs) // 2]

    def reading(self) -> Smoothed | None:
        """La media recortada de los valores recientes, o None si no hay ninguno."""
        if not self._values:
            return None
        cs = sorted(c for _, c in self._values)
        n = len(cs)
        q = n // 4
        middle = cs[q:n - q] if n >= 4 else cs
        mean = sum(middle) / len(middle)
        spread = (middle[-1] - middle[0]) / 2
        return Smoothed(440.0 * 2 ** (mean / 1200), spread, n)
