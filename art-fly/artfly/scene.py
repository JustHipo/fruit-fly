"""Escena tethered: mosca soldada al mundo, mas el lienzo como cuerpo fisico.

Preparacion tethered (ARQUITECTURA.md 6.4): se elimina la `freejoint` del torax,
asi que el cuerpo queda rigidamente anclado en el origen. Es la misma tecnica
que usa la literatura de neurociencia de Drosophila para fijar la mosca a un
soporte y dejar las patas libres.

El lienzo es un geom fisico real, no una abstraccion: la garra lo toca de
verdad, y de ese contacto se lee la fuerza para la presion (scene.py, no
pen.py). Ver ARQUITECTURA.md 10.3: mover la presion de "decodificada" a "medida
por fisica" es la mejora central de F2 sobre F1.
"""

from __future__ import annotations

from dataclasses import dataclass

import mujoco
import numpy as np
from dm_control import mjcf

from artfly.body import LEGS, model_path

# Medido por busqueda binaria sobre la fisica real (no a mano): con el lienzo a
# z=-0.13281 las garras T1 ya lo tocan en la pose de reposo, porque el geom de
# colision de la garra (una capsula) cuelga varios milimetros mas abajo que el
# site que usa la IK. Confiar en la posicion del site para esto habria sido el
# mismo error que el err_norm no reproducible del solver (F2, seccion 6):
# medir en el lugar equivocado. z=-0.1358 deja margen de 0.003 sin contacto
# accidental, y presionar hacia abajo ese margen es el gesto de pintar.
DEFAULT_CANVAS_Z = -0.13717
# Medido el 2026-09-15: un lienzo de 0,11 solo cubre las patas delanteras. T2
# descansa en y=0,168 y T3 en x=-0,185, ambas fuera de esa huella: por mas que
# presionen, no llegan. 0,26 cubre la huella real de reposo+radio de las seis
# (calculo en F2-cuerpo-ik.md, actualizacion 2026-09-15d).
DEFAULT_CANVAS_SIZE = 0.26


def collision_geom(leg: str) -> str:
    return f"tarsal_claw_{leg}_collision"


CANVAS_TEXTURE_RES = 256   # resolucion de la textura editable del lienzo


def build_tethered_scene(
    canvas_z: float = DEFAULT_CANVAS_Z,
    canvas_half_size: float = DEFAULT_CANVAS_SIZE,
    texture_res: int = CANVAS_TEXTURE_RES,
) -> mjcf.Physics:
    """Mosca soldada al mundo, con un lienzo fisico debajo de las patas.

    El lienzo lleva una textura editable (`canvas_texture`) para que la pintura
    aparezca de verdad sobre la superficie fisica en el render, no solo en un
    PNG 2D aparte. Se actualiza con `paint_on_texture()` y se sube a GPU con
    `upload_canvas_texture()`.
    """
    root = mjcf.from_path(model_path())

    thorax = root.find("body", "thorax")
    freejoint = next(c for c in thorax.all_children() if c.tag == "freejoint")
    freejoint.remove()

    import numpy as np
    initial_rgb = np.full((texture_res, texture_res, 3), 247, dtype=np.uint8)
    root.asset.add(
        "texture", name="canvas_texture", type="2d", builtin="flat",
        width=texture_res, height=texture_res,
        rgb1=[0.97, 0.97, 0.95],
    )
    root.asset.add(
        "material", name="canvas_material", texture="canvas_texture",
    )

    canvas_body = root.worldbody.add(
        "body", name="canvas", pos=[0.0, 0.0, canvas_z],
    )
    canvas_body.add(
        "geom", name="canvas_surface", type="box",
        size=[canvas_half_size, canvas_half_size, 0.0008],
        material="canvas_material",
        contype=1, conaffinity=1,          # tiene que poder chocar con las garras
    )

    physics = mjcf.Physics.from_mjcf_model(root)
    tex_id = physics.model.name2id("canvas_texture", "texture")
    adr = physics.model.tex_adr[tex_id]
    n = texture_res * texture_res * 3
    physics.model.tex_data[adr:adr + n] = initial_rgb.ravel()
    return physics


def canvas_texture_array(physics: mjcf.Physics, texture_res: int = CANVAS_TEXTURE_RES) -> np.ndarray:
    """Vista (no copia) del buffer de la textura, como (H, W, 3) uint8."""
    tex_id = physics.model.name2id("canvas_texture", "texture")
    adr = physics.model.tex_adr[tex_id]
    n = texture_res * texture_res * 3
    return physics.model.tex_data[adr:adr + n].reshape(texture_res, texture_res, 3)


def upload_canvas_texture(physics: mjcf.Physics) -> None:
    """Sube la textura editada a la GPU, para el render OFFSCREEN (video, PNG).

    Requiere que ya se haya renderizado al menos una vez (`physics.render()`),
    que es lo que crea el contexto de dm_control.

    ADVERTENCIA medida (F2-cuerpo-ik.md, 2026-09-15g): esta funcion y el viewer
    interactivo (`mujoco.viewer.launch_passive`) NO PUEDEN coexistir en el mismo
    proceso en macOS. Crear el contexto offscreen de dm_control en cualquier
    momento (antes o despues de abrir el viewer) hace crashear la ventana con
    'NSWindow should only be instantiated on the main thread'. Para el viewer en
    vivo usar `live_view_upload_texture()`, que sube la textura a traves del
    contexto propio del viewer en vez de crear uno de dm_control.
    """
    import mujoco
    tex_id = physics.model.name2id("canvas_texture", "texture")
    mujoco.mjr_uploadTexture(physics.model.ptr, physics.contexts.mujoco.ptr, tex_id)


def live_view_texture_id(physics: mjcf.Physics) -> int:
    """Id de la textura del lienzo, para pasarselo a `viewer.update_texture()`."""
    return physics.model.name2id("canvas_texture", "texture")


@dataclass(frozen=True)
class Contact:
    """Un contacto real garra-lienzo, leido de la fisica."""

    leg: str
    position: np.ndarray    # punto de contacto en coordenadas del mundo
    force: float            # magnitud de la fuerza normal, unidades MuJoCo


def canvas_to_unit(x: float, y: float, half_size: float = DEFAULT_CANVAS_SIZE) -> tuple[float, float]:
    """Coordenada fisica del lienzo (metros, centrado en 0) a 0..1 normalizado."""
    u = (x + half_size) / (2 * half_size)
    v = (y + half_size) / (2 * half_size)
    return float(np.clip(u, 0.0, 1.0)), float(np.clip(v, 0.0, 1.0))


def read_contacts(physics: mjcf.Physics) -> list[Contact]:
    """Contactos garra-lienzo del ultimo `physics.forward()` o `physics.step()`.

    No se aproxima por distancia entre sitios: se lee `physics.data.contact`,
    que es lo que MuJoCo calculo de verdad a partir de la geometria de colision.
    """
    canvas_id = physics.model.name2id("canvas_surface", "geom")

    leg_geom_ids = {physics.model.name2id(collision_geom(leg), "geom"): leg
                    for leg in LEGS}

    contacts = []
    data = physics.data
    for i in range(data.ncon):
        c = data.contact[i]
        leg = None
        if c.geom1 == canvas_id and c.geom2 in leg_geom_ids:
            leg = leg_geom_ids[c.geom2]
        elif c.geom2 == canvas_id and c.geom1 in leg_geom_ids:
            leg = leg_geom_ids[c.geom1]
        if leg is None:
            continue

        force = np.zeros(6)
        mujoco.mj_contactForce(physics.model.ptr, physics.data.ptr, i, force)
        # force[0] es la componente normal en el marco de contacto: la fuerza
        # de la garra empujando hacia adentro del lienzo, que es la presion.
        contacts.append(Contact(leg=leg, position=c.pos.copy(), force=float(abs(force[0]))))

    return contacts


def paint_on_texture(physics: mjcf.Physics, u: float, v: float, rgb: tuple,
                     radius_px: int = 10, texture_res: int = CANVAS_TEXTURE_RES) -> None:
    """Deposita un toque gaussiano en la textura del lienzo, en coordenadas (u,v) 0..1.

    Analogo a `Canvas.dab()` del lienzo 2D abstracto (canvas.py), pero escribe
    directamente sobre la superficie fisica que se ve en el render.
    """
    tex = canvas_texture_array(physics, texture_res)
    cx, cy = u * texture_res, (1 - v) * texture_res   # v invertido: fila 0 es arriba
    reach = int(radius_px * 2.5)
    x0, x1 = max(0, int(cx - reach)), min(texture_res, int(cx + reach + 1))
    y0, y1 = max(0, int(cy - reach)), min(texture_res, int(cy + reach + 1))
    if x0 >= x1 or y0 >= y1:
        return
    yy, xx = np.mgrid[y0:y1, x0:x1]
    weight = np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2.0 * radius_px ** 2))
    color = np.array(rgb, dtype=np.float64)
    patch = tex[y0:y1, x0:x1].astype(np.float64)
    w = weight[..., None]
    tex[y0:y1, x0:x1] = (patch * (1 - w) + color * w).astype(np.uint8)
