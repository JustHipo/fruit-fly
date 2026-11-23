# F1: decodificador de pluma y lienzo 2D

| | |
|---|---|
| Ticket | (sin clave, se trabaja standalone) |
| Proyecto | art-fly |
| Rama | `feat/f0-flybrain-fundacion` |
| Fase | F1 |
| Fecha | 2026-09-14 |
| Impacto | 🟡 aditivo |

## 1. Qué se hizo

Paquete `artfly`, primera salida visual del proyecto:

- `pen.py`: `PenDecoder` (z-scores a parametros de trazo) y `Stroke`.
- `color.py`: dos fuentes de color. `PopulationColor` deriva matiz, saturacion y brillo del cerebro; `BandPalette` conserva la banda autoral como control.
- `canvas.py`: lienzo RGB con deposicion gaussiana, `Pen` con posicion integrada, y `paint()` con interpolacion en sub-pasos.
- `pixel.py`: `PixelCanvas`, render alternativo en pixel art con grilla discreta, sin antialiasing y paleta cuantizada de 8 colores.
- `render.py`: selector entre los dos modos.
- `scripts/paint.py`: pinta desde una traza, con `--render continuo|pixel`.
- `scripts/compare_controls.py`: pinta el real y los tres controles con el mismo decodificador. `--reuse-traces` repinta trazas ya grabadas sin resimular, que tarda 0 s en vez de 10 minutos.

## 2. Por qué

**Decodificador lineal con tanh, no algo mas expresivo.** Con 12 poblaciones son 78 parametros, que cae comodo en el rango de CMA-ES para la fase 3. Un decodificador mas grande podria generar imagenes lindas ignorando la entrada, que es justo la falla que documenta `fly-craftax`.

**Interpolacion en sub-pasos.** La traza se muestrea a 40-100 Hz, pero depositar pintura solo en los puntos decodificados deja manchas sueltas en vez de trazos. La pluma se mueve de forma continua entre objetivos y deposita en cada sub-paso.

**La pluma rebota en los bordes en vez de recortarse.** Recortar deja la pluma pegada al borde generando una linea recta artificial que no sale del cerebro.

**Paleta fija por pieza.** Sin eso la salida es ruido multicolor sin identidad. El matiz decodificado se mapea a un rango acotado alrededor de un centro.

**Rangos visuales amplios** (ancho de 0,004 a 0,020, alfa de 0,25 a 0,95). Es la correccion explicita al error de `fruit-fly-fashion`, que uso rangos tan angostos que su salida era indistinguible de la imagen semilla.

## 3. Archivos tocados

| Archivo | Cambio |
|---|---|
| `art-fly/pyproject.toml` | Nuevo |
| `art-fly/artfly/pen.py` | Nuevo, decodificador |
| `art-fly/artfly/canvas.py` | Nuevo, lienzo y deposicion |
| `art-fly/artfly/__init__.py` | Nuevo |
| `art-fly/scripts/paint.py` | Nuevo |
| `art-fly/scripts/compare_controls.py` | Nuevo, control de honestidad |
| `packages/flybrain/scripts/record_trace.py` | `--sample-every` parametrizable |

## 4. Validación

Primera pieza generada desde una traza real de 2 s (80 frames): 39 trazos con pluma abajo, 9,9% del lienzo pintado. El mecanismo funciona: trazos continuos con ancho y color variables dentro de la paleta.

Comparacion contra los tres controles: ver seccion 5.

## 5. Controles corridos

`scripts/compare_controls.py` genera las cuatro condiciones con decodificador, paleta, semilla y duracion identicos. Lo unico que cambia es el grafo.

Corrida del 2026-09-14: 12 s simulados por condicion, muestreo a 100 Hz, 1.200 trazos cada una.

| condicion | pluma abajo | tinta | **std de z** |
|---|---|---|---|
| **real** | 42% | 492.056 | **2,217** |
| shuffle_weights | 44% | 1.062.511 | 1,014 |
| degree_preserving | 44% | 883.235 | 1,263 |
| erdos_renyi | 61% | 479.834 | 1,019 |

**Resultado: las cuatro piezas son claramente distinguibles a simple vista, y la diferencia es interpretable.**

El conectoma real **ocupa todo el lienzo**, con marcas variadas, trazos finos mezclados con manchas, y verdes y cianes apareciendo entre los violetas. Los tres controles **se hunden contra el borde inferior** y se amontonan ahi.

La causa esta en la columna de la derecha: **el real tiene mas del doble de rango dinamico en la actividad poblacional** (std de z 2,22 contra 1,01-1,26). Con menos variacion en z, la salida del tanh se estanca cerca de un valor constante, asi que `dy` adquiere un sesgo persistente y la pluma deriva siempre hacia el mismo lado hasta chocar el fondo. La dinamica mas rica del conectoma real la hace cambiar de direccion y explorar.

Dicho de otro modo: **el cableado medido produce exploracion espacial; los grafos degradados producen deriva y colapso**.

Notar tambien que `shuffle_weights` deposita el doble de tinta (1.062.511) en mucho menos area: es la misma explosion de actividad a 17-22 Hz que se habia medido a nivel de simulador en F0, ahora visible como una mancha densa.

**Salvedad honesta**: la diferencia en cobertura del lienzo esta mediada por el comportamiento de deriva de *este* decodificador, que tiene pesos aleatorios sin entrenar. Un decodificador entrenado podria comportarse distinto. Lo que no depende del decodificador es la diferencia de std en z, que ocurre en el cerebro y no en la pluma.

## 6. Problemas encontrados

Ninguno bloqueante. La primera pieza salio rala porque la traza era de 2 s; se resuelve con trazas mas largas y mayor tasa de muestreo (`--sample-every 10` da 100 Hz).

## 7. Deuda que queda

- El decodificador no esta entrenado: los pesos son aleatorios con semilla fija. Eso es F3.
- La paleta esta elegida a mano, no sale del cerebro. Declarado en la tabla de lo autoral.
- Falta explorar si conviene que el ancho de trazo dependa tambien de la velocidad de la pluma, que es lo que haria un pincel real.
- ~~El color es mayormente autoral~~ **Resuelto el 2026-09-14**: los tres canales salen del cerebro via `PopulationColor`. Queda autoral solo que poblacion ocupa que ranura del circulo, o sea una rotacion. Ver ARQUITECTURA.md 7.2.
- **La presion es una ilusion**: sale de ancho mas opacidad decodificados mas la caida gaussiana, no de fisica. En F2 deberia salir de la fuerza de contacto en MuJoCo.

## 8. Cómo revertir

```bash
git revert <sha>
rm -rf art-fly/artfly art-fly/scripts art-fly/pyproject.toml
```


---

## Actualización 2026-09-15: ¿más tiempo cubre más lienzo?

Pregunta del usuario tras ver una imagen vieja (de la primera prueba de 2 segundos) que parecía muy rala. Se midió en vez de suponer.

**Primero, un chequeo sobre el recorrido real de la pluma** con la traza de 12 s: toca los cuatro bordes del lienzo (x e y van de 0 a 1), así que sí explora todo el espacio disponible. Pero el tiempo con la pluma abajo se concentra de forma pareja solo en apariencia: un histograma 2D de densidad mostró celdas con más de 10 veces la densidad de otras. Es una propiedad esperable de una caminata aleatoria con dirección persistente (el `PenDecoder` sin entrenar), no un error.

**Comparación real, 12 s contra 40 s** (misma semilla, mismo decodificador):

| Traza | Trazos | Celdas de una grilla 20x20 tocadas | Píxeles no blancos |
|---|---|---|---|
| 12 s | 1.200 | 370/400 (92%) | 68,5% |
| 40 s | 4.000 | 349/400 (87%) | 77,4% |

**Conclusión, con números**: la cobertura de *área* ya satura cerca de los 12 segundos (92%, y a 40 s incluso baja levemente a 87%, dentro del ruido de qué celdas puntuales se tocan). Lo que sigue creciendo con más tiempo es la *densidad*: más tinta depositada sobre las mismas zonas, no área nueva. Ambas trazas dejan sin tocar la misma franja diagonal arriba-izquierda, que es donde la caminata simplemente no fue en ninguna de las dos duraciones.

**Implicación práctica**: para el propósito de "cubrir el lienzo", no hace falta grabar trazas más largas que unos 10-15 segundos; el efecto de más tiempo es una obra más densa/saturada, no más extendida. Si en algún momento se quisiera cobertura más pareja sin más densidad, habría que actuar sobre el decodificador (por ejemplo, un término que penalice revisitar zonas ya densas), no sobre la duración de la traza.

Imágenes: `docs/imagenes/f1-cobertura-12s.png`, `docs/imagenes/f1-cobertura-40s.png`.
