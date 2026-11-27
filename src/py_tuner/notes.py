"""Las notas del temperamento igual: nombres, frecuencias y desviaciones en cents.

Todo se mide contra un La de referencia (A4) ajustable, 440 Hz por omisión.
Una nota es su número MIDI (A4 = 69, C4 = 60); de ahí salen su frecuencia, su
nombre en tres sistemas (inglés, latino y alemán) y la octava en la numeración
científica, en la que el Do central es C4.
"""

from __future__ import annotations

import math
import re

DEFAULT_A4 = 440.0
# El margen del La de referencia: de un La barroco grave a uno muy brillante.
MIN_A4 = 380.0
MAX_A4 = 480.0
# Common reference pitches, for menus.
COMMON_A4 = (415.0, 430.0, 432.0, 435.0, 438.0, 439.0, 440.0, 441.0, 442.0, 443.0, 444.0, 446.0, 466.0)

SHARP = "♯"
FLAT = "♭"

_ENGLISH_SHARPS = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
_ENGLISH_FLATS = ("C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B")
_LATIN_SHARPS = ("Do", "Do#", "Re", "Re#", "Mi", "Fa", "Fa#", "Sol", "Sol#", "La", "La#", "Si")
_LATIN_FLATS = ("Do", "Reb", "Re", "Mib", "Mi", "Fa", "Solb", "Sol", "Lab", "La", "Sib", "Si")
# En alemán, Si bemol es B y Si natural es H; los demás llevan -is o -es.
_GERMAN_SHARPS = ("C", "Cis", "D", "Dis", "E", "F", "Fis", "G", "Gis", "A", "B", "H")
_GERMAN_FLATS = ("C", "Des", "D", "Es", "E", "F", "Ges", "G", "As", "A", "B", "H")

NAME_SYSTEMS = ("english", "latin", "german")
ACCIDENTALS = ("sharps", "flats")

_TABLES = {
    ("english", "sharps"): _ENGLISH_SHARPS, ("english", "flats"): _ENGLISH_FLATS,
    ("latin", "sharps"): _LATIN_SHARPS, ("latin", "flats"): _LATIN_FLATS,
    ("german", "sharps"): _GERMAN_SHARPS, ("german", "flats"): _GERMAN_FLATS,
}

_PITCH_CLASS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11,
                "DO": 0, "RE": 2, "MI": 4, "FA": 5, "SOL": 7, "LA": 9, "SI": 11, "H": 11}
_NOTE_RE = re.compile(r"^\s*(do|re|mi|fa|sol|la|si|[a-h])\s*([#b♯♭]*)\s*(-?\d+)\s*$", re.IGNORECASE)


def check_a4(a4: float) -> float:
    """A4 as a float, or ValueError if it is outside MIN_A4..MAX_A4."""
    a4 = float(a4)
    if not (MIN_A4 <= a4 <= MAX_A4) or math.isnan(a4):
        raise ValueError(f"reference A4 must be between {MIN_A4:g} and {MAX_A4:g} Hz, not {a4:g}")
    return a4


def frequency(midi: float, a4: float = DEFAULT_A4) -> float:
    """La frecuencia en Hz de la nota MIDI (puede ser fraccionaria)."""
    return a4 * 2.0 ** ((midi - 69) / 12)


def midi_of(freq: float, a4: float = DEFAULT_A4) -> float:
    """The fractional MIDI number of FREQ (69.0 is A4 exactly)."""
    return 69 + 12 * math.log2(freq / a4)


def cents(freq: float, target: float) -> float:
    """Cuántos cents está FREQ por encima de TARGET (negativo: por debajo)."""
    return 1200 * math.log2(freq / target)


def nearest(freq: float, a4: float = DEFAULT_A4) -> int:
    """El número MIDI de la nota temperada más cercana a FREQ."""
    return round(midi_of(freq, a4))


def name(midi: int, system: str = "english", accidentals: str = "sharps", unicode: bool = True) -> str:
    """The name of the note MIDI without its octave ("A", "Sol#", "Fis")."""
    text = _TABLES[system, accidentals][midi % 12]
    if unicode and system != "german":
        # En las tablas, un "#" o una "b" minúscula al final son siempre la
        # alteración (la B mayúscula del inglés es la nota misma).
        if text.endswith("#"):
            text = text[:-1] + SHARP
        elif len(text) > 1 and text.endswith("b"):
            text = text[:-1] + FLAT
    return text


def octave(midi: int) -> int:
    """La octava de MIDI en la numeración científica (C4 = 60 está en la 4)."""
    return midi // 12 - 1


def full_name(midi: int, system: str = "english", accidentals: str = "sharps", unicode: bool = True) -> str:
    """La nota con su octava ("A4", "Mi2", "Fis3")."""
    return f"{name(midi, system, accidentals, unicode)}{octave(midi)}"


def parse(text: str) -> int:
    """The MIDI number of a note name with octave: "E2", "F#1", "Bb0", "Sol3", "H2".

    Raises ValueError for anything else.
    """
    m = _NOTE_RE.match(text)
    if not m:
        raise ValueError(f"not a note name with octave: {text!r}")
    letter, marks, octv = m.group(1).upper(), m.group(2), int(m.group(3))
    pc = _PITCH_CLASS[letter]
    for mark in marks:
        pc += 1 if mark in "#♯" else -1
    return (octv + 1) * 12 + pc
