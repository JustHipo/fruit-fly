"""Version con cuerpo fisico real de compose_from_trace.py. Corre en el
entorno "body" (Python 3.10, flybody+mujoco), a diferencia de
compose_from_trace.py que corre en "brain" (no necesita torch para nada de
esto, solo numpy - por eso la frontera es el archivo de traza, igual que en
art-fly).

Cada una de las seis patas intenta de verdad llegar a su objetivo decodificado
sobre la superficie fisica (reusando el cuerpo tethered de art-fly), y solo
cuenta como "press" si la fisica confirma contacto real - no si el
decodificador simplemente lo pedia. Reporta, como hace paint_3d.py, que
fraccion de los intentos logro contacto real.

Uso:
    source .venv-body/bin/activate
    python music-fly/scripts/compose_with_body.py
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from collections import Counter
from pathlib import Path

logging.getLogger().setLevel(logging.ERROR)  # el solver de IK avisa en cada no-convergencia

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "music-fly"))

from console.body_compose import LEG_ORDER, run_body_trace  # noqa: E402
from console.compose import compose_from_legs  # noqa: E402
from console.vocabulary import INSTRUMENTS  # noqa: E402

TRACE_PATH = REPO / "out/music-fly/f1/live_trace.json"
QUEUE_DIR = REPO / "out/music-fly/f0/queue"


def load_trace_json(path: Path):
    data = json.loads(path.read_text())
    times = [f["t"] for f in data["frames"]]
    z_values = [f["z"] for f in data["frames"]]
    return times, z_values, data["populations"]


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
    times, z_values, populations = load_trace_json(TRACE_PATH)
    print(f"  {len(times)} cuadros, poblaciones: {populations}")

    print("\nArmando el cuerpo tethered y corriendo las seis patas cuadro a cuadro...")
    t0 = time.perf_counter()
    real_sequence, contact_log, physics = run_body_trace(times, z_values, seed=0)
    print(f"  {len(times)} cuadros de fisica real en {time.perf_counter() - t0:.1f}s de reloj real")

    # Estadisticas de contacto real, mismo formato que paint_3d.py de art-fly.
    contacted_counts = Counter(leg for frame in contact_log for leg in frame)
    print("\nContacto real logrado por pata (de los cuadros donde la consola pedia presionar):")
    for leg in LEG_ORDER:
        print(f"  {leg}: {contacted_counts.get(leg, 0)} contactos reales")

    result = compose_from_legs(times, real_sequence)
    print(f"\nCompas elegido: {result.meter_name}")
    print(f"Tempo elegido: {result.tempo_bpm:.1f} bpm")
    print(f"Notas decodificadas (con contacto fisico real): {len(result.notes)}")
    by_instrument = Counter(INSTRUMENTS[n.track].label for n in result.notes)
    print(f"  por instrumento: {dict(by_instrument)}")

    if not result.notes:
        print("\nNinguna pata logro contacto real con el gate abierto. Nada que mandar.")
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
    print("\nListo. Esta vez las seis patas tocaron de verdad la superficie fisica.")


if __name__ == "__main__":
    main()
