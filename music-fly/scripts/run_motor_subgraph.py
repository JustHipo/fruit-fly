"""Entregable de la Fase 1: el subgrafo motor corriendo en vivo, con reloj
real, emitiendo z-scores poblacionales sin dejar de sonar aunque el sistema
se atrase.

Carga lo que guardo select_motor_subgraph.py, calibra, y despues corre
anclado a time.perf_counter(): si un paso de 1ms simulado se atrasa
respecto del reloj real, se SALTEA en vez de acumular deuda (ARQUITECTURA.md
3.3/5), asi la traza nunca se atrasa mas y mas del presente real.

Uso:
    source .venv-brain/bin/activate
    python music-fly/scripts/run_motor_subgraph.py --seconds 15
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp
import torch

from flybrain.calibration import PopulationReader, calibrate
from flybrain.data import Connectome
from flybrain.lif import LifNetwork, LifParams
from flybrain.populations import Populations
from flybrain.trace import Trace

REPO = Path(__file__).resolve().parents[2]
SUBGRAPH_DIR = REPO / "out/music-fly/f1"
TRACE_OUT = REPO / "out/music-fly/f1/live_trace.json"

EMIT_EVERY_MS = 25.0  # mismo ritmo que el EMA (tau=25ms) y que pide 3.4: ~40Hz
MAX_CATCHUP_STEPS = 50  # si nos atrasamos mas de 50ms, se saltea, no se acumula deuda

# Calibrado especificamente para este subgrafo (4491 neuronas), no reusa el
# weight_scale=65 del cerebro completo (161429 neuronas). Ver
# music-fly/docs/migraciones/F1-subgrafo-motor.md: con el ruido de fondo sin
# escalar (n_kicks=300, pensado para el grafo completo) la tasa salia 15-20x
# mas alta sin importar weight_scale, porque el subgrafo recibia
# proporcionalmente mucho mas ruido por neurona. Escalando n_kicks al tamano
# real de la red y barriendo weight_scale de nuevo: weight_scale=100 da 4.2Hz
# de tasa media y 0.195 de correlacion contra el nulo, casi identico a la
# firma del cerebro completo (3.3Hz, 0.21) calibrada en packages/flybrain.
FULL_BRAIN_N = 161_429
FULL_BRAIN_KICKS = 300
SUBGRAPH_WEIGHT_SCALE = 100.0


def load_subgraph() -> Connectome:
    mat = sp.load_npz(SUBGRAPH_DIR / "motor_subgraph.npz").tocoo()
    meta = pd.read_csv(SUBGRAPH_DIR / "motor_subgraph_meta.csv", low_memory=False)
    body_ids = np.load(SUBGRAPH_DIR / "motor_subgraph_body_ids.npy")
    return Connectome(
        src=mat.row.astype(np.int32),
        dst=mat.col.astype(np.int32),
        weight=mat.data.astype(np.float32),
        body_ids=body_ids,
        meta=meta,
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=15.0)
    ap.add_argument("--device", default="cpu")  # CPU gana en este tamaño, ver LECCIONES_APRENDIDAS
    args = ap.parse_args()

    print("Cargando subgrafo motor guardado...")
    conn = load_subgraph()
    print(f"  {conn.n_neurons} neuronas, {conn.n_edges} aristas")

    n_kicks = max(1, round(FULL_BRAIN_KICKS * conn.n_neurons / FULL_BRAIN_N))
    print(f"  ruido de fondo escalado al tamano de la red: n_kicks={n_kicks} "
          f"(vs {FULL_BRAIN_KICKS} del cerebro completo)")

    net = LifNetwork(conn, params=LifParams(weight_scale=SUBGRAPH_WEIGHT_SCALE), device=args.device)
    print(f"  {net.n_dropped} aristas de signo indefinido descartadas (esperado, ver flybrain.data)")

    populations = Populations.from_superclass(conn, min_size=50)
    print(f"\nPoblaciones ({len(populations)}): {dict(zip(populations.names, populations.sizes))}")

    print("\nCalibrando (2.5s de reposo, sin estimulo mas alla del ruido de fondo)...")
    t_cal = time.perf_counter()
    baseline = calibrate(net, populations, seconds=2.5, n_kicks=n_kicks)
    print(f"  listo en {time.perf_counter() - t_cal:.1f}s de reloj real")
    print(f"  tasas de reposo (Hz): {dict(zip(baseline.names, np.round(baseline.mean, 2)))}")

    reader = PopulationReader(populations, net.device, dt=net.params.dt)
    reader.reset(to=baseline.mean)  # arranca en el baseline, no en cero (ver flybrain.calibration)

    trace = Trace.start(baseline, dt_ms=EMIT_EVERY_MS, dataset="male-cns:v1.0:motor-subgraph")
    state = net.initial_state()

    print(f"\nCorriendo en vivo, {args.seconds}s, anclado al reloj real...")
    t0 = time.perf_counter()
    sim_step = 0
    last_emit = 0.0
    dropped_steps = 0
    n_emits = 0

    # asentamiento de 200ms antes de grabar (ver flybrain.calibration.reset y
    # LECCIONES_APRENDIDAS: el EMA recien reseteado igual tarda en asentarse)
    settle_steps = int(200 / net.params.dt)
    for _ in range(settle_steps):
        state, fired = net.step(state, net.noise(n_kicks=n_kicks))
        reader.update(fired)

    t0 = time.perf_counter()
    while True:
        now = time.perf_counter() - t0
        if now >= args.seconds:
            break

        target_step = int(now * 1000.0 / net.params.dt)
        pending = target_step - sim_step

        if pending <= 0:
            time.sleep(0.0005)
            continue

        if pending > MAX_CATCHUP_STEPS:
            dropped_steps += pending - MAX_CATCHUP_STEPS
            sim_step = target_step - MAX_CATCHUP_STEPS
            pending = MAX_CATCHUP_STEPS

        z = None
        for _ in range(pending):
            state, fired = net.step(state, net.noise(n_kicks=n_kicks))
            rate = reader.update(fired)
            sim_step += 1

        now_ms = sim_step * net.params.dt
        if now_ms - last_emit >= EMIT_EVERY_MS:
            z = baseline.z(rate.cpu().numpy())
            trace.append(now_ms / 1000.0, z)
            last_emit = now_ms
            n_emits += 1

    wall_elapsed = time.perf_counter() - t0
    print(f"\nTerminado. {wall_elapsed:.2f}s de reloj real, {sim_step} pasos simulados "
          f"({sim_step * net.params.dt / 1000.0:.2f}s de tiempo simulado).")
    print(f"Ritmo real logrado: {sim_step / wall_elapsed:.1f} pasos/s "
          f"(tiempo real = 1000 pasos/s con dt={net.params.dt}ms)")
    print(f"Pasos salteados por atraso: {dropped_steps}")
    print(f"Muestras de z emitidas: {n_emits} (~{n_emits / wall_elapsed:.1f} Hz)")

    trace.save(TRACE_OUT)
    print(f"\nTraza guardada en {TRACE_OUT}")


if __name__ == "__main__":
    main()
