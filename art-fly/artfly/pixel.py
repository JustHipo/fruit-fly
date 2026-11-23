"""Render en pixel art: la misma traza, estetica discreta.

Diferencias de fondo con el lienzo continuo de `canvas.py`:

  La pluma se cuantiza a una grilla de celdas. No hay antialiasing ni caida
  gaussiana: una celda esta pintada o no lo esta.

  El color se cuantiza a una paleta de N entradas. El cerebro elige indice de
  paleta, no matiz continuo.

  El ancho decodificado se vuelve tamano de brocha en celdas (1x1, 2x2, 3x3),
  que es el equivalente discreto del ancho de trazo.
"""

from __future__ import annotations

import colorsys

import numpy as np

from artfly.pen import Stroke


def ramp(hue_center: float = 0.58, spread: float = 0.18, n: int = 8,
         saturation: float = 0.72, value: float = 0.95) -> np.ndarray:
    """Paleta discreta de n colores dentro de una banda de matiz."""
    hues = (hue_center + np.linspace(-spread, spread, n)) % 1.0
    return np.array([colorsys.hsv_to_rgb(h, saturation, value) for h in hues],
                    dtype=np.float32)


class PixelCanvas:
    """Lienzo de celdas discretas en coordenadas normalizadas 0..1."""

    def __init__(self, cells: int = 64, scale: int = 14, hue_levels: int = 12,
                 background: float = 0.94) -> None:
        self.cells = cells
        self.scale = scale
        self.hue_levels = hue_levels
        self.grid = np.full((cells, cells, 3), background, dtype=np.float32)
        self.painted = np.zeros((cells, cells), dtype=bool)

    def dab(self, x: float, y: float, stroke: Stroke) -> None:
        """Pinta un bloque de celdas. Sin mezcla: la celda queda del color nuevo."""
        cx = int(np.clip(x * self.cells, 0, self.cells - 1))
        cy = int(np.clip(y * self.cells, 0, self.cells - 1))

        # ancho continuo -> brocha de 1, 2 o 3 celdas de lado
        brush = int(np.clip(round(stroke.width * self.cells * 1.4), 1, 3))
        color = np.array(stroke.quantized(self.hue_levels).rgb(), dtype=np.float32)

        half = brush // 2
        y0, y1 = max(0, cy - half), min(self.cells, cy - half + brush)
        x0, x1 = max(0, cx - half), min(self.cells, cx - half + brush)
        if x0 >= x1 or y0 >= y1:
            return
        self.grid[y0:y1, x0:x1] = color
        self.painted[y0:y1, x0:x1] = True

    @property
    def coverage(self) -> float:
        return float(self.painted.mean())

    def to_uint8(self) -> np.ndarray:
        """Escala por repeticion de pixel, sin interpolar: bordes duros."""
        img = np.clip(self.grid, 0.0, 1.0)
        img = np.repeat(np.repeat(img, self.scale, axis=0), self.scale, axis=1)
        return (img * 255).astype(np.uint8)

    def save(self, path) -> None:
        from pathlib import Path

        from PIL import Image

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(self.to_uint8()).save(path)


def paint_pixels(canvas: PixelCanvas, pen, strokes, substeps: int = 6) -> PixelCanvas:
    for stroke in strokes:
        sx, sy = stroke.dx / substeps, stroke.dy / substeps
        for _ in range(substeps):
            x, y = pen.advance(sx, sy)
            if stroke.pen_down:
                canvas.dab(x, y, stroke)
    return canvas
