# Backlog

Listo para cargar en Jira una vez configurado el MCP personal. Proyecto **`FLY`**.

Jerarquía: Epic > Story > Subtask. Cada subtask equivale a un commit.

---

## EPIC 1 · Fundación compartida (`packages/flybrain`)

Prerequisito de todo lo demás. Fase F0.

### Story 1.1 · Obtención y preparación de datos del conectoma
- Clonar `connectome_data_prep` y verificar integridad de los `.npz`
- Cargar matriz MaleCNS y metadatos de neuronas en memoria
- Derivar signo excitatorio/inhibitorio desde `body-neurotransmitters`
- Documentar licencia CC-BY y la cita obligatoria

### Story 1.2 · Simulador LIF
- Implementar paso LIF vectorizado con `gather` + `index_add_`
- Backend MPS con chunking de aristas (1M por chunk, float32)
- Validar salida contra `philshiu/Drosophila_brain_model` en un circuito conocido
- Medir y documentar el ratio real de tiempo simulado por segundo de reloj

### Story 1.3 · Calibración y formato de traza
- Implementar `calibrate()` de tasas de reposo (2,5 s sin estímulo)
- Emitir z-scores poblacionales con suavizado EMA a 25 ms
- Definir y versionar el formato de traza JSON
- Chequeo de cordura: verificar 1.800 a 3.200 sinapsis en las motoneuronas elegidas

### Story 1.4 · Controles de honestidad
- Implementar control `erdos_renyi_matched`
- Implementar control `degree_preserving_rewire`
- Implementar control `shuffle_weights`
- Implementar test de cerebro congelado (`z` fijo y `z` ruidoso)

---

## EPIC 2 · art-fly

### Story 2.1 · Canvas 2D y decodificador de pluma (F1)
- Buffer de canvas y deposición con kernel gaussiano
- `PenDecoder` con mapeo fijo, rangos amplios
- Render comparativo de los tres controles de topología
- Manifiesto de procedencia por corrida (hash de datos, semilla, versión)

### Story 2.2 · Cuerpo tethered y pintura 3D (F2)
- Entorno `body` con flybody en Python 3.10
- Escena MuJoCo: mosca fija, lienzo como geom
- IK de garra hacia objetivo con `qpos_from_site_xpos`
- Detección de contacto y deposición sobre el lienzo
- Lienzo móvil (traslación y rotación)
- Export de video con ffmpeg

### Story 2.3 · Guía por concepto con CLIP (F3)
- Integrar `open_clip` en MPS, verificar coseno MPS contra CPU a 1e-3
- Loss de distancia esférica con 16 a 32 cutouts y perspectiva aleatoria
- Loop CMA-ES sobre features neuronales cacheadas
- Test de cerebro congelado sobre cada pieza entrenada

---

## EPIC 3 · music-fly

### Story 3.1 · Puente REAPER (D0)
- Configurar Python 3.12 arm64 en REAPER y verificar arquitectura de ambos
- `fly_listener.py` con drenaje completo de cola por tick
- Protocolo de comandos y cliente UDP del lado de la simulación
- Medir el ritmo real del defer loop

### Story 3.2 · Subgrafo en tiempo real (D1)
- Selección anatómica del subgrafo motor desde motoneuronas de pata del VNC
- Bucle de simulación anclado a reloj monótono, con salteo en vez de deuda

### Story 3.3 · Consola de seis patas (D2)
- Definir zonas de alcance por pata
- `ConsoleDecoder` (378 parámetros)
- Mapeo de contacto a comando de sesión
- Grabación de sesión y comparación contra controles

### Story 3.4 · Lazo cerrado sensorial (D3)
- Emitir nivel de mezcla desde REAPER por UDP
- Inyección mecanosensorial en el simulador
- Límites duros contra oscilación y estancamiento

---

## EPIC 4 · Infraestructura y metodología

### Story 4.1 · Repositorio y convenciones
- Crear repositorio y estructura de carpetas
- Documentar convenciones de git y Jira
- Configurar MCP de Jira con cuenta personal

### Story 4.2 · Entorno
- Liberar espacio en disco hasta 40 GB
- Crear entorno `brain` (Python 3.12)
- Crear entorno `body` (Python 3.10)
- Verificar MPS disponible

---

## Resumen

| Epic | Stories | Subtasks |
|---|---|---|
| 1 · Fundación | 4 | 16 |
| 2 · art-fly | 3 | 14 |
| 3 · music-fly | 4 | 13 |
| 4 · Infraestructura | 2 | 7 |
| **Total** | **13** | **50** |
