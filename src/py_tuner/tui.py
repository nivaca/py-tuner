"""La interfaz de terminal a pantalla completa, con curses.

Muestra la nota en letras grandes, la frecuencia y los cents, una aguja de
texto, un estroboscopio de tres bandas, las cuerdas del instrumento y el
nivel de entrada. Con las teclas se cambian el La de referencia, el
instrumento, la afinación, la cuerda, los nombres de las notas y la vista;
cada cambio se guarda en la configuración.
"""

from __future__ import annotations

import curses
import time
from dataclasses import replace

from . import display, instruments, interface, notes
from . import settings as settings_mod
from .interface import tr
from .settings import Settings
from .tuner import LiveTuner, Reading

# La ayuda de las teclas, en dos mitades (en inglés: las claves de su traducción)
KEYS = ("q quit   ←→ A4 ±0.1 Hz   ↑↓ A4 ±1 Hz   0 A4 = 440",
        "i instrument   t tuning   s string   c capo   n names   b accidentals   v view   m strobe   h history   "
        "f spectrum   g scale   r response   p tone   l language")

# Las teclas, una por fila, para la página de manual y el manual (en inglés: las claves de su traducción)
KEY_ROWS = (
    ("q", "Quit"),
    ("\u2190 / \u2192", "Lower / raise the reference A4 by 0.1 Hz"),
    ("\u2193 / \u2191", "Lower / raise the reference A4 by 1 Hz"),
    ("0", "Put the reference A4 back to 440 Hz"),
    ("i", "The next instrument"),
    ("t", "The next tuning of the instrument"),
    ("s", "Lock the next string (after the last one, back to the nearest string)"),
    ("n", "The next system of note names: English, Latin, German"),
    ("b", "Sharps, flats or both"),
    ("v", "Needle and strobe, the needle alone or the strobe alone"),
    ("m", "The strobe: vernier (one partial, three speeds) or harmonics (partials 1, 2, 3)"),
    ("h", "Show or hide the history of the deviation"),
    ("c", "Move the capo one fret up (after the 7th, off)"),
    ("f", "Show or hide the spectrum, with its peaks named"),
    ("g", "The needle's scale: linear, or fine (the centre spread out)"),
    ("r", "The response: normal, or steady (for the double bass)"),
    ("p", "Play the reference tone: the locked string, or the note shown, or A4"),
    ("l", "The next language of the interface"),
)

# Letras de cinco filas para la nota: las que piden los nombres en inglés,
# latín y alemán (en mayúsculas), las cifras de la octava y las alteraciones.
_FONT = {
    "A": [" ██ ", "█  █", "████", "█  █", "█  █"],
    "B": ["███ ", "█  █", "███ ", "█  █", "███ "],
    "C": [" ███", "█   ", "█   ", "█   ", " ███"],
    "D": ["███ ", "█  █", "█  █", "█  █", "███ "],
    "E": ["████", "█   ", "███ ", "█   ", "████"],
    "F": ["████", "█   ", "███ ", "█   ", "█   "],
    "G": [" ███", "█   ", "█ ██", "█  █", " ███"],
    "H": ["█  █", "█  █", "████", "█  █", "█  █"],
    "I": ["███", " █ ", " █ ", " █ ", "███"],
    "L": ["█   ", "█   ", "█   ", "█   ", "████"],
    "M": ["█   █", "██ ██", "█ █ █", "█   █", "█   █"],
    "O": [" ██ ", "█  █", "█  █", "█  █", " ██ "],
    "R": ["███ ", "█  █", "███ ", "█ █ ", "█  █"],
    "S": [" ███", "█   ", " ██ ", "   █", "███ "],
    "0": [" ██ ", "█  █", "█  █", "█  █", " ██ "],
    "1": [" █ ", "██ ", " █ ", " █ ", "███"],
    "2": ["███ ", "   █", " ██ ", "█   ", "████"],
    "3": ["███ ", "   █", " ██ ", "   █", "███ "],
    "4": ["█  █", "█  █", "████", "   █", "   █"],
    "5": ["████", "█   ", "███ ", "   █", "███ "],
    "6": [" ██ ", "█   ", "███ ", "█  █", " ██ "],
    "7": ["████", "   █", "  █ ", " █  ", " █  "],
    "8": [" ██ ", "█  █", " ██ ", "█  █", " ██ "],
    "9": [" ██ ", "█  █", " ███", "   █", " ██ "],
    notes.SHARP: [" █ █", "█████", " █ █", "█████", " █ █"],
    notes.FLAT: ["█   ", "█   ", "███ ", "█  █", "███ "],
    "-": ["   ", "   ", "███", "   ", "   "],
    "/": ["    █", "   █ ", "  █  ", " █   ", "█    "],
    " ": ["  ", "  ", "  ", "  ", "  "],
}


def big(text: str) -> list[str]:
    """TEXT in the five-row block font (unknown characters are skipped)."""
    rows = [""] * 5
    for ch in text.upper() if text else "":
        glyph = _FONT.get(ch) or _FONT.get(ch.upper())
        if glyph is None:
            continue
        width = max(len(g) for g in glyph)
        for i in range(5):
            rows[i] += glyph[i].ljust(width) + " "
    return rows


def wrap_keys(halves: list[str], width: int) -> list[str]:
    """The help of the keys in as few lines of WIDTH as it fits, never breaking one key from what it does
    (the items are separated by three spaces)."""
    items = [item for half in halves for item in half.split("   ") if item]
    lines: list[str] = []
    for item in items:
        if lines and len(lines[-1]) + 3 + len(item) <= width:
            lines[-1] += "   " + item
        else:
            lines.append(item)
    return lines


def needle_row(cents: float | None, width: int, scale: str = "linear") -> tuple[str, int | None]:
    """The scale line and the column of the needle (None without a note), on the SCALE of display.py."""
    width = max(11, width | 1)
    half = width // 2
    cells = ["─"] * width
    for c, major in display.needle_ticks(scale):
        if major:
            cells[half + round(display.needle_fraction(c, scale) * half)] = "┼" if c == 0 else "┬"
    if cents is None:
        return "".join(cells), None
    pos = half + round(display.needle_fraction(cents, scale) * half)
    return "".join(cells), pos


def trace_rows(history: list[float | None], width: int, tolerance: float) -> list[str]:
    """The history of the deviation as five rows of text, the newest at the right: more than five tolerances
    sharp, sharp, in tune, flat, more than five flat. A column without a note is blank but for a dot in tune."""
    rows = [[" "] * width for _ in range(5)]
    recent = history[-width:]
    start = width - len(recent)
    for x, c in enumerate(recent, start):
        if c is None:
            rows[2][x] = "\u00b7"
            continue
        if c > 5 * tolerance:
            band = 0
        elif c > tolerance:
            band = 1
        elif c >= -tolerance:
            band = 2
        elif c >= -5 * tolerance:
            band = 3
        else:
            band = 4
        rows[band][x] = "\u2022"
    return ["".join(r) for r in rows]


BARS = "\u2581\u2582\u2583\u2584\u2585\u2586\u2587\u2588"


def spectrum_rows(samples, rate: float, width: int, s: Settings) -> list[str]:
    """The spectrum as one row of bars (log frequency, the loudest 60 dB), and a row naming its clearest peaks."""
    freqs, levels = display.spectrum(samples, rate, points=max(10, width))
    if not levels:
        return [" " * width, ""]
    top = max(levels)
    bars = "".join(BARS[max(0, min(7, int((db - top + 60) / 60 * 8)))] if db > top - 60 else " "
                   for db in levels)
    named = "   ".join(display.peak_label(f, s) for f, _ in display.peaks(samples, rate, most=4))
    return [bars[:width], (tr("peaks") + "  " + named)[:width] if named else ""]


def strobe_row(phase: float, width: int, period: int = 8) -> str:
    shift = phase * period
    return "".join("█" if ((x - shift) % period) < period / 2 else " " for x in range(width))


class App:
    def __init__(self, screen, live: LiveTuner) -> None:
        self.screen = screen
        self.live = live
        self.strobe = display.Strobe()
        self.follower = display.Follower()
        self.history: list[float | None] = []  # la desviación, diez veces por segundo
        self.needle: float | None = None  # where the needle is drawn, which follows the reading with some lag
        self.sampled = 0.0
        self.message = ""
        self.last = time.monotonic()
        curses.curs_set(0)
        screen.nodelay(True)
        screen.keypad(True)
        self.colors = curses.has_colors()
        if self.colors:
            curses.start_color()
            curses.use_default_colors()
            curses.init_pair(1, curses.COLOR_GREEN, -1)
            curses.init_pair(2, curses.COLOR_YELLOW, -1)
            curses.init_pair(3, curses.COLOR_RED, -1)
            curses.init_pair(4, curses.COLOR_CYAN, -1)

    @property
    def s(self) -> Settings:
        return self.live.settings

    def color(self, r: Reading) -> int:
        if not self.colors or not r.active:
            return 0
        if r.in_tune:
            return curses.color_pair(1) | curses.A_BOLD
        return curses.color_pair(2 if abs(r.cents) <= 5 * self.s.tolerance else 3) | curses.A_BOLD

    def change(self, **values) -> None:
        new = replace(self.s, **values).validated()
        self.live.configure(new)
        settings_mod.save(new)

    def key(self, ch: int) -> bool:
        """Acts on one key; False to quit."""
        s = self.s
        if ch in (ord("q"), ord("Q")):
            return False
        steps = {curses.KEY_RIGHT: 0.1, curses.KEY_LEFT: -0.1, curses.KEY_UP: 1.0, curses.KEY_DOWN: -1.0}
        if ch in steps:
            self.change(a4=round(min(notes.MAX_A4, max(notes.MIN_A4, s.a4 + steps[ch])), 1))
        elif ch == ord("0"):
            self.change(a4=notes.DEFAULT_A4)
        elif ch == ord("i"):
            keys = instruments.keys()
            key = keys[(keys.index(s.instrument) + 1) % len(keys)]
            inst = instruments.with_custom(instruments.find(key), s.custom_tunings)
            self.change(instrument=key, tuning=inst.tunings[0].name if inst.tunings else "", string=None)
        elif ch == ord("t"):
            inst = s.instrument_preset()
            if inst.tunings:
                names = [t.name for t in inst.tunings]
                now = inst.tuning(s.tuning).name
                self.change(tuning=names[(names.index(now) + 1) % len(names)], string=None)
        elif ch == ord("s"):
            count = len(display.string_labels(s))
            if count:
                nxt = 0 if s.string is None else s.string + 1
                self.change(string=None if nxt >= count else nxt)
        elif ch == ord("n"):
            systems = notes.NAME_SYSTEMS
            self.change(names=systems[(systems.index(s.names) + 1) % len(systems)])
        elif ch == ord("b"):
            kinds = notes.ACCIDENTALS
            self.change(accidentals=kinds[(kinds.index(s.accidentals) + 1) % len(kinds)])
        elif ch == ord("l"):
            codes = list(interface.names())
            now = interface.current()
            code = codes[(codes.index(now) + 1) % len(codes)] if now in codes else codes[0]
            interface.use(code)
            self.change(language=code)
        elif ch == ord("v"):
            views = settings_mod.DISPLAYS
            self.change(display=views[(views.index(s.display) + 1) % len(views)])
        elif ch == ord("m"):
            modes = settings_mod.STROBE_MODES
            self.change(strobe_mode=modes[(modes.index(s.strobe_mode) + 1) % len(modes)])
        elif ch == ord("h"):
            self.change(show_trace=not s.show_trace)
        elif ch == ord("c"):
            self.change(capo=0 if s.capo >= 7 else s.capo + 1)
        elif ch == ord("f"):
            self.change(show_spectrum=not s.show_spectrum)
        elif ch == ord("g"):
            scales = settings_mod.NEEDLE_SCALES
            self.change(needle_scale=scales[(scales.index(s.needle_scale) + 1) % len(scales)])
        elif ch == ord("r"):
            kinds = settings_mod.RESPONSES
            self.change(response=kinds[(kinds.index(s.response) + 1) % len(kinds)])
        elif ch == ord("p"):
            self.play_tone()
        return True

    def play_tone(self) -> None:
        """The reference tone: the locked string, or the note shown, or A4."""
        from . import tone

        s, r, tuner = self.s, self.live.reading, self.live.tuner
        if s.string is not None and tuner.string_midis and s.string < len(tuner.string_midis):
            midi = tuner.string_midis[s.string]
        elif r.active:
            midi = r.target_midi
        else:
            midi = 69
        freq = tuner.target_frequency(midi)
        try:
            tone.play(freq)
            self.message = tr("{note}: {frequency} Hz", note=display.note_full(midi, s),
                              frequency=display.freq_text(freq))
        except Exception as exc:  # noqa: BLE001 (PortAudio levanta varios tipos)
            self.message = tr("cannot play the tone: {error}", error=exc)

    def put(self, y: int, x: int, text: str, attr: int = 0) -> None:
        h, w = self.screen.getmaxyx()
        if 0 <= y < h and x < w:
            try:
                self.screen.addstr(y, max(0, x), text[: max(0, w - max(0, x) - 1)], attr)
            except curses.error:
                pass

    def centre(self, y: int, text: str, attr: int = 0) -> None:
        _, w = self.screen.getmaxyx()
        self.put(y, (w - len(text)) // 2, text, attr)

    def draw(self) -> None:
        r = self.live.reading
        s = self.s
        now = time.monotonic()
        model = self.strobe.advance(r.cents if r.active else None, now - self.last)
        # las bandas del estroboscopio de verdad (strobe.py), si las hay; si no, el modelo
        self.follower.update(r.strobe if r.active else (), now)
        phases = self.follower.phases(now) or [(p, 1.0) for p in model]
        # la aguja sigue a la lectura con la inercia de la respuesta; aparece donde está la nota, sin barrer
        if r.active:
            start = r.cents if self.needle is None else self.needle
            self.needle = display.follow(start, r.cents, now - self.last, s.response)
        else:
            self.needle = None
        self.last = now
        scr = self.screen
        scr.erase()
        h, w = scr.getmaxyx()
        y = 0
        self.put(y, 1, "py-tuner", curses.A_BOLD)
        self.put(y, 11, display.summary(s))
        y += 2
        attr = self.color(r)
        label = display.note_full(r.target_midi, s) if r.active else "--"
        for row in big(label):
            self.centre(y, row, attr)
            y += 1
        y += 1
        if r.active:
            info = tr("{frequency} Hz    target {target} Hz    {cents} cents",
                      frequency=display.freq_text(r.frequency), target=display.freq_text(r.target_frequency),
                      cents=display.cents_text(r))
            if r.in_tune:
                info += "    " + tr("in tune")
        else:
            info = tr("play a note")
        self.centre(y, info, attr if r.active else curses.A_DIM)
        y += 2
        width = min(w - 4, 81)
        left = (w - width) // 2
        if s.display in ("both", "needle"):
            scale, pos = needle_row(self.needle, width, s.needle_scale)
            self.put(y, left - 1, "-50", curses.A_DIM)
            self.put(y, left + width - 2, "+50", curses.A_DIM)
            self.put(y + 1, left, scale, curses.A_DIM)
            if pos is not None:
                self.put(y + 2, left + pos, "▲", attr)
                self.put(y + 1, left + pos, "█", attr)
            y += 4
        if s.display in ("both", "strobe"):
            for i, (phase, alpha) in enumerate(phases):
                row = strobe_row(phase, width) if r.active else " " * width
                # (una banda que se apaga, en la terminal, se atenúa)
                self.put(y + i, left, row, attr if r.active and alpha >= 0.5 else curses.A_DIM)
            y += len(phases) + 1
        if now - self.sampled >= 0.1:
            self.sampled = now
            self.history.append(r.cents if r.active else None)
            del self.history[:-max(1, width)]
        if s.show_trace:
            for i, row in enumerate(trace_rows(self.history, width, s.tolerance)):
                # (de arriba abajo: muy alta, alta, afinada, baja, muy baja; con los colores de la aguja)
                colour = (3, 2, 1, 2, 3)[i]
                self.put(y + i, left, row, curses.color_pair(colour) if self.colors else 0)
            y += 6
        if s.show_spectrum:
            src = self.live.source
            for i, row in enumerate(spectrum_rows(src.buffer.latest(display.SPECTRUM_SAMPLES), src.rate, width, s)):
                self.put(y + i, left, row, curses.A_DIM if i else 0)
            y += 3
        labels = display.string_labels(s)
        if labels:
            x = left
            label = tr("strings") + " "
            self.put(y, x, label, curses.A_DIM)
            x += len(label)
            for i, lab in enumerate(labels):
                a = curses.A_REVERSE if r.active and r.string == i else 0
                if s.string == i:
                    a |= curses.A_UNDERLINE
                if a & curses.A_REVERSE and r.in_tune and self.colors:
                    a |= curses.color_pair(1)
                self.put(y, x, f" {lab} ", a)
                x += len(lab) + 3
            self.put(y, x + 1, tr("(auto)") if s.string is None else tr("(locked)"), curses.A_DIM)
            y += 2
        level = r.level if r.level > -120 else -120
        bar = max(0, min(30, round((level + 90) / 90 * 30)))
        self.put(y, left, f"{tr('level'):8}" + "█" * bar + "░" * (30 - bar) + f" {level:5.0f} dBFS", curses.A_DIM)
        # la ayuda de las teclas, en una línea si cabe y si no en dos
        keys = wrap_keys([tr(k) for k in KEYS], w - 2)
        for i, text in enumerate(keys):
            self.put(h - len(keys) + i, 1, text, curses.A_DIM)
        err = self.live.error or getattr(self.live.source, "error", None)
        if err:
            self.put(h - len(keys) - 1, 1, err, curses.color_pair(3) if self.colors else 0)
        elif self.message:
            # (lo que dijo la última tecla, como el tono que suena)
            self.put(h - len(keys) - 1, 1, self.message, curses.A_DIM)
        scr.refresh()

    def loop(self) -> None:
        while True:
            ch = self.screen.getch()
            while ch != -1:
                if not self.key(ch):
                    return
                ch = self.screen.getch()
            self.draw()
            time.sleep(1 / 30)


def run(s: Settings, file: str | None = None) -> int:
    import sys

    from .app import open_source

    try:
        source = open_source(s, file)
        live = LiveTuner(s, source)
        live.start()
    except Exception as exc:  # noqa: BLE001 (PortAudio levanta varios tipos)
        print("py-tuner: " + tr("cannot open the input: {error}", error=exc), file=sys.stderr)
        return 1
    try:
        curses.wrapper(lambda scr: App(scr, live).loop())
    except KeyboardInterrupt:
        pass
    finally:
        live.stop()
    return 0
