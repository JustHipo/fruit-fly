# F2: cuerpo 3D y cinemática inversa

| | |
|---|---|
| Ticket | (sin clave, se trabaja standalone) |
| Proyecto | art-fly |
| Rama | `feat/f0-flybrain-fundacion` |
| Fase | F2 |
| Fecha | 2026-09-15 |
| Impacto | 🟡 aditivo |
| Estado | En progreso: IK resuelta, falta lienzo y contacto |

## 1. Qué se hizo

- Entorno `body` con Python 3.10 y `flybody` instalado desde GitHub.
- `artfly/body.py`: `LegIK`, que lleva la punta de una pata a una coordenada respetando los límites articulares.
- `scripts/probe_reach.py`: mide el área que alcanza una garra sobre un plano.
- `artfly` separado en extras `[brain]` y `[body]` para que el núcleo instale en los dos entornos.

## 2. Por qué

**`flybody` no está en PyPI.** `pip install flybody` falla. Hay que instalarlo desde el repositorio:

```bash
uv pip install "flybody @ git+https://github.com/TuragaLab/flybody.git"
```

La documentación de la sección 6.2 decía lo contrario y quedó corregida.

**El núcleo de `artfly` no depende ni de `flybrain` ni de `flybody`.** Los dos entornos no pueden convivir (flybody fija `numpy==1.26.4`, flybrain quiere 2.x), así que pluma, color, lienzo y render quedaron sin dependencias pesadas y se instalan en ambos. `artfly.body` se importa explícitamente y solo desde el entorno `body`.

## 3. Archivos tocados

| Archivo | Cambio |
|---|---|
| `art-fly/artfly/body.py` | Nuevo, `LegIK` |
| `art-fly/scripts/probe_reach.py` | Nuevo, mapa de alcance |
| `art-fly/pyproject.toml` | Extras `[brain]` y `[body]`, sin dependencias pesadas en el núcleo |
| `art-fly/artfly/__init__.py` | Deja de exportar `body` para no romper el entorno brain |

## 4. Validación

Modelo cargado en Apple Silicon con MuJoCo 3.13.0: 68 cuerpos, 103 articulaciones, 78 actuadores, 159 geoms, y las seis garras presentes.

**Mapa de alcance** de la pata delantera izquierda sobre el plano z=-0,127, grilla de 21x21 sobre un área de 0,20x0,20:

| Métrica | Valor |
|---|---|
| Alcanzables | 419 de 441 (95%) |
| Caja útil | x [-0,008, 0,192], y [-0,012, 0,188] |
| Error mediano | 0,00044 |
| Pasadas de IK promedio | 2,9 |
| Necesitaron recorte articular | 28% |

La zona inalcanzable es una esquina, la más lejana al punto de anclaje de la pata, que es exactamente lo que se espera de una extremidad real. Sirve de chequeo de cordura.

**Consecuencia de diseño**: el área alcanzable es tan grande como la mosca, así que **el lienzo móvil de 6.4 probablemente no haga falta**. Un lienzo fijo de 0,20x0,20 alcanza.

## 5. Controles corridos

No aplica en esta etapa. Los controles se corren sobre la obra, y todavía no hay pintura desde el cuerpo.

## 6. Problemas encontrados

### El `err_norm` del solver no es reproducible (importante)

`qpos_from_site_xpos` reporta un error de **0,000103** mientras que aplicar el `qpos` que devuelve deja la garra a **0,006283** del objetivo. Sesenta veces peor. Aparentemente mide en un espacio intermedio propio.

Confiar en ese número habría dado una garra que aterriza un 2% del largo del cuerpo fuera del objetivo, **en silencio**. Es justo el tipo de error que no se nota hasta que la obra sale mal, y que después es carísimo de rastrear.

Una primera medición del alcance usando `err_norm` dio 89% de cobertura; medido de verdad y sin iterar, la cobertura real era del 0%.

**Solución**: iterar con arranque caliente (`inplace=True`, que deja la solución en el physics) y cortar por el error **medido**. Cuatro pasadas de 300 llevan el error real de 0,0063 a 0,00007, y resultan más rápidas que una sola pasada de 3.000.

### El solver no impone límites articulares

En objetivos lejanos devuelve poses que los violan, por ejemplo la tibia a 1,311 con límite en 1,300. Se recorta después de cada pasada, y como el recorte ocurre entre pasadas, la siguiente reconverge dentro de los límites.

### El flag `success` es engañoso

Solo indica si el solver convergió antes de agotar `max_steps`, no si llegó al objetivo. Devuelve `False` incluso con error de 1e-12. No se usa.

## 7. Deuda que queda

- Falta el lienzo como geom, la detección de contacto y la deposición de pintura.
- Falta anclar la mosca: el modelo tiene una articulación `free` de 6 grados de libertad que hay que soldar para la preparación tethered.
- Falta medir la presión desde la fuerza de contacto.
- No se probó si las seis patas juntas amplían el área útil.

## 8. Cómo revertir

```bash
git revert <sha>
rm -rf art-fly/artfly/body.py art-fly/scripts/probe_reach.py .venv-body
```

---

## Actualización 2026-09-15: escena tethered, lienzo físico, y primer video real

### 1. Qué se agregó

- `artfly/scene.py`: `build_tethered_scene()` (suelda el `freejoint` del tórax y agrega el lienzo como geom físico real), `read_contacts()` (contacto garra-lienzo leído de `physics.data.contact`, no aproximado), `canvas_to_unit()`.
- `scripts/paint_3d.py`: pipeline completo. Consume una traza grabada en el entorno brain, decodifica objetivos de alcance para la pata T1_left, resuelve IK, verifica contacto real, y deposita pintura solo cuando el contacto ocurrió de verdad. Renderiza frames de video.

### 2. Anclar la mosca (tethered)

Se elimina el `<freejoint name="free"/>` del body `thorax` con la API de `dm_control.mjcf` (nunca se edita el XML de flybody instalado: se carga con `mjcf.from_path()`, se modifica el árbol en memoria, y se construye la física desde ahí). Verificado: nq baja de 109 a 102, el tórax queda fijo en el origen, y la IK converge igual que antes (3 pasadas, error 0,0003).

### 3. El hallazgo grande: la fuerza de contacto no es confiable con esta IK, y por qué

Se intentó que la "presión" saliera de la fuerza de contacto medida, como proponía la sección 6.4 original. No se logró de forma confiable, y vale la pena documentar el porqué en detalle porque es una limitación real, no un bug de implementación.

**Primero, el lugar del lienzo tuvo que medirse por búsqueda binaria sobre la física, no a mano.** El intento inicial ubicó el lienzo usando la posición del `site` que usa la IK, y dio contacto espurio de las seis patas en reposo. La causa: el geom de colisión real de la garra (una cápsula) cuelga varios milímetros por debajo del `site`, así que la posición que la IK apunta y la posición donde la física realmente choca son distintas. Es el mismo tipo de error que el `err_norm` no reproducible documentado más arriba: confiar en un valor por conveniencia en vez de medir el lugar correcto. Se resolvió con búsqueda binaria: `z = -0,1358` da cero contactos en reposo, verificado.

**Segundo, y más profundo: la pata tiene 8 articulaciones actuadas para un objetivo de 3 coordenadas.** Es un problema de cinemática inversa redundante. Se midió el barrido de profundidad de objetivo cada 1 mm, y el resultado no es monótono:

| z objetivo | distancia de contacto | fuerza |
|---|---|---|
| -0,134 | -0,00106 (penetra) | 13,1 |
| -0,136 | +0,00082 (separado) | 0,0 |
| -0,138 | -0,00005 (roza) | 0,0 |
| -0,140 | -0,00198 (penetra mas) | 0,0 |
| -0,141 | -0,00264 (penetra aun mas) | 18,8 |
| -0,145 en adelante | sin contacto en absoluto | 0,0 |

Objetivos a un milímetro de distancia llevan a **posturas de pata cualitativamente distintas**: algunas tocan el lienzo, otras lo esquivan por completo, y entre las que tocan, la fuerza no crece con la profundidad pedida. Se probó adem��s:

- **Asentar dinámicamente con actuadores de posición** (en vez de teletransportar el `qpos`): la pata a veces terminó con fuerzas de 15.000 (inestable) y otras veces ni siquiera llegó a tocar.
- **Aumentar `reg_strength`** del solver (regularización hacia la postura de partida): no ayudó, y con valores altos ni converge al objetivo.

**Conclusión, y la decisión que se tomó**: resolver esto de verdad requeriría un controlador de impedancia diseñado para esta tarea de contacto, que es un proyecto de control en sí mismo y queda fuera del alcance de esta sesión. Se documenta como limitación abierta, no se fuerza una solución frágil.

### 4. La decisión de diseño para seguir sin ese control resuelto

**El contacto booleano es completamente confiable** (verificado: cero falsos positivos en reposo, detecta correctamente qué pata toca). Lo que no es confiable es la *magnitud* de la fuerza.

Entonces, para esta versión de F2:

- **La pintura se deposita solo cuando hay contacto físico real**, verificado por `read_contacts()`, nunca por la posición del objetivo decodificado ni por un umbral de profundidad asumido.
- **La "presión" (qué tanto se decodifica que hay que presionar) sale de una profundidad decodificada más allá de la superficie real del lienzo** (`MAX_PRESS_DEPTH = 0,006`), no de un canal de opacidad arbitrario como en F1. Es un paso intermedio, más anclado a la física que F1 (el lienzo es un objeto real con una posición real) pero todavía no es fuerza dinámica medida.
- La tabla de lo autoral de ARQUITECTURA.md 10.3 se actualiza para reflejar exactamente este estado intermedio.

### 5. Validación

Corrida de 200 frames sobre una traza real de F1, una sola pata (T1_left):

| Métrica | Valor |
|---|---|
| IK convergió | 200/200 (100%) |
| Pluma abajo (decodificado) | 105/200 (52%) |
| Contacto real logrado, de los intentos | 73/105 (70%) |
| Tinta depositada | 16.593 |

**El 30% de los intentos de pintar no lograron contacto real**, que es la manifestación directa de la redundancia de IK de la sección 3. Es información honesta: casi un tercio de la "intención de pintar" del cerebro no se traduce en marca física, exactamente como pasaría con una pata real intentando alcanzar un punto impreciso.

Primer video generado: mosca de `flybody` fija en el aire, lienzo blanco real debajo, seis patas visibles. Primera vez que el proyecto produce una imagen del cuerpo, no solo del lienzo resultante.

### 6. Deuda que queda, actualizada

- **Fuerza de contacto dinámica**: no resuelta, requiere un controlador de impedancia. Es el ítem más grande pendiente de F2.
- Solo una pata (T1_left). Falta decidir cómo coordinar seis patas sin que la redundancia de cada una multiplique el problema de la sección 3.
- La deposición es puntual por frame, sin interpolación en sub-pasos como F1: por eso el lienzo 3D sale con manchas dispersas en vez de trazos continuos. Se puede resolver interpolando entre posiciones de contacto consecutivas, igual que F1.
- Sin lienzo móvil todavía (sigue pareciendo innecesario dado el alcance medido, pero no se descartó formalmente).

---

## Actualización 2026-09-15b: el primer video no tenía duración

El video enviado en la actualización anterior tenía **1 solo frame codificado, 0,08 segundos**, aunque `frames/` tenía 67 PNGs en disco.

**Causa**: `paint_3d.py` nombraba los archivos con el índice `i` del frame de la traza, muestreado cada `len(frames)//60` (paso de 3 en una corrida de 200). Los nombres quedaban `00000.png, 00003.png, 00006.png, ...`, con huecos. El comando de armado usaba `ffmpeg -i frames/%05d.png`, que asume numeración secuencial sin huecos: al no encontrar `00001.png`, ffmpeg corta ahí y codifica solo el primer frame.

**Arreglo**: contador de nombre de archivo separado del índice de frame de la traza, siempre secuencial. El script ahora imprime el comando de ffmpeg correcto al terminar.

**Lección**: cuando se muestrea a intervalos para el video, el nombre de archivo no puede heredar el índice del muestreo. Es un error de un solo caracter de diferencia (`i` en vez de un contador propio) con un síntoma que no se ve hasta que se intenta reproducir el video.

---

## Actualización 2026-09-15c: el alcance de T1 no representa a las otras patas

Antes de coordinar seis patas, se midió si el radio de alcance usado para T1_left (0,08) vale también para patas medias y traseras, que son anatómicamente distintas.

Sondeo con `probe_reach.py`, grilla 11x11 sobre 0,20x0,20, mismo plano z=-0,127:

| Pata | Alcanzables | Recorte articular necesario |
|---|---|---|
| T1_left (delantera) | 95% (grilla 21x21) | 28% |
| T2_left (media) | 53% | 84% |
| T3_left (trasera) | 64% | 67% |

**Las patas medias y traseras alcanzan bastante menos, y necesitan recortar límites articulares mucho más seguido.** Usar el mismo `reach_radius=0,08` para las seis patas sería incorrecto: para T2 y T3 buena parte de esos objetivos caerían fuera de lo alcanzable o forzarían posturas en el límite articular, justo la zona donde ya se sabe que la IK es menos confiable (sección 3).

**Consecuencia para la coordinación de seis patas**: cada pata necesita su propio `reach_radius`, calibrado con su propio sondeo, no un valor único copiado de T1. Pendiente: sondear T1_right, T2_right, T3_right (por simetría deberían parecerse a sus contrapartes izquierdas, pero no se verificó) y fijar un radio conservador por pata antes de implementar la selección entre las seis.

---

## Actualización 2026-09-15d: coordinación de seis patas, y dos hallazgos grandes

### 1. Diseño de selección discreta de pata

`artfly/legs.py`: `LegSelector` mapea actividad neuronal a **cuál de las seis patas está activa este frame**, vía softmax + argmax sobre 6 logits. A diferencia del color (F1, `color.py`), donde argmax sería el mismo error que un hash porque el matiz es continuo por naturaleza, **elegir pata es legítimamente discreto**: una mosca real mueve una pata a la vez para alcanzar un punto, no mezcla continuamente fracciones de patas distintas.

`paint_3d.py` interpola en sub-pasos (`SUBSTEPS=4`) mientras la **misma** pata sigue activa entre frames consecutivos, igual que el lienzo 2D. Cuando el cerebro cambia de pata, no hay interpolación: sería una línea sin sentido físico, la tinta no puede saltar sola de una pata a otra. Un cambio de pata es un paso discreto.

### 2. Hallazgo grave: el lienzo era demasiado chico para cinco de las seis patas

Primera corrida con seis patas: **contacto real cayó a 19-20%**, contra el 70% medido con una sola pata en la actualización anterior. Desglosado por pata:

| Pata | Contacto |
|---|---|
| T1_left | 32% |
| T1_right | 48% |
| T2_left, T2_right, T3_left, T3_right | **0%** |

Cuatro de las seis patas nunca lograron contacto, ni una vez, en ningún frame.

**Causa raíz**: el lienzo (`DEFAULT_CANVAS_SIZE=0.11`, medio-lado) se había dimensionado pensando solo en T1. Las patas medias y traseras **descansan fuera de esa huella por completo**: T2 en y≈0,168 (el lienzo llega hasta 0,11), T3 en x≈-0,185 (el lienzo llega hasta -0,11). No importa qué tan profundo decodifique presionar el cerebro: si el objetivo x,y cae fuera del rectángulo del lienzo, la garra nunca lo va a tocar. Es geometría, no una falla de la IK ni del control.

Se calculó la huella real necesaria (reposo ± radio de alcance de cada pata):

```
x: [-0.246, 0.172]   y: [-0.218, 0.218]
```

Un cuadrado centrado en el origen necesita medio-lado **0,246** como mínimo. Se fijó `DEFAULT_CANVAS_SIZE = 0,26`.

### 3. Hallazgo confirmatorio: el desfase site-a-geom depende de la postura, no es una constante

Al agrandar el lienzo hubo que recalibrar `DEFAULT_CANVAS_Z` desde cero (no solo trasladar el valor viejo), porque el rango donde aparece contacto cambió por completo: con el lienzo chico el contacto aparecía en z ≈ -0,130 a -0,120; con el lienzo grande, en el mismo rango pero ahora afectando a las **seis** patas a la vez, confirmando que el hallazgo de la actualización 2026-09-15c (el geom de colisión cuelga distinto según la postura) es real y consistente entre patas cuando se mide en la zona correcta.

Además, un test más fino reveló que **incluso T1**, ya validada individualmente, fallaba contacto en 2 de 9 puntos de prueba (las esquinas más lejanas de su propio radio) con una profundidad fija de presión. Se reemplazó la profundidad fija por `LegIK.press()`: en vez de asumir una profundidad que funciona en todos lados, **prueba profundidades crecientes y verifica contacto real después de cada una**, deteniéndose en la primera que funciona. Es el mismo principio que ya aparece dos veces en este documento (el `err_norm` no reproducible, el desfase site-a-geom): nunca asumir un valor fijo donde se puede medir directamente.

### 4. Resultado tras los dos arreglos

| | Antes | Después |
|---|---|---|
| Contacto real (300 frames, seis patas) | 19% | **98%** |
| Patas con 0% de contacto | 4 de 6 | 0 de 6 |
| Tinta depositada | 4.898 | 78.730 |

Uso de cada pata sobre 300 frames: T1_left 20%, T1_right 32%, T2_left 13%, T2_right 12%, T3_left 11%, T3_right 12%. Razonablemente parejo, con cierta preferencia por T1 (que tiene el radio de alcance más grande, 0,08 contra 0,05-0,06 de las demás).

El lienzo resultante ya muestra grupos de trazos separados espacialmente, correspondientes a las distintas patas trabajando en sus propias regiones, no todo amontonado como con una sola pata.

## Deuda actualizada

- `LegIK.press()` prueba profundidades en pasos fijos (`depth_steps=4`); no se optimizó cuántos pasos hacen falta ni el costo de cómputo extra por frame.
- El radio de alcance por pata (`REACH_RADIUS`) sigue siendo una estimación conservadora a mano, no una optimización real del área utilizable.
- Fuerza de contacto dinámica: sigue sin resolver, igual que antes.

---

## Actualización 2026-09-15e: la pintura ahora aparece sobre la superficie física

Hasta esta actualización, `paint_3d.py` mantenía dos lienzos separados: uno físico (la placa blanca en la escena de MuJoCo, sin marcar) y uno abstracto (`Canvas` de F1, guardado aparte como PNG). El video mostraba la mosca sobre una placa blanca sin ningún rastro visible de que estuviera pintando, aunque la pintura sí se registraba correctamente en el archivo aparte.

**Arreglo**: el geom `canvas_surface` ahora lleva una textura editable (`canvas_texture`, `scene.py`). Cada contacto real deposita un toque gaussiano directamente en esa textura (`paint_on_texture`), que se sube a GPU con `mujoco.mjr_uploadTexture` antes de cada frame de render. Lo que se ve en el video o en el viewer en vivo **es** el resultado, no una reconstrucción aparte.

**Problema encontrado en el camino**: declarar el material con `texuniform="true"` hace que MuJoCo repita la textura según escala física en metros, no que la mapee una vez a la cara del geom. Con el lienzo a 0,52 m de lado, eso significaba que un parche pintado en el medio de la textura podía terminar mapeado a una región invisible o repetida de forma irreconocible. Se sacó `texuniform` (queda el mapeo por defecto, una vez por cara) y un cuadrado de prueba apareció exactamente donde se esperaba.

**Cómo se depuró**: primero se pintó la textura entera de un color para confirmar que la subida a GPU funcionaba (sí), después un cuadrado pequeño en el medio (invisible, con `texuniform`), lo que aisló el problema al mapeo UV y no a la subida en sí.

---

## Actualización 2026-09-15f: viewer en vivo, limitación real del entorno

`scripts/live_view.py`: reproduce una traza grabada en una ventana interactiva de MuJoCo (`mujoco.viewer.launch_passive`), con la mosca moviendo las seis patas y la pintura apareciendo sobre la superficie real (misma lógica que `paint_3d.py`, factorizada en `build_pipeline()` para que ambos scripts compartan exactamente el mismo comportamiento).

**Limitación encontrada, no un bug propio**: esta sesión de Claude Code corre en un proceso sin acceso a la sesión gráfica de macOS (WindowServer), así que no puede abrir la ventana por sí misma. Se probaron dos mecanismos de backgrounding distintos (`&` de shell, y el mecanismo nativo de background de la herramienta), ambos con el mismo error (`NSWindow should only be instantiated on the main thread`), lo que descarta un problema de threading del lado del script y confirma que es una restricción del entorno donde corre el agente, no del código.

**Lo que sí queda validado**: la lógica de simulación, selección de pata, IK, contacto y pintura es literalmente la misma función (`build_pipeline`/`step`) que ya corrió exitosamente en `paint_3d.py` (98% de contacto real, seis patas, pintura visible). Lo único no verificado directamente por el agente es la ventana interactiva en sí (orbitar, zoom), que requiere que el usuario la corra desde su propia terminal.

Instrucciones en `scripts/README_LIVE.md`.

---

## Actualización 2026-09-15g: por qué el viewer en vivo crasheaba, y cómo se resolvió de verdad

La actualización anterior atribuyó el crash a una limitación del entorno del agente (sin sesión gráfica). **Eso era falso.** El usuario corrió el mismo comando desde su propia terminal, con sesión gráfica real, y obtuvo el mismo crash exacto. Eso descartó la hipótesis del sandbox y forzó a investigar la causa real.

### Dos causas independientes, ambas confirmadas por experimento

**Causa 1: `mjpython` instalado en un entorno creado con `uv venv` está roto.**

Se aisló con un experimento mínimo: el mismo modelo de juguete (una esfera), con `mujoco.viewer.launch_passive`, corrido primero desde `.venv-body` (creado con `uv venv`, crashea) y después desde un venv nuevo creado con `python3.10 -m venv` (funciona perfecto). Es un bug conocido y activo: [`mjpython` bug when installed with `uv` package manager, issue #1923](https://github.com/google-deepmind/mujoco/issues/1923). La causa de fondo (según los reportes del issue) es que el script trampolín de `mjpython` calcula rutas de bibliotecas dinámicas relativas al ejecutable de Python del venv, y la forma en que `uv` arma esos symlinks no coincide con lo que ese cálculo espera.

**Arreglo**: se recreó `.venv-body` con `python3.10 -m venv` en vez de `uv venv`, y se reinstalaron `flybody` y `art-fly` ahí. Confirmado con el mismo experimento mínimo: viewer abre, corre, cierra sin crash.

**Causa 2: `physics.render()` de dm_control y `mujoco.viewer.launch_passive` no pueden coexistir en el mismo proceso, en ningún orden.**

Incluso con el venv arreglado, el pipeline completo seguía crasheando. Se aisló con una serie de experimentos progresivos: el viewer solo (funciona), el viewer con `flybody`/`dm_control` importados pero sin construir la escena real (funciona), la escena real sin ningún render previo (funciona), y finalmente la escena real con una llamada a `physics.render()` antes de abrir el viewer (crashea) **y** con la llamada después de abrir el viewer (crashea igual). Ambos órdenes fallan, lo que descarta que sea un problema de secuencia y confirma que es la mera coexistencia de los dos sistemas de ventana/contexto (el de dm_control, vía su propio GLFW, y el del viewer nativo de MuJoCo) lo que rompe algo a nivel de hilo de Cocoa.

**Arreglo**: para el viewer en vivo, nunca se llama a `physics.render()` ni se usa el contexto de dm_control (`physics.contexts.mujoco`). En su lugar se usa el método público `viewer.update_texture(tex_id)` del propio objeto `Handle` que devuelve `launch_passive`, que sube la textura a través del contexto que el viewer ya tiene correctamente anclado al hilo principal real. `build_pipeline()` ahora acepta `create_render_context=False` para saltarse por completo la creación del contexto de dm_control cuando se usa desde el viewer en vivo.

### Verificación final

Pipeline completo (seis patas, decodificador, selector, `LegIK.press()`) corrido dentro de la ventana interactiva real: 150 pasos, 69 con contacto real, sin crash, cerrado limpio.

### Controles agregados (pedido del usuario tras probarlo)

La primera versión solo reproducía hacia adelante en loop, sin pausa ni forma de volver atrás. Se agregó una clase `Player` con:

- **Pausa/reanudar** (espacio).
- **Paso adelante** (flecha derecha), funciona en pausa.
- **Retroceder de verdad** (flecha izquierda): restaura tanto la postura física (`qpos`) como la textura pintada desde una instantánea guardada, no solo mueve un índice. Verificado: retroceder y volver a avanzar los mismos pasos da un estado idéntico al original (el pipeline es determinista dado `z`), confirmando que el historial funciona correctamente.
- **Reinicio** (`r`): `physics.reset()` más textura vuelta al fondo, en el lugar, sin reconstruir la escena.

Las excepciones dentro del loop ahora se imprimen con traceback completo antes de dejar que la ventana se cierre, para que un cierre inesperado nunca vuelva a pasar en silencio.

---

## Actualización 2026-09-15h: las flechas colgaban la ventana

Al usar las flechas, la ventana se quedaba pegada. Causa: `key_callback` corre en el hilo de la interfaz gráfica, que `mjpython` separa a propósito del hilo donde vive el loop principal. La primera versión hacía el trabajo pesado (`step_forward`/`step_backward`, que implica varios intentos de cinemática inversa vía `LegIK.press()`) **directamente dentro del callback**, bloqueando la interfaz gráfica entera mientras calculaba.

Medido: el callback en sí tarda 0,01 ms; el paso real (`step_forward`) tarda ~53 ms. Esos 53 ms corrían sobre el hilo de la UI, y con varias flechas seguidas se acumulaban, sintiéndose como que el programa se colgó.

**Arreglo**, siguiendo el patrón recomendado por MuJoCo para `launch_passive`: el callback de teclado ahora **solo deja una intención liviana** (`player.pending = "forward"/"backward"/"reset"`), y el loop principal la ejecuta en su propio hilo, en su propio turno. El callback nunca vuelve a tocar `physics.data` directamente, lo que además elimina cualquier condición de carrera entre el hilo de la interfaz y el hilo que efectivamente mueve la física.

---

## Actualización 2026-09-15i: exportar el arte a PNG, y verificación del loop completo

Se agregó la tecla `s`: exporta la textura del lienzo (no el render 3D completo, que no es capturable desde el viewer en vivo por la misma incompatibilidad de contextos de la actualización anterior) a `out/f2/live_capture_<fecha>.png`, escalada a 1024x1024. Es una operación barata (solo lee el array de la textura ya en memoria), así que no hace falta el mecanismo de `pending` por rendimiento, pero se lo dejó ahí igual por consistencia con el resto de los controles.

Se verificó además, ante un reporte de crash del usuario que no se pudo reproducir con el traceback completo: correr el loop completo de una traza de 1200 frames más 20 de margen (para pasar el punto donde vuelve a 0) no produce ninguna excepción. Si el crash reportado vuelve a ocurrir, hace falta el traceback impreso en la terminal (ya se imprime completo antes de cerrar la ventana) para diagnosticarlo puntualmente en vez de suponer.
