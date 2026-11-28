"""El afinador completo: la nota o cuerda de referencia, los cents, y el hilo de análisis."""

from __future__ import annotations

import time

import numpy as np
import pytest
from conftest import RATE, phone_bass, string

from py_tuner import audio, notes
from py_tuner.settings import Settings
from py_tuner.tuner import LiveTuner, Tuner, STEADY_ATTACK, STEADY_CLARITY, STEADY_WINDOW


def detuned(midi: int, c: float, a4: float = 440.0) -> float:
    return notes.frequency(midi, a4) * 2 ** (c / 1200)


def last(tuner: Tuner, x: np.ndarray):
    return tuner.analyze_all(x)[-1]


@pytest.mark.parametrize(("instrument", "note", "c"), [
    ("guitar", "E2", +3.0), ("guitar", "B3", -12.5), ("bass", "E1", -0.4), ("bass", "G2", +7.0),
    ("double-bass", "A1", +1.5), ("violin", "G3", -2.25), ("violin", "E5", +0.6),
])
def test_strings_and_cents(instrument, note, c):
    s = Settings(instrument=instrument, tuning="")
    tuner = Tuner(s, RATE)
    midi = notes.parse(note)
    r = last(tuner, string(detuned(midi, c), seconds=1.5))
    assert r.active
    assert r.target_midi == midi
    assert r.string == [notes.parse(x) for x in s.instrument_preset().tunings[0].strings].index(midi)
    assert r.cents == pytest.approx(c, abs=0.05)
    assert r.in_tune == (abs(c) <= s.tolerance)


def test_reference_a4():
    # El mismo sonido, medido contra La 440 y contra La 442.
    x = string(220.0, seconds=1.2)
    r440 = last(Tuner(Settings(instrument="chromatic"), RATE), x)
    r442 = last(Tuner(Settings(instrument="chromatic", a4=442.0), RATE), x)
    assert r440.cents == pytest.approx(0.0, abs=0.05)
    assert r442.cents == pytest.approx(1200 * np.log2(220 / 221), abs=0.05)
    assert r442.target_frequency == pytest.approx(221.0)


def test_chromatic_finds_any_note():
    tuner = Tuner(Settings(instrument="chromatic"), RATE)
    r = last(tuner, string(detuned(notes.parse("C#3"), -20), seconds=1.2))
    assert r.target_midi == notes.parse("C#3")
    assert r.string is None
    assert r.cents == pytest.approx(-20, abs=0.05)


def test_locked_string():
    # Con la sexta cuerda fija, un La 110 se mide contra el Mi 82: +500 cents.
    tuner = Tuner(Settings(instrument="guitar", string=0), RATE)
    r = last(tuner, string(110.0, seconds=1.2))
    assert r.string == 0
    assert r.cents == pytest.approx(500, abs=0.1)


def test_auto_string_picks_the_nearest():
    tuner = Tuner(Settings(instrument="guitar"), RATE)
    # un Re 3 muy bajo (70 cents) sigue siendo la cuarta cuerda
    r = last(tuner, string(detuned(notes.parse("D3"), -70), seconds=1.2))
    assert r.string == 2


def test_alternate_tuning():
    tuner = Tuner(Settings(instrument="guitar", tuning="Drop D"), RATE)
    r = last(tuner, string(detuned(notes.parse("D2"), 1.0), seconds=1.5))
    assert (r.target_midi, r.string) == (notes.parse("D2"), 0)


def test_silence_reading():
    tuner = Tuner(Settings(), RATE)
    r = last(tuner, np.zeros(RATE))
    assert not r.active
    assert r.level == float("-inf")


def test_reconfigure_keeps_history_unless_the_range_changes():
    tuner = Tuner(Settings(), RATE)
    tuner.analyze_all(string(110.0, seconds=0.6))
    assert tuner.stabilizer.reading() is not None
    tuner.configure(Settings(tolerance=3.0))
    assert tuner.stabilizer.reading() is not None
    tuner.configure(Settings(instrument="violin", tuning=""))
    assert tuner.stabilizer.reading() is None


class FakeSource(audio.Source):
    """A source fed by the test."""

    def __init__(self) -> None:
        self.rate = RATE
        self.buffer = audio.RingBuffer(4 * RATE)
        self.started = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.started = False


def test_live_tuner_thread():
    src = FakeSource()
    live = LiveTuner(Settings(instrument="bass"), src)
    live.start()
    try:
        assert src.started
        x = string(notes.frequency(notes.parse("A1")), seconds=1.5)
        for i in range(0, len(x), 1200):
            src.buffer.write(x[i:i + 1200])
            time.sleep(0.005)
        deadline = time.monotonic() + 3
        while not live.reading.active and time.monotonic() < deadline:
            time.sleep(0.02)
        r = live.reading
        assert r.active and r.target_midi == notes.parse("A1")
        assert abs(r.cents) < 0.1
        live.configure(Settings(instrument="bass", a4=441.0))
        assert live.settings.a4 == 441.0
    finally:
        live.stop()
    assert not src.started
    assert live.error is None


def test_readings_count_their_frames():
    tuner = Tuner(Settings(), RATE)
    readings = [r for r in tuner.analyze_all(string(220.0, seconds=1.0)) if r.active]
    assert readings[0].count == 1
    assert readings[-1].count > 12


def test_the_search_stays_near_the_strings():
    # Con cuerdas, el margen va de una cuarta bajo la más grave a una quinta sobre la más aguda.
    tuner = Tuner(Settings(instrument="guitar", tuning="Standard"), RATE)
    assert tuner.detector.fmin == pytest.approx(notes.frequency(notes.parse("B1")))
    assert tuner.detector.fmax == pytest.approx(notes.frequency(notes.parse("B4")))
    chromatic = Tuner(Settings(), RATE)
    assert chromatic.detector.fmin < 25


def test_a_pluck_is_an_onset():
    tuner = Tuner(Settings(), RATE)
    quiet = 0.001 * string(110.0, seconds=0.5, snr_db=None)
    loud = string(110.0, seconds=0.5, snr_db=None)
    assert not tuner._onset(quiet, 0.5)
    assert not tuner._onset(quiet, 0.525)
    assert tuner._onset(loud, 0.55)


def test_the_note_held_holds_past_halfway():
    # Una nota a 55 cents sobre La sigue siendo La si ya lo era; desde el silencio es La sostenido.
    tuner = Tuner(Settings(), RATE)
    a = notes.frequency(notes.parse("A3"))
    assert tuner.target(a)[0] == notes.parse("A3")
    assert tuner.target(a * 2 ** (55 / 1200))[0] == notes.parse("A3")
    assert tuner.target(a * 2 ** (65 / 1200))[0] == notes.parse("A#3")
    tuner._held = None
    assert tuner.target(a * 2 ** (55 / 1200))[0] == notes.parse("A#3")


def test_the_string_held_holds_past_halfway():
    tuner = Tuner(Settings(instrument="guitar"), RATE)
    e2, a2 = notes.parse("E2"), notes.parse("A2")
    assert tuner.target(notes.frequency(e2))[1] == 0
    # halfway from E2 to A2 is 2.5 semitones up; 2.55 still holds E2, 2.7 goes to A2
    assert tuner.target(notes.frequency(e2 + 2.55))[1] == 0
    assert tuner.target(notes.frequency(e2 + 2.7))[1] == 1
    assert tuner.target(notes.frequency(a2 - 2.55))[1] == 1


def test_live_strobe_moves_with_the_deviation():
    # De punta a punta: el hilo de análisis alimenta el estroboscopio con cada muestra una vez, y sus bandas
    # avanzan unas 2, 4 y 8 franjas por segundo para una cuerda 2 cents alta.
    src = FakeSource()
    live = LiveTuner(Settings(instrument="guitar"), src)
    live.start()
    try:
        x = string(notes.frequency(notes.parse("A2")) * 2 ** (2 / 1200), seconds=3.0, decay=0.1)
        marks = []
        for i in range(0, len(x), 1200):
            src.buffer.write(x[i:i + 1200])
            time.sleep(0.004)
            if i in (int(1.5 * RATE) // 1200 * 1200, int(2.9 * RATE) // 1200 * 1200):
                deadline = time.monotonic() + 2
                while live.reading.time < (i + 1200) / RATE - 1e-6 and time.monotonic() < deadline:
                    time.sleep(0.005)
                marks.append((live.reading.time, live.reading.strobe))
        (t0, a), (t1, b) = marks
        speeds = [(bb.position - aa.position) / (t1 - t0) for aa, bb in zip(a, b)]
        assert speeds == pytest.approx([2, 4, 8], rel=0.2)
    finally:
        live.stop()


def test_offsets_move_the_target():
    s = Settings(instrument="guitar", offsets={"B": -2.0, "G": 1.5})
    tuner = Tuner(s, RATE)
    b3 = notes.parse("B3")
    assert tuner.target_frequency(b3) == pytest.approx(notes.frequency(b3) * 2 ** (-2 / 1200))
    r = last(tuner, string(notes.frequency(b3) * 2 ** (-2 / 1200), seconds=1.2))
    assert r.cents == pytest.approx(0.0, abs=0.05) and r.in_tune


def test_capo_raises_the_strings():
    tuner = Tuner(Settings(instrument="guitar", capo=2), RATE)
    assert tuner.string_midis[0] == notes.parse("F#2")
    r = last(tuner, string(notes.frequency(notes.parse("B2")), seconds=1.2))
    assert (r.target_midi, r.string) == (notes.parse("B2"), 1)


def test_transpose_changes_only_the_names():
    from py_tuner import display

    s = Settings(transpose=2)
    tuner = Tuner(s, RATE)
    r = last(tuner, string(notes.frequency(notes.parse("Bb3")), seconds=1.2))
    assert r.target_midi == notes.parse("Bb3")
    assert display.note_full(r.target_midi, s, unicode=False) == "C4"


def test_readings_say_how_much_sound_they_span():
    tuner = Tuner(Settings(), RATE)
    r = [x for x in tuner.analyze_all(string(220.0, seconds=1.0)) if x.active]
    assert r[0].span == 0.0
    assert 0.4 < r[-1].span <= 0.5 + 1e-9  # (la ventana de 0,5 s)


def gliding_pluck(f1: float, glide: float, seconds: float = 3.0, lead: float = 0.5) -> np.ndarray:
    """A low plucked string, after LEAD seconds of silence, that starts GLIDE cents sharp and settles on F1 as it
    fades (a pluck stretches the string: the louder, the sharper)."""
    t = np.arange(int(seconds * RATE)) / RATE
    env = np.exp(-t / 1.5)
    phase = 2 * np.pi * np.cumsum(f1 * 2 ** (glide * env ** 2 / 1200)) / RATE
    x = sum(env * np.exp(-0.2 * n * t) * np.sin(n * phase) / n for n in range(1, 9))
    x *= np.minimum(1.0, t / 0.002)
    rng = np.random.default_rng(0)
    return np.concatenate((np.zeros(int(lead * RATE)), 0.5 * x / np.max(np.abs(x)))) + rng.normal(0, 1e-4, int(
        (seconds + lead) * RATE))


def test_steady_response_configures_the_analysis():
    t = Tuner(Settings(instrument="double-bass", response="steady"), RATE)
    assert (t.stabilizer.window, t.stabilizer.attack, t.detector.min_clarity) == \
           (STEADY_WINDOW, STEADY_ATTACK, STEADY_CLARITY)
    t.configure(Settings(instrument="double-bass", response="steady", smoothing=3.0))
    assert t.stabilizer.window == 3.0  # (un promedio más largo que el suyo se respeta)
    t.configure(Settings(instrument="double-bass"))
    assert (t.stabilizer.window, t.stabilizer.attack, t.detector.min_clarity) == (0.5, 0.0, 0.75)
    # en el modo cromático, la claridad de siempre
    assert Tuner(Settings(response="steady"), RATE).detector.min_clarity == 0.75


def test_steady_response_holds_a_settling_double_bass_string():
    a1 = notes.frequency(notes.parse("A1"))
    x = gliding_pluck(a1, glide=10.0)
    shown = {}
    for response in ("normal", "steady"):
        rs = Tuner(Settings(instrument="double-bass", response=response), RATE).analyze_all(x)
        shown[response] = [(r.time, r.cents) for r in rs if r.active]
    normal = np.array([c for _, c in shown["normal"]])
    steady = np.array([c for _, c in shown["steady"]])
    # nothing during the attack, then far less movement while the string settles
    assert shown["steady"][0][0] >= 0.5 + STEADY_ATTACK
    assert np.ptp(steady) < 0.5 * np.ptp(normal)
    assert abs(steady[-1]) < 1.0


def phone_e1(settings: Settings, x: np.ndarray):
    """How a phone hears a bass's low E: when the first reading comes after the pluck (seconds, None: never), and
    the share of the following three seconds the note is shown, and is E1."""
    rs = [r for r in Tuner(settings, RATE).analyze_all(x) if r.time >= 1.0]
    first = next((r.time - 1.0 for r in rs if r.active), None)
    later = [r for r in rs if 0.5 <= r.time - 1.0 <= 3.5]
    e1 = notes.parse("E1")
    return (first, sum(r.active for r in later) / len(later),
            sum(r.active and r.target_midi == e1 for r in later) / len(later))


def test_low_e_through_a_phone_microphone():
    # La fundamental cortada por el micrófono (pasaaltos de cuarto orden a 200 Hz), el ruido a 20 dB: la nota se
    # lee en seguida y no se pierde mientras se apaga (antes: a los 0,6 s, y solo la mitad del tiempo).
    x = phone_bass()
    for s in (Settings(instrument="bass"), Settings()):
        first, shown, right = phone_e1(s, x)
        assert first is not None and first < 0.2, (s.instrument, first)
        assert shown > 0.85, (s.instrument, shown)
        assert right == shown, s.instrument
    r = [r for r in Tuner(Settings(instrument="bass"), RATE).analyze_all(x) if r.active and r.time > 2.5][-1]
    assert abs(r.cents) < 0.5


def test_low_e_still_not_read_in_the_room_alone():
    # El mismo cuarto, sin nota: ni el pasabajos de la claridad ni la puerta en banda hacen notas del ruido.
    room = phone_bass()[:RATE]
    for s in (Settings(instrument="bass", learn_noise=False, min_level=-90.0),
              Settings(learn_noise=False, min_level=-90.0)):
        assert not any(r.raw > 0 for r in Tuner(s, RATE).analyze_all(room))
