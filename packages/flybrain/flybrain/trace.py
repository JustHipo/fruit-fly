"""Formato de traza: la frontera entre el simulador y todo lo que lo consume.

Es lo unico que cruza entre el entorno "brain" (Python 3.12, torch) y el
entorno "body" (Python 3.10, flybody con numpy fijado en 1.26.4), que no pueden
convivir en un mismo interprete.

Se emiten z-scores poblacionales contra baseline, nunca conteos crudos de
spikes: lo que interesa es la desviacion respecto del reposo.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from flybrain.calibration import Baseline

TRACE_VERSION = 1


@dataclass
class Trace:
    dataset: str
    dt_ms: float
    populations: tuple[str, ...]
    baseline_mean: np.ndarray
    baseline_std: np.ndarray
    times: list[float] = field(default_factory=list)
    values: list[np.ndarray] = field(default_factory=list)

    @classmethod
    def start(cls, baseline: Baseline, dt_ms: float, dataset: str = "male-cns:v1.0") -> "Trace":
        return cls(
            dataset=dataset,
            dt_ms=dt_ms,
            populations=baseline.names,
            baseline_mean=baseline.mean,
            baseline_std=baseline.std,
        )

    def append(self, t_seconds: float, z: np.ndarray) -> None:
        if len(z) != len(self.populations):
            raise ValueError(f"esperaba {len(self.populations)} valores, llegaron {len(z)}")
        self.times.append(float(t_seconds))
        self.values.append(np.asarray(z, dtype=np.float32).copy())

    @property
    def array(self) -> np.ndarray:
        """(T, P) para consumo numerico directo, sin pasar por JSON."""
        return np.stack(self.values) if self.values else np.empty((0, len(self.populations)))

    def save(self, path: str | Path, decimals: int = 3) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": TRACE_VERSION,
            "dataset": self.dataset,
            "dt_ms": self.dt_ms,
            "populations": list(self.populations),
            "baseline": {
                "mean": np.round(self.baseline_mean, 4).tolist(),
                "std": np.round(self.baseline_std, 4).tolist(),
            },
            "frames": [
                {"t": round(t, 4), "z": np.round(v, decimals).tolist()}
                for t, v in zip(self.times, self.values)
            ],
        }
        path.write_text(json.dumps(payload))
        return path

    @classmethod
    def load(cls, path: str | Path) -> "Trace":
        data = json.loads(Path(path).read_text())
        if data.get("version") != TRACE_VERSION:
            raise ValueError(f"version de traza no soportada: {data.get('version')}")
        trace = cls(
            dataset=data["dataset"],
            dt_ms=data["dt_ms"],
            populations=tuple(data["populations"]),
            baseline_mean=np.array(data["baseline"]["mean"], dtype=np.float32),
            baseline_std=np.array(data["baseline"]["std"], dtype=np.float32),
        )
        for frame in data["frames"]:
            trace.append(frame["t"], np.array(frame["z"], dtype=np.float32))
        return trace
