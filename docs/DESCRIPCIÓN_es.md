# py-tuner 0.1.0: descripción

## Análisis

py-tuner es un afinador para guitarra, bajo, contrabajo y violín, con un modo cromático para cualquier otro instrumento. Escucha la tarjeta de sonido, reconoce la nota que suena, la compara con la cuerda más cercana de la afinación elegida (o con la que el usuario fije) y dice cuántos cents se aparta, con una aguja y con un estroboscopio. Funciona en una ventana, en la terminal a pantalla completa y en la línea de órdenes, donde además puede analizar una grabación WAV y decir, nota por nota, cuán afinada estaba.

El requisito central era la precisión. Su punto de partida fue el estudio de FMIT (Free Music Instrument Tuner), el afinador en C++ y Qt de Gilles Degottex, cuyo código se leyó pero no se copió. Ese estudio mostró dónde se pierde exactitud: FMIT promedia los armónicos sin pesos, con lo que un armónico débil y ruidoso pesa tanto como la fundamental; ignora la inarmonicidad de las cuerdas reales, cuyos parciales altos suenan algo agudos, y así su promedio sale agudo; mide pasos por cero, que los armónicos y el ruido desplazan, y promedia en hercios. Tampoco tenía pruebas que midieran el error contra una frecuencia conocida.

Los demás requisitos los fijó el autor. Los instrumentos son los cuatro de cuerda dichos, con sus afinaciones habituales y otras alternativas. No hacen falta temperamentos históricos ni escalas Scala, pero sí un La de referencia ajustable, con décimas de hercio (440, 441, 442...). Se quieren los dos modos de mostrar la desviación, aguja y estroboscopio, y las tres interfaces.

## Diseño

El programa se divide en capas que no se conocen más que hacia abajo. `pitch.py` estima la frecuencia de un trozo de señal y no sabe nada de notas ni de sonido. `notes.py` convierte frecuencias en notas y nombres, contra el La de referencia. `instruments.py` guarda los instrumentos y sus afinaciones, cada una como una lista de cuerdas escritas como notas ("E2"). `stabilizer.py` convierte las estimaciones sueltas en una lectura estable. `tuner.py` lo junta todo: elige la nota o cuerda de comparación y calcula los cents; su clase `LiveTuner` corre el análisis en un hilo propio sobre una fuente de sonido. `audio.py` tiene las fuentes (el micrófono y los archivos WAV) y el búfer circular donde escriben. `settings.py` guarda la configuración, la misma para las tres interfaces. Encima están `cli.py`, `tui.py` y el paquete `gui`, más `display.py`, con lo que las tres muestran igual (los nombres, las cifras y el movimiento del estroboscopio), y `app.py`, que lee las opciones.

La decisión principal fue separar la estimación en dos pasos, como FMIT, pero cambiando cada uno: un paso grueso que no pueda equivocarse de octava y uno fino que aproveche todos los armónicos de la cuerda con su inarmonicidad. La otra fue medir siempre en cents, nunca en hercios, desde el promedio de las lecturas hasta las pruebas. Las interfaces no analizan: leen la última lectura del hilo de análisis, y así ninguna se traba aunque un cuadro de una cuerda grave tarde unos milisegundos.

## Implementación

Está escrito en Python 3.14, con numpy para el análisis, sounddevice (y PortAudio) para la tarjeta de sonido, PySide6 para la ventana y el módulo curses de la biblioteca estándar para la terminal. Tiene 29 archivos de código, unas 3500 líneas, de las cuales algo más de 1000 son pruebas.

### El paso grueso

Es el método de McLeod: la función de diferencia cuadrada normalizada, calculada con la transformada de Fourier, cuyo primer pico alto da el período. Se toma el primero que alcance nueve décimos del más alto, no el más alto, para no elegir nunca el doble del período; su altura dice cuán periódico es el sonido y sirve para descartar el ruido.

### El paso fino

Trabaja sobre dieciséis períodos de la nota, con una ventana de Blackman-Harris. Cada armónico se busca en el máximo exacto de la transformada de la señal enventanada, evaluada en cualquier frecuencia, con el método de Newton sobre |X(f)|²; no hay interpolación entre casillas y, por tanto, tampoco su sesgo. La fundamental sale de un ajuste por mínimos cuadrados ponderados del modelo (f_n/n)² = f0² + f0²·B·n², que es exactamente lineal, con pesos (n·A_n)². Los picos que no superan en 12 dB el nivel del ruido (la mediana del espectro) quedan fuera. La matriz de exponenciales se arma como producto de una rejilla gruesa y una fina, nueve veces más rápido que de una vez.

### La lectura estable

Es la media recortada, la mitad central, del último medio segundo de estimaciones. Un salto de más de un tercio de semitono que se repite es otra nota; uno aislado se descarta. La nota se apaga tras 0,4 s sin tono.

## Validación

Las 114 pruebas corren a la vez con `tools/test.py`, cada archivo en un proceso propio, en unos cuatro segundos. Las del detector usan cuerdas sintéticas de frecuencia conocida, con armónicos, inarmonicidad, decaimiento y ruido: las cuerdas al aire de los cuatro instrumentos, desde el Si 0 del bajo de cinco cuerdas hasta el Mi 5 del violín, deben dar en cada cuadro menos de una décima de cent de error con ruido 40 dB por debajo; con ruido a 20 dB, la media de los errores debe quedarse junto a cero. También se prueban una fundamental débil o ausente, una cuerda muy inarmónica, un segundo armónico más fuerte que la fundamental, el silencio y el ruido puro, que no deben dar nota.

Las demás comprueban los nombres y frecuencias de las notas y las afinaciones, la respuesta del estabilizador a valores sueltos y a notas nuevas, la configuración (incluido un archivo dañado), los WAV de 8 a 32 bits, las opciones de la línea de órdenes y el informe de una grabación completa. La interfaz de terminal se prueba corriendo de verdad en una pseudoterminal, donde la prueba pulsa teclas y lee la pantalla; la ventana se dibuja fuera de la pantalla.

Además, la ventana y la terminal se revisaron a ojo mientras sonaba un WAV de seis cuerdas de guitarra desafinadas en cantidades conocidas (+3, -7,5, 0, +0,4, -1,2 y +12 cents), que el programa midió con errores de una centésima de cent, y la línea de órdenes se probó con el micrófono del computador.

## Plataforma

El programa está escrito para Linux, donde se desarrolló y probó, en Fedora. Por sus bibliotecas debería funcionar también en Windows y macOS, salvo la interfaz de terminal, que necesita curses y no existe en el Python de Windows; esto no se ha probado.

Necesita Python 3.14 o posterior, numpy, sounddevice con la biblioteca PortAudio del sistema y, para la ventana, PySide6. Usa cualquier entrada de sonido que PortAudio vea, a su frecuencia de muestreo (44,1 o 48 kHz, o la que se elija), y lee archivos WAV PCM de 8, 16, 24 y 32 bits. No necesita internet. El análisis gasta poco: un cuadro tarda unos 10 ms para las cuerdas más graves y 2 o 3 ms para las agudas, cuarenta veces por segundo.

## Ambiente

Fue desarrollado en Fedora 45, con Python 3.14 (en el entorno que uv arma para el proyecto), en noviembre de 2026. El código está en la carpeta del proyecto; todavía no se ha publicado ni tiene versiones empaquetadas.

Para correrlo desde el código, en la carpeta del proyecto: `uv run py-tuner` abre la ventana, `uv run py-tuner tui` la interfaz de terminal y `uv run py-tuner cli` la línea de órdenes; `uv run py-tuner devices` lista las entradas de sonido y `uv run py-tuner instruments` las afinaciones. Las opciones comunes (`--a4`, `--instrument`, `--tuning`, `--string`, `--device`, `--file`...) valen para los tres modos y solo para esa sesión, salvo que se añada `--save`.

La configuración se guarda en `~/.config/py-tuner/settings.json` (o bajo `$XDG_CONFIG_HOME`). La ventana y la terminal guardan ahí cada cambio en el acto. En ese archivo se pueden añadir afinaciones propias en `custom_tunings`. Las preguntas y comentarios pueden enviarse al autor, Nicolas Vaughan, a nicolasvaughan@proton.me.
