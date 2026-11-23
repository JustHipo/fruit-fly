"""Igual que packages/flybrain/scripts/calibrate_scale.py, pero sobre el
subgrafo motor guardado en vez del conectoma completo.

Se necesita porque el subgrafo se armo seleccionando a las neuronas con MAS
peso sinaptico entre si (metodo de 4.2), asi que es mas denso que el
promedio del conectoma completo. weight_scale=65, calibrado para el grafo
completo, dio tasas de reposo 15-20x mas altas de lo esperado (ver
music-fly/docs/migraciones/F1-subgrafo-motor.md). Este script mide si hace
falta un valor distinto para este subgrafo especifico.
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp
import torch

from flybrain.controls import erdos_renyi_matched
from flybrain.data import Connectome
from flybrain.lif import LifNetwork, LifParams

REPO = Path(__file__).resolve().parents[2]
SUBGRAPH_DIR = REPO / "out/music-fly/f1"


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


def rates(conn, scale, steps, device, seed, warmup=50):
    torch.manual_seed(seed)
    net = LifNetwork(conn, LifParams(weight_scale=scale), device=device)
    state = net.initial_state()
    for _ in range(warmup):
        state, _ = net.step(state, net.noise())
    counts = torch.zeros(net.n, device=net.device)
    for _ in range(steps):
        state, fired = net.step(state, net.noise())
        counts += fired.float()
    return (counts / (steps / 1000.0)).cpu().numpy()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", type=int, default=250)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--scales", type=float, nargs="+",
                     default=[2, 5, 10, 15, 20, 30, 45, 65])
    args = ap.parse_args()

    real = load_subgraph()
    null = erdos_renyi_matched(real, seed=1)

    print(f"subgrafo: {real.n_neurons} neuronas, {real.n_edges} aristas\n")
    print(f"{'escala':>8} {'Hz real':>9} {'Hz nulo':>9} {'corr':>7} {'silencio':>9}  veredicto")
    print("-" * 62)
    for scale in args.scales:
        r = rates(real, scale, args.steps, args.device, seed=0)
        n = rates(null, scale, args.steps, args.device, seed=0)
        corr = float(np.corrcoef(r, n)[0, 1]) if r.std() > 0 and n.std() > 0 else 1.0
        silent = float((r == 0).mean())
        if corr > 0.9:
            verdict = "manda el ruido"
        elif r.mean() > 200:
            verdict = "saturado"
        elif silent > 0.9:
            verdict = "apagado"
        else:
            verdict = "CONDUCE EL CONECTOMA"
        print(f"{scale:>8.0f} {r.mean():>9.2f} {n.mean():>9.2f} {corr:>7.3f} "
              f"{silent:>8.1%}  {verdict}")


if __name__ == "__main__":
    main()
