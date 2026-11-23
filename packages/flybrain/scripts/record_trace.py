"""Corre el conectoma y graba una traza de z-scores poblacionales.

Es el entregable de F0: el archivo que consumen art-fly y music-fly.
"""

import argparse
import time

import numpy as np
import torch

from flybrain import (Populations, Trace, calibrate, load_connectome,
                      LifNetwork, LifParams, PopulationReader)
from flybrain.controls import CONTROLS


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/connectome_data_prep/data/maleCNS")
    ap.add_argument("--seconds", type=float, default=2.0)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--control", choices=list(CONTROLS), default=None,
                    help="corre un conectoma degradado en vez del real")
    ap.add_argument("--out", default="out/trace.json")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--sample-every", type=int, default=25, help="pasos entre frames grabados")
    args = ap.parse_args()

    conn = load_connectome(
        f"{args.data}/mcns_ad_inprop_all_neuron.npz",
        f"{args.data}/mcns_all_neuron_meta.csv",
    )
    label = "real"
    if args.control:
        conn = CONTROLS[args.control](conn, seed=args.seed + 1)
        label = args.control
    print(f"conectoma [{label}]: {conn.n_neurons:,} neuronas, {conn.n_edges:,} aristas")

    pops = Populations.from_superclass(conn)
    print(f"poblaciones: {len(pops)}")

    net = LifNetwork(conn, LifParams(), device=args.device)

    t0 = time.perf_counter()
    baseline = calibrate(net, pops, seconds=2.5, seed=args.seed)
    print(f"calibracion en {time.perf_counter()-t0:.1f}s")

    torch.manual_seed(args.seed)
    reader = PopulationReader(pops, net.device, dt=net.params.dt)
    reader.reset(to=baseline.mean)        # sin esto, los primeros frames son transitorio
    state = net.initial_state()
    trace = Trace.start(baseline, net.params.dt)

    for _ in range(int(200 / net.params.dt)):   # 200 ms de asentamiento
        state, fired = net.step(state, net.noise())
        reader.update(fired)

    steps = int(args.seconds * 1000 / net.params.dt)
    t0 = time.perf_counter()
    for i in range(steps):
        state, fired = net.step(state, net.noise())
        rate = reader.update(fired)
        if i % args.sample_every == 0:
            trace.append(i * net.params.dt / 1000.0,
                         baseline.z(rate.cpu().numpy()))
    elapsed = time.perf_counter() - t0

    path = trace.save(args.out)
    z = trace.array
    print(f"\nsimulados {args.seconds}s en {elapsed:.1f}s ({args.seconds/elapsed:.3f}x tiempo real)")
    print(f"traza: {path} ({len(trace.times)} frames, {z.shape[1]} poblaciones)")

    print(f"\n{'poblacion':<20} {'n':>7} {'Hz reposo':>10} {'z min':>7} {'z max':>7} {'z std':>7}")
    print("-" * 62)
    for k, name in enumerate(pops.names):
        print(f"{name:<20} {pops.sizes[k]:>7,} {baseline.mean[k]:>10.2f} "
              f"{z[:,k].min():>7.2f} {z[:,k].max():>7.2f} {z[:,k].std():>7.2f}")


if __name__ == "__main__":
    main()
