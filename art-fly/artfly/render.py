"""Selector de modo de render.

Los dos modos consumen exactamente los mismos trazos decodificados. Lo unico que
cambia es como se depositan. La eleccion es autoral y se declara como tal
(ARQUITECTURA.md 10.3).
"""

from __future__ import annotations

from typing import Literal

from artfly.canvas import Canvas, Pen, paint
from artfly.pixel import PixelCanvas, paint_pixels

RenderMode = Literal["continuo", "pixel"]
MODES: tuple[str, ...] = ("continuo", "pixel")


def render(strokes, mode: RenderMode = "continuo", size: int = 900,
           cells: int = 64, substeps: int = 6, hue_levels: int = 12):
    """Devuelve el lienzo pintado. Ambos tipos exponen .save() y .to_uint8()."""
    if mode == "continuo":
        return paint(Canvas(size), Pen(), strokes, substeps=substeps)
    if mode == "pixel":
        scale = max(1, size // cells)
        return paint_pixels(PixelCanvas(cells=cells, scale=scale, hue_levels=hue_levels),
                            Pen(), strokes, substeps=substeps)
    raise ValueError(f"modo desconocido: {mode!r}, esperaba uno de {MODES}")
