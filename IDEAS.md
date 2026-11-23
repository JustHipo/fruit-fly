# Fruit Fly Brain: ideas de experimentación

Documento de referencia sobre el proyecto: usar el conectoma completo del cerebro de la mosca de la fruta (mapeo de Janelia/Google del cerebro macho, ~166.000 neuronas y 11.691 tipos celulares; y el conectoma FlyWire del cerebro hembra, Princeton/Seung Lab) como sustrato de simulación para experimentos creativos.

## Contexto técnico compartido

Todas las ideas parten de la misma base:

1. **Datos**: el conectoma es un grafo dirigido y con pesos (número de sinapsis por par de neuronas, con signo excitatorio/inhibitorio inferido). Fuentes públicas: FlyWire Codex (codex.flywire.ai), neuPrint (neuprint.janelia.org), librerías `navis` y `connectome-interpreter` en Python.
2. **Simulación**: el grafo se convierte en una red neuronal simulable, típicamente con neuronas leaky integrate-and-fire (LIF) o modelos de tasa. Proyectos de referencia: `flyvis` (Janelia/Turaga lab, sistema visual del lóbulo óptico entrenado con deep learning) y el modelo whole-brain LIF de Shiu et al. 2024.
3. **Entrada/salida**: se elige un subconjunto de neuronas sensoriales como entrada (inyección de estímulo artificial) y un subconjunto de neuronas motoras o de una capa intermedia como salida (lectura de actividad).
4. **Aprendizaje**: la topología del conectoma queda fija (es el dato biológico real); lo que se entrena es una capa de lectura y/o los pesos, vía backpropagation con gradientes sustitutos para spikes, algoritmos evolutivos, o aprendizaje por refuerzo. Este patrón es análogo a *reservoir computing* / *echo state networks*.

---

## Ideas activas

Las dos ideas activas se separaron en **dos proyectos independientes**, porque la idea 4 creció de alcance y ya no comparte casi nada con la idea 3 más allá del simulador de cerebro.

| Proyecto | Documento | Estado |
|---|---|---|
| Mosca que pinta (idea 3) | [art-fly/ARQUITECTURA.md](art-fly/ARQUITECTURA.md) | Documentación técnica completa |
| Mosca que opera un DAW (idea 4) | [music-fly/ARQUITECTURA.md](music-fly/ARQUITECTURA.md) | Documentación técnica completa |

### Idea 3: Arte generativo a partir de la actividad del conectoma

**Alcance revisado (2026-09-14)**: la mosca no camina, queda fija (preparación tethered) y pinta moviendo las patas sobre un lienzo que se desplaza debajo. Ver [art-fly/ARQUITECTURA.md](art-fly/ARQUITECTURA.md) sección 6.4. Lo que sigue es la descripción original.

**Nivel alto**: dejar que la dinámica simulada del cerebro de la mosca "pinte" un canvas. La versión simple es arte abstracto puro, dirigido solo por la dinámica interna de la red y ruido de entrada. La versión extendida acepta un concepto o imagen de referencia y trata de acercar la salida visual a ese concepto, sin buscar ser el mejor generador de imágenes, solo un resultado entretenido y con identidad propia (más cercano a arte generativo/sonificación visual que a un modelo de imagen convencional).

**Nivel técnico**:

- **Simulación base**: cargar el conectoma (subconjunto manejable, por ejemplo el sistema visual/lóbulo óptico vía `flyvis`, o una porción del cerebro central) y correrlo como red LIF en PyTorch. Alimentar con ruido gaussiano o señales periódicas como estímulo de entrada continuo.
- **Mapeo a canvas (versión abstracta)**: elegir un grupo de neuronas de salida (por ejemplo, un conjunto de neuronas motoras o de una capa intermedia con actividad rica) y mapear su tasa de disparo/potencial de membrana a canales de color (HSV o RGB) y posición/trazo en el canvas. Iterar en el tiempo para construir la imagen frame a frame (similar a un sintetizador visual reactivo).
- **Condicionamiento por concepto (versión extendida)**:
  - Traducir una palabra o imagen de referencia a un vector con un modelo de embeddings tipo CLIP.
  - Inyectar ese vector como sesgo/estímulo adicional sobre las neuronas de entrada de la red simulada (en vez de solo ruido).
  - Entrenar una capa de lectura pequeña (o ajustar pesos de una porción acotada de la red) con una función de pérdida basada en similitud CLIP entre la imagen resultante y el concepto objetivo, usando optimización sin gradiente (CMA-ES, evolución) dado que la simulación de spikes puede no ser directamente diferenciable extremo a extremo.
- **Herramientas**: `flyvis`, `connectome-interpreter`, PyTorch, `open_clip` o CLIP de OpenAI, Pillow/canvas HTML5 o `p5.py` para el render.
- **Complejidad**: baja para la versión abstracta (prototipo en un fin de semana), media-alta para la versión condicionada por concepto (el entrenamiento de la capa de lectura contra CLIP es la parte no trivial).
- **Riesgos**: la simulación completa del conectoma (166k neuronas) puede ser costosa computacionalmente; conviene arrancar con un subconjunto (por ejemplo solo el sistema visual, que ya viene empaquetado y validado en `flyvis`).

### Idea 4: Mosca que opera un DAW en vivo

**Alcance revisado (2026-09-14)**: la idea original era sonificación MIDI. Se amplió a algo bastante más ambicioso: una mosca visible en pantalla que, en una sección contigua, **manipula un DAW real en vivo** usando su API, agregando y quitando pistas, moviendo clips y cambiando parámetros. Ver [music-fly/ARQUITECTURA.md](music-fly/ARQUITECTURA.md). Lo que sigue es la descripción original de la sonificación, que queda como la capa más simple de ese proyecto.

**Nivel alto**: traducir la actividad neuronal simulada del conectoma en eventos musicales (notas, velocidad, timing) enviados en vivo a un DAW. No se le pide a la red que "componga" con criterio musical, se sonifica su dinámica directamente, con la opción de agregar estructura (escalas, cuantización rítmica) por encima para que suene menos a ruido puro.

**Nivel técnico**:

- **Simulación base**: igual que en la idea 3, correr el conectoma (o un subconjunto) como red LIF, alimentada con ruido o estímulos artificiales continuos.
- **Extracción de eventos**: detectar picos ("spikes") de un grupo de neuronas de salida. Cada spike de una neurona específica dispara un evento MIDI: nota (mapeada por ejemplo por identidad o tipo de neurona), velocidad (mapeada por la magnitud del potencial o frecuencia de disparo reciente), duración/timing (mapeado por el intervalo entre spikes).
- **Ruteo a DAW**: en macOS, usar el IAC Driver (puerto MIDI virtual nativo del sistema, en Audio MIDI Setup) como puente. Desde Python, la librería `mido` (o `python-rtmidi`) envía mensajes MIDI al puerto IAC. Cualquier DAW (Ableton Live, Logic, Reaper, Bitwig) puede recibir esa entrada como si fuera un controlador MIDI más, sin necesidad de una API propietaria del DAW.
- **Capa musical opcional**: cuantizar las notas generadas a una escala (por ejemplo pentatónica o modal) y a una grilla rítmica, para que el resultado sea más "musical" sin dejar de estar guiado por la actividad real de la red.
- **Herramientas**: `flyvis`/`connectome-interpreter` o simulación LIF propia, `mido`, IAC Driver (macOS), cualquier DAW con entrada MIDI estándar.
- **Complejidad**: baja-media. La parte de simulación es la misma que en la idea 3; la integración MIDI es la parte más simple y estandarizada de las cuatro ideas originales.
- **Riesgos**: mínimos comparado con las otras ideas; el mayor desafío es de diseño (elegir mapeos de spike a nota que resulten interesantes musicalmente, no técnico).

---

## Ideas archivadas (documentadas, no en desarrollo)

### Idea 1: Conectoma como Dungeon Master de un TTRPG (Dragonbane)

Idea descartada por malentendido de alcance: el conectoma de la mosca no tiene ninguna estructura análoga a procesamiento de lenguaje (sus entradas son sensoriales, sus salidas son motoras). No hay forma de que esta red "aprenda" un reglamento escrito ni genere narrativa coherente; esa tarea requiere un LLM, tecnología completamente distinta en escala y arquitectura. Como mucho, la actividad simulada del conectoma podría usarse como generador de números pseudoaleatorios con sabor biológico (por ejemplo, para tiradas de dados), mientras el LLM hace todo el trabajo real de DM. No se justifica como proyecto centrado en el conectoma.

### Idea 2: Optimización de combates de Beyblade

Idea viable pero donde el conectoma no aporta ventaja real. Lo que resuelve el problema (encontrar la mejor combinación de ataque/defensa/resistencia/tipo) es un algoritmo de búsqueda estándar (optimización bayesiana, algoritmo genético, o RL con cualquier red como política), combinado con un motor de física de cuerpo rígido (PyBullet o MuJoCo) para simular colisiones, momento angular y fricción con precisión suficiente. El conectoma podría usarse como "reservorio" fijo (caja negra con dinámica compleja) entrenando solo una capa de lectura encima, pero es un agregado cosmético, no esencial. La dificultad real del proyecto está en la física de la simulación, no en la parte neuronal. Los modelos 3D (por ejemplo de Sketchfab) sirven solo para visualización, no para la física, que necesita datos simplificados (masa, geometría de colisión, coeficientes).
