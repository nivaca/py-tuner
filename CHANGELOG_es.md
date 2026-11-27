# Registro de cambios

Los cambios de cada versión de py-tuner. Las versiones, con el RPM, la
AppImage, el wheel y el código, están en
[Codeberg](https://codeberg.org/nivaca/py-tuner/releases) y en
[GitHub](https://github.com/nivaca/py-tuner/releases).

## Sin publicar

- `--once` espera una docena de cuadros antes de dar una lectura por
  estable (con uno o dos, una errada podía pasar, como en una máquina
  lenta), y un cuadro más corto de lo que pide el análisis, o cuyos
  armónicos no concuerdan con su período, no da lectura en vez de dar una
  mala.
- Imágenes de la interfaz de terminal y de la línea de órdenes, en los
  README y los manuales (tools/terminal_images.py).

## 0.1.0 — 2026-11-27

La primera versión.

- Un afinador para guitarra, bajo, contrabajo y violín, con sus afinaciones
  habituales y otras, y un modo cromático; afinaciones propias en la
  configuración.
- La altura a partir de todos los armónicos de la cuerda, con su
  inarmonicidad: a unas centésimas de cent en una cuerda estable.
- Un La de referencia de 380 a 480 Hz, en décimas de hercio.
- Aguja y estroboscopio, en una ventana (PySide6), en la terminal a
  pantalla completa (curses) y en la línea de órdenes, que además mide una
  grabación WAV nota por nota.
- Nombres de las notas en inglés, latinos o alemanes, con sostenidos,
  bemoles o ambos (F♯/G♭); la interfaz en inglés o en español.
