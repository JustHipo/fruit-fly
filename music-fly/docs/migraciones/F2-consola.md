# F2: la consola (primera versión)

| | |
|---|---|
| Ticket | (sin clave, se trabaja standalone) |
| Proyecto | music-fly |
| Rama | `feat/f0-flybrain-fundacion` |
| Fase | F2 |
| Fecha | 2026-09-16 |
| Impacto | 🟡 aditivo |
| Estado | En progreso: primera versión funcionando, sin cuerpo físico todavía |

## 1. Qué se hizo

Primera vez que actividad real del cerebro (la traza grabada en F1, subgrafo motor corriendo en tiempo real) le dice algo a REAPER, sin nota escrita a mano de por medio. Se diseñó (con el usuario, ver `ARQUITECTURA.md` 7.5/7.6) y se implementó el `ConsoleDecoder` y una capa de interpretación que arma una composición completa: pistas, instrumentos, tempo, compás y notas.

## 2. Por qué

Regla 0: se retomó directamente sobre `music-fly/docs/migraciones/F1-subgrafo-motor.md`, que ya dejaba la traza real grabada en `out/music-fly/f1/live_trace.json`.

**Decisión de diseño explícita**: ninguna elección (instrumento, patrón, compás) se resuelve por umbral/menú — todo es posición continua sobre una zona, igual que ya usaba 7.2 para las patas. Documentado en detalle en `ARQUITECTURA.md` 7.5 (el principio) y 7.6 (la asignación concreta de las seis patas), discutido y aprobado por el usuario antes de escribir código.

## 3. Archivos tocados

| Archivo | Cambio |
|---|---|
| `music-fly/console/decoder.py` | Nuevo. `ConsoleDecoder`: z (6 poblaciones) -> 6 `LegTarget` (x,y,press), sin estado, sin entrenar (semilla fija) |
| `music-fly/console/vocabulary.py` | Nuevo. Todo lo autoral: escala pentatónica, paleta de 2 instrumentos (ReaSynth grave/agudo), paleta de 4 compases, límite de notas por compás |
| `music-fly/scripts/compose_from_trace.py` | Nuevo. Interpreta la traza real, arma la composición, la manda a REAPER |
| `music-fly/reaper/fly_listener.lua` | Agrega comandos `tempo` y `dumpstate` (diagnóstico) |
| `music-fly/ARQUITECTURA.md` | Secciones 7.5 (zona continua, nunca menú) y 7.6 (asignación de patas) |

## 4. Validación

**Decodificación, contra la traza real de F1** (599 cuadros, 15s): T1L (gate de nota) activo en 317/599 cuadros, T1R (duración) en 265/599 — ninguno saturado ni apagado. El compás y el tempo variaron a lo largo de la traza (las 4 zonas de compás aparecieron, tempo entre 80,1 y 159,1 bpm) antes de fijarse una vez para toda la pieza.

**Resultado**: 22 notas decodificadas en 15s, repartidas 10/12 entre los dos instrumentos. Tempo elegido: 119,3 bpm. Compás elegido: 4/4.

**Verificado end-to-end contra REAPER real**: se mandó la composición completa (2 pistas nuevas + `ReaSynth` en cada una + tempo + 22 notas + play). El log del listener mostró los 28 comandos procesados (`total_comandos`). Confirmado con una captura de pantalla **real** del usuario (no vía OBS, ver sección 6): 7 pistas totales, las 2 nuevas con el indicador de FX en verde y bloques de nota reales (no "Empty Item"), tempo mostrado 119,31 — coincide exacto con lo calculado. El usuario confirmó haberlo escuchado sonar.

## 5. Controles corridos

No aplica todavía en el sentido de topología (eso ya se hizo en F1 sobre el subgrafo). No se corrió el test de cerebro congelado (11.1) porque para eso hace falta comparar contra `z` fijo en su media y contra ruido de igual varianza — queda como paso obligatorio antes de dar por buena esta pieza como "compuesta por el cerebro" en un sentido fuerte, ver deuda.

## 6. Problemas encontrados

### Las capturas de OBS mintieron durante la verificación, y casi se reporta un fallo que no existía

Cambiando el `window` target de la fuente de captura muy seguido (buscando cuál id correspondía a la ventana correcta de REAPER) las capturas devolvieron un cuadro **viejo, cacheado**, sin error. Por varios minutos parecía que la composición no había hecho nada (mismas 4 pistas de siempre, sin instrumentos nuevos), cuando en realidad sí había funcionado. Se resolvió cuando el usuario mandó una captura de pantalla real, que mostraba el estado correcto.

**Consecuencia metodológica, ya aplicada**: no confiar en una captura de OBS solo porque no dio error. Preferir datos que la propia app escriba a un archivo (`tick_log.jsonl`) antes que capturas visuales en ráfaga; documentado como lección transversal en `LECCIONES_APRENDIDAS.md`.

## Actualización 2026-09-16b: test de cerebro congelado, con un error metodológico propio corregido en el camino

A pedido del usuario ("¿esa melodía la hizo la mosca o vos?"), se corrió el test obligatorio de 11.1.

**Primera versión del test** (`test_frozen_brain.py`): comparó la composición real contra (a) cerebro congelado en su media y (b) ruido con la misma media/varianza por población. Congelada dio 0 notas (correcto, se distingue). Pero ruido dio una composición **casi idéntica** a la real en cantidad de notas, pitch promedio, velocity — señal de alarma real, documentada tal cual salió (Regla 6 del `REGLAMENTO.md`: los resultados negativos se publican).

**Hipótesis descartada, probada, no asumida**: se sospechó que `MAX_NOTES_PER_BAR=3` (un techo autoral fijo, cooldown entre notas) estaba ahogando cualquier diferencia. Se aflojó a `MIN_NOTE_GAP_STEPS=1` (un piso de un paso de grilla en vez de un techo por compás) y se volvió a correr: **el resultado no cambió** (50 notas reales contra 50 de ruido, gaps casi idénticos). La hipótesis era incorrecta.

**El error real estaba en la prueba, no en el diseño**: se agregó un control adicional, "BARAJADO" (los mismos valores reales de la traza, en otro orden) — dio resultados **igual de parecidos** a los de ruido puro. Esto expuso el problema: los promedios y conteos son invariantes al orden por definición matemática. Comparar promedios nunca iba a poder distinguir una secuencia real de la misma secuencia mezclada, sin importar qué tan bien o mal estuviera diseñado el decodificador.

**La prueba correcta** (`test_autocorrelation.py`): en vez de promedios, se midió la autocorrelación de un paso al siguiente de la señal continua decodificada (antes del gate/cooldown) — si el cerebro real tiene continuidad temporal (la tiene: el EMA del simulador tiene tau=25ms), un valor decodificado debería parecerse al del instante anterior, cosa que ningún ruido puede tener por construcción.

| Variante | Autocorr. T1L.x | Autocorr. T1L.y |
|---|---|---|
| Real | **0,490** | **0,427** |
| Ruido (poblaciones independientes) | 0,007 | -0,021 |
| Barajado (mismos valores, otro orden) | -0,061 | 0,009 |
| Ruido con covarianza real | -0,022 | 0,044 |

**Resultado**: el cerebro real tiene una continuidad temporal clara (~0,43-0,49) que ninguno de los tres controles reproduce, ni siquiera el que respeta la covarianza real entre poblaciones. Es una diferencia que ningún control estadístico puede replicar por construcción — el decodificador no está ignorando al cerebro.

**Lo que esto NO prueba todavía**: que esa continuidad se traduzca en algo musicalmente distinguible al oído. Comparar cómo suena de verdad una versión con ruido contra la real queda como deuda.

## Actualización 2026-09-16c: cuerpo físico real conectado, ya no hay atajo

Se reemplazó el uso directo de los valores decodificados por el cuerpo tethered real de art-fly: seis patas con `LegIK`, contacto leído de la física (`scene.read_contacts`), reusando sin cambios la escena, el lienzo-ahora-consola y los radios de alcance ya medidos en art-fly (F2-cuerpo-ik.md). Nuevo módulo `music-fly/console/body_compose.py` (entorno `body`, Python 3.10) y `music-fly/scripts/compose_with_body.py`.

**Diferencia de diseño respecto de art-fly**: allí una sola pata está activa por cuadro (`LegSelector`, discreto, porque pintar es un gesto de una pata a la vez). Acá las seis patas tienen un rol fijo simultáneo (7.6: nota, duración, instrumento, perillas, mute, compás/tempo), así que las seis se simulan físicamente cada cuadro — 6x más trabajo de IK por cuadro que art-fly.

**Resultado, medido, mismo formato que `paint_3d.py`**: 599 cuadros, 332,2s de reloj real (≈0,56 fps de física real — mucho más lento que tiempo real, esperado dado el costo de IK; es post-proceso offline sobre una traza ya grabada, no la performance en vivo). Contacto real logrado: T1L 316, T1R 243, T2L 271, T2R 285, T3L 301, T3R 302 — en el mismo orden que el 98% combinado de art-fly.

**Consecuencia sobre la composición**: con contacto físico real en vez de intención decodificada, la pieza salió con **45 notas** (contra 50 sin cuerpo físico) — algunos intentos de la consola no lograron contacto real y quedaron descartados, exactamente el comportamiento honesto esperado ("el contacto siempre se mide, nunca se asume", heredado de art-fly). Enviado a REAPER y confirmado sonando (`playstate=1`, picos de audio reales entre 0,10 y 0,30 variando en el tiempo).

**Deuda que abre esto**: el bucle no corre en tiempo real (0,56 fps de física contra los ~40Hz de la traza) — sirve para renderizar una pieza ya grabada, no para una performance en vivo con el cuerpo físico moviéndose junto al cerebro. Sería necesario perfilar o simplificar el IK de seis patas simultáneas para acercarse a tiempo real, si se quiere una performance en vivo con cuerpo. Por ahora, exactamente igual que art-fly F2, sirve para producir la pieza offline con contacto real verificado.

## Actualización 2026-09-16d: visualización 3D de la consola

Pedido del usuario de varias actualizaciones atrás, retomado ahora. `music-fly/scripts/live_view_console.py`, mismo patrón que `art-fly/scripts/live_view.py` (Player, key_callback liviano, `viewer.update_texture` en vez de `physics.render`, mismo motivo: no pueden coexistir en el mismo proceso en macOS).

**Qué dibuja**: la superficie física reusada de art-fly, con una leyenda pintada una sola vez al arrancar — zonas de color para las dos elecciones discretas de la consola (instrumento en T2 izquierda: azul/naranja; compás en T3 derecha: verde/violeta/amarillo/rojo) — y un punto blanco en cada cuadro donde una pata logró contacto real, así se ve en vivo dónde cae cada decisión respecto de la zona correspondiente.

**Verificado antes de entregarlo, sin poder abrir la ventana**: se corrió el mismo pipeline en modo offscreen (15 cuadros reales, `physics.render` en vez del viewer) y se guardaron dos PNG: el render 3D completo (la mosca tethered sobre la superficie, igual que en art-fly) y la textura de la consola vista desde arriba. Los puntos de contacto real aparecen agrupados cerca de las zonas de color esperadas, confirmando que el mecanismo funciona, aunque **no** confirma que la distribución final de colores en la superficie completa se vea prolija (la muestra de 15 cuadros no alcanza para ver las 6 zonas a la vez con claridad).

**Para verlo en vivo, desde la terminal del usuario** (esta sesión no tiene acceso a la sesión gráfica de macOS, mismo límite documentado desde F2 de art-fly):

```bash
source .venv-body/bin/activate
mjpython music-fly/scripts/live_view_console.py --trace out/music-fly/f1/live_trace.json
```

Cada cuadro hace IK real de las seis patas (recordar: 332s para 599 cuadros en modo batch), así que el `--fps` por defecto es bajo (10) a propósito.

## Actualización 2026-09-16e: el visor en vivo colgaba, bug propio no del entorno

El usuario corrió `live_view_console.py` y la ventana crasheó con `NSWindow should only be instantiated on the main thread`. Antes de sospechar del entorno (que es exactamente lo que art-fly documentó como causa en F2-cuerpo-ik.md 2026-09-15g, un `.venv-body` creado con `uv venv` en vez de `python3.10 -m venv`), se verificó: `pyvenv.cfg` no tiene ninguna marca de `uv`, es un venv estándar — no era eso.

**La causa real era propia**: `body_compose.build_body()` llamaba a `physics.render(width=64, height=64)` sin condición, copiado de `paint_3d.py` sin notar que ese archivo lo hace condicional (`create_render_context`) exactamente por este motivo. Ese contexto offscreen de dm_control no puede coexistir con `mujoco.viewer.launch_passive` en el mismo proceso. Arreglado: `build_body(create_render_context=False)` por defecto; ninguno de los dos consumidores (`compose_with_body.py`, `live_view_console.py`) lo necesita.

## Actualización 2026-09-16f: ver y escuchar juntos

El usuario probó el visor y notó que no sonaba nada — correcto, hasta acá `live_view_console.py` nunca hablaba con REAPER, solo movía las patas y pintaba la textura. Se conectó: al arrancar, prepara la sesión de REAPER (pistas, `ReaSynth`, tempo, `play`) igual que los otros scripts, y agrega `console.compose.LiveNoteGate` (extraído de la lógica de `compose_from_legs`, mismo cooldown y misma escala, pero sin poder mirar el futuro — la duración de la nota queda fija en un paso de grilla en vez de contar cuadros de contacto consecutivos hacia adelante, porque en vivo todavía no se sabe cuánto va a durar el contacto). Cada vez que T1 izquierda logra contacto real con el cooldown ya cumplido, la nota se manda a REAPER en ese mismo instante, con el reloj real del visor.

Compás y tempo se calculan una sola vez al arrancar, sobre la traza cruda (T3R es continuo, no necesita cuerpo físico para decodificarse), antes de abrir la ventana.

**Verificado sin la ventana** (la lógica del gate, no el visor): recorriendo las 599 z de la traza con el mismo `LiveNoteGate`, disparó 50 notas — coincide con lo medido en la versión sin cuerpo físico (F2-consola.md, sección 4b/actualización 2026-09-16b), confirmando que el gate en vivo se comporta igual que el offline antes de sumarle la incertidumbre del contacto físico real.

## Actualización 2026-09-16g: loop real, pausa sincronizada, tope por pista

El usuario probó el visor con audio y encontró tres problemas de diseño reales, no bugs de implementación:

1. **Pausa desincronizada**: al pausar la ventana, REAPER seguía sonando por su cuenta hasta llegar al final de lo ya escrito y pararse solo; al reanudar, la mosca seguía pero REAPER ya se había detenido.
2. **La pieza crecía sin límite**: cada nota se agregaba más allá de la anterior, sin ningún loop — "la mosca debe agregar todo dentro de un loop, no seguir después de donde se cierra".
3. **Riesgo de saturar un solo canal**: sin límite, todas las notas de un instrumento se amontonan en la misma pista indefinidamente.

Los tres se resolvieron:

- **Loop real**: `setloop`/`repeat` (ya existían del experimento de melodía de F0) se mandan una vez al arrancar, con un largo de `LOOP_BARS=4` compases calculado del compás y tempo elegidos. Cada nota se ubica con el tiempo modulado al largo del loop (`t % loop_length_s`), nunca más allá.
- **Pausa sincronizada**: el `key_callback` de la tecla espacio manda `stop`/`play` a REAPER en el mismo instante que pausa la ventana — es solo escribir un archivo chico, no el trabajo pesado de IK que el callback nunca puede hacer (misma regla de `art-fly/scripts/live_view.py`).
- **Tope por pista, con la opción que propuso el usuario**: `MAX_NOTES_PER_TRACK=16`. `LiveNoteGate.maybe_fire` ahora recibe qué pistas están llenas y, si la que eligió T2 izquierda está llena, prueba las otras de la paleta antes de descartar la nota — nunca crea una pista nueva sobre la marcha, cicla entre las ya armadas (la opción "b" que el usuario mismo ofreció, más simple que crear pistas en vivo).

**Verificado sin la ventana**: se simularon 3 vueltas completas del loop reusando la traza — 32 notas disparadas, exactamente 16 por pista (el tope), nunca lo superó, confirmando que el ciclo de reseteo del cooldown al detectar la vuelta del loop funciona.

**Recomendación dada al usuario**: abrir un proyecto nuevo en REAPER (sin guardar el anterior) antes de la próxima prueba, para ver a la mosca construir desde cero en vez de sumarse al amontonamiento de pruebas anteriores. No se scripteó un borrado automático porque implicaría acciones destructivas sobre el proyecto del usuario sin pedir permiso en el momento.

## Actualización 2026-09-16h: la pantalla de REAPER dentro de la escena 3D, y la mosca ya no se queda muda

Dos pedidos más del usuario probando el visor.

**"La pantalla de OBS debería aparecer frente a la mosca"**: nuevo módulo `music-fly/console/screen.py`, que arma la misma escena tethered que `artfly.scene.build_tethered_scene` (sin tocar ese archivo de art-fly) pero agrega un cuerpo "screen" — un geom delgado con su propia textura — delante de la cabeza. Se midió primero, no se supuso, hacia dónde mira la mosca: `head=[0.057, 0, -0.003]` con el tórax en el origen, o sea que la cabeza está en +X. La pantalla se ubica más adelante en esa misma dirección.

Verificado offscreen con un color de prueba antes de conectar nada real: la textura no se actualizaba con solo escribir el buffer — hacía falta el mismo paso de "subir a GPU" que ya usa el lienzo (`upload_screen_texture`, análogo a `artfly.scene.upload_canvas_texture`). Con eso, el color de prueba apareció en el lugar correcto.

`live_view_console.py` ahora se conecta a OBS al arrancar (`obsws-python`, instalado en `.venv-body`) y cada 20 cuadros le pide una captura real de la fuente de REAPER, la redimensiona, y la sube a la textura de la pantalla 3D. Si OBS no está disponible, el visor sigue funcionando igual, simplemente sin la pantalla (no se cae por esto).

**"Después de un rato la mosca no creó más tracks"**: era el tope de `MAX_NOTES_PER_TRACK=16` funcionando exactamente como se diseñó — pero una vez las dos pistas llenas, la mosca se quedaba muda para siempre, que no es lo que se quería. Se reemplazó por un balanceo suave en `LiveNoteGate.maybe_fire`: sigue mandando la elección real de T2 izquierda la mayoría del tiempo, pero si esa pista queda mucho más cargada que la otra (`BALANCE_THRESHOLD=4` notas de diferencia), usa la menos cargada. Nunca se niega a tocar. Verificado: 6 vueltas de loop simuladas dan 490 notas (antes se frenaba en 32), pistas parejas (246 contra 244).

## Actualización 2026-09-16i: un bug real colgaba el listener sin avisar, e instrumentos reales verificados

**El listener se congelaba sin ningún aviso y costó varios reinicios diagnosticarlo.** Al probar nombres de instrumentos candidatos en pistas que en realidad no existían (`addtrack 50` no crea una pista *en* el índice 50 si solo hay 10 pistas — inserta al final real, que quedó en el índice 2; el índice 50 nunca existió), `addfx 50 ...` llamó a `TrackFX_AddByName` con un `MediaTrack` nulo, que tira un error de Lua sin atrapar. Eso mata el `defer` loop **entero**, sin ningún mensaje visible más allá de que el reloj de ritmo (`tick_log.jsonl`) deja de escribir — nada que apunte a la causa. Se encontró recién cuando el usuario copió el texto exacto de la consola de REAPER.

**Arreglo de fondo, no un parche puntual**: `drain_queue()` ahora envuelve cada comando en `pcall`. Un comando roto queda registrado como error en la consola, pero el listener sigue vivo y sigue procesando los siguientes. Confirmado real: los 8 comandos que habían quedado colgados desde el bug se procesaron todos (con su error visible) apenas se recargó el listener con el arreglo.

**Instrumentos reales, verificados uno por uno, no supuestos**: con el listener ya estable, se probó `AUMIDISynth` y `DLSMusicDevice` (ambos `AudioUnit` de Apple, no dependen de una muestra externa como sí necesitarían `ReaSamplomatic5000` o `AUSampler`) sobre pistas que **sí existían** — se agregó el FX, se mandó una nota real, y se midió el pico del master: 0,109 a 0,218, variando mientras sonaban las dos notas. La paleta pasa de "ReaSynth en dos registros" (misma síntesis, declarado como limitación en F2-consola.md) a **tres motores de sonido genuinamente distintos**: `ReaSynth` (grave/agudo), `AUMIDISynth`, `DLSMusicDevice`.

**Efecto secundario de la investigación fallida**: quedaron 8 pistas vacías en el proyecto actual del usuario (índices reales 4-9 más algo), producto de los intentos con índices que no existían. Se avisó al usuario, no se agregó un comando de borrado de pistas solo para esto — es un caso de uso único, no algo que la mosca vaya a repetir con la paleta ya corregida.

## Actualización 2026-09-16j: por qué se repetían las notas, medido de verdad

El usuario preguntó, con razón, si el problema de "siempre las mismas 3 notas" era realmente por el tiempo (traza corta repitiéndose) o por otra cosa. Se midió en vez de sostener la explicación anterior sin chequear.

**Hipótesis descartada**: que el decodificador saturara (que T1L.y quedara siempre cerca de un extremo del `tanh`, colapsando el pitch a 2-3 grados). Medido sobre 7.172 cuadros reales: los 10 grados de la escala aparecen todos, entre 4,9% y 12,2% cada uno — bien repartido, no hay saturación.

**La causa real**: el gesto decodificado tiene una autocorrelación de **0,41 de un cuadro al siguiente** (coherente con el test de cerebro congelado de la actualización 2026-09-16b: el cerebro real tiene continuidad temporal genuina). El visor avanza un cuadro de la traza por paso — eso significa que cuadros consecutivos, que están correlacionados, son los que se usan para notas consecutivas. El resultado sí suena repetitivo dentro de un loop corto, aunque la traza completa tenga variedad de sobra.

**Por qué alargar la traza a 3 minutos no era la solución** (el usuario lo notó antes de que se implementara mal): el largo del loop musical (`LOOP_BARS=4`, ~8s) y el largo de la traza son parámetros independientes en el código — alargar la traza no acorta ni alarga lo que se escucha repetirse. Además, con el paso lento del visor (una IK real de 6 patas por cuadro), una traza de 3 minutos tardaría mucho en recorrerse entera, sin resolver la repetición de corto plazo.

**El arreglo real, medido**: la autocorrelación de la secuencia de grados resultante cae de 0,40 (salto de 1 cuadro) a practicamente 0 (-0,03 a 0,02) a partir de saltar 3 cuadros o más entre pasos del visor. Se agregó `FRAME_STRIDE=7`: en vez de `self.i += 1`, el visor salta 7 cuadros de la traza por paso. Cada paso ahora mira un estado cerebral genuinamente distinto del anterior, sin tocar el loop musical ni necesitar una traza más larga (aunque la de 3 minutos queda igual, como pool más grande, sin costo).

## Actualización 2026-09-16k: los "acordes siempre iguales" eran notas viejas nunca borradas, mas perillas reales

El usuario mandó una captura de REAPER: notas apiladas una encima de otra en los mismos compases, y dijo que los acordes que se forman "son todos iguales". No era una elección repetida del cerebro — era un bug de acumulación.

**La causa real**: `testnote` siempre agrega un item nuevo, nunca borra nada. Con un loop que se repite indefinidamente, el mismo compás (misma posición modulo el largo del loop) recibe una nota nueva en **cada** vuelta del loop, para siempre — nunca se reemplaza la de la vuelta anterior. Después de suficiente tiempo, cada compás termina con un acorde denso hecho de notas de docenas de vueltas distintas, apiladas, no una decisión del cerebro repetida.

**Arreglo**: nuevo comando `replacenote` en `fly_listener.lua` — antes de insertar la nota, borra cualquier item que ya ocupe ese mismo rango en esa pista (`D_POSITION`/`D_LENGTH` comparado contra el rango nuevo). `live_view_console.py` ahora manda `replacenote` en vez de `testnote`. Cada compás muestra la decisión más reciente del cerebro para esa posición, no la acumulación de todas las anteriores.

**Perillas (T2 derecha), implementado**: se decodificaban desde el principio pero nunca se enviaban a REAPER (deuda explícita desde la primera versión de la consola). Ahora, cada vez que una nota dispara de verdad, se manda `fx <pista> 0 0 <valor>` y `fx <pista> 0 1 <valor>` con los primeros dos parámetros del instrumento activo, continuos, derivados de T2 derecha.

**De paso**: `AUMIDISynth` y `DLSMusicDevice` habían quedado con la misma nota base (60) — sonaban exactamente superpuestos en registro pese a ser timbres distintos. Se separaron a 42/78/54/66, repartidos para que las cuatro paletas de ~2 octavas se superpongan lo menos posible.

## 7. Deuda que queda

- ~~Sin cuerpo físico~~ — resuelto, ver actualización 2026-09-16c. `compose_from_trace.py` (sin cuerpo, rápido) sigue existiendo para iterar rápido en el diseño de la consola; `compose_with_body.py` (con cuerpo, lento) es la versión honesta con contacto real verificado.
- El bucle con cuerpo físico corre a 0,56 fps, muy por debajo de tiempo real — sirve para renderizar offline, no para una performance en vivo con el cuerpo moviéndose junto al cerebro.
- **Tempo y compás fijos por pieza**: se deciden una vez (promedio/moda sobre toda la traza), no varían en vivo. Para una performance de verdad tendrían que decidirse en streaming.
- **Perillas (T2 derecha) y mute (T3 izquierda) se decodifican pero no se envían a REAPER** — quedó fuera del alcance de esta primera versión para tener algo audible antes.
- ~~Test de cerebro congelado no corrido~~ — hecho, ver actualización 2026-09-16b. Pendiente: confirmar que la diferencia de autocorrelación se nota *al oído*, no solo en el número.
- ~~Visualización 3D de la mosca sobre la consola~~ — resuelto, ver actualización 2026-09-16d. Falta que el usuario la corra en vivo y confirme que la leyenda de zonas se ve clara con la traza completa, no solo los 15 cuadros de la prueba offscreen.

## 8. Cómo revertir

```bash
git revert <sha>
rm -rf music-fly/console
rm -f music-fly/scripts/compose_from_trace.py music-fly/scripts/test_frozen_brain.py \
      music-fly/scripts/test_autocorrelation.py
```
