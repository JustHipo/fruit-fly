"""Lienzo y deposicion de pintura.

Cada toque deposita un kernel gaussiano, no un pixel. La pluma se mueve de forma
continua entre objetivos decodificados, asi que un trazo se interpola en
sub-pasos: si se depositara solo en los puntos decodificados, a 40 Hz quedarian
manchas sueltas en vez de trazos.
"""

from __future__ import annotations

import numpy as np

from artfly.pen import Stroke


class Canvas:
    """Lienzo RGB en coordenadas normalizadas 0..1."""

    def __init__(self, size: int = 900, background: float = 0.97) -> None:
        self.size = size
        self.rgb = np.full((size, size, 3), background, dtype=np.float32)
        self.ink = 0.0                       # pintura depositada, para diagnostico

    def dab(self, x: float, y: float, stroke: Stroke) -> None:
        """Deposita un toque gaussiano centrado en (x, y) normalizado."""
        radius_px = max(1.0, stroke.width * self.size)
        cx, cy = x * self.size, y * self.size
        reach = int(np.ceil(radius_px * 2.5))

        x0, x1 = int(max(0, cx - reach)), int(min(self.size, cx + reach + 1))
        y0, y1 = int(max(0, cy - reach)), int(min(self.size, cy + reach + 1))
        if x0 >= x1 or y0 >= y1:
            return

        yy, xx = np.mgrid[y0:y1, x0:x1]
        d2 = (xx - cx) ** 2 + (yy - cy) ** 2
        weight = np.exp(-d2 / (2.0 * radius_px ** 2)) * stroke.alpha

        color = np.array(stroke.rgb(), dtype=np.float32)
        patch = self.rgb[y0:y1, x0:x1]
        w = weight[..., None].astype(np.float32)
        self.rgb[y0:y1, x0:x1] = patch * (1.0 - w) + color * w
        self.ink += float(weight.sum())

    def to_uint8(self) -> np.ndarray:
        return (np.clip(self.rgb, 0.0, 1.0) * 255).astype(np.uint8)

    def save(self, path) -> None:
        from PIL import Image
        from pathlib import Path

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(self.to_uint8()).save(path)


class Pen:
    """Posicion de la pluma, integrada en el tiempo.

    Rebota en los bordes en vez de recortarse: recortar deja la pluma pegada al
    borde generando una linea recta artificial que no sale del cerebro.
    """

    def __init__(self, x: float = 0.5, y: float = 0.5) -> None:
        self.x, self.y = x, y

    def advance(self, dx: float, dy: float) -> tuple[float, float]:
        self.x = _bounce(self.x + dx)
        self.y = _bounce(self.y + dy)
        return self.x, self.y


def _bounce(v: float) -> float:
    if v < 0.0:
        return -v
    if v > 1.0:
        return 2.0 - v
    return v


def paint(canvas: Canvas, pen: Pen, strokes, substeps: int = 6) -> Canvas:
    """Recorre los trazos decodificados depositando pintura interpolada."""
    for stroke in strokes:
        step_x, step_y = stroke.dx / substeps, stroke.dy / substeps
        for _ in range(substeps):
            x, y = pen.advance(step_x, step_y)
            if stroke.pen_down:
                canvas.dab(x, y, stroke)
    return canvas
