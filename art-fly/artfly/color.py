"""De donde sale el color.

Dos fuentes, ambas disponibles, para poder comparar.

`BandPalette` es la original y es **autoral**: el cerebro elige una posicion
dentro de una banda de matiz que elegimos nosotros, con saturacion y brillo
fijos. Se conserva porque sirve de control: permite ver cuanto cambia una pieza
cuando el color pasa a salir del cerebro.

`PopulationColor` es la honesta: matiz, saturacion y brillo salen los tres de la
actividad, y ademas el resultado es **interpretable**. Cada poblacion ocupa una
ranura del circulo cromatico, y el color de un trazo es la media circular de
esas ranuras pesada por la actividad de cada poblacion. Mirando una pieza se
puede leer que parte del cerebro la estaba manejando.

Notar que la media circular es continua: cuando una poblacion sube de a poco, el
matiz se desplaza de a poco hacia su ranura. Un `argmax` habria sido mas simple
pero discontinuo, y saltar de color ante un cambio minimo de actividad viola la
regla 4 de CLAUDE.md igual que un hash.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

HSV = tuple[float, float, float]


@dataclass(frozen=True)
class BandPalette:
    """Autoral: banda de matiz elegida a mano, saturacion y brillo fijos."""

    hue_center: float = 0.58
    hue_spread: float = 0.18
    saturation: float = 0.72
    value: float = 0.95

    def __call__(self, z: np.ndarray, hue_raw: float) -> HSV:
        return ((self.hue_center + hue_raw * self.hue_spread) % 1.0,
                self.saturation, self.value)


class PopulationColor:
    """Derivado del cerebro: cada poblacion ocupa una ranura del circulo.

    - **matiz**: media circular de las ranuras, pesada por actividad.
    - **saturacion**: longitud del vector resultante de esa media circular, que
      es exactamente la concentracion de la distribucion. Una poblacion domina
      -> color saturado. Actividad repartida -> color lavado, casi gris.
    - **brillo**: magnitud global de la actividad.

    La saturacion sale gratis de la estadistica circular: no hay que inventar
    una medida de concentracion, el largo del resultante ya lo es.
    """

    def __init__(
        self,
        n_pop: int,
        temperature: float = 2.0,
        hue_offset: float = 0.0,
        saturation_range: tuple[float, float] = (0.25, 1.0),
        value_range: tuple[float, float] = (0.55, 1.0),
        value_scale: float = 2.5,
    ) -> None:
        if n_pop < 2:
            raise ValueError("hacen falta al menos dos poblaciones")
        slots = np.linspace(0.0, 1.0, n_pop, endpoint=False) + hue_offset
        self.angles = 2.0 * np.pi * (slots % 1.0)
        self.cos, self.sin = np.cos(self.angles), np.sin(self.angles)
        self.temperature = temperature
        self.saturation_range = saturation_range
        self.value_range = value_range
        self.value_scale = value_scale

    def weights(self, z: np.ndarray) -> np.ndarray:
        scaled = np.asarray(z, dtype=np.float64) * self.temperature
        scaled = scaled - scaled.max()
        w = np.exp(scaled)
        return w / w.sum()

    def __call__(self, z: np.ndarray, hue_raw: float = 0.0) -> HSV:
        w = self.weights(z)
        x = float((w * self.cos).sum())
        y = float((w * self.sin).sum())

        hue = (np.arctan2(y, x) / (2.0 * np.pi)) % 1.0
        concentration = float(np.hypot(x, y))          # 0..1
        activity = float(np.linalg.norm(z) / np.sqrt(len(z)))

        return (
            hue,
            _remap(concentration, *self.saturation_range),
            _remap(min(activity / self.value_scale, 1.0), *self.value_range),
        )


def _remap(unit: float, lo: float, hi: float) -> float:
    return float(lo + np.clip(unit, 0.0, 1.0) * (hi - lo))


SOURCES = {"poblacion": PopulationColor, "banda": BandPalette}
