"""Decodificador de pluma: z-scores poblacionales a parametros de trazo.

Reglas no negociables (CLAUDE.md, regla 4, y ARQUITECTURA.md 2.3):

  Continuo y monotono respecto de z. Si el cerebro hace algo parecido, el trazo
  tiene que ser parecido. Nada de hashes: `fruit-fly-fashion` metio sus spikes
  en un SHA-256 y destruyo toda la estructura neuronal por construccion.

  Rangos visuales amplios. El otro error de `fruit-fly-fashion` fue usar rangos
  tan angostos (rotacion de +-1,5 grados) que la salida era indistinguible de la
  imagen semilla.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

N_OUTPUTS = 6      # dx, dy, pen, width, hue, alpha


@dataclass(frozen=True)
class Stroke:
    dx: float
    dy: float
    pen_down: bool
    width: float
    alpha: float
    hsv: tuple[float, float, float]

    @property
    def hue(self) -> float:
        return self.hsv[0]

    def rgb(self) -> tuple[float, float, float]:
        import colorsys
        return colorsys.hsv_to_rgb(*self.hsv)

    def quantized(self, n_levels: int) -> "Stroke":
        """Version con matiz y saturacion en escalones, para el pixel art."""
        h, sat, val = self.hsv
        q = lambda v, n: round(v * (n - 1)) / (n - 1)
        return Stroke(self.dx, self.dy, self.pen_down, self.width, self.alpha,
                      (q(h, n_levels) % 1.0, q(sat, 4), q(val, 4)))


class PenDecoder:
    """z (n_pop,) -> parametros de trazo.

    Los pesos son el unico objeto entrenable del sistema. El conectoma nunca se
    toca. Con n_pop=12 son 6*12 + 6 = 78 parametros, comodo para CMA-ES.
    """

    def __init__(
        self,
        n_pop: int,
        seed: int = 0,
        max_step: float = 0.045,
        width_range: tuple[float, float] = (0.004, 0.020),
        alpha_range: tuple[float, float] = (0.25, 0.95),
        pen_threshold: float = 0.05,
    ) -> None:
        rng = np.random.default_rng(seed)
        self.W = rng.normal(0.0, 0.5, size=(N_OUTPUTS, n_pop))
        self.b = np.zeros(N_OUTPUTS)
        self.max_step = max_step
        self.width_range = width_range
        self.alpha_range = alpha_range
        self.pen_threshold = pen_threshold

    @property
    def n_params(self) -> int:
        return self.W.size + self.b.size

    def get_params(self) -> np.ndarray:
        return np.concatenate([self.W.ravel(), self.b])

    def set_params(self, theta: np.ndarray) -> "PenDecoder":
        if theta.size != self.n_params:
            raise ValueError(f"esperaba {self.n_params} parametros, llegaron {theta.size}")
        clone = PenDecoder.__new__(PenDecoder)
        clone.__dict__.update(self.__dict__)
        clone.W = theta[: self.W.size].reshape(self.W.shape).copy()
        clone.b = theta[self.W.size :].copy()
        return clone

    def __call__(self, z: np.ndarray, color_source) -> Stroke:
        """`color_source` recibe (z, hue_raw) y devuelve (h, s, v).

        El color no lo decide el decodificador sino la fuente de color, que
        puede leer el vector de actividad entero en vez de una sola salida. Ver
        `color.py`.
        """
        z = np.asarray(z, dtype=np.float64)
        y = np.tanh(self.W @ z + self.b)
        return Stroke(
            dx=float(y[0]) * self.max_step,
            dy=float(y[1]) * self.max_step,
            pen_down=bool(y[2] > self.pen_threshold),
            width=_remap(y[3], *self.width_range),
            alpha=_remap(y[5], *self.alpha_range),
            hsv=color_source(z, float(y[4])),
        )


def _remap(value: float, lo: float, hi: float) -> float:
    """-1..1 -> lo..hi"""
    return float(lo + (value + 1.0) * 0.5 * (hi - lo))
