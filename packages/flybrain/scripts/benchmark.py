"""Mide el rendimiento real del paso LIF en esta maquina.

Usa un grafo sintetico del tamano de MaleCNS. Sirve para validar la
implementacion y medir el ratio de tiempo real ANTES de bajar los datos.
"""

import argparse
import time

import numpy as np
import pandas as pd
import torch

from flybrain.data import Connectome
from flybrain.lif import LifNetwork, LifParams


def synthetic(n_neurons: int, n_edges: int, seed: int = 0) -> Connectome:
    rng = np.random.default_rng(seed)
    nt = rng.choice(
        ["acetylcholine", "gaba", "glutamate"], size=n_neurons, p=[0.75, 0.15, 0.10]
    )
    meta = pd.DataFrame({"body_id": np.arange(n_neurons), "nt": nt})
    src = rng.integers(0, n_neurons, n_edges, dtype=np.int32)
    dst = rng.integers(0, n_neurons, n_edges, dtype=np.int32)
    sign = np.where(nt[src] == "acetylcholine", 1.0, -1.0).astype(np.float32)
    weight = rng.exponential(0.02, n_edges).astype(np.float32) * sign
    return Connectome(src, dst, weight, meta["body_id"].to_numpy(), meta)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--neurons", type=int, default=165_122)
    ap.add_argument("--edges", type=int, default=25_580_000)
    ap.add_argument("--steps", type=int, default=200)
    ap.add_argument("--device", default="mps")
    args = ap.parse_args()

    print(f"construyendo grafo sintetico: {args.neurons:,} neuronas, {args.edges:,} aristas")
    conn = synthetic(args.neurons, args.edges)

    net = LifNetwork(conn, LifParams(), device=args.device)
    print(f"  excitatorias {net.exc_src.numel():,} | inhibitorias {net.inh_src.numel():,}"
          f" | descartadas {net.n_dropped:,}")

    state = net.initial_state()

    for _ in range(20):                                    # calentamiento
        state, _ = net.step(state, net.noise())
    if args.device == "mps":
        torch.mps.synchronize()

    spikes, t0 = 0, time.perf_counter()
    for _ in range(args.steps):
        state, fired = net.step(state, net.noise())
        spikes += int(fired.sum())
    if args.device == "mps":
        torch.mps.synchronize()
    elapsed = time.perf_counter() - t0

    sps = args.steps / elapsed
    dt_s = LifParams().dt / 1000.0
    print(f"\n{args.steps} pasos en {elapsed:.2f} s")
    print(f"  {sps:.1f} pasos/s")
    print(f"  ratio de tiempo real: {sps * dt_s:.4f}x  ({1/(sps*dt_s):.1f}x mas lento)")
    print(f"  tasa media de disparo: {spikes/args.steps/args.neurons*1000:.2f} Hz")


if __name__ == "__main__":
    main()
