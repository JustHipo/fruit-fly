# Cómo correr el viewer en vivo

```bash
cd fruit-fly
source .venv-body/bin/activate
cd art-fly/scripts
mjpython live_view.py --trace ../../out/f1/trace_real.json --fps 20
```

Tiene que ser `mjpython`, no `python`.

## Controles

Se muestran directamente en la ventana (arriba a la izquierda), no hace falta memorizarlos:

- **Espacio**: pausar / reanudar
- **Flecha derecha**: un paso adelante (funciona en pausa)
- **Flecha izquierda**: retroceder de verdad (restaura postura y pintura desde una instantánea, no es solo un contador)
- **r**: reiniciar desde el frame 0
- **s**: exportar el lienzo pintado a PNG (`out/f2/live_capture_<fecha>.png`)
- **Mouse**: arrastrar para orbitar, rueda para zoom, shift+arrastrar para paneo

Ctrl+C en la terminal para cortar.

## Si vuelve a crashear con "NSWindow should only be instantiated on the main thread"

Dos causas posibles, ambas ya resueltas una vez en este proyecto:

1. **`.venv-body` se recreó con `uv venv`.** `mjpython` está roto en entornos creados por `uv` ([bug conocido](https://github.com/google-deepmind/mujoco/issues/1923)). Solución: `rm -rf .venv-body && python3.10 -m venv .venv-body`, y reinstalar `flybody` y `art-fly` ahí. Nunca usar `uv venv` para este entorno específico.
2. **Algo en el código llama a `physics.render()`** (el render offscreen de dm_control) en el mismo proceso que el viewer interactivo. Los dos no pueden coexistir, en ningún orden. Si se agrega código nuevo a `live_view.py`, no debe llamar nunca a `physics.render()` ni tocar `physics.contexts`; usar `viewer.update_texture()` para subir la textura del lienzo.

Detalle completo de cómo se diagnosticaron ambas causas en `../docs/migraciones/F2-cuerpo-ik.md`, actualización 2026-09-15g.
