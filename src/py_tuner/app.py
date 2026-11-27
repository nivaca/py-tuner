"""La entrada del programa: lee las opciones y arranca la ventana, la terminal o la línea de órdenes.

Las opciones comunes (La de referencia, instrumento, afinación, dispositivo,
archivo...) valen para los tres modos y pisan la configuración guardada solo
en esta sesión, salvo que se pida --save.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace

from . import __version__, audio, instruments, notes
from . import settings as settings_mod
from .settings import Settings

DESCRIPTION = ("An accurate tuner for guitar, bass, double bass and violin (and a chromatic one), "
               "with a needle and a strobe, in a window, in the terminal or on the command line.")
EPILOG = ("Without a command, the window opens. Options given here override the saved settings for this "
          "session only, unless --save is given. Settings: " + str(settings_mod.path()))

MODES = ("gui", "tui", "cli", "devices", "instruments")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="py-tuner", description=DESCRIPTION, epilog=EPILOG)
    p.add_argument("--version", action="version", version=f"py-tuner {__version__}")
    p.add_argument("mode", nargs="?", choices=MODES, default="gui",
                   help="gui (the window, default), tui (full-screen terminal), cli (a line of text), "
                        "devices (list the inputs), instruments (list the tunings)")
    g = p.add_argument_group("tuning")
    g.add_argument("-a", "--a4", type=float, metavar="HZ",
                   help=f"reference A4 in Hz, {notes.MIN_A4:g} to {notes.MAX_A4:g} (default 440)")
    g.add_argument("-i", "--instrument", choices=instruments.keys(), help="the instrument, or chromatic")
    g.add_argument("-t", "--tuning", metavar="NAME", help='the tuning, by name (e.g. "Drop D")')
    g.add_argument("-s", "--string", metavar="N|auto",
                   help="tune against string N (1 = the lowest) instead of the nearest one")
    g.add_argument("--names", choices=notes.NAME_SYSTEMS, help="note names: english, latin or german")
    g.add_argument("--flats", action="store_true", default=None, help="write accidentals as flats")
    g.add_argument("--sharps", dest="flats", action="store_false", help="write accidentals as sharps")
    g.add_argument("--tolerance", type=float, metavar="CENTS", help="in tune within this many cents (default 1)")
    g = p.add_argument_group("input")
    g.add_argument("-d", "--device", metavar="DEV", help="input device: its number or part of its name")
    g.add_argument("-r", "--rate", type=int, metavar="HZ", help="sample rate (default: the device's)")
    g.add_argument("-c", "--channel", metavar="mix|N", help="use channel N (from 1) or the mix of all")
    g.add_argument("-f", "--file", metavar="WAV", help="read a WAV file instead of the sound card")
    g.add_argument("--min-level", type=float, metavar="DBFS", help="ignore sounds quieter than this (default -60)")
    g.add_argument("--smoothing", type=float, metavar="SECONDS",
                   help="seconds the reading averages (default 0.5)")
    g.add_argument("--periods", type=float, metavar="N",
                   help="periods per analysis frame: more is steadier, fewer is faster (default 16)")
    g = p.add_argument_group("output")
    g.add_argument("--display", choices=settings_mod.DISPLAYS, help="needle, strobe or both (gui, tui)")
    g.add_argument("--once", action="store_true",
                   help="cli: print the first steady reading and exit")
    g.add_argument("--realtime", action="store_true",
                   help="cli with --file: play the file at its own pace instead of analysing it at once")
    g.add_argument("--save", action="store_true", help="save the options given as the new settings")
    return p


def apply(args: argparse.Namespace, base: Settings) -> Settings:
    """BASE with the options of ARGS that were given; ValueError for bad ones."""
    s = replace(base)
    if args.a4 is not None:
        s.a4 = notes.check_a4(args.a4)
    if args.instrument is not None and args.instrument != s.instrument:
        s.instrument = args.instrument
        s.string = None
        inst = s.instrument_preset()
        s.tuning = inst.tunings[0].name if inst.tunings else ""
    if args.tuning is not None:
        inst = s.instrument_preset()
        match = [t.name for t in inst.tunings if t.name.lower() == args.tuning.lower()]
        if not match:
            names = ", ".join(t.name for t in inst.tunings) or "none (chromatic)"
            raise ValueError(f"{inst.name} has no tuning {args.tuning!r}; it has: {names}")
        s.tuning = match[0]
        s.string = None
    if args.string is not None:
        if args.string.lower() == "auto":
            s.string = None
        else:
            inst = s.instrument_preset()
            count = len(inst.tuning(s.tuning).strings) if inst.tunings else 0
            if not args.string.isdigit() or not 1 <= int(args.string) <= count:
                raise ValueError(f"--string must be auto or 1..{count}" if count
                                 else "--string needs an instrument with strings")
            s.string = int(args.string) - 1
    if args.names is not None:
        s.names = args.names
    if args.flats is not None:
        s.accidentals = "flats" if args.flats else "sharps"
    for name in ("tolerance", "device", "rate", "min_level", "smoothing", "periods", "display"):
        value = getattr(args, name)
        if value is not None:
            setattr(s, name, value)
    if args.channel is not None:
        if args.channel != "mix" and not args.channel.isdigit():
            raise ValueError("--channel must be mix or a number from 1")
        s.channel = args.channel
    checked = s.validated()
    for name in ("tolerance", "rate", "min_level", "smoothing", "periods"):
        if getattr(args, name) is not None and getattr(checked, name) != getattr(s, name):
            raise ValueError(f"--{name.replace('_', '-')} {getattr(args, name)} is out of range")
    return checked


def open_source(s: Settings, file: str | None, realtime: bool = True) -> audio.Source:
    """La fuente de sonido para S: el archivo (servido en tiempo real) o el dispositivo."""
    # El búfer guarda más de lo que el análisis más largo pide.
    seconds = 4.0 + s.periods / 10
    if file:
        return audio.FileSource(file, seconds, s.channel)
    return audio.MicSource(seconds, s.device, s.rate, s.channel)


def list_devices() -> int:
    found = audio.input_devices()
    if not found:
        print("No input devices (is PortAudio installed?)")
        return 1
    for index, name, rate in found:
        print(f"{index:3}  {name}  ({rate} Hz)")
    return 0


def list_instruments(s: Settings) -> int:
    for inst in instruments.INSTRUMENTS:
        inst = instruments.with_custom(inst, s.custom_tunings)
        print(f"{inst.key}  ({inst.name})")
        for t in inst.tunings:
            print(f"    {t.name:20} {' '.join(t.strings)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = parser()
    args = p.parse_args(argv)
    try:
        s = apply(args, settings_mod.load())
    except ValueError as exc:
        p.error(str(exc))
    if args.save:
        settings_mod.save(s)
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
