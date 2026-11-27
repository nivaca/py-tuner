"""El paso de las estimaciones sueltas a una lectura estable.

Cada cuadro de análisis da una frecuencia con su ruido; el afinador muestra la
media recortada (la mitad central) de las de los últimos instantes, medidas en
cents, que resiste un valor aislado y aun así afina por debajo de lo que da
un cuadro solo. Un salto grande y sostenido es una nota nueva y vacía la
historia; un salto aislado se descarta. Tras un rato sin tono, la nota se
apaga. En la respuesta estable (la del contrabajo) se deja fuera además el
ataque de cada pulsación, mientras la cuerda recién pulsada suena alta.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass

# Un salto de más de un tercio de semitono no es la misma nota.
JUMP_CENTS = 35.0
# A new note right after a pluck (an onset in the last ONSET_S) is taken after `confirm` estimates; without one,
# it must hold this long, and longer if it is a harmonic or an undertone of the note sounding. Como en Strobie
# (Davorin Šego): en la cola de una nota, un múltiplo o un submúltiplo suyo aparece a ratos, y una nota nueva de
# verdad casi siempre llega con un ataque.
ONSET_S = 0.3
NO_ONSET_S = 0.3
RELATED_S = 0.6
# Las relaciones que cuentan como armónico o subarmónico: la octava, la duodécima, la doble octava y la quinta
RELATED_RATIOS = (2.0, 3.0, 4.0, 1.5)
# Onsets closer than this are one pluck (the onset of tuner.py stays on while its envelope catches up, about
# a third of a second): the attack is counted from the first of them
PLUCK_GAP_S = 0.1
# A note that has just ended is remembered this long: a harmonic or undertone of it that shows up from silence
# without a pluck (its tail, read an octave down) waits as a jump would
MEMORY_S = 2.0


@dataclass(frozen=True)
class Smoothed:
    """The steady reading: frequency in Hz, its spread (cents, the half-width of
    the central half of the recent values), how many values it is made of, and
    the seconds of sound between the first of them and the last."""

    frequency: float
    spread: float
    count: int
    span: float = 0.0


class Stabilizer:
    """Smooths a stream of (time, frequency) estimates, 0.0 meaning no pitch.

    window: seconds of history the reading averages. hold: seconds without a
    pitch before the note ends. confirm: how many consecutive estimates a jump
    needs to be taken as a new note. attack: seconds after each pluck whose
    estimates are left out (0: none), while the note sounding stays.
    """

    def __init__(self, window: float = 0.5, hold: float = 0.4, confirm: int = 2, attack: float = 0.0) -> None:
        self.window = window
        self.hold = hold
        self.confirm = confirm
        self.attack = attack
        self._values: deque[tuple[float, float]] = deque()  # (tiempo, cents absolutos)
        self._pending: list[tuple[float, float]] = []
        self._last_seen = -math.inf
        self._last_onset = -math.inf
        self._pluck = -math.inf  # cuándo empezó la última pulsación (su primer ataque)
        self._taken = False  # si ya se tomó una nota tras el ataque de esa pulsación
        self._last_note: tuple[float, float] | None = None  # (cents, tiempo) de la última nota

    def reset(self) -> None:
        self._values.clear()
        self._pending.clear()
        self._last_seen = -math.inf

    @staticmethod
    def related(cents: float) -> bool:
        """Whether a jump of CENTS is a harmonic or an undertone (within 50 cents of an octave, a twelfth...)."""
        return any(abs(abs(cents) - 1200 * math.log2(r)) < 50 for r in RELATED_RATIOS)

    def push(self, time: float, freq: float, onset: bool = False) -> Smoothed | None:
        """Toma una estimación y devuelve la lectura actual (None: no hay nota). ONSET: se acaba de pulsar."""
        if onset:
            if time - self._last_onset > PLUCK_GAP_S:
                self._pluck = time
                self._taken = False
            self._last_onset = time
        if freq > 0 and time - self._pluck < self.attack:
            # El ataque no cuenta: la cuerda recién pulsada suena alta y se va asentando. La nota que sonaba se
            # queda en pantalla mientras tanto.
            if self._values:
                self._last_seen = time
            return self.reading()
        if freq > 0:
            c = 1200 * math.log2(freq / 440.0)
            centre = self._centre()
            if centre is None and self._suspect(c, time):
                # Desde el silencio, pero pariente de la nota que acaba de callar y sin ataque: se espera como un
                # salto desde ella.
                centre = self._last_note[0]
            # With an attack left out (the steady response), a note that rises from silence without a pluck waits
            # as a jump would: in the faint tail of a string read at a lower clarity, a stray pitch shows up a
            # moment. (A bowed note, which has no pluck, waits too.)
            quiet = centre is None and self.attack > 0 and not self.recent_onset(time)
            if centre is None and not quiet:
                self._pending.clear()
            if (centre is None and not quiet) or (centre is not None and self._values
                                                   and abs(c - centre) <= JUMP_CENTS):
                self._values.append((time, c))
                self._pending.clear()
                self._last_seen = time
                self._taken = True
            else:
                # Un salto: si los saltos seguidos coinciden entre sí, es otra nota.
                if self._pending and abs(c - self._pending[-1][1]) > JUMP_CENTS:
                    self._pending.clear()
                self._pending.append((time, c))
                span = self._pending[-1][0] - self._pending[0][0]
                if self.recent_onset(time):
                    need = 0.0
                else:
                    need = RELATED_S if centre is not None and self.related(c - centre) else NO_ONSET_S
                if len(self._pending) >= self.confirm and span >= need - 1e-9:
                    self._values = deque(self._pending)
                    self._pending = []
                    self._last_seen = time
                    self._taken = True
            if self._values:
                self._last_note = (self._centre(), time)
        else:
            # Una nota nueva se ve seguida: un cuadro sin altura borra el salto que esperaba.
            self._pending.clear()
        # La nota se apaga tras HOLD sin un valor suyo (los de un salto que espera no la sostienen).
        if self._values and time - self._last_seen > self.hold:
            self._values.clear()
            self._pending.clear()
        # La ventana se mide desde el último valor, no desde ahora: en una pausa
        # breve (dentro de HOLD) la lectura sigue en pantalla, sin encogerse.
        if self._values:
            latest = self._values[-1][0]
            while self._values[0][0] < latest - self.window:
                self._values.popleft()
        return self.reading()

    def _suspect(self, cents: float, time: float) -> bool:
        """Whether CENTS, from silence, is a harmonic or undertone of the note that has just ended, with no pluck."""
        if self._last_note is None or self.recent_onset(time):
            return False
        last, when = self._last_note
        return time - when <= MEMORY_S and abs(cents - last) > JUMP_CENTS and self.related(cents - last)

    def centre_frequency(self) -> float | None:
        """The frequency of the note sounding (the median of the recent values), or None."""
        c = self._centre()
        return None if c is None else 440.0 * 2 ** (c / 1200)

    def recent_onset(self, time: float) -> bool:
        """Whether TIME is just after a pluck: within ONSET_S of its last onset or, with an attack left out, of
        the end of the attack, until the first estimate after it is taken (then the note is the pluck's own, and
        a jump away from it waits as any other)."""
        if time - self._last_onset <= ONSET_S:
            return True
        return self.attack > 0 and not self._taken and time - self._pluck <= self.attack + ONSET_S

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
        return Smoothed(440.0 * 2 ** (mean / 1200), spread, n, self._values[-1][0] - self._values[0][0])
