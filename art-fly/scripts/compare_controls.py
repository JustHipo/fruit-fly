"""Pinta el conectoma real y los tres controles con el MISMO decodificador.

Es el control de honestidad de F1. Sin esto la obra es infalsable: si el lienzo
sale igual con un grafo recableado, el conectoma era decoracion.

Todo se mantiene identico entre condiciones (semilla del decodificador, paleta,
semilla del ruido, duracion). Lo unico que cambia es el grafo.
"""

import argparse
import time
from pathlib import Path

import numpy as np
import torch
from PIL import Image

from artfly import MODES, SOURCES, BandPalette, PenDecoder, PopulationColor, render
from flybrain import (Populations, Trace, calibrate, load_connectome,
                      LifNetwork, LifParams, PopulationReader)
from flybrain.controls import CONTROLS


def record(conn, pops, seconds, device, seed, sample_every):
    net = LifNetwork(conn, LifParams(), device=device)
    baseline = calibrate(net, pops, seconds=2.0, seed=seed)

    torch.manual_seed(seed)
    reader = PopulationReader(pops, net.device, dt=net.params.dt)
    reader.reset(to=baseline.mean)
    state = net.initial_state()
    for _ in range(200):
        state, fired = net.step(state, net.noise())
        reader.update(fired)

    trace = Trace.start(baseline, net.params.dt)
    for i in range(int(seconds * 1000)):
        state, fired = net.step(state, net.noise())
        rate = reader.update(fired)
        if i % sample_every == 0:
            trace.append(i / 1000.0, baseline.z(rate.cpu().numpy()))
    return trace


def contact_sheet(images, labels, out_path, pad=16):
    from PIL import ImageDraw
    w, h = images[0].size
    sheet = Image.new("RGB", (w * len(images) + pad * (len(images) + 1), h + pad * 3), "white")
    draw = ImageDraw.Draw(sheet)
    for k, (im, label) in enumerate(zip(images, labels)):
        x = pad + k * (w + pad)
        sheet.paste(im, (x, pad * 2))
        draw.text((x + 4, 6), label, fill="black")
    sheet.save(out_path)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/connectome_data_prep/data/maleCNS")
    ap.add_argument("--seconds", type=float, default=12.0)
    ap.add_argument("--sample-every", type=int, default=10)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--size", type=int, default=700)
    ap.add_argument("--outdir", default="out/f1")
    ap.add_argument("--render", choices=MODES, default="continuo")
    ap.add_argument("--color", choices=list(SOURCES), default="poblacion")
    ap.add_argument("--cells", type=int, default=64)
    ap.add_argument("--reuse-traces", action="store_true",
                    help="repinta trazas ya grabadas en outdir en vez de simular")
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    real = load_connectome(f"{args.data}/mcns_ad_inprop_all_neuron.npz",
                           f"{args.data}/mcns_all_neuron_meta.csv")
    pops = Populations.from_superclass(real)
    color_source = (PopulationColor(len(pops)) if args.color == "poblacion"
                    else BandPalette())

    conditions = [("real", real)] + [(n, fn(real, seed=args.seed + 1))
                                     for n, fn in CONTROLS.items()]

    images, labels, stats = [], [], []
    for name, conn in conditions:
        t0 = time.perf_counter()
        cached = outdir / f"trace_{name}.json"
        if args.reuse_traces and cached.exists():
            trace = Trace.load(cached)
        else:
            trace = record(conn, pops, args.seconds, args.device, args.seed, args.sample_every)
            trace.save(cached)

        decoder = PenDecoder(n_pop=len(pops), seed=args.seed)
        strokes = [decoder(z, color_source) for z in trace.array]
        canvas = render(strokes, mode=args.render, size=args.size, cells=args.cells)
        suffix = ("" if args.render == "continuo" else f"_{args.render}")
        suffix += "" if args.color == "poblacion" else f"_{args.color}"
        canvas.save(outdir / f"{name}{suffix}.png")

        z = trace.array
        down = sum(s.pen_down for s in strokes)
        amount = getattr(canvas, "ink", None)
        if amount is None:
            amount = canvas.coverage * 100
        stats.append((name, len(strokes), down, amount, float(z.std())))
        images.append(Image.open(outdir / f"{name}{suffix}.png"))
        labels.append(name)
        print(f"{name:<18} {time.perf_counter()-t0:6.1f}s  "
              f"trazos {len(strokes):>5}  pluma abajo {down/len(strokes):>4.0%}  "
              f"pintura {amount:>10,.0f}")

    sheet = outdir / f"comparacion{suffix}.png"
    contact_sheet(images, labels, sheet)

    print(f"\n{'condicion':<18} {'trazos':>7} {'pluma':>7} {'pintura':>12} {'std z':>8}")
    print("-" * 56)
    for name, n, down, ink, zstd in stats:
        print(f"{name:<18} {n:>7,} {down/n:>6.0%} {ink:>12,.0f} {zstd:>8.3f}")
    print(f"\ncomparacion: {sheet}")


if __name__ == "__main__":
    main()
