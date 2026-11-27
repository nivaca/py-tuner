"""La configuración del afinador, la misma para la ventana, la terminal y la línea de órdenes.

Se guarda en JSON en $XDG_CONFIG_HOME/py-tuner/settings.json (por omisión
~/.config/py-tuner/settings.json). Al leerla, un valor que falte o no sirva
se cambia por el de fábrica, sin error: un archivo editado a mano nunca
impide arrancar.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from . import instruments, interface, notes

DISPLAYS = ("both", "needle", "strobe")
# (los de display.NEEDLE_SCALES: lineal, o fina, con el centro abierto)
NEEDLE_SCALES = ("linear", "fine")
# Note offsets go up to this many cents either way
MAX_OFFSET = 50.0
# (los de strobe.MODES: vernier, la parcial más clara a 1, 2 y 4 veces; harmonics, cada banda la suya)
STROBE_MODES = ("vernier", "harmonics")


@dataclass
class Settings:
    """Everything the user can change.

    a4: reference A in Hz. instrument, tuning: the preset (tuning by name).
    string: a string index to tune against, or None for the nearest one.
    names, accidentals: how notes are written. device: the input device
    (index or part of its name; None: the default one). rate: sample rate
    (None: the device's). channel: "mix" or a channel number from 1.
    min_level: the quietest sound analysed, dBFS. learn_noise: also ignore
    what does not stand 10 dB over the room's noise, learned while nothing
    plays. smoothing: seconds the
    reading averages. periods: periods of the note in each fine frame.
    tolerance: cents within which a note counts as in tune.
    display: "both", "needle" or "strobe". strobe_mode: "vernier" (three
    speeds of the clearest partial) or "harmonics" (partials 1, 2 and 3).
    show_trace: the history of the deviation. needle_scale: "linear" or
    "fine" (the centre spread out). show_spectrum: the spectrum, with its
    peaks named. offsets: cents off equal
    temperament for each note name (C, C#, ... B), in every octave.
    transpose: semitones added to the names shown (a B-flat instrument: 2).
    capo: the fret of a capo, which raises every string. language: of the
    interface ("en", "es"; "" follows the system's). custom_tunings: the
    user's own.
    """

    a4: float = notes.DEFAULT_A4
    instrument: str = "chromatic"
    tuning: str = ""
    string: int | None = None
    names: str = "english"
    accidentals: str = "sharps"
    device: str | None = None
    rate: int | None = None
    channel: str = "mix"
    min_level: float = -60.0
    learn_noise: bool = True
    smoothing: float = 0.5
    periods: float = 16.0
    tolerance: float = 1.0
    display: str = "both"
    strobe_mode: str = "vernier"
    show_trace: bool = True
    needle_scale: str = "linear"
    show_spectrum: bool = False
    offsets: dict[str, float] = field(default_factory=dict)
    transpose: int = 0
    capo: int = 0
    language: str = ""
    custom_tunings: list[dict] = field(default_factory=list)

    def validated(self) -> Settings:
        """Una copia en la que cada valor que no sirve vuelve al de fábrica."""
        good = Settings()
        out = Settings(**asdict(self))
        checks = {
            "a4": lambda v: notes.MIN_A4 <= float(v) <= notes.MAX_A4,
            "instrument": lambda v: v in instruments.keys(),
            "tuning": lambda v: isinstance(v, str),
            "string": lambda v: v is None or (isinstance(v, int) and v >= 0),
            "names": lambda v: v in notes.NAME_SYSTEMS,
            "accidentals": lambda v: v in notes.ACCIDENTALS,
            "device": lambda v: v is None or isinstance(v, str),
            "rate": lambda v: v is None or (isinstance(v, int) and 8000 <= v <= 384000),
            "channel": lambda v: v == "mix" or (str(v).isdigit() and int(v) >= 1),
            "min_level": lambda v: -120 <= float(v) <= 0,
            "learn_noise": lambda v: isinstance(v, bool),
            "smoothing": lambda v: 0.05 <= float(v) <= 5,
            "periods": lambda v: 4 <= float(v) <= 64,
            "tolerance": lambda v: 0.1 <= float(v) <= 50,
            "display": lambda v: v in DISPLAYS,
            "strobe_mode": lambda v: v in STROBE_MODES,
            "show_trace": lambda v: isinstance(v, bool),
            "needle_scale": lambda v: v in NEEDLE_SCALES,
            "show_spectrum": lambda v: isinstance(v, bool),
            "offsets": lambda v: isinstance(v, dict) and all(
                k in notes.OFFSET_NAMES and -MAX_OFFSET <= float(c) <= MAX_OFFSET for k, c in v.items()),
            "transpose": lambda v: isinstance(v, int) and not isinstance(v, bool) and -12 <= v <= 12,
            "capo": lambda v: isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 12,
            "language": lambda v: v == "" or v in interface.names(),
            "custom_tunings": lambda v: isinstance(v, list) and all(isinstance(e, dict) for e in v),
        }
        for f in fields(Settings):
            value = getattr(out, f.name)
            try:
                ok = checks[f.name](value)
            except (TypeError, ValueError):
                ok = False
            if not ok:
                setattr(out, f.name, getattr(good, f.name))
        for name in ("a4", "min_level", "smoothing", "periods", "tolerance"):
            setattr(out, name, float(getattr(out, name)))
        # (sin las de cero, y en el orden de la escala)
        out.offsets = {k: round(float(out.offsets[k]), 2) for k in notes.OFFSET_NAMES
                       if k in out.offsets and float(out.offsets[k]) != 0}
        out.channel = str(out.channel)
        return out

    def instrument_preset(self) -> instruments.Instrument:
        """The chosen instrument, with the user's tunings for it."""
        return instruments.with_custom(instruments.find(self.instrument), self.custom_tunings)


def path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "py-tuner" / "settings.json"


def load(where: Path | None = None) -> Settings:
    """La configuración guardada, o la de fábrica si no la hay (o no se puede leer)."""
    where = where or path()
    try:
        data = json.loads(where.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return Settings()
    if not isinstance(data, dict):
        return Settings()
    known = {f.name for f in fields(Settings)}
    return Settings(**{k: v for k, v in data.items() if k in known}).validated()


def save(settings: Settings, where: Path | None = None) -> None:
    """Escribe SETTINGS mediante un archivo temporal, para que un fallo nunca deje medio archivo."""
    where = where or path()
    where.parent.mkdir(parents=True, exist_ok=True)
    tmp = where.with_suffix(".tmp")
    tmp.write_text(json.dumps(asdict(settings), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(where)
