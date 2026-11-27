"""La ventana: los controles cambian la configuración, las lecturas se muestran y los dibujos se pintan."""

from __future__ import annotations

import time

import pytest
from conftest import string, write_wav

pytest.importorskip("PySide6")

import shiboken6  # noqa: E402
from PySide6.QtGui import QImage  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from py_tuner import notes, settings  # noqa: E402
from py_tuner.gui import widgets, window  # noqa: E402
from py_tuner.settings import Settings  # noqa: E402
from py_tuner.tuner import Reading  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def make(qapp):
    """Builds windows and dialogs and destroys them at the end of the test.

    Las conexiones con lambdas forman ciclos de referencias: sin borrarlas a
    mano, Python las destruiría al salir, después de la aplicación de Qt, y
    el proceso caería al terminar.
    """
    made = []

    def build(cls, *args, **kwargs):
        obj = cls(*args, **kwargs)
        made.append(obj)
        return obj

    yield build
    for obj in reversed(made):
        obj.close()
        shiboken6.delete(obj)


def render(widget) -> QImage:
    img = QImage(widget.size(), QImage.Format.Format_ARGB32)
    img.fill(0)
    widget.render(img)
    return img


def test_controls_change_and_save_settings(make):
    win = make(window.Window, Settings())
    win.instrument.setCurrentIndex(win.instrument.findData("bass"))
    assert win.s.instrument == "bass" and win.s.tuning == "Standard"
    assert [b.text() for b in win.string_group.buttons()] == ["E1", "A1", "D2", "G2"]
    win.tuning.setCurrentIndex(win.tuning.findData("5-string"))
    assert [b.text() for b in win.string_group.buttons()][0] == "B0"
    win.a4.setValue(441.3)
    assert win.s.a4 == 441.3
    saved = settings.load()
    assert (saved.instrument, saved.tuning, saved.a4) == ("bass", "5-string", 441.3)
    win.instrument.setCurrentIndex(win.instrument.findData("chromatic"))
    assert not win.strings_box.isVisibleTo(win)


def test_string_buttons_lock_and_unlock(make):
    win = make(window.Window, Settings(instrument="violin"))
    win.string_group.button(2).click()
    assert win.s.string == 2
    win.string_group.button(2).click()
    assert win.s.string is None


def test_reading_is_shown(make):
    win = make(window.Window, Settings(instrument="guitar", names="latin"))
    r = Reading(frequency=110.2, target_midi=45, target_frequency=110.0, cents=3.14, string=1, level=-20)
    win.show_reading(r, 0.016)
    assert win.note.text() == "La2"
    assert win.cents.text() == "+3.1 cents"
    assert "110.20 Hz" in win.info.text()
    win.show_reading(Reading(level=-80), 0.016)
    assert win.note.text() == "--"


def test_settings_dialog_applies(make):
    s = Settings()
    dlg = make(window.SettingsDialog, s)
    dlg.names.setCurrentIndex(dlg.names.findData("german"))
    dlg.view.setCurrentIndex(dlg.view.findData("strobe"))
    dlg.tolerance.setValue(2.5)
    dlg.response.setCurrentIndex(dlg.response.findData("steady"))
    new = dlg.apply_to(s)
    assert (new.names, new.display, new.tolerance, new.response) == ("german", "strobe", 2.5, "steady")
    win = make(window.Window, s)
    win.apply(new)
    assert not win.needle.isVisibleTo(win) and win.strobe.isVisibleTo(win)
    assert win.needle.response == "steady"


@pytest.mark.parametrize("cents", [None, 0.0, 3.0, -40.0])
def test_widgets_paint(make, cents):
    for w in (make(widgets.Needle), make(widgets.Strobe), make(widgets.Level)):
        w.resize(400, 200)
        if isinstance(w, widgets.Needle):
            w.set_cents(cents, 0.1)
        elif isinstance(w, widgets.Strobe):
            w.advance(cents, 0.1)
        else:
            w.set_level(-30.0)
        img = render(w)
        assert not img.isNull()


def test_needle_follows_with_inertia(make):
    n = make(widgets.Needle)
    n.set_cents(20.0, 0.03)
    assert 0 < n.shown < 20
    for _ in range(50):
        n.set_cents(20.0, 0.03)
    assert n.shown == pytest.approx(20.0, abs=0.01)


def test_needle_lags_more_when_steady(make):
    normal, steady = make(widgets.Needle), make(widgets.Needle)
    steady.response = "steady"
    for n in (normal, steady):
        n.set_cents(20.0, 0.1)
    assert 0 < steady.shown < normal.shown < 20


def test_deviation_colors():
    assert widgets.deviation_color(0.5, 1.0) == widgets.GREEN
    assert widgets.deviation_color(-3.0, 1.0) == widgets.AMBER
    assert widgets.deviation_color(9.0, 1.0) == widgets.RED


def test_window_with_a_file(make, tmp_path):
    write_wav(tmp_path / "a.wav", string(notes.frequency(notes.parse("A4")) * 2 ** (1.5 / 1200), seconds=3.0,
                                         decay=0.1))
    win = make(window.Window, Settings(instrument="violin"), str(tmp_path / "a.wav"), save=False)
    assert win.start()
    try:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and win.note.text() != "A4":
            QApplication.processEvents()
            time.sleep(0.02)
        assert win.note.text() == "A4"
        assert win.cents.text() in ("+1.5 cents", "+1.4 cents", "+1.6 cents")
        assert "a.wav" in win.status.text()
    finally:
        win.live.stop()
    

def test_the_program_quits_cleanly(tmp_path):
    # El programa entero, en otro proceso: se abre la ventana, se cierra, y el proceso termina sin caer (antes
    # caía al salir, con SIGBUS o SIGABRT, al destruir Python la ventana después de la aplicación de Qt).
    import os
    import subprocess
    import sys

    write_wav(tmp_path / "a.wav", string(110.0, seconds=2.0))
    code = ("import sys; from PySide6.QtCore import QTimer; from PySide6.QtWidgets import QApplication; "
            "from py_tuner.gui import window; from py_tuner.settings import Settings; "
            "app = QApplication(sys.argv[:1]); "
            "QTimer.singleShot(1500, lambda: [w.close() for w in app.topLevelWidgets()]); "
            "sys.exit(window.run(Settings(needle_scale='fine', show_spectrum=True), sys.argv[1]))")
    done = subprocess.run([sys.executable, "-c", code, str(tmp_path / "a.wav")], capture_output=True, text=True,
                          timeout=60, env={**os.environ, "XDG_CONFIG_HOME": str(tmp_path / "config")})
    assert done.returncode == 0, done.stderr[-2000:]
