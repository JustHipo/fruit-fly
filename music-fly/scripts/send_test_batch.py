"""Entregable de la Fase 0: proceso EXTERNO (no corre dentro de REAPER) que
manda un lote de comandos y construye una sesion de 4 pistas con un clip
cada una. Verifica el puente completo de punta a punta: este proceso ->
archivo con rename atomico -> fly_listener.lua -> API real de REAPER.

No es UDP (ver music-fly/docs/migraciones/F0-puente-reaper.md, actualizacion
sobre RPR_defer ausente en Python): Lua no trae sockets de fabrica, asi que
el transporte es un archivo por lote dentro de QUEUE_DIR.

Uso:
    python music-fly/scripts/send_test_batch.py
"""

import os
import time

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
QUEUE_DIR = os.path.join(RAIZ, "out", "music-fly", "f0", "queue")


def send_batch(cmds, label):
    print(f"-- {label} ({len(cmds)} comandos) --")
    for c in cmds:
        print(f"   -> {c}")

    ts = time.time_ns()
    tmp_path = os.path.join(QUEUE_DIR, f".tmp-{ts}-{os.getpid()}")
    final_path = os.path.join(QUEUE_DIR, f"{ts}-{os.getpid()}.cmd")

    with open(tmp_path, "w") as f:
        f.write("\n".join(cmds) + "\n")
    os.rename(tmp_path, final_path)  # atomico: el listener nunca ve un archivo a medio escribir


def main():
    os.makedirs(QUEUE_DIR, exist_ok=True)

    send_batch([f"addtrack {i}" for i in range(4)], "crear 4 pistas")
    time.sleep(0.2)

    send_batch([f"additem {i} {i * 2.0} 1.5" for i in range(4)], "un clip por pista")
    time.sleep(0.2)

    send_batch(["moveitem 0 4.0"], "mover el primer clip")

    print(
        "\nListo. Verificar a ojo en REAPER: 4 pistas, un clip de 1.5s cada "
        "una, y el clip de la pista 0 corrido a la posicion 4.0."
    )


if __name__ == "__main__":
    main()
