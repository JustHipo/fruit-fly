"""Test de cerebro congelado (ARQUITECTURA.md 11.1, obligatorio antes de dar
por buena cualquier pieza entrenada o decodificada). Corre la MISMA logica
de composicion (console/compose.py) sobre tres versiones de la traza real:

  1. real:      la traza tal cual se grabo en F1.
  2. congelada: z fijo en su media, todo el tiempo (el cerebro "no hace nada").
  3. ruido:     z reemplazado por ruido de igual media y varianza por
                poblacion, sin ninguna estructura temporal real.

Si la composicion congelada o la de ruido son indistinguibles de la real,
el decodificador esta ignorando al cerebro (el mismo fallo que encontro
fly-craftax en su readout entrenado, ver LECCIONES_APRENDIDAS.md).

Uso:
    source .venv-brain/bin/activate
    python music-fly/scripts/test_frozen_brain.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "music-fly"))

from console.compose import compose  # noqa: E402
from console.vocabulary import INSTRUMENTS  # noqa: E402
from flybrain.trace import Trace  # noqa: E402

TRACE_PATH = REPO / "out/music-fly/f1/live_trace.json"


def summarize(label: str, times, z_values, seed: int = 0) -> None:
    result = compose(times, z_values, seed=seed)
    notes = result.notes
    if notes:
        pitches = [n.pitch for n in notes]
        velocities = [n.velocity for n in notes]
        durations = [n.end_s - n.start_s for n in notes]
        by_instrument = {}
        for n in notes:
            label_i = INSTRUMENTS[n.track].label
            by_instrument[label_i] = by_instrument.get(label_i, 0) + 1
    else:
        pitches = velocities = durations = [0]
        by_instrument = {}

    print(f"\n{label}")
    print(f"  compas={result.meter_name}  tempo={result.tempo_bpm:.1f}bpm")
    print(f"  notas={len(notes)}  por_instrumento={by_instrument}")
    print(f"  pitch: media={np.mean(pitches):.1f} std={np.std(pitches):.2f}")
    print(f"  velocity: media={np.mean(velocities):.1f} std={np.std(velocities):.2f}")
    print(f"  duracion: media={np.mean(durations)*1000:.0f}ms std={np.std(durations)*1000:.0f}ms")
    if notes:
        times_notes = [n.start_s for n in notes]
        gaps = np.diff(sorted(times_notes))
        print(f"  gaps entre notas: media={np.mean(gaps)*1000:.0f}ms std={np.std(gaps)*1000:.0f}ms")


def main() -> None:
    print(f"Cargando traza real de {TRACE_PATH.name}...")
    trace = Trace.load(TRACE_PATH)
    z_real = np.stack(trace.values)  # (T, P)
    times = trace.times
    print(f"  {len(times)} cuadros, {z_real.shape[1]} poblaciones")

    rng = np.random.default_rng(0)

    # Congelada: cada poblacion fija en su propia media a lo largo de toda la traza.
    mean_per_pop = z_real.mean(axis=0)
    z_frozen = [mean_per_pop.copy() for _ in range(len(times))]

    # Ruido: por cuadro, ruido gaussiano con la misma media y varianza POR
    # POBLACION que la traza real (ARQUITECTURA.md 11.1: "de igual media y varianza").
    # Destruye DOS cosas a la vez: el orden temporal Y la relacion entre
    # poblaciones (cada una se genera independiente). Los dos controles de
    # abajo separan cual de las dos importa.
    std_per_pop = z_real.std(axis=0)
    z_noise = [rng.normal(mean_per_pop, std_per_pop) for _ in range(len(times))]

    # Barajado en el tiempo: los mismos valores reales, en otro orden. La
    # relacion entre poblaciones en cada instante queda intacta (son los
    # mismos vectores reales); lo unico que se destruye es la secuencia.
    order = rng.permutation(len(times))
    z_shuffled = [z_real[i].copy() for i in order]

    # Ruido con covarianza real: en vez de generar cada poblacion por
    # separado, se usa la matriz de covarianza real entre poblaciones. Se
    # mueven juntas de forma realista, pero sin la secuencia temporal real
    # (cada cuadro es un sorteo independiente de la misma distribucion).
    cov = np.cov(z_real, rowvar=False)
    z_noise_cov = list(rng.multivariate_normal(mean_per_pop, cov, size=len(times)))

    summarize("=== REAL (cerebro real, F1) ===", times, list(z_real))
    summarize("=== CONGELADA (z fijo en la media) ===", times, z_frozen)
    summarize("=== RUIDO (misma media/varianza, poblaciones independientes) ===", times, z_noise)
    summarize("=== BARAJADO (mismos valores reales, otro orden) ===", times, z_shuffled)
    summarize("=== RUIDO CON COVARIANZA REAL (poblaciones correlacionadas, sin secuencia) ===",
              times, z_noise_cov)

    print(
        "\nLectura: si 'congelada' o 'ruido' dan un numero de notas, distribucion "
        "de pitch/velocity/duracion y espaciado entre notas parecidos a 'real', "
        "el decodificador esta ignorando al cerebro. Si 'real' se distingue "
        "claramente de las otras dos, el cerebro esta aportando algo genuino."
    )


if __name__ == "__main__":
    main()
