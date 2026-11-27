"""La entrada de sonido: el micrófono (con sounddevice) o un archivo WAV.

Las dos fuentes escriben en un búfer circular, del que el afinador lee las
últimas muestras cuando quiere. Un archivo puede leerse entero de una vez
(para analizarlo sin esperar) o servirse al ritmo del reloj, como si sonara,
para probar la ventana o la terminal sin instrumento.
"""

from __future__ import annotations

import threading
import time
import wave
from pathlib import Path

import numpy as np


class RingBuffer:
    """Las últimas SIZE muestras monofónicas, que un hilo escribe y otro lee."""

    def __init__(self, size: int) -> None:
        self._data = np.zeros(size, dtype=np.float32)
        self._pos = 0
        self.total = 0  # muestras escritas desde el principio
        self._lock = threading.Lock()

    @property
    def size(self) -> int:
        return len(self._data)

    def write(self, block: np.ndarray) -> None:
        block = np.asarray(block, dtype=np.float32)
        with self._lock:
            n = len(block)
            if n >= self.size:
                self._data[:] = block[-self.size:]
                self._pos = 0
            else:
                end = self._pos + n
                if end <= self.size:
                    self._data[self._pos:end] = block
                else:
                    cut = self.size - self._pos
                    self._data[self._pos:] = block[:cut]
                    self._data[:n - cut] = block[cut:]
                self._pos = end % self.size
            self.total += n

    def latest(self, n: int) -> np.ndarray:
        """Las N muestras más recientes (menos al principio), de la más antigua a la más nueva."""
        with self._lock:
            n = min(n, self.size, self.total)
            start = (self._pos - n) % self.size
            if start + n <= self.size:
                return self._data[start:start + n].copy()
            return np.concatenate((self._data[start:], self._data[:self._pos]))


def to_mono(frames: np.ndarray, channel: str = "mix") -> np.ndarray:
    """FRAMES (samples × channels) as one channel: their mean, or channel N (from 1)."""
    if frames.ndim == 1:
        return frames
    if channel == "mix":
        return frames.mean(axis=1)
    index = min(int(channel), frames.shape[1]) - 1
    return frames[:, index]


def read_wav(path: str | Path, channel: str = "mix") -> tuple[int, np.ndarray]:
    """(sample rate, mono float samples in -1..1) of a PCM WAV file of 8, 16, 24 or 32 bits."""
    with wave.open(str(path), "rb") as w:
        rate, width, chans = w.getframerate(), w.getsampwidth(), w.getnchannels()
        raw = w.readframes(w.getnframes())
    if width == 1:
        data = (np.frombuffer(raw, dtype=np.uint8).astype(np.float64) - 128) / 128
    elif width == 2:
        data = np.frombuffer(raw, dtype="<i2") / 32768.0
    elif width == 3:
        # 24 bits: se arma cada muestra con sus tres bytes y el signo del último
        b = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3).astype(np.int32)
        v = b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)
        data = np.where(v >= 1 << 23, v - (1 << 24), v) / float(1 << 23)
    elif width == 4:
        data = np.frombuffer(raw, dtype="<i4") / 2147483648.0
    else:
        raise ValueError(f"unsupported WAV sample width: {width} bytes")
    return rate, to_mono(data.reshape(-1, chans), channel)


class Source:
    """De donde lee el afinador: una frecuencia de muestreo, un búfer circular, start() y stop()."""

    rate: int
    buffer: RingBuffer
    error: str | None = None

    def start(self) -> None: ...

    def stop(self) -> None: ...


class MicSource(Source):
    """La entrada de la tarjeta de sonido, con sounddevice (PortAudio)."""

    def __init__(self, seconds: float, device: str | None = None, rate: int | None = None,
                 channel: str = "mix") -> None:
        import sounddevice as sd

        self._sd = sd
        self.device = _device_index(sd, device)
        info = sd.query_devices(self.device, "input")
        self.rate = int(rate or info["default_samplerate"])
        self.channels = int(info["max_input_channels"]) if channel != "mix" else min(2, int(info["max_input_channels"]))
        self.channels = max(1, self.channels)
        self.channel = channel
        self.device_name = str(info["name"])
        self.buffer = RingBuffer(int(seconds * self.rate))
        self._stream = None

    def _callback(self, indata, frames, when, status) -> None:  # noqa: ARG002
        self.buffer.write(to_mono(indata, self.channel))

    def start(self) -> None:
        self._stream = self._sd.InputStream(device=self.device, samplerate=self.rate, channels=self.channels,
                                            dtype="float32", blocksize=0, latency="low",
                                            callback=self._callback)
        self._stream.start()

    def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None


class FileSource(Source):
    """A WAV file served at the pace of the clock, as if it were playing (and looped)."""

    def __init__(self, path: str | Path, seconds: float, channel: str = "mix", loop: bool = True) -> None:
        self.rate, self.samples = read_wav(path, channel)
        self.buffer = RingBuffer(int(seconds * self.rate))
        self.loop = loop
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _run(self) -> None:
        start = time.monotonic()
        sent = 0
        n = len(self.samples)
        while not self._stop.is_set():
            due = int((time.monotonic() - start) * self.rate)
            while sent < due:
                pos = sent % n if self.loop else sent
                if pos >= n:
                    return
                chunk = self.samples[pos:min(n, pos + due - sent)]
                self.buffer.write(chunk)
                sent += len(chunk)
            self._stop.wait(0.01)

    def start(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join()


def _device_index(sd, device: str | None) -> int | None:
    """El índice del dispositivo de entrada DEVICE (un número, o parte de su nombre)."""
    if device is None or device == "":
        return None
    if str(device).isdigit():
        return int(device)
    for i, info in enumerate(sd.query_devices()):
        if info["max_input_channels"] > 0 and str(device).lower() in info["name"].lower():
            return i
    raise ValueError(f"no input device matches {device!r}")


def input_devices() -> list[tuple[int, str, int]]:
    """(index, name, default sample rate) of every input device; [] without PortAudio."""
    try:
        import sounddevice as sd

        found = sd.query_devices()
    except (ImportError, OSError):
        return []
    return [(i, d["name"], int(d["default_samplerate"])) for i, d in enumerate(found)
            if d["max_input_channels"] > 0]
