"""py-tuner: un afinador preciso para guitarra, bajo, contrabajo y violín."""

import os

__version__ = "0.5.0"

# Las cuentas del análisis son productos de matrices pequeñas: los hilos que la biblioteca de álgebra de numpy
# (OpenBLAS, por FlexiBLAS en Fedora) abre en cada procesador no las aceleran, compiten entre sí y, con varios
# procesos a la vez (las pruebas en paralelo, el %check del RPM), las vuelven decenas de veces más lentas. Un
# hilo, salvo que el usuario haya dicho otra cosa; antes de que se importe numpy.
for _name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "FLEXIBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_name, "1")
