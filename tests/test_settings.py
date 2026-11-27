"""La configuración: valores de fábrica, guardado, lectura y valores que no sirven."""

from __future__ import annotations

import json

from py_tuner import settings
from py_tuner.settings import Settings


def test_defaults_without_a_file(config_home):
    s = settings.load()
    assert s == Settings()
    assert settings.path() == config_home / "py-tuner" / "settings.json"


def test_save_and_load_round_trip():
    s = Settings(a4=442.5, instrument="violin", tuning="Standard", string=2, names="latin",
                 accidentals="flats", device="USB", channel="2", tolerance=0.5, display="strobe",
                 custom_tunings=[{"instrument": "violin", "name": "Mine", "strings": "G3 D4 A4 D5"}])
    settings.save(s)
    assert settings.load() == s
    assert not settings.path().with_suffix(".tmp").exists()


def test_bad_values_fall_back_to_defaults():
    p = settings.path()
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps({"a4": 1000, "instrument": "banjo", "names": "klingon", "string": -1,
                             "rate": 12, "channel": "left", "tolerance": "x", "smoothing": 0.25,
                             "unknown": True}))
    s = settings.load()
    d = Settings()
    assert (s.a4, s.instrument, s.names, s.string, s.rate, s.channel, s.tolerance) == \
           (d.a4, d.instrument, d.names, d.string, d.rate, d.channel, d.tolerance)
    assert s.smoothing == 0.25


def test_unreadable_file_gives_defaults():
    p = settings.path()
    p.parent.mkdir(parents=True)
    p.write_text("{not json")
    assert settings.load() == Settings()
    p.write_text("[1, 2]")
    assert settings.load() == Settings()


def test_numbers_are_floats():
    s = Settings(a4=441, tolerance=2, smoothing=1, periods=8, min_level=-50).validated()
    assert all(isinstance(v, float) for v in (s.a4, s.tolerance, s.smoothing, s.periods, s.min_level))


def test_new_settings_are_checked():
    s = Settings(offsets={"B": -2, "X": 3, "E": 0}, transpose=20, capo=-1, strobe_mode="spiral",
                 show_trace="yes").validated()
    d = Settings()
    assert (s.transpose, s.capo, s.strobe_mode, s.show_trace) == (d.transpose, d.capo, d.strobe_mode, d.show_trace)
    assert s.offsets == {}  # (una clave mala invalida el conjunto)
    ok = Settings(offsets={"E": 0, "B": -2, "C#": 1.25}).validated()
    assert ok.offsets == {"C#": 1.25, "B": -2.0}
