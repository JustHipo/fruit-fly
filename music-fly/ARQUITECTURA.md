# Documentación técnica: mosca que opera un DAW

Proyecto hermano de [art-fly](../art-fly/ARQUITECTURA.md). Comparten el simulador de cerebro y la disciplina metodológica; el resto es distinto.

Origen: idea 4 de [IDEAS.md](../IDEAS.md), originalmente "sonificación MIDI". Alcance ampliado el 2026-09-14.

Estado: investigación de integración con DAW completada y verificada. Sin código escrito.
Fecha de investigación: 2026-09-14.

---

## 0. Resumen ejecutivo

Una mosca simulada a partir del conectoma real **opera una sesión de REAPER en vivo**: agrega y quita pistas, inserta y mueve clips, cambia parámetros de efectos. En pantalla se ven las dos cosas a la vez, la criatura y las consecuencias de lo que hace.

**Lo que reutilizamos**: el dataset MaleCNS, el cuerpo `flybody`, el simulador LIF del proyecto hermano, y el intérprete Python que REAPER ya embebe.

**Lo que construimos nosotros**: el listener dentro de REAPER, el protocolo de comandos, la superficie de control que las patas operan, el decodificador de actividad a operaciones de sesión, y el lazo sensorial de audio.

**Tres restricciones duras que definen la arquitectura**:

1. **Ableton Live no está soportado en macOS 26** (posición oficial de Ableton, febrero 2026). Esta máquina corre 26.6.2. Va REAPER.
2. **Esto es una performance en vivo**, así que exige tiempo real. El cerebro completo corre a 0,045x. Va subgrafo.
3. **La mosca no camina**, solo mueve las patas. Preparación tethered, igual que en el proyecto hermano.

---

## 1. Entorno local verificado

| Item | Valor |
|---|---|
| Chip | Apple M4 Pro |
| macOS | 26.6.2 (build 25G83) |
| Núcleos CPU | 12 (8 performance + 4 efficiency) |
| Núcleos GPU | 16, Metal 4 |
| RAM unificada | 24 GB |
| Python | 3.10.0, **3.12.14**, 3.13.11 |
| Node | v24.4.1 |
| Audio | ffmpeg 8.0 |

El detalle de hardware, la comparación contra una GPU NVIDIA y el presupuesto de disco están en [art-fly, secciones 1.1 y 1.2](../art-fly/ARQUITECTURA.md). Aplican igual acá.

Requisito extra de este proyecto: **REAPER 7.74 o superior** (junio 2026, Universal, Cockos declara soporte hasta macOS 26).

---

## 2. Decisión de DAW

### 2.1 Comparación

| | REAPER | Ableton Live | Bitwig |
|---|---|---|---|
| macOS 26 | **Soportado** | **No soportado** | Soportado |
| Control | **Python (CPython real)** | OSC, o TS/JS | Java, u OSC vía DrivenByMoss |
| Crear/borrar pistas | Sí | Sí | Sí |
| Mover clips | Sí | Sí | Sí |
| Parámetros de efectos | Sí | Sí | Sí |
| Transporte | Sí | Sí | Sí |
| Barrera de entrada | Licencia barata | Suite + beta cerrada | Licencia cara |

**REAPER**, por tres razones: único con soporte declarado en macOS 26 que además habla Python nativo, modelo de objetos completo de la sesión scriptable, y sin dependencia de programas beta cerrados.

### 2.2 Lo descartado, y por qué

**Ableton Extensions SDK** (`@ableton-extensions/sdk`), que es lo que usa `fly-lab`, es bastante más limitado de lo que sugiere el nombre:

- Beta pública desde junio 2026, **solo Live 12.4.5 Suite beta**, acceso vía Centercode.
- Los paquetes **no están en npm** (404 en el registro), se distribuyen como tarballs.
- Las extensiones **se invocan con clic derecho desde un menú contextual**. No arrancan solas ni por automatización.
- **Sin control de transporte.** No instancian plugins de terceros ni cambian ruteo.
- Detalle revelador: `fly-lab` igual necesita su propio puente CoreMIDI en Swift para emitir notas, porque el SDK no puede.

**AbletonOSC** ([github.com/ideoforms/AbletonOSC](https://github.com/ideoforms/AbletonOSC), 803 estrellas, activo a noviembre 2025) es el mejor camino para Ableton y expone el Live Object Model entero, incluido todo lo que necesitaríamos (`/live/song/create_midi_track`, `/live/clip_slot/create_clip`, `/live/clip/set/position`, `/live/device/set/parameter/value`). Queda como **plan B** si Ableton llega a macOS 26 o si el proyecto se mueve de máquina.

**`reapy`**, el wrapper pythónico de REAPER, está **abandonado**: último commit febrero 2021, último release diciembre 2020, 25 issues abiertos, y su propia documentación admite que "cerca de la mitad de la API de ReaScript tiene contraparte en reapy". El fork mantenido, `reapy-next` 0.10.1 (abril 2025), está probado contra REAPER 7.36 pero su autor declara tener "muy poco tiempo para armar la documentación". **No dependemos de ninguno**, ver 8.2.

**Bitwig** queda como plan C: confirma compatibilidad con macOS 26, y [DrivenByMoss](https://github.com/git-moss/DrivenByMoss) 26.6.2 agrega un servidor OSC amplio. Pero cualquier cosa que DrivenByMoss no exponga hay que escribirla en Java.

---

## 3. Decisiones de arquitectura

### 3.1 Tres procesos

```
┌──────────────────────┐   estado de     ┌──────────────────────┐
│  proceso simulación  │   la mosca      │   ventana de la      │
│  (Python 3.12)       │───────────────► │   mosca (MuJoCo)     │
│  cerebro + cuerpo    │                 └──────────────────────┘
│  + decodificador     │
└──────────┬───────────┘
           │ UDP localhost:9800  (lotes de comandos)
           ▼
┌──────────────────────────────────────┐
│  REAPER 7.74                         │
│  └─ fly_listener.py (defer loop)     │
│     drena el socket, ejecuta API     │
└──────────┬───────────────────────────┘
           │ nivel de mezcla (UDP 9801)
           └──────────────► de vuelta a la simulación (lazo cerrado, fase 3)
```

La simulación pesada corre **en proceso aparte**. Meter NumPy o torch dentro del intérprete de REAPER trabaría el defer loop y produciría cortes audibles en el transporte. Esto no es opcional.

### 3.2 Mosca fija, igual que en el proyecto hermano

**La mosca no camina.** Queda sujeta (preparación *tethered*) y solo mueve las patas. La justificación completa está en [art-fly 6.4](../art-fly/ARQUITECTURA.md): elimina el problema de la marcha que nadie del ecosistema resolvió, y reproduce el montaje experimental estándar de la neurociencia de Drosophila.

Acá tiene además una consecuencia de diseño feliz: una mosca fija con seis patas sobre una superficie **es literalmente un operador frente a una consola**. Ver sección 7.

### 3.3 Tiempo real obligatorio, y qué implica

Este proyecto es una performance en vivo, así que no admite el renderizado diferido que sí sirve para pintar.

| Cerebro | Velocidad | ¿Sirve acá? |
|---|---|---|
| Completo, 161k neuronas | 0,107x tiempo real (medido) | No |
| Subgrafo, 1k a 6k neuronas | Tiempo real holgado | **Sí** |

Va el subgrafo. Es la misma estrategia de `fly-lab` (1.045 neuronas, 17.224 aristas, subgrafo de patas de MaleCNS).

### 3.4 Presupuesto de latencia extremo a extremo

| Tramo | Latencia |
|---|---|
| Paso de simulación (subgrafo, 1 ms simulado) | < 1 ms |
| Decodificador a comando | despreciable |
| UDP localhost | < 0,1 ms |
| **Espera del defer tick de REAPER** | **16 a 33 ms** |
| Ejecución de la API en REAPER | < 1 ms por llamada |

El defer loop domina. Presupuesto realista: **20 a 40 ms** entre que la mosca "decide" y la sesión cambia. Perfectamente aceptable para operaciones de estructura (crear pistas, mover clips); sería audible si intentáramos disparar percusión así, razón por la cual las notas, si algún día las queremos, van por MIDI aparte y no por este camino.

---

## 4. Datos y subgrafo

### 4.1 Fuente

MaleCNS v1.0, igual que el proyecto hermano. Ver [art-fly sección 4](../art-fly/ARQUITECTURA.md) para descargas, formatos y licencia (CC-BY 4.0, citar el paper de Cell 2026-09-03).

Atajo: `git clone --depth 1 https://github.com/YijieYin/connectome_data_prep.git`, archivo `data/maleCNS/mcns_ad_inprop_all_neuron.npz`.

### 4.2 Selección del subgrafo motor

Copiar el método anatómico y determinista de `flyjump`, documentado en [art-fly 8.4](../art-fly/ARQUITECTURA.md). Lo esencial: **las células se eligen por conectividad medida, antes de entrenar nada**. Nunca porque funcionen bien, que es como se contamina un experimento.

Adaptación para nuestro caso, que es motor y no visual:

1. Partir de las **motoneuronas de pata del VNC** (neurómeros T1, T2, T3, que corresponden a patas delanteras, medias y traseras respectivamente). El MANC documenta que las motoneuronas de pata ocupan la capa ventral.
2. Subir hacia atrás: quedarse con las **neuronas premotoras** que más contactos hacen sobre esas motoneuronas.
3. Subir otro salto: las **neuronas descendentes** que más contactan a esas premotoras. El MANC advierte que las conexiones directas descendente-motoneurona son infrecuentes, así que el salto intermedio importa.
4. Retener **todas** las aristas medidas entre las células seleccionadas, incluidas recurrentes y de contacto único.

Objetivo de tamaño: 1.000 a 6.000 células. `fly-lab` funciona con 1.045.

---

## 5. Capa 1: simulación en tiempo real

Modelo LIF idéntico al del proyecto hermano ([art-fly sección 5](../art-fly/ARQUITECTURA.md)): tau_m 20 ms, V_rest -52 mV, V_thresh -45 mV, refractario 2,2 ms, retardo inhibitorio 4 ms, signo desde `body-neurotransmitters`.

Diferencias por ser tiempo real:

- **Tamaño**: subgrafo, no grafo completo. A esta escala corre en CPU sin problema; no hace falta MPS.
- **Reloj**: el bucle de simulación se ancla a un reloj monótono (`time.perf_counter`), no corre libre. Si un paso se atrasa, se saltea en vez de acumular deuda, porque en una performance importa más mantener el ritmo que simular cada milisegundo.
- **Salida**: z-scores poblacionales suavizados con EMA a ~25 ms, igual formato que el proyecto hermano.

### 5.1 Calibración

Obligatoria antes de decodificar nada, igual que en el proyecto hermano:

```python
def calibrate(sim, seconds=2.5):
    """Tasas de reposo por población, sin estímulo."""
    rates = collect_rates(sim, seconds)
    return rates.mean(axis=0), rates.std(axis=0) + 1e-6
```

Chequeo de cordura tomado de `infinite-sugar`: verificar que las motoneuronas elegidas reciben del orden de 1.800 a 3.200 sinapsis. Si reciben muchísimo menos, estamos decodificando ruido.

**Aclaración verificada en F1** ([music-fly/docs/migraciones/F1-subgrafo-motor.md](docs/migraciones/F1-subgrafo-motor.md)): este número es sobre **sinapsis físicas** (`mcns_ad_syncount_all_neuron.npz`), no sobre socios presinápticos distintos (`mcns_ad_inprop_all_neuron.npz`, que es lo que carga `flybrain.data.load_connectome` para el simulador). Contando socios distintos la mediana real es ~205, muy por debajo del rango — no es ruido, es una unidad distinta. Medir siempre contra `syncount` para este chequeo puntual.

---

## 6. Capa 2: cuerpo tethered

`flybody` en su propio entorno Python 3.10 (conflicto de numpy, ver [art-fly 3.2](../art-fly/ARQUITECTURA.md)).

La mosca queda fija. Los seis sitios de garra son los efectores:

```
claw_T1_left   claw_T1_right     patas delanteras
claw_T2_left   claw_T2_right     patas medias
claw_T3_left   claw_T3_right     patas traseras
```

La cinemática inversa (`qpos_from_site_xpos`) lleva cada garra a una coordenada objetivo dentro de su zona de alcance.

---

## 7. Capa 3: la consola

Esta es la sección con el problema de diseño real del proyecto.

### 7.1 El problema

El conectoma no tiene ningún concepto de pista, clip ni compás. Cualquier mapeo de actividad neuronal a operaciones de DAW lo inventamos nosotros. La pregunta no es si hay invención, la hay siempre, sino si la invención respeta lo que esos circuitos realmente hacen.

**Opción mala**: "si la población 7 supera umbral, agregar pista". Funciona, es trivial, y es indefendible: no hay razón alguna por la que esa población tenga que ver con crear pistas. Es el equivalente musical del hash de `fruit-fly-fashion` ([art-fly 2.3](../art-fly/ARQUITECTURA.md)).

### 7.2 La consola de seis patas

Como la mosca está fija y tiene seis patas que alcanzan zonas distintas, **la sesión se representa como una superficie física debajo de ella**, y cada pata opera una región:

```
                    🪰  mosca fija (tethered)
             ╱   ╱  │  ╲   ╲
            T1L T2L T3L T3R T2R T1R
        ┌─────────────────────────────┐
        │  T1 ▸ clips: posición XY     │   delanteras, trabajo fino
        │  T2 ▸ parámetros de efectos  │   medias, control continuo
        │  T3 ▸ mute / transporte      │   traseras, conmutación
        └─────────────────────────────┘
```

El mapeo es **continuo y con significado posicional**:

| Magnitud física de la pata | Significado en la sesión |
|---|---|
| Posición X de la garra en su zona | Posición temporal (compás) |
| Posición Y de la garra en su zona | Índice de pista |
| Contacto (garra toca la superficie) | Dispara la operación |
| Duración del contacto | Largo del clip |
| Velocidad de la garra al tocar | Intensidad, o valor del parámetro |

Por qué esto es defendible: usamos el **sistema motor de patas para posicionar en dos dimensiones**, que es exactamente lo que ese sistema hace en la mosca real. La interpretación de esa superficie como sesión musical es una capa de lectura encima, no una atribución falsa de intención musical al insecto.

### 7.3 Vocabulario de comandos

| Gesto de la pata | Comando | Efecto |
|---|---|---|
| T1 toca en zona vacía | `additem <pista> <pos>` | Insertar clip |
| T1 toca y arrastra | `moveitem <item> <pos>` | Mover clip |
| T1 toca borde superior | `addtrack <idx>` | Crear pista |
| T2 desliza en X | `fx <pista> <fx> <param> <v>` | Parámetro continuo |
| T3 toca | `mute <pista> <0/1>` | Silenciar/activar |
| T3 doble toque | `play` | Transporte |
| Ninguna pata toca | (nada) | Silencio, que también es decisión |

### 7.4 Decodificador

```python
class ConsoleDecoder:
    """z (n_pop,) -> objetivos de alcance por pata."""
    def __init__(self, n_pop, n_legs=6, seed=0):
        rng = np.random.default_rng(seed)
        self.W = rng.normal(0, 0.5, size=(n_legs * 3, n_pop))  # x, y, presion por pata
        self.b = np.zeros(n_legs * 3)

    def __call__(self, z):
        y = np.tanh(self.W @ z + self.b).reshape(-1, 3)
        return [
            {"x": remap(row[0], *ZONE_X[i]),
             "y": remap(row[1], *ZONE_Y[i]),
             "press": row[2] > 0.05}
            for i, row in enumerate(y)
        ]
```

Con `n_pop = 20` y seis patas son 18×20 + 18 = **378 parámetros**, que cae en el rango cómodo de CMA-ES.

Reglas heredadas del proyecto hermano, no negociables: continuo y monótono respecto de `z`, nada de hashes, rangos amplios, y el conectoma nunca se toca.

### 7.5 Elección por zona continua, nunca por menú

Aclaración de diseño (2026-09-16, discutida con el usuario) sobre cómo se resuelven decisiones de tipo "qué instrumento", "qué patrón", "qué perilla" sin violar 7.4.

**El riesgo**: cualquier decisión que suene a "elegir entre opciones" tienta a implementarla como `if poblacion > umbral: elegir opción 3`. Eso es exactamente el antipatrón de la sección 2.3 (el hash de `fruit-fly-fashion`): destruye la relación continua entre actividad y salida, y dos estados cerebrales casi idénticos podrían caer en opciones completamente distintas.

**La solución, ya usada en 7.2 y que se extiende a todo lo demás**: ninguna decisión es un menú. Es siempre una posición continua sobre una superficie que nosotros dividimos en zonas. La pata (o la coordenada decodificada que sea) se mueve de forma continua por la actividad real; en qué zona *cae* esa posición es la "elección", pero el movimiento que la lleva ahí nunca salta — es continuo y monótono respecto de `z`, igual que exige 7.4. Aplicado a instrumentos, patrones y perillas de plugins:

- **Instrumento**: no es un menú desplegable. Es una superficie dividida en zonas (como el panel de seis patas de 7.2); cada instrumento ocupa una región. La pata cae donde cae por su movimiento real, nunca por un umbral en una sola población.
- **Patrón MIDI (qué nota, cuándo)**: la posición continua decodificada se cuantiza a una escala y a una grilla rítmica que son nuestras (tabla 11.3), pero la posición en sí sigue siendo continua. El cerebro no "compone": se mueve, y el mapa que nosotros diseñamos convierte ese movimiento en algo dentro de una escala/ritmo coherente.
- **Perillas de plugins de terceros**: no se generaliza "qué hace la perilla X de este plugin" (imposible, cada uno es distinto). REAPER expone cualquier parámetro de cualquier plugin como un número continuo 0 a 1 (`TrackFX_SetParamNormalized`, ya probado en la Fase 0). Nosotros elegimos autoralmente cuántas y cuáles perillas exponerle a la mosca por instrumento; el valor que toma esa perilla sale de la superficie continua de siempre.

**Lo que sigue siendo nuestro, sin que el cerebro lo decida nunca**: el límite de notas por compás, si el compás es 4/4 o algo menos convencional, el tempo, la escala, qué perillas están expuestas. Coincide con la tabla de la sección 11.3: eso es exactamente lo que ya estaba marcado como autoral.

### 7.6 Asignación concreta de las seis patas (propuesta 2026-09-16, aprobada por el usuario)

| Pata | Rol | Qué decodifica |
|---|---|---|
| T1 izquierda | Nota | X = velocidad (remapeada 40-120), Y = grado de la escala (cuantizado) |
| T1 derecha | Duración | Cuadros consecutivos de contacto = largo de la nota, en pasos de grilla |
| T2 izquierda | Instrumento | X cuantizado a zonas, una por pista de la paleta |
| T2 derecha | Perillas | X/Y = dos parámetros continuos del instrumento activo (diferido, ver deuda de F2) |
| T3 izquierda | Mute | Y = qué pista, contacto = toggle (diferido, ver deuda de F2) |
| T3 derecha | Forma | X = compás (zona entre una paleta chica), Y = tempo (remapeado a 80-160bpm) |

Paleta de arranque: dos pistas de `ReaSynth` (el único instrumento nativo de REAPER que no depende de una muestra externa, ya probado en F0), una como registro grave y otra como agudo — no son dos timbres distintos, es la misma síntesis en dos registros, declarado así para no exagerar la variedad real disponible. Escala: pentatónica mayor. Compases de la paleta: 4/4, 3/4, 5/8, 7/8, expresados como pasos de grilla por compás (8/6/5/7) en vez de tiempo musical completo, simplificación deliberada para la primera versión.

Límite de notas por compás: cooldown físico sobre la pata T1 izquierda (no un conteo que "decida" el cerebro), igual de espíritu al periodo refractario que ya tiene el simulador LIF a nivel de neurona.

---

## 8. Capa 4: el puente REAPER

### 8.1 Cómo funciona Python dentro de REAPER

REAPER **no trae intérprete**: hace `dlopen` de una `libpython3.x.dylib` del sistema que uno le indica. Adentro corre **CPython real con toda la biblioteca estándar**, así que un script puede `import socket`. Ese hecho es lo que habilita toda la arquitectura.

Configuración en Apple Silicon:

```
Preferences > Plug-ins > ReaScript > Enable Python
  ruta:  /opt/homebrew/opt/python@3.12/Frameworks/Python.framework/Versions/3.12/lib
  dylib: libpython3.12.dylib
```

**Trampa crítica**: REAPER y Python tienen que ser **ambos arm64**. Un Python arm64 de Homebrew con un REAPER Intel bajo Rosetta **falla en silencio**, sin mensaje útil.

### 8.2 El listener

El patrón correcto **no es** una librería externa manejando REAPER (eso es lo que hace `reapy` y por eso es lento), sino **un listener persistente que escribimos nosotros y vive adentro de REAPER**.

```python
# fly_listener.py - se lanza una vez adentro de REAPER y queda corriendo
import socket
from reaper_python import *

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("127.0.0.1", 9800))
sock.setblocking(False)

def tick():
    while True:                        # drenar TODA la cola por tick
        try:
            cmd = sock.recv(4096).decode().split()
        except BlockingIOError:
            break

        if cmd[0] == "addtrack":
            RPR_InsertTrackAtIndex(int(cmd[1]), True)

        elif cmd[0] == "additem":
            tr = RPR_GetTrack(0, int(cmd[1]))
            it = RPR_AddMediaItemToTrack(tr)
            RPR_SetMediaItemInfo_Value(it, "D_POSITION", float(cmd[2]))
            RPR_SetMediaItemInfo_Value(it, "D_LENGTH", float(cmd[3]) if len(cmd) > 3 else 2.0)

        elif cmd[0] == "moveitem":
            it = RPR_GetMediaItem(0, int(cmd[1]))
            RPR_SetMediaItemInfo_Value(it, "D_POSITION", float(cmd[2]))

        elif cmd[0] == "fx":           # parametro normalizado 0..1
            tr = RPR_GetTrack(0, int(cmd[1]))
            RPR_TrackFX_SetParamNormalized(tr, int(cmd[2]), int(cmd[3]), float(cmd[4]))

        elif cmd[0] == "mute":
            RPR_SetMediaTrackInfo_Value(RPR_GetTrack(0, int(cmd[1])), "B_MUTE", float(cmd[2]))

        elif cmd[0] == "play":
            RPR_OnPlayButton()

    RPR_UpdateArrange()
    RPR_defer("tick()")

tick()
```

Del lado de la simulación:

```python
import socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
DAW = ("127.0.0.1", 9800)

def send_batch(cmds):
    for c in cmds:
        sock.sendto(c.encode(), DAW)

send_batch(["addtrack 0", "additem 0 4.0 2.0"])
```

Superficie completa de la API (pistas, items, takes, envolventes, efectos, transporte, ruteo, marcadores) en [reascripthelp.html](https://www.reaper.fm/sdk/reascript/reascripthelp.html).

### 8.3 La restricción de rendimiento que define el diseño

Los scripts diferidos de REAPER corren a **30 a 60 iteraciones por segundo**. Ese es el techo de ida y vuelta.

`reapy` paga ese costo **por llamada**, que es la razón real de su lentitud. Nuestro listener lo paga **por lote**: drena la cola entera del socket en cada tick, así entran cientos de llamadas a la API por frame.

**Regla de diseño**: la simulación acumula intenciones y las manda en lote; el listener las drena todas por tick. Nunca un comando por paquete esperando confirmación.

### 8.4 Por qué el OSC de REAPER no alcanza

REAPER tiene OSC, pero tiene forma de superficie de control (mezclador, parámetros de efectos, atajos de acciones), configurado con un `Default.ReaperOSC` editable. **No puede crear pistas ni mover items.** Sirve para transporte y mezcla; para estructura va el socket.

---

## 9. Capa 5: lazo cerrado sensorial

Fase 3 del plan. La mosca reacciona a lo que produjo.

Camino: REAPER expone el nivel de la mezcla (`RPR_Track_GetPeakInfo` sobre el master), el listener lo emite por UDP al puerto 9801, y la simulación lo convierte en estímulo inyectado sobre neuronas sensoriales.

Dos rutas de inyección, ambas biológicamente plausibles:

- **Mecanosensorial**: el nivel de la mezcla como vibración. Es la más honesta, porque las moscas sí detectan vibración, y el sonido fuerte en un insecto es, literalmente, vibración.
- **Visual**: mapear el espectro a luminancia sobre el modelo de ojo compuesto. Requiere el sistema visual, que es mucho más caro de simular.

Empezar por mecanosensorial.

**Riesgo específico del lazo cerrado**: puede oscilar (la mosca sube todo hasta saturar) o estancarse (silencio absoluto, que es un atractor estable y aburrido). Mitigación: arrancar en lazo abierto, cerrar despacio, y poner límites duros en el decodificador.

---

## 10. Visualización

**Ventana MuJoCo** (`mjpython`), reutilizando el cuerpo de `flybody`. Ventaja: mismo stack que el proyecto hermano, cuerpo anatómicamente correcto. Es el camino recomendado para empezar.

**Pet de escritorio**, siguiendo [DenisSergeevitch/desktop-fly](https://github.com/DenisSergeevitch/desktop-fly), que combina circuitos spiking de FlyWire con un extracto cerebro-a-pata de MaleCNS y tiene port a Electron. La mosca queda flotando sobre el escritorio, encima de REAPER, que es visualmente más cercano a la visión original. Evaluarlo cuando el resto funcione. Hay ports a Linux (`gnat`, `desktop-fly-linux`) que documentan la arquitectura.

Layout objetivo:

```
┌───────────────────────┬──────────────────────────────────┐
│   ventana de la mosca │  REAPER en vivo                  │
│   (+ la consola       │  ┌────────────────────────────┐  │
│    vista desde arriba)│  │ Track 1  ▓▓▓░░▓▓░░░        │  │
│                       │  │ Track 2  ░░▓▓▓▓░░░▓▓       │  │
│   🪰                   │  │ Track 3  ▓░░░░▓▓▓░░        │  │
└───────────────────────┴──────────────────────────────────┘
```

---

## 11. Controles de honestidad

Aplican los mismos que en [art-fly sección 10](../art-fly/ARQUITECTURA.md), sin excepción. Resumidos:

### 11.1 Test de cerebro congelado (el más importante)

`fly-craftax` entrenó un readout con PPO sobre un cerebro congelado y descubrió, al apagarle la visión, que su política **ignoraba al cerebro por completo**: había aprendido una secuencia casi de lazo abierto.

**Test obligatorio en cada sesión grabada**: reproducir con el vector `z` fijo en su media, y con `z` reemplazado por ruido de igual media y varianza. Si la sesión resultante suena igual, el decodificador está ignorando al cerebro.

### 11.2 Controles de topología (diseño de flydoom)

Tres controles, mismo presupuesto de entrenamiento, varias semillas:

| Control | Preserva | Destruye |
|---|---|---|
| `erdos_renyi_matched` | N y E exactos, pesos permutados | Toda la topología |
| `degree_preserving_rewire` | Grados de entrada y salida | Patrón de conexión |
| `shuffle_weights` | Topología | Solo los pesos |

Grabar una sesión con cada uno y compararlas.

### 11.3 Declaración de lo autoral

| Del conectoma | Nuestro |
|---|---|
| Trayectoria de las patas sobre la consola | Mecánica de articulación de la pata |
| Timing de las operaciones | Vocabulario de comandos y layout de la consola |
| Reacción al nivel de la mezcla | Instrumentos, efectos, escala, tempo |

---

## 12. Plan de fases

### Fase 0: puente REAPER
Configurar Python 3.12 arm64 en REAPER, escribir `fly_listener.py`, verificar que un proceso externo crea pistas y mueve clips. Medir el ritmo real del defer loop.
**Entregable**: script externo que construye una sesión de 4 pistas.
**Riesgo**: bajo. Cuidado con la trampa de arm64.

### Fase 1: subgrafo en tiempo real
Seleccionar el subgrafo motor con el método anatómico, correrlo en tiempo real, calibrar, emitir z-scores.
**Entregable**: traza en vivo a ~40 Hz.
**Riesgo**: bajo.

### Fase 2: consola y vocabulario
Cuerpo tethered en flybody, zonas de alcance por pata, decodificador, mapeo de contacto a comando.
**Entregable**: la mosca construye una sesión sola.
**Riesgo**: **medio-alto.** Acá está todo el diseño no resuelto, y la calidad del resultado depende enteramente del layout de la consola. Presupuestar iteración.

### Fase 3: lazo cerrado
Nivel de mezcla como estímulo mecanosensorial.
**Entregable**: performance autosostenida.
**Riesgo**: medio-alto. Puede oscilar o estancarse.

### Fase 4: presentación
Layout de pantalla, opcionalmente pet de escritorio, grabación.
**Riesgo**: bajo.

---

## 13. Instalación

```bash
# ---------- entorno "brain" (compartido con el proyecto hermano) ----------
uv venv --python 3.12 .venv-brain
source .venv-brain/bin/activate
pip install torch numpy scipy pandas pyarrow
pip install "cma[plotting]"

# ---------- entorno "body" ----------
uv venv --python 3.10 .venv-body
source .venv-body/bin/activate
uv pip install "flybody @ git+https://github.com/TuragaLab/flybody.git"  # NO esta en PyPI

# ---------- REAPER ----------
brew install --cask reaper
brew install python@3.12     # necesario: REAPER carga la dylib del sistema
# luego, dentro de REAPER:
#   Preferences > Plug-ins > ReaScript > Enable Python
#   ruta:  /opt/homebrew/opt/python@3.12/Frameworks/Python.framework/Versions/3.12/lib
#   dylib: libpython3.12.dylib

# verificar arquitectura (ambos deben decir arm64)
file /Applications/REAPER.app/Contents/MacOS/REAPER | grep -o 'arm64\|x86_64'
file /opt/homebrew/opt/python@3.12/Frameworks/Python.framework/Versions/3.12/lib/libpython3.12.dylib | grep -o 'arm64\|x86_64'
```

---

## 14. Riesgos abiertos

| Riesgo | Impacto | Mitigación |
|---|---|---|
| **El decodificador aprende a ignorar el cerebro** | **Alto, existencial** | Test de `z` congelado en cada sesión (11.1). Le pasó a fly-craftax |
| El layout de consola resulta arbitrario igual | Alto, conceptual | Es el trabajo de la fase 2. Iterar con los controles puestos |
| El defer loop a 30-60 Hz se siente entrecortado | Medio | Lotes por tick, nunca un comando por paquete |
| La sesión resultante es ruido, no música | Medio | Riesgo artístico legítimo. Acotar vocabulario e instrumentos |
| REAPER y Python desalineados en arquitectura | Bajo | Verificar arm64 en ambos antes de nada. Falla en silencio |
| Lazo cerrado inestable | Medio-alto | Empezar en lazo abierto, límites duros en el decodificador |
| Ableton nunca llega a macOS 26 | Bajo | Ya decidido: REAPER. AbletonOSC es el plan B |

---

## 15. Referencias

**REAPER**
- [ReaScript](https://www.reaper.fm/sdk/reascript/reascript.php) y [referencia de la API](https://www.reaper.fm/sdk/reascript/reascripthelp.html)
- [OSC en REAPER](https://www.reaper.fm/sdk/osc/osc.php)
- [Configuración de Python en Apple Silicon](https://gist.github.com/rewgs/04c6ad63f8ca5bac0b4a66fc73146538)

**Alternativas**
- [AbletonOSC](https://github.com/ideoforms/AbletonOSC) y su [paper en NIME 2023](https://nime.org/proceedings/2023/nime2023_60.pdf)
- [Ableton Extensions SDK](https://ableton.github.io/extensions-sdk/)
- [Compatibilidad de Live con macOS](https://help.ableton.com/hc/en-us/articles/115001261150-Mac-Compatibility-Guide-for-Ableton-Live)
- [DrivenByMoss](https://github.com/git-moss/DrivenByMoss) para Bitwig

**Arte previo**
- [Apolotary/fly-lab](https://github.com/Apolotary/fly-lab) (MIT)
- [DenisSergeevitch/desktop-fly](https://github.com/DenisSergeevitch/desktop-fly)

**Conectoma**: ver [art-fly sección 14](../art-fly/ARQUITECTURA.md).
