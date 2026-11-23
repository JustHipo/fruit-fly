# Plan de implementación

| Fase | Alcance | Estado |
|---|---|---|
| **F0** | Fundación compartida: datos, simulador LIF, calibración, controles | ✅ Completo salvo validación contra philshiu |
| **F1** | art-fly: canvas 2D, decodificador de pluma, controles al lado | ✅ Completo |
| **F2** | art-fly: cuerpo tethered, IK, pintura 3D, video | 🔄 En progreso: pipeline completo con una pata, primer video. Falta seis patas y fuerza de contacto |
| **F3** | art-fly: guía por concepto con CLIP | ⬜ Pendiente |
| **D0** | music-fly: puente REAPER | ⬜ Pendiente |
| **D1** | music-fly: subgrafo en tiempo real | ⬜ Pendiente |
| **D2** | music-fly: consola de seis patas | ⬜ Pendiente |
| **D3** | music-fly: lazo cerrado sensorial | ⬜ Pendiente |

## Orden recomendado

F0 es prerequisito de todo. Después, F1 y D0 pueden ir en paralelo porque no se tocan: F1 es puro Python numérico y D0 es configuración de REAPER.

La ruta más corta a algo mirable es **F0 → F1**. La ruta más corta a algo demostrable con un tercero presente es **F0 → D0 → D1 → D2**.

## Bloqueantes actuales

| Bloqueante | Estado |
|---|---|
| Espacio en disco (se necesitan ~40 GB libres) | 🟡 Parcial: 15 GB libres, alcanzó para F0 |
| MCP de Jira personal configurado | ⬜ Diferido, se trabaja standalone |
| Repositorio creado | ✅ github.com/JustHipo/fruit-fly (privado) |
