"""La ventana principal y el diálogo de ajustes.

Arriba, el instrumento, la afinación y el La de referencia; en el centro, la
nota en grande, la frecuencia y los cents; debajo, la aguja, el
estroboscopio y una fila de botones con las cuerdas (pulsar uno fija esa
cuerda; volver a pulsarlo devuelve la elección automática). Todo cambio se
guarda en la configuración en el acto.
"""

from __future__ import annotations

import sys
import time
from dataclasses import replace

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QFont, QKeySequence
from PySide6.QtWidgets import (QApplication, QButtonGroup, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                               QDoubleSpinBox, QFormLayout, QHBoxLayout, QLabel, QMainWindow, QMenu,
                               QMessageBox, QPushButton, QSpinBox, QToolButton, QVBoxLayout, QWidget)

from .. import __version__, audio, display, instruments, interface, notes
from .. import settings as settings_mod
from ..interface import tr
from ..settings import Settings
from ..tuner import LiveTuner, Reading
from .widgets import GREEN, Level, Needle, Spectrum, Strobe, Trace, deviation_color

# Los textos de las listas, en inglés (las claves de su traducción)
SCALE_LABELS = {"linear": "Linear", "fine": "Fine (the centre spread out)"}
RESPONSE_LABELS = {"normal": "Normal", "steady": "Steady (double bass)"}
STROBE_LABELS = {"vernier": "Vernier (one partial, three speeds)", "harmonics": "Harmonics (partials 1, 2, 3)"}
NAME_LABELS = {"english": "English (C D E)", "latin": "Latin (Do Re Mi)", "german": "German (C D E … H)"}
DISPLAY_LABELS = {"both": "Needle and strobe", "needle": "Needle", "strobe": "Strobe"}


class SettingsDialog(QDialog):
    """The less frequent settings: input, note names, view and analysis."""

    def __init__(self, s: Settings, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Settings"))
        form = QFormLayout(self)

        self.device = QComboBox()
        self.device.addItem(tr("Default input"), None)
        for index, name, rate in audio.input_devices():
            self.device.addItem(f"{name} ({rate} Hz)", name)
        i = self.device.findData(s.device)
        self.device.setCurrentIndex(max(0, i))
        form.addRow(tr("Input device"), self.device)

        self.channel = QComboBox()
        self.channel.addItem(tr("Mix of all channels"), "mix")
        for n in range(1, 9):
            self.channel.addItem(tr("Channel {number}", number=n), str(n))
        self.channel.setCurrentIndex(max(0, self.channel.findData(s.channel)))
        form.addRow(tr("Channel"), self.channel)

        self.names = QComboBox()
        for key in notes.NAME_SYSTEMS:
            self.names.addItem(tr(NAME_LABELS[key]), key)
        self.names.setCurrentIndex(self.names.findData(s.names))
        form.addRow(tr("Note names"), self.names)

        self.accidentals = QComboBox()
        self.accidentals.addItem(tr("Sharps ({sign})", sign=notes.SHARP), "sharps")
        self.accidentals.addItem(tr("Flats ({sign})", sign=notes.FLAT), "flats")
        self.accidentals.addItem(tr("Both ({sharp}/{flat})", sharp="F" + notes.SHARP, flat="G" + notes.FLAT),
                                 "both")
        self.accidentals.setCurrentIndex(self.accidentals.findData(s.accidentals))
        form.addRow(tr("Accidentals"), self.accidentals)

        self.view = QComboBox()
        for key in settings_mod.DISPLAYS:
            self.view.addItem(tr(DISPLAY_LABELS[key]), key)
        self.view.setCurrentIndex(self.view.findData(s.display))
        form.addRow(tr("Show"), self.view)

        self.language = QComboBox()
        self.language.addItem(tr("The system's"), "")
        for code, native in interface.names().items():
            self.language.addItem(native, code)
        self.language.setCurrentIndex(max(0, self.language.findData(s.language)))
        self.language.setToolTip(tr("The new language is used from the next time the program starts."))
        form.addRow(tr("Language"), self.language)

        def spin(value: float, lo: float, hi: float, step: float, decimals: int, suffix: str) -> QDoubleSpinBox:
            box = QDoubleSpinBox()
            box.setRange(lo, hi)
            box.setSingleStep(step)
            box.setDecimals(decimals)
            box.setSuffix(suffix)
            box.setValue(value)
            return box

        self.tolerance = spin(s.tolerance, 0.1, 50, 0.1, 1, " " + tr("cents"))
        self.tolerance.setToolTip(tr("A note within this many cents counts as in tune (shown green)."))
        form.addRow(tr("In tune within"), self.tolerance)
        self.min_level = spin(s.min_level, -120, 0, 1, 0, " dBFS")
        self.min_level.setToolTip(tr("Sounds quieter than this are ignored. Raise it in a noisy room."))
        form.addRow(tr("Ignore below"), self.min_level)
        self.smoothing = spin(s.smoothing, 0.05, 5, 0.05, 2, " s")
        self.smoothing.setToolTip(tr("How many seconds the reading averages: longer is steadier, shorter "
                                     "follows faster."))
        form.addRow(tr("Smoothing"), self.smoothing)
        self.periods = spin(s.periods, 4, 64, 1, 0, " " + tr("periods"))
        self.periods.setToolTip(tr("Length of each analysis frame, in periods of the note: more is more "
                                   "precise, fewer reacts faster."))
        form.addRow(tr("Analysis frame"), self.periods)
        self.response = QComboBox()
        for key in settings_mod.RESPONSES:
            self.response.addItem(tr(RESPONSE_LABELS[key]), key)
        self.response.setCurrentIndex(self.response.findData(s.response))
        self.response.setToolTip(tr("Steady: for the double bass and other low strings whose pitch moves as "
                                    "they sound. The attack of each pluck is left out, the reading averages "
                                    "at least 1.5 s, the quiet tail of the note is still read (with an "
                                    "instrument's strings), and the needle moves more slowly."))
        form.addRow(tr("Response"), self.response)

        self.strobe_mode = QComboBox()
        for key in settings_mod.STROBE_MODES:
            self.strobe_mode.addItem(tr(STROBE_LABELS[key]), key)
        self.strobe_mode.setCurrentIndex(self.strobe_mode.findData(s.strobe_mode))
        self.strobe_mode.setToolTip(tr("Vernier: every band follows the clearest partial, at one, two and four "
                                       "times the speed. Harmonics: each band shows a partial of its own."))
        form.addRow(tr("Strobe"), self.strobe_mode)
        self.trace = QCheckBox(tr("Show the history of the deviation"))
        self.trace.setChecked(s.show_trace)
        form.addRow("", self.trace)
        self.spectrum = QCheckBox(tr("Show the spectrum, with its peaks named"))
        self.spectrum.setChecked(s.show_spectrum)
        form.addRow("", self.spectrum)
        self.needle_scale = QComboBox()
        for key in settings_mod.NEEDLE_SCALES:
            self.needle_scale.addItem(tr(SCALE_LABELS[key]), key)
        self.needle_scale.setCurrentIndex(self.needle_scale.findData(s.needle_scale))
        self.needle_scale.setToolTip(tr("Fine: the last few cents take half of each side of the scale, and the "
                                        "rest up to 50 the other half."))
        form.addRow(tr("Needle scale"), self.needle_scale)
        self.learn_noise = QCheckBox(tr("Learn the room's noise"))
        self.learn_noise.setChecked(s.learn_noise)
        self.learn_noise.setToolTip(tr("Ignore what does not stand 10 dB over the background noise, learned while "
                                       "nothing plays. Turn it off to read the faintest tails of a note."))
        form.addRow("", self.learn_noise)

        def whole(value: int, lo: int, hi: int) -> QSpinBox:
            box = QSpinBox()
            box.setRange(lo, hi)
            box.setValue(value)
            return box

        self.transpose = whole(s.transpose, -12, 12)
        self.transpose.setSuffix(" " + tr("semitones"))
        self.transpose.setToolTip(tr("The names shown are moved this many semitones, for a transposing "
                                     "instrument (2 for one in B-flat); the pitch measured is the same."))
        form.addRow(tr("Transpose"), self.transpose)
        self.capo = whole(s.capo, 0, 12)
        self.capo.setToolTip(tr("A capo at this fret raises every string as many semitones."))
        form.addRow(tr("Capo"), self.capo)
        self.offsets = dict(s.offsets)
        offsets = QPushButton(tr("Note offsets…"))
        offsets.setToolTip(tr("Tune some notes a few cents off equal temperament, in every octave."))
        offsets.clicked.connect(self.edit_offsets)
        form.addRow(tr("Offsets"), offsets)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def edit_offsets(self) -> None:
        dlg = OffsetsDialog(self.offsets, self._names, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.offsets = dlg.offsets()

    @property
    def _names(self) -> tuple[str, str]:
        return self.names.currentData(), self.accidentals.currentData()

    def apply_to(self, s: Settings) -> Settings:
        return replace(s, device=self.device.currentData(), channel=self.channel.currentData(),
                       names=self.names.currentData(), accidentals=self.accidentals.currentData(),
                       display=self.view.currentData(), language=self.language.currentData(),
                       tolerance=self.tolerance.value(),
                       min_level=self.min_level.value(), smoothing=self.smoothing.value(),
                       periods=self.periods.value(), response=self.response.currentData(),
                       strobe_mode=self.strobe_mode.currentData(),
                       show_trace=self.trace.isChecked(), show_spectrum=self.spectrum.isChecked(),
                       needle_scale=self.needle_scale.currentData(), learn_noise=self.learn_noise.isChecked(),
                       transpose=self.transpose.value(),
                       capo=self.capo.value(), offsets=dict(self.offsets)).validated()


class OffsetsDialog(QDialog):
    """The cents each note name is tuned off equal temperament, in every octave (as Strobie's note offsets)."""

    def __init__(self, offsets: dict[str, float], names: tuple[str, str], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Note offsets"))
        form = QFormLayout(self)
        self.boxes: dict[str, QDoubleSpinBox] = {}
        system, accidentals = names
        for i, key in enumerate(notes.OFFSET_NAMES):
            box = QDoubleSpinBox()
            box.setRange(-settings_mod.MAX_OFFSET, settings_mod.MAX_OFFSET)
            box.setDecimals(1)
            box.setSingleStep(0.5)
            box.setSuffix(" " + tr("cents"))
            box.setValue(offsets.get(key, 0.0))
            self.boxes[key] = box
            form.addRow(notes.name(i, system, accidentals), box)
        clear = QPushButton(tr("All to zero"))
        clear.clicked.connect(lambda: [b.setValue(0.0) for b in self.boxes.values()])
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.addButton(clear, QDialogButtonBox.ButtonRole.ResetRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def offsets(self) -> dict[str, float]:
        return {k: b.value() for k, b in self.boxes.items() if b.value() != 0}


class Window(QMainWindow):
    def __init__(self, s: Settings, file: str | None = None, save: bool = True) -> None:
        super().__init__()
        self.file = file
        self.save = save
        self.live: LiveTuner | None = None
        self._s = s
        self.last = time.monotonic()
        self.setWindowTitle("py-tuner")
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(16, 12, 16, 12)

        # la barra de arriba: instrumento, afinación, La
        top = QHBoxLayout()
        self.instrument = QComboBox()
        for inst in instruments.INSTRUMENTS:
            self.instrument.addItem(tr(inst.name), inst.key)
        self.tuning = QComboBox()
        self.tuning.setMinimumContentsLength(14)
        self.a4 = QDoubleSpinBox()
        self.a4.setRange(notes.MIN_A4, notes.MAX_A4)
        self.a4.setDecimals(1)
        self.a4.setSingleStep(0.1)
        self.a4.setSuffix(" Hz")
        self.a4.setToolTip(tr("Reference A4. Arrow keys step 0.1 Hz; Page Up/Down step 1 Hz."))
        self.a4.setKeyboardTracking(False)
        presets = QToolButton()
        presets.setText("▾")
        presets.setToolTip(tr("Common reference pitches"))
        presets.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(presets)
        for hz in notes.COMMON_A4:
            act = menu.addAction(f"{hz:g} Hz")
            act.triggered.connect(lambda _=False, hz=hz: self.a4.setValue(hz))
        presets.setMenu(menu)
        gear = QToolButton()
        gear.setText(tr("Settings…"))
        gear.clicked.connect(self.open_settings)
        top.addWidget(QLabel(tr("Instrument")))
        top.addWidget(self.instrument)
        top.addWidget(self.tuning, 1)
        top.addSpacing(12)
        top.addWidget(QLabel("A4"))
        top.addWidget(self.a4)
        top.addWidget(presets)
        top.addSpacing(12)
        self.tone_button = QToolButton()
        self.tone_button.setText(tr("Tone"))
        self.tone_button.setToolTip(tr("Play the note: the locked string, or the note shown, or A4"))
        self.tone_button.clicked.connect(self.play_tone)
        top.addWidget(self.tone_button)
        top.addWidget(gear)
        layout.addLayout(top)

        # la nota
        self.note = QLabel("--")
        self.note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        f = QFont(self.font())
        f.setPointSize(64)
        f.setBold(True)
        self.note.setFont(f)
        self.info = QLabel("")
        self.info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        f2 = QFont(self.font())
        f2.setPointSize(15)
        self.info.setFont(f2)
        self.cents = QLabel("")
        self.cents.setAlignment(Qt.AlignmentFlag.AlignCenter)
        f3 = QFont(self.font())
        f3.setPointSize(26)
        f3.setBold(True)
        self.cents.setFont(f3)
        layout.addWidget(self.note)
        layout.addWidget(self.cents)
        layout.addWidget(self.info)

        self.needle = Needle()
        self.strobe = Strobe()
        layout.addWidget(self.needle, 1)
        layout.addWidget(self.strobe)
        self.trace = Trace()
        layout.addWidget(self.trace)
        self.spectrum = Spectrum()
        layout.addWidget(self.spectrum)
        self._spectrum_time = 0.0

        # las cuerdas
        self.strings_row = QHBoxLayout()
        self.strings_row.addStretch(1)
        self.string_group = QButtonGroup(self)
        self.string_group.setExclusive(False)
        self.string_group.idClicked.connect(self.string_clicked)
        self.strings_box = QWidget()
        self.strings_box.setLayout(self.strings_row)
        layout.addWidget(self.strings_box)

        # la barra de estado: dispositivo y nivel
        self.level = Level()
        self.status = QLabel("")
        self.statusBar().addWidget(self.status, 1)
        self.statusBar().addPermanentWidget(QLabel(tr("Level")))
        self.statusBar().addPermanentWidget(self.level)

        quit_act = QAction(tr("Quit"), self)
        quit_act.setShortcut(QKeySequence.StandardKey.Quit)
        quit_act.triggered.connect(self.close)
        self.addAction(quit_act)
        about = QAction(tr("About"), self)
        about.setShortcut(QKeySequence("F1"))
        about.triggered.connect(self.about)
        self.addAction(about)

        self._loading = False
        self.load_controls(s)
        self.instrument.currentIndexChanged.connect(self.instrument_changed)
        self.tuning.currentIndexChanged.connect(self.tuning_changed)
        self.a4.valueChanged.connect(lambda v: self.change(a4=round(v, 1)))

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(16)
        self.resize(720, 640)

    # --- la configuración ---

    @property
    def s(self) -> Settings:
        return self._s

    def load_controls(self, s: Settings) -> None:
        """Puts S in the controls without reacting to the changes it causes."""
        self._loading = True
        self.instrument.setCurrentIndex(self.instrument.findData(s.instrument))
        self.fill_tunings(s)
        self.a4.setValue(s.a4)
        self.fill_strings(s)
        self.needle.tolerance = self.strobe.tolerance = s.tolerance
        self.needle.scale = s.needle_scale
        self.needle.response = s.response
        self.level.gate = s.min_level
        self.needle.setVisible(s.display in ("both", "needle"))
        self.strobe.setVisible(s.display in ("both", "strobe"))
        self.trace.tolerance = s.tolerance
        self.trace.setVisible(s.show_trace)
        self.spectrum.setVisible(s.show_spectrum)
        self._loading = False

    def fill_tunings(self, s: Settings) -> None:
        inst = s.instrument_preset()
        self.tuning.clear()
        for t in inst.tunings:
            self.tuning.addItem(f"{tr(t.name)}   ({' '.join(t.strings)})", t.name)
        # (el modo cromático no tiene afinaciones: la lista no se muestra)
        self.tuning.setVisible(bool(inst.tunings))
        if inst.tunings:
            self.tuning.setCurrentIndex(max(0, self.tuning.findData(inst.tuning(s.tuning).name)))

    def fill_strings(self, s: Settings) -> None:
        for b in self.string_group.buttons():
            self.string_group.removeButton(b)
            b.deleteLater()
        while self.strings_row.count() > 1:
            item = self.strings_row.takeAt(1)
            if item.widget():
                item.widget().deleteLater()
        labels = display.string_labels(s)
        for i, lab in enumerate(labels):
            b = QPushButton(lab)
            b.setCheckable(True)
            b.setChecked(s.string == i)
            b.setMinimumWidth(56)
            b.setToolTip(tr("Tune this string only (click again for automatic)"))
            self.string_group.addButton(b, i)
            self.strings_row.addWidget(b)
        self.strings_row.addStretch(1)
        self.strings_box.setVisible(bool(labels))

    def change(self, **values) -> None:
        if self._loading:
            return
        new = replace(self._s, **values).validated()
        self.apply(new)

    def apply(self, new: Settings) -> None:
        input_changed = (new.device, new.channel, new.rate) != (self._s.device, self._s.channel, self._s.rate)
        self._s = new
        self.load_controls(new)
        if self.save:
            settings_mod.save(new)
        if input_changed and self.live is not None:
            self.restart()
        elif self.live is not None:
            self.live.configure(new)

    def instrument_changed(self) -> None:
        if self._loading:
            return
        key = self.instrument.currentData()
        inst = instruments.with_custom(instruments.find(key), self._s.custom_tunings)
        self.change(instrument=key, tuning=inst.tunings[0].name if inst.tunings else "", string=None)

    def tuning_changed(self) -> None:
        if self._loading or self.tuning.currentData() is None:
            return
        self.change(tuning=self.tuning.currentData(), string=None)

    def string_clicked(self, index: int) -> None:
        self.change(string=None if self._s.string == index else index)

    def open_settings(self) -> None:
        dlg = SettingsDialog(self._s, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.apply(dlg.apply_to(self._s))

    def about(self) -> None:
        QMessageBox.about(self, tr("About py-tuner"),
                          f"<b>py-tuner {__version__}</b><p>"
                          + tr("An accurate tuner for guitar, bass, double bass and violin.")
                          + "</p><p>Nicolas Vaughan &lt;nicolasvaughan@proton.me&gt;<br>"
                          + tr("GNU General Public License, version 3 or later.") + "</p>")

    # --- el sonido ---

    def start(self) -> bool:
        from ..app import open_source

        try:
            source = open_source(self._s, self.file)
            self.live = LiveTuner(self._s, source)
            self.live.start()
        except Exception as exc:  # noqa: BLE001 (PortAudio levanta varios tipos)
            self.live = None
            self.status.setText(tr("Cannot open the input: {error}", error=exc))
            return False
        name = getattr(source, "device_name", None) or self.file or "input"
        self.status.setText(f"{name} · {source.rate} Hz")
        return True

    def restart(self) -> None:
        if self.live is not None:
            self.live.stop()
            self.live = None
        self.start()

    def closeEvent(self, event) -> None:
        self.timer.stop()
        if self.live is not None:
            self.live.stop()
        super().closeEvent(event)

    def play_tone(self) -> None:
        """Plays the locked string, or else the note shown, or else A4 (as pianito's tone, by Axel Stevens)."""
        from .. import tone
        from ..tuner import Tuner

        s = self._s
        tuner = self.live.tuner if self.live is not None else Tuner(s, 48000)
        shown = getattr(self, "shown", None)
        if s.string is not None and tuner.string_midis and s.string < len(tuner.string_midis):
            midi = tuner.string_midis[s.string]
        elif shown is not None and shown.active:
            midi = shown.target_midi
        else:
            midi = 69
        freq = tuner.target_frequency(midi)
        try:
            tone.play(freq)
        except Exception as exc:  # noqa: BLE001 (PortAudio levanta varios tipos)
            self.status.setText(tr("cannot play the tone: {error}", error=exc))
            return
        self.status.setText(tr("{note}: {frequency} Hz", note=display.note_full(midi, s),
                               frequency=display.freq_text(freq)))

    # --- la pantalla ---

    def tick(self) -> None:
        now = time.monotonic()
        dt, self.last = now - self.last, now
        r = self.live.reading if self.live is not None else Reading()
        self.show_reading(r, dt)
        # el espectro, diez veces por segundo, de las muestras más recientes
        if self._s.show_spectrum and self.live is not None and now - self._spectrum_time >= 0.1:
            self._spectrum_time = now
            self.show_spectrum(self.live.source.buffer.latest(display.SPECTRUM_SAMPLES), self.live.source.rate, r)
        if self.live is not None and self.live.error:
            self.status.setText(self.live.error)

    def show_spectrum(self, samples, rate: float, r: Reading) -> None:
        freqs, levels = display.spectrum(samples, rate)
        named = [(f, display.peak_label(f, self._s)) for f, _ in display.peaks(samples, rate)]
        self.spectrum.set_data(freqs, levels, named, r.target_frequency if r.active else 0.0)

    def show_reading(self, r: Reading, dt: float) -> None:
        s = self._s
        # (la marca del medidor: el nivel que debe alcanzar un sonido, el aprendido si lo hay)
        self.level.gate = r.gate if r.gate > -200 else s.min_level
        self.level.set_level(r.level)
        cents = r.cents if r.active else None
        self.needle.set_cents(cents, dt)
        self.strobe.advance(cents, dt, r.strobe)
        self.trace.add(cents, r.time)
        self.shown = r
        if not r.active:
            self.note.setText("--")
            self.note.setStyleSheet("")
            self.cents.setText("")
            self.info.setText(tr("Play a note"))
            for b in self.string_group.buttons():
                b.setStyleSheet("")
            return
        color = deviation_color(r.cents, s.tolerance).name()
        self.note.setText(display.note_full(r.target_midi, s))
        self.note.setStyleSheet(f"color: {color}")
        self.cents.setText(tr("{cents} cents", cents=display.cents_text(r)))
        self.cents.setStyleSheet(f"color: {color}")
        self.info.setText(f"{display.freq_text(r.frequency)} Hz    →    "
                          f"{display.freq_text(r.target_frequency)} Hz")
        for i, b in enumerate(self.string_group.buttons()):
            if r.string == self.string_group.id(b) and r.string is not None:
                b.setStyleSheet(f"font-weight: bold; border: 2px solid {color};"
                                if not r.in_tune else f"font-weight: bold; border: 2px solid {GREEN.name()};")
            else:
                b.setStyleSheet("")


def translate_qt(app) -> None:
    """Las palabras propias de Qt (OK, Cancel, los nombres de las teclas) en el idioma de la interfaz."""
    from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator

    code = interface.current()
    if code == interface.REFERENCE:
        return
    QLocale.setDefault(QLocale(code))  # (también los números: 440,0 Hz)
    translator = QTranslator(app)
    if translator.load(f"qtbase_{code}", QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
        app.installTranslator(translator)
        app._qt_translator = translator  # (que el recolector no se lo lleve)


def run(s: Settings, file: str | None = None) -> int:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("py-tuner")
    app.setDesktopFileName("py-tuner")
    translate_qt(app)
    # El ícono de la ventana, en todos sus tamaños (los de tools/icons.py)
    from pathlib import Path

    from PySide6.QtGui import QIcon

    icon = QIcon()
    for png in sorted((Path(__file__).resolve().parent.parent / "icons" / "linux" / "hicolor").glob(
            "*/apps/py-tuner.png")):
        icon.addFile(str(png))
    app.setWindowIcon(icon)
    win = Window(s, file)
    win.show()
    if not win.start():
        QMessageBox.warning(win, "py-tuner", win.status.text())
    code = app.exec()
    # La ventana se borra aquí, con Qt entero: sus conexiones con lambdas forman ciclos de referencias, y sin esto
    # Python la destruía al salir, después de la aplicación, y el proceso caía (SIGBUS o SIGABRT) al cerrarse.
    if win.live is not None:
        win.live.stop()
    import shiboken6

    shiboken6.delete(win)
    return code
