"""La mosca que pinta.

El nucleo (pluma, color, lienzo, render) no importa nada pesado y funciona en
los dos entornos. `artfly.body` requiere flybody y dm_control, asi que se
importa explicitamente y solo desde el entorno "body".
"""

from artfly.canvas import Canvas, Pen, paint
from artfly.color import SOURCES, BandPalette, PopulationColor
from artfly.pen import PenDecoder, Stroke
from artfly.pixel import PixelCanvas, paint_pixels
from artfly.render import MODES, render

__all__ = [
    "Canvas", "Pen", "paint",
    "SOURCES", "BandPalette", "PopulationColor",
    "PenDecoder", "Stroke",
    "PixelCanvas", "paint_pixels",
    "MODES", "render",
]
