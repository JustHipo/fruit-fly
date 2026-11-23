# Estado del proyecto

Última actualización: 2026-09-16

## Resumen en una línea

Dos proyectos sobre el conectoma real de *Drosophila* (MaleCNS v1.0). El simulador de cerebro funciona y está validado contra controles; el de pintura ya genera obra; el del DAW tiene la Fase 0 cerrada (puente REAPER verificado de punta a punta, ~33 Hz medido).

## Qué funciona hoy

| Componente | Estado | Dónde |
|---|---|---|
| Carga del conectoma MaleCNS | ✅ | `packages/flybrain/flybrain/data.py` |
| Simulador LIF (161.429 neuronas) | ✅ | `packages/flybrain/flybrain/lif.py` |
| Poblaciones por superclase | ✅ | `packages/flybrain/flybrain/populations.py` |
| Calibración y z-scores | ✅ | `packages/flybrain/flybrain/calibration.py` |
| Formato de traza | ✅ | `packages/flybrain/flybrain/trace.py` |
| Controles de topología | ✅ | `packages/flybrain/flybrain/controls.py` |
| Decodificador de pluma | ✅ | `art-fly/artfly/pen.py` |
| Color derivado del cerebro | ✅ | `art-fly/artfly/color.py` |
| Render continuo | ✅ | `art-fly/artfly/canvas.py` |
| Render pixel art | ✅ | `art-fly/artfly/pixel.py` |
| Cuerpo 3D, patas, física (seis patas) | ✅ | `art-fly/artfly/body.py`, `scene.py`, `legs.py` |
| Coreografía de seis patas | ✅ | Selección discreta por `LegSelector`, contacto real 98% |
| Fuerza de contacto dinámica | ⬜ | F2, limitación documentada, requiere controlador de impedancia |
| Guía por concepto con CLIP | ⬜ | F3, sin empezar |
| music-fly: F0, puente REAPER | ✅ | `music-fly/reaper/fly_listener.lua`, `music-fly/scripts/send_test_batch.py`, ~33 Hz medido, instrumentos reales (`addfx`) y audio real verificados |
| music-fly: F1, subgrafo motor en vivo | ✅ | 4.491 neuronas, ~40Hz medido, 0 pasos salteados en 15s, tasas de reposo 1,7-5,4 Hz por población (calibrado, `weight_scale=100`). `music-fly/scripts/run_motor_subgraph.py` |
| music-fly: F2, consola (primera versión) | 🔄 | El cerebro real compone, pasó el test de cerebro congelado, y ahora con cuerpo físico real (contacto verificado, ~98% en línea con art-fly) y visor 3D. Falta que el usuario confirme el visor en vivo. `music-fly/console/`, `music-fly/scripts/compose_with_body.py`, `live_view_console.py` |
| music-fly: lazo cerrado | ⬜ | F3, sin empezar |

## Números medidos

| Métrica | Valor |
|---|---|
| Neuronas | 161.429 |
| Aristas con signo no nulo | 14.262.680 |
| Velocidad, CPU | 106,5 pasos/s (0,107x tiempo real) |
| Velocidad, MPS | 104,7 pasos/s |
| `weight_scale` calibrado | 65 |
| Tasa media de disparo | 3,3 Hz |
| Correlación real contra nulo | 0,21 |
| Alcance T1 (delantera) | 95% de 0,20x0,20 |
| Alcance T2 (media) | 53% de 0,20x0,20, 84% necesita recorte articular |
| Alcance T3 (trasera) | 64% de 0,20x0,20, 67% necesita recorte articular |
| Contacto real logrado (seis patas, 300 frames) | 98% de los intentos de pintar |

## Resultados

**El cableado medido importa, y se puede medir cuánto.** Los tres controles de topología producen actividad claramente distinta de la del conectoma real, cada uno fallando de un modo distinto:

| control | efecto |
|---|---|
| `shuffle_weights` | Explota a 17-22 Hz: los pesos medidos sostienen el balance excitación/inhibición |
| `erdos_renyi` | Aplana todo a 3,2 Hz uniforme: la heterogeneidad viene del cableado específico |
| `degree_preserving` | Queda en el medio |

Sobre la obra, la separación se mantiene: el conectoma real ocupa todo el lienzo y los controles se hunden contra el borde inferior. La métrica que lo explica es el rango dinámico de los z-scores, 2,22 en el real contra 1,01-1,26 en los controles.

## Comandos

```bash
# entorno brain (Python 3.12): cerebro, decodificador 2D
source .venv-brain/bin/activate

# grabar una traza de actividad
python packages/flybrain/scripts/record_trace.py --seconds 12 --sample-every 10

# pintar en 2D
python art-fly/scripts/paint.py --render continuo --color poblacion
python art-fly/scripts/paint.py --render pixel --color poblacion --cells 64

# comparar contra los tres controles (repinta sin resimular con --reuse-traces)
python art-fly/scripts/compare_controls.py --render pixel --reuse-traces

# diagnosticos del cerebro
python packages/flybrain/scripts/calibrate_scale.py
python packages/flybrain/scripts/run_controls.py

# ---

# entorno body (Python 3.10): cuerpo 3D, IK, contacto real
source .venv-body/bin/activate

# mapa de alcance de una pata
python art-fly/scripts/probe_reach.py --leg T1_left --grid 21 --span 0.20

# pintar en 3D desde una traza ya grabada (frontera entre entornos: el archivo)
python art-fly/scripts/paint_3d.py --trace out/f1/trace_real.json --frames 200
```

## Deuda abierta

| Deuda | Gravedad | Detalle |
|---|---|---|
| Sin validar contra `philshiu` | Media | `weight_scale=65` está calibrado contra el nulo, no contra registros biológicos |
| El decodificador no está entrenado | Baja | Pesos aleatorios con semilla fija. Es F3 |
| Ranuras de matiz autorales | Baja | Qué población ocupa qué color es una rotación elegida a mano |
| Fuerza de contacto no confiable | Media-alta | IK redundante (8 DOF para 3 coordenadas) da posturas discontinuas. Requiere controlador de impedancia, fuera de alcance actual |
| Fuerza de contacto dinámica sigue sin resolver | Media-alta | Requiere controlador de impedancia, fuera de alcance actual |
| Disco justo | Media | 15 GB libres; CLIP necesita más |
| Jira sin conectar | Ninguna | Diferido a propósito, se trabaja standalone |
| Vocabulario MIDI mínimo | Baja | `testnote` es un experimento de una nota; falta una API general antes de la Fase 2 |
| ARQUITECTURA.md secciones 8 y 13 desactualizadas | Baja | Documentan Python+UDP (8) y `brew install python@3.12` (13); la implementación real es Lua+archivo y `uv python install 3.12`. Detalle en `music-fly/docs/migraciones/F0-puente-reaper.md` |
| Ventana capturable en un Space inactivo, sin confirmar | Baja | Depende de si `window_capture` de OBS sobrevive a cambiar de Space; falta la prueba real |

## Decisiones tomadas

| Fecha | Decisión | Motivo |
|---|---|---|
| 2026-09-14 | MaleCNS, no FlyWire | Incluye cordón nervioso ventral, o sea control de patas |
| 2026-09-14 | **La mosca no camina**, queda fija | Elimina el problema que nadie resolvió; es la preparación tethered estándar |
| 2026-09-14 | Dos entornos Python separados | flybody fija numpy 1.26.4, el resto quiere 2.x |
| 2026-09-14 | Política de signo `strict` | La histamina es inhibitoria en Drosophila; el dataset le pone +1 |
| 2026-09-14 | REAPER sobre Ableton en music-fly | Ableton no soporta macOS 26 |
| 2026-09-14 | Correr el cerebro en CPU | MPS no aporta; deja la GPU libre para CLIP |
| 2026-09-14 | Color derivado del cerebro | Era la parte más autoral del proyecto |
| 2026-09-15 | flybody se instala desde GitHub, no PyPI | La documentación original estaba mal |
| 2026-09-15 | Presión sale de profundidad decodificada, no de fuerza medida | La fuerza de contacto no es confiable con esta IK redundante; ver lecciones aprendidas |
| 2026-09-15 | Contacto siempre booleano y medido, nunca asumido | Es lo único confiable; la pintura 3D depende de él |
| 2026-09-16 | REAPER actualizado 7.41.0 → 7.80 | El documento exige 7.74+; lo instalado estaba por debajo |
| 2026-09-16 | Python de ReaScript sale de `uv python install 3.12`, no de Homebrew | La fórmula `python@3.12` de Homebrew ya no existe; uv da un build arm64 shared reproducible sin depender de qué versiones mantenga Homebrew |
| 2026-09-16 | OBS + `obs-websocket` como método de captura de pantalla para esta sesión | Esta sesión no tiene permiso de Accessibility ni Screen Recording propios; OBS sí los tiene y su API remota no los requiere del lado de quien la llama |
| 2026-09-16 | No se suma un servidor MCP de terceros para OBS | Existen varios, pero para control programático desde el propio pipeline alcanza con hablarle al websocket directo (`obsws-python`), misma lógica que ya descartó `reapy` para REAPER |
| 2026-09-16 | El listener dentro de REAPER pasa de Python a Lua, UDP pasa a archivo con rename atómico | `RPR_defer` no existe en la API de Python de REAPER (verificado, 810 nombres volcados, ninguno es defer/atexit/runloop); los ReaScripts de Python bloquean la UI y no pueden persistir. Lua sí tiene `reaper.defer()` real pero no trae sockets de fábrica |
| 2026-09-16 | OBS captura audio+video de REAPER por aplicación (ScreenCaptureKit), no por dispositivo virtual (BlackHole/Loopback) | Cero software nuevo, sincronía automática, no cambia lo que se escucha en vivo. Verificado con una grabación real (-19.5dB, no silencio) |
| 2026-09-16 | Ninguna decisión de la consola (instrumento, patrón, perilla) se resuelve por menú/umbral; siempre por posición continua sobre una zona | Un menú por umbral es el mismo antipatrón del hash de `fruit-fly-fashion`; rompe la relación continua entre actividad y salida. Ver ARQUITECTURA.md 7.5 |

## Próximo paso

**Visualizar la consola en 3D**: hecho, `music-fly/scripts/live_view_console.py`. Verificado offscreen (15 cuadros, contacto real agrupado cerca de las zonas de color esperadas). Falta que el usuario la corra en vivo con `mjpython` (esta sesión no puede abrir la ventana directamente) y confirme que la leyenda se ve clara con la traza completa.

**Cerrar F2** (art-fly): coreografía de seis patas (sin multiplicar el problema de redundancia de IK), interpolación en sub-pasos para trazos continuos en 3D (hoy son manchas discretas por frame), y decidir si vale la pena un controlador de impedancia para fuerza de contacto real o si la profundidad decodificada es suficiente para el propósito artístico del proyecto.

**F0 y F1 de music-fly cerradas del todo**, incluidos los tres controles de topología: el subgrafo real se distingue claramente de sus versiones degradadas (correlación de tasas 0,449/0,488/-0,272, ninguna cerca de 1), y reprodujo de forma independiente un chequeo de cordura que art-fly ya había encontrado en el cerebro completo (poblaciones sensoriales iguales en real/shuffle/degree, saltan en erdos_renyi). El subgrafo motor (4.491 neuronas) corre en vivo, en tiempo real, a ~40Hz, sin saltear pasos, con tasas de reposo (1,7-5,4 Hz) en el mismo orden que el cerebro completo. F2 en progreso: el `ConsoleDecoder` y la asignación de las seis patas (7.6) ya están escritos, la traza real de F1 ya produjo una composición real, y el test de cerebro congelado ya se corrió (autocorrelación 0,43-0,49 en el real contra ~0 en los tres controles — el cerebro real aporta algo que ningún ruido puede replicar). Falta conectar el cuerpo físico (por ahora los objetivos decodificados se usan directo, sin IK ni contacto real), confirmar la diferencia al oído (no solo en el número), y la visualización 3D de la consola que pidió el usuario. También corregir ARQUITECTURA.md sección 13 (`brew install python@3.12`) según lo medido en F0.
