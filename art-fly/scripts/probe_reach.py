"""Mide el area que alcanza una garra sobre un plano horizontal.

Es el experimento que define F2: si la pata alcanza poco, el lienzo es chico o
hay que moverlo debajo de la mosca (ARQUITECTURA.md 6.4).

La mosca esta fija (tethered), asi que el alcance es puramente articular.
"""

import argparse
import logging
import os

import numpy as np

from artfly.body import LegIK, load_physics

logging.getLogger().setLevel(logging.ERROR)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--leg", default="T1_left")
    ap.add_argument("--z", type=float, default=-0.127, help="altura del plano del lienzo")
    ap.add_argument("--grid", type=int, default=21)
    ap.add_argument("--span", type=float, default=0.20, help="lado del area a sondear")
    ap.add_argument("--tol", type=float, default=0.001,
                    help="error maximo aceptado, en unidades del modelo")
    ap.add_argument("--steps", type=int, default=300)
    args = ap.parse_args()

    physics = load_physics()
    ik = LegIK(physics, leg=args.leg, tolerance=args.tol, max_steps=args.steps)
    rest = ik.rest_position
    print(f"garra {ik.site} en reposo: {np.round(rest, 4)}")
    print(f"sondeando plano z={args.z} con grilla {args.grid}x{args.grid} "
          f"de lado {args.span}\n")

    cx, cy = rest[0], rest[1]
    half = args.span / 2
    xs = np.linspace(cx - half, cx + half, args.grid)
    ys = np.linspace(cy - half, cy + half, args.grid)

    reach = np.zeros((args.grid, args.grid), dtype=bool)
    errors = np.full((args.grid, args.grid), np.nan)
    clamped = np.zeros((args.grid, args.grid), dtype=bool)
    passes = np.zeros((args.grid, args.grid), dtype=int)
    qpos0 = physics.data.qpos.copy()

    for iy, y in enumerate(ys):
        for ix, x in enumerate(xs):
            physics.data.qpos[:] = qpos0          # misma pose inicial siempre
            physics.forward()
            result = ik.reach([x, y, args.z])
            errors[iy, ix] = result.error
            reach[iy, ix] = result.reached
            clamped[iy, ix] = result.clamped
            passes[iy, ix] = result.passes

    ok = reach.mean()
    cell = (xs[1] - xs[0]) * (ys[1] - ys[0])
    print(f"alcanzables: {reach.sum()} de {reach.size} ({ok:.0%})")
    print(f"area alcanzable: {reach.sum() * cell:.5f} unidades^2 "
          f"({np.sqrt(reach.sum() * cell):.4f} de lado equivalente)")

    if reach.any():
        ry, rx = np.where(reach)
        print(f"caja util: x [{xs[rx.min()]:.4f}, {xs[rx.max()]:.4f}]  "
              f"y [{ys[ry.min()]:.4f}, {ys[ry.max()]:.4f}]")
        print(f"error mediano en los alcanzables: {np.nanmedian(errors[reach]):.6f}")
        print(f"objetivos que necesitaron recorte articular: {clamped.sum()} ({clamped.mean():.0%})")
        print(f"pasadas de IK promedio: {passes[reach].mean():.1f}")

    print("\nmapa (# alcanzable, . no):")
    for iy in range(args.grid - 1, -1, -1):
        print("  " + "".join("#" if reach[iy, ix] else "." for ix in range(args.grid)))


if __name__ == "__main__":
    main()
