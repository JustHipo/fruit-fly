"""Encuentra el rango de `weight_scale` donde el conectoma realmente conduce.

Problema que resuelve: con la escala mal puesta, la actividad la domina el ruido
inyectado y el conectoma no aporta nada. Eso es indetectable mirando la tasa
media de disparo, y produce un sistema que parece funcionar y no funciona.

Metodo: correr el conectoma real y uno con las aristas permutadas con EL MISMO
ruido, y comparar las tasas por neurona. Si son casi identicas, manda el ruido.
"""

import argparse

import numpy as np
import torch

from flybrain.controls import erdos_renyi_matched
from flybrain.data import load_connectome
from flybrain.lif import LifNetwork, LifParams


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
    ap.add_argument("--data", default="data/connectome_data_prep/data/maleCNS")
    ap.add_argument("--steps", type=int, default=250)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--scales", type=float, nargs="+",
                    default=[5, 25, 50, 100, 200, 400])
    args = ap.parse_args()

    real = load_connectome(
        f"{args.data}/mcns_ad_inprop_all_neuron.npz",
        f"{args.data}/mcns_all_neuron_meta.csv",
    )
    null = erdos_renyi_matched(real, seed=1)

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
