"""La mosca fija, con la consola fisica debajo (reusada de art-fly) Y una
pantalla real delante de la cabeza, mostrando REAPER en vivo.

No modifica art-fly/artfly/scene.py: reusa las mismas piezas
(model_path, la tecnica de soldar el freejoint, la superficie de consola)
pero agrega la pantalla ACA, porque es especifico de music-fly (pedido del
usuario: "la mosca deberia estar mirando una pantalla grande que renderize
lo que esta haciendo con el DAW", ARQUITECTURA.md seccion 10).

La cabeza de la mosca mira +X (medido: head=[0.0567,0,-0.003], thorax en el
origen), asi que la pantalla se pone mas adelante en +X, encarada hacia la
mosca.
"""

from __future__ import annotations

import numpy as np
from dm_control import mjcf

from artfly.body import model_path

SCREEN_POS = (0.75, 0.0, 0.05)       # delante de la cabeza (head en x=0.057)
SCREEN_SIZE = (0.001, 0.56, 0.34)    # fina en X: las caras grandes miran +-X (2x el tamano anterior)
SCREEN_TEXTURE_RES = 512   # subido de 256: se veia borroso


def build_console_scene(
    canvas_z: float = -0.13717,
    canvas_half_size: float = 0.26,
    canvas_texture_res: int = 256,
    screen_texture_res: int = SCREEN_TEXTURE_RES,
) -> mjcf.Physics:
    """Igual que artfly.scene.build_tethered_scene, mas una pantalla."""
    root = mjcf.from_path(model_path())

    thorax = root.find("body", "thorax")
    freejoint = next(c for c in thorax.all_children() if c.tag == "freejoint")
    freejoint.remove()

    canvas_rgb = np.full((canvas_texture_res, canvas_texture_res, 3), 247, dtype=np.uint8)
    root.asset.add(
        "texture", name="canvas_texture", type="2d", builtin="flat",
        width=canvas_texture_res, height=canvas_texture_res,
        rgb1=[0.97, 0.97, 0.95],
    )
    root.asset.add("material", name="canvas_material", texture="canvas_texture")
    canvas_body = root.worldbody.add("body", name="canvas", pos=[0.0, 0.0, canvas_z])
    canvas_body.add(
        "geom", name="canvas_surface", type="box",
        size=[canvas_half_size, canvas_half_size, 0.0008],
        material="canvas_material", contype=1, conaffinity=1,
    )

    screen_rgb = np.full((screen_texture_res, screen_texture_res, 3), 30, dtype=np.uint8)
    root.asset.add(
        "texture", name="screen_texture", type="2d", builtin="flat",
        width=screen_texture_res, height=screen_texture_res,
        rgb1=[0.1, 0.1, 0.12],
    )
    root.asset.add("material", name="screen_material", texture="screen_texture",
                   specular=0.1, shininess=0.05)
    screen_body = root.worldbody.add("body", name="screen", pos=list(SCREEN_POS))
    screen_body.add(
        "geom", name="screen_surface", type="box", size=list(SCREEN_SIZE),
        material="screen_material", contype=0, conaffinity=0,  # no choca con nada
    )

    # Camara de referencia amplia, para verificar offscreen que la pantalla
    # entra en cuadro junto con la mosca (la camara por defecto del modelo
    # de flybody es angosta, pensada para la mosca sola). mode=targetbody
    # apunta sola al torax, no hace falta calcular la orientacion a mano.
    root.worldbody.add(
        "camera", name="wide", pos=[0.4, -1.7, 0.9], fovy=70,
        mode="targetbody", target="thorax",
    )

    physics = mjcf.Physics.from_mjcf_model(root)

    tex_id = physics.model.name2id("canvas_texture", "texture")
    adr = physics.model.tex_adr[tex_id]
    n = canvas_texture_res * canvas_texture_res * 3
    physics.model.tex_data[adr:adr + n] = canvas_rgb.ravel()

    tex_id = physics.model.name2id("screen_texture", "texture")
    adr = physics.model.tex_adr[tex_id]
    n = screen_texture_res * screen_texture_res * 3
    physics.model.tex_data[adr:adr + n] = screen_rgb.ravel()

    return physics


def screen_texture_id(physics: mjcf.Physics) -> int:
    return physics.model.name2id("screen_texture", "texture")


def screen_texture_array(physics: mjcf.Physics, texture_res: int = SCREEN_TEXTURE_RES) -> np.ndarray:
    tex_id = screen_texture_id(physics)
    adr = physics.model.tex_adr[tex_id]
    n = texture_res * texture_res * 3
    return physics.model.tex_data[adr:adr + n].reshape(texture_res, texture_res, 3)


def upload_screen_texture(physics: mjcf.Physics) -> None:
    """Sube la textura de la pantalla a la GPU para el render OFFSCREEN.
    Igual advertencia que artfly.scene.upload_canvas_texture: nunca en el
    mismo proceso que el viewer interactivo. El visor en vivo usa
    viewer.update_texture(screen_texture_id(physics)) en cambio."""
    import mujoco
    tex_id = screen_texture_id(physics)
    mujoco.mjr_uploadTexture(physics.model.ptr, physics.contexts.mujoco.ptr, tex_id)
