"""Los instrumentos y sus afinaciones: guitarra, bajo, contrabajo y violín.

Cada afinación es una lista de cuerdas, de la más grave a la más aguda,
escritas como notas con octava ("E2"). El modo cromático no tiene cuerdas: la
nota de referencia es siempre la más cercana. Además de las afinaciones de
fábrica, el usuario puede añadir las suyas en la configuración.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import notes


@dataclass(frozen=True)
class Tuning:
    """Un juego de cuerdas con nombre, de la más grave a la más aguda."""

    name: str
    strings: tuple[str, ...]

    @property
    def midis(self) -> tuple[int, ...]:
        return tuple(notes.parse(s) for s in self.strings)


@dataclass(frozen=True)
class Instrument:
    """An instrument: its key (as in the settings), its name, its tunings (the
    first is the usual one) and the range its fundamental can reach, in MIDI
    numbers, for the analysis."""

    key: str
    name: str
    tunings: tuple[Tuning, ...]
    lowest: int
    highest: int

    def tuning(self, name: str | None) -> Tuning:
        """La afinación llamada NAME (sin distinguir mayúsculas), o la primera."""
        for t in self.tunings:
            if name is not None and t.name.lower() == name.lower():
                return t
        return self.tunings[0]


def _t(name: str, strings: str) -> Tuning:
    return Tuning(name, tuple(strings.split()))


# Los márgenes de análisis van algo más allá de la cuerda más grave (para
# afinar desde una cuerda floja) y de las notas agudas de cada instrumento.
INSTRUMENTS: tuple[Instrument, ...] = (
    Instrument("chromatic", "Chromatic", (), notes.parse("A0"), notes.parse("G6")),
    Instrument("guitar", "Guitar", (
        _t("Standard", "E2 A2 D3 G3 B3 E4"),
        _t("Drop D", "D2 A2 D3 G3 B3 E4"),
        _t("Half step down", "Eb2 Ab2 Db3 Gb3 Bb3 Eb4"),
        _t("Whole step down", "D2 G2 C3 F3 A3 D4"),
        _t("Drop C", "C2 G2 C3 F3 A3 D4"),
        _t("DADGAD", "D2 A2 D3 G3 A3 D4"),
        _t("Open D", "D2 A2 D3 F#3 A3 D4"),
        _t("Open G", "D2 G2 D3 G3 B3 D4"),
        _t("Open E", "E2 B2 E3 G#3 B3 E4"),
        _t("Open C", "C2 G2 C3 G3 C4 E4"),
        _t("7-string", "B1 E2 A2 D3 G3 B3 E4"),
    ), notes.parse("A1"), notes.parse("E6")),
    Instrument("bass", "Bass", (
        _t("Standard", "E1 A1 D2 G2"),
        _t("Drop D", "D1 A1 D2 G2"),
        _t("Half step down", "Eb1 Ab1 Db2 Gb2"),
        _t("5-string", "B0 E1 A1 D2 G2"),
        _t("5-string high C", "E1 A1 D2 G2 C3"),
        _t("6-string", "B0 E1 A1 D2 G2 C3"),
    ), notes.parse("A0"), notes.parse("G4")),
    Instrument("double-bass", "Double bass", (
        _t("Orchestral", "E1 A1 D2 G2"),
        _t("Solo", "F#1 B1 E2 A2"),
        _t("5-string (low B)", "B0 E1 A1 D2 G2"),
        _t("5-string (low C)", "C1 E1 A1 D2 G2"),
        _t("Fifths", "C1 G1 D2 A2"),
    ), notes.parse("A0"), notes.parse("G4")),
    Instrument("violin", "Violin", (
        _t("Standard", "G3 D4 A4 E5"),
        _t("Cross (AEAE)", "A3 E4 A4 E5"),
        _t("Scordatura GDGD", "G3 D4 G4 D5"),
    ), notes.parse("E3"), notes.parse("E7")),
)


def find(key: str) -> Instrument:
    """El instrumento de clave KEY ("guitar", "double-bass"...), o KeyError."""
    for inst in INSTRUMENTS:
        if inst.key == key:
            return inst
    raise KeyError(key)


def keys() -> tuple[str, ...]:
    return tuple(i.key for i in INSTRUMENTS)


def with_custom(inst: Instrument, custom: list[dict]) -> Instrument:
    """INST with the user's own tunings for it added after the built-in ones.

    CUSTOM is the settings' list of {"instrument": key, "name": ..., "strings":
    "E2 A2 ..."} (strings as a text or a list); entries for other instruments
    or with bad notes are skipped.
    """
    extra = []
    for entry in custom:
        if entry.get("instrument") != inst.key:
            continue
        strings = entry.get("strings", ())
        if isinstance(strings, str):
            strings = strings.split()
        try:
            t = Tuning(str(entry["name"]), tuple(str(s) for s in strings))
            if t.strings:
                t.midis  # noqa: B018 (comprueba que las notas sean válidas)
                extra.append(t)
        except (KeyError, ValueError):
            continue
    return Instrument(inst.key, inst.name, inst.tunings + tuple(extra), inst.lowest, inst.highest)
