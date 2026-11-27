# Registro de cambios

Los cambios de cada versión de py-tuner. Las versiones, con el RPM, la
AppImage, el wheel y el código, están en
[Codeberg](https://codeberg.org/nivaca/py-tuner/releases) y en
[GitHub](https://github.com/nivaca/py-tuner/releases).

## Sin publicar

- El ruido del cuarto, aprendido mientras no suena nada: lo que no lo supera
  en 10 dB se ignora (se puede quitar). En las grabaciones de guitarra, ya
  ninguna nota falsa en modo guitarra.
- El espectro, con sus picos más claros nombrados y los armónicos de la
  nota buscada marcados, en la ventana y en la terminal (`f`).
- Una escala fina para la aguja, donde los últimos 5 cents ocupan la mitad
  de cada lado (`--needle fine`, `g` en la terminal).

## 0.2.0 — 2026-11-27

La nota correcta en cuerdas reales, y un estroboscopio de verdad.

- Menos notas equivocadas en cuerdas reales: una decisión de la octava y la
  duodécima por los armónicos de cada candidato, una nota nueva sin
  pulsación espera (más si es armónico o subarmónico de la que suena), y con
  cuerdas la búsqueda se queda cerca de ellas. En once grabaciones de
  guitarra, una nota falsa donde había quince. La nota o cuerda elegida se
  mantiene hasta 10 cents pasada la mitad hacia la siguiente.
- Un estroboscopio de verdad: cada banda sigue la fase de una parcial, en
  modo vernier (la parcial más clara a tres velocidades) o de armónicos (las
  parciales 1, 2 y 3), y se apaga cuando la parcial se pierde en el ruido.
- La historia de la desviación, en la ventana y en la terminal.
- Desviaciones por nota, los nombres transpuestos, una cejilla y un tono de
  referencia (`py-tuner tone`, el botón Tono, `p` en la terminal).
- El crédito a los afinadores de donde vienen estas ideas: Strobie, Entropy
  Piano Tuner, Tuneo y pianito (docs/TERCEROS_es.md).
- `--once` espera una lectura de al menos 0,3 segundos de sonido antes de
  darla por estable (con uno o dos cuadros, una errada podía pasar, como en
  una máquina lenta), y un cuadro más corto de lo que pide el análisis, o cuyos
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
