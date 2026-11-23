"""Cuerpo de la mosca: cinematica inversa de pata con limites articulares.

La mosca esta fija (preparacion tethered, ARQUITECTURA.md 6.4): no camina, solo
mueve las patas. El alcance es puramente articular.

Dos problemas del solver de flybody que hay que manejar, los dos medidos el
2026-09-15:

1. **No impone los limites articulares.** En objetivos lejanos devuelve
   soluciones que los violan (la tibia se pasa un 0,9% en la esquina del area
   util). Se recorta despues de cada pasada.

2. **Su `err_norm` no es reproducible.** El solver reporta 0,000103 mientras que
   aplicar el `qpos` que devuelve deja la garra a 0,006283 del objetivo, sesenta
   veces peor. Aparentemente mide en un espacio intermedio propio. Confiar en ese
   numero habria dado una garra que aterriza un 2% del largo del cuerpo fuera del
   objetivo, en silencio, que es justo el tipo de error que no se nota hasta que
   la obra sale mal.

   La solucion es **iterar con arranque caliente** y cortar por el error
   *medido*, no por el reportado. Cuatro pasadas de 300 llevan el error real de
   0,0063 a 0,00007, y son mas rapidas que una sola pasada de 3.000.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

import numpy as np
from dm_control import mjcf

import flybody
from flybody.inverse_kinematics import qpos_from_site_xpos

logging.getLogger().setLevel(logging.ERROR)   # el solver avisa en cada no-convergencia

LEG_SEGMENTS = ("coxa_abduct", "coxa_twist", "coxa", "femur_twist", "femur",
                "tibia", "tarsus", "tarsus2", "tarsus3", "tarsus4", "tarsus5")

LEGS = ("T1_left", "T1_right", "T2_left", "T2_right", "T3_left", "T3_right")


def model_path() -> str:
    return os.path.join(os.path.dirname(flybody.__file__),
                        "fruitfly", "assets", "fruitfly.xml")


@dataclass(frozen=True)
class ReachResult:
    reached: bool
    error: float          # distancia medida, no la que reporta el solver
    position: np.ndarray
    clamped: bool
    passes: int


class LegIK:
    """Lleva la punta de una pata a una coordenada, respetando los limites."""

    def __init__(self, physics: mjcf.Physics, leg: str = "T1_left",
                 tolerance: float = 0.001, max_steps: int = 300, lr: float = 0.05,
                 max_passes: int = 8) -> None:
        if leg not in LEGS:
            raise ValueError(f"pata desconocida: {leg!r}, esperaba una de {LEGS}")
        self.physics = physics
        self.leg = leg
        self.site = f"claw_{leg}"
        self.joints = [f"{seg}_{leg}" for seg in LEG_SEGMENTS]
        self.tolerance = tolerance
        self.max_steps = max_steps
        self.lr = lr
        self.max_passes = max_passes

        named = physics.named.model
        self.limits = {j: (float(named.jnt_range[j][0]), float(named.jnt_range[j][1]),
                           bool(named.jnt_limited[j])) for j in self.joints}

    @property
    def rest_position(self) -> np.ndarray:
        return self.physics.named.data.site_xpos[self.site].copy()

    def _clamp(self) -> bool:
        """Recorta las articulaciones de esta pata a sus limites."""
        clamped = False
        for j in self.joints:
            lo, hi, limited = self.limits[j]
            if not limited:
                continue
            v = float(np.asarray(self.physics.named.data.qpos[j]).reshape(-1)[0])
            if v < lo or v > hi:
                self.physics.named.data.qpos[j] = np.clip(v, lo, hi)
                clamped = True
        return clamped

    def press(self, xy: np.ndarray, hover_z: float, canvas_top: float,
             max_depth: float, contact_check, depth_steps: int = 4) -> tuple[ReachResult, bool]:
        """Baja progresivamente hasta lograr contacto real, o hasta max_depth.

        No asume un desfase fijo entre el site y el geom de colision: se midio
        (F2-cuerpo-ik.md, actualizacion 2026-09-15d) que ese desfase depende de
        la POSTURA de la pata, no es una constante por pata. Lejos del reposo la
        capsula de la garra rota y su punto mas bajo cambia. La unica forma
        robusta de saber si hay contacto es preguntarle a la fisica en cada
        profundidad, no calcularlo de antemano.

        `contact_check` es una funcion sin argumentos que devuelve True si esta
        pata esta tocando el lienzo AHORA (se llama despues de cada intento).
        """
        x, y = float(xy[0]), float(xy[1])
        result = self.reach([x, y, hover_z])
        if contact_check():
            return result, True

        for depth in np.linspace(max_depth / depth_steps, max_depth, depth_steps):
            result = self.reach([x, y, canvas_top - depth])
            if contact_check():
                return result, True
        return result, False

    def reach(self, target: np.ndarray) -> ReachResult:
        """Itera hasta que la garra este a menos de `tolerance` del objetivo."""
        target = np.asarray(target, dtype=float).reshape(1, 3)
        goal = target.ravel()
        clamped_any = False

        for attempt in range(1, self.max_passes + 1):
            # inplace=True deja la solucion en el physics, asi que la pasada
            # siguiente arranca caliente desde donde quedo la anterior.
            qpos_from_site_xpos(self.physics, [self.site], target, self.joints,
                                lr=self.lr, max_steps=self.max_steps, inplace=True)
            clamped_any |= self._clamp()
            self.physics.forward()

            achieved = self.physics.named.data.site_xpos[self.site].copy()
            error = float(np.linalg.norm(achieved - goal))
            if error < self.tolerance:
                return ReachResult(True, error, achieved, clamped_any, attempt)

        return ReachResult(False, error, achieved, clamped_any, self.max_passes)


def load_physics() -> mjcf.Physics:
    return mjcf.Physics.from_xml_path(model_path())
