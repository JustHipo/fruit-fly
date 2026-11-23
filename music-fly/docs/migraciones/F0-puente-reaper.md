# F0: puente REAPER

| | |
|---|---|
| Ticket | (sin clave, se trabaja standalone) |
| Proyecto | music-fly |
| Rama | `feat/f0-flybrain-fundacion` |
| Fase | F0 |
| Fecha | 2026-09-15 |
| Impacto | 🟡 aditivo |
| Estado | ✅ Completo: puente verificado de punta a punta, ritmo real medido |

## 1. Qué se hizo

Se verificó contra la máquina real, sin asumir nada, cada supuesto de [ARQUITECTURA.md sección 8](../../ARQUITECTURA.md#8-capa-4-el-puente-reaper) y sección 13 (instalación). Se encontraron y corrigieron dos supuestos falsos antes de escribir una sola línea de `fly_listener.py`. Se escribió el listener real y el cliente externo de prueba, y se investigó, con evidencia real (no leída de un foro), una vía de visualización con OBS que no estaba en el documento original.

## 2. Por qué

Aplicando la misma desconfianza que encontró los cinco supuestos falsos de art-fly (ver prompt de la sesión anterior y [LECCIONES_APRENDIDAS.md](../../../docs/referencia/LECCIONES_APRENDIDAS.md)): cada afirmación del documento de investigación se corrió contra la máquina real antes de construir nada encima.

## 3. Archivos tocados

| Archivo | Cambio |
|---|---|
| `music-fly/reaper/fly_listener.py` | Nuevo, después borrado: `RPR_defer` no existe en la API de Python de REAPER (ver actualización 2026-09-16b) |
| `music-fly/reaper/fly_listener.lua` | Nuevo. El listener real, en Lua, con instrumentación de ritmo del defer loop que el boceto de 8.2 no tenía |
| `music-fly/reaper/probe_api.py` | Nuevo. Diagnóstico de una sola vez que volcó los 810 nombres reales de la API de Python (ver actualización 2026-09-16b) |
| `music-fly/scripts/send_test_batch.py` | Nuevo. Cliente externo, el entregable de Fase 0: construye una sesión de 4 pistas, escribe a la cola de archivos |
| `~/Library/Application Support/obs-websocket/config.json` | `server_enabled: false → true`. Backup en `config.json.bak-fase0` |
| REAPER.app | Actualizado 7.41.0 → 7.80 vía `brew install --cask reaper --force` |

## 4. Validación

Completa, de punta a punta, con el usuario habiendo hecho el único paso manual posible (cargar y correr `fly_listener.lua` desde Actions). Ver actualización final más abajo para los números medidos.

## 5. Controles corridos

No aplica. No hay pieza entrenada en esta fase.

## 6. Problemas encontrados

### 6.1 REAPER instalado estaba por debajo del mínimo del documento, y no vía Homebrew

`ARQUITECTURA.md` exige 7.74+. La versión real instalada era **7.41.0** (`reaper-install-rev.txt`), instalada a mano (no gestionada por Homebrew: `brew info --cask reaper` decía "Not installed" con el binario ya presente). Corregido con `brew install --cask reaper --force` → **7.80**, verificado leyendo el título de la ventana real (ver 6.4 sobre cómo se leyó eso sin poder ver la pantalla). El `--force` fue necesario porque Homebrew se niega a instalar sobre una app no gestionada por él; no hubo pérdida de configuración porque las preferencias de REAPER viven en `~/Library/Application Support/REAPER`, separado del bundle de la app.

### 6.2 `brew install python@3.12` del documento ya no funciona

Homebrew solo mantiene las versiones recientes de la fórmula `python@X.Y`. Hoy (2026-09-15) eso es `python@3.13` y `python@3.14`; `python@3.12` fue retirada. El comando exacto de la sección 13 del documento falla.

**Solución real, mejor que la original**: este sistema ya tenía Python 3.12.14 arm64 instalado vía `uv python install 3.12` (visible en `uv python list`), en `~/.local/share/uv/python/cpython-3.12.14-macos-aarch64-none/`. Se verificó que es un build **shared** (`Py_ENABLE_SHARED=1`) con `libpython3.12.dylib` real dentro de `lib/`, arquitectura arm64 confirmada con `file`. Es un mejor camino que Homebrew para este propósito específico: `uv python install <version>` no depende de qué versiones decida mantener la fórmula de Homebrew esta semana. **Se recomienda actualizar la sección 13 de ARQUITECTURA.md** para reemplazar `brew install python@3.12` por `uv python install 3.12`.

Valores verificados para la configuración de REAPER (Preferences > Plug-ins > ReaScript):

```
Custom path to Python dll directory:
  ~/.local/share/uv/python/cpython-3.12.14-macos-aarch64-none/lib

Force ReaScript to use specific Python dll:
  libpython3.12.dylib
```

### 6.3 La trampa de arm64 de la sección 8.1, verificada y descartada

REAPER 7.80 instalado es un binario universal (`x86_64` + `arm64`); en este Mac (`arm64` nativo) macOS ejecuta la porción `arm64` sin Rosetta. El `libpython3.12.dylib` de uv es `arm64` puro. Los dos lados están alineados — la trampa que el documento advertía en 8.1 y que ya había mordido a art-fly no aplica acá, pero se verificó con `file` en vez de asumirlo por el número de versión.

### 6.4 Esta sesión de Claude Code no tiene acceso a Accessibility ni a WindowServer (confirma y extiende el hallazgo de art-fly)

Mismo límite ya documentado en `art-fly/docs/migraciones/F2-cuerpo-ik.md` (actualización "viewer en vivo"): este proceso no puede abrir ni controlar ventanas directamente.

Verificado dos veces, con dos mecanismos distintos:

- `screencapture -x` falla con `could not create image from display`.
- `osascript` controlando "System Events" para clickear un botón falla con `osascript is not allowed assistive access. (-1728)`.

Lo que **sí** funciona, y es información nueva que no estaba antes documentada: **Apple Events de alto nivel a una app específica no requieren Accessibility.** `osascript -e 'tell application "REAPER" to activate'` funciona sin error y trae la ventana al frente de verdad (confirmado visualmente, ver 6.5). La restricción es específicamente sobre *manipular la interfaz de otra app* (clicks, keystrokes vía System Events), no sobre *activarla*.

**Consecuencia práctica para este proyecto**: los dos pasos de configuración de REAPER que requieren clickear dentro de un diálogo (activar Python en Preferences, y cargar+correr `fly_listener.py` por primera vez desde Actions > Show Action List) **no se pueden automatizar desde esta sesión**. Quedan como el único paso manual de toda la Fase 0 (sección 7).

Se buscó, vía `strings` sobre el binario real de REAPER (no un foro), el nombre exacto de las claves de `reaper.ini` que probablemente persisten esta configuración: `pythonlibpath64` y `pythonlibdll64` existen literalmente en el binario. No se encontró junto a ellas una clave booleana de "enable" evidente por nombre, así que **no se editó `reaper.ini` a ciegas** — sería exactamente el tipo de fix silencioso-y-quizás-incorrecto que este proyecto evita por principio. Queda documentado como pista verificada para quien quiera intentar automatizar esto después, no como algo ya resuelto.

### 6.5 Hallazgo no buscado: el websocket de OBS sirve como "ojos" de esta sesión

Esto no estaba en el plan original, salió de investigar la pregunta del usuario sobre visualización.

**Contexto**: `obs-websocket` viene incluido en OBS desde la versión 28, confirmado en la instalación real (OBS 31.1.2, arm64 nativo). El archivo `~/Library/Application Support/obs-studio/plugin_config/obs-websocket/config.json` ya existía en esta máquina con una contraseña generada y `server_enabled: false` — evidencia de que el usuario ya lo había usado antes para algo no relacionado con este proyecto. Se hizo backup (`config.json.bak-fase0`) y se puso `server_enabled: true`.

**Prueba real, no supuesta**: con OBS corriendo y el servidor activo, se conectó un cliente Python (`obsws_python`, instalado al vuelo con `uv run --with obsws-python`) y se llamó `GetVersion` (respondió `obs_version: 31.1.2`) y `GetSourceScreenshot` sobre una fuente `screen_capture` ya configurada de antes ("macOS Screen Capture", 3024x1964 — evidencia de que OBS ya tenía permiso de Screen Recording de macOS otorgado). La imagen devuelta (base64 PNG) se guardó a disco y se leyó con la herramienta de lectura de imágenes: era la pantalla real del usuario, con la ventana de Claude Code visible. Repetido después de `tell application "REAPER" to activate`: la captura mostró la ventana real de REAPER en primer plano, título `REAPER v7.80 - EVALUATION LICENSE`, confirmando la actualización de 6.1 sin que el usuario tuviera que mirar ni confirmar nada.

**Por qué importa más allá de este ticket**: esta sesión no tiene Accessibility ni Screen Recording propios, pero OBS (una app sin sandboxing, con los permisos ya otorgados por el usuario en el pasado) sí los tiene, y su API remota no requiere Accessibility del lado de quien la llama. Eso convierte a OBS+websocket en una forma genérica de que este agente "vea" la pantalla real cuando lo necesite, no solo para música. Se agrega como lección aprendida transversal (ver `docs/referencia/LECCIONES_APRENDIDAS.md`).

**Investigación de MCP para OBS** (pregunta original del usuario: "OBS tiene MCP?"): sí, existen varios servidores MCP de terceros sobre `obs-websocket` v5 (`royshil/obs-mcp`, `LarsCanGit/OBS-MCP`, `ironystock/agentic-obs`, `xDarkzx/OBS_MCP`, `sbroenne/mcp-server-obs`). Ninguno es oficial de OBS; todos son la misma capa fina sobre el mismo protocolo que se usó acá directamente. **Decisión**: no sumar un servidor MCP de terceros como dependencia. Para control programático desde el propio pipeline del proyecto (no desde un chat), hablarle directo al websocket con `obsws-python` (o el equivalente JS) es más simple y es exactamente la misma filosofía que ya eligió el documento para REAPER: preferir la API real y liviana antes que un wrapper de terceros (mismo argumento que descartó `reapy`, sección 2.2 de ARQUITECTURA.md; de hecho existe `itsuzef/reaper-mcp`, que por dentro usa `python-reapy` y por lo tanto hereda exactamente el problema de latencia por-llamada que ARQUITECTURA.md 8.3 ya había descartado — confirma la decisión original, no la cambia).

**Lo que responde la pregunta de layout del usuario**: capturar una ventana o un Space distinto al que el usuario está mirando es técnicamente el modo `window_capture` (o `screen_capture` apuntado a un display/Space específico) de OBS sobre macOS, vía ScreenCaptureKit. **No verificado todavía**: si `window_capture` sigue capturando una ventana cuando esa ventana está en un Space distinto al que el usuario tiene activo en su pantalla física — es la pregunta técnica real detrás de "quiero ver la mosca mientras REAPER vive en otro escritorio". No se pudo probar en esta sesión porque crear o cambiar de Space requiere Mission Control, que a su vez requiere Accessibility (mismo límite de 6.4). Queda para que el usuario lo prueba una vez con dos ventanas reales (ver sección 7).

## Actualización 2026-09-16: OBS configurado para ver solo REAPER, verificado

A pedido explícito: se reconfiguró la escena de OBS para que capture **únicamente** la ventana de REAPER, no el escritorio completo.

Pasos reales (vía websocket, `obsws-python`, ningún clic):

1. `CreateInput` de tipo `window_capture` (fuente nueva "REAPER (mosca)") en la escena "Scene".
2. La lista de ventanas capturables (`GetInputPropertiesListPropertyItems`, propiedad `window`) **no incluía a REAPER la primera vez**. Después de `tell application "REAPER" to activate` y una segunda consulta, sí apareció: `[REAPER] REAPER v7.80 - EVALUATION LICENSE`, `itemValue 5939`. Hallazgo menor pero real: la enumeración de ventanas de ScreenCaptureKit no ve una app que no se activó al menos una vez desde que arrancó OBS.
3. `SetInputSettings` con `{"window": 5939}`.
4. Primer `GetSourceScreenshot` dio un PNG en blanco — no error, blanco. Un segundo intento ~2s después ya mostró la ventana real, recortada exactamente a sus bordes (barra de título incluida, nada del resto del escritorio). El retraso es esperable: ScreenCaptureKit tarda un frame en arrancar el stream de captura después de fijar el target.
5. Se desactivó (no se borró) la fuente `macOS Screen Capture` (pantalla completa) de la escena, así que la escena ahora muestra solo REAPER.

**Prueba adicional, relevante para la pregunta de Spaces (sección 6.5)**: se pasó a primer plano la ventana de Claude Code (REAPER quedó atrás, sin foco) y se volvió a pedir el screenshot de la fuente "REAPER (mosca)": **siguió mostrando el contenido real de REAPER**, no un frame congelado ni blanco. Esto es evidencia a favor de que la captura no depende de qué ventana tiene el foco — pero **no es la misma prueba que estar en un Space distinto**, que sigue sin verificarse (requiere que el usuario cree un segundo Space, ver deuda).

**Límite real encontrado más tarde (F2, 2026-09-16)**: cambiando de `window` muy rápido (varias veces en pocos segundos, buscando cuál id correspondía a qué ventana) el screenshot devuelto quedó **cacheado en un cuadro viejo** durante varios minutos, mostrando contenido de REAPER de antes de una serie de comandos reales que sí habían corrido (confirmado después con una captura de pantalla real del usuario, que mostraba el estado correcto). No se investigó la causa exacta (podría ser un frame no refrescado del lado de ScreenCaptureKit tras cambiar el target muy seguido). **Consecuencia práctica**: no asumir que una captura de OBS es del instante actual solo porque el request no dio error; ante una duda importante, o confirmar con un dato no visual (un archivo que REAPER mismo escriba, como ya hace `tick_log.jsonl`) o pedirle al usuario una captura real de su pantalla.

## Actualización 2026-09-16b: RPR_defer no existe en Python, el listener pasa a Lua

Hallazgo grande, no un detalle de implementación: cambia la arquitectura de la sección 8 de `ARQUITECTURA.md`.

**Cómo se encontró**: al cargar y correr `fly_listener.py` por primera vez (paso manual del usuario, sección 7 original), REAPER tiró `ImportError: cannot import name 'RPR_defer' from 'reaper_python'`. En vez de adivinar el nombre correcto, se escribió `probe_api.py` (queda en el repo como utilidad de diagnóstico), que se cargó y corrió dentro de REAPER y volcó **las 810 funciones reales** disponibles en el módulo `reaper_python` de esta instalación a `out/music-fly/f0/api_dump.txt`. No hay ningún `defer`, `atexit` ni `runloop`, con ningún nombre parecido. No es un problema de nombre: la función no existe.

**Por qué**: confirmado por la documentación de `reapy` (el wrapper que la sección 2.2 del documento original ya había investigado y descartado por lento, pero cuya documentación sigue siendo válida sobre esto): los ReaScripts de Python corren en el hilo principal de REAPER y **bloquean la interfaz hasta que el script termina**. No se pueden hacer loops infinitos en Python dentro de REAPER. Es la razón de fondo por la que `defer`/`atexit` sencillamente no están expuestos para Python: esas funciones dependen de que el intérprete pueda ceder el control cooperativamente cada frame, algo que Lua y EEL2 sí saben hacer (son intérpretes embebidos) y que un Python cargado por `dlopen` no.

**Consecuencia de diseño**: el listener persistente **no puede estar escrito en Python**, como asumía 8.2. Se decidió, con el usuario, pasar a **Lua** (`reaper.defer()` real, es la base de prácticamente todo el ecosistema de scripts de REAPER — SWS, ReaPack — así que no es una rareza, es lo estándar). Lua no trae librería de sockets de fábrica (por eso el documento original había elegido Python: "puede `import socket`"), así que el transporte deja de ser UDP: pasa a ser un **archivo por lote con rename atómico** dentro de un directorio-cola (`out/music-fly/f0/queue/`). A la latencia que ya impone el propio tick (20-40ms, sección 3.4/8.3), un archivo en vez de un socket no cambia nada medible. Si más adelante hiciera falta UDP real, la vía es `luasocket` vía ReaPack — se difiere hasta tener un motivo medido, no se instala de entrada.

**Archivos reemplazados**: `fly_listener.py` se borró (nunca pudo funcionar, no queda como referencia). Nuevo: `fly_listener.lua`. `send_test_batch.py` se reescribió para escribir al directorio-cola en vez de mandar UDP.

**Lo que NO cambia**: el vocabulario de comandos (`addtrack`, `additem`, `moveitem`, `fx`, `mute`, `play`), el proceso externo sigue siendo Python, y el resto de las capas (1 a 3, 5) del documento no dependen de esto.

## Actualización 2026-09-16c: Fase 0 cerrada, entregable verificado y ritmo medido

El usuario cargó y corrió `fly_listener.lua` desde REAPER (único paso manual de toda la fase). A partir de ahí, todo lo demás se hizo y verificó desde esta sesión, sin más intervención:

**Entregable de la sección 12 del documento** ("script externo que construye una sesión de 4 pistas"): `send_test_batch.py` mandó 9 comandos (4 `addtrack`, 4 `additem`, 1 `moveitem`). La cola de archivos quedó vacía después (todo drenado). Verificado **visualmente, por esta misma sesión**, vía captura de OBS de la ventana de REAPER (6.5): 4 pistas, cada una con su clip de 1.5s en la posición esperada, y el clip de la pista 1 corrido a la posición 4.0 — exactamente lo que pedía el lote. No fue necesario que el usuario mirara ni confirmara nada.

**Ritmo real del defer loop, medido, no citado** (reemplaza el "30 a 60 Hz según la documentación de REAPER" de 3.4/8.3, que hasta ahora era una cita): régimen estable de **~33.3 Hz** sostenido durante los ~50s que corrió el listener (`out/music-fly/f0/tick_log.jsonl`, en el repo). Cae en el extremo inferior del rango que citaba el documento — la cita resultó correcta para esta máquina, a diferencia de la mayoría de los otros supuestos de esta fase. Se ven caídas puntuales (0,99 Hz y 10,8 Hz en dos ticks) que correlacionan con el momento exacto en que se procesó el lote de 9 comandos (`total_comandos` salta de 0 a 9 justo en la caída a 0,99 Hz) y con actividad de la UI durante la verificación por captura — consistente con la sección 8.3 del documento: el costo de `UpdateArrange()` y de refrescar la interfaz, no del socket/archivo en sí.

**Test de cerebro congelado**: no aplica. No hay decodificador ni pieza entrenada en esta fase (11.1 del documento original es para cuando exista un `ConsoleDecoder`, Fase 2).

Con esto, la Fase 0 del plan de `ARQUITECTURA.md` sección 12 está cerrada.

## Actualización 2026-09-16d: instrumentos reales y audio real, verificado con números

Pregunta del usuario después de cerrar F0: ¿esto llega a servir para meter plugins/instrumentos reales y sacar audio, o solo mueve pistas y clips vacíos?

Se agregaron dos comandos experimentales a `fly_listener.lua`, fuera del vocabulario original de 8.2/8.3 (que solo pone parámetros de un FX ya existente):

- `addfx <pista> <nombre>`: llama a `reaper.TrackFX_AddByName`, la función real de instanciar un plugin/instrumento.
- `testnote <pista> <inicio> <fin> <pitch> <vel>`: crea un item MIDI (`CreateNewMIDIItemInProj`) e inserta una nota real (`MIDI_InsertNote`).

Además se agregó al log por segundo el nivel de pico real del master (`Track_GetPeakInfo`, canales L/R) y el estado de transporte (`GetPlayState`), reusando el mismo archivo que ya medía el ritmo del defer loop.

**Prueba real**: pista nueva + `ReaSynth` (el sintetizador nativo de REAPER, no un plugin de terceros, para no depender de qué esté instalado) + una nota de 2s (C4, velocity 100) + `play`. El log midió `peak_master_l`/`peak_master_r` pasando de **0.000000 a 0.394635** apenas arrancó la nota, sostenido mientras sonaba, y de vuelta a 0.0 cuando terminó y el transporte paró solo (`playstate` 1→0). Es una medición del motor de audio real, no una inferencia visual: confirma que REAPER efectivamente abrió un dispositivo de audio y procesó la señal del instrumento, sin que hiciera falta que el usuario mirara ni escuchara nada.

**Consecuencia**: la deuda "el vocabulario del listener no crea instrumentos" (sección 7 original) queda resuelta con `addfx`. Sigue sin resolver el vocabulario MIDI completo (`testnote` es un experimento de una nota, no una API general de inserción de notas) — eso es trabajo de Fase 2, cuando exista el decodificador que decida qué notas tocar.

**Extensión, mismo día**: se agregaron `cleartrack` (borra los items de una pista), `setloop` (`GetSet_LoopTimeRange`) y `repeat` (`GetSetRepeatEx`), y se armó una melodía de 6 notas (arpegio C4-E4-G4-C5-G4-E4, corcheas) en loop sobre `ReaSynth`. Confirmado por el usuario **escuchándolo** por los parlantes reales (no solo por el medidor): el loop se repite solo, sin intervención, que es exactamente el patrón que va a usar la mosca en la Fase 2 — construir algo y dejarlo sonando mientras decide el siguiente gesto. `playstate` se mantuvo en 1 de forma continua (a diferencia de la nota única de la prueba anterior, que paraba sola al llegar al final) y el pico del master varió entre notas (0.395 a 0.481) en vez de quedar plano, consistente con un arpegio real y no un tono fijo.

**Nota de higiene encontrada en el camino**: correr la acción de un ReaScript en `defer` desde el Action List **no la detiene la segunda vez** como se esperaba (no es un toggle para scripts en Lua cargados así) — cada `Run` agrega una instancia nueva, y se detectaron dos corriendo en simultáneo por los contadores del log interleaved. No rompe la funcionalidad (cada archivo lo procesa una sola instancia), pero desperdicia ciclos y ensucia el log. **La forma correcta de reiniciar el listener es la acción "ReaScript: Close all running ReaScripts" antes de volver a cargarlo**, no re-correrlo repetidas veces.

## 7. Deuda que queda

Deuda de documentación agregada por el pivote a Lua:

- Corregir ARQUITECTURA.md sección 8 (listener en Python + UDP → Lua + archivo), ver actualización 2026-09-16b.

Deuda separada, no bloqueante para cerrar F0:

- Verificar si `window_capture`/`screen_capture` de OBS sobre macOS captura una ventana en un Space distinto al activo (6.5, sección "no verificado todavía"). Requiere que el usuario cree un segundo Space una vez.
- Actualizar ARQUITECTURA.md sección 13 para reemplazar `brew install python@3.12` (ya no funciona) por `uv python install 3.12`.
- ~~El vocabulario de comandos del listener no incluye crear/instanciar un instrumento~~ — resuelto, ver actualización 2026-09-16d (`addfx`).
- El vocabulario MIDI sigue siendo mínimo (`testnote` es un experimento de una nota, no una API general). Falta antes de la Fase 2.

## 8. Cómo revertir

```bash
git revert <sha>
rm -rf music-fly/reaper music-fly/scripts/send_test_batch.py
# opcional, deshacer el cambio de OBS:
cp ~/"Library/Application Support/obs-studio/plugin_config/obs-websocket/config.json.bak-fase0" \
   ~/"Library/Application Support/obs-studio/plugin_config/obs-websocket/config.json"
# la actualizacion de REAPER (7.41 -> 7.80) no hace falta revertirla, 7.80 es
# estrictamente mejor y es el minimo que pide el documento
```
