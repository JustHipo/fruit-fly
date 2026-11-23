# Modelos 3D: de dónde salen y cómo verlos

## Respuesta corta

**No hace falta ninguna app de modelado, y no hay que descargar ningún modelo de internet.** El modelo de mosca ya viene dentro de `flybody`, y todo lo demás de la escena son primitivas geométricas definidas en texto.

## Por qué no sirve bajar una mosca de Sketchfab

Esta es la parte contraintuitiva. Lo que necesitamos **no es una malla bonita**, es un **cuerpo riggeado y parametrizado físicamente**:

| Lo que trae un modelo de Sketchfab | Lo que necesita la simulación |
|---|---|
| Geometría y texturas | Geometría **y** articulaciones con sus límites |
| | Masa e inercia por segmento |
| | Actuadores (músculos) |
| | Geometrías de colisión separadas de las visuales |
| | Sitios nombrados en las puntas de las patas |

Un modelo decorativo de mosca no tiene nada de la columna derecha. Riggearlo desde cero (definir cada articulación de cada pata, sus rangos, masas e inercias) sería un proyecto entero por sí solo, y quedaría biológicamente inventado.

`flybody` resuelve exactamente eso: es un modelo **anatómicamente detallado**, construido por Janelia junto con Google DeepMind a partir de microscopía real, publicado en Nature (2025). Trae las articulaciones, las masas, los actuadores y los seis sitios de garra nombrados (`claw_T1_left` y compañía) que nuestra cinemática inversa necesita.

## Qué archivos son

Al instalar `flybody` quedan disponibles:

```
flybody/fruitfly/assets/
├── fruitfly.xml        el modelo MJCF: cuerpo, articulaciones, actuadores, sitios
└── meshes/             las mallas de cada segmento
```

El formato es **MJCF**, el XML de MuJoCo. Es texto plano y editable.

## Cómo se agrega el lienzo

En texto, dentro del MJCF. No se modela nada:

```xml
<body name="canvas" pos="0 0 0">
  <geom name="canvas_surface" type="box" size="0.02 0.015 0.0005"
        rgba="1 1 1 1" material="canvas_tex"/>
</body>
```

Un `box` fino es el lienzo. Si además tiene que trasladarse y rotar bajo la mosca (ver [art-fly 6.4](../../art-fly/ARQUITECTURA.md)), se le agregan articulaciones deslizantes y una de giro. Sigue siendo XML.

## Cómo verlo en vivo

### Viewer nativo interactivo

```bash
source .venv-body/bin/activate
mjpython -m mujoco.viewer --mjcf=escena.xml
```

Abre una ventana real donde se puede orbitar, hacer zoom y pausar. **En macOS tiene que ser `mjpython`, no `python`**: es un lanzador que MuJoCo instala justamente porque macOS exige que la interfaz gráfica corra en el hilo principal.

Desde código, para verlo mientras corre la simulación:

```python
import mujoco, mujoco.viewer

model = mujoco.MjModel.from_xml_path("escena.xml")
data = mujoco.MjData(model)

with mujoco.viewer.launch_passive(model, data) as viewer:
    while viewer.is_running():
        mujoco.mj_step(model, data)
        viewer.sync()
```

`launch_passive` es la clave: deja que nosotros manejemos el bucle, así podemos meter el cerebro y el decodificador en el medio.

### Frames para video

```python
frame = physics.render(camera_id=0, width=1280, height=720)  # (H, W, 3) uint8
```

Y después se arman con ffmpeg 8.0, que ya está instalado.

Nota de macOS: usar la ruta por defecto `glfw`/CGL. **Nunca setear `MUJOCO_GL=egl`**, EGL no existe acá.

## ¿Y Blender?

**Opcional, y no hace falta para nada de lo planificado.** Solo tendría sentido en dos casos:

1. Si quisiéramos autorear geometría nueva (un lienzo con forma rara, un soporte de la mosca más elaborado).
2. Si quisiéramos un render cinematográfico offline, más lindo que el de MuJoCo, para presentar la obra.

Para el segundo caso existe además [neuVid](https://github.com/connectome-neuprint/neuVid), que genera videos anatómicos de Drosophila con Blender a partir de datos de neuPrint. Es una opción para un video de presentación del conectoma en sí, no para la simulación.

Blender es gratis y pesa cerca de 1 GB. Dado que hoy el disco está al límite, **no instalarlo hasta que haga falta de verdad**.

## Resumen

| Necesito | Herramienta | ¿Instalar algo? |
|---|---|---|
| El cuerpo de la mosca | `flybody` | Ya está en el plan |
| El lienzo | XML a mano | No |
| Verlo en vivo | `mjpython -m mujoco.viewer` | Viene con MuJoCo |
| Grabar video | `physics.render()` + ffmpeg | ffmpeg ya instalado |
| Render cinematográfico | Blender | Solo si algún día hace falta |
