"""Primera vez que el cerebro real le dice algo a REAPER: toma la traza en
vivo ya grabada en F1 (out/music-fly/f1/live_trace.json, 15s de subgrafo
motor real corriendo en tiempo real) y la interpreta con el ConsoleDecoder
mas la asignacion de patas de ARQUITECTURA.md 7.6.

La logica de interpretacion vive en console/compose.py (reusada tambien
por test_frozen_brain.py, ver 11.1).

Simplificaciones deliberadas de esta primera version, documentadas como
deuda en music-fly/docs/migraciones/F2-consola.md:
  - Sin cuerpo fisico/IK todavia: los objetivos decodificados se usan
    directo, no pasan por flybody ni por deteccion de contacto real.
  - Tempo y compas se deciden UNA vez para toda la pieza (moda/promedio
    sobre la traza), no varian en vivo.
  - Perillas (T2 derecha) y mute (T3 izquierda) se decodifican pero no se
    envian a REAPER todavia.

Uso:
    source .venv-brain/bin/activate
    python music-fly/scripts/compose_from_trace.py
"""

from __future__ import annotations

import os
import sys
import time
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "music-fly"))

from console.compose import compose  # noqa: E402
from console.vocabulary import INSTRUMENTS  # noqa: E402
from flybrain.trace import Trace  # noqa: E402

TRACE_PATH = REPO / "out/music-fly/f1/live_trace.json"
QUEUE_DIR = REPO / "out/music-fly/f0/queue"


def send(cmds: list[str], label: str) -> None:
    print(f"-- {label} ({len(cmds)} comandos) --")
    ts = time.time_ns()
    tmp = QUEUE_DIR / f".tmp-{ts}"
    final = QUEUE_DIR / f"{ts}.cmd"
    tmp.write_text("\n".join(cmds) + "\n")
    os.rename(tmp, final)
    time.sleep(0.2)


def main() -> None:
    print(f"Cargando traza real de {TRACE_PATH.name}...")
    trace = Trace.load(TRACE_PATH)
    print(f"  {len(trace.times)} cuadros, poblaciones: {trace.populations}")

    result = compose(trace.times, trace.values, seed=0)

    print(f"\nCompas elegido: {result.meter_name}")
    print(f"Tempo elegido: {result.tempo_bpm:.1f} bpm")
    print(f"Notas decodificadas: {len(result.notes)} en {trace.times[-1]:.1f}s de traza")
    by_instrument = Counter(INSTRUMENTS[n.track].label for n in result.notes)
    print(f"  por instrumento: {dict(by_instrument)}")

    if not result.notes:
        print("\nNo se decodifico ninguna nota (el gate de T1L nunca se activo). Nada que mandar.")
        return

    QUEUE_DIR.mkdir(parents=True, exist_ok=True)

    setup = [f"addtrack {inst.track}" for inst in INSTRUMENTS]
    send(setup, "crear pistas de instrumento")

    fx = [f"addfx {inst.track} {inst.name}" for inst in INSTRUMENTS]
    send(fx, "instanciar ReaSynth en cada pista")

    send([f"tempo {result.tempo_bpm:.2f}"], "fijar tempo")

    note_cmds = [
        f"testnote {n.track} {n.start_s:.3f} {n.end_s:.3f} {n.pitch} {n.velocity}"
        for n in result.notes
    ]
    for i in range(0, len(note_cmds), 20):
        send(note_cmds[i:i + 20], f"notas {i}-{min(i + 20, len(note_cmds))}")

    send(["play"], "play")
    print("\nListo. El cerebro real acaba de componer esto.")


if __name__ == "__main__":
    main()
