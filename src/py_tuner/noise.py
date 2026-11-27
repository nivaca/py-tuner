"""El ruido de fondo del cuarto, aprendido mientras no suena nada, y la puerta que deja pasar solo lo que lo supera.

Como el nivel de fondo de Strobie (Davorin Šego): el piso sigue el nivel, en dB, mientras no suena nada más
fuerte; cuando algo sobresale, solo sube muy despacio, para alcanzar un cuarto que se volvió más ruidoso; y
mientras suena una nota no sube nunca (una nota sostenida, o un seno, se volverían el fondo), solo baja. Un
sonido cuenta si queda GATE_DB sobre ese piso. Hasta conocer el fondo (LEARN_S de silencio), la puerta no
cierra nada: una nota que suena desde el primer instante no pasa por fondo.
"""

from __future__ import annotations

import math

# Something this far over the floor is playing: the floor doesn't learn it (it only creeps toward it)
PLAY_DB = 6.0
# A sound must stand this far over the floor to be analysed
GATE_DB = 10.0
# Seconds of background the floor needs before it gates anything
LEARN_S = 0.5
# Con qué constante de tiempo sigue el piso al nivel (sin nada sonando) y con cuál se arrastra hacia un sonido
FOLLOW_S = 1.0
CREEP_S = 20.0
# A note counts this long after its last detection: its fading tail is not background
PITCH_HOLD_S = 0.5


class NoiseFloor:
    """The background level of the room, in dBFS, learned from the frames without a note."""

    def __init__(self) -> None:
        self.floor: float | None = None
        self._learned = 0.0
        self._last_pitch = -math.inf
        self._last_time: float | None = None

    def update(self, level: float, pitch: bool, now: float) -> None:
        """Takes the LEVEL (dBFS) of the frame at NOW, and whether it had a PITCH."""
        dt = 0.025 if self._last_time is None else min(0.2, max(0.0, now - self._last_time))
        self._last_time = now
        level = max(level, -140.0)
        if pitch:
            self._last_pitch = now
        if pitch or now - self._last_pitch < PITCH_HOLD_S:
            # Mientras suena (o se apaga) una nota, el piso solo baja: lo que se oye no es fondo.
            if self.floor is not None and level < self.floor:
                self.floor = level
            return
        if self.floor is None:
            self.floor = level
            self._learned = dt
            return
        tau = CREEP_S if level - self.floor > PLAY_DB else FOLLOW_S
        self.floor += (level - self.floor) * (1 - math.exp(-dt / tau))
        self._learned += dt

    def gate(self) -> float | None:
        """The level a sound must reach (dBFS), or None while the floor is not known yet."""
        if self.floor is None or self._learned < LEARN_S:
            return None
        return self.floor + GATE_DB

    def reset(self) -> None:
        self.__init__()
