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

import os
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))
OUT = ROOT / "docs" / "img" / "manual"
SIZE = (720, 640)


def main() -> int:
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    os.environ["XDG_CONFIG_HOME"] = tempfile.mkdtemp(prefix="py-tuner-images-")
    import shiboken6
    from PySide6.QtWidgets import QApplication

    from py_tuner import interface, notes
    from py_tuner.gui import window
    from py_tuner.settings import Settings
    from py_tuner.tuner import Reading

    app = QApplication.instance() or QApplication([])
    OUT.mkdir(parents=True, exist_ok=True)

    def reading(midi: int, cents: float, string: int | None, s: Settings) -> Reading:
        target = notes.frequency(midi, s.a4)
        return Reading(frequency=target * 2 ** (cents / 1200), target_midi=midi, target_frequency=target,
                       cents=cents, string=string, level=-24.0, clarity=0.98, in_tune=abs(cents) <= s.tolerance)

    def shot(name: str, lang: str, s: Settings, r: Reading, phase: float = 0.3) -> None:
        win = window.Window(s, save=False)
        win.resize(*SIZE)
        win.show()
        # (la aguja llega a su sitio y el estroboscopio queda en una fase fija)
        for _ in range(60):
            win.show_reading(r, 0.05)
        win.strobe.model.phases = [phase, (2 * phase) % 1, (4 * phase) % 1]
        win.strobe.update()
        win.status.setText("pipewire · 48000 Hz")
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
