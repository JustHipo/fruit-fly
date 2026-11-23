"""Todo lo autoral de la consola (ARQUITECTURA.md 7.5/7.6): escala, paleta
de instrumentos, paleta de compases. Nada de esto lo decide el cerebro.
"""

from __future__ import annotations

from dataclasses import dataclass

# Escala pentatonica mayor, en semitonos desde la tonica. Dos octavas de
# rango (10 grados) para dar lugar sin que el cerebro tenga que "saber"
# musica: cualquier grado cuantizado cae dentro de la escala por construccion.
PENTATONIC_DEGREES = (0, 2, 4, 7, 9)


def scale_pitch(degree_index: int, base_note: int) -> int:
    """Nota MIDI para el n-esimo grado de la pentatonica, dos octavas."""
    n = len(PENTATONIC_DEGREES)
    octave, degree = divmod(degree_index, n)
    return base_note + PENTATONIC_DEGREES[degree] + 12 * octave


@dataclass(frozen=True)
class Instrument:
    track: int
    name: str          # para TrackFX_AddByName
    base_note: int      # registro
    label: str


# Paleta real, verificada instrumento por instrumento (2026-09-16): se
# enumeraron los plugins realmente instalados en esta maquina (comando
# `listfx`, 282 resultados) y se probo cada candidato con una nota real +
# medicion del pico de audio, no se asumio que sonaban. AUMIDISynth y
# DLSMusicDevice son de Apple (AudioUnit del sistema, no dependen de una
# muestra externa como si dependerian ReaSamplomatic5000 o AUSampler).
# Ya no es "el mismo synth en dos registros" (limitacion declarada de la
# version anterior, ver F2-consola.md) - son tres motores de sonido
# genuinamente distintos.
# base_note separada para cada uno (antes AUMIDISynth y DLSMusicDevice
# compartian 60 - mismo registro exacto, sonaban superpuestos incluso
# siendo timbres distintos). Repartidos cada 6 semitonos para que las 4
# paletas de rango (~21 semitonos cada una, 2 octavas de pentatonica) se
# superpongan lo menos posible entre si.
INSTRUMENTS = (
    Instrument(track=0, name="ReaSynth", base_note=42, label="reasynth_grave"),
    Instrument(track=1, name="ReaSynth", base_note=78, label="reasynth_agudo"),
    Instrument(track=2, name="AUMIDISynth", base_note=54, label="aumidisynth"),
    Instrument(track=3, name="DLSMusicDevice", base_note=66, label="dlsmusicdevice"),
)


@dataclass(frozen=True)
class Meter:
    name: str
    steps_per_bar: int  # simplificacion deliberada: pasos de grilla, no tiempo musical completo


METERS = (
    Meter("4/4", 8),
    Meter("3/4", 6),
    Meter("5/8", 5),
    Meter("7/8", 7),
)

# Piso minimo de espaciado entre notas: un paso de grilla (evita dos notas
# en el mismo instante), no un limite por compas.
#
# Antes esto era MAX_NOTES_PER_BAR=3 (un techo autoral fijo). El test de
# cerebro congelado (ARQUITECTURA.md 11.1) mostro que ese techo dominaba el
# resultado: una version con los mismos valores reales BARAJADOS EN EL
# TIEMPO daba el mismo espaciado exacto entre notas que el real (706+-99ms
# los dos), lo que significa que el enfriamiento decidia el ritmo, no el
# cerebro. Aflojado a proposito para que la frecuencia real de activacion
# decida la densidad, no un numero puesto a ojo. Ver
# music-fly/docs/migraciones/F2-consola.md.
MIN_NOTE_GAP_STEPS = 1
TEMPO_RANGE = (80.0, 160.0)  # bpm
VELOCITY_RANGE = (40, 120)


def remap(value: float, lo: float, hi: float) -> float:
    """value en -1..1 -> lo..hi, lineal."""
    return lo + (value + 1.0) * 0.5 * (hi - lo)


def zone_index(value: float, n_zones: int) -> int:
    """value en -1..1 -> indice de zona 0..n_zones-1, division pareja."""
    idx = int((value + 1.0) * 0.5 * n_zones)
    return max(0, min(n_zones - 1, idx))
