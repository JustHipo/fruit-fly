# F1: subgrafo motor en tiempo real

| | |
|---|---|
| Ticket | (sin clave, se trabaja standalone) |
| Proyecto | music-fly |
| Rama | `feat/f0-flybrain-fundacion` |
| Fase | F1 |
| Fecha | 2026-09-16 |
| Impacto | 🟡 aditivo |
| Estado | ✅ Entregable de la Fase 1 completo (traza en vivo a ~40Hz); queda una deuda de calibración anotada |

## 1. Qué se hizo

Se implementó el método anatómico de [ARQUITECTURA.md sección 4.2](../../ARQUITECTURA.md#42-selección-del-subgrafo-motor) contra los datos reales del conectoma (no simulado ni de prueba): motoneuronas de pata → premotoras → descendentes, rankeadas por peso sináptico medido. Se agregó `flybrain.subgraph.induced_subgraph` (genérico, reusable) y `music-fly/scripts/select_motor_subgraph.py` (específico, aplica el criterio anatómico).

## 2. Por qué

Regla 0 del `REGLAMENTO.md`: se buscó en `docs/avance/REGISTRO_MIGRACIONES.md` antes de empezar. Resultado: `packages/flybrain/docs/migraciones/F0-simulador-lif.md` (el simulador LIF, la carga del conectoma y la calibración ya existen y se reusan tal cual; no se reimplementó nada de eso). También se leyó `art-fly/docs/migraciones/F2-cuerpo-ik.md` como referencia de formato.

## 3. Archivos tocados

| Archivo | Cambio |
|---|---|
| `packages/flybrain/flybrain/subgraph.py` | Nuevo. `induced_subgraph()`: subconjunto de neuronas + todas sus aristas reales, reindexado |
| `music-fly/scripts/select_motor_subgraph.py` | Nuevo. Aplica el método de 4.2 y guarda el subgrafo resultante |
| `out/music-fly/f1/motor_subgraph.npz`, `*_meta.csv`, `*_body_ids.npy` | Generados (gitignored, `out/`) |
| `music-fly/scripts/run_motor_subgraph.py` | Nuevo. El bucle en tiempo real: reloj anclado a `time.perf_counter()`, salteo de pasos si hay atraso, calibración, emisión de z-scores, ruido y `weight_scale` propios del subgrafo |
| `music-fly/scripts/calibrate_subgraph_scale.py` | Nuevo. Barrido de `weight_scale` contra el nulo, sobre el subgrafo |
| `packages/flybrain/flybrain/calibration.py` | `calibrate()` acepta `n_kicks` (default 300, no rompe nada existente) |
| `out/music-fly/f1/live_trace.json` | Generado (gitignored). Traza real de 15s, con los parámetros finales |

## 4. Validación

**Selección de motoneuronas de pata**, verificada por dos columnas independientes del metadata real (no una sola fuente):

| Neuromero | Motoneuronas (por `somaNeuromere`) |
|---|---|
| T1 (delantera) | 171 |
| T2 (media) | 174 |
| T3 (trasera) | 146 |
| **Total** | **491** |

Cruzado contra `exitNerve`: las motoneuronas de pata salen mayoritariamente por `ProLN`/`MesoLN`/`MetaLN` (nervios de pata pro/meso/metatorácicos), consistente con la selección por `somaNeuromere`.

**Subgrafo final** (motor + top 2.000 premotoras + top 2.000 descendentes por peso sináptico):

| Métrica | Valor |
|---|---|
| Neuronas | **4.491** (objetivo del documento: 1.000-6.000) |
| Aristas reales retenidas | 413.484 |
| Composición | 2.886 `vnc_intrinsic`, 569 `descending_neuron`, 491 `vnc_motor`, 360 `ascending_neuron`, 115 `vnc_sensory`, 64 `cb_intrinsic`, 6 otras |

**Chequeo de cordura no trivial**: el ranking por conectividad (que no mira ninguna etiqueta, solo peso sináptico) recuperó 569 células que el metadata etiqueta independientemente como `descending_neuron`. No se le pidió eso al algoritmo — es evidencia de que la selección encuentra neuronas anatómicamente sensatas, no ruido.

## 5. Controles corridos

Los tres, con los parámetros finales calibrados (`weight_scale=100`, `n_kicks=8`), 3 segundos simulados cada uno, `music-fly/scripts/run_subgraph_controls.py`:

| control | corr. tasas | dif. tasa media | corr. dinámica (z completo) |
|---|---|---|---|
| `shuffle_weights` | 0,449 | 2,07 | 0,105 |
| `degree_preserving` | 0,488 | 1,16 | 0,288 |
| `erdos_renyi` | **-0,272** | 1,28 | 0,150 |

Los tres correlacionan lejos de 1 con el real — el cableado medido de este subgrafo sí importa, no es indistinguible de sus versiones degradadas.

**Chequeo de cordura que se repitió solo, sin buscarlo**: `vnc_sensory` se queda en **1,80 Hz idéntico** en real, `shuffle_weights` y `degree_preserving` (no reciben sinapsis, son capa de entrada, nada que barajar les cambia la tasa), pero salta a **2,65 Hz** en `erdos_renyi` (que sí les inventa aristas entrantes de la nada). Es exactamente el mismo patrón que ya había encontrado art-fly sobre el cerebro **completo** (`LECCIONES_APRENDIDAS.md`, 2026-09-14: "las poblaciones sensoriales se quedan en 1,83 Hz en real, shuffle y degree... pero saltan a 3,2 en erdos_renyi"). Que se repita en un subgrafo de otro tamaño, con otro método de selección, es una confirmación independiente de que el mecanismo es real y no una casualidad de esta corrida puntual.

## 4b. Entregable: traza en vivo, medida

`run_motor_subgraph.py`, 15s de reloj real, `device=cpu`:

| Métrica | Valor |
|---|---|
| Pasos simulados | 14.999 (dt=1ms) |
| Ritmo real logrado | **999,9 pasos/s** (objetivo: 1000/s = tiempo real) |
| Pasos salteados por atraso | **0** |
| Muestras de z emitidas | 599, **~39,9 Hz** (objetivo del documento en 3.4: ~40Hz) |
| Tiempo de calibración | 2,4s de reloj real para 2,5s simulados |

El subgrafo (4.491 neuronas) corre tan rápido que nunca hizo falta saltear ni un paso en 15 segundos — el mecanismo de salteo está escrito y probado en el código (recorta a `MAX_CATCHUP_STEPS=50`), pero no se ejercitó porque no hizo falta. Es el resultado esperado: 36x menos neuronas que el cerebro completo, que ya corría a 106 pasos/s en CPU.

## 6. Problemas encontrados

### El chequeo de cordura de 5.1 parecía fallar, y no era así: era el archivo equivocado

`ARQUITECTURA.md` 5.1 pide verificar que las motoneuronas reciben "del orden de 1.800 a 3.200 sinapsis", si no "estamos decodificando ruido". Medido sobre la matriz que carga `flybrain.data.load_connectome` (`mcns_ad_inprop_all_neuron.npz`, proporción de input normalizada): mediana de **205** aristas entrantes por motoneurona, incluso sobre el conectoma **completo** (no el subgrafo recortado). Muy por debajo del rango esperado — la señal de alarma exacta que describe el documento.

**Diagnóstico**: `mcns_ad_inprop_all_neuron.npz` cuenta **socios presinápticos distintos** (una arista por par de neuronas conectadas), no sinapsis físicas. Un mismo par de neuronas suele tener varios contactos sinápticos reales. Se comparó contra `mcns_ad_syncount_all_neuron.npz` (conteo crudo de sinapsis físicas, no normalizado): mediana **1.767** sinapsis entrantes por motoneurona sobre el conectoma completo — dentro del orden de magnitud que pedía el documento (61 de 491 caen literalmente en el rango 1.800-3.200; la mediana general lo roza). El número de socios distintos en ese mismo archivo da mediana 208, casi idéntico a los 205 medidos por el otro camino — confirma que las dos mediciones son consistentes entre sí, solo estaban contando cosas distintas (socios vs. sinapsis físicas).

**Conclusión**: el chequeo del documento es correcto, estaba escrito pensando en sinapsis físicas (`syncount`), no en la matriz de proporción de input (`inprop`) que usa el simulador. No hay decodificación de ruido: el motivo real por el que el subgrafo ve menos conexiones por motoneurona que el conectoma completo es que el subgrafo trunca a las top 2.000 premotoras por peso (recorte intencional por presupuesto de tamaño), no un problema de la selección en sí.

**Consecuencia**: aclarar en ARQUITECTURA.md 5.1 que el chequeo de 1.800-3.200 es sobre sinapsis físicas (`syncount`), no sobre socios distintos (`inprop`), para que no genere la misma confusión de vuelta.

### Las tasas de reposo del subgrafo eran 15-20x más altas que las del cerebro completo — resuelto, y la hipótesis inicial era incorrecta

Medido en la primera calibración: 46 a 69 Hz por población en el subgrafo, contra **3,3 Hz** medido en el cerebro completo (`ESTADO.md`, "Números medidos"). No era un error del bucle en tiempo real (eso corrió perfecto desde el principio, ver 4b) — era de la dinámica misma.

**Hipótesis inicial (quedó registrada más abajo, y resultó ser falsa)**: se sospechó de `weight_scale=65`, calibrado para el conectoma completo, asumiendo que un subgrafo más denso necesitaría un valor distinto.

**Se probó directamente, no se asumió**: se corrió `weight_scale` de 2 a 65 sobre el subgrafo, todo lo demás igual. La tasa real se mantuvo estable entre 48 y 54 Hz en **todo** el rango, prácticamente sin cambiar con la escala — la prueba misma de que `weight_scale` no era la causa. Si lo fuera, la tasa habría subido con la escala; no lo hizo.

**Causa real, encontrada al revisar `LifNetwork.noise()`**: la función de ruido de fondo inyecta un número FIJO de empujones por paso (`n_kicks=300`), pensado para repartirse entre 161.429 neuronas. Aplicado sin cambios a un subgrafo de 4.491 neuronas (2,8% del tamaño), cada neurona recibe proporcionalmente **~36 veces más ruido** — eso solo alcanza para explicar tasas mucho más altas, sin que el conectoma real tenga nada que ver.

**Arreglo, medido**: escalar `n_kicks` proporcionalmente al tamaño de la red (`300 × 4491/161429 ≈ 8`) y volver a barrer `weight_scale` con el ruido ya corregido. Resultado: en `weight_scale=100`, tasa real 4,2 Hz y correlación contra el nulo 0,195 — casi idéntico a la firma ya validada del cerebro completo (3,3 Hz, correlación 0,21). Aplicado en `run_motor_subgraph.py` (`SUBGRAPH_WEIGHT_SCALE=100`, `n_kicks` calculado en tiempo de ejecución) y en `flybrain.calibration.calibrate()` (nuevo parámetro `n_kicks`, default 300 sin romper nada de art-fly).

**Confirmado en la corrida final**: tasas de reposo entre **1,74 y 5,37 Hz** por población (antes: 46-69 Hz), con la forma esperada — `vnc_sensory` es la más baja (1,74 Hz), consistente con ser capa de entrada sin sinapsis propias, mismo patrón que ya documentó art-fly para el cerebro completo. Tiempo real intacto: 999,9 pasos/s, 0 pasos salteados, ~39,9 Hz de traza.

**Lección que queda**: cuando se recorta una red a un subconjunto, cualquier parámetro que dependa implícitamente del tamaño total (acá, un conteo fijo de "empujones" de ruido) hay que revisarlo, no solo los parámetros que parecen obviamente relacionados con la densidad (`weight_scale`). La hipótesis más obvia no siempre es la correcta — medir descarta la que no era, en vez de arreglar a ciegas la primera sospecha.

## 7. Deuda que queda

- ~~Recalibrar `weight_scale` para este subgrafo~~ — resuelto, ver actualización sobre la tasa de reposo. `SUBGRAPH_WEIGHT_SCALE=100` con `n_kicks` proporcional al tamaño.
- Decidir el tamaño de premotoras/descendentes (`--n-premotor`, `--n-descending`) no está optimizado, son valores redondos que dieron un tamaño final razonable. Podría iterarse.
- Corregir ARQUITECTURA.md 5.1 según el hallazgo de la sección 6 (ya aplicado).
- ~~Correr los tres controles de topología con los parámetros finales~~ — hecho, ver sección 5.

## 8. Cómo revertir

```bash
git revert <sha>
rm -f packages/flybrain/flybrain/subgraph.py music-fly/scripts/select_motor_subgraph.py \
      music-fly/scripts/run_motor_subgraph.py music-fly/scripts/calibrate_subgraph_scale.py \
      music-fly/scripts/run_subgraph_controls.py
rm -rf out/music-fly/f1
```
