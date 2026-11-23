"""Compara el conectoma real contra los tres controles de topologia.

Es el control de honestidad de F0. Si el real no se distingue de los degradados,
el cableado medido no esta aportando nada y hay que decirlo.

Diseno escalonado tomado de `flydoom`:
  real le gana a shuffle_weights     -> importan los pesos medidos
  real le gana a degree_preserving   -> importa el cableado mas alla de los grados
  real le gana a erdos_renyi         -> al menos importan tamano y densidad
"""

import argparse

import numpy as np
import torch

from flybrain import (Populations, calibrate, load_connectome, LifNetwork,
                      LifParams, PopulationReader)
from flybrain.controls import CONTROLS


def run(conn, pops, device, seconds, seed):
    net = LifNetwork(conn, LifParams(), device=device)
    baseline = calibrate(net, pops, seconds=1.5, seed=seed)

    torch.manual_seed(seed)
    reader = PopulationReader(pops, net.device, dt=net.params.dt)
    reader.reset(to=baseline.mean)
    state = net.initial_state()
    for _ in range(200):
        state, fired = net.step(state, net.noise())
        reader.update(fired)

    frames = []
    for i in range(int(seconds * 1000)):
        state, fired = net.step(state, net.noise())
        rate = reader.update(fired)
        if i % 25 == 0:
            frames.append(baseline.z(rate.cpu().numpy()).copy())
    return baseline.mean, np.stack(frames)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/connectome_data_prep/data/maleCNS")
    ap.add_argument("--seconds", type=float, default=1.5)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    real = load_connectome(
        f"{args.data}/mcns_ad_inprop_all_neuron.npz",
        f"{args.data}/mcns_all_neuron_meta.csv",
    )
    pops = Populations.from_superclass(real)

    print("corriendo real...")
    base_rates, base_z = run(real, pops, args.device, args.seconds, args.seed)

    results = {}
    for name, fn in CONTROLS.items():
        print(f"corriendo {name}...")
        results[name] = run(fn(real, seed=args.seed + 1), pops, args.device,
                            args.seconds, args.seed)

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
