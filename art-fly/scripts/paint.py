"""Pinta un lienzo a partir de una traza de actividad neuronal."""

import argparse

import numpy as np

from artfly import MODES, SOURCES, BandPalette, PenDecoder, PopulationColor, render
from flybrain import Trace


def build_color_source(name: str, n_pop: int):
    return PopulationColor(n_pop) if name == "poblacion" else BandPalette()


def paint_trace(trace: Trace, seed: int = 0, size: int = 900, mode: str = "continuo",
                color: str = "poblacion", substeps: int = 6, cells: int = 64):
    source = build_color_source(color, len(trace.populations))
    decoder = PenDecoder(n_pop=len(trace.populations), seed=seed)
    strokes = [decoder(z, source) for z in trace.array]
    return render(strokes, mode=mode, size=size, cells=cells, substeps=substeps)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace", default="out/trace.json")
    ap.add_argument("--out", default="out/art.png")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--size", type=int, default=900)
    ap.add_argument("--substeps", type=int, default=6)
    ap.add_argument("--render", choices=MODES, default="continuo")
    ap.add_argument("--color", choices=list(SOURCES), default="poblacion")
    ap.add_argument("--cells", type=int, default=64, help="solo para --render pixel")
    args = ap.parse_args()

    trace = Trace.load(args.trace)
    z = trace.array
    print(f"traza: {z.shape[0]} frames, {z.shape[1]} poblaciones, "
          f"z en [{z.min():.2f}, {z.max():.2f}]")

    canvas = paint_trace(trace, seed=args.seed, size=args.size, mode=args.render,
                         color=args.color, substeps=args.substeps, cells=args.cells)
    canvas.save(args.out)

    source = build_color_source(args.color, z.shape[1])
    decoder = PenDecoder(n_pop=z.shape[1], seed=args.seed)
    strokes = [decoder(row, source) for row in z]
    down = sum(s.pen_down for s in strokes)
    hues = [st.hsv[0] for st in strokes]
    print(f"color [{args.color}]: {len(set(round(h,2) for h in hues))} matices distintos")
    print(f"trazos: {len(strokes)} decodificados, {down} con pluma abajo ({down/len(strokes):.0%})")
    if hasattr(canvas, "ink"):
        print(f"tinta depositada: {canvas.ink:,.0f}")
    else:
        print(f"cobertura de celdas: {canvas.coverage:.1%}")
    print(f"render: {args.render} | color: {args.color} | guardado: {args.out}")


if __name__ == "__main__":
    main()
