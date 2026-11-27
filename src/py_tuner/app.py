"""La entrada del programa: lee las opciones y arranca la ventana, la terminal o la línea de órdenes.

Las opciones comunes (La de referencia, instrumento, afinación, dispositivo,
archivo...) valen para los tres modos y pisan la configuración guardada solo
en esta sesión, salvo que se pida --save.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

from . import __version__, audio, instruments, interface, notes
from . import settings as settings_mod
from .interface import tr
from .settings import Settings

# La descripción y el epílogo de --help, en inglés (las claves de su traducción).
DESCRIPTION = ("An accurate tuner for guitar, bass, double bass and violin (and a chromatic one), "
               "with a needle and a strobe, in a window, in the terminal or on the command line.")
EPILOG = ("Without a command, the window opens. Options given here override the saved settings for this "
          "session only, unless --save is given. Settings: {path}")

MODES = ("gui", "tui", "cli", "tone", "devices", "instruments")


def shown_path(path: Path) -> str:
    """PATH con la carpeta personal escrita ~, como se lee en una ayuda."""
    try:
        return "~/" + str(path.relative_to(Path.home()))
    except ValueError:
        return str(path)


def parser() -> argparse.ArgumentParser:
    """Las opciones de la línea de órdenes, en el idioma de la interfaz."""
    p = argparse.ArgumentParser(prog="py-tuner", description=tr(DESCRIPTION),
                                epilog=tr(EPILOG, path=shown_path(settings_mod.path())), add_help=False)
    p.add_argument("-h", "--help", action="help", help=tr("show this help and quit"))
    p.add_argument("--version", action="version", version=f"py-tuner {__version__}",
                   help=tr("show the version and quit"))
    p.add_argument("mode", nargs="?", choices=MODES, default="gui",
                   help=tr("gui (the window, default), tui (full-screen terminal), cli (a line of text), "
                           "tone (play a reference note), devices (list the inputs), instruments (list the "
                           "tunings)"))
    p.add_argument("note", nargs="?", metavar=tr("NOTE"),
                   help=tr("tone: the note to play (e.g. E2), or a string number with --instrument; A4 if none"))
    g = p.add_argument_group(tr("tuning"))
    g.add_argument("-a", "--a4", type=float, metavar="HZ",
                   help=tr("reference A4 in Hz, {low} to {high} (default 440)", low=f"{notes.MIN_A4:g}",
                           high=f"{notes.MAX_A4:g}"))
    g.add_argument("-i", "--instrument", choices=instruments.keys(), help=tr("the instrument, or chromatic"))
    g.add_argument("-t", "--tuning", metavar=tr("NAME"), help=tr('the tuning, by name (e.g. "Drop D")'))
    g.add_argument("-s", "--string", metavar="N|auto",
                   help=tr("tune against string N (1 = the lowest) instead of the nearest one"))
    g.add_argument("--names", choices=notes.NAME_SYSTEMS, help=tr("note names: english, latin or german"))
    g.add_argument("--accidentals", choices=notes.ACCIDENTALS,
                   help=tr("write accidentals as sharps, flats or both (F#/Gb)"))
    g.add_argument("--flats", dest="accidentals", action="store_const", const="flats",
                   help=tr("write accidentals as flats"))
    g.add_argument("--sharps", dest="accidentals", action="store_const", const="sharps",
                   help=tr("write accidentals as sharps"))
    g.add_argument("--tolerance", type=float, metavar="CENTS",
                   help=tr("in tune within this many cents (default 1)"))
    g = p.add_argument_group(tr("input"))
    g.add_argument("-d", "--device", metavar="DEV", help=tr("input device: its number or part of its name"))
    g.add_argument("-r", "--rate", type=int, metavar="HZ", help=tr("sample rate (default: the device's)"))
    g.add_argument("-c", "--channel", metavar="mix|N", help=tr("use channel N (from 1) or the mix of all"))
    g.add_argument("-f", "--file", metavar="WAV", help=tr("read a WAV file instead of the sound card"))
    g.add_argument("--min-level", type=float, metavar="DBFS",
                   help=tr("ignore sounds quieter than this (default -60)"))
    g.add_argument("--learn-noise", dest="learn_noise", action="store_const", const=True,
                   help=tr("also ignore what does not stand 10 dB over the room's noise, learned while nothing "
                           "plays (the default)"))
    g.add_argument("--no-learn-noise", dest="learn_noise", action="store_const", const=False,
                   help=tr("only the fixed level of --min-level"))
    g.add_argument("--smoothing", type=float, metavar="SECONDS",
                   help=tr("seconds the reading averages (default 0.5)"))
    g.add_argument("--periods", type=float, metavar="N",
                   help=tr("periods per analysis frame: more is steadier, fewer is faster (default 16)"))
    g.add_argument("--response", choices=settings_mod.RESPONSES,
                   help=tr("normal, or steady: the attack of each pluck left out, a longer average and a slower "
                           "needle, for the double bass (default normal)"))
    g = p.add_argument_group(tr("output"))
    g.add_argument("--offset", action="append", metavar=tr("NOTE=CENTS"),
                   help=tr("tune a note name this many cents off equal temperament, in every octave (e.g. B=-2; "
                           "B=0 removes it); may be repeated"))
    g.add_argument("--transpose", type=int, metavar=tr("SEMITONES"),
                   help=tr("show the names transposed, for a transposing instrument (e.g. 2 for B-flat)"))
    g.add_argument("--capo", type=int, metavar=tr("FRET"), help=tr("a capo at this fret raises every string"))
    g.add_argument("--display", choices=settings_mod.DISPLAYS, help=tr("needle, strobe or both (gui, tui)"))
    g.add_argument("--strobe", dest="strobe_mode", choices=settings_mod.STROBE_MODES,
                   help=tr("the strobe: vernier (the clearest partial at three speeds) or harmonics (partials "
                           "1, 2 and 3)"))
    g.add_argument("--trace", dest="show_trace", action="store_const", const=True,
                   help=tr("show the history of the deviation (gui, tui)"))
    g.add_argument("--no-trace", dest="show_trace", action="store_const", const=False,
                   help=tr("hide the history of the deviation"))
    g.add_argument("--spectrum", dest="show_spectrum", action="store_const", const=True,
                   help=tr("show the spectrum, with its peaks named (gui, tui)"))
    g.add_argument("--no-spectrum", dest="show_spectrum", action="store_const", const=False,
                   help=tr("hide the spectrum"))
    g.add_argument("--needle", dest="needle_scale", choices=settings_mod.NEEDLE_SCALES,
                   help=tr("the needle's scale: linear, or fine (the centre spread out)"))
    g.add_argument("--language", choices=list(interface.names()),
                   help=tr("the language of the interface (default: the system's)"))
    g.add_argument("--once", action="store_true", help=tr("cli: print the first steady reading and exit"))
    g.add_argument("--realtime", action="store_true",
                   help=tr("cli with --file: play the file at its own pace instead of analysing it at once"))
    g.add_argument("--save", action="store_true", help=tr("save the options given as the new settings"))
    return p


def apply(args: argparse.Namespace, base: Settings) -> Settings:
    """BASE with the options of ARGS that were given; ValueError for bad ones."""
    s = replace(base)
    if args.a4 is not None:
        try:
            s.a4 = notes.check_a4(args.a4)
        except ValueError:
            raise ValueError(tr("reference A4 must be between {low} and {high} Hz, not {value}",
                                low=f"{notes.MIN_A4:g}", high=f"{notes.MAX_A4:g}", value=f"{args.a4:g}")) from None
    if args.instrument is not None and args.instrument != s.instrument:
        s.instrument = args.instrument
        s.string = None
        inst = s.instrument_preset()
        s.tuning = inst.tunings[0].name if inst.tunings else ""
    if args.tuning is not None:
        inst = s.instrument_preset()
        # (vale el nombre en inglés o en el idioma de la interfaz)
        wanted = args.tuning.lower()
        match = [t.name for t in inst.tunings if wanted in (t.name.lower(), tr(t.name).lower())]
        if not match:
            names = ", ".join(tr(t.name) for t in inst.tunings) or tr("none (chromatic)")
            raise ValueError(tr("{instrument} has no tuning {tuning}; it has: {names}", instrument=tr(inst.name),
                                tuning=repr(args.tuning), names=names))
        s.tuning = match[0]
        s.string = None
    if args.string is not None:
        if args.string.lower() == "auto":
            s.string = None
        else:
            inst = s.instrument_preset()
            count = len(inst.tuning(s.tuning).strings) if inst.tunings else 0
            if not args.string.isdigit() or not 1 <= int(args.string) <= count:
                raise ValueError(tr("--string must be auto or 1..{count}", count=count) if count
                                 else tr("--string needs an instrument with strings"))
            s.string = int(args.string) - 1
    if args.names is not None:
        s.names = args.names
    if args.accidentals is not None:
        s.accidentals = args.accidentals
    if args.offset:
        offsets = dict(s.offsets)
        for item in args.offset:
            name, _, value = item.partition("=")
            try:
                key = notes.OFFSET_NAMES[notes.parse(name.strip() + "4") % 12]
                cents = float(value)
            except ValueError:
                raise ValueError(tr("--offset needs NOTE=CENTS, e.g. B=-2, not {value}", value=item)) from None
            if not -settings_mod.MAX_OFFSET <= cents <= settings_mod.MAX_OFFSET:
                raise ValueError(tr("--offset {value}: at most {most} cents either way", value=item,
                                    most=f"{settings_mod.MAX_OFFSET:g}"))
            offsets[key] = cents
        s.offsets = offsets
    for name, low, high in (("transpose", -12, 12), ("capo", 0, 12)):
        value = getattr(args, name)
        if value is not None and not low <= value <= high:
            raise ValueError(tr("--{option} must be from {low} to {high}", option=name, low=low, high=high))
    for name in ("tolerance", "device", "rate", "min_level", "smoothing", "periods", "display", "language",
                 "strobe_mode", "show_trace", "transpose", "capo", "show_spectrum", "needle_scale",
                 "learn_noise", "response"):
        value = getattr(args, name)
        if value is not None:
            setattr(s, name, value)
    if args.channel is not None:
        if args.channel != "mix" and not args.channel.isdigit():
            raise ValueError(tr("--channel must be mix or a number from 1"))
        s.channel = args.channel
    checked = s.validated()
    for name in ("tolerance", "rate", "min_level", "smoothing", "periods"):
        if getattr(args, name) is not None and getattr(checked, name) != getattr(s, name):
            raise ValueError(tr("--{option} {value} is out of range", option=name.replace("_", "-"),
                                value=getattr(args, name)))
    return checked


def open_source(s: Settings, file: str | None, realtime: bool = True) -> audio.Source:
    """La fuente de sonido para S: el archivo (servido en tiempo real) o el dispositivo."""
    # El búfer guarda más de lo que el análisis más largo pide.
    seconds = 4.0 + s.periods / 10
    if file:
        return audio.FileSource(file, seconds, s.channel)
    return audio.MicSource(seconds, s.device, s.rate, s.channel)


def tone_target(s: Settings, note: str | None) -> tuple[str, float]:
    """(name, frequency) of the reference tone: NOTE (a name, or a string number of the instrument), the locked
    string, or A4; tuned as the tuner tunes it (A4, the offsets, the capo)."""
    from .tuner import Tuner

    tuner = Tuner(s, 48000)
    if note is None and s.string is not None and tuner.string_midis:
        midi = tuner.string_midis[s.string]
    elif note is not None and note.isdigit() and tuner.string_midis:
        if not 1 <= int(note) <= len(tuner.string_midis):
            raise ValueError(tr("--string must be auto or 1..{count}", count=len(tuner.string_midis)))
        midi = tuner.string_midis[int(note) - 1]
    else:
        midi = notes.parse(note) if note else 69
    from . import display

    return display.note_full(midi, s), tuner.target_frequency(midi)


def play_tone(s: Settings, note: str | None, seconds: float = 3.0) -> int:
    try:
        name, freq = tone_target(s, note)
    except ValueError as exc:
        print(f"py-tuner: {exc}", file=sys.stderr)
        return 2
    from . import display, tone

    print(tr("{note}: {frequency} Hz", note=name, frequency=display.freq_text(freq)))
    try:
        tone.play(freq, seconds, wait=True)
    except Exception as exc:  # noqa: BLE001 (PortAudio levanta varios tipos)
        print("py-tuner: " + tr("cannot play the tone: {error}", error=exc), file=sys.stderr)
        return 1
    return 0


def list_devices() -> int:
    found = audio.input_devices()
    if not found:
        print(tr("No input devices (is PortAudio installed?)"))
        return 1
    for index, name, rate in found:
        print(f"{index:3}  {name}  ({rate} Hz)")
    return 0


def list_instruments(s: Settings) -> int:
    for inst in instruments.INSTRUMENTS:
        inst = instruments.with_custom(inst, s.custom_tunings)
        print(f"{inst.key}  ({tr(inst.name)})")
        for t in inst.tunings:
            print(f"    {tr(t.name):20} {' '.join(t.strings)}")
    return 0


def choose_language(saved: Settings, argv: list[str]) -> None:
    """Pone la interfaz en el idioma de --language, si se dio, o en el guardado, o en el del sistema.
    (Se mira antes de leer las opciones, porque la ayuda misma sale en ese idioma.)"""
    code = ""
    for i, arg in enumerate(argv):
        if arg == "--language" and i + 1 < len(argv):
            code = argv[i + 1]
        elif arg.startswith("--language="):
            code = arg.split("=", 1)[1]
    interface.use(code or saved.language or interface.system_code())
    interface.translate_argparse()


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    saved = settings_mod.load()
    choose_language(saved, argv)
    p = parser()
    args = p.parse_args(argv)
    try:
        s = apply(args, saved)
    except ValueError as exc:
        p.error(str(exc))
    if args.save:
        settings_mod.save(s)
    if args.note is not None and args.mode != "tone":
        p.error(tr("a note is given only to tone"))
    if args.mode == "tone":
        return play_tone(s, args.note)
    if args.mode == "devices":
        return list_devices()
    if args.mode == "instruments":
        return list_instruments(s)
    if args.mode == "cli":
        from . import cli

        return cli.run(s, args.file, once=args.once, realtime=args.realtime)
    if args.mode == "tui":
        from . import tui

        return tui.run(s, args.file)
    from .gui import window

    return window.run(s, args.file)


if __name__ == "__main__":
    sys.exit(main())
