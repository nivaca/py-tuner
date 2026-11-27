"""La línea de órdenes: las opciones, los listados y el informe de un archivo."""

from __future__ import annotations

import subprocess
import sys

import pytest
from conftest import string, write_wav

from py_tuner import app, cli, notes, settings
from py_tuner.settings import Settings
from py_tuner.tuner import Reading


def parse(*argv):
    return app.apply(app.parser().parse_args(list(argv)), Settings())


def test_options_override_settings():
    s = parse("cli", "-a", "442.5", "-i", "bass", "-t", "5-string", "-s", "1", "--names", "latin", "--flats",
              "--tolerance", "0.5", "-c", "2")
    assert (s.a4, s.instrument, s.tuning, s.string, s.names, s.accidentals, s.tolerance, s.channel) == \
           (442.5, "bass", "5-string", 0, "latin", "flats", 0.5, "2")


def test_accidentals_options():
    assert parse("--accidentals", "both").accidentals == "both"
    assert parse("--flats").accidentals == "flats"
    assert parse("--sharps").accidentals == "sharps"
    assert parse().accidentals == "sharps"


def test_chromatic_is_the_default():
    s = parse()
    assert (s.instrument, s.tuning, s.string) == ("chromatic", "", None)


def test_instrument_resets_tuning_and_string():
    s = app.apply(app.parser().parse_args(["-i", "violin"]), Settings(tuning="Drop D", string=3))
    assert (s.tuning, s.string) == ("Standard", None)
    assert parse("-i", "chromatic").tuning == ""


@pytest.mark.parametrize("argv", [
    ["-a", "300"], ["-t", "Nope"], ["-s", "9"], ["-s", "x"], ["-i", "chromatic", "-s", "1"],
    ["-c", "left"], ["--tolerance", "500"], ["--periods", "1"],
])
def test_bad_options(argv):
    with pytest.raises(ValueError):
        parse(*argv)


def test_save_option(capsys):
    assert app.main(["instruments", "-a", "441", "--save"]) == 0
    assert settings.load().a4 == 441.0
    assert app.main(["instruments", "-a", "443"]) == 0
    assert settings.load().a4 == 441.0


def test_instruments_listing(capsys):
    assert app.main(["instruments"]) == 0
    out = capsys.readouterr().out
    assert "double-bass" in out and "E1 A1 D2 G2" in out and "G3 D4 A4 E5" in out


def test_bad_option_exits_with_usage(capsys):
    with pytest.raises(SystemExit) as e:
        app.main(["cli", "-a", "1000"])
    assert e.value.code == 2
    assert "between" in capsys.readouterr().err


def test_needle_text():
    assert cli.needle(0) == "[----------#----------]"
    assert cli.needle(50).endswith("*]")
    assert cli.needle(-500).startswith("[*")
    assert cli.needle(10) == "[----------|-*--------]"


def test_line():
    s = Settings(instrument="guitar")
    r = Reading(frequency=82.5, target_midi=40, target_frequency=82.407, cents=1.95, string=0, level=-20)
    text = cli.line(r, s)
    assert text.startswith("E2") and "82.500 Hz" in text and "+1.9" in text and "string 1" in text
    assert "OK" not in text
    assert "no pitch" in cli.line(Reading(level=-70), s)


def test_file_report(tmp_path, capsys):
    import numpy as np

    parts = []
    for note, c in (("E2", 2.0), ("A2", -5.0), ("G3", 0.3)):
        parts.append(string(notes.frequency(notes.parse(note)) * 2 ** (c / 1200), seconds=1.2, attack=True,
                            seed=len(parts)))
        parts.append(np.zeros(12000))
    write_wav(tmp_path / "g.wav", np.concatenate(parts))
    assert cli.run(Settings(instrument="guitar"), str(tmp_path / "g.wav")) == 0
    out = capsys.readouterr().out.splitlines()
    rows = [line for line in out if " s  " in line]
    assert [r.split()[3] for r in rows] == ["E2", "A2", "G3"]
    found = [float(r.split("cents")[0].split()[-1]) for r in rows]
    assert found == pytest.approx([2.0, -5.0, 0.3], abs=0.05)


def test_file_report_of_silence(tmp_path, capsys):
    import numpy as np

    write_wav(tmp_path / "s.wav", np.zeros(48000))
    assert cli.run(Settings(), str(tmp_path / "s.wav")) == 1
    assert "no steady note" in capsys.readouterr().out


def test_cli_realtime_file_once(tmp_path):
    # De punta a punta, en otro proceso: el archivo suena y la primera lectura estable sale.
    write_wav(tmp_path / "a.wav", string(110.0 * 2 ** (4 / 1200), seconds=3.0, decay=0.1))
    done = subprocess.run([sys.executable, "-m", "py_tuner", "cli", "--file", str(tmp_path / "a.wav"),
                           "--realtime", "--once", "-i", "guitar"],
                          capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr
    last = done.stdout.strip().splitlines()[-1]
    assert last.startswith("A2") and "+4.0" in last and "string 2" in last


def test_version():
    done = subprocess.run([sys.executable, "-m", "py_tuner", "--version"], capture_output=True, text=True)
    assert done.stdout.strip().startswith("py-tuner ")


def test_new_options():
    s = parse("--offset", "B=-2", "--offset", "Gb=1.5", "--transpose", "-3", "--capo", "4", "--strobe",
              "harmonics", "--no-trace")
    assert s.offsets == {"F#": 1.5, "B": -2.0}
    assert (s.transpose, s.capo, s.strobe_mode, s.show_trace) == (-3, 4, "harmonics", False)
    assert parse("--offset", "B=0").offsets == {}


@pytest.mark.parametrize("argv", [["--offset", "B"], ["--offset", "Q=1"], ["--offset", "B=70"],
                                  ["--capo", "13"], ["--transpose", "-13"]])
def test_bad_new_options(argv):
    with pytest.raises(ValueError):
        parse(*argv)


def test_tone_targets():
    s = parse("-i", "guitar", "--capo", "2", "--offset", "F#=-5")
    name, f = app.tone_target(s, "1")
    assert name == "F" + notes.SHARP + "2"
    assert f == pytest.approx(notes.frequency(notes.parse("F#2")) * 2 ** (-5 / 1200))
    assert app.tone_target(Settings(), None) == ("A4", 440.0)
    assert app.tone_target(Settings(a4=442), "A3")[1] == pytest.approx(221.0)
    with pytest.raises(ValueError):
        app.tone_target(s, "9")


def test_a_note_only_with_tone(capsys):
    with pytest.raises(SystemExit):
        app.main(["cli", "E2"])


def test_tone_command_plays(monkeypatch, capsys):
    from py_tuner import tone

    played = []
    monkeypatch.setattr(tone, "play", lambda f, seconds=3.0, wait=False: played.append((round(f, 3), wait)))
    assert app.main(["tone", "E2"]) == 0
    assert played == [(82.407, True)]
    assert "E2" in capsys.readouterr().out


def test_scale_spectrum_and_noise_options():
    s = parse("--needle", "fine", "--spectrum", "--no-learn-noise")
    assert (s.needle_scale, s.show_spectrum, s.learn_noise) == ("fine", True, False)
    assert parse().learn_noise is True and parse().needle_scale == "linear"
    assert cli.needle(2.0, scale="fine") != cli.needle(2.0)


def test_response_option():
    assert parse("--response", "steady").response == "steady"
    assert parse().response == "normal"
