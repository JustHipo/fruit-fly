"""Selección de qué pata está activa, y sus radios de alcance medidos.

La selección de pata es legítimamente DISCRETA, a diferencia del color o el
ancho de trazo: una mosca real mueve una pata a la vez para alcanzar un punto,
no mezcla continuamente "un poco de cada pata". Elegir con argmax acá no es el
mismo error que usar argmax para el color (F1, color.py): ahí el matiz es
continuo por naturaleza y argmax lo discretiza artificialmente; acá la cantidad
que se decodifica ya es discreta en la realidad.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from artfly.body import LEGS

# Radios de alcance conservadores, calibrados con `scripts/probe_reach.py`
# (ARQUITECTURA.md / F2-cuerpo-ik.md, actualizacion 2026-09-15c). Las patas
# delanteras alcanzan mucho mas que las medias y traseras (95% y 93% contra
# 53-64% de un area de 0,20x0,20), asi que comparten un solo radio seria
# forzar posturas en el limite articular para T2/T3, justo donde la IK es
# menos confiable.
REACH_RADIUS: dict[str, float] = {
    "T1_left": 0.08, "T1_right": 0.08,
    "T2_left": 0.05, "T2_right": 0.05,
    "T3_left": 0.06, "T3_right": 0.06,
}


@dataclass(frozen=True)
class LegChoice:
    leg: str
    scores: np.ndarray   # (6,) softmax, para diagnostico de que tan decidida fue la eleccion


class LegSelector:
    """z (n_pop,) -> cual de las seis patas esta activa este frame."""

    def __init__(self, n_pop: int, seed: int = 0) -> None:
        rng = np.random.default_rng(seed)
        self.W = rng.normal(0.0, 0.5, size=(len(LEGS), n_pop))
        self.b = np.zeros(len(LEGS))

    @property
    def n_params(self) -> int:
        return self.W.size + self.b.size

    def __call__(self, z: np.ndarray) -> LegChoice:
        logits = self.W @ np.asarray(z, dtype=np.float64) + self.b
        scores = np.exp(logits - logits.max())
        scores /= scores.sum()
        return LegChoice(leg=LEGS[int(np.argmax(scores))], scores=scores)
