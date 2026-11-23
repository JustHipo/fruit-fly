"""El cuerpo fisico real conectado a la consola. Corre en el entorno "body"
(Python 3.10, flybody + dm_control + mujoco), reusando directo la
infraestructura de art-fly (ARQUITECTURA.md 6, y F2-cuerpo-ik.md de
art-fly): mismo cuerpo tethered, mismo LegIK, mismo lector de contactos
reales.

Diferencia con art-fly: alli UNA pata esta activa por cuadro (LegSelector,
legitimo porque pintar es un gesto de a una pata). Aca las SEIS patas tienen
un rol fijo simultaneo (ARQUITECTURA.md 7.6: T1L=nota, T1R=duracion,
T2L=instrumento, T2R=perillas, T3L=mute, T3R=compas/tempo), asi que las seis
se simulan fisicamente cada cuadro.

Principio heredado de art-fly, aplicado ahora a la consola en vez del
lienzo: el contacto SIEMPRE se mide con la fisica real
(`scene.read_contacts`), nunca se asume. Si el decodificador "quiere" que
una pata presione pero la fisica no logra contacto real (fuera de alcance,
IK no converge), esa pata queda en press=False para la interpretacion
musical de aguas abajo - exactamente como el lienzo de art-fly nunca pinta
sobre un intento fallido.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "music-fly"))
sys.path.insert(0, str(REPO / "art-fly"))

from artfly.body import LEGS, LegIK  # noqa: E402
from artfly.legs import REACH_RADIUS  # noqa: E402
from artfly.scene import build_tethered_scene, canvas_to_unit, read_contacts  # noqa: E402

from console.decoder import ConsoleDecoder, LegTarget  # noqa: E402
from console.screen import build_console_scene  # noqa: E402

MAX_PRESS_DEPTH = 0.008

# Orden de la consola (ARQUITECTURA.md 7.6) -> nombre real de pata de art-fly.
LEG_ORDER = ("T1L", "T1R", "T2L", "T2R", "T3L", "T3R")
LEG_MAP = {
    "T1L": "T1_left", "T1R": "T1_right",
    "T2L": "T2_left", "T2R": "T2_right",
    "T3L": "T3_left", "T3R": "T3_right",
}


@dataclass(frozen=True)
class BodyStepResult:
    legs: tuple[LegTarget, ...]   # objetivos REALES, verificados por fisica
    contacted: tuple[str, ...]    # que patas lograron contacto real este cuadro


def build_body(create_render_context: bool = False, with_screen: bool = False):
    """Arma la escena tethered, los seis LegIK, y devuelve todo lo necesario
    para simular la consola cuadro a cuadro.

    `create_render_context=True` SOLO para pipelines offscreen que van a
    llamar `physics.render()` para exportar PNG/video. El visor en vivo
    (live_view_console.py, mujoco.viewer.launch_passive) NUNCA puede pasar
    True aca: crear el contexto de render de dm_control en el mismo proceso
    que el viewer interactivo cuelga la ventana en macOS
    ('NSWindow should only be instantiated on the main thread'), el mismo
    hallazgo ya documentado en art-fly/docs/migraciones/F2-cuerpo-ik.md
    (actualizacion 2026-09-15g). compose_with_body.py tampoco lo necesita:
    no renderiza nada, solo corre la fisica y manda notas a REAPER - por eso
    el default es False.
    """
    physics = build_console_scene() if with_screen else build_tethered_scene()
    if create_render_context:
        physics.render(width=64, height=64)

    ik = {leg: LegIK(physics, leg=leg) for leg in LEGS}
    rest = {leg: ik[leg].rest_position.copy() for leg in LEGS}
    canvas_gid = physics.model.name2id("canvas_surface", "geom")
    canvas_top = (physics.data.geom_xpos[canvas_gid][2]
                 + physics.model.geom_size[canvas_gid][2])
    return physics, ik, rest, canvas_top


def step_body(physics, ik, rest, canvas_top, decoded: tuple[LegTarget, ...]) -> BodyStepResult:
    """Un cuadro: intenta llevar las seis patas a sus objetivos decodificados,
    y devuelve los objetivos REALES segun lo que la fisica confirmo.
    """
    real_legs = []
    contacted = []

    for console_leg, target in zip(LEG_ORDER, decoded):
        leg = LEG_MAP[console_leg]
        rx, ry = float(rest[leg][0]), float(rest[leg][1])
        radius = REACH_RADIUS[leg]
        xs = np.clip(rx + target.x * radius, rx - radius, rx + radius)
        ys = np.clip(ry + target.y * radius, ry - radius, ry + radius)

        def touching_now(leg=leg):
            physics.forward()
            return any(c.leg == leg for c in read_contacts(physics))

        if target.press:
            _, ok = ik[leg].press(
                [xs, ys], hover_z=canvas_top + 0.002, canvas_top=canvas_top,
                max_depth=MAX_PRESS_DEPTH, contact_check=touching_now,
            )
            if ok:
                contacts = [c for c in read_contacts(physics) if c.leg == leg]
                u, v = canvas_to_unit(contacts[0].position[0], contacts[0].position[1])
                real_legs.append(LegTarget(x=2 * u - 1, y=2 * v - 1, press=True))
                contacted.append(console_leg)
            else:
                real_legs.append(LegTarget(x=target.x, y=target.y, press=False))
        else:
            ik[leg].reach([xs, ys, canvas_top + 0.002])
            real_legs.append(LegTarget(x=target.x, y=target.y, press=False))

    return BodyStepResult(legs=tuple(real_legs), contacted=tuple(contacted))


def run_body_trace(times: list[float], z_values: list[np.ndarray], seed: int = 0):
    """Corre la traza entera cuadro a cuadro, devuelve la secuencia de
    objetivos REALES (uno por cuadro) lista para console.compose.compose_from_legs.
    """
    decoder = ConsoleDecoder(n_pop=len(z_values[0]), seed=seed)
    physics, ik, rest, canvas_top = build_body()

    real_sequence = []
    contact_log = []
    for z in z_values:
        decoded = decoder(z)
        result = step_body(physics, ik, rest, canvas_top, decoded)
        real_sequence.append(result.legs)
        contact_log.append(result.contacted)

    return real_sequence, contact_log, physics
