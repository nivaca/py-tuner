#!/usr/bin/env python3
"""Mide el afinador con grabaciones reales: cuántas notas falsas da y cuán exacto es.

    uv run python tools/evaluate.py [CARPETA ...] [--instrument guitar] [--shifts -30,-7,13,45]

Para cada archivo WAV de las CARPETAS (por omisión local-only/tuneo/notebooks, que no está en el repositorio):

- las notas que oye (como `py-tuner cli --file`), y cuáles no son las que el nombre del archivo dice que suenan
  (6th_E es el Mi grave de una guitarra, 5th_A el La, 4th_D o D_4th el Re, 1st_E el Mi agudo; un nombre sin
  cuerda no dice nada): esas son notas falsas, y se cuentan con su duración;
- la exactitud sin conocer la afinación del instrumento, como en sandbox/recordings de Strobie (Davorin Šego):
  la misma grabación, declarada a otra frecuencia de muestreo, suena tantos cents más alta o más baja como se
  quiera, sin tocar una muestra. Las lecturas de cada versión desplazada deben apartarse de las del original
  justo esos cents; lo que no, es error del afinador.

Al final, los totales. Sirve para comparar un cambio del detector con el anterior; no es una prueba (las
grabaciones no se pueden distribuir con el programa).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from py_tuner import notes  # noqa: E402
from py_tuner.audio import read_wav  # noqa: E402
from py_tuner.cli import notes_in  # noqa: E402
from py_tuner.settings import Settings  # noqa: E402
from py_tuner.tuner import Tuner  # noqa: E402

DEFAULT = ROOT / "local-only" / "tuneo" / "notebooks"
# Las cuerdas de la guitarra por su número, como las nombran los archivos
# Una nota es falsa si su frecuencia queda a más de esto de toda nota que debía sonar (las cuerdas de una
# grabación pueden estar desafinadas, pero no un semitono)
FALSE_CENTS = 120
GUITAR = {"6th": "E2", "5th": "A2", "4th": "D3", "3rd": "G3", "2nd": "B3", "1st": "E4"}
HOP = 1200  # muestras entre lecturas, iguales en todas las versiones desplazadas


def expected(name: str) -> set[int] | None:
    """The notes the file name says are played, or None if it says nothing."""
    for token in re.split(r"[_\-. ]", name):
        if token.lower() in GUITAR:
            return {notes.parse(GUITAR[token.lower()])}
    if "all" in name.lower():
        return {notes.parse(n) for n in GUITAR.values()}
    return None


def readings(samples: np.ndarray, rate: float, settings: Settings) -> list:
    """Readings every HOP samples (the same positions whatever the declared RATE)."""
    tuner = Tuner(settings, int(round(rate)))
    tuner.rate = rate
    tuner.configure(settings)
    out = []
    for end in range(HOP, len(samples) + 1, HOP):
        start = max(0, end - tuner.history)
        out.append(tuner.analyze(samples[start:end], end / rate))
    return out


def evaluate(path: Path, settings: Settings, shifts: list[float]) -> dict:
    rate, samples = read_wav(path)
    base = readings(samples, rate, settings)
    found = notes_in(base)
    want = expected(path.stem)
    false = [n for n in found if want is not None
             and min(abs(1200 * np.log2(n["frequency"] / notes.frequency(m))) for m in want) > FALSE_CENTS]
    errors = []
    for c in shifts:
        shifted = readings(samples, rate * 2 ** (c / 1200), settings)
        for a, b in zip(base, shifted):
            # (las dos deben haber oído la misma nota, desplazada)
            if a.active and b.active and a.target_midi is not None and b.target_midi is not None:
                errors.append(1200 * np.log2(b.frequency / a.frequency) - c)
    return {"name": path.name, "found": found, "false": false, "errors": np.array(errors)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="tools/evaluate.py",
                                     description="Measure the tuner on real recordings: false notes and accuracy.")
    parser.add_argument("folders", nargs="*", type=Path, default=[DEFAULT])
    parser.add_argument("-i", "--instrument", default="guitar")
    parser.add_argument("--shifts", default="-30,-7,13,45", help="cents the recordings are shifted by")
    parser.add_argument("-v", "--verbose", action="store_true", help="list every note found")
    args = parser.parse_args(argv)
    settings = Settings(instrument=args.instrument, tuning="Standard" if args.instrument != "chromatic" else "")
    shifts = [float(c) for c in args.shifts.split(",") if c]
    files = sorted(p for folder in args.folders for p in folder.glob("*.wav"))
    if not files:
        print("evaluate.py: no WAV files", file=sys.stderr)
        return 1
    all_errors, false_count, false_time, mixed = [], 0, 0.0, 0
    for path in files:
        r = evaluate(path, settings, shifts)
        e = r["errors"]
        # (una lectura desplazada que oyó otra nota no mide la precisión: se cuenta aparte)
        mixed += int(np.sum(np.abs(e) > 50))
        e = e[np.abs(e) <= 50]
        r["errors"] = e
        f_time = sum(n["end"] - n["start"] for n in r["false"])
        false_count += len(r["false"])
        false_time += f_time
        all_errors.append(e)
        acc = (f"median {np.median(np.abs(e)):.3f}, 95% {np.percentile(np.abs(e), 95):.2f} cents"
               if len(e) else "no readings")
        print(f"{r['name']:24} notes {len(r['found']):2}  false {len(r['false'])} ({f_time:4.2f} s)  shift error {acc}")
        if args.verbose or r["false"]:
            for n in r["found"]:
                mark = "  FALSE" if n in r["false"] else ""
                print(f"    {n['start']:6.2f}-{n['end']:6.2f} s  {notes.full_name(n['midi'])} "
                      f"{n['frequency']:8.3f} Hz  {n['cents']:+7.2f} cents{mark}")
    e = np.concatenate(all_errors) if all_errors else np.array([])
    print(f"\nTotal: {false_count} false notes ({false_time:.2f} s); {mixed} shifted readings of another note; "
          f"shift error median {np.median(np.abs(e)):.3f}, 95% {np.percentile(np.abs(e), 95):.2f}, "
          f"max {np.max(np.abs(e)):.2f} cents over {len(e)} readings")
    return 0


if __name__ == "__main__":
    sys.exit(main())
