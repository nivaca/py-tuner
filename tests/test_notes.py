"""Las notas, sus nombres, el La de referencia y las afinaciones de los instrumentos."""

from __future__ import annotations

import pytest

from py_tuner import instruments, notes


def test_frequencies():
    assert notes.frequency(69) == 440.0
    assert notes.frequency(60) == pytest.approx(261.6256, abs=1e-4)
    assert notes.frequency(28) == pytest.approx(41.2034, abs=1e-4)  # E1
    assert notes.frequency(69, 442.0) == 442.0
    assert notes.frequency(57, 441.0) == pytest.approx(220.5)


def test_a4_shifts_every_note_by_the_same_cents():
    for midi in (23, 40, 64, 88):
        c = notes.cents(notes.frequency(midi, 441.0), notes.frequency(midi, 440.0))
        assert c == pytest.approx(1200 * __import__("math").log2(441 / 440))


def test_midi_and_cents():
    assert notes.midi_of(440.0) == 69
    assert notes.nearest(450.0) == 69
    assert notes.nearest(455.0) == 70
    assert notes.cents(880.0, 440.0) == pytest.approx(1200)
    assert notes.cents(440.0 * 2 ** (0.3 / 1200), 440.0) == pytest.approx(0.3)
    assert notes.nearest(442.0, 442.0) == 69


def test_parse():
    assert notes.parse("A4") == 69
    assert notes.parse("E2") == 40
    assert notes.parse("B0") == 23
    assert notes.parse("F#1") == 30
    assert notes.parse("Bb0") == 22
    assert notes.parse("bb0") == 22
    assert notes.parse("Eb2") == 39
    assert notes.parse("C" + notes.SHARP + "3") == 49
    assert notes.parse("Sol3") == 55
    assert notes.parse("Do4") == 60
    assert notes.parse("Re" + "b4") == 61
    assert notes.parse("H2") == 47
    with pytest.raises(ValueError):
        notes.parse("X4")
    with pytest.raises(ValueError):
        notes.parse("E")


def test_names():
    assert notes.full_name(69) == "A4"
    assert notes.full_name(70) == "A" + notes.SHARP + "4"
    assert notes.full_name(70, accidentals="flats") == "B" + notes.FLAT + "4"
    assert notes.full_name(70, accidentals="flats", unicode=False) == "Bb4"
    assert notes.full_name(71) == "B4"
    assert notes.full_name(67, "latin") == "Sol4"
    assert notes.full_name(68, "latin") == "Sol" + notes.SHARP + "4"
    assert notes.full_name(70, "latin", "flats") == "Si" + notes.FLAT + "4"
    assert notes.full_name(60, "latin", "flats") == "Do4"
    assert notes.full_name(71, "german") == "H4"
    assert notes.full_name(70, "german") == "B4"
    assert notes.full_name(66, "german") == "Fis4"
    assert notes.full_name(63, "german", "flats") == "Es4"
    assert notes.full_name(23) == "B0"
    assert notes.full_name(11) == "B-1"


def test_both_accidentals():
    assert notes.full_name(66, accidentals="both") == "F" + notes.SHARP + "/G" + notes.FLAT + "4"
    assert notes.full_name(66, accidentals="both", unicode=False) == "F#/Gb4"
    assert notes.full_name(64, accidentals="both") == "E4"
    assert notes.full_name(66, "latin", "both", unicode=False) == "Fa#/Solb4"
    assert notes.full_name(66, "german", "both") == "Fis/Ges4"
    assert notes.full_name(70, "german", "both") == "B4"
    assert notes.parse("F#/Gb3") == notes.parse("F#3")
    with pytest.raises(ValueError):
        notes.parse("F#/Ab3")


def test_names_round_trip():
    for system in ("english", "latin"):
        for acc in notes.ACCIDENTALS:
            for midi in range(21, 100):
                assert notes.parse(notes.full_name(midi, system, acc)) == midi


def test_check_a4():
    assert notes.check_a4("441.5") == 441.5
    for bad in (300, 500, float("nan")):
        with pytest.raises(ValueError):
            notes.check_a4(bad)


def test_every_tuning_parses_and_lies_in_its_range():
    for inst in instruments.INSTRUMENTS:
        for t in inst.tunings:
            midis = t.midis
            assert list(midis) == sorted(midis) or inst.key == "violin", (inst.key, t.name)
            assert inst.lowest <= min(midis) and max(midis) <= inst.highest, (inst.key, t.name)


def test_standard_tunings():
    assert instruments.find("guitar").tunings[0].strings == ("E2", "A2", "D3", "G3", "B3", "E4")
    assert instruments.find("bass").tunings[0].strings == ("E1", "A1", "D2", "G2")
    assert instruments.find("double-bass").tunings[0].strings == ("E1", "A1", "D2", "G2")
    assert instruments.find("violin").tunings[0].strings == ("G3", "D4", "A4", "E5")
    assert instruments.find("chromatic").tunings == ()
    with pytest.raises(KeyError):
        instruments.find("piano")


def test_tuning_lookup():
    g = instruments.find("guitar")
    assert g.tuning("drop d").name == "Drop D"
    assert g.tuning("nonsense").name == "Standard"
    assert g.tuning(None).name == "Standard"


def test_custom_tunings():
    custom = [
        {"instrument": "guitar", "name": "Nashville", "strings": "E3 A3 D4 G4 B3 E4"},
        {"instrument": "guitar", "name": "Broken", "strings": "E2 Q9"},
        {"instrument": "guitar", "strings": "E2"},
        {"instrument": "bass", "name": "Piccolo", "strings": ["E2", "A2", "D3", "G3"]},
    ]
    g = instruments.with_custom(instruments.find("guitar"), custom)
    assert [t.name for t in g.tunings][-1] == "Nashville"
    assert "Broken" not in [t.name for t in g.tunings]
    b = instruments.with_custom(instruments.find("bass"), custom)
    assert b.tuning("Piccolo").strings == ("E2", "A2", "D3", "G3")
