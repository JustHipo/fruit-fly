"""Viewer en vivo: la mosca pinta en una ventana real, con mouse para orbitar y
hacer zoom (controles nativos del visor de MuJoCo), mas pausa, paso a paso y
retroceder de verdad.

Tiene que correr con `mjpython`, no `python`: en macOS la interfaz grafica
exige el hilo principal, y `mjpython` es el lanzador que MuJoCo instala para
eso.

    mjpython art-fly/scripts/live_view.py --trace out/f1/trace_real.json

Reproduce una traza YA GRABADA (frontera de archivo entre los entornos brain y
body, ARQUITECTURA 3.2), no corre el cerebro en vivo.

Controles de teclado:
    espacio       pausar / reanudar
    flecha derecha  un paso adelante (funciona en pausa)
    flecha izquierda  un paso atras: restaura fisica Y lienzo pintado desde una
                      instantanea guardada, no solo mueve un indice
    r             reiniciar desde el frame 0

IMPORTANTE (hallazgo medido, F2-cuerpo-ik.md 2026-09-15g): este script NUNCA
llama a `physics.render()` (el render offscreen de dm_control). Crear ese
contexto en el mismo proceso que `mujoco.viewer.launch_passive` hace crashear
la ventana en macOS ('NSWindow should only be instantiated on the main
thread'), sin importar el orden. La textura del lienzo se sube en cambio con
`viewer.update_texture()`, que usa el contexto propio del viewer.

Otro hallazgo del mismo problema: `mjpython` instalado en un entorno creado con
`uv venv` crashea con este mismo error incluso sin ninguna de las dos causas de
arriba. Se resolvio recreando el entorno con `python3.10 -m venv` (venv
estandar) (bug conocido: github.com/google-deepmind/mujoco issue #1923). Si
esto se vuelve a romper, verificar primero que `.venv-body` no se haya vuelto a
crear con `uv venv`.
"""

from __future__ import annotations

import argparse
import time
import traceback
from pathlib import Path

import glfw
import mujoco
import mujoco.viewer
import numpy as np
from PIL import Image

from artfly.scene import canvas_texture_array, live_view_texture_id
from paint_3d import build_pipeline


class Player:
    """Estado de reproduccion: pausa, indice actual, e historial para retroceder.

    El historial guarda una copia de `qpos` y de la textura del lienzo por
    frame. Sin esto, "retroceder" solo podria mover un indice mientras la
    pintura ya depositada y la postura de las patas quedan como estaban, que es
    peor que no tener el boton: parece que retrocede pero no retrocede nada.
    """

    def __init__(self, physics, frames, step_fn, tex_id, max_history: int = 2000):
        self.physics = physics
        self.frames = frames
        self.step_fn = step_fn
        self.tex_id = tex_id
        self.max_history = max_history
        self.i = 0
        self.paused = False
        self.history: list[tuple[np.ndarray, np.ndarray]] = []
        self.viewer = None   # se asigna despues de abrir la ventana
        self.pending: str | None = None   # accion pedida por teclado, ver nota abajo
        self.last_saved: str | None = None   # para mostrarlo un rato en el overlay

    def refresh_view(self) -> None:
        """Sube la textura y el overlay al viewer, si ya esta abierto.

        Hace falta llamarlo tambien desde el callback de teclado: un paso
        manual (flecha) cambia la fisica y la textura en memoria, pero sin
        esto la pantalla no se entera hasta el siguiente ciclo del loop
        principal, que esta pausado y no va a llegar.
        """
        if self.viewer is not None:
            self.viewer.update_texture(self.tex_id)
            self.viewer.set_texts(self.overlay())

    def save_png(self, outdir: Path = Path("../../out/f2")) -> str:
        """Exporta el lienzo pintado a PNG. Solo lee la textura ya en memoria,
        sin fisica ni IK de por medio, asi que es seguro dejarlo en el loop
        principal sin preocuparse por bloquear nada."""
        outdir.mkdir(parents=True, exist_ok=True)
        tex = canvas_texture_array(self.physics)
        img = Image.fromarray(tex).resize((1024, 1024), Image.LANCZOS)
        path = outdir / f"live_capture_{time.strftime('%Y%m%d_%H%M%S')}.png"
        img.save(path)
        return str(path)

    def overlay(self) -> tuple:
        """Texto fijo en pantalla: sin esto los controles solo existian en la
        terminal, invisibles mientras se mira la ventana."""
        estado = "PAUSADO" if self.paused else "reproduciendo"
        return (
            mujoco.mjtFontScale.mjFONTSCALE_150.value,
            mujoco.mjtGridPos.mjGRID_TOPLEFT.value,
            f"frame {self.i}/{len(self.frames)}  [{estado}]",
            "espacio: pausa/reanuda\n"
            "flecha derecha: paso adelante\n"
            "flecha izquierda: retroceder (de verdad)\n"
            "r: reiniciar\n"
            "s: guardar PNG del arte\n"
            "mouse: arrastrar orbita, rueda zoom"
            + (f"\nguardado: {self.last_saved}" if self.last_saved else ""),
        )

    def _snapshot(self) -> None:
        snap = (self.physics.data.qpos.copy(), canvas_texture_array(self.physics).copy())
        self.history.append(snap)
        if len(self.history) > self.max_history:
            self.history.pop(0)

    def step_forward(self) -> None:
        self._snapshot()
        z = np.array(self.frames[self.i]["z"], dtype=np.float64)
        self.step_fn(z)
        self.i = (self.i + 1) % len(self.frames)

    def step_backward(self) -> None:
        if not self.history:
            return
        qpos, tex = self.history.pop()
        self.physics.data.qpos[:] = qpos
        self.physics.forward()
        canvas_texture_array(self.physics)[:] = tex
        self.i = max(0, self.i - 1)

    def reset(self, background_rgb: tuple[int, int, int] = (247, 247, 247)) -> None:
        """Reset real, en el lugar: no hace falta reconstruir la escena.

        `physics.reset()` (de dm_control) vuelve las articulaciones a la pose
        inicial del modelo. La textura del lienzo se limpia aparte, porque
        reset() no toca las texturas (son datos del modelo, no del estado
        fisico). El decodificador y el selector de pata NO se reinician: son
        deterministas dado z, asi que da lo mismo, y reiniciarlos forzaria
        reconstruir el pipeline entero para ganar nada.
        """
        self.physics.reset()
        canvas_texture_array(self.physics)[:] = background_rgb
        self.i = 0
        self.history.clear()


def key_callback(player: "Player") -> callable:
    """Callback de MuJoCo: corre en el hilo de la interfaz grafica, NO en el
    hilo donde vive el loop principal (mjpython separa los dos a proposito).

    Por eso este callback NUNCA hace el trabajo pesado (mover la pata implica
    varios intentos de cinematica inversa, `LegIK.press()`) directamente: eso
    bloquearia la interfaz mientras calcula, que es exactamente el "se quedo
    pegado" que se veia al usar las flechas. El callback solo deja una
    intencion liviana en `player.pending`, y el loop principal la ejecuta en su
    propio hilo, en el momento que le toca.
    """
    def _callback(keycode: int) -> None:
        if keycode == glfw.KEY_SPACE:
            player.paused = not player.paused
            print("pausado" if player.paused else "reanudado")
        elif keycode == glfw.KEY_RIGHT:
            player.paused = True
            player.pending = "forward"
        elif keycode == glfw.KEY_LEFT:
            player.paused = True
            player.pending = "backward"
        elif keycode == glfw.KEY_R:
            player.paused = True
            player.pending = "reset"
        elif keycode == glfw.KEY_S:
            player.pending = "save"
    return _callback


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace", required=True)
    ap.add_argument("--color", choices=["poblacion", "banda"], default="poblacion")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--fps", type=float, default=20.0)
    ap.add_argument("--history", type=int, default=2000,
                    help="cuantos frames de retroceso mantener en memoria")
    args = ap.parse_args()

    physics, trace, step = build_pipeline(Path(args.trace), args.color, args.seed,
                                          create_render_context=False)
    frames = trace["frames"]
    tex_id = live_view_texture_id(physics)
    player = Player(physics, frames, step, tex_id, max_history=args.history)

    print(f"traza: {len(frames)} frames. Ctrl+C en la terminal para cortar.")
    print("mouse: arrastrar orbita, rueda hace zoom, shift+arrastrar panea.")
    print("teclado: espacio pausa/reanuda, flechas paso a paso, r reinicia.")

    dt = 1.0 / args.fps
    with mujoco.viewer.launch_passive(physics.model.ptr, physics.data.ptr,
                                      key_callback=key_callback(player)) as viewer:
        player.viewer = viewer
        try:
            while viewer.is_running():
                t0 = time.perf_counter()

                if player.pending == "forward":
                    player.step_forward()
                    player.refresh_view()
                    player.pending = None
                elif player.pending == "backward":
                    player.step_backward()
                    player.refresh_view()
                    player.pending = None
                elif player.pending == "reset":
                    player.reset()
                    player.refresh_view()
                    print("reiniciado desde el frame 0")
                    player.pending = None
                elif player.pending == "save":
                    player.last_saved = player.save_png()
                    print(f"guardado: {player.last_saved}")
                    player.refresh_view()
                    player.pending = None
                elif not player.paused:
                    player.step_forward()
                    player.refresh_view()
                else:
                    viewer.set_texts(player.overlay())   # que el overlay reaccione a pausa igual
                viewer.sync()

                elapsed = time.perf_counter() - t0
                if elapsed < dt:
                    time.sleep(dt - elapsed)
        except Exception:
            print("\n--- la ventana se esta por cerrar por una excepcion, no en silencio ---")
            traceback.print_exc()
            raise


if __name__ == "__main__":
    main()
