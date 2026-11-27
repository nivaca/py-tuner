# py-tuner 0.3.0: descripción

## Análisis

py-tuner es un afinador para guitarra, bajo, contrabajo y violín, con un modo cromático para cualquier otro instrumento. Escucha la tarjeta de sonido, reconoce la nota que suena, la compara con la cuerda más cercana de la afinación elegida (o con la que el usuario fije) y dice cuántos cents se aparta, con una aguja y con un estroboscopio. Funciona en una ventana, en la terminal a pantalla completa y en la línea de órdenes, donde además puede analizar una grabación WAV y decir, nota por nota, cuán afinada estaba.

El requisito central era la precisión. Su punto de partida fue el estudio de FMIT (Free Music Instrument Tuner), el afinador en C++ y Qt de Gilles Degottex, cuyo código se leyó pero no se copió. Ese estudio mostró dónde se pierde exactitud: FMIT promedia los armónicos sin pesos, con lo que un armónico débil y ruidoso pesa tanto como la fundamental; ignora la inarmonicidad de las cuerdas reales, cuyos parciales altos suenan algo agudos, y así su promedio sale agudo; mide pasos por cero, que los armónicos y el ruido desplazan, y promedia en hercios. Tampoco tenía pruebas que midieran el error contra una frecuencia conocida.

Tras la primera versión se estudiaron otros cuatro afinadores libres, cuyas fuentes se leyeron sin copiarlas y a los que se da crédito en `docs/TERCEROS_es.md`: Tuneo, de Braulio Ríos; Strobie, de Davorin Šego; pianito, de Axel Stevens, y Entropy Piano Tuner, de Haye Hinrichsen y Christoph Wick. Las grabaciones de cuerdas de guitarra de Tuneo mostraron un requisito nuevo: en una cuerda real, py-tuner oía notas que no estaban (una octava o una duodécima bajo la verdadera, en la cola de una nota o en el golpe de la pulsación) y a veces la octava de arriba en cuerdas de acero. No bastaba ser preciso: había que acertar la nota.

Los demás requisitos los fijó el autor. Los instrumentos son los cuatro de cuerda dichos, con sus afinaciones habituales y otras alternativas. No hacen falta temperamentos históricos ni escalas Scala, pero sí un La de referencia ajustable, con décimas de hercio (440, 441, 442...). Se quieren los dos modos de mostrar la desviación, aguja y estroboscopio, y las tres interfaces. Como los demás programas del autor, debía hablar español e inglés, escribir las notas también con las dos alteraciones a la vez (F♯/G♭), arrancar en el modo cromático, y publicarse empaquetado y firmado: un RPM para Fedora, una AppImage para cualquier Linux, los manuales en los dos idiomas.

## Diseño

El programa se divide en capas que no se conocen más que hacia abajo. `pitch.py` estima la frecuencia de un trozo de señal y no sabe nada de notas ni de sonido. `notes.py` convierte frecuencias en notas y nombres, contra el La de referencia. `instruments.py` guarda los instrumentos y sus afinaciones, cada una como una lista de cuerdas escritas como notas ("E2"). `stabilizer.py` convierte las estimaciones sueltas en una lectura estable. `tuner.py` lo junta todo: elige la nota o cuerda de comparación y calcula los cents; su clase `LiveTuner` corre el análisis en un hilo propio sobre una fuente de sonido. `audio.py` tiene las fuentes (el micrófono y los archivos WAV) y el búfer circular donde escriben. `settings.py` guarda la configuración, la misma para las tres interfaces. `interface.py` traduce los textos con `tr()`, que los busca en `locale/es.xml`. `strobe.py` es el estroboscopio, que sigue la fase de las parciales; `noise.py` aprende el ruido del cuarto, y `tone.py` hace el tono de referencia. Encima están `cli.py`, `tui.py` y el paquete `gui`, más `display.py`, con lo que las tres muestran igual (los nombres, las cifras y el movimiento del estroboscopio), y `app.py`, que lee las opciones.

La decisión principal fue separar la estimación en dos pasos, como FMIT, pero cambiando cada uno: un paso grueso que no pueda equivocarse de octava y uno fino que aproveche todos los armónicos de la cuerda con su inarmonicidad. La otra fue medir siempre en cents, nunca en hercios, desde el promedio de las lecturas hasta las pruebas. Las interfaces no analizan: leen la última lectura del hilo de análisis, y así ninguna se traba aunque un cuadro de una cuerda grave tarde unos milisegundos.

## Implementación

Está escrito en Python 3.14, con numpy para el análisis, sounddevice (y PortAudio) para la tarjeta de sonido, PySide6 para la ventana y el módulo curses de la biblioteca estándar para la terminal. Tiene 49 archivos de Python, unas 9100 líneas, de las cuales unas 2450 son pruebas; las herramientas de la carpeta `tools` hacen los íconos, las páginas de manual, las imágenes de los manuales, la AppImage, las firmas y el depósito en Zenodo, y miden el afinador con grabaciones reales (`tools/evaluate.py`).

### El paso grueso

Es el método de McLeod: la función de diferencia cuadrada normalizada, calculada con la transformada de Fourier, cuyo primer pico alto da el período. Se toma el primero que alcance nueve décimos del más alto, no el más alto, para no elegir nunca el doble del período; su altura dice cuán periódico es el sonido y sirve para descartar el ruido.

### El paso fino

Trabaja sobre dieciséis períodos de la nota, con una ventana de Blackman-Harris. Cada armónico se busca en el máximo exacto de la transformada de la señal enventanada, evaluada en cualquier frecuencia, con el método de Newton sobre |X(f)|²; no hay interpolación entre casillas y, por tanto, tampoco su sesgo. La fundamental sale de un ajuste por mínimos cuadrados ponderados del modelo (f_n/n)² = f0² + f0²·B·n², que es exactamente lineal, con pesos (n·A_n)². Los picos que no superan en 12 dB el nivel del ruido (la mediana del espectro) quedan fuera. La matriz de exponenciales sale de una rejilla gruesa y una fina, nueve veces más rápido.

### La octava

Los candidatos alrededor del período (un tercio, la mitad, el doble, el triple) se puntúan por lo que sobresalen sus armónicos del fondo del espectro, como la pila de armónicos de Strobie, menos lo que hay en sus medios armónicos, como los pesos negativos del reconocedor de teclas de Entropy Piano Tuner. Uno más agudo que el período solo vale si el sonido también se repite a su retardo, y la nota que ya suena lleva ventaja mientras se apaga, como en Tuneo. Bajo el margen, un filtro paso alto sin desfase quita la continua y el retumbo; con cuerdas, el margen va de una cuarta bajo la más grave a una quinta sobre la más aguda.

### La lectura estable

Es la media recortada, la mitad central, del último medio segundo de estimaciones. Solo cuenta lo que sobresale 10 dB del ruido del cuarto, aprendido mientras no suena nada (como en Strobie). Un ataque es el nivel 1,5 veces su envolvente: tras uno, una nota nueva se acepta en dos cuadros; sin él, debe durar 0,3 s seguidos, o 0,6 s si es armónico o subarmónico de la que suena o de una que acaba de callar. La nota o la cuerda elegida se mantiene hasta 10 cents pasada la mitad hacia la siguiente. La nota se apaga tras 0,4 s sin tono.

### El estroboscopio

Cada banda demodula el sonido en una parcial del objetivo, como el estroboscopio de Entropy Piano Tuner, con dos promedios en cascada; su fase mueve las franjas, una por segundo por cada cent, y se apagan si la parcial no sobresale del ruido, como en Strobie. Las parciales se buscan donde las pone la inarmonicidad medida. Se completan con la traza de la desviación, el espectro con sus picos nombrados (de Strobie), la escala fina de la aguja (la de Tuneo), las desviaciones por nota, la transposición, la cejilla y el tono de referencia, como el de pianito.

### Idiomas

Cada texto de la interfaz pasa por `tr()`, y la prueba de la interfaz comprueba que el archivo en español los tenga todos, y nada más. En español, las cifras llevan coma decimal en las tres interfaces.

### Empaquetado

El RPM se construye y se prueba con los paquetes de Fedora y se firma con la clave del autor. La AppImage lleva su propio Python y una PortAudio compilada para glibc 2.28 con el compilador de zig, porque sounddevice no la trae en Linux; `audio.py` le señala a sounddevice esa copia cuando está. Cada archivo publicado se firma, y cada firma se comprueba solo con la clave pública que se publica.

## Validación

Las 218 pruebas corren a la vez con `tools/test.py`, cada archivo en un proceso propio, en unos ocho segundos. Las del detector usan cuerdas sintéticas de frecuencia conocida, con armónicos, inarmonicidad, decaimiento y ruido: las cuerdas al aire de los cuatro instrumentos, desde el Si 0 del bajo de cinco cuerdas hasta el Mi 5 del violín, deben dar en cada cuadro menos de una décima de cent de error con ruido 40 dB por debajo; con ruido a 20 dB, la media de los errores debe quedarse junto a cero. También se prueban una fundamental débil o ausente, una cuerda muy inarmónica, un segundo armónico más fuerte que la fundamental, una cuerda de armónicos impares débiles (que el período solo lee una octava arriba), el silencio y el ruido puro, que no deben dar nota. Otras comprueban las esperas de una nota nueva con ataque y sin él, que las bandas del estroboscopio avancen una, dos y cuatro franjas por segundo por cada cent y se queden quietas en una cuerda rígida afinada, las desviaciones por nota, la cejilla, la transposición, el tono, el ruido aprendido (que no aprende una nota y deja pasar un tono 25 dB sobre el ruido pero no uno 5 dB sobre él), los picos del espectro y las escalas de la aguja.

Las demás comprueban los nombres y frecuencias de las notas y las afinaciones, la respuesta del estabilizador a valores sueltos y a notas nuevas, la configuración (incluido un archivo dañado), los WAV de 8 a 32 bits, las opciones de la línea de órdenes y el informe de una grabación completa. La interfaz de terminal se prueba corriendo de verdad en una pseudoterminal, donde la prueba pulsa teclas y lee la pantalla; la ventana se dibuja fuera de la pantalla. Otras comprueban que el archivo en español esté completo, que las versiones del programa, del spec y de los metadatos coincidan, que las páginas de manual estén al día, que la AppImage use su propia PortAudio, y la firma de una versión y su depósito en Zenodo, con una clave hecha para la prueba.

Además, la ventana y la terminal se revisaron a ojo mientras sonaba un WAV de seis cuerdas de guitarra desafinadas en cantidades conocidas (+3, -7,5, 0, +0,4, -1,2 y +12 cents), que el programa midió con errores de una centésima de cent, y la línea de órdenes se probó con el micrófono del computador. La AppImage se corrió en el mismo equipo, y halló los dispositivos de sonido con su propia PortAudio.

Con once grabaciones reales de cuerdas de guitarra (las de Tuneo, que no pueden distribuirse con el programa), `tools/evaluate.py` cuenta las notas falsas y, como Strobie, mide la exactitud con la misma grabación declarada a otra frecuencia de muestreo, que suena tantos cents desplazada como se quiera. Las notas falsas bajaron de 15 (9,1 s) a ninguna en modo guitarra y de 26 a 1 en modo cromático; el 95 % de las lecturas desplazadas coincide a 0,15 cents.

## Plataforma

El programa está escrito para Linux, donde se desarrolló y probó, en Fedora. Por sus bibliotecas debería funcionar también en Windows y macOS, salvo la interfaz de terminal, que necesita curses y no existe en el Python de Windows; esto no se ha probado.

Desde el código o el wheel, necesita Python 3.14 o posterior, numpy, sounddevice con la biblioteca PortAudio del sistema y, para la ventana, PySide6. El RPM es para Fedora 45 y posteriores, con los paquetes de Fedora; la AppImage, para cualquier Linux x86_64 con glibc 2.34 o posterior, y no necesita nada más. Usa cualquier entrada de sonido que PortAudio vea, a su frecuencia de muestreo (44,1 o 48 kHz, o la que se elija), y lee archivos WAV PCM de 8, 16, 24 y 32 bits. No necesita internet. El análisis gasta poco: un cuadro tarda unos 10 ms para las cuerdas más graves y 2 o 3 ms para las agudas, cuarenta veces por segundo.

## Ambiente

Fue desarrollado en Fedora 45, con Python 3.14 (en el entorno que uv arma para el proyecto), en noviembre de 2026. El código está en GitHub (github.com/nivaca/py-tuner) y en Codeberg (codeberg.org/nivaca/py-tuner). Cada versión se publica en las dos, con el RPM, la AppImage, el wheel y el código, todos firmados; el RPM está además en Copr (`sudo dnf copr enable nivaca/py-tuner` y `sudo dnf install py-tuner`), y cada versión se deposita en Zenodo.

Instalado, `py-tuner` abre la ventana. Para correrlo desde el código, en la carpeta del proyecto: `uv run py-tuner` abre la ventana, `uv run py-tuner tui` la interfaz de terminal y `uv run py-tuner cli` la línea de órdenes; `uv run py-tuner devices` lista las entradas de sonido y `uv run py-tuner instruments` las afinaciones. Las opciones comunes (`--a4`, `--instrument`, `--tuning`, `--string`, `--device`, `--file`...) valen para los tres modos y solo para esa sesión, salvo que se añada `--save`.

La configuración se guarda en `~/.config/py-tuner/settings.json` (o bajo `$XDG_CONFIG_HOME`). La ventana y la terminal guardan ahí cada cambio en el acto. En ese archivo se pueden añadir afinaciones propias en `custom_tunings`. Las preguntas y comentarios pueden enviarse al autor, Nicolas Vaughan, a nicolasvaughan@proton.me.
