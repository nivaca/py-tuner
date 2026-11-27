#!/usr/bin/env python3
"""Hace las imágenes del README y de los manuales (docs/MANUAL_en.tex, docs/MANUAL_es.tex), en inglés y en español:

    uv run python tools/manual_images.py

Escribe docs/img/main_IDIOMA.png (la del README y de los metadatos de AppStream) y docs/img/manual/NOMBRE_IDIOMA.png:
la ventana con una cuerda afinada y con una desafinada, el modo cromático con nombres latinos, la cuerda fija,
solo el estroboscopio y el diálogo de configuración; y, con tools/terminal_images.py, docs/img/tui_IDIOMA.png y
docs/img/cli_IDIOMA.png. Las lecturas son fijas (no hace falta sonido), las ventanas
se dibujan fuera de la pantalla, y la configuración del usuario no se lee ni se escribe (XDG_CONFIG_HOME apunta a
una carpeta temporal).
"""

from __future__ import annotations

import math
import os
import sys
import tempfile
import time
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))
OUT = ROOT / "docs" / "img" / "manual"
SIZE = (720, 760)


def main() -> int:
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    os.environ["XDG_CONFIG_HOME"] = tempfile.mkdtemp(prefix="py-tuner-images-")
    import shiboken6
    from PySide6.QtCore import qInstallMessageHandler
    from PySide6.QtWidgets import QApplication

    # La plataforma "offscreen" avisa con cada ventana que no sabe de tamaños sugeridos: no importa aquí.
    def quiet(kind, context, message):
        if "propagateSizeHints" not in message:
            print(message, file=sys.stderr)

    qInstallMessageHandler(quiet)

    from py_tuner import display, interface, notes, tone
    from py_tuner.gui import window
    from py_tuner.settings import Settings
    from py_tuner.tuner import Reading

    app = QApplication.instance() or QApplication([])
    OUT.mkdir(parents=True, exist_ok=True)

    def reading(midi: int, cents: float, string: int | None, s: Settings) -> Reading:
        target = notes.frequency(midi, s.a4)
        return Reading(frequency=target * 2 ** (cents / 1200), target_midi=midi, target_frequency=target,
                       cents=cents, string=string, level=-24.0, clarity=0.98, in_tune=abs(cents) <= s.tolerance)

    def shot(name: str, lang: str, s: Settings, r: Reading, phase: float = 0.3, sound=None) -> None:
        """SOUND, if given: the samples whose spectrum the window shows."""
        win = window.Window(s, save=False)
        win.resize(SIZE[0], SIZE[1] + (160 if s.show_spectrum else 0))
        # (sin su reloj: sin sonido detrás, dibujaría una lectura vacía sobre la que se pone aquí)
        win.timer.stop()
        win.show()
        # (la aguja llega a su sitio y el estroboscopio queda en una fase fija)
        for _ in range(60):
            win.show_reading(r, 0.05)
        win.strobe.model.phases = [phase, (2 * phase) % 1, (4 * phase) % 1]
        # La historia: una cuerda que se afina, desde 15 cents fuera hasta la lectura, con una pulsación nueva
        # a la mitad (un hueco sin nota).
        now = time.monotonic()
        start = r.cents - 9 if r.cents <= 1 else r.cents + 9  # (desde su mismo lado, más lejos)
        points = []
        for k in range(100):
            t = now - 10 + k * 0.1
            if 48 <= k < 52:
                points.append((t, None))
                continue
            share = min(1.0, k / 80)
            points.append((t, start + (r.cents - start) * share + 0.4 * math.sin(k / 3)))
        win.trace.points = points
        win.strobe.update()
        win.status.setText("pipewire · 48000 Hz")
        if sound is not None:
            win.show_spectrum(sound, tone.RATE, r)
        app.processEvents()
        path = (ROOT / "docs" / "img" / f"main_{lang}.png") if name == "main" else OUT / f"{name}_{lang}.png"
        win.grab().save(str(path))
        print(f"Wrote {path.relative_to(ROOT)}")
        win.close()
        shiboken6.delete(win)

    for lang in ("en", "es"):
        interface.use(lang)
        window.translate_qt(app)
        guitar = Settings(instrument="guitar", tuning="Standard", language=lang)
        shot("main", lang, guitar, reading(notes.parse("G3"), 0.4, 3, guitar))
        shot("window", lang, guitar, reading(notes.parse("G3"), 0.4, 3, guitar))
        bass = Settings(instrument="bass", tuning="5-string", language=lang)
        shot("flat", lang, bass, reading(notes.parse("E1"), -12.3, 1, bass))
        violin = Settings(instrument="violin", string=2, a4=442.0, language=lang)
        shot("locked", lang, violin, reading(notes.parse("A4"), 3.1, 2, violin))
        chromatic = Settings(instrument="chromatic", tuning="", names="latin", accidentals="flats", language=lang)
        shot("chromatic", lang, chromatic, reading(notes.parse("Bb3"), -1.8, None, chromatic))
        strobe = replace(guitar, display="strobe")
        shot("strobe", lang, strobe, reading(notes.parse("E2"), 0.7, 0, strobe), phase=0.55)
        # La aguja en su escala fina y el espectro: un La 2 7,5 cents bajo (el tono de referencia del programa)
        fine = replace(guitar, needle_scale="fine", show_spectrum=True)
        a2 = reading(notes.parse("A2"), -7.5, 1, fine)
        shot("spectrum", lang, fine, a2, sound=tone.pluck(a2.frequency, 1.0)[-display.SPECTRUM_SAMPLES:])
        off = window.OffsetsDialog({"B": -2.0, "G": 1.5, "E": -1.0}, ("english", "sharps"))
        off.show()
        app.processEvents()
        path = OUT / f"offsets_{lang}.png"
        off.grab().save(str(path))
        print(f"Wrote {path.relative_to(ROOT)}")
        off.close()
        shiboken6.delete(off)
        dlg = window.SettingsDialog(guitar)
        dlg.show()
        app.processEvents()
        path = OUT / f"settings_{lang}.png"
        dlg.grab().save(str(path))
        print(f"Wrote {path.relative_to(ROOT)}")
        dlg.close()
        shiboken6.delete(dlg)
    interface.use("en")
    # la terminal y la línea de órdenes (tools/terminal_images.py, que necesita pyte, de las dependencias de desarrollo)
    import terminal_images

    terminal_images.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
