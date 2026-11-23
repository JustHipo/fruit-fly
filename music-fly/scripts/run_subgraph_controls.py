"""Igual que packages/flybrain/scripts/run_controls.py, pero sobre el
subgrafo motor guardado, con los parametros ya calibrados especificamente
para su tamano (weight_scale=100, n_kicks proporcional).

Es el control de honestidad de F1: si el subgrafo real no se distingue de
sus versiones degradadas, el cableado medido no esta aportando nada, y hay
que decirlo antes de construir la consola (F2) encima.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp
import torch

from flybrain.calibration import PopulationReader, calibrate
from flybrain.controls import CONTROLS
from flybrain.data import Connectome
from flybrain.lif import LifNetwork, LifParams
from flybrain.populations import Populations

REPO = Path(__file__).resolve().parents[2]
SUBGRAPH_DIR = REPO / "out/music-fly/f1"

FULL_BRAIN_N = 161_429
FULL_BRAIN_KICKS = 300
WEIGHT_SCALE = 100.0  # calibrado en F1, ver docs/migraciones/F1-subgrafo-motor.md


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


def run(conn, pops, n_kicks, device, seconds, seed):
    net = LifNetwork(conn, LifParams(weight_scale=WEIGHT_SCALE), device=device)
    baseline = calibrate(net, pops, seconds=1.5, seed=seed, n_kicks=n_kicks)

    torch.manual_seed(seed)
    reader = PopulationReader(pops, net.device, dt=net.params.dt)
    reader.reset(to=baseline.mean)
    state = net.initial_state()
    for _ in range(200):
        state, fired = net.step(state, net.noise(n_kicks=n_kicks))
        reader.update(fired)

    frames = []
    for i in range(int(seconds * 1000)):
        state, fired = net.step(state, net.noise(n_kicks=n_kicks))
        rate = reader.update(fired)
        if i % 25 == 0:
            frames.append(baseline.z(rate.cpu().numpy()).copy())
    return baseline.mean, np.stack(frames)


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=3.0)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    real = load_subgraph()
    n_kicks = max(1, round(FULL_BRAIN_KICKS * real.n_neurons / FULL_BRAIN_N))
    pops = Populations.from_superclass(real, min_size=50)

    print(f"subgrafo: {real.n_neurons} neuronas, {real.n_edges} aristas, n_kicks={n_kicks}")

    print("corriendo real...")
    base_rates, base_z = run(real, pops, n_kicks, args.device, args.seconds, args.seed)

    results = {}
    for name, fn in CONTROLS.items():
        print(f"corriendo {name}...")
        results[name] = run(
            fn(real, seed=args.seed + 1), pops, n_kicks, args.device, args.seconds, args.seed
        )

    print(f"\n{'control':<20} {'corr tasas':>11} {'dif tasa media':>15} {'corr dinamica':>14}")
    print("-" * 64)
    for name, (rates, z) in results.items():
        corr_r = float(np.corrcoef(base_rates, rates)[0, 1])
        d_mean = float(np.abs(base_rates.mean() - rates.mean()))
        corr_z = float(np.corrcoef(base_z.ravel(), z.ravel())[0, 1])
        print(f"{name:<20} {corr_r:>11.3f} {d_mean:>15.2f} {corr_z:>14.3f}")

    print(f"\n{'poblacion':<20} {'real':>8}" + "".join(f"{n[:9]:>11}" for n in results))
    print("-" * (28 + 11 * len(results)))
    for k, name in enumerate(pops.names):
        row = f"{name:<20} {base_rates[k]:>8.2f}"
        row += "".join(f"{r[k]:>11.2f}" for r, _ in results.values())
        print(row)

    print("\nLectura: 'corr tasas' cerca de 1 significa que el control produce el "
          "mismo\nperfil de actividad que el real, o sea que esa propiedad del "
          "grafo no importaba.")


if __name__ == "__main__":
    main()
