# Registro de migraciones

Índice permanente de todos los documentos de migración. **Esta tabla nunca se poda.**

Es lo que hace funcionar la Regla 0: antes de implementar cualquier cosa, buscar acá, recuperar los documentos que aparezcan y leerlos.

| Ticket | Título | Proyecto | Palabras clave | Recuperar |
|---|---|---|---|---|
| F2 | Cuerpo 3D, lienzo fisico, contacto real, primer video | art-fly | flybody, MuJoCo, IK redundante, limites articulares, alcance, tethered, freejoint, err_norm no reproducible, contacto boolean vs fuerza, impedancia, canvas_to_unit | `art-fly/docs/migraciones/F2-cuerpo-ik.md` |
| F1 | Decodificador de pluma y lienzo 2D | art-fly | pluma, trazo, lienzo, gaussiana, paleta, interpolacion, rebote, decodificador lineal | `art-fly/docs/migraciones/F1-decodificador-pluma.md` |
| F0 | Simulador LIF y carga del conectoma | packages/flybrain | LIF, index_add, MPS, chunks, retardo inhibitorio, signo neurotransmisor, histamina, weight_scale, controles de topologia, erdos-renyi, EMA, z-score, traza | `packages/flybrain/docs/migraciones/F0-simulador-lif.md` |
| F0 | Puente REAPER | music-fly | REAPER, ReaScript, python arm64, libpython, uv python install, defer loop, UDP listener, OBS, obs-websocket, GetSourceScreenshot, MCP, accessibility, WindowServer, Space | `music-fly/docs/migraciones/F0-puente-reaper.md` |
| F1 | Subgrafo motor en tiempo real | music-fly | subgrafo, motoneuronas, somaNeuromere, premotoras, descendentes, induced_subgraph, syncount vs inprop, socios presinapticos, chequeo de cordura | `music-fly/docs/migraciones/F1-subgrafo-motor.md` |
| F2 | La consola, primera version | music-fly | ConsoleDecoder, zona continua, escala pentatonica, compas, tempo, ReaSynth, composicion, cerebro congelado pendiente | `music-fly/docs/migraciones/F2-consola.md` |

Comando de recuperación para un documento ya borrado del árbol:

```bash
git log --all --oneline -- '**/FLY-NN-*.md'
git show <sha>:<ruta>
```
