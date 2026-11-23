"""ConsoleDecoder: z (actividad real, 6 poblaciones) -> objetivos continuos
de alcance por pata. Sigue la firma de ARQUITECTURA.md 7.4, sin entrenar
(pesos aleatorios, semilla fija) - las mismas reglas del proyecto hermano:
continuo y monotono respecto de z, nada de hashes, el conectoma nunca se
toca.

Puro y sin estado: nunca decide "cuando" disparar una nota ni lleva ningun
contador de compas o de cooldown. Eso es responsabilidad de la capa de
interpretacion (music-fly/scripts/compose_from_trace.py), que es autoral
por diseno (ver ARQUITECTURA.md 7.5/7.6).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

N_LEGS = 6
LEG_NAMES = ("T1L", "T1R", "T2L", "T2R", "T3L", "T3R")


@dataclass(frozen=True)
class LegTarget:
    x: float     # -1..1
    y: float     # -1..1
    press: bool  # gate: intensidad de contacto por encima del umbral


class ConsoleDecoder:
    """z (n_pop,) -> un LegTarget por pata, en el orden de LEG_NAMES."""

    def __init__(self, n_pop: int, seed: int = 0, press_threshold: float = 0.05):
        rng = np.random.default_rng(seed)
        self.W = rng.normal(0, 0.5, size=(N_LEGS * 3, n_pop))
        self.b = np.zeros(N_LEGS * 3)
        self.press_threshold = press_threshold

    def __call__(self, z: np.ndarray) -> tuple[LegTarget, ...]:
        y = np.tanh(self.W @ z + self.b).reshape(N_LEGS, 3)
        return tuple(
            LegTarget(x=float(row[0]), y=float(row[1]), press=bool(row[2] > self.press_threshold))
            for row in y
        )
