"""Pipeline 3D con seis patas: la pintura aparece sobre la superficie fisica.

Corre en el entorno "body" (Python 3.10, flybody). Consume una traza ya grabada
por el entorno "brain": la frontera entre entornos es ese archivo (ARQUITECTURA
3.2).

La pintura se deposita directamente en la textura del lienzo (`scene.py`,
`paint_on_texture`), no en un lienzo 2D separado: lo que se ve en el video o en
el viewer en vivo ES el resultado, no una reconstruccion aparte.

Coordinacion de seis patas (F2-cuerpo-ik.md, actualizaciones 2026-09-15c/d): el
cerebro elige UNA pata activa por frame via `LegSelector` (discreto, legitimo
porque una mosca real mueve una pata a la vez). Mientras la misma pata sigue
activa se interpola en sub-pasos; al cambiar de pata no hay interpolacion (paso
fisico discreto). La presion usa `LegIK.press()`: prueba profundidades
crecientes y verifica contacto real, nunca asume una profundidad fija.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import numpy as np

logging.getLogger().setLevel(logging.ERROR)

from artfly.body import LEGS, LegIK
from artfly.color import BandPalette, PopulationColor
from artfly.legs import REACH_RADIUS, LegSelector
from artfly.pen import PenDecoder
from artfly.scene import (build_tethered_scene, canvas_to_unit, paint_on_texture,
                          read_contacts, upload_canvas_texture)

MAX_PRESS_DEPTH = 0.008
SUBSTEPS = 4


def load_trace(path: Path) -> dict:
    return json.loads(path.read_text())


def build_pipeline(trace_path: Path, color: str, seed: int, create_render_context: bool = True):
    """Arma todo lo necesario para pintar cuadro a cuadro. Reusado por el
    script de video y por el viewer en vivo, para que se comporten igual.

    `create_render_context=False` para el viewer en vivo: ver la advertencia en
    `scene.upload_canvas_texture()`.
    """
    trace = load_trace(trace_path)
    populations = trace["populations"]
    decoder = PenDecoder(n_pop=len(populations), seed=seed)
    selector = LegSelector(n_pop=len(populations), seed=seed + 100)
    color_source = PopulationColor(len(populations)) if color == "poblacion" else BandPalette()

    physics = build_tethered_scene()
    if create_render_context:
        # SOLO para el pipeline offscreen (video/PNG). El viewer en vivo NO
        # puede llamar esto: physics.render() y mujoco.viewer.launch_passive no
        # coexisten en el mismo proceso en macOS (F2-cuerpo-ik.md, 2026-09-15g).
        physics.render(width=64, height=64)
    ik = {leg: LegIK(physics, leg=leg) for leg in LEGS}
    rest = {leg: ik[leg].rest_position.copy() for leg in LEGS}
    canvas_gid = physics.model.name2id("canvas_surface", "geom")
    canvas_top = (physics.data.geom_xpos[canvas_gid][2]
                 + physics.model.geom_size[canvas_gid][2])

    state = {"prev_leg": None, "prev_xy": {}}

    def step(z: np.ndarray) -> dict:
        """Un cuadro: decodifica, mueve la pata elegida, pinta si hay contacto."""
        stroke = decoder(z, color_source)
        choice = selector(z)
        leg = choice.leg
        radius = REACH_RADIUS[leg]
        rx, ry = rest[leg][0], rest[leg][1]
        x = float(np.clip(rx + stroke.dx / decoder.max_step * radius, rx - radius, rx + radius))
        y = float(np.clip(ry + stroke.dy / decoder.max_step * radius, ry - radius, ry + radius))

        continuing = (leg == state["prev_leg"]) and (leg in state["prev_xy"])
        substeps = SUBSTEPS if continuing else 1
        x0, y0 = state["prev_xy"].get(leg, (x, y))

        def touching_now(leg=leg):
            physics.forward()
            return any(c.leg == leg for c in read_contacts(physics))

        touched = False
        for s in range(1, substeps + 1):
            t = s / substeps
            xs, ys = x0 + (x - x0) * t, y0 + (y - y0) * t
            if stroke.pen_down:
                _, ok = ik[leg].press([xs, ys], hover_z=canvas_top + 0.002,
                                      canvas_top=canvas_top, max_depth=MAX_PRESS_DEPTH,
                                      contact_check=touching_now)
                if ok:
                    contacts = [c for c in read_contacts(physics) if c.leg == leg]
                    u, v = canvas_to_unit(contacts[0].position[0], contacts[0].position[1])
                    rgb = tuple(int(c * 255) for c in stroke.rgb())
                    paint_on_texture(physics, u, v, rgb, radius_px=int(stroke.width * 900))
                    touched = True
            else:
                ik[leg].reach([xs, ys, canvas_top + 0.002])

        state["prev_xy"][leg] = (x, y)
        state["prev_leg"] = leg
        return {"leg": leg, "pen_down": stroke.pen_down, "touched": touched}

    return physics, trace, step


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace", required=True)
    ap.add_argument("--color", choices=["poblacion", "banda"], default="poblacion")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default="out/f2")
    ap.add_argument("--frames", type=int, default=0)
    ap.add_argument("--video-frames", type=int, default=60)
    args = ap.parse_args()

    outdir = Path(args.out)
    frames_dir = outdir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    physics, trace, step = build_pipeline(Path(args.trace), args.color, args.seed)
    frames = trace["frames"][: args.frames] if args.frames else trace["frames"]
    print(f"traza: {len(frames)} frames, {len(trace['populations'])} poblaciones")

    video_every = max(1, len(frames) // args.video_frames)
    frame_counter = 0
    log = []

    for i, frame in enumerate(frames):
        z = np.array(frame["z"], dtype=np.float64)
        result = step(z)
        log.append({"i": i, **result})

        if i % video_every == 0:
            upload_canvas_texture(physics)
            img = physics.render(camera_id=0, width=480, height=360)
            from PIL import Image
            Image.fromarray(img).save(frames_dir / f"{frame_counter:05d}.png")
            frame_counter += 1

    upload_canvas_texture(physics)
    final = physics.render(camera_id=0, width=900, height=900)
    from PIL import Image
    Image.fromarray(final).save(outdir / "canvas_3d.png")
    (outdir / "log.json").write_text(json.dumps(log, indent=1))

    n_pen_down = sum(1 for l in log if l["pen_down"])
    n_touched = sum(1 for l in log if l["touched"])
    from collections import Counter
    leg_usage = Counter(l["leg"] for l in log)

    print(f"\nframes: {len(log)}")
    print(f"pluma abajo: {n_pen_down} ({n_pen_down/len(log):.0%})")
    print(f"contacto real: {n_touched} ({n_touched/max(1,n_pen_down):.0%} de los intentos)")
    print("uso de cada pata:")
    for leg in LEGS:
        n = leg_usage.get(leg, 0)
        print(f"  {leg:<10} {n:>5} ({n/len(log):.0%})")
    print(f"\nrender final: {outdir/'canvas_3d.png'}")
    print(f"frames de video: {frames_dir} ({frame_counter} archivos)")
    print(f"armar video: ffmpeg -y -framerate 12 -i {frames_dir}/%05d.png {outdir}/preview.mp4")


if __name__ == "__main__":
    main()
