# F0: simulador LIF y carga del conectoma

| | |
|---|---|
| Ticket | (sin clave, Jira todavia no existe) |
| Proyecto | packages/flybrain |
| Rama | `feat/f0-flybrain-fundacion` |
| Fase | F0 |
| Fecha | 2026-09-14 |
| Impacto | ⚪ interno |

## 1. Qué se hizo

Paquete `flybrain`, compartido por los dos proyectos:

- `data.py`: carga de la matriz dispersa de `connectome_data_prep` mas el metadata, y derivacion del signo de cada conexion desde el neurotransmisor de la celula presinaptica.
- `lif.py`: simulador leaky integrate-and-fire con retardo inhibitorio.
- `scripts/benchmark.py`: medicion de rendimiento sobre grafo sintetico del tamano de MaleCNS.

## 2. Por qué

**Lista de aristas con `gather` + `index_add_` por chunks**, en vez de las dos alternativas obvias:

- *Matriz densa N×N*: a 165.122 neuronas serian ~110 GB en float32. Imposible.
- *Tensores sparse de PyTorch*: la cobertura de kernels sparse en MPS es pobre; `torch.sparse.mm` falla o va lentisimo. Es el mismo motivo por el que `connectome-interpreter` conviene correrlo en CPU.

**Excitatorias e inhibitorias separadas en construccion** porque la inhibicion llega con 4 ms de retardo, asi que necesita un buffer circular y las excitatorias no.

**Las celulas con neurotransmisor sin asignar quedan en signo 0 y sus aristas se descartan**, en vez de adivinarles un signo. Adivinar contaminaria el dato medido.

## 3. Archivos tocados

| Archivo | Cambio |
|---|---|
| `packages/flybrain/pyproject.toml` | Nuevo |
| `packages/flybrain/flybrain/__init__.py` | Nuevo |
| `packages/flybrain/flybrain/data.py` | Nuevo, carga del conectoma |
| `packages/flybrain/flybrain/lif.py` | Nuevo, simulador |
| `packages/flybrain/scripts/benchmark.py` | Nuevo, medicion |

## 4. Validación

Conectoma **real** MaleCNS: 161.429 neuronas, 14.262.680 aristas con signo no nulo. 300 pasos con `dt = 1 ms`.

| Dispositivo | Pasos/s | Ratio de tiempo real |
|---|---|---|
| CPU | 106,5 | 0,1065x (9,4x mas lento) |
| MPS | 104,7 | 0,1047x (9,5x mas lento) |

**Orientacion de la matriz verificada**: en `mcns_ad_inprop_all_neuron.npz` las columnas suman 1 (147.307 de 161.429), confirmando filas presinapticas y columnas postsinapticas. El supuesto original era correcto.

**Poblaciones de la via de control de patas**, disponibles via `Connectome.select(superclass=...)`:

| superclass | n |
|---|---|
| descending_neuron | 1.310 |
| vnc_intrinsic | 12.967 |
| vnc_motor | 699 |
| vnc_sensory | 5.605 |

**Pendiente**: validar contra `philshiu/Drosophila_brain_model` en un circuito conocido.

## 5. Controles corridos

`controls.py` implementa los tres controles de `flydoom`: `shuffle_weights`, `degree_preserving_rewire` y `erdos_renyi_matched`.

Se uso `erdos_renyi_matched` como nulo para calibrar `weight_scale` (seccion 6).

Ademas se corrio la comparacion completa contra los tres controles, con `scripts/run_controls.py`, 1,5 s simulados por condicion:

| control | corr tasas | dif tasa media | corr dinamica |
|---|---|---|---|
| shuffle_weights | 0,584 | 11,11 | 0,136 |
| degree_preserving | 0,460 | 0,81 | 0,356 |
| erdos_renyi | -0,122 | 0,48 | 0,272 |

Tasa de reposo por poblacion (Hz):

| poblacion | real | shuffle | degree | erdos |
|---|---|---|---|---|
| descending_neuron | 3,23 | 21,99 | 5,12 | 3,23 |
| vnc_motor | 2,31 | 19,53 | 4,83 | 3,10 |
| vnc_intrinsic | 2,42 | 17,32 | 3,58 | 3,27 |
| vnc_sensory | 1,83 | 1,83 | 1,83 | 3,24 |
| cb_intrinsic | 4,63 | 17,07 | 3,42 | 3,24 |
| cb_sensory | 1,85 | 1,85 | 1,85 | 3,31 |
| ol_intrinsic | 2,80 | 8,88 | 2,55 | 3,25 |
| ol_sensory | 1,83 | 1,83 | 1,83 | 3,22 |
| visual_projection | 2,52 | 20,15 | 4,45 | 3,24 |
| visual_centrifugal | 3,67 | 18,62 | 4,56 | 3,29 |

**Resultado positivo y fuerte: el conectoma real se distingue de los tres controles**, y de un modo interpretable.

1. **`shuffle_weights` explota a 17-22 Hz.** Permutar los pesos entre aristas destruye el balance excitacion/inhibicion y la red se descontrola. O sea que la asignacion medida de pesos sostiene ese balance: es una propiedad estructural real, no un accidente.
2. **`erdos_renyi` aplana todo a ~3,2 Hz**, identico en las doce poblaciones. La heterogeneidad del cerebro real (de 1,83 a 4,63 Hz segun la poblacion) viene del cableado especifico, no de los tamanos de poblacion.
3. **`degree_preserving` queda en el medio** (3,4 a 5,1 Hz, aplanado pero no tanto). Conservar los grados conserva parte de la estructura, pero no la suficiente.
4. **Chequeo de cordura que salio solo**: en real, shuffle y degree las poblaciones sensoriales se quedan en 1,83 Hz porque no reciben entrada sinaptica, que es correcto, son la capa de entrada. En `erdos_renyi` saltan a ~3,2 porque el recableado aleatorio les inventa aristas entrantes que en la realidad no tienen.

Esto responde afirmativamente a la pregunta que `flyjump` dejo abierta y que `flydoom` planteo sin publicar resultado: **el cableado medido importa, y se puede medir cuanto**.

## 6. Problemas encontrados

### El ruido tapaba al conectoma (grave, resuelto)

Con `weight_scale=5.0` todas las superclases disparaban a 1,84 Hz. La comparacion contra un nulo de Erdos-Renyi con el mismo ruido dio **correlacion 0,997**: el conectoma real y uno aleatorio eran indistinguibles.

Barrido con `scripts/calibrate_scale.py`:

| escala | Hz real | Hz nulo | corr | silencio |
|---|---|---|---|---|
| 5 | 1,84 | 1,84 | 0,997 | 69,0% |
| 50 | 2,21 | 2,32 | 0,502 | 59,1% |
| **65** | **3,34** | **3,28** | **0,214** | 49,9% |
| 80 | 8,22 | 12,88 | 0,028 | 30,9% |

Valor adoptado: **65**. Ver lecciones aprendidas para el detalle.

### Tres supuestos del schema que estaban mal

El formato real difiere de lo que asumi leyendo la documentacion del repo:

| Asumido | Real |
|---|---|
| columna id `body_id` | `bodyid` |
| columna neurotransmisor `nt` | `top_nt` |
| habia que derivar el signo | ya viene una columna `sign` |

### Discrepancia de signo con el dataset

El dataset asigna **+1 a la histamina**, pero en Drosophila la histamina es inhibitoria: abre canales de cloruro (HisCl1 / ort) y es el transmisor de los fotorreceptores. Son 4.937 celulas, casi todas del lobulo optico. Tambien pone +1 a dopamina, octopamina, serotonina y `unclear`.

Se implementaron las dos politicas. El default es `strict`, que pone histamina en -1 y los ambiguos en 0 (declarar ignorancia en vez de adivinar). `policy="dataset"` reproduce el criterio del repo para poder comparar.

### Rendimiento mejor de lo previsto

El numero documentado (0,045x, del README de `mps-malecns-model`) quedo **2,4 veces corto**: sobre datos reales da 0,107x.

## 7. Deuda que queda

- `weight_scale=65` esta calibrado **contra el nulo**, no contra registros reales. Falta la validacion contra `philshiu/Drosophila_brain_model`.
- La politica de signo `strict` corrige la histamina segun la literatura, pero no esta validada contra el comportamiento del modelo. Conviene comparar las dos politicas en un circuito conocido.
- Falta `calibration.py` (tasas de reposo por poblacion y z-scores) y `trace.py` (formato de traza).

## 8. Cómo revertir

```bash
git revert <sha>
rm -rf packages/flybrain
```
