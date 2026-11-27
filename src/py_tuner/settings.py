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


@dataclass
class Settings:
    """Everything the user can change.

    a4: reference A in Hz. instrument, tuning: the preset (tuning by name).
    string: a string index to tune against, or None for the nearest one.
    names, accidentals: how notes are written. device: the input device
    (index or part of its name; None: the default one). rate: sample rate
    (None: the device's). channel: "mix" or a channel number from 1.
    min_level: the quietest sound analysed, dBFS. smoothing: seconds the
    reading averages. periods: periods of the note in each fine frame.
    tolerance: cents within which a note counts as in tune.
    display: "both", "needle" or "strobe". language: of the interface ("en",
    "es"; "" follows the system's). custom_tunings: the user's own.
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
    smoothing: float = 0.5
    periods: float = 16.0
    tolerance: float = 1.0
    display: str = "both"
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
            "smoothing": lambda v: 0.05 <= float(v) <= 5,
            "periods": lambda v: 4 <= float(v) <= 64,
            "tolerance": lambda v: 0.1 <= float(v) <= 50,
            "display": lambda v: v in DISPLAYS,
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
