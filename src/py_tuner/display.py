"""Lo que las tres interfaces muestran igual: nombres, cifras y el movimiento del estroboscopio.

Así la ventana, la terminal y la línea de órdenes escriben las notas, los
cents y las frecuencias con las mismas reglas, y sus estroboscopios giran a
la misma velocidad.
"""

from __future__ import annotations

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
    return notes.name(midi, s.names, s.accidentals, unicode)


def note_full(midi: int, s: Settings, unicode: bool = True) -> str:
    return notes.full_name(midi, s.names, s.accidentals, unicode)


def string_labels(s: Settings, unicode: bool = True) -> list[str]:
    """Los nombres de las cuerdas de la afinación actual, de la más grave a la más aguda ([] en modo cromático)."""
    inst = s.instrument_preset()
    if not inst.tunings:
        return []
    return [note_full(m, s, unicode) for m in inst.tuning(s.tuning).midis]


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
