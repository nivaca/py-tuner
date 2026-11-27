"""Los dibujos de la ventana: la aguja, el estroboscopio y el medidor de nivel.

Se pintan con QPainter y toman los colores de la paleta del sistema, así que
siguen el tema claro u oscuro del escritorio. El verde, el ámbar y el rojo
dicen lo mismo en todos: afinado, cerca, lejos.
"""

from __future__ import annotations

import math
import time

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPalette, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from .. import display

GREEN = QColor(46, 170, 90)
AMBER = QColor(222, 160, 30)
RED = QColor(214, 70, 60)


def deviation_color(cents: float, tolerance: float) -> QColor:
    """Green within the tolerance, amber within five times it, red beyond."""
    a = abs(cents)
    if a <= tolerance:
        return GREEN
    return AMBER if a <= 5 * tolerance else RED


class Needle(QWidget):
    """A ±50-cent arc with a needle; the tolerance zone is shaded green."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.cents: float | None = None
        self.shown = 0.0  # la posición dibujada, que sigue a la real con algo de inercia
        self.tolerance = 1.0
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(140)

    def sizeHint(self) -> QSize:
        return QSize(520, 260)

    def set_cents(self, cents: float | None, dt: float) -> None:
        self.cents = cents
        if cents is not None:
            target = max(-display.NEEDLE_RANGE, min(display.NEEDLE_RANGE, cents))
            # Seguimiento de primer orden, con constante de tiempo de 60 ms.
            k = 1 - math.exp(-dt / 0.06) if dt > 0 else 1.0
            self.shown += (target - self.shown) * k
        self.update()

    def paintEvent(self, event) -> None:  # noqa: ARG002
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pal = self.palette()
        fg = pal.color(QPalette.ColorRole.WindowText)
        dim = QColor(fg)
        dim.setAlphaF(0.45)
        w, h = self.width(), self.height()
        r = min(w / 2 - 24, h - 40)
        cx, cy = w / 2, h - 18
        span = 60.0  # grados a cada lado del centro para ±50 cents

        def point(cents: float, radius: float) -> QPointF:
            ang = math.radians(90 - cents / display.NEEDLE_RANGE * span)
            return QPointF(cx + radius * math.cos(ang), cy - radius * math.sin(ang))

        rect = QRectF(cx - r, cy - r, 2 * r, 2 * r)
        # la zona afinada
        tol = min(self.tolerance, display.NEEDLE_RANGE)
        zone = QColor(GREEN)
        zone.setAlphaF(0.25)
        p.setPen(QPen(zone, max(6.0, r * 0.08), Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
        a_tol = tol / display.NEEDLE_RANGE * span
        p.drawArc(rect.adjusted(r * 0.04, r * 0.04, -r * 0.04, -r * 0.04),
                  int((90 - a_tol) * 16), int(2 * a_tol * 16))
        # el arco y sus marcas
        p.setPen(QPen(dim, 1.5))
        p.drawArc(rect, int((90 - span) * 16), int(2 * span * 16))
        font = QFont(self.font())
        font.setPointSizeF(max(7.0, r / 22))
        p.setFont(font)
        for c in range(-50, 51, 5):
            major = c % 10 == 0
            p.setPen(QPen(fg if c == 0 else dim, 2.0 if major else 1.0))
            p.drawLine(point(c, r), point(c, r * (0.88 if major else 0.93)))
            if major:
                label = f"{c:+d}" if c else "0"
                pt = point(c, r * 0.78)
                p.drawText(QRectF(pt.x() - 20, pt.y() - 10, 40, 20), Qt.AlignmentFlag.AlignCenter, label)
        # la aguja
        if self.cents is not None:
            color = deviation_color(self.cents, self.tolerance)
            p.setPen(QPen(color, 3.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(QPointF(cx, cy), point(self.shown, r * 0.98))
            p.setBrush(color)
        else:
            p.setBrush(dim)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(cx, cy), 6, 6)


class Strobe(QWidget):
    """Three bands of stripes that drift right when sharp, left when flat, and stand still in tune."""

    STRIPES = 12

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.model = display.Strobe(period=1.0)
        self.follower = display.Follower()
        self.cents: float | None = None
        self.tolerance = 1.0
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(84)

    def advance(self, cents: float | None, dt: float, bands: tuple = ()) -> None:
        """Moves the stripes: by the real strobe's BANDS when there are any (strobe.py), or else at a speed
        proportional to CENTS (a reading without sound behind it, as in the manual's pictures)."""
        self.cents = cents
        self.follower.update(bands if cents is not None else (), time.monotonic())
        # Una franja (un período del dibujo) por segundo por cada cent, en la primera banda.
        self.model.advance(cents, dt)
        self.update()

    def phases(self) -> list[tuple[float, float]]:
        """[(phase, alpha)] of each band: the real strobe's, or the model's."""
        real = self.follower.phases(time.monotonic())
        return real if real else [(phase, 1.0) for phase in self.model.phases]

    def paintEvent(self, event) -> None:  # noqa: ARG002
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pal = self.palette()
        w, h = self.width(), self.height()
        base = pal.color(QPalette.ColorRole.Base)
        p.fillRect(self.rect(), base)
        if self.cents is None:
            color = QColor(pal.color(QPalette.ColorRole.WindowText))
            color.setAlphaF(0.12)
        else:
            color = deviation_color(self.cents, self.tolerance)
        phases = self.phases()
        bands = len(phases)
        gap = 4
        band_h = (h - gap * (bands + 1)) / bands
        stripe = w / self.STRIPES
        for i, (phase, alpha) in enumerate(phases):
            y = gap + i * (band_h + gap)
            # Las tres bandas tienen las mismas franjas; la de abajo corre cuatro
            # veces más rápido, para ver desviaciones de décimas de cent.
            width = stripe
            off = (phase * width) % width if self.cents is not None else 0.0
            path = QPainterPath()
            x = -width + off
            while x < w:
                path.addRect(QRectF(x, y, width / 2, band_h))
                x += width
            # una banda cuya parcial no sobresale del ruido se apaga (como en Strobie)
            shade = QColor(color)
            shade.setAlphaF(color.alphaF() * max(0.12, alpha))
            p.fillPath(path, shade)


class Level(QWidget):
    """A thin input-level bar, -90..0 dBFS, with the gate level marked."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.level = float("-inf")
        self.gate = -60.0
        self.setFixedHeight(10)
        self.setMinimumWidth(120)

    def set_level(self, level: float) -> None:
        self.level = level
        self.update()

    def paintEvent(self, event) -> None:  # noqa: ARG002
        p = QPainter(self)
        pal = self.palette()
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), pal.color(QPalette.ColorRole.Base))

        def x_of(db: float) -> float:
            return max(0.0, min(1.0, (db + 90) / 90)) * w

        color = GREEN if self.level >= self.gate else pal.color(QPalette.ColorRole.Mid)
        if self.level > -0.5:
            color = RED
        p.fillRect(QRectF(0, 0, x_of(self.level), h), color)
        p.setPen(QPen(pal.color(QPalette.ColorRole.WindowText), 1))
        gx = x_of(self.gate)
        p.drawLine(QPointF(gx, 0), QPointF(gx, h))


class Trace(QWidget):
    """The deviation over the last SECONDS, newest at the right, over the bands of the tolerance: a string
    settling or a peg turned the wrong way shows at a glance (as the trace of Strobie and the moving grid of
    Tuneo)."""

    SECONDS = 10.0

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.points: list[tuple[float, float | None]] = []  # (tiempo del reloj, cents o None)
        self.tolerance = 1.0
        self._last_time = None
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(90)

    def scale(self) -> float:
        """The cents at the top and bottom edges: ten times the tolerance, at least 20."""
        return max(20.0, 10 * self.tolerance)

    def add(self, cents: float | None, reading_time: float, now: float | None = None) -> None:
        """Adds a reading (CENTS None: no note), once per reading (its READING_TIME)."""
        if reading_time == self._last_time and cents is not None:
            return
        self._last_time = reading_time
        now = time.monotonic() if now is None else now
        self.points.append((now, cents))
        while self.points and self.points[0][0] < now - self.SECONDS:
            self.points.pop(0)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: ARG002
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pal = self.palette()
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), pal.color(QPalette.ColorRole.Base))
        top = self.scale()

        def y_of(c: float) -> float:
            return h / 2 - max(-1.0, min(1.0, c / top)) * (h / 2 - 3)

        zone = QColor(GREEN)
        zone.setAlphaF(0.2)
        p.fillRect(QRectF(0, y_of(self.tolerance), w, y_of(-self.tolerance) - y_of(self.tolerance)), zone)
        dim = QColor(pal.color(QPalette.ColorRole.WindowText))
        dim.setAlphaF(0.3)
        p.setPen(QPen(dim, 1))
        p.drawLine(QPointF(0, h / 2), QPointF(w, h / 2))
        now = time.monotonic()
        prev = None
        for t, c in self.points:
            x = w - (now - t) / self.SECONDS * w
            if c is None:
                prev = None
                continue
            pt = QPointF(x, y_of(c))
            if prev is not None:
                p.setPen(QPen(deviation_color(c, self.tolerance), 2.0))
                p.drawLine(prev, pt)
            prev = pt
