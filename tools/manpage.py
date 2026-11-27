#!/usr/bin/env python3
"""Hace las páginas de manual de py-tuner con la ayuda del programa mismo:

    uv run python tools/manpage.py [--check]

Escribe packaging/man/py-tuner.1 (inglés) y packaging/man/es/py-tuner.1 (español), que instalan el
RPM. Cada una tiene la descripción y las opciones de la línea de órdenes, como las
imprime --help, y las teclas de la interfaz de terminal (tui.KEY_ROWS): el manual no puede decir nada que el
programa no diga. --check solo dice si están al día (las pruebas lo usan). (De la de py-slowdown.)
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
MAN = ROOT / "packaging" / "man"

# The headings of the page, in each language
HEADINGS = {
    "en": {"name": "NAME", "synopsis": "SYNOPSIS", "description": "DESCRIPTION", "options": "OPTIONS",
           "keys": "KEYS OF THE TERMINAL INTERFACE", "files": "FILES", "author": "AUTHOR",
           "summary": "an accurate tuner for guitar, bass, double bass and violin",
           "choices": "one of",
           "files_text": [
               ("~/.config/py-tuner/settings.json",
                "The settings, the same for the window, the terminal and the command line ($XDG_CONFIG_HOME). "
                "Own tunings can be added in it, under custom_tunings."),
           ]},
    "es": {"name": "NOMBRE", "synopsis": "SINOPSIS", "description": "DESCRIPCIÓN", "options": "OPCIONES",
           "keys": "TECLAS DE LA INTERFAZ DE TERMINAL", "files": "ARCHIVOS", "author": "AUTOR",
           "summary": "un afinador preciso para guitarra, bajo, contrabajo y violín",
           "choices": "uno de",
           "files_text": [
               ("~/.config/py-tuner/settings.json",
                "La configuración, la misma para la ventana, la terminal y la línea de órdenes ($XDG_CONFIG_HOME). "
                "En ella se pueden añadir afinaciones propias, en custom_tunings."),
           ]},
}


def roff(text: str) -> str:
    """TEXT safe in roff: backslashes doubled, and no line starting with . or '."""
    out = []
    for line in text.replace("\\", "\\e").replace("-", "\\-").splitlines():
        out.append("\\&" + line if line.startswith((".", "'")) else line)
    return "\n".join(out)


def page(lang: str) -> str:
    from py_tuner import __version__, interface
    from py_tuner.app import parser as build_parser
    from py_tuner.tui import KEY_ROWS

    interface.use(lang)
    interface.translate_argparse()
    # (la configuración donde está para todos: ~/.config, no la de este entorno)
    os.environ.pop("XDG_CONFIG_HOME", None)
    os.environ.update(COLUMNS="78", NO_COLOR="1", PYTHON_COLORS="0")  # (the same text in and out of a terminal)
    h = HEADINGS[lang]
    parser = build_parser()
    lines = [f'.TH PY-TUNER 1 "" "py-tuner {__version__}" "py-tuner"',
             f".SH {h['name']}", f"py\\-tuner \\- {h['summary']}",
             f".SH {h['synopsis']}", ".B py\\-tuner",
             "[gui | tui | cli | devices | instruments] [\\-a\\ HZ] [\\-i\\ INSTRUMENT] [\\-t\\ TUNING] "
             "[\\-f\\ WAV] [...]",
             f".SH {h['description']}", roff(parser.description), "", roff(parser.epilog),
             f".SH {h['options']}"]
    for action in parser._actions:
        name = ", ".join(action.option_strings) or action.metavar or action.dest
        text = action.help
        # (las opciones con valores fijos los dicen, si su ayuda no los nombra ya)
        if action.choices and action.option_strings:
            text += f" ({h['choices']}: {', '.join(map(str, action.choices))})"
        lines += [".TP", f".B {roff(name)}", roff(text)]
    lines.append(f".SH {h['keys']}")
    for keys, what in KEY_ROWS:
        lines += [".TP", f".B {roff(keys)}", roff(interface.tr(what))]
    lines.append(f".SH {h['files']}")
    for path, text in h["files_text"]:
        lines += [".TP", f".I {roff(path)}", roff(text)]
    lines += [f".SH {h['author']}", "Nicolas Vaughan <nicolasvaughan@proton.me>"]
    interface.use("en")
    return "\n".join(lines) + "\n"


def targets() -> dict[str, Path]:
    return {"en": MAN / "py-tuner.1", "es": MAN / "es" / "py-tuner.1"}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Make the manual pages from the help of the program.")
    parser.add_argument("--check", action="store_true", help="only say whether they are up to date")
    args = parser.parse_args(argv)
    stale = []
    for lang, path in targets().items():
        text = page(lang)
        if args.check:
            if not path.is_file() or path.read_text(encoding="utf-8") != text:
                stale.append(path)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            print(f"Wrote {path.relative_to(ROOT)}")
    if stale:
        sys.exit("Out of date (run uv run python tools/manpage.py): " + ", ".join(str(p.relative_to(ROOT))
                                                                          for p in stale))


if __name__ == "__main__":
    main()
