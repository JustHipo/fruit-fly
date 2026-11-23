"""Complementa test_frozen_brain.py: las estadisticas resumen (cantidad de
notas, promedios) no pueden distinguir una secuencia real de la misma
secuencia barajada en el tiempo, porque un promedio es invariante al orden
por definicion. Esta prueba mide algo que SI depende del orden: la
autocorrelacion de un paso al siguiente del valor CONTINUO decodificado
(antes del gate/cooldown), que es donde vive la suavidad temporal real del
EMA del simulador (tau=25ms).

Si el cerebro real tiene continuidad temporal real, la autocorrelacion a un
paso deberia ser claramente positiva. Si el ruido/barajado no la tienen (por
construccion no deberian), la diferencia aparece aca aunque los promedios
sean iguales.

Uso:
    source .venv-brain/bin/activate
    python music-fly/scripts/test_autocorrelation.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "music-fly"))

from console.decoder import ConsoleDecoder  # noqa: E402
from flybrain.trace import Trace  # noqa: E402

TRACE_PATH = REPO / "out/music-fly/f1/live_trace.json"


def lag1_autocorr(series: np.ndarray) -> float:
    a, b = series[:-1], series[1:]
    if a.std() == 0 or b.std() == 0:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def decode_series(decoder: ConsoleDecoder, z_values) -> dict[str, np.ndarray]:
    decoded = [decoder(z) for z in z_values]
    # T1L.x y T1L.y: el gesto que decide velocidad y pitch de la nota, sin
    # pasar por el gate/cooldown - la señal continua cruda.
    return {
        "T1L.x": np.array([legs[0].x for legs in decoded]),
        "T1L.y": np.array([legs[0].y for legs in decoded]),
    }


def main() -> None:
    print(f"Cargando traza real de {TRACE_PATH.name}...")
    trace = Trace.load(TRACE_PATH)
    z_real = np.stack(trace.values)
    n = len(trace.times)
    print(f"  {n} cuadros, {z_real.shape[1]} poblaciones\n")

    rng = np.random.default_rng(0)
    mean_per_pop = z_real.mean(axis=0)
    std_per_pop = z_real.std(axis=0)
    cov = np.cov(z_real, rowvar=False)

    variants = {
        "REAL": list(z_real),
        "RUIDO (poblaciones independientes)": [rng.normal(mean_per_pop, std_per_pop) for _ in range(n)],
        "BARAJADO (mismos valores, otro orden)": [z_real[i].copy() for i in rng.permutation(n)],
        "RUIDO CON COVARIANZA REAL": list(rng.multivariate_normal(mean_per_pop, cov, size=n)),
    }

    decoder = ConsoleDecoder(n_pop=z_real.shape[1], seed=0)

    print(f"{'variante':<38} {'autocorr T1L.x':>15} {'autocorr T1L.y':>15}")
    print("-" * 70)
    for name, z_values in variants.items():
        series = decode_series(decoder, z_values)
        ac_x = lag1_autocorr(series["T1L.x"])
        ac_y = lag1_autocorr(series["T1L.y"])
        print(f"{name:<38} {ac_x:>15.3f} {ac_y:>15.3f}")

    print(
        "\nLectura: autocorrelacion cerca de 0 = cada paso es independiente del "
        "anterior (ruido). Claramente positiva = hay continuidad temporal real "
        "que el ruido/barajado no puede tener por construccion, sin importar "
        "que tan parecidos salgan los promedios."
    )


if __name__ == "__main__":
    main()
