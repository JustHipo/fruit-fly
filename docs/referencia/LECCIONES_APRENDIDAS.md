# Lecciones aprendidas

Se agrega una entrada cada vez que algo cuesta más de una hora de depuración.

## 2026-09-14: hallazgos de la investigación previa

Estas no vienen de depurar sino de leer el ecosistema, pero valen igual.

- **Un readout entrenado puede aprender a ignorar el cerebro por completo.** `fly-craftax` lo descubrió apagando la visión: la política seguía puntuando igual. Por eso el test de cerebro congelado es obligatorio.
- **Simular caro y decodificar mal desperdicia todo.** `fruit-fly-fashion` simula 166.700 neuronas y después mete los spikes en un SHA-256, destruyendo toda la estructura. El decodificador tiene que ser continuo.
- **Nadie logró sacar marcha coordinada del conectoma.** Por eso la mosca no camina: evitamos el único problema abierto del área.
- **REAPER y Python desalineados en arquitectura fallan en silencio.** Un Python arm64 con REAPER Intel bajo Rosetta no carga y no avisa.

## 2026-09-14: MPS aporta apenas 7% sobre CPU en el simulador LIF

Medido con `packages/flybrain/scripts/benchmark.py` sobre grafo sintetico del tamano de MaleCNS: MPS 63,0 pasos/s, CPU 59,0 pasos/s.

**Por que**: el paso LIF es un scatter-gather disperso (`gather` + `index_add_`) sobre 25 millones de aristas, mil veces por segundo simulado. Esta limitado por ancho de banda de memoria, no por computo, que es justo donde una GPU no luce sus FLOPS.

**Consecuencia practica**: correr el cerebro en CPU y dejar la GPU para CLIP, que si es limitado por computo. En el loop de entrenamiento de la fase 3 eso deja las dos unidades trabajando en paralelo en vez de pelearse la GPU.

**Consecuencia de diseno**: valida la decision de no mover el proyecto a una maquina con GTX 1650. Si ni la GPU integrada del M4 Pro ayuda, una discreta de gama baja tampoco.

*Actualizacion con datos reales*: sobre el conectoma real (14,26M aristas, no 25,58M sinteticas) CPU da 106,5 pasos/s y MPS 104,7. CPU ya directamente gana.

## 2026-09-14: el ruido inyectado puede tapar al conectoma por completo, y no se ve

La leccion mas importante hasta ahora.

Al correr el conectoma real con `weight_scale=5.0`, todas las superclases (descendentes, motoras, lobulo optico, cerebro central) disparaban a la misma tasa: 1,84 Hz. Sospechoso, porque poblaciones con funciones distintas deberian comportarse distinto.

**Diagnostico**: correr el conectoma real y uno de Erdos-Renyi igualado con EL MISMO ruido, y correlacionar las tasas por neurona. Dio **0,997**. Eran indistinguibles: la actividad la generaba integramente el ruido inyectado y el grafo medido no aportaba nada.

**Por que pasaba**: los pesos vienen normalizados por input del postsinaptico (las columnas suman 1), asi que con escala 5 mV la corriente sinaptica real rondaba los 0,09 mV, contra empujones de ruido de 8 mV. El umbral esta a 7 mV del reposo.

**Por que es grave**: es invisible en las metricas obvias. La tasa media de disparo se veia perfectamente razonable. Un proyecto entero puede construirse encima de esto y producir arte generado por un generador de numeros aleatorios caro.

**Regla que queda**: *cualquier* cambio en los parametros de la dinamica exige volver a correr la comparacion contra el nulo. La correlacion contra el nulo es un numero que hay que mirar siempre, no solo al final. `scripts/calibrate_scale.py` lo automatiza.

**Conexion con el resto**: es la version en el simulador del mismo error que `fly-craftax` encontro en su readout entrenado. El patron general es "el sistema parece funcionar pero el conectoma no participa", y aparece en todas las capas del proyecto.

## 2026-09-14: el cableado medido si importa, y los controles lo muestran distinto cada uno

Corrida completa de los tres controles de topologia contra el conectoma real (`scripts/run_controls.py`).

Cada control degrada una propiedad distinta y produce una falla distinta, lo que los vuelve un diagnostico y no solo una casilla que tildar:

- **`shuffle_weights`**: la red explota a 17-22 Hz. La asignacion medida de pesos es lo que sostiene el balance excitacion/inhibicion.
- **`erdos_renyi`**: todo se aplana a ~3,2 Hz uniforme. La heterogeneidad entre poblaciones viene del cableado especifico.
- **`degree_preserving`**: queda en el medio. Conservar grados conserva parte de la estructura.

**Chequeo de cordura inesperado**: las poblaciones sensoriales se quedan en 1,83 Hz en real, shuffle y degree (correcto, son capa de entrada y no reciben sinapsis), pero saltan a 3,2 en `erdos_renyi`, que les inventa aristas entrantes. Es una forma barata de detectar que un recableado rompio la estructura de entrada/salida del grafo.

**Conclusion practica**: correr los tres, no uno. Un solo control habria dado una foto incompleta.

## 2026-09-14: el lector EMA arranca en cero y arruina los primeros frames

Los primeros 3 frames de cada traza tenian z-scores de -25, -20 y -18. No era la dinamica: el suavizado exponencial arranca en cero y tarda ~3 tau en converger. En poblaciones de baja varianza eso se traduce en z absurdos.

Dos arreglos, los dos necesarios:

1. `PopulationReader.reset(to=baseline.mean)` arranca el suavizado en el baseline en vez de cero.
2. 200 ms de asentamiento antes de empezar a grabar.

Ademas el piso de la desviacion paso de absoluto (`+1e-6`) a relativo (`max(std, 0.02*mean)`), porque las poblaciones sensoriales tienen varianza minuscula y dividir por ella amplifica cualquier fluctuacion.

## 2026-09-14: el rango dinamico de z es lo que se traduce en variedad visual

Al pintar el conectoma real y los tres controles con decodificador y semilla identicos, el real ocupa todo el lienzo y los tres controles se hunden contra el borde inferior.

La metrica que lo explica es una sola: **la desviacion estandar de los z-scores**. Real 2,217; controles entre 1,01 y 1,26.

**Mecanismo**: con poca variacion en z, `tanh(W @ z + b)` se estanca cerca de un valor constante. El componente `dy` queda con sesgo persistente, la pluma deriva siempre hacia el mismo lado y termina rebotando contra el fondo. Con rango dinamico alto la direccion cambia y la pluma explora.

**Consecuencia de diseno**: `std(z)` es un indicador barato y temprano de si una configuracion va a producir algo visualmente interesante. Conviene mirarlo antes de gastar minutos pintando.

**Consecuencia metodologica**: la diferencia visual esta mediada por el decodificador, que hoy tiene pesos aleatorios. Lo que NO depende del decodificador es la diferencia de std en z, que ocurre en el cerebro. Al entrenar el decodificador (F3) hay que volver a correr los controles, porque un decodificador entrenado puede aplanar o exagerar esta diferencia.

## 2026-09-14: la estadistica circular da la saturacion gratis

Al derivar el color del cerebro, cada poblacion ocupa una ranura del circulo cromatico y el matiz es la media circular pesada por actividad.

El hallazgo util: **el largo del vector resultante de esa media circular ya es una medida de concentracion**, entre 0 y 1. No hace falta inventar una metrica aparte ni calcular entropia. Una poblacion domina, el resultante es largo, color saturado. Actividad repartida entre muchas, los vectores se cancelan, resultante corto, color lavado.

Sale de la misma operacion que ya haciamos para el matiz, a costo cero.

**Lo que hubo que evitar**: usar `argmax` para elegir la poblacion dominante. Es mas simple pero discontinuo, y un cambio minimo de actividad haria saltar el color de golpe. Es el mismo error que el hash de `fruit-fly-fashion`, en chico.

## 2026-09-15: el error que reporta un solver de IK no es necesariamente el error real

`qpos_from_site_xpos` de flybody reporta `err_norm = 0,000103`. Aplicar el `qpos` que devuelve y medir la distancia real de la garra al objetivo da **0,006283**, sesenta veces peor.

**Por que importa tanto**: la primera medicion del area alcanzable, hecha confiando en `err_norm`, dio 89% de cobertura. Medida de verdad, era 0%. Toda la fase se habria construido sobre una garra que aterriza un 2% del largo del cuerpo fuera del objetivo, sin ningun sintoma visible hasta que la obra saliera mal.

**Regla que queda**: medir siempre el resultado en el espacio que importa (la posicion real del efector), nunca el numero que el optimizador reporta sobre si mismo. Vale para cualquier solver, no solo para este.

**Ademas**: el flag `success` de ese solver solo dice si convergio antes de agotar `max_steps`. Devuelve `False` con errores de 1e-12. No sirve como criterio.

**Solucion aplicada**: iterar con arranque caliente cortando por el error medido. Cuatro pasadas de 300 pasos llevan el error real de 0,0063 a 0,00007, y son mas rapidas que una sola pasada de 3.000.

## 2026-09-15: cinematica inversa redundante puede dar posturas discontinuas para objetivos vecinos

Al intentar que la presion de pintura saliera de fuerza de contacto medida (no decodificada), se encontro que una pata con 8 articulaciones actuadas para un objetivo de 3 coordenadas tiene infinitas soluciones (espacio nulo de dimension 5). El solver de gradiente de flybody no elige consistentemente la "mas cercana" entre objetivos vecinos.

**Medido**: objetivos de profundidad a 1 mm de distancia dieron posturas cualitativamente distintas, algunas tocando el lienzo y otras esquivandolo por completo. La fuerza de contacto resultante no fue monotona con la profundidad pedida (13,1 -> 0,0 -> 0,0 -> 0,0 -> 18,8 -> sin contacto, en un barrido de -0,134 a -0,150).

**Lo que se probo y no alcanzo**: asentar dinamicamente con actuadores de posicion (a veces fuerzas de 15.000, inestable), aumentar la regularizacion del solver hacia la pose de partida (no ayuda, y en exceso impide converger).

**Decision tomada**: no forzar una solucion fragil de control de impedancia dentro del alcance de esta sesion. El contacto BOOLEANO es completamente confiable (se verifico con cero falsos positivos); la MAGNITUD de fuerza no lo es. Se redisenio la presion para salir de profundidad decodificada mas alla de una superficie fisica real, no de fuerza medida, dejando eso ultimo como trabajo futuro explicito.

**Principio general que deja esto**: cuando una cadena cinematica es redundante para la tarea, no asumir que el solver converge a la solucion "esperada" solo porque el error de posicion es chico. Verificar la postura completa, no solo el punto que se pidio alcanzar.

## 2026-09-15: la posicion de referencia de una IK no es necesariamente donde choca la fisica

Al ubicar el lienzo usando la posicion del `site` de la garra (el punto que la IK apunta), las seis patas resultaron tocandolo en reposo sin que nadie lo pidiera. El geom de colision real (una capsula) cuelga varios milimetros por debajo del site.

Se resolvio por busqueda binaria sobre la fisica real (subir el lienzo hasta el punto exacto donde deja de haber contacto en reposo), no calculando el desplazamiento a mano. Es el mismo principio que el hallazgo del err_norm no reproducible: medir en el espacio que importa, nunca confiar en un proxy por conveniencia.

## 2026-09-15: nombrar frames de video con un indice muestreado, no secuencial, corta el video en el primer frame

paint_3d.py guardaba frames de video cada N pasos de la traza, y uso ese mismo indice salteado como nombre de archivo (00000, 00003, 00006...). ffmpeg con patron %05d.png asume secuencia sin huecos: al no encontrar 00001.png, corta ahi. El video resultante tenia 1 frame de 67, 0,08 segundos en vez de 5,6.

**Regla que queda**: el nombre de archivo de una secuencia para ffmpeg (o cualquier lector por patron) tiene que ser un contador propio, secuencial, nunca el indice de otra cosa que se muestrea con huecos. Es un error de una linea con un sintoma que solo aparece al reproducir el archivo, no al generarlo.

## 2026-09-15: mas tiempo de traza satura el area cubierta, no la sigue extendiendo

Comparacion medida (no supuesta) entre traza de 12s (1.200 trazos) y 40s (4.000 trazos), mismo decodificador y semilla: cobertura de una grilla 20x20 paso de 92% a 87% (dentro del ruido), mientras que el porcentaje de pixeles con tinta subio de 68,5% a 77,4%.

**Interpretacion**: el PenDecoder sin entrenar hace una caminata aleatoria con direccion persistente que ya recorre casi todo el lienzo alcanzable en ~12 segundos. Tiempo adicional deposita mas tinta sobre las mismas zonas (mas densidad), no descubre area nueva.

**Consecuencia practica**: no hace falta grabar trazas mas largas que ~10-15s para cobertura. Si se quisiera cobertura mas pareja, la palanca es el decodificador (penalizar revisitar zonas densas), no la duracion.

## 2026-09-15: dimensionar un objeto fisico para "una parte" y despues sumar mas partes rompe la geometria en silencio

El lienzo se dimensiono (0,11 de medio-lado) pensando solo en la pata delantera T1. Al sumar las otras cinco patas, cuatro de seis nunca lograron contacto: T2 y T3 descansan fisicamente fuera de esa huella (T2 en y=0,168, T3 en x=-0,185, el lienzo llegaba hasta 0,11). No importaba que tan profundo se decodificara presionar, la garra nunca iba a tocar algo que no esta ahi.

**Sintoma enganoso**: el contacto medido (booleano, confiable) daba 0% para esas patas, que podria leerse como "la IK no converge" o "hace falta presionar mas hondo" - ambas hipotesis descartadas antes de encontrar la real (revisar el error de IK mostraba convergencia perfecta; profundizar la presion hasta 0,020 seguia sin dar contacto). La causa no estaba en la dinamica ni en el control, estaba en un numero de geometria puesto a mano sin pensar en el caso general.

**Regla que queda**: cuando un objeto fisico se dimensiona para un caso (una pata), y despues se generaliza a varios casos (seis patas), recalcular la geometria desde los requisitos de TODOS los casos, no extender el caso original. Calcular la huella union de las seis (reposo +- radio de cada una) hubiera evitado el problema desde el principio.

## 2026-09-15: nunca asumir una profundidad de presion fija, medir contacto en cada intento

Incluso la pata ya validada individualmente (T1) fallaba contacto en 2 de 9 puntos de su propio radio con una profundidad de presion fija, porque el desfase entre el punto que apunta la IK y el geom de colision real cambia con la postura (hallazgo relacionado: 2026-09-15c).

**Solucion que queda como patron reusable**: `LegIK.press()` prueba profundidades crecientes y verifica contacto REAL (via colision fisica) despues de cada una, en vez de calcular o asumir una profundidad que deberia funcionar. Result: contacto paso de 19% a 98% combinado con el arreglo del tamano del lienzo.

## 2026-09-16: esta sesion no tiene Accessibility ni WindowServer, pero OBS + obs-websocket sirve de ojos

Confirma y extiende el hallazgo de `art-fly` (F2, actualizacion "viewer en vivo", 2026-09-15f): esta sesion de Claude Code corre sin acceso a Accessibility ni a la sesion grafica de macOS.

**Verificado dos veces, con dos mecanismos independientes**: `screencapture -x` falla (`could not create image from display`), y `osascript` controlando "System Events" para clickear un boton falla (`osascript is not allowed assistive access`, -1728).

**Lo nuevo**: los Apple Events de alto nivel a una app especifica (`tell application "X" to activate`) SI funcionan sin Accessibility. La restriccion es especifica sobre manipular la interfaz de otra app (clicks, keystrokes), no sobre activarla.

**El atajo real**: OBS Studio (una app sin este sandboxing, con permiso de Screen Recording ya otorgado por el usuario en algun uso anterior) expone via `obs-websocket` (incluido desde OBS 28+) el request `GetSourceScreenshot`, que devuelve un PNG real de cualquier fuente configurada, incluida una captura de pantalla completa. Conectando un cliente (`obsws-python`, instalable al vuelo con `uv run --with obsws-python`) esta sesion pudo pedir una captura, guardarla, y leerla con la herramienta de lectura de imagenes - viendo la pantalla real del usuario sin tener el permiso ella misma.

**Consecuencia practica, para cualquier tarea futura que necesite verificar algo visual y esta sesion no pueda screenshotear directo**: si OBS esta instalado y tiene permiso de Screen Recording (verificar con una fuente `screen_capture` existente antes de asumirlo), habilitar su servidor websocket (`~/Library/Application Support/obs-studio/plugin_config/obs-websocket/config.json`, `server_enabled: true`, hacer backup antes) da una via real de verificacion visual sin depender de que el usuario mire y confirme. Detalle completo en `music-fly/docs/migraciones/F0-puente-reaper.md` seccion 6.4-6.5.

## 2026-09-16: una captura de OBS puede devolver un cuadro viejo sin avisar

Extiende la leccion de "OBS sirve de ojos" (2026-09-16, mas arriba): el metodo es real y funciona, pero tiene un limite que se encontro recien esta vez.

Cambiando el `window` target de una fuente `window_capture`/`screen_capture` muy seguido (varias veces en pocos segundos, mientras se buscaba que id de ventana correspondia a que) las capturas siguientes quedaron devolviendo un cuadro **cacheado**, de varios minutos antes, sin ningun error. Se penso que una serie de comandos reales a REAPER no habian funcionado, cuando en realidad si habian funcionado — lo unico roto era la captura.

**Como se detecto**: el usuario mando una captura de pantalla REAL (no via OBS) que mostraba el estado correcto, contradiciendo lo que las capturas de OBS venian mostrando.

**Regla que queda**: una captura de OBS que no da error no es evidencia de que sea del instante actual. Para confirmar algo importante, preferir un dato que la propia aplicacion escriba a un archivo (como ya hace `tick_log.jsonl` de REAPER) antes que una captura visual repetida en rafaga; y si hay que usar captura visual, no cambiar de `window` target mas de una vez sin verificar que el contenido efectivamente cambio.

## 2026-09-15: texuniform en MuJoCo mapea la textura por escala fisica, no una vez por cara

Al darle textura editable al lienzo para que la pintura se vea en el render, un parche pintado en el centro de la textura no aparecia en absoluto, aunque subir la textura ENTERA de un color si funcionaba (confirmando que la subida a GPU estaba bien).

**Causa**: el material tenia `texuniform="true"`, que en MuJoCo hace que la textura se repita segun la escala fisica del geom en metros, no que se mapee una vez a la cara completa. Con un lienzo de 0,52 m de lado, un parche en el centro de la textura terminaba mapeado a una posicion irreconocible o repetida.

**Diagnostico util**: pintar la textura ENTERA de un color primero aisla si el problema esta en la subida a GPU (bien) o en el mapeo UV (mal), antes de asumir cual de las dos etapas fallo.

**Arreglo**: sacar `texuniform`. El mapeo por defecto de MuJoCo para un geom `box` es una vez por cara, que es lo esperado para pintar sobre una superficie.
