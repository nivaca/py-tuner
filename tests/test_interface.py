"""Cada texto del programa está en el archivo en español, con las mismas {partes}, y nada más."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from py_tuner import instruments, interface

SOURCE = Path(interface.__file__).parent


def program_texts() -> set[str]:
    texts = set()
    for path in SOURCE.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (isinstance(node, ast.Call) and getattr(node.func, "id", None) == "tr"
                    and node.args and isinstance(node.args[0], ast.Constant)):
                texts.add(interface.key_of(node.args[0].value))
    # Los que tr() recibe por nombre: la ayuda, las teclas, las listas, los instrumentos y sus afinaciones.
    from py_tuner import app, tui
    from py_tuner.gui import window

    texts.update(interface.key_of(t) for t in (app.DESCRIPTION, app.EPILOG, *tui.KEYS,
                                                *window.NAME_LABELS.values(), *window.DISPLAY_LABELS.values(),
                                                *window.STROBE_LABELS.values()))
    texts.update(what for _, what in tui.KEY_ROWS)
    for inst in instruments.INSTRUMENTS:
        texts.add(inst.name)
        texts.update(t.name for t in inst.tunings)
    texts.update(interface.key_of(t) for t in interface.ARGPARSE_TEXTS)
    return texts


def test_spanish_is_complete():
    spanish = interface.read("es")
    program = program_texts()
    assert sorted(program - set(spanish)) == []
    assert sorted(set(spanish) - program) == []


def test_same_parts():
    part = re.compile(r"\{(\w+)\}")
    for english, spanish in interface.read("es").items():
        assert set(part.findall(english)) == set(part.findall(spanish)), english


def test_each_text_once():
    text = (interface.FOLDER / "es.xml").read_text(encoding="utf-8")
    keys = re.findall(r"<en>(.*?)</en>", text, re.S)
    assert len(keys) == len(set(keys))


def test_use_and_tr():
    interface.use("es")
    try:
        assert interface.tr("Guitar") == "Guitarra"
        assert interface.tr("string {number}", number=3) == "cuerda 3"
        assert interface.tr("not a known text") == "not a known text"
        assert interface.names()["es"] == "Español"
    finally:
        interface.use("en")
    assert interface.tr("Guitar") == "Guitar"


def test_language_option(capsys):
    from py_tuner import app

    try:
        assert app.main(["instruments", "--language", "es"]) == 0
        out = capsys.readouterr().out
        assert "Contrabajo" in out and "Afinación estándar" not in out and "Estándar" in out
    finally:
        interface.use("en")
