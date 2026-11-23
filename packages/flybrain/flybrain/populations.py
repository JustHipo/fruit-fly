"""Agrupacion de neuronas en poblaciones legibles.

El decodificador no consume 161.429 neuronas sueltas sino unas decenas de
poblaciones. Agrupar por `superclass` da 22 grupos con significado anatomico.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from flybrain.data import Connectome

# Poblaciones utiles por defecto: la via de control de patas mas las grandes
# estructuras sensoriales y centrales. Deja afuera los grupos de menos de
# ~50 celulas, donde la tasa poblacional es demasiado ruidosa.
DEFAULT_SUPERCLASSES = (
    "descending_neuron",
    "vnc_motor",
    "vnc_intrinsic",
    "vnc_sensory",
    "ascending_neuron",
    "cb_intrinsic",
    "cb_sensory",
    "cb_motor",
    "ol_intrinsic",
    "ol_sensory",
    "visual_projection",
    "visual_centrifugal",
)


@dataclass(frozen=True)
class Populations:
    """Nombres y los indices de neurona que agrupa cada uno."""

    names: tuple[str, ...]
    indices: tuple[np.ndarray, ...]

    def __len__(self) -> int:
        return len(self.names)

    @property
    def sizes(self) -> tuple[int, ...]:
        return tuple(len(i) for i in self.indices)

    @classmethod
    def from_superclass(
        cls,
        conn: Connectome,
        superclasses: tuple[str, ...] = DEFAULT_SUPERCLASSES,
        min_size: int = 50,
    ) -> "Populations":
        names, indices = [], []
        for sc in superclasses:
            idx = conn.select(superclass=sc)
            if len(idx) < min_size:
                continue
            names.append(sc)
            indices.append(idx)
        if not names:
            raise ValueError("ninguna superclase supero min_size")
        return cls(tuple(names), tuple(indices))

    @classmethod
    def from_types(cls, conn: Connectome, types: list[str]) -> "Populations":
        """Poblaciones a partir de tipos celulares concretos, por ejemplo DNa01."""
        names, indices = [], []
        for t in types:
            idx = conn.select(type=t)
            if len(idx) == 0:
                raise KeyError(f"el tipo '{t}' no existe en el conectoma")
            names.append(t)
            indices.append(idx)
        return cls(tuple(names), tuple(indices))
