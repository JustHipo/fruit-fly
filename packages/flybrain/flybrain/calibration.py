"""Tasas de reposo por poblacion y conversion a z-scores.

Sin calibrar, el decodificador termina leyendo el nivel de actividad basal, que
es constante y no dice nada. Lo que interesa es la DESVIACION respecto del
reposo. Tecnica tomada de `infinite-sugar`.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import torch

from flybrain.lif import LifNetwork
from flybrain.populations import Populations


@dataclass(frozen=True)
class Baseline:
    """Media y desviacion de la tasa de cada poblacion en reposo."""

    names: tuple[str, ...]
    mean: np.ndarray   # (P,) Hz
    std: np.ndarray    # (P,) Hz

    def z(self, rates: np.ndarray) -> np.ndarray:
        return (rates - self.mean) / self.std


class PopulationReader:
    """Convierte spikes por paso en tasas poblacionales suavizadas."""

    def __init__(
        self,
        populations: Populations,
        device: torch.device,
        tau_ms: float = 25.0,
        dt: float = 1.0,
    ) -> None:
        self.populations = populations
        self.dt = dt
        self.alpha = dt / tau_ms
        # Matriz (P, N) dispersa en espiritu, pero como P es chico conviene densa:
        # un solo matmul por paso es mas rapido que P reducciones indexadas.
        n = max(int(i.max()) for i in populations.indices) + 1
        weights = torch.zeros(len(populations), n, device=device)
        for row, idx in enumerate(populations.indices):
            weights[row, torch.from_numpy(idx.astype(np.int64)).to(device)] = 1.0 / len(idx)
        self.weights = weights
        self.rate = torch.zeros(len(populations), device=device)

    def update(self, fired: torch.Tensor) -> torch.Tensor:
        """Tasa poblacional en Hz, suavizada con media movil exponencial."""
        instant = (self.weights @ fired.float()) * (1000.0 / self.dt)
        self.rate = self.rate + self.alpha * (instant - self.rate)
        return self.rate

    def reset(self, to: np.ndarray | None = None) -> None:
        """Reinicia el suavizado.

        Arrancar en cero produce un transitorio de ~3 tau que, en poblaciones de
        baja varianza, se traduce en z-scores absurdos (se midieron -25 en las
        sensoriales). Arrancar en el baseline lo elimina de raiz.
        """
        if to is None:
            self.rate = torch.zeros_like(self.rate)
        else:
            self.rate = torch.as_tensor(to, dtype=torch.float32, device=self.rate.device).clone()


def calibrate(
    net: LifNetwork,
    populations: Populations,
    seconds: float = 2.5,
    warmup: float = 0.5,
    seed: int = 0,
    n_kicks: int = 300,
) -> Baseline:
    """Mide las tasas de reposo, sin estimulo mas alla del ruido de fondo.

    `n_kicks` es la cantidad de empujones de ruido por paso (ver
    `LifNetwork.noise`). El default (300) esta calibrado para el conectoma
    COMPLETO (161k neuronas); una red mas chica (un subgrafo) recibe
    proporcionalmente mucho mas ruido por neurona con el mismo numero fijo, y
    eso por si solo infla la tasa de disparo sin que tenga nada que ver con
    `weight_scale`. Escalar `n_kicks` al tamano de la red evita ese sesgo
    (ver music-fly/docs/migraciones/F1-subgrafo-motor.md).
    """
    torch.manual_seed(seed)
    reader = PopulationReader(populations, net.device, dt=net.params.dt)
    state = net.initial_state()

    for _ in range(int(warmup * 1000 / net.params.dt)):
        state, fired = net.step(state, net.noise(n_kicks=n_kicks))
        reader.update(fired)

    samples = []
    for _ in range(int(seconds * 1000 / net.params.dt)):
        state, fired = net.step(state, net.noise(n_kicks=n_kicks))
        samples.append(reader.update(fired).cpu().numpy().copy())

    arr = np.stack(samples)
    mean = arr.mean(axis=0)
    # Piso relativo, no absoluto. Las poblaciones sensoriales no reciben entrada
    # sinaptica en esta configuracion (son la capa de entrada del modelo), asi
    # que su tasa la fija solo el ruido de fondo y su desviacion es minuscula.
    # Sin piso, dividir por ella convierte cualquier fluctuacion en un z enorme.
    std = np.maximum(arr.std(axis=0), np.maximum(0.02 * mean, 1e-6))
    return Baseline(names=populations.names, mean=mean, std=std)
