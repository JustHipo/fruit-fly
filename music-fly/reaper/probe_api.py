# probe_api.py - diagnostico de una sola vez. Vuelca todos los nombres
# reales disponibles en el modulo reaper_python de ESTA instalacion de
# REAPER a un archivo de texto legible desde fuera. No se deja como parte
# del puente: es para resolver el hallazgo de F0-puente-reaper.md sobre
# RPR_defer ausente, sin adivinar el nombre correcto.

import os
import reaper_python as rp

RAIZ = os.environ.get("FRUITFLY_ROOT", os.path.expanduser("~/fruit-fly"))
out = os.path.join(RAIZ, "out", "music-fly", "f0", "api_dump.txt")
names = sorted(n for n in dir(rp) if not n.startswith("__"))

with open(out, "w") as f:
    f.write("total de nombres: %d\n\n" % len(names))
    f.write("candidatos a loop persistente / salida:\n")
    for n in names:
        low = n.lower()
        if any(k in low for k in ("defer", "loop", "exit", "timer", "tick")):
            f.write("  %s\n" % n)
    f.write("\ntodos los nombres:\n")
    for n in names:
        f.write("%s\n" % n)

rp.RPR_ShowConsoleMsg("probe_api: volcado en %s\n" % out)
