"""Viewer en vivo de la consola: la mosca real (cuerpo tethered de art-fly)
sobre la superficie fisica, con las zonas de la consola (ARQUITECTURA.md 7.6)
pintadas encima como leyenda, y un punto que marca donde cada pata toco de
verdad este cuadro.

Ademas suena: apenas arranca, prepara la sesion de REAPER (pistas,
instrumentos, tempo) y manda "play". A medida que T1 izquierda logra
contacto real con su cooldown respetado, la nota se manda a REAPER ahi
mismo, con el reloj real del visor - ver y escuchar pasan juntos, a
diferencia de compose_with_body.py (que arma toda la pieza antes de mandar
nada) o de correr este visor solo (que antes no tocaba REAPER para nada).

Mismo patron que art-fly/scripts/live_view.py (Player, key_callback liviano,
viewer.update_texture en vez de physics.render - ver ese archivo para el por
que de cada decision, se aplica igual aca).

Tiene que correr con mjpython, no python (igual que el de art-fly):

    mjpython music-fly/scripts/live_view_console.py --trace out/music-fly/f1/live_trace.json

Reproduce una traza YA GRABADA, no corre el cerebro en vivo (frontera de
archivo entre entornos, ARQUITECTURA 3.2).

Controles: espacio pausa/reanuda, flechas paso a paso (sin retroceder: a
diferencia del lienzo de art-fly, acA no hay pintura acumulada que
reconstruir, retroceder es solo el indice), r reinicia, s guarda PNG.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from pathlib import Path

import glfw
import mujoco
import mujoco.viewer
import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "music-fly"))
sys.path.insert(0, str(REPO / "art-fly"))

from artfly.legs import REACH_RADIUS  # noqa: E402
from artfly.scene import canvas_texture_array, live_view_texture_id, paint_on_texture  # noqa: E402

from console.body_compose import LEG_MAP, LEG_ORDER, build_body, step_body  # noqa: E402
from console.compose import LiveNoteGate, meter_and_tempo  # noqa: E402
from console.decoder import ConsoleDecoder  # noqa: E402
from console.screen import SCREEN_TEXTURE_RES, screen_texture_array, screen_texture_id  # noqa: E402
from console.vocabulary import INSTRUMENTS, METERS  # noqa: E402

import os  # noqa: E402
OBS_HOST, OBS_PORT = "127.0.0.1", 4455
OBS_PASSWORD = os.environ.get("OBS_PASSWORD", "")  # clave del websocket de OBS, fuera del repo
# Nombre real, verificado, de la fuente que muestra REAPER (2026-09-16: la
# fuente vieja "macOS Screen Capture 2" quedo con el stream interno de
# ScreenCaptureKit trabado - se probo con --force, con recrearla, nada la
# revivio; se resolvio usando otra fuente que si funcionaba y renombrandola).
# Ver music-fly/docs/migraciones/F2-consola.md.
OBS_SOURCE = "REAPER capture"
SCREEN_REFRESH_SECONDS = 1.0   # reloj real, no cuadros: cada cuadro de IK tarda distinto


def connect_obs():
    """None si OBS no esta corriendo o la fuente no existe - la pantalla 3D
    se queda en negro en vez de romper el visor entero por esto."""
    try:
        import obsws_python as obs
        client = obs.ReqClient(host=OBS_HOST, port=OBS_PORT, password=OBS_PASSWORD, timeout=3)
        client.get_version()
        return client
    except Exception as e:
        print(f"OBS no disponible para la pantalla 3D ({e}); sigue sin ella.")
        return None


def fetch_reaper_frame(obs_client) -> np.ndarray | None:
    """Un frame de REAPER via OBS, como array (H,W,3) uint8, o None si falla.
    Imprime el error en vez de tragarlo en silencio: la vez anterior que
    fallo, tragarlo en silencio hizo perder tiempo adivinando por que la
    pantalla se veia vacia."""
    if obs_client is None:
        return None
    try:
        import base64
        import io
        shot = obs_client.get_source_screenshot(OBS_SOURCE, "png", 800, 500, -1)
        b64 = shot.image_data.split(",", 1)[1]
        img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
        # Espejado: MuJoCo mapea la cara -X de una caja al reves de como se
        # ve desde adentro (la mosca mira +X hacia la pantalla, o sea ve la
        # cara -X). Confirmado por el usuario, no supuesto.
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
        img = img.resize((SCREEN_TEXTURE_RES, SCREEN_TEXTURE_RES), Image.LANCZOS)
        return np.asarray(img)
    except Exception as e:
        print(f"pantalla 3D: no se pudo traer un cuadro de OBS ({e})")
        return None

QUEUE_DIR = REPO / "out/music-fly/f0/queue"


def send_reaper(cmds: list[str]) -> None:
    """Igual que send() en los scripts de composicion, pero silenciosa (esto
    corre dentro del loop del visor, no hace falta imprimir cada lote)."""
    import os
    ts = time.time_ns()
    tmp = QUEUE_DIR / f".tmp-{ts}"
    final = QUEUE_DIR / f"{ts}.cmd"
    tmp.write_text("\n".join(cmds) + "\n")
    os.rename(tmp, final)

# Colores de la leyenda: una zona por instrumento (T2L, mas una de silencio -
# ver console.compose.REST_ZONE) y una por compas (T3R).
REST_COLOR = (40, 40, 45)   # gris oscuro: la zona de silencio, no un instrumento
INSTRUMENT_COLORS = [(90, 160, 220), (220, 140, 60), (140, 220, 160), (220, 90, 160)]
METER_COLORS = [(120, 200, 120), (200, 120, 200), (220, 200, 90), (220, 90, 90)]
TOUCH_COLOR = (255, 255, 255)

# La mosca no compone una linea de tiempo que crece para siempre: trabaja
# adentro de un loop de REAPER (setloop + repeat), y cada nota se ubica
# modulo el largo del loop. Evita que "se cierre el loop y siga agregando
# cosas despues" (hallazgo del usuario, 2026-09-16).
LOOP_BARS = 4
# Salto entre cuadros de la traza, medido, no puesto a ojo: la autocorrelacion
# del gesto decodificado cae de 0.41 (1 cuadro) a ~0 a partir de 5 cuadros de
# distancia (music-fly/docs/migraciones/F2-consola.md). Sin este salto, cada
# paso del visor mira el cuadro siguiente al anterior - casi el mismo estado
# cerebral - y dentro de un loop corto suena siempre parecido, sin que haga
# falta alargar el loop ni la traza para arreglarlo.
FRAME_STRIDE = 7
# El balanceo entre pistas (para no saturar un solo canal) vive en
# console.compose.LiveNoteGate (BALANCE_THRESHOLD) - nunca deja de tocar,
# solo prefiere la pista menos cargada cuando la diferencia es grande.


def paint_zone_legend(physics, rest, canvas_top) -> None:
    """Pinta, una sola vez, donde esta cada zona de eleccion (7.6) sobre la
    superficie fisica: las zonas de instrumento (silencio + 4 instrumentos
    reales, ver console.vocabulary.INSTRUMENTS) bajo T2 izquierda, las 4
    de compas bajo T3 derecha. El resto de la superficie queda neutra: T1
    (nota) y T2 derecha (perillas) son continuas, no tienen zonas discretas
    que dibujar."""
    from artfly.scene import canvas_to_unit

    def zone_center(leg_console: str, n_zones: int, zone_i: int) -> tuple[float, float]:
        leg = LEG_MAP[leg_console]
        rx, ry = float(rest[leg][0]), float(rest[leg][1])
        radius = REACH_RADIUS[leg]
        # centro de la zona i de n en X, Y fijo en el medio del alcance de la pata.
        frac = (zone_i + 0.5) / n_zones * 2 - 1  # -1..1
        x = rx + frac * radius
        y = ry
        return x, y

    n_zones = len(INSTRUMENTS) + 1  # +1: la zona de silencio, ver console.compose.REST_ZONE
    x, y = zone_center("T2L", n_zones, 0)
    u, v = canvas_to_unit(x, y)
    paint_on_texture(physics, u, v, REST_COLOR, radius_px=30)
    for i, inst in enumerate(INSTRUMENTS):
        x, y = zone_center("T2L", n_zones, i + 1)
        u, v = canvas_to_unit(x, y)
        paint_on_texture(physics, u, v, INSTRUMENT_COLORS[i], radius_px=30)

    for i, meter in enumerate(METERS):
        x, y = zone_center("T3R", len(METERS), i)
        u, v = canvas_to_unit(x, y)
        paint_on_texture(physics, u, v, METER_COLORS[i], radius_px=25)


class Player:
    def __init__(self, physics, ik, rest, canvas_top, decoder, frames, tex_id, note_gate,
                loop_length_s, play_t0, screen_tex_id=None, obs_client=None):
        self.physics = physics
        self.ik = ik
        self.rest = rest
        self.canvas_top = canvas_top
        self.decoder = decoder
        self.frames = frames
        self.tex_id = tex_id
        self.note_gate = note_gate
        self.loop_length_s = loop_length_s
        self.play_t0 = play_t0
        self.screen_tex_id = screen_tex_id
        self.obs_client = obs_client
        self.last_screen_refresh = -SCREEN_REFRESH_SECONDS
        self.i = 0
        self.paused = False
        self.viewer = None
        self.pending: str | None = None
        self.last_saved: str | None = None
        self.last_contacted: tuple[str, ...] = ()
        self.notes_sent = 0
        self.track_counts: dict[int, int] = {inst.track: 0 for inst in INSTRUMENTS}
        self._last_t_loop = 0.0

    def refresh_view(self) -> None:
        if self.viewer is not None:
            self.viewer.update_texture(self.tex_id)
            if self.screen_tex_id is not None:
                self.viewer.update_texture(self.screen_tex_id)
            self.viewer.set_texts(self.overlay())

    def save_png(self, outdir: Path = REPO / "out/music-fly/f2") -> str:
        outdir.mkdir(parents=True, exist_ok=True)
        tex = canvas_texture_array(self.physics)
        img = Image.fromarray(tex).resize((1024, 1024), Image.LANCZOS)
        path = outdir / f"console_capture_{time.strftime('%Y%m%d_%H%M%S')}.png"
        img.save(path)
        return str(path)

    def overlay(self) -> tuple:
        estado = "PAUSADO" if self.paused else "reproduciendo"
        contactos = ", ".join(self.last_contacted) if self.last_contacted else "(ninguna)"
        pistas = ", ".join(f"{INSTRUMENTS[i].label}:{n}"
                           for i, n in enumerate(self.track_counts.values()))
        return (
            mujoco.mjtFontScale.mjFONTSCALE_150.value,
            mujoco.mjtGridPos.mjGRID_TOPLEFT.value,
            f"cuadro {self.i}/{len(self.frames)}  [{estado}]\ncontacto real: {contactos}\n"
            f"notas mandadas a REAPER: {self.notes_sent}  ({pistas})",
            "espacio: pausa/reanuda\n"
            "flecha derecha: paso adelante\n"
            "r: reiniciar\n"
            "s: guardar PNG\n"
            "mouse: arrastrar orbita, rueda zoom\n"
            "gris osc.=silencio, azul/naranja/verde/rosa=instrumento (T2 izq)\n"
            "verde/violeta/amarillo/rojo: zonas de compas (T3 der)"
            + (f"\nguardado: {self.last_saved}" if self.last_saved else ""),
        )

    def step_forward(self) -> None:
        z = np.array(self.frames[self.i]["z"], dtype=np.float64)
        decoded = self.decoder(z)
        result = step_body(self.physics, self.ik, self.rest, self.canvas_top, decoded)
        self.last_contacted = result.contacted
        for leg_name, target in zip(LEG_ORDER, result.legs):
            if target.press:
                u, v = (target.x + 1) / 2, (target.y + 1) / 2
                from artfly.scene import paint_on_texture as _paint
                _paint(self.physics, u, v, TOUCH_COLOR, radius_px=6)

        # Ver Y escuchar juntos: en cuanto T1L logra contacto real (con su
        # cooldown ya respetado), la nota se manda a REAPER ahi mismo. El
        # tiempo se modula al largo del loop (nunca escribe mas alla de
        # donde REAPER va a repetir), y al detectar la vuelta del loop se
        # resetea el cooldown para que el primer cuadro del ciclo nuevo
        # pueda disparar de inmediato en vez de quedar bloqueado por el
        # ultimo tiempo (alto) del ciclo anterior.
        t_real = time.perf_counter() - self.play_t0
        t_loop = t_real % self.loop_length_s
        if t_loop < self._last_t_loop:
            self.note_gate.last_note_t = -self.note_gate.min_gap_s
        self._last_t_loop = t_loop

        note = self.note_gate.maybe_fire(t_loop, result.legs, self.track_counts)
        if note is not None:
            end = min(note.end_s, self.loop_length_s)
            # replacenote, no testnote: sin esto una nota vieja del mismo
            # compas de un ciclo anterior del loop nunca se borraba, solo
            # se apilaban notas encima para siempre (hallazgo del usuario).
            send_reaper([f"replacenote {note.track} {note.start_s:.3f} {end:.3f} "
                        f"{note.pitch} {note.velocity}"])
            self.notes_sent += 1
            self.track_counts[note.track] += 1

            # Perillas (T2 derecha): se decodificaban pero nunca se mandaban
            # a REAPER (hallazgo del usuario: "eligio instrumentos pero no
            # edito nada dentro de ellos"). Los primeros 2 parametros del
            # instrumento activo, continuos, cuando esa pata realmente
            # dispara una nota.
            t2r = result.legs[3]  # LEG_ORDER: T1L,T1R,T2L,T2R,T3L,T3R
            knob0 = (t2r.x + 1.0) / 2.0
            knob1 = (t2r.y + 1.0) / 2.0
            send_reaper([
                f"fx {note.track} 0 0 {knob0:.3f}",
                f"fx {note.track} 0 1 {knob1:.3f}",
            ])

        now = time.perf_counter()
        if self.screen_tex_id is not None and now - self.last_screen_refresh >= SCREEN_REFRESH_SECONDS:
            self.last_screen_refresh = now
            frame = fetch_reaper_frame(self.obs_client)
            if frame is not None:
                screen_texture_array(self.physics)[:] = frame

        self.i = (self.i + FRAME_STRIDE) % len(self.frames)

    def reset(self) -> None:
        self.physics.reset()
        self.i = 0
        canvas_texture_array(self.physics)[:] = (247, 247, 247)
        paint_zone_legend(self.physics, self.rest, self.canvas_top)
        # No reinicia la sesion de REAPER: las notas ya mandadas quedan. Solo
        # se le permite al gate volver a disparar de inmediato.
        self.note_gate.last_note_t = -self.note_gate.min_gap_s


def key_callback(player: "Player"):
    def _callback(keycode: int) -> None:
        if keycode == glfw.KEY_SPACE:
            player.paused = not player.paused
            # Sincronizado con REAPER en el mismo instante (hallazgo del
            # usuario: antes solo se pausaba la mosca, y REAPER seguia
            # solo hasta llegar al final del loop y pararse por su cuenta).
            # Es solo escribir un archivo chiquito, no es el trabajo pesado
            # de IK que el callback nunca puede hacer (ver docstring de
            # art-fly/scripts/live_view.py).
            send_reaper(["stop" if player.paused else "play"])
        elif keycode == glfw.KEY_RIGHT:
            player.paused = True
            player.pending = "forward"
        elif keycode == glfw.KEY_R:
            player.paused = True
            player.pending = "reset"
        elif keycode == glfw.KEY_S:
            player.pending = "save"
    return _callback


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace", default=str(REPO / "out/music-fly/f1/live_trace.json"))
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--fps", type=float, default=10.0,
                    help="ritmo de reproduccion; bajo a proposito porque cada cuadro hace IK real de 6 patas")
    args = ap.parse_args()

    trace = json.loads(Path(args.trace).read_text())
    frames = trace["frames"]
    decoder = ConsoleDecoder(n_pop=len(trace["populations"]), seed=args.seed)

    # Compas y tempo: no necesitan cuerpo fisico (T3R es continuo, no
    # depende de contacto), asi que se calculan una vez sobre la traza cruda,
    # igual que hace compose_from_legs.
    decoded_all = [decoder(np.array(f["z"], dtype=np.float64)) for f in frames]
    meter, tempo = meter_and_tempo(decoded_all)
    note_gate = LiveNoteGate(meter, tempo)
    print(f"compas: {meter.name}  tempo: {tempo:.1f}bpm")

    loop_length_s = LOOP_BARS * meter.steps_per_bar * note_gate.grid_step_s
    print(f"loop: {LOOP_BARS} compases de {meter.name} = {loop_length_s:.2f}s, repitiendo")

    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    send_reaper([f"addtrack {inst.track}" for inst in INSTRUMENTS])
    time.sleep(0.3)
    send_reaper([f"addfx {inst.track} {inst.name}" for inst in INSTRUMENTS])
    time.sleep(0.3)
    send_reaper([f"tempo {tempo:.2f}"])
    time.sleep(0.1)
    send_reaper([f"setloop 0.0 {loop_length_s:.3f}", "repeat 1"])
    time.sleep(0.1)
    send_reaper(["play"])
    play_t0 = time.perf_counter()
    print("REAPER: pistas creadas, tempo y loop fijados, play mandado. Las notas van a ir "
          "apareciendo DENTRO del loop a medida que las patas toquen de verdad. Espacio pausa "
          "el loop en REAPER tambien, no solo la ventana.")

    print("Conectando con OBS para la pantalla 3D (opcional, si falla sigue sin ella)...")
    obs_client = connect_obs()

    print("Construyendo el cuerpo fisico (esto tarda unos segundos, no esta colgado)...")
    physics, ik, rest, canvas_top = build_body(with_screen=obs_client is not None)
    paint_zone_legend(physics, rest, canvas_top)
    print("Cuerpo listo. Abriendo la ventana...")
    tex_id = live_view_texture_id(physics)
    screen_tex_id = screen_texture_id(physics) if obs_client is not None else None
    player = Player(physics, ik, rest, canvas_top, decoder, frames, tex_id, note_gate,
                    loop_length_s, play_t0, screen_tex_id, obs_client)

    print(f"traza: {len(frames)} cuadros. Cada cuadro hace IK real de 6 patas, va lento.")
    print("mouse: arrastrar orbita, rueda zoom. teclado: espacio, flecha derecha, r, s.")

    dt = 1.0 / args.fps
    with mujoco.viewer.launch_passive(physics.model.ptr, physics.data.ptr,
                                      key_callback=key_callback(player)) as viewer:
        player.viewer = viewer
        player.refresh_view()
        try:
            while viewer.is_running():
                t0 = time.perf_counter()

                if player.pending == "forward":
                    player.step_forward()
                    player.refresh_view()
                    player.pending = None
                elif player.pending == "reset":
                    player.reset()
                    player.refresh_view()
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
                    viewer.set_texts(player.overlay())
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
