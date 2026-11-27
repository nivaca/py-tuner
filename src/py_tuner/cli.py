"""La línea de órdenes: una línea de texto que se reescribe, o un informe de un archivo.

En vivo, la lectura se reescribe en su propia línea (en una terminal) o sale
una línea por cuarto de segundo (en una tubería). Con un archivo WAV y sin
--realtime, el archivo se analiza de una vez y sale una línea por cada nota
que suene en él, con su frecuencia y su desviación.
"""

from __future__ import annotations

import statistics
import sys
import time

from . import display
from .settings import Settings
from .tuner import LiveTuner, Reading, Tuner

# Una nota de un archivo cuenta si se sostiene al menos esto (segundos).
MIN_NOTE = 0.15
# Los primeros instantes de una cuerda pulsada suenan algo altos: se saltan.
ATTACK = 0.1


def needle(cents: float, width: int = 21) -> str:
    """A text needle: "[----------|----------]" with the mark where CENTS falls (±50)."""
    half = width // 2
    pos = half + round(max(-1.0, min(1.0, cents / display.NEEDLE_RANGE)) * half)
    cells = ["-"] * width
    cells[half] = "|"
    cells[pos] = "*" if pos != half else "#"
    return "[" + "".join(cells) + "]"


def line(r: Reading, s: Settings) -> str:
    """Una lectura como una línea de texto."""
    if not r.active:
        level = "silence" if r.level == float("-inf") else f"{r.level:.0f} dBFS"
        return f"--  (no pitch, {level})"
    name = display.note_full(r.target_midi, s)
    mark = " OK" if r.in_tune else ""
    text = (f"{name:5} {display.freq_text(r.frequency):>9} Hz  {display.cents_text(r):>6} cents  "
            f"{needle(r.cents)}{mark}")
    if r.string is not None:
        text += f"  string {r.string + 1}"
    return text


def notes_in(readings: list[Reading], min_note: float = MIN_NOTE) -> list[dict]:
    """The notes heard through READINGS: [{start, end, midi, frequency, cents, spread}],
    each from the steady part (after the attack) of a run of readings with the same target."""
    runs: list[list[Reading]] = []
    for r in readings:
        if not r.active:
            runs.append([])
            continue
        if runs and runs[-1] and runs[-1][-1].target_midi == r.target_midi:
            runs[-1].append(r)
        else:
            runs.append([r])
    found = []
    for run in runs:
        if not run or run[-1].time - run[0].time < min_note:
            continue
        steady = [r for r in run if r.time - run[0].time >= ATTACK] or run
        freq = statistics.median(r.frequency for r in steady)
        c = statistics.median(r.cents for r in steady)
        found.append({"start": run[0].time, "end": run[-1].time, "midi": run[0].target_midi,
                      "frequency": freq, "target": run[0].target_frequency, "cents": c,
                      "string": run[0].string, "spread": statistics.median(r.spread for r in steady)})
    return found


def report_file(s: Settings, path: str) -> int:
    from .audio import read_wav

    rate, samples = read_wav(path, s.channel)
    tuner = Tuner(s, rate)
    found = notes_in(tuner.analyze_all(samples))
    print(f"{path}: {len(samples) / rate:.2f} s at {rate} Hz, {display.summary(s)}")
    if not found:
        print("no steady note found")
        return 1
    for n in found:
        name = display.note_full(n["midi"], s)
        string = f"  string {n['string'] + 1}" if n["string"] is not None else ""
        print(f"{n['start']:7.2f}-{n['end']:7.2f} s  {name:5} {display.freq_text(n['frequency']):>9} Hz  "
              f"(target {display.freq_text(n['target'])})  {n['cents']:+6.2f} cents  "
              f"±{n['spread']:.2f}{string}")
    return 0


def run(s: Settings, file: str | None = None, once: bool = False, realtime: bool = False,
        out=None) -> int:
    out = out or sys.stdout
    if file and not realtime:
        return report_file(s, file)
    from .app import open_source

    try:
        source = open_source(s, file)
    except (OSError, ValueError) as exc:
        print(f"py-tuner: {exc}", file=sys.stderr)
        return 1
    live = LiveTuner(s, source)
    tty = out.isatty()
    print(display.summary(s) + "  (Ctrl+C to stop)", file=out)
    try:
        live.start()
    except Exception as exc:  # noqa: BLE001 (PortAudio levanta varios tipos)
        print(f"py-tuner: cannot open the input: {exc}", file=sys.stderr)
        return 1
    last_print = 0.0
    try:
        while True:
            time.sleep(0.05)
            r = live.reading
            if once and r.active and r.spread <= s.tolerance / 2 and r.time > 0.3:
                print(line(r, s), file=out)
                return 0
            now = time.monotonic()
            if tty:
                out.write("\r\x1b[2K" + line(r, s))
                out.flush()
            elif now - last_print >= 0.25:
                print(line(r, s), file=out, flush=True)
                last_print = now
    except KeyboardInterrupt:
        if tty:
            out.write("\n")
        return 0
    finally:
        live.stop()
